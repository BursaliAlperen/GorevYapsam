"""
🤖 GÖREV YAPSAM BOTU v11.0 - SADE & ETKİLİ
Telegram: @GorevYapsam
Developer: Alperen
Token: 8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co
"""

import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import random
from flask import Flask
import os
import json

# ================= 1. KONFİGÜRASYON =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877
ADMIN_USER = "@AlperenTHE"
ZORUNLU_KANAL = "GY_Refim"  # Güncellenmiş kanal

# FİYATLAR
PRICES = {
    "bot": 2.50,    # 🤖 BOT GÖREV
    "kanal": 1.50,  # 📢 KANAL GÖREV  
    "grup": 1.00    # 👥 GRUP GÖREV
}

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
            ref_earned REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            channel_joined INTEGER DEFAULT 0
        )''')
        
        # Görevler tablosu
        cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_type TEXT,
            title TEXT,
            link TEXT,
            description TEXT,
            cost_per_view REAL,
            views INTEGER DEFAULT 0,
            cost_spent REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Görev tamamlamalar
        cursor.execute('''CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            earned REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Referanslar
        cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER,
            earned REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()

init_db()

# ================= 3. TEMEL FONKSİYONLAR =================
def format_money(num):
    """Para formatı"""
    return f"{float(num):,.2f} ₺"

def kanal_kontrol(user_id):
    """Kanal üyeliği kontrolü"""
    try:
        member = bot.get_chat_member("@" + ZORUNLU_KANAL, user_id)
        is_member = member.status in ['member', 'administrator', 'creator']
        
        # Veritabanına kaydet
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''UPDATE users SET 
                           channel_joined = ?
                           WHERE user_id = ?''', 
                           (1 if is_member else 0, user_id))
            conn.commit()
        
        return is_member
    except:
        return False

def get_user(user_id):
    """Kullanıcı bilgisi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def create_user(user_id, username, first_name):
    """Yeni kullanıcı oluştur"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT OR IGNORE INTO users 
                       (user_id, username, first_name, balance) 
                       VALUES (?, ?, ?, 0.0)''', 
                       (user_id, username, first_name))
        conn.commit()

def update_balance(user_id, amount):
    """Bakiye güncelle"""
    with get_db() as conn:
        cursor = conn.cursor()
        if amount > 0:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           total_earned = total_earned + ?,
                           last_active = CURRENT_TIMESTAMP
                           WHERE user_id = ?''', 
                           (amount, amount, user_id))
        else:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           last_active = CURRENT_TIMESTAMP
                           WHERE user_id = ?''', 
                           (amount, user_id))
        conn.commit()

def update_user_activity(user_id):
    """Aktiflik güncelle"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET 
                       last_active = CURRENT_TIMESTAMP
                       WHERE user_id = ?''', (user_id,))
        conn.commit()

def add_ref(referrer_id, referred_id):
    """Referans ekle"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Kontrol et
        cursor.execute('''SELECT * FROM referrals 
                       WHERE referrer_id = ? AND referred_id = ?''',
                       (referrer_id, referred_id))
        
        if cursor.fetchone():
            return False
        
        # Referans kaydı oluştur
        cursor.execute('''INSERT INTO referrals 
                       (referrer_id, referred_id, earned)
                       VALUES (?, ?, ?)''', (referrer_id, referred_id, 1.0))
        
        # Referrer'a bonus ver
        cursor.execute('''UPDATE users SET 
                       referrals = referrals + 1,
                       ref_earned = ref_earned + 1.0,
                       balance = balance + 1.0,
                       last_active = CURRENT_TIMESTAMP
                       WHERE user_id = ?''', (referrer_id,))
        
        conn.commit()
        return True

def get_active_tasks(task_type=None, limit=10):
    """Aktif görevleri getir"""
    with get_db() as conn:
        cursor = conn.cursor()
        if task_type:
            cursor.execute('''SELECT * FROM tasks 
                           WHERE status = 'active' AND task_type = ?
                           ORDER BY created_at DESC LIMIT ?''', (task_type, limit))
        else:
            cursor.execute('''SELECT * FROM tasks 
                           WHERE status = 'active'
                           ORDER BY created_at DESC LIMIT ?''', (limit,))
        return cursor.fetchall()

