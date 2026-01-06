"""
🤖 GÖREV BOTU - TAM PAKET
Telegram: @GorevYapsam
Developer: Sen
Bot Token: 8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co
"""

import telebot
from telebot import types
import sqlite3
import time
import random
from datetime import datetime, timedelta
import threading
import os
import json

# ================= CONFIG =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877
MAIN_CHANNEL = "@GorevYapsam"
bot = telebot.TeleBot(TOKEN)

# ================= DATABASE =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Users table
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0,
                tasks_completed INTEGER DEFAULT 0,
                ads_purchased INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                referral_earned INTEGER DEFAULT 0,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                banned INTEGER DEFAULT 0
            )
        ''')
        
        # Tasks table
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT,
                title TEXT,
                description TEXT,
                target TEXT,
                reward INTEGER,
                max_completions INTEGER DEFAULT 100,
                current_completions INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Completed tasks
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                earned INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (task_id) REFERENCES tasks (task_id)
            )
        ''')
        
        # Ads table
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                ad_type TEXT,
                title TEXT,
                description TEXT,
                target TEXT,
                reward INTEGER,
                cost INTEGER,
                views INTEGER DEFAULT 0,
                completions INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Daily bonuses
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS daily_bonus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                last_claim TIMESTAMP,
                streak INTEGER DEFAULT 0,
                total_claimed INTEGER DEFAULT 0
            )
        ''')
        
        # Withdrawals
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                withdrawal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                method TEXT,
                details TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Referral codes
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS referral_codes (
                code_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT UNIQUE,
                uses INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 10,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User settings
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                notifications INTEGER DEFAULT 1,
                language TEXT DEFAULT 'tr',
                daily_reminder INTEGER DEFAULT 0
            )
        ''')
        
        # Admin logs
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    # ============ USER METHODS ============
    def add_user(self, user_id, username, first_name, referrer_id=None):
        """Yeni kullanıcı ekle"""
        self.c.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, referrer_id))
        
        if referrer_id:
            # Referrer'a bonus ver
            self.c.execute('''
                UPDATE users SET 
                referrals = referrals + 1,
                referral_earned = referral_earned + 5,
                balance = balance + 5
                WHERE user_id = ?
            ''', (referrer_id,))
            
            # Referral log
            self.c.execute('''
                INSERT INTO admin_logs (admin_id, action, details)
                VALUES (?, ?, ?)
            ''', (0, 'REFERRAL', f'{user_id} referred by {referrer_id}'))
        
        # Settings ekle
        self.c.execute('''
            INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
        ''', (user_id,))
        
        self.conn.commit()
    
    def get_user(self, user_id):
        """Kullanıcı bilgilerini getir"""
        self.c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        columns = [desc[0] for desc in self.c.description]
        row = self.c.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def update_balance(self, user_id, amount, reason=""):
        """Bakiye güncelle"""
        if amount > 0:
            self.c.execute('''
                UPDATE users SET 
                balance = balance + ?,
                total_earned = total_earned + ?,
                last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (amount, amount, user_id))
        else:
            self.c.execute('''
                UPDATE users SET 
                balance = balance + ?,
                total_spent = total_spent + ABS(?),
                last_active = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (amount, amount, user_id))
        
        # Log
        self.c.execute('''
            INSERT INTO admin_logs (admin_id, action, details)
            VALUES (?, ?, ?)
        ''', (user_id, 'BALANCE_UPDATE', f'{amount} - {reason}'))
        
        self.conn.commit()
    
    def get_balance(self, user_id):
        """Bakiye sorgula"""
        self.c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = self.c.fetchone()
        return result[0] if result else 0
    
    def update_last_active(self, user_id):
        """Son aktifliği güncelle"""
        self.c.execute('''
            UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
    
    # ============ TASK METHODS ============
    def add_task(self, task_type, title, description, target, reward, max_completions=100, created_by=0):
        """Yeni görev ekle"""
        self.c.execute('''
            INSERT INTO tasks (task_type, title, description, target, reward, max_completions, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_type, title, description, target, reward, max_completions, created_by))
        
        task_id = self.c.lastrowid
        
        # Log
        self.c.execute('''
            INSERT INTO admin_logs (admin_id, action, details)
            VALUES (?, ?, ?)
        ''', (created_by, 'TASK_ADD', f'{task_id}: {title}'))
        
        self.conn.commit()
        return task_id
    
    def get_random_task(self, task_type, user_id):
        """Kullanıcı için rastgele görev getir"""
        # Daha önce yapılmamış görevleri getir
        self.c.execute('''
            SELECT t.* FROM tasks t
            WHERE t.task_type = ? 
            AND t.is_active = 1
            AND t.current_completions < t.max_completions
            AND NOT EXISTS (
                SELECT 1 FROM completed_tasks ct
                WHERE ct.user_id = ? AND ct.task_id = t.task_id
            )
            ORDER BY RANDOM() LIMIT 1
        ''', (task_type, user_id))
        
        columns = [desc[0] for desc in self.c.description]
        row = self.c.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def get_task_by_id(self, task_id):
        """ID ile görev getir"""
        self.c.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
        columns = [desc[0] for desc in self.c.description]
        row = self.c.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def complete_task(self, user_id, task_id):
        """Görevi tamamla"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False
        
        reward = task['reward']
        
        # Tamamlananlara ekle
        self.c.execute('''
            INSERT INTO completed_tasks (user_id, task_id, earned)
            VALUES (?, ?, ?)
        ''', (user_id, task_id, reward))
        
        # Görev istatistiği güncelle
        self.c.execute('''
            UPDATE tasks SET current_completions = current_completions + 1
            WHERE task_id = ?
        ''', (task_id,))
        
        # Kullanıcı istatistiği güncelle
        self.c.execute('''
            UPDATE users SET 
            tasks_completed = tasks_completed + 1,
            balance = balance + ?,
            total_earned = total_earned + ?,
            last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (reward, reward, user_id))
        
        # Eğer reklam göreviyse
        if task['created_by'] > 0:
            self.c.execute('''
                UPDATE ads SET completions = completions + 1
                WHERE ad_id = ?
            ''', (task['created_by'],))
        
        self.conn.commit()
        return reward
    
    def get_user_tasks(self, user_id, limit=10):
        """Kullanıcının tamamladığı görevler"""
        self.c.execute('''
            SELECT ct.*, t.title, t.task_type, t.reward
            FROM completed_tasks ct
            JOIN tasks t ON ct.task_id = t.task_id
            WHERE ct.user_id = ?
            ORDER BY ct.completed_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        columns = [desc[0] for desc in self.c.description]
        rows = self.c.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    # ============ AD METHODS ============
    def create_ad(self, user_id, ad_type, title, description, target, reward, cost):
        """Yeni reklam oluştur"""
        expires_at = datetime.now() + timedelta(days=1)
        
        self.c.execute('''
            INSERT INTO ads (user_id, ad_type, title, description, target, reward, cost, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, ad_type, title, description, target, reward, cost, expires_at))
        
        ad_id = self.c.lastrowid
        
        # Kullanıcı bakiyesinden düş
        self.update_balance(user_id, -cost, f"Ad #{ad_id}")
        
        # Kullanıcı istatistiği
        self.c.execute('''
            UPDATE users SET ads_purchased = ads_purchased + 1
            WHERE user_id = ?
        ''', (user_id,))
        
        # Görev olarak ekle
        if ad_type == 'channel':
            task_type = 'channel'
        elif ad_type == 'bot':
            task_type = 'bot'
        else:
            task_type = 'other'
        
        self.add_task(
            task_type=task_type,
            title=title,
            description=description,
            target=target,
            reward=reward,
            max_completions=10,  # Varsayılan 10 tamamlama
            created_by=ad_id
        )
        
        self.conn.commit()
        return ad_id
    
    def get_user_ads(self, user_id):
        """Kullanıcının reklamlarını getir"""
        self.c.execute('''
            SELECT * FROM ads WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        columns = [desc[0] for desc in self.c.description]
        rows = self.c.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def get_pending_ads(self):
        """Onay bekleyen reklamlar"""
        self.c.execute('SELECT * FROM ads WHERE status = "pending" ORDER BY created_at')
        
        columns = [desc[0] for desc in self.c.description]
        rows = self.c.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def update_ad_status(self, ad_id, status):
        """Reklam durumu güncelle"""
        self.c.execute('UPDATE ads SET status = ? WHERE ad_id = ?', (status, ad_id))
        
        if status == 'approved':
            # Görevi aktif et
            self.c.execute('UPDATE tasks SET is_active = 1 WHERE created_by = ?', (ad_id,))
        
        self.conn.commit()
    
    # ============ DAILY BONUS ============
    def can_claim_daily(self, user_id):
        """Günlük bonus alabilir mi?"""
        self.c.execute('SELECT * FROM daily_bonus WHERE user_id = ?', (user_id,))
        row = self.c.fetchone()
        
        if not row:
            return True, 1  # İlk kez
        
        last_claim = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
        streak = row[3]
        now = datetime.now()
        
        # Aynı gün mü?
        if last_claim.date() == now.date():
            return False, streak
        
        # Arka arkaya mı?
        if (now.date() - last_claim.date()).days == 1:
            new_streak = streak + 1
        else:
            new_streak = 1
        
        return True, new_streak
    
    def claim_daily(self, user_id, streak):
        """Günlük bonusu ver"""
        # Bonus hesapla (max 20 TL)
        bonus = min(streak * 2, 20)
        
        # Bonus ver
        self.update_balance(user_id, bonus, "Daily bonus")
        
        # Kaydı güncelle
        self.c.execute('''
            INSERT OR REPLACE INTO daily_bonus (user_id, last_claim, streak, total_claimed)
            VALUES (?, CURRENT_TIMESTAMP, ?, COALESCE((SELECT total_claimed FROM daily_bonus WHERE user_id = ?), 0) + ?)
        ''', (user_id, streak, user_id, bonus))
        
        self.conn.commit()
        return bonus
    
    # ============ LEADERBOARD ============
    def get_leaderboard(self, limit=10):
        """Lider tablosu"""
        self.c.execute('''
            SELECT user_id, username, balance, tasks_completed, total_earned
            FROM users 
            WHERE banned = 0
            ORDER BY balance DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in self.c.description]
        rows = self.c.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def get_user_rank(self, user_id):
        """Kullanıcı sıralaması"""
        self.c.execute('''
            SELECT COUNT(*) FROM users 
            WHERE balance > (SELECT balance FROM users WHERE user_id = ?) 
            AND banned = 0
        ''', (user_id,))
        return self.c.fetchone()[0] + 1
    
    # ============ WITHDRAWAL ============
    def create_withdrawal(self, user_id, amount, method, details):
        """Para çekme talebi oluştur"""
        self.c.execute('''
            INSERT INTO withdrawals (user_id, amount, method, details)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, method, details))
        
        # Bakiyeden düş
        self.update_balance(user_id, -amount, "Withdrawal")
        
        withdrawal_id = self.c.lastrowid
        
        # Admin'e bildir
        user = self.get_user(user_id)
        self.c.execute('''
            INSERT INTO admin_logs (admin_id, action, details)
            VALUES (?, ?, ?)
        ''', (0, 'WITHDRAWAL_REQUEST', 
              f'ID: {withdrawal_id}, User: {user_id}, Amount: {amount}, Method: {method}'))
        
        self.conn.commit()
        return withdrawal_id
    
    def get_pending_withdrawals(self):
        """Bekleyen para çekme talepleri"""
        self.c.execute('SELECT * FROM withdrawals WHERE status = "pending" ORDER BY requested_at')
        
        columns = [desc[0] for desc in self.c.description]
        rows = self.c.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    
    def update_withdrawal_status(self, withdrawal_id, status):
        """Para çekme durumu güncelle"""
        self.c.execute('''
            UPDATE withdrawals SET status = ?, processed_at = CURRENT_TIMESTAMP
            WHERE withdrawal_id = ?
        ''', (status, withdrawal_id))
        
        self.conn.commit()
    
    # ============ STATISTICS ============
    def get_stats(self):
        """Bot istatistikleri"""
        stats = {}
        
        # Toplam kullanıcı
        self.c.execute('SELECT COUNT(*) FROM users')
        stats['total_users'] = self.c.fetchone()[0]
        
        # Aktif kullanıcı (son 7 gün)
        self.c.execute('''
            SELECT COUNT(*) FROM users 
            WHERE last_active >= datetime('now', '-7 days')
        ''')
        stats['active_users'] = self.c.fetchone()[0]
        
        # Toplam bakiye
        self.c.execute('SELECT SUM(balance) FROM users')
        stats['total_balance'] = self.c.fetchone()[0] or 0
        
        # Toplam kazanç
        self.c.execute('SELECT SUM(total_earned) FROM users')
        stats['total_earned'] = self.c.fetchone()[0] or 0
        
        # Toplam görev
        self.c.execute('SELECT COUNT(*) FROM completed_tasks')
        stats['total_tasks'] = self.c.fetchone()[0]
        
        # Aktif görev
        self.c.execute('SELECT COUNT(*) FROM tasks WHERE is_active = 1')
        stats['active_tasks'] = self.c.fetchone()[0]
        
        return stats
    
    def close(self):
        """Bağlantıyı kapat"""
        self.conn.close()

# Database instance
db = Database()

# ================= BOT FUNCTIONS =================
def check_channel_membership(user_id):
    """Kanal üyeliğini kontrol et"""
    try:
        chat_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False

def format_number(num):
    """Sayıyı formatla"""
    return f"{num:,}".replace(",", ".")

def get_task_type_name(task_type):
    """Görev türü ismini getir"""
    names = {
        'channel': '📢 Kanal Görevi',
        'bot': '🤖 Bot Görevi', 
        'forward': '🔁 Forward Görevi',
        'website': '🌐 Website Görevi',
        'review': '⭐ Yorum Görevi',
        'other': '📝 Diğer Görev'
    }
    return names.get(task_type, '📝 Görev')

def create_main_menu():
    """Ana menü oluştur"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görevler", callback_data="main_tasks"),
        types.InlineKeyboardButton("💰 Bakiyem", callback_data="main_balance"),
        types.InlineKeyboardButton("📢 Reklam Ver", callback_data="main_ads"),
        types.InlineKeyboardButton("🏆 Lider Tablosu", callback_data="main_leaderboard"),
        types.InlineKeyboardButton("🎁 Günlük Bonus", callback_data="main_daily"),
        types.InlineKeyboardButton("💳 Para Çek", callback_data="main_withdraw"),
        types.InlineKeyboardButton("👤 Profilim", callback_data="main_profile"),
        types.InlineKeyboardButton("⚙️ Ayarlar", callback_data="main_settings"),
        types.InlineKeyboardButton("📞 Destek", callback_data="main_support"),
        types.InlineKeyboardButton("ℹ️ Yardım", callback_data="main_help")
    )
    return markup

