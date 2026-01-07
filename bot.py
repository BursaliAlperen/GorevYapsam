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
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v17.0"})

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
            
            # Admin'e bildirim
            self.send_new_user_notification(user_id)
            
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        
        return dict(user) if user else {}
    
    def send_new_user_notification(self, new_user_id):
        """Admin'e yeni kullanıcı bildirimi"""
        try:
            new_user = self.get_user(new_user_id)
            self.cursor.execute("SELECT COUNT(*) as total FROM users")
            total_result = self.cursor.fetchone()
            total_users = total_result['total'] if total_result else 0
            
            referred_by = new_user.get('referred_by', '')
            if referred_by:
                referral_type = f"Referans ile (ID: {referred_by})"
            else:
                referral_type = "Normal giriş"
            
            send_message(ADMIN_ID, f"""
👤 <b>YENİ KULLANICI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 <b>Kullanıcı:</b> {new_user.get('name', 'Yok')}
🆔 <b>ID:</b> <code>{new_user_id}</code>
📊 <b>Kayıt Türü:</b> {referral_type}

📈 <b>Toplam Kullanıcı:</b> {total_users}
⏰ <b>Zaman:</b> {new_user.get('created_at', 'Bilinmiyor')[:19]}
""")
        except:
            pass
    
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
        
        # Bildirim
        if amount > 0:
            source_text = "sistem" if source == "system" else "referans"
            message = f"""
<b>💰 BAKİYE EKLENDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>+{total:.2f}₺ eklendi!</b>
• Kaynak: {source_text}
• Tutar: {amount:.2f}₺
• Bonus: {bonus:.2f}₺
• Yeni Bakiye: {new_balance:.2f}₺

💡 <b>Hemen görev yap!</b>
"""
            send_message(user_id, message)
        
        return True

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
    except: pass
    return False

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
            
            # State kontrolü
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
        
        except Exception as e:
            print(f"❌ Mesaj hatası: {e}")
    
    def process_callback(self, callback):
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            answer_callback(callback_id)
            
            # Ana butonlar
            if data == 'menu':
                self.show_main_menu(user_id)
            elif data == 'back':
                self.show_main_menu(user_id)
            
            # Menü butonları
            elif data == 'tasks':
                self.show_active_tasks(user_id)
            elif data == 'create_campaign':
                self.start_campaign_type_selection(user_id)
            elif data == 'my_campaigns':
                self.show_my_campaigns(user_id)
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
            
            # Kampanya tipi
            elif data.startswith('camp_type_'):
                task_type = data.replace('camp_type_', '')
                self.start_campaign_creation(user_id, task_type)
            
            # Depozit tutarları
            elif data.startswith('deposit_amount_'):
                amount = float(data.replace('deposit_amount_', ''))
                self.start_deposit(user_id, amount)
            
            # Referans butonları
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

📢 <b>Kullanmak için kanala katılın:</b>
👉 @GY_Refim

