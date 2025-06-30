import asyncio
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import json
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
from bs4 import BeautifulSoup

TOKEN = "7831412310:AAFjmDiqwXpYGMWK5OXx7NVebQQtIuK1YZw"  # Замените на токен вашего бота
ADMIN_ID = "5890065908"  # Замените на ID администратора

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

STOCK_PATH = "stock.json"
USER_DATA_PATH = "user_data.json"
PRICES_PATH = "prices.json"

# --- Смайлики ---
SEEDS_EMOJI = "🌱"
GEAR_EMOJI = "⚙️"
EGG_EMOJI = "🥚"
NEW_EMOJI = "✨"
REMOVED_EMOJI = "🗑️"
CHANGED_EMOJI = "🔄"
PRICE_EMOJI = "💰"

# --- Названия стоков ---
SEEDS_STOCK_NAME = "🌱Семена"
GEAR_STOCK_NAME = "⚙️Предметы"
EGG_STOCK_NAME = "🥚Яйца"

# --- URL для парсинга ---
url = "https://vulcanvalues.com/grow-a-garden/stock"

# --- Заголовки для имитации браузера ---
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/"
}

# --- База данных цен и товаров ---
PRICES_DATA = {
    "SEEDS STOCK": {
        "Carrot": 10,
        "Strawberry": 50,
        "Blueberry": 400,
        "Tomato": 800,
        "Pineapple": "N/A",
        "Banana": 7000,
        "Caulflower": "N/A",
        "Watermelon": 2500,
        "Rafflesia": "N/A",
        "Green Apple": "N/A",
        "Avocado": "N/A",
        "Kiwi": "N/A",
        "Bell Pepper": "N/A",
        "Prickly Pear": "N/A",
        "Loquat": "N/A",
        "Feijoa": "N/A",
        "Pitcher": "N/A",
        "Sugar Apple": "N/A"
    },
    "GEAR STOCK": {
        "Watering Can": 50000,
        "Trowel": 100000,
        "Recall Wrench": 150000,
        "Basic Sprinkler": 25000,
        "Advanced Sprinkler": "N/A",
        "Godly Sprinkler": "N/A",
        "Magnifying Glass": 10000000,
        "Tanning Mirror": 1000000,
        "Master Sprinkler": "N/A",
        "Cleaning Spray": 15000000,
        "Favorite Tool": 20000000,
        "Harvest Tool": 30000000,
        "Friendship Pot": "N/A"
    },
    "EGG STOCK": {
        "Common Egg": 50000,
        "Common summer egg": "N/A",
        "Rare Summer Egg": "N/A",
        "Mythical Egg": "N/A",
        "Paradise Egg": "N/A",
        "Bee Egg": "N/A",
        "Bug Egg": 50000000
    }
}


