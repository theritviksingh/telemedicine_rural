from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from datetime import timedelta, datetime, time
import mysql.connector
import psycopg2
from psycopg2.extras import RealDictCursor
from functools import wraps
from flask_socketio import SocketIO, join_room, leave_room, emit
import os
from werkzeug.utils import secure_filename
import json
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'devkey')
app.permanent_session_lifetime = timedelta(days=7)
socketio = SocketIO(app)

@app.template_filter('fromjson')
def fromjson_filter(value):
    return json.loads(value)

@app.template_filter('now')
def now_filter(value):
    return datetime.now()

# Upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'ogg', 'mp3', 'wav', 'pdf', 'doc', 'docx', 'txt', 'zip', 'rar'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Get database connection - PostgreSQL for production, MySQL for development"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Production - PostgreSQL on Render
        url = urlparse(database_url)
        return psycopg2.connect(
            host=dpg-d36223ndiees738oknqg-a,
            port=5432,
            database=telemedicine_s8km,  # Remove leading slash
            user=telemedicine_s8km_user,
            password=x6qv1bgCEh8qFkuABCmV03XZsSvIj8OF,
            cursor_factory=RealDictCursor
        )
    else:
        # Development - MySQL local
        return mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST', 'localhost'),
            user=os.environ.get('MYSQL_USER', 'root'),
            password=os.environ.get('MYSQL_PASSWORD', ''),
            database=os.environ.get('MYSQL_DB', 'telemedicine')
        )

