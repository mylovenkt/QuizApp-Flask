import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from quiz_app.extentions import db
from sqlalchemy import text
from datetime import datetime

# Get absolute path to instance directory
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, '..', 'instance')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "db.sqlite")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def run_migration():
    with app.app_context():
        try:
            # Add column without default value
            db.session.execute(text('ALTER TABLE question ADD COLUMN created_at DATETIME'))
            
            # Update existing rows with current timestamp
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            db.session.execute(text(f"UPDATE question SET created_at = '{current_time}'"))
            
            db.session.commit()
            print("✅ Added and populated created_at column in question table")
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration() 