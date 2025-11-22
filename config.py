import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота - теперь из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', '--------------------------')

# Настройки базы данных для SQLAlchemy
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:----------@localhost:5432/english_bot_db')

# ID администраторов (ваш Telegram ID)
ADMIN_IDS = [123456789]  # Замените на ваш реальный ID

# Настройки приложения
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Дополнительные настройки
MAX_WORDS_PER_USER = 1000
SESSION_TIMEOUT = 3600  # 1 час в секундах