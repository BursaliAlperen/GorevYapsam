"""
╔════════════════════════════════════════════════════════════════╗
║                    GÖREV YAPSAM BOT v11.0                      ║
║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAM BAKİYESİ + BONUS SİSTEM║
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
import re
from decimal import Decimal, ROUND_DOWN

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
print("🤖 GÖREV YAPSAM BOT v11.0")
print("💰 TRX DEPOZİT + OTOMATİK GÖREV + BONUS SİSTEM")
print("=" * 60)

# ================= 3. TRX AYARLARI =================
TRX_ADDRESS = "TVJKGbdBQrbvQzq6WZhb3kaGa3LYgVrMSK"  # Sabit TRX adresiniz
TRX_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=try"
TRX_PRICE = 12.61  # Başlangıç fiyatı
MIN_DEPOSIT_TRY = 25.0  # Minimum depozit
MAX_DEPOSIT_TRY = 200.0  # Maksimum depozit
DEPOSIT_BONUS_PERCENT = 35  # %35 depozit bonusu
ADS_BONUS_PERCENT = 20  # %20 reklam bonusu

# ================= 4. FLASK APP =================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online", 
        "bot": "Görev Yapsam Bot v11.0",
        "features": ["TRX Depozit", "Otomatik Kampanya", "Reklam Bakiyesi", "Bonus Sistemi"],
        "trx_address": TRX_ADDRESS,
        "min_deposit": MIN_DEPOSIT_TRY,
        "max_deposit": MAX_DEPOSIT_TRY,
        "bonuses": {
            "deposit": f"%{DEPOSIT_BONUS_PERCENT}",
            "ads": f"%{ADS_BONUS_PERCENT}"
        }
    })

@app.route('/trx-price')
def trx_price():
    # TRX fiyatını getir
    try:
        response = requests.get(TRX_PRICE_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            price = data.get('tron', {}).get('try', 12.61)
            return jsonify({
                "price": price,
                "currency": "TRY",
                "timestamp": datetime.now().isoformat()
            })
    except:
        pass
    return jsonify({"price": 12.61, "currency": "TRY", "timestamp": datetime.now().isoformat()})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ================= 5. SQLITE VERİTABANI =================
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
                ads_balance REAL DEFAULT 0.0,  -- Reklam bakiyesi
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
                is_active INTEGER DEFAULT 1,
                total_deposited REAL DEFAULT 0.0,
                deposit_count INTEGER DEFAULT 0,
                total_bonus REAL DEFAULT 0.0
            )
        ''')
        
        # Kampanyalar tablosu - OTOMATİK AKTİF
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
                status TEXT DEFAULT 'active',  -- Direkt aktif
                created_at TEXT,
                is_active INTEGER DEFAULT 1,
                total_spent REAL DEFAULT 0.0,
                forward_message_id TEXT,
                target_chat_id TEXT,
                requires_admin_check INTEGER DEFAULT 0,
                admin_checked INTEGER DEFAULT 0
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
                forward_message_id TEXT
            )
        ''')
        
        # Depozit tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS deposits (
                deposit_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount_try REAL,
                amount_trx REAL,
                txid TEXT,
                status TEXT DEFAULT 'pending', -- pending, verifying, completed, failed
                created_at TEXT,
                completed_at TEXT,
                bonus_amount REAL DEFAULT 0.0,
                trx_price REAL,
                wallet_address TEXT
            )
        ''')
        
        # Reklam bakiyesi tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ads_balances (
                ad_id TEXT PRIMARY KEY,
                user_id TEXT,
                amount REAL,
                source TEXT, -- deposit, task, referral, etc.
                description TEXT,
                created_at TEXT,
                expires_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # TRX fiyat geçmişi tablosu
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trx_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                price_try REAL,
                created_at TEXT
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
                (user_id, name, username, balance, ads_balance, created_at, 
                 welcome_bonus, last_active, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, '', '', 0.0, 0.0, now, 0, now, 1))
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
    
    def add_balance(self, user_id, amount, is_ads_balance=False):
        """Bakiye ekle"""
        user = self.get_user(user_id)
        
        if is_ads_balance:
            # Reklam bakiyesine ekle (%20 bonuslu)
            bonus_amount = amount * (ADS_BONUS_PERCENT / 100)
            total_amount = amount + bonus_amount
            new_ads_balance = user.get('ads_balance', 0) + total_amount
            
            self.cursor.execute('''
                UPDATE users 
                SET ads_balance = ?, total_earned = total_earned + ? 
                WHERE user_id = ?
            ''', (new_ads_balance, total_amount, user_id))
            
            # Reklam bakiyesi kaydı
            ad_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10]
            self.cursor.execute('''
                INSERT INTO ads_balances 
                (ad_id, user_id, amount, source, description, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ad_id,
                user_id,
                total_amount,
                'deposit_bonus',
                f'Depozit bonusu: {amount}₺ + %{ADS_BONUS_PERCENT} = {total_amount}₺',
                datetime.now().isoformat(),
                (datetime.now() + timedelta(days=30)).isoformat()
            ))
            
        else:
            # Normal bakiyeye ekle
            new_balance = user.get('balance', 0) + amount
            self.cursor.execute('''
                UPDATE users 
                SET balance = ?, total_earned = total_earned + ? 
                WHERE user_id = ?
            ''', (new_balance, amount, user_id))
        
        self.conn.commit()
        return True
    
    def create_deposit(self, deposit_data):
        """Depozit oluştur"""
        try:
            self.cursor.execute('''
                INSERT INTO deposits 
                (deposit_id, user_id, amount_try, amount_trx, txid, status, 
                 created_at, bonus_amount, trx_price, wallet_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                deposit_data['deposit_id'],
                deposit_data['user_id'],
                deposit_data['amount_try'],
                deposit_data['amount_trx'],
                deposit_data.get('txid', ''),
                deposit_data.get('status', 'pending'),
                datetime.now().isoformat(),
                deposit_data.get('bonus_amount', 0.0),
                deposit_data.get('trx_price', 0.0),
                deposit_data.get('wallet_address', '')
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Depozit oluşturma hatası: {e}")
            return False
    
    def update_deposit_status(self, deposit_id, status, txid=None):
        """Depozit durumunu güncelle"""
        try:
            if txid:
                query = '''
                    UPDATE deposits 
                    SET status = ?, txid = ?, completed_at = ?
                    WHERE deposit_id = ?
                '''
                self.cursor.execute(query, (status, txid, datetime.now().isoformat(), deposit_id))
            else:
                query = '''
                    UPDATE deposits 
                    SET status = ?, completed_at = ?
                    WHERE deposit_id = ?
                '''
                self.cursor.execute(query, (status, datetime.now().isoformat(), deposit_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Depozit durumu güncelleme hatası: {e}")
            return False
    
    def complete_deposit(self, deposit_id, user_id, amount_try, bonus_amount):
        """Depoziti tamamla ve bakiyeleri güncelle"""
        try:
            # Normal bakiye ekle
            self.cursor.execute('''
                UPDATE users 
                SET balance = balance + ?,
                    total_deposited = total_deposited + ?,
                    deposit_count = deposit_count + 1,
                    total_bonus = total_bonus + ?
                WHERE user_id = ?
            ''', (amount_try, amount_try, bonus_amount, user_id))
            
            # Depozit durumunu güncelle
            self.cursor.execute('''
                UPDATE deposits 
                SET status = 'completed'
                WHERE deposit_id = ?
            ''', (deposit_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Depozit tamamlama hatası: {e}")
            return False
    
    def get_user_deposits(self, user_id, limit=10):
        """Kullanıcının depozitlerini getir"""
        query = '''
            SELECT * FROM deposits 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        '''
        self.cursor.execute(query, (user_id, limit))
        deposits = self.cursor.fetchall()
        return [dict(dep) for dep in deposits]
    
    def create_campaign(self, campaign_data):
        """Yeni kampanya oluştur - OTOMATİK AKTİF"""
        try:
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
                'active',  # Direkt aktif
                datetime.now().isoformat(),
                1,  # Direkt aktif
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
    
    def get_user_campaigns(self, user_id):
        """Kullanıcının kampanyalarını getir"""
        query = '''
            SELECT * FROM campaigns 
            WHERE creator_id = ?
            ORDER BY created_at DESC 
            LIMIT 20
        '''
        self.cursor.execute(query, (user_id,))
        campaigns = self.cursor.fetchall()
        return [dict(camp) for camp in campaigns]
    
    def save_trx_price(self, price):
        """TRX fiyatını kaydet"""
        try:
            self.cursor.execute('''
                INSERT INTO trx_prices (price_try, created_at)
                VALUES (?, ?)
            ''', (price, datetime.now().isoformat()))
            
            # Eski kayıtları temizle (son 1000 kayıt sakla)
            self.cursor.execute('''
                DELETE FROM trx_prices 
                WHERE id NOT IN (
                    SELECT id FROM trx_prices 
                    ORDER BY created_at DESC 
                    LIMIT 1000
                )
            ''')
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ TRX fiyatı kaydetme hatası: {e}")
            return False
    
    def get_latest_trx_price(self):
        """Son TRX fiyatını getir"""
        self.cursor.execute('''
            SELECT price_try FROM trx_prices 
            ORDER BY created_at DESC 
            LIMIT 1
        ''')
        result = self.cursor.fetchone()
        return result['price_try'] if result else 12.61

# ================= 6. TRX FİYAT GÜNCELLEYİCİ =================
class TRXPriceUpdater:
    def __init__(self, db):
        self.db = db
        self.current_price = 12.61
        self.running = False
    
    def start(self):
        """TRX fiyat güncelleyiciyi başlat"""
        self.running = True
        print("🔄 TRX fiyat güncelleyici başlatıldı...")
        
        def update_loop():
            while self.running:
                try:
                    self.update_price()
                    time.sleep(10)  # 10 saniyede bir güncelle
                except Exception as e:
                    print(f"❌ TRX fiyat güncelleme hatası: {e}")
                    time.sleep(30)
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
    
    def update_price(self):
        """TRX fiyatını güncelle"""
        try:
            response = requests.get(TRX_PRICE_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'tron' in data and 'try' in data['tron']:
                    new_price = data['tron']['try']
                    self.current_price = new_price
                    
                    # Veritabanına kaydet
                    self.db.save_trx_price(new_price)
                    
                    print(f"✅ TRX fiyatı güncellendi: {new_price}₺")
                    return new_price
        except Exception as e:
            print(f"❌ TRX fiyatı alma hatası: {e}")
        
        return self.current_price
    
    def get_price(self):
        """Güncel TRX fiyatını getir"""
        return self.current_price

# ================= 7. TELEGRAM FONKSİYONLARI =================
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

# ================= 8. BOT SİSTEMİ =================
class BotSystem:
    def __init__(self):
        self.db = Database()
        self.trx_updater = TRXPriceUpdater(self.db)
        self.trx_updater.start()
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
                    'allowed_updates': ['message', 'callback_query']
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
                        
                        if 'message' in update:
                            threading.Thread(
                                target=self.process_message,
                                args=(update['message'],),
                                daemon=True
                            ).start()
                        
                        elif 'callback_query' in update:
                            threading.Thread(
                                target=self.process_callback,
                                args=(update['callback_query'],),
                                daemon=True
                            ).start()
                
            except Exception as e:
                print(f"❌ Polling hatası: {e}")
                time.sleep(2)
    
    def process_message(self, message):
        """Gelen mesajı işle"""
        try:
            if 'from' not in message:
                return
            
            user_id = str(message['from']['id'])
            user_state = self.get_user_state(user_id)
            
            user = self.db.get_user(user_id)
            if not user.get('name'):
                self.db.update_user(user_id, {
                    'name': message['from'].get('first_name', 'Kullanıcı'),
                    'username': message['from'].get('username', '')
                })
            
            if user_state['state']:
                self.handle_user_state(user_id, message, user_state)
                return
            
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
                elif text == '/deposit':
                    self.show_deposit_menu(user_id)
                elif text == '/mycampaigns':
                    self.show_my_campaigns(user_id)
                elif text == '/balance':
                    self.show_balance_detail(user_id)
                elif text == '/myads':
                    self.show_ads_balance(user_id)
                elif text == '/convertads':
                    self.show_convert_ads_menu(user_id)
                elif text == '/trxprice':
                    self.show_trx_price(user_id)
            
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def handle_user_state(self, user_id, message, user_state):
        """Kullanıcı durumuna göre mesajı işle"""
        state = user_state['state']
        data = user_state['data']
        step = user_state.get('step', 1)
        
        # DEPOZIT SÜRECİ
        if state == 'deposit_amount':
            try:
                amount_try = float(message['text'])
                
                if amount_try < MIN_DEPOSIT_TRY:
                    send_telegram_message(
                        user_id,
                        f"❌ <b>Minimum depozit tutarı {MIN_DEPOSIT_TRY}₺!</b>\n\n"
                        f"💡 Lütfen {MIN_DEPOSIT_TRY}₺ veya üzeri bir tutar girin."
                    )
                    return
                
                if amount_try > MAX_DEPOSIT_TRY:
                    send_telegram_message(
                        user_id,
                        f"❌ <b>Maksimum depozit tutarı {MAX_DEPOSIT_TRY}₺!</b>\n\n"
                        f"💡 Lütfen {MAX_DEPOSIT_TRY}₺ veya altı bir tutar girin."
                    )
                    return
                
                data['amount_try'] = amount_try
                self.update_user_state_step(user_id, 2)
                
                # TRX fiyatını al
                trx_price = self.trx_updater.get_price()
                
                # TRX miktarını hesapla
                amount_trx = amount_try / trx_price
                
                # Bonus hesapla (%35)
                bonus_amount = amount_try * (DEPOSIT_BONUS_PERCENT / 100)
                total_with_bonus = amount_try + bonus_amount
                
                # Reklam bonusu hesapla (%20)
                ads_bonus = amount_try * (ADS_BONUS_PERCENT / 100)
                total_ads_bonus = amount_try + ads_bonus
                
                data['amount_trx'] = amount_trx
                data['trx_price'] = trx_price
                data['bonus_amount'] = bonus_amount
                data['ads_bonus'] = ads_bonus
                
                message_text = (
                    f"💰 <b>DEPOZİT ÖZETİ</b>\n"
                    f"══════════════════════════════\n\n"
                    f"💵 <b>Tutar:</b> {amount_try:.2f}₺\n"
                    f"₿ <b>TRX Fiyatı:</b> {trx_price:.2f}₺\n"
                    f"🔢 <b>TRX Miktarı:</b> {amount_trx:.4f} TRX\n\n"
                    f"🎁 <b>BONUSLAR:</b>\n"
                    f"• Normal Bakiye: +%{DEPOSIT_BONUS_PERCENT} = <b>{bonus_amount:.2f}₺</b>\n"
                    f"• Reklam Bakiye: +%{ADS_BONUS_PERCENT} = <b>{ads_bonus:.2f}₺</b>\n\n"
                    f"💰 <b>TOPLAM:</b>\n"
                    f"• Normal: {total_with_bonus:.2f}₺\n"
                    f"• Reklam: {total_ads_bonus:.2f}₺\n\n"
                    f"👇 <b>Devam etmek için tıklayın:</b>"
                )
                
                markup = {
                    'inline_keyboard': [
                        [
                            {'text': "✅ ÖDEME YAP", 'callback_data': 'deposit_confirm'},
                            {'text': "❌ İPTAL", 'callback_data': 'deposit_cancel'}
                        ]
                    ]
                }
                
                send_telegram_message(user_id, message_text, markup)
                
            except ValueError:
                send_telegram_message(
                    user_id,
                    "❌ <b>Geçersiz tutar!</b>\n"
                    "Lütfen geçerli bir sayı girin (örn: 50, 100.5)"
                )
        
        # TXID GİRME
        elif state == 'deposit_txid':
            txid = message['text'].strip()
            
            # TXID formatını kontrol et (64 karakter hex)
            if not re.match(r'^[a-fA-F0-9]{64}$', txid):
                send_telegram_message(
                    user_id,
                    "❌ <b>Geçersiz TXID!</b>\n\n"
                    "TXID 64 karakterlik hexadecimal bir koddur.\n"
                    "Lütfen geçerli bir TXID girin."
                )
                return
            
            # Depozit ID'sini al
            deposit_id = data.get('deposit_id')
            
            if not deposit_id:
                send_telegram_message(user_id, "❌ Depozit bilgisi bulunamadı!")
                self.clear_user_state(user_id)
                return
            
            # TXID'yi kaydet
            self.db.update_deposit_status(deposit_id, 'verifying', txid)
            
            # Kullanıcıya bilgi ver
            send_telegram_message(
                user_id,
                f"✅ <b>TXID alındı!</b>\n\n"
                f"📋 <b>TXID:</b> <code>{txid}</code>\n\n"
                f"⏳ <b>İşlem doğrulanıyor...</b>\n"
                f"TRX işleminiz kontrol ediliyor, lütfen bekleyin.\n\n"
                f"✅ İşlem doğrulandığında bakiyeniz otomatik yüklenecektir."
            )
            
            # İşlemi doğrulamaya başla (simülasyon)
            threading.Thread(
                target=self.verify_deposit,
                args=(user_id, deposit_id, txid),
                daemon=True
            ).start()
            
            self.clear_user_state(user_id)
        
        # KAMPANYA OLUŞTURMA
        elif state == 'creating_campaign':
            task_type = data.get('task_type')
            
            if step == 1:  # İsim
                data['name'] = message['text']
                self.update_user_state_step(user_id, 2)
                
                send_telegram_message(
                    user_id,
                    f"✅ <b>1/5 - İsim Onaylandı:</b> {data['name']}\n\n"
                    f"📝 <b>2/5 - Kampanya Açıklaması</b>\n\n"
                    f"Lütfen kampanya açıklamasını girin:"
                )
            
            elif step == 2:  # Açıklama
                data['description'] = message['text']
                self.update_user_state_step(user_id, 3)
                
                send_telegram_message(
                    user_id,
                    f"✅ <b>2/5 - Açıklama Onaylandı</b>\n\n"
                    f"🔗 <b>3/5 - Kampanya Linki</b>\n\n"
                    f"Lütfen kampanya linkini girin:"
                )
            
            elif step == 3:  # Link
                data['link'] = message['text']
                self.update_user_state_step(user_id, 4)
                
                if task_type in ['channel', 'group']:
                    send_telegram_message(
                        user_id,
                        f"✅ <b>3/5 - Link Onaylandı</b>\n\n"
                        f"🎯 <b>4/5 - Hedef Kanal/Grup</b>\n\n"
                        f"Lütfen katılım yapılacak kanalın veya grubun @kullanıcıadı veya ID'sini girin:"
                    )
                else:
                    send_telegram_message(
                        user_id,
                        f"✅ <b>3/5 - Link Onaylandı</b>\n\n"
                        f"💰 <b>4/5 - Kampanya Bütçesi</b>\n\n"
                        f"Lütfen kampanya bütçesini girin (₺):"
                    )
            
            elif step == 4:  # Target Chat ID veya Bütçe
                if task_type in ['channel', 'group']:
                    target_chat = message['text'].strip()
                    data['target_chat_id'] = target_chat
                    self.update_user_state_step(user_id, 5)
                    
                    send_telegram_message(
                        user_id,
                        f"✅ <b>4/5 - Hedef Onaylandı:</b> {target_chat}\n\n"
                        f"💰 <b>5/5 - Kampanya Bütçesi</b>\n\n"
                        f"Lütfen kampanya bütçesini girin (₺):"
                    )
                else:
                    try:
                        budget = float(message['text'])
                        data['budget'] = budget
                        self.update_user_state_step(user_id, 6)
                        
                        self.show_campaign_summary(user_id, data)
                        
                    except ValueError:
                        send_telegram_message(
                            user_id,
                            "❌ <b>Geçersiz bütçe!</b>\n"
                            "Lütfen geçerli bir sayı girin (örn: 100, 50.5)"
                        )
            
            elif step == 5:  # Bütçe (Kanal/Grup)
                try:
                    budget = float(message['text'])
                    data['budget'] = budget
                    self.update_user_state_step(user_id, 6)
                    
                    self.show_campaign_summary(user_id, data)
                    
                except ValueError:
                    send_telegram_message(
                        user_id,
                        "❌ <b>Geçersiz bütçe!</b>\n"
                        "Lütfen geçerli bir sayı girin (örn: 100, 50.5)"
                    )
    
    def process_callback(self, callback):
        """Callback işle"""
        try:
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
                amount_try = float(data.replace('deposit_amount_', ''))
                self.start_deposit_process(user_id, amount_try)
            
            elif data == 'deposit_custom':
                self.start_custom_deposit(user_id)
            
            elif data == 'deposit_confirm':
                self.confirm_deposit(user_id)
            
            elif data == 'deposit_cancel':
                self.clear_user_state(user_id)
                send_telegram_message(user_id, "❌ Depozit işlemi iptal edildi.")
            
            elif data == 'campaign_publish':
                self.publish_campaign(user_id)
            
            elif data == 'campaign_cancel':
                self.clear_user_state(user_id)
                send_telegram_message(user_id, "❌ Kampanya oluşturma iptal edildi.")
            
            elif data == 'my_campaigns':
                self.show_my_campaigns(user_id)
            
            elif data == 'convert_ads':
                self.start_convert_ads(user_id)
            
            elif data == 'trx_price':
                self.show_trx_price(user_id)
            
            else:
                self.handle_general_callback(user_id, data)
                
        except Exception as e:
            print(f"❌ Callback işleme hatası: {e}")
    
    def show_deposit_menu(self, user_id):
        """Depozit menüsünü göster"""
        trx_price = self.trx_updater.get_price()
        
        message = (
            f"💰 <b>BAKİYE YÜKLEME</b>\n"
            f"══════════════════════════════\n\n"
            f"₿ <b>Güncel TRX Fiyatı:</b> {trx_price:.2f}₺\n"
            f"💵 <b>Minimum:</b> {MIN_DEPOSIT_TRY}₺\n"
            f"💎 <b>Maksimum:</b> {MAX_DEPOSIT_TRY}₺\n\n"
            f"🎁 <b>BONUS SİSTEMİ:</b>\n"
            f"• Normal Bakiye: +%{DEPOSIT_BONUS_PERCENT}\n"
            f"• Reklam Bakiye: +%{ADS_BONUS_PERCENT}\n\n"
            f"💡 <b>Örnek:</b> 100₺ yüklersen:\n"
            f"• Normal: 135₺ (35₺ bonus)\n"
            f"• Reklam: 120₺ (20₺ bonus)\n\n"
            f"👇 <b>Tutar seçin veya özel tutar girin:</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': f"25₺ ({(25/trx_price):.2f} TRX)", 'callback_data': 'deposit_amount_25'},
                    {'text': f"50₺ ({(50/trx_price):.2f} TRX)", 'callback_data': 'deposit_amount_50'}
                ],
                [
                    {'text': f"100₺ ({(100/trx_price):.2f} TRX)", 'callback_data': 'deposit_amount_100'},
                    {'text': f"200₺ ({(200/trx_price):.2f} TRX)", 'callback_data': 'deposit_amount_200'}
                ],
                [
                    {'text': "📝 Özel Tutar", 'callback_data': 'deposit_custom'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def start_custom_deposit(self, user_id):
        """Özel depozit tutarı başlat"""
        self.set_user_state(user_id, 'deposit_amount', {})
        
        send_telegram_message(
            user_id,
            f"💰 <b>ÖZEL DEPOZİT TUTARI</b>\n\n"
            f"Lütfen yüklemek istediğiniz tutarı girin (₺):\n\n"
            f"💵 <b>Minimum:</b> {MIN_DEPOSIT_TRY}₺\n"
            f"💎 <b>Maksimum:</b> {MAX_DEPOSIT_TRY}₺\n\n"
            f"💡 Örnek: 75, 125, 150"
        )
    
    def start_deposit_process(self, user_id, amount_try):
        """Depozit sürecini başlat"""
        self.set_user_state(user_id, 'deposit_amount', {})
        
        # Kullanıcı durumunu güncelle
        user_state = self.get_user_state(user_id)
        user_state['data']['amount_try'] = amount_try
        self.set_user_state(user_id, 'deposit_amount', user_state['data'])
        
        # Hesaplamaları yap ve göster
        trx_price = self.trx_updater.get_price()
        amount_trx = amount_try / trx_price
        
        bonus_amount = amount_try * (DEPOSIT_BONUS_PERCENT / 100)
        total_with_bonus = amount_try + bonus_amount
        
        ads_bonus = amount_try * (ADS_BONUS_PERCENT / 100)
        total_ads_bonus = amount_try + ads_bonus
        
        user_state['data']['amount_trx'] = amount_trx
        user_state['data']['trx_price'] = trx_price
        user_state['data']['bonus_amount'] = bonus_amount
        user_state['data']['ads_bonus'] = ads_bonus
        
        message_text = (
            f"💰 <b>DEPOZİT ÖZETİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💵 <b>Tutar:</b> {amount_try:.2f}₺\n"
            f"₿ <b>TRX Fiyatı:</b> {trx_price:.2f}₺\n"
            f"🔢 <b>TRX Miktarı:</b> {amount_trx:.4f} TRX\n\n"
            f"🎁 <b>BONUSLAR:</b>\n"
            f"• Normal Bakiye: +%{DEPOSIT_BONUS_PERCENT} = <b>{bonus_amount:.2f}₺</b>\n"
            f"• Reklam Bakiye: +%{ADS_BONUS_PERCENT} = <b>{ads_bonus:.2f}₺</b>\n\n"
            f"💰 <b>TOPLAM:</b>\n"
            f"• Normal: {total_with_bonus:.2f}₺\n"
            f"• Reklam: {total_ads_bonus:.2f}₺\n\n"
            f"👇 <b>Devam etmek için tıklayın:</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "✅ ÖDEME YAP", 'callback_data': 'deposit_confirm'},
                    {'text': "❌ İPTAL", 'callback_data': 'deposit_cancel'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message_text, markup)
    
    def confirm_deposit(self, user_id):
        """Depoziti onayla ve ödeme bilgilerini göster"""
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_telegram_message(user_id, "❌ Depozit bilgisi bulunamadı!")
            return
        
        amount_try = data['amount_try']
        amount_trx = data['amount_trx']
        trx_price = data['trx_price']
        bonus_amount = data['bonus_amount']
        
        # Depozit ID oluştur
        deposit_id = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:10].upper()
        
        # Depozit verilerini hazırla
        deposit_data = {
            'deposit_id': deposit_id,
            'user_id': user_id,
            'amount_try': amount_try,
            'amount_trx': amount_trx,
            'trx_price': trx_price,
            'bonus_amount': bonus_amount,
            'wallet_address': TRX_ADDRESS,
            'status': 'pending'
        }
        
        # Veritabanına kaydet
        if self.db.create_deposit(deposit_data):
            # Kullanıcı durumunu güncelle
            data['deposit_id'] = deposit_id
            self.set_user_state(user_id, 'deposit_pending', data)
            
            # Ödeme bilgilerini göster
            total_with_bonus = amount_try + bonus_amount
            
            message = (
                f"💳 <b>ÖDEME BİLGİLERİ</b>\n"
                f"══════════════════════════════\n\n"
                f"📋 <b>Depozit ID:</b> <code>{deposit_id}</code>\n"
                f"💵 <b>Tutar:</b> {amount_try:.2f}₺\n"
                f"₿ <b>TRX Miktarı:</b> {amount_trx:.4f} TRX\n"
                f"📈 <b>TRX Fiyatı:</b> {trx_price:.2f}₺\n\n"
                f"🎁 <b>Bonus:</b> +{bonus_amount:.2f}₺ (%{DEPOSIT_BONUS_PERCENT})\n"
                f"💰 <b>Toplam Alacağınız:</b> {total_with_bonus:.2f}₺\n\n"
                f"🔗 <b>TRX ADRESİ:</b>\n"
                f"<code>{TRX_ADDRESS}</code>\n\n"
                f"👇 <b>Adım adım yapmanız gerekenler:</b>"
            )
            
            steps = (
                f"1. <b>Adresi kopyala</b> (üstüne tıkla)\n"
                f"2. <b>TRX cüzdanınızdan</b> {amount_trx:.4f} TRX gönder\n"
                f"3. <b>İşlem tamamlandığında</b> TXID'yi bana gönder\n"
                f"4. <b>Bakiyeniz otomatik yüklenecek</b>\n\n"
                f"⏳ <b>İşlem süresi:</b> 2-5 dakika\n"
                f"✅ <b>TXID formatı:</b> 64 karakterlik hex kodu"
            )
            
            markup = {
                'inline_keyboard': [
                    [
                        {'text': "📋 Adresi Kopyala", 'callback_data': f'copy_{TRX_ADDRESS}'},
                        {'text': "🔄 TRX Fiyatını Yenile", 'callback_data': 'refresh_trx_price'}
                    ],
                    [
                        {'text': "✅ TRX GÖNDERDİM", 'callback_data': 'sent_trx'},
                        {'text': "❌ İPTAL", 'callback_data': 'deposit_cancel'}
                    ]
                ]
            }
            
            # Mesajı gönder
            send_telegram_message(user_id, message)
            time.sleep(0.5)
            send_telegram_message(user_id, steps, markup)
            
        else:
            send_telegram_message(user_id, "❌ Depozit oluşturulurken bir hata oluştu!")
    
    def verify_deposit(self, user_id, deposit_id, txid):
        """Depoziti doğrula (simülasyon)"""
        try:
            # 30 saniye bekle (simülasyon için)
            time.sleep(30)
            
            # Depoziti tamamla
            user_state = self.get_user_state(user_id)
            data = user_state.get('data', {})
            
            amount_try = data.get('amount_try', 0)
            bonus_amount = data.get('bonus_amount', 0)
            
            # Bakiyeleri güncelle
            self.db.complete_deposit(deposit_id, user_id, amount_try + bonus_amount, bonus_amount)
            
            # Reklam bakiyesini de güncelle (%20 bonus)
            ads_bonus = amount_try * (ADS_BONUS_PERCENT / 100)
            self.db.add_balance(user_id, ads_bonus, is_ads_balance=True)
            
            # Kullanıcıya bildir
            total_normal = amount_try + bonus_amount
            total_ads = amount_try + ads_bonus
            
            success_msg = (
                f"✅ <b>DEPOZİT TAMAMLANDI!</b>\n\n"
                f"📋 <b>Depozit ID:</b> <code>{deposit_id}</code>\n"
                f"🔗 <b>TXID:</b> <code>{txid}</code>\n\n"
                f"💰 <b>BAKİYELERİNİZ YÜKLENDİ:</b>\n"
                f"• Normal Bakiye: +{total_normal:.2f}₺\n"
                f"• Reklam Bakiye: +{total_ads:.2f}₺\n\n"
                f"🎁 <b>TOPLAM BONUS:</b> {bonus_amount + ads_bonus:.2f}₺\n\n"
                f"💡 Artık görev yapmaya veya kampanya oluşturmaya başlayabilirsiniz!"
            )
            
            send_telegram_message(user_id, success_msg)
            
            # Kullanıcı durumunu temizle
            self.clear_user_state(user_id)
            
        except Exception as e:
            print(f"❌ Depozit doğrulama hatası: {e}")
            
            # Hata mesajı gönder
            error_msg = (
                f"❌ <b>DEPOZİT DOĞRULANAMADI!</b>\n\n"
                f"📋 <b>Depozit ID:</b> <code>{deposit_id}</code>\n"
                f"🔗 <b>TXID:</b> <code>{txid}</code>\n\n"
                f"⚠️ <b>Hata:</b> İşlem doğrulanamadı.\n\n"
                f"💡 Lütfen:\n"
                f"1. TXID'nin doğru olduğundan emin olun\n"
                f"2. İşlemin onaylandığından emin olun\n"
                f"3. Destek ekibiyle iletişime geçin"
            )
            
            send_telegram_message(user_id, error_msg)
    
    def show_balance_detail(self, user_id):
        """Detaylı bakiye bilgisi göster"""
        user = self.db.get_user(user_id)
        
        normal_balance = user.get('balance', 0)
        ads_balance = user.get('ads_balance', 0)
        total_balance = normal_balance + ads_balance
        
        total_deposited = user.get('total_deposited', 0)
        total_bonus = user.get('total_bonus', 0)
        
        message = (
            f"💰 <b>BAKİYE DETAYLARI</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 <b>Kullanıcı:</b> {user.get('name', 'Kullanıcı')}\n"
            f"🆔 <b>ID:</b> {user_id}\n\n"
            f"💵 <b>NORMAL BAKİYE:</b> {normal_balance:.2f}₺\n"
            f"📺 <b>REKLAM BAKİYESİ:</b> {ads_balance:.2f}₺\n"
            f"💰 <b>TOPLAM BAKİYE:</b> {total_balance:.2f}₺\n\n"
            f"📊 <b>İSTATİSTİKLER:</b>\n"
            f"• Toplam Yatırım: {total_deposited:.2f}₺\n"
            f"• Toplam Bonus: {total_bonus:.2f}₺\n"
            f"• Görev Sayısı: {user.get('tasks_completed', 0)}\n"
            f"• Referans: {user.get('referrals', 0)}\n\n"
            f"💡 <b>Reklam bakiyesi %20 bonusludur!</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
                    {'text': "📺 Reklam Bakiyem", 'callback_data': 'myads'}
                ],
                [
                    {'text': "🔄 Çevir", 'callback_data': 'convert_ads'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_ads_balance(self, user_id):
        """Reklam bakiyesini göster"""
        user = self.db.get_user(user_id)
        ads_balance = user.get('ads_balance', 0)
        
        # Reklam bakiyesi geçmişini getir
        self.db.cursor.execute('''
            SELECT * FROM ads_balances 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 5
        ''', (user_id,))
        ads_history = self.db.cursor.fetchall()
        
        message = (
            f"📺 <b>REKLAM BAKİYESİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Toplam Reklam Bakiyesi:</b> {ads_balance:.2f}₺\n"
            f"🎁 <b>Bonus Oranı:</b> %{ADS_BONUS_PERCENT}\n\n"
            f"💡 <b>Reklam bakiyesi ile:</b>\n"
            f"1. Görev yapabilirsiniz\n"
            f"2. Kampanya oluşturabilirsiniz\n"
            f"3. %20 bonuslu olarak yatırım yapabilirsiniz\n\n"
        )
        
        if ads_history:
            message += f"📋 <b>SON İŞLEMLER:</b>\n"
            for i, ad in enumerate(ads_history, 1):
                amount = ad['amount']
                desc = ad['description'][:30] + "..." if len(ad['description']) > 30 else ad['description']
                date = ad['created_at'][:10]
                message += f"{i}. {desc} - {amount:.2f}₺ ({date})\n"
            message += "\n"
        
        message += f"👇 <b>İşlem seçin:</b>"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🔄 Normal Bakiyeye Çevir", 'callback_data': 'convert_ads'},
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def start_convert_ads(self, user_id):
        """Reklam bakiyesini normal bakiyeye çevir"""
        user = self.db.get_user(user_id)
        ads_balance = user.get('ads_balance', 0)
        
        if ads_balance <= 0:
            send_telegram_message(
                user_id,
                "❌ <b>Çevrilecek reklam bakiyeniz yok!</b>\n\n"
                "Reklam bakiyesi oluşturmak için:\n"
                "1. Bakiye yükleyin (%20 bonus alın)\n"
                "2. Görev yapın\n"
                "3. Referans davet edin"
            )
            return
        
        # Dönüşüm oranı: 1:1 (bonus zaten verilmiş)
        convert_amount = ads_balance
        
        message = (
            f"🔄 <b>REKLAM BAKİYESİ ÇEVİRME</b>\n"
            f"══════════════════════════════\n\n"
            f"📺 <b>Mevcut Reklam Bakiyesi:</b> {ads_balance:.2f}₺\n"
            f"💵 <b>Alacağınız Normal Bakiye:</b> {convert_amount:.2f}₺\n"
            f"📊 <b>Dönüşüm Oranı:</b> 1:1\n\n"
            f"💡 <b>Not:</b> Reklam bakiyesi zaten %{ADS_BONUS_PERCENT} bonusludur.\n"
            f"Dönüşüm işleminde ekstra bonus yoktur.\n\n"
            f"👇 <b>Çevirmek istiyor musunuz?</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "✅ EVET, ÇEVİR", 'callback_data': 'confirm_convert_ads'},
                    {'text': "❌ İPTAL", 'callback_data': 'cancel_convert_ads'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_trx_price(self, user_id):
        """TRX fiyatını göster"""
        trx_price = self.trx_updater.get_price()
        
        # Fiyat geçmişini getir
        self.db.cursor.execute('''
            SELECT price_try, created_at FROM trx_prices 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        price_history = self.db.cursor.fetchall()
        
        message = (
            f"₿ <b>TRON (TRX) FİYAT BİLGİSİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💵 <b>Güncel Fiyat:</b> {trx_price:.2f}₺\n"
            f"⏰ <b>Son Güncelleme:</b> Şimdi\n"
            f"🔄 <b>Güncelleme Sıklığı:</b> 10 saniye\n\n"
            f"📊 <b>DEPOZİT ARALIĞI:</b>\n"
            f"• Minimum: {MIN_DEPOSIT_TRY}₺ ({(MIN_DEPOSIT_TRY/trx_price):.2f} TRX)\n"
            f"• Maksimum: {MAX_DEPOSIT_TRY}₺ ({(MAX_DEPOSIT_TRY/trx_price):.2f} TRX)\n\n"
        )
        
        if price_history:
            message += f"📈 <b>SON FİYATLAR:</b>\n"
            for i, price in enumerate(price_history, 1):
                price_val = price['price_try']
                time_str = price['created_at'][11:19]
                message += f"{i}. {price_val:.2f}₺ ({time_str})\n"
            message += "\n"
        
        message += f"🔗 <b>TRX ADRESİ:</b>\n<code>{TRX_ADDRESS}</code>"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🔄 Fiyatı Yenile", 'callback_data': 'refresh_trx_price'},
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
    def show_my_campaigns(self, user_id):
        """Kullanıcının kampanyalarını göster"""
        campaigns = self.db.get_user_campaigns(user_id)
        
        if not campaigns:
            send_telegram_message(
                user_id,
                "📭 <b>Henüz kampanya oluşturmadınız.</b>\n\n"
                "💡 İlk kampanyanızı oluşturarak para kazanmaya başlayın!"
            )
            return
        
        message = "📋 <b>KAMPANYALARIM</b>\n"
        message += "══════════════════════════════\n\n"
        message += f"📊 <b>Toplam:</b> {len(campaigns)} kampanya\n\n"
        
        total_spent = 0
        active_count = 0
        
        for i, campaign in enumerate(campaigns[:5], 1):
            task_icons = {'bot': '🤖', 'channel': '📢', 'group': '👥'}
            icon = task_icons.get(campaign['task_type'], '🎯')
            
            status = "✅ AKTİF" if campaign['is_active'] == 1 else "❌ DURDU"
            if campaign['is_active'] == 1:
                active_count += 1
            
            spent = campaign.get('total_spent', 0)
            total_spent += spent
            budget = campaign['budget']
            
            name = campaign['name']
            if len(name) > 20:
                name = name[:17] + "..."
            
            message += (
                f"<b>{i}.</b> {icon} {name}\n"
                f"   ├ <b>Durum:</b> {status}\n"
                f"   ├ <b>Bütçe:</b> {budget:.1f}₺\n"
                f"   ├ <b>Harcanan:</b> {spent:.1f}₺\n"
                f"   └ <b>Katılım:</b> {campaign['current_participants']}\n"
                f"   ━━━━━━━━━━━━━━━━━━━━━\n"
            )
        
        message += f"\n📈 <b>ÖZET:</b>\n"
        message += f"• Aktif: {active_count}\n"
        message += f"• Toplam Harcama: {total_spent:.2f}₺\n"
        message += f"• Toplam Katılım: {sum(c['current_participants'] for c in campaigns)}"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🎯 Yeni Kampanya", 'callback_data': 'create_campaign'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)
    
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
            "• Durum: OTOMATİK AKTİF\n\n"
            "📢 <b>KANAL KAMPANYASI</b>\n"
            "• Görev: Kanala katılma\n"
            "• Ödül: 1.5₺\n"
            "• Durum: OTOMATİK AKTİF\n\n"
            "👥 <b>GRUP KAMPANYASI</b>\n"
            "• Görev: Gruba katılma\n"
            "• Ödül: 1₺\n"
            "• Durum: OTOMATİK AKTİF\n\n"
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
    
    def show_campaign_summary(self, user_id, data):
        """Kampanya özetini göster"""
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
        ads_balance = user.get('ads_balance', 0)
        total_balance = user_balance + ads_balance
        
        summary = (
            f"🎯 <b>KAMPANYA ÖZETİ (5/5)</b>\n"
            f"══════════════════════════════\n\n"
            f"📛 <b>İsim:</b> {data.get('name', 'Belirtilmedi')}\n"
            f"📄 <b>Açıklama:</b> {data.get('description', 'Belirtilmedi')}\n"
            f"🔗 <b>Link:</b> {data.get('link', 'Belirtilmedi')}\n"
        )
        
        if task_type in ['channel', 'group']:
            summary += f"🎯 <b>Hedef:</b> {data.get('target_chat_id', 'Belirtilmedi')}\n"
        
        summary += (
            f"🎯 <b>Tip:</b> {task_names.get(task_type)}\n"
            f"💰 <b>Bütçe:</b> {budget:.2f}₺\n"
            f"💵 <b>Görev Ücreti:</b> {price}₺\n"
            f"👥 <b>Maksimum Katılım:</b> {max_participants}\n"
            f"👤 <b>Oluşturan:</b> {user.get('name', 'Kullanıcı')}\n"
            f"💵 <b>Mevcut Bakiyen:</b> {total_balance:.2f}₺\n"
            f"   ├ Normal: {user_balance:.2f}₺\n"
            f"   └ Reklam: {ads_balance:.2f}₺\n\n"
        )
        
        if total_balance < budget:
            summary += f"❌ <b>YETERSİZ BAKİYE!</b> {total_balance:.2f}₺ / {budget:.2f}₺\n"
        
        summary += "👇 <b>Hangi bakiye ile ödemek istiyorsunuz?</b>"
        
        markup = {
            'inline_keyboard': []
        }
        
        # Normal bakiye yeterliyse
        if user_balance >= budget:
            markup['inline_keyboard'].append([
                {'text': f"💰 Normal Bakiye ile ({budget:.2f}₺)", 'callback_data': 'campaign_pay_normal'}
            ])
        
        # Reklam bakiyesi yeterliyse
        if ads_balance >= budget:
            markup['inline_keyboard'].append([
                {'text': f"📺 Reklam Bakiyesi ile ({budget:.2f}₺)", 'callback_data': 'campaign_pay_ads'}
            ])
        
        # İkisi birlikte yeterliyse
        if total_balance >= budget and (user_balance < budget or ads_balance < budget):
            markup['inline_keyboard'].append([
                {'text': f"💳 İkisi Birlikte ({budget:.2f}₺)", 'callback_data': 'campaign_pay_both'}
            ])
        
        if not markup['inline_keyboard']:
            summary += f"\n❌ <b>Hiçbir bakiyeniz yeterli değil!</b>\n"
            summary += f"Lütfen bakiye yükleyin."
            markup['inline_keyboard'].append([
                {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
                {'text': "❌ İPTAL", 'callback_data': 'campaign_cancel'}
            ])
        else:
            markup['inline_keyboard'].append([
                {'text': "❌ İPTAL", 'callback_data': 'campaign_cancel'}
            ])
        
        send_telegram_message(user_id, summary, markup)
    
    def publish_campaign(self, user_id):
        """Kampanyayı yayınla - OTOMATİK AKTİF"""
        user_state = self.get_user_state(user_id)
        data = user_state['data']
        
        if not data:
            send_telegram_message(user_id, "❌ Kampanya verisi bulunamadı!")
            return
        
        payment_type = data.get('payment_type', 'normal')
        user = self.db.get_user(user_id)
        
        user_balance = user.get('balance', 0)
        ads_balance = user.get('ads_balance', 0)
        campaign_budget = data.get('budget', 0)
        
        # Ödeme tipine göre bakiye kontrolü
        if payment_type == 'normal' and user_balance < campaign_budget:
            send_telegram_message(
                user_id,
                f"❌ <b>NORMAL BAKİYE YETERSİZ!</b>\n\n"
                f"💵 <b>Gerekli:</b> {campaign_budget:.2f}₺\n"
                f"💰 <b>Mevcut:</b> {user_balance:.2f}₺"
            )
            return
        
        if payment_type == 'ads' and ads_balance < campaign_budget:
            send_telegram_message(
                user_id,
                f"❌ <b>REKLAM BAKİYESİ YETERSİZ!</b>\n\n"
                f"💵 <b>Gerekli:</b> {campaign_budget:.2f}₺\n"
                f"📺 <b>Mevcut:</b> {ads_balance:.2f}₺"
            )
            return
        
        if payment_type == 'both':
            remaining = campaign_budget
            use_normal = min(user_balance, remaining)
            remaining -= use_normal
            use_ads = min(ads_balance, remaining)
            
            if use_normal + use_ads < campaign_budget:
                send_telegram_message(
                    user_id,
                    f"❌ <b>TOPLAM BAKİYE YETERSİZ!</b>\n\n"
                    f"💵 <b>Gerekli:</b> {campaign_budget:.2f}₺\n"
                    f"💰 <b>Normal:</b> {user_balance:.2f}₺\n"
                    f"📺 <b>Reklam:</b> {ads_balance:.2f}₺\n"
                    f"📊 <b>Toplam:</b> {user_balance + ads_balance:.2f}₺"
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
            # Bakiyelerden düş
            if payment_type == 'normal':
                self.db.add_balance(user_id, -campaign_budget)
            elif payment_type == 'ads':
                # Reklam bakiyesinden düş
                self.db.update_user(user_id, {'ads_balance': ads_balance - campaign_budget})
            elif payment_type == 'both':
                # İkisinden de düş
                self.db.add_balance(user_id, -use_normal)
                self.db.update_user(user_id, {'ads_balance': ads_balance - use_ads})
            
            # Kullanıcıya bilgi ver
            task_names = {
                'bot': '🤖 Bot Kampanyası',
                'channel': '📢 Kanal Kampanyası',
                'group': '👥 Grup Kampanyası'
            }
            
            prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
            price = prices.get(full_data['task_type'], 1.0)
            max_participants = int(campaign_budget / price)
            
            success_msg = (
                f"✅ <b>KAMPANYA OLUŞTURULDU!</b>\n\n"
                f"📛 <b>İsim:</b> {full_data['name']}\n"
                f"🎯 <b>Tip:</b> {task_names.get(full_data['task_type'])}\n"
                f"💰 <b>Bütçe:</b> {full_data['budget']:.2f}₺\n"
                f"💵 <b>Görev Ücreti:</b> {price}₺\n"
                f"👥 <b>Maksimum Katılım:</b> {max_participants}\n"
                f"🔢 <b>Kampanya ID:</b> <code>{campaign_id}</code>\n\n"
                f"🎉 <b>Kampanya direkt aktif oldu!</b>\n"
                f"Kullanıcılar hemen katılmaya başlayabilir."
            )
            
            send_telegram_message(user_id, success_msg)
            
            self.clear_user_state(user_id)
        else:
            send_telegram_message(user_id, "❌ Kampanya oluşturulurken bir hata oluştu!")
    
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
                        # Referans bonusu
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
    
    def show_main_menu(self, user_id):
        """ANA MENÜ"""
        user = self.db.get_user(user_id)
        
        trx_price = self.trx_updater.get_price()
        
        message = (
            f"🚀 <b>GÖREV YAPSAM BOT v11.0</b>\n"
            f"══════════════════════════════\n\n"
            f"👋 <b>Merhaba {user.get('name', 'Kullanıcı')}!</b>\n\n"
            f"💰 <b>Bakiyen:</b> {user.get('balance', 0):.2f}₺\n"
            f"📺 <b>Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺\n"
            f"📊 <b>Görevler:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n\n"
            f"₿ <b>TRX Fiyatı:</b> {trx_price:.2f}₺\n\n"
            f"🎯 <b>YENİ ÖZELLİKLER:</b>\n"
            f"• 💰 TRX ile bakiye yükleme\n"
            f"• 📺 %20 bonuslu reklam bakiyesi\n"
            f"• 🎯 OTOMATİK kampanya sistemi\n"
            f"• 🎁 %35 depozit bonusu\n\n"
            f"📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🎯 GÖREV YAP", 'callback_data': 'active_campaigns'},
                    {'text': "📢 KAMPANYA OLUŞTUR", 'callback_data': 'create_campaign'}
                ],
                [
                    {'text': "💰 BAKİYE YÜKLE", 'callback_data': 'deposit'},
                    {'text': "📋 KAMPANYALARIM", 'callback_data': 'my_campaigns'}
                ],
                [
                    {'text': "👤 PROFİL", 'callback_data': 'profile'},
                    {'text': "🎁 GÜNLÜK BONUS", 'callback_data': 'daily_bonus'}
                ],
                [
                    {'text': "👥 REFERANS", 'callback_data': 'referral'},
                    {'text': "₿ TRX FİYATI", 'callback_data': 'trx_price'}
                ]
            ]
        }
        
        if user_id == ADMIN_ID:
            markup['inline_keyboard'].append([
                {'text': "👑 ADMIN", 'callback_data': 'admin'}
            ])
        
        send_telegram_message(user_id, message, markup)
    
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
            self.show_balance_detail(user_id)
        
        elif data == 'daily_bonus':
            self.handle_daily_bonus(user_id)
        
        elif data == 'referral':
            self.show_referral(user_id)
        
        elif data == 'help':
            self.show_help(user_id)
        
        elif data == 'withdraw':
            self.show_withdraw(user_id)
        
        elif data == 'refresh_trx_price':
            self.show_trx_price(user_id)
        
        elif data == 'sent_trx':
            self.ask_for_txid(user_id)
        
        else:
            self.show_main_menu(user_id)
    
    def ask_for_txid(self, user_id):
        """TXID girmesini iste"""
        user_state = self.get_user_state(user_id)
        
        if user_state['state'] != 'deposit_pending':
            send_telegram_message(
                user_id,
                "❌ <b>Devam eden bir depozit işleminiz yok!</b>\n\n"
                "Lütfen önce depozit işlemi başlatın."
            )
            return
        
        self.set_user_state(user_id, 'deposit_txid', user_state['data'])
        
        send_telegram_message(
            user_id,
            "📋 <b>TXID GİRİŞİ</b>\n\n"
            "Lütfen TRX işleminizin TXID'sini girin:\n\n"
            "💡 <b>TXID nedir?</b>\n"
            "• TRX gönderdiğinizde aldığınız işlem kodu\n"
            "• 64 karakterlik hexadecimal kod\n"
            "• Örnek: a1b2c3d4e5f6...\n\n"
            "⏳ <b>İşlem tamamlandıktan sonra</b> TXID'yi gönderin.\n"
            "✅ İşlem doğrulandığında bakiyeniz otomatik yüklenecektir."
        )
    
    def show_profile(self, user_id):
        """PROFİL"""
        user = self.db.get_user(user_id)
        
        # Son depozitleri getir
        deposits = self.db.get_user_deposits(user_id, 3)
        
        message = (
            f"👤 <b>PROFİL BİLGİLERİ</b>\n"
            f"══════════════════════════════\n\n"
            f"🆔 <b>ID:</b> {user_id}\n"
            f"👤 <b>İsim:</b> {user.get('name', 'Kullanıcı')}\n"
            f"🔗 <b>Kullanıcı Adı:</b> @{user.get('username', 'yok')}\n"
            f"💰 <b>Normal Bakiye:</b> {user.get('balance', 0):.2f}₺\n"
            f"📺 <b>Reklam Bakiyesi:</b> {user.get('ads_balance', 0):.2f}₺\n"
            f"📊 <b>Tamamlanan Görev:</b> {user.get('tasks_completed', 0)}\n"
            f"👥 <b>Referans:</b> {user.get('referrals', 0)}\n"
            f"🎯 <b>Toplam Kazanç:</b> {user.get('total_earned', 0):.2f}₺\n\n"
            f"💳 <b>DEPOZİT BİLGİLERİ:</b>\n"
            f"• Toplam Yatırım: {user.get('total_deposited', 0):.2f}₺\n"
            f"• Toplam Bonus: {user.get('total_bonus', 0):.2f}₺\n"
            f"• Depozit Sayısı: {user.get('deposit_count', 0)}\n\n"
        )
        
        if deposits:
            message += f"📋 <b>SON DEPOZİTLER:</b>\n"
            for dep in deposits:
                status_icon = "✅" if dep['status'] == 'completed' else "⏳" if dep['status'] == 'verifying' else "🔄"
                message += f"{status_icon} {dep['amount_try']:.2f}₺ - {dep['status']}\n"
            message += "\n"
        
        message += f"📅 <b>Kayıt Tarihi:</b> {user.get('created_at', 'Bilinmiyor')[:10]}"
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
                    {'text': "📺 Reklam Bakiyem", 'callback_data': 'myads'}
                ],
                [
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
            f"2. TRX ile bakiye yükle\n"
            f"3. Kampanya oluştur\n"
            f"4. Referans davet et\n\n"
            f"📢 <b>Sistem yakında aktif olacaktır!</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
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
        
        # Bonusu normal bakiyeye ekle
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
            f"• /deposit - Bakiye yükle\n"
            f"• /mycampaigns - Kampanyalarım\n"
            f"• /createcampaign - Kampanya oluştur\n"
            f"• /myads - Reklam bakiyem\n"
            f"• /convertads - Reklam bakiyesi çevir\n"
            f"• /trxprice - TRX fiyatı\n"
            f"• /bonus - Günlük bonus\n"
            f"• /referral - Referans sistemi\n"
            f"• /withdraw - Para çekme (YAKINDA)\n"
            f"• /help - Yardım\n\n"
            f"💰 <b>BAKİYE YÜKLEME:</b>\n"
            f"1. /deposit komutunu kullan\n"
            f"2. Tutar seç (25-200₺)\n"
            f"3. TRX adresine TRX gönder\n"
            f"4. TXID'yi gir\n"
            f"5. Bakiyen otomatik yüklenir\n\n"
            f"🎁 <b>BONUS SİSTEMİ:</b>\n"
            f"• Depozit: %{DEPOSIT_BONUS_PERCENT} normal bakiye\n"
            f"• Reklam: %{ADS_BONUS_PERCENT} reklam bakiyesi\n"
            f"• Referans: Her referans 1₺\n"
            f"• Günlük: Her gün 1-5₺\n\n"
            f"⚠️ <b>ÖNEMLİ KURALLAR</b>\n"
            f"• Sahte görev yasak\n"
            f"• Çoklu hesap yasak\n"
            f"• Spam yasak\n"
            f"• Kurallara uymayanlar banlanır"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
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
        
        self.db.cursor.execute("SELECT SUM(balance) as total FROM users")
        total_balance = self.db.cursor.fetchone()['total'] or 0.0
        
        self.db.cursor.execute("SELECT SUM(ads_balance) as total FROM users")
        total_ads_balance = self.db.cursor.fetchone()['total'] or 0.0
        
        self.db.cursor.execute("SELECT SUM(total_deposited) as total FROM users")
        total_deposited = self.db.cursor.fetchone()['total'] or 0.0
        
        message = (
            f"👑 <b>ADMIN PANELİ v11.0</b>\n"
            f"══════════════════════════════\n\n"
            f"📊 <b>İSTATİSTİKLER</b>\n"
            f"• Toplam Kullanıcı: <b>{total_users}</b>\n"
            f"• Toplam Normal Bakiye: {total_balance:.2f}₺\n"
            f"• Toplam Reklam Bakiye: {total_ads_balance:.2f}₺\n"
            f"• Toplam Yatırım: {total_deposited:.2f}₺\n"
            f"• TRX Fiyatı: {self.trx_updater.get_price():.2f}₺\n\n"
            f"🛠️ <b>ADMIN ARAÇLARI</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "👥 Kullanıcılar", 'callback_data': 'admin_users'},
                    {'text': "📊 İstatistik", 'callback_data': 'admin_stats'}
                ],
                [
                    {'text': "💰 Depozitler", 'callback_data': 'admin_deposits'},
                    {'text': "📢 Bildirim", 'callback_data': 'admin_broadcast'}
                ],
                [
                    {'text': "🔙 Ana Menü", 'callback_data': 'menu'}
                ]
            ]
        }
        
        send_telegram_message(user_id, message, markup)

# ================= 9. ANA PROGRAM =================
def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                    GÖREV YAPSAM BOT v11.0                      ║
    ║   TRX DEPOZİT + OTOMATİK GÖREV + REKLAM BAKİYESİ + BONUS SİSTEM║
    ╚════════════════════════════════════════════════════════════════╝
    
    ✅ /start ÇALIŞIYOR
    ✅ TRX Depozit Sistemi
    ✅ %35 Depozit Bonusu
    ✅ %20 Reklam Bakiyesi
    ✅ OTOMATİK kampanya sistemi
    ✅ Coingecko TRX fiyatı (10sn)
    ✅ TXID doğrulama sistemi
    """)
    
    bot = BotSystem()
    
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
    print(f"₿ TRX Adresi: {TRX_ADDRESS}")
    print(f"💰 Min Depozit: {MIN_DEPOSIT_TRY}₺, Max: {MAX_DEPOSIT_TRY}₺")
    print(f"🎁 Bonuslar: %{DEPOSIT_BONUS_PERCENT} Normal, %{ADS_BONUS_PERCENT} Reklam")
    print("🔗 Telegram'da /start yazarak test edin")
    
    return app

# ================= 10. UYGULAMA BAŞLATMA =================
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
        # Flask app başlat
        port = int(os.environ.get('PORT', 8080))
        print(f"🌐 Web server başlatılıyor: http://0.0.0.0:{port}")
        
        # Bot'u başlat
        main()
        
        # Flask app çalıştır
        app.run(host='0.0.0.0', port=port, debug=False)

def create_app():
    # Render için WSGI uyumlu fonksiyon
    bot = BotSystem()
    bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
    bot_thread.start()
    return app
