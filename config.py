from os import environ

SECRET_KEY = environ.get("SECRET_KEY") or "github.com/mylovenkt"
SQLALCHEMY_DATABASE_URI = environ.get("SQLALCHEMY_DATABASE_URI") or "sqlite:///db.sqlite"
