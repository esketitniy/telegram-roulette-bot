import os
import sqlite3
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random
import json
import os
import sqlite3
import threading
import time
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import hashlib
import secrets
from datetime import datetime, timedelta

# Глобальное игровое состояние
game_state = {
    'round': 0,
    'phase': 'betting',
    'time_left': 30,
    'bets': {},
    'last_result': None,
    'spinning_result': None,
    'start_time': time.time()
}

# Определяем путь к базе данных
DB_PATH = '/data/casino_online.db' if os.path.exists('/data') else 'casino_online.db'

print(f"🗂️  Using database path: {DB_PATH}")
print(f"💾 Disk mounted: {os.path.exists('/data')}")

# Создаем директорию для БД если нужно
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
    print(f"📁 Created directory: {db_dir}")
    
def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_session_token():
    """Генерация токена сессии"""
    return secrets.token_urlsafe(32)

def create_user_account(username, password, display_name):
    """Создание аккаунта пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем уникальность username
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return None, "Username already exists"
        
        # Создаем пользователя
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, display_name, balance)
            VALUES (?, ?, ?, 1000)
        ''', (username, password_hash, display_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id, "User created successfully"
        
    except Exception as e:
        print(f"Error creating user: {e}")
        if 'conn' in locals():
            conn.close()
        return None, str(e)

def authenticate_user(username, password):
    """Аутентификация пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        cursor.execute('''
            SELECT id, username, display_name, balance 
            FROM users 
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash))
        
        user = cursor.fetchone()
        
        if user:
            # Обновляем время последнего входа
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (user[0],))
            conn.commit()
        
        conn.close()
        return user
        
    except Exception as e:
        print(f"Authentication error: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def create_session(user_id):
    """Создание сессии пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Деактивируем старые сессии
        cursor.execute('UPDATE user_sessions SET is_active = 0 WHERE user_id = ?', (user_id,))
        
        # Создаем новую сессию
        session_token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)  # Сессия на 7 дней
        
        cursor.execute('''
            INSERT INTO user_sessions (user_id, session_token, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, session_token, expires_at))
        
        conn.commit()
        conn.close()
        
        return session_token
        
    except Exception as e:
        print(f"Session creation error: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def validate_session(session_token):
    """Проверка действительности сессии"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.display_name, u.balance
            FROM users u
            JOIN user_sessions s ON u.id = s.user_id
            WHERE s.session_token = ? AND s.is_active = 1 AND s.expires_at > CURRENT_TIMESTAMP
        ''', (session_token,))
        
        user = cursor.fetchone()
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"Session validation error: {e}")
        if 'conn' in locals():
            conn.close()
        return None


# Версия приложения
APP_VERSION = "1.0.0"

# Логирование
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Настройки
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
PORT = int(os.getenv('PORT', 5000))
APP_URL = os.getenv('APP_URL', 'https://your-app.onrender.com')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'casino_secret_key_2024'

# Глобальные переменные для ОНЛАЙН игры
online_players = {}
current_bets = {}
game_state = {
    'countdown': 25,
    'is_spinning': False,
    'last_result': {'number': 0, 'color': 'green'},
    'spin_history': [],
    'round_id': int(time.time())
}

# База данных
def init_application():
    """Инициализация приложения"""
    print("🎰 Initializing Live Casino...")
    
    # Инициализация БД
    if not ensure_database():
        print("❌ Database initialization failed")
        return False
    
    print("✅ Database initialized")
    
    # Инициализация игрового состояния
    global game_state
    game_state = {
        'round': 0,
        'phase': 'betting',
        'time_left': 30,
        'bets': {},
        'last_result': None,
        'spinning_result': None,
        'start_time': time.time()
    }
    
    # Запуск игрового движка
    try:
        game_thread = threading.Thread(target=online_game_engine, daemon=True)
        game_thread.start()
        print("✅ Game engine started")
        
        # Даем время движку запуститься
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Failed to start game engine: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def get_user(telegram_id):
    """Получение пользователя с отладкой"""
    print(f"🔍 get_user called with telegram_id: {telegram_id}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        
        print(f"🔍 get_user result: {user}")
        conn.close()
        return user
        
    except Exception as e:
        print(f"❌ Error in get_user: {e}")
        if 'conn' in locals():
            conn.close()
        return None
        
def create_user(telegram_id, username, display_name):
    """Создание нового пользователя с отладкой"""
    print(f"🔄 create_user called with: {telegram_id}, {username}, {display_name}")
    
    try:
        print(f"🔍 Connecting to database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔍 Executing INSERT query...")
        cursor.execute('''
            INSERT INTO users 
            (telegram_id, username, display_name, balance, is_registered) 
            VALUES (?, ?, ?, 1000, 1)
        ''', (telegram_id, username or '', display_name))
        
        conn.commit()
        user_id = cursor.lastrowid
        print(f"🔍 Insert successful, lastrowid: {user_id}")
        
        # Проверяем что пользователь действительно создался
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        created_user = cursor.fetchone()
        print(f"🔍 Verification query result: {created_user}")
        
        conn.close()
        print(f"✅ User created successfully with ID: {user_id}")
        return user_id
        
    except sqlite3.IntegrityError as e:
        print(f"❌ IntegrityError (user already exists): {e}")
        if 'conn' in locals():
            conn.close()
        return None
        
    except Exception as e:
        print(f"❌ Error in create_user: {e}")
        import traceback
        print("Full traceback:")
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.close()
        return None

def update_balance(telegram_id, new_balance):
    """Обновление баланса пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, telegram_id))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        print(f"Error updating balance: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def ensure_database():
    """Обновленная схема БД с миграцией"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование таблицы users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            # Проверяем структуру таблицы
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Если нет колонки password_hash, делаем миграцию
            if 'password_hash' not in columns:
                print("🔄 Migrating database structure...")
                
                # Создаем новую таблицу с правильной структурой
                cursor.execute('''
                    CREATE TABLE users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        balance INTEGER DEFAULT 1000,
                        last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Если есть старые данные, пытаемся их перенести
                if 'password' in columns:
                    cursor.execute('''
                        INSERT INTO users_new (id, username, password_hash, display_name, balance, created_at)
                        SELECT id, username, password, display_name, balance, created_at
                        FROM users
                    ''')
                
                # Удаляем старую таблицу и переименовываем новую
                cursor.execute('DROP TABLE users')
                cursor.execute('ALTER TABLE users_new RENAME TO users')
                
                print("✅ Database migration completed")
        else:
            # Создаем таблицу с нуля
            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    balance INTEGER DEFAULT 1000,
                    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_token TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица ставок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                round_id INTEGER,
                bet_type TEXT,
                bet_amount INTEGER,
                result TEXT,
                win_amount INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица истории игр
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER UNIQUE,
                result_number INTEGER,
                result_color TEXT,
                total_bets INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Database updated at: {DB_PATH}")
        return True
        
    except Exception as e:
        print(f"❌ Database update error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

# 6. ФУНКЦИИ АВТОРИЗАЦИИ (ПЕРЕМЕСТИТЕ СЮДА ВАШ КОД)
def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_session_token():
    """Генерация токена сессии"""
    return secrets.token_urlsafe(32)

def create_user_account(username, password, display_name):
    """Создание аккаунта пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем уникальность username
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return None, "Username already exists"
        
        # Создаем пользователя
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO users (username, password_hash, display_name, balance)
            VALUES (?, ?, ?, 1000)
        ''', (username, password_hash, display_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id, "User created successfully"
        
    except Exception as e:
        print(f"Error creating user: {e}")
        if 'conn' in locals():
            conn.close()
        return None, str(e)

def authenticate_user(username, password):
    """Аутентификация пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        cursor.execute('''
            SELECT id, username, display_name, balance 
            FROM users 
            WHERE username = ? AND password_hash = ?
        ''', (username, password_hash))
        
        user = cursor.fetchone()
        
        if user:
            # Обновляем время последнего входа
            cursor.execute('''
                UPDATE users SET last_login = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (user[0],))
            conn.commit()
        
        conn.close()
        return user
        
    except Exception as e:
        print(f"Authentication error: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def create_session(user_id):
    """Создание сессии пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Деактивируем старые сессии
        cursor.execute('UPDATE user_sessions SET is_active = 0 WHERE user_id = ?', (user_id,))
        
        # Создаем новую сессию
        session_token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)  # Сессия на 7 дней
        
        cursor.execute('''
            INSERT INTO user_sessions (user_id, session_token, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, session_token, expires_at))
        
        conn.commit()
        conn.close()
        
        return session_token
        
    except Exception as e:
        print(f"Session creation error: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def validate_session(session_token):
    """Проверка действительности сессии"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.display_name, u.balance
            FROM users u
            JOIN user_sessions s ON u.id = s.user_id
            WHERE s.session_token = ? AND s.is_active = 1 AND s.expires_at > CURRENT_TIMESTAMP
        ''', (session_token,))
        
        user = cursor.fetchone()
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"Session validation error: {e}")
        if 'conn' in locals():
            conn.close()
        return None

# 7. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
        
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def update_user_balance(user_id, new_balance):
    """Обновление баланса пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        print(f"Error updating balance: {e}")
        return False

def save_bet_history(user_id, round_id, bet_type, bet_amount, result, win_amount):
    """Сохранение ставки в историю"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_bets 
            (user_id, round_id, bet_type, bet_amount, result, win_amount) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, round_id, bet_type, bet_amount, result, win_amount))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error saving bet: {e}")
        return False

def save_game_result(round_id, result_number, result_color, total_bets):
    """Сохранение результата игры"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO game_history 
            (round_id, result_number, result_color, total_bets) 
            VALUES (?, ?, ?, ?)
        ''', (round_id, result_number, result_color, total_bets))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error saving game result: {e}")
        return False

