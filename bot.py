import os
import time
import json
import requests
from datetime import datetime, timedelta
import threading
import sqlite3
from flask import Flask, jsonify
import hashlib
import re

# Telegram Ayarları
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "7904032877")
MANDATORY_CHANNEL = os.environ.get("MANDATORY_CHANNEL", "GY_Refim")
BOT_ID = TOKEN.split(':')[0] if TOKEN else ""

if not TOKEN:
    raise ValueError("Bot token gerekli!")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

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
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v13.0"})

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
                total_bonus REAL DEFAULT 0.0
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
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                forward_message_id TEXT,
                forward_chat_id TEXT,
                forward_message_text TEXT,
                target_chat_id TEXT,
                target_chat_name TEXT,
                admin_approved INTEGER DEFAULT 0,
                admin_checked INTEGER DEFAULT 0,
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
            now = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO users (user_id, name, balance, ads_balance, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, '', 0.0, 0.0, now))
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
    try: return requests.post(url, json=data, timeout=10).json()
    except: return None

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
    url = BASE_URL + "getChatMember"
    data = {'chat_id': chat_id, 'user_id': int(BOT_ID)}
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
        except: pass
    
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
<b>✅ 1/5 - İsim Kaydedildi</b>

<b>📄 2/5 - Açıklama girin:</b>
<i>Örnek: 'Kanalımıza katılın, içeriklerimizi takip edin'</i>

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
            
            elif step == 2:  # Açıklama
                data['description'] = message['text']
                user_state['step'] = 3
                send_message(user_id, f"""
<b>✅ 2/5 - Açıklama Kaydedildi</b>

<b>🔗 3/5 - Link girin:</b>
<i>Örnek: https://t.me/kanaladi</i>

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
            
            elif step == 3:  # Link
                data['link'] = message['text']
                user_state['step'] = 4
                
                task_type = data['task_type']
                if task_type == 'bot':
                    send_message(user_id, f"""
<b>✅ 3/5 - Link Kaydedildi</b>

<b>💰 4/5 - Bütçe girin (₺):</b>
<i>Minimum: 10₺ - Sadece sayı girin (örn: 50)</i>

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
                else:
                    send_message(user_id, f"""
<b>✅ 3/5 - Link Kaydedildi</b>

<b>🎯 4/5 - Kanal/Grup ismi girin:</b>
<i>@ ile başlamalı veya link olmalı</i>
<i>Örnek: @kanaladi veya https://t.me/kanaladi</i>

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
            
            elif step == 4:
                task_type = data['task_type']
                
                if task_type == 'bot':
                    try:
                        budget = float(message['text'])
                        if budget < 10:
                            send_message(user_id, "❌ <b>Minimum bütçe 10₺!</b>")
                            return
                        
                        data['budget'] = budget
                        user_state['step'] = 5
                        self.show_campaign_summary(user_id, data)
                    except:
                        send_message(user_id, "❌ <b>Geçersiz bütçe! Lütfen sayı girin.</b>")
                
                else:  # Kanal veya Grup
                    chat_input = message['text'].strip()
                    
                    # @ işaretini kontrol et
                    if not chat_input.startswith('@') and not chat_input.startswith('https://t.me/'):
                        send_message(user_id, "❌ <b>Geçersiz format! @ ile başlamalı veya link olmalı.</b>\n\nÖrnek: @kanaladi veya https://t.me/kanaladi")
                        return
                    
                    # Linkten @username çıkar
                    if chat_input.startswith('https://t.me/'):
                        chat_input = '@' + chat_input.split('/')[-1]
                    
                    # Kanal bilgilerini al
                    chat_info = get_chat_info(chat_input)
                    if not chat_info:
                        send_message(user_id, f"❌ <b>Kanal/Grup bulunamadı!</b>\n\nLütfen doğru isim girin: {chat_input}")
                        return
                    
                    # Botun admin olup olmadığını kontrol et
                    is_bot_admin = check_bot_admin(chat_info['id'])
                    
                    data['target_chat_id'] = str(chat_info['id'])
                    data['target_chat_name'] = chat_info.get('title', chat_input)
                    data['is_bot_admin'] = 1 if is_bot_admin else 0
                    user_state['step'] = 5
                    
                    if not is_bot_admin:
                        send_message(user_id, f"""
<b>⚠️ BOT ADMIN DEĞİL!</b>

📢 <b>Kanal/Grup:</b> {chat_info.get('title', chat_input)}

<b>Kampanyayı oluşturmak için:</b>
1️⃣ Botu kanalda <b>ADMIN</b> yapın
2️⃣ Üye listesini görme yetkisi verin
3️⃣ İşlemler yapma yetkisi verin

<b>Admin yaptıktan sonra devam edin:</b>
""")
                        time.sleep(1)
                    
                    send_message(user_id, f"""
<b>✅ 4/5 - Kanal/Grup Kaydedildi</b>

<b>💰 5/5 - Bütçe girin (₺):</b>
<i>Kanal: <b>{chat_info.get('title', chat_input)}</b></i>
<i>Minimum: 10₺ - Sadece sayı girin</i>

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
            
            elif step == 5:  # Bütçe (kanal/grup için)
                try:
                    budget = float(message['text'])
                    if budget < 10:
                        send_message(user_id, "❌ <b>Minimum bütçe 10₺!</b>")
                        return
                    
                    data['budget'] = budget
                    user_state['step'] = 6
                    self.show_campaign_summary(user_id, data)
                except:
                    send_message(user_id, "❌ <b>Geçersiz bütçe! Lütfen sayı girin.</b>")
        
        # BOT MESAJ FORWARD - DÜZELTİLMİŞ VERSİYON
        elif state == 'forward_message':
            # Önce forward mesaj olup olmadığını kontrol et
            if 'forward_from' in message:
                # Bot kontrolü - FIXED: Sadece forward_from.is_bot kontrolü
                if message['forward_from'].get('is_bot', False):
                    forward_from_id = str(message['forward_from']['id'])
                    
                    # FIX: Bu botun kendi mesajını kontrol et
                    if forward_from_id == BOT_ID:
                        data['forward_message_id'] = message['message_id']
                        data['forward_chat_id'] = message['chat']['id']
                        
                        # Mesaj metnini al
                        message_text = message.get('text', '') or message.get('caption', '') or ''
                        data['forward_message_text'] = message_text[:200] + '...' if len(message_text) > 200 else message_text
                        
                        # Başarılı mesajı
                        send_message(user_id, "<b>✅ Bot mesajı başarıyla alındı!</b>\n\n<b>📛 1/5 - Kampanya ismi girin:</b>\n\n<i>Örnek: 'Bot Mesajı Forward Görevi'</i>")
                        user_state['step'] = 1
                        user_state['state'] = 'creating_campaign'
                    else:
                        # Başka bir botun mesajı forward edilmiş
                        answer_callback(None, "❌ Sadece bu botun mesajını forward edin!", show_alert=True)
                        send_message(user_id, """
<b>❌ Sadece bu botun mesajını forward edin!</b>

⚠️ <b>YANLIŞ:</b> Başka bot mesajı forward ettiniz.
✅ <b>DOĞRU:</b> Bu botun (@GorevYapsamBot) mesajını forward edin.

<b>Nasıl yapılır:</b>
1️⃣ Bu botun mesajını bulun (örnek: /start mesajı)
2️⃣ Mesajı bu bota forward edin
3️⃣ Sistem otomatik algılayacak
""")
                else:
                    # Bot değil, normal kullanıcı mesajı
                    send_message(user_id, """
<b>❌ Sadece BOT mesajı forward edin!</b>

⚠️ <b>Normal kullanıcı mesajı forward ettiniz.</b>

<b>Doğru adımlar:</b>
1️⃣ Herhangi bir <b>BOT</b>'un mesajını bulun
2️⃣ Mesajı bu bota <b>FORWARD</b> edin
3️⃣ Sistem otomatik algılayacak

<i>Not: Sadece botların mesajları kabul edilir!</i>
""")
            elif 'text' in message and message['text'] == '/cancel':
                self.handle_cancel(user_id)
            else:
                # Forward mesaj değil
                send_message(user_id, """
<b>📤 LÜTFEN MESAJ FORWARD EDİN!</b>

<i>Bir mesaj forward etmeniz gerekiyor:</i>

<b>Adımlar:</b>
1️⃣ Başka bir <b>BOT</b>'un mesajını bulun
2️⃣ Mesaja basılı tutun veya sağ tıklayın
3️⃣ <b>Forward</b> seçeneğine tıklayın
4️⃣ Bu botu (@GorevYapsamBot) seçin
5️⃣ Gönderin

<code>/cancel</code> yazarak iptal edebilirsiniz.
""")
    
    def process_callback(self, callback):
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            message_id = callback['message']['message_id'] if 'message' in callback else None
            
            # İptal butonu kontrolü
            if data == 'cancel':
                self.handle_cancel(user_id)
                answer_callback(callback_id, "❌ İşlem iptal edildi.")
                return
            
            # Admin callback'leri
            if data.startswith('admin_'):
                if user_id != ADMIN_ID:
                    answer_callback(callback_id, "❌ Bu işlem için yetkiniz yok!", show_alert=True)
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
                answer_callback(callback_id, "❌ Kampanya oluşturma iptal edildi.")
                send_message(user_id, "<b>❌ Kampanya oluşturma iptal edildi.</b>\n\nAna menüye yönlendiriliyorsunuz...")
                time.sleep(1)
                self.show_main_menu(user_id)
            elif data == 'check_bot_admin':
                self.check_bot_admin_status(user_id)
            elif data == 'joined':
                if get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
                    self.db.update_user(user_id, {'in_channel': 1})
                    answer_callback(callback_id, "✅ Kanal kontrolü başarılı!")
                    self.show_main_menu(user_id)
                else:
                    answer_callback(callback_id, "❌ Hala kanala katılmadınız!", show_alert=True)
        
        except Exception as e:
            print(f"❌ Callback hatası: {e}")
            answer_callback(callback_id, f"❌ Bir hata oluştu: {str(e)}", show_alert=True)
    
    def handle_cancel(self, user_id):
        """Kullanıcının mevcut işlemini iptal et"""
        user_state = self.get_user_state(user_id)
        
        if user_state['state']:
            previous_state = user_state['state']
            self.clear_user_state(user_id)
            
            cancel_messages = {
                'forward_message': "📤 Forward işlemi iptal edildi.",
                'creating_campaign': "📢 Kampanya oluşturma iptal edildi.",
                'waiting_txid': "💳 Depozit işlemi iptal edildi."
            }
            
            message = cancel_messages.get(previous_state, "🔄 İşlem iptal edildi.")
            send_message(user_id, f"<b>{message}</b>\n\nAna menüye yönlendiriliyorsunuz...")
            time.sleep(1)
            self.show_main_menu(user_id)
        else:
            send_message(user_id, "<b>⚠️ Aktif bir işleminiz bulunmuyor.</b>")
    
    def handle_start(self, user_id, text):
        in_channel = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        
        if not in_channel:
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 KANALA KATIL', 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': '✅ KATILDIM', 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, f"""
<b>👋 MERHABA!</b>

🤖 <b>Görev Yapsam Bot</b>'a hoş geldiniz!

📢 <b>Botu kullanmak için:</b>
1️⃣ Önce kanala katılın: <b>@{MANDATORY_CHANNEL}</b>
2️⃣ Katıldıktan sonra <b>✅ KATILDIM</b> butonuna basın

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
<b>🎉 HOŞGELDİN {user.get('name', 'Kullanıcı')}!</b>

✅ <b>2₺ hoşgeldin bonusu</b> yüklendi!
💰 <b>Yeni bakiyen:</b> {user.get('balance', 0) + 2.0:.2f}₺

⚡ <i>Hemen görev yapmaya başlayabilirsin!</i>
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
                        send_message(user_id, "<b>🎉 Referans başarılı!</b>\n\n💰 <b>1₺ referans bonusu</b> arkadaşınıza yüklendi!")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>🤖 GÖREV YAPSAM BOT v13.0</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Kullanıcı:</b> {user.get('name', 'Kullanıcı')}
💰 <b>Bakiye:</b> <code>{user.get('balance', 0):.2f}₺</code>
📊 <b>Görevler:</b> {user.get('tasks_completed', 0)}
👥 <b>Referans:</b> {user.get('referrals', 0)}

<b>₿ TRX Fiyatı:</b> {self.trx_price:.2f}₺
<b>📢 Zorunlu Kanal:</b> @{MANDATORY_CHANNEL}
━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 ANA MENÜ</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '🎯 GÖREV YAP', 'callback_data': 'active_tasks'}],
                [{'text': '📢 KAMPANYA OLUŞTUR', 'callback_data': 'create_campaign'}],
                [{'text': '📋 KAMPANYALARIM', 'callback_data': 'my_campaigns'}],
                [{'text': '💰 BAKİYE YÜKLE', 'callback_data': 'deposit'}],
                [{'text': '👤 PROFİL', 'callback_data': 'profile'}],
                [{'text': 'ℹ️ BOT BİLGİSİ', 'callback_data': 'bot_info'}, {'text': '❓ YARDIM', 'callback_data': 'help'}]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([{'text': '👑 YÖNETİCİ PANELİ', 'callback_data': 'admin_panel'}])
        
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            send_message(user_id, f"❌ <b>Önce kanala katılmalısın!</b>\n\n👉 @{MANDATORY_CHANNEL}")
            return
        
        message = """
<b>📢 KAMPANYA TİPİ SEÇİN</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 BOT KAMPANYASI</b>
• Görev: Bot mesajını forward etme
• Ödül: 2.5₺ her katılım
• Durum: Admin onayı gerektirir
• Not: Bot mesajı forward etmeniz gerekir

<b>📢 KANAL KAMPANYASI</b>
• Görev: Kanala katılma
• Ödül: 1.5₺ her katılım
• Durum: Bot kanalda admin olmalı
• Not: Botu kanalda admin yapın

<b>👥 GRUP KAMPANYASI</b>
• Görev: Gruba katılma
• Ödül: 1₺ her katılım
• Durum: Bot grupta admin olmalı
• Not: Botu grupta admin yapın

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>👇 Hangi tür kampanya oluşturacaksınız?</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '🤖 BOT KAMPANYASI', 'callback_data': 'camp_type_bot'}],
                [{'text': '📢 KANAL KAMPANYASI', 'callback_data': 'camp_type_channel'}],
                [{'text': '👥 GRUP KAMPANYASI', 'callback_data': 'camp_type_group'}],
                [{'text': '❌ İPTAL', 'callback_data': 'cancel'}, {'text': '🔙 GERİ', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        user = self.db.get_user(user_id)
        
        if task_type == 'bot':
            self.set_user_state(user_id, 'forward_message', {'task_type': task_type})
            send_message(user_id, """
<b>🤖 BOT KAMPANYASI OLUŞTURMA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 1:</b> Bot mesajı forward edin

<b>Nasıl yapılır:</b>
1️⃣ Herhangi bir botun mesajını bulun
2️⃣ Mesajı bu bota forward edin
3️⃣ Sistem otomatik algılayacak

<b>⚠️ NOT:</b> Sadece BOT mesajı forward edin!

<i>Bir mesaj forward edin veya</i>
<code>/cancel</code> <i>yazarak iptal edin</i>
""")
        else:
            task_name = "KANAL" if task_type == 'channel' else "GRUP"
            self.set_user_state(user_id, 'creating_campaign', {'task_type': task_type})
            send_message(user_id, f"""
<b>📢 {task_name} KAMPANYASI OLUŞTURMA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📌 ADIM 1/5:</b> Kampanya ismi girin

<b>Örnek isimler:</b>
• Telegram Kanalına Katıl
• YouTube Abone Ol
• Instagram Takip Et
• Discord Sunucusu

<i>Kampanya isminizi yazın veya</i>
<code>/cancel</code> <i>yazarak iptal edin</i>
""")
    
    def show_campaign_summary(self, user_id, data):
        task_type = data['task_type']
        task_name = "🤖 BOT" if task_type == 'bot' else "📢 KANAL" if task_type == 'channel' else "👥 GRUP"
        price = 2.5 if task_type == 'bot' else 1.5 if task_type == 'channel' else 1.0
        budget = data['budget']
        max_participants = int(budget / price)
        
        summary = f"""
<b>📋 KAMPANYA ÖZETİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🎯 KAMPANYA TİPİ:</b> {task_name}
<b>📛 İSİM:</b> {data['name']}
<b>📄 AÇIKLAMA:</b> {data['description'][:80]}...
<b>🔗 LİNK:</b> {data['link'][:50]}...
"""
        
        if task_type in ['channel', 'group']:
            chat_name = data.get('target_chat_name', 'Bilinmiyor')
            is_bot_admin = data.get('is_bot_admin', 0)
            admin_status = "✅ BOT ADMIN" if is_bot_admin else "❌ BOT ADMIN DEĞİL"
            
            summary += f"<b>🎯 HEDEF:</b> {chat_name}\n"
            summary += f"<b>👑 BOT DURUMU:</b> {admin_status}\n"
            
            if not is_bot_admin:
                summary += f"\n<b>⚠️ UYARI:</b> Bot bu {task_type}da admin değil!\n"
                summary += "<b>Devam etmeden önce botu admin yapın.</b>\n"
        
        summary += f"""
<b>💰 BÜTÇE:</b> {budget:.2f}₺
<b>💵 GÖREV ÜCRETİ:</b> {price}₺
<b>👥 MAKSİMUM KATILIM:</b> {max_participants}
<b>👤 OLUŞTURAN:</b> {data.get('creator_name', 'Kullanıcı')}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Kampanyayı onaylıyor musunuz?</b>
<i>✅ Onaylandıktan sonra admin kontrolünden geçecek.</i>
"""
        
        markup = {
            'inline_keyboard': []
        }
        
        if task_type in ['channel', 'group'] and not data.get('is_bot_admin', 0):
            markup['inline_keyboard'].append([{'text': '🔄 BOT ADMIN KONTROL ET', 'callback_data': 'check_bot_admin'}])
        
        markup['inline_keyboard'].extend([
            [{'text': '✅ EVET, ONAYLA VE GÖNDER', 'callback_data': 'campaign_confirm'}],
            [{'text': '❌ HAYIR, İPTAL ET', 'callback_data': 'campaign_cancel'}]
        ])
        
        send_message(user_id, summary, markup)
    
    def confirm_campaign(self, user_id):
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_message(user_id, "❌ <b>Kampanya verisi bulunamadı!</b>")
            return
        
        # Kanal/grup için bot admin kontrolü
        if data['task_type'] in ['channel', 'group']:
            chat_id = data.get('target_chat_id')
            if chat_id:
                is_bot_admin = check_bot_admin(chat_id)
                if not is_bot_admin:
                    send_message(user_id, """
<b>❌ BOT ADMIN DEĞİL!</b>

Kampanyayı oluşturmak için botu kanalda/grupta admin yapmalısınız.

<b>Adımlar:</b>
1️⃣ Kanal/grup ayarlarına git
2️⃣ Yöneticiler (Admins) bölümüne git
3️⃣ Botu admin olarak ekle
4️⃣ TÜM YETKİLERİ aktif edin
5️⃣ Özellikle: Üyeleri görme yetkisi
6️⃣ Kaydet butonuna basın

<b>Admin yaptıktan sonra tekrar deneyin.</b>
""")
                    return
        
        user = self.db.get_user(user_id)
        balance = user.get('balance', 0)
        budget = data['budget']
        
        if balance < budget:
            send_message(user_id, f"""
<b>❌ YETERSİZ BAKİYE!</b>

<b>Gerekli:</b> {budget:.2f}₺
<b>Mevcut:</b> {balance:.2f}₺
<b>Eksik:</b> {budget - balance:.2f}₺

💡 <b>Lütfen önce bakiye yükleyin.</b>
""")
            return
        
        # Kampanya ID oluştur
        campaign_id = hashlib.md5(f"{user_id}{time.time()}{data['name']}".encode()).hexdigest()[:10].upper()
        
        # Fiyat belirle
        price = 2.5 if data['task_type'] == 'bot' else 1.5 if data['task_type'] == 'channel' else 1.0
        max_participants = int(budget / price)
        
        # Veritabanına kaydet
        try:
            self.db.cursor.execute('''
                INSERT INTO campaigns 
                (campaign_id, name, description, link, budget, remaining_budget,
                 creator_id, creator_name, task_type, price_per_task, max_participants,
                 status, created_at, forward_message_id, forward_chat_id, forward_message_text,
                 target_chat_id, target_chat_name, admin_approved, admin_checked, is_bot_admin)
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
                'pending',
                datetime.now().isoformat(),
                data.get('forward_message_id', ''),
                data.get('forward_chat_id', ''),
                data.get('forward_message_text', ''),
                data.get('target_chat_id', ''),
                data.get('target_chat_name', ''),
                0,  # admin_approved
                0,  # admin_checked
                data.get('is_bot_admin', 0)
            ))
            
            # Bakiyeden düş
            self.db.update_user(user_id, {'balance': balance - budget})
            
            self.db.conn.commit()
            
            # Admin'e bildir
            if ADMIN_ID:
                task_name = "BOT" if data['task_type'] == 'bot' else "KANAL" if data['task_type'] == 'channel' else "GRUP"
                admin_msg = f"""
<b>🆕 YENİ KAMPANYA ONAY BEKLİYOR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 İSİM:</b> {data['name']}
<b>🎯 TİP:</b> {task_name}
<b>👤 OLUŞTURAN:</b> {user.get('name', 'Kullanıcı')} ({user_id})
<b>💰 BÜTÇE:</b> {budget:.2f}₺
<b>👥 MAKSİMUM:</b> {max_participants}
<b>🔢 KAMPANYA ID:</b> <code>{campaign_id}</code>

"""
                
                if data['task_type'] in ['channel', 'group']:
                    admin_msg += f"<b>🎯 HEDEF:</b> {data.get('target_chat_name', 'Bilinmiyor')}\n"
                    admin_msg += f"<b>👑 BOT ADMIN:</b> {'✅ EVET' if data.get('is_bot_admin', 0) else '❌ HAYIR'}\n"
                
                admin_msg += "\n<b>👇 ONAYLA VEYA REDDET:</b>"
                
                admin_markup = {
                    'inline_keyboard': [[
                        {'text': '✅ ONAYLA', 'callback_data': f'admin_approve_{campaign_id}'},
                        {'text': '❌ REDDET', 'callback_data': f'admin_reject_{campaign_id}'},
                        {'text': '🗑️ SİL', 'callback_data': f'admin_delete_{campaign_id}'}
                    ]]
                }
                send_message(ADMIN_ID, admin_msg, admin_markup)
            
            # Kullanıcıya bilgi ver
            success_msg = f"""
<b>✅ KAMPANYA OLUŞTURULDU!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 İSİM:</b> {data['name']}
<b>💰 BÜTÇE:</b> {budget:.2f}₺
<b>🔢 KAMPANYA ID:</b> <code>{campaign_id}</code>

<b>📊 DURUM:</b> <i>Admin onayı bekleniyor...</i>

⏳ <b>Admin onayı genellikle 24 saat içinde yapılır.</b>
📢 <b>Onaylandıktan sonra kampanya aktif olacak.</b>

💰 <b>{budget:.2f}₺ bakiyenizden düşüldü.</b>
"""
            
            send_message(user_id, success_msg)
            self.clear_user_state(user_id)
            time.sleep(2)
            self.show_main_menu(user_id)
            
        except Exception as e:
            print(f"❌ Kampanya hatası: {e}")
            send_message(user_id, "❌ <b>Kampanya oluşturulamadı! Lütfen tekrar deneyin.</b>")
    
    def check_bot_admin_status(self, user_id):
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data or 'target_chat_id' not in data:
            send_message(user_id, "❌ <b>Kanal bilgisi bulunamadı!</b>")
            return
        
        chat_id = data['target_chat_id']
        is_bot_admin = check_bot_admin(chat_id)
        
        if is_bot_admin:
            data['is_bot_admin'] = 1
            send_message(user_id, "✅ <b>BOT ARTIK ADMIN!</b>\n\nDevam edebilirsiniz.")
            time.sleep(1)
            self.show_campaign_summary(user_id, data)
        else:
            send_message(user_id, """
<b>❌ HENÜZ BOT ADMIN DEĞİL!</b>

<b>Lütfen aşağıdaki adımları takip edin:</b>

1️⃣ Kanal/grup ayarlarına gidin
2️⃣ <b>Yöneticiler (Admins)</b> bölümüne tıklayın
3️⃣ <b>Yönetici Ekle</b> butonuna basın
4️⃣ <b>@GorevYapsamBot</b> yazın
5️⃣ <b>TÜM YETKİLERİ</b> aktif edin
6️⃣ Özellikle: <b>Üyeleri görme</b> yetkisi
7️⃣ <b>Kaydet</b> butonuna basın

<b>✅ Admin yaptıktan sonra tekrar kontrol edin.</b>

<code>/cancel</code> yazarak iptal edebilirsiniz.
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
            send_message(user_id, """
<b>📭 HENÜZ KAMPANYANIZ YOK</b>

💡 <b>İlk kampanyanızı oluşturarak para kazanmaya başlayın!</b>

<b>Nasıl kampanya oluşturulur:</b>
1️⃣ Ana menüden <b>Kampanya Oluştur</b>'a tıklayın
2️⃣ Kampanya tipini seçin
3️⃣ Adımları takip edin
4️⃣ Admin onayı bekleyin
""")
            time.sleep(2)
            self.show_main_menu(user_id)
            return
        
        message = "<b>📋 KAMPANYALARIM</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        active_count = 0
        pending_count = 0
        completed_count = 0
        
        for i, camp in enumerate(campaigns, 1):
            status = camp['status']
            status_icon = "🟢" if status == 'active' else "🟡" if status == 'pending' else "🔴"
            status_text = "AKTİF" if status == 'active' else "BEKLİYOR" if status == 'pending' else "PASİF"
            
            if status == 'active': active_count += 1
            elif status == 'pending': pending_count += 1
            else: completed_count += 1
            
            name = camp['name'][:20] + "..." if len(camp['name']) > 20 else camp['name']
            
            message += f"""{status_icon} <b>{name}</b>
├ <b>Durum:</b> {status_text}
├ <b>Bütçe:</b> {camp['budget']:.1f}₺
├ <b>Katılım:</b> {camp['current_participants']}/{camp['max_participants']}
└ <b>ID:</b> <code>{camp['campaign_id']}</code>
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        message += f"\n<b>📊 ÖZET:</b>\n"
        message += f"• 🟢 Aktif: {active_count}\n"
        message += f"• 🟡 Bekleyen: {pending_count}\n"
        message += f"• 🔴 Pasif: {completed_count}\n"
        message += f"• 📈 Toplam: {len(campaigns)}"
        
        markup = {
            'inline_keyboard': [[
                {'text': '📢 YENİ KAMPANYA', 'callback_data': 'create_campaign'},
                {'text': '🔙 GERİ', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_deposit_menu(self, user_id):
        self.update_trx_price()
        
        message = f"""
<b>💰 BAKİYE YÜKLEME</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>₿ TRX FİYATI:</b> {self.trx_price:.2f}₺
<b>💵 MİNİMUM:</b> {MIN_DEPOSIT_TRY}₺
<b>💎 MAKSİMUM:</b> {MAX_DEPOSIT_TRY}₺

<b>🎁 BONUS SİSTEMİ:</b>
• Normal Bakiye: +%{DEPOSIT_BONUS_PERCENT}
• Reklam Bakiye: +%{ADS_BONUS_PERCENT}

<b>💡 ÖRNEK:</b> 100₺ yüklersen:
• Normal: 135₺ (35₺ bonus)
• Reklam: 120₺ (20₺ bonus)

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>👇 TUTAR SEÇİN:</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': f'25₺ ({(25/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_25'},
                 {'text': f'50₺ ({(50/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_50'}],
                [{'text': f'100₺ ({(100/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_100'},
                 {'text': f'200₺ ({(200/self.trx_price):.2f} TRX)', 'callback_data': 'deposit_amount_200'}],
                [{'text': '❌ İPTAL', 'callback_data': 'cancel'}, {'text': '🔙 GERİ', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_deposit(self, user_id, amount):
        trx_amount = amount / self.trx_price
        bonus = amount * DEPOSIT_BONUS_PERCENT / 100
        total_receive = amount + bonus
        
        message = f"""
<b>💳 ÖDEME BİLGİLERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💵 TUTAR:</b> {amount:.2f}₺
<b>₿ TRX MİKTARI:</b> {trx_amount:.4f} TRX
<b>📈 TRX FİYATI:</b> {self.trx_price:.2f}₺

<b>🎁 BONUS:</b> +{bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})
<b>💰 TOPLAM ALACAĞINIZ:</b> {total_receive:.2f}₺

<b>🔗 TRX ADRESİ:</b>
<code>{TRX_ADDRESS}</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>👇 ADIM ADIM YAPMANIZ GEREKENLER:</b>

1️⃣ <b>Adresi kopyala</b> (üstüne tıkla)
2️⃣ <b>TRX cüzdanınızdan</b> {trx_amount:.4f} TRX gönder
3️⃣ <b>İşlem tamamlandığında</b> TXID'yi bana gönder
4️⃣ <b>Bakiyeniz otomatik yüklenecek</b>

⏳ <b>İşlem süresi:</b> 2-5 dakika
✅ <b>TXID formatı:</b> 64 karakterlik hex kodu

<code>/cancel</code> yazarak iptal edebilirsiniz.
"""
        
        deposit_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        try:
            self.db.cursor.execute('''
                INSERT INTO deposits (deposit_id, user_id, amount_try, amount_trx, created_at, trx_price, bonus_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (deposit_id, user_id, amount, trx_amount, datetime.now().isoformat(), self.trx_price, bonus))
            self.db.conn.commit()
            
            self.set_user_state(user_id, 'waiting_txid', {'deposit_id': deposit_id, 'amount': amount, 'bonus': bonus})
            send_message(user_id, message)
            
        except Exception as e:
            print(f"❌ Depozit hatası: {e}")
            send_message(user_id, "❌ <b>Depozit oluşturulamadı! Lütfen tekrar deneyin.</b>")
    
    def show_balance(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>💰 BAKİYE DETAYLARI</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 KULLANICI:</b> {user.get('name', 'Kullanıcı')}
<b>🆔 ID:</b> {user_id}

<b>💵 NORMAL BAKİYE:</b> {user.get('balance', 0):.2f}₺
<b>📺 REKLAM BAKİYESİ:</b> {user.get('ads_balance', 0):.2f}₺
<b>💰 TOPLAM BAKİYE:</b> {user.get('balance', 0) + user.get('ads_balance', 0):.2f}₺

<b>📊 İSTATİSTİKLER:</b>
• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺
• Toplam Bonus: {user.get('total_bonus', 0):.2f}₺
• Görev Sayısı: {user.get('tasks_completed', 0)}
• Referans: {user.get('referrals', 0)}

<b>💡 Reklam bakiyesi %{ADS_BONUS_PERCENT} bonusludur!</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '💰 BAKİYE YÜKLE', 'callback_data': 'deposit'},
                 {'text': '📺 REKLAM BAKİYEM', 'callback_data': 'ads_balance'}],
                [{'text': '🔙 GERİ', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_bot_info(self, user_id):
        message = f"""
<b>ℹ️ BOT HAKKINDA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 BOT ADI:</b> Görev Yapsam Bot
<b>🔄 VERSİYON:</b> v13.0
<b>👑 YÖNETİCİ:</b> {ADMIN_ID}
<b>📢 ZORUNLU KANAL:</b> @{MANDATORY_CHANNEL}
<b>₿ TRX ADRESİ:</b> <code>{TRX_ADDRESS}</code>

<b>💰 ÖZELLİKLER:</b>
• TRX ile bakiye yükleme
• Otomatik kampanya sistemi
• %{DEPOSIT_BONUS_PERCENT} depozit bonusu
• %{ADS_BONUS_PERCENT} reklam bonusu
• Admin onaylı kampanyalar
• Referans sistemi

<b>📋 KOMUTLAR:</b>
/start - Botu başlat
/menu - Ana menü
/deposit - Bakiye yükle
/createcampaign - Kampanya oluştur
/mycampaigns - Kampanyalarım
/balance - Bakiyem
/botinfo - Bu menü
/help - Yardım
/cancel - İptal et

<b>⚠️ KURALLAR:</b>
• Sahte görev yasak
• Çoklu hesap yasak
• Spam yasak
• Kurallara uymayanlar banlanır

<b>📞 DESTEK:</b>
Sorularınız için admin ile iletişime geçin.
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 GERİ', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        message = """
<b>❓ YARDIM MENÜSÜ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 BOT NASIL ÇALIŞIR?</b>
1️⃣ Kanalımıza katılın
2️⃣ Bakiye yükleyin veya görev yapın
3️⃣ Kampanya oluşturun veya katılın
4️⃣ Para kazanın!

<b>💰 BAKİYE NASIL YÜKLENİR?</b>
1️⃣ /deposit komutunu kullan
2️⃣ Tutar seç (25-200₺)
3️⃣ TRX adresine TRX gönder
4️⃣ TXID'yi gir
5️⃣ Bakiyen otomatik yüklenecek

<b>📢 KAMPANYA NASIL OLUŞTURULUR?</b>
1️⃣ /createcampaign komutunu kullan
2️⃣ Kampanya tipini seç
3️⃣ Adımları takip et
4️⃣ Admin onayı bekle
5️⃣ Kampanya aktif olacak

<b>🎯 GÖREV NASIL YAPILIR?</b>
1️⃣ Aktif kampanyaları gör
2️⃣ Görevi tamamla
3️⃣ Kanıt gönder
4️⃣ Onay bekle
5️⃣ Ödülü al

<b>👥 REFERANS SİSTEMİ</b>
• Her referans: 1₺
• Referans linkin: /start ref_XXXXXXXX
• Arkadaşların kanala katılmazsa bonus alamazsın

<b>🔄 İPTAL SİSTEMİ</b>
• Her adımda <code>/cancel</code> yazabilirsin
• Her menüde ❌ İPTAL butonu var
• Yanlışlıkla başlatılan işlemleri durdurabilirsin

<b>⚠️ ÖNEMLİ UYARILAR</b>
• Sahte görev yapma
• Çoklu hesap açma
• Spam yapma
• Kurallara uy
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '💰 BAKİYE YÜKLE', 'callback_data': 'deposit'},
                {'text': '🔙 GERİ', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, "❌ <b>Bu işlem için yetkiniz yok!</b>")
            return
        
        # İstatistikler
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'pending'")
        pending_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = self.db.cursor.fetchone()[0]
        
        message = f"""
<b>👑 YÖNETİCİ PANELİ v13.0</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 İSTATİSTİKLER</b>
• 👥 Toplam Kullanıcı: <b>{total_users}</b>
• 💰 Toplam Bakiye: {total_balance:.2f}₺
• 📢 Aktif Kampanyalar: {active_campaigns}
• ⏳ Onay Bekleyen: {pending_campaigns}
• ₿ TRX Fiyatı: {self.trx_price:.2f}₺
• ⏰ Saat: {datetime.now().strftime('%H:%M')}

<b>🛠️ YÖNETİCİ ARAÇLARI</b>
"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '📊 İSTATİSTİKLER', 'callback_data': 'admin_stats'},
                 {'text': '📢 KAMPANYALAR', 'callback_data': 'admin_campaigns'}],
                [{'text': '👥 KULLANICILAR', 'callback_data': 'admin_users'},
                 {'text': '💰 DEPOZİTLER', 'callback_data': 'admin_deposits'}],
                [{'text': '📣 BİLDİRİM', 'callback_data': 'admin_broadcast'},
                 {'text': '⚙️ AYARLAR', 'callback_data': 'admin_settings'}],
                [{'text': '❌ İPTAL', 'callback_data': 'cancel'}, {'text': '🔙 ANA MENÜ', 'callback_data': 'menu'}]
            ]
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
            
            # Kampanyayı aktif et
            self.db.cursor.execute("UPDATE campaigns SET status = 'active', admin_approved = 1 WHERE campaign_id = ?", (campaign_id,))
            self.db.conn.commit()
            
            # Oluşturucuya bildir
            creator_id = campaign['creator_id']
            send_message(creator_id, f"""
<b>🎉 KAMPANYANIZ ONAYLANDI!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 İSİM:</b> {campaign['name']}
<b>🔢 ID:</b> <code>{campaign_id}</code>
<b>💰 BÜTÇE:</b> {campaign['budget']:.2f}₺
<b>👥 MAKSİMUM:</b> {campaign['max_participants']}

✅ <b>Kampanyanız şimdi aktif!</b>
📢 <b>Kullanıcılar katılmaya başlayabilir.</b>

💰 <b>Kazanç:</b> Her katılım için {campaign['price_per_task']}₺
⏳ <b>Süre:</b> Bütçe bitene kadar aktif
""")
            
            # Admin'e bildir
            send_message(ADMIN_ID, f"✅ <b>Kampanya onaylandı:</b> {campaign_id}\n\nKampanya aktif edildi ve kullanıcıya bildirildi.")
            
        except Exception as e:
            print(f"❌ Onay hatası: {e}")
            send_message(ADMIN_ID, f"❌ <b>Kampanya onaylanamadı:</b> {campaign_id}")
    
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
            self.db.cursor.execute("UPDATE campaigns SET status = 'rejected', admin_approved = 0 WHERE campaign_id = ?", (campaign_id,))
            self.db.conn.commit()
            
            # Oluşturucuya bildir
            send_message(creator_id, f"""
<b>❌ KAMPANYANIZ REDDEDİLDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📛 İSİM:</b> {campaign['name']}
<b>🔢 ID:</b> <code>{campaign_id}</code>
<b>💰 BÜTÇE:</b> {budget:.2f}₺

<b>⚠️ RED SEBEBİ:</b>
• Bot kanalda admin değil
• Kampanya kurallara uymuyor
• Eksik bilgi
• Şüpheli içerik

💰 <b>{budget:.2f}₺ bakiyenize iade edildi.</b>
💡 <b>Lütfen kuralları kontrol edip tekrar deneyin.</b>
""")
            
            # Admin'e bildir
            send_message(ADMIN_ID, f"❌ <b>Kampanya reddedildi:</b> {campaign_id}\n\n{budget:.2f}₺ kullanıcıya iade edildi.")
            
        except Exception as e:
            print(f"❌ Reddetme hatası: {e}")
            send_message(ADMIN_ID, f"❌ <b>Kampanya reddedilemedi:</b> {campaign_id}")

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v13.0                      ║
    ║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAM BAKİYESİ + BONUS SİSTEM║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🤖 Bot ID: {BOT_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    print(f"₿ TRX Adresi: {TRX_ADDRESS}")
    print(f"💰 Min Depozit: {MIN_DEPOSIT_TRY}₺, Max: {MAX_DEPOSIT_TRY}₺")
    print(f"🎁 Bonuslar: %{DEPOSIT_BONUS_PERCENT} Normal, %{ADS_BONUS_PERCENT} Reklam")
    print("🔄 İptal sistemi aktif: /cancel komutu her yerde çalışır")
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
