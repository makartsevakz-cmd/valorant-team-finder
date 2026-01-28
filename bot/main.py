"""
VALORANT Team Finder - Telegram Bot (Cloud Version v2)
С поддержкой временных слотов
"""
import os
import logging
from datetime import time, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
import database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
VALORANT_NICK, RANK, ROLES = range(3)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
PORT = int(os.environ.get('PORT', 10000))

# Временные слоты
TIME_SLOTS = {
    'morning': '🌅 Утро (6:00-12:00)',
    'day': '☀️ День (12:00-18:00)',
    'evening': '🌆 Вечер (18:00-00:00)',
    'night': '🌙 Ночь (00:00-6:00)'
}

TIME_SLOTS_EMOJI = {
    'morning': '🌅',
    'day': '☀️',
    'evening': '🌆',
    'night': '🌙'
}

TIME_SLOTS_RU = {
    'morning': 'утром',
    'day': 'днём',
    'evening': 'вечером',
    'night': 'ночью'
}

# Простой HTTP сервер для health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass

def run_http_server():
    """Запуск HTTP сервера в отдельном потоке"""
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    logger.info(f"HTTP server started on port {PORT}")
    server.serve_forever()


# ======================
# КЛАВИАТУРЫ
# ======================

def get_main_menu_keyboard():
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("🎮 Мой план на сегодня", callback_data="play_today_slots")],
        [InlineKeyboardButton("👥 Кто играет сегодня?", url="https://valorant-team-finder-ten.vercel.app/")],
        [InlineKeyboardButton("⚙️ Изменить данные", callback_data="edit_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_time_slots_keyboard(selected_slots=None):
    """Клавиатура выбора временных слотов"""
    if selected_slots is None:
        selected_slots = []
    
    keyboard = []
    for slot_id, slot_name in TIME_SLOTS.items():
        # Добавляем галочку если выбрано
        prefix = "✅ " if slot_id in selected_slots else ""
        keyboard.append([InlineKeyboardButton(
            f"{prefix}{slot_name}",
            callback_data=f"slot_{slot_id}"
        )])
    
    # Кнопка подтверждения (только если что-то выбрано)
    if selected_slots:
        keyboard.append([InlineKeyboardButton("✅ Подтвердить выбор", callback_data="confirm_slots")])
    
    # Кнопка "Не буду играть"
    keyboard.append([InlineKeyboardButton("❌ Не буду играть сегодня", callback_data="not_playing")])
    keyboard.append([InlineKeyboardButton("🔙 Отмена", callback_data="cancel_slots")])
    
    return InlineKeyboardMarkup(keyboard)


def get_rank_keyboard():
    """Клавиатура выбора ранга"""
    ranks = ["Железо", "Бронза", "Серебро", "Золото", 
             "Платина", "Алмаз", "Бессмертный", "Сияющий"]
    keyboard = [[InlineKeyboardButton(rank, callback_data=f"rank_{rank}")] 
                for rank in ranks]
    return InlineKeyboardMarkup(keyboard)


def get_roles_keyboard():
    """Клавиатура выбора ролей"""
    roles = [
        ("💨 Дуэлист", "duelist"),
        ("🛡 Страж", "sentinel"),
        ("⚡ Инициатор", "initiator"),
        ("🎯 Контроллер", "controller")
    ]
    keyboard = [[InlineKeyboardButton(name, callback_data=f"role_{value}")] 
                for name, value in roles]
    return InlineKeyboardMarkup(keyboard)


# ======================
# РЕГИСТРАЦИЯ
# ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    telegram_id = user.id
    
    # Проверяем, зарегистрирован ли пользователь
    player = database.get_player(telegram_id)
    
    if player:
        # Пользователь уже зарегистрирован
        await update.message.reply_text(
            f"👋 Привет, {player['valorant_nick']}!\n\n"
            f"📊 Твой ранг: {player['rank']}\n"
            f"🎯 Роли: {', '.join(player['roles'])}\n\n"
            "Что хочешь сделать?",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Новый пользователь - начинаем регистрацию
        await update.message.reply_text(
            "👋 Привет! Это бот для поиска тиммейтов в VALORANT!\n\n"
            "Давай заполним твою анкету:\n\n"
            "🎮 Введи свой игровой ник в VALORANT:"
        )
        return VALORANT_NICK
    
    return ConversationHandler.END


async def get_valorant_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение игрового ника (регистрация)"""
    nick = update.message.text.strip()
    
    if len(nick) < 2 or len(nick) > 30:
        await update.message.reply_text(
            "❌ Ник должен быть от 2 до 30 символов. Попробуй еще раз:"
        )
        return VALORANT_NICK
    
    context.user_data['valorant_nick'] = nick
    
    await update.message.reply_text(
        f"✅ Отлично! Твой ник: {nick}\n\n"
        "📊 Теперь выбери свой ранг:",
        reply_markup=get_rank_keyboard()
    )
    return RANK


async def handle_nick_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода ника (может быть регистрация или редактирование)"""
    # Проверяем режим
    if context.user_data.get('editing') == 'nick':
        return await save_edited_nick(update, context)
    else:
        return await get_valorant_nick(update, context)


async def get_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ранга (регистрация)"""
    query = update.callback_query
    await query.answer()
    
    rank = query.data.replace("rank_", "")
    context.user_data['rank'] = rank
    context.user_data['roles'] = []
    
    await query.edit_message_text(
        f"✅ Ранг: {rank}\n\n"
        "🎯 Выбери роли, которыми играешь (можно выбрать несколько):",
        reply_markup=get_roles_keyboard()
    )
    return ROLES


async def handle_rank_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора ранга (может быть регистрация или редактирование)"""
    # Проверяем режим
    if context.user_data.get('editing') == 'rank':
        return await save_edited_rank(update, context)
    else:
        return await get_rank(update, context)


async def get_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ролей"""
    query = update.callback_query
    await query.answer()
    
    role = query.data.replace("role_", "")
    roles = context.user_data.get('roles', [])
    
    # Переключаем роль
    if role in roles:
        roles.remove(role)
    else:
        roles.append(role)
    
    context.user_data['roles'] = roles
    
    # Создаем клавиатуру с отметками
    roles_dict = {
        "duelist": "💨 Дуэлист",
        "sentinel": "🛡 Страж",
        "initiator": "⚡ Инициатор",
        "controller": "🎯 Контроллер"
    }
    
    keyboard = []
    for role_id, role_name in roles_dict.items():
        prefix = "✅ " if role_id in roles else ""
        keyboard.append([InlineKeyboardButton(
            f"{prefix}{role_name}",
            callback_data=f"role_{role_id}"
        )])
    
    # Кнопка готово (если выбрана хотя бы одна роль)
    if roles:
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="roles_done")])
    
    await query.edit_message_text(
        f"✅ Ранг: {context.user_data['rank']}\n\n"
        f"🎯 Выбери роли (выбрано: {len(roles)}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ROLES


async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение регистрации"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    nick = context.user_data['valorant_nick']
    rank = context.user_data['rank']
    roles = context.user_data['roles']
    
    # Сохраняем в базу
    success = database.save_player(telegram_id, nick, rank, roles)
    
    if success:
        await query.edit_message_text(
            f"✅ Регистрация завершена!\n\n"
            f"🎮 Ник: {nick}\n"
            f"📊 Ранг: {rank}\n"
            f"🎯 Роли: {', '.join(roles)}\n\n"
            "Теперь ты можешь искать тиммейтов!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при сохранении данных. Попробуй еще раз: /start"
        )
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена регистрации"""
    await update.message.reply_text(
        "❌ Регистрация отменена. Для начала напиши /start"
    )
    return ConversationHandler.END


# ======================
# ВЫБОР ВРЕМЕННЫХ СЛОТОВ
# ======================

async def play_today_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало выбора временных слотов (или изменение существующих)"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    today = datetime.now().date().isoformat()
    
    # Получаем текущий план
    current_status = database.get_daily_status(telegram_id, today)
    current_slots = current_status.get('time_slots', []) if current_status else []
    
    # Инициализируем выбранные слоты текущим планом
    context.user_data['selected_slots'] = current_slots.copy()
    
    # Формируем сообщение
    if current_slots:
        slots_text = ", ".join([TIME_SLOTS_RU[s] for s in current_slots])
        message = f"📝 Ваш текущий план на сегодня:\n{slots_text}\n\n"
        message += "🎮 Измените или подтвердите время игры:"
    else:
        message = "🎮 Выбери время когда будешь играть сегодня\n(можно выбрать несколько):"
    
    await query.edit_message_text(
        message,
        reply_markup=get_time_slots_keyboard(current_slots)
    )


async def toggle_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключение временного слота"""
    query = update.callback_query
    await query.answer()
    
    slot = query.data.replace("slot_", "")
    selected_slots = context.user_data.get('selected_slots', [])
    
    # Переключаем слот
    if slot in selected_slots:
        selected_slots.remove(slot)
    else:
        selected_slots.append(slot)
    
    context.user_data['selected_slots'] = selected_slots
    
    await query.edit_message_text(
        "🎮 Выбери время когда будешь играть сегодня\n"
        f"(выбрано: {len(selected_slots)}):",
        reply_markup=get_time_slots_keyboard(selected_slots)
    )


async def confirm_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение выбора слотов"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    selected_slots = context.user_data.get('selected_slots', [])
    
    if not selected_slots:
        await query.edit_message_text(
            "❌ Нужно выбрать хотя бы один временной слот!",
            reply_markup=get_time_slots_keyboard([])
        )
        return
    
    # Сохраняем в базу
    today = datetime.now().date().isoformat()
    success = database.update_daily_status(telegram_id, today, True, selected_slots)
    
    if not success:
        await query.edit_message_text(
            "❌ Ошибка при сохранении. Попробуй еще раз.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Получаем других игроков в эти же слоты
    teammates = database.get_players_by_slots(today, selected_slots, limit=5, exclude_id=telegram_id)
    
    # Формируем сообщение
    slots_text = ", ".join([TIME_SLOTS_RU[s] for s in selected_slots])
    date_text = datetime.now().strftime("%d.%m.%Y")
    
    message = f"✅ {date_text}\n\n"
    message += f"Сегодня вы будете играть {slots_text}"
    
    if teammates:
        message += "\n\n👥 В это же время с вами будут играть:\n"
        for teammate in teammates[:5]:
            # Используем telegram username если есть, иначе создаём ссылку по ID
            if teammate.get('telegram_username'):
                telegram_link = f"@{teammate['telegram_username']}"
            else:
                # Создаём кликабельную ссылку через tg://user?id=
                telegram_link = f"[{teammate['telegram_first_name']}](tg://user?id={teammate['telegram_id']})"
            
            valorant_nick = teammate['valorant_nick']
            message += f"• {telegram_link} ({valorant_nick})\n"
    else:
        message += "\n\n🔍 Пока никто больше не планирует играть в это время"
    
    await query.edit_message_text(
        message,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )


async def not_playing_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь не будет играть сегодня"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    today = datetime.now().date().isoformat()
    
    # Удаляем или помечаем как не играющий
    success = database.update_daily_status(telegram_id, today, False, [])
    
    if success:
        await query.edit_message_text(
            "✅ Понял! Сегодня ты не будешь играть.\n\n"
            "Твой статус обновлён.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при обновлении статуса. Попробуй еще раз.",
            reply_markup=get_main_menu_keyboard()
        )


async def cancel_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена выбора слотов"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "❌ Выбор отменен",
        reply_markup=get_main_menu_keyboard()
    )


# ======================
# ИЗМЕНЕНИЕ ПЛАНА
# ======================

async def change_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Изменение плана на сегодня"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    today = datetime.now().date().isoformat()
    
    # Получаем текущий план
    current_status = database.get_daily_status(telegram_id, today)
    current_slots = current_status.get('time_slots', []) if current_status else []
    
    # Инициализируем выбранные слоты текущим планом
    context.user_data['selected_slots'] = current_slots.copy()
    
    message = "📝 Изменение плана на сегодня\n\n"
    if current_slots:
        slots_text = ", ".join([TIME_SLOTS_RU[s] for s in current_slots])
        message += f"Сейчас вы играете: {slots_text}\n\n"
    else:
        message += "Сейчас у вас нет плана на сегодня\n\n"
    
    message += "Выберите новое время:"
    
    await query.edit_message_text(
        message,
        reply_markup=get_time_slots_keyboard(current_slots)
    )


# ======================
# ДРУГИЕ КОМАНДЫ
# ======================

async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню редактирования профиля"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    player = database.get_player(telegram_id)
    
    if not player:
        await query.edit_message_text(
            "❌ Профиль не найден. Начните регистрацию: /start"
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("🎮 Изменить игровой ник", callback_data="edit_nick")],
        [InlineKeyboardButton("📊 Изменить ранг", callback_data="edit_rank")],
        [InlineKeyboardButton("🎯 Изменить роли", callback_data="edit_roles")],
        [InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"⚙️ Редактирование профиля\n\n"
        f"🎮 Ник: {player['valorant_nick']}\n"
        f"📊 Ранг: {player['rank']}\n"
        f"🎯 Роли: {', '.join(player['roles'])}\n\n"
        "Что хочешь изменить?",
        reply_markup=reply_markup
    )


async def edit_nick_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало изменения ника"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎮 Изменение игрового ника\n\n"
        "Введи новый ник в VALORANT:"
    )
    context.user_data['editing'] = 'nick'
    return VALORANT_NICK


async def edit_rank_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало изменения ранга"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 Изменение ранга\n\n"
        "Выбери новый ранг:",
        reply_markup=get_rank_keyboard()
    )
    context.user_data['editing'] = 'rank'


async def edit_roles_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало изменения ролей"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    player = database.get_player(telegram_id)
    
    # Инициализируем текущие роли
    context.user_data['roles'] = player['roles'].copy()
    context.user_data['editing'] = 'roles'
    
    # Создаем клавиатуру с отметками текущих ролей
    roles_dict = {
        "duelist": "💨 Дуэлист",
        "sentinel": "🛡 Страж",
        "initiator": "⚡ Инициатор",
        "controller": "🎯 Контроллер"
    }
    
    keyboard = []
    for role_id, role_name in roles_dict.items():
        prefix = "✅ " if role_id in context.user_data['roles'] else ""
        keyboard.append([InlineKeyboardButton(
            f"{prefix}{role_name}",
            callback_data=f"role_{role_id}"
        )])
    
    if context.user_data['roles']:
        keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="save_roles")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="edit_profile")])
    
    await query.edit_message_text(
        f"🎯 Изменение ролей\n\n"
        f"Выбери роли (сейчас выбрано: {len(context.user_data['roles'])}):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def save_edited_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового ника"""
    user = update.effective_user
    telegram_id = user.id
    new_nick = update.message.text.strip()
    
    if len(new_nick) < 2 or len(new_nick) > 30:
        await update.message.reply_text(
            "❌ Ник должен быть от 2 до 30 символов. Попробуй еще раз:"
        )
        return VALORANT_NICK
    
    # Получаем текущий профиль
    player = database.get_player(telegram_id)
    if not player:
        await update.message.reply_text(
            "❌ Ошибка. Начни заново: /start"
        )
        return ConversationHandler.END
    
    # Сохраняем с новым ником
    success = database.save_player(telegram_id, new_nick, player['rank'], player['roles'])
    
    if success:
        await update.message.reply_text(
            f"✅ Ник изменён на: {new_nick}",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка при сохранении. Попробуй еще раз: /start"
        )
    
    context.user_data.pop('editing', None)
    return ConversationHandler.END


async def save_edited_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового ранга"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    new_rank = query.data.replace("rank_", "")
    
    # Получаем текущий профиль
    player = database.get_player(telegram_id)
    if not player:
        await query.edit_message_text(
            "❌ Ошибка. Начни заново: /start"
        )
        return ConversationHandler.END
    
    # Сохраняем с новым рангом
    success = database.save_player(telegram_id, player['valorant_nick'], new_rank, player['roles'])
    
    if success:
        await query.edit_message_text(
            f"✅ Ранг изменён на: {new_rank}",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при сохранении. Попробуй еще раз: /start"
        )
    
    context.user_data.pop('editing', None)
    return ConversationHandler.END


async def save_edited_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение новых ролей"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    new_roles = context.user_data.get('roles', [])
    
    if not new_roles:
        await query.answer("❌ Нужно выбрать хотя бы одну роль!", show_alert=True)
        return
    
    # Получаем текущий профиль
    player = database.get_player(telegram_id)
    if not player:
        await query.edit_message_text(
            "❌ Ошибка. Начни заново: /start"
        )
        return ConversationHandler.END
    
    # Сохраняем с новыми ролями
    success = database.save_player(telegram_id, player['valorant_nick'], player['rank'], new_roles)
    
    if success:
        await query.edit_message_text(
            f"✅ Роли изменены: {', '.join(new_roles)}",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Ошибка при сохранении. Попробуй еще раз: /start"
        )
    
    context.user_data.pop('editing', None)
    context.user_data.pop('roles', None)
    return ConversationHandler.END


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    telegram_id = user.id
    player = database.get_player(telegram_id)
    
    if player:
        await query.edit_message_text(
            f"👋 Привет, {player['valorant_nick']}!\n\n"
            f"📊 Твой ранг: {player['rank']}\n"
            f"🎯 Роли: {', '.join(player['roles'])}\n\n"
            "Что хочешь сделать?",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "❌ Профиль не найден. Начни заново: /start"
        )
    
    return ConversationHandler.END


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    data = query.data
    
    # Проверяем контекст редактирования
    editing = context.user_data.get('editing')
    
    if data == "play_today_slots":
        await play_today_slots(update, context)
    elif data.startswith("slot_"):
        await toggle_slot(update, context)
    elif data == "confirm_slots":
        await confirm_slots(update, context)
    elif data == "cancel_slots":
        await cancel_slots(update, context)
    elif data == "not_playing":
        await not_playing_today(update, context)
    elif data == "edit_profile":
        await edit_profile(update, context)
    elif data == "edit_nick":
        await edit_nick_start(update, context)
        return VALORANT_NICK
    elif data == "edit_rank":
        await edit_rank_start(update, context)
    elif data.startswith("rank_") and editing == 'rank':
        await save_edited_rank(update, context)
        return ConversationHandler.END
    elif data == "edit_roles":
        await edit_roles_start(update, context)
    elif data.startswith("role_") and editing == 'roles':
        # Переключаем роль в режиме редактирования
        role = data.replace("role_", "")
        roles = context.user_data.get('roles', [])
        
        if role in roles:
            roles.remove(role)
        else:
            roles.append(role)
        
        context.user_data['roles'] = roles
        
        # Обновляем клавиатуру
        roles_dict = {
            "duelist": "💨 Дуэлист",
            "sentinel": "🛡 Страж",
            "initiator": "⚡ Инициатор",
            "controller": "🎯 Контроллер"
        }
        
        keyboard = []
        for role_id, role_name in roles_dict.items():
            prefix = "✅ " if role_id in roles else ""
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{role_name}",
                callback_data=f"role_{role_id}"
            )])
        
        if roles:
            keyboard.append([InlineKeyboardButton("✅ Сохранить", callback_data="save_roles")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="edit_profile")])
        
        await query.edit_message_text(
            f"🎯 Изменение ролей\n\n"
            f"Выбери роли (сейчас выбрано: {len(roles)}):",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.answer()
    elif data == "save_roles":
        await save_edited_roles(update, context)
        return ConversationHandler.END
    elif data == "back_to_menu":
        await back_to_menu(update, context)
        return ConversationHandler.END
    else:
        await query.answer("⚠️ Неизвестная команда")


# ======================
# ЕЖЕДНЕВНЫЕ УВЕДОМЛЕНИЯ
# ======================

async def send_daily_notification(context: ContextTypes.DEFAULT_TYPE):
    """Отправка ежедневных уведомлений"""
    logger.info("Sending daily notifications...")
    
    # Получаем всех игроков
    all_players = database.get_all_players()
    
    for player in all_players:
        try:
            telegram_id = player['telegram_id']
            
            keyboard = [
                [InlineKeyboardButton("🎮 Буду играть сегодня", callback_data="play_today_slots")],
                [InlineKeyboardButton("❌ Не буду играть", callback_data="cancel_slots")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=telegram_id,
                text=f"🌅 Доброе утро, {player['valorant_nick']}!\n\n"
                     "Будешь играть в VALORANT сегодня?",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send notification to {telegram_id}: {e}")
    
    logger.info(f"Notifications sent to {len(all_players)} players")


# ======================
# MAIN
# ======================

def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    # Запуск HTTP сервера в отдельном потоке (для Render health checks)
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler для регистрации и редактирования
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(edit_nick_start, pattern="^edit_nick$"),
            CallbackQueryHandler(edit_rank_start, pattern="^edit_rank$"),
            CallbackQueryHandler(edit_roles_start, pattern="^edit_roles$"),
        ],
        states={
            VALORANT_NICK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nick_input),
            ],
            RANK: [
                CallbackQueryHandler(handle_rank_callback, pattern="^rank_"),
            ],
            ROLES: [
                CallbackQueryHandler(get_roles, pattern="^role_"),
                CallbackQueryHandler(finish_registration, pattern="^roles_done$"),
                CallbackQueryHandler(save_edited_roles, pattern="^save_roles$"),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"),
            CallbackQueryHandler(edit_profile, pattern="^edit_profile$"),
        ],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Ежедневные уведомления (если доступен job_queue)
    try:
        job_queue = application.job_queue
        if job_queue:
            # Устанавливаем время в UTC (10:00 UTC = 13:00 MSK, 18:00 UTC = 21:00 MSK)
            # Если нужно 10:00 и 18:00 по Москве, то в UTC это 07:00 и 15:00
            job_queue.run_daily(send_daily_notification, time=time(7, 0, 0))  # 10:00 MSK
            job_queue.run_daily(send_daily_notification, time=time(15, 0, 0))  # 18:00 MSK
            logger.info("Ежедневные уведомления настроены на 10:00 и 18:00 МСК (7:00 и 15:00 UTC)")
        else:
            logger.warning("JobQueue недоступен. Ежедневные уведомления отключены.")
    except Exception as e:
        logger.warning(f"Не удалось настроить ежедневные уведомления: {e}")
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
