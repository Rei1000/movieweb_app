"""
init_db.py
Dieses Skript initialisiert die Datenbank und erstellt alle Tabellen.
This script initializes the database and creates all tables.
"""

import os
from flask import Flask
from dotenv import load_dotenv
from models import db, User, Movie, UserMovie # UserMovie hinzugefügt, falls es für create_all benötigt wird, obwohl nicht direkt verwendet

# Umgebungsvariablen aus .env laden
# Load environment variables from .env
load_dotenv()

app = Flask(__name__) # Eigene Flask-App-Instanz für dieses Skript

# Datenbankkonfiguration aus Umgebungsvariablen oder Default
# Database config from environment variable or default
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///moviewebapp.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy an die Flask-App anbinden
# Bind SQLAlchemy to the Flask app
db.init_app(app)

def create_db():
    """
    Erstellt alle Tabellen in der Datenbank, falls sie noch nicht existieren.
    Creates all tables in the database if they do not already exist.
    """
    with app.app_context(): # Wichtig: app_context hier verwenden
        db.create_all()
        print("Datenbank und Tabellen wurden erfolgreich erstellt. / Database and tables have been successfully created.")

if __name__ == '__main__':
    create_db() 