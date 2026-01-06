"""
🤖 GÖREV BOTU - RENDER UYUMLU SÜRÜM
Telegram: @GorevYapsam
"""

import telebot
from telebot import types
import sqlite3
import time
import threading
import os
from datetime import datetime, timedelta
from flask import Flask, request

# ================= CONFIG =================
# Tokenı Render Environment Variables'dan almak daha güvenlidir ama buraya da yazabilirsin.
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877 
MAIN_CHANNEL = "@GorevYapsam"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= WEB SERVER (RENDER İÇİN) =================
# Bu kısım Render'ın "Port Bulunamadı" hatasını çözer.
@app.route('/')
def home():
    return "🤖 Bot Aktif ve Çalışıyor! (Render Web Service)", 200

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    # Render PORT environment variable'ını otomatik atar
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

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
                balance REAL DEFAULT 0.0,
                total_earned REAL DEFAULT 0.0,
                tasks_completed INTEGER DEFAULT 0,
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
                reward REAL,
                max_completions INTEGER DEFAULT 100,
                current_completions INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Completed tasks
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_id INTEGER,
                earned REAL,
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
                reward REAL,
                cost REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')
        
        # Daily bonus
        self.c.execute('''
            CREATE TABLE IF NOT EXISTS daily_bonus (
                user_id INTEGER PRIMARY KEY,
                last_claim TIMESTAMP,
                streak INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    # --- USER METHODS ---
    def add_user(self, user_id, username, first_name):
        self.c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)', 
                      (user_id, username, first_name))
        self.conn.commit()
    
    def get_user(self, user_id):
        self.c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.c.fetchone()
        if row:
            # Sütun isimlerini dict olarak döndür
            columns = [desc[0] for desc in self.c.description]
            return dict(zip(columns, row))
        return None
    
    def update_balance(self, user_id, amount):
        self.c.execute('''
            UPDATE users SET 
            balance = balance + ?,
            total_earned = total_earned + (CASE WHEN ? > 0 THEN ? ELSE 0 END),
            last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (amount, amount, amount, user_id))
        self.conn.commit()
        
    def get_balance(self, user_id):
        self.c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        res = self.c.fetchone()
        return res[0] if res else 0.0

    # --- TASK METHODS ---
    def add_task(self, task_type, title, description, target, reward, max_completions=100):
        self.c.execute('''
            INSERT INTO tasks (task_type, title, description, target, reward, max_completions)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_type, title, description, target, reward, max_completions))
        self.conn.commit()
        return self.c.lastrowid
        
    def get_random_task(self, task_type, user_id):
        # Henüz yapılmamış, aktif ve kotası dolmamış görev
        self.c.execute('''
            SELECT * FROM tasks 
            WHERE task_type = ? 
            AND is_active = 1 
            AND current_completions < max_completions
            AND task_id NOT IN (SELECT task_id FROM completed_tasks WHERE user_id = ?)
            ORDER BY RANDOM() LIMIT 1
        ''', (task_type, user_id))
        
        row = self.c.fetchone()
        if row:
            columns = [desc[0] for desc in self.c.description]
            return dict(zip(columns, row))
        return None

    def complete_task(self, user_id, task_id):
        # Görev kontrolü
        self.c.execute('SELECT reward, current_completions, max_completions FROM tasks WHERE task_id = ?', (task_id,))
        task = self.c.fetchone()
        
        if not task: return 0
        reward, current, max_c = task
        
        if current >= max_c: return 0
        
        # Zaten yapılmış mı?
        self.c.execute('SELECT 1 FROM completed_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
        if self.c.fetchone(): return 0
        
        # İşle
        self.c.execute('INSERT INTO completed_tasks (user_id, task_id, earned) VALUES (?, ?, ?)', (user_id, task_id, reward))
        self.c.execute('UPDATE tasks SET current_completions = current_completions + 1 WHERE task_id = ?', (task_id,))
        self.update_balance(user_id, reward)
        self.c.execute('UPDATE users SET tasks_completed = tasks_completed + 1 WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return reward

    # --- DAILY BONUS ---
    def check_daily(self, user_id):
        self.c.execute('SELECT last_claim, streak FROM daily_bonus WHERE user_id = ?', (user_id,))
        row = self.c.fetchone()
        
        if not row: return True, 1
        
        last_date = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        if last_date.date() == datetime.now().date():
            return False, row[1]
            
        streak = row[1] + 1 if (datetime.now().date() - last_date.date()).days == 1 else 1
        return True, streak

    def claim_daily(self, user_id, streak):
        bonus = min(streak * 0.5, 5.0) # Her gün 0.5 TL artar, max 5 TL
        self.c.execute('INSERT OR REPLACE INTO daily_bonus (user_id, last_claim, streak) VALUES (?, CURRENT_TIMESTAMP, ?)', (user_id, streak))
        self.update_balance(user_id, bonus)
        self.conn.commit()
        return bonus

    def get_user_tasks_history(self, user_id):
        self.c.execute('''
            SELECT t.title, ct.earned, ct.completed_at 
            FROM completed_tasks ct
            JOIN tasks t ON ct.task_id = t.task_id
            WHERE ct.user_id = ?
            ORDER BY ct.completed_at DESC LIMIT 10
        ''', (user_id,))
        return self.c.fetchall()

db = Database()

# ================= HELPERS =================
def format_money(amount):
    return f"{amount:.2f}₺"

def check_channel_membership(user_id):
    try:
        chat_member = bot.get_chat_member(MAIN_CHANNEL, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return False # Bot kanalda admin değilse veya hata varsa

# ================= MENUS =================
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görevler", callback_data="menu_tasks"),
        types.InlineKeyboardButton("💰 Bakiye & Profil", callback_data="menu_profile"),
        types.InlineKeyboardButton("📢 Reklam Ver", callback_data="menu_ads"),
        types.InlineKeyboardButton("🏆 Liderler", callback_data="menu_leaderboard"),
        types.InlineKeyboardButton("🎁 Günlük Bonus", callback_data="action_daily"),
        types.InlineKeyboardButton("ℹ️ Yardım", callback_data="menu_help")
    )
    return markup

def task_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Telegram Kanal (2₺)", callback_data="task_channel"),
        types.InlineKeyboardButton("👥 Telegram Grup (1.5₺)", callback_data="task_group"),
        types.InlineKeyboardButton("🤖 Telegram Bot (1₺)", callback_data="task_bot"),
        types.InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")
    )
    return markup

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    if not check_channel_membership(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 Kanala Katıl", url=f"https://t.me/{MAIN_CHANNEL.replace('@','')}"),
            types.InlineKeyboardButton("✅ Katıldım", callback_data="check_join")
        )
        bot.send_message(message.chat.id, f"👋 Merhaba! Botu kullanmak için {MAIN_CHANNEL} kanalına katılmalısın.", reply_markup=markup)
        return

    text = f"""
    👋 *Hoş Geldin {message.from_user.first_name}!*
    
    🤖 Bu bot ile basit görevler yaparak bakiye kazanabilirsin.
    
    💰 *Fiyatlandırma:*
    📢 Kanal Katılımı: **2.00 ₺**
    👥 Gruba Katılım: **1.50 ₺**
    🤖 Bot Başlatma: **1.00 ₺**
    
    👇 Menüden seçim yap:
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if check_channel_membership(user_id):
            bot.answer_callback_query(call.id, "✅ Teşekkürler!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Henüz katılmamışsın!", show_alert=True)
            
    elif call.data == "main_menu":
        bot.edit_message_text("🏠 *Ana Menü*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu())
        
    elif call.data == "menu_tasks":
        bot.edit_message_text("🎯 *Görev Türünü Seç:*", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=task_menu())
        
    elif call.data.startswith("task_"):
        # task_channel, task_group, task_bot
        t_type = call.data.split("_")[1]
        task = db.get_random_task(t_type, user_id)
        
        if not task:
            bot.answer_callback_query(call.id, "❌ Bu kategoride şuan aktif görev yok.", show_alert=True)
            return
            
        markup = types.InlineKeyboardMarkup()
        btn_text = "🔗 Kanala Git" if t_type == "channel" else ("🔗 Gruba Git" if t_type == "group" else "🔗 Botu Başlat")
        
        # Link düzeltme (https yoksa ekle)
        target = task['target']
        if not target.startswith('http'):
            target = f"https://t.me/{target.replace('@','')}"
            
        markup.add(types.InlineKeyboardButton(btn_text, url=target))
        markup.add(types.InlineKeyboardButton("✅ Yaptım, Parayı Ver", callback_data=f"do_{task['task_id']}"))
        markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="menu_tasks"))
        
        txt = f"""
        📝 *GÖREV:* {task['title']}
        
        ℹ️ *Açıklama:* {task['description']}
        
        💰 *Ödül:* {format_money(task['reward'])}
        """
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("do_"):
        task_id = int(call.data.split("_")[1])
        # Gerçek kontrol için Telegram API user check yapılabilir ama şimdilik güvene dayalı/basit onay.
        reward = db.complete_task(user_id, task_id)
        
        if reward > 0:
            bot.answer_callback_query(call.id, f"✅ Tebrikler! {format_money(reward)} kazandın!", show_alert=True)
            user = db.get_user(user_id)
            txt = f"💰 *Yeni Bakiyen:* {format_money(user['balance'])}"
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Hata: Görev zaten yapılmış veya geçersiz.", show_alert=True)
            
    elif call.data == "menu_profile":
        user = db.get_user(user_id)
        history = db.get_user_tasks_history(user_id)
        
        hist_txt = "\n".join([f"• {h[0]}: +{format_money(h[1])}" for h in history]) if history else "Henüz görev yok."
        
        txt = f"""
        👤 *PROFİLİN*
        
        🆔 ID: `{user_id}`
        👤 İsim: {user['first_name']}
        
        💰 *Bakiye:* {format_money(user['balance'])}
        📈 *Toplam Kazanç:* {format_money(user['total_earned'])}
        ✅ *Tamamlanan Görev:* {user['tasks_completed']}
        
        📜 *Son İşlemler:*
        {hist_txt}
        """
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu"))
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "action_daily":
        can_claim, info = db.check_daily(user_id)
        if can_claim:
            bonus = db.claim_daily(user_id, info)
            bot.answer_callback_query(call.id, f"🎁 {format_money(bonus)} Günlük Bonus Alındı!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"⏳ Günlük bonusu zaten aldın! Seri: {info} Gün", show_alert=True)

# ================= ADMIN COMMANDS =================
@bot.message_handler(commands=['addtask'])
def admin_add_task(message):
    if message.from_user.id != ADMIN_ID: return
    # Format: /addtask channel @kanaladresi Başlık Açıklama
    try:
        parts = message.text.split(maxsplit=4)
        t_type = parts[1] # channel, group, bot
        target = parts[2]
        title = parts[3]
        desc = parts[4]
        
        # Fiyatlandırma
        if t_type == "channel": reward = 2.0
        elif t_type == "group": reward = 1.5
        elif t_type == "bot": reward = 1.0
        else: reward = 0.5
        
        db.add_task(t_type, title, desc, target, reward)
        bot.reply_to(message, f"✅ Görev eklendi! Ödül: {reward}₺")
    except:
        bot.reply_to(message, "Hata! Kullanım: /addtask [channel/group/bot] [link] [Başlık] [Açıklama]")

# ================= BAŞLANGIÇ GÖREVLERİ (DEMO) =================
def init_demo_tasks():
    # Sistem ilk açıldığında veritabanı boşsa örnek görevler ekler
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT count(*) FROM tasks')
    if c.fetchone()[0] == 0:
        print("Demo görevler yükleniyor...")
        db.add_task('channel', 'Sponsor Kanalı Takip Et', 'Ana haber kanalımızı takip et', '@haberler', 2.0)
        db.add_task('group', 'Sohbet Grubuna Katıl', 'Sohbet grubumuza gel ve selam ver', 'https://t.me/sohbet', 1.5)
        db.add_task('bot', 'Yardımcı Botu Başlat', '/start diyerek botu başlat', '@BotFather', 1.0)
        db.add_task('channel', 'Yedek Kanal', 'Yedek kanalımız', '@yedek', 2.0)
    conn.close()

if __name__ == '__main__':
    # 1. Veritabanını hazırla
    db.init_tables()
    init_demo_tasks()
    
    # 2. Flask Sunucusunu Arka Planda Başlat (Thread)
    print("🌍 Web sunucusu başlatılıyor...")
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    # 3. Botu Başlat
    print("🚀 Bot başlatılıyor...")
    while True:
        try:
            # 409 Conflict hatasını önlemek için infinity_polling kullanıyoruz
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Bot hatası: {e}")
            time.sleep(5)
