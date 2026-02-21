#!/usr/bin/env python3
"""
Advanced System & Network Audit
Windows UI app for checking system settings and network connectivity
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import font
import threading
import subprocess
import json
import winreg
import ctypes
import sys
import os

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── Colors ───────────────────────────────────────────────────────────────────
PANEL_BG  = "#252526"
HEADER_BG = "#2d2d2d"
BTN_BG    = "#0078d4"
BTN_HOV   = "#106ebe"
FG        = "#d4d4d4"
FG_DIM    = "#888888"
GREEN     = "#00c853"
RED       = "#f44336"
ORANGE    = "#ff9800"
BLUE      = "#0078d4"
DOT       = "#4fc3f7"

# ── Network targets from picture 3 ───────────────────────────────────────────
NETWORK_TARGETS = {
    "91.217.245.43": [(80, "TCP"), (443, "TCP"), (21, "TCP")],
    "91.217.245.48": [(80, "TCP"), (443, "TCP")],
    "91.217.245.49": [(80, "TCP"), (443, "TCP"), (7774, "TCP")],
    "78.141.207.139": [(80, "TCP")],
    "www.teamviewer.com": [(80, "TCP"), (443, "TCP")],
    "www.splashtop.com": [(80, "TCP"), (443, "TCP")],
}

# ── Windows Settings Checks ───────────────────────────────────────────────────

def run_ps(cmd: str) -> str:
    """Run a PowerShell command and return stdout."""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30, shell=False
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def check_windows_updates() -> tuple[bool, str]:
    """PASS when Automatic Updates are OFF (disabled)."""
    try:
        # Check Windows Update service startup type
        svc = run_ps("(Get-Service -Name wuauserv -ErrorAction SilentlyContinue).StartType")
        if svc.lower() == "disabled":
            return True, ""

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

        # Check via Windows Update AutoUpdate settings
        au_status = run_ps("try { (New-Object -ComObject Microsoft.Update.AutoUpdate).Settings.NotificationLevel } catch { -1 }")
        if au_status.strip() == "1":
            return True, ""

        return False, "Automatic Windows Updates are still enabled. Disable via Settings > Windows Update > Advanced Options."
    except Exception as e:
        return False, f"Could not determine update status: {e}"


def check_antivirus() -> tuple[bool, str]:
    """PASS when no active AV product is detected (or all are disabled)."""
    try:
        av_out = run_ps(
            "try { Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
            "| Select-Object displayName, productState | ConvertTo-Json -Compress } catch { $null }"
        )
        if not av_out or av_out == "null" or av_out == "":
            return True, ""

        products = json.loads(av_out)
        if isinstance(products, dict):
            products = [products]

        active = []
        for p in products:
            state = int(p.get("productState", 0))
            # productState bit 12-15: 0x1000 = enabled, 0x0000 = disabled
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
            "try { Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json -Compress } catch { $null }"
        )
        if not out or out == "null":
            return False, "Could not query firewall status"

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
    """PASS when UAC is OFF (EnableLUA = 0 or ConsentPromptBehaviorAdmin = 0)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System")
        try:
            val, _ = winreg.QueryValueEx(key, "EnableLUA")
            if val == 0:
                winreg.CloseKey(key)
                return True, ""
        except FileNotFoundError:
            pass

        try:
            consent, _ = winreg.QueryValueEx(key, "ConsentPromptBehaviorAdmin")
            if consent == 0:
                winreg.CloseKey(key)
                return True, ""
        except FileNotFoundError:
            pass

        winreg.CloseKey(key)
        return False, "UAC is enabled. Disable via Control Panel > User Accounts > Change UAC settings (set to Never notify)."
    except Exception as e:
        return False, f"Could not read UAC registry value: {e}"


