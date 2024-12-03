import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from quiz_app.extentions import db
from quiz_app.models import *  # Import all models to ensure they're registered

# Get absolute path to instance directory
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, 'instance')

# Create instance directory if it doesn't exist
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

# Create a minimal Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "db.sqlite")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def recreate_db():
    with app.app_context():
        try:
            # Drop all tables
            db.drop_all()
            print("✅ Dropped all existing tables")
            
            # Create all tables
            db.create_all()
            print("✅ Created all tables with new schema")
            
            print("✅ Database recreation completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during database recreation: {str(e)}")

if __name__ == "__main__":
    recreate_db() 