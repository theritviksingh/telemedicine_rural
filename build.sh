#!/usr/bin/env bash
# build.sh - Render build script

set -o errexit  # exit on error

# Install Python dependencies
pip install -r requirements.txt

# Run database initialization (for first deploy only)
python -c "
import os
os.environ['FLASK_ENV'] = 'production'
from app_fixed_render import init_database
init_database()
print('Database initialization completed')
"
