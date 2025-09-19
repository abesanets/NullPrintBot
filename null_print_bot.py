import telebot
from telebot import types
from PIL import Image
from io import BytesIO
import time
import json
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
from telebot.types import Message

TOKEN = 'your-token'
bot = telebot.TeleBot(TOKEN)

def reset_daily_limits():
    while True:
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            users = load_users()
            for uid, data in users.items():
                if not data.get("is_premium", False):
                    data["daily_left"] = data.get("daily_limit", 5)
            save_users(users)
            time.sleep(60)  # ждём минуту, чтобы не сбросилось снова
        time.sleep(10)  # проверяем каждые 10 секунд

# Внизу перед bot.polling()
threading.Thread(target=reset_daily_limits, daemon=True).start()


TOKEN = '7985933208:AAFQJNFxobbwq-Tpurwmpyt-9lhuOSjJTlk'
bot = telebot.TeleBot(TOKEN)

user_sessions = {}
PARAMS_FILE = "params.json"

# Загрузка параметров
if os.path.exists(PARAMS_FILE):
    with open(PARAMS_FILE, "r") as f:
        saved_params = json.load(f)
else:
    saved_params = {}

def save_user_params(chat_id, params):
    saved_params[str(chat_id)] = params
    with open(PARAMS_FILE, "w") as f:
        json.dump(saved_params, f)


USERS_FILE = 'users.json'

# Загрузка базы пользователей из файла
def load_users():
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Сохранение базы пользователей в файл
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# Добавление или обновление пользователя в базе
def add_or_update_user(user):
    users = load_users()
    chat_id = str(user.id)
    now_date = datetime.utcnow().strftime('%Y-%m-%d')


    if chat_id in users:
        i = 1+1
    else:
        users[chat_id] = {
            "username": user.username or "",
            "first_name": user.first_name or "",
            "first_seen": now_date,
            "generate_count": 0,
            "is_premium": False,
            "daily_left": 5,
            "daily_limit": 5
        }

    save_users(users)


#region обновление лимитов
ADMINS = ["5682825129"]
SETTINGS_FILE = 'settings.json'

# Создание settings.json если нет
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump({"wait_time": 60}, f)

def load_settings():
    with open(SETTINGS_FILE, 'r') as f:
        return json.load(f)

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

# Хендлер на /setlimits (только для админа):
@bot.message_handler(commands=['setlimits'])
def set_limits_start(message):
    if str(message.chat.id) not in ADMINS:
        bot.send_message(message.chat.id, "⛔ У вас нет прав для этой команды.")
        return
    bot.send_message(message.chat.id, "🔢 Введите новое количество ежедневных генераций для всех пользователей:")
    bot.register_next_step_handler(message, process_new_limit)

def process_new_limit(message):
    try:
        new_limit = int(message.text)
        message.chat.new_limit = new_limit
        bot.send_message(message.chat.id, "⏱ Введите новое время ожидания (в секундах):")
        bot.register_next_step_handler(message, process_new_wait_time, new_limit)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите число.")
        bot.register_next_step_handler(message, process_new_limit)

def process_new_wait_time(message, new_limit):
    try:
        new_wait = int(message.text)
        settings = load_settings()
        settings['wait_time'] = new_wait
        save_settings(settings)

        # Обновим daily_limit у всех пользователей
        users = load_users()
        for user_id in users:
            old_limit = users[user_id].get("daily_limit")
            users[user_id]['daily_limit'] = new_limit
            users[user_id]['daily_left'] = new_limit + (users[user_id].get("daily_left") - old_limit)
        save_users(users)

        bot.send_message(message.chat.id, "📢 Хотите разослать сообщение пользователям о новых лимитах? (да/нет)")
        bot.register_next_step_handler(message, ask_broadcast_confirm, new_limit, new_wait)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число (секунды).")
        bot.register_next_step_handler(message, process_new_wait_time, new_limit)

def ask_broadcast_confirm(message, new_limit, new_wait):
    if message.text.lower() in ['да', 'yes']:
        bot.send_message(message.chat.id, "📝 Введите текст уведомления. В конце будут добавлены лимиты автоматически.")
        bot.register_next_step_handler(message, process_broadcast_text, new_limit, new_wait)
    else:
        bot.send_message(message.chat.id, "✅ Лимиты обновлены без уведомления.")

