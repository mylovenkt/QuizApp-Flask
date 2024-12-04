import os
import sys
import glob

# Add the parent directory to Python path so we can import quiz_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from quiz_app.extentions import db
from sqlalchemy import text

def setup_app():
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, '..', 'instance')
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_dir, "db.sqlite")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def run_migration(sql_file):
    app = setup_app()
    with app.app_context():
        try:
            with open(sql_file, 'r') as f:
                sql_commands = f.read()
                for command in sql_commands.split(';'):
                    if command.strip():
                        try:
                            db.session.execute(text(command))
                            print(f"✅ Executed: {command[:50]}...")
                        except Exception as e:
                            print(f"⚠️ Error executing command: {str(e)}")
                            continue
                db.session.commit()
                print(f"✅ Migration {os.path.basename(sql_file)} completed successfully!")
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    # Run all SQL migrations in the migrations folder
    sql_files = glob.glob('migrations/*.sql')
    for sql_file in sorted(sql_files):
        run_migration(sql_file) 