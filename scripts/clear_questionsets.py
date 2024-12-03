import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from quiz_app.extentions import db
from quiz_app.models import QuestionSet
from sqlalchemy import text

# Get absolute path to instance directory
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, '..', 'instance')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "db.sqlite")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def clear_questionsets():
    with app.app_context():
        try:
            # First, set question_set_id to NULL for all questions
            db.session.execute(text('UPDATE question SET question_set_id = NULL'))
            
            # Then delete all records from user_quiz_sets
            db.session.execute(text('DELETE FROM user_quiz_sets'))
            
            # Finally delete all records from questionset
            db.session.execute(text('DELETE FROM questionset'))
            
            db.session.commit()
            print("✅ Successfully cleared all quiz sets")
        except Exception as e:
            print(f"❌ Error clearing quiz sets: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    clear_questionsets() 