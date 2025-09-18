# Symptom Checker Setup Guide

## Current Status
The symptom checker is currently running in **demo mode** with mock data. This means it will work and provide sample results, but it's not using real medical AI analysis.

## To Enable Full Functionality

### 1. Get Infermedica API Credentials
1. Visit [Infermedica Developer Portal](https://developer.infermedica.com/)
2. Sign up for a free account
3. Create a new application
4. Get your `App-ID` and `App-Key`

### 2. Update Environment Variables
Edit the `.env` file in your project root:

```env
INFERMEDICA_APP_ID=your-actual-app-id-here
INFERMEDICA_APP_KEY=your-actual-app-key-here
```

### 3. Restart the Application
After updating the credentials, restart your Flask application:

```bash
python app.py
```

## Features

### Current (Demo Mode)
- ✅ Mock symptom analysis based on keywords
- ✅ Database storage of symptom check history
- ✅ User-friendly interface
- ✅ Age and gender consideration
- ✅ Probability scoring and urgency levels

### With API (Full Mode)
- ✅ Real AI-powered symptom analysis
- ✅ Natural language processing
- ✅ Medical-grade condition matching
- ✅ Evidence-based probability calculations
- ✅ Integration with medical knowledge base

## Testing

You can test the current demo functionality by:

1. Starting the Flask app: `python app.py`
2. Logging in to your account
3. Going to `/symptom-checker`
4. Entering symptoms like:
   - "fever and headache"
   - "cough and sore throat"
   - "stomach pain and nausea"

The system will provide relevant mock results and save them to your history.

## Database

The system automatically creates a `symptom_checker_history` table that stores:
- User ID
- Symptoms entered
- Age group and gender
- Conditions found
- Probability scores
- Full API response (when available)
- Timestamp

View your history at `/symptom-history` after logging in.