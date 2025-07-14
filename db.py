# db.py
import sqlite3
import threading
import time

class Database:
    """Класс для управления базой данных SQLite."""
    def __init__(self, db_path='userbot.db'):
        # check_same_thread=False необходимо для работы с асинхронными фреймворками
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        """Инициализация таблиц в базе данных."""
        with self.lock:
            cursor = self.conn.cursor()
            # Таблица для хранения данных сессий UserBot
            # user_id - это ID пользователя в управляющем боте, чтобы можно было иметь несколько аккаунтов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    api_id INTEGER NOT NULL,
                    api_hash TEXT NOT NULL,
                    session_string TEXT UNIQUE NOT NULL
                )
            ''')
            # Таблица для отчетов / логов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            ''')
            # Таблица для чатов и зависимостей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_name TEXT NOT NULL,
                    dependency_chat_id INTEGER,
                    UNIQUE(chat_id)
                )
            ''')
            self.conn.commit()

    def log_event(self, event_type: str, message: str):
        """Запись события в лог."""
        with self.lock:
            timestamp = int(time.time())
            self.conn.execute(
                "INSERT INTO logs (timestamp, event_type, message) VALUES (?, ?, ?)",
                (timestamp, event_type, message)
            )
            self.conn.commit()

    def save_session(self, user_id: int, api_id: int, api_hash: str, session_string: str):
        """Сохранение или обновление данных сессии UserBot."""
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO sessions (user_id, api_id, api_hash, session_string) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    api_id=excluded.api_id,
                    api_hash=excluded.api_hash,
                    session_string=excluded.session_string
                """,
                (user_id, api_id, api_hash, session_string)
            )
            self.conn.commit()

    def get_session(self, user_id: int):
        """Получение данных сессии по user_id управляющего бота."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT api_id, api_hash, session_string FROM sessions WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

    def add_chat(self, chat_id: int, chat_name: str, dependency_chat_id: int = None):
        """Добавить или обновить чат и его зависимость."""
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO chats (chat_id, chat_name, dependency_chat_id)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_name=excluded.chat_name,
                    dependency_chat_id=excluded.dependency_chat_id
                """,
                (chat_id, chat_name, dependency_chat_id)
            )
            self.conn.commit()

    def get_chats(self):
        """Получить список всех чатов и их зависимостей."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT chat_id, chat_name, dependency_chat_id FROM chats")
            return cursor.fetchall()

    def get_chat_dependency(self, chat_id: int):
        """Получить зависимость для чата."""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT dependency_chat_id FROM chats WHERE chat_id=?", (chat_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_chat_dependency(self, chat_id: int, dependency_chat_id: int):
        """Установить/обновить зависимость для чата."""
        with self.lock:
            self.conn.execute(
                "UPDATE chats SET dependency_chat_id=? WHERE chat_id=?",
                (dependency_chat_id, chat_id)
            )
            self.conn.commit()

    def delete_session(self, user_id: int):
        """Удалить сессию UserBot по user_id управляющего бота."""
        with self.lock:
            self.conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            self.conn.commit()

    def close(self):
        """Закрытие соединения с базой данных."""
        if self.conn:
            self.conn.close()