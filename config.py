import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'nyayasetu-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///nyayasetu.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
