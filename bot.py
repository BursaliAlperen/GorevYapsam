"""
🚀 GÖREV YAPSAM BOT - DÜZENLENMİŞ VERSİYON
Render için optimize edilmiştir.
"""

import os
import asyncio
import telebot
from telebot import types
from telebot.async_telebot import AsyncTeleBot
import threading
import time
from datetime import datetime
import requests
import json
import pytz
from dotenv import load_dotenv
import cachetools
import firebase_admin
from firebase_admin import credentials, firestore
import schedule
from typing import Dict, Optional

# ================= 1. ÇEVRE DEĞİŞKENLERİ =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")

# ================= 2. FIREBASE FIRESTORE BAĞLANTISI =================
try:
    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    
    if firebase_creds_json:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'projectId': 'gorev-yapsam-bot',
        })
        db = firestore.client()
        print("✅ Firebase Firestore bağlantısı başarılı!")
    else:
        print(f"⚠️ Firebase credentials bulunamadı, local modda çalışıyor.")
        db = None
except Exception as e:
    print(f"❌ Firebase bağlantı hatası: {e}")
    db = None

# ================= 3. BOT KONFİGÜRASYONU =================
bot = AsyncTeleBot(TOKEN, parse_mode='HTML')  # threaded=True kaldırıldı

# ================= 4. CACHE SİSTEMİ =================
price_cache = cachetools.TTLCache(maxsize=100, ttl=30)
user_cache = cachetools.TTLCache(maxsize=1000, ttl=60)

# ================= 5. FİYAT SİSTEMİ =================
def get_trx_price():
    """Canlı TRX/TRY fiyatını al"""
    try:
        if 'trx_price' in price_cache:
            return price_cache['trx_price']
        
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            price_cache['trx_price'] = price
            return price
        
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=try",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['tron']['try'])
            price_cache['trx_price'] = price
            return price
        
    except Exception as e:
        print(f"Fiyat çekme hatası: {e}")
    
    return 0.35

# ================= 6. DİL SİSTEMİ (KISALTILMIŞ) =================
TRANSLATIONS = {
    'tr': {
        'main_menu': {
            'title': '🚀 <b>GÖREV YAPSAM BOT</b>',
            'welcome': '👋 <b>Merhaba {name}!</b>',
        },
        'buttons': {
            'do_task': '🤖 GÖREV YAP',
            'my_balance': '💰 BAKİYEM',
            'back_menu': '🏠 ANA MENÜ',
            'refresh': '🔄 YENİLE',
        }
    },
    'az': {
        'main_menu': {
            'title': '🚀 <b>TAPŞIRIQ EDƏM BOT</b>',
            'welcome': '👋 <b>Salam {name}!</b>',
        },
        'buttons': {
            'do_task': '🤖 TAPŞIRIQ ET',
            'my_balance': '💰 BALANSIM',
            'back_menu': '🏠 ƏSAS MENYU',
            'refresh': '🔄 YENİLƏ',
        }
    }
}

def get_translation(lang: str, key_path: str) -> str:
    """Çeviri metnini getir"""
    try:
        keys = key_path.split('.')
        current = TRANSLATIONS.get(lang, TRANSLATIONS['tr'])
        for key in keys:
            current = current[key]
        return str(current) if not isinstance(current, dict) else str(current)
    except:
        return f"[{key_path}]"

# ================= 7. FIRESTORE İŞLEMLERİ =================
async def get_user(user_id: int) -> Optional[Dict]:
    """Kullanıcı bilgilerini getir"""
    try:
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            return user_cache[cache_key]
        
        if db:
            user_ref = db.collection('users').document(str(user_id))
            user_doc = user_ref.get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_data['id'] = str(user_id)
                user_cache[cache_key] = user_data
                return user_data
        else:
            user_data = {
                'id': str(user_id),
                'first_name': '',
                'language': 'tr',
                'balance': 0.0,
                'ad_balance': 0.0,
                'tasks_completed': 0,
                'referrals': 0,
            }
            user_cache[cache_key] = user_data
            return user_data
            
    except Exception as e:
        print(f"Kullanıcı getirme hatası: {e}")
        return None

async def create_or_update_user(user_id: int, user_data: Dict) -> bool:
    """Kullanıcı oluştur veya güncelle"""
    try:
        if db:
            user_ref = db.collection('users').document(str(user_id))
            user_ref.set(user_data, merge=True)
        else:
            cache_key = f"user_{user_id}"
            user_cache[cache_key] = user_data
        
        return True
    except Exception as e:
        print(f"Kullanıcı güncelleme hatası: {e}")
        return False

# ================= 8. KANAL KONTROLÜ =================
async def check_channel_membership(user_id: int) -> bool:
    """Kanal üyeliğini kontrol et"""
    try:
        member = await bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Kanal kontrol hatası: {e}")
        return False

# ================= 9. ANA MENÜ =================
async def show_main_menu(user_id: int, message_id: int = None, edit: bool = True):
    """Ana menü göster"""
    user = await get_user(user_id)
    if not user:
        user = {
            'id': str(user_id),
            'first_name': 'Kullanıcı',
            'balance': 0.0,
            'ad_balance': 0.0,
            'tasks_completed': 0,
            'referrals': 0,
            'language': 'tr'
        }
        await create_or_update_user(user_id, user)
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    total_balance = user.get('balance', 0) + user.get('ad_balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('buttons.do_task'), callback_data="do_task"),
        types.InlineKeyboardButton(t('buttons.my_balance'), callback_data="my_balance")
    )
    markup.add(
        types.InlineKeyboardButton(t('buttons.refresh'), callback_data="refresh_main"),
        types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu")
    )
    
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel"))
    
    message = f"""
{t('main_menu.title')}

{t('main_menu.welcome').format(name=user.get('first_name', 'Kullanıcı'))}

<b>─────────────────────</b>

💰 <b>Bakiyen:</b> <code>{total_balance:.2f} ₺</code>
📊 <b>Görevler:</b> <code>{user.get('tasks_completed', 0)}</code>
👥 <b>Referanslar:</b> <code>{user.get('referrals', 0)}</code>

<b>─────────────────────</b>

📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}
"""
    
    try:
        if edit and message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Menü gönderme hatası: {e}")

