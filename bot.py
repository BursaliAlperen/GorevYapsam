"""
╔════════════════════════════════════════════════════════════════╗
║                    GÖREV YAPSAM BOT v10.0                      ║
║        FORWARD SİSTEMİ + BOT ADMIN KONTROLÜ + 5 ADIMLI ONAY    ║
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
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "7904032877")
MANDATORY_CHANNEL = os.environ.get("MANDATORY_CHANNEL", "GY_Refim")

if not TOKEN:
    raise ValueError("⚠️ TELEGRAM_BOT_TOKEN environment variable bulunamadı!")

BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

print("=" * 60)
print("🤖 GÖREV YAPSAM BOT v10.0")
print("🔄 FORWARD SİSTEMİ + BOT ADMIN KONTROLÜ")
print("=" * 60)

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
                withdrawal_count INTEGER DEFAULT 0,
                referred_by TEXT DEFAULT NULL,
                last_active TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Kampanyalar tablosu - FORWARD MESAJ ID EKLENDİ
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
                task_type TEXT CHECK(task_type IN ('bot', 'group', 'channel')),
                price_per_task REAL,
                max_participants INTEGER,
                current_participants INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending', -- pending, active, completed, cancelled
                created_at TEXT,
                is_active INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                forward_message_id TEXT, -- Forward edilecek mesaj ID'si (sadece bot kampanyası için)
                target_chat_id TEXT, -- Kanal/Grup ID'si (kanal/grup kampanyası için)
                requires_admin_check INTEGER DEFAULT 0, -- Bot admin mi kontrolü
                admin_checked INTEGER DEFAULT 0 -- Admin kontrolü yapıldı mı?
            )
        ''')
        
        # Katılımlar tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS participations (
                participation_id TEXT PRIMARY KEY,
                user_id TEXT,
                campaign_id TEXT,
                status TEXT DEFAULT 'pending',
                proof_text TEXT,
                screenshot_id TEXT,
                created_at TEXT,
                verified_at TEXT,
                reward_paid INTEGER DEFAULT 0,
                reward_amount REAL DEFAULT 0.0,
                forward_message_id TEXT -- Kullanıcının forward ettiği mesaj ID
            )
        ''')
        
        # Bot admin durumu tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_admin_status (
                chat_id TEXT PRIMARY KEY,
                chat_title TEXT,
                is_admin INTEGER DEFAULT 0,
                added_by TEXT,
                added_at TEXT,
                last_checked TEXT
            )
        ''')
        
        # Forward mesajları tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS forward_messages (
                message_id TEXT PRIMARY KEY,
                from_user_id TEXT,
                from_chat_id TEXT,
                message_text TEXT,
                created_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        self.conn.commit()
        print("✅ Veritabanı tabloları oluşturuldu")
    
    def get_user(self, user_id):
        """Kullanıcıyı getir veya oluştur"""
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = self.cursor.fetchone()
        
        if not user:
            now = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO users 
                (user_id, name, username, balance, created_at, welcome_bonus, last_active, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, '', '', 0.0, now, 0, now, 1))
            self.conn.commit()
            
            self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = self.cursor.fetchone()
        else:
            self.cursor.execute('''
                UPDATE users SET last_active = ? WHERE user_id = ?
            ''', (datetime.now().isoformat(), user_id))
            self.conn.commit()
        
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
            # Fiyatları belirle
            price_map = {
                'bot': 2.5,
                'channel': 1.5,
                'group': 1.0
            }
            
            task_type = campaign_data['task_type']
            price_per_task = price_map.get(task_type, 1.0)
            budget = campaign_data['budget']
            max_participants = int(budget / price_per_task)
            
            self.cursor.execute('''
                INSERT INTO campaigns 
                (campaign_id, name, description, link, budget, remaining_budget,
                 creator_id, creator_name, task_type, price_per_task, max_participants,
                 status, created_at, is_active, forward_message_id, target_chat_id,
                 requires_admin_check, admin_checked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                campaign_data['campaign_id'],
                campaign_data['name'],
                campaign_data['description'],
                campaign_data['link'],
                budget,
                budget,
                campaign_data['creator_id'],
                campaign_data['creator_name'],
                task_type,
                price_per_task,
                max_participants,
                'pending',  # Admin onayı bekliyor
                datetime.now().isoformat(),
                0,  # Başlangıçta pasif
                campaign_data.get('forward_message_id', ''),
                campaign_data.get('target_chat_id', ''),
                campaign_data.get('requires_admin_check', 0),
                campaign_data.get('admin_checked', 0)
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Kampanya oluşturma hatası: {e}")
            return False
    
    def check_bot_admin_status(self, chat_id):
        """Bot'un chat'te admin olup olmadığını kontrol et"""
        self.cursor.execute(
            "SELECT is_admin, last_checked FROM bot_admin_status WHERE chat_id = ?",
            (chat_id,)
        )
        result = self.cursor.fetchone()
        
        if result:
            return result['is_admin'] == 1
        return False
    
    def update_bot_admin_status(self, chat_id, chat_title, is_admin, added_by=""):
        """Bot admin durumunu güncelle"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO bot_admin_status 
                (chat_id, chat_title, is_admin, added_by, added_at, last_checked)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                chat_id,
                chat_title,
                1 if is_admin else 0,
                added_by,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Bot admin durumu güncelleme hatası: {e}")
            return False
    
    def save_forward_message(self, message_data):
        """Forward mesajını kaydet"""
        try:
            self.cursor.execute('''
                INSERT INTO forward_messages 
                (message_id, from_user_id, from_chat_id, message_text, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                message_data['message_id'],
                message_data['from_user_id'],
                message_data['from_chat_id'],
                message_data.get('message_text', ''),
                datetime.now().isoformat(),
                1
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Forward mesajı kaydetme hatası: {e}")
            return False
    
    def get_latest_forward_messages(self, limit=5):
        """Son forward mesajlarını getir"""
        query = '''
            SELECT * FROM forward_messages 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT ?
        '''
        self.cursor.execute(query, (limit,))
        messages = self.cursor.fetchall()
        return [dict(msg) for msg in messages]
    
    def update_campaign_status(self, campaign_id, status, is_active=None):
        """Kampanya durumunu güncelle"""
        try:
            if is_active is not None:
                query = '''
                    UPDATE campaigns 
                    SET status = ?, is_active = ?
                    WHERE campaign_id = ?
                '''
                self.cursor.execute(query, (status, 1 if is_active else 0, campaign_id))
            else:
                query = '''
                    UPDATE campaigns 
                    SET status = ?
                    WHERE campaign_id = ?
                '''
                self.cursor.execute(query, (status, campaign_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Kampanya durumu güncelleme hatası: {e}")
            return False

# ================= 4. TELEGRAM FONKSİYONLARI =================
def send_telegram_message(chat_id, text, reply_markup=None, parse_mode='HTML', reply_to_message_id=None):
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
    
    if reply_to_message_id:
        data['reply_to_message_id'] = reply_to_message_id
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Mesaj gönderme hatası: {e}")
        return None

def forward_message(from_chat_id, to_chat_id, message_id):
    """Mesaj forward et"""
    url = BASE_URL + "forwardMessage"
    data = {
        'chat_id': to_chat_id,
        'from_chat_id': from_chat_id,
        'message_id': message_id
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Forward hatası: {e}")
        return None

def get_chat(chat_id):
    """Chat bilgilerini al"""
    url = BASE_URL + "getChat"
    data = {'chat_id': chat_id}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Chat bilgisi alma hatası: {e}")
        return None

def get_chat_administrators(chat_id):
    """Chat adminlerini getir"""
    url = BASE_URL + "getChatAdministrators"
    data = {'chat_id': chat_id}
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get('ok'):
            return result['result']
    except Exception as e:
        print(f"❌ Admin listesi alma hatası: {e}")
        pass
    return []

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
    except Exception as e:
        print(f"❌ Üyelik kontrol hatası: {e}")
        pass
    return False

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

# ================= 5. BOT SİSTEMİ =================
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.running = False
        self.user_states = {}
        print("🤖 Bot sistemi başlatıldı")
    
    def set_user_state(self, user_id, state, data=None):
        """Kullanıcı durumunu ayarla"""
        if data is None:
            data = {}
        self.user_states[user_id] = {'state': state, 'data': data, 'step': 1}
    
    def get_user_state(self, user_id):
        """Kullanıcı durumunu getir"""
        return self.user_states.get(user_id, {'state': None, 'data': {}, 'step': 1})
    
    def update_user_state_step(self, user_id, step):
        """Kullanıcı durum adımını güncelle"""
        if user_id in self.user_states:
            self.user_states[user_id]['step'] = step
    
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
                        
                        # FORWARD EDİLEN MESAJ
                        elif 'message' in update and 'forward_from' in update['message']:
                            threading.Thread(
                                target=self.process_forwarded_message,
                                args=(update['message'],),
                                daemon=True
                            ).start()
                        
                        # NORMAL MESAJ
                        elif 'message' in update:
                            threading.Thread(
                                target=self.process_message,
                                args=(update['message'],),
                                daemon=True
                            ).start()
                        
                        # CALLBACK
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
            
            chat_id = str(chat['id'])
            chat_title = chat.get('title', 'Bilinmeyen')
            
            is_admin = new_status == 'administrator'
            added_by = str(chat_member_update.get('from', {}).get('id', 'unknown'))
            
            # Bot admin durumunu güncelle
            self.db.update_bot_admin_status(chat_id, chat_title, is_admin, added_by)
            
            if is_admin:
                print(f"✅ Bot admin yapıldı: {chat_title} ({chat_id})")
                
                # Admin'e bildir
                admin_msg = (
                    f"✅ <b>BOT ADMIN YAPILDI!</b>\n\n"
                    f"📢 <b>Grup/Kanal:</b> {chat_title}\n"
                    f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
                    f"👤 <b>Ekleyen:</b> {chat_member_update.get('from', {}).get('first_name', 'Bilinmeyen')}\n"
                    f"⏰ <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                send_telegram_message(ADMIN_ID, admin_msg)
            
        except Exception as e:
            print(f"❌ Chat member update hatası: {e}")
    
    def process_forwarded_message(self, message):
        """Forward edilen mesajı işle (BOT KAMPANYASI İÇİN)"""
        try:
            if 'from' not in message:
                return
            
            user_id = str(message['from']['id'])
            user_state = self.get_user_state(user_id)
            
            # Eğer kullanıcı forward mesajı bekliyorsa (bot kampanyası oluşturuyorsa)
            if user_state['state'] == 'waiting_forward_message':
                # Forward mesajını kaydet
                forward_data = {
                    'message_id': str(message['message_id']),
                    'from_user_id': user_id,
                    'from_chat_id': str(message['chat']['id']),
                    'message_text': message.get('text', message.get('caption', ''))
                }
                
                self.db.save_forward_message(forward_data)
                
                # Kullanıcının durumunu güncelle
                user_state['data']['forward_message_id'] = str(message['message_id'])
                self.set_user_state(user_id, user_state['state'], user_state['data'])
                
                # Kullanıcıya teşekkür et
                send_telegram_message(
                    user_id,
                    "✅ <b>Forward mesajı alındı!</b>\n\n"
                    "Şimdi kampanya oluşturmaya devam edebilirsiniz.\n\n"
                    "👇 <b>Devam etmek için tıklayın:</b>",
                    {'inline_keyboard': [[
                        {'text': "➡️ Devam Et", 'callback_data': 'continue_campaign_creation'}
                    ]]}
                )
            
        except Exception as e:
            print(f"❌ Forward mesaj işleme hatası: {e}")
    
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
                elif text == '/createcampaign':
                    self.start_campaign_type_selection(user_id)
                elif text == '/forwardtest' and user_id == ADMIN_ID:
                    self.test_forward_message(user_id)
            
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def handle_user_state(self, user_id, message, user_state):
        """Kullanıcı durumuna göre mesajı işle"""
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # KAMPANYA OLUŞTURMA ADIMLARI
        if state == 'creating_campaign':
            task_type = data.get('task_type')
            
            # ADIM 1: Kampanya İsmi
            if step == 1:
                data['name'] = message['text']
                self.update_user_state_step(user_id, 2)
                
                # Admin'e bildir (1/5)
                self.send_admin_progress(user_id, task_type, 1, data['name'])
                
                send_telegram_message(
                    user_id,
                    f"✅ <b>1/5 - İsim Onaylandı:</b> {data['name']}\n\n"
                    f"📝 <b>2/5 - Kampanya Açıklaması</b>\n\n"
                    f"Lütfen kampanya açıklamasını girin:"
                )
            
            # ADIM 2: Açıklama
            elif step == 2:
                data['description'] = message['text']
                self.update_user_state_step(user_id, 3)
                
                # Admin'e bildir (2/5)
                self.send_admin_progress(user_id, task_type, 2, data['description'])
                
                send_telegram_message(
                    user_id,
                    f"✅ <b>2/5 - Açıklama Onaylandı</b>\n\n"
                    f"🔗 <b>3/5 - Kampanya Linki</b>\n\n"
                    f"Lütfen kampanya linkini girin:"
                )
            
            # ADIM 3: Link
            elif step == 3:
                data['link'] = message['text']
                self.update_user_state_step(user_id, 4)
                
                # Admin'e bildir (3/5)
                self.send_admin_progress(user_id, task_type, 3, data['link'])
                
                # KANAL/GRUP KAMPANYASI İSE TARGET CHAT ID İSTE
                if task_type in ['channel', 'group']:
                    send_telegram_message(
                        user_id,
                        f"✅ <b>3/5 - Link Onaylandı</b>\n\n"
                        f"🎯 <b>4/5 - Hedef Kanal/Grup</b>\n\n"
                        f"Lütfen katılım yapılacak kanalın veya grubun @kullanıcıadı veya ID'sini girin:\n\n"
                        f"💡 Örnekler:\n"
                        f"• @kanal_adi\n"
                        f"• -1001234567890 (kanal ID)\n"
                        f"• @grup_adi"
                    )
                else:
                    send_telegram_message(
                        user_id,
                        f"✅ <b>3/5 - Link Onaylandı</b>\n\n"
                        f"💰 <b>4/5 - Kampanya Bütçesi</b>\n\n"
                        f"Lütfen kampanya bütçesini girin (₺):"
                    )
            
            # ADIM 4: Target Chat ID (Kanal/Grup) veya Bütçe (Bot)
            elif step == 4:
                if task_type in ['channel', 'group']:
                    # Kanal/Grup ID'sini al
                    target_chat = message['text'].strip()
                    data['target_chat_id'] = target_chat
                    
                    # Bot'un admin olup olmadığını kontrol et
                    if not self.check_bot_admin_in_chat(target_chat):
                        send_telegram_message(
                            user_id,
                            f"❌ <b>BOT ADMIN DEĞİL!</b>\n\n"
                            f"Kanal/Grup: {target_chat}\n\n"
                            f"⚠️ <b>Önce bot'u bu kanala/gruba ekleyin ve ADMIN yapın!</b>\n\n"
                            f"💡 Nasıl yapılır:\n"
                            f"1. Bot'u kanala/gruba ekle\n"
                            f"2. Tüm yetkileri ver (Admin yap)\n"
                            f"3. Buraya tekrar kanal/grubun @adını yaz\n\n"
                            f"🔙 İptal etmek için: /menu"
                        )
                        return
                    
                    self.update_user_state_step(user_id, 5)
                    
                    # Admin'e bildir (4/5)
                    self.send_admin_progress(user_id, task_type, 4, f"Hedef: {target_chat}")
                    
                    send_telegram_message(
                        user_id,
                        f"✅ <b>4/5 - Hedef Onaylandı:</b> {target_chat}\n\n"
                        f"💰 <b>5/5 - Kampanya Bütçesi</b>\n\n"
                        f"Lütfen kampanya bütçesini girin (₺):"
                    )
                else:
                    # Bot kampanyası için direkt bütçe
                    try:
                        budget = float(message['text'])
                        data['budget'] = budget
                        self.update_user_state_step(user_id, 6)  # Bot için son adım
                        
                        # Admin'e bildir (4/5)
                        self.send_admin_progress(user_id, task_type, 4, f"Bütçe: {budget}₺")
                        
                        # Son özet ve onay
                        self.show_campaign_summary(user_id, data)
                        
                    except ValueError:
                        send_telegram_message(
                            user_id,
                            "❌ <b>Geçersiz bütçe!</b>\n"
                            "Lütfen geçerli bir sayı girin (örn: 100, 50.5)"
                        )
            
            # ADIM 5: Bütçe (Kanal/Grup)
            elif step == 5 and task_type in ['channel', 'group']:
                try:
                    budget = float(message['text'])
                    data['budget'] = budget
                    self.update_user_state_step(user_id, 6)  # Son adım
                    
                    # Admin'e bildir (5/5)
                    self.send_admin_progress(user_id, task_type, 5, f"Bütçe: {budget}₺")
                    
                    # Son özet ve onay
                    self.show_campaign_summary(user_id, data)
                    
                except ValueError:
                    send_telegram_message(
                        user_id,
                        "❌ <b>Geçersiz bütçe!</b>\n"
                        "Lütfen geçerli bir sayı girin (örn: 100, 50.5)"
                    )
    
    def send_admin_progress(self, user_id, task_type, step, content):
        """Admin'e ilerleme bildirimi gönder"""
        user = self.db.get_user(user_id)
        user_name = user.get('name', 'Kullanıcı')
        
        step_names = {
            1: "İsim",
            2: "Açıklama", 
            3: "Link",
            4: "Hedef" if task_type in ['channel', 'group'] else "Bütçe",
            5: "Bütçe"
        }
        
        task_names = {
            'bot': '🤖 Bot Kampanyası',
            'channel': '📢 Kanal Kampanyası',
            'group': '👥 Grup Kampanyası'
        }
        
        admin_msg = (
            f"📝 <b>KAMPANYA OLUŞTURMA İLERLEMESİ</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 <b>Kullanıcı:</b> {user_name}\n"
            f"🆔 <b>ID:</b> {user_id}\n"
            f"🎯 <b>Tip:</b> {task_names.get(task_type)}\n"
            f"📊 <b>Adım:</b> {step}/5 - {step_names.get(step)}\n\n"
            f"📋 <b>İçerik:</b>\n{content}\n\n"
            f"⏰ <b>Zaman:</b> {datetime.now().strftime('%H:%M:%S')}"
        )
        
        send_telegram_message(ADMIN_ID, admin_msg)
    
    def show_campaign_summary(self, user_id, data):
        """Kampanya özetini göster ve onay iste"""
        task_type = data.get('task_type', 'group')
        task_names = {
            'bot': '🤖 Bot Kampanyası',
            'channel': '📢 Kanal Kampanyası',
            'group': '👥 Grup Kampanyası'
        }
        
        prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
        price = prices.get(task_type, 1.0)
        budget = data.get('budget', 0)
        max_participants = int(budget / price)
        
        user = self.db.get_user(user_id)
        user_balance = user.get('balance', 0)
        
        summary = (
            f"🎯 <b>KAMPANYA ÖZETİ (5/5)</b>\n"
            f"══════════════════════════════\n\n"
            f"📛 <b>İsim:</b> {data.get('name', 'Belirtilmedi')}\n"
            f"📄 <b>Açıklama:</b> {data.get('description', 'Belirtilmedi')}\n"
            f"🔗 <b>Link:</b> {data.get('link', 'Belirtilmedi')}\n"
        )
        
        if task_type in ['channel', 'group']:
            summary += f"🎯 <b>Hedef:</b> {data.get('target_chat_id', 'Belirtilmedi')}\n"
        
        if task_type == 'bot':
            summary += f"🔄 <b>Görev:</b> Forward mesajı\n"
        
        summary += (
            f"🎯 <b>Tip:</b> {task_names.get(task_type)}\n"
            f"💰 <b>Bütçe:</b> {budget:.2f}₺\n"
            f"💵 <b>Görev Ücreti:</b> {price}₺\n"
            f"👥 <b>Maksimum Katılım:</b> {max_participants}\n"
            f"👤 <b>Oluşturan:</b> {user.get('name', 'Kullanıcı')}\n"
            f"💵 <b>Mevcut Bakiyen:</b> {user_balance:.2f}₺\n\n"
        )
        
        if user_balance < budget:
            summary += f"❌ <b>YETERSİZ BAKİYE!</b> {user_balance:.2f}₺ / {budget:.2f}₺\n"
        
        summary += "👇 <b>Yayınlamak için onay verin:</b>"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "✅ YAYINLA", 'callback_data': 'campaign_publish'},
                    {'text': "❌ İPTAL ET", 'callback_data': 'campaign_cancel'}
                ]
            ]
        }
        
        send_telegram_message(user_id, summary, markup)
    
    def check_bot_admin_in_chat(self, chat_id):
        """Bot'un bir chat'te admin olup olmadığını kontrol et"""
        try:
            # Önce veritabanından kontrol et
            if self.db.check_bot_admin_status(chat_id):
                return True
            
            # Telegram API'den kontrol et
            admins = get_chat_administrators(chat_id)
            if not admins:
                return False
            
            # Bot ID'sini al
            bot_info = requests.get(f"{BASE_URL}getMe", timeout=10).json()
            if not bot_info.get('ok'):
                return False
            
            bot_id = str(bot_info['result']['id'])
            
            # Admin listesinde bot var mı kontrol et
            for admin in admins:
                if str(admin['user']['id']) == bot_id:
                    is_admin = admin['status'] == 'administrator'
                    # Veritabanını güncelle
                    chat_info = get_chat(chat_id)
                    chat_title = chat_info.get('result', {}).get('title', 'Bilinmeyen') if chat_info.get('ok') else 'Bilinmeyen'
                    self.db.update_bot_admin_status(chat_id, chat_title, is_admin)
                    return is_admin
            
            return False
            
        except Exception as e:
            print(f"❌ Bot admin kontrol hatası: {e}")
            return False
    
    def process_callback(self, callback):
        """Callback işle"""
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # Cevap gönder
            answer_callback(callback_id)
            
            # Callback türlerine göre işle
            if data == 'menu':
                self.show_main_menu(user_id)
            
            elif data == 'create_campaign':
                self.start_campaign_type_selection(user_id)
            
            elif data.startswith('camp_type_'):
                task_type = data.replace('camp_type_', '')
                self.start_campaign_creation(user_id, task_type)
            
            elif data == 'continue_campaign_creation':
                self.continue_campaign_creation(user_id)
            
            elif data == 'campaign_publish':
                self.publish_campaign(user_id)
            
            elif data == 'campaign_cancel':
                self.clear_user_state(user_id)
                send_telegram_message(user_id, "❌ Kampanya oluşturma iptal edildi.")
            
            elif data.startswith('admin_approve_'):
                campaign_id = data.replace('admin_approve_', '')
                self.admin_approve_campaign(user_id, campaign_id)
            
            elif data.startswith('admin_reject_'):
                campaign_id = data.replace('admin_reject_', '')
                self.admin_reject_campaign(user_id, campaign_id)
            
            elif data == 'admin_check_bot':
                self.check_bot_admin_command(user_id, callback.get('message', {}))
            
            else:
                self.handle_general_callback(user_id, data)
                
        except Exception as e:
            print(f"❌ Callback işleme hatası: {e}")
    
    def start_campaign_type_selection(self, user_id):
        """Kampanya tipi seçimi"""
        if not get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
            send_telegram_message(
                user_id,
                f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}"
            )
            return
        
        message = (
            "🎯 <b>KAMPANYA TİPİ SEÇİN</b>\n"
            "══════════════════════════════\n\n"
            "🤖 <b>BOT KAMPANYASI</b>\n"
            "• Görev: Bot mesajını forward etme\n"
            "• Ödül: 2.5₺\n"
            "• Gereksinim: Forward mesajı\n\n"
            "📢 <b>KANAL KAMPANYASI</b>\n"
            "• Görev: Kanala katılma\n"
            "• Ödül: 1.5₺\n"
            "• Gereksinim: Bot kanalda admin olmalı\n\n"
            "👥 <b>GRUP KAMPANYASI</b>\n"
            "• Görev: Gruba katılma\n"
            "• Ödül: 1₺\n"
            "• Gereksinim: Bot grupta admin olmalı\n\n"
            "👇 <b>Hangi tür kampanya oluşturmak istiyorsunuz?</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🤖 Bot Kampanyası", 'callback_data': 'camp_type_bot'},
                    {'text': "📢 Kanal Kampanyası", 'callback_data': 'camp_type_channel'}
                ],
                [
                    {'text': "👥 Grup Kampanyası", 'callback_data': 'camp_type_group'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def start_campaign_creation(self, user_id, task_type):
        """Kampanya oluşturma sürecini başlat"""
        task_names = {
            'bot': '🤖 Bot Kampanyası',
            'channel': '📢 Kanal Kampanyası',
            'group': '👥 Grup Kampanyası'
        }
        
        if task_type == 'bot':
            # BOT KAMPANYASI: Önce forward mesajı iste
            self.set_user_state(user_id, 'waiting_forward_message', {
                'task_type': task_type
            })
            
            # Son forward mesajları göster
            latest_messages = self.db.get_latest_forward_messages(3)
            
            message = (
                f"🎯 <b>{task_names.get(task_type)} OLUŞTURMA</b>\n"
                f"══════════════════════════════\n\n"
                f"🔄 <b>ADIM 1/6 - Forward Mesajı</b>\n\n"
                f"Lütfen <b>bu bot'tan bir mesajı</b> bana forward edin:\n\n"
                f"💡 <b>Nasıl yapılır:</b>\n"
                f"1. Bu bot'tan bir mesaj bulun\n"
                f"2. Mesajı seçin\n"
                f"3. 'Forward' butonuna basın\n"
                f"4. Beni (@{requests.get(f'{BASE_URL}getMe').json()['result']['username']}) seçin\n\n"
            )
            
            if latest_messages:
                message += f"📋 <b>Son Kullanılan Mesajlar:</b>\n"
                for i, msg in enumerate(latest_messages, 1):
                    preview = msg['message_text'][:50] + "..." if len(msg['message_text']) > 50 else msg['message_text']
                    message += f"{i}. {preview}\n"
                message += "\n"
            
            message += "⏳ <b>Forward mesajınızı bekliyorum...</b>"
            
            send_telegram_message(user_id, message)
            
        else:
            # KANAL/GRUP KAMPANYASI: Direkt isimle başla
            self.set_user_state(user_id, 'creating_campaign', {
                'task_type': task_type
            })
            
            send_telegram_message(
                user_id,
                f"🎯 <b>{task_names.get(task_type)} OLUŞTURMA</b>\n"
                f"══════════════════════════════\n\n"
                f"📝 <b>1/5 - Kampanya İsmi</b>\n\n"
                f"Lütfen kampanya ismini girin:\n\n"
                f"💡 Örnek: 'Telegram Kanalına Katıl', 'Youtube Abone Ol'"
            )
    
    def continue_campaign_creation(self, user_id):
        """Forward mesajı alındıktan sonra kampanya oluşturmaya devam et"""
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        # Durumu güncelle
        self.set_user_state(user_id, 'creating_campaign', data)
        self.update_user_state_step(user_id, 1)  # İsim adımına geç
        
        send_telegram_message(
            user_id,
            f"✅ <b>Forward mesajı kaydedildi!</b>\n\n"
            f"📝 <b>1/5 - Kampanya İsmi</b>\n\n"
            f"Lütfen kampanya ismini girin:"
        )
    
    def publish_campaign(self, user_id):
        """Kampanyayı yayınla (admin onayına gönder)"""
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_telegram_message(user_id, "❌ Kampanya verisi bulunamadı!")
            return
        
        # Bakiye kontrolü
        user = self.db.get_user(user_id)
        user_balance = user.get('balance', 0)
        campaign_budget = data.get('budget', 0)
        
        if user_balance < campaign_budget:
            send_telegram_message(
                user_id,
                f"❌ <b>YETERSİZ BAKİYE!</b>\n\n"
                f"💰 <b>Kampanya bütçesi:</b> {campaign_budget:.2f}₺\n"
                f"💵 <b>Mevcut bakiyen:</b> {user_balance:.2f}₺\n\n"
                f"⚠️ <b>Lütfen bakiye doldur veya görev yap!</b>"
            )
            return
        
        # Kampanya ID oluştur
        campaign_id = hashlib.md5(
            f"{user_id}{time.time()}{data['name']}".encode()
        ).hexdigest()[:10].upper()
        
        # Kampanya verilerini hazırla
        full_data = {
            'campaign_id': campaign_id,
            'name': data.get('name', 'İsimsiz'),
            'description': data.get('description', 'Açıklama yok'),
            'link': data.get('link', ''),
            'budget': campaign_budget,
            'creator_id': user_id,
            'creator_name': user.get('name', 'Kullanıcı'),
            'task_type': data.get('task_type', 'group'),
            'forward_message_id': data.get('forward_message_id', ''),
            'target_chat_id': data.get('target_chat_id', ''),
            'requires_admin_check': 1 if data.get('task_type') in ['channel', 'group'] else 0,
            'admin_checked': 1 if data.get('task_type') in ['channel', 'group'] and data.get('target_chat_id') else 0
        }
        
        # Veritabanına kaydet
        if self.db.create_campaign(full_data):
            # Kullanıcıya bilgi ver
            task_names = {
                'bot': '🤖 Bot Kampanyası',
                'channel': '📢 Kanal Kampanyası',
                'group': '👥 Grup Kampanyası'
            }
            
            send_telegram_message(
                user_id,
                f"✅ <b>KAMPANYA OLUŞTURULDU!</b>\n\n"
                f"📛 <b>İsim:</b> {full_data['name']}\n"
                f"🎯 <b>Tip:</b> {task_names.get(full_data['task_type'])}\n"
                f"💰 <b>Bütçe:</b> {full_data['budget']:.2f}₺\n"
                f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
                f"⏳ <b>Durum:</b> Admin onayı bekleniyor...\n"
                f"✅ Onaylandıktan sonra kampanya aktif olacaktır."
            )
            
            # Admin'e onay isteği gönder
            self.send_admin_approval_request(campaign_id, full_data)
            
            self.clear_user_state(user_id)
        else:
            send_telegram_message(user_id, "❌ Kampanya oluşturulurken bir hata oluştu!")
    
    def send_admin_approval_request(self, campaign_id, campaign_data):
        """Admin'e onay isteği gönder"""
        task_names = {
            'bot': '🤖 Bot Kampanyası',
            'channel': '📢 Kanal Kampanyası', 
            'group': '👥 Grup Kampanyası'
        }
        
        prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
        price = prices.get(campaign_data['task_type'], 1.0)
        budget = campaign_data['budget']
        max_participants = int(budget / price)
        
        admin_msg = (
            f"🔔 <b>YENİ KAMPANYA ONAY BEKLİYOR</b>\n"
            f"══════════════════════════════\n\n"
            f"📛 <b>İsim:</b> {campaign_data['name']}\n"
            f"🎯 <b>Tip:</b> {task_names.get(campaign_data['task_type'])}\n"
            f"👤 <b>Oluşturan:</b> {campaign_data['creator_name']}\n"
            f"🆔 <b>Kullanıcı ID:</b> {campaign_data['creator_id']}\n"
            f"💰 <b>Bütçe:</b> {budget:.2f}₺\n"
            f"💵 <b>Görev Ücreti:</b> {price}₺\n"
            f"👥 <b>Maksimum Katılım:</b> {max_participants}\n"
            f"🔗 <b>Link:</b> {campaign_data['link']}\n"
        )
        
        if campaign_data['task_type'] in ['channel', 'group']:
            admin_msg += f"🎯 <b>Hedef:</b> {campaign_data['target_chat_id']}\n"
        
        if campaign_data['task_type'] == 'bot':
            admin_msg += f"🔄 <b>Forward Mesajı:</b> Evet\n"
        
        admin_msg += (
            f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
            f"📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"👇 <b>Onaylıyor musunuz?</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "✅ YAYINLA", 'callback_data': f'admin_approve_{campaign_id}'},
                    {'text': "❌ REDDET", 'callback_data': f'admin_reject_{campaign_id}'}
                ]
            ]
        }
        
        send_telegram_message(ADMIN_ID, admin_msg, markup)
    
    def admin_approve_campaign(self, user_id, campaign_id):
        """Admin kampanyayı onayla"""
        if user_id != ADMIN_ID:
            send_telegram_message(user_id, "❌ Bu işlem için yetkiniz yok!")
            return
        
        # Kampanya bilgilerini al
        self.db.cursor.execute(
            "SELECT * FROM campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        campaign = self.db.cursor.fetchone()
        
        if not campaign:
            send_telegram_message(user_id, "❌ Kampanya bulunamadı!")
            return
        
        campaign = dict(campaign)
        
        # Kampanyayı aktif yap
        self.db.update_campaign_status(campaign_id, 'active', True)
        
        # Kullanıcının bakiyesinden düş
        self.db.add_balance(campaign['creator_id'], -campaign['budget'])
        
        # Kullanıcıya bildir
        task_names = {
            'bot': '🤖 Bot Kampanyası',
            'channel': '📢 Kanal Kampanyası',
            'group': '👥 Grup Kampanyası'
        }
        
        user_msg = (
            f"✅ <b>KAMPANYANIZ ONAYLANDI!</b>\n\n"
            f"📛 <b>İsim:</b> {campaign['name']}\n"
            f"🎯 <b>Tip:</b> {task_names.get(campaign['task_type'])}\n"
            f"💰 <b>Bütçe:</b> {campaign['budget']:.2f}₺\n"
            f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
            f"🎉 <b>Kampanya aktif oldu!</b>\n"
            f"Kullanıcılar hemen katılmaya başlayabilir."
        )
        
        send_telegram_message(campaign['creator_id'], user_msg)
        
        # Admin'e bildir
        send_telegram_message(
            ADMIN_ID,
            f"✅ <b>Kampanya onaylandı:</b> {campaign['name']}\n"
            f"🔢 ID: <code>{campaign_id}</code>"
        )
    
    def admin_reject_campaign(self, user_id, campaign_id):
        """Admin kampanyayı reddet"""
        if user_id != ADMIN_ID:
            send_telegram_message(user_id, "❌ Bu işlem için yetkiniz yok!")
            return
        
        # Kampanya bilgilerini al
        self.db.cursor.execute(
            "SELECT * FROM campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        campaign = self.db.cursor.fetchone()
        
        if not campaign:
            send_telegram_message(user_id, "❌ Kampanya bulunamadı!")
            return
        
        campaign = dict(campaign)
        
        # Kampanyayı reddedildi olarak işaretle
        self.db.update_campaign_status(campaign_id, 'rejected', False)
        
        # Kullanıcıya bildir
        user_msg = (
            f"❌ <b>KAMPANYANIZ REDDEDİLDİ</b>\n\n"
            f"📛 <b>İsim:</b> {campaign['name']}\n"
            f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
            f"⚠️ <b>Sebep:</b> Admin tarafından reddedildi.\n\n"
            f"💡 Daha uygun bir kampanya ile tekrar deneyebilirsiniz."
        )
        
        send_telegram_message(campaign['creator_id'], user_msg)
        
        # Admin'e bildir
        send_telegram_message(
            ADMIN_ID,
            f"❌ <b>Kampanya reddedildi:</b> {campaign['name']}\n"
            f"🔢 ID: <code>{campaign_id}</code>"
        )
    
    def check_bot_admin_command(self, user_id, message):
        """Bot'un admin durumunu kontrol et"""
        if not message or 'chat' not in message:
            send_telegram_message(
                user_id,
                "❌ Bu komutu bir grup veya kanalda kullanmalısınız!"
            )
            return
        
        chat_id = str(message['chat']['id'])
        chat_title = message['chat'].get('title', 'Bilinmeyen')
        
        # Bot'un admin olup olmadığını kontrol et
        is_admin = self.check_bot_admin_in_chat(chat_id)
        
        if is_admin:
            status_msg = (
                f"✅ <b>BOT BU GRUPTA/KANALDA ADMIN!</b>\n\n"
                f"📢 <b>Grup/Kanal:</b> {chat_title}\n"
                f"🆔 <b>ID:</b> <code>{chat_id}</code>\n\n"
                f"🎯 Artık bu kanal/grup için kampanya oluşturabilirsiniz!"
            )
        else:
            status_msg = (
                f"❌ <b>BOT BU GRUPTA/KANALDA ADMIN DEĞİL!</b>\n\n"
                f"📢 <b>Grup/Kanal:</b> {chat_title}\n"
                f"🆔 <b>ID:</b> <code>{chat_id}</code>\n\n"
                f"💡 <b>Nasıl admin yapılır:</b>\n"
                f"1. Gruba/kanala botu ekleyin\n"
                f"2. Tüm yetkileri verin (Admin yapın)\n"
                f"3. Bu komutu tekrar gönderin\n\n"
                f"⚠️ Bot admin olmadan kampanya oluşturamazsınız!"
            )
        
        send_telegram_message(user_id, status_msg)
    
    def test_forward_message(self, user_id):
        """Admin için forward mesaj testi"""
        if user_id != ADMIN_ID:
            return
        
        # Test mesajı gönder
        test_msg = send_telegram_message(
            user_id,
            "📝 <b>TEST FORWARD MESAJI</b>\n\n"
            "Bu mesajı forward ederek bot kampanyası oluşturmayı test edebilirsiniz.\n\n"
            "1. Bu mesajı seçin\n"
            "2. Forward butonuna basın\n"
            "3. Bot'u seçin\n"
            "4. '/createcampaign' yazın\n"
            "5. Bot kampanyası seçin\n"
            "6. Bu mesajı forward edin"
        )
        
        if test_msg and 'result' in test_msg:
            message_id = str(test_msg['result']['message_id'])
            
            # Mesajı kaydet
            forward_data = {
                'message_id': message_id,
                'from_user_id': user_id,
                'from_chat_id': str(user_id),
                'message_text': 'TEST FORWARD MESAJI'
            }
            
            self.db.save_forward_message(forward_data)
            
            send_telegram_message(
                user_id,
                f"✅ <b>Test mesajı gönderildi ve kaydedildi!</b>\n\n"
                f"📋 Mesaj ID: <code>{message_id}</code>\n\n"
                f"Şimdi bu mesajı forward ederek bot kampanyası oluşturmayı test edebilirsiniz."
            )
    
    def handle_general_callback(self, user_id, data):
        """Genel callback'leri işle"""
        if data == 'joined':
            if get_chat_member(f"@{MANDATORY_CHANNEL}", user_id):
                self.db.update_user(user_id, {'in_channel': 1})
                self.show_main_menu(user_id)
            else:
                send_telegram_message(
                    user_id,
                    f"❌ Hala kanala katılmadın!\n\n"
                    f"👉 @{MANDATORY_CHANNEL}"
                )
        
        elif data == 'profile':
            self.show_profile(user_id)
        
        elif data == 'balance':
            self.show_balance(user_id)
        
        elif data == 'daily_bonus':
            self.handle_daily_bonus(user_id)
        
        elif data == 'referral':
            self.show_referral(user_id)
        
        elif data == 'help':
            self.show_help(user_id)
        
        elif data == 'withdraw':
            self.show_withdraw(user_id)
        
        else:
            self.show_main_menu(user_id)
    
    def handle_start(self, user_id, text):
        """START KOMUTU"""
        in_channel = get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        
        user = self.db.get_user(user_id)
        
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
                        
                        # Referans bildirimi
                        self.send_referral_notification(referrer_id, user_id, user.get('name', 'Yeni Kullanıcı'))
                        
                        send_telegram_message(
                            user_id,
                            "🎉 <b>Referans başarılı!</b>\n\n"
                            "💰 <b>1₺ referans bonusu</b> arkadaşına yüklendi!\n\n"
                            "👥 Artık sen de arkadaşlarını davet ederek para kazanabilirsin!"
                        )
        
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
        
        self.show_main_menu(user_id)
    
    def send_referral_notification(self, referrer_id, referred_id, referred_name):
        """Referans bildirimi gönder"""
        referrer = self.db.get_user(referrer_id)
        if not referrer:
            return
        
        referrals = referrer.get('referrals', 0)
        
        message = (
            f"🎉 <b>YENİ REFERANS!</b>\n\n"
            f"👤 <b>Arkadaşınız:</b> {referred_name}\n"
            f"🆔 <b>ID:</b> <code>{referred_id}</code>\n\n"
            f"💰 <b>1₺ referans bonusu</b> hesabınıza yüklendi!\n"
            f"📊 <b>Toplam referans:</b> {referrals}\n\n"
            f"🏆 <b>Bonus Seviyeleri:</b>\n"
            f"• 5 referans: +2₺\n"
            f"• 10 referans: +5₺\n"
            f"• 25 referans: +15₺\n"
            f"• 50 referans: +35₺\n\n"
            f"👥 Daha fazla arkadaşını davet et, daha çok kazan!"
        )
        
        send_telegram_message(referrer_id, message)
    
    def show_main_menu(self, user_id):
        """ANA MENÜ"""
        user = self.db.get_user(user_id)
        
        message = (
            f"🚀 <b>GÖREV YAPSAM BOT v10.0</b>\n"
            f"══════════════════════════════\n\n"
            f"👋 <b>Merhaba {user.get('name', 'Kullanıcı')}!</b>\n\n"
            f"💰 <b>Bakiyen:</b> {user.get('balance', 0):.2f}₺\n"
            f"📊 <b>Görevler:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n\n"
            f"🎯 <b>YENİ SİSTEM:</b>\n"
            f"• 🤖 Bot: Forward mesajı\n"
            f"• 📢 Kanal: Bot admin kontrolü\n"
            f"• 👥 Grup: Bot admin kontrolü\n"
            f"• 👑 5 adımlı onay sistemi\n\n"
            f"📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📢 KAMPANYA OLUŞTUR", 'callback_data': 'create_campaign'},
                    {'text': "🎯 GÖREV YAP", 'callback_data': 'active_campaigns'}
                ],
                [
                    {'text': "💰 BAKİYEM", 'callback_data': 'balance'},
                    {'text': "👤 PROFİL", 'callback_data': 'profile'}
                ],
                [
                    {'text': "🎁 GÜNLÜK BONUS", 'callback_data': 'daily_bonus'},
                    {'text': "👥 REFERANS", 'callback_data': 'referral'}
                ],
                [
                    {'text': "❓ YARDIM", 'callback_data': 'help'},
                    {'text': "💸 PARA ÇEK", 'callback_data': 'withdraw'}
                ]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([
                {'text': "👑 ADMIN", 'callback_data': 'admin'}
            ])
        
        send_telegram_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        """PROFİL"""
        user = self.db.get_user(user_id)
        
        message = (
            f"👤 <b>PROFİL BİLGİLERİ</b>\n"
            f"══════════════════════════════\n\n"
            f"🆔 <b>ID:</b> {user_id}\n"
            f"👤 <b>İsim:</b> {user.get('name', 'Kullanıcı')}\n"
            f"🔗 <b>Kullanıcı Adı:</b> @{user.get('username', 'yok')}\n"
            f"💰 <b>Bakiye:</b> {user.get('balance', 0):.2f}₺\n"
            f"📊 <b>Tamamlanan Görev:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n"
            f"🎯 <b>Toplam Kazanç:</b> {user.get('total_earned', 0):.2f}₺\n\n"
            f"📅 <b>Kayıt Tarihi:</b> {user.get('created_at', 'Bilinmiyor')[:10]}"
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
    
    def show_balance(self, user_id):
        """BAKİYE"""
        user = self.db.get_user(user_id)
        
        message = (
            f"💰 <b>BAKİYE DETAYLARI</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 {user.get('name', 'Kullanıcı')}\n"
            f"🆔 {user_id}\n\n"
            f"💵 <b>Mevcut Bakiye:</b> {user.get('balance', 0):.2f}₺\n"
            f"🏆 <b>Toplam Kazanç:</b> {user.get('total_earned', 0):.2f}₺\n"
            f"📊 <b>Minimum Çekim:</b> 20₺\n\n"
            f"💡 <b>Para kazanmak için:</b>\n"
            f"1. Görev yap\n"
            f"2. Kampanya oluştur\n"
            f"3. Referans davet et\n"
            f"4. Günlük bonus al"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📢 Kampanya Oluştur", 'callback_data': 'create_campaign'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_withdraw(self, user_id):
        """PARA ÇEKME - YAKINDA"""
        user = self.db.get_user(user_id)
        balance = user.get('balance', 0)
        
        message = (
            f"💸 <b>PARA ÇEKME SİSTEMİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Mevcut Bakiye:</b> {balance:.2f}₺\n"
            f"📊 <b>Minimum Çekim:</b> 20₺\n\n"
            f"🎯 <b>❗ YAKINDA AKTİF OLACAK ❗</b>\n\n"
            f"⏳ <b>Geliştirme Aşamasında...</b>\n\n"
            f"💡 <b>Şimdilik yapabilecekleriniz:</b>\n"
            f"1. Görev yaparak para biriktir\n"
            f"2. Referans sisteminden kazan\n"
            f"3. Kampanya oluştur\n\n"
            f"📢 <b>Sistem yakında aktif olacaktır!</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📢 Kampanya Oluştur", 'callback_data': 'create_campaign'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_referral(self, user_id):
        """REFERANS"""
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
    
    def handle_daily_bonus(self, user_id):
        """GÜNLÜK BONUS"""
        user = self.db.get_user(user_id)
        now = datetime.now()
        
        last_daily = user.get('last_daily')
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            if last_date == now.date():
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
        
        import random
        bonus = round(random.uniform(1.0, 5.0), 2)
        
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
        
        self.db.add_balance(user_id, bonus)
        
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
    
    def show_help(self, user_id):
        """YARDIM"""
        message = (
            f"❓ <b>YARDIM</b>\n"
            f"══════════════════════════════\n\n"
            f"📋 <b>TEMEL KOMUTLAR</b>\n"
            f"• /start - Botu başlat\n"
            f"• /menu - Ana menü\n"
            f"• /profile - Profilim\n"
            f"• /balance - Bakiyem\n"
            f"• /createcampaign - Kampanya oluştur\n"
            f"• /bonus - Günlük bonus\n"
            f"• /referral - Referans sistemi\n"
            f"• /withdraw - Para çekme (YAKINDA)\n"
            f"• /help - Yardım\n\n"
            f"🎯 <b>KAMPANYA TİPLERİ</b>\n"
            f"1. 🤖 <b>Bot Kampanyası</b>\n"
            f"   • Görev: Bot mesajını forward et\n"
            f"   • Ödül: 2.5₺\n"
            f"   • Gereksinim: Forward mesajı\n\n"
            f"2. 📢 <b>Kanal Kampanyası</b>\n"
            f"   • Görev: Kanala katıl\n"
            f"   • Ödül: 1.5₺\n"
            f"   • Gereksinim: Bot kanalda admin olmalı\n\n"
            f"3. 👥 <b>Grup Kampanyası</b>\n"
            f"   • Görev: Gruba katıl\n"
            f"   • Ödül: 1₺\n"
            f"   • Gereksinim: Bot grupta admin olmalı\n\n"
            f"⚠️ <b>ÖNEMLİ KURALLAR</b>\n"
            f"• Sahte görev yasak\n"
            f"• Çoklu hesap yasak\n"
            f"• Spam yasak\n"
            f"• Kurallara uymayanlar banlanır"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📢 Kampanya Oluştur", 'callback_data': 'create_campaign'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        """ADMIN PANELİ"""
        if user_id != ADMIN_ID:
            send_telegram_message(user_id, "❌ Bu işlem için yetkiniz yok!")
            return
        
        # İstatistikler
        self.db.cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = self.db.cursor.fetchone()['count']
        
        self.db.cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE status = 'pending'")
        pending_campaigns = self.db.cursor.fetchone()['count']
        
        self.db.cursor.execute("SELECT COUNT(*) as count FROM campaigns WHERE status = 'active'")
        active_campaigns = self.db.cursor.fetchone()['count']
        
        message = (
            f"👑 <b>ADMIN PANELİ v10.0</b>\n"
            f"══════════════════════════════\n\n"
            f"📊 <b>İSTATİSTİKLER</b>\n"
            f"• Toplam Kullanıcı: <b>{total_users}</b>\n"
            f"• Bekleyen Kampanya: {pending_campaigns}\n"
            f"• Aktif Kampanya: {active_campaigns}\n\n"
            f"🛠️ <b>ADMIN ARAÇLARI</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📋 Bekleyenler", 'callback_data': 'admin_pending'},
                    {'text': "📊 İstatistik", 'callback_data': 'admin_stats'}
                ],
                [
                    {'text': "👥 Kullanıcılar", 'callback_data': 'admin_users'},
                    {'text': "📢 Bildirim", 'callback_data': 'admin_broadcast'}
                ],
                [
                    {'text': "🔙 Ana Menü", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)

# ================= 6. ANA PROGRAM =================
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v10.0                      ║
    ║        FORWARD SİSTEMİ + BOT ADMIN KONTROLÜ + 5 ADIMLI ONAY    ║
    ╚════════════════════════════════════════════════════════════════╝
    
    ✅ /start ÇALIŞIYOR
    ✅ 🤖 Bot: Forward mesajı gereksinimi
    ✅ 📢 Kanal: Bot admin kontrolü
    ✅ 👥 Grup: Bot admin kontrolü
    ✅ 👑 5 adımlı onay sistemi
    ✅ Admin onayı ile yayınlama
    """)
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    print("🔗 Telegram'da /start yazarak test edin")
    print("🎯 Komutlar: /menu, /createcampaign")
    
    return app

# ================= 7. UYGULAMA BAŞLATMA =================
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
        app_instance = main()
        port = int(os.environ.get('PORT', 8080))
        print(f"🌐 Web server başlatılıyor: http://0.0.0.0:{port}")
        app_instance.run(host='0.0.0.0', port=port, debug=False)

def create_app():
    return main()
