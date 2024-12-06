from os import environ
from dotenv import load_dotenv
import os
from datetime import timedelta

load_dotenv()

SECRET_KEY = environ.get("SECRET_KEY") or "github.com/mylovenkt"
SQLALCHEMY_DATABASE_URI = environ.get("SQLALCHEMY_DATABASE_URI") or "sqlite:///db.sqlite"
SQLALCHEMY_TRACK_MODIFICATIONS = False
PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

# File upload settings
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'chat')
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size