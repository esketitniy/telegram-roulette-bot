import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'https://example.com')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

Это казино-рулетка где ты можешь играть на Telegram Stars ⭐

🎮 **Как играть:**
• Нажми "🎰 Рулетка" чтобы начать игру
• Делай ставки на числа, цвета или секторы  
• Выигрывай Stars и увеличивай свой баланс!

💫 **Коэффициенты выплат:**
• Число (0-36): ×35
• Цвет (красный/чёрный): ×2  
• Чётность: ×2

Удачи! 🍀"""
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "roulette":
        await query.edit_message_text("🎰 Игра в рулетку пока в разработке!\n\nСкоро здесь будет крутая игра! 🚀")
    elif query.data == "stats":
        await query.edit_message_text("📊 Статистика:\n\n• Сыграно игр: 0\n• Выиграно: 0 ⭐\n• Проиграно: 0 ⭐")
    elif query.data == "balance":
        await query.edit_message_text("💰 Твой баланс: 100 ⭐\n\n(Стартовый бонус)")

def main():
    """Главная функция - запуск бота"""
    # Проверяем наличие токена
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.error("❌ Установите BOT_TOKEN в переменных окружения!")
        return
    
    logger.info("🤖 Запуск Telegram Roulette Bot...")
    
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    logger.info("✅ Бот успешно запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
