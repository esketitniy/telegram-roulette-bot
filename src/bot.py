import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from config import BOT_TOKEN, WEB_APP_URL

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
        [InlineKeyboardButton("🎰 Рулетка", web_app=WebAppInfo(url=WEB_APP_URL))],
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

def main():
    """Главная функция - запуск бота"""
    # Проверяем наличие токена
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        logger.error("Пожалуйста, установите BOT_TOKEN")
        return
    
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    
    # Запускаем бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
