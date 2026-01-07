"""
🚀 GÖREV YAPSAM BOT PRO v16.2 - SQLite PERSISTENT
Telegram: @GorevYapsamBot
Developer: Alperen
Database: SQLite3 + Render Disk Backup
Ödeme: Yakında (Papara & Kripto)
Dil: Türkçe & Azerbaycan Türkçesi
Render Optimized - Persistent Data
"""

import os
import sqlite3
import json
import asyncio
import telebot
from telebot import types
import threading
import time
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv
import cachetools
import schedule
from typing import Dict, List, Optional
from pathlib import Path
import logging

# ================= 1. LOGGING SETUP =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= 2. ÇEVRE DEĞİŞKENLERİ =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")

# ================= 3. DATABASE SETUP (SQLITE PERSISTENT) =================
# Render Disk kullanıyoruz (kalıcı depolama)
DB_PATH = "/opt/render/project/src/data/bot_database.db"
BACKUP_PATH = "/opt/render/project/src/data/backup.json"

# Klasörleri oluştur
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_database():
    """Veritabanını başlat"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    
    # Users tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        language TEXT DEFAULT 'tr',
        balance REAL DEFAULT 0.0,
        ad_balance REAL DEFAULT 0.0,
        tasks_completed INTEGER DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        ref_earned REAL DEFAULT 0.0,
        total_earned REAL DEFAULT 0.0,
        channel_joined INTEGER DEFAULT 0,
        welcome_bonus INTEGER DEFAULT 0,
        ref_parent INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Referans linkleri için indeks
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ref_parent ON users(ref_parent)')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully")

# Veritabanını başlat
init_database()

# ================= 4. DATABASE FUNCTIONS =================
def get_db_connection():
    """Database bağlantısı al"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

async def get_user(user_id: int) -> Optional[Dict]:
    """Kullanıcı bilgilerini getir"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM users WHERE user_id = ?', 
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row:
            user_data = dict(row)
            conn.close()
            return user_data
        
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"Kullanıcı getirme hatası: {e}")
        return None

async def create_or_update_user(user_id: int, user_data: Dict) -> bool:
    """Kullanıcı oluştur veya güncelle"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Var mı kontrol et
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Update
            update_fields = []
            values = []
            
            for key, value in user_data.items():
                if key != 'user_id':
                    update_fields.append(f"{key} = ?")
                    values.append(value)
            
            values.append(user_id)
            query = f"UPDATE users SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
            cursor.execute(query, values)
        else:
            # Insert
            fields = ['user_id'] + list(user_data.keys())
            placeholders = ['?'] * len(fields)
            values = [user_id] + list(user_data.values())
            
            query = f"INSERT INTO users ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Kullanıcı güncelleme hatası: {e}")
        return False