# Добавьте эти функции в раздел "ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ"

def get_color_emoji(color):
    """Получение эмодзи для цвета"""
    color_emojis = {
        'red': '🔴',
        'black': '⚫',
        'green': '🟢'
    }
    return color_emojis.get(color, '⚪')

def get_color_name(color):
    """Получение названия цвета"""
    color_names = {
        'red': 'КРАСНОЕ',
        'black': 'ЧЕРНОЕ', 
        'green': 'ЗЕЛЕНОЕ'
    }
    return color_names.get(color, color.upper())

def get_number_color(number):
    """Определение цвета числа"""
    if number == 0:
        return 'green'
    elif number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
        return 'red'
    else:
        return 'black'

# 8. ИГРОВОЙ ДВИЖОК
def online_game_engine():
    """Непрерывный игровой движок с точным таймингом"""
    print("🎮 Live Casino Engine Started")
    
    # Инициализируем первый раунд
    game_state['round'] = 0
    game_state['phase'] = 'betting'
    game_state['time_left'] = 30
    game_state['bets'] = {}
    game_state['last_result'] = None
    game_state['spinning_result'] = None
    
    while True:
        try:
            # Новый раунд
            game_state['round'] += 1
            game_state['bets'] = {}
            game_state['spinning_result'] = None
            
            print(f"🎰 Round {game_state['round']} - Starting")
            
            # ФАЗА СТАВОК (30 секунд)
            game_state['phase'] = 'betting'
            betting_duration = 30
            
            print(f"🎰 Round {game_state['round']} - Betting Open")
            
            for remaining in range(betting_duration, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
            # ЗАКРЫТИЕ СТАВОК
            print(f"🚫 Round {game_state['round']} - Betting Closed")
            
            # ФАЗА ВРАЩЕНИЯ (8 секунд)
            game_state['phase'] = 'spinning'
            spinning_duration = 8
            
            # Генерируем результат заранее
            result_number = random.randint(0, 36)
            if result_number == 0:
                result_color = 'green'
            elif result_number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
                result_color = 'red'
            else:
                result_color = 'black'
            
            # Устанавливаем результат для анимации
            game_state['spinning_result'] = {
                'number': result_number,
                'color': result_color
            }
            
            print(f"🌀 Round {game_state['round']} - Spinning... Target: {result_number} ({result_color})")
            
            for remaining in range(spinning_duration, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
            # ПОКАЗ РЕЗУЛЬТАТА (5 секунд)
            game_state['phase'] = 'result'
            game_state['last_result'] = {
                'number': result_number,
                'color': result_color,
                'round': game_state['round']
            }
            
            print(f"🎯 Round {game_state['round']} - Result: {result_number} ({result_color})")
            
            # Обрабатываем ставки
            process_round_bets(result_number, result_color)
            
            # Показываем результат
            for remaining in range(5, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
        except Exception as e:
            print(f"❌ Game engine error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(2)

def process_round_bets(result_number, result_color):
    """Обработка всех ставок раунда"""
    try:
        total_bets_amount = 0
        total_wins_amount = 0
        
        for user_id, user_bets in game_state['bets'].items():
            # Получаем актуальный баланс пользователя
            user = get_user_by_id(int(user_id))
            if not user:
                continue
            
            current_balance = user[4]  # balance column
            
            for bet in user_bets:
                bet_type = bet['bet_type']
                bet_amount = bet['bet_amount']
                win_amount = 0
                result = 'lose'
                
                # Определяем выигрыш
                if bet_type == result_color:
                    # Ставка на цвет
                    if result_color == 'green':
                        win_amount = bet_amount * 14  # x14 за зеленый
                    else:
                        win_amount = bet_amount * 2   # x2 за красный/черный
                    result = 'win'
                    
                elif bet_type.isdigit() and int(bet_type) == result_number:
                    # Ставка на конкретное число
                    win_amount = bet_amount * 36  # x36 за число
                    result = 'win'
                
                # Начисляем выигрыш
                if win_amount > 0:
                    new_balance = current_balance + win_amount
                    update_user_balance(int(user_id), new_balance)
                    current_balance = new_balance
                    total_wins_amount += win_amount
                    print(f"💰 User {user_id} won {win_amount} (bet: {bet_amount} on {bet_type})")
                
                # Сохраняем ставку в БД
                save_bet_history(user[0], game_state['round'], bet_type, bet_amount, result, win_amount)
                total_bets_amount += bet_amount
        
        # Сохраняем результат раунда
        save_game_result(game_state['round'], result_number, result_color, total_bets_amount)
        
        print(f"📊 Round {game_state['round']} processed: {total_bets_amount} bet, {total_wins_amount} paid out")
        
    except Exception as e:
        print(f"❌ Error processing bets: {e}")

@app.route('/')
def index():
    """Главная страница казино"""
    return '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Casino Roulette</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            overflow-x: hidden;
        }

        /* Экран авторизации */
        .auth-screen {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }

        .auth-container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .auth-title {
            font-size: 2.5em;
            margin-bottom: 30px;
            background: linear-gradient(45deg, #ffd700, #ffed4e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .auth-tabs {
            display: flex;
            margin-bottom: 30px;
            border-radius: 10px;
            overflow: hidden;
            background: rgba(0, 0, 0, 0.3);
        }

        .auth-tab {
            flex: 1;
            padding: 15px;
            background: transparent;
            border: none;
            color: white;
            cursor: pointer;
            transition: all 0.3s;
        }

        .auth-tab.active {
            background: linear-gradient(45deg, #d4af37, #ffd700);
            color: black;
        }

        .auth-form {
            display: none;
        }

        .auth-form.active {
            display: block;
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: #ffd700;
        }

        .form-input {
            width: 100%;
            padding: 15px;
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 10px;
            background: rgba(0, 0, 0, 0.3);
            color: white;
            font-size: 16px;
            transition: all 0.3s;
        }

        .form-input:focus {
            outline: none;
            border-color: #ffd700;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }

        .auth-button {
            width: 100%;
            background: linear-gradient(45deg, #d4af37, #ffd700);
            color: black;
            border: none;
            padding: 15px;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }

        .auth-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 215, 0, 0.3);
        }

        /* Игровой экран */
        .game-screen {
            display: none;
            min-height: 100vh;
            padding: 20px;
        }

        .game-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .balance {
            background: linear-gradient(45deg, #d4af37, #ffd700);
            color: black;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 18px;
        }

        .logout-btn {
            background: rgba(255, 0, 0, 0.2);
            color: white;
            border: 1px solid rgba(255, 0, 0, 0.5);
            padding: 10px 20px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }

        .logout-btn:hover {
            background: rgba(255, 0, 0, 0.3);
        }

        /* Рулетка */
        .roulette-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 40px;
        }

        .roulette-wheel {
            position: relative;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: linear-gradient(45deg, #8b4513, #a0522d);
            border: 10px solid #d4af37;
            margin-bottom: 20px;
            overflow: hidden;
        }

        .wheel-inner {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 360px;
            height: 360px;
            border-radius: 50%;
            background: #000;
            transition: transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99);
        }

        .wheel-number {
            position: absolute;
            width: 30px;
            height: 15px;
            color: white;
            font-size: 12px;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            transform-origin: 15px 180px;
        }

        .wheel-number.red {
            background: #ff0000;
        }

        .wheel-number.black {
            background: #000000;
        }

        .wheel-number.green {
            background: #008000;
        }

        .wheel-pointer {
            position: absolute;
            top: -5px;
            left: 50%;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 15px solid transparent;
            border-right: 15px solid transparent;
            border-top: 30px solid #ffd700;
            z-index: 10;
        }

        .game-timer {
            font-size: 3em;
            font-weight: bold;
            color: #ffd700;
            text-align: center;
            margin: 20px 0;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }

        .game-phase {
            font-size: 1.5em;
            text-align: center;
            margin-bottom: 20px;
            color: #ffd700;
        }

        /* Зона ставок */
        .betting-area {
            max-width: 600px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.3);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }

        .betting-title {
            text-align: center;
            font-size: 1.8em;
            margin-bottom: 30px;
            color: #ffd700;
        }

        /* Поле ввода ставки */
        .bet-input-section {
            margin-bottom: 30px;
            text-align: center;
        }

        .bet-input-label {
            display: block;
            font-size: 1.2em;
            margin-bottom: 10px;
            color: #ffd700;
        }

        .bet-amount-input {
            width: 200px;
            padding: 15px;
            border: 2px solid #ffd700;
            border-radius: 10px;
            background: rgba(0, 0, 0, 0.5);
            color: white;
            font-size: 18px;
            text-align: center;
            transition: all 0.3s;
        }

        .bet-amount-input:focus {
            outline: none;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
            border-color: #ffed4e;
        }

        /* Выбор цвета */
        .color-selection {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .color-option {
            background: rgba(255, 255, 255, 0.1);
            border: 3px solid transparent;
            border-radius: 15px;
            padding: 30px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
            font-size: 18px;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }

        .color-option:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 25px rgba(0, 0, 0, 0.3);
        }

        .color-option.red {
            background: linear-gradient(135deg, #ff4757, #ff3742);
            color: white;
        }

        .color-option.black {
            background: linear-gradient(135deg, #2f3542, #40424a);
            color: white;
        }

        .color-option.green {
            background: linear-gradient(135deg, #26de81, #20bf6b);
            color: white;
        }

        .color-option.selected {
            border-color: #ffd700;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
            transform: scale(1.05);
        }

        .color-emoji {
            font-size: 2em;
            margin-bottom: 10px;
        }

        .color-multiplier {
            font-size: 1.2em;
            opacity: 0.8;
        }

        /* Кнопка ставки */
        .bet-button {
            width: 100%;
            background: linear-gradient(45deg, #d4af37, #ffd700);
            color: black;
            border: none;
            padding: 20px;
            border-radius: 15px;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
        }

        .bet-button:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 15px 25px rgba(255, 215, 0, 0.4);
        }

        .bet-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: rgba(255, 255, 255, 0.2);
            color: rgba(255, 255, 255, 0.5);
        }

        /* Результаты */
        .results-section {
            max-width: 600px;
            margin: 40px auto 0;
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }

        .results-title {
            text-align: center;
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #ffd700;
        }

        .recent-results {
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .result-number {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            font-size: 18px;
        }

        .result-number.red {
            background: #ff0000;
        }

        .result-number.black {
            background: #000000;
        }

        .result-number.green {
            background: #008000;
        }

        /* Адаптивность */
        @media (max-width: 768px) {
            .roulette-wheel {
                width: 300px;
                height: 300px;
            }

            .wheel-inner {
                width: 260px;
                height: 260px;
            }

            .color-selection {
                grid-template-columns: 1fr;
                gap: 15px;
            }

            .bet-amount-input {
                width: 150px;
            }
        }

        /* Анимации */
        @keyframes spin {
            from {
                transform: translate(-50%, -50%) rotate(0deg);
            }
            to {
                transform: translate(-50%, -50%) rotate(1800deg);
            }
        }

        .spinning {
            animation: spin 4s cubic-bezier(0.17, 0.67, 0.12, 0.99) forwards;
        }

        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            border-left: 4px solid #ffd700;
            z-index: 1000;
            backdrop-filter: blur(10px);
            max-width: 300px;
        }

        .notification.success {
            border-left-color: #26de81;
        }

        .notification.error {
            border-left-color: #ff4757;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        .pulse {
            animation: pulse 1s infinite;
        }
    </style>
</head>
<body>
    <!-- Экран авторизации -->
    <div id="authScreen" class="auth-screen">
        <div class="auth-container">
            <h1 class="auth-title">🎰 Live Casino</h1>
            
            <div class="auth-tabs">
                <button class="auth-tab active" onclick="switchTab('login')">Вход</button>
                <button class="auth-tab" onclick="switchTab('register')">Регистрация</button>
            </div>

            <!-- Форма входа -->
            <form id="loginForm" class="auth-form active">
                <div class="form-group">
                    <label class="form-label">Логин</label>
                    <input type="text" class="form-input" id="loginUsername" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" class="form-input" id="loginPassword" required>
                </div>
                <button type="submit" class="auth-button">Войти</button>
            </form>

            <!-- Форма регистрации -->
            <form id="registerForm" class="auth-form">
                <div class="form-group">
                    <label class="form-label">Логин</label>
                    <input type="text" class="form-input" id="registerUsername" required minlength="3">
                </div>
                <div class="form-group">
                    <label class="form-label">Пароль</label>
                    <input type="password" class="form-input" id="registerPassword" required minlength="4">
                </div>
                <div class="form-group">
                    <label class="form-label">Имя для отображения</label>
                    <input type="text" class="form-input" id="registerDisplayName" required>
                </div>
                <button type="submit" class="auth-button">Зарегистрироваться</button>
            </form>
        </div>
    </div>

    <!-- Игровой экран -->
    <div id="gameScreen" class="game-screen">
        <!-- Заголовок -->
        <div class="game-header">
            <div class="user-info">
                <span id="userName">Добро пожаловать!</span>
                <div class="balance">💰 <span id="userBalance">1000</span></div>
            </div>
            <button class="logout-btn" onclick="logout()">Выйти</button>
        </div>

        <!-- Рулетка -->
        <div class="roulette-container">
            <div class="roulette-wheel">
                <div class="wheel-pointer"></div>
                <div id="wheelInner" class="wheel-inner"></div>
            </div>
            
            <div class="game-timer" id="gameTimer">30</div>
            <div class="game-phase" id="gamePhase">Делайте ваши ставки!</div>
        </div>

        <!-- Зона ставок -->
        <div class="betting-area">
            <h2 class="betting-title">🎯 Сделайте ставку</h2>
            
            <!-- Поле ввода суммы ставки -->
            <div class="bet-input-section">
                <label class="bet-input-label">Размер ставки:</label>
                <input type="number" class="bet-amount-input" id="betAmountInput" 
                       min="1" max="10000" value="10" 
                       placeholder="Введите сумму">
            </div>

            <!-- Выбор цвета -->
            <div class="color-selection">
                <div class="color-option red" data-color="red">
                    <div class="color-emoji">🔴</div>
                    <div>КРАСНОЕ</div>
                    <div class="color-multiplier">x2</div>
                </div>
                <div class="color-option black" data-color="black">
                    <div class="color-emoji">⚫</div>
                    <div>ЧЕРНОЕ</div>
                    <div class="color-multiplier">x2</div>
                </div>
                <div class="color-option green" data-color="green">
                    <div class="color-emoji">🟢</div>
                    <div>ЗЕЛЕНОЕ</div>
                    <div class="color-multiplier">x14</div>
                </div>
            </div>

            <button class="bet-button" id="betButton" onclick="placeBet()" disabled>
                Выберите цвет
            </button>
        </div>

        <!-- Последние результаты -->
        <div class="results-section">
            <h3 class="results-title">📊 Последние результаты</h3>
            <div class="recent-results" id="recentResults">
                <!-- Генерируется JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // Глобальные переменные
        let currentUser = null;
        let sessionToken = null;
        let selectedColor = null;
        let gameState = {};
        let gameUpdateInterval = null;
        let recentResults = [];

        // Числа рулетки по порядку
        const rouletteNumbers = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];

        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            checkExistingSession();
            setupEventListeners();
            generateRouletteWheel();
        });

        // Проверка существующей сессии
        function checkExistingSession() {
            const savedToken = localStorage.getItem('sessionToken');
            if (savedToken) {
                validateSession(savedToken);
            }
        }

        // Валидация сессии
        function validateSession(token) {
            fetch('/api/validate_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_token: token })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    sessionToken = token;
                    currentUser = data.user;
                    showGameScreen();
                    startGameUpdates();
                } else {
                    localStorage.removeItem('sessionToken');
                    showAuthScreen();
                }
            })
            .catch(error => {
                console.error('Session validation error:', error);
                showAuthScreen();
            });
        }

        // Переключение вкладок авторизации
        function switchTab(tabName) {
            // Переключаем кнопки
            document.querySelectorAll('.auth-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            event.target.classList.add('active');

            // Переключаем формы
            document.querySelectorAll('.auth-form').forEach(form => {
                form.classList.remove('active');
            });
            document.getElementById(tabName + 'Form').classList.add('active');
        }

        // Настройка обработчиков событий
        function setupEventListeners() {
            // Форма входа
            document.getElementById('loginForm').addEventListener('submit', function(e) {
                e.preventDefault();
                login();
            });

            // Форма регистрации
            document.getElementById('registerForm').addEventListener('submit', function(e) {
                e.preventDefault();
                register();
            });

            // Выбор цвета
            document.querySelectorAll('.color-option').forEach(option => {
                option.addEventListener('click', function() {
                    selectColor(this.dataset.color);
                });
            });

            // Поле ввода ставки
            document.getElementById('betAmountInput').addEventListener('input', function() {
                updateBetButton();
            });
        }

        // Вход
        function login() {
            const username = document.getElementById('loginUsername').value.trim();
            const password = document.getElementById('loginPassword').value;

            if (!username || !password) {
                showNotification('Заполните все поля', 'error');
                return;
            }

            fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    sessionToken = data.session_token;
                    currentUser = data.user;
                    localStorage.setItem('sessionToken', sessionToken);
                    showGameScreen();
                    startGameUpdates();
                    showNotification('Добро пожаловать!', 'success');
                } else {
                    showNotification(data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Login error:', error);
                showNotification('Ошибка входа', 'error');
            });
        }

        // Регистрация
        function register() {
            const username = document.getElementById('registerUsername').value.trim();
            const password = document.getElementById('registerPassword').value;
            const displayName = document.getElementById('registerDisplayName').value.trim();

            if (!username || !password || !displayName) {
                showNotification('Заполните все поля', 'error');
                return;
            }

            if (username.length < 3) {
                showNotification('Логин должен быть не менее 3 символов', 'error');
                return;
            }

            if (password.length < 4) {
                showNotification('Пароль должен быть не менее 4 символов', 'error');
                return;
            }

            fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password,
                    display_name: displayName
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    sessionToken = data.session_token;
                    currentUser = data.user;
                    localStorage.setItem('sessionToken', sessionToken);
                    showGameScreen();
                    startGameUpdates();
                    showNotification('Регистрация успешна!', 'success');
                } else {
                    showNotification(data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Registration error:', error);
                showNotification('Ошибка регистрации', 'error');
            });
        }

        // Выход
        function logout() {
            sessionToken = null;
            currentUser = null;
            localStorage.removeItem('sessionToken');
            stopGameUpdates();
            showAuthScreen();
            showNotification('Вы вышли из системы', 'success');
        }

        // Показать экран авторизации
        function showAuthScreen() {
            document.getElementById('authScreen').style.display = 'flex';
            document.getElementById('gameScreen').style.display = 'none';
        }

        // Показать игровой экран
        function showGameScreen() {
            document.getElementById('authScreen').style.display = 'none';
            document.getElementById('gameScreen').style.display = 'block';
            updateUserInfo();
        }

        // Обновить информацию о пользователе
        function updateUserInfo() {
            if (currentUser) {
                document.getElementById('userName').textContent = currentUser.display_name;
                document.getElementById('userBalance').textContent = currentUser.balance;
            }
        }

        // Генерация колеса рулетки
        function generateRouletteWheel() {
            const wheelInner = document.getElementById('wheelInner');
            const numberColors = {
                0: 'green',
                1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black',
                7: 'red', 8: 'black', 9: 'red', 10: 'black', 11: 'black', 12: 'red',
                13: 'black', 14: 'red', 15: 'black', 16: 'red', 17: 'black', 18: 'red',
                19: 'red', 20: 'black', 21: 'red', 22: 'black', 23: 'red', 24: 'black',
                25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red',
                31: 'black', 32: 'red', 33: 'black', 34: 'red', 35: 'black', 36: 'red'
            };

            rouletteNumbers.forEach((number, index) => {
                const angle = (360 / rouletteNumbers.length) * index;
                const numberDiv = document.createElement('div');
                numberDiv.className = `wheel-number ${numberColors[number]}`;
                numberDiv.textContent = number;
                numberDiv.style.transform = `rotate(${angle}deg)`;
                numberDiv.style.left = '165px';
                numberDiv.style.top = '10px';
                wheelInner.appendChild(numberDiv);
            });
        }

        // Выбор цвета
        function selectColor(color) {
            // Убираем выделение со всех цветов
            document.querySelectorAll('.color-option').forEach(option => {
                option.classList.remove('selected');
            });

            // Выделяем выбранный цвет
            const selectedElement = document.querySelector(`[data-color="${color}"]`);
            if (selectedElement) {
                selectedElement.classList.add('selected');
            }

            selectedColor = color;
            updateBetButton();
        }

        // Обновление кнопки ставки
        function updateBetButton() {
            const betBtn = document.getElementById('betButton');
            const betAmount = parseInt(document.getElementById('betAmountInput').value) || 0;
            
            if (selectedColor && betAmount > 0 && gameState.phase === 'betting') {
                if (currentUser && betAmount <= currentUser.balance) {
                    betBtn.disabled = false;
                    betBtn.textContent = `BET ${betAmount} на ${getColorName(selectedColor)}`;
                    betBtn.classList.remove('pulse');
                } else {
                    betBtn.disabled = true;
                    betBtn.textContent = 'Недостаточно средств';
                }
            } else {
                betBtn.disabled = true;
                if (gameState.phase !== 'betting') {
                    betBtn.textContent = 'Ставки закрыты';
                } else if (!selectedColor) {
                    betBtn.textContent = 'Выберите цвет';
                } else if (betAmount <= 0) {
                    betBtn.textContent = 'Введите сумму ставки';
                } else {
                    betBtn.textContent = 'Сделайте ставку';
                }
            }
        }

        // Получить название цвета
        function getColorName(color) {
            switch(color) {
                case 'red': return 'КРАСНОЕ';
                case 'black': return 'ЧЕРНОЕ';
                case 'green': return 'ЗЕЛЕНОЕ';
                default: return color;
            }
        }

        // Размещение ставки
        function placeBet() {
            const betAmount = parseInt(document.getElementById('betAmountInput').value);
            
            if (!selectedColor || !betAmount || !sessionToken) {
                showNotification('Выберите цвет и введите сумму ставки', 'error');
                return;
            }

            if (gameState.phase !== 'betting') {
                showNotification('Ставки закрыты', 'error');
                return;
            }

            if (betAmount <= 0) {
                showNotification('Сумма ставки должна быть больше 0', 'error');
                return;
            }

            if (currentUser.balance < betAmount) {
                showNotification('Недостаточно средств', 'error');
                return;
            }

            fetch('/api/place_bet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_token: sessionToken,
                    bet_type: selectedColor,
                    bet_amount: betAmount
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentUser.balance = data.new_balance;
                    updateUserInfo();
                    showNotification(`Ставка размещена: ${betAmount} на ${getColorName(selectedColor)}`, 'success');
                    
                    // Сбрасываем выбор
                    selectedColor = null;
                    document.querySelectorAll('.color-option').forEach(option => {
                        option.classList.remove('selected');
                    });
                    updateBetButton();
                } else {
                    showNotification(data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Bet placement error:', error);
                showNotification('Ошибка размещения ставки', 'error');
            });
        }

        // Запуск обновлений игры
        function startGameUpdates() {
            if (gameUpdateInterval) {
                clearInterval(gameUpdateInterval);
            }
            
            updateGameState();
            gameUpdateInterval = setInterval(updateGameState, 1000);
        }

        // Остановка обновлений игры
        function stopGameUpdates() {
            if (gameUpdateInterval) {
                clearInterval(gameUpdateInterval);
                gameUpdateInterval = null;
            }
        }

        // Обновление состояния игры
        function updateGameState() {
            fetch('/api/game_state')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const newGameState = data.game_state;
                        
                        // Проверяем изменение фазы
                        if (gameState.phase !== newGameState.phase) {
                            handlePhaseChange(gameState.phase, newGameState.phase);
                        }
                        
                        // Обновляем состояние
                        gameState = newGameState;
                        
                        // Обновляем UI
                        updateGameUI();
                        
                        // Обновляем результаты
                        if (gameState.last_result) {
                            updateRecentResults(gameState.last_result);
                        }
                    }
                })
                .catch(error => {
                    console.error('Game state update error:', error);
                });
        }

        // Обработка смены фазы игры
        function handlePhaseChange(oldPhase, newPhase) {
            const wheelInner = document.getElementById('wheelInner');
            
            if (newPhase === 'spinning' && gameState.spinning_result) {
                // Запускаем анимацию вращения
                const targetNumber = gameState.spinning_result.number;
                const targetIndex = rouletteNumbers.indexOf(targetNumber);
                const baseRotation = 1800; // 5 полных оборотов
                const sectorAngle = 360 / rouletteNumbers.length;
                const targetAngle = baseRotation + (sectorAngle * targetIndex);
                
                wheelInner.style.transform = `translate(-50%, -50%) rotate(${targetAngle}deg)`;
                wheelInner.style.transition = 'transform 4s cubic-bezier(0.17, 0.67, 0.12, 0.99)';
                
                // Показать результат через 4 секунды
                setTimeout(() => {
                    showSpinResult(gameState.spinning_result);
                }, 4000);
                
            } else if (newPhase === 'betting') {
                // Сброс колеса для нового раунда
                wheelInner.style.transform = 'translate(-50%, -50%) rotate(0deg)';
                wheelInner.style.transition = 'none';
                
                // Обновляем баланс пользователя
                refreshUserBalance();
            }
        }

        // Показать результат вращения
        function showSpinResult(result) {
            const resultText = `Выпало: ${result.number} (${getColorName(result.color)})`;
            showNotification(resultText, 'success');
        }

        // Обновление UI игры
        function updateGameUI() {
            // Обновляем таймер
            document.getElementById('gameTimer').textContent = gameState.time_left || 0;
            
            // Обновляем фазу
            const phaseText = {
                'betting': 'Делайте ваши ставки!',
                'spinning': 'Вращение...',
                'result': 'Результат раунда'
            };
            document.getElementById('gamePhase').textContent = phaseText[gameState.phase] || 'Ожидание...';
            
            // Обновляем кнопку ставки
            updateBetButton();
            
            // Цветовая индикация таймера
            const timer = document.getElementById('gameTimer');
            if (gameState.phase === 'betting') {
                if (gameState.time_left <= 5) {
                    timer.style.color = '#ff4757';
                    timer.classList.add('pulse');
                } else {
                    timer.style.color = '#ffd700';
                    timer.classList.remove('pulse');
                }
            } else {
                timer.style.color = '#ffd700';
                timer.classList.remove('pulse');
            }
        }

        // Обновление последних результатов
        function updateRecentResults(newResult) {
            // Добавляем новый результат в начало массива
            if (!recentResults.find(r => r.round === newResult.round)) {
                recentResults.unshift(newResult);
                
                // Ограничиваем количество результатов
                if (recentResults.length > 10) {
                    recentResults = recentResults.slice(0, 10);
                }
                
                // Обновляем отображение
                displayRecentResults();
            }
        }

        // Отображение последних результатов
        function displayRecentResults() {
            const resultsContainer = document.getElementById('recentResults');
            resultsContainer.innerHTML = '';
            
            recentResults.forEach(result => {
                const resultDiv = document.createElement('div');
                resultDiv.className = `result-number ${result.color}`;
                resultDiv.textContent = result.number;
                resultDiv.title = `Раунд ${result.round}: ${result.number} (${getColorName(result.color)})`;
                resultsContainer.appendChild(resultDiv);
            });
        }

        // Обновление баланса пользователя
        function refreshUserBalance() {
            if (!sessionToken) return;
            
            fetch('/api/validate_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_token: sessionToken })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentUser = data.user;
                    updateUserInfo();
                }
            })
            .catch(error => {
                console.error('Balance refresh error:', error);
            });
        }

        // Показать уведомление
        function showNotification(message, type = 'info') {
            // Удаляем предыдущие уведомления
            const existingNotifications = document.querySelectorAll('.notification');
            existingNotifications.forEach(notification => {
                notification.remove();
            });
            
            // Создаем новое уведомление
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            // Автоматически удаляем через 4 секунды
            setTimeout(() => {
                notification.remove();
            }, 4000);
        }
    </script>
