"""
╔════════════════════════════════════════════════════════════════╗
║                    GÖREV YAPSAM BOT v7.0                       ║
║            PARA ÇEKİM + KAMPANYA SİSTEMİ + ADMIN YETKİ         ║
╚════════════════════════════════════════════════════════════════╝
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
import threading
import sqlite3
from flask import Flask, jsonify
import logging
import hashlib

# ================= 1. LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= 2. TELEGRAM AYARLARI =================
# Render'da environment variables'dan al
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "7904032877")
MANDATORY_CHANNEL = os.environ.get("MANDATORY_CHANNEL", "GY_Refim")

if not TOKEN:
    raise ValueError("⚠️ TELEGRAM_BOT_TOKEN environment variable bulunamadı!")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

print("=" * 50)
print("🤖 GÖREV YAPSAM BOT v7.0")
print("💰 PARA ÇEKİM + KAMPANYA SİSTEMİ")
print("=" * 50)

# ================= 3. SQLITE VERİTABANI =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        """Tabloları oluştur"""
        # Kullanıcılar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                username TEXT,
                balance REAL DEFAULT 0.0,
                total_earned REAL DEFAULT 0.0,
                tasks_completed INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                ref_earned REAL DEFAULT 0.0,
                daily_streak INTEGER DEFAULT 0,
                last_daily TEXT,
                language TEXT DEFAULT 'tr',
                in_channel INTEGER DEFAULT 0,
                created_at TEXT,
                welcome_bonus INTEGER DEFAULT 0,
                withdrawal_total REAL DEFAULT 0.0,
                withdrawal_count INTEGER DEFAULT 0
            )
        ''')
        
        # Görevler/Kampanyalar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                link TEXT,
                budget REAL,
                creator_id TEXT,
                creator_name TEXT,
                task_type TEXT,
                price_per_task REAL,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft', -- draft, pending, active, completed, cancelled
                requires_forward INTEGER DEFAULT 0,
                forward_channel TEXT,
                created_at TEXT,
                admin_approved INTEGER DEFAULT 0,
                steps TEXT -- JSON formatında adımlar
            )
        ''')
        
        # Katılımlar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS participations (
                participation_id TEXT PRIMARY KEY,
                user_id TEXT,
                campaign_id TEXT,
                status TEXT DEFAULT 'pending', -- pending, completed, verified, rejected
                proof_text TEXT,
                screenshot_id TEXT,
                created_at TEXT,
                verified_at TEXT,
                reward_paid INTEGER DEFAULT 0
            )
        ''')
        
        # Para çekim talepleri tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                withdrawal_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                method TEXT, -- papara, bank, crypto
                account_info TEXT,
                status TEXT DEFAULT 'pending', -- pending, processing, completed, rejected
                created_at TEXT,
                processed_at TEXT,
                admin_notes TEXT
            )
        ''')
        
        # Bot admin durumu tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_admin_status (
                chat_id TEXT PRIMARY KEY,
                chat_title TEXT,
                is_admin INTEGER DEFAULT 0,
                added_by TEXT,
                added_at TEXT
            )
        ''')
        
        self.conn.commit()
        print("✅ Veritabanı tabloları oluşturuldu")
    
    def get_user(self, user_id):
        """Kullanıcıyı getir veya oluştur"""
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            # Yeni kullanıcı oluştur
            now = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO users 
                (user_id, name, username, balance, created_at, welcome_bonus)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, '', '', 0.0, now, 0))
            self.conn.commit()
            
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        
        return dict(user) if user else {}
    
    def update_user(self, user_id, data):
        """Kullanıcıyı güncelle"""
        if not data:
            return False
        
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(user_id)
        
        query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
        self.cursor.execute(query, values)
        self.conn.commit()
        return True
    
    def add_balance(self, user_id, amount):
        """Bakiye ekle"""
        user = self.get_user(user_id)
        new_balance = user.get('balance', 0) + amount
        
        self.cursor.execute('''
            UPDATE users 
            SET balance = ?, total_earned = total_earned + ? 
            WHERE user_id = ?
        ''', (new_balance, amount, user_id))
        self.conn.commit()
        return True
    
    def create_campaign(self, campaign_data):
        """Yeni kampanya oluştur"""
        try:
            self.cursor.execute('''
                INSERT INTO campaigns 
                (campaign_id, name, description, link, budget, creator_id, 
                 creator_name, task_type, price_per_task, max_participants, 
                 status, requires_forward, forward_channel, created_at, steps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign_data['campaign_id'],
                campaign_data['name'],
                campaign_data['description'],
                campaign_data['link'],
                campaign_data['budget'],
                campaign_data['creator_id'],
                campaign_data['creator_name'],
                campaign_data['task_type'],
                campaign_data['price_per_task'],
                campaign_data['max_participants'],
                campaign_data.get('status', 'draft'),
                campaign_data.get('requires_forward', 0),
                campaign_data.get('forward_channel', ''),
                datetime.now().isoformat(),
                campaign_data.get('steps', '[]')
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Kampanya oluşturma hatası: {e}")
            return False
    
    def create_withdrawal(self, withdrawal_data):
        """Para çekim talebi oluştur"""
        try:
            self.cursor.execute('''
                INSERT INTO withdrawals 
                (withdrawal_id, user_id, amount, method, account_info, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                withdrawal_data['withdrawal_id'],
                withdrawal_data['user_id'],
                withdrawal_data['amount'],
                withdrawal_data['method'],
                withdrawal_data['account_info'],
                withdrawal_data.get('status', 'pending'),
                datetime.now().isoformat()
            ))
            
            # Kullanıcının bakiyesini düş
            self.cursor.execute('''
                UPDATE users SET balance = balance - ? WHERE user_id = ?
            ''', (withdrawal_data['amount'], withdrawal_data['user_id']))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Para çekim talebi oluşturma hatası: {e}")
            return False
    
    def check_bot_admin(self, chat_id):
        """Botun chat'te admin olup olmadığını kontrol et"""
        self.cursor.execute("SELECT is_admin FROM bot_admin_status WHERE chat_id = ?", (chat_id,))
        result = self.cursor.fetchone()
        return result['is_admin'] == 1 if result else False
    
    def set_bot_admin(self, chat_id, chat_title, added_by, is_admin=True):
        """Botun admin durumunu güncelle"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO bot_admin_status 
                (chat_id, chat_title, is_admin, added_by, added_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, chat_title, 1 if is_admin else 0, added_by, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Bot admin durumu güncelleme hatası: {e}")
            return False

# ================= 4. FLASK APP =================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online", 
        "bot": "Görev Yapsam Bot v7.0",
        "features": ["Para Çekim", "Kampanya Sistemi", "Admin Yetki Kontrolü"]
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

# ================= 5. TELEGRAM FONKSİYONLARI =================
def send_telegram_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    """Telegram'a mesaj gönder"""
    url = BASE_URL + "sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Mesaj gönderme hatası: {e}")
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    """Callback'e cevap ver"""
    url = BASE_URL + "answerCallbackQuery"
    data = {
        'callback_query_id': callback_id,
        'show_alert': show_alert
    }
    
    if text:
        data['text'] = text
    
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def get_chat_member(chat_id, user_id):
    """Kanal/grup üyeliğini kontrol et"""
    url = BASE_URL + "getChatMember"
    data = {
        'chat_id': chat_id,
        'user_id': int(user_id)
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get('ok'):
            status = result['result']['status']
            return status in ['member', 'administrator', 'creator']
    except:
        pass
    return False

def get_chat_administrators(chat_id):
    """Chat adminlerini getir"""
    url = BASE_URL + "getChatAdministrators"
    data = {'chat_id': chat_id}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get('ok'):
            return result['result']
    except:
        pass
    return []

def get_bot_id():
    """Botun ID'sini al"""
    url = BASE_URL + "getMe"
    try:
        response = requests.get(url, timeout=10)
        result = response.json()
        if result.get('ok'):
            return str(result['result']['id'])
    except:
        pass
    return None

# ================= 6. BOT SİSTEMİ =================
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.running = False
        self.user_states = {}  # Kullanıcı durumlarını takip et
        self.campaign_creation = {}  # Kampanya oluşturma sürecini takip et
        print("🤖 Bot sistemi başlatıldı")
    
    def set_user_state(self, user_id, state, data=None):
        """Kullanıcı durumunu ayarla"""
        if data is None:
            data = {}
        self.user_states[user_id] = {'state': state, 'data': data}
    
    def get_user_state(self, user_id):
        """Kullanıcı durumunu getir"""
        return self.user_states.get(user_id, {'state': None, 'data': {}})
    
    def clear_user_state(self, user_id):
        """Kullanıcı durumunu temizle"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def start_polling(self):
        """Polling başlat"""
        self.running = True
        offset = 0
        
        print("🔄 Telegram polling başlatıldı...")
        
        while self.running:
            try:
                url = BASE_URL + "getUpdates"
                params = {
                    'offset': offset,
                    'timeout': 30,
                    'allowed_updates': ['message', 'callback_query', 'chat_member', 'my_chat_member']
                }
                
                response = requests.get(url, params=params, timeout=35)
                
                if response.status_code == 409:
                    print("⚠️ 409 Conflict - 5 saniye bekleniyor...")
                    time.sleep(5)
                    offset = 0
                    continue
                
                data = response.json()
                
                if data.get('ok') and data.get('result'):
                    updates = data['result']
                    
                    for update in updates:
                        offset = update['update_id'] + 1
                        
                        # BOTUN GRUPTA DURUMU DEĞİŞTİ
                        if 'my_chat_member' in update:
                            threading.Thread(
                                target=self.process_chat_member_update,
                                args=(update['my_chat_member'],),
                                daemon=True
                            ).start()
                        
                        # MESAJ GELDİ
                        elif 'message' in update:
                            threading.Thread(
                                target=self.process_message,
                                args=(update['message'],),
                                daemon=True
                            ).start()
                        
                        # CALLBACK GELDİ
                        elif 'callback_query' in update:
                            threading.Thread(
                                target=self.process_callback,
                                args=(update['callback_query'],),
                                daemon=True
                            ).start()
                
            except Exception as e:
                print(f"❌ Polling hatası: {e}")
                time.sleep(2)
    
    def process_chat_member_update(self, chat_member_update):
        """Botun gruptaki durum değişikliğini işle"""
        try:
            chat = chat_member_update['chat']
            new_status = chat_member_update['new_chat_member']['status']
            old_status = chat_member_update['old_chat_member']['status']
            
            chat_id = str(chat['id'])
            chat_title = chat.get('title', 'Bilinmeyen')
            
            print(f"🤖 Bot durumu değişti: {chat_title} - {old_status} -> {new_status}")
            
            if new_status == 'administrator':
                # Bot admin yapıldı
                added_by = str(chat_member_update.get('from', {}).get('id', 'unknown'))
                self.db.set_bot_admin(chat_id, chat_title, added_by, True)
                
                # Admin'e bildir
                admin_msg = (
                    f"✅ <b>BOT ADMIN YAPILDI!</b>\n\n"
                    f"📢 <b>Grup/Kanal:</b> {chat_title}\n"
                    f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
                    f"👤 <b>Ekleyen:</b> {chat_member_update.get('from', {}).get('first_name', 'Bilinmeyen')}\n"
                    f"⏰ <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                send_telegram_message(ADMIN_ID, admin_msg)
                
            elif new_status in ['kicked', 'left']:
                # Bot gruptan çıkarıldı
                self.db.set_bot_admin(chat_id, chat_title, '', False)
                
        except Exception as e:
            print(f"❌ Chat member update hatası: {e}")
    
    def process_message(self, message):
        """Gelen mesajı işle"""
        try:
            if 'from' not in message:
                return
            
            user_id = str(message['from']['id'])
            user_state = self.get_user_state(user_id)
            
            # Kullanıcı bilgilerini güncelle
            user = self.db.get_user(user_id)
            if not user.get('name'):
                self.db.update_user(user_id, {
                    'name': message['from'].get('first_name', 'Kullanıcı'),
                    'username': message['from'].get('username', '')
                })
            
            # Özel durumlar (kampanya oluşturma vs.)
            if user_state['state']:
                self.handle_user_state(user_id, message, user_state)
                return
            
            # Komutlar
            if 'text' in message:
                text = message['text'].lower()
                
                if text.startswith('/start'):
                    self.handle_start(user_id, message['text'])
                elif text == '/menu':
                    self.show_main_menu(user_id)
                elif text == '/admin' and user_id == ADMIN_ID:
                    self.show_admin_panel(user_id)
                elif text == '/checkadmin':
                    self.check_bot_admin_status(user_id, message)
                elif text == '/withdraw':
                    self.show_withdraw(user_id)
                elif text == '/createcampaign':
                    self.start_campaign_creation(user_id)
            
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def handle_user_state(self, user_id, message, user_state):
        """Kullanıcı durumuna göre mesajı işle"""
        state = user_state['state']
        data = user_state['data']
        
        if state == 'creating_campaign_name':
            # Kampanya ismi alındı
            data['name'] = message['text']
            self.set_user_state(user_id, 'creating_campaign_desc', data)
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "✅ Onayla", 'callback_data': 'camp_confirm_name'},
                        {'text': "❌ İptal", 'callback_data': 'camp_cancel'}
                    ]
                ]
            }
            
            send_telegram_message(
                user_id,
                f"📝 <b>Kampanya İsmi:</b> {message['text']}\n\n"
                f"✅ Onaylıyor musunuz?",
                markup
            )
        
        elif state == 'creating_campaign_desc':
            # Kampanya açıklaması alındı
            data['description'] = message['text']
            self.set_user_state(user_id, 'creating_campaign_link', data)
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "✅ Onayla", 'callback_data': 'camp_confirm_desc'},
                        {'text': "❌ İptal", 'callback_data': 'camp_cancel'}
                    ]
                ]
            }
            
            send_telegram_message(
                user_id,
                f"📄 <b>Kampanya Açıklaması:</b>\n{message['text']}\n\n"
                f"✅ Onaylıyor musunuz?",
                markup
            )
        
        elif state == 'creating_campaign_link':
            # Kampanya linki alındı
            data['link'] = message['text']
            self.set_user_state(user_id, 'creating_campaign_budget', data)
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "✅ Onayla", 'callback_data': 'camp_confirm_link'},
                        {'text': "❌ İptal", 'callback_data': 'camp_cancel'}
                    ]
                ]
            }
            
            send_telegram_message(
                user_id,
                f"🔗 <b>Kampanya Linki:</b>\n{message['text']}\n\n"
                f"✅ Onaylıyor musunuz?",
                markup
            )
        
        elif state == 'creating_campaign_budget':
            # Kampanya bütçesi alındı
            try:
                budget = float(message['text'])
                data['budget'] = budget
                self.set_user_state(user_id, 'creating_campaign_final', data)
                
                # Özet göster
                user = self.db.get_user(user_id)
                summary = (
                    f"🎯 <b>KAMPANYA ÖZETİ</b>\n"
                    f"══════════════════════════════\n\n"
                    f"📛 <b>İsim:</b> {data.get('name', 'Belirtilmedi')}\n"
                    f"📄 <b>Açıklama:</b> {data.get('description', 'Belirtilmedi')}\n"
                    f"🔗 <b>Link:</b> {data.get('link', 'Belirtilmedi')}\n"
                    f"💰 <b>Bütçe:</b> {budget:.2f}₺\n"
                    f"👤 <b>Oluşturan:</b> {user.get('name', 'Kullanıcı')}\n\n"
                    f"⚠️ <b>Not:</b> Kampanya admin onayından sonra aktif olacaktır."
                )
                
                markup = {
                    'inline_keyboard': [
                        [
                            {'text': "✅ Kampanyayı Oluştur", 'callback_data': 'camp_create_final'},
                            {'text': "❌ İptal Et", 'callback_data': 'camp_cancel'}
                        ]
                    ]
                }
                
                send_telegram_message(user_id, summary, markup)
                
            except ValueError:
                send_telegram_message(
                    user_id,
                    "❌ <b>Geçersiz bütçe!</b>\n"
                    "Lütfen geçerli bir sayı girin (örn: 100, 50.5)"
                )
        
        elif state == 'withdraw_method':
            # Para çekim yöntemi seçildi
            if message['text'] in ['Papara', 'Banka', 'Kripto']:
                data['method'] = message['text']
                self.set_user_state(user_id, 'withdraw_amount', data)
                
                send_telegram_message(
                    user_id,
                    f"💸 <b>Para Çekme - Adım 2/3</b>\n\n"
                    f"✅ <b>Yöntem:</b> {message['text']}\n\n"
                    f"💰 <b>Çekmek istediğiniz tutarı girin:</b>\n"
                    f"(Minimum: 20₺, Maksimum: Bakiyeniz)"
                )
        
        elif state == 'withdraw_amount':
            # Para çekim tutarı alındı
            try:
                amount = float(message['text'])
                user = self.db.get_user(user_id)
                balance = user.get('balance', 0)
                
                if amount < 20:
                    send_telegram_message(
                        user_id,
                        f"❌ <b>Minimum çekim tutarı 20₺!</b>\n\n"
                        f"💰 Mevcut bakiye: {balance:.2f}₺"
                    )
                elif amount > balance:
                    send_telegram_message(
                        user_id,
                        f"❌ <b>Yetersiz bakiye!</b>\n\n"
                        f"💰 Mevcut bakiye: {balance:.2f}₺\n"
                        f"💸 İstenen tutar: {amount:.2f}₺"
                    )
                else:
                    data['amount'] = amount
                    self.set_user_state(user_id, 'withdraw_account', data)
                    
                    method = data.get('method', 'Bilinmiyor')
                    
                    send_telegram_message(
                        user_id,
                        f"💸 <b>Para Çekme - Adım 3/3</b>\n\n"
                        f"✅ <b>Yöntem:</b> {method}\n"
                        f"💰 <b>Tutar:</b> {amount:.2f}₺\n\n"
                        f"📋 <b>{method} bilgilerinizi girin:</b>\n"
                        f"• Papara için: Papara numarası\n"
                        f"• Banka için: IBAN\n"
                        f"• Kripto için: Cüzdan adresi"
                    )
                    
            except ValueError:
                send_telegram_message(
                    user_id,
                    "❌ <b>Geçersiz tutar!</b>\n"
                    "Lütfen geçerli bir sayı girin (örn: 50, 100.5)"
                )
        
        elif state == 'withdraw_account':
            # Hesap bilgileri alındı
            data['account_info'] = message['text']
            self.set_user_state(user_id, 'withdraw_confirm', data)
            
            # Özet göster
            summary = (
                f"💸 <b>PARA ÇEKİM ÖZETİ</b>\n"
                f"══════════════════════════════\n\n"
                f"👤 <b>Kullanıcı:</b> {self.db.get_user(user_id).get('name', 'Kullanıcı')}\n"
                f"💰 <b>Tutar:</b> {data.get('amount', 0):.2f}₺\n"
                f"📋 <b>Yöntem:</b> {data.get('method', 'Bilinmiyor')}\n"
                f"🔢 <b>Hesap:</b> {message['text']}\n\n"
                f"⚠️ <b>Not:</b> İşlem 24-48 saat içinde tamamlanacaktır."
            )
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "✅ Onayla", 'callback_data': 'withdraw_confirm_final'},
                        {'text': "❌ İptal", 'callback_data': 'withdraw_cancel'}
                    ]
                ]
            }
            
            send_telegram_message(user_id, summary, markup)
            self.clear_user_state(user_id)
    
    def process_callback(self, callback):
        """Callback işle"""
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # Cevap gönder
            answer_callback(callback_id)
            
            # Özel callback'ler
            if data == 'joined':
                self.handle_joined(user_id)
            
            elif data == 'menu':
                self.show_main_menu(user_id)
            
            elif data == 'withdraw':
                self.show_withdraw(user_id)
            
            elif data == 'start_withdraw':
                self.start_withdrawal_process(user_id)
            
            elif data.startswith('withdraw_confirm_'):
                if data == 'withdraw_confirm_final':
                    self.finalize_withdrawal(user_id)
                elif data == 'withdraw_cancel':
                    self.clear_user_state(user_id)
                    send_telegram_message(user_id, "❌ Para çekim işlemi iptal edildi.")
            
            elif data == 'create_campaign':
                self.start_campaign_creation(user_id)
            
            elif data.startswith('camp_'):
                self.handle_campaign_callback(user_id, data)
            
            elif data == 'check_admin_status':
                self.check_bot_admin_status(user_id, callback.get('message', {}))
            
            elif data == 'forward_on':
                self.set_forward_requirement(user_id, True)
            
            elif data == 'forward_off':
                self.set_forward_requirement(user_id, False)
            
            else:
                # Diğer callback'ler (eski sistemle uyumluluk)
                self.process_legacy_callback(user_id, data)
                
        except Exception as e:
            print(f"❌ Callback işleme hatası: {e}")
    
    def handle_campaign_callback(self, user_id, data):
        """Kampanya callback'lerini işle"""
        user_state = self.get_user_state(user_id)
        
        if data == 'camp_cancel':
            self.clear_user_state(user_id)
            send_telegram_message(user_id, "❌ Kampanya oluşturma iptal edildi.")
        
        elif data == 'camp_confirm_name':
            send_telegram_message(
                user_id,
                "📄 <b>Kampanya Açıklaması</b>\n\n"
                "Lütfen kampanya açıklamasını girin:"
            )
        
        elif data == 'camp_confirm_desc':
            send_telegram_message(
                user_id,
                "🔗 <b>Kampanya Linki</b>\n\n"
                "Lütfen kampanya linkini girin:"
            )
        
        elif data == 'camp_confirm_link':
            send_telegram_message(
                user_id,
                "💰 <b>Kampanya Bütçesi</b>\n\n"
                "Lütfen kampanya bütçesini girin (₺):"
            )
        
        elif data == 'camp_create_final':
            self.finalize_campaign_creation(user_id, user_state['data'])
    
    def finalize_campaign_creation(self, user_id, campaign_data):
        """Kampanya oluşturmayı tamamla"""
        try:
            # Kampanya ID oluştur
            campaign_id = hashlib.md5(
                f"{user_id}{time.time()}{campaign_data['name']}".encode()
            ).hexdigest()[:10].upper()
            
            # Kampanya verilerini hazırla
            user = self.db.get_user(user_id)
            full_data = {
                'campaign_id': campaign_id,
                'name': campaign_data.get('name', 'İsimsiz'),
                'description': campaign_data.get('description', 'Açıklama yok'),
                'link': campaign_data.get('link', ''),
                'budget': campaign_data.get('budget', 0),
                'creator_id': user_id,
                'creator_name': user.get('name', 'Kullanıcı'),
                'task_type': 'custom',
                'price_per_task': 1.0,  # Varsayılan
                'max_participants': int(campaign_data.get('budget', 0) / 1.0),
                'status': 'pending',
                'requires_forward': 0,
                'forward_channel': '',
                'steps': json.dumps(['Linke tıkla', 'Formu doldur', 'Ekran görüntüsü al'])
            }
            
            # Veritabanına kaydet
            if self.db.create_campaign(full_data):
                # Kullanıcıya bilgi ver
                send_telegram_message(
                    user_id,
                    f"✅ <b>KAMPANYA OLUŞTURULDU!</b>\n\n"
                    f"📛 <b>İsim:</b> {full_data['name']}\n"
                    f"💰 <b>Bütçe:</b> {full_data['budget']:.2f}₺\n"
                    f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
                    f"⏳ <b>Durum:</b> Admin onayı bekleniyor...\n"
                    f"✅ Admin onayından sonra kampanya aktif olacaktır."
                )
                
                # Admin'e bildir
                admin_msg = (
                    f"🔔 <b>YENİ KAMPANYA ONAY BEKLİYOR</b>\n\n"
                    f"📛 <b>İsim:</b> {full_data['name']}\n"
                    f"👤 <b>Oluşturan:</b> {user.get('name', 'Kullanıcı')}\n"
                    f"🆔 <b>Kullanıcı ID:</b> {user_id}\n"
                    f"💰 <b>Bütçe:</b> {full_data['budget']:.2f}₺\n"
                    f"🔗 <b>Link:</b> {full_data['link']}\n"
                    f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
                    f"📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                
                markup = {
                    'inline_keyboard': [
                        [
                            {'text': "✅ Onayla", 'callback_data': f'admin_approve_campaign_{campaign_id}'},
                            {'text': "❌ Reddet", 'callback_data': f'admin_reject_campaign_{campaign_id}'}
                        ]
                    ]
                }
                
                send_telegram_message(ADMIN_ID, admin_msg, markup)
                
                self.clear_user_state(user_id)
            else:
                send_telegram_message(user_id, "❌ Kampanya oluşturulurken bir hata oluştu!")
                
        except Exception as e:
            print(f"❌ Kampanya oluşturma hatası: {e}")
            send_telegram_message(user_id, "❌ Kampanya oluşturulurken bir hata oluştu!")
    
    def start_campaign_creation(self, user_id):
        """Kampanya oluşturma sürecini başlat"""
        # Kanal kontrolü
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            send_telegram_message(
                user_id,
                f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}"
            )
            return
        
        self.set_user_state(user_id, 'creating_campaign_name', {})
        
        send_telegram_message(
            user_id,
            "🎯 <b>YENİ KAMPANYA OLUŞTUR</b>\n"
            "══════════════════════════════\n\n"
            "📝 <b>Adım 1/4 - Kampanya İsmi</b>\n\n"
            "Lütfen kampanya ismini girin:"
        )
    
    def show_withdraw(self, user_id):
        """PARA ÇEKME MENÜSÜ"""
        user = self.db.get_user(user_id)
        balance = user.get('balance', 0)
        
        # Son çekimler
        self.db.cursor.execute(
            "SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT 3",
            (user_id,)
        )
        recent_withdrawals = self.db.cursor.fetchall()
        
        message = (
            f"💸 <b>PARA ÇEKME</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Mevcut Bakiye:</b> {balance:.2f}₺\n"
            f"📊 <b>Minimum Çekim:</b> 20₺\n"
            f"⏰ <b>İşlem Süresi:</b> 24-48 saat\n\n"
            f"🎯 <b>YÖNTEMLER</b>\n"
            f"• 📱 Papara\n"
            f"• 🏦 Banka Havalesi\n"
            f"• ₿ Kripto Para\n\n"
            f"📋 <b>SON İŞLEMLER:</b>\n"
        )
        
        if recent_withdrawals:
            for wd in recent_withdrawals:
                status_icon = "✅" if wd['status'] == 'completed' else "⏳" if wd['status'] == 'processing' else "🔄"
                message += f"{status_icon} {wd['amount']:.2f}₺ - {wd['status']}\n"
        else:
            message += "Henüz çekim yapılmamış.\n"
        
        message += f"\n⚠️ <i>İşlem ücreti yoktur.</i>"
        
        markup = {
            'inline_keyboard': []
        }
        
        # Minimum kontrolü
        if balance >= 20.0:
            markup['inline_keyboard'].append([
                {'text': "💸 PARA ÇEK", 'callback_data': 'start_withdraw'}
            ])
        else:
            markup['inline_keyboard'].append([
                {'text': f"❌ Minimum: 20₺ (Bakiyen: {balance:.2f}₺)", 'callback_data': 'none'}
            ])
        
        markup['inline_keyboard'].append([
            {'text': "📊 Bakiye", 'callback_data': 'balance'},
            {'text': "🔙 Geri", 'callback_data': 'menu'}
        ])
        
        send_telegram_message(user_id, message, markup)
    
    def start_withdrawal_process(self, user_id):
        """Para çekim sürecini başlat"""
        user = self.db.get_user(user_id)
        balance = user.get('balance', 0)
        
        if balance < 20.0:
            send_telegram_message(
                user_id,
                f"❌ <b>Minimum çekim tutarı 20₺!</b>\n\n"
                f"💰 Mevcut bakiye: {balance:.2f}₺"
            )
            return
        
        self.set_user_state(user_id, 'withdraw_method', {})
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📱 Papara", 'callback_data': 'withdraw_method_papara'},
                    {'text': "🏦 Banka", 'callback_data': 'withdraw_method_banka'}
                ],
                [
                    {'text': "₿ Kripto", 'callback_data': 'withdraw_method_kripto'},
                    {'text': "❌ İptal", 'callback_data': 'withdraw_cancel'}
                ]
            ]
        }
        
        send_telegram_message(
            user_id,
            f"💸 <b>PARA ÇEKME - Adım 1/3</b>\n\n"
            f"💰 <b>Mevcut bakiye:</b> {balance:.2f}₺\n\n"
            f"👇 <b>Para çekme yöntemini seç:</b>",
            markup
        )
    
    def finalize_withdrawal(self, user_id):
        """Para çekim talebini tamamla"""
        user_state = self.get_user_state(user_id)
        
        if not user_state['data']:
            send_telegram_message(user_id, "❌ Geçersiz işlem!")
            return
        
        # Talep ID oluştur
        withdrawal_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        withdrawal_data = {
            'withdrawal_id': withdrawal_id,
            'user_id': user_id,
            'amount': user_state['data'].get('amount', 0),
            'method': user_state['data'].get('method', 'Bilinmiyor'),
            'account_info': user_state['data'].get('account_info', ''),
            'status': 'pending'
        }
        
        # Veritabanına kaydet
        if self.db.create_withdrawal(withdrawal_data):
            # Kullanıcıya bilgi ver
            user = self.db.get_user(user_id)
            
            message = (
                f"✅ <b>PARA ÇEKİM TALEBİ OLUŞTURULDU!</b>\n\n"
                f"📋 <b>Talep No:</b> <code>{withdrawal_id}</code>\n"
                f"💰 <b>Tutar:</b> {withdrawal_data['amount']:.2f}₺\n"
                f"📋 <b>Yöntem:</b> {withdrawal_data['method']}\n"
                f"👤 <b>Adınız:</b> {user.get('name', 'Kullanıcı')}\n"
                f"📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"⏳ <b>DURUM:</b> Admin onayı bekleniyor...\n"
                f"🕐 <b>Süre:</b> 24-48 saat\n\n"
                f"⚠️ <i>Lütfen bildirimleri açık tutun!</i>"
            )
            
            # Admin'e bildir
            admin_msg = (
                f"🔔 <b>YENİ PARA ÇEKİM TALEBİ</b>\n\n"
                f"👤 <b>Kullanıcı:</b> {user.get('name', 'Kullanıcı')}\n"
                f"🆔 <b>ID:</b> {user_id}\n"
                f"💰 <b>Tutar:</b> {withdrawal_data['amount']:.2f}₺\n"
                f"📋 <b>Yöntem:</b> {withdrawal_data['method']}\n"
                f"🔢 <b>Hesap:</b> {withdrawal_data['account_info']}\n"
                f"📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🔢 <b>Talep No:</b> <code>{withdrawal_id}</code>"
            )
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "✅ Ödemeyi Yap", 'callback_data': f'admin_complete_withdraw_{withdrawal_id}'},
                        {'text': "❌ Reddet", 'callback_data': f'admin_reject_withdraw_{withdrawal_id}'}
                    ]
                ]
            }
            
            send_telegram_message(user_id, message)
            send_telegram_message(ADMIN_ID, admin_msg, markup)
            
            self.clear_user_state(user_id)
        else:
            send_telegram_message(user_id, "❌ Para çekim talebi oluşturulurken bir hata oluştu!")
    
    def check_bot_admin_status(self, user_id, message=None):
        """Botun admin durumunu kontrol et"""
        if not message or 'chat' not in message:
            send_telegram_message(
                user_id,
                "❌ Bu komutu bir grup veya kanalda kullanmalısınız!"
            )
            return
        
        chat_id = str(message['chat']['id'])
        chat_title = message['chat'].get('title', 'Bilinmeyen')
        
        # Adminleri kontrol et
        admins = get_chat_administrators(chat_id)
        bot_id = get_bot_id()
        
        is_admin = False
        for admin in admins:
            if str(admin['user']['id']) == bot_id:
                is_admin = admin['status'] == 'administrator'
                break
        
        # Veritabanını güncelle
        self.db.set_bot_admin(chat_id, chat_title, user_id, is_admin)
        
        if is_admin:
            status_msg = "✅ <b>Bot bu grupta admin!</b>"
        else:
            status_msg = "❌ <b>Bot bu grupta admin değil!</b>"
        
        message_text = (
            f"🤖 <b>BOT ADMIN DURUMU</b>\n"
            f"══════════════════════════════\n\n"
            f"📢 <b>Grup/Kanal:</b> {chat_title}\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"🔍 <b>Durum:</b> {status_msg}\n\n"
            f"💡 <i>Kampanya oluşturmak için botu admin yapın.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🔄 Tekrar Kontrol Et", 'callback_data': 'check_admin_status'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        } if is_admin else {
            'inline_keyboard': [
                [
                    {'text': "🔄 Tekrar Kontrol Et", 'callback_data': 'check_admin_status'},
                    {'text': "❓ Nasıl Admin Yapılır?", 'callback_data': 'how_to_admin'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message_text, markup)
    
    def set_forward_requirement(self, user_id, require_forward):
        """Forward gereksinimini ayarla"""
        user_state = self.get_user_state(user_id)
        
        if 'campaign_data' in user_state['data']:
            user_state['data']['campaign_data']['requires_forward'] = 1 if require_forward else 0
            self.set_user_state(user_id, user_state['state'], user_state['data'])
            
            status = "AKTİF" if require_forward else "PASİF"
            send_telegram_message(
                user_id,
                f"✅ <b>Forward gereksinimi {status} yapıldı!</b>\n\n"
                f"Kampanya oluşturmaya devam edebilirsiniz."
            )
        else:
            send_telegram_message(user_id, "❌ Kampanya bulunamadı!")
    
    def handle_start(self, user_id, text):
        """START KOMUTU"""
        # Kanal kontrolü
        in_channel = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        
        user = self.db.get_user(user_id)
        
        # HOŞGELDİN BONUSU (2₺)
        if not user.get('welcome_bonus'):
            self.db.add_balance(user_id, 2.0)
            self.db.update_user(user_id, {
                'welcome_bonus': 1,
                'in_channel': 1 if in_channel else 0
            })
            
            send_telegram_message(
                user_id,
                f"🎉 <b>Hoşgeldin {user.get('name', 'Kullanıcı')}!</b>\n\n"
                f"✅ <b>2₺ hoşgeldin bonusu</b> yüklendi!\n"
                f"💰 <b>Yeni bakiyen:</b> {user.get('balance', 0) + 2.0:.2f}₺\n\n"
                f"⚡ <i>Hemen görev yapmaya başlayabilirsin!</i>"
            )
        
        # REFERANS KONTROLÜ
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1 and parts[1].startswith('ref_'):
                referrer_id = parts[1].replace('ref_', '')
                if referrer_id != user_id:
                    referrer = self.db.get_user(referrer_id)
                    if referrer:
                        # Referans bonusu (1₺)
                        self.db.add_balance(referrer_id, 1.0)
                        self.db.update_user(referrer_id, {
                            'referrals': referrer.get('referrals', 0) + 1,
                            'ref_earned': referrer.get('ref_earned', 0) + 1.0
                        })
                        
                        send_telegram_message(
                            user_id,
                            "🎉 <b>Referans başarılı!</b>\n\n"
                            "💰 <b>1₺ referans bonusu</b> arkadaşına yüklendi!\n\n"
                            "👥 Artık sen de arkadaşlarını davet ederek para kazanabilirsin!"
                        )
        
        # KANAL KONTROLÜ
        if not in_channel:
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '📢 KANALA KATIL', 'url': f'https://t.me/{MANDATORY_CHANNEL}'}
                    ],
                    [
                        {'text': '✅ KATILDIM', 'callback_data': 'joined'}
                    ]
                ]
            }
            
            send_telegram_message(
                user_id,
                f"👋 <b>Merhaba {user.get('name', 'Kullanıcı')}!</b>\n\n"
                f"Botu kullanabilmek için kanala katılmalısın:\n\n"
                f"👉 @{MANDATORY_CHANNEL}\n\n"
                f"<b>Katıldıktan sonra '✅ KATILDIM' butonuna bas.</b>",
                markup
            )
            return
        
        # Ana menü göster
        self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        """ANA MENÜ"""
        user = self.db.get_user(user_id)
        
        message = (
            f"🚀 <b>GÖREV YAPSAM BOT v7.0</b>\n"
            f"══════════════════════════════\n\n"
            f"👋 <b>Merhaba {user.get('name', 'Kullanıcı')}!</b>\n\n"
            f"💰 <b>Bakiyen:</b> {user.get('balance', 0):.2f}₺\n"
            f"📊 <b>Görevler:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n\n"
            f"🎯 <b>YENİ ÖZELLİKLER:</b>\n"
            f"• 💸 Para Çekim Sistemi\n"
            f"• 🎯 Kampanya Oluşturma\n"
            f"• 🤖 Admin Kontrolü\n\n"
            f"📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🤖 GÖREV YAP", 'callback_data': 'tasks'},
                    {'text': "🎯 KAMPANYA OLUŞTUR", 'callback_data': 'create_campaign'}
                ],
                [
                    {'text': "💰 BAKİYEM", 'callback_data': 'balance'},
                    {'text': "💸 PARA ÇEK", 'callback_data': 'withdraw'}
                ],
                [
                    {'text': "👤 PROFİL", 'callback_data': 'profile'},
                    {'text': "🎁 GÜNLÜK BONUS", 'callback_data': 'daily_bonus'}
                ],
                [
                    {'text': "👥 REFERANS", 'callback_data': 'referral'},
                    {'text': "❓ YARDIM", 'callback_data': 'help'}
                ]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([
                {'text': "👑 ADMIN PANEL", 'callback_data': 'admin'}
            ])
        
        send_telegram_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        """ADMIN PANELİ"""
        if user_id != ADMIN_ID:
            send_telegram_message(user_id, "❌ Bu işlem için yetkiniz yok!")
            return
        
        # İstatistikler
        self.db.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'pending'")
        pending_campaigns = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'")
        pending_withdrawals = self.db.cursor.fetchone()[0]
        
        self.db.cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = self.db.cursor.fetchone()[0] or 0.0
        
        message = (
            f"👑 <b>ADMIN PANELİ v7.0</b>\n"
            f"══════════════════════════════\n\n"
            f"📊 <b>İSTATİSTİKLER</b>\n"
            f"• Toplam Kullanıcı: {total_users}\n"
            f"• Toplam Kampanya: {total_campaigns}\n"
            f"• Bekleyen Kampanya: {pending_campaigns}\n"
            f"• Bekleyen Para Çekim: {pending_withdrawals}\n"
            f"• Toplam Bakiye: {total_balance:.2f}₺\n\n"
            f"🛠️ <b>ADMIN ARAÇLARI</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📊 İstatistikler", 'callback_data': 'admin_stats'},
                    {'text': "👥 Kullanıcılar", 'callback_data': 'admin_users'}
                ],
                [
                    {'text': "🎯 Kampanyalar", 'callback_data': 'admin_campaigns'},
                    {'text': "💸 Para Çekimler", 'callback_data': 'admin_withdrawals'}
                ],
                [
                    {'text': "📢 Bildirim Gönder", 'callback_data': 'admin_broadcast'},
                    {'text': "⚙️ Ayarlar", 'callback_data': 'admin_settings'}
                ],
                [
                    {'text': "🔙 Ana Menü", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def process_legacy_callback(self, user_id, data):
        """Eski callback'leri işle (geriye uyumluluk için)"""
        # Kanal kontrolü
        need_channel = ['tasks', 'create_task', 'daily_bonus', 'withdraw', 'request_withdraw']
        
        if data in need_channel:
            if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
                send_telegram_message(
                    user_id,
                    f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}"
                )
                return
        
        if data == 'profile':
            self.show_profile(user_id)
        elif data.startswith('task_'):
            self.show_task_info(user_id, data.replace('task_', ''))
        elif data == 'create_task':
            self.start_task_creation(user_id)
        elif data == 'daily_bonus':
            self.handle_daily_bonus(user_id)
        elif data == 'referral':
            self.show_referral(user_id)
        elif data == 'balance':
            self.show_balance(user_id)
        elif data == 'admin':
            self.show_admin_panel(user_id)
        elif data == 'help':
            self.show_help(user_id)
        else:
            self.show_main_menu(user_id)
    
    def show_profile(self, user_id):
        """PROFİL (eski sistem)"""
        user = self.db.get_user(user_id)
        
        message = (
            f"👤 <b>PROFİL BİLGİLERİ</b>\n"
            f"══════════════════════════════\n\n"
            f"🆔 <b>ID:</b> {user_id}\n"
            f"👤 <b>İsim:</b> {user.get('name', 'Kullanıcı')}\n"
            f"💰 <b>Bakiye:</b> {user.get('balance', 0):.2f}₺\n"
            f"📊 <b>Tamamlanan Görev:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n"
            f"🎯 <b>Toplam Kazanç:</b> {user.get('total_earned', 0):.2f}₺\n\n"
            f"💸 <b>Para Çekim:</b>\n"
            f"• Toplam: {user.get('withdrawal_total', 0):.2f}₺\n"
            f"• Sayı: {user.get('withdrawal_count', 0)}\n"
            f"══════════════════════════════"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye", 'callback_data': 'balance'},
                    {'text': "💸 Para Çek", 'callback_data': 'withdraw'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_balance(self, user_id):
        """BAKİYE (eski sistem)"""
        user = self.db.get_user(user_id)
        
        message = (
            f"💰 <b>BAKİYE DETAYLARI</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 {user.get('name', 'Kullanıcı')}\n"
            f"🆔 {user_id}\n\n"
            f"💵 <b>Mevcut Bakiye:</b> {user.get('balance', 0):.2f}₺\n"
            f"🏆 <b>Toplam Kazanç:</b> {user.get('total_earned', 0):.2f}₺\n"
            f"📊 <b>Minimum Çekim:</b> 20₺\n\n"
            f"💡 <i>Para çekmek için en az 20₺ bakiyen olmalı.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💸 Para Çek", 'callback_data': 'withdraw'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def handle_joined(self, user_id):
        """KATILIM KONTROLÜ"""
        if get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            self.db.update_user(user_id, {'in_channel': 1})
            self.show_main_menu(user_id)
        else:
            send_telegram_message(
                user_id,
                f"❌ Hala kanala katılmadın!\n\n"
                f"👉 @{MANDATORY_CHANNEL}"
            )
    
    def start_task_creation(self, user_id):
        """GÖREV OLUŞTURMA (eski sistem)"""
        message = (
            "📢 <b>GÖREV OLUŞTURMA</b>\n"
            "══════════════════════════════\n\n"
            "1️⃣ <b>Adım:</b> Botu kanalına/grubuna ekle\n"
            "2️⃣ <b>Adım:</b> Admin yetkileri ver\n"
            "3️⃣ <b>Adım:</b 'Görev Yap' butonuna bas\n\n"
            "👇 <b>Görev tipini seç:</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🤖 Bot Görevi", 'callback_data': 'create_bot'},
                    {'text': "📢 Kanal Görevi", 'callback_data': 'create_channel'}
                ],
                [
                    {'text': "👥 Grup Görevi", 'callback_data': 'create_group'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_task_info(self, user_id, task_type):
        """GÖREV BİLGİSİ (eski sistem)"""
        prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
        price = prices.get(task_type, 1.0)
        
        task_names = {
            'bot': '🤖 BOT GÖREVİ',
            'channel': '📢 KANAL GÖREVİ',
            'group': '👥 GRUP GÖREVİ'
        }
        
        message = (
            f"🎯 <b>{task_names.get(task_type)}</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Ödül:</b> {price}₺\n\n"
            f"📊 <b>Kota Hesaplama:</b>\n"
            f"• 10₺ = {int(10/price)} görev\n"
            f"• 50₺ = {int(50/price)} görev\n"
            f"• 100₺ = {int(100/price)} görev\n\n"
            f"⚠️ <i>Görev oluşturmak için 'GÖREV OLUŞTUR' butonuna bas.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📝 Görev Oluştur", 'callback_data': 'create_task'},
                    {'text': "🔙 Geri", 'callback_data': 'tasks'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def handle_daily_bonus(self, user_id):
        """GÜNLÜK BONUS (eski sistem)"""
        user = self.db.get_user(user_id)
        now = datetime.now()
        
        # Bugün bonus alınmış mı?
        last_daily = user.get('last_daily')
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            if last_date == now.date():
                # Bugün zaten alınmış
                next_time = (now + timedelta(days=1)).strftime('%d.%m.%Y %H:%M')
                
                message = (
                    f"🎁 <b>GÜNLÜK BONUS</b>\n"
                    f"══════════════════════════════\n\n"
                    f"❌ <b>Bugünkü bonusu zaten aldın!</b>\n\n"
                    f"⏳ <b>Bir sonraki bonus:</b> {next_time}\n"
                    f"🔥 <b>Üst üste gün:</b> {user.get('daily_streak', 0)}\n\n"
                    f"💡 <i>Yarın tekrar gel!</i>"
                )
                
                markup = {
                    'inline_keyboard': [
                        [{'text': "🔙 Geri", 'callback_data': 'menu'}]
                    ]
                }
                
                send_telegram_message(user_id, message, markup)
                return
        
        # Bonus ver (1-5₺ arası)
        import random
        bonus = round(random.uniform(1.0, 5.0), 2)
        
        # Streak hesapla
        streak = user.get('daily_streak', 0)
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            yesterday = (now - timedelta(days=1)).date()
            
            if last_date == yesterday:
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        
        # Bonusu ekle
        self.db.add_balance(user_id, bonus)
        
        # Kullanıcıyı güncelle
        self.db.update_user(user_id, {
            'last_daily': now.isoformat(),
            'daily_streak': streak
        })
        
        message = (
            f"🎁 <b>GÜNLÜK BONUS</b>\n"
            f"══════════════════════════════\n\n"
            f"🎉 <b>TEBRİKLER! Günlük bonusun yüklendi!</b>\n\n"
            f"💰 <b>Bonus:</b> {bonus:.2f}₺\n"
            f"🔥 <b>Üst üste gün:</b> {streak}\n"
            f"💸 <b>Yeni Bakiye:</b> {user.get('balance', 0) + bonus:.2f}₺\n\n"
            f"💡 <i>Yarın daha fazla kazanmak için tekrar gel!</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye", 'callback_data': 'balance'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_referral(self, user_id):
        """REFERANS (eski sistem)"""
        user = self.db.get_user(user_id)
        ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = (
            f"👥 <b>REFERANS SİSTEMİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Her referans:</b> 1₺\n"
            f"👤 <b>Toplam referans:</b> {user.get('referrals', 0)}\n"
            f"📈 <b>Referans kazancı:</b> {user.get('ref_earned', 0):.2f}₺\n\n"
            f"🔗 <b>Referans Linkin:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            f"🏆 <b>Bonus Seviyeleri:</b>\n"
            f"• 5 referans: +2₺\n"
            f"• 10 referans: +5₺\n"
            f"• 25 referans: +15₺\n"
            f"• 50 referans: +35₺\n\n"
            f"⚠️ <b>Arkadaşların kanala katılmazsa bonus alamazsın!</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📤 PAYLAŞ", 
                     'url': f'https://t.me/share/url?url={ref_link}&text=Görev Yap Para Kazan!'},
                    {'text': "📋 KOPYALA", 'callback_data': f'copy_{ref_link}'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_help(self, user_id):
        """YARDIM (eski sistem)"""
        message = (
            f"❓ <b>YARDIM</b>\n"
            f"══════════════════════════════\n\n"
            f"📋 <b>TEMEL KOMUTLAR</b>\n"
            f"• /start - Botu başlat\n"
            f"• /menu - Ana menü\n"
            f"• /profile - Profilim\n"
            f"• /balance - Bakiyem\n"
            f"• /tasks - Görev yap\n"
            f"• /bonus - Günlük bonus\n"
            f"• /referral - Referans sistemi\n"
            f"• /withdraw - Para çekme\n"
            f"• /createcampaign - Kampanya oluştur\n"
            f"• /checkadmin - Admin kontrolü\n"
            f"• /help - Yardım\n\n"
            f"🎯 <b>YENİ ÖZELLİKLER</b>\n"
            f"• Kampanya Oluşturma\n"
            f"• Para Çekim Sistemi\n"
            f"• Bot Admin Kontrolü\n\n"
            f"⚠️ <b>ÖNEMLİ KURALLAR</b>\n"
            f"• Sahte görev yasak\n"
            f"• Çoklu hesap yasak\n"
            f"• Spam yasak\n"
            f"• Kurallara uymayanlar banlanır"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📞 Destek", 'callback_data': 'support'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)

# ================= 7. ANA PROGRAM =================
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v7.0                       ║
    ║            PARA ÇEKİM + KAMPANYA SİSTEMİ + ADMIN YETKİ         ║
    ╚════════════════════════════════════════════════════════════════╝
    
    ✅ /start ÇALIŞIYOR
    ✅ Para Çekim Sistemi
    ✅ Kampanya Oluşturma
    ✅ Bot Admin Kontrolü
    ✅ SQLite Veritabanı
    ✅ Render Uyumlu
    """)
    
    # Botu başlat
    bot = BotSystem()
    
    # Telegram polling'i thread'de başlat
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print("🔗 Telegram'da /start yazarak test edin")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    
    return app

# ================= 8. UYGULAMA BAŞLATMA =================
if __name__ == "__main__":
    if not TOKEN:
        print("""
        ⚠️ ⚠️ ⚠️ HATA! ⚠️ ⚠️ ⚠️
        
        TELEGRAM_BOT_TOKEN environment variable bulunamadı!
        
        Render'da Environment Variables ayarlayın:
        1. TELEGRAM_BOT_TOKEN = bot_token_gelecek
        2. ADMIN_ID = 7904032877
        3. MANDATORY_CHANNEL = GY_Refim
        """)
    else:
        # Flask web server'ı başlat
        app_instance = main()
        port = int(os.environ.get('PORT', 8080))
        print(f"🌐 Web server başlatılıyor: http://0.0.0.0:{port}")
        app_instance.run(host='0.0.0.0', port=port, debug=False)

# WSGI için
def create_app():
    return main()
