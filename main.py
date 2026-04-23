# main.py - Casinobot Pro | Ana Orkestra Şefi
import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Telegram
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    PreCheckoutQueryHandler, MessageHandler, filters, ChatMemberHandler
)

# Config
from config import (
    BOT_TOKEN, LOG_FILE, BACKUP_DIR, DATABASE_NAME, BASE_DIR
)

# Core
from core.database import init_db, get_db
from core.state import _state_lock, _active_games

# Features
from features.help import cmd_start, cmd_help
from features.balance import cmd_balance
from features.leaderboard_cmd import cmd_leaderboard
from features.daily_cmd import cmd_daily
from features.transfer import cmd_moneys
from features.shop import cmd_buy, buy_callback, pre_checkout_callback, successful_payment_callback
from features.menu import cmd_menu, menu_callback
from features.admin import cmd_id, cmd_addbalance, cmd_setbalance, cmd_cleanup, cmd_stats
from features.jackpot import cmd_jackpot, process_jackpot_on_game_end

# Games
from games.roulette.handlers import cmd_rulet, cmd_red, cmd_black, cmd_green, cmd_number, cmd_numbers
from games.blackjack.handlers import cmd_blackjack, cmd_bj
from games.blackjack.engine import bj_callback
from games.dice.handlers import cmd_dicebet, cmd_dice
from games.dice.engine import dice_callback
from games.wheel.handlers import cmd_wheelbet, cmd_wheel
from games.scratch.handlers import cmd_kazisolo, cmd_kazibet, cmd_kazi

# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  POST INIT / SHUTDOWN
# ═══════════════════════════════════════════════════════════════
async def post_init(app):
    await init_db()
    await cleanup_stuck_games()
    asyncio.create_task(backup_task())
    logger.info("🎰 CasiniBot-Pro başlatıldı!")
    logger.info(f"📁 BASE_DIR: {BASE_DIR}")
    logger.info(f"💾 Veritabanı: {DATABASE_NAME}")

async def post_shutdown(app):
    from core.database import _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("🔌 MongoDB bağlantısı kapatıldı.")
    logger.info("👋 CasiniBot-Pro kapatıldı.")

async def cleanup_stuck_games():
    db = await get_db()
    await db.games.update_many(
        {"state": {"$in": ["OPEN", "PLAYING", "CALCULATING", "BETTING", "DEALING", "ROLLING"]}},
        {"$set": {"state": "FINISHED", "finished_at": datetime.now()}}
    )
    logger.info("🧹 Takılı kalmış oyunlar temizlendi.")

async def backup_task():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(BACKUP_DIR, f"casinobot-pro_{ts}.json")
            db = await get_db()
            users = await db.users.find().to_list(length=None)
            transactions = await db.transactions.find().to_list(length=None)
            games = await db.games.find().to_list(length=None)
            user_stats = await db.user_stats.find().to_list(length=None)
            
            import json
            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            backup_data = {
                "users": users, "transactions": transactions,
                "games": games, "user_stats": user_stats,
                "backup_date": datetime.now().isoformat()
            }
            
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, default=json_serial, indent=2)
            
            logger.info(f"📦 Backup alındı: {dest}")
            backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')])
            for old in backups[:-7]:
                os.remove(os.path.join(BACKUP_DIR, old))
        except Exception as e:
            logger.error(f"Backup hatası: {e}")

async def error_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Hata: {ctx.error}", exc_info=ctx.error)
    try:
        if update and update.effective_chat:
            await ctx.bot.send_message(update.effective_chat.id, "❌ Bir hata oluştu. Lütfen tekrar deneyin.")
    except:
        pass

# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN ayarlanmamış!")
        return
    
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # --- GENEL KOMUTLAR ---
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("moneys", cmd_moneys))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("id", cmd_id))
    
    # --- RULET ---
    app.add_handler(CommandHandler("rulet", cmd_rulet))
    app.add_handler(CommandHandler("red", cmd_red))
    app.add_handler(CommandHandler("black", cmd_black))
    app.add_handler(CommandHandler("green", cmd_green))
    app.add_handler(CommandHandler("number", cmd_number))
    app.add_handler(CommandHandler("numbers", cmd_numbers))
    
    # --- BLACKJACK ---
    app.add_handler(CommandHandler("blackjack", cmd_blackjack))
    app.add_handler(CommandHandler("bj", cmd_bj))
    app.add_handler(CallbackQueryHandler(bj_callback, pattern=r"^bj_(hit|stand):"))
    
    # --- ZAR ---
    app.add_handler(CommandHandler("dicebet", cmd_dicebet))
    app.add_handler(CommandHandler("dice", cmd_dice))
    app.add_handler(CallbackQueryHandler(dice_callback, pattern=r"^dice_roll:"))
    
    # --- ÇARKIFELEK ---
    app.add_handler(CommandHandler("wheelbet", cmd_wheelbet))
    app.add_handler(CommandHandler("wheel", cmd_wheel))
    
    # --- KAZI KAZAN ---
    app.add_handler(CommandHandler("kazisolo", cmd_kazisolo))
    app.add_handler(CommandHandler("kazibet", cmd_kazibet))
    app.add_handler(CommandHandler("kazi", cmd_kazi))
    
    # --- VIP KASA ---
    app.add_handler(CommandHandler("buy", cmd_buy))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # --- ADMIN ---
    app.add_handler(CommandHandler("addbalance", cmd_addbalance))
    app.add_handler(CommandHandler("setbalance", cmd_setbalance))
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CommandHandler("stats", cmd_stats))
    
    # --- JACKPOT ---
    app.add_handler(CommandHandler("jackpot", cmd_jackpot))
    
    # --- MENÜ ---
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    
    # --- HATA ---
    app.add_error_handler(error_handler)
    
    logger.info("🚀 Handler'lar yüklendi. Polling başlıyor...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=[
            Update.MESSAGE, Update.CALLBACK_QUERY,
            Update.PRE_CHECKOUT_QUERY, Update.CHAT_MEMBER, Update.MY_CHAT_MEMBER
        ]
    )

if __name__ == "__main__":
    main()
