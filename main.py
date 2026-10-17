import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from app import admin, db, scheduler, worker
from app.config import ADMIN_IDS, BOT_TOKEN, DB_PATH


async def main() -> None:
    if not BOT_TOKEN:
        sys.exit("BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... yozing (README.md ga qarang).")
    if not ADMIN_IDS:
        logging.warning("ADMIN_IDS bo'sh: botga /start bosib ID ingizni bilib oling va .env ga yozing.")
    db.init()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(worker.router)
    await bot.set_my_commands([BotCommand(command="start", description="Boshlash")], scope=BotCommandScopeDefault())
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin.ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:  # the admin has not opened the bot yet
            logging.warning("admin %s commands not set: %s", admin_id, e)
    sched = scheduler.setup(bot)
    sched.start()
    logging.info("Ishchilar boti ishga tushdi. Adminlar: %s. Baza: %s", sorted(ADMIN_IDS) or "yo'q", DB_PATH)
    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main())
