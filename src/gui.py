import os
import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import time
import threading
import cv2
import numpy as np
from PIL import Image, ImageTk
import calendar
import webbrowser

# Calendar widget for schedule view
from tkcalendar import Calendar

class MedicineReminderApp:
    """
    Main GUI class for the Medicine Reminder Application.
    """
    
    def __init__(self, root, db_manager, notifier, telegram_bot, drive_sync, pharmacy_locator, 
                 calendar_integration, sheets_integration, xai_assistant):
        """
        Initialize the GUI.
        
        Args:
            root: Tkinter root window
            db_manager: Database manager instance
            notifier: Notification manager instance
            telegram_bot: Telegram bot instance
            drive_sync: Google Drive sync instance
            pharmacy_locator: Pharmacy locator instance
            calendar_integration: Google Calendar integration instance
            sheets_integration: Google Sheets integration instance
            xai_assistant: XAI Assistant instance for AI features
        """
        self.logger = logging.getLogger(__name__)
        self.root = root
        self.db_manager = db_manager
        self.notifier = notifier
        self.telegram_bot = telegram_bot
        self.drive_sync = drive_sync
        self.pharmacy_locator = pharmacy_locator
        self.calendar_integration = calendar_integration
        self.sheets_integration = sheets_integration
        self.xai_assistant = xai_assistant
        
        # Set up the main window
        self.root.title("Medicine Reminder")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Variables for camera/scanning
        self.camera_active = False
        self.cap = None
        self.camera_thread = None
        self.stop_camera_flag = threading.Event()
        
        # Variables for form fields
        self.medicine_name_var = tk.StringVar()
        self.barcode_var = tk.StringVar()
        self.dosage_var = tk.StringVar()
        self.expiry_date_var = tk.StringVar()
        self.doses_remaining_var = tk.StringVar()
        self.notes_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.radius_var = tk.StringVar(value="5")  # Default 5 km
        
        # Variables for AI assistant
        self.ai_medicine_var = tk.StringVar()
        self.ai_query_var = tk.StringVar()
        self.ai_result_text = None  # Will be a Text widget
        
        # Create the tab control
        self.tab_control = ttk.Notebook(self.root)
        
        # Create tabs
        self.home_tab = ttk.Frame(self.tab_control)
        self.medicines_tab = ttk.Frame(self.tab_control)
        self.schedule_tab = ttk.Frame(self.tab_control)
        self.scan_tab = ttk.Frame(self.tab_control)
        self.pharmacy_tab = ttk.Frame(self.tab_control)
        self.ai_assistant_tab = ttk.Frame(self.tab_control)  # New AI Assistant tab
        self.settings_tab = ttk.Frame(self.tab_control)
        
        # Add tabs to the notebook
        self.tab_control.add(self.home_tab, text="Home")
        self.tab_control.add(self.medicines_tab, text="Medicines")
        self.tab_control.add(self.schedule_tab, text="Schedule")
        self.tab_control.add(self.scan_tab, text="Scan")
        self.tab_control.add(self.pharmacy_tab, text="Find Pharmacy")
        self.tab_control.add(self.ai_assistant_tab, text="AI Assistant")  # New AI Assistant tab
        self.tab_control.add(self.settings_tab, text="Settings")
        
        self.tab_control.pack(expand=1, fill="both")
        
        # Set up each tab
        self.setup_home_tab()
        self.setup_medicines_tab()
        self.setup_schedule_tab()
        self.setup_scan_tab()
        self.setup_pharmacy_tab()
        self.setup_ai_assistant_tab()  # Setup the AI assistant tab
        self.setup_settings_tab()
        
        # Add event for tab change
        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_change)
        
        # Load data for the first time
        self.refresh_medicine_list()
        self.refresh_home_tab()
        self.refresh_schedule_tab()
        
        self.logger.info("GUI initialized")
        
    def on_tab_change(self, event):
        """
        Handle tab change events.
        
        Args:
            event: The tab change event
        """
        tab_id = self.tab_control.select()
        tab_name = self.tab_control.tab(tab_id, "text")
        
        if tab_name == "Home":
            self.refresh_home_tab()
        elif tab_name == "Medicines":
            self.refresh_medicine_list()
        elif tab_name == "Schedule":
            self.refresh_schedule_tab()
        elif tab_name == "Scan":
            # If entering scan tab, prepare camera
            if not self.camera_active:
                self.prepare_camera()
        elif tab_name == "Find Pharmacy":
            pass
        elif tab_name == "AI Assistant":
            # If entering AI assistant tab, refresh any content
            pass
        elif tab_name == "Settings":
            pass
            
        # If leaving scan tab, stop the camera
        if tab_name != "Scan" and self.camera_active:
            self.stop_camera()
    
    # ----- Home Tab -----
    
    def setup_home_tab(self):
        """Set up the home tab with today's medicines and streak information."""
        # Top frame for streak information
        self.home_top_frame = ttk.Frame(self.home_tab, padding=10)
        self.home_top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Welcome label
        welcome_label = ttk.Label(
            self.home_top_frame, 
            text="Medicine Reminder", 
            font=("Arial", 18, "bold")
        )
        welcome_label.pack(pady=10)
        
        # Streak frame
        self.streak_frame = ttk.LabelFrame(self.home_top_frame, text="Your Progress", padding=10)
        self.streak_frame.pack(fill=tk.X, pady=10)
        
        # Current streak
        self.current_streak_label = ttk.Label(
            self.streak_frame, 
            text="Current Streak: 0 days", 
            font=("Arial", 12)
        )
        self.current_streak_label.pack(anchor=tk.W, pady=5)
        
        # Longest streak
        self.longest_streak_label = ttk.Label(
            self.streak_frame, 
            text="Longest Streak: 0 days", 
            font=("Arial", 12)
        )
        self.longest_streak_label.pack(anchor=tk.W, pady=5)
        
        # Today's medicines frame
        self.today_frame = ttk.LabelFrame(self.home_tab, text="Today's Medicines", padding=10)
        self.today_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable frame for medicines
        self.today_scrollframe = ttk.Frame(self.today_frame)
        self.today_scrollframe.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        self.today_scrollbar = ttk.Scrollbar(self.today_scrollframe)
        self.today_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas for scrolling
        self.today_canvas = tk.Canvas(self.today_scrollframe)
        self.today_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        self.today_scrollbar.configure(command=self.today_canvas.yview)
        self.today_canvas.configure(yscrollcommand=self.today_scrollbar.set)
        
        # Bind scroll event
        self.today_canvas.bind('<Configure>', 
            lambda e: self.today_canvas.configure(scrollregion=self.today_canvas.bbox('all')))
        
        # Create a frame inside the canvas for medicines
        self.today_medicines_frame = ttk.Frame(self.today_canvas)
        self.today_canvas.create_window((0, 0), window=self.today_medicines_frame, anchor=tk.NW)
        
        # Button frame at the bottom
        self.home_button_frame = ttk.Frame(self.home_tab, padding=10)
        self.home_button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Refresh button
        self.refresh_button = ttk.Button(
            self.home_button_frame, 
            text="Refresh", 
            command=self.refresh_home_tab
        )
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
        
        # Add Medicine button
        self.add_med_button = ttk.Button(
            self.home_button_frame, 
            text="Add Medicine", 
            command=lambda: self.tab_control.select(self.medicines_tab)
        )
        self.add_med_button.pack(side=tk.RIGHT, padx=5)
        
        # View Schedule button
        self.view_schedule_button = ttk.Button(
            self.home_button_frame, 
            text="View Schedule", 
            command=lambda: self.tab_control.select(self.schedule_tab)
        )
        self.view_schedule_button.pack(side=tk.RIGHT, padx=5)
        
    def refresh_home_tab(self):
        """Refresh the home tab content with latest data."""
        # Update streak information
        streak_data = self.db_manager.get_streak()
        current_streak = streak_data.get('current_streak', 0)
        longest_streak = streak_data.get('longest_streak', 0)
        
        self.current_streak_label.config(text=f"Current Streak: {current_streak} days")
        self.longest_streak_label.config(text=f"Longest Streak: {longest_streak} days")
        
        # Clear existing medicines
        for widget in self.today_medicines_frame.winfo_children():
            widget.destroy()
        
        # Get today's date
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Get medicines for today
        medicines = self.db_manager.get_medicines_for_date(today)
        
        if not medicines:
            no_meds_label = ttk.Label(
                self.today_medicines_frame, 
                text="No medicines scheduled for today.", 
                font=("Arial", 12),
                padding=20
            )
            no_meds_label.pack(pady=20)
            return
        
        # Sort medicines by time
        medicines.sort(key=lambda x: x['time'])
        
        # Group medicines by time
        by_time = {}
        for med in medicines:
            time_str = med['time']
            if time_str not in by_time:
                by_time[time_str] = []
            by_time[time_str].append(med)
        
        # Create a frame for each time
        for time_str, meds in by_time.items():
            # Time frame
            time_frame = ttk.LabelFrame(
                self.today_medicines_frame, 
                text=f"Time: {time_str}", 
                padding=10
            )
            time_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Add each medicine
            for med in meds:
                med_frame = ttk.Frame(time_frame, padding=5)
                med_frame.pack(fill=tk.X, pady=2)
                
                # Medicine name and dosage
                med_label = ttk.Label(
                    med_frame, 
                    text=f"{med['name']} - {med['dosage']}", 
                    font=("Arial", 12)
                )
                med_label.pack(side=tk.LEFT, padx=5)
                
                # "Taken" button
                taken_button = ttk.Button(
                    med_frame, 
                    text="Mark as Taken", 
                    command=lambda m=med: self.mark_medicine_taken(m)
                )
                taken_button.pack(side=tk.RIGHT, padx=5)
                
                # Add a separator
                separator = ttk.Separator(time_frame, orient=tk.HORIZONTAL)
                separator.pack(fill=tk.X, pady=5)
        
        # Update the canvas
        self.today_canvas.update_idletasks()
        self.today_canvas.configure(scrollregion=self.today_canvas.bbox('all'))
    
    def mark_medicine_taken(self, medicine):
        """
        Mark a medicine as taken and update the database.
        
        Args:
            medicine (dict): The medicine to mark as taken
        """
        try:
            log_id = self.db_manager.log_medicine_intake(medicine['id'], taken=True)
            if log_id:
                messagebox.showinfo("Success", f"Marked {medicine['name']} as taken!")
                self.refresh_home_tab()
            else:
                messagebox.showerror("Error", "Failed to record medicine intake.")
        except Exception as e:
            self.logger.error(f"Error marking medicine as taken: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
    
    # ----- Medicines Tab -----
    
    def setup_medicines_tab(self):
        """Set up the medicines tab with list and add/edit form."""
        # Left frame for medicine list
        self.medicines_left_frame = ttk.Frame(self.medicines_tab, padding=10)
        self.medicines_left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        # Search frame
        search_frame = ttk.Frame(self.medicines_left_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        search_label = ttk.Label(search_frame, text="Search:")
        search_label.pack(side=tk.LEFT, padx=5)
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        search_button = ttk.Button(
            search_frame, 
            text="Search", 
            command=self.refresh_medicine_list
        )
        search_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind Enter key to search
        search_entry.bind('<Return>', lambda event: self.refresh_medicine_list())
        
        # Medicine list
        list_frame = ttk.LabelFrame(self.medicines_left_frame, text="Your Medicines")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollbar
        self.medicine_scrollbar = ttk.Scrollbar(list_frame)
        self.medicine_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for medicines
        self.medicine_tree = ttk.Treeview(
            list_frame, 
            columns=("id", "name", "dosage", "expiry"), 
            show="headings",
            yscrollcommand=self.medicine_scrollbar.set
        )
        
        # Configure scrollbar
        self.medicine_scrollbar.config(command=self.medicine_tree.yview)
        
        # Define columns
        self.medicine_tree.heading("id", text="ID")
        self.medicine_tree.heading("name", text="Medicine Name")
        self.medicine_tree.heading("dosage", text="Dosage")
        self.medicine_tree.heading("expiry", text="Expires")
        
        # Configure column widths
        self.medicine_tree.column("id", width=50, minwidth=50)
        self.medicine_tree.column("name", width=150, minwidth=100)
        self.medicine_tree.column("dosage", width=100, minwidth=80)
        self.medicine_tree.column("expiry", width=100, minwidth=80)
        
        self.medicine_tree.pack(fill=tk.BOTH, expand=True)
        
        # Bind select event
        self.medicine_tree.bind('<<TreeviewSelect>>', self.on_medicine_select)
        
        # Buttons under the list
        list_button_frame = ttk.Frame(self.medicines_left_frame)
        list_button_frame.pack(fill=tk.X, pady=5)
        
        add_button = ttk.Button(
            list_button_frame, 
            text="Add New", 
            command=self.clear_medicine_form
        )
        add_button.pack(side=tk.LEFT, padx=5)
        
        delete_button = ttk.Button(
            list_button_frame, 
            text="Delete", 
            command=self.delete_medicine
        )
        delete_button.pack(side=tk.LEFT, padx=5)
        
        refresh_button = ttk.Button(
            list_button_frame, 
            text="Refresh", 
            command=self.refresh_medicine_list
        )
        refresh_button.pack(side=tk.RIGHT, padx=5)
        
        # Right frame for medicine details
        self.medicines_right_frame = ttk.Frame(self.medicines_tab, padding=10)
        self.medicines_right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        # Medicine form
        form_frame = ttk.LabelFrame(self.medicines_right_frame, text="Medicine Details")
        form_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Medicine Name
        name_frame = ttk.Frame(form_frame, padding=5)
        name_frame.pack(fill=tk.X, pady=5)
        
        name_label = ttk.Label(name_frame, text="Medicine Name:", width=15)
        name_label.pack(side=tk.LEFT, padx=5)
        
        name_entry = ttk.Entry(name_frame, textvariable=self.medicine_name_var)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Barcode
        barcode_frame = ttk.Frame(form_frame, padding=5)
        barcode_frame.pack(fill=tk.X, pady=5)
        
        barcode_label = ttk.Label(barcode_frame, text="Barcode:", width=15)
        barcode_label.pack(side=tk.LEFT, padx=5)
        
        barcode_entry = ttk.Entry(barcode_frame, textvariable=self.barcode_var)
        barcode_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        scan_button = ttk.Button(
            barcode_frame, 
            text="Scan", 
            command=lambda: self.tab_control.select(self.scan_tab)
        )
        scan_button.pack(side=tk.RIGHT, padx=5)
        
        # Dosage
        dosage_frame = ttk.Frame(form_frame, padding=5)
        dosage_frame.pack(fill=tk.X, pady=5)
        
        dosage_label = ttk.Label(dosage_frame, text="Dosage:", width=15)
        dosage_label.pack(side=tk.LEFT, padx=5)
        
        dosage_entry = ttk.Entry(dosage_frame, textvariable=self.dosage_var)
        dosage_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Expiry Date
        expiry_frame = ttk.Frame(form_frame, padding=5)
        expiry_frame.pack(fill=tk.X, pady=5)
        
        expiry_label = ttk.Label(expiry_frame, text="Expiry Date:", width=15)
        expiry_label.pack(side=tk.LEFT, padx=5)
        
        expiry_entry = ttk.Entry(expiry_frame, textvariable=self.expiry_date_var)
        expiry_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        cal_button = ttk.Button(
            expiry_frame, 
            text="...", 
            width=3,
            command=self.show_calendar_for_expiry
        )
        cal_button.pack(side=tk.RIGHT)
        
        # Doses Remaining
        doses_frame = ttk.Frame(form_frame, padding=5)
        doses_frame.pack(fill=tk.X, pady=5)
        
        doses_label = ttk.Label(doses_frame, text="Doses Remaining:", width=15)
        doses_label.pack(side=tk.LEFT, padx=5)
        
        doses_entry = ttk.Entry(doses_frame, textvariable=self.doses_remaining_var)
        doses_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Notes
        notes_frame = ttk.Frame(form_frame, padding=5)
        notes_frame.pack(fill=tk.X, pady=5)
        
        notes_label = ttk.Label(notes_frame, text="Notes:", width=15)
        notes_label.pack(side=tk.LEFT, padx=5)
        
        self.notes_text = tk.Text(notes_frame, height=4, width=30)
        self.notes_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Schedule section
        schedule_frame = ttk.LabelFrame(form_frame, text="Reminder Schedule")
        schedule_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # Schedule list
        self.schedule_list_frame = ttk.Frame(schedule_frame)
        self.schedule_list_frame.pack(fill=tk.X, pady=5)
        
        # Add schedule button
        add_schedule_button = ttk.Button(
            schedule_frame, 
            text="Add Schedule", 
            command=self.add_schedule_row
        )
        add_schedule_button.pack(pady=5)
        
        # Save button
        save_button = ttk.Button(
            form_frame, 
            text="Save Medicine", 
            command=self.save_medicine
        )
        save_button.pack(pady=10)
        
        # Hidden field for medicine ID (for editing)
        self.current_medicine_id = None
        
        # Add initial empty schedule row
        self.add_schedule_row()
        
    def show_calendar_for_expiry(self):
        """Show a calendar popup for selecting expiry date."""
        def set_date():
            date_str = cal.get_date()
            self.expiry_date_var.set(date_str)
            top.destroy()
            
        top = tk.Toplevel(self.root)
        top.title("Select Expiry Date")
        
        # If there's a current date, try to parse it
        current_date = self.expiry_date_var.get()
        try:
            if current_date:
                year, month, day = map(int, current_date.split('-'))
                cal = Calendar(top, selectmode="day", year=year, month=month, day=day)
            else:
                cal = Calendar(top, selectmode="day")
        except (ValueError, IndexError):
            cal = Calendar(top, selectmode="day")
            
        cal.pack(padx=10, pady=10)
        
        select_button = ttk.Button(top, text="Select", command=set_date)
        select_button.pack(pady=10)
        
    def add_schedule_row(self):
        """Add a new schedule row to the form."""
        # Create a frame for the schedule row
        row_frame = ttk.Frame(self.schedule_list_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        # Day of week dropdown
        day_label = ttk.Label(row_frame, text="Day:", width=5)
        day_label.pack(side=tk.LEFT, padx=2)
        
        day_combo = ttk.Combobox(
            row_frame, 
            values=["Every day", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            width=10
        )
        day_combo.current(0)  # Default to "Every day"
        day_combo.pack(side=tk.LEFT, padx=2)
        
        # Time entry
        time_label = ttk.Label(row_frame, text="Time:", width=5)
        time_label.pack(side=tk.LEFT, padx=2)
        
        time_entry = ttk.Entry(row_frame, width=10)
        # Set a default time (8:00)
        time_entry.insert(0, "08:00")
        time_entry.pack(side=tk.LEFT, padx=2)
        
        # Remove button
        remove_button = ttk.Button(
            row_frame, 
            text="X", 
            width=2,
            command=lambda: row_frame.destroy()
        )
        remove_button.pack(side=tk.RIGHT, padx=2)
        
    def clear_medicine_form(self):
        """Clear the medicine form for adding a new medicine."""
        self.current_medicine_id = None
        self.medicine_name_var.set("")
        self.barcode_var.set("")
        self.dosage_var.set("")
        self.expiry_date_var.set("")
        self.doses_remaining_var.set("")
        self.notes_text.delete(1.0, tk.END)
        
        # Clear existing schedule rows
        for widget in self.schedule_list_frame.winfo_children():
            widget.destroy()
            
        # Add a fresh schedule row
        self.add_schedule_row()
        
    def on_medicine_select(self, event):
        """
        Handle medicine selection from the list.
        
        Args:
            event: The selection event
        """
        selected_items = self.medicine_tree.selection()
        if not selected_items:
            return
            
        # Get the first selected item
        item_id = selected_items[0]
        medicine_id = self.medicine_tree.item(item_id, "values")[0]
        
        # Get medicine details
        medicine = self.db_manager.get_medicine_by_id(int(medicine_id))
        if not medicine:
            return
            
        # Fill the form
        self.current_medicine_id = medicine['id']
        self.medicine_name_var.set(medicine['name'])
        self.barcode_var.set(medicine.get('barcode', ""))
        self.dosage_var.set(medicine.get('dosage', ""))
        self.expiry_date_var.set(medicine.get('expiry_date', ""))
        self.doses_remaining_var.set(str(medicine.get('doses_remaining', "")))
        
        # Clear notes and set new value
        self.notes_text.delete(1.0, tk.END)
        if medicine.get('notes'):
            self.notes_text.insert(1.0, medicine['notes'])
            
        # Clear existing schedule rows
        for widget in self.schedule_list_frame.winfo_children():
            widget.destroy()
            
        # Get schedules for this medicine
        schedules = self.db_manager.get_schedules_for_medicine(medicine['id'])
        
        if schedules:
            # Add a row for each schedule
            for schedule in schedules:
                self.add_schedule_for_medicine(schedule)
        else:
            # Add an empty schedule row
            self.add_schedule_row()
            
    def add_schedule_for_medicine(self, schedule):
        """
        Add a schedule row with data from the database.
        
        Args:
            schedule (dict): Schedule information
        """
        # Create a frame for the schedule row
        row_frame = ttk.Frame(self.schedule_list_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        # Day of week dropdown
        day_label = ttk.Label(row_frame, text="Day:", width=5)
        day_label.pack(side=tk.LEFT, padx=2)
        
        day_options = ["Every day", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_combo = ttk.Combobox(
            row_frame, 
            values=day_options,
            width=10
        )
        
        # Set the day based on day_of_week value
        day_of_week = schedule['day_of_week']
        if day_of_week == -1:
            day_combo.current(0)  # "Every day"
        else:
            day_combo.current(day_of_week + 1)  # +1 because "Every day" is at index 0
            
        day_combo.pack(side=tk.LEFT, padx=2)
        
        # Time entry
        time_label = ttk.Label(row_frame, text="Time:", width=5)
        time_label.pack(side=tk.LEFT, padx=2)
        
        time_entry = ttk.Entry(row_frame, width=10)
        time_entry.insert(0, schedule['time'])
        time_entry.pack(side=tk.LEFT, padx=2)
        
        # Schedule ID (hidden)
        row_frame.schedule_id = schedule['id']
        
        # Remove button
        remove_button = ttk.Button(
            row_frame, 
            text="X", 
            width=2,
            command=lambda: self.remove_schedule(row_frame)
        )
        remove_button.pack(side=tk.RIGHT, padx=2)
        
    def remove_schedule(self, row_frame):
        """
        Remove a schedule row and delete from database if it exists.
        
        Args:
            row_frame: The schedule row frame to remove
        """
        # If this schedule has an ID (exists in database), delete it
        if hasattr(row_frame, 'schedule_id'):
            try:
                self.db_manager.delete_schedule(row_frame.schedule_id)
            except Exception as e:
                self.logger.error(f"Error deleting schedule: {str(e)}")
                messagebox.showerror("Error", f"Failed to delete schedule: {str(e)}")
                
        # Remove the frame
        row_frame.destroy()
        
    def save_medicine(self):
        """Save the medicine data from the form to the database."""
        # Get values from form
        name = self.medicine_name_var.get().strip()
        barcode = self.barcode_var.get().strip() or None
        dosage = self.dosage_var.get().strip() or None
        expiry_date = self.expiry_date_var.get().strip() or None
        
        # Validate doses_remaining
        doses_remaining_str = self.doses_remaining_var.get().strip()
        doses_remaining = None
        if doses_remaining_str:
            try:
                doses_remaining = int(doses_remaining_str)
                if doses_remaining < 0:
                    messagebox.showerror("Error", "Doses remaining must be a positive number.")
                    return
            except ValueError:
                messagebox.showerror("Error", "Doses remaining must be a number.")
                return
                
        # Get notes
        notes = self.notes_text.get(1.0, tk.END).strip() or None
        
        # Validate required fields
        if not name:
            messagebox.showerror("Error", "Medicine name is required.")
            return
            
        try:
            # Save or update medicine
            if self.current_medicine_id is not None:
                # Update existing medicine
                success = self.db_manager.update_medicine(
                    self.current_medicine_id,
                    name=name,
                    barcode=barcode,
                    dosage=dosage,
                    expiry_date=expiry_date,
                    doses_remaining=doses_remaining,
                    notes=notes
                )
                
                if not success:
                    messagebox.showerror("Error", "Failed to update medicine.")
                    return
                    
                medicine_id = self.current_medicine_id
            else:
                # Add new medicine
                medicine_id = self.db_manager.add_medicine(
                    name=name,
                    barcode=barcode,
                    dosage=dosage,
                    expiry_date=expiry_date,
                    doses_remaining=doses_remaining,
                    notes=notes
                )
                
                if not medicine_id:
                    messagebox.showerror("Error", "Failed to add medicine.")
                    return
                    
            # Save schedules
            for schedule_frame in self.schedule_list_frame.winfo_children():
                try:
                    # Get the day of week
                    day_combo = schedule_frame.winfo_children()[1]  # The combobox
                    day_index = day_combo.current()
                    
                    # Convert to database format (-1 for every day, 0-6 for Monday-Sunday)
                    if day_index == 0:
                        day_of_week = -1  # Every day
                    else:
                        day_of_week = day_index - 1  # 0 = Monday, 6 = Sunday
                        
                    # Get the time
                    time_entry = schedule_frame.winfo_children()[3]  # The time entry
                    time_str = time_entry.get().strip()
                    
                    # Validate time format (HH:MM)
                    if not time_str or not self.is_valid_time_format(time_str):
                        messagebox.showerror("Error", "Invalid time format. Use HH:MM.")
                        return
                        
                    # Check if this is an existing schedule or new one
                    if hasattr(schedule_frame, 'schedule_id'):
                        # Update existing schedule
                        self.db_manager.update_schedule(
                            schedule_frame.schedule_id,
                            time=time_str,
                            day_of_week=day_of_week
                        )
                    else:
                        # Add new schedule
                        self.db_manager.add_schedule(
                            medicine_id=medicine_id,
                            time=time_str,
                            day_of_week=day_of_week
                        )
                except Exception as e:
                    self.logger.error(f"Error saving schedule: {str(e)}")
                    messagebox.showerror("Error", f"Failed to save schedule: {str(e)}")
                    continue
                    
            # Show success message
            messagebox.showinfo("Success", "Medicine saved successfully!")
            
            # Try to sync with Google services if enabled
            try:
                # Google Calendar sync
                if hasattr(self.calendar_integration, 'sync_thread') and self.calendar_integration.sync_thread:
                    self.calendar_integration.sync_medicine_schedule()
                    
                # Google Sheets sync
                if hasattr(self.sheets_integration, 'sync_thread') and self.sheets_integration.sync_thread:
                    self.sheets_integration.export_medicines_to_sheets()
                    
            except Exception as e:
                self.logger.error(f"Error syncing with Google services: {str(e)}")
                # Don't show error to user, just log it
                
            # Refresh the medicine list
            self.refresh_medicine_list()
            # Clear the form for next entry
            self.clear_medicine_form()
            
        except Exception as e:
            self.logger.error(f"Error saving medicine: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            
    def is_valid_time_format(self, time_str):
        """
        Validate time string format (HH:MM).
        
        Args:
            time_str (str): Time string to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            hours, minutes = map(int, time_str.split(':'))
            return 0 <= hours < 24 and 0 <= minutes < 60
        except (ValueError, AttributeError):
            return False
            
    def delete_medicine(self):
        """Delete the selected medicine from the database."""
        selected_items = self.medicine_tree.selection()
        if not selected_items:
            messagebox.showinfo("Info", "Please select a medicine to delete.")
            return
            
        # Get the first selected item
        item_id = selected_items[0]
        medicine_id = self.medicine_tree.item(item_id, "values")[0]
        medicine_name = self.medicine_tree.item(item_id, "values")[1]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {medicine_name}?"):
            return
            
        try:
            # Delete the medicine
            success = self.db_manager.delete_medicine(int(medicine_id))
            
            if success:
                messagebox.showinfo("Success", f"{medicine_name} deleted successfully.")
                # Refresh the list
                self.refresh_medicine_list()
                # Clear the form
                self.clear_medicine_form()
            else:
                messagebox.showerror("Error", "Failed to delete medicine.")
                
        except Exception as e:
            self.logger.error(f"Error deleting medicine: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            
    def refresh_medicine_list(self):
        """Refresh the medicine list with latest data."""
        # Clear existing items
        for item in self.medicine_tree.get_children():
            self.medicine_tree.delete(item)
            
        # Get medicines from database
        medicines = self.db_manager.get_all_medicines()
        
        # Filter if search term is provided
        search_term = self.search_var.get().strip().lower()
        if search_term:
            medicines = [m for m in medicines if search_term in m['name'].lower()]
            
        # Add medicines to the treeview
        for medicine in medicines:
            self.medicine_tree.insert(
                "", 
                tk.END, 
                values=(
                    medicine['id'],
                    medicine['name'],
                    medicine.get('dosage', ""),
                    medicine.get('expiry_date', "")
                )
            )
    
    # ----- Schedule Tab -----
    
    def setup_schedule_tab(self):
        """Set up the schedule tab with calendar view."""
        # Top frame for date navigation
        top_frame = ttk.Frame(self.schedule_tab, padding=10)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Calendar widget for date selection
        self.schedule_calendar = Calendar(top_frame, selectmode="day")
        self.schedule_calendar.pack(side=tk.LEFT, padx=10)
        
        # Bind date selection event
        self.schedule_calendar.bind("<<CalendarSelected>>", self.on_date_selected)
        
        # Selected date medicines frame
        self.date_frame = ttk.LabelFrame(self.schedule_tab, text="Medicines for Selected Date", padding=10)
        self.date_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable frame for medicines
        self.schedule_scrollframe = ttk.Frame(self.date_frame)
        self.schedule_scrollframe.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        self.schedule_scrollbar = ttk.Scrollbar(self.schedule_scrollframe)
        self.schedule_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas for scrolling
        self.schedule_canvas = tk.Canvas(self.schedule_scrollframe)
        self.schedule_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        self.schedule_scrollbar.configure(command=self.schedule_canvas.yview)
        self.schedule_canvas.configure(yscrollcommand=self.schedule_scrollbar.set)
        
        # Bind scroll event
        self.schedule_canvas.bind('<Configure>', 
            lambda e: self.schedule_canvas.configure(scrollregion=self.schedule_canvas.bbox('all')))
        
        # Create a frame inside the canvas for medicines
        self.schedule_medicines_frame = ttk.Frame(self.schedule_canvas)
        self.schedule_canvas.create_window((0, 0), window=self.schedule_medicines_frame, anchor=tk.NW)
        
    def on_date_selected(self, event):
        """
        Handle date selection in the schedule calendar.
        
        Args:
            event: The selection event
        """
        self.refresh_schedule_tab()
        
    def refresh_schedule_tab(self):
        """Refresh the schedule tab with medicines for selected date."""
        # Clear existing medicines
        for widget in self.schedule_medicines_frame.winfo_children():
            widget.destroy()
            
        # Get selected date
        selected_date = self.schedule_calendar.get_date()
        
        # Update frame title
        self.date_frame.configure(text=f"Medicines for {selected_date}")
        
        # Convert date to DB format (YYYY-MM-DD)
        try:
            date_obj = datetime.datetime.strptime(selected_date, "%m/%d/%y")
            db_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            # Try alternative format
            try:
                date_obj = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
                db_date = selected_date
            except ValueError:
                messagebox.showerror("Error", "Invalid date format.")
                return
                
        # Get medicines for selected date
        medicines = self.db_manager.get_medicines_for_date(db_date)
        
        if not medicines:
            no_meds_label = ttk.Label(
                self.schedule_medicines_frame, 
                text="No medicines scheduled for this date.", 
                font=("Arial", 12),
                padding=20
            )
            no_meds_label.pack(pady=20)
            return
            
        # Sort medicines by time
        medicines.sort(key=lambda x: x['time'])
        
        # Group medicines by time
        by_time = {}
        for med in medicines:
            time_str = med['time']
            if time_str not in by_time:
                by_time[time_str] = []
            by_time[time_str].append(med)
            
        # Create a frame for each time
        for time_str, meds in by_time.items():
            # Time frame
            time_frame = ttk.LabelFrame(
                self.schedule_medicines_frame, 
                text=f"Time: {time_str}", 
                padding=10
            )
            time_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Add each medicine
            for med in meds:
                med_frame = ttk.Frame(time_frame, padding=5)
                med_frame.pack(fill=tk.X, pady=2)
                
                # Medicine name and dosage
                med_label = ttk.Label(
                    med_frame, 
                    text=f"{med['name']} - {med['dosage'] if 'dosage' in med else 'No dosage specified'}", 
                    font=("Arial", 12)
                )
                med_label.pack(side=tk.LEFT, padx=5)
                
                # Edit button
                edit_button = ttk.Button(
                    med_frame, 
                    text="Edit", 
                    command=lambda m=med: self.edit_medicine_from_schedule(m)
                )
                edit_button.pack(side=tk.RIGHT, padx=5)
                
                # Add a separator
                separator = ttk.Separator(time_frame, orient=tk.HORIZONTAL)
                separator.pack(fill=tk.X, pady=5)
                
        # Update the canvas
        self.schedule_canvas.update_idletasks()
        self.schedule_canvas.configure(scrollregion=self.schedule_canvas.bbox('all'))
        
    def edit_medicine_from_schedule(self, medicine):
        """
        Switch to the medicines tab to edit the selected medicine.
        
        Args:
            medicine (dict): The medicine to edit
        """
        # Switch to medicines tab
        self.tab_control.select(self.medicines_tab)
        
        # Find and select the medicine in the treeview
        for item in self.medicine_tree.get_children():
            if self.medicine_tree.item(item, "values")[0] == str(medicine['id']):
                self.medicine_tree.selection_set(item)
                self.medicine_tree.focus(item)
                
                # Trigger the selection event
                self.on_medicine_select(None)
                break
    
    # ----- Scan Tab -----
    
    def setup_scan_tab(self):
        """Set up the scan tab with camera view and controls."""
        # Top frame for instructions
        instr_frame = ttk.Frame(self.scan_tab, padding=10)
        instr_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Instructions
        instructions = ttk.Label(
            instr_frame, 
            text="Position the barcode in front of the camera and keep it steady.",
            font=("Arial", 12),
            padding=10
        )
        instructions.pack()
        
        # Frame for camera view
        self.camera_frame = ttk.LabelFrame(self.scan_tab, text="Camera View", padding=10)
        self.camera_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Camera feed label (will be updated with camera frames)
        self.camera_label = ttk.Label(self.camera_frame)
        self.camera_label.pack(fill=tk.BOTH, expand=True)
        
        # Status frame
        status_frame = ttk.Frame(self.scan_tab, padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Status label
        self.scan_status_label = ttk.Label(
            status_frame, 
            text="Ready to scan", 
            font=("Arial", 12)
        )
        self.scan_status_label.pack(side=tk.LEFT, padx=10)
        
        # Buttons frame
        button_frame = ttk.Frame(self.scan_tab, padding=10)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Start/stop camera button
        self.camera_button = ttk.Button(
            button_frame, 
            text="Start Camera", 
            command=self.toggle_camera
        )
        self.camera_button.pack(side=tk.LEFT, padx=10)
        
        # Load image button
        self.load_image_button = ttk.Button(
            button_frame, 
            text="Scan from Image", 
            command=self.scan_from_image
        )
        self.load_image_button.pack(side=tk.LEFT, padx=10)
        
        # Cancel button
        self.cancel_button = ttk.Button(
            button_frame, 
            text="Cancel", 
            command=lambda: self.tab_control.select(self.medicines_tab)
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=10)
        
    def prepare_camera(self):
        """Prepare the camera for scanning."""
        if not self.camera_active:
            self.toggle_camera()
            
    def toggle_camera(self):
        """Toggle the camera on/off."""
        if self.camera_active:
            self.stop_camera()
            self.camera_button.config(text="Start Camera")
        else:
            self.start_camera()
            self.camera_button.config(text="Stop Camera")
            
    def start_camera(self):
        """Start the camera and scanning thread."""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Error", "Failed to open camera.")
                return
                
            self.camera_active = True
            self.stop_camera_flag.clear()
            
            # Start the camera thread
            self.camera_thread = threading.Thread(target=self.update_camera)
            self.camera_thread.daemon = True
            self.camera_thread.start()
            
            self.scan_status_label.config(text="Scanning for barcode...")
            
        except Exception as e:
            self.logger.error(f"Error starting camera: {str(e)}")
            messagebox.showerror("Error", f"Failed to start camera: {str(e)}")
            
    def stop_camera(self):
        """Stop the camera and scanning thread."""
        self.stop_camera_flag.set()
        
        if self.camera_thread:
            self.camera_thread.join(timeout=1.0)
            self.camera_thread = None
            
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            
        self.camera_active = False
        
        # Reset the camera label
        self.camera_label.config(image="")
        self.scan_status_label.config(text="Camera stopped")
        
    def update_camera(self):
        """Update the camera feed and scan for barcodes."""
        from pyzbar.pyzbar import decode
        
        while self.camera_active and not self.stop_camera_flag.is_set():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.error("Failed to capture frame")
                    break
                    
                # Mirror the frame
                frame = cv2.flip(frame, 1)
                
                # Convert to grayscale for barcode detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Scan for barcodes
                decoded_objects = decode(gray)
                
                for obj in decoded_objects:
                    # Draw rectangle around barcode
                    points = obj.polygon
                    if len(points) > 4:
                        hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                        cv2.polylines(frame, [hull], True, (0, 255, 0), 2)
                    else:
                        pts = np.array([point for point in points], dtype=np.int32)
                        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                        
                    # Get barcode data
                    barcode_data = obj.data.decode('utf-8')
                    barcode_type = obj.type
                    
                    # Display barcode info on frame
                    cv2.putText(frame, f"{barcode_type}: {barcode_data}", (obj.rect.left, obj.rect.top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                
                    # Handle barcode detection
                    self.root.after(0, lambda d=barcode_data, t=barcode_type: self.on_barcode_detected(d, t))
                    
                    # Pause for a moment to avoid multiple detections
                    time.sleep(1.0)
                    
                # Convert frame to a format tkinter can display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                imgtk = ImageTk.PhotoImage(image=img)
                
                # Update the label
                self.camera_label.imgtk = imgtk
                self.camera_label.config(image=imgtk)
                
                # Short sleep to reduce CPU usage
                time.sleep(0.03)
                
            except Exception as e:
                self.logger.error(f"Error in camera update: {str(e)}")
                break
                
        # Clean up
        if self.cap and self.cap.isOpened():
            self.cap.release()
            
        self.camera_active = False
        
    def on_barcode_detected(self, barcode_data, barcode_type):
        """
        Handle detected barcode data.
        
        Args:
            barcode_data (str): The barcode data
            barcode_type (str): The barcode type
        """
        self.scan_status_label.config(text=f"Detected: {barcode_type} - {barcode_data}")
        
        # Set the barcode value in the medicines form
        self.barcode_var.set(barcode_data)
        
        # Check if this barcode exists in the database
        medicine = self.db_manager.get_medicine_by_barcode(barcode_data)
        
        if medicine:
            if messagebox.askyesno("Barcode Found", 
                                  f"This barcode belongs to {medicine['name']}. Do you want to edit it?"):
                # Stop the camera
                self.stop_camera()
                
                # Switch to the medicines tab
                self.tab_control.select(self.medicines_tab)
                
                # Find and select the medicine in the treeview
                for item in self.medicine_tree.get_children():
                    if self.medicine_tree.item(item, "values")[0] == str(medicine['id']):
                        self.medicine_tree.selection_set(item)
                        self.medicine_tree.focus(item)
                        
                        # Trigger the selection event
                        self.on_medicine_select(None)
                        break
        else:
            if messagebox.askyesno("New Barcode", 
                                  "This barcode is not in the database. Do you want to add a new medicine?"):
                # Stop the camera
                self.stop_camera()
                
                # Switch to the medicines tab
                self.tab_control.select(self.medicines_tab)
                
                # Clear the form but keep the barcode
                self.clear_medicine_form()
                self.barcode_var.set(barcode_data)
                
    def scan_from_image(self):
        """Scan a barcode from an image file."""
        from pyzbar.pyzbar import decode
        
        # Open file dialog to select an image
        file_path = filedialog.askopenfilename(
            title="Select Image with Barcode",
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        
        if not file_path:
            return
            
        try:
            # Load the image
            image = cv2.imread(file_path)
            if image is None:
                messagebox.showerror("Error", "Failed to load image.")
                return
                
            # Decode barcodes
            decoded_objects = decode(image)
            
            if not decoded_objects:
                messagebox.showinfo("No Barcode", "No barcode found in the image.")
                return
                
            # Get the first barcode
            barcode = decoded_objects[0]
            barcode_data = barcode.data.decode('utf-8')
            barcode_type = barcode.type
            
            # Call the handler with the detected barcode
            self.on_barcode_detected(barcode_data, barcode_type)
            
        except Exception as e:
            self.logger.error(f"Error scanning image: {str(e)}")
            messagebox.showerror("Error", f"Failed to scan image: {str(e)}")
    
    # ----- Pharmacy Tab -----
    
    def setup_pharmacy_tab(self):
        """Set up the pharmacy finder tab."""
        # Top frame for search options
        search_frame = ttk.Frame(self.pharmacy_tab, padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Location input
        location_label = ttk.Label(search_frame, text="Location:", width=10)
        location_label.pack(side=tk.LEFT, padx=5)
        
        location_entry = ttk.Entry(search_frame, textvariable=self.location_var, width=40)
        location_entry.pack(side=tk.LEFT, padx=5)
        
        # Radius input
        radius_label = ttk.Label(search_frame, text="Radius (km):", width=12)
        radius_label.pack(side=tk.LEFT, padx=5)
        
        radius_entry = ttk.Entry(search_frame, textvariable=self.radius_var, width=5)
        radius_entry.pack(side=tk.LEFT, padx=5)
        
        # Search button
        search_button = ttk.Button(
            search_frame, 
            text="Find Pharmacies", 
            command=self.find_pharmacies
        )
        search_button.pack(side=tk.LEFT, padx=10)
        
        # Results frame
        results_frame = ttk.LabelFrame(self.pharmacy_tab, text="Nearby Pharmacies", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable frame for results
        self.pharmacy_scrollframe = ttk.Frame(results_frame)
        self.pharmacy_scrollframe.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        self.pharmacy_scrollbar = ttk.Scrollbar(self.pharmacy_scrollframe)
        self.pharmacy_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas for scrolling
        self.pharmacy_canvas = tk.Canvas(self.pharmacy_scrollframe)
        self.pharmacy_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        self.pharmacy_scrollbar.configure(command=self.pharmacy_canvas.yview)
        self.pharmacy_canvas.configure(yscrollcommand=self.pharmacy_scrollbar.set)
        
        # Bind scroll event
        self.pharmacy_canvas.bind('<Configure>', 
            lambda e: self.pharmacy_canvas.configure(scrollregion=self.pharmacy_canvas.bbox('all')))
        
        # Create a frame inside the canvas for pharmacies
        self.pharmacy_results_frame = ttk.Frame(self.pharmacy_canvas)
        self.pharmacy_canvas.create_window((0, 0), window=self.pharmacy_results_frame, anchor=tk.NW)
        
        # Initial message
        self.pharmacy_status = ttk.Label(
            self.pharmacy_results_frame, 
            text="Enter a location to find nearby pharmacies.",
            font=("Arial", 12),
            padding=20
        )
        self.pharmacy_status.pack(pady=20)
        
    def find_pharmacies(self):
        """Find pharmacies near the specified location."""
        # Clear existing results
        for widget in self.pharmacy_results_frame.winfo_children():
            widget.destroy()
            
        # Get location and radius
        location = self.location_var.get().strip()
        radius_str = self.radius_var.get().strip()
        
        if not location:
            messagebox.showerror("Error", "Please enter a location.")
            return
            
        try:
            radius = float(radius_str)
            if radius <= 0:
                messagebox.showerror("Error", "Radius must be a positive number.")
                return
        except ValueError:
            messagebox.showerror("Error", "Radius must be a number.")
            return
            
        # Update status
        self.pharmacy_status = ttk.Label(
            self.pharmacy_results_frame, 
            text=f"Searching for pharmacies near {location}...",
            font=("Arial", 12),
            padding=20
        )
        self.pharmacy_status.pack(pady=20)
        self.pharmacy_canvas.update()
        
        # Start search in a separate thread to avoid freezing UI
        search_thread = threading.Thread(
            target=self.search_pharmacies_thread,
            args=(location, radius * 1000)  # Convert km to meters
        )
        search_thread.daemon = True
        search_thread.start()
        
    def search_pharmacies_thread(self, location, radius):
        """
        Thread function to search for pharmacies.
        
        Args:
            location (str): Location to search near
            radius (float): Search radius in meters
        """
        try:
            # Find pharmacies
            pharmacies = self.pharmacy_locator.find_pharmacies_by_address(location, radius)
            
            # Update UI in the main thread
            self.root.after(0, lambda: self.display_pharmacy_results(pharmacies))
            
        except Exception as e:
            self.logger.error(f"Error searching for pharmacies: {str(e)}")
            self.root.after(0, lambda: self.display_pharmacy_error(str(e)))
            
    def display_pharmacy_results(self, pharmacies):
        """
        Display the pharmacy search results.
        
        Args:
            pharmacies (list): List of pharmacy dictionaries
        """
        # Clear existing results
        for widget in self.pharmacy_results_frame.winfo_children():
            widget.destroy()
            
        if not pharmacies:
            self.pharmacy_status = ttk.Label(
                self.pharmacy_results_frame, 
                text="No pharmacies found in this area.",
                font=("Arial", 12),
                padding=20
            )
            self.pharmacy_status.pack(pady=20)
            return
            
        # Results count
        results_label = ttk.Label(
            self.pharmacy_results_frame, 
            text=f"Found {len(pharmacies)} pharmacies",
            font=("Arial", 12, "bold"),
            padding=10
        )
        results_label.pack(fill=tk.X, pady=5)
        
        # Display each pharmacy
        for i, pharmacy in enumerate(pharmacies):
            # Create a frame for each pharmacy
            pharm_frame = ttk.Frame(self.pharmacy_results_frame, padding=10)
            pharm_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Name (with number)
            name_label = ttk.Label(
                pharm_frame, 
                text=f"{i+1}. {pharmacy['name']}",
                font=("Arial", 12, "bold")
            )
            name_label.pack(anchor=tk.W)
            
            # Distance
            distance_label = ttk.Label(
                pharm_frame, 
                text=f"Distance: {pharmacy['distance']:.2f} km"
            )
            distance_label.pack(anchor=tk.W)
            
            # Address
            if 'address' in pharmacy and pharmacy['address'] != "Unknown address":
                address_label = ttk.Label(
                    pharm_frame, 
                    text=f"Address: {pharmacy['address']}"
                )
                address_label.pack(anchor=tk.W)
                
            # Phone
            if 'phone' in pharmacy and pharmacy['phone'] != "Unknown":
                phone_label = ttk.Label(
                    pharm_frame, 
                    text=f"Phone: {pharmacy['phone']}"
                )
                phone_label.pack(anchor=tk.W)
                
            # Opening hours
            if 'opening_hours' in pharmacy and pharmacy['opening_hours'] != "Unknown":
                hours_label = ttk.Label(
                    pharm_frame, 
                    text=f"Hours: {pharmacy['opening_hours']}"
                )
                hours_label.pack(anchor=tk.W)
                
            # Map button
            map_button = ttk.Button(
                pharm_frame, 
                text="Open in Map", 
                command=lambda lat=pharmacy['lat'], lon=pharmacy['lon']: self.open_map(lat, lon)
            )
            map_button.pack(anchor=tk.W, pady=5)
            
            # Add a separator
            separator = ttk.Separator(self.pharmacy_results_frame, orient=tk.HORIZONTAL)
            separator.pack(fill=tk.X, pady=5)
            
        # Update the canvas
        self.pharmacy_canvas.update_idletasks()
        self.pharmacy_canvas.configure(scrollregion=self.pharmacy_canvas.bbox('all'))
        
    def display_pharmacy_error(self, error_message):
        """
        Display an error message in the pharmacy tab.
        
        Args:
            error_message (str): Error message to display
        """
        # Clear existing results
        for widget in self.pharmacy_results_frame.winfo_children():
            widget.destroy()
            
        error_label = ttk.Label(
            self.pharmacy_results_frame, 
            text=f"Error: {error_message}",
            foreground="red",
            font=("Arial", 12),
            padding=20
        )
        error_label.pack(pady=20)
        
    def open_map(self, lat, lon):
        """
        Open the location in a web browser map.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
        """
        url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=19/{lat}/{lon}"
        webbrowser.open(url)
    
    # ----- AI Assistant Tab -----
    
    def setup_ai_assistant_tab(self):
        """Set up the AI assistant tab with medicine analysis and interactions features."""
        # Main frame for AI assistant tab
        main_frame = ttk.Frame(self.ai_assistant_tab, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title label
        title_label = ttk.Label(
            main_frame, 
            text="AI Assistant", 
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)
        
        # Status frame to show if AI is configured
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.ai_status_label = ttk.Label(
            status_frame,
            text="AI Status: Not configured",
            font=("Arial", 12)
        )
        self.ai_status_label.pack(side=tk.LEFT, padx=5)
        
        # Update the status label based on xAI configuration
        if self.xai_assistant.is_configured():
            self.ai_status_label.config(
                text="AI Status: Connected",
                foreground="green"
            )
        else:
            self.ai_status_label.config(
                text="AI Status: Not configured (XAI_API_KEY not set)",
                foreground="red"
            )
        
        # Notebook for different AI features
        ai_notebook = ttk.Notebook(main_frame)
        ai_notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Medicine analysis tab
        analysis_tab = ttk.Frame(ai_notebook)
        ai_notebook.add(analysis_tab, text="Medicine Analysis")
        
        # Medicine interactions tab
        interactions_tab = ttk.Frame(ai_notebook)
        ai_notebook.add(interactions_tab, text="Food Interactions")
        
        # Alternatives tab
        alternatives_tab = ttk.Frame(ai_notebook)
        ai_notebook.add(alternatives_tab, text="Alternative Medicines")
        
        # Medicine recognition tab
        recognition_tab = ttk.Frame(ai_notebook)
        ai_notebook.add(recognition_tab, text="Image Recognition")
        
        # ----- Medicine Analysis Tab -----
        analysis_frame = ttk.Frame(analysis_tab, padding=10)
        analysis_frame.pack(fill=tk.BOTH, expand=True)
        
        # Medicine selector
        medicine_select_frame = ttk.Frame(analysis_frame)
        medicine_select_frame.pack(fill=tk.X, pady=10)
        
        medicine_label = ttk.Label(
            medicine_select_frame,
            text="Select Medicine:"
        )
        medicine_label.pack(side=tk.LEFT, padx=5)
        
        self.ai_medicine_select = ttk.Combobox(medicine_select_frame, textvariable=self.ai_medicine_var)
        self.ai_medicine_select.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Populate the medicine dropdown
        medicines = self.db_manager.get_all_medicines()
        if medicines:
            self.ai_medicine_select['values'] = [med['name'] for med in medicines]
        
        # Analyze button
        analyze_button = ttk.Button(
            medicine_select_frame,
            text="Analyze",
            command=self.analyze_medicine
        )
        analyze_button.pack(side=tk.RIGHT, padx=5)
        
        # Results area
        results_frame = ttk.LabelFrame(analysis_frame, text="Analysis Results")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbar for results text
        scrollbar = ttk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget for results
        self.ai_result_text = tk.Text(results_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.ai_result_text.pack(fill=tk.BOTH, expand=True)
        self.ai_result_text.config(state=tk.DISABLED)  # Make read-only by default
        
        scrollbar.config(command=self.ai_result_text.yview)
        
        # ----- Food Interactions Tab -----
        interactions_frame = ttk.Frame(interactions_tab, padding=10)
        interactions_frame.pack(fill=tk.BOTH, expand=True)
        
        # Medicine selector (similar to analysis tab)
        int_medicine_select_frame = ttk.Frame(interactions_frame)
        int_medicine_select_frame.pack(fill=tk.X, pady=10)
        
        int_medicine_label = ttk.Label(
            int_medicine_select_frame,
            text="Select Medicine:"
        )
        int_medicine_label.pack(side=tk.LEFT, padx=5)
        
        self.int_medicine_select = ttk.Combobox(int_medicine_select_frame)
        self.int_medicine_select.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Use the same values as the analysis tab
        if medicines:
            self.int_medicine_select['values'] = [med['name'] for med in medicines]
        
        # Find interactions button
        interactions_button = ttk.Button(
            int_medicine_select_frame,
            text="Find Interactions",
            command=self.find_food_interactions
        )
        interactions_button.pack(side=tk.RIGHT, padx=5)
        
        # Results area for interactions
        int_results_frame = ttk.LabelFrame(interactions_frame, text="Food Interactions")
        int_results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbar for interactions text
        int_scrollbar = ttk.Scrollbar(int_results_frame)
        int_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget for interactions
        self.int_result_text = tk.Text(int_results_frame, wrap=tk.WORD, yscrollcommand=int_scrollbar.set)
        self.int_result_text.pack(fill=tk.BOTH, expand=True)
        self.int_result_text.config(state=tk.DISABLED)  # Make read-only by default
        
        int_scrollbar.config(command=self.int_result_text.yview)
        
        # ----- Alternative Medicines Tab -----
        alternatives_frame = ttk.Frame(alternatives_tab, padding=10)
        alternatives_frame.pack(fill=tk.BOTH, expand=True)
        
        # Medicine selector
        alt_medicine_select_frame = ttk.Frame(alternatives_frame)
        alt_medicine_select_frame.pack(fill=tk.X, pady=10)
        
        alt_medicine_label = ttk.Label(
            alt_medicine_select_frame,
            text="Select Medicine:"
        )
        alt_medicine_label.pack(side=tk.LEFT, padx=5)
        
        self.alt_medicine_select = ttk.Combobox(alt_medicine_select_frame)
        self.alt_medicine_select.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Use the same values as other tabs
        if medicines:
            self.alt_medicine_select['values'] = [med['name'] for med in medicines]
        
        # Reason for alternatives
        reason_frame = ttk.Frame(alternatives_frame)
        reason_frame.pack(fill=tk.X, pady=10)
        
        reason_label = ttk.Label(
            reason_frame,
            text="Reason for alternatives:"
        )
        reason_label.pack(side=tk.LEFT, padx=5)
        
        self.alt_reason_entry = ttk.Entry(reason_frame)
        self.alt_reason_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Find alternatives button
        alternatives_button = ttk.Button(
            alternatives_frame,
            text="Find Alternatives",
            command=self.find_alternative_medicines
        )
        alternatives_button.pack(pady=10)
        
        # Results area for alternatives
        alt_results_frame = ttk.LabelFrame(alternatives_frame, text="Alternative Medicines")
        alt_results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbar for alternatives text
        alt_scrollbar = ttk.Scrollbar(alt_results_frame)
        alt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget for alternatives
        self.alt_result_text = tk.Text(alt_results_frame, wrap=tk.WORD, yscrollcommand=alt_scrollbar.set)
        self.alt_result_text.pack(fill=tk.BOTH, expand=True)
        self.alt_result_text.config(state=tk.DISABLED)  # Make read-only by default
        
        alt_scrollbar.config(command=self.alt_result_text.yview)
        
        # ----- Image Recognition Tab -----
        recognition_frame = ttk.Frame(recognition_tab, padding=10)
        recognition_frame.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions_label = ttk.Label(
            recognition_frame,
            text="Upload an image of a medicine for AI analysis",
            font=("Arial", 12)
        )
        instructions_label.pack(pady=10)
        
        # Image upload button
        upload_button = ttk.Button(
            recognition_frame,
            text="Upload Image",
            command=self.upload_medicine_image
        )
        upload_button.pack(pady=10)
        
        # Image display area
        self.img_display_frame = ttk.LabelFrame(recognition_frame, text="Uploaded Image")
        self.img_display_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.img_label = ttk.Label(self.img_display_frame)
        self.img_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Recognition results area
        recog_results_frame = ttk.LabelFrame(recognition_frame, text="Recognition Results")
        recog_results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Scrollbar for recognition text
        recog_scrollbar = ttk.Scrollbar(recog_results_frame)
        recog_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget for recognition results
        self.recog_result_text = tk.Text(recog_results_frame, wrap=tk.WORD, yscrollcommand=recog_scrollbar.set)
        self.recog_result_text.pack(fill=tk.BOTH, expand=True)
        self.recog_result_text.config(state=tk.DISABLED)  # Make read-only by default
        
        recog_scrollbar.config(command=self.recog_result_text.yview)
    
    def analyze_medicine(self):
        """Analyze a medicine using xAI."""
        if not self.xai_assistant.is_configured():
            messagebox.showerror("Error", "XAI Assistant is not configured. Please set the XAI_API_KEY environment variable.")
            return
            
        medicine_name = self.ai_medicine_var.get()
        if not medicine_name:
            messagebox.showerror("Error", "Please select a medicine to analyze.")
            return
            
        # Get medicine details from the database
        medicines = self.db_manager.get_all_medicines()
        selected_medicine = None
        for med in medicines:
            if med['name'] == medicine_name:
                selected_medicine = med
                break
                
        if not selected_medicine:
            messagebox.showerror("Error", "Medicine not found in database.")
            return
            
        # Show loading message
        self.ai_result_text.config(state=tk.NORMAL)
        self.ai_result_text.delete(1.0, tk.END)
        self.ai_result_text.insert(tk.END, "Analyzing medicine... Please wait.")
        self.ai_result_text.config(state=tk.DISABLED)
        self.root.update()
        
        try:
            # Call the xAI service
            result = self.xai_assistant.analyze_medicine_info(
                medicine_name=selected_medicine['name'],
                dosage=selected_medicine['dosage'],
                notes=selected_medicine.get('notes', '')
            )
            
            if not result:
                messagebox.showerror("Error", "Failed to analyze medicine. Check the logs for details.")
                return
                
            # Display the results
            self.ai_result_text.config(state=tk.NORMAL)
            self.ai_result_text.delete(1.0, tk.END)
            
            # Format the results nicely
            self.ai_result_text.insert(tk.END, f"Analysis Results for {medicine_name}\n\n")
            
            if 'usage_advice' in result:
                self.ai_result_text.insert(tk.END, "USAGE ADVICE:\n")
                self.ai_result_text.insert(tk.END, f"{result['usage_advice']}\n\n")
                
            if 'side_effects' in result and result['side_effects']:
                self.ai_result_text.insert(tk.END, "POTENTIAL SIDE EFFECTS:\n")
                for effect in result['side_effects']:
                    self.ai_result_text.insert(tk.END, f"• {effect}\n")
                self.ai_result_text.insert(tk.END, "\n")
                
            if 'interactions' in result and result['interactions']:
                self.ai_result_text.insert(tk.END, "POTENTIAL INTERACTIONS:\n")
                for interaction in result['interactions']:
                    self.ai_result_text.insert(tk.END, f"• {interaction}\n")
                self.ai_result_text.insert(tk.END, "\n")
                
            if 'general_info' in result:
                self.ai_result_text.insert(tk.END, "GENERAL INFORMATION:\n")
                self.ai_result_text.insert(tk.END, f"{result['general_info']}\n\n")
                
            self.ai_result_text.insert(tk.END, "DISCLAIMER: This information is provided by an AI assistant and should not replace professional medical advice. Always consult with a healthcare provider.")
            
            self.ai_result_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.error(f"Error analyzing medicine: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.ai_result_text.config(state=tk.NORMAL)
            self.ai_result_text.delete(1.0, tk.END)
            self.ai_result_text.insert(tk.END, f"Error analyzing medicine: {str(e)}")
            self.ai_result_text.config(state=tk.DISABLED)
    
    def find_food_interactions(self):
        """Find food interactions for a medicine using xAI."""
        if not self.xai_assistant.is_configured():
            messagebox.showerror("Error", "XAI Assistant is not configured. Please set the XAI_API_KEY environment variable.")
            return
            
        medicine_name = self.int_medicine_select.get()
        if not medicine_name:
            messagebox.showerror("Error", "Please select a medicine to find interactions for.")
            return
            
        # Show loading message
        self.int_result_text.config(state=tk.NORMAL)
        self.int_result_text.delete(1.0, tk.END)
        self.int_result_text.insert(tk.END, "Finding food interactions... Please wait.")
        self.int_result_text.config(state=tk.DISABLED)
        self.root.update()
        
        try:
            # Call the xAI service
            result = self.xai_assistant.get_food_interactions(medicine_name)
            
            if not result:
                messagebox.showerror("Error", "Failed to find food interactions. Check the logs for details.")
                return
                
            # Display the results
            self.int_result_text.config(state=tk.NORMAL)
            self.int_result_text.delete(1.0, tk.END)
            
            # Format the results nicely
            self.int_result_text.insert(tk.END, f"Food Interactions for {medicine_name}\n\n")
            
            if isinstance(result, list):
                if len(result) == 0:
                    self.int_result_text.insert(tk.END, "No known food interactions found.")
                else:
                    for item in result:
                        if isinstance(item, dict) and 'food' in item and 'description' in item:
                            self.int_result_text.insert(tk.END, f"{item['food']}:\n")
                            self.int_result_text.insert(tk.END, f"{item['description']}\n\n")
            else:
                self.int_result_text.insert(tk.END, str(result))
                
            self.int_result_text.insert(tk.END, "\nDISCLAIMER: This information is provided by an AI assistant and should not replace professional medical advice. Always consult with a healthcare provider.")
            
            self.int_result_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.error(f"Error finding food interactions: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.int_result_text.config(state=tk.NORMAL)
            self.int_result_text.delete(1.0, tk.END)
            self.int_result_text.insert(tk.END, f"Error finding food interactions: {str(e)}")
            self.int_result_text.config(state=tk.DISABLED)
    
    def find_alternative_medicines(self):
        """Find alternative medicines using xAI."""
        if not self.xai_assistant.is_configured():
            messagebox.showerror("Error", "XAI Assistant is not configured. Please set the XAI_API_KEY environment variable.")
            return
            
        medicine_name = self.alt_medicine_select.get()
        if not medicine_name:
            messagebox.showerror("Error", "Please select a medicine to find alternatives for.")
            return
            
        reason = self.alt_reason_entry.get()
        
        # Show loading message
        self.alt_result_text.config(state=tk.NORMAL)
        self.alt_result_text.delete(1.0, tk.END)
        self.alt_result_text.insert(tk.END, "Finding alternative medicines... Please wait.")
        self.alt_result_text.config(state=tk.DISABLED)
        self.root.update()
        
        try:
            # Call the xAI service
            result = self.xai_assistant.suggest_alternative_medicines(medicine_name, reason)
            
            if not result:
                messagebox.showerror("Error", "Failed to find alternative medicines. Check the logs for details.")
                return
                
            # Display the results
            self.alt_result_text.config(state=tk.NORMAL)
            self.alt_result_text.delete(1.0, tk.END)
            
            # Format the results nicely
            self.alt_result_text.insert(tk.END, f"Alternative Medicines for {medicine_name}\n\n")
            
            if 'disclaimer' in result:
                self.alt_result_text.insert(tk.END, f"DISCLAIMER: {result['disclaimer']}\n\n")
                
            if 'alternatives' in result and isinstance(result['alternatives'], list):
                if len(result['alternatives']) == 0:
                    self.alt_result_text.insert(tk.END, "No alternative medicines found.")
                else:
                    for item in result['alternatives']:
                        if isinstance(item, dict):
                            if 'name' in item:
                                self.alt_result_text.insert(tk.END, f"NAME: {item['name']}\n")
                            if 'class' in item:
                                self.alt_result_text.insert(tk.END, f"CLASS: {item['class']}\n")
                            if 'notes' in item:
                                self.alt_result_text.insert(tk.END, f"NOTES: {item['notes']}\n")
                            self.alt_result_text.insert(tk.END, "\n")
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        self.alt_result_text.insert(tk.END, f"NAME: {item.get('name', 'Unknown')}\n")
                        if 'class' in item:
                            self.alt_result_text.insert(tk.END, f"CLASS: {item['class']}\n")
                        if 'notes' in item:
                            self.alt_result_text.insert(tk.END, f"NOTES: {item['notes']}\n")
                        self.alt_result_text.insert(tk.END, "\n")
            else:
                self.alt_result_text.insert(tk.END, str(result))
                
            self.alt_result_text.insert(tk.END, "DISCLAIMER: This information is provided by an AI assistant and should not replace professional medical advice. Always consult with a healthcare provider before changing medications.")
            
            self.alt_result_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.error(f"Error finding alternative medicines: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.alt_result_text.config(state=tk.NORMAL)
            self.alt_result_text.delete(1.0, tk.END)
            self.alt_result_text.insert(tk.END, f"Error finding alternative medicines: {str(e)}")
            self.alt_result_text.config(state=tk.DISABLED)
    
    def upload_medicine_image(self):
        """Upload an image for medicine recognition."""
        if not self.xai_assistant.is_configured():
            messagebox.showerror("Error", "XAI Assistant is not configured. Please set the XAI_API_KEY environment variable.")
            return
            
        # Open file dialog to select an image
        filetypes = (
            ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif"),
            ("All files", "*.*")
        )
        filename = filedialog.askopenfilename(
            title="Select an image",
            filetypes=filetypes
        )
        
        if not filename:
            return  # User cancelled
            
        try:
            # Display the selected image
            img = Image.open(filename)
            # Resize to fit the display area
            img = img.resize((300, 300), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            self.img_label.config(image=photo)
            self.img_label.image = photo  # Keep a reference
            
            # Show loading message
            self.recog_result_text.config(state=tk.NORMAL)
            self.recog_result_text.delete(1.0, tk.END)
            self.recog_result_text.insert(tk.END, "Analyzing image... Please wait.")
            self.recog_result_text.config(state=tk.DISABLED)
            self.root.update()
            
            # Call the xAI service for image recognition
            result = self.xai_assistant.identify_medicine_from_image(filename)
            
            if not result:
                messagebox.showerror("Error", "Failed to identify medicine from image. Check the logs for details.")
                return
                
            # Display the results
            self.recog_result_text.config(state=tk.NORMAL)
            self.recog_result_text.delete(1.0, tk.END)
            
            # Format the results nicely
            self.recog_result_text.insert(tk.END, "Medicine Image Analysis Results\n\n")
            
            if 'name' in result:
                self.recog_result_text.insert(tk.END, f"IDENTIFIED AS: {result['name']}\n\n")
                
            if 'description' in result:
                self.recog_result_text.insert(tk.END, f"DESCRIPTION: {result['description']}\n\n")
                
            if 'confidence' in result:
                self.recog_result_text.insert(tk.END, f"CONFIDENCE: {result['confidence']}\n\n")
                
            if 'notes' in result:
                self.recog_result_text.insert(tk.END, f"ADDITIONAL NOTES: {result['notes']}\n\n")
                
            self.recog_result_text.insert(tk.END, "DISCLAIMER: This identification is provided by an AI assistant and should not replace professional verification. Always confirm with a healthcare provider or pharmacist.")
            
            self.recog_result_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.logger.error(f"Error identifying medicine from image: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.recog_result_text.config(state=tk.NORMAL)
            self.recog_result_text.delete(1.0, tk.END)
            self.recog_result_text.insert(tk.END, f"Error identifying medicine from image: {str(e)}")
            self.recog_result_text.config(state=tk.DISABLED)
    
    # ----- Settings Tab -----
    
    def setup_settings_tab(self):
        """Set up the settings tab with notification and integration options."""
        # Create a notebook for settings sections
        settings_notebook = ttk.Notebook(self.settings_tab)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create settings tabs
        notification_tab = ttk.Frame(settings_notebook, padding=10)
        google_tab = ttk.Frame(settings_notebook, padding=10)
        telegram_tab = ttk.Frame(settings_notebook, padding=10)
        about_tab = ttk.Frame(settings_notebook, padding=10)
        
        settings_notebook.add(notification_tab, text="Notifications")
        settings_notebook.add(google_tab, text="Google Services")
        settings_notebook.add(telegram_tab, text="Telegram")
        settings_notebook.add(about_tab, text="About")
        
        # ----- Notifications Settings -----
        
        # Email notification settings
        email_frame = ttk.LabelFrame(notification_tab, text="Email Notifications", padding=10)
        email_frame.pack(fill=tk.X, pady=10)
        
        # Email settings
        self.email_enabled_var = tk.BooleanVar(value=self.notifier.email_enabled)
        email_enabled_check = ttk.Checkbutton(
            email_frame, 
            text="Enable Email Notifications", 
            variable=self.email_enabled_var
        )
        email_enabled_check.pack(anchor=tk.W, pady=5)
        
        # Sender
        sender_frame = ttk.Frame(email_frame, padding=5)
        sender_frame.pack(fill=tk.X, pady=2)
        
        sender_label = ttk.Label(sender_frame, text="Sender Email:", width=15)
        sender_label.pack(side=tk.LEFT, padx=5)
        
        self.email_sender_var = tk.StringVar(value=self.notifier.email_sender)
        sender_entry = ttk.Entry(sender_frame, textvariable=self.email_sender_var, width=30)
        sender_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Password
        password_frame = ttk.Frame(email_frame, padding=5)
        password_frame.pack(fill=tk.X, pady=2)
        
        password_label = ttk.Label(password_frame, text="Password:", width=15)
        password_label.pack(side=tk.LEFT, padx=5)
        
        self.email_password_var = tk.StringVar(value=self.notifier.email_password)
        password_entry = ttk.Entry(password_frame, textvariable=self.email_password_var, show="*", width=30)
        password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Recipient
        recipient_frame = ttk.Frame(email_frame, padding=5)
        recipient_frame.pack(fill=tk.X, pady=2)
        
        recipient_label = ttk.Label(recipient_frame, text="Recipient Email:", width=15)
        recipient_label.pack(side=tk.LEFT, padx=5)
        
        self.email_recipient_var = tk.StringVar(value=self.notifier.email_recipient)
        recipient_entry = ttk.Entry(recipient_frame, textvariable=self.email_recipient_var, width=30)
        recipient_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Save email settings button
        save_email_button = ttk.Button(
            email_frame, 
            text="Save Email Settings", 
            command=self.save_email_settings
        )
        save_email_button.pack(anchor=tk.E, pady=10)
        
        # System notification settings
        system_frame = ttk.LabelFrame(notification_tab, text="System Notifications", padding=10)
        system_frame.pack(fill=tk.X, pady=10)
        
        self.system_enabled_var = tk.BooleanVar(value=True)  # Always enabled
        system_enabled_check = ttk.Checkbutton(
            system_frame, 
            text="Enable System Notifications", 
            variable=self.system_enabled_var
        )
        system_enabled_check.pack(anchor=tk.W, pady=5)
        system_enabled_check.configure(state=tk.DISABLED)  # Can't disable system notifications
        
        system_note = ttk.Label(
            system_frame, 
            text="System notifications are always enabled and will appear as pop-ups on your desktop.",
            wraplength=400
        )
        system_note.pack(anchor=tk.W, pady=5)
        
        # ----- Google Services Settings -----
        
        # Google Drive
        drive_frame = ttk.LabelFrame(google_tab, text="Google Drive Backup", padding=10)
        drive_frame.pack(fill=tk.X, pady=10)
        
        self.drive_enabled_var = tk.BooleanVar(value=False)
        drive_enabled_check = ttk.Checkbutton(
            drive_frame, 
            text="Enable Google Drive Backup", 
            variable=self.drive_enabled_var
        )
        drive_enabled_check.pack(anchor=tk.W, pady=5)
        
        drive_auth_button = ttk.Button(
            drive_frame, 
            text="Authenticate with Google Drive", 
            command=self.authenticate_drive
        )
        drive_auth_button.pack(anchor=tk.W, pady=5)
        
        drive_status_frame = ttk.Frame(drive_frame, padding=5)
        drive_status_frame.pack(fill=tk.X, pady=5)
        
        drive_status_label = ttk.Label(drive_status_frame, text="Status:")
        drive_status_label.pack(side=tk.LEFT, padx=5)
        
        self.drive_status_var = tk.StringVar(value="Not authenticated")
        drive_status_value = ttk.Label(drive_status_frame, textvariable=self.drive_status_var)
        drive_status_value.pack(side=tk.LEFT, padx=5)
        
        drive_sync_button = ttk.Button(
            drive_frame, 
            text="Sync Now", 
            command=lambda: self.drive_sync.force_sync(upload=True)
        )
        drive_sync_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Google Calendar
        calendar_frame = ttk.LabelFrame(google_tab, text="Google Calendar Integration", padding=10)
        calendar_frame.pack(fill=tk.X, pady=10)
        
        self.calendar_enabled_var = tk.BooleanVar(value=False)
        calendar_enabled_check = ttk.Checkbutton(
            calendar_frame, 
            text="Enable Google Calendar Integration", 
            variable=self.calendar_enabled_var
        )
        calendar_enabled_check.pack(anchor=tk.W, pady=5)
        
        calendar_auth_button = ttk.Button(
            calendar_frame, 
            text="Authenticate with Google Calendar", 
            command=self.authenticate_calendar
        )
        calendar_auth_button.pack(anchor=tk.W, pady=5)
        
        calendar_status_frame = ttk.Frame(calendar_frame, padding=5)
        calendar_status_frame.pack(fill=tk.X, pady=5)
        
        calendar_status_label = ttk.Label(calendar_status_frame, text="Status:")
        calendar_status_label.pack(side=tk.LEFT, padx=5)
        
        self.calendar_status_var = tk.StringVar(value="Not authenticated")
        calendar_status_value = ttk.Label(calendar_status_frame, textvariable=self.calendar_status_var)
        calendar_status_value.pack(side=tk.LEFT, padx=5)
        
        calendar_sync_button = ttk.Button(
            calendar_frame, 
            text="Sync Now", 
            command=self.calendar_integration.sync_medicine_schedule
        )
        calendar_sync_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Google Sheets
        sheets_frame = ttk.LabelFrame(google_tab, text="Google Sheets Integration", padding=10)
        sheets_frame.pack(fill=tk.X, pady=10)
        
        self.sheets_enabled_var = tk.BooleanVar(value=False)
        sheets_enabled_check = ttk.Checkbutton(
            sheets_frame, 
            text="Enable Google Sheets Integration", 
            variable=self.sheets_enabled_var
        )
        sheets_enabled_check.pack(anchor=tk.W, pady=5)
        
        sheets_auth_button = ttk.Button(
            sheets_frame, 
            text="Authenticate with Google Sheets", 
            command=self.authenticate_sheets
        )
        sheets_auth_button.pack(anchor=tk.W, pady=5)
        
        sheets_status_frame = ttk.Frame(sheets_frame, padding=5)
        sheets_status_frame.pack(fill=tk.X, pady=5)
        
        sheets_status_label = ttk.Label(sheets_status_frame, text="Status:")
        sheets_status_label.pack(side=tk.LEFT, padx=5)
        
        self.sheets_status_var = tk.StringVar(value="Not authenticated")
        sheets_status_value = ttk.Label(sheets_status_frame, textvariable=self.sheets_status_var)
        sheets_status_value.pack(side=tk.LEFT, padx=5)
        
        sheets_buttons_frame = ttk.Frame(sheets_frame, padding=5)
        sheets_buttons_frame.pack(fill=tk.X, pady=5)
        
        sheets_export_button = ttk.Button(
            sheets_buttons_frame, 
            text="Export to Sheets", 
            command=lambda: self.sheets_integration.export_medicines_to_sheets()
        )
        sheets_export_button.pack(side=tk.LEFT, padx=5)
        
        sheets_import_button = ttk.Button(
            sheets_buttons_frame, 
            text="Import from Sheets", 
            command=lambda: self.sheets_integration.import_medicines_from_sheets()
        )
        sheets_import_button.pack(side=tk.LEFT, padx=5)
        
        # Save Google settings button
        save_google_button = ttk.Button(
            google_tab, 
            text="Save Google Settings", 
            command=self.save_google_settings
        )
        save_google_button.pack(anchor=tk.E, pady=10)
        
        # ----- Telegram Settings -----
        
        # Telegram Bot
        telegram_frame = ttk.LabelFrame(telegram_tab, text="Telegram Bot Settings", padding=10)
        telegram_frame.pack(fill=tk.X, pady=10)
        
        self.telegram_enabled_var = tk.BooleanVar(value=self.telegram_bot.is_configured())
        telegram_enabled_check = ttk.Checkbutton(
            telegram_frame, 
            text="Enable Telegram Notifications", 
            variable=self.telegram_enabled_var
        )
        telegram_enabled_check.pack(anchor=tk.W, pady=5)
        
        # Token
        token_frame = ttk.Frame(telegram_frame, padding=5)
        token_frame.pack(fill=tk.X, pady=2)
        
        token_label = ttk.Label(token_frame, text="Bot Token:", width=15)
        token_label.pack(side=tk.LEFT, padx=5)
        
        self.telegram_token_var = tk.StringVar(value=self.telegram_bot.token)
        token_entry = ttk.Entry(token_frame, textvariable=self.telegram_token_var, width=40)
        token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Chat IDs
        chat_frame = ttk.LabelFrame(telegram_frame, text="Registered Chat IDs", padding=5)
        chat_frame.pack(fill=tk.X, pady=5)
        
        # Display chat IDs
        self.telegram_chats_text = tk.Text(chat_frame, height=5, width=40)
        self.telegram_chats_text.pack(fill=tk.X, pady=5)
        
        # Populate chat IDs
        for chat_id in self.telegram_bot.chat_ids:
            self.telegram_chats_text.insert(tk.END, f"{chat_id}\n")
            
        # Instructions
        instructions_label = ttk.Label(
            telegram_frame, 
            text="To use Telegram notifications: \n"
                 "1. Create a bot with BotFather on Telegram and get the token. \n"
                 "2. Start a chat with your bot and use /start command. \n"
                 "3. The bot will then send you medicine reminders.",
            wraplength=400
        )
        instructions_label.pack(anchor=tk.W, pady=10)
        
        # Save Telegram settings button
        save_telegram_button = ttk.Button(
            telegram_frame, 
            text="Save Telegram Settings", 
            command=self.save_telegram_settings
        )
        save_telegram_button.pack(anchor=tk.E, pady=10)
        
        # ----- About Tab -----
        
        about_label = ttk.Label(
            about_tab, 
            text="Medicine Reminder Application",
            font=("Arial", 16, "bold")
        )
        about_label.pack(pady=10)
        
        version_label = ttk.Label(
            about_tab, 
            text="Version 1.0",
            font=("Arial", 10)
        )
        version_label.pack()
        
        description_label = ttk.Label(
            about_tab, 
            text="An application to help you manage your medicines, send reminders, "
                 "and track your intake progress.",
            wraplength=400
        )
        description_label.pack(pady=10)
        
        features_frame = ttk.LabelFrame(about_tab, text="Features", padding=10)
        features_frame.pack(fill=tk.X, pady=10, padx=20)
        
        features_text = (
            "• Medicine Management with Barcode Scanning\n"
            "• Reminder Notifications (System, Email, Telegram)\n"
            "• Medicine Schedule Calendar\n"
            "• Google Services Integration\n"
            "• Nearby Pharmacy Locator\n"
            "• Streak Tracking for Adherence Monitoring"
        )
        
        features_label = ttk.Label(
            features_frame, 
            text=features_text,
            justify=tk.LEFT,
            wraplength=400
        )
        features_label.pack(anchor=tk.W)
        
        # Update status of Google services
        self.update_google_status()
        
    def save_email_settings(self):
        """Save email notification settings."""
        try:
            # Get values from the form
            enabled = self.email_enabled_var.get()
            sender = self.email_sender_var.get().strip()
            password = self.email_password_var.get().strip()
            recipient = self.email_recipient_var.get().strip()
            
            # Validate required fields if enabled
            if enabled:
                if not sender or not password or not recipient:
                    messagebox.showerror("Error", "All email fields are required when email notifications are enabled.")
                    return
                    
                # Configure the notifier
                self.notifier.configure_email(sender, password, recipient)
                
                # Save to environment variables for persistence
                os.environ["EMAIL_SENDER"] = sender
                os.environ["EMAIL_PASSWORD"] = password
                os.environ["EMAIL_RECIPIENT"] = recipient
                
                messagebox.showinfo("Success", "Email settings saved successfully.")
            else:
                # Disable email notifications
                self.notifier.email_enabled = False
                messagebox.showinfo("Success", "Email notifications disabled.")
                
        except Exception as e:
            self.logger.error(f"Error saving email settings: {str(e)}")
            messagebox.showerror("Error", f"Failed to save email settings: {str(e)}")
            
    def update_google_status(self):
        """Update the status display of Google services."""
        # Drive status
        if self.drive_sync.is_authenticated():
            self.drive_status_var.set("Authenticated")
            self.drive_enabled_var.set(True)
        else:
            self.drive_status_var.set("Not authenticated")
            self.drive_enabled_var.set(False)
            
        # Calendar status
        if self.calendar_integration.is_authenticated():
            self.calendar_status_var.set("Authenticated")
            self.calendar_enabled_var.set(True)
        else:
            self.calendar_status_var.set("Not authenticated")
            self.calendar_enabled_var.set(False)
            
        # Sheets status
        if self.sheets_integration.is_authenticated():
            self.sheets_status_var.set("Authenticated")
            self.sheets_enabled_var.set(True)
        else:
            self.sheets_status_var.set("Not authenticated")
            self.sheets_enabled_var.set(False)
            
    def authenticate_drive(self):
        """Authenticate with Google Drive."""
        try:
            if self.drive_sync.authenticate():
                messagebox.showinfo("Success", "Authenticated with Google Drive successfully.")
                self.update_google_status()
            else:
                messagebox.showerror("Error", "Authentication with Google Drive failed.")
        except Exception as e:
            self.logger.error(f"Error authenticating with Google Drive: {str(e)}")
            messagebox.showerror("Error", f"Authentication failed: {str(e)}")
            
    def authenticate_calendar(self):
        """Authenticate with Google Calendar."""
        try:
            if self.calendar_integration.authenticate():
                messagebox.showinfo("Success", "Authenticated with Google Calendar successfully.")
                self.update_google_status()
            else:
                messagebox.showerror("Error", "Authentication with Google Calendar failed.")
        except Exception as e:
            self.logger.error(f"Error authenticating with Google Calendar: {str(e)}")
            messagebox.showerror("Error", f"Authentication failed: {str(e)}")
            
    def authenticate_sheets(self):
        """Authenticate with Google Sheets."""
        try:
            if self.sheets_integration.authenticate():
                messagebox.showinfo("Success", "Authenticated with Google Sheets successfully.")
                self.update_google_status()
            else:
                messagebox.showerror("Error", "Authentication with Google Sheets failed.")
        except Exception as e:
            self.logger.error(f"Error authenticating with Google Sheets: {str(e)}")
            messagebox.showerror("Error", f"Authentication failed: {str(e)}")
            
    def save_google_settings(self):
        """Save Google services settings."""
        try:
            # Google Drive
            drive_enabled = self.drive_enabled_var.get()
            if drive_enabled:
                if not self.drive_sync.is_authenticated():
                    if not self.drive_sync.authenticate():
                        messagebox.showerror("Error", "Authentication with Google Drive required.")
                        return
                        
                # Start sync if not already running
                if not hasattr(self.drive_sync, 'sync_thread') or not self.drive_sync.sync_thread:
                    self.drive_sync.start_sync()
            else:
                # Stop sync if running
                if hasattr(self.drive_sync, 'sync_thread') and self.drive_sync.sync_thread:
                    self.drive_sync.stop_sync()
                    
            # Google Calendar
            calendar_enabled = self.calendar_enabled_var.get()
            if calendar_enabled:
                if not self.calendar_integration.is_authenticated():
                    if not self.calendar_integration.authenticate():
                        messagebox.showerror("Error", "Authentication with Google Calendar required.")
                        return
                        
                # Start sync if not already running
                if not hasattr(self.calendar_integration, 'sync_thread') or not self.calendar_integration.sync_thread:
                    self.calendar_integration.start_sync()
            else:
                # Stop sync if running
                if hasattr(self.calendar_integration, 'sync_thread') and self.calendar_integration.sync_thread:
                    self.calendar_integration.stop_sync()
                    
            # Google Sheets
            sheets_enabled = self.sheets_enabled_var.get()
            if sheets_enabled:
                if not self.sheets_integration.is_authenticated():
                    if not self.sheets_integration.authenticate():
                        messagebox.showerror("Error", "Authentication with Google Sheets required.")
                        return
                        
                # Start sync if not already running
                if not hasattr(self.sheets_integration, 'sync_thread') or not self.sheets_integration.sync_thread:
                    self.sheets_integration.start_sync()
            else:
                # Stop sync if running
                if hasattr(self.sheets_integration, 'sync_thread') and self.sheets_integration.sync_thread:
                    self.sheets_integration.stop_sync()
                    
            messagebox.showinfo("Success", "Google settings saved successfully.")
            
        except Exception as e:
            self.logger.error(f"Error saving Google settings: {str(e)}")
            messagebox.showerror("Error", f"Failed to save Google settings: {str(e)}")
            
    def save_telegram_settings(self):
        """Save Telegram bot settings."""
        try:
            # Get values from the form
            enabled = self.telegram_enabled_var.get()
            token = self.telegram_token_var.get().strip()
            
            # Validate token if enabled
            if enabled:
                if not token:
                    messagebox.showerror("Error", "Bot token is required when Telegram notifications are enabled.")
                    return
                    
                # Set the token
                os.environ["TELEGRAM_BOT_TOKEN"] = token
                
                # Get chat IDs from the text field
                chat_ids_text = self.telegram_chats_text.get(1.0, tk.END).strip()
                chat_ids = [line.strip() for line in chat_ids_text.split('\n') if line.strip()]
                
                # Restart the bot
                self.telegram_bot.stop()
                
                # Create a new bot instance with the new token
                self.telegram_bot = TelegramBot(self.db_manager)
                
                # Add the chat IDs
                for chat_id in chat_ids:
                    self.telegram_bot.add_chat(chat_id)
                    
                # Start the bot
                if self.telegram_bot.start():
                    messagebox.showinfo("Success", "Telegram settings saved and bot started successfully.")
                else:
                    messagebox.showerror("Error", "Failed to start Telegram bot.")
            else:
                # Stop the bot
                self.telegram_bot.stop()
                messagebox.showinfo("Success", "Telegram notifications disabled.")
                
        except Exception as e:
            self.logger.error(f"Error saving Telegram settings: {str(e)}")
            messagebox.showerror("Error", f"Failed to save Telegram settings: {str(e)}")