def create_task_menu():
    """Görev menüsü oluştur"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Kanal Görevleri", callback_data="task_channel"),
        types.InlineKeyboardButton("🤖 Bot Görevleri", callback_data="task_bot"),
        types.InlineKeyboardButton("🔁 Forward Görevleri", callback_data="task_forward"),
        types.InlineKeyboardButton("🌐 Website Görevleri", callback_data="task_website"),
        types.InlineKeyboardButton("⭐ Yorum Görevleri", callback_data="task_review"),
        types.InlineKeyboardButton("🎲 Rastgele Görev", callback_data="task_random"),
        types.InlineKeyboardButton("📋 Görev Geçmişim", callback_data="task_history"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    return markup

def create_back_button(back_to="main_menu"):
    """Geri butonu oluştur"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Geri", callback_data=back_to))
    return markup

# ================= COMMAND HANDLERS =================
@bot.message_handler(commands=['start'])
def start_command(message):
    """Başlangıç komutu"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Kullanıcı"
    
    # Referral kontrol
    referrer_id = None
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
        try:
            referrer_id = int(ref_code)
        except:
            pass
    
    # Kullanıcıyı ekle
    db.add_user(user_id, username, first_name, referrer_id)
    db.update_last_active(user_id)
    
    # Kanal kontrolü
    if not check_channel_membership(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 Kanalımıza Katıl", url=f"https://t.me/{MAIN_CHANNEL[1:]}"),
            types.InlineKeyboardButton("✅ Katıldım", callback_data="check_channel")
        )
        
        bot.send_message(
            message.chat.id,
            f"👋 *Merhaba {first_name}!*\n\n"
            f"🤖 *Görev Botu*'na hoş geldin!\n\n"
            f"⚠️ *Devam etmek için kanalımıza katılmalısın:*\n"
            f"{MAIN_CHANNEL}\n\n"
            f"Katıldıktan sonra '✅ Katıldım' butonuna tıkla.",
            parse_mode='Markdown',
            reply_markup=markup
        )
        return
    
    # Karşılama mesajı
    user = db.get_user(user_id)
    balance = user['balance'] if user else 0
    
    welcome_text = f"""
    🎉 *HOŞ GELDİN {first_name}!* 🎉

    🤖 *Görev Botu* ile para kazanmaya hazır mısın?

    💰 *Mevcut Bakiyen:* `{format_number(balance)} TL`

    🎯 *Yapabileceklerin:*
    • Görevler yap → Para kazan
    • Reklam ver → Kendini tanıt  
    • Günlük bonus al → Her gün para
    • Lider ol → En çok kazanan sen ol
    • Para çek → Kazandığını al

    🔥 *Hemen başlamak için aşağıdaki butonları kullan!*
    """
    
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=create_main_menu()
    )

@bot.message_handler(commands=['balance'])
def balance_command(message):
    """Bakiye komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ Lütfen önce /start yazın.")
        return
    
    balance_text = f"""
    💰 *BAKİYE DETAYLARI*

    👤 Kullanıcı: @{user['username'] or user['first_name']}
    
    💵 *Cari Bakiye:* `{format_number(user['balance'])} TL`
    📈 *Toplam Kazanç:* `{format_number(user['total_earned'])} TL`
    📉 *Toplam Harcama:* `{format_number(user['total_spent'])} TL`
    
    ✅ *Tamamlanan Görev:* {user['tasks_completed']}
    📢 *Satın Alınan Reklam:* {user['ads_purchased']}
    
    👥 *Referanslar:* {user['referrals']} kişi
    🎁 *Referans Kazancı:* `{format_number(user['referral_earned'])} TL`
    
    ⚡ *Son Aktif:* {user['last_active'][:16]}
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("📢 Reklam Ver", callback_data="main_ads"),
        types.InlineKeyboardButton("💳 Para Çek", callback_data="main_withdraw"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        balance_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['tasks'])
def tasks_command(message):
    """Görevler komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    if not check_channel_membership(user_id):
        bot.send_message(
            message.chat.id,
            f"❌ Görev yapmak için kanalımıza katılmalısın: {MAIN_CHANNEL}",
            reply_markup=create_back_button()
        )
        return
    
    bot.send_message(
        message.chat.id,
        "🎯 *GÖREV MERKEZİ*\n\n"
        "Aşağıdaki görev türlerinden birini seç ve para kazanmaya başla!\n\n"
        "📢 *Kanal Görevleri:* Kanallara katıl\n"
        "🤖 *Bot Görevleri:* Botlara katıl\n"  
        "🔁 *Forward Görevleri:* Mesaj paylaş\n"
        "🌐 *Website Görevleri:* Site ziyaret\n"
        "⭐ *Yorum Görevleri:* Yorum bırak\n"
        "🎲 *Rastgele Görev:* Şansını dene",
        parse_mode='Markdown',
        reply_markup=create_task_menu()
    )