async def update_balance(user_id: int, amount: float, balance_type: str = 'balance') -> bool:
    """Bakiye güncelle"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if balance_type == 'ad_balance':
            cursor.execute(
                'UPDATE users SET ad_balance = ad_balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                (amount, user_id)
            )
        else:
            cursor.execute(
                '''UPDATE users SET 
                balance = balance + ?, 
                total_earned = total_earned + ?,
                updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?''',
                (amount, max(amount, 0), user_id)
            )
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Bakiye güncelleme hatası: {e}")
        return False

async def add_referral(user_id: int, parent_id: int) -> bool:
    """Referans ekle (KANAL KONTROLÜ EKLENDİ)"""
    try:
        # Önce referans yapan kullanıcının kanala katılıp katılmadığını kontrol et
        parent_user = await get_user(parent_id)
        if not parent_user or parent_user.get('channel_joined', 0) == 0:
            logger.info(f"Referans ebeveyni {parent_id} kanala katılmamış, referans eklenmedi")
            return False
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Referans sayısını artır
        cursor.execute(
            '''UPDATE users SET 
            referrals = referrals + 1,
            ref_earned = ref_earned + 1.0,
            balance = balance + 1.0,
            updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?''',
            (parent_id,)
        )
        
        # Yeni kullanıcıya parent id ekle
        cursor.execute(
            'UPDATE users SET ref_parent = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
            (parent_id, user_id)
        )
        
        conn.commit()
        conn.close()
        
        # Bonus kontrolü
        await check_referral_bonuses(parent_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Referans ekleme hatası: {e}")
        return False

async def check_referral_bonuses(user_id: int):
    """Referans bonuslarını kontrol et"""
    try:
        user = await get_user(user_id)
        if not user:
            return
        
        referrals = user.get('referrals', 0)
        bonus_added = 0
        
        # Bonus seviyeleri
        bonuses = {
            5: 2.0,
            10: 5.0,
            25: 15.0,
            50: 35.0
        }
        
        for threshold, amount in bonuses.items():
            if referrals >= threshold:
                # Bonus henüz eklenmemişse ekle
                cursor = get_db_connection().cursor()
                cursor.execute(
                    'SELECT 1 FROM referral_bonuses WHERE user_id = ? AND threshold = ?',
                    (user_id, threshold)
                )
                exists = cursor.fetchone()
                
                if not exists:
                    cursor.execute(
                        'UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                        (amount, user_id)
                    )
                    cursor.execute(
                        'INSERT INTO referral_bonuses (user_id, threshold, amount) VALUES (?, ?, ?)',
                        (user_id, threshold, amount)
                    )
                    bonus_added += amount
        
        if bonus_added > 0:
            logger.info(f"User {user_id} received {bonus_added} TL referral bonus")
            
    except Exception as e:
        logger.error(f"Referans bonus kontrol hatası: {e}")

# ================= 5. BOT KONFİGÜRASYONU =================
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ================= 6. CACHE SİSTEMİ =================
user_cache = cachetools.TTLCache(maxsize=1000, ttl=60)
user_states = {}

# ================= 7. DİL SİSTEMİ =================
TRANSLATIONS = {
    'tr': {
        'main_menu': {
            'title': '🚀 <b>GÖREV YAPSAM BOT</b>',
            'welcome': '👋 <b>Merhaba {name}!</b>',
            'balance_section': '💰 <b>BAKİYE DURUMU</b>',
            'stats_section': '📊 <b>İSTATİSTİKLER</b>',
            'total_balance': '• Toplam Bakiye:',
            'normal_balance': '• Normal Bakiye:',
            'ad_balance': '• Reklam Bakiyesi:',
            'tasks_completed': '• Tamamlanan Görev:',
            'referrals': '• Referans Sayısı:',
            'channel_info': '📢 <b>Zorunlu Kanal:</b>',
            'start_action': '⚡ <i>Aşağıdaki butonlardan işlemini seç!</i>'
        },
        
        'buttons': {
            'do_task': '🤖 GÖREV YAP',
            'create_task': '📢 GÖREV OLUŞTUR',
            'my_balance': '💰 BAKİYEM',
            'referrals': '👥 REFERANSLARIM',
            'deposit': '💳 BAKİYE YÜKLE',
            'ad_balance': '🔄 ÇEVİRİ YAP',
            'withdraw': '💸 PARA ÇEK',
            'support': '🛠 DESTEK',
            'faq': '❓ YARDIM',
            'language': '🌐 DİL',
            'back_menu': '🏠 ANA MENÜ',
            'refresh': '🔄 YENİLE',
            'copy': '📋 KOPYALA'
        },
        
        'deposit': {
            'title': '💳 <b>BAKİYE YÜKLEME</b>',
            'soon_title': '⏳ <b>YAKINDA AKTİF!</b>',
            'soon_message': 'Bakiye yükleme sistemi çok yakında aktif edilecektir.\n\nÖdeme yöntemleri:\n• Papara\n• Kripto Para (TRX, USDT)\n• Banka Havalesi\n\nLütfen kısa bir süre bekleyin.'
        }
    },
    
    'az': {
        'main_menu': {
            'title': '🚀 <b>TAPŞIRIQ EDƏM BOT</b>',
            'welcome': '👋 <b>Salam {name}!</b>',
            'balance_section': '💰 <b>BALANS VƏZİYYƏTİ</b>',
            'stats_section': '📊 <b>STATİSTİKA</b>',
            'total_balance': '• Ümumi Balans:',
            'normal_balance': '• Normal Balans:',
            'ad_balance': '• Reklam Balansı:',
            'tasks_completed': '• Tamamlanan Tapşırıq:',
            'referrals': '• Referans Sayı:',
            'channel_info': '📢 <b>Məcburi Kanal:</b>',
            'start_action': '⚡ <i>Aşağıdakı düymələrdən əməliyyatını seç!</i>'
        },
        
        'buttons': {
            'do_task': '🤖 TAPŞIRIQ ET',
            'create_task': '📢 TAPŞIRIQ YARAT',
            'my_balance': '💰 BALANSIM',
            'referrals': '👥 REFERANSLARIM',
            'deposit': '💳 BALANS ARTIR',
            'ad_balance': '🔄 ÇEVİR ET',
            'withdraw': '💸 PUL ÇIXART',
            'support': '🛠 DƏSTƏK',
            'faq': '❓ KÖMƏK',
            'language': '🌐 DİL',
            'back_menu': '🏠 ƏSAS MENYU',
            'refresh': '🔄 YENİLƏ',
            'copy': '📋 KOPYALA'
        },
        
        'deposit': {
            'title': '💳 <b>BALANS ARTIRMA</b>',
            'soon_title': '⏳ <b>TEZLİKDA AKTİV!</b>',
            'soon_message': 'Balans artırma sistemi tezlikdə aktiv ediləcək.\n\nÖdəniş üsulları:\n• Papara\n• Kripto Valyuta (TRX, USDT)\n• Bank köçürməsi\n\nZəhmət olmasa qısa müddət gözləyin.'
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

# ================= 8. KANAL KONTROLÜ =================
def check_channel_membership(user_id: int) -> bool:
    """Kanal üyeliğini kontrol et (sync)"""
    try:
        member = bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Kanal kontrol hatası: {e}")
        return False

# ================= 9. REFERANS KONTROLÜ =================
def check_and_add_referral(user_id: int, referrer_id: Optional[int] = None):
    """Referans kontrolü ve ekleme (KANAL KONTROLLÜ)"""
    try:
        if not referrer_id:
            return
        
        # Referans yapan kişinin kanala katılıp katılmadığını kontrol et
        if not check_channel_membership(referrer_id):
            logger.info(f"Referans yapan {referrer_id} kanala katılmamış, referans eklenmedi")
            return
        
        # Referans ekle
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Referans sayısını artır
        cursor.execute(
            '''UPDATE users SET 
            referrals = referrals + 1,
            ref_earned = ref_earned + 1.0,
            balance = balance + 1.0,
            updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?''',
            (referrer_id,)
        )
        
        # Yeni kullanıcıya parent id ekle
        cursor.execute(
            'UPDATE users SET ref_parent = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
            (referrer_id, user_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Referans eklendi: {user_id} -> {referrer_id}")
        
    except Exception as e:
        logger.error(f"Referans ekleme hatası: {e}")

# ================= 10. START KOMUTU (REFERANS DÜZELTMESİ) =================
@bot.message_handler(commands=['start', 'menu', 'yardım', 'help'])
def handle_start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    username = message.from_user.username or ""
    
    # Referans parametresini kontrol et
    referrer_id = None
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = int(param.replace('ref_', ''))
                # Referans yapan kişinin kendisi olmadığından emin ol
                if referrer_id == user_id:
                    referrer_id = None
            except:
                referrer_id = None
    
    is_member = check_channel_membership(user_id)
    
    user = get_user(user_id)
    if not user:
        user_data = {
            'first_name': first_name,
            'username': username,
            'channel_joined': 1 if is_member else 0,
            'language': 'tr',
            'balance': 0.0,
            'ad_balance': 0.0,
            'welcome_bonus': 0,
            'created_at': datetime.now().isoformat()
        }
        create_or_update_user(user_id, user_data)
        user = get_user(user_id)
    
    # Hoşgeldin bonusu
    if user and user.get('welcome_bonus', 0) == 0:
        update_balance(user_id, 2.0)
        create_or_update_user(user_id, {'welcome_bonus': 1})
        
        welcome_msg = f"""
