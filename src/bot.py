import os
import json
import random
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

# Токен бота
BOT_TOKEN = "7427699649:AAGBHat_h0miG5MX83OOn_UiA9A9kjky1YY"

# Файл для сохранения данных пользователей
USER_DATA_FILE = "users_data.json"

# Рулетка: номера и цвета
ROULETTE_NUMBERS = {
    0: "🟢", 1: "🔴", 2: "⚫", 3: "🔴", 4: "⚫", 5: "🔴", 6: "⚫", 7: "🔴", 8: "⚫", 9: "🔴",
    10: "⚫", 11: "🔴", 12: "⚫", 13: "🔴", 14: "⚫", 15: "🔴", 16: "⚫", 17: "🔴", 18: "⚫",
    19: "🔴", 20: "⚫", 21: "🔴", 22: "⚫", 23: "🔴", 24: "⚫", 25: "🔴", 26: "⚫", 27: "🔴",
    28: "⚫", 29: "🔴", 30: "⚫", 31: "🔴", 32: "⚫", 33: "🔴", 34: "⚫", 35: "🔴", 36: "⚫"
}

def load_user_data():
    """Загрузка данных пользователей"""
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_user_data(data):
    """Сохранение данных пользователей"""
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_balance(user_id):
    """Получить баланс пользователя"""
    users_data = load_user_data()
    if str(user_id) not in users_data:
        # Новый пользователь - стартовые 1000 звёзд
        users_data[str(user_id)] = {
            "balance": 1000,
            "games_played": 0,
            "total_won": 0,
            "total_lost": 0
        }
        save_user_data(users_data)
    return users_data[str(user_id)]

def update_user_balance(user_id, amount, won=False):
    """Обновить баланс пользователя"""
    users_data = load_user_data()
    user_data = users_data[str(user_id)]
    
    user_data["balance"] += amount
    user_data["games_played"] += 1
    
    if won:
        user_data["total_won"] += amount
    else:
        user_data["total_lost"] += abs(amount)
    
    save_user_data(users_data)

def start(update, context):
    """Команда /start - главное меню"""
    user = update.effective_user
    user_data = get_user_balance(user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ В РУЛЕТКУ", callback_data="play_roulette")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"), 
         InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("ℹ️ Правила", callback_data="rules")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""🎰 **ДОБРО ПОЖАЛОВАТЬ В ROULETTE CASINO!** 🎰

Привет, **{user.first_name}**! 👋

🔥 **ЕВРОПЕЙСКАЯ РУЛЕТКА** 🔥
🎯 Ставки на цвета и числа
⭐ Выигрывай Telegram Stars!

💰 **Твой баланс:** {user_data['balance']} ⭐