@bot.message_handler(commands=['daily'])
def daily_command(message):
    """Günlük bonus komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    can_claim, streak = db.can_claim_daily(user_id)
    
    if can_claim:
        bonus = db.claim_daily(user_id, streak)
        new_balance = db.get_balance(user_id)
        
        text = f"""
        🎁 *GÜNLÜK BONUS KAZANDIN!* 🎁

        ✅ Bonus başarıyla hesabına yatırıldı!

        📊 *Detaylar:*
        • Seri: `{streak}. gün`
        • Bonus Miktarı: `+{format_number(bonus)} TL`
        • Yeni Bakiye: `{format_number(new_balance)} TL`
        
        🔥 *Tebrikler!* Yarın tekrar gel, serini bozma!
        
        💡 *İpucu:* 7 gün üst üste gelerek max bonusu al!
        """
    else:
        text = """
        ⏳ *BUGÜNLÜK BONUSUNU ZATEN ALDIN!*

        ❌ Her kullanıcı günde sadece 1 kez bonus alabilir.

        ⏰ *Yeni bonus için:* 24 saat sonra tekrar gel!
        
        📅 *Bonus Sıfırlanma:* Her gün 00:00'da
        """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("💰 Bakiyemi Gör", callback_data="main_balance"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['leaderboard'])
def leaderboard_command(message):
    """Lider tablosu komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    leaders = db.get_leaderboard(15)
    user_rank = db.get_user_rank(user_id)
    user_balance = db.get_balance(user_id)
    
    text = "🏆 *EN ÇOK KAZANANLAR* 🏆\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️⃣1️⃣", "1️⃣2️⃣", "1️⃣3️⃣", "1️⃣4️⃣", "1️⃣5️⃣"]
    
    for i, leader in enumerate(leaders):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{leader['username']}" if leader['username'] else leader.get('first_name', 'Anonim')
        if len(name) > 15:
            name = name[:12] + "..."
        
        text += f"{medal} *{name}*\n"
        text += f"   💰 `{format_number(leader['balance'])} TL` | ✅ {leader['tasks_completed']} görev\n\n"
    
    text += f"📊 *Senin Sıran:* #{user_rank}\n"
    text += f"💰 *Senin Bakiyen:* `{format_number(user_balance)} TL`\n\n"
    text += "🔥 *En çok kazanan sen ol!*"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("👤 Profilim", callback_data="main_profile"),
        types.InlineKeyboardButton("🔄 Yenile", callback_data="main_leaderboard"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['profile'])