# --- Вспомогательные функции ---
async def load_user_data():
    """Загружает данные пользователей (включая подписки) из файла."""
    if os.path.exists(USER_DATA_PATH):
        with open(USER_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def save_user_data(user_data):
    """Сохраняет данные пользователей в файл."""
    with open(USER_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)

async def get_stock(shop_name):
    """Получает текущий сток с веб-сайта и отображает его."""
    try:
        # Получаем актуальный сток с веб-сайта
        html_content = await fetch_stock_data()
        if not html_content:
            return "Не удалось получить данные о стоке."
        actual_stock = await parse_stock_data(html_content)

        # Формируем текст для отображения
        if not actual_stock or shop_name not in actual_stock:
            return "Нет данных для этого стока."

        emoji = {
            "SEEDS STOCK": SEEDS_EMOJI,
            "GEAR STOCK": GEAR_EMOJI,
            "EGG STOCK": EGG_EMOJI
        }.get(shop_name, "")

        shop_name_display = {
            "SEEDS STOCK": SEEDS_STOCK_NAME,
            "GEAR STOCK": GEAR_STOCK_NAME,
            "EGG STOCK": EGG_STOCK_NAME
        }.get(shop_name, shop_name)

        stock_text = f"<b>{emoji} {shop_name_display}:</b>\n"
        for item, amount in actual_stock[shop_name].items():
            price = PRICES_DATA.get(shop_name, {}).get(item, "Цена не найдена")
            stock_text += f"  -  {item} ({amount}) {PRICE_EMOJI}Цена: {price}\n"

        return stock_text

    except Exception as e:
        print(f"Ошибка при получении стока: {e}")
        return f"⚠️ Произошла ошибка: {e}"

async def subscribe_user(user_id: int, shop_name: str):
    """Подписывает пользователя на уведомления об изменении стока для указанного магазина."""
    user_data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {"subscriptions": []}

    if shop_name not in user_data[user_id_str]["subscriptions"]:
        user_data[user_id_str]["subscriptions"].append(shop_name)
        await save_user_data(user_data)
        return True
    return False  # Уже подписан

async def unsubscribe_user(user_id: int, shop_name: str):
    """Отписывает пользователя от уведомлений об изменении стока для указанного магазина."""
    user_data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in user_data and shop_name in user_data[user_id_str]["subscriptions"]:
        user_data[user_id_str]["subscriptions"].remove(shop_name)
        await save_user_data(user_data)
        return True
    return False  # Не был подписан

# --- Клавиатуры ---
def get_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👀Посмотреть стоки👀", callback_data="view_stock")
    builder.button(text="🔔Управление уведомлениями🔔", callback_data="manage_notifications")
    return builder.as_markup()

def get_stock_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{SEEDS_EMOJI} {SEEDS_STOCK_NAME}", callback_data="seeds_stock")
    builder.button(text=f"{GEAR_EMOJI} {GEAR_STOCK_NAME}", callback_data="gear_stock")
    builder.button(text=f"{EGG_EMOJI} {EGG_STOCK_NAME}", callback_data="egg_stock")
    builder.button(text="⬅ Назад", callback_data="back_to_main")
    return builder.as_markup()

async def get_notification_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления уведомлениями (подписка/отписка)."""
    builder = InlineKeyboardBuilder()
    user_data = await load_user_data()
    user_id_str = str(user_id)

    if user_id_str in user_data:
        subscriptions = user_data[user_id_str].get("subscriptions", [])
    else:
        subscriptions = []

    buttons = []
    for shop_name in PRICES_DATA.keys():  # Используем названия стоков из базы данных цен
        is_subscribed = shop_name in subscriptions
        if is_subscribed:
            text = f"✅ Отписаться от {shop_name}"
            callback_data = f"unsubscribe:{shop_name}"
        else:
            text = f"🔔 Подписаться на {shop_name}"
            callback_data = f"subscribe:{shop_name}"
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))

    # Разбить список кнопок на строки по одной кнопке в каждой
    keyboard = [buttons[i:i + 1] for i in range(0, len(buttons), 1)]

    keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_main")])  # Кнопка "Назад" в отдельной строке
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Обработчики команд ---
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {"subscriptions": []}  # Создаем запись о пользователе
        await save_user_data(user_data)
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nЯ бот для отслеживания стока в Grow a Garden! 🌿",
        reply_markup=get_main_keyboard()
    )

@router.callback_query(F.data == "view_stock")
async def view_stock_command(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите сток для просмотра:", reply_markup=get_stock_keyboard())
    await callback.answer()

@router.callback_query(F.data == "seeds_stock")
async def view_seed_stock(callback: types.CallbackQuery):
    text = await get_stock("SEEDS STOCK")
    await callback.message.edit_text(text, reply_markup=get_stock_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "gear_stock")
async def view_gear_stock(callback: types.CallbackQuery):
    text = await get_stock("GEAR STOCK")
    await callback.message.edit_text(text, reply_markup=get_stock_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "egg_stock")
async def view_egg_stock(callback: types.CallbackQuery):
    text = await get_stock("EGG STOCK")
    await callback.message.edit_text(text, reply_markup=get_stock_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите действие:", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "manage_notifications")
async def manage_notifications(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    keyboard = await get_notification_management_keyboard(user_id)
    await callback.message.edit_text("Управление уведомлениями:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("subscribe:"))
async def subscribe_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    shop_name = callback.data.split(":")[1]
    if await subscribe_user(user_id, shop_name):
        await callback.answer(f"Вы подписались на {shop_name}")
    else:
        await callback.answer(f"Вы уже подписаны на {shop_name}")
    keyboard = await get_notification_management_keyboard(user_id)
    await callback.message.edit_text("Управление уведомлениями:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith("unsubscribe:"))
async def unsubscribe_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    shop_name = callback.data.split(":")[1]
    if await unsubscribe_user(user_id, shop_name):
        await callback.answer(f"Вы отписались от {shop_name}")
    else:
        await callback.answer(f"Вы не были подписаны на {shop_name}")
    keyboard = await get_notification_management_keyboard(user_id)
    await callback.message.edit_text("Управление уведомлениями:", reply_markup=keyboard)

# --- Функции для отслеживания изменений файла И ОБНОВЛЕНИЯ СТОКА ---
class StockFileHandler(FileSystemEventHandler):
    def __init__(self, bot: Bot):
        super().__init__()
        self.bot = bot
        self.last_modified = time.time()
        self.last_stock_data = {}  # Инициализируем пустым словарём
        self.is_updating = False  # Флаг для предотвращения одновременных обновлений
        self.update_interval = 30  # Интервал обновления стока в секундах
        # self.directory_to_watch = os.path.dirname(os.path.abspath(STOCK_PATH))
        print(f"Начинаю отслеживание изменений и обновление стока")
        asyncio.create_task(self.periodic_update_stock())

    async def periodic_update_stock(self):
        """Периодически обновляет сток с сайта и уведомляет пользователей."""
        while True:
            try:
                await self.update_stock()
                print(f"Сток успешно обновлен. Следующее обновление через {self.update_interval} секунд.")
            except Exception as e:
                print(f"Ошибка при обновлении стока: {e}")
                if ADMIN_ID:
                    await self.bot.send_message(ADMIN_ID, f"Ошибка при обновлении стока: {e}")
            await asyncio.sleep(self.update_interval)

    async def fetch_stock_data(self):
        """Получает данные о стоке с сайта."""
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Проверить на HTTP ошибки
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к сайту: {e}")
            return None

    async def parse_stock_data(self, html_content):
        """Парсит HTML и извлекает данные о стоке."""
        if not html_content:
            return None

        soup = BeautifulSoup(html_content, "html.parser")

        shops = {}  # Изменено на словарь
        grid_blocks = soup.select("div.grid > div")

        allowed_shops = ["SEEDS STOCK", "GEAR STOCK", "EGG STOCK"]

        for block in grid_blocks:
            title_tag = block.find("h2")
            if not title_tag:
                continue
            shop_name = title_tag.get_text(strip=True)

            if shop_name not in allowed_shops:
                continue

            shops[shop_name] = {}  # Инициализируем словарь для магазина
            ul = block.find("ul")
            if not ul:
                continue
            for li in ul.find_all("li"):
                span = li.find("span")
                if not span:
                    continue
                name_part = span.find(text=True, recursive=False)
                qty_part = span.find("span", class_="text-gray-400")
                if name_part and qty_part:
                    name = name_part.strip()
                    qty_text = qty_part.get_text().strip()
                    qty = qty_text.replace('x', '').replace(' ', '')
                    try:
                        amount = int(qty) if qty.isdigit() else qty
                    except ValueError:
                        print(f"Не удалось преобразовать количество '{qty}' в число для товара '{name}' в магазине '{shop_name}'. Установлено значение 'Неизвестно'.")
                        amount = "Неизвестно"

                    shops[shop_name][name] = amount  # Добавляем в shop

        return shops  # Возвращаем словарь

    async def update_stock(self):
        """Обновляет данные о стоке и уведомляет."""
        if self.is_updating:
            print("Обновление стока уже выполняется, пропуск...")
            return

        self.is_updating = True
        try:
            html_content = await self.fetch_stock_data()
            if html_content:
                new_stock_data = await self.parse_stock_data(html_content)
                if new_stock_data:
                    # Сравниваем старые и новые данные и отправляем уведомления
                    messages_by_user = await self.compare_stock_data(self.last_stock_data, new_stock_data)
                    if messages_by_user:
                        user_data = await load_user_data()
                        for user_id_str, messages in messages_by_user.items():
                            user_id = int(user_id_str)
                            for message in messages:
                                try:
                                    await bot.send_message(user_id, message, parse_mode="HTML")
                                except Exception as e:
                                    print(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                                    if ADMIN_ID:
                                        await self.bot.send_message(ADMIN_ID, f"Не удалось отправить уведомление пользователю {user_id}: {e}")

                    self.last_stock_data = new_stock_data  # Обновляем last_stock_data

        finally:
            self.is_updating = False

    async def compare_stock_data(self, old_data, new_data):
        """Сравнивает два набора данных о стоке и возвращает сообщения об изменениях для каждого пользователя."""
        user_data = await load_user_data()
        messages_by_user = {}

        for user_id_str, user_info in user_data.items():
            user_id = int(user_id_str)
            subscriptions = user_info.get("subscriptions", [])
            user_messages = []

            for shop_name in subscriptions: # Итерируемся по названиям магазинов, на которые подписан пользователь
                if shop_name not in PRICES_DATA: # Проверяем, есть ли такой магазин в нашей базе данных цен
                    continue

                old_shop = old_data.get(shop_name, {})  # Данные из старого стока (храним внутри бота)
                new_shop = new_data.get(shop_name, {})  # Данные из нового стока (с сайта)

                shop_emoji = {"SEEDS STOCK": SEEDS_EMOJI, "GEAR STOCK": GEAR_EMOJI, "EGG STOCK": EGG_EMOJI}.get(shop_name, "")
                shop_name_display = {"SEEDS STOCK": SEEDS_STOCK_NAME, "GEAR STOCK": GEAR_STOCK_NAME, "EGG STOCK": EGG_STOCK_NAME}.get(shop_name, shop_name)
                shop_message = f"{shop_emoji} <b>{shop_name_display}:</b>\n"
                item_changes = False # Флаг для определения, есть ли изменения в магазине

                # Проверяем изменения по каждому товару в базе данных, а не в актуальном стоке
                for item_name, price in PRICES_DATA[shop_name].items():
                    old_amount = old_shop.get(item_name)
                    new_amount = new_shop.get(item_name)

                    if old_amount != new_amount:
                        item_changes = True
                        emoji = NEW_EMOJI if old_amount is None else REMOVED_EMOJI if new_amount is None else CHANGED_EMOJI
                        if old_amount is None:
                            shop_message += f"   {NEW_EMOJI} Новый товар: {item_name} ({new_amount}) {PRICE_EMOJI}Цена: {price}\n"
                        elif new_amount is None:
                            shop_message += f"   {REMOVED_EMOJI} Товар удален: {item_name}\n"
                        else:
                            shop_message += f"   {CHANGED_EMOJI} {item_name}: {old_amount} -> {new_amount} {PRICE_EMOJI}Цена: {price}\n"

                if item_changes: # Если есть изменения, добавляем сообщение в список
                    user_messages.append(shop_message)

            if user_messages:
                messages_by_user[user_id_str] = user_messages

        return messages_by_user

# --- Функции для получения данных о стоке с сайта ---
async def fetch_stock_data():
    """Получает данные о стоке с сайта."""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Проверить на HTTP ошибки
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе к сайту: {e}")
        return None

async def parse_stock_data(html_content):
    """Парсит HTML и извлекает данные о стоке."""
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, "html.parser")

    shops = {}  # Изменено на словарь
    grid_blocks = soup.select("div.grid > div")

    allowed_shops = ["SEEDS STOCK", "GEAR STOCK", "EGG STOCK"]

    for block in grid_blocks:
        title_tag = block.find("h2")
        if not title_tag:
            continue
        shop_name = title_tag.get_text(strip=True)

        if shop_name not in allowed_shops:
            continue

        shops[shop_name] = {}  # Инициализируем словарь для магазина
        ul = block.find("ul")
        if not ul:
            continue
        for li in ul.find_all("li"):
            span = li.find("span")
            if not span:
                continue
            name_part = span.find(text=True, recursive=False)
            qty_part = span.find("span", class_="text-gray-400")
            if name_part and qty_part:
                name = name_part.strip()
                qty_text = qty_part.get_text().strip()
                qty = qty_text.replace('x', '').replace(' ', '')
                try:
                    amount = int(qty) if qty.isdigit() else qty
                except ValueError:
                    print(f"Не удалось преобразовать количество '{qty}' в число для товара '{name}' в магазине '{shop_name}'. Установлено значение 'Неизвестно'.")
                    amount = "Неизвестно"

                shops[shop_name][name] = amount  # Добавляем в shop

    return shops  # Возвращаем словарь

# --- Основная функция ---
async def main():
    dp.include_router(router)

    # Создаем экземпляр StockFileHandler *до* запуска бота
    event_handler = StockFileHandler(bot)

    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        observer.stop()
        await observer.join()

if __name__ == "__main__":
    asyncio.run(main())