def check_daily_restart() -> tuple[bool, str]:
    """PASS when an Active Hours or scheduled restart task is configured."""
    try:
        # Check if Active Hours are set
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings")
            ah_start, _ = winreg.QueryValueEx(key, "ActiveHoursStart")
            ah_end, _ = winreg.QueryValueEx(key, "ActiveHoursEnd")
            winreg.CloseKey(key)
            return True, f"Active Hours configured: {ah_start:02d}:00 – {ah_end:02d}:00"
        except FileNotFoundError:
            pass

        # Look for a scheduled task named restart or reboot
        tasks = run_ps(
            "Get-ScheduledTask | Where-Object {$_.TaskName -match 'restart|reboot|auto restart'} "
            "| Select-Object -ExpandProperty TaskName"
        )
        if tasks and tasks != "":
            return True, ""

        # Check for Windows built-in scheduled restart feature
        restart_cfg = run_ps("Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings' -Name 'RestartNotificationSnooze' -ErrorAction SilentlyContinue")

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
        if fmt.lower() in ("dd/mm/yyyy", "d/m/yyyy", "dd/mm/yy"):
            return True, ""
        return False, f"Date format is '{fmt}'. Change to DD/MM/YYYY via Settings > Time & Language > Region."
    except Exception as e:
        return False, f"Could not determine date format: {e}"


WINDOWS_CHECKS = [
    ("Firewall OFF",         check_firewall, lambda: run_ps("Start-Process firewall.cpl")),
    ("UAC Settings OFF",     check_uac, lambda: run_ps("Start-Process C:\\Windows\\System32\\UserAccountControlSettings.exe")),
    ("Language: ENGLISH",    check_language, lambda: run_ps("start ms-settings:regionlanguage")),
    ("Date Format: UK",      check_date_format, lambda: run_ps("start ms-settings:regionformatting")),
]


# ── Network Check ─────────────────────────────────────────────────────────────

def check_network_target(host: str, port: int, proto: str) -> tuple[str, str]:
    """Returns ('PASS'|'BLOCK', reason)."""
    try:
        ps_cmd = (
            f"try {{ $r = Test-NetConnection -ComputerName '{host}' -Port {port} "
            f"-InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction SilentlyContinue; "
            f"if ($r) {{ 'PASS' }} else {{ 'BLOCK' }} }} catch {{ 'BLOCK' }}"
        )
        out = run_ps(ps_cmd).strip().upper()
        if out == "PASS":
            return "PASS", ""
        return "BLOCK", f"Connection to {host}:{port} is blocked or unreachable."
    except subprocess.TimeoutExpired:
        return "BLOCK", f"Timed out connecting to {host}:{port}."
    except Exception as e:
        return "BLOCK", str(e)


# ── UI Components ────────────────────────────────────────────────────────────

