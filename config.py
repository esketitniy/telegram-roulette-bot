import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    WEB_APP_URL = os.getenv('WEB_APP_URL')
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///casino.db')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
    PAYMENT_PROVIDER_TOKEN = os.getenv('TELEGRAM_PAYMENT_PROVIDER_TOKEN')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
