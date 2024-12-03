from create_app import create_app, socketio, login_manager
from quiz_app.models import User
from flask_migrate import Migrate
from quiz_app.extentions import db

app = create_app()
migrate = Migrate(app, db)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

if __name__ == "__main__":
    socketio.run(app, debug=True, port=15000)
