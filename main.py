import sqlite3
import hashlib
import secrets
import time
import threading
import random
import json
from flask import Flask, request, jsonify
import os

# Константы
DB_PATH = 'casino.db'

# Глобальное игровое состояние
game_state = {
    'round_id': int(time.time()),
    'countdown': 30,
    'is_spinning': False,
    'last_result': None,
    'spin_history': [],
    'bets': {}
}

# Flask приложение
app = Flask(__name__)

# ================================
# ФУНКЦИИ БАЗЫ ДАННЫХ
# ================================

def ensure_database():
    """Создание и инициализация базы данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                balance REAL DEFAULT 1000.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Таблица истории игр
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                bet_type TEXT NOT NULL,
                bet_amount REAL NOT NULL,
                result_number INTEGER,
                result_color TEXT,
                win_amount REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database error: {e}")
        return False

# ================================
# ФУНКЦИИ АВТОРИЗАЦИИ
# ================================

def hash_password(password):
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user_account(username, password, display_name):
    """Создание нового аккаунта"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, display_name, password_hash, balance)
            VALUES (?, ?, ?, ?)
        ''', (username, display_name, password_hash, 1000.0))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
        
    except sqlite3.IntegrityError:
        return None
    except Exception as e:
        print(f"User creation error: {e}")
        return None

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
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"Authentication error: {e}")
        return None

def create_session(user_id):
    """Создание сессии"""
    try:
        session_token = secrets.token_urlsafe(32)
        expires_at = time.time() + (24 * 60 * 60)  # 24 часа
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sessions (user_id, session_token, expires_at)
            VALUES (?, ?, ?)
        ''', (user_id, session_token, expires_at))
        
        conn.commit()
        conn.close()
        
        return session_token
        
    except Exception as e:
        print(f"Session creation error: {e}")
        return None

def validate_session(session_token):
    """Проверка сессии"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.display_name, u.balance
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.session_token = ? AND s.expires_at > ?
        ''', (session_token, time.time()))
        
        user = cursor.fetchone()
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"Session validation error: {e}")
        return None

def get_user_by_id(user_id):
    """Получение пользователя по ID"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, display_name, balance
            FROM users 
            WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"Get user error: {e}")
        return None

