# index.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from telethon import errors
from telethon.sessions import StringSession
from telethon import TelegramClient # Импортируем явно для создания временного клиента
from aiogram.filters import StateFilter

# Импортируем наши модули
from db import Database
import utils

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8072580447:AAHVGhEKrJqyT2HuwcHYHxIi9TZDeiEFpHE"  # <-- ВАЖНО: Вставьте сюда ваш токен
# -----------------

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация объектов
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

# FSM для процесса авторизации UserBot
class Login(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code = State()
    password = State()

# --- Обработчики команд управляющего бота ---

@dp.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот для управления вашим UserBot аккаунтом.\n\n"
        "Доступные команды:\n"
        "/login - Авторизация или переавторизация вашего аккаунта.\n"
        "/status - Проверить статус UserBot.\n"
        "/join <ссылка> - Вступить в чат по публичной или приватной ссылке.\n"
        "/send <id_чата> <текст> - Отправить сообщение в чат."
    )

@dp.message(Command("login"), StateFilter("*"))
async def cmd_login(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Login.api_id)
    await message.answer("Введите ваш `api_id`. Его можно получить на my.telegram.org.", parse_mode="Markdown")

@dp.message(Login.api_id)
async def process_api_id(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        return await message.answer("Неверный формат `api_id`. Введите только цифры.", parse_mode="Markdown")
    await state.update_data(api_id=int(message.text))
    await state.set_state(Login.api_hash)
    await message.answer("Отлично. Теперь введите ваш `api_hash`.", parse_mode="Markdown")

@dp.message(Login.api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        return await message.answer("`api_hash` не может быть пустым.", parse_mode="Markdown")
    await state.update_data(api_hash=message.text.strip())
    await state.set_state(Login.phone)
    await message.answer("Хорошо. Теперь введите номер телефона в международном формате (например, +79123456789).")

@dp.message(Login.phone)
async def process_phone(message: Message, state: FSMContext):
    phone_number = message.text.strip()
    if not phone_number.startswith('+'):
        return await message.answer("Неверный формат номера. Он должен начинаться с `+`.", parse_mode="Markdown")
        
    await state.update_data(phone=phone_number)
    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")

    # Создаем временный клиент для получения кода
    temp_client = TelegramClient(StringSession(), api_id, api_hash)
    await message.answer("Подключаюсь к Telegram для отправки кода...")
    
    try:
        await temp_client.connect()
        sent_code = await temp_client.send_code_request(phone_number)
        # Сохраняем phone_code_hash и временную сессию
        await state.update_data(phone_code_hash=sent_code.phone_code_hash, temp_session=temp_client.session.save())
        await state.set_state(Login.code)
        await message.answer("Код подтверждения отправлен вам в Telegram. Пожалуйста, введите его.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")
        await state.clear()
    finally:
        await temp_client.disconnect()

@dp.message(Login.code)
async def process_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    data = await state.get_data()
    
    # Используем временную сессию, сохранённую после отправки кода
    session_str = data.get('temp_session')
    temp_client = TelegramClient(StringSession(session_str), data['api_id'], data['api_hash'])
    
    try:
        await temp_client.connect()
        await temp_client.sign_in(
            phone=data['phone'],
            code=data['code'],
            phone_code_hash=data['phone_code_hash']
        )
        
        session_str_final = temp_client.session.save()
        db.save_session(message.from_user.id, data['api_id'], data['api_hash'], session_str_final)
        db.log_event("AUTH_SUCCESS", f"Пользователь {message.from_user.id} успешно авторизовался.")
        
        await message.answer("✅ Авторизация прошла успешно! Ваша сессия надежно сохранена.")
        await state.clear()
        
    except errors.SessionPasswordNeededError:
        await state.set_state(Login.password)
        await message.answer("Аккаунт защищен двухфакторной аутентификацией. Введите облачный пароль.")
    except errors.PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте снова /login.")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")
        await state.clear()
    finally:
        if temp_client.is_connected():
            await temp_client.disconnect()

@dp.message(Login.password)
async def process_password(message: Message, state: FSMContext):
    data = await state.get_data()
    temp_client = TelegramClient(StringSession(), data['api_id'], data['api_hash'])

    try:
        await temp_client.connect()
        await temp_client.sign_in(password=message.text.strip())

        session_str = temp_client.session.save()
        db.save_session(message.from_user.id, data['api_id'], data['api_hash'], session_str)
        db.log_event("AUTH_SUCCESS_2FA", f"Пользователь {message.from_user.id} успешно авторизовался с 2FA.")
        
        await message.answer("✅ Пароль принят! Авторизация успешна. Ваша сессия сохранена.")
        
    except errors.PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль. Попробуйте начать заново с /login.")
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")
    finally:
        if temp_client.is_connected():
            await temp_client.disconnect()
        await state.clear()

@dp.message(Command("status"), StateFilter("*"))
async def cmd_status(message: Message, state: FSMContext):
    await state.clear()
    session_data = db.get_session(message.from_user.id)
    if not session_data:
        return await message.answer("❌ Вы не авторизованы. Используйте /login.")
    
    api_id, api_hash, session_string = session_data
    try:
        client = await utils.get_userbot_client(message.from_user.id, api_id, api_hash, session_string)
        me = await client.get_me()
        # --- Добавляем inline-кнопку ---
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Выйти из аккаунта", callback_data="logout_userbot")]
            ]
        )
        await message.answer(
            f"✅ UserBot активен.\nАккаунт: **{me.first_name}** (`@{me.username}`)",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        await message.answer(f"❌ Не удалось проверить статус. Ошибка: {e}\n\nВозможно, нужно пройти авторизацию заново: /login")

@dp.message(Command("join"), StateFilter("*"))
async def cmd_join(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Использование: `/join <ссылка_на_чат>`", parse_mode="Markdown")
    
    chat_link = args[1]
    
    session_data = db.get_session(message.from_user.id)
    if not session_data:
        return await message.answer("❌ Сначала авторизуйтесь через /login.")
        
    api_id, api_hash, session_string = session_data
    client = await utils.get_userbot_client(message.from_user.id, api_id, api_hash, session_string)
    
    await message.answer(f"⏳ Пытаюсь вступить в `{chat_link}`...", parse_mode="Markdown")
    success, msg = await utils.join_chat(client, chat_link)
    
    event_type = "JOIN_SUCCESS" if success else "JOIN_FAIL"
    db.log_event(event_type, msg)
    
    await message.answer(msg)

@dp.message(Command("send"), StateFilter("*"))
async def cmd_send(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Использование: `/send <id_чата_или_@username> <текст сообщения>`", parse_mode="Markdown")
    
    chat_entity = parts[1]
    text_to_send = parts[2]
    
    session_data = db.get_session(message.from_user.id)
    if not session_data:
        return await message.answer("❌ Сначала авторизуйтесь через /login.")
    
    api_id, api_hash, session_string = session_data
    client = await utils.get_userbot_client(message.from_user.id, api_id, api_hash, session_string)

    await message.answer(f"⏳ Отправляю сообщение в `{chat_entity}`...", parse_mode="Markdown")
    success, msg = await utils.send_message(client, chat_entity, text_to_send)

    event_type = "SEND_SUCCESS" if success else "SEND_FAIL"
    db.log_event(event_type, msg)

    await message.answer(msg)

# === ЧАТЫ И ЗАВИСИМОСТИ ===
@dp.message(Command("scan"), StateFilter("*"))
async def cmd_scan(message: Message, state: FSMContext):
    await state.clear()
    session_data = db.get_session(message.from_user.id)
    if not session_data:
        return await message.answer("❌ Сначала авторизуйтесь через /login.")
    api_id, api_hash, session_string = session_data
    client = await utils.get_userbot_client(message.from_user.id, api_id, api_hash, session_string)
    await message.answer("⏳ Сканирую чаты и каналы...")
    try:
        dialogs = await client.get_dialogs()
        count = 0
        for d in dialogs:
            if hasattr(d.entity, 'id') and hasattr(d.entity, 'title'):
                db.add_chat(d.entity.id, d.entity.title)
                count += 1
        await message.answer(f"✅ Найдено и сохранено чатов/каналов: {count}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при сканировании: {e}")

@dp.message(Command("addchat"), StateFilter("*"))
async def cmd_addchat(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Использование: /addchat <chat_id> <chat_name>")
    try:
        chat_id = int(parts[1])
        chat_name = parts[2]
        dependency = None
        if "авито" in chat_name.lower():
            for c_id, c_name, _ in db.get_chats():
                if "прогрев" in c_name.lower():
                    dependency = c_id
                    break
        db.add_chat(chat_id, chat_name, dependency)
        await message.answer(f"Чат {chat_name} сохранён. Зависимость: {dependency}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("listchats"), StateFilter("*"))
async def cmd_listchats(message: Message, state: FSMContext):
    await state.clear()
    chats = db.get_chats()
    if not chats:
        return await message.answer("Чаты не найдены")
    text = "\n".join([f"📍 {name} ({chat_id}) -> {dep}" for chat_id, name, dep in chats])
    await message.answer(text)

# === АНТИСПАМ: задержка между отправками ===
last_sent = {}  # {chat_id: datetime}

@dp.message(Command("senddep"), StateFilter("*"))
async def cmd_senddep(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer("Использование: /senddep <chat_id> <текст>")
    try:
        chat_id = int(parts[1])
        text = parts[2]
        dep = db.get_chat_dependency(chat_id)
        session_data = db.get_session(message.from_user.id)
        if not session_data:
            return await message.answer("❌ Сначала авторизуйтесь через /login.")
        api_id, api_hash, session_string = session_data
        client = await utils.get_userbot_client(message.from_user.id, api_id, api_hash, session_string)
        results = []
        # --- Антиспам: задержка ---
        from datetime import datetime, timedelta
        now = datetime.now()
        global last_sent
        def can_send(cid):
            if cid in last_sent:
                diff = (now - last_sent[cid]).total_seconds()
                return diff >= 120
            return True
        # --- Сначала зависимый чат ---
        if dep:
            if not can_send(dep):
                wait = 120 - (now - last_sent[dep]).total_seconds()
                await message.answer(f"⏳ Жду {int(wait)} сек для зависимого чата...")
                await asyncio.sleep(wait)
            ok, msg1 = await utils.send_message(client, dep, utils.adaptive_text(text))
            last_sent[dep] = datetime.now()
            db.log_event("SENDDEP_DEP", msg1)
            results.append(f"Зависимый чат: {'✅' if ok else '❌'}")
        # --- Потом основной чат ---
        if not can_send(chat_id):
            wait = 120 - (now - last_sent[chat_id]).total_seconds()
            await message.answer(f"⏳ Жду {int(wait)} сек для основного чата...")
            await asyncio.sleep(wait)
        ok2, msg2 = await utils.send_message(client, chat_id, utils.adaptive_text(text))
        last_sent[chat_id] = datetime.now()
        db.log_event("SENDDEP_MAIN", msg2)
        results.append(f"Основной чат: {'✅' if ok2 else '❌'}")
        await message.answer("\n".join(results))
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# --- Обработчик inline-кнопки выхода ---
@dp.callback_query(lambda c: c.data == "logout_userbot")
async def logout_userbot_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    db.delete_session(user_id)
    await state.clear()
    await callback.message.edit_text("Вы вышли из аккаунта UserBot. Для повторной авторизации используйте /login.")
    await callback.answer("Сессия удалена.")

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Приветствие и список команд"),
        BotCommand(command="login", description="Авторизация UserBot"),
        BotCommand(command="status", description="Проверить статус UserBot"),
        BotCommand(command="join", description="Вступить в чат по ссылке"),
        BotCommand(command="send", description="Отправить сообщение в чат"),
        BotCommand(command="scan", description="Сканировать все чаты/каналы"),
        BotCommand(command="addchat", description="Добавить чат вручную"),
        BotCommand(command="listchats", description="Список чатов и зависимостей"),
        BotCommand(command="senddep", description="Рассылка с учётом зависимостей"),
    ]
    await bot.set_my_commands(commands)

async def main():
    """Основная функция для запуска бота."""
    logging.info("Запуск управляющего бота...")
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
    finally:
        db.close()