💡 <b>Sonra "Katıldım" butonuna basın</b>
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
                        # Referans ile kaydol
                        self.db.update_user(user_id, {'referred_by': referrer_id})
                        
                        # Bonus ekle
                        self.db.add_balance(referrer_id, 1.0, 0, "referral")
                        self.db.update_user(referrer_id, {
                            'referrals': referrer.get('referrals', 0) + 1,
                            'ref_earned': referrer.get('ref_earned', 0) + 1.0
                        })
                        
                        # Bildirim gönder
                        send_message(referrer_id, f"""
<b>🎉 REFERANS KAZANCI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Yeni referans:</b> {user.get('name', 'Kullanıcı')}
💰 <b>Kazandınız:</b> 1.00₺
📊 <b>Toplam referans:</b> {referrer.get('referrals', 0) + 1}
""")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        current_time = get_turkey_time().strftime('%H:%M')
        
        message = f"""
<b>🤖 GÖREV YAPSAM BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 Kullanıcı:</b> {user.get('name', 'Kullanıcı')}
<b>💰 Bakiye:</b> <code>{user.get('balance', 0):.2f}₺</code>
<b>🎯 Görev:</b> {user.get('tasks_completed', 0)}
<b>👥 Referans:</b> {user.get('referrals', 0)}

<b>⏰ Saat:</b> {current_time} 🇹🇷
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 ANA MENÜ</b>
"""
        
        # Yan yana butonlar (2'li sıralar)
        markup = {
            'inline_keyboard': [
                [
                    {'text': '🎯 Görev Yap', 'callback_data': 'tasks'},
                    {'text': '📢 Kampanya', 'callback_data': 'create_campaign'}
                ],
                [
                    {'text': '💰 Bakiye', 'callback_data': 'deposit'},
                    {'text': '🏧 Çekim', 'callback_data': 'withdraw'}
                ],
                [
                    {'text': '👤 Profil', 'callback_data': 'profile'},
                    {'text': '👥 Referans', 'callback_data': 'referral'}
                ],
                [
                    {'text': '🤖 Bot Bilgi', 'callback_data': 'help'},
                    {'text': '📋 Menü', 'callback_data': 'menu'}
                ]
            ]
        }
        
        # Admin butonu (tek başına)
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([
                {'text': '👑 Admin Panel', 'callback_data': 'admin_panel'}
            ])
        
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
            message = """
<b>🎯 AKTİF GÖREVLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Şu anda aktif görev yok</b>

💡 <b>Kendi kampanyanızı oluşturun!</b>
"""
        else:
            message = """
<b>🎯 AKTİF GÖREVLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            for camp in campaigns:
                task_type = "🤖" if camp['task_type'] == 'bot' else "📢" if camp['task_type'] == 'channel' else "👥"
                message += f"""
{task_type} <b>{camp['name'][:25]}</b>
├ <b>Ödül:</b> {camp['price_per_task']}₺
├ <b>Kalan:</b> {int(camp['remaining_budget'] / camp['price_per_task'])} kişi
└ <b>ID:</b> <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        message = """
<b>📢 KAMPANYA OLUŞTUR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👇 TİP SEÇİN</b>

🤖 <b>BOT KAMPANYASI</b>
• Görev: Bot mesajı iletme
• Ödül: 2.5₺ her katılım
• Durum: Otomatik aktif

📢 <b>KANAL KAMPANYASI</b>
• Görev: Kanala katılma
• Ödül: 1.5₺ her katılım
• Durum: Bot admin olmalı

👥 <b>GRUP KAMPANYASI</b>
• Görev: Gruba katılma
• Ödül: 1₺ her katılım
• Durum: Bot admin olmalı
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '🤖 Bot Kampanyası', 'callback_data': 'camp_type_bot'},
                    {'text': '📢 Kanal Kampanyası', 'callback_data': 'camp_type_channel'}
                ],
                [
                    {'text': '👥 Grup Kampanyası', 'callback_data': 'camp_type_group'},
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        if task_type == 'bot':
            self.set_user_state(user_id, 'forward_message', {'task_type': task_type, 'step': 1})
            send_message(user_id, """
<b>🤖 BOT KAMPANYASI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 1/6</b>
<b>🤖 Bot mesajı iletin</b>

• <b>Herhangi bir bot mesajı iletin</b>
• Örnek: @BotFather, @like, @vid, @gamebot
• Sistem otomatik algılayacak

<code>/cancel</code> iptal etmek için
""")
        else:
            self.set_user_state(user_id, 'creating_campaign', {'task_type': task_type, 'step': 1})
            type_name = "Kanal" if task_type == 'channel' else "Grup"
            send_message(user_id, f"""
<b>📢 {type_name.upper()} KAMPANYASI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 1/5</b>
<b>📛 Kampanya ismi girin</b>

<i>Örnek isimler:</i>
• Kanalımıza katılın
• YouTube abone ol
• Instagram takip et

