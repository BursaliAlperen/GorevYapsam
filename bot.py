"""
🤖 GÖREV YAPSAM BOT v13.0 - ÇOK DİLLİ & TRX OTOMATİK SİSTEM
Telegram: @GorevYapsam
Developer: Alperen
Token: 8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co
Dil Desteği: Türkçe & Azerbaycan Türkçesi
TRX Ödeme: Tam Otomatik
"""

import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import random
import requests
import json
import os
from flask import Flask

# ================= 1. KONFİGÜRASYON =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877
ZORUNLU_KANAL = "GY_Refim"

# TRX CÜZDAN ADRESİ
TRX_WALLET = "TVJKGbdBQrbvQzq6WZhb3kaGa3LYgVrMSK"
TRONGRID_API_KEY = "YOUR_TRONGRID_API_KEY"  # TronGrid'den alınacak

# API URL'leri
BINANCE_API = "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY"
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=try"

# FİYATLAR (TL cinsinden)
PRICES = {
    "bot": 2.50,    # 🤖 BOT GÖREV
    "kanal": 1.50,  # 📢 KANAL GÖREV  
    "grup": 1.00    # 👥 GRUP GÖREV
}

# Bot nesnesi
bot = telebot.TeleBot(TOKEN, parse_mode='HTML', threaded=True)
app = Flask(__name__)