# ================= 10. START KOMUTU =================
@bot.message_handler(commands=['start', 'menu'])
async def handle_start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    
    is_member = await check_channel_membership(user_id)
    
    if not is_member:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}")
        )
        markup.row(
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        channel_msg = f"""
👋 <b>Merhaba {first_name}!</b>

Botu kullanabilmek için kanala katılman gerekiyor:

👉 @{MANDATORY_CHANNEL}

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>
"""
        await bot.send_message(user_id, channel_msg, reply_markup=markup)
        return
    
    user = await get_user(user_id)
    if not user:
        user_data = {
            'first_name': first_name,
            'channel_joined': True,
            'language': 'tr',
            'balance': 2.0,
            'ad_balance': 0.0,
            'welcome_bonus': True,
            'created_at': datetime.now().isoformat()
        }
        await create_or_update_user(user_id, user_data)
        
        welcome_msg = f"""
🎉 <b>Hoş Geldin {first_name}!</b>

✅ <b>2 ₺ Hoşgeldin Bonusu</b> hesabına yüklendi!
💰 <b>Yeni Bakiyen:</b> 2.00 ₺
"""
        await bot.send_message(user_id, welcome_msg)
    
    await show_main_menu(user_id)

# ================= 11. CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data == "check_join":
            if await check_channel_membership(user_id):
                await create_or_update_user(user_id, {'channel_joined': True})
                await show_main_menu(user_id, call.message.message_id)
                await bot.answer_callback_query(call.id, "✅ Başarılı!")
            else:
                await bot.answer_callback_query(call.id, "❌ Hala kanala katılmadın!", show_alert=True)
        
        elif data == "refresh_main":
            await show_main_menu(user_id, call.message.message_id)
            await bot.answer_callback_query(call.id, "🔄 Yenilendi!")
        
        elif data == "back_menu":
            await show_main_menu(user_id, call.message.message_id)
        
        elif data == "my_balance":
            user = await get_user(user_id)
            if user:
                total_balance = user.get('balance', 0) + user.get('ad_balance', 0)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_menu"))
                
                message = f"""
💰 <b>BAKİYE DETAYLARI</b>

<b>─────────────────────</b>

👤 <b>Kullanıcı:</b> {user.get('first_name', 'Kullanıcı')}
🆔 <b>ID:</b> <code>{user_id}</code>

<b>─────────────────────</b>

• <b>Normal Bakiye:</b> <code>{user.get('balance', 0):.2f} ₺</code>
• <b>Reklam Bakiyesi:</b> <code>{user.get('ad_balance', 0):.2f} ₺</code>
• <b>Toplam Bakiye:</b> <code>{total_balance:.2f} ₺</code>

<b>─────────────────────</b>

• <b>Tamamlanan Görev:</b> <code>{user.get('tasks_completed', 0)}</code>
• <b>Referans Sayısı:</b> <code>{user.get('referrals', 0)}</code>
"""
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    text=message,
                    reply_markup=markup
                )
        
        elif data == "do_task":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_menu"))
            
            message = """
🤖 <b>GÖREV SİSTEMİ</b>

<b>─────────────────────</b>

⏳ <b>Yakında Aktif!</b>

Görev sistemi çok yakında açılacaktır.
Şimdilik ana menüye dönüp bakiyenizi kontrol edebilirsiniz.
"""
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text=message,
                reply_markup=markup
            )
        
        elif data == "admin_panel" and user_id == ADMIN_ID:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_menu"))
            
            message = """
👑 <b>ADMIN PANEL</b>

<b>─────────────────────</b>

Hoş geldiniz admin!

Özellikler yakında eklenecektir.
"""
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text=message,
                reply_markup=markup
            )
        
    except Exception as e:
        print(f"Callback hatası: {e}")
        await bot.answer_callback_query(call.id, "❌ Bir hata oluştu!")

# ================= 12. FİYAT GÜNCELLEME =================
def update_prices():
    """TRX fiyatlarını güncelle"""
    get_trx_price()

schedule.every(30).seconds.do(update_prices)

def schedule_runner():
    """Schedule görevlerini çalıştır"""
    while True:
        schedule.run_pending()
        time.sleep(1)

# ================= 13. ANA ÇALIŞTIRMA =================
async def run_bot_async():
    """Async bot'u çalıştır"""
    print(f"""
    🚀 GÖREV YAPSAM BOT
    ═══════════════════════════════════════════
    📅 Başlatılıyor: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    🔧 Database: {'Firebase Firestore ✅' if db else 'Local Cache'}
    🌍 Dil Desteği: Türkçe & Azerbaycan
    ═══════════════════════════════════════════
    """)
    
    try:
        print("🤖 Bot başlatılıyor...")
        # DÜZELTİLDİ: long_polling_timeout parametresi kaldırıldı
        await bot.infinity_polling()
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
        await asyncio.sleep(5)
        await run_bot_async()

def main():
    """Ana çalıştırma fonksiyonu"""
    schedule_thread = threading.Thread(target=schedule_runner, daemon=True)
    schedule_thread.start()
    
    asyncio.run(run_bot_async())

if __name__ == "__main__":
    main()
