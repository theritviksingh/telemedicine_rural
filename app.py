from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from datetime import timedelta, datetime, time
import psycopg2
import psycopg2.extras
from functools import wraps
from flask_socketio import SocketIO, join_room, leave_room, emit
import os
from werkzeug.utils import secure_filename
import json
import logging
from urllib.parse import urlparse

# Initialize Flask app
app = Flask(__name__)

# Configuration for Render
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'ogg', 'mp3', 'wav', 'pdf', 'doc', 'docx', 'txt', 'zip', 'rar'}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}

@app.template_filter('now')
def now_filter(value):
    return datetime.now()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get PostgreSQL database connection for Render"""
    try:
        database_url = os.environ.get('DATABASE_URL')
        
        if database_url:
            # Ensure compatibility
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)

            url = urlparse(database_url)
            conn = psycopg2.connect(
                database=url.path[1:],
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port,
                sslmode='require'  # 🔑 Required on Render
            )
        else:
            # Local development fallback
            conn = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'telemedicine'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', 'password'),
                port=os.environ.get('DB_PORT', '5432')
            )
        
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize PostgreSQL database tables for Render"""
    conn = get_db_connection()
    if not conn:
        logger.error("Could not connect to database for initialization")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('doctor', 'patient', 'pharmacy')),
                name VARCHAR(100),
                email VARCHAR(100),
                mobile VARCHAR(15) DEFAULT '',
                date_of_birth DATE,
                gender VARCHAR(10) CHECK (gender IN ('Male', 'Female', 'Other')),
                address TEXT,
                pin_code VARCHAR(10),
                health_history TEXT,
                emergency_contact_name VARCHAR(100),
                emergency_contact_number VARCHAR(15),
                preferred_language VARCHAR(20) DEFAULT 'English',
                description TEXT,
                specialist VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create chat_messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                room VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                media_url VARCHAR(255),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create health_records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_records (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER,
                record_type VARCHAR(100) NOT NULL,
                description TEXT,
                file_path VARCHAR(255) NOT NULL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # Create symptom_checker_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symptom_checker_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                symptoms TEXT NOT NULL,
                age_group VARCHAR(20) NOT NULL,
                gender VARCHAR(10) NOT NULL,
                conditions_found TEXT NOT NULL,
                highest_probability FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                api_response TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create prescriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prescriptions (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                medicines TEXT NOT NULL,
                instructions TEXT,
                diagnosis TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create appointments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                doctor_id INTEGER NOT NULL,
                appointment_date DATE NOT NULL,
                appointment_time TIME NOT NULL,
                appointment_type VARCHAR(20) DEFAULT 'video' CHECK (appointment_type IN ('video', 'chat', 'in_person')),
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
                symptoms TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(30) DEFAULT 'general' CHECK (type IN ('appointment_approved', 'appointment_declined', 'appointment_reminder', 'prescription_ready', 'general', 'sos_alert')),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create sos_alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sos_alerts (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                location_error TEXT,
                status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'responded', 'resolved')),
                user_agent TEXT,
                page_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                responded_at TIMESTAMP,
                resolved_at TIMESTAMP,
                responding_doctor_id INTEGER,
                notes TEXT,
                FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (responding_doctor_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # Create medicines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                pharmacy_id INTEGER NOT NULL,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pharmacy_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages(room)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_records_patient ON health_records(patient_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor ON prescriptions(doctor_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
        
        # Insert sample data if no users exist
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            # Insert sample doctors
            sample_doctors = [
                ('dr_smith', 'password123', 'doctor', 'Dr. John Smith', 'john.smith@telemedicine.com', '1234567890', 'Experienced cardiologist with 15 years of practice', 'Cardiology'),
                ('dr_johnson', 'password123', 'doctor', 'Dr. Sarah Johnson', 'sarah.johnson@telemedicine.com', '1234567891', 'General practitioner specializing in family medicine', 'General Medicine'),
                ('dr_williams', 'password123', 'doctor', 'Dr. Michael Williams', 'michael.williams@telemedicine.com', '1234567892', 'Orthopedic surgeon with expertise in sports medicine', 'Orthopedics'),
                ('dr_brown', 'password123', 'doctor', 'Dr. Emily Brown', 'emily.brown@telemedicine.com', '1234567893', 'Dermatologist specializing in skin conditions', 'Dermatology'),
                ('dr_davis', 'password123', 'doctor', 'Dr. Robert Davis', 'robert.davis@telemedicine.com', '1234567894', 'Neurologist with focus on migraine treatment', 'Neurology')
            ]
            
            for doctor in sample_doctors:
                cursor.execute("""
                    INSERT INTO users (username, password, role, name, email, mobile, description, specialist)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, doctor)
            
            # Insert sample pharmacies
            sample_pharmacies = [
                ('medplus_pharmacy', 'password123', 'pharmacy', 'MedPlus Pharmacy', 'contact@medplus.com', '1234567895', 'Leading pharmacy chain with 24/7 service'),
                ('apollo_pharmacy', 'password123', 'pharmacy', 'Apollo Pharmacy', 'info@apollo.com', '1234567896', 'Trusted pharmacy with home delivery'),
                ('wellness_pharmacy', 'password123', 'pharmacy', 'Wellness Pharmacy', 'support@wellness.com', '1234567897', 'Your neighborhood pharmacy for all health needs')
            ]
            
            for pharmacy in sample_pharmacies:
                cursor.execute("""
                    INSERT INTO users (username, password, role, name, email, mobile, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, pharmacy)
            
            # Insert sample patient
            cursor.execute("""
                INSERT INTO users (username, password, role, name, email, mobile, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, ('patient_demo', 'password123', 'patient', 'Demo Patient', 'patient@demo.com', '9876543210', 'Demo patient account for testing'))
        
        cursor.close()
        conn.close()
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        if conn:
            conn.close()
        return False

# Initialize database on startup (only in development)
# For Render, this should be done via a separate script or database migration
if os.environ.get('FLASK_ENV') == 'development':
    init_database()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not username or not password or not role:
            flash('Please fill in all fields', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('login.html')
        
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
                SELECT * FROM users 
                WHERE username = %s AND password = %s AND role = %s
            """, (username, password, role))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['name'] = user['name']
                
                # Redirect based on role
                if role == 'patient':
                    return redirect(url_for('patient_dashboard'))
                elif role == 'doctor':
                    return redirect(url_for('doctor_dashboard'))
                elif role == 'pharmacy':
                    return redirect(url_for('pharmacy_dashboard'))
            else:
                flash('Invalid credentials', 'error')
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login error occurred', 'error')
            if conn:
                conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        name = request.form.get('name')
        email = request.form.get('email')
        mobile = request.form.get('mobile', '')
        
        if not all([username, password, role, name, email]):
            flash('Please fill in all required fields', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('register.html')
        
        try:
            cursor = conn.cursor()
            
            # Check if username already exists
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                cursor.close()
                conn.close()
                return render_template('register.html')
            
            # Insert new user
            cursor.execute("""
                INSERT INTO users (username, password, role, name, email, mobile)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, password, role, name, email, mobile))
            
            cursor.close()
            conn.close()
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            flash('Registration error occurred', 'error')
            if conn:
                conn.close()
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/patient_dashboard')
@login_required
def patient_dashboard():
    if session.get('role') != 'patient':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('patient_dashboard.html')
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get recent appointments
        cursor.execute("""
            SELECT a.*, u.name as doctor_name, u.specialist
            FROM appointments a
            JOIN users u ON a.doctor_id = u.id
            WHERE a.patient_id = %s
            ORDER BY a.appointment_date DESC, a.appointment_time DESC
            LIMIT 5
        """, (session['user_id'],))
        appointments = cursor.fetchall()
        
        # Get recent prescriptions
        cursor.execute("""
            SELECT p.*, u.name as doctor_name
            FROM prescriptions p
            JOIN users u ON p.doctor_id = u.id
            WHERE p.patient_id = %s
            ORDER BY p.date DESC
            LIMIT 5
        """, (session['user_id'],))
        prescriptions = cursor.fetchall()
        
        # Get unread notifications
        cursor.execute("""
            SELECT * FROM notifications
            WHERE user_id = %s AND is_read = FALSE
            ORDER BY created_at DESC
            LIMIT 5
        """, (session['user_id'],))
        notifications = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('patient_dashboard.html', 
                             appointments=appointments,
                             prescriptions=prescriptions,
                             notifications=notifications)
        
    except Exception as e:
        logger.error(f"Patient dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        if conn:
            conn.close()
        return render_template('patient_dashboard.html')

@app.route('/doctor_dashboard')
@login_required
def doctor_dashboard():
    if session.get('role') != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('doctor_dashboard.html')
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get pending appointments
        cursor.execute("""
            SELECT a.*, u.name as patient_name, u.mobile
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = %s AND a.status = 'pending'
            ORDER BY a.appointment_date, a.appointment_time
        """, (session['user_id'],))
        pending_appointments = cursor.fetchall()
        
        # Get today's appointments
        cursor.execute("""
            SELECT a.*, u.name as patient_name, u.mobile
            FROM appointments a
            JOIN users u ON a.patient_id = u.id
            WHERE a.doctor_id = %s AND a.appointment_date = CURRENT_DATE
            AND a.status IN ('confirmed', 'scheduled')
            ORDER BY a.appointment_time
        """, (session['user_id'],))
        today_appointments = cursor.fetchall()
        
        # Get recent prescriptions written
        cursor.execute("""
            SELECT p.*, u.name as patient_name
            FROM prescriptions p
            JOIN users u ON p.patient_id = u.id
            WHERE p.doctor_id = %s
            ORDER BY p.date DESC
            LIMIT 5
        """, (session['user_id'],))
        prescriptions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('doctor_dashboard.html',
                             pending_appointments=pending_appointments,
                             today_appointments=today_appointments,
                             prescriptions=prescriptions)
        
    except Exception as e:
        logger.error(f"Doctor dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        if conn:
            conn.close()
        return render_template('doctor_dashboard.html')

@app.route('/pharmacy_dashboard')
@login_required
def pharmacy_dashboard():
    if session.get('role') != 'pharmacy':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('pharmacy_dashboard.html')
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get medicine inventory
        cursor.execute("""
            SELECT * FROM medicines
            WHERE pharmacy_id = %s
            ORDER BY name
        """, (session['user_id'],))
        medicines = cursor.fetchall()
        
        # Get recent prescriptions for this pharmacy
        cursor.execute("""
            SELECT p.*, u.name as patient_name, d.name as doctor_name
            FROM prescriptions p
            JOIN users u ON p.patient_id = u.id
            JOIN users d ON p.doctor_id = d.id
            WHERE p.status = 'active'
            ORDER BY p.date DESC
            LIMIT 10
        """, ())
        prescriptions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('pharmacy_dashboard.html',
                             medicines=medicines,
                             prescriptions=prescriptions)
        
    except Exception as e:
        logger.error(f"Pharmacy dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        if conn:
            conn.close()
        return render_template('pharmacy_dashboard.html')

@app.route('/book_appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if session.get('role') != 'patient':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        appointment_type = request.form.get('appointment_type', 'video')
        symptoms = request.form.get('symptoms', '')
        
        if not all([doctor_id, appointment_date, appointment_time]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('book_appointment'))
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('book_appointment'))
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_type, symptoms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session['user_id'], doctor_id, appointment_date, appointment_time, appointment_type, symptoms))
            
            cursor.close()
            conn.close()
            
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('patient_appointments'))
            
        except Exception as e:
            logger.error(f"Appointment booking error: {e}")
            flash('Error booking appointment', 'error')
            if conn:
                conn.close()
    
    # Get list of doctors
    conn = get_db_connection()
    doctors = []
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
                SELECT id, name, specialist, description
                FROM users
                WHERE role = 'doctor'
                ORDER BY name
            """)
            doctors = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching doctors: {e}")
            if conn:
                conn.close()
    
    return render_template('book_appointment.html', doctors=doctors)

@app.route('/patient_appointments')
@login_required
def patient_appointments():
    if session.get('role') != 'patient':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    appointments = []
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
                SELECT a.*, u.name as doctor_name, u.specialist
                FROM appointments a
                JOIN users u ON a.doctor_id = u.id
                WHERE a.patient_id = %s
                ORDER BY a.appointment_date DESC, a.appointment_time DESC
            """, (session['user_id'],))
            appointments = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            if conn:
                conn.close()
    
    return render_template('patient_appointments.html', appointments=appointments)

@app.route('/doctor_appointments')
@login_required
def doctor_appointments():
    if session.get('role') != 'doctor':
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    appointments = []
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("""
                SELECT a.*, u.name as patient_name, u.mobile, u.email
                FROM appointments a
                JOIN users u ON a.patient_id = u.id
                WHERE a.doctor_id = %s
                ORDER BY a.appointment_date DESC, a.appointment_time DESC
            """, (session['user_id'],))
            appointments = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching appointments: {e}")
            if conn:
                conn.close()
    
    return render_template('doctor_appointments.html', appointments=appointments)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/init_db')
def init_db_route():
    """Manual database initialization route for Render deployment"""
    if init_database():
        return jsonify({'status': 'success', 'message': 'Database initialized successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Database initialization failed'}), 500

@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    user_data = {}
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            if conn:
                conn.close()
    
    return render_template('profile.html', user=user_data)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# SocketIO events for chat functionality
@socketio.on('join')
def on_join(data):
    username = session.get('username')
    room = data['room']
    if username:
        join_room(room)
        emit('status', {'msg': f'{username} has entered the room.'}, room=room)

@socketio.on('leave')
def on_leave(data):
    username = session.get('username')
    room = data['room']
    if username:
        leave_room(room)
        emit('status', {'msg': f'{username} has left the room.'}, room=room)

@socketio.on('message')
def handle_message(data):
    username = session.get('username')
    room = data['room']
    message = data['message']
    
    if username and room and message:
        # Save message to database
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chat_messages (room, username, message)
                    VALUES (%s, %s, %s)
                """, (room, username, message))
                cursor.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error saving chat message: {e}")
                if conn:
                    conn.close()
        
        # Emit message to room
        emit('message', {
            'username': username,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if os.environ.get('FLASK_ENV') == 'production':
        # Production mode
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
    else:
        # Development mode
        socketio.run(app, host='0.0.0.0', port=port, debug=True)
