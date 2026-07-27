import json
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://rghpu.ru/konkursy-i-granty/"
BASE_URL = "https://rghpu.ru"

# Добавили "научарт" в ключевые слова
KEYWORDS = [
    "дизайн",
    "научарт",
    "плакат",
    "иллюстрац",
    "конкурс",
    "грант",
    "open call",
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
            print("✅ Уведомление успешно отправлено в Telegram!")
        else:
            print(f"❌ Ошибка отправки: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")


def parse_stroganovka():
    print("🚀 ТЕСТОВЫЙ ЗАПУСК ПАРСЕРА...")
    
    # 1. Сразу отправляем тестовое сообщение, чтобы проверить связи с Telegram
    send_telegram_notification(
        "⚙️ ТЕСТ: Проверка связи с ботом прошла успешно!", 
        URL
    )

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

    for a_tag in soup.find_all("a"):
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")

        if not title or not href or href.startswith("#") or "javascript:" in href:
            continue

        full_link = urljoin(BASE_URL, href)
        title_lower = title.lower()

        # Если в ссылке или тексте есть "научарт" или другие ключевые слова
        if any(kw in title_lower for kw in KEYWORDS):
            print(f"🎯 Найден конкурс: {title}")
            send_telegram_notification(title, full_link)


if __name__ == "__main__":
    parse_stroganovka()
