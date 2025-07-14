# utils.py
import asyncio
import logging
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from typing import Optional
import random
from telethon.errors.rpcerrorlist import UserNotParticipantError

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Глобальный словарь для хранения активных клиентов UserBot {user_id: client}
userbot_clients = {}

async def get_userbot_client(user_id: int, api_id: int, api_hash: str, session_string: Optional[str] = None) -> TelegramClient:
    """
    Создает, авторизует и возвращает клиент Telethon.
    Использует кэш для уже подключенных клиентов, чтобы избежать лишних соединений.
    """
    if user_id in userbot_clients and userbot_clients[user_id].is_connected():
        return userbot_clients[user_id]

    # StringSession хранит сессию в виде строки, что идеально для сохранения в БД
    session = StringSession(session_string)
    
    # Указываем параметры устройства, чтобы сессия выглядела как с мобильного приложения
    client = TelegramClient(session, api_id, api_hash,
                            device_model="iPhone 14 Pro Max",
                            system_version="16.5.1",
                            app_version="9.6.3",
                            lang_code="en")
    
    logging.info(f"Подключение UserBot для пользователя {user_id}...")
    await client.connect()

    if not await client.is_user_authorized():
        logging.warning(f"UserBot для {user_id} не авторизован. Требуется вход.")
        # Этот клиент будет использоваться для процесса входа
        return client

    me = await client.get_me()
    logging.info(f"UserBot успешно авторизован как: {me.first_name} (@{me.username})")
    userbot_clients[user_id] = client
    return client

async def join_chat(client: TelegramClient, chat_link: str) -> tuple[bool, str]:
    """
    Вступление в чат по публичной ссылке или приватной ссылке-приглашению.
    Возвращает кортеж (успех, сообщение).
    """
    try:
        await asyncio.sleep(5)

        # Для публичных чатов — проверяем участие через GetParticipantRequest
        if 't.me/' in chat_link and not ('t.me/+' in chat_link or 't.me/joinchat/' in chat_link):
            username = chat_link.split('/')[-1]
            try:
                entity = await client.get_entity(username)
                try:
                    await client(GetParticipantRequest(entity, 'me'))
                    return True, f"ℹ️ Уже являюсь участником чата: {chat_link}"
                except UserNotParticipantError:
                    pass  # Не участник — можно вступать
            except Exception as e:
                logging.warning(f"[join_chat] Не удалось получить entity для публичного чата {chat_link}: {e}")
                pass

        # Для приватных чатов — старая логика, с подробным логированием
        if 't.me/+' in chat_link or 't.me/joinchat/' in chat_link:
            hash_code = chat_link.split('/')[-1]
            logging.info(f"[join_chat] Приватная ссылка: {chat_link}, hash_code: {hash_code}")
            try:
                result = await client(ImportChatInviteRequest(hash_code))
                logging.info(f"[join_chat] Результат ImportChatInviteRequest: {result}")
            except Exception as e:
                logging.error(f"[join_chat] Ошибка ImportChatInviteRequest для {chat_link} (hash: {hash_code}): {e}")
                raise
        else:
            entity = await client.get_entity(chat_link)
            await client(JoinChannelRequest(entity))

        msg = f"✅ Успешно вступил в чат: {chat_link}"
        logging.info(msg)
        return True, msg

    except errors.FloodWaitError as e:
        msg = f"⏳ Превышен лимит запросов. Жду {e.seconds} секунд и пробую снова."
        logging.warning(msg)
        await asyncio.sleep(e.seconds + 5)
        return await join_chat(client, chat_link)
    except errors.UserAlreadyParticipantError:
        msg = f"ℹ️ Уже являюсь участником чата: {chat_link}"
        logging.info(msg)
        return True, msg
    except (ValueError, TypeError, errors.InviteHashInvalidError) as e:
        msg = f"❌ Неверная или истекшая ссылка-приглашение: {chat_link}. Ошибка: {e}"
        logging.error(msg)
        return False, msg
    except Exception as e:
        msg = (f"❌ Не удалось вступить в чат {chat_link}. Ошибка: {e}\n"
               f"Если вы можете вступить вручную, попробуйте сгенерировать новую ссылку-приглашение, "
               f"убедитесь, что UserBot полностью авторизован, и повторите попытку через несколько минут.")
        logging.error(msg)
        return False, msg

async def send_message(client: TelegramClient, chat_entity, message: str) -> tuple[bool, str]:
    """
    Отправка сообщения в указанный чат.
    Возвращает кортеж (успех, сообщение).
    """
    try:
        # Адаптивная задержка
        await asyncio.sleep(3)
        
        await client.send_message(chat_entity, message)
        msg = f"✅ Сообщение успешно отправлено в чат {chat_entity}"
        logging.info(msg)
        return True, msg
        
    except errors.FloodWaitError as e:
        msg = f"⏳ Превышен лимит запросов при отправке. Жду {e.seconds} секунд."
        logging.warning(msg)
        await asyncio.sleep(e.seconds + 5)
        return await send_message(client, chat_entity, message) # Повтор
    except Exception as e:
        msg = f"❌ Ошибка при отправке сообщения в {chat_entity}: {e}"
        logging.error(msg)
        return False, msg

def adaptive_text(base_text: str) -> str:
    """
    Генерирует адаптивный текст для обхода антиспама (эмодзи + случайные слова).
    """
    variations = ["🔥", "✅", "📌", "💬", "👉", "🚀", "⭐", "🎯"]
    words = ["Круто", "Интересно", "Новинка", "Промо", "Выгодно", "Топ", "Рекомендуем", "Обновление"]
    emoji = random.choice(variations)
    word = random.choice(words)
    return f"{emoji} {word}! {base_text}"