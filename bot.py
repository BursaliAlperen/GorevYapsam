"""
🤖 GÖREV YAPSAM BOTU v12.0 - GELİŞMİŞ SİSTEM
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
ZORUNLU_KANAL = "GY_Refim"

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
            ad_balance REAL DEFAULT 0.0,  -- Reklam bakiyesi
            total_earned REAL DEFAULT 0.0,
            tasks_completed INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            ref_earned REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            channel_joined INTEGER DEFAULT 0,
            welcome_bonus INTEGER DEFAULT 0
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
            max_views INTEGER,
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
        
        # Bakiye yüklemeleri
        cursor.execute('''CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Reklam dönüşümleri
        cursor.execute('''CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_balance REAL,
            to_ad_balance REAL,
            bonus REAL,
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
                       (user_id, username, first_name, balance, ad_balance) 
                       VALUES (?, ?, ?, 0.0, 0.0)''', 
                       (user_id, username, first_name))
        conn.commit()

def update_balance(user_id, amount, balance_type='balance'):
    """Bakiye güncelle"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if balance_type == 'ad_balance':
            if amount > 0:
                cursor.execute('''UPDATE users SET 
                               ad_balance = ad_balance + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, user_id))
            else:
                cursor.execute('''UPDATE users SET 
                               ad_balance = ad_balance + ?,
                               last_active = CURRENT_TIMESTAMP
                               WHERE user_id = ?''', 
                               (amount, user_id))
        else:
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

def get_total_balance(user_id):
    """Toplam bakiye (normal + reklam)"""
    user = get_user(user_id)
    return user['balance'] + user['ad_balance']

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
        
        cursor.execute('''SELECT * FROM referrals 
                       WHERE referrer_id = ? AND referred_id = ?''',
                       (referrer_id, referred_id))
        
        if cursor.fetchone():
            return False
        
        cursor.execute('''INSERT INTO referrals 
                       (referrer_id, referred_id, earned)
                       VALUES (?, ?, ?)''', (referrer_id, referred_id, 1.0))
        
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

# Kullanıcı durumları için sözlük
user_states = {}

# ================= 4. ANA MENÜ =================
def show_main_menu(user_id, message_id=None):
    """Ana menü"""
    user = get_user(user_id)
    update_user_activity(user_id)
    
    if not user:
        create_user(user_id, "", "")
        user = get_user(user_id)
    
    total_balance = get_total_balance(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Ana butonlar
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("💰 " + format_money(total_balance), callback_data="my_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton("📢 GÖREV OLUŞTUR", callback_data="create_task_menu"),
        types.InlineKeyboardButton("👥 REFERANS", callback_data="my_refs")
    )
    
    markup.add(
        types.InlineKeyboardButton("💳 BAKİYE YÜKLE", callback_data="deposit_menu"),
        types.InlineKeyboardButton("🔄 REKLAM BAKİYESİ", callback_data="ad_balance_menu")
    )
    
    # Admin butonu
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel"))
    
    text = f"""<b>🤖 GÖREV YAPSAM</b>

Merhaba {user['first_name']}!

💰 <b>Toplam Bakiye:</b> {format_money(total_balance)}
• Normal: {format_money(user['balance'])}
• Reklam: {format_money(user['ad_balance'])}

🎯 <b>Görev:</b> {user['tasks_completed']}
👥 <b>Ref:</b> {user['referrals']}

📢 <b>Kanal:</b> @{ZORUNLU_KANAL}

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
    
    # Kullanıcı oluştur veya kontrol et
    create_user(user_id, message.from_user.username, first_name)
    user = get_user(user_id)
    
    # Referans kontrolü
    ref_used = False
    ref_info = ""
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = int(param.replace('ref_', ''))
                if referrer_id != user_id:
                    if add_ref(referrer_id, user_id):
                        ref_used = True
                        ref_user = get_user(referrer_id)
                        ref_info = f"\n👥 <b>Referans:</b> {ref_user['first_name']} kazandı!"
            except:
                pass
    
    # SADECE İLK KEZ GELİYORSA HOŞGELDİN BONUSU
    welcome_bonus = 0
    if user['welcome_bonus'] == 0:
        welcome_bonus = 2.0
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''UPDATE users SET 
                           welcome_bonus = 1,
                           balance = balance + ?,
                           total_earned = total_earned + ?
                           WHERE user_id = ?''', 
                           (welcome_bonus, welcome_bonus, user_id))
            conn.commit()
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{ZORUNLU_KANAL}"),
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        welcome_text = f"""Merhaba {first_name}!

Botu kullanmak için kanala katıl:

@{ZORUNLU_KANAL}

Katıldıktan sonra "✅ KATILDIM" butonuna bas."""
        
        if welcome_bonus > 0:
            welcome_text += f"\n\n💰 <b>Hoşgeldin bonusu:</b> {format_money(welcome_bonus)}"
        
        if ref_used:
            welcome_text += ref_info
        
        bot.send_message(user_id, welcome_text, reply_markup=markup)
        return
    
    # Hoşgeldin mesajı
    welcome_msg = f"""Hoş geldin {first_name}!

✅ Botu başarıyla kullanabilirsin."""
    
    if welcome_bonus > 0:
        welcome_msg += f"\n💰 <b>Hoşgeldin bonusu:</b> {format_money(welcome_bonus)}"
    
    if ref_used:
        welcome_msg += ref_info
    
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
    
    # Kanal kontrolü (check_join hariç)
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
    
    elif call.data == "create_task_menu":
        create_task_menu(user_id, call.message.message_id)
    
    elif call.data == "my_refs":
        show_my_refs(user_id, call.message.message_id)
    
    elif call.data == "deposit_menu":
        show_deposit_menu(user_id, call.message.message_id)
    
    elif call.data == "ad_balance_menu":
        show_ad_balance_menu(user_id, call.message.message_id)
    
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
    
    # Görev oluşturma butonları
    elif call.data in ["create_bot", "create_kanal", "create_grup"]:
        task_type = call.data.replace("create_", "")
        start_task_creation(user_id, task_type, call.message.message_id)
    
    # Görev oluşturma adımları
    elif call.data == "cancel_task":
        show_main_menu(user_id, call.message.message_id)
        bot.answer_callback_query(call.id, "❌ Görev oluşturma iptal edildi!")
    
    elif call.data.startswith("confirm_task_"):
        task_type = call.data.replace("confirm_task_", "")
        confirm_task_creation(user_id, task_type, call.message.message_id)
    
    elif call.data.startswith("complete_"):
        task_id = int(call.data.replace("complete_", ""))
        complete_user_task(user_id, task_id, call)
    
    elif call.data.startswith("copy_"):
        link = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, "✅ Link kopyalandı!")
    
    # Bakiye yükleme
    elif call.data.startswith("deposit_"):
        amount = call.data.replace("deposit_", "")
        if amount == "other":
            ask_custom_deposit(user_id, call.message.message_id)
        else:
            confirm_deposit(user_id, float(amount), call.message.message_id)
    
    elif call.data == "confirm_deposit":
        process_deposit(user_id, call.message.message_id)
    
    # Reklam bakiyesi
    elif call.data.startswith("convert_"):
        amount = float(call.data.replace("convert_", ""))
        convert_to_ad_balance(user_id, amount, call.message.message_id)
    
    elif call.data == "convert_custom":
        ask_custom_conversion(user_id, call.message.message_id)
    
    # Admin işlemleri
    elif call.data.startswith("admin_"):
        handle_admin_action(call)

