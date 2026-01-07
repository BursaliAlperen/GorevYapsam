import os
import time
import json
import requests
from datetime import datetime, timedelta
import threading
import sqlite3
from flask import Flask, jsonify
import hashlib

# pytz alternatifi - datetime kullanımı
from datetime import timezone
import pytz

# Telegram Ayarları
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "7904032877")
MANDATORY_CHANNEL = os.environ.get("MANDATORY_CHANNEL", "GY_Refim")

if not TOKEN:
    raise ValueError("Bot token gerekli!")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Türkiye saati için (pytz olmadan alternatif)
def get_turkey_time():
    """Türkiye saatini döndür"""
    try:
        # pytz varsa kullan
        import pytz
        return datetime.now(pytz.timezone('Europe/Istanbul'))
    except:
        # pytz yoksa UTC+3 kullan
        return datetime.now(timezone(timedelta(hours=3)))

# TRX Ayarları
TRX_ADDRESS = "TVJKGbdBQrbvQzq6WZhb3kaGa3LYgVrMSK"
TRX_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=try"
MIN_DEPOSIT_TRY = 25.0
MAX_DEPOSIT_TRY = 200.0
DEPOSIT_BONUS_PERCENT = 35
ADS_BONUS_PERCENT = 20

# Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v15.0"})

