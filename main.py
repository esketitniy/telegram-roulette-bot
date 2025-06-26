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

# Определяем путь к базе данных
DB_PATH = '/data/casino_online.db' if os.path.exists('/data') else 'casino_online.db'

print(f"🗂️  Using database path: {DB_PATH}")
print(f"💾 Disk mounted: {os.path.exists('/data')}")

# Создаем директорию для БД если нужно
db_dir = os.path.dirname(DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
    print(f"📁 Created directory: {db_dir}")

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
def init_background_services():
    """Инициализация фоновых сервисов"""
    print(f"📁 Database path: {DB_PATH}")
    
    # Инициализация базы данных на диске
    if ensure_database():
        print("✅ Database initialized on persistent disk")
    else:
        print("❌ Database initialization failed")
    
    # Устанавливаем время запуска
    game_state['start_time'] = time.time()
    
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
    """Гарантированная инициализация базы данных на диске"""
    try:
        # Создаем директорию если не существует
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                display_name TEXT NOT NULL,
                balance INTEGER DEFAULT 1000,
                is_registered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        print(f"✅ Database ensured at: {DB_PATH}")
        return True
        
    except Exception as e:
        print(f"❌ Database ensure error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def update_user(telegram_id, **kwargs):
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    
    set_clause = ', '.join([f'{key} = ?' for key in kwargs.keys()])
    values = list(kwargs.values()) + [telegram_id]
    
    cursor.execute(f'UPDATE users SET {set_clause}, last_seen = CURRENT_TIMESTAMP WHERE telegram_id = ?', values)
    conn.commit()
    conn.close()

def save_bet(user_id, round_id, bet_type, bet_amount, result, win_amount):
    """Сохранение ставки в базу данных"""
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
        if 'conn' in locals():
            conn.close()
        return False

def save_game_history(round_id, result_number, result_color, total_bets):
    """Сохранение истории игры"""
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
        print(f"Error saving game history: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def get_game_history(limit=20):
    """Получение истории игр"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT round_id, result_number, result_color, total_bets, created_at 
            FROM game_history 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        history = cursor.fetchall()
        conn.close()
        return history
        
    except Exception as e:
        print(f"Error getting game history: {e}")
        if 'conn' in locals():
            conn.close()
        return []
        
def get_user_stats(telegram_id):
    """Получение статистики пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Получаем пользователя
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return None
        
        user_id = user[0]
        
        # Получаем статистику ставок
        cursor.execute('''
            SELECT 
                COUNT(*) as total_bets,
                SUM(bet_amount) as total_wagered,
                SUM(win_amount) as total_won,
                SUM(CASE WHEN win_amount > 0 THEN 1 ELSE 0 END) as wins
            FROM user_bets 
            WHERE user_id = ?
        ''', (user_id,))
        
        stats = cursor.fetchone()
        conn.close()
        
        return {
            'user': user,
            'total_bets': stats[0] or 0,
            'total_wagered': stats[1] or 0,
            'total_won': stats[2] or 0,
            'wins': stats[3] or 0
        }
        
    except Exception as e:
        print(f"Error getting user stats: {e}")
        if 'conn' in locals():
            conn.close()
        return None

def get_color_emoji(color):
    return {'red': '🔴', 'black': '⚫', 'green': '🟢'}.get(color, '🎰')

# Flask маршруты
@app.route('/')
def index():
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎰 Online Casino</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; padding: 20px; text-align: center;
                min-height: 100vh; margin: 0;
            }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .status {{ 
                background: rgba(255,255,255,0.1); padding: 20px; border-radius: 15px; 
                margin: 20px 0; backdrop-filter: blur(10px);
            }}
            .button {{ 
                display: inline-block; background: linear-gradient(45deg, #FFD700, #FFA500);
                color: black; padding: 15px 30px; text-decoration: none; border-radius: 10px;
                font-weight: bold; margin: 10px; transition: transform 0.3s;
            }}
            .button:hover {{ transform: translateY(-2px); }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-item {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 ONLINE CASINO</h1>
            <p>Real-time multiplayer European Roulette</p>
            
            <div class="status">
                <h3>📊 Live Status</h3>
                <div class="stats">
                    <div class="stat-item">
                        <strong>👥 Players</strong><br>
                        <span id="player-count">{len(online_players)}</span>
                    </div>
                    <div class="stat-item">
                        <strong>⏰ Next Spin</strong><br>
                        <span id="countdown">{game_state['countdown']}</span>s
                    </div>
                    <div class="stat-item">
                        <strong>🎲 Last Result</strong><br>
                        {get_color_emoji(game_state['last_result']['color'])} {game_state['last_result']['number']}
                    </div>
                    <div class="stat-item">
                        <strong>📊 Round</strong><br>
                        #{game_state['round_id']}
                    </div>
                </div>
            </div>
            
            <div>
                <a href="/game" class="button">🎮 Play Casino</a>
                <a href="/api/status" class="button">📊 API Status</a>
            </div>
            
            <div style="margin-top: 30px; opacity: 0.8;">
                <p>✨ Features: Real-time multiplayer • Persistent balance • Auto-sync</p>
            </div>
        </div>
        
        <script>
            setInterval(async () => {{
                try {{
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    document.getElementById('player-count').textContent = data.players_online;
                    document.getElementById('countdown').textContent = data.game_state.countdown;
                }} catch (e) {{
                    console.log('Status update failed:', e);
                }}
            }}, 5000);
        </script>
    </body>
    </html>
    '''

@app.route('/game')
def game():
    return render_template_string('''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎰 Online European Roulette</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; min-height: 100vh; padding: 10px; overflow-x: hidden;
        }
        .container { max-width: 420px; margin: 0 auto; }
        
        .connection-status { 
            position: fixed; top: 10px; right: 10px; padding: 8px 15px; 
            border-radius: 20px; font-size: 12px; font-weight: bold; z-index: 100;
        }
        .status-connected { background: #00aa00; color: white; }
        .status-disconnected { background: #ff4444; color: white; }
        
        .registration-modal { 
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center;
            z-index: 1000;
        }
        .registration-form { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px; border-radius: 20px; text-align: center; max-width: 350px;
            margin: 20px; border: 2px solid rgba(255,215,0,0.5);
        }
        .registration-form h2 { margin-bottom: 20px; color: #FFD700; }
        .registration-form input { 
            width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 10px;
            background: rgba(255,255,255,0.1); color: white; font-size: 16px;
            border: 2px solid rgba(255,215,0,0.3);
        }
        .registration-form input::placeholder { color: rgba(255,255,255,0.7); }
        .registration-form button { 
            width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 10px;
            background: linear-gradient(45deg, #FFD700, #FFA500); color: black;
            font-size: 16px; font-weight: bold; cursor: pointer;
        }
        
        .header { text-align: center; margin-bottom: 20px; }
        .header h1 { 
            font-size: 24px; margin-bottom: 10px; 
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        
        .player-info { 
            background: rgba(255, 215, 0, 0.1); padding: 10px; border-radius: 15px; 
            margin-bottom: 15px; text-align: center; border: 2px solid rgba(255, 215, 0, 0.3);
        }
        
        .stats-row { 
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 20px;
        }
        .stat-box { 
            background: rgba(255, 255, 255, 0.15); padding: 12px; border-radius: 15px; 
            text-align: center; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .stat-box h3 { font-size: 12px; margin-bottom: 5px; opacity: 0.8; }
        .stat-value { font-size: 16px; font-weight: bold; color: #FFD700; }
        
        .countdown-box { 
            background: linear-gradient(45deg, rgba(255, 69, 0, 0.3), rgba(255, 140, 0, 0.3));
            border: 2px solid rgba(255, 69, 0, 0.5);
        }
        .countdown-timer { font-size: 24px; font-weight: bold; color: #ff4500; }
        .countdown-warning { animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
        
        .roulette-container { 
            position: relative; width: 280px; height: 280px; margin: 20px auto;
            display: flex; align-items: center; justify-content: center;
        }
        .roulette-wheel { 
            width: 260px; height: 260px; border-radius: 50%; position: relative;
            background: conic-gradient(
                #00ff00 0deg 9.73deg, #ff0000 9.73deg 19.46deg, #000000 19.46deg 29.19deg,
                #ff0000 29.19deg 38.92deg, #000000 38.92deg 48.65deg, #ff0000 48.65deg 58.38deg,
                #000000 58.38deg 68.11deg, #ff0000 68.11deg 77.84deg, #000000 77.84deg 87.57deg,
                #ff0000 87.57deg 97.30deg, #000000 97.30deg 107.03deg, #ff0000 107.03deg 116.76deg,
                #000000 116.76deg 126.49deg, #ff0000 126.49deg 136.22deg, #000000 136.22deg 145.95deg, #ff0000 145.95deg 155.68deg, #000000 155.68deg 165.41deg,
                #ff0000 165.41deg 175.14deg, #000000 175.14deg 184.87deg, #ff0000 184.87deg 194.60deg,
                #000000 194.60deg 204.33deg, #ff0000 204.33deg 214.06deg, #000000 214.06deg 223.79deg,
                #ff0000 223.79deg 233.52deg, #000000 233.52deg 243.25deg, #ff0000 243.25deg 252.98deg,
                #000000 252.98deg 262.71deg, #ff0000 262.71deg 272.44deg, #000000 272.44deg 282.17deg,
                #ff0000 282.17deg 291.90deg, #000000 291.90deg 301.63deg, #ff0000 301.63deg 311.36deg,
                #000000 311.36deg 321.09deg, #ff0000 321.09deg 330.82deg, #000000 330.82deg 340.55deg,
                #ff0000 340.55deg 350.28deg, #000000 350.28deg 360deg
            );
            border: 6px solid #FFD700; 
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.6), inset 0 0 20px rgba(0,0,0,0.3);
            transition: transform 8s cubic-bezier(0.25, 0.1, 0.25, 1);
        }
        .roulette-arrow { 
            position: absolute; top: -15px; left: 50%; transform: translateX(-50%);
            width: 0; height: 0; border-left: 20px solid transparent; 
            border-right: 20px solid transparent; border-top: 40px solid #FFD700; 
            z-index: 10; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
        }
        .wheel-center { 
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 80px; height: 80px; 
            background: radial-gradient(circle, #FFD700 30%, #FFA500 70%, #FF8C00 100%); 
            border-radius: 50%; display: flex; align-items: center; justify-content: center; 
            font-weight: bold; color: #000; font-size: 24px; 
            border: 4px solid #fff; z-index: 5;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.9), inset 0 0 15px rgba(0,0,0,0.2);
        }
        .spinning { animation: spin 8s cubic-bezier(0.25, 0.1, 0.25, 1); }
        @keyframes spin { 
            from { transform: rotate(0deg); } 
            to { transform: rotate(var(--spin-degrees, 2880deg)); } 
        }
        
        .bet-section { 
            background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 20px; 
            margin: 20px 0; backdrop-filter: blur(15px); 
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .bet-input-container { text-align: center; margin-bottom: 20px; }
        .bet-input { 
            padding: 15px 20px; border: 2px solid rgba(255, 215, 0, 0.5);
            border-radius: 30px; background: rgba(255, 255, 255, 0.1);
            color: white; font-size: 18px; text-align: center; width: 200px;
            backdrop-filter: blur(10px); font-weight: bold;
        }
        .bet-input:focus { 
            outline: none; border-color: #FFD700; 
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5); 
        }
        .bet-input::placeholder { color: rgba(255, 255, 255, 0.7); }
        .bet-buttons { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }
        .bet-btn { 
            padding: 18px 15px; border: none; border-radius: 15px; font-size: 14px; 
            font-weight: bold; cursor: pointer; transition: all 0.3s; text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        .bet-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.4); }
        .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .bet-red { background: linear-gradient(45deg, #ff4444, #cc0000); color: white; }
        .bet-black { background: linear-gradient(45deg, #333333, #000000); color: white; }
        .bet-green { background: linear-gradient(45deg, #00aa00, #006600); color: white; }
        
        .online-players { 
            background: rgba(255, 215, 0, 0.1); padding: 15px; border-radius: 15px; 
            margin: 15px 0; border: 2px solid rgba(255, 215, 0, 0.3);
        }
        .online-players h4 { margin-bottom: 15px; color: #FFD700; text-align: center; }
        .players-list { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
        .player-chip { 
            padding: 5px 10px; background: rgba(255, 255, 255, 0.2); 
            border-radius: 15px; font-size: 12px; border: 1px solid rgba(255, 255, 255, 0.3);
            color: #00ff00;
        }
        
        .live-bets { 
            background: rgba(255, 215, 0, 0.1); padding: 15px; border-radius: 15px; 
            margin: 15px 0; border: 2px solid rgba(255, 215, 0, 0.3); max-height: 200px; overflow-y: auto;
        }
        .live-bets h4 { margin-bottom: 15px; color: #FFD700; text-align: center; }
        .bet-item { 
            display: flex; justify-content: space-between; align-items: center;             
            padding: 8px 12px; margin: 5px 0; 
            background: rgba(255, 255, 255, 0.1); border-radius: 10px; font-size: 13px;
            animation: fadeInBet 0.5s ease;
        }
        @keyframes fadeInBet { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .bet-player { font-weight: bold; }
        .bet-details { display: flex; gap: 10px; align-items: center; }
        .bet-color-red { color: #ff4444; }
        .bet-color-black { color: #cccccc; }
        .bet-color-green { color: #00ff00; }
        
        .result-section { 
            background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 15px; 
            margin: 20px 0; text-align: center; backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2); min-height: 80px;
            display: flex; align-items: center; justify-content: center;
        }
        .result-win { 
            background: linear-gradient(45deg, rgba(0, 255, 0, 0.2), rgba(0, 200, 0, 0.2));
            border-color: #00ff00; color: #00ff00; animation: winPulse 1s ease;
        }
        .result-lose { 
            background: linear-gradient(45deg, rgba(255, 0, 0, 0.2), rgba(200, 0, 0, 0.2));
            border-color: #ff4444; color: #ff4444;
        }
        @keyframes winPulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        .result-text { font-size: 16px; font-weight: bold; }
        
        .history-section { 
            background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 15px; 
            margin: 15px 0; backdrop-filter: blur(10px);
        }
        .history-title { text-align: center; margin-bottom: 15px; color: #FFD700; }
        .history-numbers { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
        .history-number { 
            width: 35px; height: 35px; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center;
            font-size: 12px; font-weight: bold; border: 2px solid rgba(255,255,255,0.3);
            animation: slideIn 0.5s ease;
        }
        @keyframes slideIn { from { transform: translateX(-50px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .history-red { background: #ff4444; color: white; }
        .history-black { background: #333333; color: white; }
        .history-green { background: #00aa00; color: white; }
        
        .footer { text-align: center; margin-top: 30px; opacity: 0.7; font-size: 12px; }
        
        @media (max-width: 480px) {
            .stats-row { grid-template-columns: 1fr 1fr; }
            .roulette-container { width: 250px; height: 250px; }
            .roulette-wheel { width: 230px; height: 230px; }
            .bet-input { width: 180px; font-size: 16px; }
        }
    </style>
</head>
<body>
    <div class="connection-status status-connected" id="connection-status">🟢 Connected</div>

    <div class="registration-modal" id="registration-modal" style="display: none;">
        <div class="registration-form">
            <h2>🎰 Welcome to Casino!</h2>
            <p>Enter your display name to start playing</p>
            <input type="text" id="display-name" placeholder="Enter your name" maxlength="20" autocomplete="name">
            <button onclick="registerUser()" id="register-btn">🚀 Start Playing</button>
            <p><small>Your progress will be saved automatically</small></p>
        </div>
    </div>

    <div class="container" id="game-container" style="display: none;">
        <div class="header">
            <h1>🎰 ONLINE ROULETTE</h1>
        </div>
        
        <div class="player-info">
            <strong>👋 <span id="player-name">Player</span></strong>
            <small id="player-id" style="opacity: 0.7;"></small>
        </div>
        
        <div class="stats-row">
            <div class="stat-box">
                <h3>💰 Balance</h3>
                <div class="stat-value" id="balance">1000 ⭐</div>
            </div>
            <div class="stat-box">
                <h3>👥 Online</h3>
                <div class="stat-value" id="online-count">1</div>
            </div>
            <div class="stat-box countdown-box" id="countdown-container">
                <h3>⏰ Next Spin</h3>
                <div class="countdown-timer" id="countdown">25</div>
            </div>
        </div>
        
        <div class="roulette-container">
            <div class="roulette-arrow"></div>
            <div class="roulette-wheel" id="roulette-wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
        </div>
        
        <div class="bet-section">
            <div class="bet-input-container">
                <input type="number" id="bet-amount" class="bet-input" 
                       placeholder="Enter bet (10-20000)" min="10" max="20000" value="10">
            </div>
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red')" id="red-btn">
                    🔴 RED<br><small>x2</small>
                </button>
                <button class="bet-btn bet-black" onclick="placeBet('black')" id="black-btn">
                    ⚫ BLACK<br><small>x2</small>
                </button>
                <button class="bet-btn bet-green" onclick="placeBet('green')" id="green-btn">
                    🟢 GREEN<br><small>x36</small>
                </button>
            </div>
        </div>
        
        <div class="online-players" id="online-players">
            <h4>👥 Online Players (<span id="players-count">0</span>)</h4>
            <div class="players-list" id="players-list"></div>
        </div>
        
        <div class="live-bets" id="live-bets" style="display: none;">
            <h4>🔥 Live Bets</h4>
            <div id="bets-list"></div>
        </div>
        
        <div class="result-section" id="result-section">
            <div class="result-text">🌐 Connected! Place your bet and wait for spin!</div>
        </div>
        
        <div class="history-section">
            <h4 class="history-title">📊 Recent Results</h4>
            <div class="history-numbers" id="history-numbers"></div>
        </div>
        
        <div class="footer">
            <p>🎰 Synchronized online roulette • Auto spin every 25 seconds</p>
        </div>
    </div>

    <script>
        // Глобальные переменные
        let tg = window.Telegram.WebApp;
        let userId = tg.initDataUnsafe?.user?.id || Math.floor(Math.random() * 1000000);
        let userName = tg.initDataUnsafe?.user?.username || `guest_${userId}`;
        let displayName = '';
        let userBalance = 1000;
        let isRegistered = false;
        let gameState = {
            countdown: 25,
            isSpinning: false,
            lastResult: { number: 0, color: 'green' },
            history: []
        };
        let onlinePlayers = {};
        let liveBets = {};
        let userBets = {};
        let gameInterval;
        let lastSpinResult = null;
        
        // Инициализация Telegram WebApp
        if (tg) {
            tg.ready();
            tg.expand();
            tg.MainButton.hide();
        }
        
        // Функция для HTTP запросов
        async function apiRequest(url, data = null) {
            const options = {
                method: data ? 'POST' : 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            try {
                const response = await fetch(url, options);
                return await response.json();
            } catch (error) {
                console.error('API request failed:', error);
                return { success: false, message: 'Connection failed' };
            }
        }
        
        // Проверка регистрации
        async function checkRegistration() {
            try {
                const result = await apiRequest(`/api/check_registration?user_id=${userId}`);
                if (result.success && result.is_registered) {
                    isRegistered = true;
                    displayName = result.display_name;
                    userBalance = result.balance;
                    showGameInterface();
                    startGamePolling();
                } else {
                    showRegistrationModal();
                }
            } catch (error) {
                console.error('Registration check failed:', error);
                showRegistrationModal();
            }
        }
        
        // Регистрация пользователя
        async function registerUser() {
            const nameInput = document.getElementById('display-name');
            const name = nameInput.value.trim();
            
            if (name.length < 2) {
                alert('Name must be at least 2 characters long');
                return;
            }
            
            if (name.length > 20) {
                alert('Name must be less than 20 characters');
                return;
            }
            
            document.getElementById('register-btn').disabled = true;
            document.getElementById('register-btn').textContent = 'Registering...';
            
            try {
                const result = await apiRequest('/api/register', {
                    user_id: userId,
                    username: userName,
                    display_name: name
                });
                
                if (result.success) {
                    displayName = result.display_name;
                    userBalance = result.balance;
                    isRegistered = true;
                    showGameInterface();
                    startGamePolling();
                } else {
                    alert(result.message);
                    document.getElementById('register-btn').disabled = false;
                    document.getElementById('register-btn').textContent = '🚀 Start Playing';
                }
            } catch (error) {
                alert('Registration failed. Please try again.');
                document.getElementById('register-btn').disabled = false;
                document.getElementById('register-btn').textContent = '🚀 Start Playing';
            }
        }
        
        // Размещение ставки
        async function placeBet(color) {
            if (gameState.isSpinning || gameState.countdown <= 3) {
                showResult('❌ Betting is closed!', 'result-lose');
                return;
            }
            
            const betAmount = parseInt(document.getElementById('bet-amount').value);
            
            if (betAmount < 10 || betAmount > 20000) {
                showResult('❌ Bet must be between 10 and 20,000 stars!', 'result-lose');
                return;
            }
            
            if (betAmount > userBalance) {
                showResult('❌ Insufficient balance!', 'result-lose');
                return;
            }
            
            try {
                const result = await apiRequest('/api/place_bet', {
                    user_id: userId,
                    bet_type: color,
                    amount: betAmount
                });
                
                if (result.success) {
                    userBalance = result.new_balance;
                    userBets[color] = (userBets[color] || 0) + betAmount;
                    showResult(`✅ Bet placed: ${color.toUpperCase()} ${betAmount} ⭐`, '');
                    updateGameUI();
                } else {
                    showResult('❌ ' + result.message, 'result-lose');
                }
            } catch (error) {
                showResult('❌ Bet failed. Please try again.', 'result-lose');
            }
        }
        
        // Polling для обновления состояния игры
        function startGamePolling() {
            // Добавляем игрока в онлайн список
            onlinePlayers[userId] = {
                display_name: displayName,
                user_id: userId
            };
            
            gameInterval = setInterval(async () => {
                try {
                    const result = await apiRequest('/api/game_state');
                    
                    // Обновляем состояние игры
                    const previousSpinning = gameState.isSpinning;
                    gameState = result.game_state;
                    onlinePlayers = result.online_players || onlinePlayers;
                    liveBets = result.current_bets || {};
                    
                    // Проверяем начало спина
                    if (!previousSpinning && gameState.is_spinning) {
                        startSpinAnimation();
                        showResult('🎰 Spinning...', '');
                    }
                    
                    // Проверяем окончание спина
                    if (previousSpinning && !gameState.is_spinning && lastSpinResult !== gameState.last_result.number) {
                        lastSpinResult = gameState.last_result.number;
                        document.getElementById('result-number').textContent = gameState.last_result.number;
                        processSpinResult(gameState.last_result);
                        userBets = {}; // Очищаем ставки пользователя
                    }
                    
                    updateGameUI();
                    updatePlayersDisplay();
                    updateBetsDisplay();
                    
                } catch (error) {
                    console.error('Game state update failed:', error);
                    document.getElementById('connection-status').className = 'connection-status status-disconnected';
                    document.getElementById('connection-status').textContent = '🔴 Connection Lost';
                }
            }, 1000); // Обновление каждую секунду
        }
        
        // Функции интерфейса
        function showRegistrationModal() {
            document.getElementById('registration-modal').style.display = 'flex';
            document.getElementById('game-container').style.display = 'none';
        }
        
        function showGameInterface() {
            document.getElementById('registration-modal').style.display = 'none';
            document.getElementById('game-container').style.display = 'block';
            
            document.getElementById('player-name').textContent = displayName;
            document.getElementById('player-id').textContent = `ID: ${userId}`;
            
            updateGameUI();
        }
        
        function updateGameUI() {
            document.getElementById('balance').textContent = userBalance + ' ⭐';
            document.getElementById('countdown').textContent = gameState.countdown;
            document.getElementById('online-count').textContent = Object.keys(onlinePlayers).length;
            
            // Предупреждение при последних секундах
            const countdownContainer = document.getElementById('countdown-container');
            if (gameState.countdown <= 5 && !gameState.is_spinning) {
                countdownContainer.classList.add('countdown-warning');
            } else {
                countdownContainer.classList.remove('countdown-warning');
            }
            
            updateBetButtons();
            updateHistoryDisplay();
        }
        
        function updateBetButtons() {
            const betAmount = parseInt(document.getElementById('bet-amount').value) || 0;
            const buttons = ['red-btn', 'black-btn', 'green-btn'];
            const canBet = !gameState.is_spinning && gameState.countdown > 3 && betAmount >= 10 && betAmount <= 20000 && betAmount <= userBalance;
            
            buttons.forEach(btnId => {
                document.getElementById(btnId).disabled = !canBet;
            });
            
            // Обновляем состояние input
            const betInput = document.getElementById('bet-amount');
            betInput.style.borderColor = canBet ? 'rgba(255, 215, 0, 0.5)' : 'rgba(255, 0, 0, 0.5)';
        }
        
        function updatePlayersDisplay() {
            const playersList = document.getElementById('players-list');
            const playersCount = document.getElementById('players-count');
            
            const playersArray = Object.values(onlinePlayers);
            playersCount.textContent = playersArray.length;
            playersList.innerHTML = '';
            
            playersArray.forEach(player => {
                const playerChip = document.createElement('div');
                playerChip.className = 'player-chip';
                playerChip.textContent = player.display_name || `Player ${player.user_id}`;
                playersList.appendChild(playerChip);
            });
        }
        
        function updateBetsDisplay() {
            const liveBetsContainer = document.getElementById('live-bets');
            const betsList = document.getElementById('bets-list');
            
            const allBets = [];
            Object.values(liveBets).forEach(playerBets => {
                Object.values(playerBets).forEach(bet => {
                    allBets.push(bet);
                });
            });
            
            if (allBets.length > 0) {
                liveBetsContainer.style.display = 'block';
                betsList.innerHTML = '';
                
                // Сортируем по времени (новые сверху)
                allBets.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                
                allBets.slice(0, 10).forEach(bet => {
                    const betItem = document.createElement('div');
                    betItem.className = 'bet-item';
                    betItem.innerHTML = `
                        <span class="bet-player">${bet.display_name}</span>
                        <div class="bet-details">
                            <span class="bet-color-${bet.type}">${bet.type.toUpperCase()}</span>
                            <span>${bet.amount} ⭐</span>
                        </div>
                    `;
                    betsList.appendChild(betItem);
                });
            } else {
                liveBetsContainer.style.display = 'none';
            }
        }
        
        function updateHistoryDisplay() {
            const historyContainer = document.getElementById('history-numbers');
            historyContainer.innerHTML = '';
            
            if (gameState.spin_history && gameState.spin_history.length > 0) {
                gameState.spin_history.slice(-10).forEach((result, index) => {
                    const numberDiv = document.createElement('div');
                    numberDiv.className = `history-number history-${result.color}`;
                    numberDiv.textContent = result.number;
                    numberDiv.style.animationDelay = `${index * 0.1}s`;
                    historyContainer.appendChild(numberDiv);
                });
            }
        }
        
        function startSpinAnimation() {
            const wheel = document.getElementById('roulette-wheel');
            const finalNumber = gameState.last_result.number;
            const rouletteNumbers = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
            
            // Случайное количество оборотов + точная позиция
            const spins = 8 + Math.random() * 4; // 8-12 оборотов
            const numberIndex = rouletteNumbers.indexOf(finalNumber);
            const degreesPerNumber = 360 / 37;
            const finalDegree = 360 - (numberIndex * degreesPerNumber) + (degreesPerNumber / 2);
            const totalDegrees = (spins * 360) + finalDegree;
            
            wheel.style.setProperty('--spin-degrees', totalDegrees + 'deg');
            wheel.classList.add('spinning');
            
            setTimeout(() => {
                wheel.classList.remove('spinning');
            }, 8000);
        }
        
        function processSpinResult(result) {
            // Проверяем выигрыш пользователя
            let totalWin = 0;
            let totalLoss = 0;
            let won = false;
            
            for (const [betType, betAmount] of Object.entries(userBets)) {
                if (betType === result.color) {
                    const multiplier = result.color === 'green' ? 36 : 2;
                    const winAmount = betAmount * multiplier;
                    totalWin += winAmount;
                    won = true;
                } else {
                    totalLoss += betAmount;
                }
            }
            
            if (won) {
                userBalance += totalWin;
                showResult(`🎉 WIN! ${result.color.toUpperCase()} ${result.number} - You won ${totalWin} ⭐!`, 'result-win');
            } else if (totalLoss > 0) {
                showResult(`💔 LOSE! ${result.color.toUpperCase()} ${result.number} - You lost ${totalLoss} ⭐`, 'result-lose');
            } else {
                showResult(`🎰 Result: ${result.color.toUpperCase()} ${result.number}`, '');
            }
        }
        
        function showResult(message, className) {
            const resultSection = document.getElementById('result-section');
            resultSection.className = 'result-section ' + className;
            resultSection.innerHTML = `<div class="result-text">${message}</div>`;
        }
        
        // Обработчики событий
        document.getElementById('bet-amount').addEventListener('input', updateBetButtons);
        
        // Обработка нажатия Enter в поле регистрации
        document.getElementById('display-name').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                registerUser();
            }
        });
        
        // Предотвращение закрытия во время игры
        window.addEventListener('beforeunload', function(e) {
            if (Object.keys(userBets).length > 0 && !gameState.is_spinning) {
                e.preventDefault();
                e.returnValue = 'You have active bets. Are you sure you want to leave?';
            }
        });
        
        // Запуск при загрузке страницы
        document.addEventListener('DOMContentLoaded', function() {
            checkRegistration();
        });
    </script>
</body>
</html>''')

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
    print("🔄 Starting registration process...")
    ensure_database()
    
    try:
        data = request.get_json()
        print(f"🔍 Parsed JSON: {data}")
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        # Извлекаем данные
        telegram_id = data.get('telegram_id')
        username = data.get('username', '')
        display_name = data.get('display_name', '')
        
        # ВРЕМЕННОЕ ИСПРАВЛЕНИЕ: Генерируем ID если не передан
        if not telegram_id:
            # Извлекаем числа из username если есть
            import re
            if username and 'guest_' in username:
                numbers = re.findall(r'\d+', username)
                if numbers:
                    telegram_id = int(numbers[0])
                    print(f"🔧 Generated telegram_id from username: {telegram_id}")
                else:
                    telegram_id = int(time.time())  # Используем timestamp
                    print(f"🔧 Generated telegram_id from timestamp: {telegram_id}")
            else:
                telegram_id = int(time.time())
                print(f"🔧 Generated telegram_id: {telegram_id}")
        
        print(f"🔍 Final data:")
        print(f"  - telegram_id: {telegram_id}")
        print(f"  - username: {username}")
        print(f"  - display_name: {display_name}")
        
        if not display_name:
            return jsonify({
                'success': False,
                'message': 'Display name required'
            }), 400
        
        # Проверяем существующего пользователя
        existing_user = get_user(int(telegram_id))
        
        if existing_user:
            # Обновляем существующего
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET username = ?, display_name = ?, is_registered = 1 
                WHERE telegram_id = ?
            ''', (username, display_name, int(telegram_id)))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'User updated successfully',
                'user_id': existing_user[0],
                'display_name': display_name,
                'balance': existing_user[4]
            })
        
        else:
            # Создаем нового
            user_id = create_user(int(telegram_id), username, display_name)
            
            if user_id:
                return jsonify({
                    'success': True,
                    'message': 'User registered successfully',
                    'user_id': user_id,
                    'display_name': display_name,
                    'balance': 1000
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to create user'
                }), 500
                
    except Exception as e:
        print(f"❌ Exception in api_register: {e}")
        import traceback
        print(traceback.format_exc())
        
        return jsonify({
            'success': False,
            'message': f'Registration error: {str(e)}'
        }), 500
        
@app.route('/api/place_bet', methods=['POST'])
def api_place_bet():
    ensure_database()
    data = request.json
    user_id = data['user_id']
    bet_type = data['bet_type']
    amount = data['amount']
    
    user = get_user(user_id)
    if not user or not user[5]:  # not registered
        return jsonify({'success': False, 'message': 'User not registered'})
    
    if game_state['is_spinning'] or game_state['countdown'] <= 3:
        return jsonify({'success': False, 'message': 'Betting is closed'})
    
    if amount < 10 or amount > 20000:
        return jsonify({'success': False, 'message': 'Invalid bet amount'})
    
    if amount > user[4]:  # balance
        return jsonify({'success': False, 'message': 'Insufficient balance'})
    
    # Сохраняем ставку
    new_balance = user[4] - amount
    update_user(user_id, balance=new_balance)
    save_bet(user[0], game_state['round_id'], bet_type, amount)
    
    # Добавляем в текущие ставки
    user_id_str = str(user_id)
    if user_id_str not in current_bets:
        current_bets[user_id_str] = {}
    
    if bet_type not in current_bets[user_id_str]:
        current_bets[user_id_str][bet_type] = {
            'display_name': user[3],
            'type': bet_type,
            'amount': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    current_bets[user_id_str][bet_type]['amount'] += amount
    
    return jsonify({
        'success': True,
        'bet_type': bet_type,
        'amount': amount,
        'new_balance': new_balance
    })

@app.route('/api/game_state')
def api_game_state():
    return jsonify({
        'game_state': game_state,
        'online_players': online_players,
        'current_bets': current_bets,
        'timestamp': datetime.now().isoformat()
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
    """Синхронизированный игровой движок для всех игроков"""
    global game_state, current_bets
    
    while True:
        try:
            if not game_state['is_spinning']:
                # Обратный отсчет синхронизированный для всех
                for i in range(25, 0, -1):
                    if game_state['is_spinning']:
                        break
                    
                    game_state['countdown'] = i
                    time.sleep(1)
                
                if not game_state['is_spinning']:
                    # Начинаем спин
                    game_state['is_spinning'] = True
                    game_state['countdown'] = 0
                    game_state['round_id'] = int(time.time())
                    
                    # Генерируем результат
                    roulette_numbers = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
                    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
                    
                    result_number = random.choice(roulette_numbers)
                    result_color = 'green' if result_number == 0 else ('red' if result_number in red_numbers else 'black')
                    
                    print(f"🎰 ONLINE SPIN: {result_color.upper()} {result_number}")
                    
                    # Ждем анимацию (8 секунд)
                    time.sleep(8)
                    
                    # Обрабатываем результаты для всех игроков
                    process_online_spin_results(result_number, result_color)
                    
                    # Сохраняем результат
                    game_state['last_result'] = {'number': result_number, 'color': result_color}
                    game_state['spin_history'].append({'number': result_number, 'color': result_color})
                    
                    # Ограничиваем историю
                    if len(game_state['spin_history']) > 50:
                        game_state['spin_history'] = game_state['spin_history'][-50:]
                    
                    # Сохраняем в базу данных
                    save_game_history(game_state['round_id'], result_number, result_color, len(current_bets))
                    
                    # Очищаем ставки
                    current_bets = {}
                    game_state['is_spinning'] = False
            
            time.sleep(0.1)  # Малая задержка для плавности
            
        except Exception as e:
            print(f"Online game engine error: {e}")
            time.sleep(1)

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
            
if __name__ == '__main__':
    print("🌐 Starting Online Casino Server...")
    
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