# ================= 7. GÖREV YAPMA SİSTEMİ =================
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
            types.InlineKeyboardButton("📢 GÖREV OLUŞTUR", callback_data="create_task_menu"),
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
    
    reward = PRICES[task['task_type']]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 GİT", url=task['link']),
        types.InlineKeyboardButton("✅ TAMAMLA", callback_data=f"complete_{task['task_id']}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 YENİ", callback_data=f"task_{task['task_type']}"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    text = f"""{type_emojis[task['task_type']]} <b>{type_names[task['task_type']]} GÖREV</b>

<b>{task['title']}</b>
{task['description']}

💰 <b>Ödül:</b> {format_money(reward)}
👁️ <b>Görüntü:</b> {task['views']}/{task['max_views']}

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
        
        # Aynı görevi daha önce tamamladı mı?
        cursor.execute('''SELECT * FROM completions 
                       WHERE task_id = ? AND user_id = ?''',
                       (task_id, user_id))
        
        if cursor.fetchone():
            bot.answer_callback_query(call.id, "❌ Bu görevi zaten tamamladın!", show_alert=True)
            return
        
        # Görev sahibinin reklam bakiyesini kontrol et
        cursor.execute("SELECT ad_balance FROM users WHERE user_id = ?", (task['user_id'],))
        owner = cursor.fetchone()
        
        if not owner or owner['ad_balance'] < task['cost_per_view']:
            cursor.execute("UPDATE tasks SET status = 'inactive' WHERE task_id = ?", (task_id,))
            conn.commit()
            bot.answer_callback_query(call.id, "❌ Görev sahibinin reklam bakiyesi yetersiz!", show_alert=True)
            return
        
        # Maksimum görüntü kontrolü
        if task['views'] >= task['max_views']:
            cursor.execute("UPDATE tasks SET status = 'completed' WHERE task_id = ?", (task_id,))
            conn.commit()
            bot.answer_callback_query(call.id, "❌ Görev kotası doldu!", show_alert=True)
            return
        
        reward = PRICES[task['task_type']]
        
        # Kullanıcıya ödeme yap
        update_balance(user_id, reward)
        
        # Görev sahibinden reklam bakiyesinden düş
        cursor.execute('''UPDATE users SET 
                       ad_balance = ad_balance - ?
                       WHERE user_id = ?''', 
                       (task['cost_per_view'], task['user_id']))
        
        # İstatistikleri güncelle
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
        
        # Görüntü sayısı dolduysa görevi kapat
        if task['views'] + 1 >= task['max_views']:
            cursor.execute("UPDATE tasks SET status = 'completed' WHERE task_id = ?", (task_id,))
        
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

# ================= 8. GÖREV OLUŞTURMA SİSTEMİ (ADIM ADIM) =================
def create_task_menu(user_id, message_id):
    """Görev oluşturma menüsü"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT GÖREV OLUŞTUR (2.50 ₺/görüntü)", callback_data="create_bot"),
        types.InlineKeyboardButton("📢 KANAL GÖREV OLUŞTUR (1.50 ₺/görüntü)", callback_data="create_kanal"),
        types.InlineKeyboardButton("👥 GRUP GÖREV OLUŞTUR (1.00 ₺/görüntü)", callback_data="create_grup")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = """<b>📢 GÖREV OLUŞTUR</b>

Hangi görevi oluşturmak istiyorsun?

🤖 <b>BOT GÖREV</b>
• Maliyet: 2.50 ₺ / görüntü
• Forward mesaj zorunlu

📢 <b>KANAL GÖREV</b>
• Maliyet: 1.50 ₺ / görüntü  
• Forward mesaj zorunlu
• Bot kanalda admin olmalı

👥 <b>GRUP GÖREV</b>
• Maliyet: 1.00 ₺ / görüntü
• Forward mesaj zorunlu
• Bot grupta admin olmalı

Birini seç:"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def start_task_creation(user_id, task_type, message_id):
    """Görev oluşturmaya başla"""
    # Kullanıcı durumunu sıfırla
    if user_id in user_states:
        del user_states[user_id]
    
    user_states[user_id] = {
        'creating_task': True,
        'task_type': task_type,
        'step': 1,
        'data': {}
    }
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task"))
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    cost = PRICES[task_type]
    
    bot.edit_message_text(
        f"""<b>📝 {type_names[task_type]} Görevi Oluştur</b>

