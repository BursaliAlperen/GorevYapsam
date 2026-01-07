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
MIN_WITHDRAW = 10.0
ADS_CONVERSION_RATE = 0.8  # %80 oranında reklam bakiyesine çevrilebilir

# Flask App
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "bot": "Görev Yapsam Bot v19.0"})

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
                last_notification_time TEXT
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
    
    def convert_to_ads_balance(self, user_id, amount):
        """Normal bakiyeyi reklam bakiyesine çevir"""
        user = self.get_user(user_id)
        normal_balance = user.get('balance', 0)
        
        if amount > normal_balance:
            return False, "Yetersiz bakiye!"
        
        if amount < 1:
            return False, "Minimum 1₺ çevirebilirsiniz!"
        
        # %80 oranında çevir
        ads_amount = amount * ADS_CONVERSION_RATE
        
        # Bakiyeleri güncelle
        new_normal_balance = normal_balance - amount
        new_ads_balance = user.get('ads_balance', 0) + ads_amount
        
        self.cursor.execute('''
            UPDATE users 
            SET balance = ?, ads_balance = ?, total_earned = total_earned + ?
            WHERE user_id = ?
        ''', (new_normal_balance, new_ads_balance, ads_amount, user_id))
        self.conn.commit()
        
        # Bildirim gönder
        message = f"""
<b>🔄 REKLAM BAKİYESİNE ÇEVRİLDİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>{amount:.2f}₺ reklam bakiyesine çevrildi!</b>

📊 <b>Detaylar:</b>
• Çevrilen: {amount:.2f}₺
• Reklam Bakiyesi: +{ads_amount:.2f}₺ (%{int(ADS_CONVERSION_RATE*100)})
• Kalan Normal Bakiye: {new_normal_balance:.2f}₺
• Toplam Reklam Bakiyesi: {new_ads_balance:.2f}₺

💡 <b>Reklam bakiyesi ile reklam gösterimi yapabilirsiniz!</b>
"""
        send_message(user_id, message)
        
        return True, f"{amount:.2f}₺ reklam bakiyesine çevrildi!"

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
                params = {'offset': offset, 'timeout': 10, 'allowed_updates': ['message', 'callback_query']}
                response = requests.get(url, params=params, timeout=15).json()
                
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
            
            # Ana menü butonları
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
            elif data == 'convert':
                self.show_convert_menu(user_id)
            
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
            
            # Convert butonları
            elif data == 'convert_all':
                self.convert_all_balance(user_id)
            elif data == 'convert_half':
                self.convert_half_balance(user_id)
            elif data == 'convert_quarter':
                self.convert_quarter_balance(user_id)
            elif data == 'convert_custom':
                self.start_custom_convert(user_id)
            
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
            self.db.add_balance(user_id, 2.0, 0, "welcome_bonus")
            self.db.update_user(user_id, {'welcome_bonus': 1, 'in_channel': 1})
            send_message(user_id, """
<b>🎉 HOŞ GELDİNİZ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>2₺ hoşgeldin bonusu hesabınıza yüklendi!</b>
💰 <b>Hemen görev yapmaya başlayabilirsiniz!</b>
""")
        
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
                        send_message(referrer_id, f"""
<b>🎉 REFERANS KAZANCI!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>Yeni referansınız:</b> {user.get('name', 'Kullanıcı')}
💰 <b>Kazandınız:</b> 1.00₺
📊 <b>Toplam referans:</b> {referrer.get('referrals', 0) + 1}

💡 <b>Referans linkinizi paylaşmaya devam edin!</b>
""")
        
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>🤖 GÖREV YAPSAM BOT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 Hoş geldin</b> {user.get('name', 'Kullanıcı')}!
<b>💰 Bakiye:</b> <code>{user.get('balance', 0):.2f}₺</code>
<b>📺 Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺

