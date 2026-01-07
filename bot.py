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
from typing import Optional, Dict, List, Tuple

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
MIN_WITHDRAW = 10.0

# Görev Ücretleri
GROUP_TASK_PRICE = 0.5  # Grup görevi ücreti (Reklamveren öder)
CHANNEL_TASK_PRICE = 1.25  # Kanal görevi ücreti (Reklamveren öder)

# Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v20.0"})

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
                referred_by TEXT,
                total_withdrawn REAL DEFAULT 0.0,
                withdraw_count INTEGER DEFAULT 0,
                last_notification_time TEXT,
                is_referred INTEGER DEFAULT 0,
                ref_first_login INTEGER DEFAULT 0,
                ref_link_used TEXT,
                is_advertiser INTEGER DEFAULT 0,  -- Reklamveren mi?
                advertiser_balance REAL DEFAULT 0.0,  -- Reklamveren bakiyesi
                total_spent_on_ads REAL DEFAULT 0.0,  -- Reklamlara harcanan toplam
                active_group_id TEXT,  -- Aktif grup ID
                active_channel_id TEXT,  -- Aktif kanal ID
                last_join_check TEXT  -- Son katılım kontrolü
            )
        ''')
        
        # Görevler (Tasks)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                advertiser_id TEXT,
                task_type TEXT,  -- 'group' veya 'channel'
                target_id TEXT,  -- Grup veya kanal ID
                target_name TEXT,
                task_description TEXT,
                reward_amount REAL,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',  -- active, completed, cancelled
                created_at TEXT,
                completed_at TEXT,
                total_spent REAL DEFAULT 0.0,
                is_paid INTEGER DEFAULT 0
            )
        ''')
        
        # Görev Katılımları
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_participations (
                participation_id TEXT PRIMARY KEY,
                task_id TEXT,
                user_id TEXT,
                user_name TEXT,
                status TEXT DEFAULT 'pending',  -- pending, verified, rejected, left
                joined_at TEXT,
                left_at TEXT,
                reward_paid REAL DEFAULT 0.0,
                paid_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
            )
        ''')
        
        # Referans kayıtları
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referral_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id TEXT,
                referred_id TEXT,
                referral_link TEXT,
                amount REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                reward_type TEXT,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
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
                trx_price REAL,
                deposit_type TEXT DEFAULT 'user'  -- 'user' veya 'advertiser'
            )
        ''')
        
        # Reklamveren Ödemeleri
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS advertiser_payments (
                payment_id TEXT PRIMARY KEY,
                advertiser_id TEXT,
                task_id TEXT,
                user_id TEXT,
                amount REAL,
                payment_type TEXT,  -- 'task_payment' veya 'withdrawal'
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                txid TEXT,
                FOREIGN KEY (advertiser_id) REFERENCES users (user_id),
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
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
                INSERT INTO users (user_id, name, balance, ads_balance, created_at, language, last_active, referral_code, last_notification_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, '', 0.0, 0.0, now, 'tr', now, referral_code, now))
            self.conn.commit()
            
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        
        return dict(user) if user else {}
    
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
<b>💰 BAKİYE EKLENDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>+{total:.2f}₺ bakiyenize eklendi!</b>

📊 <b>Detaylar:</b>
• Kaynak: {source_text}
• Tutar: {amount:.2f}₺
• Bonus: {bonus:.2f}₺ (%{bonus_percent})
• Yeni Bakiye: {new_balance:.2f}₺

💡 <b>Hemen görev yapmaya başlayın!</b>
"""
            send_message(user_id, message)
        
        return True
    
    def add_advertiser_balance(self, user_id, amount):
        """Reklamveren bakiyesine ekle"""
        user = self.get_user(user_id)
        new_balance = user.get('advertiser_balance', 0) + amount
        
        self.cursor.execute('''
            UPDATE users 
            SET advertiser_balance = ?, total_deposited = total_deposited + ?
            WHERE user_id = ?
        ''', (new_balance, amount, user_id))
        self.conn.commit()
        
        # Reklamveren bakiye bildirimi
        message = f"""
<b>💰 REKLAMVEREN BAKİYESİ EKLENDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>+{amount:.2f}₺ reklamveren bakiyenize eklendi!</b>

📊 <b>Detaylar:</b>
• Yeni Reklamveren Bakiye: {new_balance:.2f}₺
• Toplam Yatırım: {user.get('total_deposited', 0) + amount:.2f}₺

💡 <b>Hemen reklam vermeye başlayın!</b>
"""
        send_message(user_id, message)
        
        return True
    
    def deduct_advertiser_balance(self, user_id, amount):
        """Reklamveren bakiyesinden düş"""
        user = self.get_user(user_id)
        current_balance = user.get('advertiser_balance', 0)
        
        if current_balance < amount:
            return False, "Yetersiz reklamveren bakiyesi!"
        
        new_balance = current_balance - amount
        
        self.cursor.execute('''
            UPDATE users 
            SET advertiser_balance = ?, total_spent_on_ads = total_spent_on_ads + ?
            WHERE user_id = ?
        ''', (new_balance, amount, user_id))
        self.conn.commit()
        
        return True, f"{amount:.2f}₺ reklamveren bakiyenizden düşüldü"
    
    def create_task(self, advertiser_id, task_type, target_id, target_name, description, reward, max_participants):
        """Yeni görev oluştur"""
        task_id = hashlib.md5(f"{advertiser_id}{target_id}{time.time()}".encode()).hexdigest()[:10].upper()
        now = get_turkey_time().isoformat()
        
        self.cursor.execute('''
            INSERT INTO tasks (task_id, advertiser_id, task_type, target_id, target_name, 
                             task_description, reward_amount, max_participants, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, advertiser_id, task_type, target_id, target_name, 
              description, reward, max_participants, now))
        self.conn.commit()
        
        return task_id
    
    def join_task(self, task_id, user_id, user_name):
        """Göreve katıl"""
        participation_id = hashlib.md5(f"{task_id}{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        now = get_turkey_time().isoformat()
        
        # Önce katılım var mı kontrol et
        self.cursor.execute('''
            SELECT * FROM task_participations 
            WHERE task_id = ? AND user_id = ?
        ''', (task_id, user_id))
        existing = self.cursor.fetchone()
        
        if existing:
            return False, "Zaten bu göreve katıldınız!"
        
        self.cursor.execute('''
            INSERT INTO task_participations (participation_id, task_id, user_id, user_name, joined_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (participation_id, task_id, user_id, user_name, now))
        
        # Görev katılımcı sayısını güncelle
        self.cursor.execute('''
            UPDATE tasks SET current_participants = current_participants + 1 
            WHERE task_id = ?
        ''', (task_id,))
        
        self.conn.commit()
        return True, "Göreve katıldınız!"
    
    def verify_task_participation(self, participation_id):
        """Görev katılımını doğrula ve ödeme yap"""
        self.cursor.execute('''
            SELECT tp.*, t.advertiser_id, t.reward_amount, t.task_type
            FROM task_participations tp
            JOIN tasks t ON tp.task_id = t.task_id
            WHERE tp.participation_id = ?
        ''', (participation_id,))
        participation = self.cursor.fetchone()
        
        if not participation:
            return False, "Katılım bulunamadı"
        
        if participation['status'] == 'verified':
            return False, "Zaten doğrulanmış"
        
        now = get_turkey_time().isoformat()
        
        # Reklamveren bakiyesini kontrol et
        advertiser = self.get_user(participation['advertiser_id'])
        if advertiser.get('advertiser_balance', 0) < participation['reward_amount']:
            return False, "Reklamveren bakiyesi yetersiz!"
        
        # Reklamveren bakiyesinden düş
        success, message = self.deduct_advertiser_balance(
            participation['advertiser_id'], 
            participation['reward_amount']
        )
        
        if not success:
            return False, message
        
        # Kullanıcıya ödeme yap
        user = self.get_user(participation['user_id'])
        new_balance = user.get('balance', 0) + participation['reward_amount']
        
        self.cursor.execute('''
            UPDATE users 
            SET balance = ?, tasks_completed = tasks_completed + 1, total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (new_balance, participation['reward_amount'], participation['user_id']))
        
        # Katılımı güncelle
        self.cursor.execute('''
            UPDATE task_participations 
            SET status = 'verified', reward_paid = ?, paid_at = ?
            WHERE participation_id = ?
        ''', (participation['reward_amount'], now, participation_id))
        
        # Görev giderini güncelle
        self.cursor.execute('''
            UPDATE tasks 
            SET total_spent = total_spent + ?
            WHERE task_id = ?
        ''', (participation['reward_amount'], participation['task_id']))
        
        self.conn.commit()
        
        # Ödeme kaydı oluştur
        payment_id = hashlib.md5(f"{participation_id}{time.time()}".encode()).hexdigest()[:10].upper()
        self.cursor.execute('''
            INSERT INTO advertiser_payments (payment_id, advertiser_id, task_id, user_id, 
                                           amount, payment_type, status, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, 'task_payment', 'completed', ?, ?)
        ''', (payment_id, participation['advertiser_id'], participation['task_id'], 
              participation['user_id'], participation['reward_amount'], now, now))
        
        self.conn.commit()
        
        # Kullanıcıya bildirim
        send_message(participation['user_id'], f"""
<b>✅ GÖREV TAMAMLANDI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>+{participation['reward_amount']:.2f}₺ kazandınız!</b>

📊 <b>Detaylar:</b>
• Görev Türü: {'Kanal' if participation['task_type'] == 'channel' else 'Grup'}
• Ödül: {participation['reward_amount']:.2f}₺
• Yeni Bakiye: {new_balance:.2f}₺