Adım 1/4: <b>Görev İsmi</b>

Görevin için bir isim yaz:

Örnek: <code>Yapay Zeka Asistanı</code>
Örnek: <code>Teknoloji Haberleri</code>

⚠️ <b>Not:</b> İptal etmek için "❌ İPTAL" butonuna bas.

💰 <b>Maliyet:</b> {format_money(cost)} / görüntü""",
        user_id,
        message_id,
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('creating_task') and user_states[message.from_user.id]['step'] == 1)
def process_task_name(message):
    """Görev ismini işle"""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    state['data']['title'] = message.text.strip()
    state['step'] = 2
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task"))
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    
    bot.send_message(
        user_id,
        f"""✅ <b>Adım 1 tamamlandı!</b>

Adım 2/4: <b>Görev Linki</b>

Görevin linkini yaz:

Örnek: <code>https://t.me/bot_adi</code>
Örnek: <code>https://t.me/kanal_adi</code>

⚠️ <b>Format:</b> https://t.me/ ile başlamalı

📌 <b>İsim:</b> {state['data']['title']}""",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('creating_task') and user_states[message.from_user.id]['step'] == 2)
def process_task_link(message):
    """Görev linkini işle"""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    link = message.text.strip()
    
    if not link.startswith('https://t.me/'):
        bot.send_message(user_id, "❌ Link https://t.me/ ile başlamalı! Tekrar dene:")
        return
    
    state['data']['link'] = link
    state['step'] = 3
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task"))
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    
    bot.send_message(
        user_id,
        f"""✅ <b>Adım 2 tamamlandı!</b>

Adım 3/4: <b>Görev Açıklaması</b>

Görevin için bir açıklama yaz:

Örnek: <code>En gelişmiş AI asistanı!</code>
Örnek: <code>Teknoloji haberleri için kanalımıza katılın!</code>

📌 <b>İsim:</b> {state['data']['title']}
🔗 <b>Link:</b> {state['data']['link']}""",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('creating_task') and user_states[message.from_user.id]['step'] == 3)
def process_task_description(message):
    """Görev açıklamasını işle"""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    state['data']['description'] = message.text.strip()
    state['step'] = 4
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task"))
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    cost = PRICES[state['task_type']]
    
    bot.send_message(
        user_id,
        f"""✅ <b>Adım 3 tamamlandı!</b>

