import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from quiz_app.extentions import db
from sqlalchemy import text

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
            db.session.execute(text('ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0'))
            db.session.commit()
            print("✅ Added email_verified column to user table")
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration() 