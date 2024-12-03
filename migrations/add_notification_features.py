import os
import sys

# Add the parent directory to Python path so we can import quiz_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from quiz_app.extentions import db
from sqlalchemy import text

# Get absolute path to instance directory
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, '..', 'instance')

# Create instance directory if it doesn't exist
if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

# Create a minimal Flask app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "db.sqlite")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def run_migration():
    with app.app_context():
        try:
            # Add new columns to notification table
            commands = [
                'ALTER TABLE notification ADD COLUMN is_read BOOLEAN DEFAULT 0',
                'ALTER TABLE notification ADD COLUMN action_taken BOOLEAN DEFAULT 0',
                'ALTER TABLE notification ADD COLUMN priority VARCHAR(10) DEFAULT "normal"',
                'ALTER TABLE notification ADD COLUMN expiry_date DATETIME',
                'ALTER TABLE notification ADD COLUMN extra_data JSON'
            ]
            
            for command in commands:
                try:
                    db.session.execute(text(command))
                    print(f"✅ Executed: {command}")
                except Exception as e:
                    print(f"⚠️ Error executing {command}: {str(e)}")
                    # Continue with other commands even if one fails
                    continue
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration() 