<b>🎯 Tamamlanan Görev:</b> {user.get('tasks_completed', 0)}
<b>👥 Referans:</b> {user.get('referrals', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📋 ANA MENÜ</b>
"""
        
        # Profesyonel ve temiz buton düzeni
        markup = {
            'inline_keyboard': [
                # Birinci satır: Ana işlemler
                [
                    {'text': '🎯 Görev Yap', 'callback_data': 'tasks'},
                    {'text': '📢 Kampanya', 'callback_data': 'create_campaign'}
                ],
                # İkinci satır: Finansal işlemler
                [
                    {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'},
                    {'text': '🔄 Çevir', 'callback_data': 'convert'}
                ],
                # Üçüncü satır: Kişisel işlemler
                [
                    {'text': '👤 Profil', 'callback_data': 'profile'},
                    {'text': '👥 Referans', 'callback_data': 'referral'}
                ],
                # Dördüncü satır: Yardım ve diğer
                [
                    {'text': '❓ Yardım', 'callback_data': 'help'},
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
    
    def show_convert_menu(self, user_id):
        user = self.db.get_user(user_id)
        normal_balance = user.get('balance', 0)
        
        if normal_balance < 1:
            message = f"""
<b>🔄 REKLAM BAKİYESİNE ÇEVİR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Normal Bakiye:</b> {normal_balance:.2f}₺
<b>📺 Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺

⚠️ <b>Yetersiz bakiye!</b>
• Minimum çevrim: 1₺
• Mevcut bakiye: {normal_balance:.2f}₺

💡 <b>Önce bakiye yükleyin:</b>
1. "💰 Bakiye Yükle" butonuna basın
2. Tutar seçin
3. TRX gönderin
"""
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '💰 Bakiye Yükle', 'callback_data': 'deposit'},
                        {'text': '🔙 Geri', 'callback_data': 'menu'}
                    ]
                ]
            }
        else:
            # Hesaplamalar
            half_amount = normal_balance / 2
            quarter_amount = normal_balance / 4
            
            message = f"""
<b>🔄 REKLAM BAKİYESİNE ÇEVİR</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Mevcut Bakiye:</b> {normal_balance:.2f}₺
<b>📺 Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺

<b>💡 Nasıl Çalışır?</b>
• Normal bakiyenizi reklam bakiyesine çevirebilirsiniz
• Çevrim oranı: <b>%{int(ADS_CONVERSION_RATE*100)}</b>
• Reklam bakiyesi ile reklam gösterimi yapabilirsiniz

<b>👇 Ne kadar çevirmek istersiniz?</b>
"""
            
            markup = {
                'inline_keyboard': [
                    # Tamamını çevir
                    [
                        {'text': f'💯 Tamamını Çevir ({normal_balance:.0f}₺)', 'callback_data': 'convert_all'}
                    ],
                    # Yarısını ve çeyreğini
                    [
                        {'text': f'½ Yarısını Çevir ({half_amount:.0f}₺)', 'callback_data': 'convert_half'},
                        {'text': f'¼ Çeyreğini Çevir ({quarter_amount:.0f}₺)', 'callback_data': 'convert_quarter'}
                    ],
                    # Özel tutar
                    [
                        {'text': f'🔢 Özel Tutar Gir', 'callback_data': 'convert_custom'},
                        {'text': '🔙 Geri', 'callback_data': 'menu'}
                    ]
                ]
            }
        
        send_message(user_id, message, markup)
    
    def convert_all_balance(self, user_id):
        user = self.db.get_user(user_id)
        normal_balance = user.get('balance', 0)
        
        if normal_balance < 1:
            send_message(user_id, "❌ Minimum çevrim tutarı 1₺!")
            self.show_convert_menu(user_id)
            return
        
        success, message = self.db.convert_to_ads_balance(user_id, normal_balance)
        
        if success:
            send_message(user_id, f"""
<b>✅ TAMAMI ÇEVRİLDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>{normal_balance:.2f}₺ reklam bakiyesine çevrildi!</b>

📊 <b>Detaylar:</b>
• Çevrilen: {normal_balance:.2f}₺
• Reklam Bakiyesi: +{normal_balance * ADS_CONVERSION_RATE:.2f}₺
• Çevrim Oranı: %{int(ADS_CONVERSION_RATE*100)}

💡 <b>Reklam bakiyeniz ile reklam gösterimi yapabilirsiniz!</b>
""")
        else:
            send_message(user_id, f"❌ {message}")
        
        time.sleep(1)
        self.show_main_menu(user_id)
    
    def convert_half_balance(self, user_id):
        user = self.db.get_user(user_id)
        half_amount = user.get('balance', 0) / 2
        
        if half_amount < 1:
            send_message(user_id, "❌ Çevrilecek tutar minimum 1₺ olmalı!")
            self.show_convert_menu(user_id)
            return
        
        success, message = self.db.convert_to_ads_balance(user_id, half_amount)
        
        if success:
            send_message(user_id, f"""
<b>✅ YARISI ÇEVRİLDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>{half_amount:.2f}₺ reklam bakiyesine çevrildi!</b>

📊 <b>Detaylar:</b>
• Çevrilen: {half_amount:.2f}₺
• Reklam Bakiyesi: +{half_amount * ADS_CONVERSION_RATE:.2f}₺
• Çevrim Oranı: %{int(ADS_CONVERSION_RATE*100)}
• Kalan Normal Bakiye: {user.get('balance', 0) - half_amount:.2f}₺

💡 <b>Reklam bakiyeniz ile reklam gösterimi yapabilirsiniz!</b>
""")
        else:
            send_message(user_id, f"❌ {message}")
        
        time.sleep(1)
        self.show_main_menu(user_id)
    
    def convert_quarter_balance(self, user_id):
        user = self.db.get_user(user_id)
        quarter_amount = user.get('balance', 0) / 4
        
        if quarter_amount < 1:
            send_message(user_id, "❌ Çevrilecek tutar minimum 1₺ olmalı!")
            self.show_convert_menu(user_id)
            return
        
        success, message = self.db.convert_to_ads_balance(user_id, quarter_amount)
        
        if success:
            send_message(user_id, f"""
<b>✅ ÇEYREĞİ ÇEVRİLDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>{quarter_amount:.2f}₺ reklam bakiyesine çevrildi!</b>

📊 <b>Detaylar:</b>
• Çevrilen: {quarter_amount:.2f}₺
• Reklam Bakiyesi: +{quarter_amount * ADS_CONVERSION_RATE:.2f}₺
• Çevrim Oranı: %{int(ADS_CONVERSION_RATE*100)}
• Kalan Normal Bakiye: {user.get('balance', 0) - quarter_amount:.2f}₺

💡 <b>Reklam bakiyeniz ile reklam gösterimi yapabilirsiniz!</b>
""")
        else:
            send_message(user_id, f"❌ {message}")
        
        time.sleep(1)
        self.show_main_menu(user_id)
    
    def start_custom_convert(self, user_id):
        user = self.db.get_user(user_id)
        
        self.set_user_state(user_id, 'convert_custom')
        send_message(user_id, f"""
<b>🔄 ÖZEL TUTAR ÇEVİRİMİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>💰 Mevcut Bakiye:</b> {user.get('balance', 0):.2f}₺
<b>📺 Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺

<b>💡 Çevrim Oranı:</b> %{int(ADS_CONVERSION_RATE*100)}
<b>⚠️ Minimum Tutar:</b> 1₺

<b>📝 Ne kadar çevirmek istersiniz?</b>
• Sadece sayı girin (örn: 15.5)
• Tüm bakiyeniz: {user.get('balance', 0):.2f}₺
• Yarısı: {user.get('balance', 0) / 2:.2f}₺
• Çeyreği: {user.get('balance', 0) / 4:.2f}₺

<code>/cancel</code> iptal etmek için
""")
    
    def handle_user_state(self, user_id, message, user_state):
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # /cancel komutu
        if 'text' in message and message['text'] == '/cancel':
            self.clear_user_state(user_id)
            send_message(user_id, "🔄 İşlem iptal edildi.")
            self.show_main_menu(user_id)
            return
        
        # ÖZEL TUTAR ÇEVİRME
        if state == 'convert_custom':
            try:
                amount = float(message['text'])
                user = self.db.get_user(user_id)
                
                if amount < 1:
                    send_message(user_id, "❌ Minimum çevrim tutarı 1₺!")
                    return
                
                if amount > user.get('balance', 0):
                    send_message(user_id, "❌ Yetersiz bakiye!")
                    return
                
                success, result_message = self.db.convert_to_ads_balance(user_id, amount)
                
                if success:
                    # Hesaplanan reklam bakiyesi
                    ads_amount = amount * ADS_CONVERSION_RATE
                    
                    send_message(user_id, f"""
<b>✅ ÖZEL TUTAR ÇEVRİLDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 <b>{amount:.2f}₺ reklam bakiyesine çevrildi!</b>

📊 <b>Detaylar:</b>
• Çevrilen: {amount:.2f}₺
• Reklam Bakiyesi: +{ads_amount:.2f}₺
• Çevrim Oranı: %{int(ADS_CONVERSION_RATE*100)}
• Kalan Normal Bakiye: {user.get('balance', 0) - amount:.2f}₺

💡 <b>Reklam bakiyeniz ile reklam gösterimi yapabilirsiniz!</b>
""")
                else:
                    send_message(user_id, f"❌ {result_message}")
                
                self.clear_user_state(user_id)
                time.sleep(1)
                self.show_main_menu(user_id)
                
            except ValueError:
                send_message(user_id, "❌ Geçersiz tutar! Lütfen sadece sayı girin (örn: 15.5)")
        
        # TXID BEKLEME
        elif state == 'waiting_txid':
            txid = message['text'].strip()
            
            if len(txid) < 10:
                send_message(user_id, "❌ Geçersiz TXID!")
                return
            
            try:
                deposit_data = data
                deposit_id = deposit_data['deposit_id']
                amount = deposit_data['amount']
                bonus = deposit_data['bonus']
                
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
                
                # Başarı mesajı
                send_message(user_id, f"""
<b>✅ BAKİYE YÜKLENDİ!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Toplam: {amount + bonus:.2f}₺</b>
• Yatırım: {amount:.2f}₺
• Bonus: {bonus:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})
• Yeni Bakiye: {new_balance:.2f}₺

🎉 <b>Hemen görev yapmaya başlayın!</b>
""")
                
                self.clear_user_state(user_id)
                time.sleep(2)
                self.show_main_menu(user_id)
                
            except Exception as e:
                print(f"❌ TXID hatası: {e}")
                send_message(user_id, "❌ İşlem kaydedilemedi!")
    
    def show_active_tasks(self, user_id):
        message = """
<b>🎯 AKTİF GÖREVLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 Bot Kampanyaları</b>
• Görev: Bot mesajı iletme
• Ödül: 2.5₺ her katılım
• Durum: 🟢 Aktif

<b>📢 Kanal Kampanyaları</b>
• Görev: Kanala katılma
• Ödül: 1.5₺ her katılım
• Durum: 🟢 Aktif

<b>👥 Grup Kampanyaları</b>
• Görev: Gruba katılma
• Ödül: 1₺ her katılım
• Durum: 🟢 Aktif

💡 <b>Kendi kampanyanızı oluşturun ve daha fazla kazanın!</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📢 Kampanya Oluştur', 'callback_data': 'create_campaign'},
                    {'text': '🔙 Geri', 'callback_data': 'menu'}
                ]
            ]
        }
        send_message(user_id, message, markup)
    
    def start_campaign_type_selection(self, user_id):
        message = """
<b>📢 KAMPANYA OLUŞTURMA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👇 Kampanya Türünü Seçin:</b>

<b>🤖 BOT KAMPANYASI</b>
• Görev: Bot mesajı iletme
• Ödül: 2.5₺ her katılım
• Kolay: Otomatik aktif

<b>📢 KANAL KAMPANYASI</b>
• Görev: Kanala katılma
• Ödül: 1.5₺ her katılım
• Gerekli: Bot kanalda admin

<b>👥 GRUP KAMPANYASI</b>
• Görev: Gruba katılma
• Ödül: 1₺ her katılım
• Gerekli: Bot grupta admin
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
    
    def show_profile(self, user_id):
        user = self.db.get_user(user_id)
        
        message = f"""