def update_user_balance(user_id, new_balance):
    """Обновление баланса пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET balance = ? 
            WHERE id = ?
        ''', (new_balance, user_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
        
    except Exception as e:
        print(f"Balance update error: {e}")
        return False

# ================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================

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

def get_bet_display_name(bet_type):
    """Отображаемое имя ставки"""
    if bet_type == 'red':
        return 'КРАСНОЕ'
    elif bet_type == 'black':
        return 'ЧЕРНОЕ'
    elif bet_type == 'green':
        return 'ЗЕЛЕНОЕ'
    else:
        return f'число {bet_type}'

def ensure_game_state_keys():
    """Обеспечивает наличие всех необходимых ключей в game_state"""
    required_keys = {
        'round_id': int(time.time()),
        'bets': {},
        'is_spinning': False,
        'countdown': 30,
        'last_result': None,
        'spin_history': []
    }
    
    for key, default_value in required_keys.items():
        if key not in game_state:
            game_state[key] = default_value
            print(f"📝 Added missing key '{key}' to game_state")

# ================================
# ИГРОВОЙ ДВИЖОК
# ================================

def online_game_engine():
    """Непрерывный игровой движок"""
    print("🎮 Live Casino Engine Started")
    
    global game_state
    ensure_game_state_keys()
    
    while True:
        try:
            # Новый раунд
            game_state['round_id'] = int(time.time())
            game_state['bets'] = {}
            game_state['is_spinning'] = False
            
            print(f"🎰 Round {game_state['round_id']} - Starting")
            
            # ФАЗА СТАВОК (30 секунд)
            for countdown in range(30, 0, -1):
                game_state['countdown'] = countdown
                time.sleep(1)
            
            # ЗАКРЫТИЕ СТАВОК
            game_state['countdown'] = 0
            game_state['is_spinning'] = True
            print("🚫 Betting Closed - Spinning...")
            
            # ВРАЩЕНИЕ (5 секунд)
            result_number = random.randint(0, 36)
            result_color = get_number_color(result_number)
            
            # Спин анимация
            for i in range(5, 0, -1):
                time.sleep(1)
            
            # РЕЗУЛЬТАТ
            game_state['is_spinning'] = False
            game_state['last_result'] = {
                'number': result_number,
                'color': result_color,
                'round': game_state['round_id']
            }
            
            print(f"🎯 Result: {result_number} ({result_color})")
            
            # Обрабатываем ставки
            process_round_bets(result_number, result_color)
            
            # Добавляем в историю
            game_state['spin_history'].insert(0, {
                'number': result_number,
                'color': result_color,
                'round': game_state['round_id']
            })
            if len(game_state['spin_history']) > 10:
                game_state['spin_history'] = game_state['spin_history'][:10]
            
            # Показываем результат 5 секунд
            for i in range(5, 0, -1):
                game_state['countdown'] = i
                time.sleep(1)
            
        except Exception as e:
            print(f"❌ Game engine error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(2)

def process_round_bets(result_number, result_color):
    """Обработка ставок раунда"""
    try:
        if not game_state.get('bets'):
            print("📝 No bets to process")
            return
        
        print(f"💰 Processing bets for result: {result_number} ({result_color})")
        
        for user_id, user_bets in game_state['bets'].items():
            user = get_user_by_id(int(user_id))
            if not user:
                continue
            
            current_balance = user[3]
            total_winnings = 0
            
            for bet in user_bets:
                bet_type = bet['bet_type']
                bet_amount = bet['bet_amount']
                win_amount = 0
                
                # Проверяем выигрыш
                if bet_type == result_color:
                    if result_color == 'green':
                        win_amount = bet_amount * 14
                    else:
                        win_amount = bet_amount * 2
                elif bet_type.isdigit() and int(bet_type) == result_number:
                    win_amount = bet_amount * 36
                
                total_winnings += win_amount
                
                # Сохраняем в историю
                save_bet_history(
                    game_state['round_id'],
                    int(user_id),
                    bet_type,
                    bet_amount,
                    result_number,
                    result_color,
                    win_amount
                )
            
            # Начисляем выигрыши
            if total_winnings > 0:
                new_balance = current_balance + total_winnings
                update_user_balance(int(user_id), new_balance)
                print(f"💰 User {user_id} won {total_winnings}")
            
    except Exception as e:
        print(f"❌ Error processing bets: {e}")
        import traceback
        traceback.print_exc()

def save_bet_history(round_id, user_id, bet_type, bet_amount, result_number, result_color, win_amount):
    """Сохранение истории ставки"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO game_history 
            (round_id, user_id, bet_type, bet_amount, result_number, result_color, win_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (round_id, user_id, bet_type, bet_amount, result_number, result_color, win_amount))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"History save error: {e}")

