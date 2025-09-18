# Telemedicine for Rural Nabha - Deployment Guide

## 🚀 Deploy to Render

This guide will help you deploy your telemedicine application to Render with a PostgreSQL database.

### Prerequisites
- GitHub account
- Render account (free tier available)
- Your project code pushed to GitHub

### Step 1: Prepare Your Repository

1. Make sure all files are committed to your GitHub repository:
   - `render.yaml` (deployment configuration)
   - `requirements.txt` (Python dependencies)
   - `scripts/init_db.py` (database initialization)
   - `.env.example` (environment template)
   - All your Flask app files

### Step 2: Deploy to Render

1. **Login to Render**: Go to [render.com](https://render.com) and sign in
2. **Create New Service**: Click "New +" → "Blueprint"
3. **Connect Repository**: 
   - Connect your GitHub account if not already connected
   - Select your telemedicine project repository
4. **Configure Deployment**:
   - Render will automatically detect the `render.yaml` file
   - It will create both a PostgreSQL database and web service
   - Wait for the build to complete (5-10 minutes)

### Step 3: Environment Variables (Automatic)

The `render.yaml` file automatically configures:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Auto-generated secure key
- `FLASK_ENV=production`
- `FLASK_APP=app.py`

### Step 4: Database Initialization

The database tables are automatically created during deployment by the `scripts/init_db.py` script.

### Step 5: Access Your Application

Once deployment is complete:
1. Render will provide a URL like: `https://your-app-name.onrender.com`
2. Visit the URL to see your live application
3. You can register patients and login as:
   - Default admin: `admin` / `admin123`
   - Test doctors: `doctor-1` / `doctor-123`
   - Test pharmacies: `pharmacy-1` / `pharm-123`

## 🔧 Local Development Setup

### Prerequisites
- Python 3.9+
- MySQL Server (for local development)
- Git

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/telemedicine-rural-nabha.git
   cd telemedicine-rural-nabha
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1  # Windows PowerShell
   # or
   source .venv/bin/activate   # Linux/Mac
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   copy .env.example .env
   # Edit .env with your MySQL credentials
   ```

5. **Set up MySQL database**:
   ```sql
   CREATE DATABASE telemedicine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

6. **Run the application**:
   ```bash
   python app.py
   # or
   flask run
   ```

7. **Access locally**: http://localhost:5000

## 🌐 Multi-Device Setup (Same Database)

To run the app on multiple devices (doctor, pharmacy, patient laptops) sharing the same database:

### Option 1: Use Render Production Database
All devices point to the same Render database:
1. Get the `DATABASE_URL` from your Render dashboard
2. Create `.env` file on each device with:
   ```
   DATABASE_URL=your_render_postgresql_url_here
   FLASK_ENV=development
   SECRET_KEY=same_secret_key_for_all
   ```

### Option 2: Local Network Database
Set up one machine as database server:
1. Install MySQL on one machine (database host)
2. Configure MySQL to accept remote connections
3. Update `.env` on all other machines:
   ```
   MYSQL_HOST=192.168.1.100  # IP of database host
   MYSQL_USER=telemedicine_user
   MYSQL_PASSWORD=secure_password
   MYSQL_DB=telemedicine
   ```

## 📱 Features Included

- **Patient Registration & Login**
- **Doctor Dashboard** with appointment management
- **Pharmacy Network** for prescription fulfillment
- **AI Symptom Checker** (UI ready for API integration)
- **Video Consultation** scheduling
- **Real-time Chat** via SocketIO
- **Emergency SOS** with location sharing
- **Multi-language Support** (Google Translate)
- **Responsive Design** for mobile/desktop

## 🔒 Security Notes

- Change default passwords in production
- Use HTTPS (Render provides this automatically)
- Set strong `SECRET_KEY` in production
- Limit database access to authorized IPs only
- Review and update dependencies regularly

## 🐛 Troubleshooting

### Database Connection Issues
- Check `DATABASE_URL` format for PostgreSQL
- Verify MySQL credentials for local development
- Ensure database server is running

### Static Files Not Loading
- Check static file paths in templates
- Ensure `static/` folder contains required images
- Verify `url_for('static', filename='...')` calls

### SocketIO Connection Problems
- Check firewall settings
- Ensure proper CORS configuration
- Verify WebSocket support in deployment environment

## 📞 Support

For issues or questions:
- Check the GitHub Issues
- Review deployment logs in Render dashboard
- Contact: Team ALPHA 01

---

**Problem Statement ID**: 25018  
**Project**: Telemedicine Access for Rural healthcare in Nabha  
**Team**: ALPHA 01  
**Category**: Software - MedTech/BioTech/HealthTech