class NetworkCheckRow(ctk.CTkFrame):
    """A network check row with dropdown for multiple ports"""

    def __init__(self, parent, host: str, ports: list, **kwargs):
        super().__init__(parent, fg_color=PANEL_BG, **kwargs)
        self.grid_columnconfigure(1, weight=1)
        
        self.host = host
        self.ports = ports
        self.expanded = False
        self.port_rows = []
        self.results = {}

        # Main row with expand/collapse button
        self._create_main_row()

    def _create_main_row(self):
        # Expand/Collapse button
        self.toggle_btn = ctk.CTkButton(self, text="+", width=25, height=24,
                                       fg_color="#404040", hover_color="#505050",
                                       text_color="white", font=ctk.CTkFont(size=12),
                                       command=self.toggle_expand)
        self.toggle_btn.grid(row=0, column=0, padx=(12, 6), pady=(2, 0), sticky="w")

        # Host label
        self.host_lbl = ctk.CTkLabel(self, text=self.host, text_color=FG,
                                    font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                    anchor="w")
        self.host_lbl.grid(row=0, column=1, sticky="ew", pady=(2, 0))

        # Overall status label
        self.status_lbl = ctk.CTkLabel(self, text="—", text_color=FG_DIM,
                                       font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                       width=60, anchor="e")
        self.status_lbl.grid(row=0, column=2, padx=(4, 16), pady=(2, 0), sticky="e")

        # Reason label (created dynamically only when needed)
        self.reason_lbl = None

    def toggle_expand(self):
        self.expanded = not self.expanded
        if self.expanded:
            self._show_ports()
            self.toggle_btn.configure(text="-")
        else:
            self._hide_ports()
            self.toggle_btn.configure(text="+")

    def _show_ports(self):
        # Clear existing port rows
        for row in self.port_rows:
            row.destroy()
        self.port_rows.clear()

        # Create port rows
        for i, (port, proto) in enumerate(self.ports):
            port_row = ctk.CTkFrame(self, fg_color="#2a2a2a")
            # Position ports immediately after the main row (row 0) and reason (row 1)
            port_row.grid(row=2+i, column=0, columnspan=3, sticky="ew", padx=(40, 0), pady=(0, 1))
            port_row.grid_columnconfigure(1, weight=1)

            # Port label
            port_lbl = ctk.CTkLabel(port_row, text=f"Port {port} ({proto})", text_color=FG_DIM,
                                    font=ctk.CTkFont(family="Segoe UI", size=11),
                                    anchor="w")
            port_lbl.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=2)

            # Port status
            port_status = ctk.CTkLabel(port_row, text=self.results.get(port, "—"), 
                                      text_color=FG_DIM,
                                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                                      width=60, anchor="e")
            port_status.grid(row=0, column=2, padx=(4, 16), pady=2, sticky="e")
            
            self.port_rows.append(port_row)

    def _hide_ports(self):
        for row in self.port_rows:
            row.destroy()
        self.port_rows.clear()

    def set_result(self, port: int, status: str, reason: str = ""):
        self.results[port] = status
        
        # Update overall status
        passed_count = sum(1 for s in self.results.values() if s == "PASS")
        total_count = len(self.results)
        
        if total_count == 0:
            overall_status = "—"
            overall_color = FG_DIM
        elif passed_count == total_count:
            overall_status = "PASS"
            overall_color = GREEN
        else:
            overall_status = "FAIL"
            overall_color = RED
        
        self.status_lbl.configure(text=overall_status, text_color=overall_color)
        
        # Handle reason label dynamically
        if reason and overall_status == "FAIL":
            if self.reason_lbl is None:
                self.reason_lbl = ctk.CTkLabel(self, text="", text_color=ORANGE,
                                               font=ctk.CTkFont(family="Segoe UI", size=10),
                                               anchor="w", wraplength=280, justify="left")
                self.reason_lbl.grid(row=1, column=1, columnspan=3, sticky="ew",
                                     padx=(4, 16), pady=(0, 2))
            self.reason_lbl.configure(text=f"↳ {reason}")
        else:
            if self.reason_lbl is not None:
                self.reason_lbl.destroy()
                self.reason_lbl = None
        
        # Update port rows if expanded
        if self.expanded:
            self._show_ports()

    def reset(self):
        self.results.clear()
        self.status_lbl.configure(text="—", text_color=FG_DIM)
        if self.reason_lbl is not None:
            self.reason_lbl.destroy()
            self.reason_lbl = None
        if self.expanded:
            self._show_ports()