💡 <b>Daha fazla görev yaparak kazanmaya devam edin!</b>
""")
        
        return True, f"{participation['reward_amount']:.2f}₺ ödendi"
    
    def handle_user_left_group(self, user_id, chat_id):
        """Kullanıcı gruptan çıkınca işlem yap"""
        # Aktif grup görevlerini bul
        self.cursor.execute('''
            SELECT tp.*, t.reward_amount
            FROM task_participations tp
            JOIN tasks t ON tp.task_id = t.task_id
            WHERE tp.user_id = ? AND t.target_id = ? 
            AND t.task_type = 'group' AND tp.status = 'verified'
        ''', (user_id, chat_id))
        
        participations = self.cursor.fetchall()
        
        total_deducted = 0
        for participation in participations:
            # Kullanıcının bakiyesinden düş
            user = self.get_user(user_id)
            if user.get('balance', 0) >= participation['reward_amount']:
                new_balance = user.get('balance', 0) - participation['reward_amount']
                self.cursor.execute('''
                    UPDATE users SET balance = ? WHERE user_id = ?
                ''', (new_balance, user_id))
                
                # Reklamverene iade
                advertiser = self.get_user(participation['advertiser_id'])
                new_ad_balance = advertiser.get('advertiser_balance', 0) + participation['reward_amount']
                self.cursor.execute('''
                    UPDATE users SET advertiser_balance = ?, total_spent_on_ads = total_spent_on_ads - ?
                    WHERE user_id = ?
                ''', (new_ad_balance, participation['reward_amount'], participation['advertiser_id']))
                
                # Katılım durumunu güncelle
                now = get_turkey_time().isoformat()
                self.cursor.execute('''
                    UPDATE task_participations 
                    SET status = 'left', left_at = ?, reward_paid = 0
                    WHERE participation_id = ?
                ''', (now, participation['participation_id']))
                
                total_deducted += participation['reward_amount']
                
                # Bildirim gönder
                send_message(user_id, f"""
<b>⚠️ GRUPTAN AYRILMA CEZASI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>{participation['reward_amount']:.2f}₺ bakiyenizden düşüldü!</b>

📊 <b>Sebep:</b>
• Grubu terk ettiğiniz için
• Görev ödülü iade edildi

💡 <b>Tekrar katılın ve kazanmaya devam edin!</b>
""")
        
        self.conn.commit()
        return total_deducted > 0, total_deducted
    
    def handle_user_left_channel(self, user_id, chat_id):
        """Kullanıcı kanaldan çıkınca işlem yap"""
        # Aktif kanal görevlerini bul
        self.cursor.execute('''
            SELECT tp.*, t.reward_amount
            FROM task_participations tp
            JOIN tasks t ON tp.task_id = t.task_id
            WHERE tp.user_id = ? AND t.target_id = ? 
            AND t.task_type = 'channel' AND tp.status = 'verified'
        ''', (user_id, chat_id))
        
        participations = self.cursor.fetchall()
        
        total_deducted = 0
        for participation in participations:
            # Kullanıcının bakiyesinden düş
            user = self.get_user(user_id)
            if user.get('balance', 0) >= participation['reward_amount']:
                new_balance = user.get('balance', 0) - participation['reward_amount']
                self.cursor.execute('''
                    UPDATE users SET balance = ? WHERE user_id = ?
                ''', (new_balance, user_id))
                
                # Reklamverene iade
                advertiser = self.get_user(participation['advertiser_id'])
                new_ad_balance = advertiser.get('advertiser_balance', 0) + participation['reward_amount']
                self.cursor.execute('''
                    UPDATE users SET advertiser_balance = ?, total_spent_on_ads = total_spent_on_ads - ?
                    WHERE user_id = ?
                ''', (new_ad_balance, participation['reward_amount'], participation['advertiser_id']))
                
                # Katılım durumunu güncelle
                now = get_turkey_time().isoformat()
                self.cursor.execute('''
                    UPDATE task_participations 
                    SET status = 'left', left_at = ?, reward_paid = 0
                    WHERE participation_id = ?
                ''', (now, participation['participation_id']))
                
                total_deducted += participation['reward_amount']
                
                # Bildirim gönder
                send_message(user_id, f"""
<b>⚠️ KANALDAN AYRILMA CEZASI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>{participation['reward_amount']:.2f}₺ bakiyenizden düşüldü!</b>

📊 <b>Sebep:</b>
• Kanalı terk ettiğiniz için
• Görev ödülü iade edildi

💡 <b>Tekrar katılın ve kazanmaya devam edin!</b>
""")
        
        self.conn.commit()
        return total_deducted > 0, total_deducted
    
    def check_referral_usage(self, user_id, referral_code):
        """Kullanıcının bu referans kodunu daha önce kullanıp kullanmadığını kontrol et"""
        self.cursor.execute('''
            SELECT ref_link_used FROM users WHERE user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()
        if result and result[0]:
            return result[0] == referral_code
        return False
    
    def record_referral(self, referrer_id, referred_id, referral_link, amount=0.0):
        """Referans kaydı oluştur"""
        now = get_turkey_time().isoformat()
        self.cursor.execute('''
            INSERT INTO referral_logs (referrer_id, referred_id, referral_link, amount, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (referrer_id, referred_id, referral_link, amount, now, 'pending'))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def complete_referral(self, log_id, reward_type="welcome"):
        """Referansı tamamla ve bonus ver"""
        now = get_turkey_time().isoformat()
        self.cursor.execute('''
            UPDATE referral_logs 
            SET status = 'completed', completed_at = ?, reward_type = ?
            WHERE log_id = ?
        ''', (now, reward_type, log_id))
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
        print(f"❌ Mesaj hatası: {e}")
        return None

def edit_message(chat_id, message_id, text, markup=None, parse_mode='HTML'):
    url = BASE_URL + "editMessageText"
    data = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': parse_mode}
    if markup: data['reply_markup'] = json.dumps(markup)
    try: 
        response = requests.post(url, json=data, timeout=10).json()
        return response
    except Exception as e:
        print(f"❌ Mesaj düzenleme hatası: {e}")
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
    if text: data['text'] = text
    if show_alert: data['show_alert'] = True
    try: 
        requests.post(url, json=data, timeout=5)
    except: 
        pass

def get_chat_member(chat_id, user_id):
    url = BASE_URL + "getChatMember"
    data = {'chat_id': chat_id, 'user_id': int(user_id)}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            status = response['result']['status']
            return status in ['member', 'administrator', 'creator']
    except: 
        print(f"❌ Chat member kontrol hatası: chat_id={chat_id}, user_id={user_id}")
        return False

def get_chat(chat_id):
    url = BASE_URL + "getChat"
    data = {'chat_id': chat_id}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            return response['result']
    except: 
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
    except: 
        return False

def delete_message(chat_id, message_id):
    url = BASE_URL + "deleteMessage"
    data = {'chat_id': chat_id, 'message_id': message_id}
    try:
        response = requests.post(url, json=data, timeout=5).json()
        return response.get('ok', False)
    except:
        return False

# Bot Sistemi
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.user_states = {}
        self.trx_price = 12.61
        self.update_trx_price()
        self.background_checker = BackgroundChecker(self.db)
        self.background_checker.start()
        print("🤖 Bot sistemi başlatıldı")
    
    def update_trx_price(self):
        try:
            response = requests.get(TRX_PRICE_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.trx_price = data.get('tron', {}).get('try', 12.61)
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
                params = {'offset': offset, 'timeout': 10, 'allowed_updates': ['message', 'callback_query', 'chat_member']}
                response = requests.get(url, params=params, timeout=15).json()
                
                if response.get('ok'):
                    updates = response['result']
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            threading.Thread(target=self.process_message, args=(update['message'],)).start()
                        elif 'callback_query' in update:
                            threading.Thread(target=self.process_callback, args=(update['callback_query'],)).start()
                        elif 'chat_member' in update:
                            threading.Thread(target=self.process_chat_member_update, args=(update['chat_member'],)).start()
                
            except Exception as e:
                print(f"❌ Polling hatası: {e}")
                time.sleep(2)
    
    def process_chat_member_update(self, chat_member_update):
        """Kullanıcı grup/kanal üyelik değişikliklerini işle"""
        try:
            if 'old_chat_member' in chat_member_update and 'new_chat_member' in chat_member_update:
                user_id = str(chat_member_update['new_chat_member']['user']['id'])
                chat_id = str(chat_member_update['chat']['id'])
                
                old_status = chat_member_update['old_chat_member']['status']
                new_status = chat_member_update['new_chat_member']['status']
                
                # Kullanıcı gruptan/kanaldan ayrıldı mı?
                if old_status in ['member', 'administrator', 'creator'] and new_status == 'left':
                    print(f"⚠️ Kullanıcı {user_id} gruptan/kanaldan ayrıldı: {chat_id}")
                    
                    # Grup mu kanal mı kontrol et
                    chat_info = get_chat(chat_id)
                    if chat_info:
                        chat_type = chat_info.get('type', '')
                        
                        if chat_type == 'group' or chat_type == 'supergroup':
                            # Grup için işlem yap
                            deducted, amount = self.db.handle_user_left_group(user_id, chat_id)
                            if deducted:
                                print(f"✅ {user_id} kullanıcısından {amount}₺ düşüldü (gruptan ayrılma)")
                        
                        elif chat_type == 'channel':
                            # Kanal için işlem yap
                            deducted, amount = self.db.handle_user_left_channel(user_id, chat_id)
                            if deducted:
                                print(f"✅ {user_id} kullanıcısından {amount}₺ düşüldü (kanaldan ayrılma)")
                        
                        # Zorunlu kanal kontrolü
                        if f"@{MANDATORY_CHANNEL}" in chat_info.get('username', ''):
                            print(f"⚠️ Kullanıcı {user_id} zorunlu kanaldan ayrıldı!")
                            self.db.update_user(user_id, {'in_channel': 0})
                            send_message(user_id, """
<b>⚠️ ZORUNLU KANALDAN AYRILDINIZ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>@GY_Refim kanalından ayrıldınız!</b>

📊 <b>Sonuçlar:</b>
• Botu kullanamazsınız
• Mevcut görevleriniz iptal edilebilir
• Kazançlarınız düşülebilir