</body>
</html>'''
         
# API endpoints
@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'online',
        'version': APP_VERSION,
        'players_online': len(online_players),
        'game_state': game_state,
        'current_bets_count': len(current_bets),
        'uptime': time.time() - game_state.get('start_time', time.time()),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/check_registration', methods=['GET'])
def api_check_registration():
    """Проверка статуса регистрации пользователя"""
    ensure_database()
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'message': 'User ID required'
            }), 400
        
        user = get_user(int(user_id))
        
        if user and user[5]:  # is_registered = 1
            return jsonify({
                'success': True,
                'is_registered': True,
                'display_name': user[3],
                'balance': user[4],
                'username': user[2] or ''
            })
        else:
            return jsonify({
                'success': True,
                'is_registered': False,
                'balance': user[4] if user else 1000
            })
            
    except Exception as e:
        print(f"Error in check_registration: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error'
        }), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    """Регистрация нового пользователя"""
    ensure_database()
    
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip()
        
        if not all([username, password, display_name]):
            return jsonify({
                'success': False,
                'message': 'All fields are required'
            }), 400
        
        if len(username) < 3:
            return jsonify({
                'success': False,
                'message': 'Username must be at least 3 characters'
            }), 400
        
        if len(password) < 4:
            return jsonify({
                'success': False,
                'message': 'Password must be at least 4 characters'
            }), 400
        
        user_id, message = create_user_account(username, password, display_name)
        
        if user_id:
            # Создаем сессию
            session_token = create_session(user_id)
            
            return jsonify({
                'success': True,
                'message': message,
                'session_token': session_token,
                'user': {
                    'id': user_id,
                    'username': username,
                    'display_name': display_name,
                    'balance': 1000
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'message': 'Registration failed'
        }), 500



@app.route('/api/login', methods=['POST'])
def api_login():
    """Вход пользователя"""
    ensure_database()
    
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not all([username, password]):
            return jsonify({
                'success': False,
                'message': 'Username and password are required'
            }), 400
        
        user = authenticate_user(username, password)
        
        if user:
            # Создаем сессию
            session_token = create_session(user[0])
            
            return jsonify({
                'success': True,
                'session_token': session_token,
                'user': {
                    'id': user[0],
                    'username': user[1],
                    'display_name': user[2],
                    'balance': user[3]
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Login failed'
        }), 500

@app.route('/api/validate_session', methods=['POST'])
def api_validate_session():
    """Проверка сессии"""
    try:
        data = request.get_json()
        session_token = data.get('session_token')
        
        if not session_token:
            return jsonify({
                'success': False,
                'message': 'Session token required'
            }), 400
        
        user = validate_session(session_token)
        
        if user:
            return jsonify({
                'success': True,
                'user': {
                    'id': user[0],
                    'username': user[1],
                    'display_name': user[2],
                    'balance': user[3]
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid session'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
@app.route('/api/place_bet', methods=['POST'])
def api_place_bet():
    """Размещение ставки"""
    try:
        data = request.get_json()
        session_token = data.get('session_token')
        bet_type = data.get('bet_type')
        bet_amount = data.get('bet_amount')
        
        if not all([session_token, bet_type, bet_amount]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
        # Проверяем сессию
        user = validate_session(session_token)
        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid session'
            }), 401
        
        user_id = user[0]
        current_balance = user[3]
        
        # Проверяем баланс
        if current_balance < bet_amount:
            return jsonify({
                'success': False,
                'message': 'Insufficient balance'
            }), 400
        
        # Проверяем фазу игры
        if game_state['phase'] != 'betting':
            return jsonify({
                'success': False,
                'message': 'Betting is closed'
            }), 400
        
        # Списываем ставку с баланса
        new_balance = current_balance - bet_amount
        if update_user_balance(user_id, new_balance):
            # Сохраняем ставку
            if str(user_id) not in game_state['bets']:
                game_state['bets'][str(user_id)] = []
            
            game_state['bets'][str(user_id)].append({
                'bet_type': bet_type,
                'bet_amount': bet_amount
            })
            
            return jsonify({
                'success': True,
                'message': 'Bet placed successfully',
                'new_balance': new_balance
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update balance'
            }), 500
            
    except Exception as e:
        print(f"Place bet error: {e}")
        return jsonify({
            'success': False,
            'message': 'Bet placement failed'
        }), 500

@app.route('/api/game_state')
def api_game_state():
    """Получение текущего состояния игры"""
    try:
        return jsonify({
            'success': True,
            'game_state': {
                'round': game_state['round'],
                'phase': game_state['phase'],
                'time_left': game_state['time_left'],
                'last_result': game_state.get('last_result'),
                'spinning_result': game_state.get('spinning_result')
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/players')
def api_players():
    return jsonify({
        'players': online_players,
        'count': len(online_players)
    })

@app.route('/api/history')
def api_history():
    try:
        conn = sqlite3.connect('casino_online.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT round_id, result_number, result_color, total_bets, created_at
            FROM game_history 
            ORDER BY created_at DESC 
            LIMIT 50
        ''')
        history = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'history': [
                {
                    'round_id': row[0],
                    'number': row[1],
                    'color': row[2],
                    'total_bets': row[3],
                    'timestamp': row[4]
                } for row in history
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test')
def api_test():
    """Тестирование API"""
    return jsonify({
        'status': 'OK',
        'endpoints': [
            '/api/status',
            '/api/check_registration',
            '/api/register',
            '/api/place_bet',
            '/api/game_state',
            '/api/players',
            '/api/history'
        ],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/disk_check')
def api_disk_check():
    """Проверка прав доступа к диску"""
    try:
        import stat
        
        info = {
            'data_dir_exists': os.path.exists('/data'),
            'db_path': DB_PATH,
            'db_exists': os.path.exists(DB_PATH)
        }
        
        if os.path.exists('/data'):
            stat_info = os.stat('/data')
            info['data_dir_permissions'] = oct(stat_info.st_mode)[-3:]
        
        if os.path.exists(DB_PATH):
            stat_info = os.stat(DB_PATH)
            info['db_permissions'] = oct(stat_info.st_mode)[-3:]
            info['db_size'] = os.path.getsize(DB_PATH)
        
        # Попробуем создать тестовый файл
        try:
            test_file = '/data/test_write.txt'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            info['write_access'] = True
        except:
            info['write_access'] = False
        
        return jsonify(info)
        
    except Exception as e:
        return jsonify({'error': str(e)})
        
# Telegram Bot функции
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("🎰 Play Online Casino", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""
🎰 <b>Welcome to Online European Roulette!</b>

💰 Your balance: <b>{user[4]} ⭐</b>
👤 Status: {'Registered' if user[5] else 'Guest'}

🌐 <b>REAL-TIME MULTIPLAYER CASINO</b>
• Synchronized gameplay with all players
• Live betting and results
• Real-time player interactions
• Persistent balance and progress

🎲 <b>How to play:</b>
• Register with your display name
• Place bets from 10 to 20,000 stars
• Choose RED, BLACK, or GREEN
• Automatic synchronized spin every 25 seconds
• RED/BLACK: x2 payout
• GREEN (0): x36 payout

🚀 <b>Features:</b>
• Real-time multiplayer experience
• Live chat with other players
• Synchronized countdown timer
• Persistent user profiles
• Advanced betting statistics
• Mobile-optimized interface

Click below to join the online casino!
    """
    
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='HTML', 
        reply_markup=reply_markup
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    stats = get_user_stats(update.effective_user.id)
    
    balance_msg = f"""
💰 <b>Your Casino Account</b>

💳 Current Balance: <b>{user[4]} ⭐</b>
👤 Display Name: <b>{user[3] if user[5] else 'Not Set'}</b>
📊 Registration: {'✅ Complete' if user[5] else '❌ Incomplete'}

📈 <b>Statistics:</b>
🎮 Games Played: <b>{stats['total_games']}</b>
🏆 Games Won: <b>{stats['wins']}</b>
💎 Total Won: <b>{stats['total_won']} ⭐</b>
💸 Total Bet: <b>{stats['total_bet']} ⭐</b>
📊 Win Rate: <b>{(stats['wins'] / max(stats['total_games'], 1) * 100):.1f}%</b>

💡 <b>Tips:</b>
• Complete registration to save progress
• Start with small bets to learn
• Watch live bets from other players
• Green (0) has highest payout but lowest chance
    """
    
    keyboard = [[InlineKeyboardButton("🎰 Play Now", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(balance_msg, parse_mode='HTML', reply_markup=reply_markup)

async def online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    online_count = len(online_players)
    current_round_bets = len(current_bets)
    
    online_msg = f"""
🌐 <b>Online Casino Status</b>

👥 Players Online: <b>{online_count}</b>
🎰 Current Round: <b>#{game_state['round_id']}</b>
⏰ Next Spin: <b>{game_state['countdown']} seconds</b>
🎲 Status: {'🎯 Spinning' if game_state['is_spinning'] else '💰 Betting Open'}
📊 Active Bets: <b>{current_round_bets}</b>

🏆 <b>Last Result:</b>
{get_color_emoji(game_state['last_result']['color'])} <b>{game_state['last_result']['color'].upper()} {game_state['last_result']['number']}</b>

📈 <b>Recent Results:</b>
{' '.join([f"{get_color_emoji(r['color'])} {r['number']}" for r in game_state['spin_history'][-5:]])}

🔥 <b>Live Features:</b>
• Real-time synchronized gameplay
• Live player betting display  
• Instant balance updates
• Cross-platform compatibility
• Persistent game progress
    """
    
    keyboard = [[InlineKeyboardButton("🎮 Join Game", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(online_msg, parse_mode='HTML', reply_markup=reply_markup)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    user_stats = get_user_stats(update.effective_user.id)
    
    # Общая статистика казино
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_registered = 1')
    total_registered = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM game_history')
    total_games = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM user_bets')
    total_wagered = cursor.fetchone()[0] or 0
    
    conn.close()
    
    stats_msg = f"""
📊 <b>Casino Statistics</b>

👤 <b>Your Stats:</b>
💰 Balance: <b>{user[4]} ⭐</b>
🎮 Games: <b>{user_stats['total_games']}</b>
🏆 Wins: <b>{user_stats['wins']}</b>
💎 Won: <b>{user_stats['total_won']} ⭐</b>
💸 Bet: <b>{user_stats['total_bet']} ⭐</b>
📈 Win Rate: <b>{(user_stats['wins'] / max(user_stats['total_games'], 1) * 100):.1f}%</b>

🌐 <b>Casino Stats:</b>
👥 Registered Players: <b>{total_registered}</b>
🎰 Total Games: <b>{total_games}</b>
💰 Total Wagered: <b>{total_wagered:,} ⭐</b>
👥 Currently Online: <b>{len(online_players)}</b>

🎯 <b>Current Game:</b>
⏰ Next Spin: <b>{game_state['countdown']}s</b>
🎲 Last: {get_color_emoji(game_state['last_result']['color'])} <b>{game_state['last_result']['number']}</b>
📊 Active Bets: <b>{len(current_bets)}</b>

📈 <b>Last 10 Results:</b>
{' '.join([f"{get_color_emoji(r['color'])}{r['number']}" for r in game_state['spin_history'][-10:]])}
    """
    
    keyboard = [[InlineKeyboardButton("🎰 Play Now", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_msg, parse_mode='HTML', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎰 <b>Online European Roulette Help</b>

<b>📖 Commands:</b>
/start - Start the casino
/balance - Check balance & stats
/online - View online status
/stats - Detailed statistics
/help - Show this help

<b>🎮 How to Play:</b>
1. Click "Play Online Casino"
2. Register with your display name
3. Enter bet amount (10-20,000 ⭐)
4. Choose: RED, BLACK, or GREEN
5. Wait for synchronized spin (every 25 seconds)
6. Win and collect your payout!

<b>💰 Payouts:</b>
• 🔴 RED: x2 (18/37 chance)
• ⚫ BLACK: x2 (18/37 chance)  
• 🟢 GREEN (0): x36 (1/37 chance)

<b>🌐 Online Features:</b>
• Real-time multiplayer experience
• Synchronized countdown for all players
• Live betting display from other players
• Persistent balance and progress
• Cross-platform compatibility
• Mobile-optimized interface

Good luck at the tables! 🍀
    """
    
    keyboard = [[InlineKeyboardButton("🚀 Start Playing", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

def run_bot():
    """Запуск Telegram бота"""
    try:
        app_bot = Application.builder().token(BOT_TOKEN).build()
        
        # Команды
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("balance", balance))
        app_bot.add_handler(CommandHandler("online", online))
        app_bot.add_handler(CommandHandler("stats", stats))
        app_bot.add_handler(CommandHandler("help", help_command))
        
        # Запуск бота
        app_bot.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"Bot error: {e}")

# Игровой движок (ОНЛАЙН синхронизированный)
def online_game_engine():
    """Непрерывный игровой движок с точным таймингом"""
    print("🎮 Live Casino Engine Started")
    
    while True:
        try:
            # Новый раунд
            round_start_time = time.time()
            game_state['round'] += 1
            game_state['bets'] = {}
            
            # ФАЗА СТАВОК (30 секунд)
            game_state['phase'] = 'betting'
            betting_duration = 30
            
            print(f"🎰 Round {game_state['round']} - Betting Open")
            
            for remaining in range(betting_duration, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
            # ЗАКРЫТИЕ СТАВОК
            game_state['phase'] = 'spinning'
            print(f"🚫 Round {game_state['round']} - Betting Closed")
            
            # ФАЗА ВРАЩЕНИЯ (8 секунд)
            spinning_duration = 8
            
            # Генерируем результат заранее
            result_number = random.randint(0, 36)
            if result_number == 0:
                result_color = 'green'
            elif result_number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
                result_color = 'red'
            else:
                result_color = 'black'
            
            # Устанавливаем результат для анимации
            game_state['spinning_result'] = {
                'number': result_number,
                'color': result_color
            }
            
            print(f"🌀 Round {game_state['round']} - Spinning... Target: {result_number} ({result_color})")
            
            for remaining in range(spinning_duration, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
            # ПОКАЗ РЕЗУЛЬТАТА (5 секунд)
            game_state['phase'] = 'result'
            game_state['last_result'] = {
                'number': result_number,
                'color': result_color,
                'round': game_state['round']
            }
            
            print(f"🎯 Round {game_state['round']} - Result: {result_number} ({result_color})")
            
            # Обрабатываем ставки
            process_round_bets(result_number, result_color)
            
            # Показываем результат
            for remaining in range(5, 0, -1):
                game_state['time_left'] = remaining
                time.sleep(1)
            
        except Exception as e:
            print(f"❌ Game engine error: {e}")
            time.sleep(2)

def process_round_bets(result_number, result_color):
    """Обработка всех ставок раунда"""
    try:
        total_bets_amount = 0
        total_wins_amount = 0
        
        for user_id, user_bets in game_state['bets'].items():
            # Получаем актуальный баланс пользователя
            user = get_user_by_id(int(user_id))
            if not user:
                continue
            
            current_balance = user[4]  # balance column
            
            for bet in user_bets:
                bet_type = bet['bet_type']
                bet_amount = bet['bet_amount']
                win_amount = 0
                result = 'lose'
                
                # Определяем выигрыш
                if bet_type == result_color:
                    # Ставка на цвет
                    if result_color == 'green':
                        win_amount = bet_amount * 14  # x14 за зеленый
                    else:
                        win_amount = bet_amount * 2   # x2 за красный/черный
                    result = 'win'
                    
                elif bet_type.isdigit() and int(bet_type) == result_number:
                    # Ставка на конкретное число
                    win_amount = bet_amount * 36  # x36 за число
                    result = 'win'
                
                # Начисляем выигрыш
                if win_amount > 0:
                    new_balance = current_balance + win_amount
                    update_user_balance(int(user_id), new_balance)
                    current_balance = new_balance
                    total_wins_amount += win_amount
                    print(f"💰 User {user_id} won {win_amount} (bet: {bet_amount} on {bet_type})")
                
                # Сохраняем ставку в БД
                save_bet_history(user[0], game_state['round'], bet_type, bet_amount, result, win_amount)
                total_bets_amount += bet_amount
        
        # Сохраняем результат раунда
        save_game_result(game_state['round'], result_number, result_color, total_bets_amount)
        
        print(f"📊 Round {game_state['round']} processed: {total_bets_amount} bet, {total_wins_amount} paid out")
        
    except Exception as e:
        print(f"❌ Error processing bets: {e}")

def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
        
    except Exception as e:
        print(f"Error getting user by ID: {e}")
        return None

def update_user_balance(user_id, new_balance):
    """Обновление баланса пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        
        return rows_affected > 0
        
    except Exception as e:
        print(f"Error updating balance: {e}")
        return False

def save_bet_history(user_id, round_id, bet_type, bet_amount, result, win_amount):
    """Сохранение ставки в историю"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_bets 
            (user_id, round_id, bet_type, bet_amount, result, win_amount) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, round_id, bet_type, bet_amount, result, win_amount))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error saving bet: {e}")
        return False

def save_game_result(round_id, result_number, result_color, total_bets):
    """Сохранение результата игры"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO game_history 
            (round_id, result_number, result_color, total_bets) 
            VALUES (?, ?, ?, ?)
        ''', (round_id, result_number, result_color, total_bets))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error saving game result: {e}")
        return False

def process_online_spin_results(number, color):
    """Обработка результатов спина для всех онлайн игроков"""
    try:
        conn = sqlite3.connect('casino_online.db')
        cursor = conn.cursor()
        
        # Получаем все ставки текущего раунда
        for user_id, user_bets in current_bets.items():
            total_win = 0
            total_loss = 0
            won = False
            
            user = get_user(int(user_id))
            if not user:
                continue
                
            current_balance = user[4]
            
            for bet_type, bet_data in user_bets.items():
                bet_amount = bet_data['amount']
                
                if bet_type == color:
                    # Выигрыш
                    multiplier = 36 if color == 'green' else 2
                    win_amount = bet_amount * multiplier
                    total_win += win_amount
                    won = True
                    
                    # Обновляем запись ставки в БД
                    cursor.execute('''
                        UPDATE user_bets SET result = 'win', win_amount = ?
                        WHERE user_id = ? AND round_id = ? AND bet_type = ?
                    ''', (win_amount, user[0], game_state['round_id'], bet_type))
                else:
                    # Проигрыш
                    total_loss += bet_amount
                    cursor.execute('''
                        UPDATE user_bets SET result = 'lose', win_amount = 0
                        WHERE user_id = ? AND round_id = ? AND bet_type = ?
                    ''', (user[0], game_state['round_id'], bet_type))
            
            # Обновляем баланс
            if won:
                new_balance = current_balance + total_win
                update_user(int(user_id), balance=new_balance)
                print(f"Player {user[3]} won {total_win} stars!")
            else:
                print(f"Player {user[3]} lost {total_loss} stars")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error processing online spin results: {e}")
        if 'conn' in locals():
            conn.close()

def save_game_history(round_id, result_number, result_color, total_bets):
    """Сохранение истории игры"""
    try:
        conn = sqlite3.connect('casino_online.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO game_history (round_id, result_number, result_color, total_bets)
            VALUES (?, ?, ?, ?)
        ''', (round_id, result_number, result_color, total_bets))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving game history: {e}")

def cleanup_inactive_players():
    """Очистка неактивных игроков"""
    while True:
        try:
            current_time = datetime.now()
            inactive_players = []
            
            for user_id, player in online_players.items():
                joined_time = datetime.fromisoformat(player['joined_at'])
                if (current_time - joined_time).seconds > 300:  # 5 минут неактивности
                    inactive_players.append(user_id)
            
            for user_id in inactive_players:
                del online_players[user_id]
                print(f"Removed inactive player: {user_id}")
            
            time.sleep(60)  # Проверка каждую минуту
            
        except Exception as e:
            print(f"Cleanup error: {e}")
            time.sleep(60)

# В самом конце файла, перед if __name__ == '__main__':

def start_game_engine():
    """Запуск игрового движка в отдельном потоке"""
    import threading
    game_thread = threading.Thread(target=online_game_engine, daemon=True)
    game_thread.start()
    print("🎮 Live Game Engine Started in background")

if __name__ == '__main__':
    # Инициализация
    ensure_database()
    start_game_engine()  # ⭐ ЗАПУСКАЕМ ИГРОВОЙ ДВИЖОК
    
    # Запуск приложения
    try:
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=False,
            threaded=True  # ⭐ ВАЖНО для многопоточности
        )
    except Exception as e:
        print(f"❌ Server error: {e}")
            
if __name__ == '__main__':
    if init_application():
        port = int(os.environ.get('PORT', 5000))
        print(f"🚀 Starting Live Casino on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ Failed to initialize application")
    
    # Устанавливаем время запуска
    game_state['start_time'] = time.time()
    
    # Инициализация базы данных
    init_db()
    print("✅ Database initialized")
    
    # Запуск игрового движка
    game_engine_thread = threading.Thread(target=online_game_engine)
    game_engine_thread.daemon = True
    game_engine_thread.start()
    print("✅ Online game engine started")
    
    # Запуск очистки неактивных игроков
    cleanup_thread = threading.Thread(target=cleanup_inactive_players)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    print("✅ Cleanup service started")
    
    # Запуск Telegram бота
    if BOT_TOKEN and BOT_TOKEN != 'YOUR_BOT_TOKEN':
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        print("✅ Telegram bot started")
    else:
        print("⚠️  BOT_TOKEN not configured")
    
    # Запуск Flask сервера
    print(f"🚀 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