def profile_command(message):
    """Profil komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ Lütfen önce /start yazın.")
        return
    
    # Görev geçmişi
    recent_tasks = db.get_user_tasks(user_id, 5)
    
    text = f"""
    👤 *PROFİL BİLGİLERİ*

    🆔 *Kullanıcı ID:* `{user_id}`
    👤 *Kullanıcı Adı:* @{user['username'] or 'Yok'}
    👋 *İsim:* {user['first_name']}
    
    📅 *Katılma Tarihi:* {user['joined_date'][:10]}
    ⚡ *Son Aktif:* {user['last_active'][:16]}
    
    📈 *İSTATİSTİKLER*
    
    💰 *Finansal:*
    • Anlık Bakiye: `{format_number(user['balance'])} TL`
    • Toplam Kazanç: `{format_number(user['total_earned'])} TL`
    • Toplam Harcama: `{format_number(user['total_spent'])} TL`
    
    🎯 *Görevler:*
    • Tamamlanan: {user['tasks_completed']} görev
    • Satın Alınan Reklam: {user['ads_purchased']}
    
    👥 *Referans Sistemi:*
    • Referanslar: {user['referrals']} kişi
    • Referans Kazancı: `{format_number(user['referral_earned'])} TL`
    
    🏆 *Sıralama:* #{db.get_user_rank(user_id)}
    """
    
    if recent_tasks:
        text += "\n📋 *Son Görevler:*\n"
        for task in recent_tasks[:3]:
            text += f"• {task['title'][:20]}... (+{task['earned']} TL)\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Detaylı İstatistik", callback_data="stats_detailed"),
        types.InlineKeyboardButton("📋 Görev Geçmişim", callback_data="task_history"),
        types.InlineKeyboardButton("👥 Referans Linkim", callback_data="referral_link"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['withdraw'])
def withdraw_command(message):
    """Para çekme komutu"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    user = db.get_user(user_id)
    if not user:
        bot.send_message(message.chat.id, "❌ Lütfen önce /start yazın.")
        return
    
    balance = user['balance']
    
    if balance < 50:
        bot.send_message(
            message.chat.id,
            f"❌ *Para çekmek için minimum 50 TL bakiyen olmalı!*\n\n"
            f"💰 Mevcut bakiyen: `{format_number(balance)} TL`\n"
            f"🎯 Eksik: `{format_number(50 - balance)} TL`\n\n"
            f"Görev yaparak para kazanmaya devam et!",
            parse_mode='Markdown',
            reply_markup=create_back_button()
        )
        return
    
    text = f"""
    💳 *PARA ÇEKME TALEBİ*

    💰 *Mevcut Bakiyen:* `{format_number(balance)} TL`
    
    ⚠️ *Minimum Çekim:* 50 TL
    ⚠️ *Maksimum Çekim:* 10,000 TL
    
    📋 *Çekim Yöntemleri:*
    1. Banka Havalesi (TR)
    2. PayPal
    3. Papara
    4. Payeer
    5. Crypto (USDT)
    
    ⏳ *İşlem Süresi:* 1-24 saat
    
    📝 *Talep oluşturmak için:*
    `/withdraw_50 banka Mehmet Yılmaz TR330006100519786647741326`
    
    💡 *Örnek:* `/withdraw_100 papara 1234567890`
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💸 50 TL Çek", callback_data="withdraw_50"),
        types.InlineKeyboardButton("💸 100 TL Çek", callback_data="withdraw_100"),
        types.InlineKeyboardButton("💸 250 TL Çek", callback_data="withdraw_250"),
        types.InlineKeyboardButton("💸 500 TL Çek", callback_data="withdraw_500"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    """Yardım komutu"""
    text = """
    🤖 *GÖREV BOTU YARDIM MERKEZİ*

    📌 *TEMEL KOMUTLAR:*
    /start - Botu başlat
    /balance - Bakiyeni gör
    /tasks - Görevleri gör
    /daily - Günlük bonus al
    /leaderboard - Lider tablosu
    /profile - Profilini gör
    /withdraw - Para çek
    /help - Bu mesajı gör

    ❓ *SIK SORULAN SORULAR:*

    *1. Para nasıl kazanılır?*
    • Görevler yap (kanal, bot, forward vb.)
    • Günlük bonus al
    • Arkadaşlarını davet et
    • Özel etkinliklere katıl

    *2. Para nasıl çekilir?*
    • Bakiye 50 TL üstü olmalı
    • /withdraw komutunu kullan
    • Çekim yöntemini belirt
    • Admin onayını bekle

    *3. Görev neden onaylanmıyor?*
    • Görevi doğru yaptığından emin ol
    • Kanala gerçekten katıldın mı?
    • Admin kontrolü gerekebilir
    • Bekleme süresi olabilir

    *4. Günlük bonus nedir?*
    • Her gün ücretsiz para
    • Arka arkaya gel, bonus artsın
    • Max 20 TL'ye kadar çıkabilir

    *5. Referans sistemi nedir?*
    • Arkadaşlarını davet et
    • Onlar kazanınca sen de kazan
    • Her referans için 5 TL bonus

    📞 *DESTEK:*
    • Sorularınız için: @GorevYapsam
    • Şikayetleriniz için: @GorevYapsam
    • Önerileriniz için: @GorevYapsam

    ⚠️ *KURALLAR:*
    • Sahte hesap yasak
    • Hile yapmak yasak
    • Spam yapmak yasak
    • Kuralları çiğneyenler banlanır
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 Kanalımız", url=f"https://t.me/{MAIN_CHANNEL[1:]}"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Admin komutu"""
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bu komut sadece admin içindir!")
        return
    
    text = """
    🔧 *ADMIN PANELİ*

    📊 *İstatistik Komutları:*
    /stats - Bot istatistikleri
    /users - Kullanıcı listesi
    /tasks_list - Görev listesi
    /ads_list - Reklam listesi
    /withdrawals_list - Çekim talepleri

    ⚙️ *Yönetim Komutları:*
    /add_task - Yeni görev ekle
    /add_balance - Bakiye ekle
    /ban_user - Kullanıcı banla
    /unban_user - Kullanıcı banını kaldır
    /approve_ad - Reklam onayla
    /reject_ad - Reklam reddet
    /approve_withdrawal - Çekim onayla
    /reject_withdrawal - Çekim reddet
    /broadcast - Tüm kullanıcılara mesaj gönder

    📝 *Örnek Kullanım:*
    /add_task channel "Kanal Adı" "Açıklama" "@kanal" 10
    /add_balance 123456789 100
    /broadcast Merhaba! Yeni görevler eklendi.
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistik", callback_data="admin_stats"),
        types.InlineKeyboardButton("➕ Görev Ekle", callback_data="admin_add_task"),
        types.InlineKeyboardButton("💰 Bakiye Ekle", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 Reklam Onay", callback_data="admin_ads"),
        types.InlineKeyboardButton("💳 Çekim Onay", callback_data="admin_withdrawals"),
        types.InlineKeyboardButton("👥 Kullanıcılar", callback_data="admin_users"),
        types.InlineKeyboardButton("🔔 Broadcast", callback_data="admin_broadcast")
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """İstatistikler komutu"""
    if message.from_user.id != ADMIN_ID:
        return
    
    stats = db.get_stats()
    
    text = f"""
    📊 *BOT İSTATİSTİKLERİ*

    👥 *Kullanıcılar:*
    • Toplam Kullanıcı: {stats['total_users']}
    • Aktif Kullanıcı (7 gün): {stats['active_users']}
    
    💰 *Finansal:*
    • Toplam Bakiye: {format_number(stats['total_balance'])} TL
    • Toplam Kazanç: {format_number(stats['total_earned'])} TL
    
    🎯 *Görevler:*
    • Toplam Tamamlanan: {stats['total_tasks']}
    • Aktif Görev: {stats['active_tasks']}
    
    ⚙️ *Sistem:*
    • Bot Durumu: ✅ Çalışıyor
    • Database: SQLite
    • Admin: @GorevYapsam
    """
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ================= CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Tüm callback'leri işle"""
    user_id = call.from_user.id
    db.update_last_active(user_id)
    
    # Ana menü
    if call.data == "main_menu":
        show_main_menu(call)
    
    elif call.data == "main_tasks":
        show_tasks_menu(call)
    
    elif call.data == "main_balance":
        show_balance_menu(call)
    
    elif call.data == "main_ads":
        show_ads_menu(call)
    
    elif call.data == "main_leaderboard":
        show_leaderboard_menu(call)
    
    elif call.data == "main_daily":
        show_daily_menu(call)
    
    elif call.data == "main_withdraw":
        show_withdraw_menu(call)
    
    elif call.data == "main_profile":
        show_profile_menu(call)
    
    elif call.data == "main_settings":
        show_settings_menu(call)
    
    elif call.data == "main_support":
        show_support_menu(call)
    
    elif call.data == "main_help":
        show_help_menu(call)
    
    # Görev türleri
    elif call.data.startswith("task_"):
        task_type = call.data.split("_")[1]
        if task_type == "random":
            task_types = ['channel', 'bot', 'forward', 'website', 'review']
            task_type = random.choice(task_types)
        
        show_random_task(call, task_type)
    
    elif call.data == "task_history":
        show_task_history(call)
    
    # Görev tamamlama
    elif call.data.startswith("complete_"):
        task_id = int(call.data.split("_")[1])
        complete_task_action(call, task_id)
    
    # Günlük bonus
    elif call.data == "claim_daily":
        claim_daily_action(call)
    
    # Para çekme
    elif call.data.startswith("withdraw_"):
        amount = int(call.data.split("_")[1])
        show_withdraw_methods(call, amount)
    
    # Kanal kontrol
    elif call.data == "check_channel":
        check_channel_action(call)
    
    # Admin
    elif call.data.startswith("admin_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Yetkin yok!", show_alert=True)
            return
        handle_admin_action(call)

