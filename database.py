import psycopg2
from config import DB_CONFIG
import random


class Database:
    def __init__(self):
        self._connection = None
        self._connect()
        if self._is_connected():
            self._create_tables()
            self._insert_common_words()
        else:
            print("WARNING: Database connection failed")

    def _connect(self):
        """Устанавливает соединение с базой данных"""
        try:
            self._connection = psycopg2.connect(**DB_CONFIG)
            self._connection.autocommit = False
            print("✓ Connected to PostgreSQL database successfully")
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
            self._connection = None

    def _is_connected(self):
        """Проверяет, активно ли соединение"""
        return self._connection is not None and not self._connection.closed

    def _ensure_connection(self):
        """Убеждается, что соединение активно"""
        if not self._is_connected():
            self._connect()
        return self._is_connected()

    def _create_tables(self):
        """Создает таблицы в базе данных"""
        if not self._ensure_connection():
            return False

        commands = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS words (
                word_id SERIAL PRIMARY KEY,
                english_word VARCHAR(100) NOT NULL,
                russian_translation VARCHAR(100) NOT NULL,
                is_common BOOLEAN DEFAULT FALSE,
                UNIQUE(english_word, russian_translation)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_words (
                user_word_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                word_id INTEGER REFERENCES words(word_id) ON DELETE CASCADE,
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE(user_id, word_id)
            )
            """
        ]

        try:
            cursor = self._connection.cursor()
            for command in commands:
                cursor.execute(command)
            self._connection.commit()
            cursor.close()
            print("✓ Tables created successfully")
            return True
        except Exception as e:
            print(f"✗ Error creating tables: {e}")
            if self._is_connected():
                self._connection.rollback()
            return False

    def _insert_common_words(self):
        """Добавляет общие слова в базу данных"""
        if not self._ensure_connection():
            return False

        common_words = [
            ('Peace', 'Мир'),
            ('Green', 'Зеленый'),
            ('White', 'Белый'),
            ('Hello', 'Привет'),
            ('Car', 'Машина'),
            ('House', 'Дом'),
            ('Book', 'Книга'),
            ('Water', 'Вода'),
            ('Sun', 'Солнце'),
            ('Tree', 'Дерево')
        ]

        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM words WHERE is_common = TRUE")
            count = cursor.fetchone()[0]

            if count == 0:
                for eng_word, rus_word in common_words:
                    try:
                        cursor.execute(
                            """INSERT INTO words (english_word, russian_translation, is_common) 
                               VALUES (%s, %s, %s)""",
                            (eng_word, rus_word, True)
                        )
                    except psycopg2.IntegrityError:
                        # Слово уже существует, пропускаем
                        self._connection.rollback()
                        continue

                self._connection.commit()
                print(f"✓ Common words inserted successfully")
            else:
                print(f"✓ Common words already exist ({count} words)")

            cursor.close()
            return True
        except Exception as e:
            print(f"✗ Error inserting common words: {e}")
            if self._is_connected():
                self._connection.rollback()
            return False

    def add_user(self, user_id, username):
        """Добавляет пользователя в базу данных"""
        if not self._ensure_connection():
            return False

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                """INSERT INTO users (user_id, username) 
                   VALUES (%s, %s) 
                   ON CONFLICT (user_id) DO NOTHING""",
                (user_id, username)
            )
            self._connection.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"✗ Error adding user {user_id}: {e}")
            if self._is_connected():
                self._connection.rollback()
            return False

    def get_random_word(self, user_id):
        """Получает случайное слово для пользователя"""
        if not self._ensure_connection():
            return None

        try:
            cursor = self._connection.cursor()

            cursor.execute("""
                SELECT w.word_id, w.english_word, w.russian_translation 
                FROM words w
                LEFT JOIN user_words uw ON w.word_id = uw.word_id AND uw.user_id = %s
                WHERE (w.is_common = TRUE OR (uw.user_id = %s AND uw.is_active = TRUE))
                AND (uw.is_active IS NULL OR uw.is_active = TRUE)
                ORDER BY RANDOM()
                LIMIT 1
            """, (user_id, user_id))

            result = cursor.fetchone()
            cursor.close()

            if result:
                return {
                    'word_id': result[0],
                    'english_word': result[1],
                    'russian_translation': result[2]
                }
            return None

        except Exception as e:
            print(f"✗ Error getting random word: {e}")
            return None

    def get_wrong_options(self, correct_word_id, user_id, limit=3):
        """Получает неправильные варианты ответов"""
        if not self._ensure_connection():
            return []

        try:
            cursor = self._connection.cursor()
            cursor.execute("""
                SELECT english_word 
                FROM words 
                WHERE word_id != %s 
                AND (is_common = TRUE OR word_id IN (
                    SELECT word_id FROM user_words 
                    WHERE user_id = %s AND is_active = TRUE
                ))
                ORDER BY RANDOM() 
                LIMIT %s
            """, (correct_word_id, user_id, limit))

            results = cursor.fetchall()
            cursor.close()

            return [result[0] for result in results]

        except Exception as e:
            print(f"✗ Error getting wrong options: {e}")
            return []

    def add_custom_word(self, user_id, english_word, russian_translation):
        """Добавляет пользовательское слово"""
        if not self._ensure_connection():
            return False

        try:
            cursor = self._connection.cursor()

            # Сначала проверяем, существует ли уже такое слово
            cursor.execute(
                "SELECT word_id FROM words WHERE english_word = %s AND russian_translation = %s",
                (english_word, russian_translation)
            )
            existing_word = cursor.fetchone()

            if existing_word:
                word_id = existing_word[0]
                print(f"✓ Word already exists with ID: {word_id}")
            else:
                # Добавляем новое слово
                cursor.execute(
                    """INSERT INTO words (english_word, russian_translation, is_common) 
                       VALUES (%s, %s, %s) 
                       RETURNING word_id""",
                    (english_word, russian_translation, False)
                )
                word_id = cursor.fetchone()[0]
                print(f"✓ New word added with ID: {word_id}")

            # Связываем слово с пользователем
            cursor.execute(
                """INSERT INTO user_words (user_id, word_id, is_active) 
                   VALUES (%s, %s, %s) 
                   ON CONFLICT (user_id, word_id) 
                   DO UPDATE SET is_active = EXCLUDED.is_active""",
                (user_id, word_id, True)
            )

            self._connection.commit()
            cursor.close()
            print(f"✓ Word '{english_word}' successfully linked to user {user_id}")
            return True

        except Exception as e:
            print(f"✗ Error adding custom word '{english_word}': {e}")
            if self._is_connected():
                self._connection.rollback()
            return False

    def deactivate_user_word(self, user_id, english_word):
        """Деактивирует слово для пользователя"""
        if not self._ensure_connection():
            return False

        try:
            cursor = self._connection.cursor()

            cursor.execute("""
                UPDATE user_words 
                SET is_active = FALSE 
                WHERE user_id = %s AND word_id IN (
                    SELECT word_id FROM words WHERE english_word = %s
                )
            """, (user_id, english_word))

            rows_affected = cursor.rowcount
            self._connection.commit()
            cursor.close()

            if rows_affected > 0:
                print(f"✓ Word '{english_word}' deactivated for user {user_id}")
            else:
                print(f"✗ Word '{english_word}' not found for user {user_id}")

            return rows_affected > 0

        except Exception as e:
            print(f"✗ Error deactivating word: {e}")
            if self._is_connected():
                self._connection.rollback()
            return False

    def get_user_words_count(self, user_id):
        """Получает количество активных слов пользователя"""
        if not self._ensure_connection():
            return 0

        try:
            cursor = self._connection.cursor()

            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_words 
                WHERE user_id = %s AND is_active = TRUE
            """, (user_id,))

            count = cursor.fetchone()[0]
            cursor.close()

            return count

        except Exception as e:
            print(f"✗ Error getting user words count: {e}")
            return 0

    def close(self):
        """Закрывает соединение с базой данных"""
        if self._is_connected():
            self._connection.close()
            print("✓ Database connection closed")

    def get_user_active_words_count(self, user_id):
        """Получает количество активных слов пользователя (общие + персональные)"""
        if not self._ensure_connection():
            return 0

        try:
            cursor = self._connection.cursor()

            cursor.execute("""
                SELECT COUNT(*) 
                FROM words w
                LEFT JOIN user_words uw ON w.word_id = uw.word_id AND uw.user_id = %s
                WHERE (w.is_common = TRUE OR (uw.user_id = %s AND uw.is_active = TRUE))
                AND (uw.is_active IS NULL OR uw.is_active = TRUE)
            """, (user_id, user_id))

            count = cursor.fetchone()[0]
            cursor.close()

            return count

        except Exception as e:
            print(f"✗ Error getting user active words count: {e}")
            return 0