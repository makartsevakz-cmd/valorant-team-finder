"""
VALORANT Team Finder - Telegram Bot (Cloud Version)
Optimized for Railway/Render deployment
"""
import os
import logging
from datetime import time
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
PORT = int(os.environ.get('PORT', 10000))  # Render использует переменную PORT

# Простой HTTP сервер для health checks
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        # Отключаем логирование HTTP запросов
        pass

def run_http_server():
    """Запуск HTTP сервера в отдельном потоке"""
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    logger.info(f"HTTP server started on port {PORT}")
    server.serve_forever()

# Клавиатуры
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Моя анкета", callback_data="view_profile")],
        [InlineKeyboardButton("✏️ Редактировать анкету", callback_data="edit_profile")],
        [InlineKeyboardButton("👥 Кто играет сегодня", callback_data="view_players")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_yes_no_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Да, буду играть!", callback_data="play_yes")],
        [InlineKeyboardButton("❌ Нет, сегодня не смогу", callback_data="play_no")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_rank_keyboard():
    ranks = ["Железо", "Бронза", "Серебро", "Золото", 
             "Платина", "Алмаз", "Бессмертный", "Сияющий"]
    keyboard = [[InlineKeyboardButton(rank, callback_data=f"rank_{rank}")] 
                for rank in ranks]
    return InlineKeyboardMarkup(keyboard)


def get_roles_selection_keyboard(selected_roles):
    role_names = {
        "duelist": "⚔️ Дуэлянт",
        "initiator": "🔥 Зачинщик", 
        "sentinel": "🛡️ Страж",
        "controller": "💨 Контроллер"
    }
    
    keyboard = []
    for role_key, role_name in role_names.items():
        if role_key in selected_roles:
            keyboard.append([InlineKeyboardButton(f"✅ {role_name}", callback_data=f"role_{role_key}")])
        else:
            keyboard.append([InlineKeyboardButton(role_name, callback_data=f"role_{role_key}")])
    
    keyboard.append([InlineKeyboardButton("✔️ Готово", callback_data="roles_done")])
    return InlineKeyboardMarkup(keyboard)


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = database.get_player(user.id)
    
    if player:
        await update.message.reply_text(
            f"С возвращением, {user.first_name}! 👋\n\n"
            "Добро пожаловать в VALORANT Team Finder!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "Добро пожаловать в VALORANT Team Finder!\n"
            "Давай создадим твою анкету игрока.\n\n"
            "Введи свой ник в VALORANT:"
        )
        return VALORANT_NICK
    return ConversationHandler.END


# Обработка ника
async def valorant_nick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['valorant_nick'] = update.message.text
    await update.message.reply_text(
        "Отлично! Теперь выбери свой ранг:",
        reply_markup=get_rank_keyboard()
    )
    return RANK


# Обработка ранга
async def rank_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rank = query.data.replace("rank_", "")
    context.user_data['rank'] = rank
    context.user_data['roles'] = []
    
    await query.edit_message_text(
        f"Ранг: {rank} ✅\n\n"
        "Теперь выбери роли, за которые ты играешь.\n"
        "Можешь выбрать несколько ролей.\n"
        "Когда закончишь, нажми 'Готово'.",
        reply_markup=get_roles_selection_keyboard([])
    )
    return ROLES


# Обработка ролей
async def roles_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if 'roles' not in context.user_data:
        context.user_data['roles'] = []
    
    if query.data == "roles_done":
        if not context.user_data['roles']:
            await query.answer("Выбери хотя бы одну роль!", show_alert=True)
            return ROLES
        
        # Сохранение профиля в Supabase
        user = update.effective_user
        success = database.create_player(
            telegram_id=user.id,
            telegram_username=user.username or "",
            telegram_first_name=user.first_name,
            valorant_nick=context.user_data['valorant_nick'],
            rank=context.user_data['rank'],
            roles=context.user_data['roles']
        )
        
        if success:
            await query.edit_message_text(
                "🎉 Отлично! Твоя анкета создана!\n\n"
                f"Ник: {context.user_data['valorant_nick']}\n"
                f"Ранг: {context.user_data['rank']}\n"
                f"Роли: {', '.join(context.user_data['roles'])}\n\n"
                "Теперь ты можешь отмечаться, когда хочешь играть!",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при сохранении анкеты. Попробуй ещё раз.",
                reply_markup=get_main_menu_keyboard()
            )
        
        return ConversationHandler.END
    else:
        # Переключение роли
        role = query.data.replace("role_", "")
        if role in context.user_data['roles']:
            context.user_data['roles'].remove(role)
        else:
            context.user_data['roles'].append(role)
        
        await query.edit_message_reply_markup(
            reply_markup=get_roles_selection_keyboard(context.user_data['roles'])
        )
        return ROLES


# Просмотр профиля
async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    player = database.get_player(user.id)
    
    if player:
        is_playing = database.get_daily_status(user.id)
        playing_today = "✅ Да" if is_playing else "❌ Нет"
        
        roles_text = '\n'.join([f"  • {role}" for role in player['roles']])
        
        await query.edit_message_text(
            f"📋 Твоя анкета:\n\n"
            f"🎮 Ник: {player['valorant_nick']}\n"
            f"🏆 Ранг: {player['rank']}\n"
            f"🎯 Роли:\n{roles_text}\n\n"
            f"Играю сегодня: {playing_today}",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.edit_message_text(
            "У тебя еще нет анкеты. Используй /start для создания.",
            reply_markup=get_main_menu_keyboard()
        )


# Просмотр играющих
async def view_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    players = database.get_players_playing_today()
    
    if not players:
        await query.edit_message_text(
            "😔 Сегодня пока никто не отметился.\n"
            "Будь первым!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        text = f"👥 Играют сегодня ({len(players)} игроков):\n\n"
        
        for i, player in enumerate(players, 1):
            username = f"@{player['telegram_username']}" if player['telegram_username'] else "Без username"
            roles = ', '.join(player['roles'])
            text += f"{i}. {player['valorant_nick']}\n"
            text += f"   TG: {username}\n"
            text += f"   🏆 {player['rank']} | {roles}\n\n"
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard()
        )


# Ежедневная рассылка
async def send_daily_notification(context: ContextTypes.DEFAULT_TYPE):
    players = database.get_all_players()
    
    for player in players:
        try:
            await context.bot.send_message(
                chat_id=player['telegram_id'],
                text=f"Привет, {player['telegram_first_name']}! 👋\n\n"
                     "🎮 Будешь играть в VALORANT сегодня?",
                reply_markup=get_yes_no_keyboard()
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение {player['telegram_id']}: {e}")


# Обработка ответа на вопрос
async def handle_daily_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    is_playing = query.data == "play_yes"
    
    success = database.update_daily_status(user.id, is_playing)
    
    if success:
        if is_playing:
            await query.edit_message_text(
                "✅ Отлично! Ты в списке на сегодня!\n"
                "Твой профиль виден всем в веб-приложении.",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await query.edit_message_text(
                "👌 Понял, в следующий раз!",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await query.edit_message_text(
            "❌ Ошибка при сохранении статуса.",
            reply_markup=get_main_menu_keyboard()
        )


# Главный обработчик кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data == "view_profile":
        await view_profile(update, context)
    elif query.data == "view_players":
        await view_players(update, context)
    elif query.data == "edit_profile":
        await query.answer()
        await query.edit_message_text("Давай обновим твою анкету!\n\nВведи свой ник в VALORANT:")
        return VALORANT_NICK
    elif query.data in ["play_yes", "play_no"]:
        await handle_daily_response(update, context)
    
    return ConversationHandler.END


# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Создание анкеты отменено.",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


def main():
    """Запуск бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен!")
        return
    
    # Запуск HTTP сервера в отдельном потоке (для Render health checks)
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(handle_callback, pattern="^edit_profile$")
        ],
        states={
            VALORANT_NICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, valorant_nick)],
            RANK: [CallbackQueryHandler(rank_selection, pattern="^rank_")],
            ROLES: [CallbackQueryHandler(roles_selection, pattern="^role_|^roles_done$")]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Ежедневная рассылка (если доступен job_queue)
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