# Database - pytz bağımlılığını kaldırdık
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        # Kullanıcılar
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                username TEXT,
                balance REAL DEFAULT 0.0,
                ads_balance REAL DEFAULT 0.0,
                total_earned REAL DEFAULT 0.0,
                tasks_completed INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                ref_earned REAL DEFAULT 0.0,
                daily_streak INTEGER DEFAULT 0,
                last_daily TEXT,
                in_channel INTEGER DEFAULT 0,
                created_at TEXT,
                welcome_bonus INTEGER DEFAULT 0,
                total_deposited REAL DEFAULT 0.0,
                deposit_count INTEGER DEFAULT 0,
                total_bonus REAL DEFAULT 0.0,
                language TEXT DEFAULT 'tr'
            )
        ''')
        
        # Kampanyalar
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                link TEXT,
                budget REAL,
                remaining_budget REAL,
                creator_id TEXT,
                creator_name TEXT,
                task_type TEXT,
                price_per_task REAL,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                forward_message_id TEXT,
                forward_chat_id TEXT,
                forward_message_text TEXT,
                forward_from_bot_id TEXT,
                forward_from_bot_name TEXT,
                target_chat_id TEXT,
                target_chat_name TEXT,
                is_bot_admin INTEGER DEFAULT 0
            )
        ''')
        
        # Depozitler
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS deposits (
                deposit_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount_try REAL,
                amount_trx REAL,
                txid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                bonus_amount REAL DEFAULT 0.0,
                trx_price REAL
            )
        ''')
        
        # Katılımlar
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS participations (
                participation_id TEXT PRIMARY KEY,
                user_id TEXT,
                campaign_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                reward_amount REAL DEFAULT 0.0
            )
        ''')
        
        self.conn.commit()
        print("✅ Veritabanı hazır")
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            now = get_turkey_time().isoformat()
            self.cursor.execute('''
                INSERT INTO users (user_id, name, balance, ads_balance, created_at, language)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, '', 0.0, 0.0, now, 'tr'))
            self.conn.commit()
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        
        return dict(user) if user else {}
    
    def update_user(self, user_id, data):
        if not data: return False
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(user_id)
        query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
        self.cursor.execute(query, values)
        self.conn.commit()
        return True
    
    def add_balance(self, user_id, amount, bonus_percent=0):
        user = self.get_user(user_id)
        bonus = amount * bonus_percent / 100
        total = amount + bonus
        new_balance = user.get('balance', 0) + total
        
        self.cursor.execute('''
            UPDATE users 
            SET balance = ?, total_earned = total_earned + ?, total_bonus = total_bonus + ? 
            WHERE user_id = ?
        ''', (new_balance, total, bonus, user_id))
        self.conn.commit()
        return True

# Telegram Fonksiyonları
def send_message(chat_id, text, markup=None, parse_mode='HTML'):
    url = BASE_URL + "sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if markup: data['reply_markup'] = json.dumps(markup)
    try: 
        response = requests.post(url, json=data, timeout=10).json()
        return response
    except: 
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
    if text: data['text'] = text
    if show_alert: data['show_alert'] = True
    try: requests.post(url, json=data, timeout=5)
    except: pass

def get_chat_member(chat_id, user_id):
    url = BASE_URL + "getChatMember"
    data = {'chat_id': chat_id, 'user_id': int(user_id)}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            status = response['result']['status']
            return status in ['member', 'administrator', 'creator']
    except: pass
    return False

def get_chat_info(chat_id):
    url = BASE_URL + "getChat"
    data = {'chat_id': chat_id}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            return response['result']
    except: pass
    return None

def check_bot_admin(chat_id):
    bot_id = int(TOKEN.split(':')[0])
    url = BASE_URL + "getChatMember"
    data = {'chat_id': chat_id, 'user_id': bot_id}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            status = response['result']['status']
            return status in ['administrator', 'creator']
    except: pass
    return False

def edit_message(chat_id, message_id, text, markup=None, parse_mode='HTML'):
    url = BASE_URL + "editMessageText"
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': parse_mode}
    if markup: data['reply_markup'] = json.dumps(markup)
    try: return requests.post(url, json=data, timeout=10).json()
    except: return None

def delete_message(chat_id, message_id):
    url = BASE_URL + "deleteMessage"
    data = {'chat_id': chat_id, 'message_id': message_id}
    try: return requests.post(url, json=data, timeout=5).json()
    except: return None

# Dil sistemi
translations = {
    'tr': {
        'welcome': '👋 Hoş Geldin!',
        'balance': '💰 Bakiye',
        'tasks': '📊 Görevler',
        'referrals': '👥 Referanslar',
        'price': '₿ TRX Fiyatı',
        'channel': '📢 Kanal',
        'main_menu': '📋 ANA MENÜ',
        'do_task': '🎯 GÖREV YAP',
        'create_campaign': '📢 KAMPANYA OLUŞTUR',
        'my_campaigns': '📋 KAMPANYALARIM',
        'deposit': '💰 BAKİYE YÜKLE',
        'profile': '👤 PROFİL',
        'bot_info': 'ℹ️ BOT BİLGİSİ',
        'help': '❓ YARDIM',
        'admin_panel': '👑 YÖNETİCİ',
        'back': '🔙 GERİ',
        'cancel': '❌ İPTAL',
        'yes': '✅ EVET',
        'no': '❌ HAYIR',
        'time': '⏰ Saat',
        'join_channel': '📢 KANALA KATIL',
        'joined': '✅ KATILDIM',
        'loading': '⏳ Yükleniyor...',
        'success': '✅ Başarılı!',
        'error': '❌ Hata!',
        'choose_amount': '👇 TUTAR SEÇİN',
        'min': 'Min',
        'max': 'Max',
        'bonus_system': '🎁 BONUS',
        'example': '💡 ÖRNEK',
        'payment_info': '💳 ÖDEME',
        'steps': '👇 ADIMLAR',
        'copy_address': '1️⃣ Adresi kopyala',
        'send_trx': '2️⃣ TRX gönder',
        'send_txid': '3️⃣ TXID gönder',
        'balance_loaded': '4️⃣ Bakiye yüklenecek',
        'processing_time': '⏳ İşlem süresi',
        'txid_format': '✅ TXID formatı',
        'user': '👤 Kullanıcı',
        'normal_balance': '💵 Normal Bakiye',
        'ad_balance': '📺 Reklam Bakiyesi',
        'total_balance': '💰 Toplam Bakiye',
        'statistics': '📊 İstatistikler',
        'total_investment': 'Toplam Yatırım',
        'total_bonus': 'Toplam Bonus',
        'task_count': 'Görev Sayısı',
        'referral_count': 'Referans',
        'ad_bonus_note': '💡 Reklam bakiyesi bonusludur!',
        'features': '💰 ÖZELLİKLER',
        'commands': '📋 KOMUTLAR',
        'rules': '⚠️ KURALLAR',
        'support': '📞 DESTEK',
        'how_it_works': '🤖 BOT NASIL ÇALIŞIR?',
        'how_deposit': '💰 BAKİYE NASIL YÜKLENİR?',
        'how_create_campaign': '📢 KAMPANYA NASIL OLUŞTURULUR?',
        'how_do_task': '🎯 GÖREV NASIL YAPILIR?',
        'referral_system': '👥 REFERANS SİSTEMİ',
        'cancel_system': '🔄 İPTAL SİSTEMİ',
        'important_warnings': '⚠️ ÖNEMLİ UYARILAR',
        'no_campaigns': '📭 HENÜZ KAMPANYANIZ YOK',
        'create_first_campaign': '💡 İlk kampanyanızı oluşturun!',
        'active': '🟢 Aktif',
        'pending': '🟡 Bekleyen',
        'inactive': '🔴 Pasif',
        'summary': '📊 ÖZET',
        'total': '📈 Toplam',
        'campaign_type': '🎯 KAMPANYA TİPİ',
        'bot_campaign': '🤖 BOT KAMPANYASI',
        'channel_campaign': '📢 KANAL KAMPANYASI',
        'group_campaign': '👥 GRUP KAMPANYASI',
        'choose_type': '👇 TİP SEÇİN',
        'step': '📌 ADIM',
        'enter_name': 'İsim girin',
        'enter_description': 'Açıklama girin',
        'enter_link': 'Link girin',
        'enter_budget': 'Bütçe girin',
        'enter_channel': 'Kanal/Grup girin',
        'forward_message': '📤 Mesaj forward edin',
        'how_to_forward': 'Nasıl yapılır',
        'accepted': '✅ KABUL EDİLEN',
        'rejected': '❌ REDDEDİLEN',
        'campaign_summary': '📋 KAMPANYA ÖZETİ',
        'target_bot': '🤖 HEDEF BOT',
        'message_content': '📝 MESAJ',
        'target': '🎯 HEDEF',
        'bot_status': '👑 BOT DURUMU',
        'warning': '⚠️ UYARI',
        'task_price': '💵 GÖREV ÜCRETİ',
        'max_participants': '👥 MAKSİMUM',
        'creator': '👤 OLUŞTURAN',
        'confirm_campaign': 'Kampanyayı onaylıyor musunuz?',
        'auto_approval': '✅ Otomatik aktif olacak',
        'check_bot_admin': '🔄 BOT ADMIN KONTROL',
        'approve_send': '✅ ONAYLA VE GÖNDER',
        'campaign_created': '✅ KAMPANYA OLUŞTURULDU!',
        'campaign_id': '🔢 KAMPANYA ID',
        'status': '📊 DURUM',
        'budget_deducted': '💰 Bakiye düşüldü',
        'bot_not_admin': '❌ BOT ADMIN DEĞİL!',
        'insufficient_balance': '❌ YETERSİZ BAKİYE!',
        'required': 'Gerekli',
        'available': 'Mevcut',
        'missing': 'Eksik',
        'please_deposit': '💡 Lütfen önce bakiye yükleyin',
        'follow_steps': 'Lütfen adımları takip edin',
        'add_admin': 'Yönetici Ekle',
        'all_permissions': 'TÜM YETKİLERİ aktif edin',
        'see_members': 'Üyeleri görme yetkisi',
        'save': 'Kaydet',
        'check_again': '✅ Tekrar kontrol edin',
        'any_bot': 'HERHANGİ BİR BOT',
        'any_bot_message': 'HERHANGİ BİR BOT mesajı',
        'all_bots_accepted': 'Tüm bot mesajları',
        'normal_users_rejected': 'Normal kullanıcı mesajları',
        'suggested_bots': 'Önerilen botlar',
        'bot_father': '@BotFather - Bot oluşturma',
        'like_bot': '@like - Beğeni botu',
        'vid_bot': '@vid - Video indirme',
        'game_bot': '@gamebot - Oyun botu',
        'or_any_bot': 'veya herhangi bir bot...',
        'only_bot_message': '❌ Sadece BOT mesajı forward edin!',
        'normal_user_message': '⚠️ Normal kullanıcı mesajı forward ettiniz',
        'correct_steps': 'Doğru adımlar',
        'find_bot_message': 'BOT mesajı bulun',
        'forward_to_bot': 'Bu bota FORWARD edin',
        'system_will_detect': 'Sistem otomatik algılayacak',
        'note_only_bots': 'Not: Sadece bot mesajları kabul edilir!',
        'please_forward': '📤 LÜTFEN MESAJ FORWARD EDİN!',
        'forward_any_bot': 'HERHANGİ BİR BOT mesajı forward edin',
        'steps_to_forward': 'Adımlar',
        'find_bot': 'BOT mesajı bulun',
        'press_hold': 'Mesaja basılı tutun',
        'click_forward': 'Forward tıklayın',
        'select_this_bot': 'Bu botu seçin',
        'send': 'Gönderin',
        'operation_cancelled': '🔄 İşlem iptal edildi',
        'no_active_operation': '⚠️ Aktif işlem yok',
        'redirecting_to_menu': 'Ana menüye yönlendiriliyorsunuz...',
        'channel_check_success': '✅ Kanal kontrolü başarılı!',
        'not_joined_channel': '❌ Hala kanala katılmadınız!',
        'error_occurred': '❌ Bir hata oluştu',
        'admin_no_permission': '❌ Bu işlem için yetkiniz yok!',
        'admin_panel_title': '👑 YÖNETİCİ PANELİ',
        'statistics_title': '📊 İSTATİSTİKLER',
        'total_users': 'Toplam Kullanıcı',
        'total_balance': 'Toplam Bakiye',
        'active_campaigns': 'Aktif Kampanyalar',
        'pending_approval': 'Onay Bekleyen',
        'current_time': '⏰ Saat',
        'admin_tools': '🛠️ YÖNETİCİ ARAÇLARI',
        'user_stats': '📊 İSTATİSTİKLER',
        'campaign_stats': '📢 KAMPANYALAR',
        'user_management': '👥 KULLANICILAR',
        'deposit_management': '💰 DEPOZİTLER',
        'broadcast': '📣 BİLDİRİM',
        'settings': '⚙️ AYARLAR',
        'campaign_approved': '✅ Kampanya onaylandı!',
        'campaign_active': 'Kampanya aktif edildi',
        'users_can_join': 'Kullanıcılar katılabilir',
        'earnings_per_participation': 'Her katılım için kazanç',
        'duration_until_budget': 'Bütçe bitene kadar süre',
        'campaign_rejected': '❌ Kampanya reddedildi!',
        'reason_for_rejection': 'RED SEBEBİ',
        'bot_not_admin_reason': 'Bot kanalda admin değil',
        'not_following_rules': 'Kampanya kurallara uymuyor',
        'missing_info': 'Eksik bilgi',
        'suspicious_content': 'Şüpheli içerik',
        'balance_refunded': '💰 Bakiye iade edildi',
        'check_rules_try_again': '💡 Kuralları kontrol edip tekrar deneyin',
        'welcome_bonus_loaded': '✅ Hoşgeldin bonusu yüklendi!',
        'new_balance': 'Yeni bakiyen',
        'start_tasks': '⚡ Hemen görev yapmaya başla!',
        'referral_successful': '🎉 Referans başarılı!',
        'referral_bonus_loaded': '💰 Referans bonusu yüklendi',
        'forward_bot_message': '🤖 Bot mesajı başarıyla alındı!',
        'enter_campaign_name': '📛 Kampanya ismi girin',
        'example_names': 'Örnek isimler',
        'join_our_channel': 'Kanalımıza katılın',
        'youtube_subscribe': 'YouTube Abone Ol',
        'instagram_follow': 'Instagram Takip Et',
        'discord_join': 'Discord Sunucusu',
        'enter_your_name': 'Kampanya isminizi yazın',
        'name_saved': '✅ İsim Kaydedildi',
        'description_saved': '✅ Açıklama Kaydedildi',
        'link_saved': '✅ Link Kaydedildi',
        'channel_saved': '✅ Kanal/Grup Kaydedildi',
        'budget_saved': '✅ Bütçe Kaydedildi',
        'minimum_budget': 'Minimum bütçe 10₺!',
        'invalid_budget': '❌ Geçersiz bütçe! Lütfen sayı girin',
        'invalid_format': '❌ Geçersiz format! @ ile başlamalı veya link olmalı',
        'channel_not_found': '❌ Kanal/Grup bulunamadı!',
        'enter_correct_name': 'Lütfen doğru isim girin',
        'bot_not_admin_warning': '⚠️ BOT ADMIN DEĞİL!',
        'to_create_campaign': 'Kampanyayı oluşturmak için',
        'make_bot_admin': 'Botu kanalda ADMIN yapın',
        'give_permissions': 'Yetkileri verin',
        'continue_after_admin': 'Admin yaptıktan sonra devam edin',
        'cancel_text': '/cancel yazarak iptal edebilirsiniz',
        'operation_cancelled_text': '❌ İşlem iptal edildi'
    },
    'az': {
        'welcome': '👋 Xoş Gəldin!',
        'balance': '💰 Balans',
        'tasks': '📊 Tapşırıqlar',
        'referrals': '👥 Referallar',
        'price': '₿ TRX Qiyməti',
        'channel': '📢 Kanal',
        'main_menu': '📋 ƏSAS MENYU',
        'do_task': '🎯 TAPŞIRIQ ET',
        'create_campaign': '📢 KAMPANIYA YARAT',
        'my_campaigns': '📋 KAMPANIYALARIM',
        'deposit': '💰 BALANS YÜKLƏ',
        'profile': '👤 PROFİL',
        'bot_info': 'ℹ️ BOT HAQQINDA',
        'help': '❓ KÖMƏK',
        'admin_panel': '👑 İDARƏÇİ',
        'back': '🔙 GERİ',
        'cancel': '❌ LƏĞV ET',
        'yes': '✅ BƏLİ',
        'no': '❌ XEYR',
        'time': '⏰ Saat',
        'join_channel': '📢 KANALA QOŞUL',
        'joined': '✅ QOŞULDUM',
        'loading': '⏳ Yüklənir...',
        'success': '✅ Uğurlu!',
        'error': '❌ Xəta!',
        'choose_amount': '👇 MƏBLƏĞ SEÇİN',
        'min': 'Min',
        'max': 'Max',
        'bonus_system': '🎁 BONUS',
        'example': '💡 NÜMUNƏ',
        'payment_info': '💳 ÖDƏNİŞ',
        'steps': '👇 ADDIMLAR',
        'copy_address': '1️⃣ Ünvanı kopyala',
        'send_trx': '2️⃣ TRX göndər',
        'send_txid': '3️⃣ TXID göndər',
        'balance_loaded': '4️⃣ Balans yüklənəcək',
        'processing_time': '⏳ Əməliyyat müddəti',
        'txid_format': '✅ TXID formatı',
        'user': '👤 İstifadəçi',
        'normal_balance': '💵 Normal Balans',
        'ad_balance': '📺 Reklam Balansı',
        'total_balance': '💰 Ümumi Balans',
        'statistics': '📊 Statistikalar',
        'total_investment': 'Ümumi İnvestisiya',
        'total_bonus': 'Ümumi Bonus',
        'task_count': 'Tapşırıq Sayısı',
        'referral_count': 'Referal',
        'ad_bonus_note': '💡 Reklam balansı bonusludur!',
        'features': '💰 XÜSUSİYYƏTLƏR',
        'commands': '📋 KOMANDALAR',
        'rules': '⚠️ QAYDALAR',
        'support': '📞 DƏSTƏK',
        'how_it_works': '🤖 BOT NECƏ İŞLƏYİR?',
        'how_deposit': '💰 BALANS NECƏ YÜKLƏNİR?',
        'how_create_campaign': '📢 KAMPANIYA NECƏ YARADILIR?',
        'how_do_task': '🎯 TAPŞIRIQ NECƏ EDİLİR?',
        'referral_system': '👥 REFERAL SİSTEMİ',
        'cancel_system': '🔄 LƏĞV SİSTEMİ',
        'important_warnings': '⚠️ ƏHƏMİYYƏTLİ XƏBƏRDARLIQLAR',
        'no_campaigns': '📭 HƏLƏ KAMPANIYANIZ YOXDUR',
        'create_first_campaign': '💡 İlk kampaniyanızı yaradın!',
        'active': '🟢 Aktiv',
        'pending': '🟡 Gözləyən',
        'inactive': '🔴 Passiv',
        'summary': '📊 XÜLASƏ',
        'total': '📈 Ümumi',
        'campaign_type': '🎯 KAMPANIYA NÖVÜ',
        'bot_campaign': '🤖 BOT KAMPANIYASI',
        'channel_campaign': '📢 KANAL KAMPANIYASI',
        'group_campaign': '👥 QRUPA KAMPANIYASI',
        'choose_type': '👇 NÖV SEÇİN',
        'step': '📌 ADDIM',
        'enter_name': 'Ad daxil edin',
        'enter_description': 'Təsvir daxil edin',
        'enter_link': 'Link daxil edin',
        'enter_budget': 'Büdcə daxil edin',
        'enter_channel': 'Kanal/Qrup daxil edin',
        'forward_message': '📤 Mesaj forward edin',
        'how_to_forward': 'Necə edilir',
        'accepted': '✅ QƏBUL EDİLƏN',
        'rejected': '❌ RƏDD EDİLƏN',
        'campaign_summary': '📋 KAMPANIYA XÜLASƏSİ',
        'target_bot': '🤖 HƏDƏF BOT',
        'message_content': '📝 MESAJ',
        'target': '🎯 HƏDƏF',
        'bot_status': '👑 BOT VƏZİYYƏTİ',
        'warning': '⚠️ XƏBƏRDARLIQ',
        'task_price': '💵 TAPŞIRIQ QİYMƏTİ',
        'max_participants': '👥 MAKSİMUM',
        'creator': '👤 YARADAN',
        'confirm_campaign': 'Kampaniyanı təsdiqləyirsiniz?',
        'auto_approval': '✅ Avtomatik aktiv olacaq',
        'check_bot_admin': '🔄 BOT ADMIN KONTROL',
        'approve_send': '✅ TƏSDİQLƏ VƏ GÖNDƏR',
        'campaign_created': '✅ KAMPANIYA YARADILDI!',
        'campaign_id': '🔢 KAMPANIYA ID',
        'status': '📊 VƏZİYYƏT',
        'budget_deducted': '💰 Balans çıxıldı',
        'bot_not_admin': '❌ BOT ADMIN DEYİL!',
        'insufficient_balance': '❌ KİFAYƏT QƏDƏR BALANS YOXDUR!',
        'required': 'Tələb olunan',
        'available': 'Mövcud',
        'missing': 'Çatışmayan',
        'please_deposit': '💡 Zəhmət olmasa əvvəlcə balans yükləyin',
        'follow_steps': 'Zəhmət olmasa addımları izləyin',
        'add_admin': 'İdarəçi Əlavə Et',
        'all_permissions': 'BÜTÜN SƏLAHİYYƏTLƏRİ aktiv edin',
        'see_members': 'Üzvləri görə bilmə səlahiyyəti',
        'save': 'Saxla',
        'check_again': '✅ Yenidən yoxla',
        'any_bot': 'HƏRHANSİ BİR BOT',
        'any_bot_message': 'HƏRHANSİ BİR BOT mesajı',
        'all_bots_accepted': 'Bütün bot mesajları',
        'normal_users_rejected': 'Normal istifadəçi mesajları',
        'suggested_bots': 'Tövsiyyə edilən botlar',
        'bot_father': '@BotFather - Bot yaratma',
        'like_bot': '@like - Bəyənmə botu',
        'vid_bot': '@vid - Video yükləmə',
        'game_bot': '@gamebot - Oyun botu',
        'or_any_bot': 'və ya hər hansı bir bot...',
        'only_bot_message': '❌ Yalnız BOT mesajı forward edin!',
        'normal_user_message': '⚠️ Normal istifadəçi mesajı forward etdiniz',
        'correct_steps': 'Doğru addımlar',
        'find_bot_message': 'BOT mesajı tapın',
        'forward_to_bot': 'Bu bota FORWARD edin',
        'system_will_detect': 'Sistem avtomatik aşkarlayacaq',
        'note_only_bots': 'Qeyd: Yalnız bot mesajları qəbul edilir!',
        'please_forward': '📤 ZƏHMƏT OLMASA MESAJ FORWARD EDİN!',
        'forward_any_bot': 'HƏRHANSİ BİR BOT mesajı forward edin',
        'steps_to_forward': 'Addımlar',
        'find_bot': 'BOT mesajı tapın',
        'press_hold': 'Mesaja basılı saxlayın',
        'click_forward': 'Forward klikləyin',
        'select_this_bot': 'Bu botu seçin',
        'send': 'Göndərin',
        'operation_cancelled': '🔄 Əməliyyat ləğv edildi',
        'no_active_operation': '⚠️ Aktiv əməliyyat yoxdur',
        'redirecting_to_menu': 'Əsas menyuya yönləndirilirsiniz...',
        'channel_check_success': '✅ Kanal yoxlaması uğurlu!',
        'not_joined_channel': '❌ Hələ kanala qoşulmadınız!',
        'error_occurred': '❌ Xəta baş verdi',
        'admin_no_permission': '❌ Bu əməliyyat üçün icazəniz yoxdur!',
        'admin_panel_title': '👑 İDARƏÇİ PANELİ',
        'statistics_title': '📊 STATİSTİKALAR',
        'total_users': 'Ümumi İstifadəçilər',
        'total_balance': 'Ümumi Balans',
        'active_campaigns': 'Aktiv Kampaniyalar',
        'pending_approval': 'Təsdiq Gözləyən',
        'current_time': '⏰ Saat',
        'admin_tools': '🛠️ İDARƏÇİ ALƏTLƏRİ',
        'user_stats': '📊 STATİSTİKALAR',
        'campaign_stats': '📢 KAMPANIYALAR',
        'user_management': '👥 İSTİFADƏÇİLƏR',
        'deposit_management': '💰 DEPOZİTLƏR',
        'broadcast': '📣 BİLDİRİŞ',
        'settings': '⚙️ AYARLAR',
        'campaign_approved': '✅ Kampaniya təsdiqləndi!',
        'campaign_active': 'Kampaniya aktiv edildi',
        'users_can_join': 'İstifadəçilər qoşula bilər',
        'earnings_per_participation': 'Hər iştirak üçün qazanc',
        'duration_until_budget': 'Büdcə bitənə qədər müddət',
        'campaign_rejected': '❌ Kampaniya rədd edildi!',
        'reason_for_rejection': 'RƏDD SƏBƏBİ',
        'bot_not_admin_reason': 'Bot kanalda admin deyil',
        'not_following_rules': 'Kampaniya qaydalara uyğun deyil',
        'missing_info': 'Çatışmayan məlumat',
        'suspicious_content': 'Şübhəli məzmun',
        'balance_refunded': '💰 Balans geri qaytarıldı',
        'check_rules_try_again': '💡 Qaydaları yoxlayıb yenidən cəhd edin',
        'welcome_bonus_loaded': '✅ Xoş gəldin bonusu yükləndi!',
        'new_balance': 'Yeni balansınız',
        'start_tasks': '⚡ Dərhal tapşırıq etməyə başla!',
        'referral_successful': '🎉 Referal uğurlu!',
        'referral_bonus_loaded': '💰 Referal bonusu yükləndi',
        'forward_bot_message': '🤖 Bot mesajı uğurla alındı!',
        'enter_campaign_name': '📛 Kampaniya adı daxil edin',
        'example_names': 'Nümunə adlar',
        'join_our_channel': 'Kanalımıza qoşulun',
        'youtube_subscribe': 'YouTube Abunə Ol',
        'instagram_follow': 'Instagram İzləyin',
        'discord_join': 'Discord Serverinə Qoşulun',
        'enter_your_name': 'Kampaniya adınızı yazın',
        'name_saved': '✅ Ad Saxlandı',
        'description_saved': '✅ Təsvir Saxlandı',
        'link_saved': '✅ Link Saxlandı',
        'channel_saved': '✅ Kanal/Qrup Saxlandı',
        'budget_saved': '✅ Büdcə Saxlandı',
        'minimum_budget': 'Minimum büdcə 10₺!',
        'invalid_budget': '❌ Yanlış büdcə! Zəhmət olmasa rəqəm daxil edin',
        'invalid_format': '❌ Yanlış format! @ ilə başlamalı və ya link olmalı',
        'channel_not_found': '❌ Kanal/Qrup tapılmadı!',
        'enter_correct_name': 'Zəhmət olmasa doğru ad daxil edin',
        'bot_not_admin_warning': '⚠️ BOT ADMIN DEYİL!',
        'to_create_campaign': 'Kampaniya yaratmaq üçün',
        'make_bot_admin': 'Botu kanalda ADMIN edin',
        'give_permissions': 'Səlahiyyətləri verin',
        'continue_after_admin': 'Admin etdikdən sonra davam edin',
        'cancel_text': '/cancel yazaraq ləğv edə bilərsiniz',
        'operation_cancelled_text': '❌ Əməliyyat ləğv edildi'
    }
}

def get_translation(user_id, key, language=None):
    """Kullanıcının diline göre çeviri döndür"""
    if not language:
        db = Database()
        user = db.get_user(user_id)
        language = user.get('language', 'tr')
    return translations.get(language, translations['tr']).get(key, key)

# Bot Sistemi
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.user_states = {}
        self.trx_price = 12.61
        self.update_trx_price()
        print("🤖 Bot sistemi başlatıldı")
    
    def update_trx_price(self):
        try:
            response = requests.get(TRX_PRICE_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.trx_price = data.get('tron', {}).get('try', 12.61)
                print(f"₿ TRX Fiyatı: {self.trx_price:.2f}₺")
        except: 
            pass
    
    def set_user_state(self, user_id, state, data=None):
        self.user_states[user_id] = {'state': state, 'data': data or {}, 'step': 1}
    
    def get_user_state(self, user_id):
        return self.user_states.get(user_id, {'state': None, 'data': {}, 'step': 1})
    
    def clear_user_state(self, user_id):
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def start_polling(self):
        offset = 0
        print("🔄 Telegram polling başladı...")
        
        while True:
            try:
                url = BASE_URL + "getUpdates"
                params = {'offset': offset, 'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
                response = requests.get(url, params=params, timeout=35).json()
                
                if response.get('ok'):
                    updates = response['result']
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            threading.Thread(target=self.process_message, args=(update['message'],)).start()
                        elif 'callback_query' in update:
                            threading.Thread(target=self.process_callback, args=(update['callback_query'],)).start()
                
            except Exception as e:
                print(f"❌ Polling hatası: {e}")
                time.sleep(2)
    
    def process_message(self, message):
        try:
            if 'from' not in message: return
            
            user_id = str(message['from']['id'])
            user_state = self.get_user_state(user_id)
            
            user = self.db.get_user(user_id)
            if not user.get('name'):
                self.db.update_user(user_id, {
                    'name': message['from'].get('first_name', 'Kullanıcı'),
                    'username': message['from'].get('username', '')
                })
            
            # Kullanıcı state'i varsa önce onu işle
            if user_state['state']:
                self.handle_user_state(user_id, message, user_state)
                return
            
            if 'text' in message:
                text = message['text']
                if text.startswith('/start'): 
                    self.handle_start(user_id, text)
                elif text == '/menu': 
                    self.show_main_menu(user_id)
                elif text == '/admin' and user_id == ADMIN_ID: 
                    self.show_admin_panel(user_id)
                elif text == '/createcampaign': 
                    self.start_campaign_type_selection(user_id)
                elif text == '/deposit': 
                    self.show_deposit_menu(user_id)
                elif text == '/mycampaigns': 
                    self.show_my_campaigns(user_id)
                elif text == '/balance': 
                    self.show_balance(user_id)
                elif text == '/botinfo': 
                    self.show_bot_info(user_id)
                elif text == '/help': 
                    self.show_help(user_id)
                elif text == '/cancel':
                    self.handle_cancel(user_id)
                elif text == '/language':
                    self.show_language_menu(user_id)
                elif text == '/tasks':
                    self.show_active_tasks(user_id)
                elif text == '/profile':
                    self.show_profile(user_id)
        
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def handle_user_state(self, user_id, message, user_state):
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # /cancel komutu için her durumda çalışsın
        if 'text' in message and message['text'] == '/cancel':
            self.handle_cancel(user_id)
            return
        
        # KAMPANYA OLUŞTURMA
        if state == 'creating_campaign':
            if step == 1:  # İsim
                data['name'] = message['text']
                user_state['step'] = 2
                send_message(user_id, f"""
<b>{get_translation(user_id, 'name_saved')}</b>

<b>{get_translation(user_id, 'step')} 2/5 - {get_translation(user_id, 'enter_description')}:</b>
<i>{get_translation(user_id, 'example')}: '{get_translation(user_id, 'join_our_channel')}'</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
            
            elif step == 2:  # Açıklama
                data['description'] = message['text']
                user_state['step'] = 3
                send_message(user_id, f"""
<b>{get_translation(user_id, 'description_saved')}</b>

<b>{get_translation(user_id, 'step')} 3/5 - {get_translation(user_id, 'enter_link')}:</b>
<i>{get_translation(user_id, 'example')}: https://t.me/kanaladi</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
            
            elif step == 3:  # Link
                data['link'] = message['text']
                user_state['step'] = 4
                
                task_type = data['task_type']
                if task_type == 'bot':
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'link_saved')}</b>

<b>{get_translation(user_id, 'step')} 4/5 - {get_translation(user_id, 'enter_budget')} (₺):</b>
<i>{get_translation(user_id, 'min')}: 10₺ - {get_translation(user_id, 'enter_budget')} (örn: 50)</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
                else:
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'link_saved')}</b>

<b>{get_translation(user_id, 'step')} 4/5 - {get_translation(user_id, 'enter_channel')}:</b>
<i>@ {get_translation(user_id, 'enter_channel')}</i>
<i>{get_translation(user_id, 'example')}: @kanaladi və ya https://t.me/kanaladi</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
            
            elif step == 4:
                task_type = data['task_type']
                
                if task_type == 'bot':
                    try:
                        budget = float(message['text'])
                        if budget < 10:
                            send_message(user_id, f"❌ <b>{get_translation(user_id, 'minimum_budget')}</b>")
                            return
                        
                        data['budget'] = budget
                        user_state['step'] = 5
                        self.show_campaign_summary(user_id, data)
                    except:
                        send_message(user_id, f"❌ <b>{get_translation(user_id, 'invalid_budget')}</b>")
                
                else:  # Kanal veya Grup
                    chat_input = message['text'].strip()
                    
                    # @ işaretini kontrol et
                    if not chat_input.startswith('@') and not chat_input.startswith('https://t.me/'):
                        send_message(user_id, f"❌ <b>{get_translation(user_id, 'invalid_format')}</b>\n\n{get_translation(user_id, 'example')}: @kanaladi və ya https://t.me/kanaladi")
                        return
                    
                    # Linkten @username çıkar
                    if chat_input.startswith('https://t.me/'):
                        chat_input = '@' + chat_input.split('/')[-1]
                    
                    # Kanal bilgilerini al
                    chat_info = get_chat_info(chat_input)
                    if not chat_info:
                        send_message(user_id, f"❌ <b>{get_translation(user_id, 'channel_not_found')}</b>\n\n{get_translation(user_id, 'enter_correct_name')}: {chat_input}")
                        return
                    
                    # Botun admin olup olmadığını kontrol et
                    is_bot_admin = check_bot_admin(chat_info['id'])
                    
                    data['target_chat_id'] = str(chat_info['id'])
                    data['target_chat_name'] = chat_info.get('title', chat_input)
                    data['is_bot_admin'] = 1 if is_bot_admin else 0
                    user_state['step'] = 5
                    
                    if not is_bot_admin:
                        send_message(user_id, f"""
<b>{get_translation(user_id, 'bot_not_admin_warning')}</b>

📢 <b>Kanal/Qrup:</b> {chat_info.get('title', chat_input)}

<b>{get_translation(user_id, 'to_create_campaign')}:</b>
1️⃣ {get_translation(user_id, 'make_bot_admin')}
2️⃣ {get_translation(user_id, 'give_permissions')}
3️⃣ {get_translation(user_id, 'give_permissions')}

<b>{get_translation(user_id, 'continue_after_admin')}:</b>
""")
                        time.sleep(1)
                    
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'channel_saved')}</b>

<b>{get_translation(user_id, 'step')} 5/5 - {get_translation(user_id, 'enter_budget')} (₺):</b>
<i>Kanal: <b>{chat_info.get('title', chat_input)}</b></i>
<i>{get_translation(user_id, 'min')}: 10₺ - {get_translation(user_id, 'enter_budget')}</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
            
            elif step == 5:  # Bütçe (kanal/grup için)
                try:
                    budget = float(message['text'])
                    if budget < 10:
                        send_message(user_id, f"❌ <b>{get_translation(user_id, 'minimum_budget')}</b>")
                        return
                    
                    data['budget'] = budget
                    user_state['step'] = 6
                    self.show_campaign_summary(user_id, data)
                except:
                    send_message(user_id, f"❌ <b>{get_translation(user_id, 'invalid_budget')}</b>")
        
        # BOT MESAJ FORWARD
        elif state == 'forward_message':
            # Önce forward mesaj olup olmadığını kontrol et
            if 'forward_from' in message:
                # Bot kontrolü - HERHANGİ BİR BOT OLABİLİR
                if message['forward_from'].get('is_bot', False):
                    forward_from_id = str(message['forward_from']['id'])
                    forward_from_name = message['forward_from'].get('first_name', 'Bot')
                    forward_from_username = message['forward_from'].get('username', '')
                    
                    # Forward edilen mesajın içeriğini al
                    message_text = message.get('text', '') or message.get('caption', '') or ''
                    truncated_text = message_text[:200] + '...' if len(message_text) > 200 else message_text
                    
                    # Verileri kaydet
                    data['forward_message_id'] = message['message_id']
                    data['forward_chat_id'] = message['chat']['id']
                    data['forward_message_text'] = truncated_text
                    data['forward_from_bot_id'] = forward_from_id
                    data['forward_from_bot_name'] = f"{forward_from_name} (@{forward_from_username})" if forward_from_username else forward_from_name
                    
                    # Başarılı mesajı
                    bot_info = f"🤖 <b>{forward_from_name}</b>"
                    if forward_from_username:
                        bot_info += f" (@{forward_from_username})"
                    
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'forward_bot_message')}</b>

{bot_info}

<b>{get_translation(user_id, 'message_content')}:</b>
<i>{truncated_text}</i>

<b>{get_translation(user_id, 'step')} 1/5 - {get_translation(user_id, 'enter_campaign_name')}:</b>
<i>{get_translation(user_id, 'example')}: '{get_translation(user_id, 'join_our_channel')}'</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
                    
                    # Kampanya oluşturma state'ine geç
                    user_state['step'] = 1
                    user_state['state'] = 'creating_campaign'
                    
                else:
                    # Bot değil, normal kullanıcı mesajı
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'only_bot_message')}</b>

⚠️ <b>{get_translation(user_id, 'normal_user_message')}.</b>

<b>{get_translation(user_id, 'correct_steps')}:</b>
1️⃣ {get_translation(user_id, 'find_bot_message')}
2️⃣ {get_translation(user_id, 'forward_to_bot')}
3️⃣ {get_translation(user_id, 'system_will_detect')}

<i>{get_translation(user_id, 'note_only_bots')}</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
            elif 'text' in message and message['text'] == '/cancel':
                self.handle_cancel(user_id)
            else:
                # Forward mesaj değil
                send_message(user_id, f"""
<b>{get_translation(user_id, 'please_forward')}</b>

<i>{get_translation(user_id, 'forward_any_bot')}:</i>

<b>{get_translation(user_id, 'steps_to_forward')}:</b>
1️⃣ {get_translation(user_id, 'find_bot')}
2️⃣ {get_translation(user_id, 'press_hold')}
3️⃣ {get_translation(user_id, 'click_forward')}
4️⃣ {get_translation(user_id, 'select_this_bot')}
5️⃣ {get_translation(user_id, 'send')}

<b>{get_translation(user_id, 'suggested_bots')}:</b>
• {get_translation(user_id, 'bot_father')}
• {get_translation(user_id, 'like_bot')}
• {get_translation(user_id, 'vid_bot')}
• {get_translation(user_id, 'game_bot')}
• <i>{get_translation(user_id, 'or_any_bot')}</i>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
        
        # TXID BEKLEME
        elif state == 'waiting_txid':
            txid = message['text'].strip()
            deposit_id = data.get('deposit_id')
            
            # TXID format kontrolü
            if len(txid) < 10 or len(txid) > 100:
                send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: TXID formatı geçersiz!</b>\n\n<i>Geçerli TXID girin veya /cancel ile iptal edin</i>")
                return
            
            # Depoziti güncelle
            try:
                self.db.cursor.execute('''
                    UPDATE deposits 
                    SET txid = ?, status = 'completed', completed_at = ?
                    WHERE deposit_id = ? AND user_id = ?
                ''', (txid, get_turkey_time().isoformat(), deposit_id, user_id))
                
                # Kullanıcı bakiyesini güncelle
                user = self.db.get_user(user_id)
                amount = data['amount']
                bonus = data['bonus']
                
                # Normal bakiye güncelle
                new_balance = user.get('balance', 0) + amount + bonus
                self.db.update_user(user_id, {
                    'balance': new_balance,
                    'total_deposited': user.get('total_deposited', 0) + amount,
                    'deposit_count': user.get('deposit_count', 0) + 1,
                    'total_bonus': user.get('total_bonus', 0) + bonus
                })
                
                self.db.conn.commit()
                
                # Başarı mesajı
                send_message(user_id, f"""
<b>✅ {get_translation(user_id, 'success')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 {get_translation(user_id, 'deposit')} tamamlandı!</b>
<b>💳 Tutar:</b> {amount:.2f}₺
<b>🎁 Bonus:</b> {bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})
<b>💰 Toplam:</b> {amount + bonus:.2f}₺
<b>📊 Yeni bakiye:</b> {new_balance:.2f}₺
<b>🔗 TXID:</b> <code>{txid[:20]}...</code>

<i>Bakiye başarıyla yüklendi. Hemen görev yapmaya başlayabilirsin!</i>
""")
                
                self.clear_user_state(user_id)
                time.sleep(2)
                self.show_main_menu(user_id)
                
            except Exception as e:
                print(f"❌ TXID hatası: {e}")
                send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: İşlem kaydedilemedi! Lütfen admin ile iletişime geçin.</b>")
    
    def process_callback(self, callback):
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # İptal butonu kontrolü
            if data == 'cancel':
                self.handle_cancel(user_id)
                answer_callback(callback_id, get_translation(user_id, 'operation_cancelled'))
                return
            
            # Dil değiştirme
            if data.startswith('lang_'):
                language = data.replace('lang_', '')
                self.db.update_user(user_id, {'language': language})
                answer_callback(callback_id, f"✅ Dil {language.upper()} olarak ayarlandı!")
                self.show_main_menu(user_id)
                return
            
            # Admin callback'leri
            if data.startswith('admin_'):
                if user_id != ADMIN_ID:
                    answer_callback(callback_id, get_translation(user_id, 'admin_no_permission'), show_alert=True)
                    return
                
                if data.startswith('admin_approve_'):
                    campaign_id = data.replace('admin_approve_', '')
                    self.approve_campaign(campaign_id)
                    answer_callback(callback_id, f"✅ Kampanya {campaign_id} onaylandı!")
                elif data.startswith('admin_reject_'):
                    campaign_id = data.replace('admin_reject_', '')
                    self.reject_campaign(campaign_id)
                    answer_callback(callback_id, f"❌ Kampanya {campaign_id} reddedildi!")
                elif data == 'admin_panel':
                    self.show_admin_panel(user_id)
                elif data == 'admin_campaigns':
                    self.show_admin_campaigns(user_id)
                elif data == 'admin_users':
                    self.show_admin_users(user_id)
                elif data == 'admin_stats':
                    self.show_admin_stats(user_id)
                elif data == 'admin_broadcast':
                    self.start_broadcast(user_id)
            
            # Normal callback'ler
            elif data == 'menu':
                self.show_main_menu(user_id)
            elif data == 'create_campaign':
                self.start_campaign_type_selection(user_id)
            elif data.startswith('camp_type_'):
                task_type = data.replace('camp_type_', '')
                self.start_campaign_creation(user_id, task_type)
            elif data == 'deposit':
                self.show_deposit_menu(user_id)
            elif data.startswith('deposit_amount_'):
                amount = float(data.replace('deposit_amount_', ''))
                self.start_deposit(user_id, amount)
            elif data == 'my_campaigns':
                self.show_my_campaigns(user_id)
            elif data == 'bot_info':
                self.show_bot_info(user_id)
            elif data == 'help':
                self.show_help(user_id)
            elif data == 'campaign_confirm':
                self.confirm_campaign(user_id)
            elif data == 'campaign_cancel':
                self.clear_user_state(user_id)
                answer_callback(callback_id, get_translation(user_id, 'operation_cancelled'))
                send_message(user_id, f"<b>{get_translation(user_id, 'operation_cancelled_text')}</b>\n\n{get_translation(user_id, 'redirecting_to_menu')}")
                time.sleep(1)
                self.show_main_menu(user_id)
            elif data == 'check_bot_admin':
                self.check_bot_admin_status(user_id)
            elif data == 'joined':
                if get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
                    self.db.update_user(user_id, {'in_channel': 1})
                    answer_callback(callback_id, get_translation(user_id, 'channel_check_success'))
                    self.show_main_menu(user_id)
                else:
                    answer_callback(callback_id, get_translation(user_id, 'not_joined_channel'), show_alert=True)
            elif data == 'active_tasks':
                self.show_active_tasks(user_id)
            elif data == 'profile':
                self.show_profile(user_id)
            elif data == 'language':
                self.show_language_menu(user_id)
        
        except Exception as e:
            print(f"❌ Callback hatası: {e}")
            answer_callback(callback_id, f"{get_translation(user_id, 'error_occurred')}: {str(e)}", show_alert=True)
    
    def handle_cancel(self, user_id):
        """Kullanıcının mevcut işlemini iptal et"""
        user_state = self.get_user_state(user_id)
        
        if user_state['state']:
            previous_state = user_state['state']
            self.clear_user_state(user_id)
            
            cancel_messages = {
                'forward_message': f"📤 {get_translation(user_id, 'operation_cancelled')}",
                'creating_campaign': f"📢 {get_translation(user_id, 'operation_cancelled')}",
                'waiting_txid': f"💳 {get_translation(user_id, 'operation_cancelled')}"
            }
            
            message = cancel_messages.get(previous_state, f"🔄 {get_translation(user_id, 'operation_cancelled')}")
            send_message(user_id, f"<b>{message}</b>\n\n{get_translation(user_id, 'redirecting_to_menu')}")
            time.sleep(1)
            self.show_main_menu(user_id)
        else:
            send_message(user_id, f"<b>{get_translation(user_id, 'no_active_operation')}</b>")
    
    def show_language_menu(self, user_id):
        """Dil seçim menüsü"""
        markup = {
            'inline_keyboard': [
                [{'text': '🇹🇷 Türkçe', 'callback_data': 'lang_tr'}],
                [{'text': '🇦🇿 Azərbaycan Dili', 'callback_data': 'lang_az'}],
                [{'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, "🌐 <b>Dil Seçin / Dil Seçin</b>\n\n👇 Aşağıdaki dillerden birini seçin:", markup)
    
    def handle_start(self, user_id, text):
        in_channel = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        
        if not in_channel:
            markup = {
                'inline_keyboard': [[
                    {'text': get_translation(user_id, 'join_channel'), 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': get_translation(user_id, 'joined'), 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, f"""
<b>{get_translation(user_id, 'welcome')}</b>

🤖 <b>Görev Yapsam Bot</b>'a hoş geldiniz!

📢 <b>Botu kullanmak için:</b>
1️⃣ Önce kanala katılın: <b>@{MANDATORY_CHANNEL}</b>
2️⃣ Katıldıktan sonra <b>{get_translation(user_id, 'joined')}</b> butonuna basın

💡 <b>Özellikler:</b>
• Görev yap para kazan
• Kampanya oluştur
• TRX ile bakiye yükle
• Bonus sistemi
""", markup)
            return
        
        user = self.db.get_user(user_id)
        if not user.get('welcome_bonus'):
            self.db.add_balance(user_id, 2.0)
            self.db.update_user(user_id, {'welcome_bonus': 1, 'in_channel': 1})
            send_message(user_id, f"""
<b>🎉 {get_translation(user_id, 'welcome')} {user.get('name', 'Kullanıcı')}!</b>

✅ <b>{get_translation(user_id, 'welcome_bonus_loaded')}</b>
💰 <b>{get_translation(user_id, 'new_balance')}:</b> {user.get('balance', 0) + 2.0:.2f}₺

⚡ <i>{get_translation(user_id, 'start_tasks')}</i>
""")
        
        # Referans kontrolü
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith('ref_'):
                referrer_id = parts[1].replace('ref_', '')
                if referrer_id and referrer_id != user_id:
                    referrer = self.db.get_user(referrer_id)
                    if referrer:
                        self.db.add_balance(referrer_id, 1.0)
                        self.db.update_user(referrer_id, {
                            'referrals': referrer.get('referrals', 0) + 1,
                            'ref_earned': referrer.get('ref_earned', 0) + 1.0
                        })
                        send_message(user_id, f"<b>{get_translation(user_id, 'referral_successful')}</b>\n\n💰 <b>{get_translation(user_id, 'referral_bonus_loaded')}</b>")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>🤖 GÖREV YAPSAM BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>{get_translation(user_id, 'user')}:</b> {user.get('name', 'Kullanıcı')}
💰 <b>{get_translation(user_id, 'balance')}:</b> <code>{user.get('balance', 0):.2f}₺</code>
📊 <b>{get_translation(user_id, 'tasks')}:</b> {user.get('tasks_completed', 0)}
👥 <b>{get_translation(user_id, 'referrals')}:</b> {user.get('referrals', 0)}

<b>{get_translation(user_id, 'price')}:</b> {self.trx_price:.2f}₺
<b>{get_translation(user_id, 'channel')}:</b> @{MANDATORY_CHANNEL}
<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{get_translation(user_id, 'main_menu')}</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation(user_id, 'do_task'), 'callback_data': 'active_tasks'}],
                [{'text': get_translation(user_id, 'create_campaign'), 'callback_data': 'create_campaign'}],
                [{'text': get_translation(user_id, 'my_campaigns'), 'callback_data': 'my_campaigns'}],
                [{'text': get_translation(user_id, 'deposit'), 'callback_data': 'deposit'}],
                [{'text': get_translation(user_id, 'profile'), 'callback_data': 'profile'},
                 {'text': get_translation(user_id, 'language'), 'callback_data': 'language'}],
                [{'text': get_translation(user_id, 'bot_info'), 'callback_data': 'bot_info'},
                 {'text': get_translation(user_id, 'help'), 'callback_data': 'help'}]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([{'text': get_translation(user_id, 'admin_panel'), 'callback_data': 'admin_panel'}])
        
        send_message(user_id, message, markup)
    
    def show_active_tasks(self, user_id):
        """Aktif görevleri göster"""
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            WHERE status = 'active' AND remaining_budget > 0
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            send_message(user_id, f"""
<b>🎯 {get_translation(user_id, 'do_task')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>{get_translation(user_id, 'no_campaigns')}</b>

💡 <b>{get_translation(user_id, 'create_first_campaign')}</b>

<i>Şu anda aktif görev bulunmuyor.</i>
""")
            time.sleep(2)
            self.show_main_menu(user_id)
            return
        
        message = f"<b>🎯 {get_translation(user_id, 'do_task')}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, camp in enumerate(campaigns, 1):
            task_type = camp['task_type']
            task_icon = "🤖" if task_type == 'bot' else "📢" if task_type == 'channel' else "👥"
            task_name = get_translation(user_id, 'bot_campaign') if task_type == 'bot' else get_translation(user_id, 'channel_campaign') if task_type == 'channel' else get_translation(user_id, 'group_campaign')
            
            message += f"""{task_icon} <b>{camp['name'][:30]}</b>
├ <b>Tip:</b> {task_name}
├ <b>Ödül:</b> {camp['price_per_task']}₺
├ <b>Kalan:</b> {int(camp['remaining_budget'] / camp['price_per_task'])} kişi
└ <b>ID:</b> <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        message += f"\n<b>💡 Görev yapmak için:</b>\n1. Görev ID'sini kopyala\n2. Görevi tamamla\n3. Kanıt gönder\n4. Ödülü al"
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        """Profil bilgilerini göster"""
        user = self.db.get_user(user_id)
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>👤 {get_translation(user_id, 'profile')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'user')}:</b> {user.get('name', 'Kullanıcı')}
<b>👤 Username:</b> @{user.get('username', 'yok')}
<b>🆔 ID:</b> <code>{user_id}</code>

<b>💰 {get_translation(user_id, 'balance')}:</b>
• {get_translation(user_id, 'normal_balance')}: {user.get('balance', 0):.2f}₺
• {get_translation(user_id, 'ad_balance')}: {user.get('ads_balance', 0):.2f}₺
• {get_translation(user_id, 'total_balance')}: {user.get('balance', 0) + user.get('ads_balance', 0):.2f}₺

<b>{get_translation(user_id, 'statistics')}:</b>
• {get_translation(user_id, 'total_investment')}: {user.get('total_deposited', 0):.2f}₺
• {get_translation(user_id, 'total_bonus')}: {user.get('total_bonus', 0):.2f}₺
• {get_translation(user_id, 'task_count')}: {user.get('tasks_completed', 0)}
• {get_translation(user_id, 'referral_count')}: {user.get('referrals', 0)}

<b>💡 {get_translation(user_id, 'ad_bonus_note')}</b>
<b>⏰ {get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation(user_id, 'deposit'), 'callback_data': 'deposit'}],
                [{'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            send_message(user_id, f"❌ <b>Önce kanala katılmalısın!</b>\n\n👉 @{MANDATORY_CHANNEL}")
            return
        
        message = f"""
<b>{get_translation(user_id, 'create_campaign')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'bot_campaign')}</b>
• Görev: <b>{get_translation(user_id, 'any_bot_message')}</b>
• Ödül: 2.5₺ her katılım
• Durum: OTOMATİK AKTİF
• Not: {get_translation(user_id, 'all_bots_accepted')}

<b>{get_translation(user_id, 'channel_campaign')}</b>
• Görev: Kanala katılma
• Ödül: 1.5₺ her katılım
• Durum: Bot kanalda admin olmalı
• Not: Botu kanalda admin yapın

<b>{get_translation(user_id, 'group_campaign')}</b>
• Görev: Gruba katılma
• Ödül: 1₺ her katılım
• Durum: Bot grupta admin olmalı
• Not: Botu grupta admin yapın

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{get_translation(user_id, 'choose_type')}</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation(user_id, 'bot_campaign'), 'callback_data': 'camp_type_bot'}],
                [{'text': get_translation(user_id, 'channel_campaign'), 'callback_data': 'camp_type_channel'}],
                [{'text': get_translation(user_id, 'group_campaign'), 'callback_data': 'camp_type_group'}],
                [{'text': get_translation(user_id, 'cancel'), 'callback_data': 'cancel'}, 
                 {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        user = self.db.get_user(user_id)
        
        if task_type == 'bot':
            self.set_user_state(user_id, 'forward_message', {'task_type': task_type})
            send_message(user_id, f"""
<b>{get_translation(user_id, 'bot_campaign')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'step')} 1:</b> <b>{get_translation(user_id, 'forward_message')}</b>

<b>{get_translation(user_id, 'how_to_forward')}:</b>
1️⃣ <b>{get_translation(user_id, 'any_bot')}</b>'in mesajını tapın
   • @BotFather, @like, @vid, @gamebot və s.
2️⃣ Mesajı bu bota forward edin
3️⃣ Sistem avtomatik aşkarlayacaq

<b>{get_translation(user_id, 'accepted')}:</b> {get_translation(user_id, 'all_bots_accepted')}
<b>{get_translation(user_id, 'rejected')}:</b> {get_translation(user_id, 'normal_users_rejected')}

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
        else:
            task_name = get_translation(user_id, 'channel_campaign') if task_type == 'channel' else get_translation(user_id, 'group_campaign')
            self.set_user_state(user_id, 'creating_campaign', {'task_type': task_type})
            send_message(user_id, f"""
<b>{task_name}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'step')} 1/5:</b> {get_translation(user_id, 'enter_campaign_name')}

<b>{get_translation(user_id, 'example_names')}:</b>
• {get_translation(user_id, 'join_our_channel')}
• {get_translation(user_id, 'youtube_subscribe')}
• {get_translation(user_id, 'instagram_follow')}
• {get_translation(user_id, 'discord_join')}

<i>{get_translation(user_id, 'enter_your_name')} və ya</i>
<code>/cancel</code> <i>{get_translation(user_id, 'cancel_text')}</i>
""")
    
    def show_campaign_summary(self, user_id, data):
        task_type = data['task_type']
        task_name = get_translation(user_id, 'bot_campaign') if task_type == 'bot' else get_translation(user_id, 'channel_campaign') if task_type == 'channel' else get_translation(user_id, 'group_campaign')
        price = 2.5 if task_type == 'bot' else 1.5 if task_type == 'channel' else 1.0
        budget = data['budget']
        max_participants = int(budget / price)
        
        summary = f"""
<b>{get_translation(user_id, 'campaign_summary')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'campaign_type')}:</b> {task_name}
<b>📛 {get_translation(user_id, 'enter_name')}:</b> {data['name']}
<b>📄 {get_translation(user_id, 'enter_description')}:</b> {data['description'][:80]}...
<b>🔗 {get_translation(user_id, 'enter_link')}:</b> {data['link'][:50]}...
"""
        
        if task_type == 'bot':
            bot_name = data.get('forward_from_bot_name', 'Bilinmeyen Bot')
            summary += f"<b>{get_translation(user_id, 'target_bot')}:</b> {bot_name}\n"
            summary += f"<b>{get_translation(user_id, 'message_content')}:</b> {data.get('forward_message_text', '')[:50]}...\n"
        elif task_type in ['channel', 'group']:
            chat_name = data.get('target_chat_name', 'Bilinmiyor')
            is_bot_admin = data.get('is_bot_admin', 0)
            admin_status = "✅ BOT ADMIN" if is_bot_admin else "❌ BOT ADMIN DEĞİL"
            
            summary += f"<b>{get_translation(user_id, 'target')}:</b> {chat_name}\n"
            summary += f"<b>{get_translation(user_id, 'bot_status')}:</b> {admin_status}\n"
            
            if not is_bot_admin:
                summary += f"\n<b>{get_translation(user_id, 'warning')}:</b> Bot bu {task_type}da admin değil!\n"
                summary += f"<b>{get_translation(user_id, 'continue_after_admin')}.</b>\n"
        
        summary += f"""
<b>💰 {get_translation(user_id, 'enter_budget')}:</b> {budget:.2f}₺
<b>{get_translation(user_id, 'task_price')}:</b> {price}₺
<b>{get_translation(user_id, 'max_participants')}:</b> {max_participants}
<b>{get_translation(user_id, 'creator')}:</b> {data.get('creator_name', 'Kullanıcı')}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{get_translation(user_id, 'confirm_campaign')}</b>
<i>{get_translation(user_id, 'auto_approval')}.</i>
"""
        
        markup = {
            'inline_keyboard': []
        }
        
        if task_type in ['channel', 'group'] and not data.get('is_bot_admin', 0):
            markup['inline_keyboard'].append([{'text': get_translation(user_id, 'check_bot_admin'), 'callback_data': 'check_bot_admin'}])
        
        markup['inline_keyboard'].extend([
            [{'text': get_translation(user_id, 'approve_send'), 'callback_data': 'campaign_confirm'}],
            [{'text': get_translation(user_id, 'cancel'), 'callback_data': 'campaign_cancel'}]
        ])
        
        send_message(user_id, summary, markup)
    
    def confirm_campaign(self, user_id):
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: Kampanya verisi bulunamadı!</b>")
            return
        
        # Kanal/grup için bot admin kontrolü
        if data['task_type'] in ['channel', 'group']:
            chat_id = data.get('target_chat_id')
            if chat_id:
                is_bot_admin = check_bot_admin(chat_id)
                if not is_bot_admin:
                    send_message(user_id, f"""
<b>{get_translation(user_id, 'bot_not_admin')}</b>

{get_translation(user_id, 'to_create_campaign')} botu kanalda/grupta admin yapmalısınız.

<b>{get_translation(user_id, 'follow_steps')}:</b>
1️⃣ {get_translation(user_id, 'enter_channel')} ayarlarına gedin
2️⃣ <b>{get_translation(user_id, 'add_admin')}</b> bölməsinə gedin
3️⃣ <b>@GorevYapsamBot</b> yazın
4️⃣ <b>{get_translation(user_id, 'all_permissions')}</b>
5️⃣ Xüsusilə: <b>{get_translation(user_id, 'see_members')}</b>
6️⃣ <b>{get_translation(user_id, 'save')}</b> düyməsinə basın

<b>{get_translation(user_id, 'check_again')}.</b>
""")
                    return
        
        user = self.db.get_user(user_id)
        balance = user.get('balance', 0)
        budget = data['budget']
        
        if balance < budget:
            send_message(user_id, f"""
<b>{get_translation(user_id, 'insufficient_balance')}</b>

<b>{get_translation(user_id, 'required')}:</b> {budget:.2f}₺
<b>{get_translation(user_id, 'available')}:</b> {balance:.2f}₺
<b>{get_translation(user_id, 'missing')}:</b> {budget - balance:.2f}₺

💡 <b>{get_translation(user_id, 'please_deposit')}.</b>
""")
            return
        
        # Kampanya ID oluştur
        campaign_id = hashlib.md5(f"{user_id}{time.time()}{data['name']}".encode()).hexdigest()[:10].upper()
        
        # Fiyat belirle
        price = 2.5 if data['task_type'] == 'bot' else 1.5 if data['task_type'] == 'channel' else 1.0
        max_participants = int(budget / price)
        
        # Veritabanına kaydet - OTOMATİK AKTİF
        try:
            self.db.cursor.execute('''
                INSERT INTO campaigns 
                (campaign_id, name, description, link, budget, remaining_budget,
                 creator_id, creator_name, task_type, price_per_task, max_participants,
                 status, created_at, forward_message_id, forward_chat_id, forward_message_text,
                 forward_from_bot_id, forward_from_bot_name, target_chat_id, target_chat_name,
                 is_bot_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign_id,
                data['name'],
                data['description'],
                data['link'],
                budget,
                budget,
                user_id,
                user.get('name', 'Kullanıcı'),
                data['task_type'],
                price,
                max_participants,
                'active',  # OTOMATİK AKTİF
                get_turkey_time().isoformat(),
                data.get('forward_message_id', ''),
                data.get('forward_chat_id', ''),
                data.get('forward_message_text', ''),
                data.get('forward_from_bot_id', ''),
                data.get('forward_from_bot_name', ''),
                data.get('target_chat_id', ''),
                data.get('target_chat_name', ''),
                data.get('is_bot_admin', 0)
            ))
            
            # Bakiyeden düş
            self.db.update_user(user_id, {'balance': balance - budget})
            
            self.db.conn.commit()
            
            # Kullanıcıya bilgi ver
            success_msg = f"""
<b>{get_translation(user_id, 'campaign_created')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 {get_translation(user_id, 'enter_name')}:</b> {data['name']}
<b>💰 {get_translation(user_id, 'enter_budget')}:</b> {budget:.2f}₺
<b>{get_translation(user_id, 'campaign_id')}:</b> <code>{campaign_id}</code>

<b>{get_translation(user_id, 'status')}:</b> <i>✅ OTOMATİK AKTİF!</i>

📢 <b>Kampanyanız şimdi aktif! Kullanıcılar katılmaya başlayabilir.</b>

💰 <b>{get_translation(user_id, 'budget_deducted')}:</b> {budget:.2f}₺
"""
            
            send_message(user_id, success_msg)
            self.clear_user_state(user_id)
            time.sleep(2)
            self.show_main_menu(user_id)
            
        except Exception as e:
            print(f"❌ Kampanya hatası: {e}")
            send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: Kampanya oluşturulamadı! Lütfen tekrar deneyin.</b>")
    
    def check_bot_admin_status(self, user_id):
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data or 'target_chat_id' not in data:
            send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: Kanal bilgisi bulunamadı!</b>")
            return
        
        chat_id = data['target_chat_id']
        is_bot_admin = check_bot_admin(chat_id)
        
        if is_bot_admin:
            data['is_bot_admin'] = 1
            send_message(user_id, f"✅ <b>{get_translation(user_id, 'check_again')}</b>\n\n{get_translation(user_id, 'continue_after_admin')}.")
            time.sleep(1)
            self.show_campaign_summary(user_id, data)
        else:
            send_message(user_id, f"""
<b>{get_translation(user_id, 'bot_not_admin')}</b>

<b>{get_translation(user_id, 'follow_steps')}:</b>

1️⃣ {get_translation(user_id, 'enter_channel')} ayarlarına gedin
2️⃣ <b>{get_translation(user_id, 'add_admin')}</b> bölməsinə tıklayın
3️⃣ <b>{get_translation(user_id, 'add_admin')}</b> düyməsinə basın
4️⃣ <b>@GorevYapsamBot</b> yazın
5️⃣ <b>{get_translation(user_id, 'all_permissions')}</b>
6️⃣ Xüsusilə: <b>{get_translation(user_id, 'see_members')}</b>
7️⃣ <b>{get_translation(user_id, 'save')}</b> düyməsinə basın

<b>{get_translation(user_id, 'check_again')}.</b>

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
""")
    
    def show_my_campaigns(self, user_id):
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            WHERE creator_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            send_message(user_id, f"""
<b>📭 {get_translation(user_id, 'no_campaigns')}</b>

💡 <b>{get_translation(user_id, 'create_first_campaign')}</b>

<b>{get_translation(user_id, 'how_create_campaign')}:</b>
1️⃣ {get_translation(user_id, 'main_menu')}'dan <b>{get_translation(user_id, 'create_campaign')}</b>'a tıklayın
2️⃣ {get_translation(user_id, 'campaign_type')}'ni seçin
3️⃣ {get_translation(user_id, 'steps')}'ı takip edin
4️⃣ {get_translation(user_id, 'auto_approval')}
""")
            time.sleep(2)
            self.show_main_menu(user_id)
            return
        
        message = f"<b>📋 {get_translation(user_id, 'my_campaigns')}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        active_count = 0
        pending_count = 0
        completed_count = 0
        
        for i, camp in enumerate(campaigns, 1):
            status = camp['status']
            status_icon = "🟢" if status == 'active' else "🟡" if status == 'pending' else "🔴"
            status_text = get_translation(user_id, 'active') if status == 'active' else get_translation(user_id, 'pending') if status == 'pending' else get_translation(user_id, 'inactive')
            
            if status == 'active': active_count += 1
            elif status == 'pending': pending_count += 1
            else: completed_count += 1
            
            name = camp['name'][:20] + "..." if len(camp['name']) > 20 else camp['name']
            
            message += f"""{status_icon} <b>{name}</b>
├ <b>{get_translation(user_id, 'status')}:</b> {status_text}
├ <b>{get_translation(user_id, 'enter_budget')}:</b> {camp['budget']:.1f}₺
├ <b>{get_translation(user_id, 'task_count')}:</b> {camp['current_participants']}/{camp['max_participants']}
└ <b>ID:</b> <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        message += f"\n<b>{get_translation(user_id, 'summary')}:</b>\n"
        message += f"• 🟢 {get_translation(user_id, 'active')}: {active_count}\n"
        message += f"• 🟡 {get_translation(user_id, 'pending')}: {pending_count}\n"
        message += f"• 🔴 {get_translation(user_id, 'inactive')}: {completed_count}\n"
        message += f"• 📈 {get_translation(user_id, 'total')}: {len(campaigns)}"
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'create_campaign'), 'callback_data': 'create_campaign'},
                {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_deposit_menu(self, user_id):
        self.update_trx_price()
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>{get_translation(user_id, 'deposit')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'price')}:</b> {self.trx_price:.2f}₺
<b>{get_translation(user_id, 'min')}:</b> {MIN_DEPOSIT_TRY}₺
<b>{get_translation(user_id, 'max')}:</b> {MAX_DEPOSIT_TRY}₺

<b>{get_translation(user_id, 'bonus_system')}:</b>
• {get_translation(user_id, 'normal_balance')}: +%{DEPOSIT_BONUS_PERCENT}
• {get_translation(user_id, 'ad_balance')}: +%{ADS_BONUS_PERCENT}

<b>{get_translation(user_id, 'example')}:</b> 100₺ yüklersen:
• {get_translation(user_id, 'normal_balance')}: 135₺ (35₺ bonus)
• {get_translation(user_id, 'ad_balance')}: 120₺ (20₺ bonus)

<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{get_translation(user_id, 'choose_amount')}</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': f'25₺ ({(25/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_25'},
                 {'text': f'50₺ ({(50/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_50'}],
                [{'text': f'100₺ ({(100/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_100'},
                 {'text': f'200₺ ({(200/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_200'}],
                [{'text': get_translation(user_id, 'cancel'), 'callback_data': 'cancel'}, 
                 {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_deposit(self, user_id, amount):
        trx_amount = amount / self.trx_price
        bonus = amount * DEPOSIT_BONUS_PERCENT / 100
        total_receive = amount + bonus
        
        message = f"""
