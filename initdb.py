import os
from flask import Flask
from extensions import db
from models import *
from dotenv import load_dotenv

def create_app():
    app = Flask(__name__)

    # Load .env
    load_dotenv()

    # Ambil DB URL dari env
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Membuat semua tabel di database...")
        db.drop_all()   # hati-hati: ini hapus semua tabel lama
        db.create_all()
        print("Selesai membuat tabel.")