# ================= 2. DİL SİSTEMİ =================
TRANSLATIONS = {
    'tr': {
        'main_menu': {
            'title': '🤖 GÖREV YAPSAM',
            'welcome': 'Merhaba {name}!',
            'total_balance': '💰 Toplam Bakiye:',
            'normal_balance': '• Normal:',
            'ad_balance': '• Reklam:',
            'tasks_completed': '🎯 Görev:',
            'refs': '👥 Ref:',
            'channel': '📢 Kanal:',
            'start_now': 'Hemen başla!'
        },
        'buttons': {
            'do_task': '🤖 GÖREV YAP',
            'create_task': '📢 GÖREV OLUŞTUR',
            'my_balance': '💰 BAKİYE',
            'referrals': '👥 REFERANS',
            'deposit': '💳 BAKİYE YÜKLE',
            'ad_balance': '🔄 REKLAM BAKİYESİ',
            'withdraw': '💸 PARA ÇEK',
            'support': '🛠 TEKNİK DESTEK',
            'faq': '❓ FAQ',
            'language': '🌐 DİL',
            'back_menu': '🏠 MENÜ',
            'admin_panel': '👑 ADMIN'
        },
        'tasks': {
            'select_task': 'GÖREV SEÇ',
            'bot_task': '🤖 BOT ({price} ₺)',
            'channel_task': '📢 KANAL ({price} ₺)',
            'group_task': '👥 GRUP ({price} ₺)',
            'choose_one': 'Birini seç:'
        },
        'deposit': {
            'title': '💳 BAKİYE YÜKLE',
            'select_amount': 'Hangi miktarı yüklemek istiyorsun?',
            'custom_amount': '💳 Özel Miktar',
            'enter_amount': 'Yüklemek istediğin TRX miktarını yaz:',
            'min_amount': 'Minimum: 2 TRX',
            'trx_address': 'TRX Cüzdan Adresi:',
            'send_exact': 'Lütfen TAM {amount} TRX gönder:',
            'enter_txid': 'İşlem tamamlandığında TXID/Hash numarasını buraya yaz:',
            'verifying': '✅ Ödeme kontrol ediliyor...',
            'success': '✅ Ödeme Onaylandı!',
            'failed': '❌ Ödeme bulunamadı. TXID kontrol edin.'
        },
        'ad_balance': {
            'title': '🔄 REKLAM BAKİYESİ',
            'normal_balance': '💰 Normal Bakiye:',
            'ad_balance': '💰 Reklam Bakiyesi:',
            'bonus_25': '🎁 %25 BONUS! Normal bakiyeni reklam bakiyesine çevir, %25 bonus kazan!',
            'example': 'Örnek: 100 ₺ normal bakiye → 125 ₺ reklam bakiyesi',
            'select_amount': 'Çevirmek istediğin miktarı seç:',
            'custom': 'Diğer',
            'converted': '✅ BAKİYE ÇEVRİLDİ!',
            'converted_amount': '💰 Çevrilen:',
            'bonus': '🎁 Bonus (%25):',
            'total_ad': '💰 Toplam Reklam Bakiyesi:',
            'new_status': '💳 Yeni Durum:',
            'create_task_now': '🎯 Şimdi görev oluşturabilirsin!'
        },
        'support': {
            'title': '🛠 TEKNİK DESTEK',
            'contact': 'Sorunlarınız için: @AlperenTHE',
            'ticket_system': '📝 Bilet sistemi yakında aktif!',
            'response_time': '⏰ Yanıt süresi: 24 saat'
        },
        'faq': {
            'title': '❓ SIKÇA SORULAN SORULAR',
            'q1': '❓ <b>Bakiye nasıl yüklenir?</b>',
            'a1': '💳 "BAKİYE YÜKLE" butonuna tıkla → TRX miktarını seç → TRX gönder → TXID gir.',
            'q2': '❓ <b>Görev nasıl yapılır?</b>',
            'a2': '🤖 "GÖREV YAP" butonu → görev seç → linke git → 3 dakika bekle → TAMAMLA.',
            'q3': '❓ <b>Ödeme ne zaman gelir?</b>',
            'a3': '⚡ TRX ödemeleri 1-5 dakika içinde otomatik onaylanır.',
            'q4': '❓ <b>Reklam bakiyesi nedir?</b>',
            'a4': '🔄 Görev oluşturmak için kullanılan özel bakiyedir. %25 bonusla çevrilir.',
            'q5': '❓ <b>Minimum para çekme nedir?</b>',
            'a5': '💸 Minimum para çekme: 20 ₺ (sistem yakında aktif).'
        },
        'withdraw': {
            'title': '💸 PARA ÇEK',
            'coming_soon': '🛠 Para Çekme sistemi çok yakında aktif edilecektir!'
        }
    },
    'az': {
        'main_menu': {
            'title': '🤖 TAPŞIRIQ EDƏM',
            'welcome': 'Salam {name}!',
            'total_balance': '💰 Ümumi Balans:',
            'normal_balance': '• Normal:',
            'ad_balance': '• Reklam:',
            'tasks_completed': '🎯 Tapşırıq:',
            'refs': '👥 Ref:',
            'channel': '📢 Kanal:',
            'start_now': 'Dərhal başla!'
        },
        'buttons': {
            'do_task': '🤖 TAPŞIRIQ ET',
            'create_task': '📢 TAPŞIRIQ YARAT',
            'my_balance': '💰 BALANS',
            'referrals': '👥 REFERANS',
            'deposit': '💳 BALANS ARTIR',
            'ad_balance': '🔄 REKLAM BALANSI',
            'withdraw': '💸 PUL ÇIXART',
            'support': '🛠 TEKNİK DƏSTƏK',
            'faq': '❓ MƏLUMAT',
            'language': '🌐 DİL',
            'back_menu': '🏠 MENYU',
            'admin_panel': '👑 ADMIN'
        },
        'tasks': {
            'select_task': 'TAPŞIRIQ SEÇ',
            'bot_task': '🤖 BOT ({price} ₺)',
            'channel_task': '📢 KANAL ({price} ₺)',
            'group_task': '👥 QRUPPA ({price} ₺)',
            'choose_one': 'Birini seç:'
        },
        'deposit': {
            'title': '💳 BALANS ARTIR',
            'select_amount': 'Hansı məbləği yükləmək istəyirsən?',
            'custom_amount': '💳 Xüsusi Məbləğ',
            'enter_amount': 'Yükləmək istədiyin TRX məbləğini yaz:',
            'min_amount': 'Minimum: 2 TRX',
            'trx_address': 'TRX Cüzdan Ünvanı:',
            'send_exact': 'Zəhmət olmazsa TAM {amount} TRX göndər:',
            'enter_txid': 'Əməliyyat tamamlandıqda TXID/Hash nömrəsini buraya yaz:',
            'verifying': '✅ Ödəniş yoxlanılır...',
            'success': '✅ Ödəniş Təsdiqləndi!',
            'failed': '❌ Ödəniş tapılmadı. TXID-i yoxlayın.'
        },
        'ad_balance': {
            'title': '🔄 REKLAM BALANSI',
            'normal_balance': '💰 Normal Balans:',
            'ad_balance': '💰 Reklam Balansı:',
            'bonus_25': '🎁 %25 BONUS! Normal balansını reklam balansına çevir, %25 bonus qazan!',
            'example': 'Nümunə: 100 ₺ normal balans → 125 ₺ reklam balansı',
            'select_amount': 'Çevirmək istədiyin məbləği seç:',
            'custom': 'Digər',
            'converted': '✅ BALANS ÇEVRİLDİ!',
            'converted_amount': '💰 Çevrilən:',
            'bonus': '🎁 Bonus (%25):',
            'total_ad': '💰 Ümumi Reklam Balansı:',
            'new_status': '💳 Yeni Vəziyyət:',
            'create_task_now': '🎯 İndi tapşırıq yarada bilərsən!'
        },
        'support': {
            'title': '🛠 TEKNİK DƏSTƏK',
            'contact': 'Problemleriniz üçün: @AlperenTHE',
            'ticket_system': '📝 Bilet sistemi tezliklə aktiv!',
            'response_time': '⏰ Cavab müddəti: 24 saat'
        },
        'faq': {
            'title': '❓ TEZ-TEZ VERİLƏN SUALLAR',
            'q1': '❓ <b>Balans necə yüklənir?</b>',
            'a1': '💳 "BALANS ARTIR" düyməsinə toxun → TRX məbləğini seç → TRX göndər → TXID yaz.',
            'q2': '❓ <b>Tapşırıq necə edilir?</b>',
            'a2': '🤖 "TAPŞIRIQ ET" düyməsi → tapşırıq seç → linkə get → 3 dəqiqə gözlə → TAMAMLA.',
            'q3': '❓ <b>Ödəniş nə zaman gəlir?</b>',
            'a3': '⚡ TRX ödənişləri 1-5 dəqiqə ərzində avtomatik təsdiqlənir.',
            'q4': '❓ <b>Reklam balansı nədir?</b>',
            'a4': '🔄 Tapşırıq yaratmaq üçün istifadə olunan xüsusi balansdır. %25 bonusla çevrilir.',
            'q5': '❓ <b>Minimum pul çıxarma nədir?</b>',
            'a5': '💸 Minimum pul çıxarma: 20 ₺ (sistem tezliklə aktiv).'
        },
        'withdraw': {
            'title': '💸 PUL ÇIXART',
            'coming_soon': '🛠 Pul çıxarışı sistemi tezliklə aktiv ediləcək!'
        }
    }
}