def process_broadcast_text(message, new_limit, new_wait):
    users = load_users()
    base_text = message.text
    full_message = f"{base_text}\n\n📈 Новый лимит: {new_limit} в день\n⏳ Новое ожидание: {new_wait} сек"

    for user_id in users:
        try:
            bot.send_message(user_id, full_message)
        except:
            continue
    bot.send_message(message.chat.id, "✅ Лимиты обновлены и сообщение разослано всем пользователям.")

#endregion 



# В твоём хэндлере /start меняем так:
@bot.message_handler(commands=['start', 'create'])
def start(message):
    add_or_update_user(message.from_user)
    bot.send_message(message.chat.id, "👋 Привет! Отправь изображение, которое будет *основой*.", parse_mode="Markdown")
    user_sessions[message.chat.id] = {}

@bot.message_handler(content_types=['photo', 'document'])
def handle_image(message):
    chat_id = message.chat.id

    # Загрузка изображения
    if message.content_type == 'photo':
        file_info = bot.get_file(message.photo[-1].file_id)
        file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(file)).convert('RGB')
        image_type = 'photo'
    elif message.content_type == 'document':
        if not message.document.mime_type.startswith("image/"):
            bot.send_message(chat_id, "❗ Пожалуйста, отправь изображение или фото-файл.")
            return
        file_info = bot.get_file(message.document.file_id)
        file = bot.download_file(file_info.file_path)
        image = Image.open(BytesIO(file)).convert('RGB')
        image_type = 'document'
    else:
        bot.send_message(chat_id, "❗ Не удалось обработать файл.")
        return

    # Автосоздание сессии, если её нет
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {}

    # Если и base и overlay уже есть — начинаем заново
    if 'base' in user_sessions[chat_id] and 'overlay' in user_sessions[chat_id]:
        user_sessions[chat_id] = {}

    # Сохраняем base, если его ещё нет
    if 'base' not in user_sessions[chat_id]:
        user_sessions[chat_id]['base'] = image
        user_sessions[chat_id]['base_type'] = image_type
        bot.send_message(chat_id, "✅ Базовое изображение сохранено.\nТеперь отправь принт для наложения (чёрно-белый).")
    else:
        # Принт получен
        user_sessions[chat_id]['overlay'] = image.convert('L')
        user_id_str = str(chat_id)

        if user_id_str in saved_params:
            params = saved_params[user_id_str]
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add("✅ Да", "🔁 Ввести новые")
            bot.send_message(
                chat_id,
                f"❓ Использовать прошлые настройки?\nКанал: {params['channel']}, Дельта: {params['delta']}, Порог: {params['threshold']}",
                reply_markup=keyboard
            )
            bot.register_next_step_handler(message, use_old_or_new_params)
        else:
            ask_channel(message)




def use_old_or_new_params(message):
    if message.text == "✅ Да":
        apply_overlay_with_params(message.chat.id, saved_params[str(message.chat.id)])
    else:
        ask_channel(message)

def ask_channel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("R", "G", "B", "All")
    bot.send_message(message.chat.id,
                     "🔴 *Канал* — какой цветовой канал будет изменяться.\n"
                     "🟥 R — Красный, 🟩 G — Зелёный, 🟦 B — Синий, 🌈 All — Все сразу.\n\n"
                     "Выберите один из них:",
                     parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, save_channel)

def save_channel(message):
    chat_id = message.chat.id
    user_sessions[chat_id]['params'] = {'channel': message.text.upper()}
    bot.send_message(chat_id,
                     "🔼 *Дельта* — насколько увеличить значение цвета в выбранном канале (обычно 5–30).\n"
                     "Например: `15`",
                     parse_mode="Markdown")
    bot.register_next_step_handler(message, save_delta)

def save_delta(message):
    chat_id = message.chat.id
    try:
        user_sessions[chat_id]['params']['delta'] = int(message.text)
        bot.send_message(chat_id,
                         "⚪ *Порог (Threshold)* — уровень яркости пикселя принта (от 0 до 255), выше которого будет применено изменение.\n"
                         "Обычно: `128` или `100` — значит, чем светлее пиксель, тем больше шанс наложения.",
                         parse_mode="Markdown")
        bot.register_next_step_handler(message, save_threshold)
    except:
        bot.send_message(chat_id, "❗ Пожалуйста, введите число для дельты.")
        bot.register_next_step_handler(message, save_delta)