# ================= 4. ANA MENÜ =================
def show_main_menu(user_id, message_id=None):
    """Ana menü"""
    user = get_user(user_id)
    update_user_activity(user_id)
    
    if not user:
        create_user(user_id, "", "")
        user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Ana butonlar
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("💰 " + format_money(user['balance']), callback_data="my_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_task"),
        types.InlineKeyboardButton("👥 REFERANS", callback_data="my_refs")
    )
    
    # Admin butonu
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel"))
    
    text = f"""<b>🤖 GÖREV YAPSAM</b>

Merhaba {user['first_name']}!

Bakiye: <b>{format_money(user['balance'])}</b>
Görev: {user['tasks_completed']}
Ref: {user['referrals']}

Hemen başla!"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 5. START KOMUTU =================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    
    # Referans kontrolü
    ref_used = False
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = int(param.replace('ref_', ''))
                if referrer_id != user_id:
                    create_user(user_id, message.from_user.username, first_name)
                    if add_ref(referrer_id, user_id):
                        ref_used = True
            except:
                pass
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{ZORUNLU_KANAL}"),
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        bot.send_message(
            user_id,
            f"""Merhaba {first_name}!

Botu kullanmak için kanala katıl:

@{ZORUNLU_KANAL}

Katıldıktan sonra "✅ KATILDIM" butonuna bas.""",
            reply_markup=markup
        )
        return
    
    # Kullanıcı oluştur
    create_user(user_id, message.from_user.username, first_name)
    
    # Hoşgeldin bonusu
    user = get_user(user_id)
    if user['tasks_completed'] == 0:
        update_balance(user_id, 2.0)
    
    # Hoşgeldin mesajı
    welcome_msg = f"""Hoş geldin {first_name}!

✅ Kaydın oluşturuldu.
💰 Hoşgeldin bonusu: 2 ₺"""
    
    if ref_used:
        welcome_msg += "\n👥 Referans bonusu: Arkadaşın 1 ₺ kazandı!"
    
    bot.send_message(user_id, welcome_msg)
    
    # Ana menü
    show_main_menu(user_id)

@bot.message_handler(commands=['help', 'menu'])
def help_command(message):
    user_id = message.from_user.id
    show_main_menu(user_id)

# ================= 6. CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    update_user_activity(user_id)
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id) and call.data != "check_join":
        bot.answer_callback_query(call.id, "❌ Önce kanala katıl!", show_alert=True)
        return
    
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Başarılı!")
        else:
            bot.answer_callback_query(call.id, "❌ Hala katılmadın!", show_alert=True)
    
    elif call.data == "do_task":
        show_task_types(user_id, call.message.message_id)
    
    elif call.data == "my_balance":
        show_my_balance(user_id, call.message.message_id)
    
    elif call.data == "create_task":
        create_task_menu(user_id, call.message.message_id)
    
    elif call.data == "my_refs":
        show_my_refs(user_id, call.message.message_id)
    
    elif call.data == "admin_panel":
        if user_id == ADMIN_ID:
            show_admin_panel(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Yetkin yok!")
    
    elif call.data == "back_menu":
        show_main_menu(user_id, call.message.message_id)
    
    elif call.data in ["task_bot", "task_kanal", "task_grup"]:
        task_type = call.data.replace("task_", "")
        show_available_task(user_id, task_type, call.message.message_id)
    
    elif call.data.startswith("create_"):
        task_type = call.data.replace("create_", "")
        ask_task_info(user_id, task_type, call.message.message_id)
    
    elif call.data.startswith("complete_"):
        task_id = int(call.data.replace("complete_", ""))
        complete_user_task(user_id, task_id, call)
    
    elif call.data.startswith("copy_"):
        link = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, "✅ Link kopyalandı!")
    
    elif call.data.startswith("admin_"):
        handle_admin_action(call)

# ================= 7. GÖREV SİSTEMİ =================
def show_task_types(user_id, message_id):
    """Görev tipleri"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT (2.50 ₺)", callback_data="task_bot"),
        types.InlineKeyboardButton("📢 KANAL (1.50 ₺)", callback_data="task_kanal"),
        types.InlineKeyboardButton("👥 GRUP (1.00 ₺)", callback_data="task_grup")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = """<b>GÖREV SEÇ</b>

Hangi görevi yapmak istiyorsun?

🤖 <b>BOT</b> - 2.50 ₺
📢 <b>KANAL</b> - 1.50 ₺  
👥 <b>GRUP</b> - 1.00 ₺

Birini seç:"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_available_task(user_id, task_type, message_id):
    """Mevcut görevi göster"""
    tasks = get_active_tasks(task_type)
    
    if not tasks:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 YENİLE", callback_data=f"task_{task_type}"),
            types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_task"),
            types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
        )
        
        type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
        
        bot.edit_message_text(
            f"""<b>{type_names[task_type]} Görevi</b>

