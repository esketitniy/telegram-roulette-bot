from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=1000.0)  # Стартовый баланс
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь с ставками
    bets = db.relationship('Bet', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class GameRound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_number = db.Column(db.Integer, unique=True, nullable=False)
    winning_number = db.Column(db.Integer, nullable=True)
    winning_color = db.Column(db.String(10), nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='betting')  # betting, spinning, finished
    
    # Связь со ставками
    bets = db.relationship('Bet', backref='game_round', lazy=True)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('game_round.id'), nullable=False)
    bet_type = db.Column(db.String(20), nullable=False)  # red, black, green
    amount = db.Column(db.Float, nullable=False)
    potential_win = db.Column(db.Float, nullable=False)
    actual_win = db.Column(db.Float, default=0.0)
    is_winner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
