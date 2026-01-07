import os
import time
import json
import requests
from datetime import datetime, timedelta
import threading
import sqlite3
from flask import Flask, jsonify
import hashlib
import pytz
import random

# Telegram Ayarları
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "7904032877")
MANDATORY_CHANNEL = os.environ.get("MANDATORY_CHANNEL", "GY_Refim")

if not TOKEN:
    raise ValueError("Bot token gerekli!")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Türkiye saati için
TURKEY_TZ = pytz.timezone('Europe/Istanbul')

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
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v16.0"})

def get_turkey_time():
    """Türkiye saatini döndür"""
    return datetime.now(TURKEY_TZ)

# Database
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
                language TEXT DEFAULT 'tr',
                notification_enabled INTEGER DEFAULT 1,
                last_active TEXT,
                referral_code TEXT,
                referred_by TEXT
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
        
        # Bot istatistikleri
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_users INTEGER DEFAULT 0,
                total_deposits INTEGER DEFAULT 0,
                total_campaigns INTEGER DEFAULT 0,
                total_tasks_completed INTEGER DEFAULT 0,
                total_balance REAL DEFAULT 0.0,
                last_updated TEXT
            )
        ''')
        
        self.conn.commit()
        print("✅ Veritabanı hazır")
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            now = get_turkey_time().isoformat()
            referral_code = f"ref_{user_id[-8:]}"
            self.cursor.execute('''
                INSERT INTO users (user_id, name, balance, ads_balance, created_at, language, last_active, referral_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, '', 0.0, 0.0, now, 'tr', now, referral_code))
            self.conn.commit()
            
            # Bot istatistiklerini güncelle
            self.update_bot_stats('new_user')
            
            # Admin'e yeni kullanıcı bildirimi
            self.send_new_user_notification(user_id)
            
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        
        return dict(user) if user else {}
    
    def send_new_user_notification(self, new_user_id):
        """Admin'e yeni kullanıcı bildirimi gönder"""
        try:
            new_user = self.get_user(new_user_id)
            # Toplam kullanıcı sayısını al
            self.cursor.execute("SELECT COUNT(*) as total FROM users")
            total_result = self.cursor.fetchone()
            total_users = total_result['total'] if total_result else 0
            
            # Referans ile mi normal giriş ile mi kaydolduğunu kontrol et
            referred_by = new_user.get('referred_by', '')
            if referred_by:
                referral_type = f"Referans ile (Referans ID: {referred_by})"
            else:
                referral_type = "Normal giriş"
            
            send_message(ADMIN_ID, f"""
👤 <b>YENİ KULLANICI KAYDOLDU!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 <b>Kullanıcı Adı:</b> {new_user.get('name', 'Yok')}
🆔 <b>User ID:</b> <code>{new_user_id}</code>
📊 <b>Kayıt Türü:</b> {referral_type}

📈 <b>Toplam Kullanıcı Sayısı:</b> {total_users}
⏰ <b>Kayıt Zamanı:</b> {new_user.get('created_at', 'Bilinmiyor')[:19]}
""")
        except Exception as e:
            print(f"❌ Admin bildirimi hatası: {e}")
    
    def update_user(self, user_id, data):
        if not data: return False
        data['last_active'] = get_turkey_time().isoformat()
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(user_id)
        query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
        self.cursor.execute(query, values)
        self.conn.commit()
        return True
    
    def add_balance(self, user_id, amount, bonus_percent=0, source="system"):
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
        
        # Bakiye eklendi bildirimi
        if amount > 0:
            source_text = "sistem" if source == "system" else "referans"
            message = f"""
💰 <b>BAKİYE EKLENDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>+{total:.2f}₺ bakiyenize eklendi!</b>
• Kaynak: {source_text}
• Tutar: {amount:.2f}₺
• Bonus: {bonus:.2f}₺ (%{bonus_percent})
• Yeni Bakiye: {new_balance:.2f}₺

💡 <b>Hemen görev yapmaya başlayabilirsiniz!</b>
"""
            send_message(user_id, message)
        
        return True
    
    def update_bot_stats(self, stat_type):
        """Bot istatistiklerini güncelle"""
        now = get_turkey_time().isoformat()
        
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM deposits WHERE status = 'completed'")
        total_deposits = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT SUM(tasks_completed) FROM users")
        total_tasks = self.cursor.fetchone()[0] or 0
        
        self.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.cursor.fetchone()[0] or 0.0
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO bot_stats (stat_id, total_users, total_deposits, total_campaigns, 
            total_tasks_completed, total_balance, last_updated)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        ''', (total_users, total_deposits, total_campaigns, total_tasks, total_balance, now))
        self.conn.commit()

# Telegram Fonksiyonları
def send_message(chat_id, text, markup=None, parse_mode='HTML'):
    url = BASE_URL + "sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if markup: data['reply_markup'] = json.dumps(markup)
    try: 
        response = requests.post(url, json=data, timeout=10).json()
        return response
    except Exception as e:
        print(f"❌ Mesaj gönderme hatası: {e}")
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
    if text: data['text'] = text
    if show_alert: data['show_alert'] = True
    try: 
        response = requests.post(url, json=data, timeout=5)
        return response
    except: 
        return None

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

# Dil sistemi
translations = {
    'tr': {
        'welcome': '👋 Hoş Geldin',
        'balance': '💰 Bakiye',
        'tasks': '🎯 Görevler',
        'referrals': '👥 Referans',
        'deposit': '💳 Yükle',
        'withdraw': '🏧 Çek',
        'profile': '👤 Profil',
        'help': '❓ Yardım',
        'admin': '👑 Admin',
        'back': '🔙 Geri',
        'cancel': '❌ İptal',
        'menu': '📋 Menü',
        'create_campaign': '📢 Kampanya',
        'my_campaigns': '📋 Kampanyalarım',
        'bot_info': '🤖 Bot',
        'notifications': '🔔 Bildirim',
        'referral_link': '🔗 Referans Linki',
        'copy_link': '📋 Linki Kopyala',
        'share_link': '📤 Paylaş',
        'referral_earnings': '💰 Kazanç',
        'new_user': '🆕 Yeni Kullanıcı',
        'total_users': '👥 Toplam',
        'active_campaigns': '📢 Aktif',
        'pending_approval': '⏳ Bekleyen',
        'user_stats': '📊 İstatistik',
        'campaign_stats': '📈 Kampanyalar',
        'user_management': '👥 Kullanıcılar',
        'deposit_management': '💳 Depozitler',
        'broadcast': '📢 Duyuru',
        'settings': '⚙️ Ayarlar'
    }
}

def get_translation(key):
    """Çeviri döndür"""
    return translations['tr'].get(key, key)

# Bildirim Sistemi
class NotificationSystem:
    def __init__(self, bot_system):
        self.bot_system = bot_system
        self.db = bot_system.db
    
    def send_referral_notification(self, referrer_id, referral_id):
        """Referans bildirimi gönder"""
        try:
            referrer = self.db.get_user(referrer_id)
            referral = self.db.get_user(referral_id)
            
            # Referans sahibine bildirim
            message = f"""
🎉 <b>REFERANS KAZANCI!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Yeni referansınız:</b> {referral.get('name', 'Kullanıcı')}
💰 <b>Kazandınız:</b> 1.00₺
📊 <b>Toplam referans:</b> {referrer.get('referrals', 0)}
💵 <b>Yeni bakiye:</b> {referrer.get('balance', 0):.2f}₺

🔗 <b>Referans linkinizle daha çok kişi davet edin!</b>
"""
            send_message(referrer_id, message)
            
        except Exception as e:
            print(f"❌ Referans bildirimi hatası: {e}")

# Bot Sistemi
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.notification_system = NotificationSystem(self)
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
                elif text == '/referral':
                    self.show_referral_menu(user_id)
                elif text == '/deposit':
                    self.show_deposit_menu(user_id)
        
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def process_callback(self, callback):
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # Önce callback'i cevapla
            answer_callback(callback_id)
            
            # Temel navigasyon
            if data == 'menu':
                self.show_main_menu(user_id)
            elif data == 'back':
                self.show_main_menu(user_id)
            elif data == 'cancel':
                self.clear_user_state(user_id)
                self.show_main_menu(user_id)
            
            # Ana menü butonları
            elif data == 'tasks':
                self.show_active_tasks(user_id)
            elif data == 'create_campaign':
                self.start_campaign_type_selection(user_id)
            elif data == 'my_campaigns':
                self.show_my_campaigns(user_id)
            elif data == 'deposit':
                self.show_deposit_menu(user_id)
            elif data == 'profile':
                self.show_profile(user_id)
            elif data == 'referral':
                self.show_referral_menu(user_id)
            elif data == 'bot_info':
                self.show_bot_info(user_id)
            elif data == 'help':
                self.show_help(user_id)
            elif data == 'notifications':
                self.toggle_notifications(user_id)
            
            # Admin butonları
            elif data == 'admin_panel':
                self.show_admin_panel(user_id)
            elif data == 'admin_stats':
                self.show_admin_stats(user_id)
            elif data == 'admin_campaigns':
                self.show_admin_campaigns(user_id)
            elif data == 'admin_users':
                self.show_admin_users(user_id)
            elif data == 'admin_deposits':
                self.show_admin_deposits(user_id)
            elif data == 'admin_broadcast':
                self.show_admin_broadcast(user_id)
            elif data == 'admin_settings':
                self.show_admin_settings(user_id)
            
            # Kampanya oluşturma
            elif data.startswith('camp_type_'):
                task_type = data.replace('camp_type_', '')
                self.start_campaign_creation(user_id, task_type)
            
            # Depozit işlemleri
            elif data.startswith('deposit_'):
                if data == 'deposit_menu':
                    self.show_deposit_menu(user_id)
                elif data.startswith('deposit_amount_'):
                    amount = float(data.replace('deposit_amount_', ''))
                    self.start_deposit(user_id, amount)
            
            # Referans işlemleri
            elif data == 'referral_copy':
                self.copy_referral_link(user_id)
            elif data == 'referral_share':
                self.share_referral_link(user_id)
            
            # Kanal kontrolü
            elif data == 'joined':
                if get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
                    self.db.update_user(user_id, {'in_channel': 1})
                    self.show_main_menu(user_id)
                else:
                    send_message(user_id, "❌ Hala kanala katılmadınız!")
        
        except Exception as e:
            print(f"❌ Callback hatası: {e}")
            send_message(user_id, "❌ Bir hata oluştu!")
    
    def handle_start(self, user_id, text):
        # Kanal kontrolü
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 Kanala Katıl', 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': '✅ Katıldım', 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, f"""
🤖 <b>Görev Yapsam Bot'a Hoş Geldiniz!</b>

📢 <b>Botu kullanmak için:</b>
1️⃣ Önce kanala katılın: @{MANDATORY_CHANNEL}
2️⃣ Katıldıktan sonra "Katıldım" butonuna basın

💡 <b>Özellikler:</b>
• Görev yap para kazan
• Kampanya oluştur
• TRX ile bakiye yükle
• Referans sistemi
""", markup)
            return
        
        user = self.db.get_user(user_id)
        
        # Hoşgeldin bonusu
        if not user.get('welcome_bonus'):
            self.db.add_balance(user_id, 2.0, 0, "welcome_bonus")
            self.db.update_user(user_id, {'welcome_bonus': 1, 'in_channel': 1})
        
        # Referans kontrolü
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith('ref_'):
                referrer_id = parts[1].replace('ref_', '')
                if referrer_id and referrer_id != user_id:
                    referrer = self.db.get_user(referrer_id)
                    if referrer:
                        # Referans ile kaydolduğunu işaretle
                        self.db.update_user(user_id, {'referred_by': referrer_id})
                        
                        # Referans sahibine bonus ekle
                        self.db.add_balance(referrer_id, 1.0, 0, "referral")
                        self.db.update_user(referrer_id, {
                            'referrals': referrer.get('referrals', 0) + 1,
                            'ref_earned': referrer.get('ref_earned', 0) + 1.0
                        })
                        
                        # Referans bildirimi gönder
                        self.notification_system.send_referral_notification(referrer_id, user_id)
                        
                        # Yeni kullanıcıya mesaj
                        send_message(user_id, "🎉 Referans linki ile kaydoldunuz! Davet eden kullanıcıya 1₺ bonus yüklendi.")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>{get_translation('welcome')} {user.get('name', 'Kullanıcı')}!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Bakiye:</b> {user.get('balance', 0):.2f}₺
🎯 <b>Görev:</b> {user.get('tasks_completed', 0)}
👥 <b>Referans:</b> {user.get('referrals', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 ANA MENÜ</b>
"""
        
        # Temel butonlar
        buttons = [
            [{'text': get_translation('tasks'), 'callback_data': 'tasks'}],
            [{'text': get_translation('create_campaign'), 'callback_data': 'create_campaign'},
             {'text': get_translation('my_campaigns'), 'callback_data': 'my_campaigns'}],
            [{'text': get_translation('deposit'), 'callback_data': 'deposit'},
             {'text': get_translation('referral'), 'callback_data': 'referral'}],
            [{'text': get_translation('profile'), 'callback_data': 'profile'},
             {'text': get_translation('bot_info'), 'callback_data': 'bot_info'}],
            [{'text': '🔔', 'callback_data': 'notifications'},
             {'text': get_translation('help'), 'callback_data': 'help'}]
        ]
        
        # Admin butonu
        if user_id == ADMIN_ID:
            buttons.append([{'text': get_translation('admin'), 'callback_data': 'admin_panel'}])
        
        markup = {'inline_keyboard': buttons}
        send_message(user_id, message, markup)
    
    def show_referral_menu(self, user_id):
        user = self.db.get_user(user_id)
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = f"""
<b>{get_translation('referrals')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 <b>Toplam Referans:</b> {user.get('referrals', 0)}
💰 <b>Referans Kazancı:</b> {user.get('ref_earned', 0):.2f}₺

🔗 <b>Referans Linkiniz:</b>
<code>{referral_link}</code>

💡 <b>Her referans için 1₺ kazanırsınız!</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '📋 Linki Kopyala', 'callback_data': 'referral_copy'}],
                [{'text': '📤 Arkadaşlarını Paylaş', 'callback_data': 'referral_share'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def copy_referral_link(self, user_id):
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        send_message(user_id, f"🔗 <b>Referans Linkiniz:</b>\n\n<code>{referral_link}</code>\n\n📋 Yukarıdaki linki kopyalayıp paylaşabilirsiniz.")
    
    def share_referral_link(self, user_id):
        user = self.db.get_user(user_id)
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = f"""
🎉 <b>Görev Yapsam Bot'ta Para Kazan!</b>

🤖 Arkadaşlarım, bu bot ile görev yaparak para kazanabilirsiniz!
💰 Her görev için ödeme alın
📢 Kendi kampanyalarınızı oluşturun
👥 Referans sistemi ile ekstra kazanın

🔗 <b>Benim referans linkim:</b>
{referral_link}

💡 <b>Linke tıklayarak kaydolun ve hemen 2₺ bonus alın!</b>
"""
        
        # Paylaşım butonları
        markup = {
            'inline_keyboard': [[
                {'text': '📤 Telegramda Paylaş', 'url': f'https://t.me/share/url?url={referral_link}&text=Görev+Yapsam+Bot+ile+para+kazan!'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_active_tasks(self, user_id):
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            WHERE status = 'active' AND remaining_budget > 0
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            message = "📭 <b>Şu anda aktif görev bulunmuyor.</b>"
        else:
            message = "<b>🎯 AKTİF GÖREVLER</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                message += f"""📢 <b>{camp['name'][:30]}</b>
• Ödül: {camp['price_per_task']}₺
• Kalan: {int(camp['remaining_budget'] / camp['price_per_task'])} kişi
• ID: <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'menu'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>{get_translation('profile')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>İsim:</b> {user.get('name', 'Kullanıcı')}
🆔 <b>ID:</b> <code>{user_id}</code>

💰 <b>Bakiye:</b> {user.get('balance', 0):.2f}₺
🎯 <b>Görev:</b> {user.get('tasks_completed', 0)}
👥 <b>Referans:</b> {user.get('referrals', 0)}

📈 <b>İstatistik:</b>
• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺
• Toplam Bonus: {user.get('total_bonus', 0):.2f}₺
• Referans Kazancı: {user.get('ref_earned', 0):.2f}₺
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': get_translation('deposit'), 'callback_data': 'deposit'},
                 {'text': get_translation('referral'), 'callback_data': 'referral'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        send_message(user_id, message, markup)
    
    def show_deposit_menu(self, user_id):
        self.update_trx_price()
        
        message = f"""
<b>{get_translation('deposit')}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>TRX Fiyatı:</b> {self.trx_price:.2f}₺
🎁 <b>Bonus:</b> %{DEPOSIT_BONUS_PERCENT}

👇 <b>Tutar Seçin:</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': f'25₺ ({(25/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_25'},
                 {'text': f'50₺ ({(50/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_50'}],
                [{'text': f'100₺ ({(100/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_100'},
                 {'text': f'200₺ ({(200/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_200'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        send_message(user_id, message, markup)
    
    def start_deposit(self, user_id, amount):
        trx_amount = amount / self.trx_price
        bonus = amount * DEPOSIT_BONUS_PERCENT / 100
        
        message = f"""
<b>{get_translation('deposit')} Bilgileri</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💵 <b>Tutar:</b> {amount:.2f}₺
₿ <b>TRX Tutarı:</b> {trx_amount:.4f} TRX
🎁 <b>Bonus:</b> {bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})
💰 <b>Toplam:</b> {amount + bonus:.2f}₺

🔗 <b>TRX Adresi:</b>
<code>{TRX_ADDRESS}</code>

📝 <b>Adımlar:</b>
1. Yukarıdaki adrese {trx_amount:.4f} TRX gönderin
2. İşlem tamamlandığında TXID'yi bota gönderin
3. Bakiyeniz otomatik yüklenecek
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
            send_message(user_id, "❌ Depozit oluşturulamadı!")
    
    def show_bot_info(self, user_id):
        message = """
<b>🤖 BOT BİLGİSİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📢 <b>Kanal:</b> @GY_Refim
💰 <b>TRX Adresi:</b>
<code>TVJKGbdBQrbvQzq6WZhb3kaGa3LYgVrMSK</code>

🎁 <b>Bonus Sistemi:</b>
• Depozit: %35 bonus
• Referans: 1₺ her davet

⚡ <b>Özellikler:</b>
• Görev yap para kazan
• Kampanya oluştur
• TRX ile ödeme
• Referans sistemi

📞 <b>Destek:</b>
Admin ile iletişime geçin.
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'menu'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        message = """
<b>❓ YARDIM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 Bot Nasıl Çalışır?</b>
1. Kanala katılın
2. Bakiye yükleyin veya görev yapın
3. Para kazanın!

<b>💰 Bakiye Nasıl Yüklenir?</b>
1. /deposit komutunu kullanın
2. Tutar seçin
3. TRX gönderin
4. TXID'yi girin

<b>📢 Kampanya Nasıl Oluşturulur?</b>
1. "Kampanya" butonuna basın
2. Tip seçin
3. Bilgileri doldurun
4. Onaylayın

<b>👥 Referans Sistemi</b>
• Her davet: 1₺ bonus
• Referans linkinizi paylaşın
• Arkadaşlarınızı davet edin
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'menu'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def toggle_notifications(self, user_id):
        user = self.db.get_user(user_id)
        current = user.get('notification_enabled', 1)
        new_status = 0 if current == 1 else 1
        
        self.db.update_user(user_id, {'notification_enabled': new_status})
        
        if new_status == 1:
            message = "🔔 <b>Bildirimler açıldı!</b>"
        else:
            message = "🔕 <b>Bildirimler kapatıldı!</b>"
        
        send_message(user_id, message)
        self.show_main_menu(user_id)
    
    def show_admin_panel(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, "❌ Yetkiniz yok!")
            return
        
        # İstatistikler
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = self.db.cursor.fetchone()[0]
        
        message = f"""
<b>👑 ADMIN PANELİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 <b>İstatistikler</b>
• 👥 Kullanıcı: {total_users}
• 💰 Toplam Bakiye: {total_balance:.2f}₺
• 📢 Aktif Kampanya: {active_campaigns}

🛠️ <b>Araçlar</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '📊 İstatistik', 'callback_data': 'admin_stats'},
                 {'text': '📢 Kampanyalar', 'callback_data': 'admin_campaigns'}],
                [{'text': '👥 Kullanıcılar', 'callback_data': 'admin_users'},
                 {'text': '💰 Depozitler', 'callback_data': 'admin_deposits'}],
                [{'text': '📣 Duyuru', 'callback_data': 'admin_broadcast'},
                 {'text': '⚙️ Ayarlar', 'callback_data': 'admin_settings'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_stats(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute("SELECT * FROM bot_stats WHERE stat_id = 1")
        stats = self.db.cursor.fetchone()
        
        if stats:
            total_users = stats['total_users']
            total_deposits = stats['total_deposits']
            total_campaigns = stats['total_campaigns']
            total_tasks = stats['total_tasks_completed']
            total_balance = stats['total_balance']
        else:
            total_users = total_deposits = total_campaigns = total_tasks = 0
            total_balance = 0.0
        
        message = f"""
<b>📊 DETAYLI İSTATİSTİKLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 <b>Toplam Kullanıcı:</b> {total_users}
💰 <b>Toplam Bakiye:</b> {total_balance:.2f}₺

💳 <b>Toplam Depozit:</b> {total_deposits}
📢 <b>Toplam Kampanya:</b> {total_campaigns}
🎯 <b>Toplam Görev:</b> {total_tasks}

⏰ <b>Sistem Durumu:</b> ✅ ÇALIŞIYOR
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_campaigns(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            message = "📭 <b>Hiç kampanya bulunamadı!</b>"
        else:
            message = "<b>📢 TÜM KAMPANYALAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""{status} <b>{camp['name'][:20]}</b>
• Durum: {camp['status']}
• Bütçe: {camp['budget']:.1f}₺
• Katılım: {camp['current_participants']}/{camp['max_participants']}
• ID: <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_users(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute('''
            SELECT * FROM users 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        users = self.db.cursor.fetchall()
        
        if not users:
            message = "👥 <b>Hiç kullanıcı bulunamadı!</b>"
        else:
            message = "<b>👥 TÜM KULLANICILAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for usr in users:
                referred = "✅" if usr['referred_by'] else "❌"
                message += f"""👤 <b>{usr['name'][:15]}</b>
• ID: <code>{usr['user_id']}</code>
• Bakiye: {usr['balance']:.1f}₺
• Referans: {usr['referrals']} {referred}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_deposits(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute('''
            SELECT * FROM deposits 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        deposits = self.db.cursor.fetchall()
        
        if not deposits:
            message = "💰 <b>Hiç depozit bulunamadı!</b>"
        else:
            message = "<b>💰 TÜM DEPOZİTLER</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for dep in deposits:
                status = "✅" if dep['status'] == 'completed' else "⏳" if dep['status'] == 'pending' else "❌"
                message += f"""{status} <b>Depozit #{dep['deposit_id'][:8]}</b>