🎉 <b>Hoş Geldin {first_name}!</b>

✅ <b>2 ₺ Hoşgeldin Bonusu</b> hesabına yüklendi!
💰 <b>Yeni Bakiyen:</b> 2.00 ₺

<i>Hemen görev yapmaya başlayabilirsin!</i>
"""
        bot.send_message(user_id, welcome_msg)
    
    # REFERANS KONTROLÜ - KANAL KATILIMI ZORUNLU
    if referrer_id and is_member:
        # Referans yapan kişinin kanala katılıp katılmadığını kontrol et
        if check_channel_membership(referrer_id):
            check_and_add_referral(user_id, referrer_id)
            bot.send_message(
                user_id,
                f"🎉 <b>Referans başarılı!</b>\n\n"
                f"@{message.from_user.username if message.from_user.username else 'Kullanıcı'} seni referans etti!\n"
                f"💰 <b>1 ₺ referans bonusu</b> kazandın!"
            )
    
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

Botu kullanabilmek için aşağıdaki kanala katılman gerekiyor:

👉 @{MANDATORY_CHANNEL}

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>

⚠️ <i>Kanalı terk edersen botu kullanamazsın!</i>

{"⚠️ <b>Referans bonusu almak için önce kanala katılmalısın!</b>" if referrer_id else ""}
"""
        bot.send_message(user_id, channel_msg, reply_markup=markup)
        return
    
    show_main_menu(user_id)

