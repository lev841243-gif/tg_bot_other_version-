import random
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from database import Database
from config import BOT_TOKEN

print('Starting telegram bot...')

# Проверяем токен бота
if BOT_TOKEN == 'your_bot_token_here':
    print("ERROR: Please set your bot token in config.py")
    exit(1)

state_storage = StateMemoryStorage()
bot = TeleBot(BOT_TOKEN, state_storage=state_storage)

# Инициализируем базу данных
try:
    db = Database()
    print("✓ Database initialized successfully")
except Exception as e:
    print(f"✗ Failed to initialize database: {e}")
    exit(1)


class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    add_word_english = State()
    add_word_russian = State()
    delete_word = State()


def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


@bot.message_handler(commands=['start', 'cards'])
def start_handler(message):
    cid = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    print(f"User {user_id} started the bot")

    # Добавляем пользователя в базу
    db.add_user(user_id, username)

    # Приветственное сообщение
    welcome_text = """Привет 👋 Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе.

У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспользуйся инструментами:

• добавить слово ➕
• удалить слово 🔙

Ну что, начнём ⬇️"""
    bot.send_message(cid, welcome_text)

    show_next_card(message)


def show_next_card(message):
    cid = message.chat.id
    user_id = message.from_user.id

    # Получаем случайное слово
    word_data = db.get_random_word(user_id)

    if not word_data:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton(Command.ADD_WORD))
        bot.send_message(cid, "Пока нет слов для изучения. Добавьте слова с помощью кнопки ниже:", reply_markup=markup)
        return

    # Получаем неправильные варианты
    wrong_options = db.get_wrong_options(word_data['word_id'], user_id, 3)

    # Создаем клавиатуру
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    # Все варианты ответов
    all_options = [word_data['english_word']] + wrong_options
    random.shuffle(all_options)

    # Добавляем кнопки вариантов
    for option in all_options:
        markup.add(types.KeyboardButton(option))

    # Добавляем служебные кнопки
    markup.add(
        types.KeyboardButton(Command.NEXT),
        types.KeyboardButton(Command.ADD_WORD),
        types.KeyboardButton(Command.DELETE_WORD)
    )

    # Сохраняем состояние
    bot.set_state(user_id, MyStates.target_word, cid)
    with bot.retrieve_data(user_id, cid) as data:
        data['target_word'] = word_data['english_word']
        data['translate_word'] = word_data['russian_translation']
        data['options'] = all_options

    # Отправляем вопрос
    question = f"Выбери перевод слова:\n🇷🇺 {word_data['russian_translation']}"
    bot.send_message(cid, question, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_handler(message):
    show_next_card(message)


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word_handler(message):
    cid = message.chat.id
    user_id = message.from_user.id

    bot.send_message(cid, "Введите слово на английском:")
    bot.set_state(user_id, MyStates.add_word_english, cid)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word_handler(message):
    cid = message.chat.id
    user_id = message.from_user.id

    bot.send_message(cid, "Введите английское слово, которое хотите удалить:")
    bot.set_state(user_id, MyStates.delete_word, cid)


@bot.message_handler(state=MyStates.add_word_english)
def process_english_word(message):
    cid = message.chat.id
    user_id = message.from_user.id

    english_word = message.text.strip()
    if not english_word:
        bot.send_message(cid, "Слово не может быть пустым. Введите слово на английском:")
        return

    with bot.retrieve_data(user_id, cid) as data:
        data['new_english_word'] = english_word

    bot.send_message(cid, "Теперь введите перевод на русском:")
    bot.set_state(user_id, MyStates.add_word_russian, cid)


@bot.message_handler(state=MyStates.add_word_russian)
@bot.message_handler(state=MyStates.add_word_russian)
def process_russian_word(message):
    cid = message.chat.id
    user_id = message.from_user.id

    russian_word = message.text.strip()
    if not russian_word:
        bot.send_message(cid, "Перевод не может быть пустым. Введите перевод на русском:")
        return

    with bot.retrieve_data(user_id, cid) as data:
        english_word = data['new_english_word']

    # Добавляем слово
    if db.add_custom_word(user_id, english_word, russian_word):
        # Получаем общее количество активных слов пользователя
        words_count = db.get_user_active_words_count(user_id)
        bot.send_message(cid,
                         f"✅ Слово '{english_word}' -> '{russian_word}' успешно добавлено!\n\n📚 Теперь вы изучаете: {words_count} слов")
    else:
        bot.send_message(cid, "❌ Не удалось добавить слово. Попробуйте еще раз.")

    bot.delete_state(user_id, cid)
    show_next_card(message)


@bot.message_handler(state=MyStates.delete_word)
@bot.message_handler(state=MyStates.delete_word)
def process_delete_word(message):
    cid = message.chat.id
    user_id = message.from_user.id
    word_to_delete = message.text.strip()

    if not word_to_delete:
        bot.send_message(cid, "Слово не может быть пустым. Введите слово для удаления:")
        return

    # Удаляем слово
    if db.deactivate_user_word(user_id, word_to_delete):
        # Получаем обновленное количество слов
        words_count = db.get_user_active_words_count(user_id)
        bot.send_message(cid, f"✅ Слово '{word_to_delete}' удалено!\n\n📚 Теперь вы изучаете: {words_count} слов")
    else:
        bot.send_message(cid, f"❌ Слово '{word_to_delete}' не найдено.")

    bot.delete_state(user_id, cid)
    show_next_card(message)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_answer(message):
    cid = message.chat.id
    user_id = message.from_user.id
    user_answer = message.text

    # Игнорируем команды
    if user_answer in [Command.NEXT, Command.ADD_WORD, Command.DELETE_WORD]:
        return

    with bot.retrieve_data(user_id, cid) as data:
        if not data or 'target_word' not in data:
            show_next_card(message)
            return

        target_word = data['target_word']
        translate_word = data['translate_word']
        options = data['options']

        if user_answer == target_word:
            # Правильный ответ
            response = f"✅ Отлично! Правильно!\n{show_target(data)}"

            # Создаем клавиатуру для следующего действия
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(
                types.KeyboardButton(Command.NEXT),
                types.KeyboardButton(Command.ADD_WORD),
                types.KeyboardButton(Command.DELETE_WORD)
            )

            # Отправляем результат с новой клавиатурой
            bot.send_message(cid, response, reply_markup=markup)

        else:
            # Неправильный ответ - предлагаем попробовать снова
            response = f"❌ Неправильно! Попробуйте ещё раз вспомнить слово:\n🇷🇺 {translate_word}"

            # Создаем ту же клавиатуру, но помечаем неправильный ответ
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

            # Обновляем кнопки, помечая неправильный ответ
            new_buttons = []
            for option in options:
                if option == user_answer:
                    # Помечаем неправильный ответ
                    new_buttons.append(types.KeyboardButton(option + ' ❌'))
                else:
                    new_buttons.append(types.KeyboardButton(option))

            # Перемешиваем кнопки заново, чтобы неправильный ответ не всегда был на одном месте
            random.shuffle(new_buttons)

            # Добавляем служебные кнопки
            for btn in new_buttons:
                markup.add(btn)

            markup.add(
                types.KeyboardButton(Command.NEXT),
                types.KeyboardButton(Command.ADD_WORD),
                types.KeyboardButton(Command.DELETE_WORD)
            )

            # Сохраняем состояние для повторной попытки
            bot.set_state(user_id, MyStates.target_word, cid)
            with bot.retrieve_data(user_id, cid) as data:
                data['target_word'] = target_word
                data['translate_word'] = translate_word
                data['options'] = [btn.text.replace(' ❌', '') for btn in new_buttons if '❌' not in btn.text]

            # Отправляем результат с обновленной клавиатурой
            bot.send_message(cid, response, reply_markup=markup)


# Добавляем фильтры состояний
bot.add_custom_filter(custom_filters.StateFilter(bot))

if __name__ == '__main__':
    print("✓ Bot starting...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        print(f"✗ Bot stopped with error: {e}")
    finally:
        db.close()
