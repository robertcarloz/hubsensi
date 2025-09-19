#!/usr/bin/env python3
"""
Script to insert initial superadmin user into HubSensi database
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from app import create_app
from extensions import db
from models import User, UserRole, School, SchoolSubscription, SubscriptionPlan

def insert_superadmin():
    """Insert the initial superadmin user"""
    
    app = create_app()
    
    with app.app_context():
        # Check if superadmin already exists
        superadmin = User.query.filter_by(role=UserRole.SUPERADMIN).first()
        
        if superadmin:
            print(f"Superadmin sudah ada: {superadmin.username}")
            return False
        
        # Create superadmin user
        superadmin = User(
            username=os.environ.get('SUPERADMIN_USERNAME', 'superadmin'),
            email=os.environ.get('SUPERADMIN_EMAIL', 'superadmin@hubsensi.com'),
            role=UserRole.SUPERADMIN
        )
        superadmin.set_password('superadmin123')  # Ganti di production!
        
        db.session.add(superadmin)
        db.session.commit()
        
        print("=" * 50)
        print("SUPERADMIN USER BERHASIL DIBUAT!")
        print("=" * 50)
        print(f"Username: {superadmin.username}")
        print(f"Password: superadmin123")
        print(f"Email: {superadmin.email}")
        print("=" * 50)
        print("PENTING: Ganti password setelah login pertama!")
        print("=" * 50)
        
        return True

if __name__ == '__main__':
    insert_superadmin()