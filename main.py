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
    return render_template('index.html')

@app.route('/game')
def game():
    return render_template('game.html')

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

# Telegram Bot (упрощенная версия)
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

# Инициализация
init_db()

# Запуск бота в отдельном потоке
if BOT_TOKEN:
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

# Для Gunicorn
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