class CheckRow(ctk.CTkFrame):
    """A single check row: [ACTION] • label ............ STATUS [reason]"""

    def __init__(self, parent, label: str, action_cmd=None, **kwargs):
        super().__init__(parent, fg_color=PANEL_BG, **kwargs)
        self.grid_columnconfigure(2, weight=1)

        # Action button (if provided)
        if action_cmd:
            self.action_btn = ctk.CTkButton(self, text="⚙", width=30, height=24,
                                           fg_color="#404040", hover_color="#505050",
                                           text_color="white", font=ctk.CTkFont(size=12),
                                           command=action_cmd)
            self.action_btn.grid(row=0, column=0, padx=(12, 6), pady=2, sticky="w")
        else:
            self.action_btn = None

        # Bullet
        self.bullet = ctk.CTkLabel(self, text="●", text_color=DOT,
                                   font=ctk.CTkFont(family="Segoe UI", size=10))
        self.bullet.grid(row=0, column=1, padx=(6, 6), pady=2, sticky="w")

        # Check label
        self.lbl = ctk.CTkLabel(self, text=label, text_color=FG,
                                font=ctk.CTkFont(family="Segoe UI", size=12),
                                anchor="w")
        self.lbl.grid(row=0, column=2, sticky="ew", pady=2)

        # Status label
        self.status_lbl = ctk.CTkLabel(self, text="—", text_color=FG_DIM,
                                       font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                                       width=60, anchor="e")
        self.status_lbl.grid(row=0, column=3, padx=(4, 16), pady=2, sticky="e")

        # Reason label (hidden until needed)
        self.reason_lbl = ctk.CTkLabel(self, text="", text_color=ORANGE,
                                       font=ctk.CTkFont(family="Segoe UI", size=10),
                                       anchor="w", wraplength=280, justify="left")
        self.reason_lbl.grid(row=1, column=2, columnspan=2, sticky="ew",
                             padx=(4, 16), pady=(0, 6))

    def set_result(self, status: str, reason: str = ""):
        colour_map = {"PASS": GREEN, "FAIL": RED, "BLOCK": ORANGE, "—": FG_DIM}
        self.status_lbl.configure(text=status, text_color=colour_map.get(status, FG))
        if reason:
            self.reason_lbl.configure(text=f"↳ {reason}")
        else:
            self.reason_lbl.configure(text="")

    def reset(self):
        self.status_lbl.configure(text="—", text_color=FG_DIM)
        self.reason_lbl.configure(text="")


class SectionPanel(ctk.CTkFrame):
    """Left or right panel with title, progress bar, rows, and a button."""

    def __init__(self, parent, title: str, btn_text: str, btn_cmd, **kwargs):
        super().__init__(parent, fg_color=PANEL_BG, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Title
        self.title_lbl = ctk.CTkLabel(self, text=title, text_color="white",
                                      font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.title_lbl.grid(row=0, column=0, pady=(24, 12), padx=20)

        # Progress bar frame
        pb_frame = ctk.CTkFrame(self, fg_color=HEADER_BG, height=10, corner_radius=2)
        pb_frame.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 4))
        pb_frame.grid_propagate(False)
        pb_frame.grid_columnconfigure(0, weight=1)

        # Percentage label
        self.pct_lbl = ctk.CTkLabel(self, text="", text_color=FG_DIM,
                                    font=ctk.CTkFont(family="Segoe UI", size=11))
        self.pct_lbl.grid(row=2, column=0, pady=(0, 8))

        # Canvas for custom progress bar
        self.pb_canvas = tk.Canvas(pb_frame, bg=HEADER_BG, highlightthickness=0, height=10)
        self.pb_canvas.grid(row=0, column=0, sticky="ew")
        self.pb_fill = None
        self.update_progress(0)

        # Scrollable rows area
        self.rows_frame = ctk.CTkScrollableFrame(self, fg_color=PANEL_BG,
                                                  scrollbar_button_color=HEADER_BG,
                                                  scrollbar_button_hover_color=BTN_HOV)
        self.rows_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)
        self.rows_frame.grid_columnconfigure(0, weight=1)

        # Button at bottom
        self.btn = ctk.CTkButton(self, text=btn_text, fg_color=BTN_BG,
                                 hover_color=BTN_HOV, text_color="white",
                                 font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                                 height=42, corner_radius=0, command=btn_cmd)
        self.btn.grid(row=4, column=0, sticky="ew", padx=24, pady=(8, 24))

    def update_progress(self, pct: int):
        self.pb_canvas.delete("all")
        width = self.pb_canvas.winfo_width()
        if width < 10:
            width = 350
        fill_width = int(width * (pct / 100))
        if fill_width > 0:
            self.pb_canvas.create_rectangle(0, 0, fill_width, 10, fill=BLUE, outline="")
        self.pct_lbl.configure(text=f"{pct}%" if pct > 0 else "")

    def reset_progress(self):
        self.update_progress(0)


