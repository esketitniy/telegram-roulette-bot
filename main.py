import asyncio
import json
import random
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, render_template, request, jsonify
import threading

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'https://telegram-casino.onrender.com')
PORT = int(os.getenv('PORT', 5000))

print(f"✅ Bot Token: {'НАЙДЕН' if BOT_TOKEN else 'НЕ НАЙДЕН'}")
print(f"✅ Web App URL: {WEB_APP_URL}")
print(f"✅ Port: {PORT}")

# Flask приложение
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'telegram-casino-secret')

# Рулетка - европейская версия
ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "black", 12: "red",
    13: "black", 14: "red", 15: "black", 16: "red", 17: "black", 18: "red",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "black", 30: "red",
    31: "black", 32: "red", 33: "black", 34: "red", 35: "black", 36: "red"
}

# База данных
def init_db():
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 1000,
                total_games INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0,
                total_lost INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bet_type TEXT,
                bet_amount INTEGER,
                result_number INTEGER,
                result_color TEXT,
                won BOOLEAN,
                winnings INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")

def get_user(user_id):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def create_user(user_id, username, first_name):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка создания пользователя: {e}")

def save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO games (user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, bet_type, bet_amount, result_number, result_color, won, winnings))
        
        if won:
            cursor.execute('UPDATE users SET total_games = total_games + 1, total_won = total_won + ?, balance = balance + ? WHERE user_id = ?', (winnings, winnings - bet_amount, user_id))
        else:
            cursor.execute('UPDATE users SET total_games = total_games + 1, total_lost = total_lost + ?, balance = balance - ? WHERE user_id = ?', (bet_amount, bet_amount, user_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка сохранения игры: {e}")

# Flask routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎰 Telegram Casino</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; display: flex;
                align-items: center; justify-content: center; padding: 20px;
            }
            .container { 
                text-align: center; max-width: 400px; padding: 40px 20px;
                background: rgba(255, 255, 255, 0.1); border-radius: 20px;
                backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .logo { font-size: 4em; margin-bottom: 20px; animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            h1 { font-size: 2.5em; margin-bottom: 20px; 
                 background: linear-gradient(45deg, #FFD700, #FFA500);
                 -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                 background-clip: text; }
            .subtitle { font-size: 1.2em; margin-bottom: 30px; opacity: 0.9; }
            .features { list-style: none; margin-bottom: 30px; }
            .features li { padding: 10px 0; font-size: 1.1em; }
            .cta-button { 
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4); color: white;
                padding: 15px 30px; border: none; border-radius: 50px;
                font-size: 1.2em; font-weight: bold; cursor: pointer;
                transition: transform 0.3s; text-decoration: none; display: inline-block;
                margin: 10px;
            }
            .cta-button:hover { transform: translateY(-2px); }
            .status { margin-top: 20px; padding: 10px; 
                     background: rgba(0, 255, 0, 0.2); border-radius: 10px;
                     border: 1px solid rgba(0, 255, 0, 0.3); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎰</div>
            <h1>PREMIUM CASINO</h1>
            <p class="subtitle">Премиум казино в Telegram</p>
            
            <ul class="features">
                <li>🔥 Европейская рулетка</li>
                <li>💎 Виртуальные звезды</li>
                <li>⚡ Мгновенные результаты</li>
                <li>🎯 Честная игра</li>
            </ul>
            
            <a href="/game" class="cta-button">🎮 ИГРАТЬ СЕЙЧАС</a>
            <a href="/health" class="cta-button" style="background: linear-gradient(45deg, #28a745, #20c997);">📊 СТАТУС</a>
            
            <div class="status">✅ Сервер работает</div>
        </div>

        <script>
            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                
                if (tg.themeParams.bg_color) {
                    document.body.style.background = 'linear-gradient(135deg, ' + tg.themeParams.bg_color + ' 0%, #2a5298 100%)';
                }
            }
        </script>
    </body>
    </html>
    '''
    @app.route('/game')
def game():
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎰 European Roulette</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; padding: 20px;
            }
            .container { max-width: 400px; margin: 0 auto; text-align: center; }
            
            /* Рулетка с стрелкой */
            .roulette-container { 
                position: relative; width: 220px; height: 220px; 
                margin: 20px auto; display: flex; align-items: center; justify-content: center;
            }
            .roulette-wheel { 
                width: 200px; height: 200px; border-radius: 50%; 
                position: relative;
                background: conic-gradient(
                    #00ff00 0deg 10deg,    /* 0 - зелёный */
                    #ff0000 10deg 20deg,   /* 32 - красный */
                    #000000 20deg 30deg,   /* 15 - чёрный */
                    #ff0000 30deg 40deg,   /* 19 - красный */
                    #000000 40deg 50deg,   /* 4 - чёрный */
                    #ff0000 50deg 60deg,   /* 21 - красный */
                    #000000 60deg 70deg,   /* 2 - чёрный */
                    #ff0000 70deg 80deg,   /* 25 - красный */
                    #000000 80deg 90deg,   /* 17 - чёрный */
                    #ff0000 90deg 100deg,  /* 34 - красный */
                    #000000 100deg 110deg, /* 6 - чёрный */
                    #ff0000 110deg 120deg, /* 27 - красный */
                    #000000 120deg 130deg, /* 13 - чёрный */
                    #ff0000 130deg 140deg, /* 36 - красный */
                    #000000 140deg 150deg, /* 11 - чёрный */
                    #ff0000 150deg 160deg, /* 30 - красный */
                    #000000 160deg 170deg, /* 8 - чёрный */
                    #ff0000 170deg 180deg, /* 23 - красный */
                    #000000 180deg 190deg, /* 10 - чёрный */
                    #ff0000 190deg 200deg, /* 5 - красный */
                    #000000 200deg 210deg, /* 24 - чёрный */
                    #ff0000 210deg 220deg, /* 16 - красный */
                    #000000 220deg 230deg, /* 33 - чёрный */
                    #ff0000 230deg 240deg, /* 1 - красный */
                    #000000 240deg 250deg, /* 20 - чёрный */
                    #ff0000 250deg 260deg, /* 14 - красный */
                    #000000 260deg 270deg, /* 31 - чёрный */
                    #ff0000 270deg 280deg, /* 9 - красный */
                    #000000 280deg 290deg, /* 22 - чёрный */
                    #ff0000 290deg 300deg, /* 18 - красный */
                    #000000 300deg 310deg, /* 29 - чёрный */
                    #ff0000 310deg 320deg, /* 7 - красный */
                    #000000 320deg 330deg, /* 28 - чёрный */
                    #ff0000 330deg 340deg, /* 12 - красный */
                    #000000 340deg 350deg, /* 35 - чёрный */
                    #ff0000 350deg 360deg  /* 3 - красный */
                );
                border: 5px solid gold; 
                transition: transform 4s cubic-bezier(0.25, 0.1, 0.25, 1);
                z-index: 1;
            }
            
            /* Стрелка указатель */
            .roulette-arrow { 
                position: absolute; top: -10px; left: 50%; 
                transform: translateX(-50%); width: 0; height: 0; 
                border-left: 15px solid transparent; 
                border-right: 15px solid transparent; 
                border-top: 30px solid #FFD700; 
                z-index: 10; 
                filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
            }
            
            .wheel-center { 
                position: absolute; top: 50%; left: 50%; 
                transform: translate(-50%, -50%); width: 50px; height: 50px; 
                background: radial-gradient(circle, #FFD700, #FFA500); 
                border-radius: 50%; display: flex; 
                align-items: center; justify-content: center; 
                font-weight: bold; color: black; font-size: 18px;
                border: 3px solid #fff; z-index: 5;
                box-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
            }
            
            /* Система ставок */
            .bet-system { 
                background: rgba(255, 255, 255, 0.1); padding: 20px;
                border-radius: 15px; margin: 20px 0; backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .bet-input-group { 
                display: flex; gap: 10px; margin-bottom: 15px; 
                align-items: center; justify-content: center;
            }
            .bet-input { 
                padding: 12px 15px; border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 25px; background: rgba(255, 255, 255, 0.1);
                color: white; font-size: 16px; text-align: center; width: 120px;
                backdrop-filter: blur(10px);
            }
            .bet-input:focus { 
                outline: none; border-color: #FFD700; 
                box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
            }
            .bet-input::placeholder { color: rgba(255, 255, 255, 0.6); }
            
            .bet-buttons { 
                display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; 
                margin-top: 15px;
            }
            .bet-btn { 
                padding: 15px 10px; border: none; border-radius: 12px;
                font-size: 13px; font-weight: bold; cursor: pointer;
                transition: all 0.3s; text-align: center; position: relative;
                overflow: hidden;
            }
            .bet-btn:hover { transform: translateY(-2px); }
            .bet-btn:active { transform: scale(0.95); }
            .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
            .bet-red { 
                background: linear-gradient(45deg, #ff4444, #cc0000); color: white; 
                box-shadow: 0 4px 15px rgba(255, 68, 68, 0.4);
            }
            .bet-black { 
                background: linear-gradient(45deg, #333333, #000000); color: white; 
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
            }
            .bet-green { 
                background: linear-gradient(45deg, #00aa00, #006600); color: white; 
                box-shadow: 0 4px 15px rgba(0, 170, 0, 0.4);
            }
            
            .balance, .result, .timer { 
                background: rgba(255, 255, 255, 0.1); padding: 15px;
                border-radius: 12px; margin: 15px 0; backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .balance h3 { margin: 0; color: #FFD700; font-size: 1.4em; }
            .result { min-height: 60px; display: flex; align-items: center; justify-content: center; }
            
            .timer { 
                background: linear-gradient(45deg, rgba(255, 215, 0, 0.2), rgba(255, 165, 0, 0.2));
                border: 2px solid rgba(255, 215, 0, 0.5);
            }
            .timer h4 { margin: 0; color: #FFD700; }
            .countdown { font-size: 2em; font-weight: bold; color: #fff; margin: 10px 0; }
            
            /* Анимации */
            @keyframes spin { 
                from { transform: rotate(0deg); } 
                to { transform: rotate(var(--spin-degrees, 1800deg)); } 
            }
            .spinning { animation: spin 4s cubic-bezier(0.25, 0.1, 0.25, 1); }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            .win-animation { animation: pulse 0.6s ease-in-out 3; }
            @keyframes countdown-pulse { 
                0%, 100% { transform: scale(1); color: #fff; } 
                50% { transform: scale(1.1); color: #ff4444; } 
            }
            .countdown-warning { animation: countdown-pulse 1s infinite; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА</h1>
            
            <div class="balance">
                <h3>💰 Баланс: <span id="balance">1000</span> ⭐</h3>
            </div>
            
            <div class="timer">
                <h4>⏰ До следующего спина:</h4>
                <div class="countdown" id="countdown">25</div>
            </div>
            
            <div class="roulette-container">
                <div class="roulette-arrow"></div>
                <div class="roulette-wheel" id="wheel">
                    <div class="wheel-center" id="result-number">0</div>
                </div>
            </div>
            
            <div class="bet-system">
                <h3>💸 Сделать ставку</h3>
                <div class="bet-input-group">
                    <input type="number" id="bet-amount" class="bet-input" placeholder="Сумма ⭐" min="1" max="1000" value="10">
                </div>
                <div class="bet-buttons">
                    <button class="bet-btn bet-red" onclick="placeBet('red')">🔴 КРАСНОЕ<br>×2</button>
                    <button class="bet-btn bet-black" onclick="placeBet('black')">⚫ ЧЁРНОЕ<br>×2</button>
                    <button class="bet-btn bet-green" onclick="placeBet('green')">🟢 ЗЕЛЁНОЕ<br>×36</button>
                </div>
            </div>
            
            <div class="result" id="game-result">
                <p>🎯 Введите сумму ставки и выберите цвет!</p>
            </div>
        </div>

        <script>
            let userBalance = 1000;
            let isSpinning = false;
            let userId = null;
            let currentBets = [];
            let countdownTimer = 25;
            let gameInterval;
            let countdownInterval;

            // Telegram WebApp инициализация
            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                
                if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
                    userId = tg.initDataUnsafe.user.id;
                }
            }

            // Автоматический спин каждые 25 секунд
            function startGameTimer() {
                countdownInterval = setInterval(function() {
                    countdownTimer--;
                    const countdownEl = document.getElementById('countdown');
                    countdownEl.textContent = countdownTimer;
                    
                    if (countdownTimer <= 5) {
                        countdownEl.classList.add('countdown-warning');
                    } else {
                        countdownEl.classList.remove('countdown-warning');
                    }
                    
                    if (countdownTimer <= 0) {
                        autoSpin();
                        countdownTimer = 25;
                    }
                }, 1000);
            }

            // Автоматический спин
            function autoSpin() {
                if (isSpinning) return;
                
                isSpinning = true;
                document.getElementById('game-result').innerHTML = '<p>🎰 Автоматический спин...</p>';
                
                // Генерация результата
                const result = Math.floor(Math.random() * 37);
                const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
                const resultColor = result === 0 ? 'green' : (redNumbers.includes(result) ? 'red' : 'black');
                
                // Расчет угла поворота для остановки на нужном числе
                const segmentAngle = 360 / 37;
                const targetAngle = result * segmentAngle;
                const spinRotations = 5; // 5 полных оборотов
                const finalAngle = (spinRotations * 360) + (360 - targetAngle);
                
                // Анимация вращения
                const wheel = document.getElementById('wheel');
                wheel.style.setProperty('--spin-degrees', finalAngle + 'deg');
                wheel.classList.add('spinning');
                
                setTimeout(function() {
                    processSpinResult(result, resultColor);
                    wheel.classList.remove('spinning');
                    is
