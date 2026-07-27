import json
import os
import re
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
    "логотип",
    "упаковк",
    "open call",
    "опенколл",
    "выставк",
    "арт",
]

DB_FILE = "seen_stroganovka.json"


def extract_contest_details(contest_url, headers):
    """Переходит на страницу конкретного конкурса и ищет дедлайн и номинации"""
    deadline = "См. на странице конкурса"
    nominations = "См. на странице конкурса"

    try:
        res = requests.get(contest_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return deadline, nominations

        soup = BeautifulSoup(res.text, "html.parser")
        page_text = soup.get_text(separator="\n", strip=True)

        # 1. Поиск сроков подачи / дедлайна с помощью регулярных выражений
        deadline_match = re.search(
            r"(прием\s+(?:заявок|работ)\s+до\s+\d{1,2}\s+[а-яА-Я]+(?:\s+\d{4})?|дедлайн[:\s]+\d{1,2}\s+[а-яА-Я]+(?:\s+\d{4})?|до\s+\d{1,2}\s+[а-яА-Я]+\s+\d{4}\s*г?\.?|\d{2}\.\d{2}\.\d{4})",
            page_text,
            re.IGNORECASE,
        )
        if deadline_match:
            deadline = deadline_match.group(0).strip()

        # 2. Поиск номинаций и категорий
        lines = [line.strip() for line in page_text.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            # Если нашли заголовок "Номинации:" или "Направления:"
            if re.search(
                r"^(номинации|направления|категории)[:\s]*$", line, re.IGNORECASE
            ):
                # Берем следующие 2-3 строки после заголовка
                next_lines = lines[i + 1 : i + 4]
                nominations = " | ".join(next_lines)
                break
            elif "номинаци" in line.lower() and len(line) < 120:
                nominations = line
                break

    except Exception as e:
        print(f"⚠️ Не удалось извлечь детали со страницы {contest_url}: {e}")

    return deadline, nominations


def send_telegram_notification(title, link, deadline, nominations):
    """Отправляет детализированную карточку конкурса в Telegram"""
    text = (
        f"🎨 <b>Строгановка: Новый конкурс для дизайнера!</b>\n\n"
        f"📌 <b>Название:</b> {title}\n"
        f"⏰ <b>Сроки подачи:</b> {deadline}\n"
        f"🏷 <b>Номинации:</b> {nominations}\n\n"
        f"🔗 <a href='{link}'>Перейти к конкурсу</a>"
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
            print(f"✅ Отправлено в Telegram: {title[:30]}...")
        else:
            print(f"❌ Ошибка отправки: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")


def load_seen_items():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_seen_items(seen_list):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f, ensure_ascii=False, indent=2)


def parse_stroganovka():
    print("🔍 Сканируем Строгановку на конкурсы...")
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

            # Заходим внутрь страницы конкурса за деталями
            deadline, nominations = extract_contest_details(full_link, headers)

            # Отправляем сообщение с подробностями
            send_telegram_notification(title, full_link, deadline, nominations)

            seen_items.append(full_link)
            new_found += 1

    save_seen_items(seen_items)

    if new_found == 0:
        print("ℹ️ Новых конкурсов не обнаружено.")


if __name__ == "__main__":
    parse_stroganovka()
