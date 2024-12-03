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
            # Drop old table if exists
            db.session.execute(text('DROP TABLE IF EXISTS user_sets'))
            # Create new table if not exists
            db.session.execute(text('''
                CREATE TABLE IF NOT EXISTS user_quiz_sets (
                    user_id INTEGER NOT NULL,
                    quiz_set_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, quiz_set_id),
                    FOREIGN KEY (user_id) REFERENCES user (id),
                    FOREIGN KEY (quiz_set_id) REFERENCES questionset (id)
                )
            '''))
            db.session.commit()
            print("✅ Updated user-quiz sets relationship tables")
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration() 