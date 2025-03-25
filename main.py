import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import json
from datetime import datetime, timedelta
import base64

# Configure app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import required modules
from src.utils.db_manager import DatabaseManager
from src.utils.notifier import MedicineNotifier
from src.utils.telegram_bot import TelegramBot
from src.utils.cloud_sync import GoogleDriveSync
from src.utils.pharmacy_locator import PharmacyLocator
from src.utils.google_calendar import GoogleCalendarIntegration
from src.utils.google_sheets import GoogleSheetsIntegration
from src.utils.xai_assistant import XAIAssistant

# Initialize components
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Initialize database
# Use PostgreSQL if DATABASE_URL is available, otherwise use SQLite
if os.environ.get("DATABASE_URL"):
    db_manager = DatabaseManager(db_url=os.environ.get("DATABASE_URL"))
    logger.info("Using PostgreSQL database")
else:
    db_path = os.path.join(data_dir, "medicine_database.db")
    db_manager = DatabaseManager(db_path=db_path)
    logger.info(f"Database initialized at {db_path}")

# Initialize notifier
notifier = MedicineNotifier(db_manager)

# Initialize Telegram bot
telegram_bot = TelegramBot(db_manager)
if telegram_bot.is_configured():
    telegram_bot.start()
    logger.info("Telegram bot started")
else:
    logger.warning("Telegram bot not configured (TELEGRAM_BOT_TOKEN environment variable not set)")

# Initialize Google Drive sync
if hasattr(db_manager, 'db_path') and db_manager.db_path:
    # SQLite is being used
    drive_sync = GoogleDriveSync(db_manager.db_path)
    logger.info(f"Google Drive sync initialized with SQLite database at {db_manager.db_path}")
else:
    # PostgreSQL is being used, initialize without specific path
    # Create a temporary SQLite database for sync purposes
    temp_db_path = os.path.join(data_dir, "temp_sync_database.db")
    drive_sync = GoogleDriveSync(temp_db_path)
    logger.info("Google Drive sync initialized for PostgreSQL database (using temp file for sync)")

# Initialize Pharmacy Locator
pharmacy_locator = PharmacyLocator()

# Initialize Google Calendar integration
calendar_integration = GoogleCalendarIntegration(db_manager)

# Initialize Google Sheets integration
sheets_integration = GoogleSheetsIntegration(db_manager)

# Initialize XAI Assistant
xai_assistant = XAIAssistant()
if xai_assistant.is_configured():
    logger.info("XAI Assistant initialized")
else:
    logger.warning("XAI Assistant not configured (XAI_API_KEY environment variable not set)")

# Start the notification scheduler
notifier.start_scheduler()
logger.info("Notification scheduler started")

# Routes
@app.route('/')
def index():
    """Home page with today's medicines and streak information."""
    medicines = db_manager.get_medicines_for_date(datetime.now().strftime("%Y-%m-%d"))
    streak_info = db_manager.get_streak()
    return render_template('index.html', 
                          medicines=medicines, 
                          streak_info=streak_info,
                          current_date=datetime.now().strftime("%Y-%m-%d"))

@app.route('/medicines')
def medicines():
    """Medicines management page."""
    all_medicines = db_manager.get_all_medicines()
    return render_template('medicines.html', medicines=all_medicines)

@app.route('/medicine/add', methods=['GET', 'POST'])
def add_medicine():
    """Add a new medicine."""
    if request.method == 'POST':
        name = request.form.get('name')
        barcode = request.form.get('barcode')
        dosage = request.form.get('dosage')
        notes = request.form.get('notes')
        expiry_date = request.form.get('expiry_date')
        doses_remaining = request.form.get('doses_remaining')
        
        if not name:
            flash('Medicine name is required', 'danger')
            return redirect(url_for('add_medicine'))
        
        try:
            if doses_remaining:
                doses_remaining = int(doses_remaining)
            
            medicine_id = db_manager.add_medicine(
                name, barcode, dosage, notes, expiry_date, doses_remaining
            )
            
            # Process schedule times
            times = request.form.getlist('time[]')
            days = request.form.getlist('day[]')
            
            for i, time in enumerate(times):
                if time:
                    day = int(days[i]) if i < len(days) else -1
                    db_manager.add_schedule(medicine_id, time, day)
            
            flash('Medicine added successfully', 'success')
            return redirect(url_for('medicines'))
        except Exception as e:
            flash(f'Error adding medicine: {str(e)}', 'danger')
            return redirect(url_for('add_medicine'))
    
    return render_template('add_medicine.html')