Adım 4/4: <b>Kaç Kişi Tamamlayacak?</b>

Görevin kaç kişi tarafından tamamlansın?

Örnek: <code>10</code> (10 kişi)
Örnek: <code>50</code> (50 kişi)

📌 <b>İsim:</b> {state['data']['title']}
🔗 <b>Link:</b> {state['data']['link']}
📝 <b>Açıklama:</b> {state['data']['description']}

💰 <b>Toplam Maliyet:</b> (kişi sayısı × {format_money(cost)})""",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('creating_task') and user_states[message.from_user.id]['step'] == 4)
def process_task_views(message):
    """Görev görüntü sayısını işle"""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    try:
        max_views = int(message.text.strip())
        if max_views < 1:
            bot.send_message(user_id, "❌ En az 1 kişi olmalı! Tekrar dene:")
            return
    except:
        bot.send_message(user_id, "❌ Sayı girmelisin! Örnek: 10")
        return
    
    state['data']['max_views'] = max_views
    
    # Forward mesaj iste
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task"))
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    cost = PRICES[state['task_type']]
    total_cost = cost * max_views
    
    bot.send_message(
        user_id,
        f"""✅ <b>Adım 4 tamamlandı!</b>

📝 <b>GÖREV ÖZETİ</b>

📌 <b>İsim:</b> {state['data']['title']}
🔗 <b>Link:</b> {state['data']['link']}
📝 <b>Açıklama:</b> {state['data']['description']}
👥 <b>Kişi Sayısı:</b> {max_views}
💰 <b>Kişi Başı:</b> {format_money(cost)}
💰 <b>Toplam Maliyet:</b> {format_money(total_cost)}

⚠️ <b>Şimdi bu mesajı FORWARD etmelisin!</b>

<i>Bu mesajı bana forward et ki görev oluşturabileyim.</i>""",
        reply_markup=markup
    )
    
    # Forward mesaj beklemeye başla
    state['step'] = 5

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get('creating_task') and user_states[message.from_user.id]['step'] == 5 and message.forward_from is not None)
def process_forwarded_message(message):
    """Forward edilen mesajı işle"""
    user_id = message.from_user.id
    state = user_states[user_id]
    
    type_names = {"bot": "Bot", "kanal": "Kanal", "grup": "Grup"}
    cost = PRICES[state['task_type']]
    total_cost = cost * state['data']['max_views']
    
    # Reklam bakiyesi kontrolü
    user = get_user(user_id)
    if user['ad_balance'] < total_cost:
        bot.send_message(
            user_id,
            f"""❌ <b>Yetersiz Reklam Bakiyesi!</b>

Gerekli: {format_money(total_cost)}
Mevcut: {format_money(user['ad_balance'])}

💡 <b>Çözüm:</b>
1. "🔄 REKLAM BAKİYESİ" menüsüne git
2. Normal bakiyenden reklam bakiyesine çevir
3. %25 bonus kazan""",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔄 REKLAM BAKİYESİ", callback_data="ad_balance_menu")
            )
        )
        del user_states[user_id]
        return
    
    # Kanal/Grup görevi için admin kontrolü
    if state['task_type'] in ['kanal', 'grup']:
        try:
            bot_id = bot.get_me().id
            chat_username = state['data']['link'].replace('https://t.me/', '').replace('@', '')
            
            try:
                chat = bot.get_chat('@' + chat_username)
                chat_member = bot.get_chat_member(chat.id, bot_id)
                
                if chat_member.status not in ['administrator', 'creator']:
                    bot.send_message(
                        user_id,
                        f"""❌ <b>Bot {type_names[state['task_type']]}da admin değil!</b>

Lütfen botu {state['data']['link']} adresindeki {type_names[state['task_type']]}a admin yapın, sonra tekrar deneyin."""
                    )
                    del user_states[user_id]
                    return
            except:
                bot.send_message(
                    user_id,
                    f"❌ {type_names[state['task_type']]} bulunamadı veya erişim yok!"
                )
                del user_states[user_id]
                return
        except Exception as e:
            bot.send_message(
                user_id,
                f"❌ {type_names[state['task_type']]} kontrol hatası!"
            )
            del user_states[user_id]
            return
    
    # Onay menüsü
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ OLUŞTUR", callback_data=f"confirm_task_{state['task_type']}"),
        types.InlineKeyboardButton("❌ İPTAL", callback_data="cancel_task")
    )
    
    bot.send_message(
        user_id,
        f"""✅ <b>Forward Mesaj Alındı!</b>

🎯 <b>GÖREV DETAYLARI</b>

