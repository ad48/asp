from flask import Flask
from app.config import Config

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter

import logging
from logging.handlers import SMTPHandler, RotatingFileHandler

app = Flask(__name__)
app.config.from_object(Config)

# app.debug=True

sadb = SQLAlchemy(app)
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

limiter = Limiter(app, default_limits=["100 per hour", "20 per minute"])
lm = LoginManager(app)


from app import routes, models, utils
