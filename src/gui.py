import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
from PIL import Image, ImageTk
import datetime
import threading
import calendar
import os
import sys
import logging

# Add src directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class MedicineReminderApp:
    """Main GUI class for the Medicine Reminder Application"""
    
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        
        # Set up the main window
        self.root.title("Medicine Reminder")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Initialize variables
        self.camera_active = False
        self.camera_thread = None
        self.video_capture = None
        
        # Create GUI components
        self.create_menu()
        self.create_notebook()
        
        # Load initial data
        self.load_medicines_data()
        self.update_calendar_view()
        
    def create_menu(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Backup to Cloud", command=self.backup_to_cloud)
        file_menu.add_command(label="Restore from Cloud", command=self.restore_from_cloud)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Find Nearby Pharmacies", command=self.find_pharmacies)
        tools_menu.add_command(label="Settings", command=self.open_settings)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def create_notebook(self):
        """Create the main tabbed interface"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.medicines_tab = ttk.Frame(self.notebook)
        self.scanner_tab = ttk.Frame(self.notebook)
        self.calendar_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.notebook.add(self.medicines_tab, text="Medicines")
        self.notebook.add(self.scanner_tab, text="Barcode Scanner")
        self.notebook.add(self.calendar_tab, text="Calendar")
        
        # Set up each tab
        self.setup_dashboard_tab()
        self.setup_medicines_tab()
        self.setup_scanner_tab()
        self.setup_calendar_tab()
    
    def setup_dashboard_tab(self):
        """Create the dashboard tab with upcoming reminders and statistics"""
        frame = ttk.Frame(self.dashboard_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Medicine Reminder Dashboard", font=("TkDefaultFont", 16, "bold")).pack(pady=(0, 20))
        
        # Upcoming reminders section
        reminders_frame = ttk.LabelFrame(frame, text="Upcoming Reminders")
        reminders_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Reminders list
        self.reminders_tree = ttk.Treeview(reminders_frame, columns=("Medicine", "Dosage", "Time"), show="headings", height=6)
        self.reminders_tree.heading("Medicine", text="Medicine")
        self.reminders_tree.heading("Dosage", text="Dosage")
        self.reminders_tree.heading("Time", text="Reminder Time")
        
        self.reminders_tree.column("Medicine", width=200)
        self.reminders_tree.column("Dosage", width=100)
        self.reminders_tree.column("Time", width=150)
        
        self.reminders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(reminders_frame, orient=tk.VERTICAL, command=self.reminders_tree.yview)
        self.reminders_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Stats section
        stats_frame = ttk.LabelFrame(frame, text="Statistics")
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Statistics grid
        self.total_medicines_label = ttk.Label(stats_frame, text="Total Medicines: 0")
        self.total_medicines_label.grid(row=0, column=0, padx=20, pady=10, sticky=tk.W)
        
        self.expiring_medicines_label = ttk.Label(stats_frame, text="Expiring Soon: 0")
        self.expiring_medicines_label.grid(row=0, column=1, padx=20, pady=10, sticky=tk.W)
        
        self.reminders_today_label = ttk.Label(stats_frame, text="Reminders Today: 0")
        self.reminders_today_label.grid(row=1, column=0, padx=20, pady=10, sticky=tk.W)
        
        self.adherence_label = ttk.Label(stats_frame, text="Adherence Rate: 0%")
        self.adherence_label.grid(row=1, column=1, padx=20, pady=10, sticky=tk.W)
        
        # Action buttons
        buttons_frame = ttk.Frame(frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(buttons_frame, text="Add Medicine", command=self.add_medicine_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Scan Barcode", command=lambda: self.notebook.select(self.scanner_tab)).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="View Calendar", command=lambda: self.notebook.select(self.calendar_tab)).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_dashboard).pack(side=tk.LEFT, padx=5)
        
        # Sync status
        self.sync_status_label = ttk.Label(frame, text="Last synced: Never")
        self.sync_status_label.pack(anchor=tk.E, pady=5)
        
        # Load dashboard data
        self.refresh_dashboard()
    
    def setup_medicines_tab(self):
        """Create the medicines tab with the list of medicines and actions"""
        frame = ttk.Frame(self.medicines_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and add button row
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Medicine List", font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Add New Medicine", command=self.add_medicine_dialog).pack(side=tk.RIGHT)
        
        # Search box
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda name, index, mode: self.filter_medicines())
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT)
        
        # Medicines list
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create treeview for medicines
        self.medicines_tree = ttk.Treeview(
            list_frame, 
            columns=("Name", "Dosage", "Expiry", "Next Reminder"),
            show="headings",
            height=15
        )
        
        # Configure columns
        self.medicines_tree.heading("Name", text="Medicine Name")
        self.medicines_tree.heading("Dosage", text="Dosage")
        self.medicines_tree.heading("Expiry", text="Expiry Date")
        self.medicines_tree.heading("Next Reminder", text="Next Reminder")
        
        self.medicines_tree.column("Name", width=200)
        self.medicines_tree.column("Dosage", width=100)
        self.medicines_tree.column("Expiry", width=100)
        self.medicines_tree.column("Next Reminder", width=150)
        
        self.medicines_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.medicines_tree.yview)
        self.medicines_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click event
        self.medicines_tree.bind("<Double-1>", self.edit_medicine_dialog)
        
        # Button frame
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Edit", command=lambda: self.edit_medicine_dialog(None)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Delete", command=self.delete_medicine).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Take Medicine", command=self.mark_as_taken).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_medicines_data).pack(side=tk.RIGHT)
    
    def setup_scanner_tab(self):
        """Create the barcode scanner tab"""
        frame = ttk.Frame(self.scanner_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Medicine Barcode Scanner", font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 20))
        
        # Camera frame
        self.camera_frame = ttk.LabelFrame(frame, text="Camera")
        self.camera_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Camera view
        self.camera_label = ttk.Label(self.camera_frame)
        self.camera_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Status and result frame
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill=tk.X, pady=10)
        
        self.scan_status_label = ttk.Label(status_frame, text="Status: Ready to scan")
        self.scan_status_label.pack(side=tk.LEFT)
        
        self.barcode_result_label = ttk.Label(status_frame, text="")
        self.barcode_result_label.pack(side=tk.RIGHT)
        
        # Buttons
        buttons_frame = ttk.Frame(frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.start_camera_button = ttk.Button(buttons_frame, text="Start Camera", command=self.toggle_camera)
        self.start_camera_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(buttons_frame, text="Manual Entry", command=self.add_medicine_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Load Image", command=self.load_barcode_image).pack(side=tk.LEFT, padx=5)
    
    def setup_calendar_tab(self):
        """Create the calendar tab with the medicine schedule"""
        frame = ttk.Frame(self.calendar_tab, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and navigation frame
        nav_frame = ttk.Frame(frame)
        nav_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(nav_frame, text="Medicine Schedule", font=("TkDefaultFont", 14, "bold")).pack(side=tk.LEFT)
        
        self.date_label = ttk.Label(nav_frame, text="")
        self.date_label.pack(side=tk.RIGHT)
        
        # Navigation buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="< Previous Month", command=lambda: self.change_month(-1)).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Today", command=self.go_to_today).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Next Month >", command=lambda: self.change_month(1)).pack(side=tk.LEFT)
        
        # Calendar view
        cal_frame = ttk.Frame(frame)
        cal_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create calendar widgets
        self.calendar_cells = []
        self.calendar_dates = []
        
        # Create grid for calendar
        self.calendar_grid = ttk.Frame(cal_frame)
        self.calendar_grid.pack(fill=tk.BOTH, expand=True)
        
        # Day headers
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            ttk.Label(
                self.calendar_grid, 
                text=day, 
                anchor="center",
                font=("TkDefaultFont", 10, "bold")
            ).grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
        
        # Calendar cells (6 rows, 7 columns)
        for row in range(6):
            for col in range(7):
                cell_frame = ttk.Frame(self.calendar_grid, borderwidth=1, relief="solid")
                cell_frame.grid(row=row+1, column=col, sticky="nsew", padx=2, pady=2)
                cell_frame.rowconfigure(0, weight=0)  # Date label
                cell_frame.rowconfigure(1, weight=1)  # Content
                
                date_label = ttk.Label(cell_frame, text="", anchor="nw")
                date_label.grid(row=0, column=0, sticky="nw", padx=5, pady=2)
                
                content_frame = ttk.Frame(cell_frame)
                content_frame.grid(row=1, column=0, sticky="nsew", padx=3, pady=3)
                
                self.calendar_dates.append(date_label)
                self.calendar_cells.append(content_frame)
        
        # Configure grid weights
        for i in range(7):
            self.calendar_grid.columnconfigure(i, weight=1)
        for i in range(7):
            self.calendar_grid.rowconfigure(i, weight=1)
        
        # Set current date
        self.current_year = datetime.datetime.now().year
        self.current_month = datetime.datetime.now().month
        
        # Daily schedule view
        schedule_frame = ttk.LabelFrame(frame, text="Daily Schedule")
        schedule_frame.pack(fill=tk.X, pady=10)
        
        self.selected_date_label = ttk.Label(schedule_frame, text="No date selected", font=("TkDefaultFont", 11, "bold"))
        self.selected_date_label.pack(anchor="w", padx=10, pady=(5, 10))
        
        # Daily reminders list
        self.daily_reminders_frame = ttk.Frame(schedule_frame)
        self.daily_reminders_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Update calendar
        self.update_calendar_view()
        
    def load_medicines_data(self):
        """Load medicines data from database and populate the treeview"""
        try:
            # Clear existing data
            for item in self.medicines_tree.get_children():
                self.medicines_tree.delete(item)
            
            # Get medicines from database
            medicines = self.controller.db.get_all_medicines()
            
            # Add to treeview
            for medicine in medicines:
                self.medicines_tree.insert(
                    "", "end", 
                    values=(
                        medicine["name"],
                        medicine["dosage"],
                        medicine["expiry_date"],
                        medicine["next_reminder"]
                    ),
                    iid=medicine["id"]
                )
        except Exception as e:
            logger.error(f"Error loading medicines data: {e}")
            messagebox.showerror("Error", f"Failed to load medicines: {e}")
    
    def refresh_dashboard(self):
        """Refresh dashboard data"""
        try:
            # Clear existing reminders
            for item in self.reminders_tree.get_children():
                self.reminders_tree.delete(item)
            
            # Get upcoming reminders
            now = datetime.datetime.now()
            tomorrow = now + datetime.timedelta(days=1)
            reminders = self.controller.db.get_upcoming_reminders(now, tomorrow)
            
            # Add to reminders tree
            for reminder in reminders:
                self.reminders_tree.insert(
                    "", "end",
                    values=(
                        reminder["name"],
                        reminder["dosage"],
                        reminder["next_reminder"]
                    )
                )
            
            # Update statistics
            all_medicines = self.controller.db.get_all_medicines()
            expiring_soon = [m for m in all_medicines if self._is_expiring_soon(m["expiry_date"])]
            
            today_reminders = self.controller.db.get_todays_reminders()
            adherence_rate = self.controller.db.get_adherence_rate()
            
            # Update labels
            self.total_medicines_label.config(text=f"Total Medicines: {len(all_medicines)}")
            self.expiring_medicines_label.config(text=f"Expiring Soon: {len(expiring_soon)}")
            self.reminders_today_label.config(text=f"Reminders Today: {len(today_reminders)}")
            self.adherence_label.config(text=f"Adherence Rate: {adherence_rate:.1f}%")
            
            # Update sync status
            last_sync = self.controller.cloud_sync.get_last_sync_time()
            if last_sync:
                self.sync_status_label.config(text=f"Last synced: {last_sync}")
            else:
                self.sync_status_label.config(text="Last synced: Never")
                
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
            messagebox.showerror("Error", f"Failed to refresh dashboard: {e}")
    
    def _is_expiring_soon(self, expiry_date_str):
        """Check if a medicine is expiring within 30 days"""
        try:
            expiry_date = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d")
            now = datetime.datetime.now()
            days_remaining = (expiry_date - now).days
            return 0 <= days_remaining <= 30
        except:
            return False
    
    def filter_medicines(self):
        """Filter medicines list based on search text"""
        search_text = self.search_var.get().lower()
        
        # Clear the tree
        for item in self.medicines_tree.get_children():
            self.medicines_tree.delete(item)
        
        # Filter and re-populate
        medicines = self.controller.db.get_all_medicines()
        for medicine in medicines:
            if (search_text in medicine["name"].lower() or 
                search_text in medicine["dosage"].lower()):
                self.medicines_tree.insert(
                    "", "end", 
                    values=(
                        medicine["name"],
                        medicine["dosage"],
                        medicine["expiry_date"],
                        medicine["next_reminder"]
                    ),
                    iid=medicine["id"]
                )
    
    def add_medicine_dialog(self):
        """Open dialog to add a new medicine"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Medicine")
        dialog.geometry("500x550")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form frame
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Form fields
        ttk.Label(form_frame, text="Medicine Information", font=("TkDefaultFont", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        
        # Barcode
        ttk.Label(form_frame, text="Barcode:").grid(row=1, column=0, sticky="w", pady=5)
        barcode_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=barcode_var, width=30).grid(row=1, column=1, sticky="w")
        
        # Name
        ttk.Label(form_frame, text="Name:").grid(row=2, column=0, sticky="w", pady=5)
        name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=2, column=1, sticky="w")
        
        # Dosage
        ttk.Label(form_frame, text="Dosage:").grid(row=3, column=0, sticky="w", pady=5)
        dosage_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=dosage_var, width=30).grid(row=3, column=1, sticky="w")
        
        # Expiry date
        ttk.Label(form_frame, text="Expiry Date:").grid(row=4, column=0, sticky="w", pady=5)
        expiry_frame = ttk.Frame(form_frame)
        expiry_frame.grid(row=4, column=1, sticky="w")
        
        # Date picker components
        year_var = tk.StringVar(value=str(datetime.datetime.now().year))
        month_var = tk.StringVar(value=str(datetime.datetime.now().month))
        day_var = tk.StringVar(value=str(datetime.datetime.now().day))
        
        ttk.Spinbox(expiry_frame, from_=1, to=31, width=3, textvariable=day_var).pack(side=tk.LEFT)
        ttk.Label(expiry_frame, text="/").pack(side=tk.LEFT)
        ttk.Spinbox(expiry_frame, from_=1, to=12, width=3, textvariable=month_var).pack(side=tk.LEFT)
        ttk.Label(expiry_frame, text="/").pack(side=tk.LEFT)
        ttk.Spinbox(expiry_frame, from_=2023, to=2050, width=5, textvariable=year_var).pack(side=tk.LEFT)
        
        # Reminders section
        ttk.Label(form_frame, text="Reminder Settings", font=("TkDefaultFont", 12, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(20, 15))
        
        # Reminder frequency
        ttk.Label(form_frame, text="Frequency:").grid(row=6, column=0, sticky="w", pady=5)
        frequency_var = tk.StringVar(value="daily")
        ttk.Combobox(form_frame, textvariable=frequency_var, 
                    values=["daily", "weekly", "monthly"]).grid(row=6, column=1, sticky="w")
        
        # Times per day
        ttk.Label(form_frame, text="Times per Day:").grid(row=7, column=0, sticky="w", pady=5)
        times_var = tk.IntVar(value=1)
        ttk.Spinbox(form_frame, from_=1, to=5, width=5, textvariable=times_var).grid(row=7, column=1, sticky="w")
        
        # Reminder time
        ttk.Label(form_frame, text="First Reminder:").grid(row=8, column=0, sticky="w", pady=5)
        time_frame = ttk.Frame(form_frame)
        time_frame.grid(row=8, column=1, sticky="w")
        
        hour_var = tk.StringVar(value="9")
        minute_var = tk.StringVar(value="00")
        
        ttk.Spinbox(time_frame, from_=0, to=23, width=3, textvariable=hour_var).pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)
        ttk.Spinbox(time_frame, from_=0, to=59, width=3, textvariable=minute_var).pack(side=tk.LEFT)
        
        # Notification options
        ttk.Label(form_frame, text="Notifications", font=("TkDefaultFont", 12, "bold")).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(20, 15))
        
        # System notifications
        system_notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="System Notifications", 
                       variable=system_notify_var).grid(row=10, column=0, sticky="w", pady=5)
        
        # Telegram notifications
        telegram_notify_var = tk.BooleanVar(value=False)
        telegram_check = ttk.Checkbutton(form_frame, text="Telegram Notifications", 
                                         variable=telegram_notify_var)
        telegram_check.grid(row=10, column=1, sticky="w", pady=5)
        
        # Disable Telegram option if not configured
        if not self.controller.telegram_bot:
            telegram_check.configure(state="disabled")
        
        # Google Calendar sync
        calendar_sync_var = tk.BooleanVar(value=False)
        calendar_check = ttk.Checkbutton(form_frame, text="Add to Google Calendar", 
                                       variable=calendar_sync_var)
        calendar_check.grid(row=11, column=0, sticky="w", pady=5)
        
        # Disable calendar option if not authenticated
        if not self.controller.calendar.is_authenticated():
            calendar_check.configure(state="disabled")
        
        # Button frame
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=12, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Save button with form validation and processing
        def save_medicine():
            try:
                # Validate inputs
                if not name_var.get().strip():
                    messagebox.showerror("Error", "Medicine name is required")
                    return
                
                # Create expiry date string
                try:
                    expiry_date = f"{year_var.get()}-{int(month_var.get()):02d}-{int(day_var.get()):02d}"
                    datetime.datetime.strptime(expiry_date, "%Y-%m-%d")  # Validate format
                except ValueError:
                    messagebox.showerror("Error", "Invalid expiry date")
                    return
                
                # Create reminder time
                try:
                    reminder_time = f"{int(hour_var.get()):02d}:{int(minute_var.get()):02d}"
                except ValueError:
                    messagebox.showerror("Error", "Invalid reminder time")
                    return
                
                # Save medicine to database
                medicine_data = {
                    "barcode": barcode_var.get().strip(),
                    "name": name_var.get().strip(),
                    "dosage": dosage_var.get().strip(),
                    "expiry_date": expiry_date,
                    "reminder_frequency": frequency_var.get(),
                    "times_per_day": times_var.get(),
                    "reminder_time": reminder_time,
                    "system_notify": system_notify_var.get(),
                    "telegram_notify": telegram_notify_var.get(),
                    "calendar_sync": calendar_sync_var.get()
                }
                
                self.controller.db.add_medicine(medicine_data)
                
                # Add to Google Calendar if enabled
                if calendar_sync_var.get() and self.controller.calendar.is_authenticated():
                    self.controller.calendar.add_medicine_reminder(medicine_data)
                
                # Refresh data
                self.load_medicines_data()
                self.refresh_dashboard()
                self.update_calendar_view()
                
                dialog.destroy()
                messagebox.showinfo("Success", f"Medicine '{name_var.get()}' added successfully")
                
            except Exception as e:
                logger.error(f"Error adding medicine: {e}")
                messagebox.showerror("Error", f"Failed to add medicine: {e}")
        
        ttk.Button(button_frame, text="Save", command=save_medicine).pack(side=tk.LEFT, padx=5)
    
    def edit_medicine_dialog(self, event=None):
        """Open dialog to edit an existing medicine"""
        # Get selected item
        selected_id = self.medicines_tree.focus()
        if not selected_id:
            messagebox.showinfo("Information", "Please select a medicine to edit")
            return
        
        try:
            # Get medicine data
            medicine = self.controller.db.get_medicine_by_id(selected_id)
            if not medicine:
                messagebox.showerror("Error", "Failed to retrieve medicine details")
                return
            
            # Create dialog similar to add_medicine_dialog, but pre-populate fields
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Medicine: {medicine['name']}")
            dialog.geometry("500x550")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Form frame
            form_frame = ttk.Frame(dialog, padding=20)
            form_frame.pack(fill=tk.BOTH, expand=True)
            
            # Form fields with pre-populated data
            ttk.Label(form_frame, text="Medicine Information", font=("TkDefaultFont", 12, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
            
            # Barcode
            ttk.Label(form_frame, text="Barcode:").grid(row=1, column=0, sticky="w", pady=5)
            barcode_var = tk.StringVar(value=medicine.get("barcode", ""))
            ttk.Entry(form_frame, textvariable=barcode_var, width=30).grid(row=1, column=1, sticky="w")
            
            # Name
            ttk.Label(form_frame, text="Name:").grid(row=2, column=0, sticky="w", pady=5)
            name_var = tk.StringVar(value=medicine["name"])
            ttk.Entry(form_frame, textvariable=name_var, width=30).grid(row=2, column=1, sticky="w")
            
            # Dosage
            ttk.Label(form_frame, text="Dosage:").grid(row=3, column=0, sticky="w", pady=5)
            dosage_var = tk.StringVar(value=medicine["dosage"])
            ttk.Entry(form_frame, textvariable=dosage_var, width=30).grid(row=3, column=1, sticky="w")
            
            # Expiry date
            ttk.Label(form_frame, text="Expiry Date:").grid(row=4, column=0, sticky="w", pady=5)
            expiry_frame = ttk.Frame(form_frame)
            expiry_frame.grid(row=4, column=1, sticky="w")
            
            # Parse existing expiry date
            expiry_parts = medicine["expiry_date"].split("-")
            year_var = tk.StringVar(value=expiry_parts[0])
            month_var = tk.StringVar(value=expiry_parts[1].lstrip("0"))
            day_var = tk.StringVar(value=expiry_parts[2].lstrip("0"))
            
            ttk.Spinbox(expiry_frame, from_=1, to=31, width=3, textvariable=day_var).pack(side=tk.LEFT)
            ttk.Label(expiry_frame, text="/").pack(side=tk.LEFT)
            ttk.Spinbox(expiry_frame, from_=1, to=12, width=3, textvariable=month_var).pack(side=tk.LEFT)
            ttk.Label(expiry_frame, text="/").pack(side=tk.LEFT)
            ttk.Spinbox(expiry_frame, from_=2023, to=2050, width=5, textvariable=year_var).pack(side=tk.LEFT)
            
            # Reminders section
            ttk.Label(form_frame, text="Reminder Settings", font=("TkDefaultFont", 12, "bold")).grid(
                row=5, column=0, columnspan=2, sticky="w", pady=(20, 15))
            
            # Reminder frequency
            ttk.Label(form_frame, text="Frequency:").grid(row=6, column=0, sticky="w", pady=5)
            frequency_var = tk.StringVar(value=medicine.get("reminder_frequency", "daily"))
            ttk.Combobox(form_frame, textvariable=frequency_var, 
                        values=["daily", "weekly", "monthly"]).grid(row=6, column=1, sticky="w")
            
            # Times per day
            ttk.Label(form_frame, text="Times per Day:").grid(row=7, column=0, sticky="w", pady=5)
            times_var = tk.IntVar(value=medicine.get("times_per_day", 1))
            ttk.Spinbox(form_frame, from_=1, to=5, width=5, textvariable=times_var).grid(row=7, column=1, sticky="w")
            
            # Reminder time
            ttk.Label(form_frame, text="First Reminder:").grid(row=8, column=0, sticky="w", pady=5)
            time_frame = ttk.Frame(form_frame)
            time_frame.grid(row=8, column=1, sticky="w")
            
            # Parse existing reminder time
            reminder_parts = medicine.get("reminder_time", "09:00").split(":")
            hour_var = tk.StringVar(value=reminder_parts[0].lstrip("0") or "0")
            minute_var = tk.StringVar(value=reminder_parts[1].lstrip("0") or "0")
            
            ttk.Spinbox(time_frame, from_=0, to=23, width=3, textvariable=hour_var).pack(side=tk.LEFT)
            ttk.Label(time_frame, text=":").pack(side=tk.LEFT)
            ttk.Spinbox(time_frame, from_=0, to=59, width=3, textvariable=minute_var).pack(side=tk.LEFT)
            
            # Notification options
            ttk.Label(form_frame, text="Notifications", font=("TkDefaultFont", 12, "bold")).grid(
                row=9, column=0, columnspan=2, sticky="w", pady=(20, 15))
            
            # System notifications
            system_notify_var = tk.BooleanVar(value=medicine.get("system_notify", True))
            ttk.Checkbutton(form_frame, text="System Notifications", 
                           variable=system_notify_var).grid(row=10, column=0, sticky="w", pady=5)
            
            # Telegram notifications
            telegram_notify_var = tk.BooleanVar(value=medicine.get("telegram_notify", False))
            telegram_check = ttk.Checkbutton(form_frame, text="Telegram Notifications", 
                                             variable=telegram_notify_var)
            telegram_check.grid(row=10, column=1, sticky="w", pady=5)
            
            # Disable Telegram option if not configured
            if not self.controller.telegram_bot:
                telegram_check.configure(state="disabled")
            
            # Google Calendar sync
            calendar_sync_var = tk.BooleanVar(value=medicine.get("calendar_sync", False))
            calendar_check = ttk.Checkbutton(form_frame, text="Add to Google Calendar", 
                                           variable=calendar_sync_var)
            calendar_check.grid(row=11, column=0, sticky="w", pady=5)
            
            # Disable calendar option if not authenticated
            if not self.controller.calendar.is_authenticated():
                calendar_check.configure(state="disabled")
            
            # Button frame
            button_frame = ttk.Frame(form_frame)
            button_frame.grid(row=12, column=0, columnspan=2, pady=20)
            
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
            
            # Save button with form validation and processing
            def update_medicine():
                try:
                    # Validate inputs
                    if not name_var.get().strip():
                        messagebox.showerror("Error", "Medicine name is required")
                        return
                    
                    # Create expiry date string
                    try:
                        expiry_date = f"{year_var.get()}-{int(month_var.get()):02d}-{int(day_var.get()):02d}"
                        datetime.datetime.strptime(expiry_date, "%Y-%m-%d")  # Validate format
                    except ValueError:
                        messagebox.showerror("Error", "Invalid expiry date")
                        return
                    
                    # Create reminder time
                    try:
                        reminder_time = f"{int(hour_var.get()):02d}:{int(minute_var.get()):02d}"
                    except ValueError:
                        messagebox.showerror("Error", "Invalid reminder time")
                        return
                    
                    # Update medicine in database
                    medicine_data = {
                        "id": selected_id,
                        "barcode": barcode_var.get().strip(),
                        "name": name_var.get().strip(),
                        "dosage": dosage_var.get().strip(),
                        "expiry_date": expiry_date,
                        "reminder_frequency": frequency_var.get(),
                        "times_per_day": times_var.get(),
                        "reminder_time": reminder_time,
                        "system_notify": system_notify_var.get(),
                        "telegram_notify": telegram_notify_var.get(),
                        "calendar_sync": calendar_sync_var.get()
                    }
                    
                    self.controller.db.update_medicine(medicine_data)
                    
                    # Update in Google Calendar if enabled
                    if calendar_sync_var.get() and self.controller.calendar.is_authenticated():
                        self.controller.calendar.update_medicine_reminder(medicine_data)
                    
                    # Refresh data
                    self.load_medicines_data()
                    self.refresh_dashboard()
                    self.update_calendar_view()
                    
                    dialog.destroy()
                    messagebox.showinfo("Success", f"Medicine '{name_var.get()}' updated successfully")
                    
                except Exception as e:
                    logger.error(f"Error updating medicine: {e}")
                    messagebox.showerror("Error", f"Failed to update medicine: {e}")
            
            ttk.Button(button_frame, text="Save Changes", command=update_medicine).pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            logger.error(f"Error editing medicine: {e}")
            messagebox.showerror("Error", f"Failed to open edit dialog: {e}")
    
    def delete_medicine(self):
        """Delete selected medicine"""
        selected_id = self.medicines_tree.focus()
        if not selected_id:
            messagebox.showinfo("Information", "Please select a medicine to delete")
            return
        
        try:
            # Get medicine name
            medicine = self.controller.db.get_medicine_by_id(selected_id)
            if not medicine:
                messagebox.showerror("Error", "Failed to retrieve medicine details")
                return
            
            # Confirm deletion
            if messagebox.askyesno("Confirm Deletion", 
                                  f"Are you sure you want to delete '{medicine['name']}'?"):
                # Delete from database
                self.controller.db.delete_medicine(selected_id)
                
                # Remove from Google Calendar if synced
                if medicine.get("calendar_sync", False) and self.controller.calendar.is_authenticated():
                    self.controller.calendar.delete_medicine_reminder(medicine)
                
                # Refresh data
                self.load_medicines_data()
                self.refresh_dashboard()
                self.update_calendar_view()
                
                messagebox.showinfo("Success", f"Medicine '{medicine['name']}' deleted successfully")
        
        except Exception as e:
            logger.error(f"Error deleting medicine: {e}")
            messagebox.showerror("Error", f"Failed to delete medicine: {e}")
    
    def mark_as_taken(self):
        """Mark selected medicine as taken"""
        selected_id = self.medicines_tree.focus()
        if not selected_id:
            messagebox.showinfo("Information", "Please select a medicine to mark as taken")
            return
        
        try:
            # Get medicine name
            medicine = self.controller.db.get_medicine_by_id(selected_id)
            if not medicine:
                messagebox.showerror("Error", "Failed to retrieve medicine details")
                return
            
            # Mark as taken in database
            self.controller.db.mark_medicine_taken(selected_id)
            
            # Refresh data
            self.load_medicines_data()
            self.refresh_dashboard()
            
            messagebox.showinfo("Success", f"'{medicine['name']}' marked as taken")
            
            # Update streaks and gamification
            streak = self.controller.db.get_current_streak()
            if streak and streak % 5 == 0:  # Milestone streak
                messagebox.showinfo("Achievement", 
                                   f"Congratulations! You've maintained a {streak}-day streak!")
            
        except Exception as e:
            logger.error(f"Error marking medicine as taken: {e}")
            messagebox.showerror("Error", f"Failed to mark medicine as taken: {e}")
    
    def toggle_camera(self):
        """Start or stop the camera for barcode scanning"""
        if self.camera_active:
            # Stop camera
            self.camera_active = False
            self.start_camera_button.config(text="Start Camera")
            
            if self.video_capture:
                self.video_capture.release()
                self.video_capture = None
            
            # Clear camera display
            self.camera_label.config(image="")
            self.scan_status_label.config(text="Status: Camera stopped")
            
        else:
            # Start camera
            try:
                self.video_capture = cv2.VideoCapture(0)
                if not self.video_capture.isOpened():
                    raise Exception("Could not open camera")
                
                self.camera_active = True
                self.start_camera_button.config(text="Stop Camera")
                self.scan_status_label.config(text="Status: Scanning...")
                
                # Start scanning thread
                self.camera_thread = threading.Thread(target=self.scan_barcode_loop)
                self.camera_thread.daemon = True
                self.camera_thread.start()
                
            except Exception as e:
                logger.error(f"Error starting camera: {e}")
                messagebox.showerror("Camera Error", f"Failed to start camera: {e}")
    
    def scan_barcode_loop(self):
        """Loop to continuously scan for barcodes"""
        last_scan_time = 0
        last_barcode = None
        
        while self.camera_active and self.video_capture and self.video_capture.isOpened():
            try:
                # Read frame
                ret, frame = self.video_capture.read()
                if not ret:
                    continue
                
                # Convert to RGB for display
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Scan for barcodes
                current_time = time.time()
                if current_time - last_scan_time > 0.5:  # Scan every 0.5 seconds
                    last_scan_time = current_time
                    barcodes = self.controller.scanner.scan_image(rgb_frame)
                    
                    # If barcode found and it's new
                    if barcodes and barcodes[0] != last_barcode:
                        last_barcode = barcodes[0]
                        
                        # Update UI from main thread
                        self.root.after(0, self.process_scanned_barcode, last_barcode)
                
                # Display the frame
                img = Image.fromarray(rgb_frame)
                img = img.resize((640, 480))
                img_tk = ImageTk.PhotoImage(image=img)
                
                # Update label (must keep a reference to image)
                self.camera_label.img_tk = img_tk
                self.camera_label.config(image=img_tk)
                
                # Sleep briefly to reduce CPU usage
                time.sleep(0.03)
                
            except Exception as e:
                logger.error(f"Error in scanning loop: {e}")
                self.root.after(0, lambda: self.scan_status_label.config(
                    text=f"Scanning error: {e}"))
                break
        
        # Clean up
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None
    
    def process_scanned_barcode(self, barcode):
        """Process a scanned barcode"""
        # Update status
        self.barcode_result_label.config(text=f"Barcode: {barcode}")
        
        # Check if medicine already exists
        medicine = self.controller.db.get_medicine_by_barcode(barcode)
        
        if medicine:
            self.scan_status_label.config(text=f"Found: {medicine['name']}")
            
            # Show medicine details
            messagebox.showinfo("Medicine Found", 
                               f"Name: {medicine['name']}\n"
                               f"Dosage: {medicine['dosage']}\n"
                               f"Expiry: {medicine['expiry_date']}")
        else:
            self.scan_status_label.config(text="New medicine detected")
            
            # Look up medicine details (mock function)
            if messagebox.askyesno("New Medicine", 
                                  f"Barcode {barcode} not found in database. Add new medicine?"):
                # Pre-fill barcode in add form
                self.toggle_camera()  # Stop camera first
                
                # Open add form with barcode pre-filled
                dialog = tk.Toplevel(self.root)
                dialog.title("Add New Medicine")
                dialog.geometry("500x550")
                dialog.transient(self.root)
                dialog.grab_set()
                
                # Create form (simplified version of add_medicine_dialog)
                form_frame = ttk.Frame(dialog, padding=20)
                form_frame.pack(fill=tk.BOTH, expand=True)
                
                # Barcode (pre-filled)
                ttk.Label(form_frame, text="Barcode:").grid(row=0, column=0, sticky="w", pady=5)
                barcode_var = tk.StringVar(value=barcode)
                ttk.Entry(form_frame, textvariable=barcode_var, width=30, state="readonly").grid(
                    row=0, column=1, sticky="w")
                
                # Rest of form would be added here...
                # (Using the same form as in add_medicine_dialog)
    
    def load_barcode_image(self):
        """Load barcode from an image file"""
        file_path = filedialog.askopenfilename(
            title="Select Barcode Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        
        if not file_path:
            return
        
        try:
            # Load and scan image
            image = cv2.imread(file_path)
            if image is None:
                raise Exception("Failed to load image")
            
            # Convert to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Scan for barcodes
            barcodes = self.controller.scanner.scan_image(rgb_image)
            
            if not barcodes:
                messagebox.showinfo("Scan Result", "No barcode found in the image")
                return
            
            # Process the first barcode found
            self.process_scanned_barcode(barcodes[0])
            
            # Display the image
            img = Image.fromarray(rgb_image)
            img = img.resize((640, 480), Image.LANCZOS)
            img_tk = ImageTk.PhotoImage(image=img)
            
            # Update label
            self.camera_label.img_tk = img_tk
            self.camera_label.config(image=img_tk)
            
        except Exception as e:
            logger.error(f"Error loading barcode image: {e}")
            messagebox.showerror("Error", f"Failed to process image: {e}")
    
    def update_calendar_view(self):
        """Update the calendar view with medicine schedules"""
        try:
            # Clear previous calendar data
            for cell in self.calendar_cells:
                for widget in cell.winfo_children():
                    widget.destroy()
            
            # Update date label
            self.date_label.config(text=f"{calendar.month_name[self.current_month]} {self.current_year}")
            
            # Get first day of month and number of days
            first_day = datetime.datetime(self.current_year, self.current_month, 1)
            _, num_days = calendar.monthrange(self.current_year, self.current_month)
            
            # Calculate day offset (0 = Monday in our grid)
            first_weekday = first_day.weekday()  # 0 = Monday, 6 = Sunday
            
            # Get medicine schedule for this month
            month_schedule = self.controller.db.get_month_schedule(
                self.current_year, self.current_month)
            
            # Fill in the calendar
            for i in range(42):  # 6 rows * 7 columns
                cell_index = i % 42
                day = i - first_weekday + 1
                
                if 1 <= day <= num_days:
                    # Set the date number
                    self.calendar_dates[cell_index].config(text=str(day))
                    
                    # Check if current date
                    now = datetime.datetime.now()
                    if (day == now.day and self.current_month == now.month and 
                        self.current_year == now.year):
                        self.calendar_dates[cell_index].config(
                            foreground="white", 
                            background="#4a86e8",
                            font=("TkDefaultFont", 10, "bold")
                        )
                    else:
                        self.calendar_dates[cell_index].config(
                            foreground="black", 
                            background="",
                            font=("TkDefaultFont", 10, "normal")
                        )
                    
                    # Add medicine reminders for this day
                    date_str = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
                    if date_str in month_schedule:
                        medicines = month_schedule[date_str]
                        self._add_medicines_to_cell(self.calendar_cells[cell_index], medicines, day)
                else:
                    # Clear cell for days outside current month
                    self.calendar_dates[cell_index].config(text="")
            
        except Exception as e:
            logger.error(f"Error updating calendar: {e}")
            messagebox.showerror("Error", f"Failed to update calendar: {e}")
    
    def _add_medicines_to_cell(self, cell, medicines, day):
        """Add medicine indicators to a calendar cell"""
        if not medicines:
            return
        
        # Create a canvas for medicine indicators
        canvas = tk.Canvas(cell, height=60, bg="white", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Add medicine indicators (limited to first 3)
        y_pos = 5
        for i, medicine in enumerate(medicines[:3]):
            # Draw a colored pill icon
            color = ["#4a86e8", "#e67c73", "#f6bf26", "#33a853"][i % 4]
            canvas.create_rectangle(5, y_pos, 15, y_pos+10, fill=color, outline="")
            canvas.create_text(20, y_pos+5, text=medicine["name"], anchor="w")
            y_pos += 15
        
        # Indicate if there are more medicines
        if len(medicines) > 3:
            canvas.create_text(5, y_pos+5, text=f"+ {len(medicines)-3} more...", anchor="w")
        
        # Make the cell clickable to show details
        canvas.bind("<Button-1>", lambda e, d=day: self.show_day_schedule(d))
        
    def show_day_schedule(self, day):
        """Show the medicine schedule for a selected day"""
        try:
            # Clear previous day schedule
            for widget in self.daily_reminders_frame.winfo_children():
                widget.destroy()
            
            # Format date
            selected_date = datetime.datetime(self.current_year, self.current_month, day)
            formatted_date = selected_date.strftime("%A, %B %d, %Y")
            self.selected_date_label.config(text=formatted_date)
            
            # Get medicines for this day
            date_str = f"{self.current_year}-{self.current_month:02d}-{day:02d}"
            medicines = self.controller.db.get_day_schedule(date_str)
            
            if not medicines:
                ttk.Label(self.daily_reminders_frame, 
                          text="No medicines scheduled for this day").pack(pady=10)
                return
            
            # Sort by time
            medicines.sort(key=lambda m: m.get("reminder_time", "00:00"))
            
            # Create a list of medicines
            for medicine in medicines:
                med_frame = ttk.Frame(self.daily_reminders_frame)
                med_frame.pack(fill=tk.X, pady=5)
                
                time_str = medicine.get("reminder_time", "")
                name_str = medicine.get("name", "Unknown")
                dosage_str = medicine.get("dosage", "")
                
                ttk.Label(med_frame, text=time_str, width=10).pack(side=tk.LEFT)
                ttk.Label(med_frame, text=name_str, width=20).pack(side=tk.LEFT, padx=5)
                ttk.Label(med_frame, text=dosage_str).pack(side=tk.LEFT, padx=5)
                
                # Add buttons
                ttk.Button(med_frame, text="Edit", 
                          command=lambda id=medicine.get("id"): self.edit_scheduled_medicine(id)).pack(
                    side=tk.RIGHT, padx=2)
                
                # Check if it's today
                now = datetime.datetime.now()
                if (day == now.day and self.current_month == now.month and 
                    self.current_year == now.year):
                    ttk.Button(med_frame, text="Take", 
                              command=lambda id=medicine.get("id"): self.mark_medicine_taken(id)).pack(
                        side=tk.RIGHT, padx=2)
            
        except Exception as e:
            logger.error(f"Error showing day schedule: {e}")
            messagebox.showerror("Error", f"Failed to show schedule: {e}")
    
    def edit_scheduled_medicine(self, medicine_id):
        """Edit a medicine from the schedule view"""
        # Redirect to the main edit function with the ID
        self.medicines_tree.selection_set(medicine_id)
        self.medicines_tree.focus(medicine_id)
        self.notebook.select(self.medicines_tab)
        self.edit_medicine_dialog()
    
    def mark_medicine_taken(self, medicine_id):
        """Mark a medicine as taken from the schedule view"""
        try:
            # Mark as taken in database
            self.controller.db.mark_medicine_taken(medicine_id)
            
            # Refresh views
            self.refresh_dashboard()
            self.update_calendar_view()
            
            # Show current day schedule again
            self.show_day_schedule(datetime.datetime.now().day)
            
            messagebox.showinfo("Success", "Medicine marked as taken")
            
        except Exception as e:
            logger.error(f"Error marking medicine as taken: {e}")
            messagebox.showerror("Error", f"Failed to mark medicine as taken: {e}")
    
    def change_month(self, offset):
        """Change the displayed month by the given offset"""
        month = self.current_month + offset
        year = self.current_year
        
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
            
        self.current_month = month
        self.current_year = year
        self.update_calendar_view()
    
    def go_to_today(self):
        """Reset calendar to current month"""
        now = datetime.datetime.now()
        self.current_month = now.month
        self.current_year = now.year
        self.update_calendar_view()
        
        # Show today's schedule
        self.show_day_schedule(now.day)
    
    def find_pharmacies(self):
        """Open pharmacy locator dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nearby Pharmacy Locator")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Find Nearby Pharmacies", 
                 font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 20))
        
        # Location input
        location_frame = ttk.Frame(main_frame)
        location_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(location_frame, text="Your Location:").grid(row=0, column=0, padx=5, pady=5)
        
        # Latitude and longitude inputs
        lat_var = tk.StringVar()
        lon_var = tk.StringVar()
        
        ttk.Label(location_frame, text="Latitude:").grid(row=0, column=1, padx=5, pady=5)
        ttk.Entry(location_frame, textvariable=lat_var, width=10).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(location_frame, text="Longitude:").grid(row=0, column=3, padx=5, pady=5)
        ttk.Entry(location_frame, textvariable=lon_var, width=10).grid(row=0, column=4, padx=5, pady=5)
        
        # Radius selection
        radius_frame = ttk.Frame(main_frame)
        radius_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(radius_frame, text="Search Radius (meters):").pack(side=tk.LEFT, padx=5)
        
        radius_var = tk.StringVar(value="5000")
        ttk.Combobox(radius_frame, textvariable=radius_var, 
                    values=["1000", "2000", "5000", "10000"]).pack(side=tk.LEFT, padx=5)
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Pharmacies")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Results list
        self.pharmacy_tree = ttk.Treeview(
            results_frame, 
            columns=("Name", "Distance", "Coordinates"),
            show="headings",
            height=10
        )
        
        self.pharmacy_tree.heading("Name", text="Pharmacy Name")
        self.pharmacy_tree.heading("Distance", text="Distance")
        self.pharmacy_tree.heading("Coordinates", text="Coordinates")
        
        self.pharmacy_tree.column("Name", width=200)
        self.pharmacy_tree.column("Distance", width=100)
        self.pharmacy_tree.column("Coordinates", width=200)
        
        self.pharmacy_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.pharmacy_tree.yview)
        self.pharmacy_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status label
        self.pharmacy_status_label = ttk.Label(main_frame, text="")
        self.pharmacy_status_label.pack(fill=tk.X, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Use current location button
        def use_current_location():
            # This would use geolocation in a real application
            # For demo, use a default location
            lat_var.set("37.7749")
            lon_var.set("-122.4194")
            messagebox.showinfo("Location", "Using demo location (San Francisco)")
        
        ttk.Button(button_frame, text="Use Current Location", 
                  command=use_current_location).pack(side=tk.LEFT, padx=5)
        
        # Search button
        def search_pharmacies():
            try:
                # Validate inputs
                try:
                    lat = float(lat_var.get())
                    lon = float(lon_var.get())
                    radius = int(radius_var.get())
                except ValueError:
                    raise ValueError("Please enter valid latitude, longitude, and radius")
                
                # Clear previous results
                for item in self.pharmacy_tree.get_children():
                    self.pharmacy_tree.delete(item)
                
                # Update status
                self.pharmacy_status_label.config(text="Searching for pharmacies...")
                
                # Search for pharmacies
                pharmacies = self.controller.pharmacy_locator.find_nearby_pharmacies(lat, lon, radius)
                
                if not pharmacies:
                    self.pharmacy_status_label.config(text="No pharmacies found nearby.")
                    return
                
                # Add results to tree
                for i, pharmacy in enumerate(pharmacies):
                    # Calculate rough distance (simplified)
                    p_lat = pharmacy["lat"]
                    p_lon = pharmacy["lon"]
                    distance = self.controller.pharmacy_locator.calculate_distance(
                        lat, lon, p_lat, p_lon)
                    
                    self.pharmacy_tree.insert(
                        "", "end", 
                        values=(
                            pharmacy["name"],
                            f"{distance:.1f} km",
                            f"{p_lat:.6f}, {p_lon:.6f}"
                        ),
                        iid=i
                    )
                
                self.pharmacy_status_label.config(
                    text=f"Found {len(pharmacies)} pharmacies within {radius/1000:.1f} km")
                
            except Exception as e:
                logger.error(f"Error searching pharmacies: {e}")
                self.pharmacy_status_label.config(text=f"Error: {e}")
        
        ttk.Button(button_frame, text="Search", command=search_pharmacies).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Create notebook for settings categories
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # General settings tab
        general_tab = ttk.Frame(notebook, padding=20)
        notebook.add(general_tab, text="General")
        
        ttk.Label(general_tab, text="General Settings", 
                 font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Notification settings
        notify_frame = ttk.LabelFrame(general_tab, text="Notifications")
        notify_frame.pack(fill=tk.X, pady=10)
        
        # System notifications
        system_notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(notify_frame, text="Enable System Notifications", 
                       variable=system_notify_var).pack(anchor="w", padx=20, pady=10)
        
        # Sound alerts
        sound_notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(notify_frame, text="Enable Sound Alerts", 
                       variable=sound_notify_var).pack(anchor="w", padx=20, pady=10)
        
        # Advance reminders
        advance_frame = ttk.Frame(notify_frame)
        advance_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(advance_frame, text="Send reminders").pack(side=tk.LEFT)
        
        advance_minutes_var = tk.StringVar(value="30")
        ttk.Spinbox(advance_frame, from_=5, to=60, width=3, 
                   textvariable=advance_minutes_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(advance_frame, text="minutes before scheduled time").pack(side=tk.LEFT)
        
        # Cloud sync tab
        cloud_tab = ttk.Frame(notebook, padding=20)
        notebook.add(cloud_tab, text="Cloud Sync")
        
        ttk.Label(cloud_tab, text="Cloud Synchronization", 
                 font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Google account
        google_frame = ttk.LabelFrame(cloud_tab, text="Google Account")
        google_frame.pack(fill=tk.X, pady=10)
        
        # Show current status
        if self.controller.cloud_sync.is_authenticated():
            account_info = self.controller.cloud_sync.get_user_info()
            ttk.Label(google_frame, text=f"Connected as: {account_info}").pack(
                anchor="w", padx=20, pady=10)
            
            ttk.Button(google_frame, text="Disconnect Account", 
                      command=self.disconnect_google_account).pack(
                anchor="w", padx=20, pady=10)
        else:
            ttk.Label(google_frame, text="Not connected to Google").pack(
                anchor="w", padx=20, pady=10)
            
            ttk.Button(google_frame, text="Connect Google Account", 
                      command=self.connect_google_account).pack(
                anchor="w", padx=20, pady=10)
        
        # Auto sync settings
        sync_settings_frame = ttk.LabelFrame(cloud_tab, text="Sync Settings")
        sync_settings_frame.pack(fill=tk.X, pady=10)
        
        auto_sync_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(sync_settings_frame, text="Enable Automatic Sync", 
                       variable=auto_sync_var).pack(anchor="w", padx=20, pady=10)
        
        # Sync frequency
        sync_freq_frame = ttk.Frame(sync_settings_frame)
        sync_freq_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(sync_freq_frame, text="Sync every").pack(side=tk.LEFT)
        
        sync_interval_var = tk.StringVar(value="30")
        ttk.Spinbox(sync_freq_frame, from_=5, to=1440, width=4, 
                   textvariable=sync_interval_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(sync_freq_frame, text="minutes").pack(side=tk.LEFT)
        
        # Manual sync buttons
        manual_sync_frame = ttk.Frame(sync_settings_frame)
        manual_sync_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(manual_sync_frame, text="Backup Now", 
                  command=self.backup_to_cloud).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(manual_sync_frame, text="Restore", 
                  command=self.restore_from_cloud).pack(side=tk.LEFT, padx=5)
        
        # Telegram tab
        telegram_tab = ttk.Frame(notebook, padding=20)
        notebook.add(telegram_tab, text="Telegram")
        
        ttk.Label(telegram_tab, text="Telegram Notifications", 
                 font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Telegram settings
        telegram_frame = ttk.LabelFrame(telegram_tab, text="Telegram Bot Settings")
        telegram_frame.pack(fill=tk.X, pady=10)
        
        if self.controller.telegram_bot:
            # Bot token (masked)
            token_frame = ttk.Frame(telegram_frame)
            token_frame.pack(fill=tk.X, padx=20, pady=10)
            
            ttk.Label(token_frame, text="Bot Token:").pack(side=tk.LEFT)
            
            # Show masked token with last 4 chars visible
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            masked_token = "*" * (len(token) - 4) + token[-4:] if token else ""
            ttk.Entry(token_frame, width=30, state="readonly", 
                     textvariable=tk.StringVar(value=masked_token)).pack(side=tk.LEFT, padx=5)
            
            # Chat ID
            chat_id_frame = ttk.Frame(telegram_frame)
            chat_id_frame.pack(fill=tk.X, padx=20, pady=10)
            
            ttk.Label(chat_id_frame, text="Chat ID:").pack(side=tk.LEFT)
            
            # Get current chat ID from settings
            chat_id = self.controller.db.get_user_settings().get("telegram_chat_id", "")
            chat_id_var = tk.StringVar(value=chat_id)
            ttk.Entry(chat_id_frame, width=30, textvariable=chat_id_var).pack(side=tk.LEFT, padx=5)
            
            # Enable Telegram
            telegram_enabled_var = tk.BooleanVar(value=bool(chat_id))
            ttk.Checkbutton(telegram_frame, text="Enable Telegram Notifications", 
                           variable=telegram_enabled_var).pack(anchor="w", padx=20, pady=10)
            
            # Test Telegram button
            def test_telegram():
                try:
                    chat_id = chat_id_var.get().strip()
                    if not chat_id:
                        messagebox.showerror("Error", "Please enter a Chat ID")
                        return
                    
                    # Save chat ID to settings
                    self.controller.db.update_telegram_settings(chat_id)
                    
                    # Send test message
                    self.controller.telegram_bot.send_message(
                        chat_id=chat_id,
                        text="Test message from Medicine Reminder App! 💊"
                    )
                    
                    messagebox.showinfo("Success", "Test message sent successfully")
                    
                except Exception as e:
                    logger.error(f"Error sending Telegram test: {e}")
                    messagebox.showerror("Error", f"Failed to send message: {e}")
            
            ttk.Button(telegram_frame, text="Send Test Message", 
                      command=test_telegram).pack(anchor="w", padx=20, pady=10)
            
        else:
            ttk.Label(telegram_frame, 
                     text="Telegram Bot is not configured. Please set TELEGRAM_BOT_TOKEN in environment variables.").pack(
                padx=20, pady=20)
        
        # Save settings button
        def save_settings():
            try:
                # Save general settings
                settings = {
                    "system_notify": system_notify_var.get(),
                    "sound_notify": sound_notify_var.get(),
                    "advance_minutes": int(advance_minutes_var.get()),
                    "auto_sync": auto_sync_var.get(),
                    "sync_interval": int(sync_interval_var.get())
                }
                
                # Save Telegram settings if enabled
                if self.controller.telegram_bot and telegram_enabled_var.get():
                    settings["telegram_chat_id"] = chat_id_var.get().strip()
                
                # Save to database
                self.controller.db.save_user_settings(settings)
                
                dialog.destroy()
                messagebox.showinfo("Success", "Settings saved successfully")
                
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                messagebox.showerror("Error", f"Failed to save settings: {e}")
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Save", command=save_settings).pack(side=tk.RIGHT, padx=5)
    
    def connect_google_account(self):
        """Start Google authentication process"""
        try:
            # This would launch the browser auth flow
            auth_url = self.controller.cloud_sync.get_auth_url()
            
            if not auth_url:
                messagebox.showerror("Error", "Failed to generate authentication URL")
                return
            
            # Ask user to enter the auth code
            auth_dialog = tk.Toplevel(self.root)
            auth_dialog.title("Google Authentication")
            auth_dialog.geometry("500x300")
            auth_dialog.transient(self.root)
            auth_dialog.grab_set()
            
            ttk.Label(auth_dialog, text="Google Authentication", 
                     font=("TkDefaultFont", 14, "bold")).pack(pady=10)
            
            ttk.Label(auth_dialog, 
                     text="Please open the following URL in your browser:").pack(pady=5)
            
            # URL display (readonly)
            url_var = tk.StringVar(value=auth_url)
            url_entry = ttk.Entry(auth_dialog, textvariable=url_var, width=50)
            url_entry.pack(padx=20, pady=5, fill=tk.X)
            
            # Copy URL button
            def copy_url():
                self.root.clipboard_clear()
                self.root.clipboard_append(auth_url)
                messagebox.showinfo("Copied", "URL copied to clipboard")
            
            ttk.Button(auth_dialog, text="Copy URL", command=copy_url).pack(pady=5)
            
            ttk.Label(auth_dialog, 
                     text="After authentication, enter the code below:").pack(pady=10)
            
            # Code entry
            code_var = tk.StringVar()
            ttk.Entry(auth_dialog, textvariable=code_var, width=30).pack(pady=5)
            
            # Submit button
            def submit_code():
                try:
                    auth_code = code_var.get().strip()
                    if not auth_code:
                        messagebox.showerror("Error", "Please enter the authentication code")
                        return
                    
                    # Exchange code for tokens
                    success = self.controller.cloud_sync.exchange_code(auth_code)
                    
                    if success:
                        auth_dialog.destroy()
                        messagebox.showinfo("Success", "Google account connected successfully")
                        self.open_settings()  # Refresh settings dialog
                    else:
                        messagebox.showerror("Error", "Failed to authenticate with Google")
                        
                except Exception as e:
                    logger.error(f"Error in Google auth: {e}")
                    messagebox.showerror("Error", f"Authentication error: {e}")
            
            button_frame = ttk.Frame(auth_dialog)
            button_frame.pack(fill=tk.X, padx=20, pady=20)
            
            ttk.Button(button_frame, text="Cancel", 
                      command=auth_dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
            ttk.Button(button_frame, text="Submit", 
                      command=submit_code).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            logger.error(f"Error starting Google auth: {e}")
            messagebox.showerror("Error", f"Failed to start authentication: {e}")
    
    def disconnect_google_account(self):
        """Disconnect Google account"""
        try:
            if messagebox.askyesno("Confirm", "Are you sure you want to disconnect your Google account?"):
                self.controller.cloud_sync.revoke_token()
                messagebox.showinfo("Success", "Google account disconnected")
                self.open_settings()  # Refresh settings dialog
        except Exception as e:
            logger.error(f"Error disconnecting account: {e}")
            messagebox.showerror("Error", f"Failed to disconnect account: {e}")
    
    def backup_to_cloud(self):
        """Backup data to cloud"""
        try:
            if not self.controller.cloud_sync.is_authenticated():
                if messagebox.askyesno("Not Connected", 
                                      "You need to connect a Google account first. Connect now?"):
                    self.connect_google_account()
                return
            
            # Perform backup
            success = self.controller.cloud_sync.backup_database()
            
            if success:
                messagebox.showinfo("Success", "Database backed up to cloud successfully")
                self.sync_status_label.config(text=f"Last synced: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
            else:
                messagebox.showerror("Error", "Failed to backup database to cloud")
                
        except Exception as e:
            logger.error(f"Error backing up to cloud: {e}")
            messagebox.showerror("Error", f"Backup failed: {e}")
    
    def restore_from_cloud(self):
        """Restore data from cloud"""
        try:
            if not self.controller.cloud_sync.is_authenticated():
                if messagebox.askyesno("Not Connected", 
                                      "You need to connect a Google account first. Connect now?"):
                    self.connect_google_account()
                return
            
            # Confirm restore
            if not messagebox.askyesno("Confirm Restore", 
                                      "This will replace your current data with the cloud backup. Continue?"):
                return
            
            # Perform restore
            success = self.controller.cloud_sync.restore_database()
            
            if success:
                messagebox.showinfo("Success", "Database restored from cloud successfully")
                
                # Refresh all data
                self.load_medicines_data()
                self.refresh_dashboard()
                self.update_calendar_view()
                
            else:
                messagebox.showerror("Error", "Failed to restore database from cloud")
                
        except Exception as e:
            logger.error(f"Error restoring from cloud: {e}")
            messagebox.showerror("Error", f"Restore failed: {e}")
    
    def show_about(self):
        """Show about dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("About Medicine Reminder")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Medicine Reminder", 
                 font=("TkDefaultFont", 16, "bold")).pack(pady=(0, 5))
        
        ttk.Label(frame, text="Version 1.0").pack(pady=5)
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        ttk.Label(frame, text="A comprehensive medicine management application with\n"
                             "barcode scanning, reminders, and cloud synchronization.").pack(pady=10)
        
        ttk.Label(frame, text="Features:").pack(anchor="w", pady=(10, 5))
        features = [
            "• Barcode scanning for medicines",
            "• Reminder notifications",
            "• Google Calendar & Sheets integration",
            "• Telegram notifications",
            "• Cloud backup and sync",
            "• Nearby pharmacy locator"
        ]
        
        for feature in features:
            ttk.Label(frame, text=feature).pack(anchor="w", padx=20)
        
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(pady=20)