def execute_query(query, params=None, fetch=False, fetchone=False):
    """Execute database query with proper handling for both MySQL and PostgreSQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
        elif fetchone:
            result = cursor.fetchone()
        else:
            result = None
        
        conn.commit()
        return result
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_db_placeholder():
    """Get correct placeholder for SQL queries based on database type"""
    return '%s' if not os.environ.get('DATABASE_URL') else '%s'

# Skip database initialization for production (handled by init_db.py)
if not os.environ.get('DATABASE_URL'):
    # Initialize database for development only
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password=''
        )
        cursor = conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS telemedicine")
        cursor.close()
        conn.close()

        # Now connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('doctor', 'patient', 'pharmacy') NOT NULL,
            name VARCHAR(100),
            email VARCHAR(100),
            mobile VARCHAR(15) NOT NULL DEFAULT '',
            date_of_birth DATE,
            gender ENUM('Male','Female','Other'),
            address TEXT,
            pin_code VARCHAR(10),
            health_history TEXT,
            emergency_contact_name VARCHAR(100),
            emergency_contact_number VARCHAR(15),
            preferred_language ENUM('English','Hindi','Punjabi') DEFAULT 'English',
            description TEXT,
            specialist VARCHAR(100)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            room VARCHAR(100) NOT NULL,
            username VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            media_url VARCHAR(255),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            doctor_id INT,
            record_type VARCHAR(100) NOT NULL,
            description TEXT,
            file_path VARCHAR(255) NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (doctor_id) REFERENCES users(id)
        )
        """)

        # Create symptom checker history table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS symptom_checker_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            symptoms TEXT NOT NULL,
            age_group VARCHAR(20) NOT NULL,
            gender VARCHAR(10) NOT NULL,
            conditions_found TEXT NOT NULL,
            highest_probability FLOAT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            api_response TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            doctor_id INT NOT NULL,
            medicines TEXT NOT NULL,
            instructions TEXT,
            diagnosis TEXT,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status ENUM('active', 'completed', 'cancelled') DEFAULT 'active',
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (doctor_id) REFERENCES users(id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            doctor_id INT NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            appointment_type ENUM('video', 'chat', 'in_person') DEFAULT 'video',
            status ENUM('pending', 'scheduled', 'confirmed', 'completed', 'cancelled', 'no_show') DEFAULT 'pending',
            symptoms TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (doctor_id) REFERENCES users(id)
        )
        """)

        # Create notifications table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            type ENUM('appointment_approved', 'appointment_declined', 'appointment_reminder', 'prescription_ready', 'general', 'sos_alert') DEFAULT 'general',
            is_read BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # Create SOS alerts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sos_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patient_id INT NOT NULL,
            latitude DECIMAL(10, 8) NULL,
            longitude DECIMAL(11, 8) NULL,
            location_error TEXT NULL,
            status ENUM('active', 'responded', 'resolved') DEFAULT 'active',
            user_agent TEXT NULL,
            page_url TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            responded_at DATETIME NULL,
            resolved_at DATETIME NULL,
            responding_doctor_id INT NULL,
            notes TEXT NULL,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            FOREIGN KEY (responding_doctor_id) REFERENCES users(id)
        )
        """)

        # Create medicines table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            quantity INT NOT NULL,
            pharmacy_id INT NOT NULL,
            added_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (pharmacy_id) REFERENCES users(id)
        )
        """)

        # Alter table to add new columns if not exists (for existing installations)
        alter_queries = [
            "ALTER TABLE users ADD COLUMN mobile VARCHAR(15) NOT NULL DEFAULT ''",
            "ALTER TABLE users ADD COLUMN date_of_birth DATE",
            "ALTER TABLE users ADD COLUMN gender ENUM('Male','Female','Other')",
            "ALTER TABLE users ADD COLUMN address TEXT",
            "ALTER TABLE users ADD COLUMN pin_code VARCHAR(10)",
            "ALTER TABLE users ADD COLUMN health_history TEXT",
            "ALTER TABLE users ADD COLUMN emergency_contact_name VARCHAR(100)",
            "ALTER TABLE users ADD COLUMN emergency_contact_number VARCHAR(15)",
            "ALTER TABLE users ADD COLUMN preferred_language ENUM('English','Hindi','Punjabi') DEFAULT 'English'",
            "ALTER TABLE users ADD COLUMN description TEXT",
            "ALTER TABLE users ADD COLUMN specialist VARCHAR(100)",
            "ALTER TABLE chat_messages ADD COLUMN media_url VARCHAR(255)",
            "ALTER TABLE appointments MODIFY COLUMN status ENUM('pending', 'scheduled', 'confirmed', 'completed', 'cancelled', 'no_show') DEFAULT 'pending'"
        ]
        for query in alter_queries:
            try:
                cursor.execute(query)
            except mysql.connector.Error as err:
                if err.errno != 1060:  # Duplicate column name
                    print(f"Error altering table: {err}")
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'doctor'")
        doctor_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'pharmacy'")
        pharmacy_count = cursor.fetchone()[0]
        if doctor_count == 0:
            dummy_doctors = [
                ('doctor-1', 'doctor-123', 'doctor', 'Dr. Singh', 'doctor1@example.com', '9876543210', 'Experienced general physician with 10+ years in rural healthcare.', 'General Medicine'),
                ('doctor-2', 'doctor-231', 'doctor', 'Dr. Patel', 'doctor2@example.com', '9876543211', 'Cardiologist specializing in heart diseases and preventive care.', 'Cardiology'),
                ('doctor-3', 'doctor-321', 'doctor', 'Dr. Kumar', 'doctor3@example.com', '9876543212', 'Pediatrician focused on child health and vaccinations.', 'Pediatrics')
            ]
            cursor.executemany("INSERT INTO users (username, password, role, name, email, mobile, description, specialist) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", dummy_doctors)
        if pharmacy_count == 0:
            dummy_pharmacies = [
                ('pharmacy-1', 'pharm-123', 'pharmacy', 'Nabha Medical Store', 'pharm1@example.com', '9876543213', None, None),
                ('pharmacy-2', 'pharm-231', 'pharmacy', 'City Pharmacy', 'pharm2@example.com', '9876543214', None, None),
                ('pharmacy-3', 'pharm-321', 'pharmacy', 'Health Plus', 'pharm3@example.com', '9876543215', None, None)
            ]
            cursor.executemany("INSERT INTO users (username, password, role, name, email, mobile, description, specialist) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", dummy_pharmacies)
        conn.commit()
        # Update existing doctors with descriptions and specialists
        update_doctors = [
            ("Experienced general physician with 10+ years in rural healthcare.", "General Medicine", "doctor-1"),
            ("Cardiologist specializing in heart diseases and preventive care.", "Cardiology", "doctor-2"),
            ("Pediatrician focused on child health and vaccinations.", "Pediatrics", "doctor-3")
        ]
        cursor.executemany("UPDATE users SET description = %s, specialist = %s WHERE username = %s", update_doctors)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Development database initialization error: {e}")
        pass

USERS = {'patient1':{'role':'patient','name':'Ananya','points':120},
         'doctor1':{'role':'doctor','name':'Dr. Singh'}}
PRESCRIPTIONS = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s AND role = %s", (username, password, role))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session['username'] = username
            session['role'] = role
            session['user_id'] = user[0]  # Store user ID from database
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/init_pharmacy')
def init_pharmacy():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if pharmacy users exist
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'pharmacy'")
    count = cursor.fetchone()[0]
    if count == 0:
        dummy_pharmacies = [
            ('pharmacy-1', 'pharm-123', 'pharmacy', 'Nabha Medical Store', 'pharm1@example.com', '9876543213'),
            ('pharmacy-2', 'pharm-231', 'pharmacy', 'City Pharmacy', 'pharm2@example.com', '9876543214'),
            ('pharmacy-3', 'pharm-321', 'pharmacy', 'Health Plus', 'pharm3@example.com', '9876543215')
        ]
        cursor.executemany("INSERT INTO users (username, password, role, name, email, mobile) VALUES (%s, %s, %s, %s, %s, %s)", dummy_pharmacies)
        conn.commit()
        message = "Pharmacy users created successfully."
    else:
        message = f"Pharmacy users already exist ({count} found)."
    cursor.close()
    conn.close()
    return message

@app.route('/list_pharmacy')
def list_pharmacy():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, name FROM users WHERE role = 'pharmacy'")
    pharmacies = cursor.fetchall()
    cursor.close()
    conn.close()
    return '<br>'.join([f"{u[0]}: {u[1]}" for u in pharmacies])
@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    username = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    
    # Fetch medicines from database
    cursor.execute("""
        SELECT m.name, m.quantity, u.name as pharmacy_name 
        FROM medicines m 
        JOIN users u ON m.pharmacy_id = u.id 
        ORDER BY m.added_date DESC
    """)
    medicines_data = cursor.fetchall()
    medicines = [{'name': row[0], 'qty': row[1], 'pharmacy': row[2]} for row in medicines_data]
    
    cursor.close()
    conn.close()
    user = {'name': user_data[0] if user_data else username, 'points': 0, 'username': username}  # Assuming points not in db yet
    if role == 'doctor':
        return render_template('doctor_dashboard.html', user=user, prescriptions=PRESCRIPTIONS)
    elif role == 'pharmacy':
        return render_template('pharmacy_dashboard.html', user=user, medicines=medicines)
    else:
        return render_template('patient_dashboard.html', user=user, medicines=medicines)

@app.route('/pharmacy_network')
@login_required
def pharmacy_network():
    if session.get('role') != 'patient':
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch medicines with pharmacy information
    cursor.execute("""
        SELECT m.name, m.quantity, u.name as pharmacy_name, u.email, u.mobile, m.added_date
        FROM medicines m 
        JOIN users u ON m.pharmacy_id = u.id 
        ORDER BY u.name, m.name
    """)
    medicines_data = cursor.fetchall()
    
    # Group medicines by pharmacy
    pharmacies = {}
    for row in medicines_data:
        pharmacy_name = row[2]
        if pharmacy_name not in pharmacies:
            pharmacies[pharmacy_name] = {
                'name': pharmacy_name,
                'email': row[3],
                'mobile': row[4],
                'medicines': []
            }
        pharmacies[pharmacy_name]['medicines'].append({
            'name': row[0],
            'quantity': row[1],
            'added_date': row[5]
        })
    
    cursor.close()
    conn.close()
    
    username = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    user = {'name': user_data[0] if user_data else username, 'username': username}
    
    return render_template('pharmacy_network.html', user=user, pharmacies=pharmacies)

@app.route('/add_medicine', methods=['POST'])
@login_required
def add_medicine():
    if session.get('role') != 'pharmacy':
        return jsonify({'error': 'Unauthorized'}), 403
    
    medicine_name = request.form.get('name')
    quantity = request.form.get('quantity')
    
    if not medicine_name or not quantity:
        return jsonify({'error': 'Medicine name and quantity are required'}), 400
    
    try:
        quantity = int(quantity)
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
    except ValueError:
        return jsonify({'error': 'Quantity must be a number'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO medicines (name, quantity, pharmacy_id) VALUES (%s, %s, %s)", 
                   (medicine_name, quantity, session.get('user_id')))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': 'Medicine added successfully'})

@app.route('/get_pharmacy_medicines')
@login_required
def get_pharmacy_medicines():
    if session.get('role') != 'pharmacy':
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, quantity, added_date FROM medicines WHERE pharmacy_id = %s ORDER BY added_date DESC", 
                   (session.get('user_id'),))
    medicines = cursor.fetchall()
    cursor.close()
    conn.close()
    
    medicines_list = [{'id': row[0], 'name': row[1], 'quantity': row[2], 'added_date': row[3].isoformat() if row[3] else None} for row in medicines]
    return jsonify(medicines_list)

@app.route('/update_medicine/<int:medicine_id>', methods=['POST'])
@login_required
def update_medicine(medicine_id):
    if session.get('role') != 'pharmacy':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_quantity = data.get('quantity')
    
    if not new_quantity or new_quantity < 1:
        return jsonify({'error': 'Invalid quantity'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if medicine belongs to this pharmacy
    cursor.execute("SELECT pharmacy_id FROM medicines WHERE id = %s", (medicine_id,))
    result = cursor.fetchone()
    if not result or result[0] != session.get('user_id'):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Medicine not found or unauthorized'}), 404
    
    cursor.execute("UPDATE medicines SET quantity = %s WHERE id = %s", (new_quantity, medicine_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': 'Medicine updated successfully'})

@app.route('/delete_medicine/<int:medicine_id>', methods=['POST'])
@login_required
def delete_medicine(medicine_id):
    if session.get('role') != 'pharmacy':
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if medicine belongs to this pharmacy
    cursor.execute("SELECT pharmacy_id FROM medicines WHERE id = %s", (medicine_id,))
    result = cursor.fetchone()
    if not result or result[0] != session.get('user_id'):
        cursor.close()
        conn.close()
        return jsonify({'error': 'Medicine not found or unauthorized'}), 404
    
    cursor.execute("DELETE FROM medicines WHERE id = %s", (medicine_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({'success': 'Medicine deleted successfully'})

# The symptom checker route has been moved to the bottom of this file

@app.route('/book', methods=['POST'])
@login_required
def book():
    patient = session.get('username','patient1')
    PRESCRIPTIONS.append({'patient':patient,'doctor':'doctor1','notes':'Video consult requested','status':'pending'})
    return redirect(url_for('dashboard'))

@app.route('/sos_alert', methods=['POST'])
@login_required
def sos_alert():
    try:
        # Get patient information from session
        patient_username = session.get('username')
        if not patient_username:
            return jsonify({'error': 'User not authenticated'}), 401
            
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Extract location and metadata
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_error = data.get('locationError')
        user_agent = data.get('userAgent')
        page_url = data.get('pageUrl')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get patient ID
        cursor.execute("SELECT id, name FROM users WHERE username = %s", (patient_username,))
        patient_result = cursor.fetchone()
        if not patient_result:
            return jsonify({'error': 'Patient not found'}), 404
            
        patient_id, patient_name = patient_result
        
        # Insert SOS alert
        cursor.execute("""
            INSERT INTO sos_alerts (patient_id, latitude, longitude, location_error, user_agent, page_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (patient_id, latitude, longitude, location_error, user_agent, page_url))
        
        alert_id = cursor.lastrowid
        
        # Create location string for notification
        location_str = ""
        if latitude and longitude:
            location_str = f"📍 GPS: {latitude:.6f}, {longitude:.6f}"
            # Add Google Maps link
            maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
            location_str += f"\n🗺️ View on Maps: {maps_link}"
        elif location_error:
            location_str = f"⚠️ Location: {location_error}"
        else:
            location_str = "❌ Location: Not available"
        
        # Create urgent notification for all doctors
        cursor.execute("SELECT id FROM users WHERE role = 'doctor'")
        doctors = cursor.fetchall()
        
        notification_title = f"🚨 EMERGENCY SOS ALERT - {patient_name}"
        notification_message = f"""
URGENT: Patient {patient_name} has triggered an emergency SOS alert.

{location_str}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Alert ID: #{alert_id}

Please respond immediately if available to assist.
        """.strip()
        
        # Insert notifications for all doctors
        for doctor in doctors:
            doctor_id = doctor[0]
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, %s, %s, 'sos_alert')
            """, (doctor_id, notification_title, notification_message))
        
        conn.commit()
        
        # Emit real-time notification via WebSocket to doctors
        socketio.emit('sos_alert', {
            'alertId': alert_id,
            'patientName': patient_name,
            'patientId': patient_id,
            'latitude': latitude,
            'longitude': longitude,
            'locationError': location_error,
            'timestamp': datetime.now().isoformat(),
            'message': notification_message
        }, room='doctors')
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'SOS alert sent successfully to all doctors',
            'alertId': alert_id,
            'doctorsNotified': len(doctors),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"SOS Alert Error: {str(e)}")
        return jsonify({'error': 'Failed to send SOS alert', 'details': str(e)}), 500

@app.route('/sos_respond/<int:alert_id>', methods=['POST'])
@login_required
def sos_respond(alert_id):
    try:
        doctor_username = session.get('username')
        data = request.get_json() or {}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get doctor ID
        cursor.execute("SELECT id, name FROM users WHERE username = %s AND role = 'doctor'", (doctor_username,))
        doctor_result = cursor.fetchone()
        if not doctor_result:
            return jsonify({'error': 'Doctor not found'}), 404
            
        doctor_id, doctor_name = doctor_result
        
        # Update SOS alert
        cursor.execute("""
            UPDATE sos_alerts 
            SET status = 'responded', responding_doctor_id = %s, responded_at = NOW(), notes = %s
            WHERE id = %s AND status = 'active'
        """, (doctor_id, data.get('notes', f'Responded by Dr. {doctor_name}'), alert_id))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Alert not found or already responded'}), 404
        
        # Get patient info for notification
        cursor.execute("""
            SELECT u.id, u.name, sa.patient_id 
            FROM sos_alerts sa 
            JOIN users u ON sa.patient_id = u.id 
            WHERE sa.id = %s
        """, (alert_id,))
        patient_result = cursor.fetchone()
        
        if patient_result:
            patient_id, patient_name, _ = patient_result
            
            # Notify patient that help is coming
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type)
                VALUES (%s, %s, %s, 'sos_alert')
            """, (patient_id, 
                  f"✅ Help is Coming!",
                  f"Dr. {doctor_name} has responded to your SOS alert and is coordinating assistance. Please stay calm and wait for help to arrive."))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'SOS alert responded by Dr. {doctor_name}',
            'doctorName': doctor_name
        })
        
    except Exception as e:
        print(f"SOS Response Error: {str(e)}")
        return jsonify({'error': 'Failed to respond to SOS alert'}), 500

