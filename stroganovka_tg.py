import json
import os
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

URL = "https://rghpu.ru/konkursy-i-granty/"
BASE_URL = "https://rghpu.ru"

# 1. ТРИГГЕРЫ КОНКУРСОВ (Если скрипт видит эти слова, он заходит внутрь страницы читать подробности)
CONTEST_TRIGGERS = [
    "конкурс", "грант", "open call", "опенколл", "выставк", 
    "арт", "фестиваль", "премия", "проект", "биеннале"
]

# 2. ЦЕЛЕВЫЕ СЛОВА ГРАФДИЗАЙНА (Ищем их в заголовке ИЛИ внутри текста самой страницы)
GD_KEYWORDS = [
    "графическ", "плакат", "иллюстрац", "айдентик", "фирменн", 
    "шрифт", "логотип", "упаковк", "полиграф", "верстк", 
    "брендинг", "типографик", "веб-дизайн", "2d"
]

# 3. ЖЕСТКИЕ СТОП-СЛОВА (Сразу бракуем ссылку, если видим это в заголовке)
STOP_WORDS = [
    "карта сайта", "партнер", "контакты", "о нас", "руководство",
    "интерьер", "промышленн", "мебель", "керамик", "стекло", 
    "текстиль", "мода", "одежд", "архитектур", "зодчеств", 
    "скульптур", "театр", "кино", "музык", "танц", "хореограф"
]

DB_FILE = "seen_stroganovka.json"


def analyze_contest_page(contest_url, headers):
    """Глубокий анализ страницы: проверяет наличие графдизайна, ищет дедлайн и номинации"""
    is_target_contest = False
    deadline = "Не указан (см. на сайте)"
    nominations = "Различные (см. на сайте)"

    try:
        res = requests.get(contest_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return False, deadline, nominations

        soup = BeautifulSoup(res.text, "html.parser")
        page_text = soup.get_text(separator="\n", strip=True)
        page_text_lower = page_text.lower()

        # 1. Проверяем, есть ли упоминания графического дизайна внутри страницы
        if any(kw in page_text_lower for kw in GD_KEYWORDS):
            is_target_contest = True

        if not is_target_contest:
            return False, deadline, nominations

        # 2. Улучшенный поиск дедлайна
        deadline_match = re.search(
            r"(?i)(?:прием\s+(?:заявок|работ)\s+до|дедлайн|срок\s+подачи)[:\s]*(\d{1,2}\s+[а-яА-Яa-zA-Z]+(?:\s+\d{4})?|\d{2}\.\d{2}\.\d{4}|\d{1,2}\s+[а-яА-Яa-zA-Z]+)",
            page_text
        )
        if deadline_match:
            # Очищаем найденную дату от лишних слов
            clean_date = re.sub(r"(?i)(прием|заявок|работ|до|дедлайн|срок|подачи|:)", "", deadline_match.group(0)).strip()
            deadline = f"до {clean_date}"

        # 3. Поиск блока с номинациями
        lines = [line.strip() for line in page_text.split("\n") if line.strip()]
        for i, line in enumerate(lines):
            if re.search(r"^(номинации|направления|категории)[:\s]*$", line, re.IGNORECASE):
                # Собираем до 4 следующих строк, пока они не станут слишком длинными
                nom_list = []
                for j in range(1, 5):
                    if i + j < len(lines) and len(lines[i + j]) < 100:
                        nom_list.append(lines[i + j].strip("-•* "))
                    else:
                        break
                if nom_list:
                    nominations = ", ".join(nom_list)
                break
            # Если номинация указана в одну строку
            elif "номинаци" in line.lower() and len(line) < 150:
                nominations = line.replace("Номинации:", "").replace("Номинация:", "").strip()
                break

    except Exception as e:
        print(f"⚠️ Ошибка сканирования внутри {contest_url}: {e}")

    return is_target_contest, deadline, nominations


def send_telegram_notification(title, link, deadline, nominations):
    text = (
        f"🎨 <b>Новый профильный конкурс!</b>\n\n"
        f"📌 <b>Название:</b> {title}\n"
        f"⏰ <b>Дедлайн:</b> {deadline}\n"
        f"🏷 <b>Номинации:</b> {nominations}\n\n"
        f"🔗 <a href='{link}'>Открыть страницу конкурса</a>"
    )

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        requests.post(api_url, json=payload, timeout=10)
        print(f"✅ Отправлено: {title[:40]}...")
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
    print("🔍 Запуск глубокого сканирования конкурсов...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Ошибка загрузки сайта: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    main_content = soup.find("main") or soup.find("div", id="content") or soup.find("body") or soup
    
    seen_items = load_seen_items()
    new_found = 0

    for a_tag in main_content.find_all("a"):
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")

        if not title or not href or href.startswith("#") or "javascript:" in href or len(title) < 5:
            continue

        full_link = urljoin(BASE_URL, href)
        title_lower = title.lower()

        # 1. Отбрасываем откровенный мусор и чужие кафедры
        if any(stop in title_lower for stop in STOP_WORDS):
            continue

        # 2. Проверяем, не отправляли ли мы это уже
        if full_link in seen_items:
            continue

        # 3. Логика принятия решения
        is_target = False
        
        # Если в заголовке прямо написано про графдизайн — берем однозначно
        if any(kw in title_lower for kw in GD_KEYWORDS):
            is_target = True
        # Если заголовок звучит как конкурс, но без конкретики — заходим внутрь читать текст
        elif any(trigger in title_lower for trigger in CONTEST_TRIGGERS):
            print(f"🕵️ Читаем внутри: {title[:50]}...")
            is_graphic_design, deadline, nominations = analyze_contest_page(full_link, headers)
            
            if is_graphic_design:
                send_telegram_notification(title, full_link, deadline, nominations)
                seen_items.append(full_link)
                new_found += 1
            
            # Даже если внутри нет графдизайна, помечаем ссылку как просмотренную, 
            # чтобы бот не сканировал её каждый раз заново
            if not is_graphic_design:
                 seen_items.append(full_link)
            
            continue # Переходим к следующей ссылке, так как эту уже обработали внутри условия

        # Если конкурс сразу подошел по заголовку (is_target == True)
        if is_target:
            print(f"🎯 Найдено по заголовку: {title[:50]}...")
            _, deadline, nominations = analyze_contest_page(full_link, headers) # Все равно идем внутрь за датами
            send_telegram_notification(title, full_link, deadline, nominations)
            seen_items.append(full_link)
            new_found += 1

    save_seen_items(seen_items)

    if new_found == 0:
        print("ℹ️ Сканирование завершено. Новых профильных конкурсов не найдено.")


if __name__ == "__main__":
    parse_stroganovka()
