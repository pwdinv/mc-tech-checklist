import tkinter as tk
from tkinter import ttk, font
import threading
import subprocess
import json
import winreg
import ctypes
import locale
import datetime
import sys
import os

# ── Colours ──────────────────────────────────────────────────────────────────
BG        = "#1e1e1e"
PANEL_BG  = "#252526"
HEADER_BG = "#2d2d2d"
BTN_BG    = "#0078d4"
BTN_HOV   = "#005fa3"
FG        = "#d4d4d4"
FG_DIM    = "#888888"
GREEN     = "#00c853"
RED       = "#f44336"
ORANGE    = "#ff9800"
BLUE      = "#0078d4"
DOT       = "#4fc3f7"

# ── Network targets from picture 3 ───────────────────────────────────────────
NETWORK_TARGETS = [
    # (label, host, port, protocol)
    ("91.217.245.43 (80)",   "91.217.245.43",  80,   "TCP"),
    ("91.217.245.43 (443)",  "91.217.245.43",  443,  "TCP"),
    ("91.217.245.43 (7774)", "91.217.245.43",  7774, "TCP"),
    ("91.217.245.43 (20)",   "91.217.245.43",  20,   "TCP"),
    ("91.217.245.43 (21)",   "91.217.245.43",  21,   "TCP"),
    ("91.217.245.48 (80)",   "91.217.245.48",  80,   "TCP"),
    ("91.217.245.48 (443)",  "91.217.245.48",  443,  "TCP"),
    ("91.217.245.48 (7774)", "91.217.245.48",  7774, "TCP"),
    ("91.217.245.49 (80)",   "91.217.245.49",  80,   "TCP"),
    ("91.217.245.49 (443)",  "91.217.245.49",  443,  "TCP"),
    ("91.217.245.49 (7774)", "91.217.245.49",  7774, "TCP"),
    ("78.141.207.139 (80)",  "78.141.207.139", 80,   "TCP"),
    ("www.teamviewer.com (80)",  "www.teamviewer.com",  80,  "TCP"),
    ("www.teamviewer.com (443)", "www.teamviewer.com",  443, "TCP"),
    ("www.splashtop.com (80)",   "www.splashtop.com",   80,  "TCP"),
    ("www.splashtop.com (443)",  "www.splashtop.com",   443, "TCP"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_ps(cmd: str) -> str:
    """Run a PowerShell command and return stdout."""
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  Windows Settings Checks
# ══════════════════════════════════════════════════════════════════════════════

def check_windows_updates() -> tuple[bool, str]:
    """PASS when Automatic Updates are OFF (disabled)."""
    try:
        # Check Windows Update service startup type
        svc = run_ps("(Get-Service -Name wuauserv).StartType")
        # Check AU registry key
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU")
            no_auto, _ = winreg.QueryValueEx(key, "NoAutoUpdate")
            winreg.CloseKey(key)
            if no_auto == 1:
                return True, ""
        except FileNotFoundError:
            pass

        # Check via scheduled task / service
        if svc.lower() in ("disabled",):
            return True, ""

        # Check via PowerShell Get-WindowsUpdateLog / UsoClient
        au_status = run_ps(
            "(New-Object -ComObject Microsoft.Update.AutoUpdate).Settings.NotificationLevel"
        )
        # NotificationLevel 1 = disabled
        if au_status.strip() == "1":
            return True, ""

        return False, "Automatic Windows Updates are still enabled. Disable via Settings > Windows Update > Advanced Options."
    except Exception as e:
        return False, f"Could not determine update status: {e}"


def check_antivirus() -> tuple[bool, str]:
    """PASS when no active AV product is detected (or all are disabled)."""
    try:
        av_out = run_ps(
            "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
            "| Select-Object displayName, productState | ConvertTo-Json -Compress"
        )
        if not av_out or av_out == "null":
            return True, ""

        products = json.loads(av_out)
        if isinstance(products, dict):
            products = [products]

        active = []
        for p in products:
            state = int(p.get("productState", 0))
            # productState bit 12-19: 0x1000 = enabled, 0x0000 = disabled
            enabled = (state >> 12) & 0xF
            if enabled != 0:
                active.append(p.get("displayName", "Unknown AV"))

        if not active:
            return True, ""
        return False, f"Active AV detected: {', '.join(active)}. Disable or uninstall before proceeding."
    except Exception as e:
        return False, f"Could not query antivirus status: {e}"


def check_firewall() -> tuple[bool, str]:
    """PASS when all firewall profiles are OFF."""
    try:
        out = run_ps(
            "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json -Compress"
        )
        profiles = json.loads(out)
        if isinstance(profiles, dict):
            profiles = [profiles]

        enabled_profiles = [p["Name"] for p in profiles if p.get("Enabled")]
        if not enabled_profiles:
            return True, ""
        return False, f"Firewall enabled on: {', '.join(enabled_profiles)}. Turn off via Windows Defender Firewall."
    except Exception as e:
        return False, f"Could not query firewall status: {e}"


def check_uac() -> tuple[bool, str]:
    """PASS when UAC is OFF (EnableLUA = 0)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
        val, _ = winreg.QueryValueEx(key, "EnableLUA")
        winreg.CloseKey(key)
        if val == 0:
            return True, ""
        return False, "UAC is enabled. Disable via Control Panel > User Accounts > Change UAC settings (set to Never notify)."
    except Exception as e:
        return False, f"Could not read UAC registry value: {e}"


def check_daily_restart() -> tuple[bool, str]:
    """PASS when an Active Hours or scheduled restart task is configured."""
    try:
        # Check if Active Hours are set (a proxy for scheduled restart awareness)
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings")
            ah_start, _ = winreg.QueryValueEx(key, "ActiveHoursStart")
            ah_end,   _ = winreg.QueryValueEx(key, "ActiveHoursEnd")
            winreg.CloseKey(key)
            return True, f"Active Hours configured: {ah_start:02d}:00 – {ah_end:02d}:00"
        except FileNotFoundError:
            pass

        # Fallback: look for a scheduled task named *restart* or *reboot*
        tasks = run_ps(
            "Get-ScheduledTask | Where-Object {$_.TaskName -match 'restart|reboot'} "
            "| Select-Object -ExpandProperty TaskName"
        )
        if tasks:
            return True, ""

        return False, "No daily restart schedule found. Configure Active Hours or a scheduled restart task."
    except Exception as e:
        return False, f"Could not check restart schedule: {e}"


def check_language() -> tuple[bool, str]:
    """PASS when the UI language is English."""
    try:
        lang = run_ps("(Get-Culture).Name")
        if lang.lower().startswith("en"):
            return True, ""
        return False, f"System language is '{lang}'. Change to English via Settings > Time & Language > Language."
    except Exception as e:
        return False, f"Could not determine system language: {e}"


def check_date_format() -> tuple[bool, str]:
    """PASS when short date format is DD/MM/YYYY (UK)."""
    try:
        fmt = run_ps("(Get-Culture).DateTimeFormat.ShortDatePattern")
        if fmt.lower() in ("dd/mm/yyyy", "d/m/yyyy"):
            return True, ""
        return False, f"Date format is '{fmt}'. Change to DD/MM/YYYY via Settings > Time & Language > Region."
    except Exception as e:
        return False, f"Could not determine date format: {e}"


WINDOWS_CHECKS = [
    ("Updates OFF",          check_windows_updates),
    ("Anti-Virus OFF",       check_antivirus),
    ("Firewall OFF",         check_firewall),
    ("UAC Settings OFF",     check_uac),
    ("Daily Restart",        check_daily_restart),
    ("Language: ENGLISH",    check_language),
    ("Date Format: UK",      check_date_format),
]


# ══════════════════════════════════════════════════════════════════════════════
#  Network Check
# ══════════════════════════════════════════════════════════════════════════════

def check_network_target(host: str, port: int, proto: str) -> tuple[str, str]:
    """Returns ('PASS'|'BLOCK', reason)."""
    try:
        ps_cmd = (
            f"$r = Test-NetConnection -ComputerName '{host}' -Port {port} "
            f"-InformationLevel Quiet -WarningAction SilentlyContinue; "
            f"if ($r) {{ 'PASS' }} else {{ 'BLOCK' }}"
        )
        out = run_ps(ps_cmd).strip().upper()
        if out == "PASS":
            return "PASS", ""
        return "BLOCK", f"Connection to {host}:{port} is blocked or unreachable."
    except subprocess.TimeoutExpired:
        return "BLOCK", f"Timed out connecting to {host}:{port}."
    except Exception as e:
        return "BLOCK", str(e)


# ══════════════════════════════════════════════════════════════════════════════
#  UI Components
# ══════════════════════════════════════════════════════════════════════════════

class CheckRow(tk.Frame):
    """A single check row: bullet • label ............ STATUS [reason]"""

    def __init__(self, parent, label: str, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)
        self.columnconfigure(1, weight=1)

        # Bullet
        tk.Label(self, text="●", fg=DOT, bg=PANEL_BG,
                 font=("Segoe UI", 9)).grid(row=0, column=0, padx=(8, 4), pady=2, sticky="w")

        # Check label
        self.lbl = tk.Label(self, text=label, fg=FG, bg=PANEL_BG,
                            font=("Segoe UI", 10), anchor="w")
        self.lbl.grid(row=0, column=1, sticky="ew", pady=2)

        # Status label
        self.status_lbl = tk.Label(self, text="—", fg=FG_DIM, bg=PANEL_BG,
                                   font=("Segoe UI", 10, "bold"), width=6, anchor="e")
        self.status_lbl.grid(row=0, column=2, padx=(4, 12), pady=2, sticky="e")

        # Reason label (hidden until needed)
        self.reason_lbl = tk.Label(self, text="", fg=ORANGE, bg=PANEL_BG,
                                   font=("Segoe UI", 8), anchor="w",
                                   wraplength=340, justify="left")
        self.reason_lbl.grid(row=1, column=1, columnspan=2, sticky="ew",
                             padx=(4, 12), pady=(0, 4))

    def set_result(self, status: str, reason: str = ""):
        colour_map = {"PASS": GREEN, "FAIL": RED, "BLOCK": ORANGE, "—": FG_DIM}
        self.status_lbl.config(text=status, fg=colour_map.get(status, FG))
        if reason:
            self.reason_lbl.config(text=f"  ↳ {reason}")
        else:
            self.reason_lbl.config(text="")

    def reset(self):
        self.status_lbl.config(text="—", fg=FG_DIM)
        self.reason_lbl.config(text="")


class SectionPanel(tk.Frame):
    """Left or right panel with title, progress bar, rows, and a button."""

    def __init__(self, parent, title: str, btn_text: str, btn_cmd, **kwargs):
        super().__init__(parent, bg=PANEL_BG, **kwargs)

        # Title
        tk.Label(self, text=title, fg=FG, bg=PANEL_BG,
                 font=("Segoe UI", 14, "bold")).pack(pady=(24, 8))

        # Progress bar
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor=HEADER_BG, background=BLUE,
                        bordercolor=PANEL_BG, lightcolor=BLUE, darkcolor=BLUE)

        pb_frame = tk.Frame(self, bg=PANEL_BG)
        pb_frame.pack(fill="x", padx=24, pady=(0, 2))
        self.pb = ttk.Progressbar(pb_frame, style="Blue.Horizontal.TProgressbar",
                                  orient="horizontal", mode="determinate", length=400)
        self.pb.pack(fill="x")

        self.pct_lbl = tk.Label(self, text="", fg=FG_DIM, bg=PANEL_BG,
                                font=("Segoe UI", 8))
        self.pct_lbl.pack()

        # Scrollable rows area
        self.rows_frame = tk.Frame(self, bg=PANEL_BG)
        self.rows_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Button at bottom
        self.btn = tk.Button(self, text=btn_text, bg=BTN_BG, fg="white",
                             font=("Segoe UI", 11, "bold"),
                             relief="flat", cursor="hand2",
                             activebackground=BTN_HOV, activeforeground="white",
                             command=btn_cmd, pady=10)
        self.btn.pack(fill="x", padx=24, pady=(8, 24))
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=BTN_HOV))
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=BTN_BG))

    def set_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self.pb["value"] = pct
        self.pct_lbl.config(text=f"{pct}%")

    def reset_progress(self):
        self.pb["value"] = 0
        self.pct_lbl.config(text="")


# ══════════════════════════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════════════════════════

class AuditApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Advanced System & Network Audit")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 560)

        # Try to set window icon (ignore if missing)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._build_ui()
        self.update_idletasks()
        self._center_window(1060, 680)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _center_window(self, w: int, h: int):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Admin warning banner
        if not is_admin():
            banner = tk.Label(
                self,
                text="⚠  Run as Administrator for full accuracy  ⚠",
                bg="#5c3a00", fg=ORANGE,
                font=("Segoe UI", 9, "bold"), pady=4
            )
            banner.pack(fill="x")

        # Two-column layout
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=8)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # ── Left panel: Windows Settings ──────────────────────────────────────
        self.win_panel = SectionPanel(
            main, "Windows Settings", "CHECK WINDOWS", self._run_windows_checks
        )
        self.win_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.win_rows: list[CheckRow] = []
        for label, _ in WINDOWS_CHECKS:
            row = CheckRow(self.win_panel.rows_frame, label)
            row.pack(fill="x", pady=1)
            self.win_rows.append(row)

        # ── Right panel: Network Connectivity ─────────────────────────────────
        self.net_panel = SectionPanel(
            main, "Network Connectivity", "CHECK NETWORK", self._run_network_checks
        )
        self.net_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.net_rows: list[CheckRow] = []
        for label, host, port, proto in NETWORK_TARGETS:
            row = CheckRow(self.net_panel.rows_frame, label)
            row.pack(fill="x", pady=1)
            self.net_rows.append(row)

    # ── Windows checks ────────────────────────────────────────────────────────

    def _run_windows_checks(self):
        self.win_panel.btn.config(state="disabled", text="Checking…")
        for r in self.win_rows:
            r.reset()
        self.win_panel.reset_progress()
        threading.Thread(target=self._windows_worker, daemon=True).start()

    def _windows_worker(self):
        total = len(WINDOWS_CHECKS)
        for i, (label, fn) in enumerate(WINDOWS_CHECKS):
            try:
                passed, reason = fn()
            except Exception as e:
                passed, reason = False, str(e)

            status = "PASS" if passed else "FAIL"
            row = self.win_rows[i]
            self.after(0, row.set_result, status, reason)
            self.after(0, self.win_panel.set_progress, i + 1, total)

        self.after(0, self.win_panel.btn.config,
                   {"state": "normal", "text": "CHECK WINDOWS"})

    # ── Network checks ────────────────────────────────────────────────────────

    def _run_network_checks(self):
        self.net_panel.btn.config(state="disabled", text="Checking…")
        for r in self.net_rows:
            r.reset()
        self.net_panel.reset_progress()
        threading.Thread(target=self._network_worker, daemon=True).start()

    def _network_worker(self):
        total = len(NETWORK_TARGETS)
        for i, (label, host, port, proto) in enumerate(NETWORK_TARGETS):
            status, reason = check_network_target(host, port, proto)
            row = self.net_rows[i]
            self.after(0, row.set_result, status, reason)
            self.after(0, self.net_panel.set_progress, i + 1, total)

        self.after(0, self.net_panel.btn.config,
                   {"state": "normal", "text": "CHECK NETWORK"})


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = AuditApp()
    app.mainloop()
