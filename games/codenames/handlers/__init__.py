"""
Codenames oyunu için tüm handler'ların kaydedilmesi.
"""
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, filters
from .lobby import cstart, cjoin, ciptal
from .team_setup import ckaptan, csec, csozcu, cistifa
from .captain import cipucu
from .ingame import ctahmin, cpas, cdurum, cson
from .callbacks import button_handler
from .help import chelp


def register_handlers(app: Application):
    """Tüm Codenames komutlarını ve callback'lerini kaydeder."""
    # Lobi komutları
    app.add_handler(CommandHandler("cstart", cstart))
    app.add_handler(CommandHandler("cjoin", cjoin))
    app.add_handler(CommandHandler("ciptal", ciptal))

    # Takım kurulum
    app.add_handler(CommandHandler("ckaptan", ckaptan))
    app.add_handler(CommandHandler("csec", csec))
    app.add_handler(CommandHandler("csozcu", csozcu))
    app.add_handler(CommandHandler("cistifa", cistifa))

    # Kaptan DM komutu
    app.add_handler(CommandHandler("cipucu", cipucu, filters=filters.ChatType.PRIVATE))

    # Oyun içi komutlar
    app.add_handler(CommandHandler("ctahmin", ctahmin))
    app.add_handler(CommandHandler("cpas", cpas))
    app.add_handler(CommandHandler("cdurum", cdurum))
    app.add_handler(CommandHandler("cson", cson))

    # Yardım
    app.add_handler(CommandHandler("chelp", chelp))

    # Buton callback'leri
    app.add_handler(CallbackQueryHandler(button_handler))