@app.route('/api/active_sos_alerts')
@login_required
def get_active_sos_alerts():
    try:
        if session.get('role') != 'doctor':
            return jsonify({'error': 'Unauthorized'}), 403
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sa.id, sa.latitude, sa.longitude, sa.location_error, sa.created_at,
                   u.id as patient_id, u.name as patient_name
            FROM sos_alerts sa
            JOIN users u ON sa.patient_id = u.id
            WHERE sa.status = 'active'
            ORDER BY sa.created_at DESC
        """)
        
        alerts = cursor.fetchall()
        alert_list = []
        
        for alert in alerts:
            alert_list.append({
                'id': alert[0],
                'latitude': float(alert[1]) if alert[1] else None,
                'longitude': float(alert[2]) if alert[2] else None,
                'locationError': alert[3],
                'timestamp': alert[4].isoformat() if alert[4] else None,
                'patientId': alert[5],
                'patientName': alert[6]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'alerts': alert_list
        })
        
    except Exception as e:
        print(f"Error getting active SOS alerts: {str(e)}")
        return jsonify({'error': 'Failed to get SOS alerts'}), 500

@app.route('/prescribe', methods=['POST'])
@login_required
def prescribe():
    doctor = session.get('username','doctor1')
    patient = request.form.get('patient')
    notes = request.form.get('notes')
    PRESCRIPTIONS.append({'patient':patient,'doctor':doctor,'notes':notes,'status':'done'})
    return redirect(url_for('dashboard'))

@app.route('/medicine_check')
@login_required
def medicine_check():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.name, m.quantity, u.name as pharmacy_name 
        FROM medicines m 
        JOIN users u ON m.pharmacy_id = u.id 
        ORDER BY m.added_date DESC
    """)
    medicines_data = cursor.fetchall()
    medicines = [{'name': row[0], 'qty': row[1], 'pharmacy': row[2]} for row in medicines_data]
    cursor.close()
    conn.close()
    return jsonify(medicines)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        name = request.form.get('name')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        date_of_birth = request.form.get('date_of_birth') or None
        gender = request.form.get('gender') or None
        address = request.form.get('address') or None
        pin_code = request.form.get('pin_code') or None
        health_history = request.form.get('health_history') or None
        emergency_contact_name = request.form.get('emergency_contact_name') or None
        emergency_contact_number = request.form.get('emergency_contact_number') or None
        preferred_language = request.form.get('preferred_language') or 'English'
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password, role, name, email, mobile, date_of_birth, gender, address, pin_code, health_history, emergency_contact_name, emergency_contact_number, preferred_language) 
                VALUES (%s, %s, 'patient', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (username, password, name, email, mobile, date_of_birth, gender, address, pin_code, health_history, emergency_contact_name, emergency_contact_number, preferred_language))
            conn.commit()
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            return render_template('register.html', error='The username you chose already exists. Please choose another username.')
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/profile')
@login_required
def profile():
    username = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('profile.html', user=user)

@app.route('/video_consultation')
@login_required
def video_consultation():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, name, email, description, specialist FROM users WHERE role = 'doctor'")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('video_consultation.html', doctors=doctors)

@app.route('/chat/<doctor_username>')
@login_required
def chat(doctor_username):
    if session.get('role') != 'patient':
        return redirect(url_for('dashboard'))
    # Check if doctor exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE username = %s AND role = 'doctor'", (doctor_username,))
    doctor = cursor.fetchone()
    cursor.close()
    conn.close()
    if not doctor:
        return "Doctor not found", 404
    room = f"{session['username']}_{doctor_username}"
    return render_template('chat.html', doctor_username=doctor_username, doctor_name=doctor[0], room=room)

@app.route('/doctor_chat')
@login_required
def doctor_chat():
    if session.get('role') != 'doctor':
        return redirect(url_for('dashboard'))
    
    # Create user object for template
    user = {
        'username': session.get('username'),
        'role': session.get('role')
    }
    
    # Get active chats (rooms with messages for this doctor)
    doctor_username = session['username']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT cm.room, 
               SUBSTRING_INDEX(cm.room, '_', 1) as patient_username,
               u.id as patient_id,
               (SELECT message FROM chat_messages WHERE room = cm.room ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM chat_messages WHERE room = cm.room ORDER BY timestamp DESC LIMIT 1) as last_timestamp
        FROM chat_messages cm 
        JOIN users u ON u.username = SUBSTRING_INDEX(cm.room, '_', 1) AND u.role = 'patient'
        WHERE cm.room LIKE CONCAT('%_', %s)
    """, (doctor_username,))
    active_chats = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('doctor_chat.html', active_chats=active_chats, user=user)

@app.route('/get_messages/<room>')
def get_messages(room):
    # Temporarily allow access for testing - in production this should be @login_required
    # For now, extract username from room name
    if '_' in room:
        username = room.split('_')[0] if room.endswith('_doctor-1') else room.split('_')[1]
    else:
        username = 'test'

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, message, media_url, timestamp FROM chat_messages WHERE room = %s ORDER BY timestamp", (room,))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()

    # Convert timestamps to strings for JSON serialization
    for msg in messages:
        if msg['timestamp']:
            msg['timestamp'] = msg['timestamp'].isoformat()

    return jsonify(messages)

@app.route('/upload_media', methods=['POST'])
@login_required
def upload_media():
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    room = request.form.get('room')
    username = request.form.get('username')

    if not files or not room or not username:
        return jsonify({'success': False, 'error': 'Missing required parameters'}), 400

    # Verify user is part of the room
    if not (room.startswith(username + '_') or room.endswith('_' + username)):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    uploaded_urls = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            file_url = f'/static/uploads/{filename}'
            uploaded_urls.append(file_url)

    return jsonify({'success': True, 'media_urls': uploaded_urls})

@app.route('/doctor_chat/<room>')
@login_required
def doctor_chat_room(room):
    if session.get('role') != 'doctor':
        return redirect(url_for('dashboard'))
    
    # Create user object for template
    user = {
        'username': session.get('username'),
        'role': session.get('role')
    }
    
    doctor_username = session['username']
    if not room.endswith(f'_{doctor_username}'):
        return "Unauthorized", 403
    patient_username = room.split('_')[0]
    # Get patient name
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE username = %s AND role = 'patient'", (patient_username,))
    patient = cursor.fetchone()
    cursor.close()
    conn.close()
    if not patient:
        return "Patient not found", 404
    return render_template('doctor_chat_room.html', patient_username=patient_username, patient_name=patient[0], room=room, user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Health Records Routes
@app.route('/patient/records')
@login_required
def patient_records():
    if session.get('role') != 'patient':
        return "Unauthorized", 403
    
    # Ensure user_id is in session (for backward compatibility)
    if 'user_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            session['user_id'] = user_data[0]
        else:
            return "User not found", 404
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hr.*, u.name as doctor_name 
        FROM health_records hr 
        LEFT JOIN users u ON hr.doctor_id = u.id 
        WHERE hr.patient_id = %s 
        ORDER BY hr.date DESC
    """, (session['user_id'],))
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('patient_records.html', records=records)