❌ Şu anda görev yok.

💡 Kendi görevini oluşturabilirsin!""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    task = tasks[0]
    show_single_task(user_id, task, message_id)

def show_single_task(user_id, task, message_id):
    """Tek görevi göster"""
    type_emojis = {"bot": "🤖", "kanal": "📢", "grup": "👥"}
    type_names = {"bot": "BOT", "kanal": "KANAL", "grup": "GRUP"}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 GİT", url=task['link']),
        types.InlineKeyboardButton("✅ TAMAMLA", callback_data=f"complete_{task['task_id']}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 YENİ", callback_data=f"task_{task['task_type']}"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    reward = PRICES[task['task_type']]
    
    text = f"""{type_emojis[task['task_type']]} <b>{type_names[task['task_type']]} GÖREV</b>

<b>{task['title']}</b>
{task['description']}

💰 <b>Ödül:</b> {format_money(reward)}
👁️ <b>Görüntü:</b> {task['views']}

1. "GİT" butonuna tıkla
2. Görevi yap
3. 3 dakika bekle
4. "TAMAMLA" butonuna bas"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def complete_user_task(user_id, task_id, call):
    """Görevi tamamla"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Görevi al
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            bot.answer_callback_query(call.id, "❌ Görev bulunamadı!")
            return
        
        # Görev sahibinin bakiyesini kontrol et
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (task['user_id'],))
        owner = cursor.fetchone()
        
        if not owner or owner['balance'] < task['cost_per_view']:
            cursor.execute("UPDATE tasks SET status = 'inactive' WHERE task_id = ?", (task_id,))
            conn.commit()
            bot.answer_callback_query(call.id, "❌ Görev sahibinin parası yok!")
            return
        
        reward = PRICES[task['task_type']]
        
        # Ödemeleri yap
        update_balance(user_id, reward)
        
        cursor.execute('''UPDATE users SET 
                       tasks_completed = tasks_completed + 1
                       WHERE user_id = ?''', (user_id,))
        
        cursor.execute('''UPDATE tasks SET 
                       views = views + 1,
                       cost_spent = cost_spent + ?
                       WHERE task_id = ?''', 
                       (task['cost_per_view'], task_id))
        
        cursor.execute('''INSERT INTO completions 
                       (task_id, user_id, earned)
                       VALUES (?, ?, ?)''', 
                       (task_id, user_id, reward))
        
        # Görev sahibinden para düş
        cursor.execute('''UPDATE users SET 
                       balance = balance - ?
                       WHERE user_id = ?''', 
                       (task['cost_per_view'], task['user_id']))
        
        # Bakiye bitmişse görevi kapat
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (task['user_id'],))
        new_balance = cursor.fetchone()['balance']
        
        if new_balance < task['cost_per_view']:
            cursor.execute("UPDATE tasks SET status = 'inactive' WHERE task_id = ?", (task_id,))
        
        conn.commit()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 YENİ GÖREV", callback_data="do_task"),
        types.InlineKeyboardButton("💰 BAKİYE", callback_data="my_balance")
    )
    
    bot.edit_message_text(
        f"""<b>✅ GÖREV TAMAMLANDI!</b>

💰 <b>Kazandın:</b> +{format_money(reward)}
💰 <b>Yeni bakiye:</b> {format_money(user['balance'])}
🎯 <b>Toplam görev:</b> {user['tasks_completed']}

Tebrikler!""",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, f"✅ +{format_money(reward)} kazandın!")

# ================= 8. GÖREV OLUŞTURMA =================
def create_task_menu(user_id, message_id):
    """Görev verme menüsü"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT GÖREV VER (2.50 ₺/görüntü)", callback_data="create_bot"),
        types.InlineKeyboardButton("📢 KANAL GÖREV VER (1.50 ₺/görüntü)", callback_data="create_kanal"),
        types.InlineKeyboardButton("👥 GRUP GÖREV VER (1.00 ₺/görüntü)", callback_data="create_grup")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = """<b>GÖREV VER</b>

Hangi görevi vermek istiyorsun?