@app.route('/medicine/edit/<int:medicine_id>', methods=['GET', 'POST'])
def edit_medicine(medicine_id):
    """Edit an existing medicine."""
    medicine = db_manager.get_medicine_by_id(medicine_id)
    if not medicine:
        flash('Medicine not found', 'danger')
        return redirect(url_for('medicines'))
    
    schedules = db_manager.get_schedules_for_medicine(medicine_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        barcode = request.form.get('barcode')
        dosage = request.form.get('dosage')
        notes = request.form.get('notes')
        expiry_date = request.form.get('expiry_date')
        doses_remaining = request.form.get('doses_remaining')
        
        if not name:
            flash('Medicine name is required', 'danger')
            return redirect(url_for('edit_medicine', medicine_id=medicine_id))
        
        try:
            if doses_remaining:
                doses_remaining = int(doses_remaining)
            
            db_manager.update_medicine(
                medicine_id, 
                name=name, 
                barcode=barcode, 
                dosage=dosage, 
                notes=notes, 
                expiry_date=expiry_date, 
                doses_remaining=doses_remaining
            )
            
            # Remove all existing schedules and add new ones
            for schedule in schedules:
                db_manager.delete_schedule(schedule['id'])
            
            # Process schedule times
            times = request.form.getlist('time[]')
            days = request.form.getlist('day[]')
            
            for i, time in enumerate(times):
                if time:
                    day = int(days[i]) if i < len(days) else -1
                    db_manager.add_schedule(medicine_id, time, day)
            
            flash('Medicine updated successfully', 'success')
            return redirect(url_for('medicines'))
        except Exception as e:
            flash(f'Error updating medicine: {str(e)}', 'danger')
            return redirect(url_for('edit_medicine', medicine_id=medicine_id))
    
    return render_template('edit_medicine.html', medicine=medicine, schedules=schedules)

@app.route('/medicine/delete/<int:medicine_id>', methods=['POST'])
def delete_medicine(medicine_id):
    """Delete a medicine."""
    medicine = db_manager.get_medicine_by_id(medicine_id)
    if not medicine:
        flash('Medicine not found', 'danger')
        return redirect(url_for('medicines'))
    
    try:
        db_manager.delete_medicine(medicine_id)
        flash('Medicine deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting medicine: {str(e)}', 'danger')
    
    return redirect(url_for('medicines'))

@app.route('/medicine/take/<int:medicine_id>', methods=['POST'])
def take_medicine(medicine_id):
    """Mark a medicine as taken."""
    medicine = db_manager.get_medicine_by_id(medicine_id)
    if not medicine:
        flash('Medicine not found', 'danger')
        return redirect(url_for('index'))
    
    try:
        db_manager.log_medicine_intake(medicine_id, taken=True)
        if medicine['doses_remaining'] is not None and medicine['doses_remaining'] > 0:
            db_manager.update_medicine(medicine_id, doses_remaining=medicine['doses_remaining'] - 1)
        flash(f'Marked {medicine["name"]} as taken', 'success')
    except Exception as e:
        flash(f'Error marking medicine as taken: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/schedule')
def schedule():
    """Schedule page with calendar view."""
    # Default to current date if not specified
    current_date = datetime.now()
    date_str = request.args.get('date', current_date.strftime("%Y-%m-%d"))
    medicines = db_manager.get_medicines_for_date(date_str)
    
    # Generate dates for the week view
    today = datetime.strptime(date_str, "%Y-%m-%d")
    week_dates = []
    for i in range(-3, 4):  # -3 to 3 days from selected date
        date = today + timedelta(days=i)
        week_dates.append({
            'date': date.strftime("%Y-%m-%d"),
            'day': date.strftime("%a"),
            'is_today': date.date() == current_date.date()
        })
    
    # Calculate previous and next week dates for navigation
    prev_week_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    next_week_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    
    return render_template('schedule.html', 
                          medicines=medicines, 
                          selected_date=date_str,
                          week_dates=week_dates,
                          prev_week_date=prev_week_date,
                          next_week_date=next_week_date,
                          now_date=current_date.strftime("%Y-%m-%d"))

@app.route('/scan')
def scan():
    """Barcode scanning page."""
    return render_template('scan.html')

@app.route('/scan/process', methods=['POST'])
def process_scan():
    """Process a scanned barcode."""
    barcode = request.form.get('barcode')
    if not barcode:
        flash('No barcode provided', 'danger')
        return redirect(url_for('scan'))
    
    # Check if medicine with this barcode exists
    medicine = db_manager.get_medicine_by_barcode(barcode)
    if medicine:
        flash(f'Found medicine: {medicine["name"]}', 'success')
        return redirect(url_for('edit_medicine', medicine_id=medicine['id']))
    else:
        # Store barcode in session and redirect to add medicine form
        session['scanned_barcode'] = barcode
        flash('No medicine found with this barcode. Please add a new one.', 'info')
        return redirect(url_for('add_medicine'))

@app.route('/scan/upload', methods=['POST'])
def scan_upload():
    """Process an uploaded image for barcode scanning."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'})
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'success': False, 'error': 'No image selected'})
    
    try:
        # Save the uploaded image temporarily
        temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_scan.jpg')
        image_file.save(temp_path)
        
        # Use the scanner to scan the image
        from src.utils.scanner import BarcodeScanner
        scanner = BarcodeScanner()
        result = scanner.scan_from_image(temp_path)
        
        # Remove the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if result:
            barcode_data = result['data']
            barcode_type = result['type']
            return jsonify({
                'success': True, 
                'barcode': barcode_data,
                'type': barcode_type
            })
        else:
            return jsonify({'success': False, 'error': 'No barcode found in image'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/pharmacy')
def pharmacy():
    """Pharmacy finder page."""
    return render_template('pharmacy.html')

@app.route('/pharmacy/search', methods=['POST'])
def search_pharmacy():
    """Search for pharmacies near a location."""
    location = request.form.get('location')
    radius = request.form.get('radius', 5000)
    
    if not location:
        flash('Location is required', 'danger')
        return redirect(url_for('pharmacy'))
    
    try:
        radius = int(radius)
        pharmacies = pharmacy_locator.find_pharmacies_by_address(location, radius)
        return render_template('pharmacy_results.html', 
                              pharmacies=pharmacies, 
                              location=location, 
                              radius=radius)
    except Exception as e:
        flash(f'Error finding pharmacies: {str(e)}', 'danger')
        return redirect(url_for('pharmacy'))

@app.route('/assistant')
def assistant():
    """AI assistant page."""
    all_medicines = db_manager.get_all_medicines()
    return render_template('assistant.html', medicines=all_medicines)

@app.route('/assistant/analyze', methods=['POST'])
def analyze_medicine():
    """Analyze a medicine using xAI."""
    medicine_id = request.form.get('medicine_id')
    if not medicine_id:
        return jsonify({'success': False, 'error': 'No medicine selected'})
    
    try:
        medicine = db_manager.get_medicine_by_id(int(medicine_id))
        if not medicine:
            return jsonify({'success': False, 'error': 'Medicine not found'})
        
        analysis = xai_assistant.analyze_medicine_info(medicine['name'], medicine['dosage'], medicine['notes'])
        if analysis:
            return jsonify({'success': True, 'analysis': analysis})
        else:
            return jsonify({'success': False, 'error': 'Failed to analyze medicine'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/assistant/food-interactions', methods=['POST'])
def food_interactions():
    """Find food interactions for a medicine."""
    medicine_id = request.form.get('medicine_id')
    if not medicine_id:
        return jsonify({'success': False, 'error': 'No medicine selected'})
    
    try:
        medicine = db_manager.get_medicine_by_id(int(medicine_id))
        if not medicine:
            return jsonify({'success': False, 'error': 'Medicine not found'})
        
        interactions = xai_assistant.get_food_interactions(medicine['name'])
        if interactions:
            return jsonify({'success': True, 'interactions': interactions})
        else:
            return jsonify({'success': False, 'error': 'Failed to find food interactions'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/assistant/alternatives', methods=['POST'])
def alternatives():
    """Find alternative medicines."""
    medicine_id = request.form.get('medicine_id')
    reason = request.form.get('reason', '')
    
    if not medicine_id:
        return jsonify({'success': False, 'error': 'No medicine selected'})
    
    try:
        medicine = db_manager.get_medicine_by_id(int(medicine_id))
        if not medicine:
            return jsonify({'success': False, 'error': 'Medicine not found'})
        
        alternatives = xai_assistant.suggest_alternative_medicines(medicine['name'], reason)
        if alternatives:
            return jsonify({'success': True, 'alternatives': alternatives})
        else:
            return jsonify({'success': False, 'error': 'Failed to find alternative medicines'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/assistant/identify', methods=['POST'])
def identify_medicine():
    """Identify medicine from an image."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'})
    
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'success': False, 'error': 'No image selected'})
    
    try:
        # Save the uploaded image temporarily
        temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_medicine.jpg')
        image_file.save(temp_path)
        
        # Use XAI to identify the medicine
        result = xai_assistant.identify_medicine_from_image(temp_path)
        
        # Remove the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if result:
            return jsonify({'success': True, 'identification': result})
        else:
            return jsonify({'success': False, 'error': 'Failed to identify medicine'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/settings')
def settings():
    """Settings page."""
    email_settings = {
        'sender': db_manager.get_setting('email_sender', ''),
        'recipient': db_manager.get_setting('email_recipient', '')
    }
    
    telegram_settings = {
        'is_configured': telegram_bot.is_configured(),
        'chats': db_manager.get_setting('telegram_chats', [])
    }
    
    google_settings = {
        'drive_sync': db_manager.get_setting('google_drive_sync', False),
        'calendar_sync': db_manager.get_setting('google_calendar_sync', False),
        'sheets_sync': db_manager.get_setting('google_sheets_sync', False),
        'drive_authenticated': drive_sync.is_authenticated(),
        'calendar_authenticated': calendar_integration.is_authenticated(),
        'sheets_authenticated': sheets_integration.is_authenticated()
    }
    
    return render_template('settings.html', 
                          email_settings=email_settings,
                          telegram_settings=telegram_settings,
                          google_settings=google_settings)

@app.route('/settings/email', methods=['POST'])
def settings_email():
    """Save email notification settings."""
    sender = request.form.get('email_sender')
    password = request.form.get('email_password')
    recipient = request.form.get('email_recipient')
    
    if sender and password and recipient:
        try:
            notifier.configure_email(sender, password, recipient)
            db_manager.save_setting('email_sender', sender)
            db_manager.save_setting('email_recipient', recipient)
            flash('Email settings saved successfully', 'success')
        except Exception as e:
            flash(f'Error saving email settings: {str(e)}', 'danger')
    else:
        flash('All email fields are required', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/telegram', methods=['POST'])
def settings_telegram():
    """Save Telegram notification settings."""
    chat_id = request.form.get('telegram_chat_id')
    
    if chat_id:
        try:
            telegram_bot.add_chat(chat_id)
            chats = db_manager.get_setting('telegram_chats', [])
            if chat_id not in chats:
                chats.append(chat_id)
                db_manager.save_setting('telegram_chats', chats)
            flash('Telegram chat added successfully', 'success')
        except Exception as e:
            flash(f'Error adding Telegram chat: {str(e)}', 'danger')
    else:
        flash('Telegram chat ID is required', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/telegram/remove/<chat_id>', methods=['POST'])
def remove_telegram_chat(chat_id):
    """Remove a Telegram chat."""
    try:
        telegram_bot.remove_chat(chat_id)
        chats = db_manager.get_setting('telegram_chats', [])
        if chat_id in chats:
            chats.remove(chat_id)
            db_manager.save_setting('telegram_chats', chats)
        flash('Telegram chat removed successfully', 'success')
    except Exception as e:
        flash(f'Error removing Telegram chat: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/settings/google', methods=['POST'])
def settings_google():
    """Save Google services settings."""
    drive_sync_enabled = 'drive_sync' in request.form
    calendar_sync_enabled = 'calendar_sync' in request.form
    sheets_sync_enabled = 'sheets_sync' in request.form
    
    try:
        # Save settings
        db_manager.save_setting('google_drive_sync', drive_sync_enabled)
        db_manager.save_setting('google_calendar_sync', calendar_sync_enabled)
        db_manager.save_setting('google_sheets_sync', sheets_sync_enabled)
        
        # Start or stop syncs based on settings
        if drive_sync_enabled and drive_sync.is_authenticated():
            drive_sync.start_sync()
        else:
            drive_sync.stop_sync()
            
        if calendar_sync_enabled and calendar_integration.is_authenticated():
            calendar_integration.start_sync()
        else:
            calendar_integration.stop_sync()
            
        if sheets_sync_enabled and sheets_integration.is_authenticated():
            sheets_integration.start_sync()
        else:
            sheets_integration.stop_sync()
            
        flash('Google services settings saved successfully', 'success')
    except Exception as e:
        flash(f'Error saving Google services settings: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/authenticate/drive')
def authenticate_drive():
    """Authenticate with Google Drive."""
    try:
        success = drive_sync.authenticate()
        if success:
            flash('Google Drive authentication successful', 'success')
        else:
            flash('Google Drive authentication failed', 'danger')
    except Exception as e:
        flash(f'Error authenticating with Google Drive: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/authenticate/calendar')
def authenticate_calendar():
    """Authenticate with Google Calendar."""
    try:
        success = calendar_integration.authenticate()
        if success:
            flash('Google Calendar authentication successful', 'success')
        else:
            flash('Google Calendar authentication failed', 'danger')
    except Exception as e:
        flash(f'Error authenticating with Google Calendar: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/authenticate/sheets')
def authenticate_sheets():
    """Authenticate with Google Sheets."""
    try:
        success = sheets_integration.authenticate()
        if success:
            flash('Google Sheets authentication successful', 'success')
        else:
            flash('Google Sheets authentication failed', 'danger')
    except Exception as e:
        flash(f'Error authenticating with Google Sheets: {str(e)}', 'danger')
    
    return redirect(url_for('settings'))

@app.route('/shutdown')
def shutdown():
    """Shutdown the application."""
    # Stop all background threads
    notifier.stop_scheduler()
    telegram_bot.stop()
    drive_sync.stop_sync()
    calendar_integration.stop_sync()
    sheets_integration.stop_sync()
    # Close database connection
    db_manager.close()
    flash('Application shut down successfully', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)