@app.route('/patient/prescriptions')
@login_required
def patient_prescriptions():
    if session.get('role') != 'patient':
        return "Unauthorized", 403
    
    # Ensure user_id is in session (for backward compatibility)
    if 'user_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            session['user_id'] = user_data[0]
        else:
            return "User not found", 404
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, u.name as doctor_name, u.specialist
        FROM prescriptions p 
        JOIN users u ON p.doctor_id = u.id 
        WHERE p.patient_id = %s 
        ORDER BY p.date DESC
    """, (session['user_id'],))
    prescriptions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('patient_prescriptions.html', prescriptions=prescriptions)

@app.route('/doctor/records/<patient_id>')
@login_required
def doctor_records(patient_id):
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    try:
        patient_id = int(patient_id)
    except ValueError:
        return "Invalid patient ID", 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get patient info
    cursor.execute("SELECT name, username FROM users WHERE id = %s AND role = 'patient'", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        cursor.close()
        conn.close()
        return "Patient not found", 404
    
    # Get health records
    cursor.execute("""
        SELECT hr.*, u.name as doctor_name 
        FROM health_records hr 
        LEFT JOIN users u ON hr.doctor_id = u.id 
        WHERE hr.patient_id = %s 
        ORDER BY hr.date DESC
    """, (patient_id,))
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('doctor_records.html', records=records, patient=patient)

@app.route('/doctor/write_prescription/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def write_prescription(patient_id):
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get patient info
    cursor.execute("SELECT name, username FROM users WHERE id = %s AND role = 'patient'", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        cursor.close()
        conn.close()
        return "Patient not found", 404
    
    # Get doctor info
    cursor.execute("SELECT id, name FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
    doctor = cursor.fetchone()
    if not doctor:
        cursor.close()
        conn.close()
        return "Doctor not found", 404
    
    if request.method == 'POST':
        medicines = request.form.get('medicines')
        instructions = request.form.get('instructions')
        diagnosis = request.form.get('diagnosis')
        
        if not medicines:
            cursor.close()
            conn.close()
            return render_template('write_prescription.html', patient=patient, error="Medicines field is required")
        
        # Insert prescription
        cursor.execute("""
            INSERT INTO prescriptions (patient_id, doctor_id, medicines, instructions, diagnosis)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, doctor[0], medicines, instructions, diagnosis))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return redirect(url_for('doctor_chat'))
    
    cursor.close()
    conn.close()
    return render_template('write_prescription.html', patient=patient)

# Appointment Routes
@app.route('/book_appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if session.get('role') != 'patient':
        return "Unauthorized", 403

    # Ensure user_id is in session
    if 'user_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            session['user_id'] = user_data[0]
        else:
            return "User not found", 404

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        appointment_type = request.form.get('appointment_type', 'video')
        symptoms = request.form.get('symptoms')

        if not all([doctor_id, appointment_date, appointment_time]):
            # Create user object for error template
            username = session.get('username')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name, email FROM users WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            cursor.execute("SELECT id, name, specialist, description FROM users WHERE role = 'doctor' ORDER BY name")
            doctors = cursor.fetchall()
            cursor.close()
            conn.close()
            user = {'name': user_data[0] if user_data else username, 'points': 0, 'username': username}
            min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            return render_template('book_appointment.html', error="All fields are required", doctors=doctors, user=user, min_date=min_date)

        # Check if slot is available
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM appointments
            WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s
            AND status IN ('pending', 'scheduled', 'confirmed')
        """, (doctor_id, appointment_date, appointment_time))
        existing_appointments = cursor.fetchone()[0]

        if existing_appointments > 0:
            cursor.close()
            conn.close()
            # Create user object for error template
            username = session.get('username')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name, email FROM users WHERE username = %s", (username,))
            user_data = cursor.fetchone()
            cursor.execute("SELECT id, name, specialist, description FROM users WHERE role = 'doctor' ORDER BY name")
            doctors = cursor.fetchall()
            cursor.close()
            conn.close()
            user = {'name': user_data[0] if user_data else username, 'points': 0, 'username': username}
            min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            return render_template('book_appointment.html', error="This time slot is already booked", doctors=doctors, user=user, min_date=min_date)

        # Book appointment
        cursor.execute("""
            INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_type, symptoms, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (session['user_id'], doctor_id, appointment_date, appointment_time, appointment_type, symptoms))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('patient_appointments'))

    # Get available doctors
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, specialist, description FROM users WHERE role = 'doctor' ORDER BY name")
    doctors = cursor.fetchall()
    cursor.close()
    conn.close()

    # Create user object for template
    username = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    user = {'name': user_data[0] if user_data else username, 'points': 0, 'username': username}

    # Calculate minimum date (tomorrow)
    min_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    return render_template('book_appointment.html', doctors=doctors, user=user, min_date=min_date)

