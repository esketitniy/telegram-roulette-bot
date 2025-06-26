import os
from datetime import timedelta

class Config:
    # Основные настройки
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///roulette.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Игровые настройки
    BETTING_TIME = 30  # секунд на ставки
    SPINNING_TIME = 10  # секунд вращения
    STARTING_BALANCE = 1000.0  # стартовый баланс
    MIN_BET = 1.0  # минимальная ставка
    MAX_BET = 10000.0  # максимальная ставка
    
    # Коэффициенты выплат
    PAYOUT_MULTIPLIERS = {
        'red': 2,
        'black': 2,
        'green': 36
    }

class ProductionConfig(Config):
    DEBUG = False
    REMEMBER_COOKIE_SECURE = True

class DevelopmentConfig(Config):
    DEBUG = True
    REMEMBER_COOKIE_SECURE = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
