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
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot"})

# Database
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                username TEXT,
                balance REAL DEFAULT 0.0,
                ads_balance REAL DEFAULT 0.0,
                tasks_completed INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                total_deposited REAL DEFAULT 0.0,
                created_at TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                link TEXT,
                budget REAL,
                remaining_budget REAL,
                creator_id TEXT,
                task_type TEXT,
                price_per_task REAL,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                forward_message_id TEXT,
                target_chat_id TEXT,
                admin_approved INTEGER DEFAULT 0
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS deposits (
                deposit_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount_try REAL,
                amount_trx REAL,
                txid TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                bonus_amount REAL DEFAULT 0.0
            )
        ''')
        
        self.conn.commit()
        print("Veritabanı hazır")
    
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
    
    def add_balance(self, user_id, amount):
        user = self.get_user(user_id)
        new_balance = user.get('balance', 0) + amount
        self.cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        self.conn.commit()
        return True

# Telegram Fonksiyonları
def send_message(chat_id, text, markup=None):
    url = BASE_URL + "sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if markup: data['reply_markup'] = json.dumps(markup)
    try: return requests.post(url, json=data, timeout=10).json()
    except: return None

def answer_callback(callback_id):
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
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

def get_chat_admins(chat_id):
    url = BASE_URL + "getChatAdministrators"
    data = {'chat_id': chat_id}
    try:
        response = requests.post(url, json=data, timeout=10).json()
        if response.get('ok'):
            admins = response['result']
            return [str(admin['user']['id']) for admin in admins]
    except: pass
    return []

# Bot Sistemi
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.user_states = {}
        self.trx_price = 12.61
        self.update_trx_price()
    
    def update_trx_price(self):
        try:
            response = requests.get(TRX_PRICE_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.trx_price = data.get('tron', {}).get('try', 12.61)
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
        print("Bot başladı...")
        
        while True:
            try:
                url = BASE_URL + "getUpdates"
                params = {'offset': offset, 'timeout': 30}
                response = requests.get(url, params=params, timeout=35).json()
                
                if response.get('ok'):
                    updates = response['result']
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            self.process_message(update['message'])
                        elif 'callback_query' in update:
                            self.process_callback(update['callback_query'])
                
            except Exception as e:
                print(f"Hata: {e}")
                time.sleep(2)
    
    def process_message(self, message):
        if 'from' not in message: return
        
        user_id = str(message['from']['id'])
        user_state = self.get_user_state(user_id)
        
        if not self.db.get_user(user_id).get('name'):
            self.db.update_user(user_id, {
                'name': message['from'].get('first_name', 'Kullanıcı'),
                'username': message['from'].get('username', '')
            })
        
        if user_state['state']:
            self.handle_user_state(user_id, message, user_state)
            return
        
        if 'text' in message:
            text = message['text']
            if text.startswith('/start'): self.handle_start(user_id, text)
            elif text == '/menu': self.show_main_menu(user_id)
            elif text == '/admin' and user_id == ADMIN_ID: self.show_admin_panel(user_id)
            elif text == '/createcampaign': self.start_campaign_type_selection(user_id)
            elif text == '/deposit': self.show_deposit_menu(user_id)
            elif text == '/mycampaigns': self.show_my_campaigns(user_id)
            elif text == '/balance': self.show_balance(user_id)
            elif text == '/botinfo': self.show_bot_info(user_id)
    
    def handle_user_state(self, user_id, message, user_state):
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        if state == 'creating_campaign':
            if step == 1:  # İsim
                data['name'] = message['text']
                user_state['step'] = 2
                send_message(user_id, "✅ İsim alındı\n2/5 - Açıklama girin:")
            
            elif step == 2:  # Açıklama
                data['description'] = message['text']
                user_state['step'] = 3
                send_message(user_id, "✅ Açıklama alındı\n3/5 - Link girin:")
            
            elif step == 3:  # Link
                data['link'] = message['text']
                user_state['step'] = 4
                
                if data['task_type'] in ['channel', 'group']:
                    send_message(user_id, "✅ Link alındı\n4/5 - Kanal/Grup ID girin (@username veya ID):")
                else:
                    send_message(user_id, "✅ Link alındı\n4/5 - Bütçe girin (₺):")
            
            elif step == 4:
                if data['task_type'] in ['channel', 'group']:
                    target = message['text'].strip()
                    data['target_chat_id'] = target
                    user_state['step'] = 5
                    
                    # Botun admin olup olmadığını kontrol et
                    admins = get_chat_admins(target)
                    if str(TOKEN.split(':')[0]) not in admins:
                        send_message(user_id, "❌ Bot bu kanalda admin değil!\nBotu admin yapın.")
                        self.clear_user_state(user_id)
                        return
                    
                    send_message(user_id, f"✅ Hedef: {target}\n5/5 - Bütçe girin (₺):")
                else:
                    try:
                        budget = float(message['text'])
                        data['budget'] = budget
                        self.show_campaign_summary(user_id, data)
                    except:
                        send_message(user_id, "❌ Geçersiz bütçe!")
            
            elif step == 5:  # Bütçe (kanal/grup için)
                try:
                    budget = float(message['text'])
                    data['budget'] = budget
                    self.show_campaign_summary(user_id, data)
                except:
                    send_message(user_id, "❌ Geçersiz bütçe!")
        
        elif state == 'forward_message':
            if 'forward_from' in message and message['forward_from']['is_bot']:
                data['forward_message_id'] = message['message_id']
                data['forward_from_id'] = message['forward_from']['id']
                send_message(user_id, "✅ Bot mesajı alındı\n1/5 - Kampanya ismi girin:")
                user_state['step'] = 1
            else:
                send_message(user_id, "❌ Sadece bot mesajı forward edin!")
    
    def process_callback(self, callback):
        user_id = str(callback['from']['id'])
        data = callback['data']
        callback_id = callback['id']
        
        answer_callback(callback_id)
        
        if data == 'menu':
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
        elif data == 'campaign_manage':
            self.show_campaign_management(user_id)
        elif data == 'bot_info':
            self.show_bot_info(user_id)
        elif data == 'campaign_approve':
            self.approve_campaign(user_id)
        elif data == 'campaign_reject':
            self.reject_campaign(user_id)
        elif data == 'campaign_confirm':
            self.confirm_campaign(user_id)
        elif data == 'campaign_cancel':
            self.clear_user_state(user_id)
            send_message(user_id, "❌ Kampanya iptal edildi")
    
    def handle_start(self, user_id, text):
        in_channel = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        
        if not in_channel:
            markup = {
                'inline_keyboard': [[
                    {'text': '📢 Kanala Katıl', 'url': f'https://t.me/{MANDATORY_CHANNEL}'},
                    {'text': '✅ Katıldım', 'callback_data': 'joined'}
                ]]
            }
            send_message(user_id, f"👋 Hoşgeldin!\nÖnce kanala katıl: @{MANDATORY_CHANNEL}", markup)
            return
        
        user = self.db.get_user(user_id)
        if not user.get('balance'):
            self.db.add_balance(user_id, 2.0)
            send_message(user_id, "🎉 2₺ hoşgeldin bonusu yüklendi!")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""🤖 GÖREV YAPSAM BOT

👤 {user.get('name', 'Kullanıcı')}
💰 Bakiye: {user.get('balance', 0):.2f}₺
📊 Görevler: {user.get('tasks_completed', 0)}

Ana Menü:"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '🎯 Görev Yap', 'callback_data': 'tasks'}],
                [{'text': '📢 Kampanya Oluştur', 'callback_data': 'create_campaign'}],
                [{'text': '📋 Kampanyalarım', 'callback_data': 'my_campaigns'}],
                [{'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'}],
                [{'text': 'ℹ️ Bot Bilgisi', 'callback_data': 'bot_info'}]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([{'text': '👑 Yönetici', 'callback_data': 'admin'}])
        
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            send_message(user_id, f"❌ Önce kanala katıl: @{MANDATORY_CHANNEL}")
            return
        
        message = """📢 KAMPANYA TİPİ

Hangi tür kampanya oluşturacaksınız?"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '🤖 Bot Kampanyası', 'callback_data': 'camp_type_bot'}],
                [{'text': '📢 Kanal Kampanyası', 'callback_data': 'camp_type_channel'}],
                [{'text': '👥 Grup Kampanyası', 'callback_data': 'camp_type_group'}],
                [{'text': '🔙 Geri', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        if task_type == 'bot':
            self.set_user_state(user_id, 'forward_message', {'task_type': task_type})
            send_message(user_id, "🤖 Bot kampanyası seçildi\n\nÖnce bot mesajı forward edin:")
        else:
            self.set_user_state(user_id, 'creating_campaign', {'task_type': task_type})
            send_message(user_id, f"{'📢 Kanal' if task_type == 'channel' else '👥 Grup'} kampanyası seçildi\n\n1/5 - Kampanya ismi girin:")
    
    def show_campaign_summary(self, user_id, data):
        task_type = data['task_type']
        budget = data['budget']
        price = 2.5 if task_type == 'bot' else 1.5 if task_type == 'channel' else 1.0
        max_participants = int(budget / price)
        
        summary = f"""📋 KAMPANYA ÖZETİ

📛 İsim: {data['name']}
📄 Açıklama: {data['description'][:50]}...
🔗 Link: {data['link']}
"""
        if task_type in ['channel', 'group']:
            summary += f"🎯 Hedef: {data['target_chat_id']}\n"
        
        summary += f"""🎯 Tip: {'🤖 Bot' if task_type == 'bot' else '📢 Kanal' if task_type == 'channel' else '👥 Grup'}
💰 Bütçe: {budget:.2f}₺
👥 Max Katılım: {max_participants}
💵 Görev Ücreti: {price}₺

Onaylıyor musunuz?"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '✅ Onayla ve Yayınla', 'callback_data': 'campaign_confirm'}],
                [{'text': '❌ İptal', 'callback_data': 'campaign_cancel'}]
            ]
        }
        
        send_message(user_id, summary, markup)
    
    def confirm_campaign(self, user_id):
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_message(user_id, "❌ Kampanya verisi bulunamadı")
            return
        
        # Kampanya ID oluştur
        campaign_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        # Fiyat belirle
        price = 2.5 if data['task_type'] == 'bot' else 1.5 if data['task_type'] == 'channel' else 1.0
        budget = data['budget']
        max_participants = int(budget / price)
        
        # Veritabanına kaydet
        try:
            self.db.cursor.execute('''
                INSERT INTO campaigns 
                (campaign_id, name, description, link, budget, remaining_budget,
                 creator_id, task_type, price_per_task, max_participants, status,
                 created_at, forward_message_id, target_chat_id, admin_approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign_id,
                data['name'],
                data['description'],
                data['link'],
                budget,
                budget,
                user_id,
                data['task_type'],
                price,
                max_participants,
                'pending',
                datetime.now().isoformat(),
                data.get('forward_message_id', ''),
                data.get('target_chat_id', ''),
                0
            ))
            self.db.conn.commit()
            
            # Admin'e bildir
            if ADMIN_ID:
                admin_msg = f"""🆕 YENİ KAMPANYA ONAY BEKLİYOR

ID: {campaign_id}
Tip: {data['task_type']}
İsim: {data['name']}
Oluşturan: {user_id}
Bütçe: {budget}₺

Onayla veya Reddet:"""
                
                admin_markup = {
                    'inline_keyboard': [[
                        {'text': '✅ Onayla', 'callback_data': f'admin_approve_{campaign_id}'},
                        {'text': '❌ Reddet', 'callback_data': f'admin_reject_{campaign_id}'}
                    ]]
                }
                send_message(ADMIN_ID, admin_msg, admin_markup)
            
            send_message(user_id, f"✅ Kampanya oluşturuldu!\nID: {campaign_id}\n\nAdmin onayı bekleniyor...")
            self.clear_user_state(user_id)
            
        except Exception as e:
            print(f"Kampanya hatası: {e}")
            send_message(user_id, "❌ Kampanya oluşturulamadı")
    
    def show_my_campaigns(self, user_id):
        self.db.cursor.execute('''
            SELECT * FROM campaigns WHERE creator_id = ? ORDER BY created_at DESC LIMIT 10
        ''', (user_id,))
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            send_message(user_id, "📭 Henüz kampanyanız yok")
            return
        
        message = "📋 KAMPANYALARIM\n\n"
        for camp in campaigns:
            status = "✅ Aktif" if camp['status'] == 'active' else "⏳ Bekliyor" if camp['status'] == 'pending' else "❌ Pasif"
            message += f"""📛 {camp['name']}
💰 {camp['budget']}₺ | 👥 {camp['current_participants']}/{camp['max_participants']}
📊 {status} | ID: {camp['campaign_id']}
━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_deposit_menu(self, user_id):
        self.update_trx_price()
        
        message = f"""💰 BAKİYE YÜKLEME

