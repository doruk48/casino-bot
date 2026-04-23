# games/blackjack/engine.py - Blackjack Oyun Mantığı
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

from config import BET_WINDOW, BLACKJACK_TURN, JACKPOT_MINIMUM
from core.state import finish_game, cleanup, _state_lock, _active_games
from core.economy import add_balance, remove_balance
from core.stats import update_stats, update_win_rate
from core.users import get_user
from utils.format import format_amount, logger
from features.jackpot import _get_jackpot_amount, _add_to_jackpot, _reset_jackpot, create_jackpot_image
from games.blackjack.cards import _new_deck, _card_val, _hand_val, combine_cards, combine_cards_with_hidden

# Blackjack durumu (RAM'de)
_bj: dict[int, dict] = {}

def _bj_kb(game_id: str):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit", callback_data=f"bj_hit:{game_id}"),
        InlineKeyboardButton("✋ Stand", callback_data=f"bj_stand:{game_id}"),
    ]])

# ═══════════════════════════════════════════════════════════════
#  BAHİS ZAMANLAYICISI
# ═══════════════════════════════════════════════════════════════
async def _bj_bet_timer(ctx, chat_id, game_id):
    await asyncio.sleep(BET_WINDOW)
    
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    if not bj["players"]:
        await ctx.bot.send_message(chat_id, "❌ Blackjack iptal — kimse katılmadı.")
        await finish_game(chat_id, game_id, "iptal", ctx)
        await cleanup(chat_id)
        return
    
    bj["state"] = "DEALING"
    deck = _new_deck()
    bj["deck"] = deck
    
    for uid in bj["order"]:
        bj["players"][uid]["hand"] = [deck.pop(), deck.pop()]
        bj["players"][uid]["state"] = "PLAYING"
        bj["players"][uid]["cards_sent"] = False
    
    bj["dealer"] = [deck.pop(), deck.pop()]
    bj["current"] = 0
    
    dealer_img = combine_cards_with_hidden(bj["dealer"])
    first_card_val = _card_val(bj["dealer"][0][0])
    await ctx.bot.send_photo(
        chat_id,
        photo=dealer_img,
        caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                f"Açık kart: {first_card_val}\nKapalı kart: ?",
        parse_mode="HTML"
    )
    
    for uid in bj["order"]:
        p = bj["players"][uid]
        hand_img = combine_cards(p["hand"])
        await ctx.bot.send_photo(
            chat_id,
            photo=hand_img,
            caption=f"🃏 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🃏 Eliniz: {_hand_val(p['hand'])}",
            parse_mode="HTML"
        )
        p["cards_sent"] = True
    
    await _bj_next(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  SIRADAKİ OYUNCU
# ═══════════════════════════════════════════════════════════════
async def _bj_next(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    if bj["current"] >= len(bj["order"]):
        await _bj_dealer(ctx, chat_id, game_id)
        return
    
    uid = bj["order"][bj["current"]]
    p = bj["players"][uid]
    
    if p["state"] != "PLAYING":
        bj["current"] += 1
        await _bj_next(ctx, chat_id, game_id)
        return
    
    val = _hand_val(p["hand"])
    
    await ctx.bot.send_message(
        chat_id,
        f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!",
        reply_markup=_bj_kb(game_id),
        parse_mode="HTML"
    )
    
    p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, uid))

# ═══════════════════════════════════════════════════════════════
#  ZAMAN AŞIMI
# ═══════════════════════════════════════════════════════════════
async def _bj_timeout(ctx, chat_id, game_id, uid):
    await asyncio.sleep(BLACKJACK_TURN)
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    p = bj["players"].get(uid)
    if not p or p["state"] != "PLAYING":
        return
    p["state"] = "STAND"
    bj["current"] += 1
    await ctx.bot.send_message(
        chat_id,
        f"⏰ <b>{p['name']}</b> süre doldu, otomatik STAND!",
        parse_mode="HTML"
    )
    await _bj_next(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  HIT / STAND CALLBACK
# ═══════════════════════════════════════════════════════════════
async def bj_callback(update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        action, game_id = query.data.split(":", 1)
    except:
        return
    
    user = query.from_user
    chat_id = query.message.chat_id
    bj = _bj.get(chat_id)
    
    if not bj or bj["game_id"] != game_id:
        await query.answer("Oyun bitti.", show_alert=True)
        return
    
    if bj["current"] >= len(bj["order"]) or bj["order"][bj["current"]] != user.id:
        await query.answer("Şu an sıranız değil!", show_alert=True)
        return
    
    p = bj["players"].get(user.id)
    if not p or p["state"] != "PLAYING":
        await query.answer("Sıranız bitti.", show_alert=True)
        return
    
    if p.get("task"):
        p["task"].cancel()
    
    if action == "bj_hit":
        card = bj["deck"].pop()
        p["hand"].append(card)
        val = _hand_val(p["hand"])
        hand_img = combine_cards(p["hand"])
        
        if val > 21:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"💥 <b>BUST!</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n🃏 Eliniz: {val}\n❌ Kaybettiniz!",
                    parse_mode="HTML"
                )
            )
            p["state"] = "BUST"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        elif val == 21:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🎉 <b>BLACKJACK! 21</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n✅ Otomatik Stand",
                    parse_mode="HTML"
                )
            )
            p["state"] = "STAND"
            bj["current"] += 1
            await _bj_next(ctx, chat_id, game_id)
            
        else:
            await query.edit_message_media(
                media=InputMediaPhoto(
                    media=hand_img,
                    caption=f"🃏 <b>SIRA SENDE</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 {p['name']}\n🃏 Eliniz: {val}\n⏳ {BLACKJACK_TURN} saniyen var!",
                    parse_mode="HTML"
                ),
                reply_markup=_bj_kb(game_id)
            )
            p["task"] = asyncio.create_task(_bj_timeout(ctx, chat_id, game_id, user.id))
    
    elif action == "bj_stand":
        hand_val = _hand_val(p["hand"])
        p["state"] = "STAND"
        bj["current"] += 1
        
        hand_img = combine_cards(p["hand"])
        await query.edit_message_media(
            media=InputMediaPhoto(
                media=hand_img,
                caption=f"✋ <b>STAND</b>\n━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {p['name']}\n🃏 Eliniz: {hand_val} ile durdu.",
                parse_mode="HTML"
            )
        )
        await _bj_next(ctx, chat_id, game_id)