@app.route('/patient/appointments')
@login_required
def patient_appointments():
    if session.get('role') != 'patient':
        return "Unauthorized", 403

    # Ensure user_id is in session
    if 'user_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            session['user_id'] = user_data[0]
        else:
            return "User not found", 404

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.patient_id, a.doctor_id, a.appointment_date, a.appointment_time,
               a.appointment_type, a.status, a.symptoms, a.notes, a.created_at, a.updated_at,
               u.name as doctor_name, u.specialist
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    """, (session['user_id'],))
    appointments = cursor.fetchall()
    
    # Convert appointments from tuples to lists so they can be modified
    appointments = [list(appointment) for appointment in appointments]

    # Convert date and time fields to datetime objects for template strftime
    for appointment in appointments:
        try:
            appointment_date = appointment[3]  # appointment_date
            appointment_time = appointment[4]  # appointment_time
            
            # Handle different possible types returned by MySQL
            if isinstance(appointment_date, str):
                # If it's a string, parse it
                date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            elif hasattr(appointment_date, 'days'):  # It's a timedelta
                # Convert timedelta to date (assuming it's days since epoch or similar)
                date_obj = (datetime(1970, 1, 1) + appointment_date).date()
            elif hasattr(appointment_date, 'strftime') and hasattr(appointment_date, 'year'):
                # It's a proper date/datetime object
                date_obj = appointment_date.date() if hasattr(appointment_date, 'date') else appointment_date
            else:
                # Try to convert from whatever type it is
                date_obj = appointment_date
            
            if isinstance(appointment_time, str):
                # If it's a string, parse it
                time_obj = datetime.strptime(appointment_time, '%H:%M:%S').time()
            elif hasattr(appointment_time, 'days'):  # It's a timedelta
                # Convert timedelta to time (assuming it's seconds)
                total_seconds = int(appointment_time.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                time_obj = datetime.time(hours, minutes, seconds)
            elif hasattr(appointment_time, 'strftime') and hasattr(appointment_time, 'hour'):
                # It's a proper time/datetime object
                time_obj = appointment_time.time() if hasattr(appointment_time, 'time') else appointment_time
            else:
                # Try to convert from whatever type it is
                time_obj = appointment_time
            
            # Create a datetime object for formatting
            if hasattr(date_obj, 'year') and hasattr(date_obj, 'month') and hasattr(date_obj, 'day'):
                if hasattr(time_obj, 'hour') and hasattr(time_obj, 'minute') and hasattr(time_obj, 'second'):
                    # Both are proper date/time objects
                    datetime_obj = datetime.combine(date_obj, time_obj)
                else:
                    # date_obj is a date, time_obj is not a time - use date as datetime
                    datetime_obj = datetime.combine(date_obj, datetime.min.time())
            else:
                # Fallback: create a datetime from current time
                datetime_obj = datetime.now()
            
            appointment[3] = datetime_obj  # Replace date with datetime
            appointment[4] = datetime_obj  # Replace time with datetime
        except (ValueError, TypeError, AttributeError) as e:
            # If conversion fails, create fallback datetime objects
            fallback_datetime = datetime.now()
            appointment[3] = fallback_datetime
            appointment[4] = fallback_datetime

    # Create user object for template
    username = session.get('username')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email FROM users WHERE username = %s", (username,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    user = {'name': user_data[0] if user_data else username, 'points': 0, 'username': username}

    return render_template('patient_appointments.html', appointments=appointments, user=user)

@app.route('/doctor/appointments')
@login_required
def doctor_appointments():
    if session.get('role') != 'doctor':
        return "Unauthorized", 403

    # Get doctor_id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First get the doctor information
    cursor.execute("""
        SELECT id, name, specialist 
        FROM users 
        WHERE username = %s AND role = 'doctor'
    """, (session['username'],))
    doctor_data = cursor.fetchone()
    
    if not doctor_data:
        cursor.close()
        conn.close()
        return "Doctor not found", 404

    doctor_id = doctor_data[0]
    
    # Get appointments with patient information
    cursor.execute("""
        SELECT 
            a.id, 
            a.patient_id, 
            a.doctor_id, 
            a.appointment_date, 
            a.appointment_time,
            a.appointment_type, 
            a.status, 
            a.symptoms, 
            a.notes, 
            a.created_at, 
            a.updated_at,
            p.name as patient_name, 
            p.username as patient_username,
            p.mobile as patient_mobile,
            p.email as patient_email
        FROM appointments a
        JOIN users p ON a.patient_id = p.id
        WHERE a.doctor_id = %s
        ORDER BY a.id DESC
    """, (doctor_id,))
    
    appointments = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert appointments from tuples to list of dicts and format dates/times as strings
    formatted_appointments = []
    for ap in appointments:
        # Map columns from the SELECT to named fields for clarity
        (a_id, patient_id, doctor_id, appointment_date, appointment_time,
         appointment_type, status, symptoms, notes, created_at, updated_at,
         patient_name, patient_username, patient_mobile, patient_email) = ap

        # Prepare formatted strings with safe fallbacks
        formatted_date = None
        formatted_time = None
        formatted_created = None

        # Format appointment_date (expected 'YYYY-MM-DD' or date/datetime)
        try:
            if appointment_date:
                if isinstance(appointment_date, str):
                    formatted_date = datetime.strptime(appointment_date, '%Y-%m-%d').strftime('%B %d, %Y')
                else:
                    # handle date or datetime
                    formatted_date = appointment_date.strftime('%B %d, %Y')
        except Exception:
            formatted_date = str(appointment_date)

        # Format appointment_time (expected 'HH:MM:SS' or time/datetime)
        try:
            if appointment_time:
                if isinstance(appointment_time, str):
                    # some DBs may return 'HH:MM:SS' or 'HH:MM'
                    try:
                        formatted_time = datetime.strptime(appointment_time, '%H:%M:%S').strftime('%I:%M %p')
                    except ValueError:
                        formatted_time = datetime.strptime(appointment_time, '%H:%M').strftime('%I:%M %p')
                else:
                    # time or datetime
                    formatted_time = appointment_time.strftime('%I:%M %p')
        except Exception:
            formatted_time = str(appointment_time)

        # Format created_at timestamp
        try:
            if created_at:
                if isinstance(created_at, str):
                    created_dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                else:
                    created_dt = created_at
                formatted_created = created_dt.strftime('%B %d, %Y at %I:%M %p')
        except Exception:
            formatted_created = str(created_at)

        formatted_appointments.append({
            'id': a_id,
            'patient_id': patient_id,
            'doctor_id': doctor_id,
            'appointment_date': formatted_date,
            'appointment_time': formatted_time,
            'appointment_type': appointment_type,
            'status': status,
            'symptoms': symptoms,
            'notes': notes,
            'created_at': formatted_created,
            'updated_at': str(updated_at) if updated_at else None,
            'patient_name': patient_name,
            'patient_username': patient_username,
            'patient_mobile': patient_mobile,
            'patient_email': patient_email
        })
    # Use the pre-formatted appointments (list of dicts)
    appointments = formatted_appointments

    # Create the user object for the template and render
    user = {
        'username': session['username'],
        'name': doctor_data[1],
        'specialist': doctor_data[2]
    }

    return render_template('doctor_appointments.html', appointments=appointments, user=user)

# Doctor management routes
@app.route('/doctor/patients')
@login_required
def doctor_patients():
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all patients that have appointments with this doctor
    cursor.execute("""
        SELECT DISTINCT u.id, u.name, u.username, u.email, u.mobile 
        FROM users u
        JOIN appointments a ON u.id = a.patient_id
        WHERE a.doctor_id = (
            SELECT id FROM users WHERE username = %s
        )
        ORDER BY u.name
    """, (session['username'],))
    
    patients = []
    for row in cursor.fetchall():
        patients.append({
            'id': row[0],
            'name': row[1],
            'username': row[2],
            'email': row[3],
            'mobile': row[4]
        })
    
    cursor.close()
    conn.close()
    
    user = {'name': session.get('username'), 'username': session.get('username')}
    return render_template('doctor_dashboard.html', user=user, patients=patients)

@app.route('/doctor/prescriptions')
@login_required
def doctor_prescriptions():
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    # For now, return the doctor dashboard with prescriptions data
    user = {'name': session.get('username'), 'username': session.get('username')}
    return render_template('doctor_dashboard.html', user=user, prescriptions=PRESCRIPTIONS)

@app.route('/settings')
@login_required
def settings():
    user = {'name': session.get('username'), 'username': session.get('username')}
    return render_template('profile.html', user=user)

@app.route('/doctor/dashboard')
@login_required
def doctor_dashboard_alt():
    # Redirect to main dashboard
    return redirect(url_for('dashboard'))

@app.route('/doctor/all_records')
@login_required
def doctor_all_records():
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    # Show all patient records for this doctor
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all patients that have appointments with this doctor
    cursor.execute("""
        SELECT DISTINCT u.id, u.name, u.username 
        FROM users u
        JOIN appointments a ON u.id = a.patient_id
        WHERE a.doctor_id = (
            SELECT id FROM users WHERE username = %s
        )
        ORDER BY u.name
    """, (session['username'],))
    
    patients = []
    for row in cursor.fetchall():
        patients.append({
            'id': row[0],
            'name': row[1],
            'username': row[2]
        })
    
    cursor.close()
    conn.close()
    
    user = {'name': session.get('username'), 'username': session.get('username')}
    return render_template('doctor_dashboard.html', user=user, patients=patients)

@app.route('/doctor/chat')
@login_required
def doctor_chat_alt():
    if session.get('role') != 'doctor':
        return "Unauthorized", 403
    
    # Redirect to doctor chat
    return redirect(url_for('doctor_chat'))


@app.route('/debug/doctor_appointments_json')
@login_required
def debug_doctor_appointments_json():
    # Debug endpoint to return the formatted appointments for the logged-in doctor
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Doctor not found'}), 404
    doctor_id = row[0]

    cursor.execute("""
        SELECT 
            a.id, a.patient_id, a.doctor_id, a.appointment_date, a.appointment_time,
            a.appointment_type, a.status, a.symptoms, a.notes, a.created_at, a.updated_at,
            p.name as patient_name, p.username as patient_username, p.mobile as patient_mobile, p.email as patient_email
        FROM appointments a
        JOIN users p ON a.patient_id = p.id
        WHERE a.doctor_id = %s
    """, (doctor_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Reuse same formatting logic as main view
    result = []
    for ap in rows:
        (a_id, patient_id, doctor_id, appointment_date, appointment_time,
         appointment_type, status, symptoms, notes, created_at, updated_at,
         patient_name, patient_username, patient_mobile, patient_email) = ap

        try:
            if appointment_date and isinstance(appointment_date, str):
                appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').strftime('%B %d, %Y')
            elif appointment_date:
                appointment_date = appointment_date.strftime('%B %d, %Y')
        except Exception:
            appointment_date = str(appointment_date)

        try:
            if appointment_time and isinstance(appointment_time, str):
                try:
                    appointment_time = datetime.strptime(appointment_time, '%H:%M:%S').strftime('%I:%M %p')
                except ValueError:
                    appointment_time = datetime.strptime(appointment_time, '%H:%M').strftime('%I:%M %p')
            elif appointment_time:
                appointment_time = appointment_time.strftime('%I:%M %p')
        except Exception:
            appointment_time = str(appointment_time)

        try:
            if created_at and isinstance(created_at, str):
                created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y at %I:%M %p')
            elif created_at:
                created_at = created_at.strftime('%B %d, %Y at %I:%M %p')
        except Exception:
            created_at = str(created_at)

        result.append({
            'id': a_id,
            'patient_id': patient_id,
            'doctor_id': doctor_id,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'appointment_type': appointment_type,
            'status': status,
            'symptoms': symptoms,
            'notes': notes,
            'created_at': created_at,
            'updated_at': str(updated_at) if updated_at else None,
            'patient_name': patient_name,
            'patient_username': patient_username,
            'patient_mobile': patient_mobile,
            'patient_email': patient_email
        })

    return jsonify(result)

@app.route('/cancel_appointment/<appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        return "Invalid appointment ID", 400
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if user owns this appointment
    if session.get('role') == 'patient':
        cursor.execute("SELECT patient_id FROM appointments WHERE id = %s", (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment or appointment[0] != session.get('user_id'):
            cursor.close()
            conn.close()
            return "Unauthorized", 403
    elif session.get('role') == 'doctor':
        cursor.execute("SELECT doctor_id FROM appointments WHERE id = %s", (appointment_id,))
        appointment = cursor.fetchone()
        cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
        doctor_data = cursor.fetchone()
        if not appointment or not doctor_data or appointment[0] != doctor_data[0]:
            cursor.close()
            conn.close()
            return "Unauthorized", 403
    else:
        cursor.close()
        conn.close()
        return "Unauthorized", 403

    # Update appointment status
    cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = %s", (appointment_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/confirm_appointment/<appointment_id>', methods=['POST'])
@login_required
def confirm_appointment(appointment_id):
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        return "Invalid appointment ID", 400
    if session.get('role') != 'doctor':
        return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if doctor owns this appointment
    cursor.execute("SELECT doctor_id FROM appointments WHERE id = %s", (appointment_id,))
    appointment = cursor.fetchone()
    cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
    doctor_data = cursor.fetchone()
    if not appointment or not doctor_data or appointment[0] != doctor_data[0]:
        cursor.close()
        conn.close()
        return "Unauthorized", 403

    # Update appointment status
    cursor.execute("UPDATE appointments SET status = 'confirmed' WHERE id = %s", (appointment_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(request.referrer or url_for('doctor_appointments'))

@app.route('/approve_appointment/<appointment_id>', methods=['POST'])
@login_required
def approve_appointment(appointment_id):
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        return "Invalid appointment ID", 400
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get doctor id and verify ownership
        cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
        doctor_data = cursor.fetchone()
        if not doctor_data:
            raise ValueError("Doctor not found")
        
        doctor_id = doctor_data[0]

        # Get appointment details and verify ownership
        cursor.execute("""
            SELECT a.doctor_id, a.patient_id, DATE_FORMAT(a.appointment_date, '%Y-%m-%d') as appointment_date, 
                   TIME_FORMAT(a.appointment_time, '%h:%i %p') as appointment_time, a.status,
                   p.name as patient_name, p.email as patient_email, p.mobile as patient_mobile
            FROM appointments a
            JOIN users p ON a.patient_id = p.id
            WHERE a.id = %s
        """, (appointment_id,))
        
        appointment = cursor.fetchone()
        if not appointment:
            raise ValueError("Appointment not found")
            
        if appointment[0] != doctor_id:
            raise ValueError("Unauthorized - not your appointment")
            
        if appointment[4] != 'pending':
            raise ValueError(f"Cannot approve appointment with status: {appointment[4]}")

        # Update appointment status
        cursor.execute("UPDATE appointments SET status = 'confirmed' WHERE id = %s", (appointment_id,))

        # Create notification for patient
        appointment_date = appointment[2]  # Already formatted by MySQL
        appointment_time = appointment[3]  # Already formatted by MySQL
        patient_name = appointment[5]
        patient_email = appointment[6]
        patient_mobile = appointment[7]

        notification_title = "Appointment Confirmed"
        notification_message = f"Dear {patient_name}, your appointment on {appointment_date} at {appointment_time} has been approved."
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type)
            VALUES (%s, %s, %s, 'appointment_approved')
        """, (appointment[1], notification_title, notification_message))

        conn.commit()
        cursor.close()
        conn.close()

        # Emit real-time notification via WebSocket to patient
        socketio.emit('appointment_notification', {
            'type': 'appointment_approved',
            'title': notification_title,
            'message': notification_message,
            'appointment_id': appointment_id,
            'patient_id': appointment[1],
            'timestamp': datetime.now().isoformat()
        }, room=f'patient_{appointment[1]}')

        return jsonify({
            'success': True,
            'message': f'Appointment approved successfully',
            'appointment_id': appointment_id
        })

    except ValueError as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 400
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/decline_appointment/<appointment_id>', methods=['POST'])
@login_required
def decline_appointment(appointment_id):
    try:
        appointment_id = int(appointment_id)
    except ValueError:
        return "Invalid appointment ID", 400
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get doctor id and verify ownership
        cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
        doctor_data = cursor.fetchone()
        if not doctor_data:
            raise ValueError("Doctor not found")
        
        doctor_id = doctor_data[0]

        # Get appointment details and verify ownership
        cursor.execute("""
            SELECT a.doctor_id, a.patient_id, DATE_FORMAT(a.appointment_date, '%Y-%m-%d') as appointment_date, 
                   TIME_FORMAT(a.appointment_time, '%h:%i %p') as appointment_time, a.status,
                   p.name as patient_name, p.email as patient_email, p.mobile as patient_mobile
            FROM appointments a
            JOIN users p ON a.patient_id = p.id
            WHERE a.id = %s
        """, (appointment_id,))
        
        appointment = cursor.fetchone()
        if not appointment:
            raise ValueError("Appointment not found")
            
        if appointment[0] != doctor_id:
            raise ValueError("Unauthorized - not your appointment")
            
        if appointment[4] != 'pending':
            raise ValueError(f"Cannot decline appointment with status: {appointment[4]}")

        # Update appointment status
        cursor.execute("UPDATE appointments SET status = 'cancelled' WHERE id = %s", (appointment_id,))

        # Create notification for patient
        appointment_date = appointment[2]  # Already formatted by MySQL
        appointment_time = appointment[3]  # Already formatted by MySQL
        patient_name = appointment[5]
        patient_email = appointment[6]
        patient_mobile = appointment[7]

        notification_title = "Appointment Declined"
        notification_message = f"Dear {patient_name}, we regret to inform you that your appointment request for {appointment_date} at {appointment_time} has been declined."
        
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, type)
            VALUES (%s, %s, %s, 'appointment_declined')
        """, (appointment[1], notification_title, notification_message))

        conn.commit()
        cursor.close()
        conn.close()

        # Emit real-time notification via WebSocket to patient
        socketio.emit('appointment_notification', {
            'type': 'appointment_declined',
            'title': notification_title,
            'message': notification_message,
            'appointment_id': appointment_id,
            'patient_id': appointment[1],
            'timestamp': datetime.now().isoformat()
        }, room=f'patient_{appointment[1]}')

        return jsonify({
            'success': True,
            'message': f'Appointment declined successfully',
            'appointment_id': appointment_id
        })

    except ValueError as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': str(e)}), 400
    
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        return jsonify({'error': 'Internal server error'}), 500

# Medication Management Routes - REMOVED

# Health Tracking Routes - REMOVED

@app.route('/upload_record', methods=['POST'])
@login_required
def upload_record():
    if session.get('role') != 'patient':
        return "Unauthorized", 403
    
    # Ensure user_id is in session (for backward compatibility)
    if 'user_id' not in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            session['user_id'] = user_data[0]
        else:
            return "User not found", 404
    
    if 'file' not in request.files:
        return "No file provided", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400
    
    if not allowed_file(file.filename):
        return "File type not allowed. Only PDF, PNG, JPG, JPEG files are accepted.", 400
    
    record_type = request.form.get('record_type')
    description = request.form.get('description', '')
    
    if not record_type:
        return "Record type is required", 400
    
    # Save file
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO health_records (patient_id, record_type, description, file_path) 
        VALUES (%s, %s, %s, %s)
    """, (session['user_id'], record_type, description, filename))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect(url_for('patient_records'))

