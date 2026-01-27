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
        [InlineKeyboardButton("🎮 Буду играть сегодня", callback_data="play_today_slots")],
        [InlineKeyboardButton("📝 Изменить план на сегодня", callback_data="change_plan")],
        [InlineKeyboardButton("👥 Кто играет сегодня?", url="https://valorant-team-finder-1.vercel.app")],
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
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_slots")])
    
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
    """Получение игрового ника"""
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


async def get_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение ранга"""
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
    """Начало выбора временных слотов"""
    query = update.callback_query
    await query.answer()
    
    # Инициализируем выбранные слоты
    context.user_data['selected_slots'] = []
    
    await query.edit_message_text(
        "🎮 Выбери время когда будешь играть сегодня\n"
        "(можно выбрать несколько):",
        reply_markup=get_time_slots_keyboard([])
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
    teammates = database.get_players_by_slots(today, selected_slots, limit=3, exclude_id=telegram_id)
    
    # Формируем сообщение
    slots_text = ", ".join([TIME_SLOTS_RU[s] for s in selected_slots])
    date_text = datetime.now().strftime("%d.%m.%Y")
    
    message = f"✅ {date_text}\n\n"
    message += f"Сегодня вы будете играть {slots_text}"
    
    if teammates:
        teammates_mentions = [f"@{t['valorant_nick']}" for t in teammates[:3]]
        message += f"\n\nВ это же время с вами будут играть:\n{' '.join(teammates_mentions)}"
    else:
        message += "\n\n🔍 Пока никто больше не планирует играть в это время"
    
    await query.edit_message_text(
        message,
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
    """Редактирование профиля"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⚙️ Редактирование профиля\n\n"
        "Начни заново регистрацию командой /start\n"
        "Твои старые данные будут заменены новыми."
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    data = query.data
    
    if data == "play_today_slots":
        await play_today_slots(update, context)
    elif data.startswith("slot_"):
        await toggle_slot(update, context)
    elif data == "confirm_slots":
        await confirm_slots(update, context)
    elif data == "cancel_slots":
        await cancel_slots(update, context)
    elif data == "change_plan":
        await change_plan(update, context)
    elif data == "edit_profile":
        await edit_profile(update, context)
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
    
    # Conversation handler для регистрации
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            VALORANT_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_valorant_nick)],
            RANK: [CallbackQueryHandler(get_rank, pattern="^rank_")],
            ROLES: [
                CallbackQueryHandler(get_roles, pattern="^role_"),
                CallbackQueryHandler(finish_registration, pattern="^roles_done$")
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Ежедневные уведомления (если доступен job_queue)
    try:
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_daily(send_daily_notification, time=time(10, 0, 0))
            job_queue.run_daily(send_daily_notification, time=time(18, 0, 0))
            logger.info("Ежедневные уведомления настроены на 10:00 и 18:00")
        else:
            logger.warning("JobQueue недоступен. Ежедневные уведомления отключены.")
    except Exception as e:
        logger.warning(f"Не удалось настроить ежедневные уведомления: {e}")
    
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