💡 <b>Tekrar katılmak için:</b>
1. @GY_Refim kanalına katılın
2. /start yazarak botu yeniden başlatın
""")
                
                # Kullanıcı gruba/kanala katıldı mı?
                elif old_status == 'left' and new_status in ['member', 'administrator', 'creator']:
                    print(f"✅ Kullanıcı {user_id} gruba/kanala katıldı: {chat_id}")
                    
                    # Zorunlu kanal kontrolü
                    chat_info = get_chat(chat_id)
                    if chat_info and f"@{MANDATORY_CHANNEL}" in chat_info.get('username', ''):
                        print(f"✅ Kullanıcı {user_id} zorunlu kanala katıldı!")
                        self.db.update_user(user_id, {'in_channel': 1})
        
        except Exception as e:
            print(f"❌ Chat member update hatası: {e}")
    
    def process_message(self, message):
        try:
            if 'from' not in message: 
                return
            
            user_id = str(message['from']['id'])
            
            # Hızlı yanıt
            if 'text' in message:
                text = message['text']
                if text.startswith('/start'):
                    self.handle_start(user_id, text)
                    return
                elif text == '/menu':
                    self.show_main_menu(user_id)
                    return
                elif text == '/admin' and user_id == ADMIN_ID:
                    self.show_admin_panel(user_id)
                    return
                elif text == '/reklamveren':
                    self.show_advertiser_menu(user_id)
                    return
                elif text == '/gorevler':
                    self.show_available_tasks(user_id)
                    return
            
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
        
        except Exception as e:
            print(f"❌ Mesaj hatası: {e}")
    
    def process_callback(self, callback):
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # Hızlı yanıt
            answer_callback(callback_id, "⏳ İşleniyor...")
            
            # Temel navigasyon
            if data == 'menu':
                self.show_main_menu(user_id)
            elif data == 'back':
                self.show_main_menu(user_id)
            elif data == 'cancel':
                self.clear_user_state(user_id)
                self.show_main_menu(user_id)
            elif data == 'advertiser_back':
                self.show_advertiser_menu(user_id)
            
            # Ana menü butonları
            elif data == 'tasks':
                self.show_available_tasks(user_id)
            elif data == 'create_task':
                self.start_task_creation(user_id)
            elif data == 'my_tasks':
                self.show_my_tasks(user_id)
            elif data == 'deposit':
                self.show_deposit_menu(user_id)
            elif data == 'withdraw':
                self.show_withdraw_menu(user_id)
            elif data == 'profile':
                self.show_profile(user_id)
            elif data == 'referral':
                self.show_referral_menu(user_id)
            elif data == 'help':
                self.show_help(user_id)
            elif data == 'advertiser_menu':
                self.show_advertiser_menu(user_id)
            
            # Reklamveren butonları
            elif data == 'advertiser_deposit':
                self.show_advertiser_deposit_menu(user_id)
            elif data == 'advertiser_balance':
                self.show_advertiser_balance(user_id)
            elif data == 'advertiser_create_task':
                self.start_advertiser_task_creation(user_id)
            elif data == 'advertiser_my_tasks':
                self.show_advertiser_my_tasks(user_id)
            elif data == 'advertiser_payments':
                self.show_advertiser_payments(user_id)
            elif data == 'advertiser_withdraw':
                self.start_advertiser_withdraw(user_id)
            elif data == 'toggle_advertiser':
                self.toggle_advertiser_mode(user_id)
            
            # Görev türü
            elif data.startswith('task_type_'):
                task_type = data.replace('task_type_', '')
                self.handle_task_type_selection(user_id, task_type)
            
            # Depozit tutarları
            elif data.startswith('deposit_amount_'):
                parts = data.replace('deposit_amount_', '').split('_')
                amount = float(parts[0])
                deposit_type = parts[1] if len(parts) > 1 else 'user'
                self.start_deposit(user_id, amount, deposit_type)
            
            # Görev katılımı
            elif data.startswith('join_task_'):
                task_id = data.replace('join_task_', '')
                self.join_task(user_id, task_id)
            
            # Görev doğrulama
            elif data.startswith('verify_task_'):
                participation_id = data.replace('verify_task_', '')
                self.verify_task_participation(user_id, participation_id)
            
            # Referans butonları
            elif data == 'referral_copy':
                self.copy_referral_link(user_id)
            elif data == 'referral_share':
                self.share_referral_link(user_id)
            elif data == 'referral_details':
                self.show_referral_details(user_id)
            
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
            elif data == 'admin_advertisers':
                self.show_admin_advertisers(user_id)
            
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
            send_message(user_id, """
<b>🤖 GÖREV YAPSAM BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📢 <b>Botu kullanmak için kanala katılın:</b>
👉 @GY_Refim

💡 <b>Katıldıktan sonra "Katıldım" butonuna basın</b>
""", markup)
            return
        
        user = self.db.get_user(user_id)
        
        # Hoşgeldin bonusu
        if not user.get('welcome_bonus'):
            # Önce referans kontrolü yap
            ref_code_used = None
            is_referred = 0
            ref_first_login = 0
            referrer_id = None
            
            if ' ' in text:
                parts = text.split()
                if len(parts) > 1 and parts[1].startswith('ref_'):
                    ref_code = parts[1]
                    referrer_id = parts[1].replace('ref_', '')
                    
                    if referrer_id and referrer_id != user_id:
                        referrer = self.db.get_user(referrer_id)
                        if referrer:
                            # Kullanıcı daha önce bu referansı kullanmış mı?
                            if not self.db.check_referral_usage(user_id, ref_code):
                                # İlk defa bu referansla geliyor
                                is_referred = 1
                                ref_first_login = 1
                                ref_code_used = ref_code
                                
                                # Referans kaydını logla
                                referral_link = f"https://t.me/GorevYapsamBot?start={ref_code}"
                                log_id = self.db.record_referral(referrer_id, user_id, referral_link, 1.0)
                                
                                # Referans sahibine bonus ekle
                                self.db.add_balance(referrer_id, 1.0, 0, "referral")
                                self.db.update_user(referrer_id, {
                                    'referrals': referrer.get('referrals', 0) + 1,
                                    'ref_earned': referrer.get('ref_earned', 0) + 1.0
                                })
                                
                                # Referansı tamamla
                                self.db.complete_referral(log_id, "welcome")
                                
                                # Referans bildirimi gönder
                                send_message(referrer_id, f"""
<b>🎉 REFERANS KAZANCI!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Yeni referansınız:</b> {user.get('name', 'Kullanıcı')}
💰 <b>Kazandınız:</b> 1.00₺
📊 <b>Toplam referans:</b> {referrer.get('referrals', 0) + 1}

💡 <b>Referans linkinizi paylaşmaya devam edin!</b>
""")
            
            # Hoşgeldin bonusunu ver
            self.db.add_balance(user_id, 2.0, 0, "welcome_bonus")
            self.db.update_user(user_id, {
                'welcome_bonus': 1, 
                'in_channel': 1,
                'is_referred': is_referred,
                'ref_first_login': ref_first_login,
                'ref_link_used': ref_code_used,
                'referred_by': referrer_id if is_referred else None
            })
            
            # Referans ile geldiyse ekstra mesaj gönder
            if is_referred:
                send_message(user_id, """
<b>🎉 HOŞ GELDİNİZ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>2₺ hoşgeldin bonusu hesabınıza yüklendi!</b>
👥 <b>Referans ile kaydoldunuz!</b>
💰 <b>Referans sahibine 1₺ bonus yüklendi!</b>

💡 <b>Hemen görev yapmaya başlayabilirsiniz!</b>
""")
            else:
                send_message(user_id, """
<b>🎉 HOŞ GELDİNİZ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>2₺ hoşgeldin bonusu hesabınıza yüklendi!</b>
💰 <b>Hemen görev yapmaya başlayabilirsiniz!</b>

👥 <b>Referans linkinizi paylaşarak daha fazla kazanın!</b>
""")
        
        # Eğer zaten kayıtlıysa ve referans linki ile gelmişse
        elif ' ' in text and user.get('is_referred') == 0:
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith('ref_'):
                ref_code = parts[1]
                referrer_id = parts[1].replace('ref_', '')
                
                if referrer_id and referrer_id != user_id:
                    # Kullanıcı daha önce referansla gelmemişse
                    if not user.get('ref_link_used'):
                        referrer = self.db.get_user(referrer_id)
                        if referrer:
                            # Referans kaydını logla
                            referral_link = f"https://t.me/GorevYapsamBot?start={ref_code}"
                            log_id = self.db.record_referral(referrer_id, user_id, referral_link, 0.5)
                            
                            # Referans sahibine bonus ekle (daha az bonus)
                            self.db.add_balance(referrer_id, 0.5, 0, "referral_late")
                            self.db.update_user(referrer_id, {
                                'referrals': referrer.get('referrals', 0) + 1,
                                'ref_earned': referrer.get('ref_earned', 0) + 0.5
                            })
                            
                            # Referansı tamamla
                            self.db.complete_referral(log_id, "late_join")
                            
                            # Kullanıcıyı güncelle
                            self.db.update_user(user_id, {
                                'is_referred': 1,
                                'ref_link_used': ref_code,
                                'referred_by': referrer_id
                            })
                            
                            # Bildirim gönder
                            send_message(referrer_id, f"""
<b>🎉 GEÇ KATILIM REFERANS KAZANCI!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Yeni geç katılım referansınız:</b> {user.get('name', 'Kullanıcı')}
💰 <b>Kazandınız:</b> 0.50₺
📊 <b>Toplam referans:</b> {referrer.get('referrals', 0) + 1}

💡 <b>Referans linkinizi paylaşmaya devam edin!</b>
""")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        # Kanal kontrolü yap
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            self.db.update_user(user_id, {'in_channel': 0})
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 Kanala Katıl', 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': '✅ Katıldım', 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, """
<b>⚠️ KANAL KONTROLÜ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>Zorunlu kanaldan ayrıldınız!</b>

📢 <b>Botu kullanmak için tekrar katılın:</b>
👉 @GY_Refim

💡 <b>Katıldıktan sonra "Katıldım" butonuna basın</b>
""", markup)
            return
        
        # Reklamveren modunu kontrol et
        is_advertiser = user.get('is_advertiser', 0)
        advertiser_text = "\n<b>👑 Reklamveren Modu:</b> Aktif" if is_advertiser else ""
        
        message = f"""
<b>🤖 GÖREV YAPSAM BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 Hoş geldin</b> {user.get('name', 'Kullanıcı')}!
<b>💰 Bakiye:</b> <code>{user.get('balance', 0):.2f}₺</code>{advertiser_text}

