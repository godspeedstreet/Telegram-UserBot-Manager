from flask import Flask, request, redirect, render_template_string
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import os

app = Flask(__name__)

ACCOUNTS_DIR = "sessions"
os.makedirs(ACCOUNTS_DIR, exist_ok=True)

# HTML шаблон
html = '''
<h2>Добавить Telegram аккаунт</h2>
<form action="/add_account" method="post">
  API ID: <input name="api_id"><br>
  API HASH: <input name="api_hash"><br>
  Номер телефона: <input name="phone"><br>
  <input type="submit" value="Авторизовать">
</form>

<h2>Доступные аккаунты</h2>
<ul>
  {% for s in sessions %}
    <li>{{ s }} <a href="/remove_account/{{s}}">Удалить</a></li>
  {% endfor %}
</ul>
'''

@app.route("/")
def index():
    sessions = [f for f in os.listdir(ACCOUNTS_DIR) if f.endswith(".session")]
    return render_template_string(html, sessions=sessions)

@app.route("/add_account", methods=["POST"])
def add_account():
    api_id = int(request.form["api_id"])
    api_hash = request.form["api_hash"]
    phone = request.form["phone"]
    
    session_path = os.path.join(ACCOUNTS_DIR, f"{phone}.session")

    async def auth():
        client = TelegramClient(session_path, api_id, api_hash)
        await client.start(phone=lambda: phone)
        await client.send_message("me", "✅ Успешная авторизация!")
        await client.disconnect()

    import asyncio
    asyncio.run(auth())

    return redirect("/")

@app.route("/remove_account/<filename>")
def remove_account(filename):
    path = os.path.join(ACCOUNTS_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, port=8080)