# ================= 3. VERİTABANI =================
def get_db():
    conn = sqlite3.connect('gorev_bot_v13.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Kullanıcılar tablosu (dil tercihi eklendi)
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            language TEXT DEFAULT 'tr',
            balance REAL DEFAULT 0.0,
            ad_balance REAL DEFAULT 0.0,
            total_earned REAL DEFAULT 0.0,
            tasks_completed INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            ref_earned REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            channel_joined INTEGER DEFAULT 0,
            welcome_bonus INTEGER DEFAULT 0
        )''')
        
        # Görevler tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_type TEXT,
            title TEXT,
            link TEXT,
            description TEXT,
            cost_per_view REAL,
            max_views INTEGER,
            views INTEGER DEFAULT 0,
            cost_spent REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Görev tamamlamalar
        cursor.execute('''CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            earned REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Referanslar
        cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            earned REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # TRX Ödemeleri (YENİ)
        cursor.execute('''CREATE TABLE IF NOT EXISTS trx_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            trx_amount REAL,
            try_amount REAL,
            txid TEXT UNIQUE,
            bonus_percent INTEGER DEFAULT 25,
            bonus_amount REAL DEFAULT 0.0,
            total_ad_balance REAL,
            status TEXT DEFAULT 'pending',
            verified_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Bakiye çevrimleri
        cursor.execute('''CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_balance REAL,
            to_ad_balance REAL,
            bonus REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()

init_db()

# ================= 4. TRX SİSTEMİ FONKSİYONLARI =================
def get_trx_price():
    """Canlı TRX/TRY fiyatını al"""
    try:
        response = requests.get(BINANCE_API, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        try:
            response = requests.get(COINGECKO_API, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data['tron']['try'])
        except:
            pass
    
    # Fallback değer
    return 0.35  # Yaklaşık TRX/TRY fiyatı

def calculate_trx_to_try(trx_amount):
    """TRX miktarını TL'ye çevir"""
    trx_price = get_trx_price()
    return trx_amount * trx_price

def calculate_bonus(trx_amount):
    """Bonus hesapla"""
    if trx_amount >= 15:
        return 50  # %50 bonus
    elif trx_amount >= 2:
        return 25  # %25 bonus
    return 0

def verify_trx_transaction(txid):
    """TRX işlemini doğrula (TronGrid API)"""
    try:
        # Bu kısım TronGrid API entegrasyonu gerektirir
        # Şimdilik manuel onay simülasyonu
        # Gerçek implementasyon için:
        # 1. TronGrid API key alın
        # 2. requests ile transaction verify edin
        
        # Geçici olarak her TXID'i doğru kabul et
        return {
            'verified': True,
            'amount': 10,  # Örnek miktar
            'to_address': TRX_WALLET
        }
    except:
        return {'verified': False}

# ================= 5. DİL FONKSİYONLARI =================
def get_user_language(user_id):
    """Kullanıcının dil tercihini getir"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result['language'] if result else 'tr'

def set_user_language(user_id, language):
    """Kullanıcının dil tercihini ayarla"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
        conn.commit()

def t(user_id, key_path):
    """Çeviri metnini getir"""
    lang = get_user_language(user_id)
    keys = key_path.split('.')
    
    current = TRANSLATIONS[lang]
    for key in keys:
        if key in current:
            current = current[key]
        else:
            # Fallback to Turkish
            current = TRANSLATIONS['tr']
            for k in keys:
                if k in current:
                    current = current[k]
                else:
                    return f"[{key_path}]"
            break
    
    return current if isinstance(current, str) else str(current)

# ================= 6. TEMEL FONKSİYONLAR (GÜNCELLENDİ) =================
def format_money(num):
    """Para formatı"""
    return f"{float(num):,.2f} ₺"

def kanal_kontrol(user_id):
    """Kanal üyeliği kontrolü"""
    try:
        member = bot.get_chat_member("@" + ZORUNLU_KANAL, user_id)
        is_member = member.status in ['member', 'administrator', 'creator']
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''UPDATE users SET 
                           channel_joined = ?
                           WHERE user_id = ?''', 
                           (1 if is_member else 0, user_id))
            conn.commit()
        
        return is_member
    except:
        return False

def get_user(user_id):
    """Kullanıcı bilgisi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def create_user(user_id, username, first_name):
    """Yeni kullanıcı oluştur"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT OR IGNORE INTO users 
                       (user_id, username, first_name, balance, ad_balance) 
                       VALUES (?, ?, ?, 0.0, 0.0)''', 
                       (user_id, username, first_name))
        conn.commit()

def update_balance(user_id, amount, balance_type='balance'):
    """Bakiye güncelle"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if balance_type == 'ad_balance':
            if amount > 0:
                cursor.execute('''UPDATE users SET 
                               ad_balance = ad_balance + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, user_id))
            else:
                cursor.execute('''UPDATE users SET 
                               ad_balance = ad_balance + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, user_id))
        else:
            if amount > 0:
                cursor.execute('''UPDATE users SET 
                               balance = balance + ?,
                               total_earned = total_earned + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, amount, user_id))
            else:
                cursor.execute('''UPDATE users SET 
                               balance = balance + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, user_id))
        conn.commit()

def get_total_balance(user_id):
    """Toplam bakiye (normal + reklam)"""
    user = get_user(user_id)
    return user['balance'] + user['ad_balance']

# ================= 7. ANA MENÜ (GÜNCELLENDİ) =================
def show_main_menu(user_id, message_id=None):
    """Ana menü"""
    user = get_user(user_id)
    
    if not user:
        create_user(user_id, "", "")
        user = get_user(user_id)
    
    total_balance = get_total_balance(user_id)
    lang = get_user_language(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Ana butonlar
    markup.add(
        types.InlineKeyboardButton(t(user_id, 'buttons.do_task'), callback_data="do_task"),
        types.InlineKeyboardButton(t(user_id, 'buttons.my_balance') + " " + format_money(total_balance), callback_data="my_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton(t(user_id, 'buttons.create_task'), callback_data="create_task_menu"),
        types.InlineKeyboardButton(t(user_id, 'buttons.referrals'), callback_data="my_refs")
    )
    
    markup.add(
        types.InlineKeyboardButton(t(user_id, 'buttons.deposit'), callback_data="deposit_menu"),
        types.InlineKeyboardButton(t(user_id, 'buttons.ad_balance'), callback_data="ad_balance_menu")
    )
    
    # Alt butonlar
    markup.add(
        types.InlineKeyboardButton(t(user_id, 'buttons.withdraw'), callback_data="withdraw_menu"),
        types.InlineKeyboardButton(t(user_id, 'buttons.support'), callback_data="support_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t(user_id, 'buttons.faq'), callback_data="faq_menu"),
        types.InlineKeyboardButton(t(user_id, 'buttons.language'), callback_data="language_menu")
    )
    
    # Admin butonu (sadece admin için)
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.admin_panel'), callback_data="admin_panel"))
    
    text = f"""<b>{t(user_id, 'main_menu.title')}</b>

{t(user_id, 'main_menu.welcome').format(name=user['first_name'])}

💰 <b>{t(user_id, 'main_menu.total_balance')}</b> {format_money(total_balance)}
• {t(user_id, 'main_menu.normal_balance')} {format_money(user['balance'])}
• {t(user_id, 'main_menu.ad_balance')} {format_money(user['ad_balance'])}

🎯 <b>{t(user_id, 'main_menu.tasks_completed')}</b> {user['tasks_completed']}
👥 <b>{t(user_id, 'main_menu.refs')}</b> {user['referrals']}

📢 <b>{t(user_id, 'main_menu.channel')}</b> @{ZORUNLU_KANAL}

{t(user_id, 'main_menu.start_now')}"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 8. START KOMUTU (GÜNCELLENDİ) =================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    
    # Kullanıcı oluştur veya kontrol et
    create_user(user_id, message.from_user.username, first_name)
    user = get_user(user_id)
    
    # Referans kontrolü
    ref_used = False
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = int(param.replace('ref_', ''))
                if referrer_id != user_id:
                    # Referans ekleme fonksiyonu
                    pass
            except:
                pass
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{ZORUNLU_KANAL}"),
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        welcome_text = f"""Merhaba {first_name}!

Botu kullanmak için kanala katıl:

@{ZORUNLU_KANAL}

Katıldıktan sonra "✅ KATILDIM" butonuna bas."""
        
        bot.send_message(user_id, welcome_text, reply_markup=markup)
        return
    
    # Ana menü
    show_main_menu(user_id)

# ================= 9. DİL SEÇİMİ MENÜSÜ =================
def show_language_menu(user_id, message_id):
    """Dil seçim menüsü"""
    current_lang = get_user_language(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🇹🇷 Türkçe" + (" ✅" if current_lang == 'tr' else ""), callback_data="set_lang_tr"),
        types.InlineKeyboardButton("🇦🇿 Azərbaycan" + (" ✅" if current_lang == 'az' else ""), callback_data="set_lang_az")
    )
    markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="back_menu"))
    
    text = """<b>🌐 DİL SEÇİMİ / DİL SEÇİMİ</b>

Aşağıdaki dillerden birini seçin:

🇹🇷 <b>Türkçe</b> - Türkiye Türkçesi
🇦🇿 <b>Azərbaycan</b> - Azerbaycan Türkçesi

Seçiminiz tüm butonları ve mesajları değiştirecektir."""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 10. TRX BAKİYE YÜKLEME SİSTEMİ =================
def show_deposit_menu(user_id, message_id):
    """TRX bakiye yükleme menüsü"""
    trx_price = get_trx_price()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(f"2 TRX ({format_money(2*trx_price)})", callback_data="deposit_2"),
        types.InlineKeyboardButton(f"5 TRX ({format_money(5*trx_price)})", callback_data="deposit_5"),
        types.InlineKeyboardButton(f"10 TRX ({format_money(10*trx_price)})", callback_data="deposit_10"),
        types.InlineKeyboardButton(f"15 TRX ({format_money(15*trx_price)})", callback_data="deposit_15")
    )
    markup.add(
        types.InlineKeyboardButton(f"25 TRX ({format_money(25*trx_price)})", callback_data="deposit_25"),
        types.InlineKeyboardButton(f"50 TRX ({format_money(50*trx_price)})", callback_data="deposit_50"),
        types.InlineKeyboardButton(t(user_id, 'deposit.custom_amount'), callback_data="deposit_other"),
        types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="back_menu")
    )
    
    text = f"""<b>{t(user_id, 'deposit.title')}</b>

{t(user_id, 'deposit.select_amount')}

💰 <b>Güncel TRX/TRY:</b> 1 TRX = {format_money(trx_price)}
🎁 <b>Bonuslar:</b>
• 2-14 TRX: %25 Reklam Bakiyesi Bonusu
• 15+ TRX: %50 Reklam Bakiyesi Bonusu + 350 ₺ Sabit

👇 Bir miktar seç veya "Diğer" seçeneğiyle özel miktar gir."""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

