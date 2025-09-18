#!/usr/bin/env python3
"""
Database initialization script for Render deployment
Creates all necessary tables for the telemedicine application
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

def get_db_connection():
    """Get database connection from DATABASE_URL environment variable"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Parse the database URL
    url = urlparse(database_url)
    
    return psycopg2.connect(
        host=url.hostname,
        port=url.port,
        database=url.path[1:],  # Remove leading slash
        user=url.username,
        password=url.password
    )

def create_tables():
    """Create all necessary tables for the application"""
    
    tables = {
        'users': """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'patient' CHECK (role IN ('patient', 'doctor', 'pharmacy', 'admin')),
                phone VARCHAR(30),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'appointments': """
            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER NOT NULL REFERENCES users(id),
                doctor_id INTEGER REFERENCES users(id),
                start_time TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending',
                notes TEXT,
                location VARCHAR(255),
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'consultations': """
            CREATE TABLE IF NOT EXISTS consultations (
                id SERIAL PRIMARY KEY,
                appointment_id INTEGER REFERENCES appointments(id),
                summary TEXT,
                recording_url VARCHAR(512),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'chat_sessions': """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255),
                patient_id INTEGER REFERENCES users(id),
                doctor_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'messages': """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES chat_sessions(id),
                sender_id INTEGER REFERENCES users(id),
                content TEXT,
                message_type VARCHAR(20) DEFAULT 'text',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'prescriptions': """
            CREATE TABLE IF NOT EXISTS prescriptions (
                id SERIAL PRIMARY KEY,
                consultation_id INTEGER REFERENCES consultations(id),
                patient_id INTEGER REFERENCES users(id),
                doctor_id INTEGER REFERENCES users(id),
                medication_details TEXT,
                instructions TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """,
        
        'pharmacy_orders': """
            CREATE TABLE IF NOT EXISTS pharmacy_orders (
                id SERIAL PRIMARY KEY,
                prescription_id INTEGER REFERENCES prescriptions(id),
                pharmacy_id INTEGER REFERENCES users(id),
                patient_id INTEGER REFERENCES users(id),
                status VARCHAR(20) DEFAULT 'pending',
                delivery_address TEXT,
                total_amount DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for table_name, create_sql in tables.items():
            print(f"Creating table: {table_name}...")
            cursor.execute(create_sql)
            conn.commit()
            print(f"✓ Table {table_name} created successfully")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);",
            "CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id);",
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);",
            "CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);",
            "CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);",
            "CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor ON prescriptions(doctor_id);",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            conn.commit()
        
        print("✓ All indexes created successfully")
        
        # Insert default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role)
                VALUES ('admin', 'admin@telemedicine.com', 'admin123', 'admin')
            """)
            conn.commit()
            print("✓ Default admin user created")
        
        print("\n🎉 Database initialization completed successfully!")
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("🚀 Initializing database for telemedicine application...")
    create_tables()