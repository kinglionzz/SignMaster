import os

class Config:
    SECRET_KEY = 'your_super_secret_key_here_change_in_production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'