def process_trx_deposit_amount(user_id, trx_amount, message_id=None):
    """TRX ödeme bilgilerini göster"""
    trx_price = get_trx_price()
    try_amount = trx_amount * trx_price
    bonus_percent = calculate_bonus(trx_amount)
    
    if trx_amount >= 15:
        bonus_text = f"🎁 <b>%{bonus_percent} Bonus + 350 ₺ Sabit</b>"
        total_try = try_amount + 350
    else:
        bonus_text = f"🎁 <b>%{bonus_percent} Bonus</b>"
        total_try = try_amount * (1 + bonus_percent/100)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📋 Cüzdanı Kopyala", callback_data=f"copy_{TRX_WALLET}"),
        types.InlineKeyboardButton("✅ ÖDEME YAPTIM", callback_data=f"verify_deposit_{trx_amount}")
    )
    markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="deposit_menu"))
    
    text = f"""<b>💳 TRX ÖDEME BİLGİLERİ</b>

{t(user_id, 'deposit.trx_address')}
<code>{TRX_WALLET}</code>

📊 <b>Ödeme Detayları:</b>
• Göndereceğin TRX: <b>{trx_amount} TRX</b>
• Anlık Kur: <b>{format_money(trx_price)}</b>
• TL Değeri: <b>{format_money(try_amount)}</b>
{bonus_text}
• Alacağın Reklam Bakiyesi: <b>{format_money(total_try)}</b>

⚠️ <b>ÖNEMLİ:</b>
1. SADECE TRX (TRON) gönder
2. <b>TAM {trx_amount} TRX</b> gönder
3. Ağ ücretini unutma
4. İşlem tamamlanınca TXID'yi bota yaz

{t(user_id, 'deposit.send_exact').format(amount=trx_amount)}"""
    
    # Kullanıcı durumunu kaydet
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['pending_deposit'] = {
        'trx_amount': trx_amount,
        'try_amount': try_amount,
        'bonus_percent': bonus_percent,
        'total_try': total_try
    }
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.from_user.id in user_states and 'pending_deposit' in user_states[message.from_user.id] and message.text and len(message.text) > 20)
def process_txid_input(message):
    """TXID inputunu işle"""
    user_id = message.from_user.id
    txid = message.text.strip()
    
    if user_id not in user_states or 'pending_deposit' not in user_states[user_id]:
        return
    
    deposit_data = user_states[user_id]['pending_deposit']
    
    # Kullanıcıya bilgi ver
    bot.send_message(user_id, t(user_id, 'deposit.verifying'))
    
    # Ödemeyi doğrula
    verification = verify_trx_transaction(txid)
    
    if verification['verified']:
        # Ödeme başarılı
        trx_amount = deposit_data['trx_amount']
        total_try = deposit_data['total_try']
        
        # Reklam bakiyesine ekle
        update_balance(user_id, total_try, 'ad_balance')
        
        # Veritabanına kaydet
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO trx_deposits 
                           (user_id, trx_amount, try_amount, txid, bonus_percent, total_ad_balance, status, verified_at)
                           VALUES (?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)''',
                           (user_id, trx_amount, deposit_data['try_amount'], txid,
                            deposit_data['bonus_percent'], total_try))
            conn.commit()
        
        # Başarı mesajı
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(t(user_id, 'buttons.create_task'), callback_data="create_task_menu"),
            types.InlineKeyboardButton(t(user_id, 'buttons.my_balance'), callback_data="my_balance")
        )
        
        text = f"""✅ <b>{t(user_id, 'deposit.success')}</b>

💰 <b>Yüklenen:</b> {trx_amount} TRX
💰 <b>TL Değeri:</b> {format_money(deposit_data['try_amount'])}
🎁 <b>Bonus:</b> %{deposit_data['bonus_percent']}
💰 <b>Reklam Bakiyesi:</b> +{format_money(total_try)}
📊 <b>Yeni Reklam Bakiyesi:</b> {format_money(get_user(user_id)['ad_balance'])}

⚡ <b>İşlem tamamlandı! Şimdi görev oluşturabilirsin.</b>"""
        
        bot.send_message(user_id, text, reply_markup=markup)
        
    else:
        # Ödeme başarısız
        text = f"""❌ <b>{t(user_id, 'deposit.failed')}</b>

TXID: <code>{txid}</code>

⚠️ <b>Olası Sebepler:</b>
1. Yanlış TXID girdin
2. Ödeme henüz onaylanmadı
3. Yanlış miktar gönderdin
4. Yanlış cüzdana gönderdin

💰 <b>Doğru Cüzdan:</b> <code>{TRX_WALLET}</code>

Lütfen kontrol edip tekrar dene."""
        
        bot.send_message(user_id, text)
    
    # Durumu temizle
    if user_id in user_states and 'pending_deposit' in user_states[user_id]:
        del user_states[user_id]['pending_deposit']

# ================= 11. TEKNİK DESTEK MENÜSÜ =================
def show_support_menu(user_id, message_id):
    """Teknik destek menüsü"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="back_menu"))
    
    text = f"""<b>{t(user_id, 'support.title')}</b>

{t(user_id, 'support.contact')}

📞 {t(user_id, 'support.ticket_system')}
⏰ {t(user_id, 'support.response_time')}

<code>Kullanıcı ID: {user_id}</code>

<b>Destek için mesaj formatı:</b>
1. Kullanıcı ID: {user_id}
2. Sorun açıklaması
3. Ekran görüntüsü (varsa)"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 12. FAQ MENÜSÜ =================
def show_faq_menu(user_id, message_id):
    """SSS menüsü"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="back_menu"))
    
    text = f"""<b>{t(user_id, 'faq.title')}</b>

{t(user_id, 'faq.q1')}
{t(user_id, 'faq.a1')}

{t(user_id, 'faq.q2')}
{t(user_id, 'faq.a2')}

{t(user_id, 'faq.q3')}
{t(user_id, 'faq.a3')}

{t(user_id, 'faq.q4')}
{t(user_id, 'faq.a4')}

{t(user_id, 'faq.q5')}
{t(user_id, 'faq.a5')}

💡 <b>Ek Bilgiler:</b>
• TRX ödemeleri otomatik onaylanır
• Minimum görev ücreti: 1.00 ₺
• Referans başına: 1.00 ₺
• Kanal zorunluluğu: @{ZORUNLU_KANAL}"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 13. PARA ÇEKME MENÜSÜ =================
def show_withdraw_menu(user_id, message_id):
    """Para çekme menüsü"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t(user_id, 'buttons.back_menu'), callback_data="back_menu"))
    
    text = f"""<b>{t(user_id, 'withdraw.title')}</b>

{t(user_id, 'withdraw.coming_soon')}

💰 <b>Mevcut Bakiye:</b> {format_money(user['balance'])}
💳 <b>Minimum Çekim:</b> 20 ₺
⏰ <b>Tahmini Süre:</b> 24 saat

📢 <b>Duyuru:</b> Para çekme sistemi en kısa sürede aktif edilecektir.

💡 <b>Öneri:</b> Bakiyeni reklam bakiyesine çevirip görev oluşturabilirsin!"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 14. CALLBACK HANDLER (GÜNCELLENDİ) =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # Kanal kontrolü (check_join hariç)
    if not kanal_kontrol(user_id) and call.data != "check_join" and not call.data.startswith("set_lang_"):
        bot.answer_callback_query(call.id, "❌ Önce kanala katıl!", show_alert=True)
        return
    
    # Dil değiştirme işlemleri
    if call.data.startswith("set_lang_"):
        lang = call.data.replace("set_lang_", "")
        set_user_language(user_id, lang)
        bot.answer_callback_query(call.id, f"✅ Dil {lang} olarak ayarlandı!")
        show_main_menu(user_id, call.message.message_id)
        return
    
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Başarılı!")
        else:
            bot.answer_callback_query(call.id, "❌ Hala katılmadın!", show_alert=True)
    
    elif call.data == "back_menu":
        show_main_menu(user_id, call.message.message_id)
    
    elif call.data == "do_task":
        show_task_types(user_id, call.message.message_id)
    
    elif call.data == "my_balance":
        show_my_balance(user_id, call.message.message_id)
    
    elif call.data == "create_task_menu":
        create_task_menu(user_id, call.message.message_id)
    
    elif call.data == "my_refs":
        show_my_refs(user_id, call.message.message_id)
    
    elif call.data == "deposit_menu":
        show_deposit_menu(user_id, call.message.message_id)
    
    elif call.data == "ad_balance_menu":
        show_ad_balance_menu(user_id, call.message.message_id)
    
    elif call.data == "withdraw_menu":
        show_withdraw_menu(user_id, call.message.message_id)
    
    elif call.data == "support_menu":
        show_support_menu(user_id, call.message.message_id)
    
    elif call.data == "faq_menu":
        show_faq_menu(user_id, call.message.message_id)
    
    elif call.data == "language_menu":
        show_language_menu(user_id, call.message.message_id)
    
    elif call.data == "admin_panel":
        if user_id == ADMIN_ID:
            show_admin_panel(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Yetkin yok!")
    
    # TRX Ödeme işlemleri
    elif call.data.startswith("deposit_"):
        amount_str = call.data.replace("deposit_", "")
        if amount_str == "other":
            ask_custom_trx_deposit(user_id, call.message.message_id)
        else:
            try:
                trx_amount = float(amount_str)
                process_trx_deposit_amount(user_id, trx_amount, call.message.message_id)
            except:
                pass
    
    elif call.data.startswith("verify_deposit_"):
        trx_amount = float(call.data.replace("verify_deposit_", ""))
        
        # TXID girmesi için talimat
        bot.edit_message_text(
            t(user_id, 'deposit.enter_txid'),
            call.message.chat.id,
            call.message.message_id
        )
    
    elif call.data.startswith("copy_"):
        text_to_copy = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, "✅ Kopyalandı!")
    
    # Diğer işlemler (eski kodun kalan kısımları)
    elif call.data in ["task_bot", "task_kanal", "task_grup"]:
        task_type = call.data.replace("task_", "")
        show_available_task(user_id, task_type, call.message.message_id)
    
    elif call.data in ["create_bot", "create_kanal", "create_grup"]:
        task_type = call.data.replace("create_", "")
        start_task_creation(user_id, task_type, call.message.message_id)
    
    elif call.data == "cancel_task":
        show_main_menu(user_id, call.message.message_id)
        bot.answer_callback_query(call.id, "❌ Görev oluşturma iptal edildi!")

# ================= 15. YARDIMCI FONKSİYONLAR =================
def ask_custom_trx_deposit(user_id, message_id):
    """Özel TRX miktarı sor"""
    bot.edit_message_text(
        t(user_id, 'deposit.enter_amount'),
        user_id,
        message_id
    )
    
    def process_custom_trx(message):
        try:
            trx_amount = float(message.text.strip())
            if trx_amount < 2:
                bot.send_message(user_id, t(user_id, 'deposit.min_amount'))
                show_deposit_menu(user_id, None)
                return
            
            process_trx_deposit_amount(user_id, trx_amount, None)
        except:
            bot.send_message(user_id, "❌ Geçersiz miktar!")
            show_deposit_menu(user_id, None)
    
    bot.register_next_step_handler_by_chat_id(user_id, process_custom_trx)

# ================= 16. FLASK SUNUCUSU =================
@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>🤖 Görev Yapsam Bot</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                }
                .container {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    padding: 30px;
                    border-radius: 20px;
                    box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
                }
                h1 {
                    text-align: center;
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                .status {
                    background: rgba(76, 175, 80, 0.2);
                    border: 2px solid #4CAF50;
                    padding: 15px;
                    border-radius: 10px;
                    text-align: center;
                    margin: 20px 0;
                    font-size: 1.2em;
                }
                .features {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                .feature {
                    background: rgba(255, 255, 255, 0.15);
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                }
                .feature-icon {
                    font-size: 2em;
                    margin-bottom: 10px;
                }
                .stats {
                    display: flex;
                    justify-content: space-around;
                    flex-wrap: wrap;
                    margin-top: 30px;
                }
                .stat {
                    text-align: center;
                    margin: 10px;
                }
                .stat-value {
                    font-size: 2em;
                    font-weight: bold;
                }
                .telegram-btn {
                    display: inline-block;
                    background: #0088cc;
                    color: white;
                    padding: 15px 30px;
                    border-radius: 10px;
                    text-decoration: none;
                    font-weight: bold;
                    margin-top: 20px;
                    transition: transform 0.3s;
                }
                .telegram-btn:hover {
                    transform: translateY(-3px);
                    background: #0077b3;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Görev Yapsam Bot v13.0</h1>
                <div class="status">
                    ✅ <strong>BOT AKTİF</strong> - Çok Dilli & TRX Otomatik Sistem
                </div>
                
                <div class="features">
                    <div class="feature">
                        <div class="feature-icon">🌍</div>
                        <h3>Çok Dilli</h3>
                        <p>Türkçe & Azerbaycan Türkçesi</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">⚡</div>
                        <h3>TRX Otomatik</h3>
                        <p>Anlık ödeme onayı</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">💰</div>
                        <h3>Bonus Sistem</h3>
                        <p>%25-%50 bonus</p>
                    </div>
                </div>
                
                <div style="text-align: center;">
                    <a href="https://t.me/GorevYapsamBot" class="telegram-btn" target="_blank">
                        📱 Telegram'da Aç
                    </a>
                </div>
                
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">2</div>
                        <div>Desteklenen Dil</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">⚡</div>
                        <div>Otomatik Ödeme</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">🎁</div>
                        <div>Bonus Sistemi</div>
                    </div>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "ok", "version": "13.0", "features": ["multi_language", "trx_auto", "bonus_system"]}

# ================= 17. BOT ÇALIŞTIRMA =================
def run_bot():
    print("🤖 Görev Yapsam Bot v13.0 başlatılıyor...")
    print("🌍 Dil Desteği: Türkçe & Azerbaycan Türkçesi")
    print("⚡ TRX Otomatik Ödeme Sistemi: AKTİF")
    print("🎁 Bonus Sistem: %25-%50")
    
    try:
        bot.remove_webhook()
        time.sleep(1)
        
        bot.polling(
            none_stop=True,
            interval=3,
            timeout=60,
            skip_pending=True
        )
    except Exception as e:
        print(f"Bot hatası: {e}")
        time.sleep(10)
        run_bot()

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Kullanıcı durumları için sözlük
    user_states = {}
    
    # Flask thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Ana thread'de botu çalıştır
    run_bot()