<b>{get_translation(user_id, 'payment_info')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💵 {get_translation(user_id, 'choose_amount')}:</b> {amount:.2f}₺
<b>₿ TRX {get_translation(user_id, 'choose_amount')}:</b> {trx_amount:.4f} TRX
<b>📈 {get_translation(user_id, 'price')}:</b> {self.trx_price:.2f}₺

<b>{get_translation(user_id, 'bonus_system')}:</b> +{bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})
<b>💰 {get_translation(user_id, 'total_balance')}:</b> {total_receive:.2f}₺

<b>🔗 TRX {get_translation(user_id, 'enter_name')}:</b>
<code>{TRX_ADDRESS}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>{get_translation(user_id, 'steps')}</b>

1️⃣ <b>{get_translation(user_id, 'copy_address')}</b> (üstüne tıkla)
2️⃣ <b>{get_translation(user_id, 'send_trx')}</b> {trx_amount:.4f} TRX gönder
3️⃣ <b>{get_translation(user_id, 'send_txid')}</b>
4️⃣ <b>{get_translation(user_id, 'balance_loaded')}</b>

<b>{get_translation(user_id, 'processing_time')}:</b> 2-5 dəqiqə
<b>{get_translation(user_id, 'txid_format')}:</b> 64 karakterlik hex kodu