<b>🎯 Tamamlanan Görev:</b> {user.get('tasks_completed', 0)}
<b>👥 Referans:</b> {user.get('referrals', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 ANA MENÜ</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '🎯 Görev Yap', 'callback_data': 'tasks'},
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'}
                ],
                [
                    {'text': '👤 Profil', 'callback_data': 'profile'},
                    {'text': '👥 Referans', 'callback_data': 'referral'}
                ]
            ]
        }
        
        # Reklamveren butonu
        if is_advertiser:
            markup['inline_keyboard'].insert(1, [
                {'text': '📢 Reklamveren', 'callback_data': 'advertiser_menu'}
            ])
        else:
            markup['inline_keyboard'].insert(1, [
                {'text': '👑 Reklamveren Ol', 'callback_data': 'toggle_advertiser'}
            ])
        
        # Yardım ve admin butonları
        markup['inline_keyboard'].append([
            {'text': '❓ Yardım', 'callback_data': 'help'},
            {'text': '📋 Menü', 'callback_data': 'menu'}
        ])
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([
                {'text': '👑 Admin Panel', 'callback_data': 'admin_panel'}
            ])
        
        send_message(user_id, message, markup)
    
    def toggle_advertiser_mode(self, user_id):
        """Reklamveren modunu aç/kapat"""
        user = self.db.get_user(user_id)
        current_status = user.get('is_advertiser', 0)
        new_status = 0 if current_status else 1
        
        self.db.update_user(user_id, {'is_advertiser': new_status})
        
        if new_status:
            message = """
<b>👑 REKLAMVEREN MODU AKTİF</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>Reklamveren moduna geçtiniz!</b>

📊 <b>Artık şunları yapabilirsiniz:</b>
• 📢 Görev oluşturabilirsiniz
• 💰 Reklamveren bakiyesi yükleyebilirsiniz
• 📈 Reklamlarınızı takip edebilirsiniz
• 💸 Reklamveren bakiyenizi çekebilirsiniz

💡 <b>"Reklamveren" butonuna tıklayarak işlemlerinize başlayın!</b>
"""
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 Reklamveren Menüsü', 'callback_data': 'advertiser_menu'},
                    {'text': '🔙 Ana Menü', 'callback_data': 'menu'}
                ]]
            }
        else:
            message = """
<b>👑 REKLAMVEREN MODU KAPALI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ️ <b>Reklamveren modunu kapattınız!</b>

📊 <b>Artık normal kullanıcı modundasınız:</b>
• 🎯 Görev yapabilirsiniz
• 💰 Normal bakiye yükleyebilirsiniz
• 💸 Kazançlarınızı çekebilirsiniz

💡 <b>Tekrar reklamveren olmak için "Reklamveren Ol" butonuna tıklayın!</b>
"""
            markup = {
                'inline_keyboard': [[
                    {'text': '👑 Reklamveren Ol', 'callback_data': 'toggle_advertiser'},
                    {'text': '🔙 Ana Menü', 'callback_data': 'menu'}
                ]]
            }
        
        send_message(user_id, message, markup)
    
    def show_advertiser_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        if not user.get('is_advertiser', 0):
            send_message(user_id, "❌ Reklamveren modunda değilsiniz!")
            self.show_main_menu(user_id)
            return
        
        message = f"""
<b>👑 REKLAMVEREN MENÜSÜ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Reklamveren Bakiye:</b> {user.get('advertiser_balance', 0):.2f}₺
<b>📈 Toplam Harcama:</b> {user.get('total_spent_on_ads', 0):.2f}₺
<b>🎯 Aktif Görevler:</b> 0

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 İŞLEMLER</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📢 Görev Oluştur', 'callback_data': 'advertiser_create_task'},
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'advertiser_deposit'}
                ],
                [
                    {'text': '📊 Görevlerim', 'callback_data': 'advertiser_my_tasks'},
                    {'text': '💳 Ödemeler', 'callback_data': 'advertiser_payments'}
                ],
                [
                    {'text': '💰 Bakiyem', 'callback_data': 'advertiser_balance'},
                    {'text': '💸 Para Çek', 'callback_data': 'advertiser_withdraw'}
                ],
                [
                    {'text': '🔙 Ana Menü', 'callback_data': 'menu'},
                    {'text': '🚫 Reklamverenliği Kapat', 'callback_data': 'toggle_advertiser'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_advertiser_balance(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>💰 REKLAMVEREN BAKİYE DETAYLARI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Bakiye Bilgileri:</b>
• Reklamveren Bakiye: {user.get('advertiser_balance', 0):.2f}₺
• Normal Bakiye: {user.get('balance', 0):.2f}₺
• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺
• Toplam Harcama: {user.get('total_spent_on_ads', 0):.2f}₺

<b>💡 Not:</b>
• Reklamveren bakiyesi sadece reklam vermek için kullanılır
• Normal bakiye kazanılan paradır ve çekilebilir
• Reklamveren bakiyesi çekilemez, sadece reklamlarda kullanılır
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'advertiser_deposit'},
                    {'text': '📢 Görev Oluştur', 'callback_data': 'advertiser_create_task'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_advertiser_task_creation(self, user_id):
        user = self.db.get_user(user_id)
        
        if user.get('advertiser_balance', 0) < GROUP_TASK_PRICE:
            message = f"""
<b>❌ YETERSİZ REKLAMVEREN BAKİYESİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Reklamveren bakiyeniz yetersiz!</b>

<b>📊 Mevcut Durum:</b>
• Reklamveren Bakiye: {user.get('advertiser_balance', 0):.2f}₺
• Minimum Gerekli: {GROUP_TASK_PRICE:.2f}₺

<b>💡 Çözüm:</b>
1. "💰 Bakiye Yükle" butonuna tıklayın
2. Reklamveren bakiyesi yükleyin
3. Tekrar görev oluşturmayı deneyin
"""
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '💰 Bakiye Yükle', 'callback_data': 'advertiser_deposit'},
                        {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                    ]
                ]
            }
            
            send_message(user_id, message, markup)
            return
        
        message = """
<b>📢 REKLAMVEREN GÖREV OLUŞTURMA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👇 Görev Türünü Seçin:</b>

<b>👥 GRUP GÖREVİ</b>
• Ödül: 0.5₺ her katılım
• Gereksinim: Bot grupta admin olmalı
• Katılımcılar gruba katılır

