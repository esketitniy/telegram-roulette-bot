import asyncio
import json
import random
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, render_template, request, jsonify, send_from_directory
import threading

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('REPL_URL', 'https://telegram-casino.your-username.repl.co')

# Flask приложение
app = Flask(__name__)

# Рулетка - европейская версия
ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "red", 12: "black",
    13: "red", 14: "black", 15: "red", 16: "black", 17: "red", 18: "black",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "red", 30: "black",
    31: "red", 32: "black", 33: "red", 34: "black", 35: "red", 36: "black"
}

# Инициализация базы данных
def init_db():
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

# Функции для работы с БД
def get_user(user_id):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO games (user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, bet_type, bet_amount, result_number, result_color, won, winnings))
    
    if won:
        cursor.execute('UPDATE users SET total_games = total_games + 1, total_won = total_won + ? WHERE user_id = ?', (winnings, user_id))
    else:
        cursor.execute('UPDATE users SET total_games = total_games + 1, total_lost = total_lost + ? WHERE user_id = ?', (bet_amount, user_id))
    
    conn.commit()
    conn.close()

# Flask routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Casino Landing</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(45deg, #1e3c72, #2a5298); color: white; }
            h1 { font-size: 3em; margin-bottom: 20px; }
            .emoji { font-size: 4em; }
        </style>
    </head>
    <body>
        <div class="emoji">🎰</div>
        <h1>Casino Bot</h1>
        <p>Telegram Casino Bot is running!</p>
        <p>Go to your Telegram bot to start playing!</p>
    </body>
    </html>
    '''

@app.route('/game')
def game():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎰 European Roulette</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; padding: 20px;
            }
            .container { max-width: 400px; margin: 0 auto; text-align: center; }
            .roulette-wheel { 
                width: 200px; height: 200px; border-radius: 50%; 
                margin: 20px auto; position: relative;
                background: conic-gradient(
                    #ff0000 0deg 9.73deg, #000000 9.73deg 19.46deg,
                    #ff0000 19.46deg 29.19deg, #000000 29.19deg 38.92deg,
                    #ff0000 38.92deg 48.65deg, #000000 48.65deg 58.38deg,
                    #ff0000 58.38deg 68.11deg, #000000 68.11deg 77.84deg,
                    #ff0000 77.84deg 87.57deg, #000000 87.57deg 97.30deg,
                    #00ff00 97.30deg 107.03deg,
                    #000000 107.03deg 116.76deg, #ff0000 116.76deg 126.49deg,
                    #000000 126.49deg 136.22deg, #ff0000 136.22deg 145.95deg,
                    #000000 145.95deg 155.68deg, #ff0000 155.68deg 165.41deg,
                    #000000 165.41deg 175.14deg, #ff0000 175.14deg 184.87deg,
                    #000000 184.87deg 194.60deg, #ff0000 194.60deg 204.33deg,
                    #000000 204.33deg 214.06deg, #ff0000 214.06deg 223.79deg,
                    #000000 223.79deg 233.52deg, #ff0000 233.52deg 243.25deg,
                    #000000 243.25deg 252.98deg, #ff0000 252.98deg 262.71deg,
                    #000000 262.71deg 272.44deg, #ff0000 272.44deg 282.17deg,
                    #000000 282.17deg 291.90deg, #ff0000 291.90deg 301.63deg,
                    #000000 301.63deg 311.36deg, #ff0000 311.36deg 321.09deg,
                    #000000 321.09deg 330.82deg, #ff0000 330.82deg 340.55deg,
                    #000000 340.55deg 350.28deg, #ff0000 350.28deg 360deg
                );
                border: 5px solid gold;
                animation: spin 3s ease-in-out;
            }
            .wheel-center { 
                position: absolute; top: 50%; left: 50%; 
                transform: translate(-50%, -50%);
                width: 40px; height: 40px; background: gold;
                border-radius: 50%; display: flex; align-items: center;
                justify-content: center; font-weight: bold; color: black;
            }
            .bet-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }
            .bet-btn { 
                padding: 15px; border: none; border-radius: 10px;
                font-size: 16px; font-weight: bold; cursor: pointer;
                transition: transform 0.2s;
            }
            .bet-btn:hover { transform: scale(1.05); }
            .bet-red { background: #ff4444; color: white; }
            .bet-black { background: #333; color: white; }
            .bet-green { background: #00aa00; color: white; }
            .balance { 
                background: rgba(255,255,255,0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0;
            }
            .result { 
                background: rgba(255,255,255,0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0; min-height: 60px;
            }
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(1800deg); } }
            .spinning { animation: spin 3s ease-in-out; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 European Roulette</h1>
            
            <div class="balance">
                <h3>💰 Balance: <span id="balance">1000</span> ⭐</h3>
            </div>
            
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
            
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red', 50)">🔴 RED ×2<br>50⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 50)">⚫ BLACK ×2<br>50⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 50)">🟢 GREEN ×36<br>50⭐</button>
                <button class="bet-btn bet-red" onclick="placeBet('red', 100)">🔴 RED<br>100⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 100)">⚫ BLACK<br>100⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 100)">🟢 GREEN<br>100⭐</button>
            </div>
            
            <div class="result" id="game-result">
                <p>🎯 Place your bet to start!</p>
            </div>
        </div>

        <script>
            let userBalance = 1000;
            let isSpinning = false;
            
            // Telegram WebApp initialization
            let tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            
            function updateBalance(newBalance) {
                userBalance = newBalance;
                document.getElementById('balance').textContent = newBalance;
            }
            
            function placeBet(color, amount) {
                if (isSpinning) return;
                if (userBalance < amount) {
                    document.getElementById('game-result').innerHTML = '<p>❌ Insufficient balance!</p>';
                    return;
                }
                
                isSpinning = true;
                document.getElementById('game-result').innerHTML = '<p>🎰 Spinning...</p>';
                
                // Simulate API call
                spinRoulette(color, amount);
            }
            
            function spinRoulette(betColor, betAmount) {
                // Start wheel animation
                const wheel = document.getElementById('wheel');
                wheel.classList.add('spinning');
                
                setTimeout(() => {
                    // Generate result
                    const resultNumber = Math.floor(Math.random() * 37); // 0-36
                    const resultColor = getNumberColor(resultNumber);
                    
                    // Update wheel center
                    document.getElementById('result-number').textContent = resultNumber;
                    
                    // Calculate winnings
                    const won = betColor === resultColor;
                    let winnings = 0;
                    
                    if (won) {
                        if (resultColor === 'green') {
                            winnings = betAmount * 36;
                        } else {
                            winnings = betAmount * 2;
                        }
                        updateBalance(userBalance + winnings - betAmount);
                    } else {
                        updateBalance(userBalance - betAmount);
                    }
                    
                    // Show result
                    const colorEmoji = resultColor === 'red' ? '🔴' : resultColor === 'black' ? '⚫' : '🟢';
                    const resultText = won 
                        ? `🎉 YOU WON! ${colorEmoji} ${resultNumber}<br>Winnings: ${winnings}⭐` 
                        : `😔 You lost! ${colorEmoji} ${resultNumber}<br>Loss: ${betAmount}⭐`;
                    
                    document.getElementById('game-result').
document.getElementById('game-result').innerHTML = `<p>${resultText}</p>`;
                    
                    wheel.classList.remove('spinning');
                    isSpinning = false;
                }, 3000);
            }
            
            function getNumberColor(number) {
                if (number === 0) return 'green';
                const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
                return redNumbers.includes(number) ? 'red' : 'black';
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api/spin', methods=['POST'])
def spin_api():
    try:
        data = request.json
        user_id = data.get('user_id', 0)
        bet_type = data.get('bet_type')
        bet_amount = data.get('bet_amount')
        
        # Generate result
        result_number = random.randint(0, 36)
        result_color = 'green' if result_number == 0 else ROULETTE_NUMBERS[result_number]
        
        # Calculate winnings
        won = bet_type == result_color
        winnings = 0
        
        if won:
            if result_color == 'green':
                winnings = bet_amount * 36
            else:
                winnings = bet_amount * 2
        
        # Save game (if user exists)
        if user_id:
            save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
            if won:
                update_balance(user_id, winnings - bet_amount)
            else:
                update_balance(user_id, -bet_amount)
        
        return jsonify({
            'result_number': result_number,
            'result_color': result_color,
            'won': won,
            'winnings': winnings
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Telegram Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    user_data = get_user(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ В РУЛЕТКУ", web_app=WebAppInfo(url=f"{WEB_APP_URL}/game"))],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ Правила", callback_data="rules")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""🎰 ДОБРО ПОЖАЛОВАТЬ В PREMIUM CASINO! 🎰

Привет, {user.first_name}! 👋

🔥 ЕВРОПЕЙСКАЯ РУЛЕТКА 🔥
💎 Играй за Telegram Stars
⚡ Мгновенные выплаты
🎯 Честные шансы

💰 Твой баланс: {user_data[3] if user_data else 1000} ⭐

🚀 Нажми "ИГРАТЬ" для запуска!"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        await show_balance(query)
    elif query.data == "stats":
        await show_stats(query)
    elif query.data == "rules":
        await show_rules(query)
    elif query.data == "back":
        await back_to_menu(query)

async def show_balance(query):
    user_data = get_user(query.from_user.id)
    
    text = f"""💰 ВАШ БАЛАНС 💰

💎 Текущий баланс: {user_data[3]} ⭐
🎮 Игр сыграно: {user_data[4]}
🏆 Всего выиграно: {user_data[5]} ⭐
📉 Всего проиграно: {user_data[6]} ⭐

💡 Играйте ответственно!"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_stats(query):
    user_data = get_user(query.from_user.id)
    
    profit_loss = user_data[5] - user_data[6]  # total_won - total_lost
    profit_emoji = "📈" if profit_loss >= 0 else "📉"
    
    text = f"""📊 ВАША СТАТИСТИКА 📊

🎮 Всего игр: {user_data[4]}
🏆 Всего выиграно: {user_data[5]} ⭐
📉 Всего проиграно: {user_data[6]} ⭐
{profit_emoji} Общий результат: {profit_loss:+d} ⭐
💰 Текущий баланс: {user_data[3]} ⭐

🎯 Удачи в следующих играх! 🍀"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_rules(query):
    text = """ℹ️ ПРАВИЛА ЕВРОПЕЙСКОЙ РУЛЕТКИ ℹ️

🎯 ЧИСЛА: от 0 до 36

🔴 КРАСНЫЕ: 1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36
⚫ ЧЁРНЫЕ: 2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35
🟢 ЗЕЛЁНОЕ: только 0

💰 КОЭФФИЦИЕНТЫ:
🔴⚫ Красное/Чёрное: ×2 (48.65% шанс)
🟢 Зелёное (0): ×36 (2.70% шанс)

🎮 Минимальная ставка: 10 ⭐
💎 Максимальная ставка: 1000 ⭐

🍀 Удачи в игре!"""
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def back_to_menu(query):
    user_data = get_user(query.from_user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ В РУЛЕТКУ", web_app=WebAppInfo(url=f"{WEB_APP_URL}/game"))],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ Правила", callback_data="rules")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎰 PREMIUM CASINO 🎰

💰 Ваш баланс: {user_data[3]} ⭐

🎮 Выберите действие:"""
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# Bot setup
def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🤖 Telegram Bot запущен!")
    application.run_polling()

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def main():
    init_db()
    
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("🌐 Flask сервер запущен на порту 5000")
    
    # Запускаем бота
    run_bot()

if __name__ == '__main__':
    main()