def show_main_menu(call):
    """Ana menüyü göster"""
    user = db.get_user(call.from_user.id)
    balance = user['balance'] if user else 0
    
    text = f"""
    🏠 *ANA MENÜ*

    👋 Merhaba {call.from_user.first_name}!
    
    💰 *Bakiyen:* `{format_number(balance)} TL`
    ✅ *Görevlerin:* {user['tasks_completed'] if user else 0} tamamlandı
    
    ⚡ *Hızlı Erişim:*
    """
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_main_menu()
    )
    bot.answer_callback_query(call.id)

def show_tasks_menu(call):
    """Görev menüsünü göster"""
    if not check_channel_membership(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            f"❌ Görev yapmak için kanalımıza katılmalısın: {MAIN_CHANNEL}",
            show_alert=True
        )
        return
    
    bot.edit_message_text(
        "🎯 *GÖREV MERKEZİ*\n\n"
        "Aşağıdaki görev türlerinden birini seç ve para kazanmaya başla!\n\n"
        "📢 *Kanal Görevleri:* Kanallara katıl\n"
        "🤖 *Bot Görevleri:* Botlara katıl\n"  
        "🔁 *Forward Görevleri:* Mesaj paylaş\n"
        "🌐 *Website Görevleri:* Site ziyaret\n"
        "⭐ *Yorum Görevleri:* Yorum bırak\n"
        "🎲 *Rastgele Görev:* Şansını dene",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=create_task_menu()
    )
    bot.answer_callback_query(call.id)