@app.route('/api/patients')
@login_required
def get_patients():
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, username FROM users WHERE role = 'patient' ORDER BY name")
    patients = cursor.fetchall()
    cursor.close()
    conn.close()
    
    patient_list = [{'id': p[0], 'name': p[1], 'username': p[2]} for p in patients]
    return jsonify(patient_list)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('status', {'msg': f'{data["username"]} has entered the room.'}, room=room)

@socketio.on('send_message')
def handle_send_message(data):
    room = data['room']
    timestamp = datetime.now()
    message = {
        'username': data['username'],
        'message': data['message'],
        'timestamp': timestamp.isoformat(),
        'media_url': data.get('media_url')
    }
    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_messages (room, username, message, media_url, timestamp) VALUES (%s, %s, %s, %s, %s)",
                   (room, data['username'], data['message'], data.get('media_url'), timestamp))
    conn.commit()
    cursor.close()
    conn.close()
    emit('receive_message', message, room=room)

@socketio.on('video_call_offer')
def handle_video_call_offer(data):
    room = data['room']
    emit('video_call_offer', {
        'offer': data['offer'],
        'from': data['from'],
        'room': room
    }, room=room, skip_sid=request.sid)

@socketio.on('video_call_answer')
def handle_video_call_answer(data):
    room = data['room']
    emit('video_call_answer', {
        'answer': data['answer'],
        'from': data['from'],
        'room': room
    }, room=room, skip_sid=request.sid)

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    room = data['room']
    emit('ice_candidate', {
        'candidate': data['candidate'],
        'from': data['from'],
        'room': room
    }, room=room, skip_sid=request.sid)

@socketio.on('end_call')
def handle_end_call(data):
    room = data['room']
    emit('end_call', {
        'from': data['from'],
        'room': room
    }, room=room, skip_sid=request.sid)

@socketio.on('decline_call')
def handle_decline_call(data):
    room = data['room']
    emit('call_declined', {
        'from': data['from'],
        'room': room
    }, room=room, skip_sid=request.sid)

@socketio.on('join_doctors_room')
def handle_join_doctors_room():
    """Allow doctors to join the doctors room for SOS alerts"""
    if session.get('role') == 'doctor':
        join_room('doctors')
        emit('status', {'msg': f'Doctor {session.get("username")} joined SOS monitoring'})

@socketio.on('leave_doctors_room')
def handle_leave_doctors_room():
    """Allow doctors to leave the doctors room"""
    if session.get('role') == 'doctor':
        leave_room('doctors')
        emit('status', {'msg': f'Doctor {session.get("username")} left SOS monitoring'})