📌 <b>İsim:</b> {state['data']['title']}
🔗 <b>Link:</b> {state['data']['link']}
📝 <b>Açıklama:</b> {state['data']['description']}
👥 <b>Kişi Sayısı:</b> {state['data']['max_views']}
💰 <b>Kişi Başı:</b> {format_money(cost)}
💰 <b>Toplam Maliyet:</b> {format_money(total_cost)}

💳 <b>Reklam Bakiyen:</b> {format_money(user['ad_balance'])}
💳 <b>Kalan Bakiye:</b> {format_money(user['ad_balance'] - total_cost)}

<i>Görevi oluşturmak için "✅ OLUŞTUR" butonuna bas.</i>""",
        reply_markup=markup
    )

def confirm_task_creation(user_id, task_type, message_id):
    """Görevi onayla ve oluştur"""
    if user_id not in user_states:
        show_main_menu(user_id, message_id)
        return
    
    state = user_states[user_id]
    
    cost = PRICES[task_type]
    total_cost = cost * state['data']['max_views']
    
    # Reklam bakiyesi kontrolü
    user = get_user(user_id)
    if user['ad_balance'] < total_cost:
        bot.edit_message_text(
            "❌ Yetersiz reklam bakiyesi!",
            user_id,
            message_id
        )
        del user_states[user_id]
        return
    
    # Görevi oluştur
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO tasks 
                       (user_id, task_type, title, link, description, cost_per_view, max_views)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (user_id, task_type, 
                        state['data']['title'],
                        state['data']['link'],
                        state['data']['description'],
                        cost,
                        state['data']['max_views']))
        
        # Reklam bakiyesinden düş
        cursor.execute('''UPDATE users SET 
                       ad_balance = ad_balance - ?
                       WHERE user_id = ?''', 
                       (total_cost, user_id))
        
        conn.commit()
    
    task_id = cursor.lastrowid
    
    # Başarı mesajı
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREVLER", callback_data="do_task"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    type_emojis = {"bot": "🤖", "kanal": "📢", "grup": "👥"}
    
    bot.edit_message_text(
        f"""<b>✅ GÖREV OLUŞTURULDU!</b>

{type_emojis[task_type]} <b>Görev Başlatıldı!</b>

📌 <b>İsim:</b> {state['data']['title']}
🔗 <b>Link:</b> {state['data']['link']}
👥 <b>Kişi Sayısı:</b> {state['data']['max_views']}
💰 <b>Toplam Maliyet:</b> {format_money(total_cost)}
🆔 <b>Görev ID:</b> {task_id}

✅ Görevin aktif! Kullanıcılar görebilir.

💡 <b>İpucu:</b> Görevlerini "GÖREV YAP" menüsünden takip edebilirsin.""",
        user_id,
        message_id,
        reply_markup=markup
    )
    
    # Durumu temizle
    del user_states[user_id]

# ================= 9. BAKİYE SİSTEMİ =================
def show_my_balance(user_id, message_id):
    """Bakiye bilgisi"""
    user = get_user(user_id)
    total_balance = get_total_balance(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("📢 GÖREV OLUŞTUR", callback_data="create_task_menu")
    )
    markup.add(
        types.InlineKeyboardButton("💳 BAKİYE YÜKLE", callback_data="deposit_menu"),
        types.InlineKeyboardButton("🔄 REKLAM BAKİYESİ", callback_data="ad_balance_menu")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    text = f"""<b>💰 BAKİYE DETAYLARI</b>

👤 {user['first_name']}

💵 <b>Toplam Bakiye:</b> {format_money(total_balance)}
• Normal Bakiye: {format_money(user['balance'])}
• Reklam Bakiyesi: {format_money(user['ad_balance'])}

📈 <b>Toplam Kazanç:</b> {format_money(user['total_earned'])}
🎯 <b>Görev:</b> {user['tasks_completed']}
👥 <b>Ref:</b> {user['referrals']}
💰 <b>Ref Kazanç:</b> {format_money(user['ref_earned'])}

💸 <b>Para Çekim:</b>
Min: 20 ₺
Süre: 24 saat"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 10. BAKİYE YÜKLEME =================
def show_deposit_menu(user_id, message_id):
    """Bakiye yükleme menüsü"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("10 ₺", callback_data="deposit_10"),
        types.InlineKeyboardButton("25 ₺", callback_data="deposit_25"),
        types.InlineKeyboardButton("50 ₺", callback_data="deposit_50"),
        types.InlineKeyboardButton("100 ₺", callback_data="deposit_100")
    )
    markup.add(
        types.InlineKeyboardButton("250 ₺", callback_data="deposit_250"),
        types.InlineKeyboardButton("500 ₺", callback_data="deposit_500"),
        types.InlineKeyboardButton("Diğer", callback_data="deposit_other"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    text = """<b>💳 BAKİYE YÜKLE</b>

