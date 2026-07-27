import json
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# Токены берутся из секретов GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://rghpu.ru/konkursy-i-granty/"
BASE_URL = "https://rghpu.ru"

KEYWORDS = [
    "дизайн",
    "графическ",
    "плакат",
    "иллюстрац",
    "айдентик",
    "фирменн",
    "шрифт",
    "конкурс",
    "грант",
    "open call",
    "опенколл",
    "выставк",
]

DB_FILE = "seen_stroganovka.json"


def send_telegram_notification(title, link):
    text = (
        f"🏛 <b>Строгановка: Новый грант / конкурс!</b>\n\n"
        f"📌 <b>Название:</b> {title}\n\n"
        f"🔗 <a href='{link}'>Открыть страницу конкурсов</a>"
    )

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        res = requests.post(api_url, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ Уведомление отправлено в Telegram!")
        else:
            print(f"❌ Ошибка отправки: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")


def load_seen_items():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_seen_items(seen_list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f, ensure_ascii=False, indent=2)


def parse_stroganovka():
    print("🔍 Проверяем сайт Строгановки...")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка загрузки сайта: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    seen_items = load_seen_items()
    new_found = 0

    for a_tag in soup.find_all("a"):
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")

        if not title or not href or href.startswith("#") or "javascript:" in href:
            continue

        full_link = urljoin(BASE_URL, href)
        if full_link in seen_items:
            continue

        title_lower = title.lower()
        if any(kw in title_lower for kw in KEYWORDS):
            print(f"🎯 Найден конкурс: {title}")
            send_telegram_notification(title, full_link)
            seen_items.append(full_link)
            new_found += 1

    save_seen_items(seen_items)
    if new_found == 0:
        print("ℹ️ Новых конкурсов пока нет.")


if __name__ == "__main__":
    parse_stroganovka()