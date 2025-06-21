import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler

# Токен напрямую (чтобы точно работал)
BOT_TOKEN = "7427699649:AAGBHat_h0miG5MX83OOn_UiA9A9kjky1YY"

def start(update, context):
    """Команда /start - главное меню бота"""
    user = update.effective_user
    
    # Создаём кнопки
    keyboard = [
        [InlineKeyboardButton("🎰 Рулетка", callback_data="roulette")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""🎰 Добро пожаловать в Telegram Roulette!

Привет, {user.first_name}! 👋

Это казино-рулетка на Telegram Stars ⭐

🎮 Нажми на кнопки ниже:"""
    
    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def button_handler(update, context):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    query.answer()
    
    if query.data == "roulette":
        query.edit_message_text("🎰 Игра в рулетку пока в разработке!\n\nСкоро здесь будет крутая игра! 🚀")
    elif query.data == "stats":
        query.edit_message_text("📊 Статистика:\n\n• Сыграно игр: 0\n• Выиграно: 0 ⭐\n• Проиграно: 0 ⭐")
    elif query.data == "balance":
        query.edit_message_text("💰 Твой баланс: 100 ⭐\n\n(Стартовый бонус)")

def main():
    """Главная функция - запуск бота"""
    print("🤖 Запуск Telegram Roulette Bot...")
    
    # Создаём updater  
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Добавляем обработчики
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    print("✅ Бот успешно запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
