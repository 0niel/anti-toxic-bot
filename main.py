import logging
from datetime import datetime, timedelta

import aiosqlite
from perspective import Attribute, Perspective
from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CallbackContext, CommandHandler, JobQueue, MessageHandler, filters

from config import config

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

p = Perspective(key=config.PERSPECTIVE_API_KEY)


async def init_db():
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


async def check_message(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type

    response = await p.score(
        text, attributes=[Attribute.SEVERE_TOXICITY, Attribute.TOXICITY, Attribute.SEXUALLY_EXPLICIT]
    )

    if response["severe_toxicity"] > 0.9 or response["toxicity"] > 0.9 or response["sexually_explicit"] > 0.9:
        until = datetime.utcnow() + timedelta(hours=1)
        async with aiosqlite.connect("mute_bot.db") as db:
            await db.execute("INSERT OR REPLACE INTO mutes (user_id, until) VALUES (?, ?)", (user_id, until))
            await db.commit()

        if chat_type == "supergroup":
            context.job_queue.run_once(unmute_user, when=until, data=(chat_id, user_id), name=str(user_id))

            await context.bot.restrict_chat_member(
                chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until
            )

            await update.message.reply_text(
                f"🚫 Пользователь @{update.message.from_user.username} был замучен на 1 час за токсичность.",
            )
        else:
            context.job_queue.run_once(unmute_user, when=until, data=(chat_id, user_id), name=str(user_id))
            await update.message.delete()
            await update.message.reply_text(
                f"🚫 Пользователь @{update.message.from_user.username} был замучен на 1 час за токсичность. Сообщения будут удаляться.",
                quote=False,
            )


async def unmute_user(context: CallbackContext):
    job = context.job
    chat_id, user_id = job.data

    async with aiosqlite.connect("mute_bot.db") as db:
        await db.execute("DELETE FROM mutes WHERE user_id = ?", (user_id,))
        await db.commit()

    chat = await context.bot.get_chat(chat_id)
    if chat.type == "supergroup":
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=True))

    await context.bot.send_message(
        chat_id,
        text=f"✅ Пользователь <a href='tg://user?id={user_id}'>@{user_id}</a> был размучен.",
        parse_mode=ParseMode.HTML,
    )


async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Привет! Я AntiToxicBot, который борется с токсичностью. Пиши аккуратнее!")


async def muted_users(update: Update, context: CallbackContext):
    async with aiosqlite.connect("mute_bot.db") as db:
        async with db.execute("SELECT user_id, until FROM mutes") as cursor:
            rows = await cursor.fetchall()
            if rows:
                message = "Замученные пользователи:\n\n"
                for row in rows:
                    user_id, until = row
                    until = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
                    message += (
                        f"- <a href='tg://user?id={user_id}'>{user_id}</a> до {until.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text("Нет замученных пользователей.")


def main():
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    job_queue = JobQueue()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("muted_users", muted_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))

    job_queue.set_application(app)
    job_queue.start()

    app.run_polling()


if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    main()