<b>📢 KANAL GÖREVİ</b>
• Ödül: 1.25₺ her katılım
• Gereksinim: Bot kanalda admin olmalı
• Katılımcılar kanala katılır
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '👥 Grup Görevi', 'callback_data': 'task_type_group'},
                    {'text': '📢 Kanal Görevi', 'callback_data': 'task_type_channel'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def handle_task_type_selection(self, user_id, task_type):
        user = self.db.get_user(user_id)
        
        if task_type == 'group':
            reward = GROUP_TASK_PRICE
            task_type_text = "Grup"
        else:  # channel
            reward = CHANNEL_TASK_PRICE
            task_type_text = "Kanal"
        
        # Kullanıcının bakiyesini kontrol et
        if user.get('advertiser_balance', 0) < reward:
            send_message(user_id, f"❌ Yetersiz bakiye! Minimum {reward:.2f}₺ gereklidir.")
            self.show_advertiser_menu(user_id)
            return
        
        self.set_user_state(user_id, 'create_task', {
            'task_type': task_type,
            'reward': reward,
            'step': 1
        })
        
        send_message(user_id, f"""
<b>📢 {task_type_text.upper()} GÖREVİ OLUŞTURMA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>ℹ️ Bilgiler:</b>
• Görev Türü: {task_type_text}
• Ödül: {reward:.2f}₺ her katılım
• Botun admin olduğu bir {task_type_text.lower()} gerekli

<b>📝 {task_type_text} ID veya linkini gönderin:</b>
• Örnek: @grup_adi veya https://t.me/grup_adi
• Botun {task_type_text.lower()}da admin olduğundan emin olun

<code>/cancel</code> iptal etmek için
""")
    
    def show_advertiser_deposit_menu(self, user_id):
        self.update_trx_price()
        
        message = f"""
<b>💰 REKLAMVEREN BAKİYE YÜKLEME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>₿ TRX Fiyatı:</b> {self.trx_price:.2f}₺
<b>⚠️ Not:</b> Reklamveren bakiyesi sadece reklam vermek için kullanılır

<b>👇 Yüklemek istediğiniz tutarı seçin:</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': f'50₺ Reklamveren', 'callback_data': 'deposit_amount_50_advertiser'},
                    {'text': f'100₺ Reklamveren', 'callback_data': 'deposit_amount_100_advertiser'}
                ],
                [
                    {'text': f'200₺ Reklamveren', 'callback_data': 'deposit_amount_200_advertiser'},
                    {'text': f'500₺ Reklamveren', 'callback_data': 'deposit_amount_500_advertiser'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_available_tasks(self, user_id):
        """Kullanıcılar için mevcut görevleri göster"""
        # Zorunlu kanal kontrolü
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            self.db.update_user(user_id, {'in_channel': 0})
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 Kanala Katıl', 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': '✅ Katıldım', 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, """
<b>⚠️ KANAL KONTROLÜ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>Önce kanala katılmalısınız!</b>

📢 <b>Görev yapmak için:</b>
👉 @GY_Refim

💡 <b>Katıldıktan sonra "Katıldım" butonuna basın</b>
""", markup)
            return
        
        # Aktif görevleri getir
        self.db.cursor.execute('''
            SELECT * FROM tasks 
            WHERE status = 'active' 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        tasks = self.db.cursor.fetchall()
        
        if not tasks:
            message = """
<b>🎯 MEVCUT GÖREVLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Şu anda aktif görev bulunmuyor</b>

💡 <b>Yeni görevler eklendiğinde bildirim alacaksınız!</b>
"""
            markup = {
                'inline_keyboard': [[
                    {'text': '🔙 Ana Menü', 'callback_data': 'menu'}
                ]]
            }
        else:
            message = "<b>🎯 MEVCUT GÖREVLER</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for task in tasks:
                task_type = "👥 Grup" if task['task_type'] == 'group' else "📢 Kanal"
                reward = task['reward_amount']
                
                # Kullanıcı bu göreve katılmış mı kontrol et
                self.db.cursor.execute('''
                    SELECT * FROM task_participations 
                    WHERE task_id = ? AND user_id = ?
                ''', (task['task_id'], user_id))
                participation = self.db.cursor.fetchone()
                
                status = "✅ Katıldınız" if participation else "🟢 Katıl"
                
                message += f"""{task_type} <b>{task['target_name'][:20]}</b>
├ <b>Ödül:</b> {reward:.2f}₺
├ <b>Katılımcı:</b> {task['current_participants']}/{task['max_participants']}
└ <b>Durum:</b> {status}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # İlk görev için katılma butonu
            if tasks:
                first_task = tasks[0]
                self.db.cursor.execute('''
                    SELECT * FROM task_participations 
                    WHERE task_id = ? AND user_id = ?
                ''', (first_task['task_id'], user_id))
                participation = self.db.cursor.fetchone()
                
                if not participation:
                    markup = {
                        'inline_keyboard': [
                            [
                                {'text': f'🎯 Katıl ({first_task["reward_amount"]:.2f}₺)', 
                                 'callback_data': f'join_task_{first_task["task_id"]}'}
                            ],
                            [
                                {'text': '🔙 Ana Menü', 'callback_data': 'menu'}
                            ]
                        ]
                    }
                else:
                    markup = {
                        'inline_keyboard': [[
                            {'text': '🔙 Ana Menü', 'callback_data': 'menu'}
                        ]]
                    }
        
        send_message(user_id, message, markup)
    
    def join_task(self, user_id, task_id):
        """Kullanıcı göreve katıl"""
        # Görev bilgilerini getir
        self.db.cursor.execute('''
            SELECT * FROM tasks WHERE task_id = ?
        ''', (task_id,))
        task = self.db.cursor.fetchone()
        
        if not task:
            send_message(user_id, "❌ Görev bulunamadı!")
            return
        
        # Zaten katılmış mı kontrol et
        self.db.cursor.execute('''
            SELECT * FROM task_participations 
            WHERE task_id = ? AND user_id = ?
        ''', (task_id, user_id))
        existing = self.db.cursor.fetchone()
        
        if existing:
            send_message(user_id, "❌ Zaten bu göreve katıldınız!")
            return
        
        # Kullanıcı grupta/kanalda mı kontrol et
        user = self.db.get_user(user_id)
        
        if task['task_type'] == 'group':
            if not get_chat_member(task['target_id'], user_id):
                # Gruba katılma linki göster
                markup = {
                    'inline_keyboard': [
                        [
                            {'text': '👥 Gruba Katıl', 'url': f'https://t.me/{task["target_id"].replace("@", "")}'},
                            {'text': '✅ Katıldım', 'callback_data': f'join_task_{task_id}'}
                        ]
                    ]
                }
                
                send_message(user_id, f"""
<b>👥 GRUPA KATILMA GÖREVİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 <b>Görev:</b> {task['target_name']}
💰 <b>Ödül:</b> {task['reward_amount']:.2f}₺

<b>📝 Adımlar:</b>
1. Yukarıdaki butona tıklayarak gruba katılın
2. Katıldıktan sonra "Katıldım" butonuna basın
3. Sistem otomatik olarak katılımınızı doğrulayacak
4. Ödülünüz bakiyenize eklenecek

⚠️ <b>Önemli:</b> Grubu terk ederseniz ödülünüz geri alınır!
""", markup)
                return
        else:  # channel
            if not get_chat_member(task['target_id'], user_id):
                # Kanala katılma linki göster
                markup = {
                    'inline_keyboard': [
                        [
                            {'text': '📢 Kanala Katıl', 'url': f'https://t.me/{task["target_id"].replace("@", "")}'},
                            {'text': '✅ Katıldım', 'callback_data': f'join_task_{task_id}'}
                        ]
                    ]
                }
                
                send_message(user_id, f"""
<b>📢 KANALA KATILMA GÖREVİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 <b>Görev:</b> {task['target_name']}
💰 <b>Ödül:</b> {task['reward_amount']:.2f}₺

<b>📝 Adımlar:</b>
1. Yukarıdaki butona tıklayarak kanala katılın
2. Katıldıktan sonra "Katıldım" butonuna basın
3. Sistem otomatik olarak katılımınızı doğrulayacak
4. Ödülünüz bakiyenize eklenecek

⚠️ <b>Önemli:</b> Kanalı terk ederseniz ödülünüz geri alınır!
""", markup)
                return
        
        # Kullanıcı zaten grupta/kanalda, doğrudan katılım kaydı oluştur
        success, message = self.db.join_task(task_id, user_id, user.get('name', 'Kullanıcı'))
        
        if success:
            # Reklamverene bildirim gönder
            send_message(task['advertiser_id'], f"""
<b>👤 YENİ GÖREV KATILIMI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>Yeni katılımcı!</b>

📊 <b>Detaylar:</b>
• Görev: {task['target_name']}
• Katılımcı: {user.get('name', 'Kullanıcı')}
• Ödül: {task['reward_amount']:.2f}₺
• Toplam Katılımcı: {task['current_participants'] + 1}

💡 <b>Katılımı doğrulamak için görevlerim sayfasına bakın!</b>
""")
            
            # Kullanıcıya bildirim
            send_message(user_id, f"""
<b>✅ GÖREVE KATILDINIZ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>Göreve başarıyla katıldınız!</b>

📊 <b>Detaylar:</b>
• Görev: {task['target_name']}
• Ödül: {task['reward_amount']:.2f}₺
• Durum: Doğrulama bekliyor

💡 <b>Reklamveren katılımınızı doğruladığında ödülünüz bakiyenize eklenecek!</b>

⚠️ <b>Önemli:</b> Grubu/Kanalı terk etmeyin, yoksa ödülünüz geri alınır!
""")
        else:
            send_message(user_id, f"❌ {message}")
    
    def verify_task_participation(self, user_id, participation_id):
        """Reklamveren katılımı doğrula"""
        # Katılım bilgilerini getir
        self.db.cursor.execute('''
            SELECT tp.*, t.advertiser_id, t.target_name, t.reward_amount, t.task_type
            FROM task_participations tp
            JOIN tasks t ON tp.task_id = t.task_id
            WHERE tp.participation_id = ?
        ''', (participation_id,))
        participation = self.db.cursor.fetchone()
        
        if not participation:
            send_message(user_id, "❌ Katılım bulunamadı!")
            return
        
        # Sadece reklamveren doğrulayabilir
        if str(participation['advertiser_id']) != user_id:
            send_message(user_id, "❌ Bu işlemi sadece görevin reklamvereni yapabilir!")
            return
        
        # Kullanıcı hala grupta/kanalda mı kontrol et
        task_type = participation['task_type']
        target_id = participation['target_id'] if 'target_id' in participation else ''
        
        if task_type == 'group' or task_type == 'channel':
            # Doğrudan doğrula
            success, result_message = self.db.verify_task_participation(participation_id)
            
            if success:
                # Reklamverene bildirim
                send_message(user_id, f"""
<b>✅ GÖREV DOĞRULANDI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>Görev başarıyla doğrulandı!</b>

📊 <b>Detaylar:</b>
• Katılımcı: {participation['user_name']}
• Ödül: {participation['reward_amount']:.2f}₺ ödendi
• Yeni Reklamveren Bakiye: {self.db.get_user(user_id)['advertiser_balance']:.2f}₺

💡 <b>Katılımcı ödülünü aldı!</b>
""")
            else:
                send_message(user_id, f"❌ {result_message}")
        else:
            send_message(user_id, "❌ Geçersiz görev türü!")
    
    def show_advertiser_my_tasks(self, user_id):
        """Reklamverenin görevlerini göster"""
        self.db.cursor.execute('''
            SELECT * FROM tasks 
            WHERE advertiser_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        tasks = self.db.cursor.fetchall()
        
        if not tasks:
            message = """
<b>📊 REKLAMVEREN GÖREVLERİM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Henüz göreviniz bulunmuyor</b>

💡 <b>İlk görevinizi oluşturun!</b>
"""
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '📢 Görev Oluştur', 'callback_data': 'advertiser_create_task'},
                        {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                    ]
                ]
            }
        else:
            message = "<b>📊 SON 10 GÖREVİM</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for task in tasks:
                task_type = "👥 Grup" if task['task_type'] == 'group' else "📢 Kanal"
                status = "🟢" if task['status'] == 'active' else "🟡" if task['status'] == 'pending' else "🔴"
                
                message += f"""{status} <b>{task['target_name'][:20]}</b>
├ <b>Tür:</b> {task_type}
├ <b>Ödül:</b> {task['reward_amount']:.2f}₺
├ <b>Katılım:</b> {task['current_participants']}/{task['max_participants']}
└ <b>Harcama:</b> {task['total_spent']:.2f}₺
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            # İlk görevin katılımlarını göster
            if tasks:
                first_task = tasks[0]
                self.db.cursor.execute('''
                    SELECT * FROM task_participations 
                    WHERE task_id = ? 
                    ORDER BY joined_at DESC 
                    LIMIT 5
                ''', (first_task['task_id'],))
                participations = self.db.cursor.fetchall()
                
                if participations:
                    message += f"\n<b>📋 {first_task['target_name'][:15]} Katılımları:</b>\n"
                    for part in participations:
                        status_icon = "✅" if part['status'] == 'verified' else "⏳" if part['status'] == 'pending' else "❌"
                        message += f"{status_icon} {part['user_name'][:15]} - {part['status']}\n"
                
                # Doğrulama butonları
                pending_participations = [p for p in participations if p['status'] == 'pending']
                if pending_participations:
                    buttons = []
                    for part in pending_participations[:3]:  # En fazla 3 buton
                        buttons.append([
                            {'text': f'✅ {part["user_name"][:10]}', 
                             'callback_data': f'verify_task_{part["participation_id"]}'}
                        ])
                    
                    buttons.append([
                        {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                    ])
                    
                    markup = {'inline_keyboard': buttons}
                else:
                    markup = {
                        'inline_keyboard': [[
                            {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                        ]]
                    }
        
        send_message(user_id, message, markup)
    
    def show_advertiser_payments(self, user_id):
        """Reklamveren ödemelerini göster"""
        self.db.cursor.execute('''
            SELECT * FROM advertiser_payments 
            WHERE advertiser_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        payments = self.db.cursor.fetchall()
        
        if not payments:
            message = """
<b>💳 REKLAMVEREN ÖDEMELERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Henüz ödemeniz bulunmuyor</b>

💡 <b>Görev oluşturarak ödemelerinizi takip edin!</b>
"""
        else:
            message = "<b>💳 SON 10 ÖDEME</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            total_spent = 0
            
            for payment in payments:
                status = "✅" if payment['status'] == 'completed' else "⏳" if payment['status'] == 'pending' else "❌"
                payment_type = "Görev Ödemesi" if payment['payment_type'] == 'task_payment' else "Para Çekme"
                
                if payment['status'] == 'completed':
                    total_spent += payment['amount']
                
                message += f"""{status} <b>{payment_type}</b>
├ <b>Tutar:</b> {payment['amount']:.2f}₺
├ <b>Durum:</b> {payment['status']}
└ <b>Tarih:</b> {payment['created_at'][:16]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            message += f"\n<b>💰 Toplam Harcama:</b> {total_spent:.2f}₺"
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def start_advertiser_withdraw(self, user_id):
        """Reklamveren para çekme işlemi"""
        user = self.db.get_user(user_id)
        advertiser_balance = user.get('advertiser_balance', 0)
        
        if advertiser_balance < MIN_WITHDRAW:
            message = f"""
<b>❌ YETERSİZ REKLAMVEREN BAKİYESİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Reklamveren bakiyeniz yetersiz!</b>

<b>📊 Mevcut Durum:</b>
• Reklamveren Bakiye: {advertiser_balance:.2f}₺
• Minimum Çekim: {MIN_WITHDRAW}₺

💡 <b>Not:</b> Reklamveren bakiyesi genellikle çekilemez, 
sadece reklam vermek için kullanılır. 
Özel durumlar için admin ile iletişime geçin.
"""
            
            markup = {
                'inline_keyboard': [[
                    {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
                ]]
            }
            
            send_message(user_id, message, markup)
            return
        
        message = f"""
<b>💸 REKLAMVEREN PARA ÇEKME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Mevcut Reklamveren Bakiye:</b> {advertiser_balance:.2f}₺

<b>⚠️ ÖNEMLİ UYARI:</b>
• Reklamveren bakiyesi genellikle çekilemez
• Sadece reklam vermek için kullanılır
• Özel durumlar için admin onayı gereklidir

<b>📞 İletişim:</b>
Para çekme talebi için admin ile iletişime geçin:
👉 @GorevYapsamBot
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'advertiser_menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def handle_user_state(self, user_id, message, user_state):
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # /cancel komutu
        if 'text' in message and message['text'] == '/cancel':
            self.clear_user_state(user_id)
            send_message(user_id, "🔄 İşlem iptal edildi.")
            user = self.db.get_user(user_id)
            if user.get('is_advertiser', 0):
                self.show_advertiser_menu(user_id)
            else:
                self.show_main_menu(user_id)
            return
        
        # GÖREV OLUŞTURMA
        if state == 'create_task':
            if step == 1:
                # Grup/Kanal linkini al
                target_input = message['text'].strip()
                
                # Link veya @username formatını işle
                if target_input.startswith('https://t.me/'):
                    target_id = '@' + target_input.split('/')[-1]
                elif target_input.startswith('@'):
                    target_id = target_input
                else:
                    target_id = '@' + target_input
                
                # Bot admin mi kontrol et
                if not check_bot_admin(target_id):
                    send_message(user_id, f"❌ Bot {target_id} grubunda/kanalında admin değil!")
                    self.clear_user_state(user_id)
                    self.show_advertiser_menu(user_id)
                    return
                
                # Grup/Kanal bilgilerini al
                chat_info = get_chat(target_id)
                if not chat_info:
                    send_message(user_id, f"❌ {target_id} bulunamadı veya erişilemiyor!")
                    self.clear_user_state(user_id)
                    self.show_advertiser_menu(user_id)
                    return
                
                target_name = chat_info.get('title', target_id)
                chat_type = chat_info.get('type', '')
                
                # Görev türüyle eşleşiyor mu kontrol et
                task_type = data['task_type']
                if (task_type == 'group' and chat_type not in ['group', 'supergroup']) or \
                   (task_type == 'channel' and chat_type != 'channel'):
                    send_message(user_id, f"❌ Bu bir {task_type} değil!")
                    self.clear_user_state(user_id)
                    self.show_advertiser_menu(user_id)
                    return
                
                # Veriyi güncelle
                data['target_id'] = target_id
                data['target_name'] = target_name
                data['step'] = 2
                self.set_user_state(user_id, state, data)
                
                send_message(user_id, f"""
<b>📝 GÖREV AÇIKLAMASI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>✅ {target_name} seçildi!</b>

<b>📋 Görev Bilgileri:</b>
• Tür: {'Grup' if task_type == 'group' else 'Kanal'}
• Ödül: {data['reward']:.2f}₺ her katılım
• Hedef: {target_name}

<b>📝 Görev açıklaması girin:</b>
• Katılımcıların ne yapması gerektiğini açıklayın
• Örnek: "Grubumuza katılın ve 24 saat kalın"
• Maksimum 200 karakter

<code>/cancel</code> iptal etmek için
""")
            
            elif step == 2:
                # Görev açıklamasını al
                description = message['text'].strip()
                
                if len(description) > 200:
                    send_message(user_id, "❌ Açıklama 200 karakterden uzun olamaz!")
                    return
                
                data['description'] = description
                data['step'] = 3
                self.set_user_state(user_id, state, data)
                
                send_message(user_id, f"""
<b>👥 KATILIMCI SAYISI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>✅ Açıklama kaydedildi!</b>

<b>📋 Görev Özeti:</b>
• Tür: {'Grup' if data['task_type'] == 'group' else 'Kanal'}
• Hedef: {data['target_name']}
• Ödül: {data['reward']:.2f}₺ her katılım
• Açıklama: {description[:50]}...

<b>📊 Kaç katılımcı kabul edeceksiniz?</b>
• Sadece sayı girin (örn: 10)
• Her katılımcı için {data['reward']:.2f}₺ ödeyeceksiniz
• Toplam maliyet: (katılımcı sayısı × {data['reward']:.2f}₺)

<code>/cancel</code> iptal etmek için
""")
            
            elif step == 3:
                # Katılımcı sayısını al
                try:
                    max_participants = int(message['text'].strip())
                    
                    if max_participants < 1:
                        send_message(user_id, "❌ En az 1 katılımcı gerekli!")
                        return
                    
                    if max_participants > 100:
                        send_message(user_id, "❌ Maksimum 100 katılımcı!")
                        return
                    
                    # Toplam maliyeti hesapla
                    total_cost = max_participants * data['reward']
                    user = self.db.get_user(user_id)
                    
                    if user.get('advertiser_balance', 0) < total_cost:
                        send_message(user_id, f"❌ Yetersiz bakiye! Toplam maliyet: {total_cost:.2f}₺, Mevcut: {user.get('advertiser_balance', 0):.2f}₺")
                        self.clear_user_state(user_id)
                        self.show_advertiser_menu(user_id)
                        return
                    
                    # Görevi oluştur
                    task_id = self.db.create_task(
                        user_id,
                        data['task_type'],
                        data['target_id'],
                        data['target_name'],
                        data['description'],
                        data['reward'],
                        max_participants
                    )
                    
                    # Bakiyeyi bloke et (henüz ödeme yapılmadı, sadece rezerve edildi)
                    self.db.cursor.execute('''
                        UPDATE users 
                        SET advertiser_balance = advertiser_balance - ?
                        WHERE user_id = ?
                    ''', (total_cost, user_id))
                    self.db.conn.commit()
                    
                    # Başarı mesajı
                    send_message(user_id, f"""
<b>✅ GÖREV OLUŞTURULDU!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>Göreviniz başarıyla oluşturuldu!</b>

📊 <b>Görev Detayları:</b>
• Görev ID: {task_id}
• Tür: {'Grup' if data['task_type'] == 'group' else 'Kanal'}
• Hedef: {data['target_name']}
• Ödül: {data['reward']:.2f}₺ her katılım
• Maksimum Katılımcı: {max_participants}
• Toplam Maliyet: {total_cost:.2f}₺ (bloke edildi)

💡 <b>Katılımcılar görevinize katıldıkça:</b>
1. Katılımları doğrulayın
2. Ödemeler otomatik olarak yapılır
3. Bloke edilen bakiye harcanır

📈 <b>Görevlerinizi takip etmek için "Görevlerim" butonuna tıklayın!</b>
""")
                    
                    self.clear_user_state(user_id)
                    self.show_advertiser_menu(user_id)
                    
                except ValueError:
                    send_message(user_id, "❌ Geçersiz sayı! Lütfen sadece sayı girin.")
        
        # TXID BEKLEME (Hem kullanıcı hem reklamveren)
        elif state == 'waiting_txid':
            txid = message['text'].strip()
            
            if len(txid) < 10:
                send_message(user_id, "❌ Geçersiz TXID!")
                return
            
            try:
                deposit_data = data
                deposit_id = deposit_data['deposit_id']
                amount = deposit_data['amount']
                deposit_type = deposit_data.get('deposit_type', 'user')
                
                # Depoziti tamamla
                self.db.cursor.execute('''
                    UPDATE deposits 
                    SET txid = ?, status = 'completed', completed_at = ?
                    WHERE deposit_id = ? AND user_id = ?
                ''', (txid, get_turkey_time().isoformat(), deposit_id, user_id))
                
                if deposit_type == 'advertiser':
                    # Reklamveren bakiyesine ekle
                    self.db.add_advertiser_balance(user_id, amount)
                    
                    # Başarı mesajı
                    send_message(user_id, f"""
<b>✅ REKLAMVEREN BAKİYESİ YÜKLENDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Toplam: {amount:.2f}₺</b>
• Yatırım: {amount:.2f}₺
• Yeni Reklamveren Bakiye: {self.db.get_user(user_id)['advertiser_balance']:.2f}₺

🎉 <b>Hemen reklam vermeye başlayın!</b>
""")
                else:
                    # Normal kullanıcı bakiyesine ekle
                    bonus = amount * DEPOSIT_BONUS_PERCENT / 100
                    total = amount + bonus
                    
                    user = self.db.get_user(user_id)
                    new_balance = user.get('balance', 0) + total
                    self.db.update_user(user_id, {
                        'balance': new_balance,
                        'total_deposited': user.get('total_deposited', 0) + amount,
                        'deposit_count': user.get('deposit_count', 0) + 1,
                        'total_bonus': user.get('total_bonus', 0) + bonus
                    })
                    
                    # Referans komisyonu
                    ref_commission = 0
                    if user.get('referred_by'):
                        ref_commission = amount * 0.10  # %10 komisyon
                        referrer = self.db.get_user(user['referred_by'])
                        if referrer:
                            self.db.add_balance(user['referred_by'], ref_commission, 0, "referral_deposit")
                            
                            # Referans komisyonu kaydı
                            referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user['referred_by']}"
                            log_id = self.db.record_referral(user['referred_by'], user_id, referral_link, ref_commission)
                            self.db.complete_referral(log_id, "referral_deposit")
                    
                    # Başarı mesajı
                    ref_message = f"\n👥 <b>Referans Komisyonu:</b> {ref_commission:.2f}₺ (referans sahibine ödendi)" if ref_commission > 0 else ""
                    
                    send_message(user_id, f"""
<b>✅ BAKİYE YÜKLENDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Toplam: {total:.2f}₺</b>
• Yatırım: {amount:.2f}₺
• Bonus: {bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT}){ref_message}
• Yeni Bakiye: {new_balance:.2f}₺

🎉 <b>Hemen görev yapmaya başlayın!</b>
""")
                
                self.db.conn.commit()
                self.clear_user_state(user_id)
                time.sleep(2)
                
                user = self.db.get_user(user_id)
                if user.get('is_advertiser', 0) and deposit_type == 'advertiser':
                    self.show_advertiser_menu(user_id)
                else:
                    self.show_main_menu(user_id)
                
            except Exception as e:
                print(f"❌ TXID hatası: {e}")
                send_message(user_id, "❌ İşlem kaydedilemedi!")
    
    def start_deposit(self, user_id, amount, deposit_type='user'):
        """Depozit işlemi başlat"""
        trx_amount = amount / self.trx_price
        
        if deposit_type == 'advertiser':
            message = f"""
<b>💰 REKLAMVEREN BAKİYE YÜKLEME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Ödeme Detayları:</b>
• Seçilen Tutar: {amount:.2f}₺
• <b>Toplam Alacak: {amount:.2f}₺</b>

<b>₿ TRX Bilgileri:</b>
• Gerekli TRX: {trx_amount:.4f} TRX
• TRX Fiyatı: {self.trx_price:.2f}₺

<b>🔗 TRX Adresi:</b>
<code>{TRX_ADDRESS}</code>

<b>📝 ADIMLAR:</b>
1. Yukarıdaki TRX adresini kopyalayın
2. Cüzdanınızdan <b>{trx_amount:.4f} TRX</b> gönderin
3. İşlem tamamlandığında TXID'yi bota gönderin
4. <b>{amount:.2f}₺</b> reklamveren bakiyenize otomatik yüklenecek

<code>/cancel</code> iptal etmek için
"""
        else:
            bonus = amount * DEPOSIT_BONUS_PERCENT / 100
            total = amount + bonus
            
            message = f"""
<b>💰 BAKİYE YÜKLEME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Ödeme Detayları:</b>
• Seçilen Tutar: {amount:.2f}₺
• Bonus (%{DEPOSIT_BONUS_PERCENT}): {bonus:.2f}₺
• <b>Toplam Alacak: {total:.2f}₺</b>

<b>₿ TRX Bilgileri:</b>
• Gerekli TRX: {trx_amount:.4f} TRX
• TRX Fiyatı: {self.trx_price:.2f}₺

<b>🔗 TRX Adresi:</b>
<code>{TRX_ADDRESS}</code>

<b>📝 ADIMLAR:</b>
1. Yukarıdaki TRX adresini kopyalayın
2. Cüzdanınızdan <b>{trx_amount:.4f} TRX</b> gönderin
3. İşlem tamamlandığında TXID'yi bota gönderin
4. <b>{total:.2f}₺</b> bakiyenize otomatik yüklenecek

<code>/cancel</code> iptal etmek için
"""
        
        deposit_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        try:
            bonus_amount = amount * DEPOSIT_BONUS_PERCENT / 100 if deposit_type == 'user' else 0
            
            self.db.cursor.execute('''
                INSERT INTO deposits (deposit_id, user_id, amount_try, amount_trx, created_at, trx_price, bonus_amount, deposit_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (deposit_id, user_id, amount, trx_amount, get_turkey_time().isoformat(), self.trx_price, bonus_amount, deposit_type))
            self.db.conn.commit()
            
            self.set_user_state(user_id, 'waiting_txid', {
                'deposit_id': deposit_id, 
                'amount': amount,
                'deposit_type': deposit_type
            })
            send_message(user_id, message)
            
        except Exception as e:
            print(f"❌ Depozit hatası: {e}")
            send_message(user_id, "❌ Depozit oluşturulamadı!")
    
    def show_deposit_menu(self, user_id):
        """Normal kullanıcı depozit menüsü"""
        self.update_trx_price()
        
        message = f"""
<b>💰 BAKİYE YÜKLEME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>₿ TRX Fiyatı:</b> {self.trx_price:.2f}₺
<b>🎁 Bonus Oranı:</b> %{DEPOSIT_BONUS_PERCENT}

<b>👇 Yüklemek istediğiniz tutarı seçin:</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': f'25₺ → {25 * (1 + DEPOSIT_BONUS_PERCENT/100):.2f}₺', 'callback_data': 'deposit_amount_25_user'},
                    {'text': f'50₺ → {50 * (1 + DEPOSIT_BONUS_PERCENT/100):.2f}₺', 'callback_data': 'deposit_amount_50_user'}
                ],
                [
                    {'text': f'100₺ → {100 * (1 + DEPOSIT_BONUS_PERCENT/100):.2f}₺', 'callback_data': 'deposit_amount_100_user'},
                    {'text': f'200₺ → {200 * (1 + DEPOSIT_BONUS_PERCENT/100):.2f}₺', 'callback_data': 'deposit_amount_200_user'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_withdraw_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>🏧 PARA ÇEKME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Mevcut Bakiye:</b> {user.get('balance', 0):.2f}₺

<b>📋 Şartlar:</b>
• Minimum çekim: {MIN_WITHDRAW}₺
• İşlem süresi: 24 saat
• Komisyon: Yok

<b>⚠️ ÖNEMLİ:</b>
• Sadece TRX (Tron) cüzdan adresi kabul edilir!
• Yanlış cüzdan adresi girerseniz para kaybolur!
"""
        
        if user.get('balance', 0) >= MIN_WITHDRAW:
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '💸 Çekim Yap', 'callback_data': 'withdraw'},
                        {'text': '🔙 Geri', 'callback_data': 'menu'}
                    ]
                ]
            }
        else:
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'},
                        {'text': '🔙 Geri', 'callback_data': 'menu'}
                    ]
                ]
            }
        
        send_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        user = self.db.get_user(user_id)
        
        # Referans durumu
        ref_status = "✅" if user.get('is_referred') else "❌"
        ref_info = ""
        if user.get('is_referred'):
            ref_info = f"\n<b>👥 Referans Durumu:</b> Referans ile kayıt oldu"
            if user.get('referred_by'):
                ref_info += f"\n<b>👤 Davet Eden:</b> Kullanıcı ID: {user['referred_by']}"
        
        # Reklamveren durumu
        advertiser_status = "✅ Aktif" if user.get('is_advertiser') else "❌ Kapalı"
        advertiser_info = ""
        if user.get('is_advertiser'):
            advertiser_info = f"""
<b>👑 Reklamveren Bilgileri:</b>
• Reklamveren Bakiye: {user.get('advertiser_balance', 0):.2f}₺
• Toplam Harcama: {user.get('total_spent_on_ads', 0):.2f}₺
"""
        
        message = f"""
<b>👤 PROFİL BİLGİLERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 İsim:</b> {user.get('name', 'Kullanıcı')}
<b>🆔 Kullanıcı ID:</b> <code>{user_id}</code>
<b>🔗 Referans Durumu:</b> {ref_status}{ref_info}
<b>👑 Reklamveren:</b> {advertiser_status}{advertiser_info}

<b>💰 Finansal Durum:</b>
• Normal Bakiye: {user.get('balance', 0):.2f}₺
• Toplam Kazanç: {user.get('total_earned', 0):.2f}₺

<b>📊 İstatistikler:</b>
• Tamamlanan Görev: {user.get('tasks_completed', 0)}
• Referans Sayısı: {user.get('referrals', 0)}
• Referans Kazancı: {user.get('ref_earned', 0):.2f}₺

<b>💳 İşlemler:</b>
• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺
• Toplam Bonus: {user.get('total_bonus', 0):.2f}₺
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'},
                    {'text': '🏧 Para Çek', 'callback_data': 'withdraw'}
                ],
                [
                    {'text': '👥 Referans', 'callback_data': 'referral'},
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        # Reklamveren butonu
        if user.get('is_advertiser'):
            markup['inline_keyboard'].insert(1, [
                {'text': '👑 Reklamveren', 'callback_data': 'advertiser_menu'}
            ])
        
        send_message(user_id, message, markup)
    
    def show_referral_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        # Referans istatistiklerini getir
        self.db.cursor.execute('''
            SELECT COUNT(*) as total_refs, 
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_refs,
                   SUM(amount) as total_earned
            FROM referral_logs 
            WHERE referrer_id = ?
        ''', (user_id,))
        ref_stats = self.db.cursor.fetchone()
        
        total_refs = ref_stats['total_refs'] if ref_stats else 0
        completed_refs = ref_stats['completed_refs'] if ref_stats else 0
        total_earned = ref_stats['total_earned'] if ref_stats and ref_stats['total_earned'] else 0
        
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = f"""
<b>👥 REFERANS SİSTEMİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Referans İstatistikleri:</b>
• Toplam Referans: {total_refs}
• Başarılı Referans: {completed_refs}
• Referans Kazancı: {total_earned:.2f}₺

<b>💰 Kazanç Sistemi:</b>
• <b>İlk kayıt referansı:</b> 1₺ bonus
• <b>Geç katılım referansı:</b> 0.5₺ bonus
• <b>Depozit referansı:</b> %10 komisyon

<b>🔗 Referans Linkiniz:</b>
<code>{referral_link}</code>

<b>💡 Nasıl Çalışır:</b>
1. Linkinizi arkadaşlarınızla paylaşın
2. Arkadaşlarınız linke tıklayarak kaydolur
3. <b>Hemen 1₺ bonus</b> alırsınız
4. Arkadaşınız depozit yaparsa <b>%10 komisyon</b> alırsınız
5. Sınırsız kazanç fırsatı!
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📋 Linki Kopyala', 'callback_data': 'referral_copy'},
                    {'text': '📤 Paylaş', 'callback_data': 'referral_share'}
                ],
                [
                    {'text': '📊 Detaylı Rapor', 'callback_data': 'referral_details'},
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def copy_referral_link(self, user_id):
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        send_message(user_id, f"""
<b>🔗 REFERANS LİNKİNİZ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<code>{referral_link}</code>

📋 <b>Yukarıdaki linki kopyalayın ve paylaşın!</b>

💡 <b>Paylaşım Önerileri:</b>
• WhatsApp grupları
• Telegram grupları
• Sosyal medya
• Arkadaşlarınıza özel mesaj
""")
    
    def share_referral_link(self, user_id):
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📱 WhatsApp', 'url': f'https://wa.me/?text=Görev Yapsam Bot ile para kazanın! {referral_link}'},
                    {'text': '✈️ Telegram', 'url': f'https://t.me/share/url?url={referral_link}&text=Görev Yapsam Bot ile para kazanın!'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'referral'}
                ]
            ]
        }
        
        send_message(user_id, """
<b>📤 REFERANS LİNKİ PAYLAŞ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 <b>Aşağıdaki butonlardan birine tıklayarak paylaşabilirsiniz:</b>
""", markup)
    
    def show_referral_details(self, user_id):
        user = self.db.get_user(user_id)
        
        self.db.cursor.execute('''
            SELECT * FROM referral_logs 
            WHERE referrer_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        ref_logs = self.db.cursor.fetchall()
        
        if not ref_logs:
            message = """
<b>📊 REFERANS DETAYLARI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Henüz referans kaydınız bulunmuyor</b>

💡 <b>Referans linkinizi paylaşarak kazanmaya başlayın!</b>
"""
        else:
            message = "<b>📊 SON 10 REFERANS KAYDI</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            total_earned = 0
            
            for log in ref_logs:
                status = "✅" if log['status'] == 'completed' else "⏳" if log['status'] == 'pending' else "❌"
                reward_type = {
                    'welcome': 'Hoşgeldin',
                    'late_join': 'Geç Katılım',
                    'referral_deposit': 'Depozit Komisyonu'
                }.get(log['reward_type'], log['reward_type'] or 'Bilinmiyor')
                
                if log['status'] == 'completed':
                    total_earned += log['amount'] or 0
                
                message += f"""{status} <b>Referans #{log['log_id']}</b>
├ <b>Tür:</b> {reward_type}
├ <b>Tutar:</b> {log['amount']:.2f}₺
├ <b>Durum:</b> {log['status']}
└ <b>Tarih:</b> {log['created_at'][:16]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            message += f"\n<b>💰 Toplam Kazanç:</b> {total_earned:.2f}₺"
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'referral'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        message = """
<b>❓ YARDIM VE DESTEK</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 BOT NASIL ÇALIŞIR?</b>
1. 📢 Kanalımıza katılın (@GY_Refim)
2. 🎯 Görev yapın veya 📢 reklam verin
3. 💰 Para kazanmaya başlayın!

<b>🎯 GÖREV YAPMA:</b>
1. "🎯 Görev Yap" butonuna tıklayın
2. Mevcut görevleri görün
3. Göreve katılın
4. Gruba/Kanala katılın
5. Reklamveren katılımınızı doğrulasın
6. Ödülünüz bakiyenize yüklensin

<b>📢 REKLAM VERME:</b>
1. "👑 Reklamveren Ol" butonuna tıklayın
2. "💰 Bakiye Yükle" ile reklamveren bakiyesi yükleyin
3. "📢 Görev Oluştur" ile görev oluşturun
4. Katılımcıların katılımını doğrulayın
5. Ödemeler otomatik olarak yapılsın

<b>⚠️ ÖNEMLİ UYARILAR:</b>
• Grubu/Kanalı terk ederseniz ödülünüz geri alınır!
• Zorunlu kanaldan ayrılırsanız botu kullanamazsınız!
• Reklamveren bakiyesi sadece reklam vermek içindir!

<b>📞 DESTEK:</b>
Sorularınız için @GorevYapsamBot yazın.
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, "❌ Yetkiniz yok!")
            return
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users WHERE is_advertiser = 1")
        total_advertisers = self.db.cursor.fetchone()[0]
        
        message = f"""
<b>👑 ADMIN PANELİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 SİSTEM İSTATİSTİKLERİ</b>
• 👥 Toplam Kullanıcı: {total_users}
• 📢 Reklamverenler: {total_advertisers}

<b>🛠️ YÖNETİM ARAÇLARI</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📊 İstatistik', 'callback_data': 'admin_stats'},
                    {'text': '👥 Kullanıcılar', 'callback_data': 'admin_users'}
                ],
                [
                    {'text': '📢 Reklamverenler', 'callback_data': 'admin_advertisers'},
                    {'text': '💰 Depozitler', 'callback_data': 'admin_deposits'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_stats(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users WHERE is_advertiser = 1")
        total_advertisers = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM deposits WHERE status = 'completed'")
        total_deposits = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM referral_logs")
        total_referrals = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(amount_try) FROM deposits WHERE status = 'completed'")
        total_deposit_amount = self.db.cursor.fetchone()[0] or 0
        
        message = f"""
<b>📊 DETAYLI İSTATİSTİKLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👥 KULLANICI İSTATİSTİKLERİ</b>
• Toplam Kullanıcı: {total_users}
• Reklamverenler: {total_advertisers}

<b>💰 FİNANSAL İSTATİSTİKLER</b>
• Toplam Yatırım Sayısı: {total_deposits}
• Toplam Yatırım Tutarı: {total_deposit_amount:.2f}₺

<b>📢 GÖREV İSTATİSTİKLERİ</b>
• Toplam Görev: {total_tasks}

<b>👥 REFERANS İSTATİSTİKLERİ</b>
• Toplam Referans Kaydı: {total_referrals}

<b>⏰ SİSTEM DURUMU:</b> ✅ ÇALIŞIYOR
<b>🔄 SON KONTROL:</b> {get_turkey_time().strftime('%H:%M')}
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def show_admin_advertisers(self, user_id):
        if user_id != ADMIN_ID:
            return
        
        self.db.cursor.execute('''
            SELECT * FROM users 
            WHERE is_advertiser = 1 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        advertisers = self.db.cursor.fetchall()
        
        if not advertisers:
            message = "📢 <b>Henüz reklamveren bulunmuyor</b>"
        else:
            message = "<b>📢 SON 10 REKLAMVEREN</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for adv in advertisers:
                message += f"""👤 <b>{adv['name'][:15]}</b>
├ <b>Reklam Bakiyesi:</b> {adv['advertiser_balance']:.1f}₺
├ <b>Toplam Harcama:</b> {adv['total_spent_on_ads']:.1f}₺
└ <b>Kayıt:</b> {adv['created_at'][:10]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
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
            message = "📭 <b>Hiç kampanya bulunamadı</b>"
        else:
            message = "<b>📢 SON 10 KAMPANYA</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""{status} <b>{camp['name'][:20]}</b>
├ <b>Tür:</b> {camp['task_type']}
├ <b>Durum:</b> {camp['status']}
└ <b>Oluşturan:</b> {camp['creator_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
            ]}
        ]
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
            message = "👥 <b>Hiç kullanıcı bulunamadı</b>"
        else:
            message = "<b>👥 SON 10 KULLANICI</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for usr in users:
                referred = "✅" if usr['referred_by'] else "❌"
                advertiser = "👑" if usr['is_advertiser'] else "👤"
                message += f"""{advertiser} <b>{usr['name'][:15]}</b>
├ <b>Bakiye:</b> {usr['balance']:.1f}₺
├ <b>Referans:</b> {usr['referrals']} {referred}
├ <b>Reklamveren:</b> {'Evet' if usr['is_advertiser'] else 'Hayır'}
└ <b>Kayıt:</b> {usr['created_at'][:10]}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
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
            message = "💰 <b>Hiç depozit bulunamadı</b>"
        else:
            message = "<b>💰 SON 10 DEPOZİT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for dep in deposits:
                status = "✅" if dep['status'] == 'completed' else "⏳" if dep['status'] == 'pending' else "❌"
                deposit_type = "👑 Reklamveren" if dep['deposit_type'] == 'advertiser' else "👤 Normal"
                message += f"""{status} <b>Depozit #{dep['deposit_id'][:8]}</b>
├ <b>Tutar:</b> {dep['amount_try']:.2f}₺
├ <b>Bonus:</b> {dep['bonus_amount']:.2f}₺
├ <b>Tür:</b> {deposit_type}
└ <b>Durum:</b> {dep['status']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)

# Arka Plan Kontrol Sistemi
class BackgroundChecker:
    def __init__(self, db):
        self.db = db
        self.running = False
    
    def start(self):
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()
        print("🔄 Arka plan kontrol sistemi başlatıldı")
    
    def stop(self):
        self.running = False
    
    def run(self):
        while self.running:
            try:
                self.check_channel_memberships()
                time.sleep(60)  # Her 60 saniyede bir kontrol et
            except Exception as e:
                print(f"❌ Arka plan kontrol hatası: {e}")
                time.sleep(30)
    
    def check_channel_memberships(self):
        """Kullanıcıların zorunlu kanal üyeliklerini kontrol et"""
        try:
            # Son 24 saatte aktif olan kullanıcıları getir
            twenty_four_hours_ago = (get_turkey_time() - timedelta(hours=24)).isoformat()
            
            self.db.cursor.execute('''
                SELECT user_id, name, in_channel, last_join_check 
                FROM users 
                WHERE last_active > ? OR last_join_check IS NULL OR last_join_check < ?
            ''', (twenty_four_hours_ago, twenty_four_hours_ago))
            
            users = self.db.cursor.fetchall()
            
            for user in users:
                user_id = user['user_id']
                
                # Kanal üyeliğini kontrol et
                is_member = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
                current_status = user['in_channel']
                
                if is_member and current_status == 0:
                    # Kullanıcı kanala katılmış
                    self.db.update_user(user_id, {
                        'in_channel': 1,
                        'last_join_check': get_turkey_time().isoformat()
                    })
                    print(f"✅ {user_id} kullanıcısı kanala katıldı")
                
                elif not is_member and current_status == 1:
                    # Kullanıcı kanaldan ayrılmış
                    self.db.update_user(user_id, {
                        'in_channel': 0,
                        'last_join_check': get_turkey_time().isoformat()
                    })
                    
                    # Kullanıcıya bildirim gönder
                    send_message(user_id, """
<b>⚠️ ZORUNLU KANALDAN AYRILDINIZ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ <b>@GY_Refim kanalından ayrıldınız!</b>

📊 <b>Sonuçlar:</b>
• Botu kullanamazsınız
• Mevcut görevleriniz iptal edilebilir
• Kazançlarınız düşülebilir

💡 <b>Tekrar katılmak için:</b>
1. @GY_Refim kanalına katılın
2. /start yazarak botu yeniden başlatın
""")
                    
                    print(f"⚠️ {user_id} kullanıcısı kanaldan ayrıldı")
            
            self.db.conn.commit()
            
        except Exception as e:
            print(f"❌ Kanal kontrol hatası: {e}")

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v20.0                      ║
    ║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAMVEREN SİSTEMİ           ║
    ║   + GRUP/KANAL TERK CEZASI + ZORUNLU KANAL KONTROLÜ           ║
    ║   + REFERANS SİSTEMİ + ADMIN PANEL + SQLITE                   ║
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
    print("🎁 Bonuslar: %35 Normal Depozit")
    print("👥 Referans Bonusu: 1₺ her davet")
    print("📢 Görev Ücretleri: Grup 0.5₺, Kanal 1.25₺")
    print("⚠️ Terk Cezası: Grubu/Kanalı terk edenler ödülü kaybeder")
    print("🎯 Reklamveren Sistemi: Aktif")
    print("🔄 Arka Plan Kontrol: Aktif")
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
