from flask import Flask
from quiz_app.extentions import db
from sqlalchemy import text
import os

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

def run_migration():
    with app.app_context():
        try:
            # Read and execute the SQL file
            with open('migrations/add_message_reactions.sql', 'r') as f:
                sql_commands = f.read()
                # Split commands if there are multiple statements
                for command in sql_commands.split(';'):
                    if command.strip():
                        try:
                            # Wrap the SQL command in text()
                            db.session.execute(text(command))
                            print(f"✅ Executed command successfully")
                        except Exception as cmd_error:
                            print(f"⚠️ Command error: {str(cmd_error)}")
                            continue
            db.session.commit()
            print("✅ Message reactions migration completed successfully!")
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    run_migration() 