Hangi miktarı yüklemek istiyorsun?

👇 Bir miktar seç veya "Diğer" seçeneğiyle özel miktar gir.

⚠️ <b>Not:</b> Bakiye yükleme işlemleri manuel onay gerektirir."""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def ask_custom_deposit(user_id, message_id):
    """Özel miktar sor"""
    bot.edit_message_text(
        """💳 <b>Özel Miktar</b>

Yüklemek istediğin miktarı yaz:

Örnek: <code>75</code> (75 ₺)
Örnek: <code>150.50</code> (150.50 ₺)

<i>Minimum: 10 ₺</i>""",
        user_id,
        message_id
    )
    
    bot.register_next_step_handler_by_chat_id(user_id, process_custom_deposit)

def process_custom_deposit(message):
    """Özel miktarı işle"""
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.strip())
        if amount < 10:
            bot.send_message(user_id, "❌ Minimum 10 ₺ yükleyebilirsin!")
            show_deposit_menu(user_id, None)
            return
    except:
        bot.send_message(user_id, "❌ Geçersiz miktar!")
        show_deposit_menu(user_id, None)
        return
    
    confirm_deposit(user_id, amount, None)

def confirm_deposit(user_id, amount, message_id):
    """Bakiye yüklemeyi onayla"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ ONAYLA", callback_data="confirm_deposit"),
        types.InlineKeyboardButton("❌ İPTAL", callback_data="back_menu")
    )
    
    if message_id:
        bot.edit_message_text(
            f"""💳 <b>BAKİYE YÜKLEME ONAYI</b>

💰 <b>Miktar:</b> {format_money(amount)}

ℹ️ <b>Bilgi:</b>
1. "✅ ONAYLA" butonuna bas
2. Admin onayı bekleyeceksin
3. Onaylandığında bakiye yüklenecek

⏰ <b>Süre:</b> 24 saat içinde onaylanır""",
            user_id,
            message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(
            user_id,
            f"""💳 <b>BAKİYE YÜKLEME ONAYI</b>

💰 <b>Miktar:</b> {format_money(amount)}

ℹ️ <b>Bilgi:</b>
1. "✅ ONAYLA" butonuna bas
2. Admin onayı bekleyeceksin
3. Onaylandığında bakiye yüklenecek

⏰ <b>Süre:</b> 24 saat içinde onaylanır""",
            reply_markup=markup
        )
    
    # Geçici olarak kaydet
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]['deposit_amount'] = amount

