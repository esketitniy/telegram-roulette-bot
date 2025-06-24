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
}# База данных
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

# Функции БД
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
                    document.body.style.background = `linear-gradient(135deg, ${tg.themeParams.bg_color} 0%, #2a5298 100%)`;
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'app': 'telegram-casino',
        'bot_configured': bool(BOT_TOKEN)
    })

@app.route('/api/user/<int:user_id>')
def get_user_info(user_id):
    user = get_user(user_id)
    if user:
        return jsonify({
            'user_id': user[0],
            'username': user[1],
            'first_name': user[2],
            'balance': user[3],
            'total_games': user[4],
            'total_won': user[5],
            'total_lost': user[6]
        })
    return jsonify({'error': 'User not found'}), 404
    @app.route('/api/spin', methods=['POST'])
def spin_api():
    try:
        data = request.json
        user_id = data.get('user_id', 0)
        bet_type = data.get('bet_type')
        bet_amount = int(data.get('bet_amount'))
        
        # Проверка баланса
        if user_id:
            user = get_user(user_id)
            if user and user[3] < bet_amount:
                return jsonify({'error': 'Insufficient balance'}), 400
        
        # Генерация результата
        result_number = random.randint(0, 36)
        result_color = 'green' if result_number == 0 else ROULETTE_NUMBERS[result_number]
        
        # Расчет выигрыша
        won = bet_type == result_color
        winnings = 0
        
        if won:
            winnings = bet_amount * 36 if result_color == 'green' else bet_amount * 2
        
        # Сохранение игры
        if user_id:
            save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
        
        return jsonify({
            'success': True,
            'result_number': result_number,
            'result_color': result_color,
            'won': won,
            'winnings': winnings,
            'bet_amount': bet_amount
        })
    
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({'error': str(e)}), 500

# Telegram Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ В РУЛЕТКУ", web_app=WebAppInfo(url=f"{WEB_APP_URL}/game"))],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎰 Добро пожаловать в казино, {user.first_name}!\n\n💰 Ваш баланс: 1000 ⭐",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        user_data = get_user(query.from_user.id)
        balance = user_data[3] if user_data else 1000
        await query.edit_message_text(f"💰 Ваш баланс: {balance} ⭐")

def run_bot():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback))
        print("🤖 Бот запущен!")
        application.run_polling()
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")
@app.route('/game')
def game():
    html_content = """
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
            .roulette-wheel { 
                width: 200px; height: 200px; border-radius: 50%; 
                margin: 20px auto; position: relative;
                background: conic-gradient(
                    #ff0000 0deg 20deg, #000000 20deg 40deg, #ff0000 40deg 60deg, 
                    #000000 60deg 80deg, #ff0000 80deg 100deg, #00ff00 100deg 120deg,
                    #000000 120deg 140deg, #ff0000 140deg 160deg, #000000 160deg 180deg,
                    #ff0000 180deg 200deg, #000000 200deg 220deg, #ff0000 220deg 240deg,
                    #000000 240deg 260deg, #ff0000 260deg 280deg, #000000 280deg 300deg,
                    #ff0000 300deg 320deg, #000000 320deg 340deg, #ff0000 340deg 360deg
                );
                border: 5px solid gold; transition: transform 0.5s ease;
            }
            .wheel-center { 
                position: absolute; top: 50%; left: 50%; 
                transform: translate(-50%, -50%); width: 40px; height: 40px; 
                background: gold; border-radius: 50%; display: flex; 
                align-items: center; justify-content: center; 
                font-weight: bold; color: black; font-size: 16px;
            }
            .bet-buttons { 
                display: grid; grid-template-columns: 1fr 1fr; gap: 10px; 
                margin: 20px 0; max-width: 300px; margin-left: auto; margin-right: auto;
            }
            .bet-btn { 
                padding: 15px; border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold; cursor: pointer;
                transition: all 0.2s; text-align: center;
            }
            .bet-btn:active { transform: scale(0.95); }
            .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .bet-red { background: linear-gradient(45deg, #ff4444, #cc0000); color: white; }
            .bet-black { background: linear-gradient(45deg, #333333, #000000); color: white; }
            .bet-green { background: linear-gradient(45deg, #00aa00, #006600); color: white; }
            .balance, .result { 
                background: rgba(255, 255, 255, 0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0; backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .balance h3 { margin: 0; color: #FFD700; }
            .result { min-height: 60px; display: flex; align-items: center; justify-content: center; }
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(1800deg); } }
            .spinning { animation: spin 3s cubic-bezier(0.25, 0.46, 0.45, 0.94); }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            .win-animation { animation: pulse 0.5s ease-in-out 3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА</h1>
            
            <div class="balance">
                <h3>💰 Баланс: <span id="balance">1000</span> ⭐</h3>
            </div>
            
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
            
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red', 50)">🔴 КРАСНОЕ ×2<br>50⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 50)">⚫ ЧЁРНОЕ ×2<br>50⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 50)">🟢 ЗЕЛЁНОЕ ×36<br>50⭐</button>
                <button class="bet-btn bet-red" onclick="placeBet('red', 100)">🔴 КРАСНОЕ<br>100⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 100)">⚫ ЧЁРНОЕ<br>100⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 100)">🟢 ЗЕЛЁНОЕ<br>100⭐</button>
            </div>
            
            <div class="result" id="game-result">
                <p>🎯 Сделайте ставку для начала игры!</p>
            </div>
        </div>

        <script>
            let userBalance = 1000;
            let isSpinning = false;
            let userId = null;

            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                
                if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
                    userId = tg.initDataUnsafe.user.id;
                }
            }

            function placeBet(color, amount) {
                if (isSpinning) {
                    document.getElementById('game-result').innerHTML = '<p>⏳ Рулетка уже крутится!</p>';
                    return;
                }
                
                if (userBalance < amount) {
                    document.getElementById('game-result').innerHTML = '<p>❌ Недостаточно средств!</p>';
                    return;
                }
                
                isSpinning = true;
                document.getElementById('game-result').innerHTML = '<p>🎰 Крутим рулетку...</p>';
                document.getElementById('wheel').classList.add('spinning');
                
                setTimeout(function() {
                    const result = Math.floor(Math.random() * 37);
                    const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
                    const resultColor = result === 0 ? 'green' : (redNumbers.includes(result) ? 'red' : 'black');
                    const won = color === resultColor;
                    const winnings = won ? (resultColor === 'green' ? amount * 36 : amount * 2) : 0;
                    
                    document.getElementById('result-number').textContent = result;
                    document.getElementById('wheel').classList.remove('spinning');
                    
                    if (won) {
                        userBalance += winnings - amount;
                        const colorEmoji = resultColor === 'red' ? '🔴' : (resultColor === 'black' ? '⚫' : '🟢');
                        document.getElementById('game-result').innerHTML = '<p>🎉 ВЫИГРЫШ! ' + colorEmoji + ' ' + result + '<br>💰 +' + winnings + '⭐</p>';
                    } else {
                        userBalance -= amount;
                        const colorEmoji = resultColor === 'red' ? '🔴' : (resultColor === 'black' ? '⚫' : '🟢');
                        document.getElementById('game-result').innerHTML = '<p>😔 Проигрыш ' + colorEmoji + ' ' + result + '<br>📉 -' + amount + '⭐</p>';
                    }
                    
                    document.getElementById('balance').textContent = userBalance;
                    isSpinning = false;
                }, 3000);
            }
        </script>
    </body>
    </html>
    """
    return html_content
