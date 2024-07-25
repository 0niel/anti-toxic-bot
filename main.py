import logging
from datetime import datetime, timedelta

import aiosqlite
from datetime import timezone
from perspective import Attribute, Perspective
from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, JobQueue, MessageHandler, filters

from config import config

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

p = Perspective(key=config.PERSPECTIVE_API_KEY)

ADMIN_USERNAMES = config.ADMIN_USERNAMES


async def init_db():
    logger.info("Initializing database...")
    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS mutes (
                user_id INTEGER PRIMARY KEY,
                until TIMESTAMP
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

    logger.info(f"Checking message from user {user_id} in chat {chat_id}.")

    response = await p.score(
        text, attributes=[Attribute.SEVERE_TOXICITY, Attribute.TOXICITY, Attribute.SEXUALLY_EXPLICIT, Attribute.INSULT]
    )

    logger.info(
        f"Perspective API response for user {user_id}: {[response.toxicity, response.severe_toxicity, response.sexually_explicit, response.insult]}"
    )

    if (
        response.severe_toxicity > 0.78
        or response.toxicity > 0.78
        or response.sexually_explicit > 0.78
        or response.insult > 0.78
    ):
        until = datetime.now(timezone.utc) + timedelta(hours=3)
        async with aiosqlite.connect("mute_bot.db") as db:
            await db.execute("INSERT OR REPLACE INTO mutes (user_id, until) VALUES (?, ?)", (user_id, until))
            await db.commit()

        logger.info(f"User {user_id} muted until {until}.")

        context.job_queue.run_once(unmute_user, when=until, data=(chat_id, user_id), name=str(user_id))

        if chat_type == "supergroup":
            await context.bot.restrict_chat_member(
                chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until
            )

            await update.message.reply_text(
                f"🚫 Пользователь @{update.message.from_user.username} был временно заблокирован на 1 час за токсичность.",
            )
        else:
            await update.message.delete()
            await update.message.reply_text(
                f"🚫 Пользователь @{update.message.from_user.username} был временно заблокирован на 1 час за токсичность. Сообщения будут удаляться.",
                quote=False,
            )


async def unmute_user(context: CallbackContext):
    job = context.job or None
    chat_id, user_id = job.data if job else context.args

    logger.info(f"Unmuting user {user_id} in chat {chat_id}.")

    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute("DELETE FROM mutes WHERE user_id = ?", (user_id,))
        await db.commit()

    chat = await context.bot.get_chat(chat_id)
    if chat.type == "supergroup":
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=True))

    await context.bot.send_message(
        chat_id,
        text=f"✅ Пользователь <a href='tg://user?id={user_id}'>@{user_id}</a> был разблокирован.",
        parse_mode=ParseMode.HTML,
    )


async def start(update: Update, context: CallbackContext):
    logger.info("Received /start command.")
    await update.message.reply_text("👋 Привет! Я AntiToxicBot, который борется с токсичностью. Пиши аккуратнее!")


async def muted_users(update: Update, context: CallbackContext):
    logger.info("Received /muted_users command.")
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute("SELECT user_id, until FROM mutes") as cursor:
            rows = await cursor.fetchall()
            if rows:
                message = "🚫 Временно заблокированные пользователи:\n\n"
                for row in rows:
                    user_id, until = row
                    until = datetime.strptime(until.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    message += (
                        f"- <a href='tg://user?id={user_id}'>{user_id}</a> до {until.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
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


def main():
    logger.info("Starting bot...")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    job_queue = JobQueue()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("muted_users", muted_users))
    app.add_handler(CommandHandler("unmute", unmute_command, filters=filters.ChatType.GROUPS))
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