def save_threshold(message):
    chat_id = message.chat.id
    try:
        user_sessions[chat_id]['params']['threshold'] = int(message.text)
        params = user_sessions[chat_id]['params']
        save_user_params(chat_id, params)
        apply_overlay_with_params(chat_id, params)
    except:
        bot.send_message(chat_id, "❗ Порог должен быть числом от 0 до 255.")
        bot.register_next_step_handler(message, save_threshold)

def apply_overlay_with_params(chat_id, params):
    import json

    def load_settings():
        with open("settings.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def get_wait_time():
        return load_settings().get("wait_time")
    
    wait_time = int(get_wait_time())



    
    users = load_users()
    chat_id_str = str(chat_id)
    user_data = users.get(chat_id_str, {})

    if not isinstance(user_data, dict):
        print(f"❌ Ошибка: user_data для {chat_id_str} — это не словарь: {user_data}")
        return


    # Проверка если не премиум
    if not user_data.get('is_premium', False):
        # Проверка на оставшиеся генерации
        if user_data.get('daily_left', 0) <= 0:
            bot.send_message(chat_id, "🚫 У вас закончились генерации на сегодня. Попробуйте завтра или получите /premium.")
            return

        # Эмуляция задержки
        bot.send_message(chat_id, f"⌛ Вы поставлены в очередь. Примерное время ожидания: {wait_time} секунд.")
        time.sleep(wait_time - 1)

        # Уменьшаем генерации только обычному юзеру
        user_data["daily_left"] -= 1
        save_users(users)


    try:
        channel = params['channel']
        delta = params['delta']
        threshold = params['threshold']
        base = user_sessions[chat_id]['base'].copy()
        overlay = user_sessions[chat_id]['overlay'].resize(base.size)
        pixels = base.load()
        overlay_pixels = overlay.load()
        w, h = base.size

        for x in range(w):
            for y in range(h):
                if overlay_pixels[x, y] > threshold:
                    r, g, b = pixels[x, y]
                    if channel == 'R':
                        r = min(255, r + delta)
                    elif channel == 'G':
                        g = min(255, g + delta)
                    elif channel == 'B':
                        b = min(255, b + delta)
                    elif channel in ('ALL', 'A'):
                        r = min(255, r + delta)
                        g = min(255, g + delta)
                        b = min(255, b + delta)
                    pixels[x, y] = (r, g, b)

        bio = BytesIO()
        bio.name = 'result.png'
        base.save(bio, 'PNG')
        bio.seek(0)
        base_type = user_sessions[chat_id].get('base_type', 'photo')
        
        # Увеличиваем счётчик 
        users = load_users()
        users[str(chat_id)]['generate_count'] += 1
        save_users(users)
        
        if base_type == 'document':
            bot.send_document(chat_id, bio, caption="✅ Готово! Вот изображение с наложенным принтом.")
        else:
            bot.send_photo(chat_id, photo=bio, caption="✅ Готово! Вот изображение с наложенным принтом.")

        


    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка: {e}")


@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "*🤖 Null Print Bot — инструкция по использованию:*\n\n"
        "Этот бот накладывает *невидимый принт (водяной знак)* на изображение.\n"
        "Работает автоматически, всё просто!\n\n"
        
        "*📌 Как пользоваться:*\n"
        "1️⃣ Отправь основное изображение — можно просто фото или *файл (document)*, если хочешь сохранить качество.\n"
        "2️⃣ Затем отправь изображение-принт (ч/б) — это будет *скрыто встраиваться* в основное.\n"
        "3️⃣ Бот спросит параметры наложения — ты можешь ввести новые или использовать старые.\n"
        "4️⃣ Получишь готовое изображение с *внедрённым принтом*. Оно будет отправлено тем же способом (фото/файл).\n\n"

        "*⚙️ Что значат параметры:*\n"
        "`Канал` — какой цветовой канал использовать (R, G или B)\n"
        "`Дельта` — насколько сильно менять яркость (рекомендуется от 5 до 25)\n"
        "`Порог` — порог черно-белого принта (от 0 до 255) — выше порога = будет внедрено\n\n"

        "*💾 Сохранение настроек:*\n"
        "Если ты уже вводил параметры раньше — бот предложит использовать те же.\n\n"

        "*📁 Поддержка форматов:*\n"
        "✅ Фото (JPEG/PNG)\n"
        "✅ Документы-файлы (для высокого качества)\n\n"

        "*🔄 Сброс:* \n"
        "Просто отправь новое изображение — и бот начнёт заново. \n\n"

        "*🆘 Команды:*\n"
        "/create — начать заново вручную (не обязательно)\n"
        "/cancel — для отмены текущей сессии\n"
        "/help — помощь\n"
        
    )

    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_session(message):
    chat_id = message.chat.id
    if chat_id in user_sessions:
        user_sessions.pop(chat_id)
        bot.send_message(chat_id, "❌ Текущая сессия сброшена. Можешь начать заново, просто отправив новое изображение.")
    else:
        bot.send_message(chat_id, "ℹ️ Нет активной сессии. Просто отправь изображение, чтобы начать.")