# ================= 11. ANA MENÜ =================
def show_main_menu(user_id: int, message_id: int = None, edit: bool = True):
    """Ana menü göster"""
    user = get_user(user_id)
    if not user:
        user = {
            'first_name': 'Kullanıcı',
            'balance': 0.0,
            'ad_balance': 0.0,
            'tasks_completed': 0,
            'referrals': 0,
            'language': 'tr'
        }
        create_or_update_user(user_id, {
            'first_name': 'Kullanıcı',
            'language': 'tr'
        })
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    total_balance = user.get('balance', 0) + user.get('ad_balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.do_task'), callback_data="do_task"),
        types.InlineKeyboardButton(t('buttons.create_task'), callback_data="create_task_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.my_balance'), callback_data="my_balance"),
        types.InlineKeyboardButton(t('buttons.deposit'), callback_data="deposit_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.referrals'), callback_data="my_refs"),
        types.InlineKeyboardButton(t('buttons.ad_balance'), callback_data="ad_balance_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.support'), callback_data="support_menu"),
        types.InlineKeyboardButton(t('buttons.faq'), callback_data="faq_menu"),
        types.InlineKeyboardButton(t('buttons.language'), callback_data="language_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.withdraw'), callback_data="withdraw_menu"),
        types.InlineKeyboardButton(t('buttons.refresh'), callback_data="refresh_main")
    )
    
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel"))
    
    message = f"""
{t('main_menu.title')}

{t('main_menu.welcome').format(name=user.get('first_name', 'Kullanıcı'))}

<b>─────────────────────</b>

{t('main_menu.balance_section')}
• {t('main_menu.total_balance')} <code>{total_balance:.2f} ₺</code>
• {t('main_menu.normal_balance')} <code>{user.get('balance', 0):.2f} ₺</code>
• {t('main_menu.ad_balance')} <code>{user.get('ad_balance', 0):.2f} ₺</code>

<b>─────────────────────</b>

{t('main_menu.stats_section')}
• {t('main_menu.tasks_completed')} <code>{user.get('tasks_completed', 0)}</code>
• {t('main_menu.referrals')} <code>{user.get('referrals', 0)}</code>

<b>─────────────────────</b>

{t('main_menu.channel_info')} @{MANDATORY_CHANNEL}

{t('main_menu.start_action')}
"""
    
    try:
        if edit and message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            bot.send_message(
                user_id,
                message,
                reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Menü gönderme hatası: {e}")

# ================= 12. CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    message_id = call.message.message_id if call.message else None
    
    try:
        if data not in ["check_join", "set_lang_tr", "set_lang_az"]:
            if not check_channel_membership(user_id):
                bot.answer_callback_query(
                    call.id,
                    f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}",
                    show_alert=True
                )
                return
        
        if data == "check_join":
            if check_channel_membership(user_id):
                create_or_update_user(user_id, {'channel_joined': 1})
                show_main_menu(user_id, message_id)
                bot.answer_callback_query(call.id, "✅ Başarılı!")
            else:
                bot.answer_callback_query(
                    call.id,
                    "❌ Hala kanala katılmadın!",
                    show_alert=True
                )
        
        elif data == "refresh_main":
            show_main_menu(user_id, message_id)
            bot.answer_callback_query(call.id, "🔄 Yenilendi!")
        
        elif data == "back_menu":
            show_main_menu(user_id, message_id)
        
        elif data == "deposit_menu":
            show_deposit_menu(user_id, message_id)
        
        elif data == "withdraw_menu":
            show_withdraw_menu(user_id, message_id)
        
        elif data.startswith("set_lang_"):
            lang = data.replace("set_lang_", "")
            create_or_update_user(user_id, {'language': lang})
            bot.answer_callback_query(call.id, f"✅ Dil {lang} olarak ayarlandı!")
            show_main_menu(user_id, message_id)
        
        elif data == "language_menu":
            show_language_menu(user_id, message_id)
        
        elif data == "support_menu":
            show_support_menu(user_id, message_id)
        
        elif data == "faq_menu":
            show_faq_menu(user_id, message_id)
        
        elif data == "my_balance":
            show_balance_details(user_id, message_id)
        
        elif data == "do_task":
            show_task_selection(user_id, message_id)
        
        elif data == "create_task_menu":
            show_create_task_menu(user_id, message_id)
        
        elif data == "my_refs":
            show_referral_info(user_id, message_id)
        
        elif data == "ad_balance_menu":
            show_ad_balance_conversion(user_id, message_id)
        
        elif data == "admin_panel" and user_id == ADMIN_ID:
            show_admin_panel(user_id, message_id)
        
        elif data.startswith("copy_"):
            text_to_copy = data.replace("copy_", "")
            bot.answer_callback_query(call.id, "✅ Kopyalandı!")
        
    except Exception as e:
        logger.error(f"Callback hatası: {e}")
        bot.answer_callback_query(call.id, "❌ Bir hata oluştu!")

# ================= 13. REFERANS LİNKİ (KANAL KONTROLLÜ) =================
def show_referral_info(user_id: int, message_id: int = None):
    """Referans bilgilerini göster"""
    user = get_user(user_id)
    if not user:
        return
    
    # KANAL KONTROLÜ: Kullanıcı kanala katılmamışsa uyarı göster
    if not check_channel_membership(user_id):
        warning_msg = f"""
⚠️ <b>REFERANS SİSTEMİ</b>

❌ <b>Referans linki oluşturamazsın!</b>

Önce kanala katılmalısın:
👉 @{MANDATORY_CHANNEL}

Katıldıktan sonra referans linkini alabilir ve arkadaşlarını davet edebilirsin!
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}"))
        markup.add(types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join"))
        
        if message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=warning_msg,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, warning_msg, reply_markup=markup)
        return
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
        types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
👥 <b>REFERANS SİSTEMİ</b>

<b>─────────────────────</b>

💰 <b>Her referans:</b> 1.00 ₺
👤 <b>Toplam referans:</b> {user.get('referrals', 0)}
📈 <b>Referans kazancı:</b> {user.get('ref_earned', 0):.2f} ₺

<b>─────────────────────</b>

🔗 <b>Referans linkin:</b>
<code>{ref_link}</code>

<b>─────────────────────</b>

🎁 <b>REFERANS BONUSLARI:</b>
• 5 referans: +2 ₺
• 10 referans: +5 ₺
• 25 referans: +15 ₺
• 50 referans: +35 ₺

<b>─────────────────────</b>

⚠️ <b>ÖNEMLİ:</b> Arkadaşların kanala katılmazsa referans bonusu alamazsın!
"""
    
    try:
        if message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        logger.error(f"Referral info hatası: {e}")

# ================= 14. DİĞER MENÜ FONKSİYONLARI =================
def show_deposit_menu(user_id: int, message_id: int = None):
    """Bakiye yükleme menüsü"""
    user = get_user(user_id)
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('deposit.title')}

<b>─────────────────────</b>

{t('deposit.soon_title')}

<b>─────────────────────</b>

{t('deposit.soon_message')}
"""
    
    try:
        if message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        logger.error(f"Deposit menu hatası: {e}")

def show_withdraw_menu(user_id: int, message_id: int = None):
    """Para çekme menüsü"""
    user = get_user(user_id)
    if not user:
        return
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_menu"))
    
    message = f"""
💸 <b>PARA ÇEKME</b>

<b>─────────────────────</b>

💰 <b>Mevcut Bakiye:</b> <code>{user.get('balance', 0):.2f} ₺</code>

<b>─────────────────────</b>

Para çekme sistemi çok yakında aktif edilecektir.

• Minimum çekim: 20 ₺
• İşlem süresi: 24 saat
• Yöntemler: Papara, Banka Havalesi

<b>─────────────────────</b>

💡 <b>İpucu:</b> Bakiyeni reklam bakiyesine çevirip görev oluşturabilirsin!
"""
    
    try:
        if message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        logger.error(f"Withdraw menu hatası: {e}")

def show_language_menu(user_id: int, message_id: int = None):
    """Dil seçim menüsü"""
    user = get_user(user_id)
    current_lang = user.get('language', 'tr') if user else 'tr'
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "🇹🇷 Türkçe" + (" ✅" if current_lang == 'tr' else ""),
            callback_data="set_lang_tr"
        ),
        types.InlineKeyboardButton(
            "🇦🇿 Azərbaycan" + (" ✅" if current_lang == 'az' else ""),
            callback_data="set_lang_az"
        )
    )
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_menu"))
    
    message = """
🌐 <b>DİL SEÇİMİ</b>

<b>─────────────────────</b>

Aşağıdaki dillerden birini seçin:

🇹🇷 <b>Türkçe</b> - Türkiye Türkçesi
🇦🇿 <b>Azərbaycan</b> - Azerbaycan Türkçesi

<b>─────────────────────</b>

<i>Seçiminiz tüm menüleri ve mesajları değiştirecektir.</i>
"""
    
    try:
        if message_id:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        logger.error(f"Language menu hatası: {e}")

# ================= 15. BACKUP SİSTEMİ =================
def backup_database():
    """Database'i JSON'a yedekle"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users')
        users = [dict(row) for row in cursor.fetchall()]
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'users': users
        }
        
        with open(BACKUP_PATH, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        conn.close()
        logger.info("✅ Database backup completed")
        
    except Exception as e:
        logger.error(f"Backup hatası: {e}")

def schedule_backup():
    """Yedekleme schedule"""
    schedule.every(6).hours.do(backup_database)
    while True:
        schedule.run_pending()
        time.sleep(60)

# ================= 16. ANA ÇALIŞTIRMA =================
def main():
    """Ana çalıştırma fonksiyonu"""
    logger.info(f"""
    🚀 GÖREV YAPSAM BOT PRO v16.2 - SQLite Persistent
    ═══════════════════════════════════════════
    📅 Başlatılıyor: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    🔧 Database: SQLite3 (Persistent)
    🌍 Dil Desteği: Türkçe & Azerbaycan
    💰 Referans Sistemi: Kanal Katılım Zorunlu
    ═══════════════════════════════════════════
    """)
    
    # Backup thread'ini başlat
    backup_thread = threading.Thread(target=schedule_backup, daemon=True)
    backup_thread.start()
    
    # İlk backup
    backup_database()
    
    # Bot'u başlat
    logger.info("🤖 Bot polling başlatılıyor...")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