<code>/cancel</code> iptal etmek için
""")
    
    def handle_user_state(self, user_id, message, user_state):
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # /cancel komutu
        if 'text' in message and message['text'] == '/cancel':
            self.clear_user_state(user_id)
            send_message(user_id, "🔄 İşlem iptal edildi")
            self.show_main_menu(user_id)
            return
        
        # BOT MESAJ İLETME (1/6)
        if state == 'forward_message':
            if 'forward_from' in message:
                if message['forward_from'].get('is_bot', False):
                    bot_name = message['forward_from'].get('first_name', 'Bot')
                    username = message['forward_from'].get('username', '')
                    
                    data['forward_from_bot_id'] = str(message['forward_from']['id'])
                    data['forward_from_bot_name'] = f"{bot_name} (@{username})" if username else bot_name
                    data['forward_message_id'] = message['message_id']
                    
                    # Mesaj içeriği
                    msg_text = message.get('text', '') or message.get('caption', '') or ''
                    data['forward_message_text'] = msg_text[:100] + '...' if len(msg_text) > 100 else msg_text
                    
                    user_state['step'] = 2
                    send_message(user_id, f"""
<b>✅ Bot mesajı alındı!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 Bot:</b> {data['forward_from_bot_name']}
<b>📝 Mesaj:</b> {data['forward_message_text'][:50]}...

<b>📌 ADIM 2/6</b>
<b>📛 Kampanya ismi girin</b>

<i>Örnek: Kanalımıza katılın</i>
""")
                else:
                    send_message(user_id, """
<b>❌ Sadece BOT mesajı iletin!</b>

⚠️ Normal kullanıcı mesajı iletmeyin

<b>Doğru adımlar:</b>
1. Bir bot bulun (@BotFather gibi)
2. Botun mesajını seçin
3. İletin (forward) butonuna basın
4. Bu botu seçin

<code>/cancel</code> iptal etmek için
""")
        
        # KAMPANYA OLUŞTURMA
        elif state == 'creating_campaign':
            task_type = data['task_type']
            
            if step == 1:  # İsim
                data['name'] = message['text']
                user_state['step'] = 2
                type_name = "Kanal" if task_type == 'channel' else "Grup"
                send_message(user_id, f"""
<b>✅ İsim kaydedildi</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 İsim:</b> {data['name']}

<b>📌 ADIM 2/5</b>
<b>📄 Açıklama girin</b>

<i>Örnek: Resmi kanalımıza katılın</i>
""")
            
            elif step == 2:  # Açıklama
                data['description'] = message['text']
                user_state['step'] = 3
                send_message(user_id, f"""
<b>✅ Açıklama kaydedildi</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 3/5</b>
<b>🔗 Link girin</b>

<i>Örnek: https://t.me/kanaladi</i>
""")
            
            elif step == 3:  # Link
                data['link'] = message['text']
                user_state['step'] = 4
                type_name = "Kanal" if task_type == 'channel' else "Grup"
                send_message(user_id, f"""
<b>✅ Link kaydedildi</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 4/5</b>
<b>📢 {type_name} girin</b>

<i>Format: @kanaladi veya https://t.me/kanaladi</i>
""")
            
            elif step == 4:  # Kanal/Grup
                chat_input = message['text'].strip()
                
                # Format kontrolü
                if not chat_input.startswith('@') and not chat_input.startswith('https://t.me/'):
                    send_message(user_id, "❌ Geçersiz format! @ ile başlamalı veya link olmalı")
                    return
                
                # Linkten @ çıkar
                if chat_input.startswith('https://t.me/'):
                    chat_input = '@' + chat_input.split('/')[-1]
                
                # Bot admin kontrolü (ZORUNLU)
                try:
                    chat_info = get_chat_info(chat_input)
                    if not chat_info:
                        send_message(user_id, "❌ Kanal/Grup bulunamadı!")
                        return
                    
                    is_bot_admin = check_bot_admin(chat_info['id'])
                    data['target_chat_id'] = str(chat_info['id'])
                    data['target_chat_name'] = chat_info.get('title', chat_input)
                    data['is_bot_admin'] = 1 if is_bot_admin else 0
                    
                    user_state['step'] = 5
                    
                    if not is_bot_admin:
                        type_name = "kanalda" if task_type == 'channel' else "grupta"
                        send_message(user_id, f"""
<b>⚠️ BOT ADMIN DEĞİL!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>{type_name.upper()}:</b> {data['target_chat_name']}

