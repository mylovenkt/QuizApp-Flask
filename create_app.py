from flask import Flask
from quiz_app.routes import main
from quiz_app.extentions import db, socketio
from flask_login import LoginManager
from flask_migrate import Migrate
import os

login_manager = LoginManager()
migrate = Migrate()

def create_app(config_file:str="config.py") -> Flask:
    '''Create flask instance, set configuration from config_file.
    Paramaneter:
        - config_file: str
    Return:
        - app: Flask
    '''
    app = Flask(__name__,
                static_folder='static',
                static_url_path='/static')

    app.config["UPLOAD_FOLDER"] = "static/uploads"
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        os.makedirs(app.config["UPLOAD_FOLDER"])
    app.config.from_pyfile(config_file)
    app.register_blueprint(main)
    
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=True
    )

    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    
    with app.app_context():
        db.create_all()

    return app