# ================================
# ROUTES
# ================================

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
            max-width: 800px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.3);
            padding: 30px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }

        .betting-title {
            text-align: center;
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #ffd700;
        }

        .bet-amount-selector {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .bet-amount-btn {
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border: 2px solid #ffd700;
            padding: 10px 20px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
        }

        .bet-amount-btn:hover,
        .bet-amount-btn.active {
            background: #ffd700;
            color: black;
            transform: scale(1.05);
        }

        .betting-options {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .bet-option {
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid transparent;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
            font-size: 16px;
        }

        .bet-option:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
        }

        .bet-option.red {
            background: linear-gradient(135deg, #ff4757, #ff3742);
            color: white;
        }

        .bet-option.black {
            background: linear-gradient(135deg, #2f3542, #40424a);
            color: white;
        }

        .bet-option.green {
            background: linear-gradient(135deg, #26de81, #20bf6b);
            color: white;
        }

        .bet-option.selected {
            border-color: #ffd700;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }

        .numbers-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 8px;
            margin-top: 20px;
        }

        .number-bet {
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 10px;
            padding: 15px 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
            min-height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .number-bet:hover {
            transform: scale(1.05);
            border-color: #ffd700;
        }

        .number-bet.red {
            background: rgba(255, 0, 0, 0.3);
            color: #ff6b6b;
        }

        .number-bet.black {
            background: rgba(0, 0, 0, 0.5);
            color: white;
        }

        .number-bet.green {
            background: rgba(0, 128, 0, 0.3);
            color: #51cf66;
        }

        .number-bet.selected {
            border-color: #ffd700;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
        }

        .place-bet-btn {
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
            margin-top: 20px;
        }

        .place-bet-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 215, 0, 0.3);
        }

        .place-bet-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Результаты */
        .results-section {
            max-width: 800px;
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
            width: 50px;
            height: 50px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
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

            .betting-options {
                grid-template-columns: repeat(2, 1fr);
            }

            .numbers-grid {
                grid-template-columns: repeat(4, 1fr);
            }

            .bet-amount-selector {
                grid-template-columns: repeat(3, 1fr);
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
        }

        .notification.success {
            border-left-color: #26de81;
        }

        .notification.error {
            border-left-color: #ff4757;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
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
            <h2 class="betting-title">Выберите ставку</h2>
            
            <!-- Выбор суммы ставки -->
            <div class="bet-amount-selector" id="betAmounts">
                <button class="bet-amount-btn active" data-amount="10">10</button>
                <button class="bet-amount-btn" data-amount="25">25</button>
                <button class="bet-amount-btn" data-amount="50">50</button>
                <button class="bet-amount-btn" data-amount="100">100</button>
                <button class="bet-amount-btn" data-amount="250">250</button>
                <button class="bet-amount-btn" data-amount="500">500</button>
            </div>

            <!-- Основные ставки -->
            <div class="betting-options">
                <div class="bet-option red" data-bet="red">
                    <div>🔴 КРАСНОЕ</div>
                    <div>x2</div>
                </div>
                <div class="bet-option black" data-bet="black">
                    <div>⚫ ЧЕРНОЕ</div>
                    <div>x2</div>
                </div>
                <div class="bet-option green" data-bet="green">
                    <div>🟢 ЗЕЛЕНОЕ</div>
                    <div>x14</div>
                </div>
            </div>

            <!-- Ставки на числа -->
            <div class="numbers-grid" id="numbersGrid">
                <!-- Генерируется JavaScript -->
            </div>

            <button class="place-bet-btn" id="placeBetBtn" onclick="placeBet()" disabled>
                Сделать ставку
            </button>
        </div>

        <!-- Последние результаты -->
        <div class="results-section">
            <h3 class="results-title">Последние результаты</h3>
            <div class="recent-results" id="recentResults">
                <!-- Генерируется JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // Глобальные переменные
        let currentUser = null;
        let sessionToken = null;
        let selectedBetType = null;
        let selectedBetAmount = 10;
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
            generateNumbersGrid();
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

            // Выбор суммы ставки
            document.querySelectorAll('.bet-amount-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    document.querySelectorAll('.bet-amount-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    selectedBetAmount = parseInt(this.dataset.amount);
                    updateBetButton();
                });
            });

            // Выбор типа ставки
            document.querySelectorAll('.bet-option').forEach(option => {
                option.addEventListener('click', function() {
                    selectBetType(this.dataset.bet);
                });
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

        // Генерация сетки чисел
        function generateNumbersGrid() {
            const numbersGrid = document.getElementById('numbersGrid');
            const numbers = [
                { num: 0, color: 'green' },
                { num: 1, color: 'red' }, { num: 2, color: 'black' }, { num: 3, color: 'red' },
                { num: 4, color: 'black' }, { num: 5, color: 'red' }, { num: 6, color: 'black' },
                { num: 7, color: 'red' }, { num: 8, color: 'black' }, { num: 9, color: 'red' },
                { num: 10, color: 'black' }, { num: 11, color: 'black' }, { num: 12, color: 'red' },
                { num: 13, color: 'black' }, { num: 14, color: 'red' }, { num: 15, color: 'black' },
                { num: 16, color: 'red' }, { num: 17, color: 'black' }, { num: 18, color: 'red' },
                { num: 19, color: 'red' }, { num: 20, color: 'black' }, { num: 21, color: 'red' },
                { num: 22, color: 'black' }, { num: 23, color: 'red' }, { num: 24, color: 'black' },
                { num: 25, color: 'red' }, { num: 26, color: 'black' }, { num: 27, color: 'red' },
                { num: 28, color: 'black' }, { num: 29, color: 'black' }, { num: 30, color: 'red' },
                { num: 31, color: 'black' }, { num: 32, color: 'red' }, { num: 33, color: 'black' },
                { num: 34, color: 'red' }, { num: 35, color: 'black' }, { num: 36, color: 'red' }
            ];

            numbers.forEach(({ num, color }) => {
                const numberDiv = document.createElement('div');
                numberDiv.className = `number-bet ${color}`;
                numberDiv.dataset.bet = num.toString();
                numberDiv.textContent = num;
                numberDiv.addEventListener('click', function() {
                    selectBetType(this.dataset.bet);
                });
                numbersGrid.appendChild(numberDiv);
            });
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

    // Выбор типа ставки
        function selectBetType(betType) {
            // Убираем выделение со всех опций
            document.querySelectorAll('.bet-option, .number-bet').forEach(option => {
                option.classList.remove('selected');
            });

            // Выделяем выбранную опцию
            const selectedElement = document.querySelector(`[data-bet="${betType}"]`);
            if (selectedElement) {
                selectedElement.classList.add('selected');
            }

            selectedBetType = betType;
            updateBetButton();
        }

        // Обновление кнопки ставки
        function updateBetButton() {
            const betBtn = document.getElementById('placeBetBtn');
            
            if (selectedBetType && selectedBetAmount && !gameState.is_spinning && gameState.countdown > 0) {
                betBtn.disabled = false;
                betBtn.textContent = `Поставить ${selectedBetAmount} на ${getBetDisplayName(selectedBetType)}`;
            } else {
                betBtn.disabled = true;
                if (gameState.is_spinning) {
                    betBtn.textContent = 'Рулетка вращается...';
                } else if (gameState.countdown <= 0) {
                    betBtn.textContent = 'Ставки закрыты';
                } else {
                    betBtn.textContent = 'Выберите ставку';
                }
            }
        }

        // Получить отображаемое имя ставки
        function getBetDisplayName(betType) {
            switch(betType) {
                case 'red': return 'КРАСНОЕ';
                case 'black': return 'ЧЕРНОЕ';
                case 'green': return 'ЗЕЛЕНОЕ';
                default: return `число ${betType}`;
            }
        }

        // Размещение ставки
        function placeBet() {
            if (!selectedBetType || !selectedBetAmount || !sessionToken) {
                showNotification('Выберите тип ставки и сумму', 'error');
                return;
            }

            if (gameState.is_spinning || gameState.countdown <= 0) {
                showNotification('Ставки закрыты', 'error');
                return;
            }

            if (currentUser.balance < selectedBetAmount) {
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
                    bet_type: selectedBetType,
                    bet_amount: selectedBetAmount
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentUser.balance = data.new_balance;
                    updateUserInfo();
                    showNotification(data.message, 'success');
                    
                    // Сбрасываем выбор
                    selectedBetType = null;
                    document.querySelectorAll('.bet-option, .number-bet').forEach(option => {
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
            
            // Показать результат вращения
        function showSpinResult(result) {
            const resultText = `Выпало: ${result.number} (${getColorName(result.color)})`;
            showNotification(resultText, 'success');
            
            // Добавляем эффект пульсации к таймеру
            const timer = document.getElementById('gameTimer');
            timer.style.animation = 'pulse 0.5s ease-in-out 3';
        }

        // Получить название цвета
        function getColorName(color) {
            switch(color) {
                case 'red': return 'КРАСНОЕ';
                case 'black': return 'ЧЕРНОЕ';
                case 'green': return 'ЗЕЛЕНОЕ';
                default: return color.toUpperCase();
            }
        }

        // Обновление UI игры
        function updateGameUI() {
            // Обновляем таймер
            const timer = document.getElementById('gameTimer');
            timer.textContent = gameState.time_left || gameState.countdown || 0;
            
            // Обновляем фазу игры
            const phaseElement = document.getElementById('gamePhase');
            
            if (gameState.is_spinning !== undefined) {
                // Используем старый формат
                if (gameState.is_spinning) {
                    phaseElement.textContent = '🌀 Рулетка вращается...';
                    timer.style.color = '#ff6b6b';
                } else if (gameState.countdown > 0) {
                    phaseElement.textContent = '💰 Делайте ваши ставки!';
                    timer.style.color = '#ffd700';
                } else {
                    phaseElement.textContent = '⏰ Ставки закрыты';
                    timer.style.color = '#ff6b6b';
                }
            } else {
                // Используем новый формат
                switch(gameState.phase) {
                    case 'betting':
                        phaseElement.textContent = '💰 Делайте ваши ставки!';
                        timer.style.color = '#ffd700';
                        break;
                    case 'spinning':
                        phaseElement.textContent = '🌀 Рулетка вращается...';
                        timer.style.color = '#ff6b6b';
                        break;
                    case 'result':
                        phaseElement.textContent = '🎯 Результат раунда';
                        timer.style.color = '#26de81';
                        break;
                    default:
                        phaseElement.textContent = 'Подготовка...';
                        timer.style.color = '#ffd700';
                }
            }
            
            // Обновляем кнопку ставки
            updateBetButton();
        }

        // Обновление последних результатов
        function updateRecentResults(newResult) {
            // Добавляем новый результат в начало массива
            const exists = recentResults.some(result => 
                result.number === newResult.number && 
                result.round === newResult.round
            );
            
            if (!exists) {
                recentResults.unshift(newResult);
                if (recentResults.length > 10) {
                    recentResults = recentResults.slice(0, 10);
                }
                renderRecentResults();
            }
        }

        // Отображение последних результатов
        function renderRecentResults() {
            const resultsContainer = document.getElementById('recentResults');
            resultsContainer.innerHTML = '';
            
            recentResults.forEach(result => {
                const resultDiv = document.createElement('div');
                resultDiv.className = `result-number ${result.color}`;
                resultDiv.textContent = result.number;
                resultDiv.title = `Раунд ${result.round || 'N/A'}`;
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
                if (data.success && data.user) {
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
            // Удаляем существующие уведомления
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
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 4000);
        }

        // Обработка ошибок сети
        window.addEventListener('online', function() {
            showNotification('Соединение восстановлено', 'success');
            if (sessionToken) {
                startGameUpdates();
            }
        });

        window.addEventListener('offline', function() {
            showNotification('Нет соединения с интернетом', 'error');
            stopGameUpdates();
        });

        // Обработка закрытия страницы
        window.addEventListener('beforeunload', function() {
            stopGameUpdates();
        });

        // Периодическая проверка сессии (каждые 5 минут)
        setInterval(function() {
            if (sessionToken) {
                validateSession(sessionToken);
            }
        }, 5 * 60 * 1000);

        // Горячие клавиши
        document.addEventListener('keydown', function(e) {
            // ESC - сброс выбора ставки
            if (e.key === 'Escape') {
                selectedBetType = null;
                document.querySelectorAll('.bet-option, .number-bet').forEach(option => {
                    option.classList.remove('selected');
                });
                updateBetButton();
            }
            
            // Enter - разместить ставку
            if (e.key === 'Enter' && selectedBetType && !document.getElementById('placeBetBtn').disabled) {
                placeBet();
            }
            
            // Цифры 1-9 для быстрого выбора суммы ставки
            if (e.key >= '1' && e.key <= '6') {
                const amounts = [10, 25, 50, 100, 250, 500];
                const index = parseInt(e.key) - 1;
                if (amounts[index]) {
                    document.querySelectorAll('.bet-amount-btn').forEach(btn => {
                        btn.classList.remove('active');
                        if (parseInt(btn.dataset.amount) === amounts[index]) {
                            btn.classList.add('active');
                            selectedBetAmount = amounts[index];
                            updateBetButton();
                        }
                    });
                }
            }
        });

        // Инициализация тач-событий для мобильных устройств
        document.addEventListener('touchstart', function() {}, {passive: true});
        
        // Предотвращение зума на мобильных устройствах
        document.addEventListener('touchend', function(e) {
            if (e.target.tagName !== 'INPUT') {
                e.preventDefault();
            }
        }, {passive: false});

        console.log('🎰 Live Casino loaded successfully!');
    </script>
</body>
</html>'''

# ================================
# API ENDPOINTS
# ================================

@app.route('/api/register', methods=['POST'])
def api_register():
    """Регистрация нового пользователя"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip()
        
        if not all([username, password, display_name]):
            return jsonify({
                'success': False,
                'message': 'Все поля обязательны'
            }), 400
        
        if len(username) < 3:
            return jsonify({
                'success': False,
                'message': 'Логин должен быть не менее 3 символов'
            }), 400
        
        if len(password) < 4:
            return jsonify({
                'success': False,
                'message': 'Пароль должен быть не менее 4 символов'
            }), 400
        
        # Создаем пользователя
        user_id = create_user_account(username, password, display_name)
        if not user_id:
            return jsonify({
                'success': False,
                'message': 'Пользователь с таким логином уже существует'
            }), 400
        
        # Создаем сессию
        session_token = create_session(user_id)
        if not session_token:
            return jsonify({
                'success': False,
                'message': 'Ошибка создания сессии'
            }), 500
        
        # Получаем данные пользователя
        user = get_user_by_id(user_id)
        
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
        
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'message': 'Ошибка регистрации'
        }), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """Вход пользователя"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Логин и пароль обязательны'
            }), 400
        
        # Аутентификация
        user = authenticate_user(username, password)
        if not user:
            return jsonify({
                'success': False,
                'message': 'Неверный логин или пароль'
            }), 401
        
        # Создаем сессию
        session_token = create_session(user[0])
        if not session_token:
            return jsonify({
                'success': False,
                'message': 'Ошибка создания сессии'
            }), 500
        
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
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            'success': False,
            'message': 'Ошибка входа'
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
                'message': 'Токен сессии отсутствует'
            }), 400
        
        user = validate_session(session_token)
        if not user:
            return jsonify({
                'success': False,
                'message': 'Недействительная сессия'
            }), 401
        
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'display_name': user[2],
                'balance': user[3]
            }
        })
        
    except Exception as e:
        print(f"Session validation error: {e}")
        return jsonify({
            'success': False,
            'message': 'Ошибка проверки сессии'
        }), 500

@app.route('/api/place_bet', methods=['POST'])
def api_place_bet():
    """Размещение ставки"""
    try:
        data = request.get_json()
        session_token = data.get('session_token')
        bet_type = data.get('bet_type')
        bet_amount = data.get('bet_amount')
        
        print(f"🎯 Bet request: {bet_type} for {bet_amount}")
        print(f"🎮 Current game state: {game_state}")
        
        if not all([session_token, bet_type, bet_amount]):
            return jsonify({
                'success': False,
                'message': 'Все поля обязательны'
            }), 400
        
        # Проверяем сессию
        user = validate_session(session_token)
        if not user:
            return jsonify({
                'success': False,
                'message': 'Недействительная сессия'
            }), 401
        
        user_id = user[0]
        current_balance = user[3]
        
        # Создаем ключ 'bets' если его нет
        if 'bets' not in game_state:
            game_state['bets'] = {}
            print("📝 Created 'bets' key in game_state")
        
        # Проверяем можно ли делать ставки
        is_spinning = game_state.get('is_spinning', False)
        countdown = game_state.get('countdown', 0)
        
        if is_spinning:
            return jsonify({
                'success': False,
                'message': 'Рулетка вращается, ставки закрыты'
            }), 400
        
        if countdown <= 0:
            return jsonify({
                'success': False,
                'message': 'Время для ставок истекло'
            }), 400
        
        # Проверяем баланс
        if current_balance < bet_amount:
            return jsonify({
                'success': False,
                'message': 'Недостаточно средств'
            }), 400
        
        # Проверяем валидность ставки
        valid_bets = ['red', 'black', 'green'] + [str(i) for i in range(37)]
        if bet_type not in valid_bets:
            return jsonify({
                'success': False,
                'message': 'Недопустимый тип ставки'
            }), 400
        
        # Списываем средства
        new_balance = current_balance - bet_amount
        if not update_user_balance(user_id, new_balance):
            return jsonify({
                'success': False,
                'message': 'Ошибка обновления баланса'
            }), 500
            # Добавляем ставку
        user_id_str = str(user_id)
        if user_id_str not in game_state['bets']:
            game_state['bets'][user_id_str] = []
        
        game_state['bets'][user_id_str].append({
            'bet_type': bet_type,
            'bet_amount': bet_amount,
            'timestamp': time.time()
        })
        
        print(f"✅ Bet placed: User {user_id} bet {bet_amount} on {bet_type}")
        print(f"📊 Current bets: {game_state['bets']}")
        
        return jsonify({
            'success': True,
            'message': f'Ставка размещена: {bet_amount} на {get_bet_display_name(bet_type)}',
            'new_balance': new_balance
        })
        
    except Exception as e:
        print(f"❌ Place bet error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Ошибка размещения ставки: {str(e)}'
        }), 500

@app.route('/api/game_state')
def api_game_state():
    """Получение текущего состояния игры"""
    try:
        # Адаптируем формат для фронтенда
        countdown = game_state.get('countdown', 30)
        is_spinning = game_state.get('is_spinning', False)
        last_result = game_state.get('last_result')
        
        # Определяем фазу на основе состояния
        if is_spinning:
            phase = 'spinning'
        elif countdown > 0:
            phase = 'betting'
        else:
            phase = 'result'
        
        return jsonify({
            'success': True,
            'game_state': {
                'round': game_state.get('round_id', 1),
                'phase': phase,
                'time_left': countdown,
                'countdown': countdown,
                'is_spinning': is_spinning,
                'last_result': last_result,
                'spinning_result': last_result if is_spinning else None,
                'spin_history': game_state.get('spin_history', [])
            }
        })
    except Exception as e:
        print(f"Game state API error: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/game_history')
def api_game_history():
    """Получение истории игр пользователя"""
    try:
        session_token = request.args.get('session_token')
        if not session_token:
            return jsonify({
                'success': False,
                'message': 'Токен сессии отсутствует'
            }), 400
        
        user = validate_session(session_token)
        if not user:
            return jsonify({
                'success': False,
                'message': 'Недействительная сессия'
            }), 401
        
        user_id = user[0]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT round_id, bet_type, bet_amount, result_number, result_color, 
                   win_amount, created_at
            FROM game_history 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 50
        ''', (user_id,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'round_id': row[0],
                'bet_type': row[1],
                'bet_amount': row[2],
                'result_number': row[3],
                'result_color': row[4],
                'win_amount': row[5],
                'created_at': row[6]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        print(f"History API error: {e}")
        return jsonify({
            'success': False,
            'message': 'Ошибка получения истории'
        }), 500

@app.route('/api/debug_state')
def debug_state():
    """Отладочная информация о состоянии"""
    return jsonify({
        'game_state': game_state,
        'game_state_keys': list(game_state.keys()),
        'bets_exists': 'bets' in game_state,
        'current_bets': game_state.get('bets', {}),
        'countdown': game_state.get('countdown', 'NOT_FOUND'),
        'is_spinning': game_state.get('is_spinning', 'NOT_FOUND')
    })

# ================================
# ИНИЦИАЛИЗАЦИЯ И ЗАПУСК
# ================================

def init_application():
    """Инициализация приложения"""
    print("🎰 Initializing Live Casino...")
    
    # Инициализация БД
    if not ensure_database():
        print("❌ Database initialization failed")
        return False
    
    print("✅ Database initialized")
    
    # Обеспечиваем наличие всех ключей в game_state
    ensure_game_state_keys()
    print(f"🎮 Game state initialized: {game_state}")
    
    # Запуск игрового движка
    try:
        game_thread = threading.Thread(target=online_game_engine, daemon=True)
        game_thread.start()
        print("✅ Game engine started")
        
        # Даем время движку запуститься
        time.sleep(2)
        print(f"🎯 Game state after engine start: {game_state}")
        
    except Exception as e:
        print(f"❌ Failed to start game engine: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Главная функция запуска"""
    print("=" * 50)
    print("🎰 LIVE CASINO ROULETTE")
    print("=" * 50)
    
    # Инициализация приложения
    if not init_application():
        print("❌ Application initialization failed")
        return
    
    print("🚀 Starting Flask server...")
    print("🌐 Open http://localhost:5000 in your browser")
    print("=" * 50)
    
    try:
        # Запуск Flask сервера
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Отключаем debug для продакшена
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
    finally:
        print("👋 Goodbye!")

if __name__ == '__main__':
    main()