<b>❌ Bot bu {type_name} admin değil!</b>
<b>✅ Kampanya oluşturmak için:</b>
1. {type_name} ayarlara gidin
2. Yöneticiler bölümüne girin
3. @GorevYapsamBot ekleyin
4. TÜM yetkileri verin
5. Özellikle "Üyeleri gör" yetkisi

<b>Admin yaptıktan sonra devam edin</b>
""")
                        return
                    
                    send_message(user_id, f"""
<b>✅ {type_name.upper()} kaydedildi</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📢 {type_name}:</b> {data['target_chat_name']}
<b>👑 Bot Durumu:</b> ✅ ADMIN

<b>📌 ADIM 5/5</b>
<b>💰 Bütçe girin (₺)</b>

<i>Minimum: 10₺</i>
<i>Örnek: 50</i>
""")
                    
                except Exception as e:
                    send_message(user_id, f"❌ Hata: {str(e)}")
            
            elif step == 5:  # Bütçe
                try:
                    budget = float(message['text'])
                    if budget < 10:
                        send_message(user_id, "❌ Minimum bütçe 10₺!")
                        return
                    
                    data['budget'] = budget
                    
                    # Kampanya özeti göster
                    self.show_campaign_summary(user_id, data)
                    
                except:
                    send_message(user_id, "❌ Geçersiz bütçe! Sayı girin")
        
        # TXID BEKLEME
        elif state == 'waiting_txid':
            txid = message['text'].strip()
            deposit_data = data
            
            if len(txid) < 10:
                send_message(user_id, "❌ Geçersiz TXID!")
                return
            
            try:
                # Depoziti tamamla
                self.db.cursor.execute('''
                    UPDATE deposits 
                    SET txid = ?, status = 'completed', completed_at = ?
                    WHERE deposit_id = ? AND user_id = ?
                ''', (txid, get_turkey_time().isoformat(), deposit_data['deposit_id'], user_id))
                
                # Bakiye ekle
                user = self.db.get_user(user_id)
                amount = deposit_data['amount']
                bonus = deposit_data['bonus']
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
<b>✅ BAKİYE YÜKLENDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Toplam:</b> {amount + bonus:.2f}₺
• Yatırım: {amount:.2f}₺
• Bonus: {bonus:.2f}₺
• Yeni Bakiye: {new_balance:.2f}₺

🎉 <b>Hemen görev yap!</b>
""")
                
                self.clear_user_state(user_id)
                time.sleep(2)
                self.show_main_menu(user_id)
                
            except Exception as e:
                print(f"❌ TXID hatası: {e}")
                send_message(user_id, "❌ İşlem hatası!")
    
    def show_campaign_summary(self, user_id, data):
        task_type = data['task_type']
        type_name = "Bot" if task_type == 'bot' else "Kanal" if task_type == 'channel' else "Grup"
        price = 2.5 if task_type == 'bot' else 1.5 if task_type == 'channel' else 1.0
        budget = data['budget']
        max_participants = int(budget / price)
        
        message = f"""
<b>📋 KAMPANYA ÖZETİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎯 Tip:</b> {type_name} Kampanyası
<b>📛 İsim:</b> {data['name']}
<b>📄 Açıklama:</b> {data['description'][:50]}...
<b>🔗 Link:</b> {data['link'][:30]}...
"""
        
        if task_type == 'bot':
            message += f"<b>🤖 Bot:</b> {data.get('forward_from_bot_name', 'Bilinmiyor')}\n"
        else:
            admin_status = "✅ ADMIN" if data.get('is_bot_admin', 0) == 1 else "❌ ADMIN DEĞİL"
            message += f"<b>📢 {type_name}:</b> {data.get('target_chat_name', 'Bilinmiyor')}\n"
            message += f"<b>👑 Bot Durumu:</b> {admin_status}\n"
        
        message += f"""
<b>💰 Bütçe:</b> {budget:.2f}₺
<b>🎁 Ödül:</b> {price}₺
<b>👥 Katılımcı:</b> {max_participants} kişi

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>✅ Onaylıyor musunuz?</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '✅ Onayla', 'callback_data': 'campaign_confirm'},
                    {'text': '❌ İptal', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>👤 PROFİL BİLGİLERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 İsim:</b> {user.get('name', 'Kullanıcı')}
<b>🆔 ID:</b> <code>{user_id}</code>

<b>💰 Bakiye:</b> {user.get('balance', 0):.2f}₺
<b>🎯 Görev:</b> {user.get('tasks_completed', 0)}
<b>👥 Referans:</b> {user.get('referrals', 0)}

<b>📈 İstatistik:</b>
• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺
• Toplam Bonus: {user.get('total_bonus', 0):.2f}₺
• Referans Kazancı: {user.get('ref_earned', 0):.2f}₺
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'},
                    {'text': '👥 Referans', 'callback_data': 'referral'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_referral_menu(self, user_id):
        user = self.db.get_user(user_id)
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = f"""
<b>👥 REFERANS SİSTEMİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👥 Toplam Referans:</b> {user.get('referrals', 0)}
<b>💰 Kazanç:</b> {user.get('ref_earned', 0):.2f}₺