🤖 <b>BOT</b> - 2.50 ₺ / görüntü
📢 <b>KANAL</b> - 1.50 ₺ / görüntü  
👥 <b>GRUP</b> - 1.00 ₺ / görüntü

⚠️ Grup görevi için bot grupta admin olmalı.

Birini seç:"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def ask_task_info(user_id, task_type, message_id):
    """Görev bilgilerini iste"""
    cost = PRICES[task_type]
    min_needed = cost * 5
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    
    bot.edit_message_text(
        f"""<b>{type_names[task_type]} Görevi Oluştur</b>

Görev bilgilerini şu şekilde gönder:

<code>Başlık
Link
Açıklama</code>

Örnek:
<code>Teknoloji Haberleri
https://t.me/teknolojihaber
En güncel teknoloji haberleri!</code>

💰 <b>Görüntü başına:</b> {format_money(cost)}
💳 <b>Min bakiye:</b> {format_money(min_needed)}

Gönder:""",
        user_id,
        message_id
    )
    
    bot.register_next_step_handler_by_chat_id(
        user_id, 
        save_task_info, 
        task_type, 
        message_id
    )

def save_task_info(message, task_type, message_id):
    """Görev bilgilerini kaydet"""
    user_id = message.from_user.id
    text = message.text.strip().split('\n')
    
    if len(text) < 3:
        bot.send_message(user_id, "❌ Hatalı format! 3 satır gönder.")
        show_main_menu(user_id)
        return
    
    title = text[0].strip()
    link = text[1].strip()
    desc = text[2].strip()
    
    # Link kontrolü
    if not link.startswith('https://t.me/'):
        bot.send_message(user_id, "❌ Link https://t.me/ ile başlamalı!")
        show_main_menu(user_id)
        return
    
    cost = PRICES[task_type]
    min_needed = cost * 5
    
    # Bakiye kontrolü
    user = get_user(user_id)
    if user['balance'] < min_needed:
        bot.send_message(
            user_id,
            f"❌ Yetersiz bakiye! Minimum {format_money(min_needed)} gerekli."
        )
        show_main_menu(user_id)
        return
    
    # Görev oluştur
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO tasks 
                       (user_id, task_type, title, link, description, cost_per_view)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                       (user_id, task_type, title, link, desc, cost))
        task_id = cursor.lastrowid
        conn.commit()
    
    # Başarı mesajı
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREVLER", callback_data="do_task"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    bot.send_message(
        user_id,
        f"""<b>✅ GÖREV OLUŞTURULDU!</b>

{get_task_emoji(task_type)} <b>{title}</b>
🔗 {link}
📝 {desc}

💰 <b>Görüntü başına:</b> {format_money(cost)}
🆔 <b>ID:</b> {task_id}

✅ Görevin aktif! Kullanıcılar görebilir.

⚠️ Her görüntülemede {format_money(cost)} düşülecek. Para bitince görev durur.""",
        reply_markup=markup
    )
    
    show_main_menu(user_id)

def get_task_emoji(task_type):
    emojis = {"bot": "🤖", "kanal": "📢", "grup": "👥"}
    return emojis.get(task_type, "🎯")

# ================= 9. BAKİYE =================
def show_my_balance(user_id, message_id):
    """Bakiye bilgisi"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("📢 GÖREV VER", callback_data="create_task")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = f"""<b>💰 BAKİYE</b>

👤 {user['first_name']}

💵 <b>Bakiye:</b> {format_money(user['balance'])}
📈 <b>Toplam:</b> {format_money(user['total_earned'])}
🎯 <b>Görev:</b> {user['tasks_completed']}
👥 <b>Ref:</b> {user['referrals']}

💸 <b>Para Çekim:</b>
Min: 20 ₺
Süre: 24 saat"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 10. REFERANS =================
def show_my_refs(user_id, message_id):
    """Referans bilgisi"""
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
        types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = f"""<b>👥 REFERANS</b>

💰 <b>Her referans:</b> 1 ₺
👤 <b>Toplam:</b> {user['referrals']}
📈 <b>Kazanç:</b> {format_money(user['ref_earned'])}

🔗 <b>Linkin:</b>
<code>{ref_link}</code>

1. Linki paylaş
2. Arkadaşların tıklasın
3. Onlar start atınca +1 ₺
4. Onlar da kazansın!

🔥 10 referansta +5 ₺ bonus!"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 11. ADMIN PANEL - TÜM BUTONLAR ÇALIŞIR =================
def show_admin_panel(user_id, message_id):
    """Admin panel ana sayfa"""
    if user_id != ADMIN_ID:
        return
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_earned) FROM users")
        total_earned = cursor.fetchone()[0] or 0
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Üst satır
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİKLER", callback_data="admin_stats"),
        types.InlineKeyboardButton("👤 KULLANICI", callback_data="admin_user")
    )
    
    # Orta satır
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE EKLE", callback_data="admin_add"),
        types.InlineKeyboardButton("📢 DUYURU", callback_data="admin_broadcast")
    )
    
    # Alt satır
    markup.add(
        types.InlineKeyboardButton("🗑️ VERİ TEMİZLE", callback_data="admin_clean"),
        types.InlineKeyboardButton("📋 LOGLAR", callback_data="admin_logs")
    )
    
    # En alt
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = f"""<b>👑 ADMIN PANEL</b>