TRX Fiyatı: {self.trx_price:.2f}₺
Min: {MIN_DEPOSIT_TRY}₺ | Max: {MAX_DEPOSIT_TRY}₺

Bonus: %{DEPOSIT_BONUS_PERCENT} normal bakiye
Reklam: %{ADS_BONUS_PERCENT} reklam bakiyesi

Tutar seçin:"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '25₺', 'callback_data': 'deposit_amount_25'}, {'text': '50₺', 'callback_data': 'deposit_amount_50'}],
                [{'text': '100₺', 'callback_data': 'deposit_amount_100'}, {'text': '200₺', 'callback_data': 'deposit_amount_200'}],
                [{'text': '🔙 Geri', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def start_deposit(self, user_id, amount):
        trx_amount = amount / self.trx_price
        
        message = f"""💳 ÖDEME BİLGİLERİ

Tutar: {amount}₺
TRX: {trx_amount:.4f} TRX
Fiyat: {self.trx_price:.2f}₺
Bonus: +{amount * DEPOSIT_BONUS_PERCENT / 100:.2f}₺

TRX Adresi:
<code>{TRX_ADDRESS}</code>

{trx_amount:.4f} TRX gönderin, TXID'yi yazın."""
        
        deposit_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        self.db.cursor.execute('''
            INSERT INTO deposits (deposit_id, user_id, amount_try, amount_trx, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (deposit_id, user_id, amount, trx_amount, datetime.now().isoformat()))
        self.db.conn.commit()
        
        self.set_user_state(user_id, 'waiting_txid', {'deposit_id': deposit_id, 'amount': amount})
        send_message(user_id, message)
    
    def show_balance(self, user_id):
        user = self.db.get_user(user_id)
        message = f"""💰 BAKİYE

Normal: {user.get('balance', 0):.2f}₺
Reklam: {user.get('ads_balance', 0):.2f}₺
Toplam: {user.get('balance', 0) + user.get('ads_balance', 0):.2f}₺

Görevler: {user.get('tasks_completed', 0)}
Referans: {user.get('referrals', 0)}
Yatırım: {user.get('total_deposited', 0):.2f}₺"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '💰 Yükle', 'callback_data': 'deposit'},
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_bot_info(self, user_id):
        message = f"""ℹ️ BOT BİLGİSİ

🤖 Görev Yapsam Bot
💰 TRX ile bakiye yükleme
📢 Otomatik kampanya sistemi
🎁 Bonus sistemi

Admin: {ADMIN_ID}
Kanal: @{MANDATORY_CHANNEL}
TRX: {TRX_ADDRESS[:15]}...

Komutlar:
/start - Botu başlat
/menu - Ana menü
/deposit - Bakiye yükle
/createcampaign - Kampanya oluştur
/mycampaigns - Kampanyalarım
/balance - Bakiyem
/botinfo - Bu menü"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        
        send_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, "❌ Yetkiniz yok")
            return
        
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'pending'")
        pending_campaigns = self.db.cursor.fetchone()[0]
        
        message = f"""👑 YÖNETİCİ PANELİ

👥 Toplam Kullanıcı: {total_users}
💰 Toplam Bakiye: {total_balance:.2f}₺
📊 Onay Bekleyen: {pending_campaigns}
⏰ Saat: {datetime.now().strftime('%H:%M')}"""
        
        markup = {
            'inline_keyboard': [
                [{'text': '📊 İstatistik', 'callback_data': 'admin_stats'}],
                [{'text': '📢 Kampanyalar', 'callback_data': 'admin_campaigns'}],
                [{'text': '👥 Kullanıcılar', 'callback_data': 'admin_users'}],
                [{'text': '🔙 Ana Menü', 'callback_data': 'menu'}]
            ]
        }
        
        send_message(user_id, message, markup)
    
    def show_campaign_management(self, user_id):
        if user_id != ADMIN_ID:
            send_message(user_id, "❌ Yetkiniz yok")
            return
        
        self.db.cursor.execute('''
            SELECT * FROM campaigns WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10
        ''')
        campaigns = self.db.cursor.fetchall()
        
        if not campaigns:
            send_message(user_id, "✅ Onay bekleyen kampanya yok")
            return
        
        message = "📋 ONAY BEKLEYEN KAMPANYALAR\n\n"
        for camp in campaigns:
            message += f"""ID: {camp['campaign_id']}
Tip: {camp['task_type']}
İsim: {camp['name']}
Oluşturan: {camp['creator_id']}
Bütçe: {camp['budget']}₺
━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin'}
            ]]
        }
        
        send_message(user_id, message, markup)

# Ana Program
def main():
    print("🤖 Görev Yapsam Bot Başlıyor...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"📢 Kanal: @{MANDATORY_CHANNEL}")
    print(f"💰 TRX: {TRX_ADDRESS}")
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    return app

if __name__ == "__main__":
    if TOKEN:
        main()
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("❌ Token gerekli!")

def create_app():
    bot = BotSystem()
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    return app
