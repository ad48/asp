from app import sadb

# ---------------------------------------------
# SQL alchemy
# ---------------------------------------------
# from app import app, db, login


# login = LoginManager(app)
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, sadb.Model):
    """User database model."""
    __tablename__ = 'user'
    id = sadb.Column(sadb.Integer, primary_key=True)
    orcid = sadb.Column(sadb.String(64), nullable=False, unique=True)
    email = sadb.Column(sadb.String(64), nullable=True)
    orcid_name = sadb.Column(sadb.String(64), nullable=True)
    username = sadb.Column(sadb.String(64), nullable=True)
    # fname = sadb.Column(sadb.String(64), nullable=False)
    # lname = sadb.Column(sadb.String(64), nullable=False)
    access_token = sadb.Column(sadb.String(64), nullable=False)
    refresh_token = sadb.Column(sadb.String(64), nullable=False)
    retrieved = sadb.Column(sadb.Integer)
    expires_in = sadb.Column(sadb.Integer)
    update_time = sadb.Column(sadb.DateTime, index=True, default=datetime.utcnow)


class Library(sadb.Model):
    __tablename__ = 'library'
    id = sadb.Column(sadb.Integer, primary_key=True)
    user_id = sadb.Column(sadb.Integer) # id from User
    paper_id = sadb.Column(sadb.String(64), nullable=False)
    update_time = sadb.Column(sadb.DateTime, index=True, default= datetime.utcnow)


class Publication(sadb.Model): # db of users' arxiv preprints
    __tablename__ = 'publication'
    id = sadb.Column(sadb.Integer, primary_key=True)
    user_id = sadb.Column(sadb.Integer)
    paper_id = sadb.Column(sadb.String(64), nullable=False)
    doi = sadb.Column(sadb.String(64), nullable=False)
    update_time = sadb.Column(sadb.DateTime, index=True, default= datetime.utcnow)