🎮 **Готов к игре? Жми "ИГРАТЬ"!** 🚀"""
    
    update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def play_roulette_menu(update, context):
    """Меню выбора ставки"""
    query = update.callback_query
    query.answer()
    
    user_data = get_user_balance(query.from_user.id)
    balance = user_data['balance']
    
    if balance < 10:
        query.edit_message_text(
            "😔 **Недостаточно средств!**\n\n"
            "Минимальная ставка: 10 ⭐\n"
            f"Твой баланс: {balance} ⭐\n\n"
            "Получи бонус командой /bonus",
            parse_mode='Markdown'
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🔴 КРАСНОЕ (×2)", callback_data="bet_red_50")],
        [InlineKeyboardButton("⚫ ЧЁРНОЕ (×2)", callback_data="bet_black_50")],
        [InlineKeyboardButton("🟢 ЗЕЛЁНОЕ (×35)", callback_data="bet_green_50")],
        [InlineKeyboardButton("🎯 Выбрать ставку", callback_data="choose_bet")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎰 **ЕВРОПЕЙСКАЯ РУЛЕТКА** 🎰

💰 **Твой баланс:** {balance} ⭐

🎯 **СДЕЛАЙ СТАВКУ:**

🔴 **КРАСНОЕ** - коэффициент ×2
⚫ **ЧЁРНОЕ** - коэффициент ×2  
🟢 **ЗЕЛЁНОЕ (0)** - коэффициент ×35

💫 **Стандартная ставка: 50 ⭐**
🎲 **Или выбери свою ставку!**"""
    
    query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def choose_bet_amount(update, context):
    """Выбор размера ставки"""
    query = update.callback_query
    query.answer()
    
    user_data = get_user_balance(query.from_user.id)
    balance = user_data['balance']
    
    keyboard = [
        [InlineKeyboardButton("10 ⭐", callback_data="amount_10"), 
         InlineKeyboardButton("25 ⭐", callback_data="amount_25")],
        [InlineKeyboardButton("50 ⭐", callback_data="amount_50"), 
         InlineKeyboardButton("100 ⭐", callback_data="amount_100")],
        [InlineKeyboardButton("250 ⭐", callback_data="amount_250"), 
         InlineKeyboardButton("500 ⭐", callback_data="amount_500")],
        [InlineKeyboardButton("🔙 Назад", callback_data="play_roulette")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""💰 **ВЫБЕРИ РАЗМЕР СТАВКИ**

Твой баланс: **{balance} ⭐**

Выбери сумму для ставки:"""
    
    query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def select_color_for_bet(update, context):
    """Выбор цвета для ставки определённого размера"""
    query = update.callback_query
    query.answer()
    
    # Извлекаем размер ставки из callback_data
    bet_amount = int(query.data.split('_')[1])
    
    user_data = get_user_balance(query.from_user.id)
    balance = user_data['balance']
    
    if balance < bet_amount:
        query.edit_message_text(
            f"😔 **Недостаточно средств!**\n\n"
            f"Нужно: {bet_amount} ⭐\n"
            f"У тебя: {balance} ⭐",
            parse_mode='Markdown'
        )
        return
    
    keyboard = [
        [InlineKeyboardButton(f"🔴 КРАСНОЕ (×2) - {bet_amount} ⭐", callback_data=f"bet_red_{bet_amount}")],
        [InlineKeyboardButton(f"⚫ ЧЁРНОЕ (×2) - {bet_amount} ⭐", callback_data=f"bet_black_{bet_amount}")],
        [InlineKeyboardButton(f"🟢 ЗЕЛЁНОЕ (×35) - {bet_amount} ⭐", callback_data=f"bet_green_{bet_amount}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="choose_bet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎯 **СТАВКА: {bet_amount} ⭐**

Выбери цвет для ставки:

🔴 **КРАСНОЕ** - выигрыш {bet_amount * 2} ⭐
⚫ **ЧЁРНОЕ** - выигрыш {bet_amount * 2} ⭐
🟢 **ЗЕЛЁНОЕ** - выигрыш {bet_amount * 35} ⭐"""
    
    query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def spin_roulette(update, context):
    """Запуск рулетки"""
    query = update.callback_query
    query.answer()
    
    # Парсим данные ставки
    bet_data = query.data.split('_')
    bet_color = bet_data[1]  # red, black, green
    bet_amount = int(bet_data[2])
    
    user_id = query.from_user.id
    user_data = get_user_balance(user_id)
    
    if user_data['balance'] < bet_amount:
        query.edit_message_text("😔 Недостаточно средств!")
        return
    
    # Анимация вращения
    animation_text = f"""🎰 **РУЛЕТКА ВРАЩАЕТСЯ...** 🎰

Твоя ставка: **{bet_amount} ⭐** на {'🔴 КРАСНОЕ' if bet_color == 'red' else '⚫ ЧЁРНОЕ' if bet_color == 'black' else '🟢 ЗЕЛЁНОЕ'}

🔄 ⚡ 🎯 ⚡ 🔄"""
    
    query.edit_message_text(animation_text, parse_mode='Markdown')
    
    # Имитация вращения (задержка)
    time.sleep(2)
    
    # Генерируем результат
    result_number = random.randint(0, 36)
    result_color = ROULETTE_NUMBERS[result_number]
    
    # Определяем цвет словом
    if result_color == "🔴":
        color_name = "КРАСНОЕ"
        color_code = "red"
    elif result_color == "⚫":
        color_name = "ЧЁРНОЕ"  
        color_code = "black"
    else:
        color_name = "ЗЕЛЁНОЕ"
        color_code = "green"
    
    # Проверяем выигрыш
    won = False
    winnings = 0
    
    if bet_color == color_code:
        won = True
        if color_code == "green":
            winnings = bet_amount * 35
        else:
            winnings = bet_amount * 2
    
    # Обновляем баланс
    if won:
        update_user_balance(user_id, winnings - bet_amount, won=True)
        new_balance = user_data['balance'] + winnings - bet_amount
    else:
        update_user_balance(user_id, -bet_amount, won=False)
        new_balance = user_data['balance'] - bet_amount
    
    # Результат
    if won:
        result_text = f"""🎉 **ПОЗДРАВЛЯЕМ! ТЫ ВЫИГРАЛ!** 🎉

🎰 **Результат:** {result_number} {result_color} {color_name}

💰 **Твоя ставка:** {bet_amount} ⭐
🏆 **Выигрыш:** {winnings} ⭐
💵 **Прибыль:** +{winnings - bet_amount} ⭐

💰 **Новый баланс:** {new_balance} ⭐

🎊 **ОТЛИЧНАЯ ИГРА!** 🎊"""
    else:
        result_text = f"""😔 **К сожалению, проигрыш...** 😔

🎰 **Результат:** {result_number} {result_color} {color_name}

💰 **Твоя ставка:** {bet_amount} ⭐
📉 **Потеря:** -{bet_amount} ⭐

💰 **Новый баланс:** {new_balance} ⭐

🍀 **Удача в следующий раз!** 🍀"""
    
    keyboard = [
        [InlineKeyboardButton("🎰 ИГРАТЬ ЕЩЁ", callback_data="play_roulette")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats"),
         InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(result_text, reply_markup=reply_markup, parse_mode='Markdown