<b>🔗 Referans Linkiniz:</b>
<code>{referral_link}</code>

<b>💡 Her referans için 1₺ kazan!</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📋 Linki Kopyala', 'callback_data': 'referral_copy'},
                    {'text': '📤 Paylaş', 'callback_data': 'referral_share'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def copy_referral_link(self, user_id):
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        send_message(user_id, f"""
<b>🔗 REFERANS LİNKİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<code>{referral_link}</code>

📋 <b>Yukarıdaki linki kopyalayın</b>
💡 <b>Paylaşın ve para kazanın!</b>
""")
    
    def share_referral_link(self, user_id):
        referral_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        markup = {
            'inline_keyboard': [[
                {'text': '📤 Telegramda Paylaş', 
                 'url': f'https://t.me/share/url?url={referral_link}&text=Görev+Yapsam+Bot+ile+para+kazanın!'}
            ]]
        }
        
        send_message(user_id, """
<b>📤 REFERANS PAYLAŞ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 <b>Aşağıdaki butona tıklayarak paylaşabilirsiniz</b>

💡 <b>Her davet için 1₺ kazanacaksınız!</b>
""", markup)
    
    def show_deposit_menu(self, user_id):
        self.update_trx_price()
        
        message = f"""
<b>💰 BAKİYE YÜKLE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>₿ TRX Fiyatı:</b> {self.trx_price:.2f}₺
<b>🎁 Bonus:</b> %{DEPOSIT_BONUS_PERCENT}

👇 <b>Tutar Seçin:</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': f'25₺', 'callback_data': 'deposit_amount_25'},
                    {'text': f'50₺', 'callback_data': 'deposit_amount_50'}
                ],
                [
                    {'text': f'100₺', 'callback_data': 'deposit_amount_100'},
                    {'text': f'200₺', 'callback_data': 'deposit_amount_200'}
                ],
                [
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_deposit(self, user_id, amount):
        trx_amount = amount / self.trx_price
        bonus = amount * DEPOSIT_BONUS_PERCENT / 100
        
        message = f"""
<b>💰 ÖDEME BİLGİLERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💵 Tutar:</b> {amount:.2f}₺
<b>₿ TRX Tutarı:</b> {trx_amount:.4f} TRX
<b>🎁 Bonus:</b> {bonus:.2f}₺
<b>💰 Toplam:</b> {amount + bonus:.2f}₺

<b>🔗 TRX Adresi:</b>
<code>{TRX_ADDRESS}</code>

<b>📝 Adımlar:</b>
1. Yukarıdaki adrese {trx_amount:.4f} TRX gönder
2. İşlem tamamlanınca TXID'yi gönder
3. Bakiye otomatik yüklenecek

<code>/cancel</code> iptal etmek için
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
    
    def show_withdraw_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>🏧 PARA ÇEKME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Mevcut Bakiye:</b> {user.get('balance', 0):.2f}₺
<b>💳 Çekilebilir:</b> {user.get('balance', 0):.2f}₺

<b>⚠️ Minimum Çekim:</b> 10₺
<b>⏳ İşlem Süresi:</b> 24 saat

👇 <b>Çekim yapmak için admin ile iletişime geçin</b>
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_my_campaigns(self, user_id):
        self.db.cursor.execute('''
            SELECT * FROM campaigns 
            WHERE creator_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (user_id,))
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            message = """
<b>📋 KAMPANYALARIM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📭 <b>Henüz kampanyanız yok</b>

💡 <b>İlk kampanyanızı oluşturun!</b>
"""
        else:
            message = """
<b>📋 KAMPANYALARIM</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""
{status} <b>{camp['name'][:20]}</b>
├ <b>Durum:</b> {camp['status']}
├ <b>Bütçe:</b> {camp['budget']:.1f}₺
└ <b>Katılım:</b> {camp['current_participants']}/{camp['max_participants']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📢 Yeni Kampanya', 'callback_data': 'create_campaign'},
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        message = """
<b>❓ YARDIM VE BİLGİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 Bot Nasıl Çalışır?</b>
1. Kanala katılın (@GY_Refim)
2. Bakiye yükleyin veya görev yapın
3. Para kazanın!

<b>💰 Bakiye Nasıl Yüklenir?</b>
1. Bakiye butonuna basın
2. Tutar seçin
3. TRX gönderin
4. TXID'yi gönderin

<b>📢 Kampanya Nasıl Oluşturulur?</b>
1. Kampanya butonuna basın
2. Tip seçin (Bot/Kanal/Grup)
3. Adımları takip edin
4. Onaylayın

<b>👥 Referans Sistemi</b>
• Her davet: 1₺ bonus
• Linkinizi paylaşın
• Arkadaşlarınızı davet edin

<b>📞 Destek:</b>
Admin ile iletişime geçin.
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
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        message = f"""
<b>👑 ADMIN PANELİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 İstatistik</b>
• 👥 Kullanıcı: {total_users}
• 💰 Toplam Bakiye: {total_balance:.2f}₺

<b>🛠️ Araçlar</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📊 İstatistik', 'callback_data': 'admin_stats'},
                    {'text': '📢 Kampanyalar', 'callback_data': 'admin_campaigns'}
                ],
                [
                    {'text': '👥 Kullanıcılar', 'callback_data': 'admin_users'},
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
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM deposits WHERE status = 'completed'")
        total_deposits = self.db.cursor.fetchone()[0]
        
        message = f"""
<b>📊 DETAYLI İSTATİSTİK</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👥 Kullanıcı İstatistikleri</b>
• Toplam Kullanıcı: {total_users}

<b>💰 Finansal İstatistikler</b>
• Toplam Depozit: {total_deposits}

<b>📢 Kampanya İstatistikleri</b>
• Toplam Kampanya: {total_campaigns}

<b>⏰ Sistem Durumu:</b> ✅ ÇALIŞIYOR
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
            message = "📭 <b>Hiç kampanya yok</b>"
        else:
            message = "<b>📢 TÜM KAMPANYALAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""{status} <b>{camp['name'][:20]}</b>
├ <b>ID:</b> <code>{camp['campaign_id']}</code>
├ <b>Durum:</b> {camp['status']}
└ <b>Oluşturan:</b> {camp['creator_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
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
            message = "👥 <b>Hiç kullanıcı yok</b>"
        else:
            message = "<b>👥 TÜM KULLANICILAR</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for usr in users:
                message += f"""👤 <b>{usr['name'][:15]}</b>
├ <b>ID:</b> <code>{usr['user_id']}</code>
├ <b>Bakiye:</b> {usr['balance']:.1f}₺
└ <b>Referans:</b> {usr['referrals']}
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
            message = "💰 <b>Hiç depozit yok</b>"
        else:
            message = "<b>💰 TÜM DEPOZİTLER</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for dep in deposits:
                status = "✅" if dep['status'] == 'completed' else "⏳" if dep['status'] == 'pending' else "❌"
                message += f"""{status} <b>#{dep['deposit_id'][:8]}</b>
├ <b>Kullanıcı:</b> <code>{dep['user_id']}</code>
├ <b>Tutar:</b> {dep['amount_try']:.2f}₺
└ <b>Durum:</b> {dep['status']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
            ]]
        }
        send_message(user_id, message, markup)

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v17.0                      ║
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
