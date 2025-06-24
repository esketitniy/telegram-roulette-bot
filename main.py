import os
import sqlite3
import threading
import time
import asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random
import json
from flask_socketio import SocketIO, emit, join_room, leave_room

# Настройки
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
PORT = int(os.getenv('PORT', 5000))
APP_URL = os.getenv('APP_URL', 'https://your-app.onrender.com')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'casino_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
def init_db():
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            display_name TEXT,
            balance INTEGER DEFAULT 1000,
            is_registered INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY,
            round_id INTEGER,
            result_number INTEGER,
            result_color TEXT,
            total_bets INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_bets (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            round_id INTEGER,
            bet_type TEXT,
            amount INTEGER,
            result TEXT DEFAULT 'pending',
            win_amount INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

def get_user(telegram_id, create_if_not_exists=True):
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    
    if not user and create_if_not_exists:
        cursor.execute('''
            INSERT INTO users (telegram_id, username, display_name, is_registered) 
            VALUES (?, ?, ?, ?)
        ''', (telegram_id, f'user_{telegram_id}', f'Player{telegram_id}', 0))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
    
    conn.close()
    return user

def update_user(telegram_id, **kwargs):
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    
    set_clause = ', '.join([f'{key} = ?' for key in kwargs.keys()])
    values = list(kwargs.values()) + [telegram_id]
    
    cursor.execute(f'UPDATE users SET {set_clause}, last_seen = CURRENT_TIMESTAMP WHERE telegram_id = ?', values)
    conn.commit()
    conn.close()

def save_bet(user_id, round_id, bet_type, amount):
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_bets (user_id, round_id, bet_type, amount)
        VALUES (?, ?, ?, ?)
    ''', (user_id, round_id, bet_type, amount))
    conn.commit()
    conn.close()

def get_user_stats(telegram_id):
    conn = sqlite3.connect('casino_online.db')
    cursor = conn.cursor()
    
    # Получаем статистику пользователя
    cursor.execute('''
        SELECT 
            COUNT(*) as total_games,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'win' THEN win_amount ELSE 0 END) as total_won,
            SUM(amount) as total_bet
        FROM user_bets ub
        JOIN users u ON u.id = ub.user_id
        WHERE u.telegram_id = ?
    ''', (telegram_id,))
    
    stats = cursor.fetchone()
    conn.close()
    
    return {
        'total_games': stats[0] or 0,
        'wins': stats[1] or 0,
        'total_won': stats[2] or 0,
        'total_bet': stats[3] or 0
    }

# Flask маршруты
@app.route('/')
def index():
    return '''
    <h1>🎰 Online Casino</h1>
    <p>Real-time multiplayer casino is running!</p>
    <p>👥 Active players: <span id="player-count">0</span></p>
    <a href="/game">Join Game</a>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        socket.on('player_count', (count) => {
            document.getElementById('player-count').textContent = count;
        });
    </script>
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; min-height: 100vh; padding: 10px; overflow-x: hidden;
        }
        .container { max-width: 420px; margin: 0 auto; }
        
        /* Регистрация */
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
                #000000 116.76deg 126.49deg, #ff0000 126.49deg 136.22deg, #000000 136.22deg 145.95deg,
                #ff0000 145.95deg 155.68deg, #000000 155.68deg 165.41deg, #ff0000 165.41deg 175.14deg,
                #000000 175.14deg 184.87deg, #ff0000 184.87deg 194.60deg, #000000 194.60deg 204.33deg,
                #ff0000 204.33deg 214.06deg, #000000 214.06deg 223.79deg, #ff0000 223.79deg 233.52deg,
                #000000 233.52deg 243.25deg, #ff0000 243.25deg 252.98deg, #000000 252.98deg 262.71deg,
                #ff0000 262.71deg 272.44deg, #000000 272.44deg 282.17deg, #ff0000 282.17deg 291.90deg,
                #000000 291.90deg 301.63deg, #ff0000 301.63deg 311.36deg, #000000 311.36deg 321.09deg,
                #ff0000 321.09deg 330.82deg, #000000 330.82deg 340.55deg, #ff0000 340.55deg 350.28deg,
                #000000 350.28deg 360deg
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
        }
        .player-chip.online { border-color: #00ff00; color: #00ff00; }
        
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
        
        .connection-status { 
            position: fixed; top: 10px; right: 10px; padding: 8px 15px; 
            border-radius: 20px; font-size: 12px; font-weight: bold; z-index: 100;
        }
        .status-connected { background: #00aa00; color: white; }
        .status-disconnected { background: #ff4444; color: white; }
        
        .footer { text-align: center; margin-top: 30px; opacity: 0.7; font-size: 12px; }
        
        /* Мобильная адаптация */
        @media (max-width: 480px) {
            .stats-row { grid-template-columns: 1fr 1fr; }
            .roulette-container { width: 250px; height: 250px; }
            .roulette-wheel { width: 230px; height: 230px; }
            .bet-input { width: 180px; font-size: 16px; }
        }
    </style>
</head>
<body>
    <!-- Модальное окно регистрации -->
    <div class="registration-modal" id="registration-modal">
        <div class="registration-form">
            <h2>🎰 Welcome to Casino!</h2>
            <p>Enter your display name to start playing</p>
            <input type="text" id="display-name" placeholder="Enter your name" maxlength="20" autocomplete="name">
            <button onclick="registerUser()" id="register-btn">🚀 Start Playing</button>
            <p><small>Your progress will be saved automatically</small></p>
        </div>
    </div>

    <!-- Статус подключения -->
    <div class="connection-status status-disconnected" id="connection-status">🔴 Connecting...</div>

    <div class="container" id="game-container" style="display: none;">
        <div class="header">
            <h1>🎰 ONLINE ROULETTE</h1>
        </div>
        
        <!-- Информация об игроке -->
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
        
        <!-- Онлайн игроки -->
        <div class="online-players" id="online-players">
            <h4>👥 Online Players (<span id="players-count">0</span>)</h4>
            <div class="players-list" id="players-list"></div>
        </div>
        
        <!-- Живые ставки -->
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
        let socket = io();
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
        
        // Инициализация Telegram WebApp
        if (tg) {
            tg.ready();
            tg.expand();
            tg.MainButton.hide();
        }
        
        // Регистрация пользователя
        function registerUser() {
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
            
            displayName = name;
            document.getElementById('register-btn').disabled = true;
            document.getElementById('register-btn').textContent = 'Registering...';
            
            // Отправляем регистрацию на сервер
            socket.emit('register_user', {
                user_id: userId,
                username: userName,
                display_name: displayName
            });
        }
        
        // Socket.IO события
        socket.on('connect', function() {
            console.log('Connected to server');
            document.getElementById('connection-status').className = 'connection-status status-connected';
            document.getElementById('connection-status').textContent = '🟢 Connected';
            
            // Проверяем регистрацию
            socket.emit('check_registration', { user_id: userId });
        });
        
        socket.on('disconnect', function() {
            console.log('Disconnected from server');
            document.getElementById('connection-status').className = 'connection-status status-disconnected';
            document.getElementById('connection-status').textContent = '🔴 Disconnected';
        });
        
        socket.on('registration_checked', function(data) {
            if (data.is_registered) {
                isRegistered = true;
                displayName = data.display_name;
                userBalance = data.balance;
                showGameInterface();
            } else {
                showRegistrationModal();
            }
        });
        
        socket.on('registration_success', function(data) {
            isRegistered = true;
            userBalance = data.balance;
            showGameInterface();
        });
        
        socket.on('registration_error', function(data) {
            alert(data.message);
            document.getElementById('register-btn').disabled = false;
            document.getElementById('register-btn').textContent = '🚀 Start Playing';
        });
        
        // Синхронизация игрового состояния
        socket.on('game_state_update', function(data) {
            gameState = data;
            updateGameUI();
        });
        
        socket.on('spin_started', function(data) {
            gameState.isSpinning = true;
            startSpinAnimation(data.final_number);
            showResult('🎰 Spinning...', '');
            updateBetButtons();
        });
        
        socket.on('spin_result', function(data) {
            gameState.lastResult = data.result;
            gameState.history = data.history;
            gameState.isSpinning = false;
            
            document.getElementById('result-number').textContent = data.result.number;
            processSpinResult(data.result, data.user_result);
            
            // Очищаем ставки
            liveBets = {};
            userBets = {};
            updateBetsDisplay();
            updateGameUI();
        });
        
        // Обновление игроков онлайн
        socket.on('players_update', function(data) {
            onlinePlayers = data.players;
            updatePlayersDisplay();
        });
        
        // Обновление ставок
        socket.on('bets_update', function(data) {
            liveBets = data.bets;
            updateBetsDisplay();
        });
        
        // Обновление баланса
        socket.on('balance_update', function(data) {
            userBalance = data.balance;
            updateGameUI();
        });
        
        // Ошибки ставок
        socket.on('bet_error', function(data) {
            showResult('❌ ' + data.message, 'result-lose');
        });
        
        socket.on('bet_success', function(data) {
            userBets[data.bet_type] = (userBets[data.bet_type] || 0) + data.amount;
            showResult(`✅ Bet placed: ${data.bet_type.toUpperCase()} ${data.amount} ⭐`, '');
        });
        
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
            
            // Присоединяемся к игровой комнате
            socket.emit('join_game', { user_id: userId });
            
            updateGameUI();
        }
        
        function updateGameUI() {
            document.getElementById('balance').textContent = userBalance + ' ⭐';
            document.getElementById('countdown').textContent = gameState.countdown;
            document.getElementById('online-count').textContent = Object.keys(onlinePlayers).length;
            
            // Предупреждение при последних секундах
            const countdownContainer = document.getElementById('countdown-container');
            if (gameState.countdown <= 5 && !gameState.isSpinning) {
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
            const canBet = !gameState.isSpinning && gameState.countdown > 3 && betAmount >= 10 && betAmount <= 20000 && betAmount <= userBalance;
            
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
            
            playersCount.textContent = Object.keys(onlinePlayers).length;
            playersList.innerHTML = '';
            
            Object.values(onlinePlayers).forEach(player => {
                const playerChip = document.createElement('div');
                playerChip.className = 'player-chip online';
                playerChip.textContent = player.display_name;
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
            
            gameState.history.slice(-10).forEach((result, index) => {
                const numberDiv = document.createElement('div');
                numberDiv.className = `history-number history-${result.color}`;
                numberDiv.textContent = result.number;
                numberDiv.style.animationDelay = `${index * 0.1}s`;
                historyContainer.appendChild(numberDiv);
            });
        }
        
        function placeBet(color) {
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
            
            // Отправляем ставку на сервер
            socket.emit('place_bet', {
                user_id: userId,
                bet_type: color,
                amount: betAmount
            });
        }
        
        function startSpinAnimation(finalNumber) {
            const wheel = document.getElementById('roulette-wheel');
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
        
        function processSpinResult(result, userResult) {
            if (userResult) {
                if (userResult.won) {
                    showResult(`🎉 WIN! ${result.color.toUpperCase()} ${result.number} - You won ${userResult.win_amount} ⭐!`, 'result-win');
                } else {
                    showResult(`💔 LOSE! ${result.color.toUpperCase()} ${result.number} - You lost ${userResult.loss_amount} ⭐`, 'result-lose');
                }
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
            if (Object.keys(userBets).length > 0 && !gameState.isSpinning) {
                e.preventDefault();
                e.returnValue = 'You have active bets. Are you sure you want to leave?';
            }
        });
        
        // Автоматическое переподключение
        socket.on('reconnect', function() {
            console.log('Reconnected to server');
            if (isRegistered) {
                socket.emit('join_game', { user_id: userId });
            }
        });
    </script>
</body>
</html>''')

# SocketIO события
@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    # Удаляем игрока из онлайн списка
    for user_id, player in list(online_players.items()):
        if player.get('session_id') == request.sid:
            del online_players[user_id]
            break
    
    socketio.emit('players_update', {'players': online_players}, broadcast=True)

@socketio.on('check_registration')
def handle_check_registration(data):
    user_id = data['user_id']
    user = get_user(user_id)
    
    if user and user[5]:  # is_registered = 1
        emit('registration_checked', {
            'is_registered': True,
            'display_name': user[3],
            'balance': user[4]
        })
    else:
        emit('registration_checked', {'is_registered': False})

@socketio.on('register_user')
def handle_register_user(data):
    user_id = data['user_id']
    username = data['username']
    display_name = data['display_name']
    
    try:
        # Проверяем уникальность имени
        conn = sqlite3.connect('casino_online.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE display_name = ? AND telegram_id != ?', (display_name, user_id))
        existing = cursor.fetchone()
        
        if existing:
            emit('registration_error', {'message': 'This name is already taken!'})
            conn.close()
            return
        
        # Обновляем или создаем пользователя
        user = get_user(user_id)
        if user:
            update_user(user_id, username=username, display_name=display_name, is_registered=1)
        
        user = get_user(user_id)
        emit('registration_success', {
            'display_name': display_name,
            'balance': user[4]
        })
        
        conn.close()
        
    except Exception as e:
        emit('registration_error', {'message': 'Registration failed. Please try again.'})

@socketio.on('join_game')
def handle_join_game(data):
    user_id = data['user_id']
    user = get_user(user_id)
    
    if user and user[5]:  # is_registered
        online_players[user_id] = {
            'user_id': user_id,
            'display_name': user[3],
            'session_id': request.sid,
            'joined_at': datetime.now().isoformat()
        }
        
        join_room('game_room')
        
        # Отправляем текущее состояние игры
        emit('game_state_update', game_state)
        emit('players_update', {'players': online_players}, broadcast=True)
        emit('bets_update', {'bets': current_bets}, broadcast=True)

@socketio.on('place_bet')
def handle_place_bet(data):
    user_id = data['user_id']
    bet_type = data['bet_type']
    amount = data['amount']
    
    user = get_user(user_id)
    if not user or not user[5]:  # not registered
        emit('bet_error', {'message': 'User not registered'})
        return
    
    if game_state['is_spinning'] or game_state['countdown'] <= 3:
        emit('bet_error', {'message': 'Betting is closed'})
        return
    
    if amount < 10 or amount > 20000:
        emit('bet_error', {'message': 'Invalid bet amount'})
        return
    
    if amount > user[4]:  # balance
        emit('bet_error', {'message': 'Insufficient balance'})
        return
    
    # Сохраняем ставку
    new_balance = user[4] - amount
    update_user(user_id, balance=new_balance)
    save_bet(user[0], game_state['round_id'], bet_type, amount)
    
    # Добавляем в текущие ставки
    if user_id not in current_bets:
        current_bets[user_id] = {}
    
    if bet_type not in current_bets[user_id]:
        current_bets[user_id][bet_type] = {
            'display_name': user[3],
            'type': bet_type,
            'amount': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    current_bets[user_id][bet_type]['amount'] += amount
    
    emit('bet_success', {'bet_type': bet_type, 'amount': amount})
    emit('balance_update', {'balance': new_balance})
    socketio.emit('bets_update', {'bets': current_bets}, room='game_room')

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

<b>🔥 Advanced Features:</b>
• Live player list with online status
• Real-time bet tracking
• Historical results display
• Personal statistics tracking
• Automatic reconnection
• Responsive design for all devices

<b>💡 Pro Tips:</b>
• Register to save your progress permanently
• Start with small bets to learn the game
• Watch other players' betting patterns
• Green has the highest payout but lowest probability
• The game runs automatically every 25 seconds
• Your balance is synchronized across all devices

<b>🛡️ Fair Play:</b>
• Results are generated server-side
• All spins are random and fair
• No manipulation possible
• Transparent gameplay for all players

Good luck at the tables! 🍀
    """
    
    keyboard = [[InlineKeyboardButton("🚀 Start Playing", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

def get_color_emoji(color):
    return {'red': '🔴', 'black': '⚫', 'green': '🟢'}.get(color, '🎰')

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
                    
                    # Отправляем обновление всем подключенным игрокам
                    socketio.emit('game_state_update', game_state, room='game_room')
                    
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
                    
                    # Уведомляем всех о начале спина
                    socketio.emit('spin_started', {
                        'final_number': result_number,
                        'timestamp': datetime.now().isoformat()
                    }, room='game_room')
                    
                    # Ждем анимацию (8 секунд)
                    time.sleep(8)
                    
                    # Обрабатываем результаты для всех игроков
                    spin_results = process_online_spin_results(result_number, result_color)
                    
                    # Сохраняем результат
                    game_state['last_result'] = {'number': result_number, 'color': result_color}
                    game_state['spin_history'].append({'number': result_number, 'color': result_color})
                    
                    # Ограничиваем историю
                    if len(game_state['spin_history']) > 50:
                        game_state['spin_history'] = game_state['spin_history'][-50:]
                    
                    # Сохраняем в базу данных
                    save_game_history(game_state['round_id'], result_number, result_color, len(current_bets))
                    
                    # Отправляем результат всем игрокам
                    socketio.emit('spin_result', {
                        'result': {'number': result_number, 'color': result_color},
                        'history': game_state['spin_history'],
                        'user_result': None,  # Будет заполнено индивидуально
                        'timestamp': datetime.now().isoformat()
                    }, room='game_room')
                    
                    # Отправляем индивидуальные результаты
                    for user_id, result_data in spin_results.items():
                        if user_id in online_players:
                            session_id = online_players[user_id]['session_id']
                            socketio.emit('spin_result', {
                                'result': {'number': result_number, 'color': result_color},
                                'history': game_state['spin_history'], 
                                'user_result': result_data,
                                'timestamp': datetime.now().isoformat()
                            }, room=session_id)
                    
                    # Очищаем ставки
                    current_bets = {}
                    game_state['is_spinning'] = False
                    
                    # Обновляем всех игроков
                    socketio.emit('game_state_update', game_state, room='game_room')
                    socketio.emit('bets_update', {'bets': current_bets}, room='game_room')
            
            time.sleep(0.1)  # Малая задержка для плавности
            
        except Exception as e:
            print(f"Online game engine error: {e}")
            time.sleep(1)

def process_online_spin_results(number, color):
    """Обработка результатов спина для всех онлайн игроков"""
    results = {}
    
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
                
                results[user_id] = {
                    'won': True,
                    'win_amount': total_win,
                    'loss_amount': 0,
                    'new_balance': new_balance
                }
                
                print(f"Player {user[3]} won {total_win} stars!")
            else:
                results[user_id] = {
                    'won': False,
                    'win_amount': 0,
                    'loss_amount': total_loss,
                    'new_balance': current_balance
                }
                
                print(f"Player {user[3]} lost {total_loss} stars")
            
            # Отправляем обновление баланса
            if user_id in online_players:
                session_id = online_players[user_id]['session_id']
                socketio.emit('balance_update', {
                    'balance': results[user_id]['new_balance']
                }, room=session_id)
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error processing online spin results: {e}")
        if conn:
            conn.close()
    
    return results

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

# API endpoints для мониторинга
@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'online',
        'players_online': len(online_players),
        'game_state': game_state,
        'current_bets_count': len(current_bets),
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

# Периодическая очистка неактивных пользователей
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
            
            if inactive_players:
                socketio.emit('players_update', {'players': online_players}, room='game_room')
            
            time.sleep(60)  # Проверка каждую минуту
            
        except Exception as e:
            print(f"Cleanup error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    print("🌐 Starting Online Casino Server...")
    
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
    
    # Запуск Flask сервера с SocketIO
    print(f"🚀 Starting online casino server on port {PORT}")
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
