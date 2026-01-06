"""
🤖 GÖREV YAPSAM BOTU v6.0 - TAM OTOMATİK SİSTEM
Telegram: @GorevYapsam
Developer: Alperen
Token: 8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co
"""

import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime
import random
from flask import Flask
import os
import asyncio

# ================= 1. KONFİGÜRASYON =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877
ADMIN_USER = "@AlperenTHE"
ZORUNLU_KANAL = "@GorevYapsam"
BOT_USERNAME = "GorevYapsamBot"

# Bot nesnesi
bot = telebot.TeleBot(TOKEN, parse_mode='HTML', threaded=True)
app = Flask(__name__)

# ================= 2. VERİTABANI =================
def get_db():
    conn = sqlite3.connect('gorev_bot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Kullanıcılar tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            total_earned REAL DEFAULT 0.0,
            tasks_completed INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            ref_earnings REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Görevler tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_type TEXT,
            task_title TEXT,
            task_link TEXT,
            task_description TEXT,
            reward REAL,
            cpm INTEGER,
            status TEXT DEFAULT 'active',
            views INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Görev tamamlamalar tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS task_completions (
            completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            earned REAL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()

init_db()

# ================= 3. TEMEL FONKSİYONLAR =================
def format_balance(num):
    return f"{float(num):,.2f} ₺"

def kanal_kontrol(user_id):
    try:
        member = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def get_user(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def create_user(user_id, username, first_name):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT OR IGNORE INTO users 
                       (user_id, username, first_name, balance) 
                       VALUES (?, ?, ?, 0.0)''', 
                       (user_id, username, first_name))
        conn.commit()

def update_balance(user_id, amount):
    with get_db() as conn:
        cursor = conn.cursor()
        if amount > 0:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           total_earned = total_earned + ?
                           WHERE user_id = ?''', 
                           (amount, amount, user_id))
        else:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?
                           WHERE user_id = ?''', 
                           (amount, user_id))
        conn.commit()

def add_task(user_id, task_type, title, link, description, reward, cpm):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO tasks 
                       (user_id, task_type, task_title, task_link, task_description, reward, cpm)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (user_id, task_type, title, link, description, reward, cpm))
        task_id = cursor.lastrowid
        conn.commit()
        return task_id

def get_active_tasks(task_type=None):
    with get_db() as conn:
        cursor = conn.cursor()
        if task_type:
            cursor.execute('''SELECT * FROM tasks 
                           WHERE status = 'active' AND task_type = ? 
                           ORDER BY created_at DESC LIMIT 10''', (task_type,))
        else:
            cursor.execute('''SELECT * FROM tasks 
                           WHERE status = 'active' 
                           ORDER BY created_at DESC LIMIT 10''')
        return cursor.fetchall()

# ================= 4. ANA MENÜ =================
def show_main_menu(user_id, message_id=None):
    """Ana menüyü göster"""
    user = get_user(user_id)
    
    # Kullanıcı yoksa oluştur
    if not user:
        create_user(user_id, "", "")
        user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Ana butonlar
    markup.add(
        types.InlineKeyboardButton("📢 GÖREV YAP", callback_data="do_tasks"),
        types.InlineKeyboardButton("💰 BAKİYE: " + format_balance(user['balance']), callback_data="balance_info")
    )
    
    # İkinci satır
    markup.add(
        types.InlineKeyboardButton("📊 GÖREV OLUŞTUR", callback_data="create_task"),
        types.InlineKeyboardButton("👥 REFERANS", callback_data="referral_info")
    )
    
    # Üçüncü satır
    markup.add(
        types.InlineKeyboardButton("📈 İSTATİSTİKLER", callback_data="stats_info"),
        types.InlineKeyboardButton("ℹ️ YARDIM", callback_data="help_info")
    )
    
    # Admin paneli
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel"))
    
    text = f"""<b>🏠 GÖREV YAPSAM BOTU</b>

👤 <b>Merhaba</b> {user['first_name']}!

💼 <b>Durumun:</b>
💰 Bakiye: <b>{format_balance(user['balance'])}</b>
🎯 Görevler: <b>{user['tasks_completed']}</b>
👥 Referans: <b>{user['referrals']}</b>

🚀 <b>Hemen görev yaparak para kazanmaya başla!</b>

👇 <i>Aşağıdaki butonlardan birini seç:</i>"""
    
    if message_id:
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 5. START KOMUTU =================
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"),
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        bot.send_message(
            user_id,
            f"""<b>👋 Merhaba {first_name}!</b>

Botu kullanmak için kanalımıza katılmalısın:

📢 <b>{ZORUNLU_KANAL}</b>

<i>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</i>""",
            reply_markup=markup
        )
        return
    
    # Kullanıcı oluştur ve hoşgeldin bonusu
    create_user(user_id, message.from_user.username, first_name)
    
    # İlk kez geliyorsa bonus ver
    user = get_user(user_id)
    if user['tasks_completed'] == 0:
        update_balance(user_id, 2.0)
        bot.send_message(
            user_id,
            f"""<b>🎉 HOŞ GELDİN {first_name}!</b>

✅ <b>Kaydın başarıyla oluşturuldu!</b>
💰 <b>Hoşgeldin bonusu:</b> 2.00 ₺ hesabına yüklendi.

<i>Hemen aşağıdaki menüden görev yapmaya başlayabilirsin!</i>"""
        )
    
    # Ana menüyü göster
    show_main_menu(user_id)

# ================= 6. CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id) and call.data != "check_join":
        bot.answer_callback_query(call.id, "❌ Önce kanala katılmalısın!", show_alert=True)
        return
    
    # Ana menü butonları
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Başarılı! Ana menüye yönlendiriliyorsun...")
        else:
            bot.answer_callback_query(call.id, "❌ Hala kanalda değilsin!", show_alert=True)
    
    elif call.data == "do_tasks":
        show_task_types(user_id, call.message.message_id)
    
    elif call.data == "balance_info":
        show_balance_info(user_id, call.message.message_id)
    
    elif call.data == "create_task":
        create_task_menu(user_id, call.message.message_id)
    
    elif call.data == "referral_info":
        show_referral_info(user_id, call.message.message_id)
    
    elif call.data == "stats_info":
        show_stats_info(user_id, call.message.message_id)
    
    elif call.data == "help_info":
        show_help_info(user_id, call.message.message_id)
    
    elif call.data == "admin_panel":
        if user_id == ADMIN_ID:
            show_admin_panel(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Yetkin yok!", show_alert=True)
    
    elif call.data == "back_to_menu":
        show_main_menu(user_id, call.message.message_id)
    
    # Görev tipi seçimi
    elif call.data in ["task_type_anal", "task_type_group", "task_type_bot"]:
        task_type = call.data.replace("task_type_", "")
        show_available_tasks(user_id, task_type, call.message.message_id)
    
    # Görev oluşturma
    elif call.data.startswith("create_"):
        task_type = call.data.replace("create_", "")
        ask_task_details(user_id, task_type, call.message.message_id)
    
    # Görev tamamlama
    elif call.data.startswith("complete_task_"):
        task_id = int(call.data.replace("complete_task_", ""))
        complete_task(user_id, task_id, call)

# ================= 7. GÖREV SİSTEMİ =================
def show_task_types(user_id, message_id):
    """Görev tiplerini göster"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 ANAL GÖREV (1.00 ₺)", callback_data="task_type_anal"),
        types.InlineKeyboardButton("👥 GRUP GÖREV (2.50 ₺)", callback_data="task_type_group"),
        types.InlineKeyboardButton("🤖 BOT GÖREV (1.50 ₺)", callback_data="task_type_bot")
    )
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu"))
    
    text = """<b>🎯 GÖREV TİPLERİ</b>

Hangi tür görev yapmak istiyorsun?

<b>📢 ANAL GÖREV</b>
• Ödül: <b>1.00 ₺</b>
• Kanal/analize katıl
• 5 dakika bekle

<b>👥 GRUP GÖREV</b>
• Ödül: <b>2.50 ₺</b>
• Gruba katıl
• 5 dakika bekle

<b>🤖 BOT GÖREV</b>
• Ödül: <b>1.50 ₺</b>
• Bota start at
• 3 dakika bekle

👇 <i>Bir görev tipi seç:</i>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def show_available_tasks(user_id, task_type, message_id):
    """Mevcut görevleri göster"""
    tasks = get_active_tasks(task_type)
    
    if not tasks:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 Yenile", callback_data=f"task_type_{task_type}"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
        )
        
        type_names = {
            "anal": "📢 Anal Görev",
            "group": "👥 Grup Görev", 
            "bot": "🤖 Bot Görev"
        }
        
        bot.edit_message_text(
            f"""<b>{type_names.get(task_type, 'Görev')}</b>

❌ <b>Şu anda aktif görev bulunmuyor.</b>

<i>Bir süre sonra tekrar kontrol et veya kendi görevini oluştur!</i>""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    # İlk görevi göster
    task = tasks[0]
    show_single_task(user_id, task, message_id)

def show_single_task(user_id, task, message_id):
    """Tek bir görevi detaylı göster"""
    reward_map = {
        "anal": 1.00,
        "group": 2.50,
        "bot": 1.50
    }
    
    task_type_names = {
        "anal": "📢 ANAL GÖREV",
        "group": "👥 GRUP GÖREV",
        "bot": "🤖 BOT GÖREV"
    }
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 GÖREVE GİT", url=task['task_link']),
        types.InlineKeyboardButton("✅ TAMAMLADIM", callback_data=f"complete_task_{task['task_id']}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 YENİ GÖREV", callback_data=f"task_type_{task['task_type']}"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
    )
    
    text = f"""<b>{task_type_names.get(task['task_type'], 'GÖREV')}</b>

📌 <b>Başlık:</b> {task['task_title']}
📝 <b>Açıklama:</b> {task['task_description']}

💰 <b>Ödül:</b> {format_balance(reward_map.get(task['task_type'], 1.00))}
👁️ <b>Görüntülenme:</b> {task['views']}
📊 <b>CPM:</b> {task['cpm']}

⚠️ <b>Talimatlar:</b>
1. "GÖREVE GİT" butonuna tıkla
2. Görevi tamamla (katıl/start at)
3. 5 dakika bekle
4. "TAMAMLADIM" butonuna bas

⏱️ <i>Tamamlamak için 5 dakikan var!</i>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def complete_task(user_id, task_id, call):
    """Görevi tamamla"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Görevi al
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            bot.answer_callback_query(call.id, "❌ Görev bulunamadı!", show_alert=True)
            return
        
        # Görev tipine göre ödül
        reward_map = {
            "anal": 1.00,
            "group": 2.50,
            "bot": 1.50
        }
        
        reward = reward_map.get(task['task_type'], 1.00)
        
        # Kullanıcı bakiyesini güncelle
        update_balance(user_id, reward)
        
        # Görev tamamlanma sayısını artır
        cursor.execute('''UPDATE users SET 
                       tasks_completed = tasks_completed + 1
                       WHERE user_id = ?''', (user_id,))
        
        # Görev görüntülenmesini artır
        cursor.execute('''UPDATE tasks SET 
                       views = views + 1,
                       cost = cost + ?
                       WHERE task_id = ?''', (reward, task_id))
        
        # Tamamlama kaydı ekle
        cursor.execute('''INSERT INTO task_completions 
                       (task_id, user_id, earned)
                       VALUES (?, ?, ?)''', 
                       (task_id, user_id, reward))
        
        conn.commit()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 YENİ GÖREV", callback_data="do_tasks"),
        types.InlineKeyboardButton("💰 BAKİYE", callback_data="balance_info")
    )
    
    bot.edit_message_text(
        f"""<b>✅ GÖREV TAMAMLANDI!</b>

🎉 <b>Tebrikler! Görevi başarıyla tamamladın.</b>

💰 <b>Kazanç:</b> +{format_balance(reward)}
💰 <b>Yeni Bakiye:</b> {format_balance(user['balance'])}
🎯 <b>Toplam Görev:</b> {user['tasks_completed']}

🚀 <i>Hemen yeni görev yapmaya devam et!</i>""",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, f"✅ +{format_balance(reward)} kazandın!")

# ================= 8. GÖREV OLUŞTURMA =================
def create_task_menu(user_id, message_id):
    """Görev oluşturma menüsü"""
    user = get_user(user_id)
    
    if user['balance'] < 5.00:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 GÖREV YAP", callback_data="do_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
        )
        
        bot.edit_message_text(
            f"""<b>❌ YETERSİZ BAKİYE!</b>

Görev oluşturmak için minimum <b>5.00 ₺</b> bakiyen olmalı.

💰 <b>Mevcut Bakiyen:</b> {format_balance(user['balance'])}
💡 <b>İpucu:</b> Önce görev yaparak bakiye kazan!

<i>Her görev için CPM bazlı ücretlendirme:</i>
• Anal Görev: 1.00 ₺ / görüntülenme
• Grup Görev: 2.50 ₺ / görüntülenme  
• Bot Görev: 1.50 ₺ / görüntülenme""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 ANAL GÖREV OLUŞTUR (1.00 ₺/görüntü)", callback_data="create_anal"),
        types.InlineKeyboardButton("👥 GRUP GÖREV OLUŞTUR (2.50 ₺/görüntü)", callback_data="create_group"),
        types.InlineKeyboardButton("🤖 BOT GÖREV OLUŞTUR (1.50 ₺/görüntü)", callback_data="create_bot")
    )
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu"))
    
    text = """<b>📊 GÖREV OLUŞTURMA</b>

Hangi türde görev oluşturmak istiyorsun?

<b>📢 ANAL GÖREV</b>
• Maliyet: <b>1.00 ₺ / görüntülenme</b>
• Kullanıcılar kanalına/analine katılır
• Minimum bakiye: 5.00 ₺

<b>👥 GRUP GÖREV</b>  
• Maliyet: <b>2.50 ₺ / görüntülenme</b>
• Kullanıcılar grubuna katılır
• Minimum bakiye: 12.50 ₺

<b>🤖 BOT GÖREV</b>
• Maliyet: <b>1.50 ₺ / görüntülenme</b>
• Kullanıcılar botuna start atar
• Minimum bakiye: 7.50 ₺

👇 <i>Bir görev tipi seç:</i>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def ask_task_details(user_id, task_type, message_id):
    """Görev detaylarını sor"""
    cpm_map = {
        "anal": 1.00,
        "group": 2.50,
        "bot": 1.50
    }
    
    type_names = {
        "anal": "Anal Görev",
        "group": "Grup Görev",
        "bot": "Bot Görev"
    }
    
    bot.edit_message_text(
        f"""<b>📝 {type_names.get(task_type, 'Görev')} Detayları</b>

Lütfen görev bilgilerini aşağıdaki formatta gönder:

<code>Başlık
Link
Açıklama</code>

<b>Örnek:</b>
<code>Teknoloji Haberleri
https://t.me/teknoloji
En güncel teknoloji haberleri için katılın!</code>

💰 <b>Görüntülenme başına maliyet:</b> {format_balance(cpm_map[task_type])}
⚠️ <b>Not:</b> Gönderdiğin mesajı forward ederek görev oluşturulacak.

👇 <i>Görev bilgilerini gönder:</i>""",
        user_id,
        message_id
    )
    
    # Mesaj beklemeye başla
    bot.register_next_step_handler_by_chat_id(
        user_id, 
        process_task_details, 
        task_type, 
        message_id
    )

def process_task_details(message, task_type, original_message_id):
    """Görev detaylarını işle"""
    user_id = message.from_user.id
    text = message.text.strip().split('\n')
    
    if len(text) < 3:
        bot.send_message(user_id, "❌ Lütfen başlık, link ve açıklama olacak şekilde 3 satır gönder!")
        show_main_menu(user_id)
        return
    
    title = text[0].strip()
    link = text[1].strip()
    description = text[2].strip()
    
    # CPM değerleri
    cpm_map = {
        "anal": 1.00,
        "group": 2.50,
        "bot": 1.50
    }
    
    cpm = cpm_map[task_type]
    
    # Bakiye kontrolü
    user = get_user(user_id)
    if user['balance'] < cpm:
        bot.send_message(
            user_id,
            f"❌ Yetersiz bakiye! Görev oluşturmak için minimum {format_balance(cpm)} gerekiyor."
        )
        show_main_menu(user_id)
        return
    
    # Görev oluştur
    task_id = add_task(user_id, task_type, title, link, description, cpm, 1000)
    
    # Forward mesajı
    try:
        forwarded_msg = bot.forward_message(
            user_id,
            message.chat.id,
            message.message_id
        )
        
        # Görev başarıyla oluşturuldu mesajı
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 GÖREVLERİ GÖR", callback_data="do_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
        )
        
        bot.send_message(
            user_id,
            f"""<b>✅ GÖREV OLUŞTURULDU!</b>

📌 <b>Başlık:</b> {title}
🔗 <b>Link:</b> {link}
📝 <b>Açıklama:</b> {description}

💰 <b>Görüntülenme başına:</b> {format_balance(cpm)}
📊 <b>CPM:</b> 1000
🆔 <b>Görev ID:</b> {task_id}

✅ <b>Görevin aktif!</b> Kullanıcılar şimdi görevini görebilir ve tamamlayabilir.

⚠️ <i>Not: Her tamamlanma için bakiyenden {format_balance(cpm)} düşülecek.</i>""",
            reply_markup=markup
        )
        
    except Exception as e:
        bot.send_message(user_id, f"❌ Hata: {str(e)}")
        show_main_menu(user_id)

# ================= 9. BAKİYE BİLGİSİ =================
def show_balance_info(user_id, message_id):
    """Bakiye bilgilerini göster"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 GÖREV YAP", callback_data="do_tasks"),
        types.InlineKeyboardButton("📊 GÖREV OLUŞTUR", callback_data="create_task")
    )
    markup.add(
        types.InlineKeyboardButton("👥 REFERANS", callback_data="referral_info"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
    )
    
    text = f"""<b>💰 BAKİYE DETAYLARI</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
🆔 <b>ID:</b> <code>{user_id}</code>

💵 <b>Cari Bakiye:</b> <b>{format_balance(user['balance'])}</b>
📈 <b>Toplam Kazanç:</b> {format_balance(user['total_earned'])}
🎯 <b>Görevler:</b> {user['tasks_completed']}
👥 <b>Referans:</b> {user['referrals']}

💸 <b>Para Çekim:</b>
• Minimum: 20.00 ₺
• Otomatik ödeme: EVET
• Süre: 24 saat

👇 <i>Hemen görev yaparak kazanmaya başla!</i>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 10. REFERANS SİSTEMİ =================
def show_referral_info(user_id, message_id):
    """Referans sistemini göster"""
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 LİNKİ PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Günlük%202₺%20bonus%20ve%20referans%20başına%201₺%20kazan!%20@GorevYapsamBot"),
        types.InlineKeyboardButton("📋 LİNKİ KOPYALA", 
            callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu"))
    
    text = f"""<b>👥 REFERANS SİSTEMİ</b>

💰 <b>Her referans başına:</b> 1.00 ₺
👤 <b>Toplam referans:</b> {user['referrals']} kişi
📈 <b>Referans kazancı:</b> {format_balance(user.get('ref_earnings', 0))}

🔗 <b>Referans linkin:</b>
<code>{ref_link}</code>

📝 <b>Nasıl çalışır?</b>
1. Linkini arkadaşlarına paylaş
2. Arkadaşların linke tıklasın
3. Onlar /start yaptığında otomatik +1.00 ₺
4. Onlar da görev yaparak kazansın!

🔥 <b>Bonus:</b> Her 10 referansta +5 ₺ bonus!"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 11. İSTATİSTİKLER =================
def show_stats_info(user_id, message_id):
    """İstatistikleri göster"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT 
                       COUNT(*) as total_users,
                       SUM(balance) as total_balance,
                       SUM(total_earned) as total_earned,
                       SUM(tasks_completed) as total_tasks
                       FROM users''')
        stats = cursor.fetchone()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Yenile", callback_data="stats_info"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu")
    )
    
    text = f"""<b>📊 İSTATİSTİKLER</b>

👤 <b>Kişisel:</b>
• Bakiye: {format_balance(user['balance'])}
• Toplam Kazanç: {format_balance(user['total_earned'])}
• Görevler: {user['tasks_completed']}
• Referanslar: {user['referrals']}
• Seri: {user['daily_streak']} gün

🌍 <b>Global:</b>
• Toplam Kullanıcı: {stats['total_users']}
• Toplam Bakiye: {format_balance(stats['total_balance'] or 0)}
• Toplam Kazanç: {format_balance(stats['total_earned'] or 0)}
• Toplam Görev: {stats['total_tasks'] or 0}

🔥 <b>En çok kazanan sen ol!</b>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 12. YARDIM =================
def show_help_info(user_id, message_id):
    """Yardım menüsü"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 KANAL", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"),
        types.InlineKeyboardButton("👤 YÖNETİCİ", url=f"https://t.me/{ADMIN_USER.replace('@', '')}")
    )
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu"))
    
    text = """<b>ℹ️ YARDIM MERKEZİ</b>

🎯 <b>GÖREV SİSTEMİ:</b>
• 📢 Anal Görev: 1.00 ₺
• 👥 Grup Görev: 2.50 ₺  
• 🤖 Bot Görev: 1.50 ₺

💰 <b>KAZANÇ YOLLARI:</b>
1. Görev yap (1.00-2.50 ₺)
2. Günlük bonus al (2.00 ₺)
3. Referans kazan (1.00 ₺/kişi)

📊 <b>GÖREV OLUŞTURMA:</b>
• Anal: 1.00 ₺/görüntü
• Grup: 2.50 ₺/görüntü
• Bot: 1.50 ₺/görüntü
• Bakiye bitince otomatik durur

⚠️ <b>KURALLAR:</b>
• @GorevYapsam kanalı zorunlu
• Sahte işlem yasak
• Çoklu hesap yasak
• Grup/kanal görevleri için bot yönetici olmalı

📞 <b>DESTEK:</b> @AlperenTHE"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 13. ADMIN PANEL =================
def show_admin_panel(user_id, message_id):
    """Admin panel"""
    if user_id != ADMIN_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİKLER", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 KULLANICI YÖNET", callback_data="admin_users")
    )
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE EKLE", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 DUYURU", callback_data="admin_broadcast")
    )
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_to_menu"))
    
    bot.edit_message_text(
        """<b>👑 ADMIN PANEL</b>

Hoş geldin Yönetici!

👇 Yapmak istediğin işlemi seç:""",
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 14. FLASK SERVER =================
@app.route('/')
def home():
    return "🤖 Görev Yapsam Bot Aktif!"

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

# ================= 15. BOT ÇALIŞTIRMA =================
def run_bot():
    print("🤖 Bot başlatılıyor...")
    try:
        bot.remove_webhook()
        time.sleep(1)
        
        bot.polling(
            none_stop=True,
            interval=3,
            timeout=60,
            skip_pending=True
        )
    except Exception as e:
        print(f"Bot hatası: {e}")
        time.sleep(10)
        run_bot()

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Flask thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Ana thread'de botu çalıştır
    run_bot()
