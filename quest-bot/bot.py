#!/usr/bin/env python3
"""Личный Telegram-бот для заметок о бронях квестов.

Сам бот только открывает мини-приложение (webapp/index.html), а брони
хранятся в Telegram CloudStorage — облачном хранилище Telegram,
привязанном к твоему аккаунту и этому боту. Сервер и база данных не нужны.

Без внешних зависимостей: нужен только Python 3.8+.

Запуск:
    cp .env.example .env   # и заполни BOT_TOKEN и WEBAPP_URL
    python3 bot.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path: Path) -> None:
    """Минимальный загрузчик .env (KEY=VALUE), без перезаписи уже заданных переменных."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(Path(__file__).with_name(".env"))

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
WEBAPP_URL = os.environ.get("WEBAPP_URL", "").strip()
OWNER_ID = os.environ.get("OWNER_ID", "").strip()

if not TOKEN:
    sys.exit("Не задан BOT_TOKEN (см. .env.example)")
if not WEBAPP_URL.startswith("https://"):
    sys.exit("WEBAPP_URL должен быть https-адресом мини-приложения (см. README.md)")

API = f"https://api.telegram.org/bot{TOKEN}/"


def api(method: str, _http_timeout: int = 40, **params):
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        API + method, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_http_timeout) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        body = json.load(e)
    if not body.get("ok"):
        raise RuntimeError(f"{method}: {body.get('description')}")
    return body["result"]


def is_owner(user_id: int) -> bool:
    return not OWNER_ID or str(user_id) == OWNER_ID


def open_app_markup():
    return {
        "inline_keyboard": [
            [{"text": "📅 Открыть брони", "web_app": {"url": WEBAPP_URL}}]
        ]
    }


def setup() -> None:
    me = api("getMe")
    print(f"Бот: @{me['username']}")
    api(
        "setMyCommands",
        commands=[
            {"command": "start", "description": "Открыть брони"},
            {"command": "id", "description": "Показать мой Telegram ID"},
        ],
    )
    # Кнопка «Брони» слева от поля ввода — открывает мини-приложение в один тап.
    api(
        "setChatMenuButton",
        menu_button={"type": "web_app", "text": "Брони", "web_app": {"url": WEBAPP_URL}},
    )
    print(f"Кнопка меню указывает на {WEBAPP_URL}")
    if not OWNER_ID:
        print("OWNER_ID не задан — бот отвечает всем. Узнай свой ID командой /id.")


def handle(update: dict) -> None:
    msg = update.get("message")
    if not msg:
        return
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    text = (msg.get("text") or "").strip()

    if text.startswith("/id"):
        api("sendMessage", chat_id=chat_id, text=f"Твой Telegram ID: {user.get('id')}")
        return

    if not is_owner(user.get("id")):
        api("sendMessage", chat_id=chat_id, text="Это личный бот 🙂")
        return

    api(
        "sendMessage",
        chat_id=chat_id,
        text=(
            "🗝️ Брони квестов\n\n"
            "Нажми кнопку ниже (или «Брони» слева от поля ввода), "
            "чтобы посмотреть и добавить брони.\n"
            "Записи хранятся в облаке Telegram и видны только тебе."
        ),
        reply_markup=open_app_markup(),
    )


def main() -> None:
    setup()
    print("Бот запущен. Ctrl+C — остановить.")
    offset = 0
    while True:
        try:
            updates = api(
                "getUpdates",
                _http_timeout=60,
                offset=offset,
                timeout=50,
                allowed_updates=["message"],
            )
            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    handle(upd)
                except Exception as e:  # ошибка одного сообщения не роняет бота
                    print("Ошибка обработки:", e)
        except KeyboardInterrupt:
            print("\nОстановлен.")
            return
        except Exception as e:
            print("Ошибка сети:", e, "— повтор через 5 с")
            time.sleep(5)


if __name__ == "__main__":
    main()
