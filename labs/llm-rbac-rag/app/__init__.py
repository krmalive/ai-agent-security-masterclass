from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import timedelta
from .models import db, User

login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        from . import routes
        db.create_all()

    return app