# Твой Telegram chat_id — подставь своё число:
ADMIN_CHAT_ID = 5682825129  # <- сюда свой chat_id поставь

@bot.message_handler(commands=['allusers'])
def all_users(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "🚫 У тебя нет доступа к этой команде.")
        return

    users = load_users()
    if not users:
        bot.send_message(message.chat.id, "📂 База пользователей пока пуста.")
        return

    response_lines = ["📋 *База пользователей:*"]
    for chat_id, info in users.items():
        line = (f"• ID: `{chat_id}`\n"
                f"  Имя: {info.get('first_name', '')}\n"
                f"  Логин: @{info.get('username', '')}\n"
                f"  Первый запуск: {info.get('first_seen', '')}\n"
                f"  Кол-во генераций: {info.get('generate_count', 0)}\n"
                f"  Премиум: {'✅' if info.get('is_premium', False) else '❌'}\n")
        response_lines.append(line)

    response_text = "\n".join(response_lines)
    # Telegram лимит на длину сообщения ~4096, если база большая — можно подумать о разбивке
    bot.send_message(message.chat.id, response_text, parse_mode="Markdown")

@bot.message_handler(commands=['profile'])
def profile(message):
    users = load_users()
    chat_id = str(message.chat.id)

    if chat_id not in users:
        bot.send_message(message.chat.id, "❌ Ты ещё не зарегистрирован. Напиши /start.")
        return

    user_data = users[chat_id]
    username = user_data.get('username', '—')
    first_name = user_data.get('first_name', '—')
    first_seen = user_data.get('first_seen', '—')
    generate_count = user_data.get('generate_count', 0)
    is_premium = user_data.get('is_premium', False)

    profile_text = f"""🧾 *Твой профиль*  
👤 *Имя:* `{first_name}`  
🔗 *Username:* @{username if username else '—'}  
📅 *С нами с:* {first_seen}  
🖼️ *Генераций:* {generate_count}  
💎 *Премиум:* {'Да ✅' if is_premium else 'Нет ❌'}
"""

    if not is_premium:
        profile_text += "\n\n🚀 *Хочешь больше возможностей?*\nОформи премиум командой /premium"

    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")


ADMIN_ID = 5682825129  # ← сюда твой Telegram ID

@bot.message_handler(commands=['premium'])
def premium(message):
    users = load_users()
    chat_id = str(message.chat.id)

    if chat_id in users and users[chat_id].get("is_premium", False):
        text = """🎉 *У тебя уже есть премиум!*

🔓 Безлимит генераций  
⏩ Приоритет в поддержке  
🚫 Нет очередей  
🤝 Прямая связь с разработчиком

Спасибо, что поддерживаешь проект ❤️"""
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        return

    # Если не премиум, то стандартный вариант
    text = """💎 *Премиум возможности*:

🔓 Безлимит генераций  
⏩ Приоритет в поддержке  
🚫 Нет очереди  
🤝 Прямая связь с разработчиком  

Нажми кнопку ниже, чтобы отправить заявку на премиум ⬇️"""

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Оформить 💎", callback_data="request_premium"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['remove_premium'])
def remove_premium(message):
    if str(message.from_user.id) != str(ADMIN_ID):  # Только для админа
        bot.reply_to(message, "⛔ Команда доступна только администратору.")
        return

    msg = bot.send_message(message.chat.id, "Введите ID пользователя, у которого нужно убрать премиум:")
    bot.register_next_step_handler(msg, process_remove_premium)