# ═══════════════════════════════════════════════════════════════
#  KURPİYERİN SIRASI VE FİNAL
# ═══════════════════════════════════════════════════════════════
async def _bj_dealer(ctx, chat_id, game_id):
    bj = _bj.get(chat_id)
    if not bj or bj["game_id"] != game_id:
        return
    
    hand = bj["dealer"]
    while _hand_val(hand) < 17:
        hand.append(bj["deck"].pop())
    
    dval = _hand_val(hand)
    dealer_img = combine_cards(hand)
    
    await ctx.bot.send_photo(
        chat_id,
        photo=dealer_img,
        caption=f"🎩 <b>KURPİYER</b>\n━━━━━━━━━━━━━━━━━━━━━\n📊 Toplam: {dval}",
        parse_mode="HTML"
    )
    
    results = [
        f"🏁 <b>BLACKJACK - FİNAL TABLOSU</b>",
        f"━━━━━━━━━━━━━━━━━━━━━"
    ]
    total_payout = 0
    
    jackpot_result = f"dealer:{dval}"
    
    for uid in bj["order"]:
        p = bj["players"][uid]
        pval = _hand_val(p["hand"])
        bet = p["bet"]
        
        # ═══════════════════════════════════════════════════════
        # JACKPOT İŞLEMLERİ
        # ═══════════════════════════════════════════════════════
        if p["state"] == "BUST":
            await _add_to_jackpot("blackjack", bet)
            jackpot_result += "|BUST"
            
        elif pval < dval and dval <= 21:
            commission = int(bet * 0.25)
            if commission > 0:
                await _add_to_jackpot("blackjack", commission)
            jackpot_result += "|LOSE"
            
        elif pval == dval:
            commission = int(bet * 0.10)
            if commission > 0:
                await _add_to_jackpot("blackjack", commission)
            jackpot_result += "|PUSH"
            
        elif pval == 21:
            jackpot_amount = await _get_jackpot_amount("blackjack")
            if jackpot_amount > JACKPOT_MINIMUM:
                total_win = bet + jackpot_amount
                await add_balance(uid, total_win, "win", f"Blackjack JACKPOT! game:{game_id}")
                await update_stats(uid, total_win)
                await update_win_rate(uid, "blackjack", True)
                
                user = await get_user(uid)
                player_name = user.get("display_name", str(uid)) if user else str(uid)
                jackpot_img = create_jackpot_image("blackjack", player_name)
                caption = (
                    f"🃏 <b>BLACKJACK JACKPOT KAZANDIN!</b> 🃏\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 GAME ID: {game_id}\n"
                    f"🃏 Oyun: Blackjack (21)\n"
                    f"💰 Havuz Payın: {format_amount(jackpot_amount)}\n"
                    f"🎁 Bahis İaden: {format_amount(bet)}\n"
                    f"💳 Toplam: {format_amount(total_win)}\n\n"
                    f"🎉 <b>TEBRİKLER!</b> 🎉"
                )
                
                try:
                    if jackpot_img:
                        await ctx.bot.send_photo(chat_id, photo=jackpot_img, caption=caption, parse_mode="HTML")
                    else:
                        await ctx.bot.send_message(chat_id, caption, parse_mode="HTML")
                except:
                    pass
                
                await _reset_jackpot("blackjack")
                logger.info(f"🃏 Blackjack JACKPOT dağıtıldı: {format_amount(jackpot_amount)}. Kazanan: {player_name}")
            
            jackpot_result += "|BLACKJACK"
        
        # ═══════════════════════════════════════════════════════
        # NORMAL KAZANÇ/KAYIP
        # ═══════════════════════════════════════════════════════
        if p["state"] == "BUST":
            results.append(f"❌ {p['name']}: {pval} (BUST) → -{format_amount(bet)}")
            await update_win_rate(uid, "blackjack", False)
            
        elif dval > 21:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} (BUST) → +{format_amount(payout)}")
            await update_win_rate(uid, "blackjack", True)
            
        elif pval > dval:
            payout = bet * 2
            await add_balance(uid, payout, "win", f"BJ game:{game_id}")
            await update_stats(uid, payout)
            total_payout += payout
            results.append(f"✅ {p['name']}: {pval} vs {dval} → +{format_amount(payout)}")
            await update_win_rate(uid, "blackjack", True)
            
        elif pval == dval:
            await add_balance(uid, bet, "refund", f"BJ game:{game_id}")
            results.append(f"🤝 {p['name']}: {pval} vs {dval} → İADE")
            
        else:
            results.append(f"❌ {p['name']}: {pval} vs {dval} → -{format_amount(bet)}")
            await update_win_rate(uid, "blackjack", False)
    
    results.append("━━━━━━━━━━━━━━━━━━━━━")
    results.append(f"🏧 DAĞITILAN TOPLAM: {format_amount(total_payout)}")
    results.append("✨ Yeni oyun için /blackjack yazın!")
    
    await ctx.bot.send_message(chat_id, "\n".join(results), parse_mode="HTML")
    
    del _bj[chat_id]
    await finish_game(chat_id, game_id, jackpot_result, ctx)
    await cleanup(chat_id)
