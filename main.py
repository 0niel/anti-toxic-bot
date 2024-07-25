import logging
from datetime import datetime, timedelta, timezone

import aiosqlite
from perspective import Attribute, Perspective
from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, JobQueue, MessageHandler, filters
from telegram_bot_pagination import InlineKeyboardPaginator

from config import config

logging.basicConfig(format="%(asctime)s - %(name)s - %(levellevel)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

p = Perspective(key=config.PERSPECTIVE_API_KEY)

ADMIN_USERNAMES = config.ADMIN_USERNAMES


async def init_db():
    logger.info("Initializing database...")
    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER,
                chat_id INTEGER,
                until TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS toxicity_scores (
                user_id INTEGER,
                chat_id INTEGER,
                score REAL,
                timestamp TIMESTAMP
            )
        """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_joins (
                user_id INTEGER,
                chat_id INTEGER,
                join_date TIMESTAMP,
                PRIMARY KEY (user_id, chat_id)
            )
        """
        )
        await db.commit()
    logger.info("Database initialized.")


async def check_message(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type
    user = update.message.from_user

    logger.info(f"Checking message from user {user_id} in chat {chat_id}.")

    response = await p.score(
        text, attributes=[Attribute.SEVERE_TOXICITY, Attribute.TOXICITY, Attribute.SEXUALLY_EXPLICIT, Attribute.INSULT]
    )

    logger.info(
        f"Perspective API response for user {user_id}: {[response.toxicity, response.severe_toxicity, response.sexually_explicit, response.insult]}"
    )

    # Accumulate toxicity score
    score = max(response.toxicity, response.severe_toxicity, response.sexually_explicit, response.insult)
    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute(
            "INSERT INTO toxicity_scores (user_id, chat_id, score, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, chat_id, score, datetime.now(timezone.utc)),
        )
        await db.commit()

    # Check user's join date
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute(
            "SELECT join_date FROM user_joins WHERE user_id = ? AND chat_id = ?", (user_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                join_date = datetime.fromisoformat(row[0])
                new_user = (datetime.now(timezone.utc) - join_date).total_seconds() < 10800  # 3 hours
            else:
                new_user = False

    # Adjust thresholds
    toxicity_threshold = 0.78
    if new_user:
        toxicity_threshold -= 0.1  # Lower threshold for new users
    if score > 0.9:
        toxicity_threshold -= 0.1  # Lower threshold for highly toxic messages

    # Check accumulated points
    accumulated_points = 0
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM toxicity_scores WHERE user_id = ? AND chat_id = ? AND score > 0.6", (user_id, chat_id)
        ) as cursor:
            row = await cursor.fetchone()
            accumulated_points = row[0]

    mute_duration_hours = 3 + (accumulated_points // 3) * 2  # Increase mute duration for repeated offenders

    if (
        response.severe_toxicity > toxicity_threshold
        or response.toxicity > toxicity_threshold
        or response.sexually_explicit > toxicity_threshold
        or response.insult > toxicity_threshold
    ):
        if accumulated_points < 3:
            accumulated_points += 1
        else:
            accumulated_points = 0
            until = datetime.now(timezone.utc) + timedelta(hours=mute_duration_hours)
            async with aiosqlite.connect("mute_bot.db") as db:
                await db.execute(
                    "INSERT OR REPLACE INTO mutes (user_id, chat_id, until) VALUES (?, ?, ?)", (user_id, chat_id, until)
                )
                await db.commit()

            logger.info(f"User {user_id} muted until {until}.")

            context.job_queue.run_once(unmute_user, when=until, data=(chat_id, user_id), name=f"{chat_id}_{user_id}")

            if chat_type == "supergroup":
                await context.bot.restrict_chat_member(
                    chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until
                )

                await update.message.reply_text(
                    f"🚫 Пользователь @{user.username or user.full_name} был временно заблокирован на {mute_duration_hours} часов за токсичность.",
                )
            else:
                await update.message.delete()
                await update.message.reply_text(
                    f"🚫 Пользователь @{user.username or user.full_name} был временно заблокирован на {mute_duration_hours} часов за токсичность. Сообщения будут удаляться.",
                    quote=False,
                )


async def unmute_user(context: CallbackContext):
    job = context.job or None
    chat_id, user_id = job.data if job else context.args

    logger.info(f"Unmuting user {user_id} in chat {chat_id}.")

    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute("DELETE FROM mutes WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
        await db.commit()

    chat = await context.bot.get_chat(chat_id)
    user = await context.bot.get_chat_member(chat_id, user_id).user
    if chat.type == "supergroup":
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=True))

    await context.bot.send_message(
        chat_id,
        text=f"✅ Пользователь <a href='tg://user?id={user_id}'>{user.username or user.full_name}</a> был разблокирован.",
        parse_mode=ParseMode.HTML,
    )


async def start(update: Update, context: CallbackContext):
    logger.info("Received /start command.")
    await update.message.reply_text("👋 Привет! Я AntiToxicBot, который борется с токсичностью. Пиши аккуратнее!")


async def muted_users(update: Update, context: CallbackContext):
    logger.info("Received /muted_users command.")
    chat_id = update.message.chat_id
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute("SELECT user_id, until FROM mutes WHERE chat_id = ?", (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                message = "🚫 Временно заблокированные пользователи:\n\n"
                for row in rows:
                    user_id, until = row
                    until = datetime.fromisoformat(until)
                    user = await context.bot.get_chat_member(chat_id, user_id).user
                    message += f"- <a href='tg://user?id={user_id}'>{user.username or user.full_name}</a> до {until.strftime('%Y-%m-%d %H:%M:%S')}\n"
                await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("✅ Нет временно заблокированных пользователей.")


async def unmute_command(update: Update, context: CallbackContext):
    username = update.message.from_user.username
    if username not in ADMIN_USERNAMES:
        await update.message.reply_text("⛔ У вас нет прав для использования этой команды.")
        return

    try:
        user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Пожалуйста, укажите корректный ID пользователя для разблокировки.")
        return

    chat_id = update.message.chat_id
    await unmute_user(
        context=CallbackContext.from_update(update, context.application), chat_id=chat_id, user_id=user_id
    )


async def toxic_users(update: Update, context: CallbackContext):
    logger.info("Received /toxic_users command.")
    chat_id = update.message.chat_id
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute(
            """
            SELECT user_id, AVG(score) as avg_score
            FROM toxicity_scores
            WHERE chat_id = ?
            GROUP BY user_id
            ORDER BY avg_score DESC
            LIMIT 10
            """,
            (chat_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            if rows:
                message = "😡 Антирейтинг самых токсичных пользователей:\n\n"
                for row in rows:
                    user_id, avg_score = row
                    user = await context.bot.get_chat_member(chat_id, user_id).user
                    message += (
                        f"- {user.username or user.full_name} 💩 со средним уровнем токсичности {avg_score:.2f}\n"
                    )
                message += "\nГоните их и порицайте! 🚫"
                await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("😊 В этом чате нет токсичных пользователей.")


async def mute_history(update: Update, context: CallbackContext):
    logger.info("Received /mute_history command.")
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    page = int(context.args[0]) if context.args else 1
    items_per_page = 10

    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute("SELECT COUNT(*) FROM mutes WHERE chat_id = ?", (chat_id,)) as cursor:
            total_records = await cursor.fetchone()[0]

        async with db.execute(
            "SELECT user_id, until FROM mutes WHERE chat_id = ? ORDER BY until DESC LIMIT ? OFFSET ?",
            (chat_id, items_per_page, (page - 1) * items_per_page),
        ) as cursor:
            rows = await cursor.fetchall()

    if rows:
        message = "📜 История блокировок:\n\n"
        for row in rows:
            user_id, until = row
            until = datetime.fromisoformat(until)
            user = await context.bot.get_chat_member(chat_id, user_id).user
            message += f"- Пользователь <a href='tg://user?id={user_id}'>{user.username or user.full_name}</a> был заблокирован до {until.strftime('%Y-%м-%d %H:%М:%S')}\n"

        paginator = InlineKeyboardPaginator(
            page_count=(total_records + items_per_page - 1) // items_per_page,
            current_page=page,
            data_pattern="mute_history#{page}",
        )
        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=paginator.markup)
    else:
        await update.message.reply_text("📜 Нет записей о блокировках.")


def main():
    logger.info("Starting bot...")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    job_queue = JobQueue()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("muted_users", muted_users))
    app.add_handler(CommandHandler("unmute", unmute_command, filters=filters.ChatType.GROUPS))
    app.add_handler(CommandHandler("toxic_users", toxic_users))
    app.add_handler(CommandHandler("mute_history", mute_history))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))

    job_queue.set_application(app)
    job_queue.start()

    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    main()