def process_remove_premium(message):
    user_id = str(message.text).strip()
    users = load_users()

    if user_id not in users:
        bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден в базе.")
        return

    if not users[user_id].get("is_premium", False):
        bot.send_message(message.chat.id, "ℹ️ У пользователя *не было* премиума.", parse_mode="Markdown")
        return

    users[user_id]["is_premium"] = False
    save_users(users)

    bot.send_message(message.chat.id, f"✅ Премиум-статус у пользователя `{user_id}` успешно снят.", parse_mode="Markdown")
    try:
        bot.send_message(user_id, "⚠️ Ваш премиум-статус был снят администратором.")
    except:
        pass  # на случай, если бот не может написать пользователю

@bot.message_handler(commands=['admin'])
def show_admin_commands(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        bot.reply_to(message, "⛔ Команда доступна только администратору.")
        return

    text = (
        "🔧 <b>Админ-команды:</b>\n\n"
        "📊 /allusers — Показать всех пользователей в базе\n"
        "📥 /remove_premium — Убрать премиум у пользователя\n"
        "⚙️ /setlimits — Изменить лимит генераций и время ожидания\n"
        "📢 /admin — Показать этот список админских команд\n"
        "💬 /send_message — Отправить сообщение пользователю\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# Временное хранилище для сообщений
pending_messages = {}

@bot.message_handler(commands=['send_message'])
def start_send_message(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        bot.reply_to(message, "⛔ Команда доступна только администратору.")
        return

    msg = bot.send_message(message.chat.id, "🔢 Введите ID пользователя, которому хотите написать:")
    bot.register_next_step_handler(msg, get_user_id_for_message)

def get_user_id_for_message(message):
    try:
        user_id = int(message.text)
        pending_messages[message.chat.id] = {'target_id': user_id}
        msg = bot.send_message(message.chat.id, "💬 Введите текст сообщения:")
        bot.register_next_step_handler(msg, get_message_text)
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID должен быть числом. Попробуйте снова с /send_message")

def get_message_text(message):
    text = message.text
    pending_messages[message.chat.id]['text'] = text

    preview = (
        f"📤 <b>Предпросмотр:</b>\n\n"
        f"👤 Кому: <code>{pending_messages[message.chat.id]['target_id']}</code>\n"
        f"📝 Сообщение:\n{text}"
    )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_send")
    )

    bot.send_message(message.chat.id, preview, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_send", "cancel_send"])
def handle_send_confirmation(call):
    chat_id = call.message.chat.id

    if call.data == "confirm_send":
        data = pending_messages.get(chat_id)
        if data:
            try:
                bot.send_message(data['target_id'], f"📩 Сообщение от администратора:\n\n{data['text']}")
                bot.edit_message_text("✅ Сообщение успешно отправлено!", chat_id, call.message.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ Ошибка при отправке: {e}", chat_id, call.message.message_id)
        else:
            bot.edit_message_text("⚠️ Данные для отправки не найдены.", chat_id, call.message.message_id)
    else:
        bot.edit_message_text("🚫 Отправка отменена.", chat_id, call.message.message_id)

    if chat_id in pending_messages:
        del pending_messages[chat_id]


@bot.callback_query_handler(func=lambda call: call.data == "request_premium")
def handle_premium_request(call):
    user = call.from_user
    chat_id = call.message.chat.id
    bot.answer_callback_query(call.id, "📬 Заявка отправлена! Мы свяжемся с вами.")
    bot.send_message(chat_id, "📬 Спасибо! Мы свяжемся с тобой для оформления премиум-статуса.")

    admin_text = f"💡 Пользователь @{'—' if not user.username else user.username} ({user.first_name}) хочет премиум!"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Добавить премиум", callback_data=f"grant_premium:{user.id}"))
    bot.send_message(ADMIN_ID, admin_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("grant_premium:"))
def grant_premium(call):
    user_id = call.data.split(":")[1]
    users = load_users()
    if user_id in users:
        users[user_id]["is_premium"] = True
        save_users(users)
        bot.answer_callback_query(call.id, "✅ Премиум добавлен.")
        bot.send_message(user_id, "🎉 Поздравляем! У тебя теперь премиум-доступ.")
    else:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден.")



bot.polling()
