# Telegram UserBot Manager

**Telegram UserBot Manager** — система для управления Telegram UserBot аккаунтами через Telegram-бота и веб-интерфейс.

## Возможности
- Авторизация Telegram UserBot аккаунтов через Telegram-бота или веб-интерфейс
- Вступление в чаты по публичным и приватным ссылкам
- Отправка сообщений в чаты и каналы
- Управление списком чатов и зависимостями между ними
- Ведение логов событий и действий
- Веб-интерфейс для добавления и удаления аккаунтов

## Структура проекта
- `index.py` — основной Telegram-бот на aiogram
- `db.py` — работа с SQLite-базой данных (сессии, чаты, логи)
- `utils.py` — асинхронные функции для работы с Telethon
- `web.py` — Flask веб-интерфейс для управления аккаунтами
- `sessions/` — папка для хранения сессий UserBot

## Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Запуск Telegram-бота
```bash
python index.py
```
- Укажите свой токен Telegram-бота в переменной `BOT_TOKEN` в `index.py`.

### 3. Запуск веб-интерфейса
```bash
python web.py
```
- Откройте [http://localhost:8080](http://localhost:8080) в браузере.

### 4. Использование команд бота
- `/login` — авторизация UserBot аккаунта
- `/status` — проверить статус UserBot
- `/join <ссылка>` — вступить в чат по ссылке
- `/send <id_чата или @username> <текст>` — отправить сообщение
- `/scan` — сканировать все чаты/каналы
- `/addchat <chat_id> <chat_name>` — добавить чат вручную
- `/listchats` — список чатов и зависимостей
- `/senddep <chat_id> <текст>` — отправить сообщение с учётом зависимостей

## Требования
- Python 3.8+
- Telegram API ID и API HASH ([my.telegram.org](https://my.telegram.org))

## Безопасность
- Не публикуйте свои session-строки, API ID, API HASH и токены бота в открытом доступе!
- Для продакшена отключите debug-режим Flask.

## Лицензия
MIT License