<code>/cancel</code> {get_translation(user_id, 'cancel_text')}
"""
        
        deposit_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        try:
            self.db.cursor.execute('''
                INSERT INTO deposits (deposit_id, user_id, amount_try, amount_trx, created_at, trx_price, bonus_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (deposit_id, user_id, amount, trx_amount, get_turkey_time().isoformat(), self.trx_price, bonus))
            self.db.conn.commit()
            
            self.set_user_state(user_id, 'waiting_txid', {'deposit_id': deposit_id, 'amount': amount, 'bonus': bonus})
            send_message(user_id, message)
            
        except Exception as e:
            print(f"❌ Depozit hatası: {e}")
            send_message(user_id, f"❌ <b>{get_translation(user_id, 'error_occurred')}: Depozit oluşturulamadı! Lütfen tekrar deneyin.</b>")
    
    def show_balance(self, user_id):
        user = self.db.get_user(user_id)
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>💰 {get_translation(user_id, 'balance')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'user')}:</b> {user.get('name', 'Kullanıcı')}
<b>🆔 ID:</b> {user_id}

<b>{get_translation(user_id, 'normal_balance')}:</b> {user.get('balance', 0):.2f}₺
<b>{get_translation(user_id, 'ad_balance')}:</b> {user.get('ads_balance', 0):.2f}₺
<b>{get_translation(user_id, 'total_balance')}:</b> {user.get('balance', 0) + user.get('ads_balance', 0):.2f}₺

<b>{get_translation(user_id, 'statistics')}:</b>
• {get_translation(user_id, 'total_investment')}: {user.get('total_deposited', 0):.2f}₺
• {get_translation(user_id, 'total_bonus')}: {user.get('total_bonus', 0):.2f}₺
• {get_translation(user_id, 'task_count')}: {user.get('tasks_completed', 0)}
• {get_translation(user_id, 'referral_count')}: {user.get('referrals', 0)}

<b>💡 {get_translation(user_id, 'ad_bonus_note')}</b>
<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation(user_id, 'deposit'), 'callback_data': 'deposit'}],
                [{'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_bot_info(self, user_id):
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>{get_translation(user_id, 'bot_info')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 {get_translation(user_id, 'bot_info')}:</b> Görev Yapsam Bot
<b>🔄 Versiya:</b> v15.0
<b>👑 {get_translation(user_id, 'admin_panel')}:</b> {ADMIN_ID}
<b>📢 {get_translation(user_id, 'channel')}:</b> @{MANDATORY_CHANNEL}
<b>₿ TRX {get_translation(user_id, 'enter_name')}:</b> <code>{TRX_ADDRESS}</code>

<b>{get_translation(user_id, 'features')}:</b>
• TRX ilə balans yükləmə
• Avtomatik kampaniya sistemi
• %{DEPOSIT_BONUS_PERCENT} depozit bonusu
• %{ADS_BONUS_PERCENT} reklam bonusu
• OTOMATİK kampanya aktivləşdirmə
• Referal sistemi

<b>{get_translation(user_id, 'commands')}:</b>
/start - Botu başlat
/menu - {get_translation(user_id, 'main_menu')}
/deposit - {get_translation(user_id, 'deposit')}
/createcampaign - {get_translation(user_id, 'create_campaign')}
/mycampaigns - {get_translation(user_id, 'my_campaigns')}
/balance - {get_translation(user_id, 'balance')}
/botinfo - {get_translation(user_id, 'bot_info')}
/help - {get_translation(user_id, 'help')}
/cancel - {get_translation(user_id, 'cancel')}
/language - Dil seçimi

<b>{get_translation(user_id, 'rules')}:</b>
• Saxta tapşırıq yasaqdır
• Çoxlu hesab yasaqdır
• Spam yasaqdır
• Qaydalara uymayanlar banlanır

<b>{get_translation(user_id, 'support')}:</b>
Suallarınız üçün admin ilə əlaqə saxlayın.

<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>❓ {get_translation(user_id, 'help')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'how_it_works')}</b>
1️⃣ Kanalımıza qoşulun
2️⃣ Balans yükləyin və ya tapşırıq edin
3️⃣ Kampaniya yaradın və ya qoşulun
4️⃣ Pul qazanın!

<b>{get_translation(user_id, 'how_deposit')}</b>
1️⃣ /deposit komandasını istifadə edin
2️⃣ {get_translation(user_id, 'choose_amount')} (25-200₺)
3️⃣ TRX ünvanına TRX göndərin
4️⃣ TXID'yi daxil edin
5️⃣ Balansınız avtomatik yüklənəcək

<b>{get_translation(user_id, 'how_create_campaign')}</b>
1️⃣ /createcampaign komandasını istifadə edin
2️⃣ {get_translation(user_id, 'campaign_type')}'ni seçin
3️⃣ {get_translation(user_id, 'steps')}'ı izləyin
4️⃣ {get_translation(user_id, 'auto_approval')}

<b>{get_translation(user_id, 'how_do_task')}</b>
1️⃣ Aktiv kampaniyaları görün
2️⃣ Tapşırığı tamamlayın
3️⃣ Sübut göndərin
4️⃣ Təsdiqi gözləyin
5️⃣ Mükafatı alın

<b>{get_translation(user_id, 'referral_system')}</b>
• Hər referal: 1₺
• Referal linkiniz: /start ref_XXXXXXXX
• Dostlarınız kanala qoşulmazsa bonus ala bilməzsiniz

<b>{get_translation(user_id, 'cancel_system')}</b>
• Hər addımda <code>/cancel</code> yaza bilərsiniz
• Hər menyuda {get_translation(user_id, 'cancel')} düyməsi var
• Səhvən başladılan əməliyyatları dayandıra bilərsiniz

<b>{get_translation(user_id, 'important_warnings')}</b>
• Saxta tapşırıq etməyin
• Çoxlu hesab açmayın
• Spam etməyin
• Qaydalara əməl edin

<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'deposit'), 'callback_data': 'deposit'},
                {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, f"<b>{get_translation(user_id, 'admin_no_permission')}</b>")
            return
        
        # İstatistikler
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'pending'")
        pending_campaigns = self.db.cursor.fetchone()[0]
        
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>{get_translation(user_id, 'admin_panel_title')} v15.0</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{get_translation(user_id, 'statistics_title')}</b>
• 👥 {get_translation(user_id, 'total_users')}: <b>{total_users}</b>
• 💰 {get_translation(user_id, 'total_balance')}: {total_balance:.2f}₺
• 📢 {get_translation(user_id, 'active_campaigns')}: {active_campaigns}
• ⏳ {get_translation(user_id, 'pending_approval')}: {pending_campaigns} (OTOMATİK)
• ₿ {get_translation(user_id, 'price')}: {self.trx_price:.2f}₺
• {get_translation(user_id, 'current_time')}: {current_time} 🇹🇷

<b>{get_translation(user_id, 'admin_tools')}</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation(user_id, 'user_stats'), 'callback_data': 'admin_stats'},
                 {'text': get_translation(user_id, 'campaign_stats'), 'callback_data': 'admin_campaigns'}],
                [{'text': get_translation(user_id, 'user_management'), 'callback_data': 'admin_users'},
                 {'text': get_translation(user_id, 'deposit_management'), 'callback_data': 'admin_deposits'}],
                [{'text': get_translation(user_id, 'broadcast'), 'callback_data': 'admin_broadcast'},
                 {'text': get_translation(user_id, 'settings'), 'callback_data': 'admin_settings'}],
                [{'text': get_translation(user_id, 'cancel'), 'callback_data': 'cancel'}, 
                 {'text': get_translation(user_id, 'back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_stats(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, f"<b>{get_translation(user_id, 'admin_no_permission')}</b>")
            return
        
        # Detaylı istatistikler
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
        new_users_today = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT SUM(total_deposited) FROM users")
        total_deposited = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT SUM(total_bonus) FROM users")
        total_bonus = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE DATE(created_at) = DATE('now')")
        new_campaigns_today = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM deposits WHERE status = 'pending'")
        pending_deposits = self.db.cursor.fetchone()[0]
        
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>📊 {get_translation(user_id, 'statistics_title')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👥 {get_translation(user_id, 'total_users')}:</b> {total_users}
<b>📈 Bugünkü yeni kullanıcılar:</b> {new_users_today}

<b>💰 {get_translation(user_id, 'total_balance')}:</b> {total_balance:.2f}₺
<b>💳 Toplam yatırım:</b> {total_deposited:.2f}₺
<b>🎁 Toplam bonus:</b> {total_bonus:.2f}₺

<b>📢 Toplam kampanyalar:</b> {total_campaigns}
<b>🟢 Aktif kampanyalar:</b> {active_campaigns}
<b>📈 Bugünkü yeni kampanyalar:</b> {new_campaigns_today}

<b>⏳ Bekleyen depozitler:</b> {pending_deposits}

<b>{get_translation(user_id, 'time')}:</b> {current_time} 🇹🇷
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>💡 Sistem OTOMATİK çalışıyor:</b>
• Kampanyalar otomatik aktif
• Admin onayı gerekmez
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'back'), 'callback_data': 'admin_panel'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def approve_campaign(self, campaign_id):
        try:
            # Kampanyayı bul
            self.db.cursor.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,))
            campaign = self.db.cursor.fetchone()
            
            if not campaign:
                send_message(ADMIN_ID, f"❌ <b>Kampanya bulunamadı:</b> {campaign_id}")
                return
            
            # Kampanyayı aktif et (OTOMATİK OLDUĞU İÇİN ARTIK GEREK YOK)
            # self.db.cursor.execute("UPDATE campaigns SET status = 'active' WHERE campaign_id = ?", (campaign_id,))
            # self.db.conn.commit()
            
            # Oluşturucuya bildir
            creator_id = campaign['creator_id']
            send_message(creator_id, f"""