def process_deposit(user_id, message_id):
    """Bakiye yüklemeyi işle"""
    if user_id not in user_states or 'deposit_amount' not in user_states[user_id]:
        show_main_menu(user_id, message_id)
        return
    
    amount = user_states[user_id]['deposit_amount']
    
    # Deposit kaydı oluştur
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO deposits 
                       (user_id, amount, method, status)
                       VALUES (?, ?, ?, ?)''',
                       (user_id, amount, 'manual', 'pending'))
        conn.commit()
    
    # Admin'e bildir
    try:
        admin_text = f"""📥 <b>YENİ BAKİYE YÜKLEME TALEBI</b>

👤 <b>Kullanıcı:</b> {get_user(user_id)['first_name']}
🆔 <b>ID:</b> {user_id}
💰 <b>Miktar:</b> {format_money(amount)}
📅 <b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        bot.send_message(ADMIN_ID, admin_text)
    except:
        pass
    
    bot.edit_message_text(
        f"""✅ <b>BAKİYE YÜKLEME TALEBİ ALINDI</b>

💰 <b>Miktar:</b> {format_money(amount)}
📊 <b>Durum:</b> Admin onayı bekleniyor
⏰ <b>Süre:</b> 24 saat içinde onaylanacak

💡 <b>Bilgi:</b> Onaylandığında bildirim alacaksın.

📞 <b>Destek:</b> @AlperenTHE""",
        user_id,
        message_id
    )
    
    # Temizle
    if user_id in user_states:
        del user_states[user_id]

# ================= 11. REKLAM BAKİYESİ =================
def show_ad_balance_menu(user_id, message_id):
    """Reklam bakiyesi menüsü"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("10 ₺", callback_data="convert_10"),
        types.InlineKeyboardButton("25 ₺", callback_data="convert_25"),
        types.InlineKeyboardButton("50 ₺", callback_data="convert_50"),
        types.InlineKeyboardButton("100 ₺", callback_data="convert_100")
    )
    markup.add(
        types.InlineKeyboardButton("Diğer", callback_data="convert_custom"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    text = f"""<b>🔄 REKLAM BAKİYESİ</b>

💰 <b>Normal Bakiye:</b> {format_money(user['balance'])}
💰 <b>Reklam Bakiyesi:</b> {format_money(user['ad_balance'])}

🎁 <b>%25 BONUS!</b> Normal bakiyeni reklam bakiyesine çevir, %25 bonus kazan!

Örnek: 100 ₺ normal bakiye → 125 ₺ reklam bakiyesi

👇 Çevirmek istediğin miktarı seç:"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def ask_custom_conversion(user_id, message_id):
    """Özel dönüşüm miktarı sor"""
    bot.edit_message_text(
        """🔄 <b>Özel Miktar</b>

Normal bakiyenden ne kadarını reklam bakiyesine çevirmek istiyorsun?

Örnek: <code>75</code> (75 ₺)
Örnek: <code>150.50</code> (150.50 ₺)

<i>Minimum: 10 ₺</i>""",
        user_id,
        message_id
    )
    
    bot.register_next_step_handler_by_chat_id(user_id, process_custom_conversion)

def process_custom_conversion(message):
    """Özel dönüşümü işle"""
    user_id = message.from_user.id
    
    try:
        amount = float(message.text.strip())
        if amount < 10:
            bot.send_message(user_id, "❌ Minimum 10 ₺ çevirebilirsin!")
            show_ad_balance_menu(user_id, None)
            return
    except:
        bot.send_message(user_id, "❌ Geçersiz miktar!")
        show_ad_balance_menu(user_id, None)
        return
    
    convert_to_ad_balance(user_id, amount, None)

def convert_to_ad_balance(user_id, amount, message_id):
    """Normal bakiyeden reklam bakiyesine çevir"""
    user = get_user(user_id)
    
    if user['balance'] < amount:
        text = f"""❌ <b>YETERSİZ BAKİYE!</b>

💵 <b>Gerekli:</b> {format_money(amount)}
💵 <b>Mevcut:</b> {format_money(user['balance'])}

💡 <b>Öneri:</b> Önce bakiye yükle veya görev yap."""
        
        if message_id:
            bot.edit_message_text(text, user_id, message_id)
        else:
            bot.send_message(user_id, text)
        return
    
    bonus = amount * 0.25  # %25 bonus
    total_ad = amount + bonus
    
    # İşlemi gerçekleştir
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Bakiyeleri güncelle
        cursor.execute('''UPDATE users SET 
                       balance = balance - ?,
                       ad_balance = ad_balance + ?
                       WHERE user_id = ?''', 
                       (amount, total_ad, user_id))
        
        # Kayıt ekle
        cursor.execute('''INSERT INTO conversions 
                       (user_id, from_balance, to_ad_balance, bonus)
                       VALUES (?, ?, ?, ?)''',
                       (user_id, amount, total_ad, bonus))
        
        conn.commit()
    
    # Başarı mesajı
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 GÖREV OLUŞTUR", callback_data="create_task_menu"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    text = f"""✅ <b>BAKIYE ÇEVİRİLDİ!</b>

💰 <b>Çevrilen:</b> {format_money(amount)}
🎁 <b>Bonus (%25):</b> {format_money(bonus)}
💰 <b>Toplam Reklam Bakiyesi:</b> {format_money(total_ad)}

💳 <b>Yeni Durum:</b>
• Normal Bakiye: {format_money(user['balance'] - amount)}
• Reklam Bakiyesi: {format_money(user['ad_balance'] + total_ad)}

🎯 <b>Şimdi görev oluşturabilirsin!</b>"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 12. REFERANS SİSTEMİ =================
def show_my_refs(user_id, message_id):
    """Referans bilgisi"""
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    # Referans geçmişi
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT COUNT(*) as total_refs,
                       SUM(earned) as total_earned
                       FROM referrals 
                       WHERE referrer_id = ?''',
                       (user_id,))
        ref_stats = cursor.fetchone()
        
        cursor.execute('''SELECT u.first_name, r.created_at 
                       FROM referrals r
                       JOIN users u ON r.referred_id = u.user_id
                       WHERE r.referrer_id = ? 
                       ORDER BY r.created_at DESC LIMIT 10''',
                       (user_id,))
        recent_refs = cursor.fetchall()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
        types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu"))
    
    # Referans geçmişi
    ref_history = ""
    if recent_refs:
        ref_history = "\n<b>📋 Son Referanslar:</b>\n"
        for i, ref in enumerate(recent_refs, 1):
            date_str = ref['created_at'][:10] if ref['created_at'] else "???"
            ref_history += f"{i}. {ref['first_name']} - {date_str}\n"
    else:
        ref_history = "\n📭 <i>Henüz referansın yok.</i>"
    
    text = f"""<b>👥 REFERANS SİSTEMİ</b>

💰 <b>Her referans:</b> 1 ₺
👤 <b>Toplam:</b> {ref_stats['total_refs'] or 0} kişi
📈 <b>Kazanç:</b> {format_money(ref_stats['total_earned'] or 0)}

🔗 <b>Linkin:</b>
<code>{ref_link}</code>

{ref_history}

🔥 <b>Bonus:</b>
• 5 referans: +2 ₺
• 10 referans: +5 ₺
• 25 referans: +15 ₺
• 50 referans: +35 ₺"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 13. ADMIN PANEL =================
def show_admin_panel(user_id, message_id):
    """Admin panel"""
    if user_id != ADMIN_ID:
        return
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(ad_balance) FROM users")
        total_ad_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM deposits WHERE status = 'pending'")
        pending_deposits = cursor.fetchone()[0]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Üst satır
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİK", callback_data="admin_stats"),
        types.InlineKeyboardButton("👤 KULLANICI", callback_data="admin_user")
    )
    
    # Orta satır
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE EKLE", callback_data="admin_add"),
        types.InlineKeyboardButton("📥 DEPOZİTLER", callback_data=f"admin_deposits_{pending_deposits}")
    )
    
    # Alt satır
    markup.add(
        types.InlineKeyboardButton("📢 DUYURU", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="back_menu")
    )
    
    text = f"""<b>👑 ADMIN PANEL</b>