# API Routes for Doctor Dashboard
@app.route('/api/doctor/stats')
@login_required
def doctor_stats():
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get doctor_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
        doctor_data = cursor.fetchone()
        if not doctor_data:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Doctor not found'}), 404

        doctor_id = doctor_data[0]

        # Get today's appointments count
        from datetime import date
        today = date.today().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT COUNT(*) FROM appointments
            WHERE doctor_id = %s AND appointment_date = %s AND status IN ('scheduled', 'confirmed')
        """, (doctor_id, today))
        today_appointments = cursor.fetchone()[0]

        # Get total patients count
        cursor.execute("""
            SELECT COUNT(DISTINCT patient_id) FROM appointments WHERE doctor_id = %s
        """, (doctor_id,))
        total_patients = cursor.fetchone()[0]

        # Get total prescriptions count
        cursor.execute("""
            SELECT COUNT(*) FROM prescriptions WHERE doctor_id = %s
        """, (doctor_id,))
        total_prescriptions = cursor.fetchone()[0]

        # Get pending reviews (appointments that need follow-up)
        cursor.execute("""
            SELECT COUNT(*) FROM appointments
            WHERE doctor_id = %s AND status = 'completed' AND appointment_date < %s
        """, (doctor_id, today))
        pending_reviews = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'todayAppointments': today_appointments,
            'totalPatients': total_patients,
            'totalPrescriptions': total_prescriptions,
            'pendingReviews': pending_reviews
        })

    except Exception as e:
        print(f"Error getting doctor stats: {e}")
        return jsonify({
            'todayAppointments': 0,
            'totalPatients': 0,
            'totalPrescriptions': 0,
            'pendingReviews': 0
        })

@app.route('/api/doctor/recent-appointments')
@login_required
def doctor_recent_appointments():
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Get doctor_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s AND role = 'doctor'", (session['username'],))
        doctor_data = cursor.fetchone()
        if not doctor_data:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Doctor not found'}), 404

        doctor_id = doctor_data[0]

        # Get recent appointments
        cursor.execute("""
            SELECT a.id, a.patient_id, a.doctor_id, a.appointment_date, a.appointment_time,
                   a.appointment_type, a.symptoms, a.status, a.duration, a.preferred_language,
                   u.name as patient_name, u.email as patient_email, u.mobile as patient_mobile,
                   u.address as patient_address, u.city as patient_city, u.gender as patient_gender,
                   u.date_of_birth, u.blood_group, u.weight, u.medical_history, u.current_medications,
                   u.allergies
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = %s
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT 5
        """, (doctor_id,))

        appointments = []
        for row in cursor.fetchall():
            # Calculate age from date_of_birth
            patient_age = None
            if row[16]:  # date_of_birth is at index 16
                from datetime import datetime
                today = datetime.today()
                birth_date = row[16]
                patient_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            
            appointments.append({
                'id': row[0],
                'patient_id': row[1],
                'doctor_id': row[2],
                'appointment_date': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'appointment_time': str(row[4]) if row[4] else None,
                'appointment_type': row[5] or 'in_person',
                'symptoms': row[6],
                'status': row[7] or 'pending',
                'duration': row[8] or '30',
                'preferred_language': row[9] or 'English',
                'patient_name': row[10],
                'patient_email': row[11],
                'patient_mobile': row[12],
                'patient_address': row[13],
                'patient_city': row[14],
                'patient_gender': row[15],
                'patient_age': patient_age,
                'blood_group': row[17],
                'weight': row[18],
                'medical_history': row[19],
                'current_medications': row[20],
                'allergies': row[21]
            })

        cursor.close()
        conn.close()

        return jsonify(appointments)

    except Exception as e:
        print(f"Error getting recent appointments: {e}")
        return jsonify([])

@app.route('/api/patients')
@login_required
def api_get_patients():
    if session.get('role') != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, username, email, phone, address, date_of_birth, gender, blood_group
            FROM users
            WHERE role = 'patient'
            ORDER BY name
        """)

        patients = []
        for row in cursor.fetchall():
            patients.append({
                'id': row[0],
                'name': row[1],
                'username': row[2],
                'email': row[3],
                'phone': row[4],
                'address': row[5],
                'date_of_birth': row[6].strftime('%Y-%m-%d') if row[6] else None,
                'gender': row[7],
                'blood_group': row[8]
            })

        cursor.close()
        conn.close()

        return jsonify(patients)

    except Exception as e:
        print(f"Error getting patients: {e}")
        return jsonify([])