def show_random_task(call, task_type):
    """Rastgele görev göster"""
    user_id = call.from_user.id
    task = db.get_random_task(task_type, user_id)
    
    if not task:
        bot.answer_callback_query(
            call.id,
            "❌ Bu türde uygun görev bulunamadı! Başka tür deneyin.",
            show_alert=True
        )
        return
    
    task_type_name = get_task_type_name(task_type)
    
    markup = types.InlineKeyboardMarkup()
    
    if task_type == 'channel':
        markup.add(
            types.InlineKeyboardButton("📢 Kanala Git", url=f"https://t.me/{task['target'][1:]}"),
            types.InlineKeyboardButton("✅ Tamamladım", callback_data=f"complete_{task['task_id']}")
        )
    elif task_type == 'bot':
        markup.add(
            types.InlineKeyboardButton("🤖 Bota Git", url=f"https://t.me/{task['target'][1:]}"),
            types.InlineKeyboardButton("✅ Tamamladım", callback_data=f"complete_{task['task_id']}")
        )
    elif task_type == 'forward':
        markup.add(
            types.InlineKeyboardButton("📨 Mesajı Gör", callback_data=f"viewmsg_{task['task_id']}"),
            types.InlineKeyboardButton("✅ Forward Ettim", callback_data=f"complete_{task['task_id']}")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("🌐 Siteye Git", url=task['target']),
            types.InlineKeyboardButton("✅ Tamamladım", callback_data=f"complete_{task['task_id']}")
        )
    
    markup.add(
        types.InlineKeyboardButton("🔄 Farklı Görev", callback_data=f"task_{task_type}"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = f"""
    🎯 *YENİ GÖREV* 🎯

    {task_type_name}
    
    📌 *{task['title']}*
    
    📝 *Açıklama:*
    {task['description']}
    
    💰 *Ödül:* `{format_number(task['reward'])} TL`
    ⏱️ *Süre:* 10 dakika
    👥 *Kalan:* {task['max_completions'] - task['current_completions']} kişi
    
    ⚠️ *Not:* Görevi tamamladıktan sonra butona basın.
    """
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def complete_task_action(call, task_id):
    """Görevi tamamla"""
    user_id = call.from_user.id
    
    # Görevi tamamla
    reward = db.complete_task(user_id, task_id)
    
    if reward:
        new_balance = db.get_balance(user_id)
        
        text = f"""
        ✅ *GÖREV TAMAMLANDI!* ✅

        🎉 Tebrikler! Görevi başarıyla tamamladın.
        
        💰 *Kazandın:* `+{format_number(reward)} TL`
        💰 *Yeni Bakiye:* `{format_number(new_balance)} TL`
        
        🚀 Hemen yeni görev yapmaya devam et!
        """
    else:
        text = """
        ❌ *HATA!*

        Bu görevi zaten tamamlamış olabilirsin
        veya görev artık aktif değil.
        
        Lütfen yeni bir görev seç.
        """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 Yeni Görev", callback_data="main_tasks"),
        types.InlineKeyboardButton("💰 Bakiyem", callback_data="main_balance"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id, f"✅ +{reward} TL kazandınız!" if reward else "❌ Hata!")

def show_balance_menu(call):
    """Bakiye menüsünü göster"""
    user = db.get_user(call.from_user.id)
    
    text = f"""
    💰 *BAKİYE DETAYLARI*

    👤 Kullanıcı: @{user['username'] or user['first_name']}
    
    💵 *Cari Bakiye:* `{format_number(user['balance'])} TL`
    📈 *Toplam Kazanç:* `{format_number(user['total_earned'])} TL`
    📉 *Toplam Harcama:* `{format_number(user['total_spent'])} TL`
    
    ✅ *Tamamlanan Görev:* {user['tasks_completed']}
    📢 *Satın Alınan Reklam:* {user['ads_purchased']}
    
    👥 *Referanslar:* {user['referrals']} kişi
    🎁 *Referans Kazancı:* `{format_number(user['referral_earned'])} TL`
    
    ⚡ *Son Aktif:* {user['last_active'][:16]}
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("📢 Reklam Ver", callback_data="main_ads"),
        types.InlineKeyboardButton("💳 Para Çek", callback_data="main_withdraw"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_ads_menu(call):
    """Reklam menüsünü göster"""
    user = db.get_user(call.from_user.id)
    balance = user['balance']
    
    text = f"""
    📢 *REKLAM PANELİ*

    💰 *Mevcut Bakiyen:* `{format_number(balance)} TL`
    
    🎯 *Reklam Türleri:*
    
    📢 *Kanal Reklamı* (50 TL)
    • Kanalını tanıt
    • 24 saat gözükür
    • 10 kişi tamamlamalı
    
    🤖 *Bot Reklamı* (30 TL)
    • Botunu tanıt  
    • 24 saat gözükür
    • 10 kişi tamamlamalı
    
    🔗 *Link Reklamı* (20 TL)
    • Web siteni tanıt
    • 24 saat gözükür
    • 10 kişi tamamlamalı
    
    ⚠️ *Kurallar:*
    1. Sahte link yasak
    2. Yetişkin içerik yasak
    3. Spam yasak
    4. Admin onayı zorunlu
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Kanal Reklamı", callback_data="ad_channel"),
        types.InlineKeyboardButton("🤖 Bot Reklamı", callback_data="ad_bot"),
        types.InlineKeyboardButton("🔗 Link Reklamı", callback_data="ad_link"),
        types.InlineKeyboardButton("📋 Reklamlarım", callback_data="my_ads"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_leaderboard_menu(call):
    """Lider tablosu menüsü"""
    leaders = db.get_leaderboard(15)
    user_rank = db.get_user_rank(call.from_user.id)
    user_balance = db.get_balance(call.from_user.id)
    
    text = "🏆 *EN ÇOK KAZANANLAR* 🏆\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "1️⃣1️⃣", "1️⃣2️⃣", "1️⃣3️⃣", "1️⃣4️⃣", "1️⃣5️⃣"]
    
    for i, leader in enumerate(leaders):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{leader['username']}" if leader['username'] else leader.get('first_name', 'Anonim')
        if len(name) > 15:
            name = name[:12] + "..."
        
        text += f"{medal} *{name}*\n"
        text += f"   💰 `{format_number(leader['balance'])} TL` | ✅ {leader['tasks_completed']} görev\n\n"
    
    text += f"📊 *Senin Sıran:* #{user_rank}\n"
    text += f"💰 *Senin Bakiyen:* `{format_number(user_balance)} TL`\n\n"
    text += "🔥 *En çok kazanan sen ol!*"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("👤 Profilim", callback_data="main_profile"),
        types.InlineKeyboardButton("🔄 Yenile", callback_data="main_leaderboard"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_daily_menu(call):
    """Günlük bonus menüsü"""
    user_id = call.from_user.id
    can_claim, streak = db.can_claim_daily(user_id)
    
    if can_claim:
        bonus = min(streak * 2, 20)
        
        text = f"""
        🎁 *GÜNLÜK BONUS* 🎁

        ✅ Bugün bonus alabilirsin!
        
        📊 *Detaylar:*
        • Mevcut Seri: `{streak-1 if streak > 1 else 0} gün`
        • Yeni Seri: `{streak}. gün`
        • Kazanacak: `{format_number(bonus)} TL`
        
        💡 *Seri Bonusları:*
        1. gün: 2 TL
        2. gün: 4 TL
        3. gün: 6 TL
        4. gün: 8 TL
        5. gün: 10 TL
        6. gün: 12 TL
        7. gün: 14 TL
        8+ gün: 20 TL (max)
        
        🔥 *Bonus al ve serini bozma!*
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎁 Bonus Al", callback_data="claim_daily"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
    else:
        text = """
        ⏳ *BUGÜNLÜK BONUSUNU ZATEN ALDIN!*

        ❌ Her kullanıcı günde sadece 1 kez bonus alabilir.

        ⏰ *Yeni bonus için:* 24 saat sonra tekrar gel!
        
        📅 *Bonus Sıfırlanma:* Her gün 00:00'da
        
        💡 *İpucu:* Yarın tekrar gel, serini devam ettir!
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def claim_daily_action(call):
    """Günlük bonusu al"""
    user_id = call.from_user.id
    can_claim, streak = db.can_claim_daily(user_id)
    
    if can_claim:
        bonus = db.claim_daily(user_id, streak)
        new_balance = db.get_balance(user_id)
        
        text = f"""
        🎁 *GÜNLÜK BONUS KAZANDIN!* 🎁

        ✅ Bonus başarıyla hesabına yatırıldı!

        📊 *Detaylar:*
        • Seri: `{streak}. gün`
        • Bonus Miktarı: `+{format_number(bonus)} TL`
        • Yeni Bakiye: `{format_number(new_balance)} TL`
        
        🔥 *Tebrikler!* Yarın tekrar gel, serini bozma!
        
        💡 *İpucu:* 7 gün üst üste gelerek max bonusu al!
        """
    else:
        text = """
        ⏳ *BUGÜNLÜK BONUSUNU ZATEN ALDIN!*

        ❌ Her kullanıcı günde sadece 1 kez bonus alabilir.

        ⏰ *Yeni bonus için:* 24 saat sonra tekrar gel!
        
        📅 *Bonus Sıfırlanma:* Her gün 00:00'da
        """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
        types.InlineKeyboardButton("💰 Bakiyemi Gör", callback_data="main_balance"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_withdraw_menu(call):
    """Para çekme menüsü"""
    user = db.get_user(call.from_user.id)
    balance = user['balance']
    
    if balance < 50:
        text = f"""
        ❌ *PARA ÇEKME ŞARTI*

        💰 *Mevcut Bakiyen:* `{format_number(balance)} TL`
        
        ⚠️ *Minimum Çekim:* 50 TL
        
        🎯 *Eksik:* `{format_number(50 - balance)} TL`
        
        Görev yaparak para kazanmaya devam et!
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 Görev Yap", callback_data="main_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
    else:
        text = f"""
        💳 *PARA ÇEKME TALEBİ*

        💰 *Mevcut Bakiyen:* `{format_number(balance)} TL`
        
        ⚠️ *Minimum Çekim:* 50 TL
        ⚠️ *Maksimum Çekim:* 10,000 TL
        
        📋 *Çekim Yöntemleri:*
        1. Banka Havalesi (TR)
        2. PayPal
        3. Papara
        4. Payeer
        5. Crypto (USDT)
        
        ⏳ *İşlem Süresi:* 1-24 saat
        
        💰 *Tutar seç:*
        """
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("💸 50 TL", callback_data="withdraw_50"),
            types.InlineKeyboardButton("💸 100 TL", callback_data="withdraw_100"),
            types.InlineKeyboardButton("💸 250 TL", callback_data="withdraw_250"),
            types.InlineKeyboardButton("💸 500 TL", callback_data="withdraw_500"),
            types.InlineKeyboardButton("💸 1000 TL", callback_data="withdraw_1000"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_withdraw_methods(call, amount):
    """Para çekme yöntemlerini göster"""
    user = db.get_user(call.from_user.id)
    balance = user['balance']
    
    if amount > balance:
        bot.answer_callback_query(
            call.id,
            f"❌ Yetersiz bakiye! Mevcut: {format_number(balance)} TL",
            show_alert=True
        )
        return
    
    text = f"""
    💳 *PARA ÇEKME TALEBİ*

    💰 *Çekilecek Tutar:* `{format_number(amount)} TL`
    💵 *Kalan Bakiye:* `{format_number(balance - amount)} TL`
    
    📋 *Çekim Yöntemi Seç:*
    
    🇹🇷 *BANK TRANSFER* (TR)
    • Banka Adı:
    • IBAN/Account:
    • Ad Soyad:
    
    🌍 *PAYPAL*
    • PayPal Email:
    
    📱 *PAPARA*
    • Papara No:
    
    💰 *PAYEER*
    • Payeer No:
    
    ₿ *CRYPTO* (USDT)
    • Network (TRC20/ERC20):
    • Wallet Address:
    
    📝 *Not:* Bilgilerini doğru gir, yanlış bilgiden sorumlu değiliz.
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🏦 Banka", callback_data=f"withdraw_method_bank_{amount}"),
        types.InlineKeyboardButton("🌍 PayPal", callback_data=f"withdraw_method_paypal_{amount}"),
        types.InlineKeyboardButton("📱 Papara", callback_data=f"withdraw_method_papara_{amount}"),
        types.InlineKeyboardButton("💰 Payeer", callback_data=f"withdraw_method_payeer_{amount}"),
        types.InlineKeyboardButton("₿ Crypto", callback_data=f"withdraw_method_crypto_{amount}"),
        types.InlineKeyboardButton("◀️ Geri", callback_data="main_withdraw")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_profile_menu(call):
    """Profil menüsü"""
    user = db.get_user(call.from_user.id)
    
    text = f"""
    👤 *PROFİL BİLGİLERİ*

    🆔 *Kullanıcı ID:* `{call.from_user.id}`
    👤 *Kullanıcı Adı:* @{user['username'] or 'Yok'}
    👋 *İsim:* {user['first_name']}
    
    📅 *Katılma Tarihi:* {user['joined_date'][:10]}
    ⚡ *Son Aktif:* {user['last_active'][:16]}
    
    📈 *İSTATİSTİKLER*
    
    💰 *Finansal:*
    • Anlık Bakiye: `{format_number(user['balance'])} TL`
    • Toplam Kazanç: `{format_number(user['total_earned'])} TL`
    • Toplam Harcama: `{format_number(user['total_spent'])} TL`
    
    🎯 *Görevler:*
    • Tamamlanan: {user['tasks_completed']} görev
    • Satın Alınan Reklam: {user['ads_purchased']}
    
    👥 *Referans Sistemi:*
    • Referanslar: {user['referrals']} kişi
    • Referans Kazancı: `{format_number(user['referral_earned'])} TL`
    
    🏆 *Sıralama:* #{db.get_user_rank(call.from_user.id)}
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Detaylı İstatistik", callback_data="stats_detailed"),
        types.InlineKeyboardButton("📋 Görev Geçmişim", callback_data="task_history"),
        types.InlineKeyboardButton("👥 Referans Linkim", callback_data="referral_link"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_task_history(call):
    """Görev geçmişi"""
    user_id = call.from_user.id
    tasks = db.get_user_tasks(user_id, 10)
    
    if not tasks:
        text = """
        📋 *GÖREV GEÇMİŞİN*
        
        Henüz hiç görev tamamlamadın.
        
        🎯 Hemen ilk görevini yap ve para kazanmaya başla!
        """
    else:
        text = "📋 *SON 10 GÖREVİN*\n\n"
        
        for i, task in enumerate(tasks[:10], 1):
            date = task['completed_at'][:16]
            text += f"{i}. *{task['title'][:25]}...*\n"
            text += f"   📅 {date} | 💰 +{task['earned']} TL\n"
            text += f"   🏷️ {get_task_type_name(task['task_type'])}\n\n"
        
        total_earned = sum(task['earned'] for task in tasks)
        text += f"💰 *Toplam Kazanç:* {format_number(total_earned)} TL\n"
        text += f"✅ *Toplam Görev:* {len(tasks)}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 Yeni Görev", callback_data="main_tasks"),
        types.InlineKeyboardButton("◀️ Geri", callback_data="main_profile")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def check_channel_action(call):
    """Kanal kontrolü"""
    user_id = call.from_user.id
    
    if check_channel_membership(user_id):
        user = db.get_user(user_id)
        balance = user['balance'] if user else 0
        
        text = f"""
        ✅ *KANAL KONTROLÜ BAŞARILI!*

        Teşekkürler! Kanalımıza katıldığın için.
        
        🎉 Artık görev yapabilir ve para kazanmaya başlayabilirsin!
        
        💰 *Başlangıç Bakiyen:* `{format_number(balance)} TL`
        
        🚀 Hemen ilk görevini yap!
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 İlk Görevimi Yap", callback_data="main_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Teşekkürler! Artık görev yapabilirsin.")
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Hâlâ kanalda değilsin! Katıldıktan sonra tekrar dene.",
            show_alert=True
        )

def show_settings_menu(call):
    """Ayarlar menüsü"""
    text = """
    ⚙️ *AYARLAR*

    🔔 *Bildirimler:*
    • Görev bildirimleri
    • Bonus hatırlatmaları
    • Reklam duyuruları
    
    🌐 *Dil:* Türkçe
    
    🔒 *Gizlilik:*
    • Profil görünürlüğü
    • İstatistik paylaşımı
    
    ⚠️ *Hesap Ayarları:*
    • Verilerimi sil
    • Hesabımı kapat
    """
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔔 Bildirimler", callback_data="settings_notifications"),
        types.InlineKeyboardButton("🌐 Dil", callback_data="settings_language"),
        types.InlineKeyboardButton("🔒 Gizlilik", callback_data="settings_privacy"),
        types.InlineKeyboardButton("⚠️ Hesap", callback_data="settings_account"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_support_menu(call):
    """Destek menüsü"""
    text = """
    📞 *DESTEK MERKEZİ*

    🤝 *Yardıma mı ihtiyacın var?*
    
    📋 *Sık Sorulan Sorular:*
    • Para nasıl kazanılır?
    • Görev neden onaylanmıyor?
    • Para nasıl çekilir?
    • Hesabım neden banlandı?
    
    👨‍💼 *İletişim:*
    • Destek: @GorevYapsam
    • Şikayet: @GorevYapsam
    • İşbirliği: @GorevYapsam
    
    ⏰ *Çalışma Saatleri:*
    • Hafta içi: 09:00 - 18:00
    • Hafta sonu: 10:00 - 16:00
    
    ⚠️ *Önemli:*
    • Mesajlar 24 saat içinde yanıtlanır
    • Spam yapmayın
    • Saygılı olun
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 Kanalımız", url=f"https://t.me/{MAIN_CHANNEL[1:]}"),
        types.InlineKeyboardButton("💬 Sohbet Grubu", url=f"https://t.me/{MAIN_CHANNEL[1:]}"),
        types.InlineKeyboardButton("📋 SSS", callback_data="main_help"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def show_help_menu(call):
    """Yardım menüsü"""
    text = """
    ℹ️ *YARDIM MERKEZİ*

    📌 *Hızlı Erişim:*
    
    🎯 *Görevler:* /tasks
    • Kanal görevleri
    • Bot görevleri
    • Forward görevleri
    • Website görevleri
    
    💰 *Finans:* /balance
    • Bakiye görüntüleme
    • Para çekme
    • Günlük bonus
    
    👤 *Profil:* /profile
    • İstatistikler
    • Görev geçmişi
    • Referans sistemi
    
    🏆 *Liderlik:* /leaderboard
    • En çok kazananlar
    • Sıralaman
    • Hedefler
    
    ⚙️ *Ayarlar:* /settings
    • Bildirimler
    • Gizlilik
    • Hesap ayarları
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 Görevler", callback_data="main_tasks"),
        types.InlineKeyboardButton("💰 Finans", callback_data="main_balance"),
        types.InlineKeyboardButton("👤 Profil", callback_data="main_profile"),
        types.InlineKeyboardButton("📞 Destek", callback_data="main_support"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

def handle_admin_action(call):
    """Admin aksiyonlarını işle"""
    action = call.data
    
    if action == "admin_stats":
        stats = db.get_stats()
        
        text = f"""
        📊 *ADMIN İSTATİSTİKLERİ*

        👥 *Kullanıcılar:*
        • Toplam: {stats['total_users']}
        • Aktif (7gün): {stats['active_users']}
        
        💰 *Finansal:*
        • Toplam Bakiye: {format_number(stats['total_balance'])} TL
        • Toplam Kazanç: {format_number(stats['total_earned'])} TL
        
        🎯 *Görevler:*
        • Toplam Tamamlanan: {stats['total_tasks']}
        • Aktif Görev: {stats['active_tasks']}
        
        📈 *Sistem:*
        • Bot: ✅ Çalışıyor
        • Database: SQLite
        • Uptime: 100%
        """
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    elif action == "admin_add_task":
        text = """
        ➕ *GÖREV EKLE*
        
        Format: `/add_task type title description target reward`
        
        Örnek: `/add_task channel "Kanal Adı" "Açıklama" "@kanal" 10`
        
        Türler: channel, bot, forward, website, review
        
        Not: Title ve description tırnak içinde olmalı.
        """
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    bot.answer_callback_query(call.id)

# ================= MESSAGE HANDLERS =================
@bot.message_handler(content_types=['text'])
def handle_text(message):
    """Metin mesajlarını işle"""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    
    # Para çekme komutu
    if message.text.startswith('/withdraw_'):
        try:
            parts = message.text.split('_')
            amount = int(parts[1])
            method = parts[2] if len(parts) > 2 else "bank"
            details = ' '.join(parts[3:]) if len(parts) > 3 else ""
            
            user = db.get_user(user_id)
            if not user:
                bot.reply_to(message, "❌ Lütfen önce /start yazın.")
                return
            
            if amount < 50:
                bot.reply_to(message, "❌ Minimum çekim tutarı 50 TL.")
                return
            
            if amount > user['balance']:
                bot.reply_to(message, f"❌ Yetersiz bakiye! Mevcut: {user['balance']} TL")
                return
            
            # Para çekme talebi oluştur
            withdrawal_id = db.create_withdrawal(user_id, amount, method, details)
            
            # Admin'e bildir
            admin_text = f"""
            📋 *YENİ PARA ÇEKME TALEBİ*
            
            🆔 Talep ID: {withdrawal_id}
            👤 Kullanıcı: @{user['username'] or user['first_name']} ({user_id})
            💰 Tutar: {format_number(amount)} TL
            📋 Yöntem: {method}
            📝 Detay: {details}
            
            ✅ Onayla: /approve_{withdrawal_id}
            ❌ Reddet: /reject_{withdrawal_id}
            """
            
            bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown')
            
            # Kullanıcıya bilgi
            bot.reply_to(
                message,
                f"✅ Para çekme talebin alındı!\n\n"
                f"🆔 Talep ID: {withdrawal_id}\n"
                f"💰 Tutar: {format_number(amount)} TL\n"
                f"📋 Yöntem: {method}\n\n"
                f"⏳ Admin onayı bekleniyor...\n"
                f"İşlem 1-24 saat sürebilir."
            )
            
        except Exception as e:
            bot.reply_to(message, f"❌ Hata: {str(e)}")
    
    # Admin komutları
    elif message.from_user.id == ADMIN_ID:
        # Görev ekle
        if message.text.startswith('/add_task '):
            try:
                parts = message.text[10:].split('" ')
                if len(parts) >= 4:
                    task_type = parts[0]
                    title = parts[1].replace('"', '')
                    description = parts[2].replace('"', '')
                    target_reward = parts[3].split(' ')
                    target = target_reward[0].replace('"', '')
                    reward = int(target_reward[1]) if len(target_reward) > 1 else 10
                    
                    task_id = db.add_task(task_type, title, description, target, reward, created_by=ADMIN_ID)
                    
                    bot.reply_to(
                        message,
                        f"✅ Görev eklendi!\n\n"
                        f"🆔 ID: {task_id}\n"
                        f"📌 Tür: {task_type}\n"
                        f"🏷️ Başlık: {title}\n"
                        f"💰 Ödül: {reward} TL"
                    )
                else:
                    bot.reply_to(message, "❌ Format: /add_task type \"title\" \"description\" \"target\" reward")
            except Exception as e:
                bot.reply_to(message, f"❌ Hata: {str(e)}")
        
        # Bakiye ekle
        elif message.text.startswith('/add_balance '):
            try:
                parts = message.text.split()
                if len(parts) >= 3:
                    target_user = int(parts[1])
                    amount = int(parts[2])
                    
                    db.update_balance(target_user, amount, f"Admin add: {ADMIN_ID}")
                    new_balance = db.get_balance(target_user)
                    
                    bot.reply_to(
                        message,
                        f"✅ Bakiye eklendi!\n\n"
                        f"👤 Kullanıcı: {target_user}\n"
                        f"💰 Eklenen: {amount} TL\n"
                        f"💵 Yeni Bakiye: {new_balance} TL"
                    )
                else:
                    bot.reply_to(message, "❌ Format: /add_balance user_id amount")
            except Exception as e:
                bot.reply_to(message, f"❌ Hata: {str(e)}")
        
        # Para çekme onay/red
        elif message.text.startswith('/approve_') or message.text.startswith('/reject_'):
            try:
                action = 'approved' if message.text.startswith('/approve_') else 'rejected'
                withdrawal_id = int(message.text.split('_')[1])
                
                db.update_withdrawal_status(withdrawal_id, action)
                
                # Kullanıcıya bildir
                withdrawal = db.c.execute('SELECT * FROM withdrawals WHERE withdrawal_id = ?', (withdrawal_id,)).fetchone()
                if withdrawal:
                    user_id = withdrawal[1]
                    amount = withdrawal[2]
                    method = withdrawal[3]
                    
                    status_text = "onaylandı" if action == 'approved' else "reddedildi"
                    
                    try:
                        bot.send_message(
                            user_id,
                            f"📋 *PARA ÇEKME TALEBİ {status_text.upper()}*\n\n"
                            f"🆔 Talep ID: {withdrawal_id}\n"
                            f"💰 Tutar: {format_number(amount)} TL\n"
                            f"📋 Yöntem: {method}\n"
                            f"📊 Durum: {status_text}\n\n"
                            f"{'✅ Paranız en kısa sürede gönderilecektir.' if action == 'approved' else '❌ Lütfen yeni talep oluşturun.'}"
                        )
                    except:
                        pass
                
                bot.reply_to(message, f"✅ Talep {status_text}!")
                
            except Exception as e:
                bot.reply_to(message, f"❌ Hata: {str(e)}")
        
        # Broadcast
        elif message.text.startswith('/broadcast '):
            try:
                broadcast_text = message.text[11:]
                
                # Tüm kullanıcılara gönder
                users = db.c.execute('SELECT user_id FROM users WHERE banned = 0').fetchall()
                sent = 0
                failed = 0
                
                for user in users:
                    try:
                        bot.send_message(user[0], broadcast_text, parse_mode='Markdown')
                        sent += 1
                    except:
                        failed += 1
                    time.sleep(0.05)  # Rate limit
                
                bot.reply_to(
                    message,
                    f"📢 *BROADCAST SONUÇLARI*\n\n"
                    f"✅ Gönderilen: {sent}\n"
                    f"❌ Başarısız: {failed}\n"
                    f"📋 Toplam: {sent + failed}"
                )
                
            except Exception as e:
                bot.reply_to(message, f"❌ Hata: {str(e)}")

# ================= BACKGROUND TASKS =================
def background_tasks():
    """Arka plan görevleri"""
    while True:
        try:
            # Her 5 dakikada bir çalış
            time.sleep(300)
            
            # Süresi dolan reklamları pasif yap
            now = datetime.now()
            db.c.execute('''
                UPDATE ads SET status = 'expired' 
                WHERE expires_at < ? AND status = 'approved'
            ''', (now,))
            
            # Pasif görevleri deaktive et
            db.c.execute('''
                UPDATE tasks SET is_active = 0 
                WHERE created_by IN (
                    SELECT ad_id FROM ads WHERE status = 'expired'
                )
            ''')
            
            db.conn.commit()
            
        except Exception as e:
            print(f"Background task error: {e}")
            time.sleep(60)

# ================= MAIN =================
if __name__ == '__main__':
    print("=" * 60)
    print("🤖 GÖREV BOTU - TAM PAKET")
    print("=" * 60)
    print(f"👤 Admin ID: {ADMIN_ID}")
    print(f"📢 Kanal: {MAIN_CHANNEL}")
    print("💾 Database başlatılıyor...")
    
    # Veritabanını başlat
    db.init_tables()
    
    # Örnek görevler ekle
    try:
        sample_tasks = [
            ('channel', 'Ana Kanalımıza Katıl', 'Resmi kanalımıza katılın ve kalın', MAIN_CHANNEL, 10, 1000),
            ('bot', 'Test Botuna Katıl', 'Test botumuza katılın ve /start yazın', '@BotFather', 5, 500),
            ('forward', 'Mesajı Paylaşın', 'Verdiğimiz mesajı 3 arkadaşınıza gönderin', 'forward', 7, 300),
            ('website', 'Web Sitemizi Ziyaret', 'Web sitemizi 30 saniye gezerek bize destek olun', 'https://t.me/GorevYapsam', 3, 200),
            ('review', 'Google Yorumu', 'Google Maps\'te işletmemize 5 yıldız verin', 'review', 6, 150),
        ]
        
        for task in sample_tasks:
            db.c.execute('''
                INSERT OR IGNORE INTO tasks (task_type, title, description, target, reward, max_completions, created_by)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', task)
        
        db.conn.commit()
        print("✅ Örnek görevler eklendi")
    except:
        print("⚠️ Örnek görevler zaten ekli")
    
    # Arka plan görevini başlat
    threading.Thread(target=background_tasks, daemon=True).start()
    
    print("✅ Bot hazır! Polling başlatılıyor...")
    print("=" * 60)
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Hata: {e}")
        print("🔄 5 saniye sonra yeniden başlatılıyor...")
        time.sleep(5)