<b>👤 PROFİL BİLGİLERİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👤 İsim:</b> {user.get('name', 'Kullanıcı')}
<b>🆔 Kullanıcı ID:</b> <code>{user_id}</code>

<b>💰 Finansal Durum:</b>
• Normal Bakiye: {user.get('balance', 0):.2f}₺
• Reklam Bakiyesi: {user.get('ads_balance', 0):.2f}₺
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
                    {'text': '🔄 Çevir', 'callback_data': 'convert'}
                ],
                [
                    {'text': '👥 Referans', 'callback_data': 'referral'},
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

<b>📊 Referans İstatistikleri:</b>
• Toplam Referans: {user.get('referrals', 0)}
• Referans Kazancı: {user.get('ref_earned', 0):.2f}₺

<b>💰 Kazanç Sistemi:</b>
• Her referans: <b>1₺ bonus</b>
• Sınırsız referans: <b>Sınırsız kazanç</b>

<b>🔗 Referans Linkiniz:</b>
<code>{referral_link}</code>

<b>💡 Nasıl Çalışır:</b>
1. Linkinizi arkadaşlarınızla paylaşın
2. Arkadaşlarınız linke tıklayarak kaydolur
3. <b>Hemen 1₺ bonus</b> alırsınız
4. Kazanmaya devam edersiniz
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
    
    def show_deposit_menu(self, user_id):
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
                    {'text': f'25₺ → 33.75₺', 'callback_data': 'deposit_amount_25'},
                    {'text': f'50₺ → 67.50₺', 'callback_data': 'deposit_amount_50'}
                ],
                [
                    {'text': f'100₺ → 135₺', 'callback_data': 'deposit_amount_100'},
                    {'text': f'200₺ → 270₺', 'callback_data': 'deposit_amount_200'}
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
        total = amount + bonus
        
        message = f"""
<b>💰 ÖDEME BİLGİLERİ</b>
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

<b>📋 Şartlar:</b>
• Minimum çekim: {MIN_WITHDRAW}₺
• İşlem süresi: 24 saat
• Komisyon: Yok

<b>⚠️ ÖNEMLİ:</b>
• Sadece TRX (Tron) cüzdan adresi kabul edilir!
• Yanlış cüzdan adresi girerseniz para kaybolur!

<b>🔄 Öneri:</b>
• Önce reklam bakiyesine çevirmeyi deneyin
• Reklam bakiyesi daha karlı olabilir
"""
        
        if user.get('balance', 0) >= MIN_WITHDRAW:
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '💸 Çekim Yap', 'callback_data': 'withdraw'},
                        {'text': '🔄 Reklam Bakiyesine Çevir', 'callback_data': 'convert'}
                    ],
                    [
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
    
    def show_help(self, user_id):
        message = """
<b>❓ YARDIM VE DESTEK</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🤖 BOT NASIL ÇALIŞIR?</b>
1. 📢 Kanalımıza katılın (@GY_Refim)
2. 💰 Bakiye yükleyin veya görev yapın
3. 🎯 Para kazanmaya başlayın!

<b>💰 BAKİYE NASIL YÜKLENİR?</b>
1. "💰 Bakiye Yükle" butonuna tıklayın
2. Tutar seçin (25-200₺)
3. TRX gönderin
4. TXID'yi gönderin
5. Bonuslu bakiye hesabınıza yüklenecek

<b>🔄 REKLAM BAKİYESİNE NASIL ÇEVİRİLİR?</b>
1. "🔄 Çevir" butonuna tıklayın
2. Çevirmek istediğiniz tutarı seçin
   • Tamamını
   • Yarısını
   • Çeyreğini
   • Özel tutar
3. Onaylayın
4. Reklam bakiyenize %80 oranında çevrilecek

<b>👥 REFERANS SİSTEMİ</b>
• Her davet için 1₺ bonus
• Linkinizi paylaşın
• Sınırsız kazanç fırsatı

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
        
        message = f"""
<b>👑 ADMIN PANELİ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>📊 SİSTEM İSTATİSTİKLERİ</b>
• 👥 Toplam Kullanıcı: {total_users}

<b>🛠️ YÖNETİM ARAÇLARI</b>
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
<b>📊 DETAYLI İSTATİSTİKLER</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>👥 KULLANICI İSTATİSTİKLERİ</b>
• Toplam Kullanıcı: {total_users}

<b>💰 FİNANSAL İSTATİSTİKLER</b>
• Toplam Yatırım Sayısı: {total_deposits}

<b>📢 KAMPANYA İSTATİSTİKLERİ</b>
• Toplam Kampanya: {total_campaigns}

<b>⏰ SİSTEM DURUMU:</b> ✅ ÇALIŞIYOR
<b>🔄 SON KONTROL:</b> {get_turkey_time().strftime('%H:%M')}
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
            message = "👥 <b>Hiç kullanıcı bulunamadı</b>"
        else:
            message = "<b>👥 SON 10 KULLANICI</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for usr in users:
                referred = "✅" if usr['referred_by'] else "❌"
                message += f"""👤 <b>{usr['name'][:15]}</b>
├ <b>Bakiye:</b> {usr['balance']:.1f}₺
├ <b>Referans:</b> {usr['referrals']} {referred}
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
                message += f"""{status} <b>Depozit #{dep['deposit_id'][:8]}</b>
├ <b>Tutar:</b> {dep['amount_try']:.2f}₺
├ <b>Bonus:</b> {dep['bonus_amount']:.2f}₺
└ <b>Durum:</b> {dep['status']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        markup = {
            'inline_keyboard': [[
                {'text': '🔙 Geri', 'callback_data': 'admin_panel'}
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

📭 <b>Henüz kampanyanız bulunmuyor</b>

💡 <b>İlk kampanyanızı oluşturun!</b>
"""
        else:
            message = "<b>📋 KAMPANYALARIM</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for camp in campaigns:
                status = "🟢" if camp['status'] == 'active' else "🟡" if camp['status'] == 'pending' else "🔴"
                message += f"""{status} <b>{camp['name'][:20]}</b>
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

# Ana Program
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v19.0                      ║
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
    print("🔄 Reklam Bakiyesi Çevrimi: %80")
    print("🏧 Para Çekme: Minimum 10₺")
    print("🎨 Arayüz: Profesyonel ve Kullanıcı Dostu")
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