# ── Main Application ───────────────────────────────────────────────────────────

class AuditApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Music Concierge SOB Checklists")
        self.configure(fg_color="#1e1e1e")
        self.resizable(True, True)
        self.minsize(960, 620)

        # Set creative custom icon
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'music_concierge_icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass  # Continue without icon if it fails

        self._center_window(1100, 720)
        self._build_ui()

    def _center_window(self, w: int, h: int):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # Two-column layout
        main = ctk.CTkFrame(self, fg_color="#1e1e1e")
        main.pack(fill="both", expand=True, padx=16, pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # ── Left panel: Windows Settings ──────────────────────────────────────
        self.win_panel = SectionPanel(
            main, "Windows Settings", "CHECK WINDOWS", self._run_windows_checks
        )
        self.win_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.win_rows: list[CheckRow] = []
        for label, fn, action_cmd in WINDOWS_CHECKS:
            row = CheckRow(self.win_panel.rows_frame, label, action_cmd)
            row.pack(fill="x", pady=1)
            self.win_rows.append(row)

        # ── Right panel: Network Connectivity ─────────────────────────────────
        self.net_panel = SectionPanel(
            main, "Network Connectivity", "CHECK NETWORK", self._run_network_checks
        )
        self.net_panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.net_rows: list[NetworkCheckRow] = []
        for host, ports in NETWORK_TARGETS.items():
            row = NetworkCheckRow(self.net_panel.rows_frame, host, ports)
            row.pack(fill="x")
            self.net_rows.append(row)

    # ── Windows checks ────────────────────────────────────────────────────────

    def _run_windows_checks(self):
        self.win_panel.btn.configure(state="disabled", text="Checking...")
        for r in self.win_rows:
            r.reset()
        self.win_panel.reset_progress()
        threading.Thread(target=self._windows_worker, daemon=True).start()

    def _windows_worker(self):
        total = len(WINDOWS_CHECKS)
        for i, (label, fn, action_cmd) in enumerate(WINDOWS_CHECKS):
            try:
                passed, reason = fn()
            except Exception as e:
                passed, reason = False, str(e)

            status = "PASS" if passed else "FAIL"
            row = self.win_rows[i]
            self.after(0, row.set_result, status, reason)
            self.after(0, self.win_panel.update_progress, int((i + 1) / total * 100))

        self.after(0, lambda: self.win_panel.btn.configure(state="normal", text="CHECK WINDOWS"))

    # ── Network checks ────────────────────────────────────────────────────────

    def _run_network_checks(self):
        self.net_panel.btn.configure(state="disabled", text="Checking...")
        for r in self.net_rows:
            r.reset()
        self.net_panel.reset_progress()
        threading.Thread(target=self._network_worker, daemon=True).start()

    def _network_worker(self):
        total_targets = sum(len(ports) for ports in NETWORK_TARGETS.values())
        checked_count = 0
        
        for i, (host, ports) in enumerate(NETWORK_TARGETS.items()):
            row = self.net_rows[i]
            
            for port, proto in ports:
                status, reason = check_network_target(host, port, proto)
                self.after(0, row.set_result, port, status, reason)
                checked_count += 1
                self.after(0, self.net_panel.update_progress, int(checked_count / total_targets * 100))

        self.after(0, lambda: self.net_panel.btn.configure(state="normal", text="CHECK NETWORK"))


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AuditApp()
    app.mainloop()
