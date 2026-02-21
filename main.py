#!/usr/bin/env python3
"""
Music Concierge Tech Checklist
A Windows-based UI application for technical checklist management
"""

import customtkinter as ctk
import json
import os
from datetime import datetime

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TechChecklistApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Music Concierge Tech Checklist")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Data file for storing checklist state
        self.data_file = "checklist_data.json"
        self.checklist_data = self.load_checklist_data()
        
        self.setup_ui()
        
    def load_checklist_data(self):
        """Load checklist data from JSON file"""
        default_data = {
            "categories": [
                {
                    "name": "System Startup",
                    "items": [
                        {"id": 1, "text": "Check power supplies and connections", "checked": False},
                        {"id": 2, "text": "Verify network connectivity", "checked": False},
                        {"id": 3, "text": "Start core services", "checked": False},
                        {"id": 4, "text": "Check system resources", "checked": False}
                    ]
                },
                {
                    "name": "Audio System",
                    "items": [
                        {"id": 5, "text": "Test audio outputs", "checked": False},
                        {"id": 6, "text": "Verify audio levels", "checked": False},
                        {"id": 7, "text": "Check audio routing", "checked": False},
                        {"id": 8, "text": "Test emergency audio", "checked": False}
                    ]
                },
                {
                    "name": "Content Management",
                    "items": [
                        {"id": 9, "text": "Verify content library integrity", "checked": False},
                        {"id": 10, "text": "Check scheduled content", "checked": False},
                        {"id": 11, "text": "Verify backup systems", "checked": False},
                        {"id": 12, "text": "Test content delivery", "checked": False}
                    ]
                },
                {
                    "name": "Safety & Security",
                    "items": [
                        {"id": 13, "text": "Check emergency systems", "checked": False},
                        {"id": 14, "text": "Verify security protocols", "checked": False},
                        {"id": 15, "text": "Test alarm systems", "checked": False},
                        {"id": 16, "text": "Check fire safety equipment", "checked": False}
                    ]
                }
            ]
        }
        
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return default_data
        return default_data
    
    def save_checklist_data(self):
        """Save checklist data to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.checklist_data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")
    
    def setup_ui(self):
        """Setup the main UI components"""
        # Main container
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.setup_header()
        
        # Content area
        self.content_frame = ctk.CTkFrame(self.main_frame)
        self.content_frame.pack(fill="both", expand=True, pady=(20, 0))
        
        # Create checklist sections
        self.create_checklist_sections()
        
        # Footer with actions
        self.setup_footer()
    
    def setup_header(self):
        """Setup the header section"""
        header_frame = ctk.CTkFrame(self.main_frame)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="🎵 Music Concierge Tech Checklist",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(side="left", padx=20, pady=15)
        
        # Progress indicator
        self.progress_label = ctk.CTkLabel(
            header_frame,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.progress_label.pack(side="right", padx=20, pady=15)
        
        self.update_progress()
    
    def create_checklist_sections(self):
        """Create checklist sections for each category"""
        # Scrollable frame for checklist items
        self.scroll_frame = ctk.CTkScrollableFrame(self.content_frame)
        self.scroll_frame.pack(fill="both", expand=True)
        
        self.checkboxes = {}
        
        for category in self.checklist_data["categories"]:
            # Category frame
            cat_frame = ctk.CTkFrame(self.scroll_frame)
            cat_frame.pack(fill="x", padx=10, pady=10)
            
            # Category header
            cat_header = ctk.CTkFrame(cat_frame)
            cat_header.pack(fill="x", padx=10, pady=10)
            
            cat_label = ctk.CTkLabel(
                cat_header,
                text=category["name"],
                font=ctk.CTkFont(size=18, weight="bold")
            )
            cat_label.pack(side="left", padx=10, pady=10)
            
            # Category progress
            cat_progress = self.calculate_category_progress(category)
            cat_progress_label = ctk.CTkLabel(
                cat_header,
                text=f"{cat_progress['completed']}/{cat_progress['total']} ({cat_progress['percentage']}%)",
                font=ctk.CTkFont(size=12),
                text_color="#888888"
            )
            cat_progress_label.pack(side="right", padx=10, pady=10)
            
            # Checklist items
            for item in category["items"]:
                item_frame = ctk.CTkFrame(cat_frame)
                item_frame.pack(fill="x", padx=10, pady=5)
                
                checkbox = ctk.CTkCheckBox(
                    item_frame,
                    text=item["text"],
                    font=ctk.CTkFont(size=14),
                    command=lambda cat=category, itm=item, cb=None: self.toggle_item(cat, itm)
                )
                checkbox.pack(side="left", padx=15, pady=8)
                
                # Store checkbox reference
                self.checkboxes[item["id"]] = checkbox
                
                # Set initial state
                if item["checked"]:
                    checkbox.select()
    
    def toggle_item(self, category, item):
        """Toggle checklist item and save state"""
        item["checked"] = not item["checked"]
        self.save_checklist_data()
        self.update_progress()
    
    def calculate_category_progress(self, category):
        """Calculate progress for a category"""
        total = len(category["items"])
        completed = sum(1 for item in category["items"] if item["checked"])
        percentage = int((completed / total) * 100) if total > 0 else 0
        return {"total": total, "completed": completed, "percentage": percentage}
    
    def calculate_total_progress(self):
        """Calculate overall progress"""
        total_items = 0
        completed_items = 0
        
        for category in self.checklist_data["categories"]:
            total_items += len(category["items"])
            completed_items += sum(1 for item in category["items"] if item["checked"])
        
        percentage = int((completed_items / total_items) * 100) if total_items > 0 else 0
        return {"total": total_items, "completed": completed_items, "percentage": percentage}
    
    def update_progress(self):
        """Update progress display"""
        progress = self.calculate_total_progress()
        self.progress_label.configure(
            text=f"Progress: {progress['completed']}/{progress['total']} ({progress['percentage']}%)"
        )
    
    def setup_footer(self):
        """Setup footer with action buttons"""
        footer_frame = ctk.CTkFrame(self.main_frame)
        footer_frame.pack(fill="x", pady=(20, 0))
        
        # Action buttons
        button_frame = ctk.CTkFrame(footer_frame)
        button_frame.pack(pady=15)
        
        # Reset all button
        reset_btn = ctk.CTkButton(
            button_frame,
            text="Reset All",
            command=self.reset_all,
            fg_color="#FF5722",
            hover_color="#FF7043"
        )
        reset_btn.pack(side="left", padx=10)
        
        # Complete all button
        complete_btn = ctk.CTkButton(
            button_frame,
            text="Complete All",
            command=self.complete_all,
            fg_color="#4CAF50",
            hover_color="#66BB6A"
        )
        complete_btn.pack(side="left", padx=10)
        
        # Export button
        export_btn = ctk.CTkButton(
            button_frame,
            text="Export Report",
            command=self.export_report
        )
        export_btn.pack(side="left", padx=10)
        
        # Last saved timestamp
        self.timestamp_label = ctk.CTkLabel(
            footer_frame,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#888888"
        )
        self.timestamp_label.pack(pady=5)
        self.update_timestamp()
    
    def reset_all(self):
        """Reset all checklist items"""
        for category in self.checklist_data["categories"]:
            for item in category["items"]:
                item["checked"] = False
        
        self.save_checklist_data()
        self.refresh_checklist()
        self.update_progress()
        self.update_timestamp()
    
    def complete_all(self):
        """Mark all checklist items as complete"""
        for category in self.checklist_data["categories"]:
            for item in category["items"]:
                item["checked"] = True
        
        self.save_checklist_data()
        self.refresh_checklist()
        self.update_progress()
        self.update_timestamp()
    
    def refresh_checklist(self):
        """Refresh the checklist display"""
        # Clear existing checkboxes
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        # Recreate checklist sections
        self.create_checklist_sections()
    
    def export_report(self):
        """Export checklist report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tech_checklist_report_{timestamp}.txt"
        
        try:
            with open(filename, 'w') as f:
                f.write("Music Concierge Tech Checklist Report\n")
                f.write("=" * 50 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                total_progress = self.calculate_total_progress()
                f.write(f"Overall Progress: {total_progress['completed']}/{total_progress['total']} ({total_progress['percentage']}%)\n\n")
                
                for category in self.checklist_data["categories"]:
                    cat_progress = self.calculate_category_progress(category)
                    f.write(f"{category['name']}: {cat_progress['completed']}/{cat_progress['total']} ({cat_progress['percentage']}%)\n")
                    
                    for item in category["items"]:
                        status = "✓" if item["checked"] else "✗"
                        f.write(f"  {status} {item['text']}\n")
                    f.write("\n")
            
            # Show success message
            dialog = ctk.CTkInputDialog(
                text=f"Report exported successfully!\n\nFile saved as:\n{filename}",
                title="Export Complete"
            )
            dialog.get_input()
            
        except Exception as e:
            # Show error message
            dialog = ctk.CTkInputDialog(
                text=f"Error exporting report:\n{str(e)}",
                title="Export Error"
            )
            dialog.get_input()
    
    def update_timestamp(self):
        """Update last saved timestamp"""
        if os.path.exists(self.data_file):
            timestamp = os.path.getmtime(self.data_file)
            last_saved = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            self.timestamp_label.configure(text=f"Last saved: {last_saved}")
    
    def run(self):
        """Run the application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = TechChecklistApp()
    app.run()