@app.route('/api/notifications')
@login_required
def get_notifications():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get unread notifications for the current user
        cursor.execute("""
            SELECT id, title, message, type, is_read, created_at
            FROM notifications 
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (session['user_id'],))
        
        notifications = []
        for row in cursor.fetchall():
            notifications.append({
                'id': row[0],
                'title': row[1],
                'message': row[2],
                'type': row[3],
                'is_read': bool(row[4]),
                'created_at': row[5].isoformat() if row[5] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(notifications)
        
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return jsonify([])

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First verify this notification belongs to the current user
        cursor.execute("""
            SELECT user_id FROM notifications 
            WHERE id = %s
        """, (notification_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != session['user_id']:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Notification not found'}), 404
            
        # Mark notification as read
        cursor.execute("""
            UPDATE notifications 
            SET is_read = TRUE 
            WHERE id = %s
        """, (notification_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return jsonify({'error': 'Internal server error'}), 500

        # Convert appointments from tuples to lists so they can be modified
        appointments = [list(appointment) for appointment in appointments]

        # Convert date and time fields to datetime objects for template strftime
        for appointment in appointments:
            try:
                appointment_date = appointment[3]  # appointment_date
                appointment_time = appointment[4]  # appointment_time

                # Handle different possible types returned by MySQL
                if isinstance(appointment_date, str):
                    # If it's a string, parse it
                    date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
                elif hasattr(appointment_date, 'days'):  # It's a timedelta
                    # Convert timedelta to date (assuming it's days since epoch or similar)
                    date_obj = (datetime(1970, 1, 1) + appointment_date).date()
                elif hasattr(appointment_date, 'strftime') and hasattr(appointment_date, 'year'):
                    # It's a proper date/datetime object
                    date_obj = appointment_date.date() if hasattr(appointment_date, 'date') else appointment_date
                else:
                    # Try to convert from whatever type it is
                    date_obj = appointment_date

                if isinstance(appointment_time, str):
                    # If it's a string, parse it
                    time_obj = datetime.strptime(appointment_time, '%H:%M:%S').time()
                elif hasattr(appointment_time, 'days'):  # It's a timedelta
                    # Convert timedelta to time (assuming it's seconds)
                    total_seconds = int(appointment_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    time_obj = datetime.time(hours, minutes, seconds)
                elif hasattr(appointment_time, 'strftime') and hasattr(appointment_time, 'hour'):
                    # It's a proper time/datetime object
                    time_obj = appointment_time.time() if hasattr(appointment_time, 'time') else appointment_time
                else:
                    # Try to convert from whatever type it is
                    time_obj = appointment_time

                # Create a datetime object for formatting
                if hasattr(date_obj, 'year') and hasattr(date_obj, 'month') and hasattr(date_obj, 'day'):
                    if hasattr(time_obj, 'hour') and hasattr(time_obj, 'minute') and hasattr(time_obj, 'second'):
                        # Both are proper date/time objects
                        datetime_obj = datetime.combine(date_obj, time_obj)
                    else:
                        # date_obj is a date, time_obj is not a time - use date as datetime
                        datetime_obj = datetime.combine(date_obj, datetime.min.time())
                else:
                    # Fallback: create a datetime from current time
                    datetime_obj = datetime.now()

                appointment[3] = datetime_obj  # Replace date with datetime
                appointment[4] = datetime_obj  # Replace time with datetime
            except (ValueError, TypeError, AttributeError) as e:
                # If conversion fails, create fallback datetime objects
                fallback_datetime = datetime.now()
                appointment[3] = fallback_datetime
                appointment[4] = fallback_datetime

        # Convert to JSON serializable format
        appointments_data = []
        for appointment in appointments:
            appointments_data.append({
                'id': appointment[0],
                'patient_id': appointment[1],
                'doctor_id': appointment[2],
                'date': appointment[3].strftime('%B %d, %Y'),
                'time': appointment[4].strftime('%I:%M %p'),
                'type': appointment[5],
                'status': appointment[6],
                'patient_name': appointment[11] or 'Unknown Patient',
                'patient_username': appointment[12] or 'unknown',
                'symptoms': appointment[7] or ''
            })

        return jsonify(appointments_data)

    except Exception as e:
        print(f"Error getting recent appointments: {e}")
        return jsonify([])

from dotenv import load_dotenv
import requests
import os
import json

# Load environment variables
load_dotenv()

INFERMEDICA_APP_ID = os.getenv('INFERMEDICA_APP_ID')
INFERMEDICA_APP_KEY = os.getenv('INFERMEDICA_APP_KEY')
INFERMEDICA_API_URL = 'https://api.infermedica.com/v3'

@app.route('/symptom-checker')
@login_required
def symptom_checker():
    return render_template('symptom_checker.html')

@app.route('/symptom-history')
@login_required
def symptom_history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user ID
    cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
    user = cursor.fetchone()
    
    # Get symptom check history
    cursor.execute("""
        SELECT 
            symptoms, age_group, gender, conditions_found, highest_probability, created_at 
        FROM symptom_checker_history 
        WHERE user_id = %s 
        ORDER BY created_at DESC
    """, (user['id'],))
    
    history = cursor.fetchall()
    
    # Calculate days ago for each entry
    for entry in history:
        if entry['created_at']:
            days_diff = (datetime.now() - entry['created_at']).days
            if days_diff == 0:
                entry['days_ago'] = 'Today'
            elif days_diff == 1:
                entry['days_ago'] = '1 day ago'
            else:
                entry['days_ago'] = f'{days_diff} days ago'
        else:
            entry['days_ago'] = 'Unknown'
    
    cursor.close()
    conn.close()
    
    return render_template('symptom_history.html', history=history)

@app.route('/check', methods=['POST'])
@login_required
def check_symptoms():
    try:
        # Get form data
        symptoms = request.form.get('symptoms', '')
        age = request.form.get('age', '')
        gender = request.form.get('gender', '')

        # Get user ID from session
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE username = %s", (session['username'],))
        user = cursor.fetchone()
        user_id = user['id']

        # Check if API credentials are configured
        if not INFERMEDICA_APP_ID or not INFERMEDICA_APP_KEY or INFERMEDICA_APP_ID == 'your-app-id-here':
            # Use mock data when API is not configured
            conditions = get_mock_conditions(symptoms.lower())
        else:
            # Use real API
            conditions = get_api_conditions(symptoms, age, gender)

        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO symptom_checker_history
            (user_id, symptoms, age_group, gender, conditions_found, highest_probability, api_response)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            symptoms,
            age,
            gender,
            json.dumps([c['name'] for c in conditions[:3]]),  # Store top 3 condition names
            conditions[0]['probability'] if conditions else 0,  # Highest probability
            json.dumps({'mock': True, 'conditions': conditions})  # Store response
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return render_template('symptom_result.html',
                            symptoms=symptoms,
                            age=age,
                            gender=gender,
                            conditions=conditions[:3])  # Show top 3 probable conditions

    except Exception as e:
        # Log the error (you should set up proper logging)
        print(f"Error in symptom checker: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return render_template('symptom_result.html',
                            symptoms=request.form.get('symptoms', ''),
                            age=request.form.get('age', ''),
                            gender=request.form.get('gender', ''),
                            error="We encountered an error processing your symptoms. Please try again or contact support.")

def get_mock_conditions(symptoms_text):
    """Mock symptom checker for when API is not available"""
    conditions = []

    # Simple keyword matching for demo purposes
    if 'fever' in symptoms_text or 'temperature' in symptoms_text:
        conditions.append({
            'name': 'Viral Fever',
            'probability': 75.0,
            'urgency': 'Medium Priority',
            'urgency_class': 'urgency-medium',
            'explanation': 'A viral fever is typically caused by viral infections and usually resolves within a few days with rest and fluids.',
            'recommendations': [
                'Rest and stay hydrated',
                'Take over-the-counter fever reducers like acetaminophen if needed',
                'Monitor temperature and seek medical attention if fever persists over 3 days',
                'Consult a doctor if accompanied by severe symptoms'
            ]
        })

    if 'headache' in symptoms_text or 'head' in symptoms_text:
        conditions.append({
            'name': 'Tension Headache',
            'probability': 60.0,
            'urgency': 'Low Priority',
            'urgency_class': 'urgency-low',
            'explanation': 'Tension headaches are the most common type of headache, often caused by stress, muscle tension, or poor posture.',
            'recommendations': [
                'Practice relaxation techniques',
                'Apply warm or cold compresses',
                'Maintain good posture and take breaks from screens',
                'Over-the-counter pain relievers may help'
            ]
        })

    if 'cough' in symptoms_text:
        conditions.append({
            'name': 'Common Cold',
            'probability': 55.0,
            'urgency': 'Low Priority',
            'urgency_class': 'urgency-low',
            'explanation': 'The common cold is a viral infection of the upper respiratory tract that typically resolves within 7-10 days.',
            'recommendations': [
                'Rest and stay hydrated',
                'Use over-the-counter cold medications for symptom relief',
                'Use a humidifier to ease congestion',
                'Seek medical attention if symptoms worsen or persist'
            ]
        })

    if 'stomach' in symptoms_text or 'nausea' in symptoms_text or 'vomiting' in symptoms_text:
        conditions.append({
            'name': 'Gastroenteritis',
            'probability': 45.0,
            'urgency': 'Medium Priority',
            'urgency_class': 'urgency-medium',
            'explanation': 'Gastroenteritis, commonly known as stomach flu, is an inflammation of the stomach and intestines usually caused by viral infection.',
            'recommendations': [
                'Stay hydrated with small sips of water or electrolyte solutions',
                'Avoid solid foods until vomiting stops',
                'Rest and avoid spreading to others',
                'Seek medical attention if dehydration signs appear'
            ]
        })

    # Add a default condition if no matches
    if not conditions:
        conditions.append({
            'name': 'General Health Concern',
            'probability': 30.0,
            'urgency': 'Low Priority',
            'urgency_class': 'urgency-low',
            'explanation': 'Based on your symptoms, we recommend monitoring your condition and consulting a healthcare provider if symptoms persist or worsen.',
            'recommendations': [
                'Monitor your symptoms and note any changes',
                'Maintain a healthy lifestyle with proper rest and nutrition',
                'Consult a healthcare provider for personalized advice',
                'Keep track of when symptoms started and their severity'
            ]
        })

    return conditions

def get_api_conditions(symptoms, age, gender):
    """Real API implementation using Infermedica"""
    # Prepare headers for Infermedica API
    headers = {
        'App-Id': INFERMEDICA_APP_ID,
        'App-Key': INFERMEDICA_APP_KEY,
        'Content-Type': 'application/json'
    }

    # Convert age range to actual number for API
    age_mapping = {
        '0-2': 1,
        '3-12': 7,
        '13-18': 15,
        '19-30': 25,
        '31-45': 38,
        '46-60': 53,
        '60+': 70
    }
    age_value = age_mapping.get(age, 30)  # Default to 30 if age range not found

    # First, analyze the text to extract symptoms
    nlp_payload = {
        'text': symptoms,
        'age': {
            'value': age_value
        },
        'sex': gender
    }

    # Parse symptoms from text
    nlp_response = requests.post(
        f'{INFERMEDICA_API_URL}/parse',
        json=nlp_payload,
        headers=headers
    )

    if nlp_response.status_code != 200:
        raise Exception(f"API Error: {nlp_response.text}")

    extracted_symptoms = nlp_response.json().get('mentions', [])

    # Prepare symptoms for diagnosis
    evidence = []
    for symptom in extracted_symptoms:
        if symptom.get('type') == 'symptom':
            evidence.append({
                'id': symptom['id'],
                'choice_id': 'present',
                'source': 'initial'
            })

    # Request diagnosis
    diagnosis_payload = {
        'age': {
            'value': age_value
        },
        'sex': gender,
        'evidence': evidence
    }

    diagnosis_response = requests.post(
        f'{INFERMEDICA_API_URL}/diagnosis',
        json=diagnosis_payload,
        headers=headers
    )

    if diagnosis_response.status_code != 200:
        raise Exception(f"API Error: {diagnosis_response.text}")

    diagnosis_data = diagnosis_response.json()

    # Process conditions
    conditions = []
    for condition in diagnosis_data.get('conditions', []):
        # Map probability to urgency level
        probability = round(condition['probability'] * 100, 1)
        if probability > 70:
            urgency = 'High Priority'
            urgency_class = 'urgency-high'
        elif probability > 40:
            urgency = 'Medium Priority'
            urgency_class = 'urgency-medium'
        else:
            urgency = 'Low Priority'
            urgency_class = 'urgency-low'

        # Get condition details
        condition_details = requests.get(
            f'{INFERMEDICA_API_URL}/conditions/{condition["id"]}',
            headers=headers
        ).json()

        conditions.append({
            'name': condition['name'],
            'probability': probability,
            'urgency': urgency,
            'urgency_class': urgency_class,
            'explanation': condition_details.get('extras', {}).get('hint', 'No additional information available.'),
            'recommendations': [
                'Consult with a healthcare provider for proper diagnosis',
                'Monitor your symptoms and note any changes',
                'Keep track of when symptoms started and their severity'
            ]
        })

    return conditions

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