• Kullanıcı: <code>{dep['user_id']}</code>
• Tutar: {dep['amount_try']:.2f}₺
• Durum: {dep['status']}
• Zaman: {dep['created_at'][:16]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_broadcast(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        message = """
<b>📣 TOPLU MESAJ GÖNDER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Bu özellik henüz tamamlanmadı.</b>

💡 <b>Yakında Eklenecek:</b>
• Tüm kullanıcılara mesaj
• Filtreli gönderim
• Zamanlı gönderim
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_settings(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        message = """
<b>⚙️ AYARLAR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Bu özellik henüz tamamlanmadı.</b>

💡 <b>Yakında Eklenecek:</b>
• Bot ayarları
• Komut yönetimi
• Sistem ayarları
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': get_translation('back'), 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        message = """
<b>📢 KAMPANYA OLUŞTUR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 <b>Kampanya Tipi Seçin:</b>

🤖 <b>Bot Kampanyası</b>
• Görev: Bot mesajı
• Ödül: 2.5₺
• Otomatik aktif

📢 <b>Kanal Kampanyası</b>
• Görev: Kanala katılma
• Ödül: 1.5₺
• Bot admin olmalı

👥 <b>Grup Kampanyası</b>
• Görev: Gruba katılma
• Ödül: 1₺
• Bot admin olmalı
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '🤖 Bot Kampanyası', 'callback_data': 'camp_type_bot'}],
                [{'text': '📢 Kanal Kampanyası', 'callback_data': 'camp_type_channel'}],
                [{'text': '👥 Grup Kampanyası', 'callback_data': 'camp_type_group'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        # Basit kampanya oluşturma - geliştirilecek
        send_message(user_id, f"📢 <b>Kampanya oluşturma özelliği geliştiriliyor...</b>\n\nSeçilen tip: {task_type}")
        time.sleep(2)
        self.show_main_menu(user_id)
    
    def show_my_campaigns(self, user_id):
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            WHERE creator_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (user_id,))
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            message = "📭 <b>Henüz kampanyanız yok.</b>"
        else:
            message = "<b>📋 KAMPANYALARIM</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""{status} <b>{camp['name'][:20]}</b>
• Durum: {camp['status']}
• Bütçe: {camp['budget']:.1f}₺
• Katılım: {camp['current_participants']}/{camp['max_participants']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '📢 Yeni Kampanya', 'callback_data': 'create_campaign'}],
                [{'text': get_translation('back'), 'callback_data': 'menu'}]
            ]
        }
        send_message(user_id, message, markup)
    
    def handle_user_state(self, user_id, message, user_state):
        # TXID bekleniyorsa
        if user_state['state'] == 'waiting_txid' and 'text' in message:
            txid = message['text'].strip()
            data = user_state['data']
            
            if len(txid) < 10:
                send_message(user_id, "❌ Geçersiz TXID!")
                return
            
            try:
                deposit_id = data['deposit_id']
                amount = data['amount']
                bonus = data['bonus']
                
                # Depoziti tamamla
                self.db.cursor.execute('''
                    UPDATE deposits 
                    SET txid = ?, status = 'completed', completed_at = ?
                    WHERE deposit_id = ? AND user_id = ?
                ''', (txid, get_turkey_time().isoformat(), deposit_id, user_id))
                
                # Bakiye ekle
                user = self.db.get_user(user_id)
                new_balance = user.get('balance', 0) + amount + bonus
                self.db.update_user(user_id, {
                    'balance': new_balance,
                    'total_deposited': user.get('total_deposited', 0) + amount,
                    'deposit_count': user.get('deposit_count', 0) + 1,
                    'total_bonus': user.get('total_bonus', 0) + bonus
                })
                
                self.db.conn.commit()
                self.db.update_bot_stats('deposit')
                
                # Başarı mesajı
                send_message(user_id, f"""
✅ <b>BAKİYE YÜKLENDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>+{amount + bonus:.2f}₺ bakiyenize eklendi!</b>
• Yatırım: {amount:.2f}₺
• Bonus: {bonus:.2f}₺
• Yeni Bakiye: {new_balance:.2f}₺

🎉 <b>Hemen görev yapmaya başlayabilirsiniz!</b>
""")
                
                self.clear_user_state(user_id)
                time.sleep(2)
                self.show_main_menu(user_id)
                
            except Exception as e:
                print(f"❌ TXID hatası: {e}")
                send_message(user_id, "❌ İşlem kaydedilemedi!")

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v16.0                      ║
    ║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAM BAKİYESİ + BONUS SİSTEM║
    ║   + REFERANS SİSTEMİ + ADMIN PANEL + SQLITE                    ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    print(f"₿ TRX Adresi: {TRX_ADDRESS}")
    print("💰 Min Depozit: 25₺, Max: 200₺")
    print("🎁 Bonuslar: %35 Normal")
    print("👥 Referans Bonusu: 1₺ her davet")
    print("⚡ Sistem tamamen Türkçe")
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
