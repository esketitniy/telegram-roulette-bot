import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Telegram Bot Token (получить у @BotFather)
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')

# URL веб-приложения (пока локальный)
WEB_APP_URL = os.getenv('WEB_APP_URL', 'http://localhost:5000')

# Секретный ключ для Flask
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Настройки рулетки
ROULETTE_NUMBERS = list(range(37))  # 0-36

# Цвета чисел на рулетке
COLORS = {
    0: 'green',
    # Красные числа
    **{i: 'red' for i in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]},
    # Чёрные числа
    **{i: 'black' for i in [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]}
}

# Коэффициенты выплат
PAYOUTS = {
    'number': 35,      # Ставка на конкретное число
    'red': 1,          # Красное
    'black': 1,        # Чёрное
    'even': 1,         # Чётное
    'odd': 1,          # Нечётное
    'low': 1,          # 1-18
    'high': 1,         # 19-36
}

# Минимальная и максимальная ставка
MIN_BET = 1
MAX_BET = 1000

# Настройки базы данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///roulette.db')

# Настройки логирования
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