<b>{get_translation(creator_id, 'campaign_approved')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 {get_translation(creator_id, 'enter_name')}:</b> {campaign['name']}
<b>{get_translation(creator_id, 'campaign_id')}:</b> <code>{campaign_id}</code>
<b>💰 {get_translation(creator_id, 'enter_budget')}:</b> {campaign['budget']:.2f}₺
<b>{get_translation(creator_id, 'max_participants')}:</b> {campaign['max_participants']}

✅ <b>{get_translation(creator_id, 'campaign_active')}</b>
📢 <b>{get_translation(creator_id, 'users_can_join')}</b>

💰 <b>{get_translation(creator_id, 'earnings_per_participation')}:</b> {campaign['price_per_task']}₺
⏳ <b>{get_translation(creator_id, 'duration_until_budget')}</b>
""")
            
            # Admin'e bildir
            send_message(ADMIN_ID, f"ℹ️ <b>BİLGİ:</b> Kampanyalar artık OTOMATİK aktif oluyor.\n\nKampanya: {campaign_id}")
            
        except Exception as e:
            print(f"❌ Onay hatası: {e}")
            send_message(ADMIN_ID, f"❌ <b>Kampanya işlem hatası:</b> {campaign_id}")
    
    def reject_campaign(self, campaign_id):
        try:
            # Kampanyayı bul
            self.db.cursor.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,))
            campaign = self.db.cursor.fetchone()
            
            if not campaign:
                send_message(ADMIN_ID, f"❌ <b>Kampanya bulunamadı:</b> {campaign_id}")
                return
            
            # Bakiye iadesi
            creator_id = campaign['creator_id']
            budget = campaign['budget']
            
            user = self.db.get_user(creator_id)
            new_balance = user.get('balance', 0) + budget
            self.db.update_user(creator_id, {'balance': new_balance})
            
            # Kampanyayı reddet
            self.db.cursor.execute("UPDATE campaigns SET status = 'rejected' WHERE campaign_id = ?", (campaign_id,))
            self.db.conn.commit()
            
            # Oluşturucuya bildir
            send_message(creator_id, f"""
<b>{get_translation(creator_id, 'campaign_rejected')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 {get_translation(creator_id, 'enter_name')}:</b> {campaign['name']}
<b>{get_translation(creator_id, 'campaign_id')}:</b> <code>{campaign_id}</code>
<b>💰 {get_translation(creator_id, 'enter_budget')}:</b> {budget:.2f}₺

<b>{get_translation(creator_id, 'reason_for_rejection')}:</b>
• {get_translation(creator_id, 'bot_not_admin_reason')}
• {get_translation(creator_id, 'not_following_rules')}
• {get_translation(creator_id, 'missing_info')}
• {get_translation(creator_id, 'suspicious_content')}

💰 <b>{get_translation(creator_id, 'balance_refunded')}:</b> {budget:.2f}₺
💡 <b>{get_translation(creator_id, 'check_rules_try_again')}</b>
""")
            
            # Admin'e bildir
            send_message(ADMIN_ID, f"❌ <b>Kampanya reddedildi:</b> {campaign_id}\n\n{budget:.2f}₺ kullanıcıya iade edildi.")
            
        except Exception as e:
            print(f"❌ Reddetme hatası: {e}")
            send_message(ADMIN_ID, f"❌ <b>Kampanya reddedilemedi:</b> {campaign_id}")

    def show_admin_campaigns(self, user_id):
        """Admin için kampanya listesi"""
        if user_id != ADMIN_ID:
            send_message(user_id, f"<b>{get_translation(user_id, 'admin_no_permission')}</b>")
            return
        
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            ORDER BY created_at DESC 
            LIMIT 20
        ''')
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            send_message(user_id, "<b>📭 Hiç kampanya bulunamadı!</b>")
            return
        
        message = "<b>📢 TÜM KAMPANYALAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, camp in enumerate(campaigns, 1):
            status = camp['status']
            status_icon = "🟢" if status == 'active' else "🟡" if status == 'pending' else "🔴"
            
            message += f"""{status_icon} <b>{camp['name'][:20]}</b>
├ <b>ID:</b> <code>{camp['campaign_id']}</code>
├ <b>Durum:</b> {status}
├ <b>Oluşturan:</b> {camp['creator_name']}
├ <b>Bütçe:</b> {camp['budget']:.1f}₺
└ <b>Katılım:</b> {camp['current_participants']}/{camp['max_participants']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        message += f"\n<b>Toplam: {len(campaigns)} kampanya</b>"
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'back'), 'callback_data': 'admin_panel'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_users(self, user_id):
        """Admin için kullanıcı listesi"""
        if user_id != ADMIN_ID:
            send_message(user_id, f"<b>{get_translation(user_id, 'admin_no_permission')}</b>")
            return
        
        self.db.cursor.execute('''
            SELECT * FROM users 
            ORDER BY created_at DESC 
            LIMIT 20
        ''')
        users = self.db.cursor.fetchall()
        
        if not users:
            send_message(user_id, "<b>👥 Hiç kullanıcı bulunamadı!</b>")
            return
        
        message = "<b>👥 TÜM KULLANICILAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, usr in enumerate(users, 1):
            message += f"""👤 <b>{usr['name'][:15]}</b>
├ <b>ID:</b> <code>{usr['user_id']}</code>
├ <b>Bakiye:</b> {usr['balance']:.1f}₺
├ <b>Referans:</b> {usr['referrals']}
└ <b>Kayıt:</b> {usr['created_at'][:10]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        message += f"\n<b>Toplam: {len(users)} kullanıcı</b>"
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation(user_id, 'back'), 'callback_data': 'admin_panel'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def start_broadcast(self, user_id):
        """Yayın başlat"""
        if user_id != ADMIN_ID:
            send_message(user_id, f"<b>{get_translation(user_id, 'admin_no_permission')}</b>")
            return
        
        send_message(user_id, "📣 <b>Yayın sistemi</b>\n\nBu özellik henüz tamamlanmadı. Yakında eklenecek!")
    
    # Diğer admin fonksiyonları için placeholder'lar
    def show_admin_deposits(self, user_id):
        send_message(user_id, "💰 <b>Depozit Yönetimi</b>\n\nBu özellik henüz tamamlanmadı. Yakında eklenecek!")
    
    def show_admin_settings(self, user_id):
        send_message(user_id, "⚙️ <b>Ayarlar</b>\n\nBu özellik henüz tamamlanmadı. Yakında eklenecek!")

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v15.0                      ║
    ║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAM BAKİYESİ + BONUS SİSTEM║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    current_time = get_turkey_time().strftime('%H:%M')
    
    print("✅ Bot başarıyla başlatıldı!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    print(f"₿ TRX Adresi: {TRX_ADDRESS}")
    print(f"💰 Min Depozit: {MIN_DEPOSIT_TRY}₺, Max: {MAX_DEPOSIT_TRY}₺")
    print(f"🎁 Bonuslar: %{DEPOSIT_BONUS_PERCENT} Normal, %{ADS_BONUS_PERCENT} Reklam")
    print(f"⏰ Türkiye Saati: {current_time}")
    print("🔄 İptal sistemi aktif: /cancel komutu her yerde çalışır")
    print("🤖 Forward sistemi: HERHANGİ BİR BOT mesajı kabul edilir")
    print("🌐 Çoklu dil desteği: Türkçe ve Azerbaycan Dili")
    print("⚡ OTOMATİK sistem: Kampanyalar otomatik aktif olur")
    print("🔗 Telegram'da /start yazarak test edin")
    
    return app

if __name__ == "__main__":
    if TOKEN:
        main()
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ TELEGRAM_BOT_TOKEN gerekli!")

def create_app():
    bot = BotSystem()
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    return app
