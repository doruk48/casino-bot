# features/menu.py - Menü Sistemi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bson.decimal128 import Decimal128
from decimal import Decimal

from config import LEADERBOARD_SIZE
from core.database import get_db
from core.economy import get_balance
from core.users import get_or_create_user, get_user
from core.leaderboard import get_leaderboard
from core.daily import get_daily_bonus, can_claim_daily
from core.economy import _get_lock
from utils.format import format_amount
from utils.helpers import get_level
from datetime import datetime
from bson.decimal128 import Decimal128

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.full_name)
    bal = await get_balance(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"),
            InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")
        ],
        [
            InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"),
            InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")
        ],
        [
            InlineKeyboardButton("🎟️ KAZI KAZAN", callback_data="menu_scratch"),
            InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance")
        ],
        [
            InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard"),
            InlineKeyboardButton("🎁 GÜNLÜK BONUS", callback_data="menu_daily")
        ],
        [
            InlineKeyboardButton("💝 DESTEK OL", callback_data="menu_donate"),
            InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")
        ]
    ]
    
    await update.message.reply_text(
        f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {user.full_name}\n"
        f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
        f"Bir oyun seçin veya bilgi almak için butonlara tıklayın:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    ana_menu_button = [[InlineKeyboardButton("🏠 ANA MENÜ", callback_data="menu_main")]]
    
    if data == "menu_roulette":
        await query.edit_message_text(
            "🎰 <b>RULET NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /rulet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde bahis yapın:\n"
            "   🔴 /red &lt;miktar&gt; - Kırmızıya bahis\n"
            "   ⚫ /black &lt;miktar&gt; - Siyaha bahis\n"
            "   🟢 /green &lt;miktar&gt; - Yeşile bahis (0)\n"
            "   🔢 /number &lt;sayı&gt; &lt;miktar&gt; - Tek sayı\n"
            "   🔢 /numbers &lt;1,2,3&gt; &lt;miktar&gt; - Çoklu sayı\n\n"
            "💰 Çarpanlar: Kırmızı/Siyah 2x, Yeşil 72x, Sayı 36x\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_blackjack":
        await query.edit_message_text(
            "🃏 <b>BLACKJACK NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /blackjack ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /bj &lt;miktar&gt; ile bahis yapın\n"
            "3️⃣ Kartlar dağıtılır, sırayla oynarsınız:\n"
            "   🃏 Hit - Yeni kart al\n"
            "   ✋ Stand - Kart dur\n\n"
            "📊 Kurallar:\n"
            "• 21'e en yakın olan kazanır\n"
            "• 21'i geçersen kaybedersin\n"
            "• Kurpiyer 17'de durur\n"
            "• Kazanırsan 2x alırsın\n\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_dice":
        await query.edit_message_text(
            "🎲 <b>ZAR OYUNU (PvP) NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /dicebet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /dice &lt;miktar&gt; ile katılın\n"
            "3️⃣ En az 2 oyuncu gerekir\n"
            "4️⃣ Sırayla butona tıklayarak zar atın\n"
            "5️⃣ En yüksek zar toplamı kazanır\n"
            "6️⃣ Beraberlikte havuz bölüşülür\n\n"
            "💰 Kazanan tüm havuzu alır!\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_wheel":
        await query.edit_message_text(
            "🎡 <b>ÇARKIFELEK NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ /wheelbet ile oyun başlatın\n"
            "2️⃣ 25 saniye içinde /wheel &lt;miktar&gt; ile bahis yapın\n"
            "3️⃣ Çark döner ve sonuç belirlenir\n\n"
            "💰 Kazançlar:\n"
            "• 💀 PASS → Bahis kaybedilir\n"
            "• 🔄 İADE → Bahis iade\n"
            "• 2x, 3x, 5x, 10x, 15x, 25x, 50x, 100x → Bahis × çarpan\n"
            "• 🎰 JACKPOT → Havuz dağıtılır\n\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_scratch":
        await query.edit_message_text(
            "🎟 <b>KAZI KAZAN NASIL OYNANIR?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🎟️ <b>TEK KİŞİLİK</b>\n"
            "📌 /kazisolo &lt;miktar&gt; - Tek başına oyna\n\n"
            "🎟️ <b>TURNUVASI</b>\n"
            "1️⃣ /kazibet - Turnuva başlat\n"
            "2️⃣ /kazi &lt;miktar&gt; - Turnuvaya katıl (en az 2 kişi)\n\n"
            "🏆 Kazanma şartı:\n"
            "6 kutuda 3 aynı çarpan = KAZANÇ!\n\n"
            "💰 Çarpanlar: 2x, 3x, 5x, 10x, 15x, 25x, 50x, 100x, 250x\n"
            "🎯 Bol şans!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_balance":
        u = await get_user(user.id)
        if u:
            db = await get_db()
            
            current_balance = u.get("balance", 0)
            if isinstance(current_balance, Decimal128):
                current_balance = int(current_balance.to_decimal())
            elif isinstance(current_balance, Decimal):
                current_balance = int(current_balance)
            else:
                current_balance = int(current_balance) if current_balance else 0
            
            try:
                higher_count = await db.users.count_documents({
                    "$or": [
                        {"balance": {"$gt": Decimal128(str(current_balance))}},
                        {"balance": {"$gt": current_balance}}
                    ]
                })
            except:
                higher_count = 0
            rank = higher_count + 1
            
            lvl, emoji = get_level(current_balance)
            
            await query.edit_message_text(
                f"📌 <b>Verilerim</b>\n\n"
                f"👤 <b>{user.full_name}</b>\n\n"
                f"🤴 Seviye 🔘 {lvl} {emoji}\n\n"
                f"🏧 Bakiye 🔘 {format_amount(u['balance'])}\n\n"
                f"🌍 Genel Sıralamanız 🔘 {rank}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎮 Oynanan oyun: {u.get('games_played', 0)}\n"
                f"📊 Toplam bahis: {format_amount(u.get('total_wagered', 0))}\n"
                f"🏆 Toplam kazanç: {format_amount(u.get('total_won', 0))}",
                reply_markup=InlineKeyboardMarkup(ana_menu_button),
                parse_mode="HTML"
            )
        else:
            await query.edit_message_text("❌ Kullanıcı bulunamadı.")
            
    elif data == "menu_leaderboard":
        rows = await get_leaderboard(LEADERBOARD_SIZE)
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 <b>LİDERLİK TABLOSU</b>", "━━━━━━━━━━━━━━━━━━━━━"]
        for i, r in enumerate(rows):
            lvl, emoji = get_level(r["balance"])
            medal = medals[i] if i < 3 else f"{i+1}."
            name = r.get("display_name", "Bilinmeyen")[:15]
            lines.append(f"{medal} {name} [{lvl}]{emoji} — {format_amount(r['balance'])}")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_daily":
        u = await get_or_create_user(user.id, user.username, user.full_name)
        db = await get_db()
        lock = await _get_lock(user.id)
        
        async with lock:
            user_data = await db.users.find_one({"telegram_id": user.id})
            last_daily = user_data.get("last_daily")
            current_streak = user_data.get("daily_streak", 0)
            
            can_claim, hours_left = can_claim_daily(last_daily)
            
            if not can_claim:
                await query.edit_message_text(
                    f"⏰ <b>Günlük bonusunuzu zaten aldınız!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎁 Sonraki bonus: <b>{hours_left} saat</b> sonra\n"
                    f"📈 Mevcut seri: <b>{current_streak} gün</b>",
                    reply_markup=InlineKeyboardMarkup(ana_menu_button),
                    parse_mode="HTML"
                )
                return
            
            new_streak = current_streak + 1
            bonus_amount = get_daily_bonus(current_streak)
            
            await db.users.update_one(
                {"telegram_id": user.id},
                {"$inc": {"balance": Decimal128(str(bonus_amount))},
                 "$set": {"last_daily": datetime.now().isoformat(), "daily_streak": new_streak, "updated_at": datetime.now()}}
            )
            
            await db.transactions.insert_one({
                "to_id": user.id,
                "amount": Decimal128(str(bonus_amount)),
                "type": "daily",
                "description": f"{new_streak}. gün bonusu",
                "created_at": datetime.now()
            })
            
            new_balance = await get_balance(user.id)
            next_bonus = get_daily_bonus(new_streak)
            
            await query.edit_message_text(
                f"🎁 <b>GÜNLÜK BONUS!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>{user.full_name}</b>\n"
                f"📅 Seri: <b>{new_streak}</b> gün\n"
                f"💰 Kazanılan: <b>+{format_amount(bonus_amount)}</b>\n"
                f"💳 Yeni bakiye: <b>{format_amount(new_balance)}</b>\n\n"
                f"🎯 Yarınki bonus: <b>{format_amount(next_bonus)}</b>",
                reply_markup=InlineKeyboardMarkup(ana_menu_button),
                parse_mode="HTML"
            )
        

    elif data == "menu_donate":
        await query.edit_message_text(
            "💝 <b>BOTA DESTEK OL</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎰 Casinobot'u seviyor musun?\n"
            "Gelişimine katkıda bulunmak ister misin?\n\n"
            "✨ Bu tamamen <b>gönüllü bir bağıştır</b>.\n"
            "🎁 Karşılığında <b>hiçbir şey almazsınız</b>.\n"
            "❤️ Sadece teşekkür ve özel 'Destekçi' rozeti!\n\n"
            "👇 /destek yazarak bağış yapabilirsin.",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
    )
        
    elif data == "menu_help":
        await query.edit_message_text(
            "🎰 <b>CASİNİBOT KOMUTLAR</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 <b>HESAP</b>\n"
            "/start, /balance, /daily, /moneys, /leaderboard\n\n"
            "🎡 <b>RULET</b>\n"
            "/rulet, /red, /black, /green, /number\n\n"
            "🎲 <b>ZAR (PvP)</b>\n"
            "/dicebet, /dice\n\n"
            "🎡 <b>ÇARKIFELEK</b>\n"
            "/wheelbet, /wheel\n\n"
            "🎟 <b>KAZI KAZAN</b>\n"
            "/kazisolo, /kazibet, /kazi\n\n"
            "🃏 <b>BLACKJACK</b>\n"
            "/blackjack, /bj\n\n"
            "🌟 <b>VIP KASA</b>\n"
            "/buy\n\n"
            "🎰 <b>JACKPOT</b>\n"
            "/jackpot\n\n"
            "💡 <code>allin</code> yazarak tüm bakiyeni yatırabilirsin!",
            reply_markup=InlineKeyboardMarkup(ana_menu_button),
            parse_mode="HTML"
        )
        
    elif data == "menu_main":
        bal = await get_balance(user.id)
        main_keyboard = [
            [
                InlineKeyboardButton("🎰 RULET", callback_data="menu_roulette"),
                InlineKeyboardButton("🃏 BLACKJACK", callback_data="menu_blackjack")
            ],
            [
                InlineKeyboardButton("🎲 ZAR (PvP)", callback_data="menu_dice"),
                InlineKeyboardButton("🎡 ÇARKIFELEK", callback_data="menu_wheel")
            ],
            [
                InlineKeyboardButton("🎟️ KAZI KAZAN", callback_data="menu_scratch"),
                InlineKeyboardButton("💰 BAKİYE", callback_data="menu_balance")
            ],
            [
                InlineKeyboardButton("🏆 LİDERLİK", callback_data="menu_leaderboard"),
                InlineKeyboardButton("🎁 GÜNLÜK BONUS", callback_data="menu_daily")
            ],
            [
                InlineKeyboardButton("💝 DESTEK OL", callback_data="menu_donate"),
                InlineKeyboardButton("❓ YARDIM", callback_data="menu_help")
            ]
        ]
        await query.edit_message_text(
            f"🎮 <b>CASİNİBOT ANA MENÜ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {user.full_name}\n"
            f"💰 Bakiyeniz: {format_amount(bal)}\n\n"
            f"Bir oyun seçin veya bilgi almak için butonlara tıklayın:",
            reply_markup=InlineKeyboardMarkup(main_keyboard),
            parse_mode="HTML"
  )
