import asyncio
import sqlite3
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Конфигурация
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
WEB_APP_URL = "https://ваш-домен.com"  # URL вашего веб-приложения

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
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
    
    # Таблица игр
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            stars_amount INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Функции для работы с базой данных
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
    cursor.execute('''
        UPDATE users SET balance = balance + ? WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO games (user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, bet_type, bet_amount, result_number, result_color, won, winnings))
    
    # Обновляем статистику пользователя
    if won:
        cursor.execute('''
            UPDATE users SET total_games = total_games + 1, total_won = total_won + ?
            WHERE user_id = ?
        ''', (winnings, user_id))
    else:
        cursor.execute('''
            UPDATE users SET total_games = total_games + 1, total_lost = total_lost + ?
            WHERE user_id = ?
        ''', (bet_amount, user_id))
    
    conn.commit()
    conn.close()

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    user_data = get_user(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ В РУЛЕТКУ", web_app=WebAppInfo(url=f"{WEB_APP_URL}/game"))],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton("⭐ Купить звезды", callback_data="buy_stars")],
        [InlineKeyboardButton("💸 Вывести звезды", callback_data="withdraw_stars")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
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
    elif query.data == "buy_stars":
        await buy_stars(query)
    elif query.data == "withdraw_stars":
        await withdraw_stars(query)
    elif query.data == "stats":
        await show_stats(query)

async def show_balance(query):
    user_data = get_user(query.from_user.id)
    
    text = f"""💰 ВАШ БАЛАНС 💰

💎 Текущий баланс: {user_data[3]} ⭐
🎮 Игр сыграно: {user_data[4]}
🏆 Всего выиграно: {user_data[5]} ⭐
📉 Всего проиграно: {user_data[6]} ⭐

💡 Пополните баланс для продолжения игры!"""
    
    keyboard = [
        [InlineKeyboardButton("⭐ Купить звезды", callback_data="buy_stars")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def buy_stars(query):
    text = """⭐ ПОКУПКА TELEGRAM STARS ⭐

💎 Выберите пакет:

💰 100 Stars - 99₽
💎 500 Stars - 449₽  
🔥 1000 Stars - 799₽
👑 2500 Stars - 1899₽

После покупки звезды поступят на ваш игровой баланс!"""
    
    keyboard = [
        [InlineKeyboardButton("💰 100 Stars - 99₽", callback_data="buy_100")],
        [InlineKeyboardButton("💎 500 Stars - 449₽", callback_data="buy_500")],
        [InlineKeyboardButton("🔥 1000 Stars - 799₽", callback_data="buy_1000")],
        [InlineKeyboardButton("👑 2500 Stars - 1899₽", callback_data="buy_2500")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def withdraw_stars(query):
    user_data = get_user(query.from_user.id)
    balance = user_data[3]
    
    if balance < 100:
        text = f"""💸 ВЫВОД ЗВЕЗД 💸

❌ Недостаточно средств для вывода!

Минимальная сумма вывода: 100 ⭐
Ваш баланс: {balance} ⭐

Играйте больше чтобы накопить нужную сумму!"""
    else:
        text = f"""💸 ВЫВОД ЗВЕЗД 💸

💰 Доступно к выводу: {balance} ⭐
💎 Минимальный вывод: 100 ⭐
⚡ Комиссия: 5%

Звезды поступят на ваш Telegram баланс в течение 5 минут."""
    
    keyboard = [
        [InlineKeyboardButton("💸 Вывести 100 ⭐", callback_data="withdraw_100")],
        [InlineKeyboardButton("💎 Вывести 500 ⭐", callback_data="withdraw_500")],
        [InlineKeyboardButton("🔥 Вывести всё", callback_data="withdraw_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_stats(query):
    user_data = get_user(query.from_user.id)
    
    # Получаем историю последних игр
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT bet_type, bet_amount, result_number, won, winnings, created_at
        FROM games 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 10
    ''', (query.from_user.id,))
    recent_games = cursor.fetchall()
    conn.close()
    
    win_rate = 0
    if user_data[4] > 0:  # total_games
        wins = len([g for g in recent_games if g[3]])  # won
        win_rate = (wins / min(len(recent_games), user_data[4])) * 100
    
    text = f"""📊 ВАША СТАТИСТИКА 📊

🎮 Всего игр: {user_data[4]}
🏆 Всего выиграно: {user_data[5]} ⭐
📉 Всего проиграно: {user_data[6]} ⭐
📈 Процент побед: {win_rate:.1f}%

🎯 ПОСЛЕДНИЕ ИГРЫ:"""
    
    for game in recent_games[:5]:
        bet_type, bet_amount, result_number, won, winnings, created_at = game
        status = "✅ Выигрыш" if won else "❌ Проигрыш"
        text += f"\n{status}: {bet_type} {bet_amount}⭐ → {result_number}"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    
    print("🎰 Casino Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