Hoş geldin Admin!

👥 <b>Kullanıcı:</b> {total_users}
💰 <b>Normal Bakiye:</b> {format_money(total_balance)}
💰 <b>Reklam Bakiyesi:</b> {format_money(total_ad_balance)}
📥 <b>Bekleyen Depozit:</b> {pending_deposits}

İşlem seç:"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

def handle_admin_action(call):
    """Admin işlemlerini yönet"""
    user_id = call.from_user.id
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Yetkin yok!")
        return
    
    action = call.data
    
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
    
    elif action.startswith("admin_deposits_"):
        show_pending_deposits(user_id, call.message.message_id)
    
    elif action == "admin_broadcast":
        bot.edit_message_text(
            "Tüm kullanıcılara gönderilecek mesajı yaz:",
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_broadcast)
    
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
        
        cursor.execute("SELECT SUM(ad_balance) FROM users")
        total_ad_balance = cursor.fetchone()[0] or 0
        
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
        
        cursor.execute("SELECT COUNT(*) FROM conversions")
        total_conversions = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(bonus) FROM conversions")
        total_bonus = cursor.fetchone()[0] or 0
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
    
    text = f"""<b>📊 İSTATİSTİKLER</b>

👤 <b>Toplam Kullanıcı:</b> {total_users}
📢 <b>Kanala Katılan:</b> {channel_joined}
💰 <b>Toplam Normal Bakiye:</b> {format_money(total_balance)}
💰 <b>Toplam Reklam Bakiyesi:</b> {format_money(total_ad_balance)}
📈 <b>Toplam Kazanç:</b> {format_money(total_earned)}
🎯 <b>Toplam Görev:</b> {total_tasks}
📢 <b>Görev İlanı:</b> {total_task_ads}
🟢 <b>Aktif Görev:</b> {active_tasks}
🔄 <b>Bakiye Çevrimi:</b> {total_conversions}
🎁 <b>Toplam Bonus:</b> {format_money(total_bonus)}"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_pending_deposits(user_id, message_id):
    """Bekleyen depozitler"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT d.*, u.first_name 
                       FROM deposits d
                       JOIN users u ON d.user_id = u.user_id
                       WHERE d.status = 'pending'
                       ORDER BY d.created_at DESC LIMIT 10''')
        deposits = cursor.fetchall()
    
    if not deposits:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
        
        bot.edit_message_text(
            "<b>📥 BEKLEYEN DEPOZİTLER</b>\n\n✅ Bekleyen depozit yok.",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    text = "<b>📥 BEKLEYEN DEPOZİTLER</b>\n\n"
    
    for dep in deposits:
        text += f"""👤 {dep['first_name']}
🆔 ID: {dep['user_id']}
💰 Miktar: {format_money(dep['amount'])}
📅 Tarih: {dep['created_at'][:19]}
━━━━━━━━━━━━━━━━━━━━━━
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_panel"))
    
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

💰 Normal Bakiye: {format_money(user['balance'])}
💰 Reklam Bakiyesi: {format_money(user['ad_balance'])}
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

# ================= 14. FLASK SUNUCUSU =================
@app.route('/')
def home():
    return "🤖 Görev Yapsam Bot Aktif!"

@app.route('/health')
def health():
    return {"status": "ok"}

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