Hoş geldin Admin!

👥 Kullanıcı: {total_users}
💰 Toplam Bakiye: {format_money(total_balance)}
📈 Toplam Kazanç: {format_money(total_earned)}

İşlem seç:"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

def handle_admin_action(call):
    """Admin işlemlerini yönet"""
    user_id = call.from_user.id
    action = call.data
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Yetkin yok!")
        return
    
    if action == "admin_stats":
        show_admin_stats(user_id, call.message.message_id)
    
    elif action == "admin_user":
        bot.edit_message_text(
            "Kullanıcı ID'si gönder:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_user_admin)
    
    elif action == "admin_add":
        bot.edit_message_text(
            "Kullanıcı ID ve miktar gönder (örn: 123456 10.50):",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_add_balance)
    
    elif action == "admin_broadcast":
        bot.edit_message_text(
            "Tüm kullanıcılara gönderilecek mesajı yaz:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_broadcast)
    
    elif action == "admin_clean":
        show_clean_options(user_id, call.message.message_id)
    
    elif action == "admin_logs":
        show_admin_logs(user_id, call.message.message_id)
    
    elif action == "admin_back":
        show_admin_panel(user_id, call.message.message_id)

def show_admin_stats(user_id, message_id):
    """Admin istatistikleri"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_earned) FROM users")
        total_earned = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(tasks_completed) FROM users")
        total_tasks = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total_task_ads = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'active'")
        active_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE channel_joined = 1")
        channel_joined = cursor.fetchone()[0]
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
    
    text = f"""<b>📊 İSTATİSTİKLER</b>

👤 <b>Toplam Kullanıcı:</b> {total_users}
📢 <b>Kanala Katılan:</b> {channel_joined}
💰 <b>Toplam Bakiye:</b> {format_money(total_balance)}
📈 <b>Toplam Kazanç:</b> {format_money(total_earned)}
🎯 <b>Toplam Görev:</b> {total_tasks}
📢 <b>Görev İlanı:</b> {total_task_ads}
🟢 <b>Aktif Görev:</b> {active_tasks}"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def process_user_admin(message):
    """Kullanıcı yönetimi"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    try:
        target_id = int(text)
        user = get_user(target_id)
        
        if not user:
            bot.send_message(user_id, "❌ Kullanıcı bulunamadı!")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
        
        info = f"""<b>👤 KULLANICI BİLGİSİ</b>

🆔 ID: {user['user_id']}
👤 Ad: {user['first_name']}
📛 Username: {user['username'] or 'Yok'}

💰 Bakiye: {format_money(user['balance'])}
📈 Toplam: {format_money(user['total_earned'])}
🎯 Görev: {user['tasks_completed']}
👥 Ref: {user['referrals']}
📅 Kayıt: {user['joined_date']}"""
        
        bot.send_message(user_id, info, reply_markup=markup)
        
    except:
        bot.send_message(user_id, "❌ Geçersiz ID!")

def process_add_balance(message):
    """Bakiye ekleme"""
    user_id = message.from_user.id
    text = message.text.strip().split()
    
    if len(text) != 2:
        bot.send_message(user_id, "❌ Format: ID MIKTAR")
        return
    
    try:
        target_id = int(text[0])
        amount = float(text[1])
        
        user = get_user(target_id)
        if not user:
            bot.send_message(user_id, "❌ Kullanıcı bulunamadı!")
            return
        
        update_balance(target_id, amount)
        
        # Kullanıcıya bildir
        try:
            bot.send_message(
                target_id,
                f"""<b>💰 BAKİYE EKLENDİ!</b>

Admin tarafından hesabına para eklendi:

💵 Miktar: +{format_money(amount)}
💰 Yeni Bakiye: {format_money(get_user(target_id)['balance'])}"""
            )
        except:
            pass
        
        bot.send_message(
            user_id,
            f"""✅ Bakiye eklendi!

👤 Kullanıcı: {user['first_name']}
🆔 ID: {target_id}
💰 Eklendi: +{format_money(amount)}
💰 Yeni: {format_money(get_user(target_id)['balance'])}"""
        )
        
    except:
        bot.send_message(user_id, "❌ Hata!")

def process_broadcast(message):
    """Toplu duyuru"""
    admin_id = message.from_user.id
    text = message.text
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_message(user[0], f"<b>📢 DUYURU</b>\n\n{text}")
            sent += 1
            time.sleep(0.05)
        except:
            failed += 1
    
    bot.send_message(
        admin_id,
        f"""✅ Duyuru tamamlandı!

✅ Başarılı: {sent}
❌ Başarısız: {failed}
👤 Toplam: {sent + failed}"""
    )

def show_clean_options(user_id, message_id):
    """Veri temizleme seçenekleri"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🗑️ ESKİ KAYITLARI TEMİZLE", callback_data="admin_clean_old"),
        types.InlineKeyboardButton("🔄 SIFIR BAKİYELİLER", callback_data="admin_clean_zero"),
        types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel")
    )
    
    text = """<b>🗑️ VERİ TEMİZLEME</b>

⚠️ <b>Dikkat:</b> Bu işlemler geri alınamaz!

<b>Seçenekler:</b>
• Eski Kayıtları Temizle: 30 günden eski pasif kullanıcıları sil
• Sıfır Bakiyeliler: 0 bakiye ve 0 görevi olanları temizle

⚠️ <b>Yedek almanız önerilir!</b>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_clean_old")
def clean_old_users(call):
    """Eski kullanıcıları temizle"""
    user_id = call.from_user.id
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''DELETE FROM users 
                       WHERE last_active < datetime('now', '-30 days') 
                       AND balance = 0 
                       AND tasks_completed = 0''')
        deleted = cursor.rowcount
        conn.commit()
    
    bot.edit_message_text(
        f"✅ {deleted} eski kullanıcı temizlendi!",
        call.message.chat.id,
        call.message.message_id
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_clean_zero")
def clean_zero_users(call):
    """Sıfır bakiye kullanıcıları temizle"""
    user_id = call.from_user.id
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''DELETE FROM users 
                       WHERE balance = 0 
                       AND tasks_completed = 0 
                       AND referrals = 0''')
        deleted = cursor.rowcount
        conn.commit()
    
    bot.edit_message_text(
        f"✅ {deleted} sıfır bakiye kullanıcı temizlendi!",
        call.message.chat.id,
        call.message.message_id
    )

def show_admin_logs(user_id, message_id):
    """Admin logları"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM completions 
                       ORDER BY created_at DESC 
                       LIMIT 10''')
        completions = cursor.fetchall()
    
    if not completions:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
        
        bot.edit_message_text(
            "<b>📋 SON İŞLEMLER</b>\n\n❌ Henüz işlem bulunmuyor.",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    log_text = "<b>📋 SON 10 GÖREV TAMAMLAMA</b>\n\n"
    
    for comp in completions:
        cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (comp['user_id'],))
        user = cursor.fetchone()
        
        cursor.execute("SELECT title FROM tasks WHERE task_id = ?", (comp['task_id'],))
        task = cursor.fetchone()
        
        username = user['first_name'] if user else f"ID:{comp['user_id']}"
        taskname = task['title'][:20] + "..." if task and task['title'] else f"Görev:{comp['task_id']}"
        timestamp = comp['created_at'][:19] if comp['created_at'] else "N/A"
        
        log_text += f"👤 {username}\n"
        log_text += f"📌 {taskname}\n"
        log_text += f"💰 {format_money(comp['earned'])}\n"
        log_text += f"📅 {timestamp}\n"
        log_text += "─" * 20 + "\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
    
    bot.edit_message_text(log_text, user_id, message_id, reply_markup=markup)

# ================= 12. FLASK SUNUCUSU =================
@app.route('/')
def home():
    return "🤖 Görev Yapsam Bot Aktif!"

@app.route('/health')
def health():
    return {"status": "ok"}

# ================= 13. BOT ÇALIŞTIRMA =================
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
