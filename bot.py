"""
🤖 GÖREV YAPSAM BOTU v9.0 - TAM ÖZELLİKLİ
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
ZORUNLU_KANAL = "@GorevYapsam"

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
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Kampanyalar
        cursor.execute('''CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            budget REAL,
            spent REAL DEFAULT 0.0,
            clicks INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Admin işlemleri
        cursor.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_id INTEGER,
            details TEXT,
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
        member = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return member.status in ['member', 'administrator', 'creator']
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

def update_balance(user_id, amount, reason=""):
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
        
        # Log ekle
        if reason:
            cursor.execute('''INSERT INTO admin_logs 
                           (admin_id, action, target_id, details)
                           VALUES (?, ?, ?, ?)''',
                           (0, 'balance_update', user_id, f"{reason}: {amount}"))
        
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

def get_task(task_id):
    """Görev bilgisi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        return cursor.fetchone()

def add_admin_log(admin_id, action, target_id=None, details=""):
    """Admin log ekle"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO admin_logs 
                       (admin_id, action, target_id, details)
                       VALUES (?, ?, ?, ?)''',
                       (admin_id, action, target_id, details))
        conn.commit()

# ================= 4. ANA MENÜ =================
def show_main_menu(user_id, message_id=None):
    """Ana menü"""
    user = get_user(user_id)
    update_user_activity(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Ana butonlar
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("💰 " + format_money(user['balance']), callback_data="my_balance")
    )
    
    markup.add(
        types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_campaign"),
        types.InlineKeyboardButton("👥 REFERANS", callback_data="my_refs")
    )
    
    # Admin butonu
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 YÖNETİCİ PANELİ", callback_data="admin_panel"))
    
    text = f"""<b>🤖 GÖREV YAPSAM BOT</b>

🎯 <b>Hoş Geldin {user['first_name']}!</b>

💼 <b>Hesap Özeti:</b>
💰 <b>Bakiye:</b> {format_money(user['balance'])}
🎯 <b>Tamamlanan Görev:</b> {user['tasks_completed']}
👥 <b>Referans Kazancı:</b> {format_money(user['ref_earned'])}

🚀 <b>Slogan:</b> "Görev Yap, Para Kazan, Kampanya Oluştur!"

👇 <i>Hemen aşağıdaki seçeneklerden birini seçerek başla:</i>"""
    
    if message_id:
        bot.edit_message_text(text, user_id, message_id, reply_markup=markup)
    else:
        bot.send_message(user_id, text, reply_markup=markup)

# ================= 5. START KOMUTU =================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    username = message.from_user.username or ""
    
    # Referans kontrolü
    ref_used = False
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = int(param.replace('ref_', ''))
                if referrer_id != user_id:
                    # Kullanıcıyı önce oluştur
                    create_user(user_id, username, first_name)
                    # Referans ekle
                    if add_ref(referrer_id, user_id):
                        ref_used = True
            except:
                pass
    
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

🤖 <b>Görev Yapsam Botuna</b> hoş geldin!

📢 <b>Botu kullanmak için kanalımıza katılman gerekiyor:</b>
{ZORUNLU_KANAL}

✅ Katıldıktan sonra "✅ KATILDIM" butonuna tıklayarak devam edebilirsin.

🚀 <i>Görev yap, para kazan, kampanya oluştur!</i>""",
            reply_markup=markup
        )
        return
    
    # Kullanıcı oluştur
    create_user(user_id, username, first_name)
    
    # Hoşgeldin bonusu
    user = get_user(user_id)
    if user['tasks_completed'] == 0 and user['balance'] == 0:
        update_balance(user_id, 2.0, "Hoşgeldin bonusu")
    
    # Hoşgeldin mesajı
    welcome_msg = f"""<b>🎉 HOŞ GELDİN {first_name}!</b>

✅ <b>Başarıyla kayıt oldun!</b>

💰 <b>Hoşgeldin Bonusu:</b> 2.00 ₺ hesabına yüklendi.

🚀 <b>Şimdi yapabileceklerin:</b>
1. 🤖 <b>Görev Yap</b> - Hemen para kazanmaya başla
2. 📢 <b>Kampanya Oluştur</b> - Kendi reklamını yap
3. 👥 <b>Referans Getir</b> - Arkadaşlarını davet et, bonus kazan

👇 <i>Aşağıdaki menüden hemen başlayabilirsin!</i>"""
    
    if ref_used:
        welcome_msg += f"\n\n👥 <b>Referans Bonusu:</b> Arkadaşın 1.00 ₺ kazandı!"
    
    bot.send_message(user_id, welcome_msg)
    
    # Ana menü
    show_main_menu(user_id)

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = message.from_user.id
    
    text = """<b>ℹ️ YARDIM MERKEZİ</b>

🤖 <b>Görev Yapsam Bot - Komutlar ve Kullanım</b>

<b>Temel Komutlar:</b>
/start - Botu başlat ve kayıt ol
/help - Yardım menüsü
/menu - Ana menüyü göster

<b>Görev Tipleri:</b>
🤖 <b>Bot Görev:</b> 2.50 ₺ - Bota /start at
📢 <b>Kanal Görev:</b> 1.50 ₺ - Kanala katıl  
👥 <b>Grup Görev:</b> 1.00 ₺ - Gruba katıl

<b>Nasıl Çalışır?</b>
1. Görev yaparak para kazan
2. Kampanya oluşturarak reklam yap
3. Referans getirerek bonus kazan

<b>Kurallar:</b>
• @GorevYapsam kanalına katılım zorunlu
• Sahte işlem yasak
• Çoklu hesap yasak
• Grup görevleri için bot admin olmalı

<b>Slogan:</b> "Görev Yap, Para Kazan, Kampanya Oluştur!"

📞 <b>Destek:</b> @AlperenTHE"""
    
    bot.send_message(user_id, text)
    show_main_menu(user_id)

@bot.message_handler(commands=['menu'])
def menu_command(message):
    user_id = message.from_user.id
    show_main_menu(user_id)

# ================= 6. CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id) and call.data != "check_join":
        bot.answer_callback_query(call.id, "❌ Önce kanala katılmalısın!", show_alert=True)
        return
    
    update_user_activity(user_id)
    
    # Ana işlemler
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Başarıyla katıldın! Ana menüye yönlendiriliyorsun...")
        else:
            bot.answer_callback_query(call.id, "❌ Hala kanalda değilsin! Lütfen katıl ve tekrar dene.", show_alert=True)
    
    elif call.data == "do_task":
        show_task_types(user_id, call.message.message_id)
    
    elif call.data == "my_balance":
        show_my_balance(user_id, call.message.message_id)
    
    elif call.data == "create_campaign":
        create_campaign_menu(user_id, call.message.message_id)
    
    elif call.data == "my_refs":
        show_my_refs(user_id, call.message.message_id)
    
    elif call.data == "admin_panel":
        if user_id == ADMIN_ID:
            show_admin_panel(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Bu işlem için yetkiniz yok!", show_alert=True)
    
    elif call.data == "back_menu":
        show_main_menu(user_id, call.message.message_id)
    
    # Görev tipleri
    elif call.data in ["task_bot", "task_kanal", "task_grup"]:
        task_type = call.data.replace("task_", "")
        show_available_task(user_id, task_type, call.message.message_id)
    
    # Görev oluşturma
    elif call.data.startswith("create_"):
        task_type = call.data.replace("create_", "")
        ask_campaign_details(user_id, task_type, call.message.message_id)
    
    # Görev tamamlama
    elif call.data.startswith("complete_"):
        task_id = int(call.data.replace("complete_", ""))
        complete_user_task(user_id, task_id, call)
    
    # Admin işlemleri
    elif call.data.startswith("admin_"):
        handle_admin_action(call)

# ================= 7. GÖREV YAPMA SİSTEMİ =================
def show_task_types(user_id, message_id):
    """Görev tiplerini göster"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT GÖREV - 2.50 ₺", callback_data="task_bot"),
        types.InlineKeyboardButton("📢 KANAL GÖREV - 1.50 ₺", callback_data="task_kanal"),
        types.InlineKeyboardButton("👥 GRUP GÖREV - 1.00 ₺", callback_data="task_grup")
    )
    markup.add(types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu"))
    
    text = """<b>🎯 GÖREV YAP - PARA KAZAN</b>

🤖 <b>Görev Yapsam Botunda</b> görev yaparak para kazanmak çok kolay!

<b>Mevcut Görev Tipleri:</b>

🤖 <b>BOT GÖREV</b>
• Ödül: <b>2.50 ₺</b>
• Süre: 3 dakika
• Talimat: Bota /start komutu gönder

📢 <b>KANAL GÖREV</b>
• Ödül: <b>1.50 ₺</b>
• Süre: 5 dakika  
• Talimat: Kanala katıl ve 5 dakika kal

👥 <b>GRUP GÖREV</b>
• Ödül: <b>1.00 ₺</b>
• Süre: 5 dakika
• Talimat: Gruba katıl ve 5 dakika kal

👇 <i>Hangi görevi yapmak istiyorsun? Birini seç:</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_available_task(user_id, task_type, message_id):
    """Mevcut görevi göster"""
    tasks = get_active_tasks(task_type, 5)
    
    if not tasks:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 YENİLE", callback_data=f"task_{task_type}"),
            types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_campaign"),
            types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
        )
        
        type_names = {
            "bot": "🤖 Bot Görevleri",
            "kanal": "📢 Kanal Görevleri", 
            "grup": "👥 Grup Görevleri"
        }
        
        bot.edit_message_text(
            f"""<b>{type_names[task_type]}</b>

❌ <b>Şu anda aktif görev bulunmuyor.</b>

💡 <b>Öneri:</b> Kendi kampanyanı oluşturarak hemen görevlerin görünür olmasını sağlayabilirsin!

🚀 <i>Unutma: "Görev Yap, Para Kazan, Kampanya Oluştur!"</i>""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    task = tasks[0]
    show_single_task(user_id, task, message_id)

def show_single_task(user_id, task, message_id):
    """Tek görevi detaylı göster"""
    type_emojis = {"bot": "🤖", "kanal": "📢", "grup": "👥"}
    type_names = {"bot": "BOT GÖREV", "kanal": "KANAL GÖREV", "grup": "GRUP GÖREV"}
    
    reward = PRICES[task['task_type']]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 GÖREVE GİT", url=task['link']),
        types.InlineKeyboardButton("✅ TAMAMLADIM", callback_data=f"complete_{task['task_id']}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 YENİ GÖREV", callback_data=f"task_{task['task_type']}"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    text = f"""{type_emojis[task['task_type']]} <b>{type_names[task['task_type']]}</b>

📌 <b>Başlık:</b> {task['title']}
📝 <b>Açıklama:</b> {task['description']}
🔗 <b>Link:</b> {task['link']}

💰 <b>Ödül:</b> {format_money(reward)}
👁️ <b>Görüntülenme:</b> {task['views']} kez
📊 <b>Kampanya Sahibi Maliyeti:</b> {format_money(task['cost_per_view'])} / görüntü

⚠️ <b>Talimatlar:</b>
1. "GÖREVE GİT" butonuna tıkla
2. Görevi eksiksiz tamamla
   • Bot görevi: /start gönder
   • Kanal görevi: Kanala katıl
   • Grup görevi: Gruba katıl
3. 3-5 dakika bekleyerek görevin geçerliliğini sağla
4. "TAMAMLADIM" butonuna bas

⏱️ <b>Süre:</b> 5 dakika
🎯 <b>Not:</b> Sahte tamamlamalar tespit edilirse hesabın askıya alınır.

🚀 <i>Görevi tamamla, parayı kazan!</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def complete_user_task(user_id, task_id, call):
    """Görevi tamamla"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Görevi al
        cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            bot.answer_callback_query(call.id, "❌ Görev bulunamadı veya süresi doldu!", show_alert=True)
            return
        
        # Aynı görevi daha önce tamamladı mı?
        cursor.execute('''SELECT * FROM completions 
                       WHERE task_id = ? AND user_id = ?''',
                       (task_id, user_id))
        
        if cursor.fetchone():
            bot.answer_callback_query(call.id, "❌ Bu görevi zaten tamamladın!", show_alert=True)
            return
        
        # Görev sahibinin bakiyesini kontrol et
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (task['user_id'],))
        owner = cursor.fetchone()
        
        if not owner or owner['balance'] < task['cost_per_view']:
            cursor.execute("UPDATE tasks SET status = 'inactive' WHERE task_id = ?", (task_id,))
            conn.commit()
            bot.answer_callback_query(call.id, "❌ Kampanya sahibinin bakiyesi yetersiz!", show_alert=True)
            return
        
        reward = PRICES[task['task_type']]
        
        # Ödemeleri yap
        update_balance(user_id, reward, f"Görev tamamlama: {task_id}")
        
        # Görev sahibinden para düş
        cursor.execute('''UPDATE users SET 
                       balance = balance - ?
                       WHERE user_id = ?''', 
                       (task['cost_per_view'], task['user_id']))
        
        # İstatistikleri güncelle
        cursor.execute('''UPDATE users SET 
                       tasks_completed = tasks_completed + 1
                       WHERE user_id = ?''', (user_id,))
        
        cursor.execute('''UPDATE tasks SET 
                       views = views + 1,
                       cost_spent = cost_spent + ?,
                       updated_at = CURRENT_TIMESTAMP
                       WHERE task_id = ?''', 
                       (task['cost_per_view'], task_id))
        
        # Tamamlama kaydı ekle
        cursor.execute('''INSERT INTO completions 
                       (task_id, user_id, earned)
                       VALUES (?, ?, ?)''', 
                       (task_id, user_id, reward))
        
        # Bakiye bitmişse görevi kapat
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (task['user_id'],))
        new_balance = cursor.fetchone()['balance']
        
        if new_balance < task['cost_per_view']:
            cursor.execute("UPDATE tasks SET status = 'inactive' WHERE task_id = ?", (task_id,))
            # Kampanyayı da kapat
            cursor.execute('''UPDATE campaigns SET 
                           status = 'completed'
                           WHERE user_id = ? AND status = 'active' ''',
                           (task['user_id'],))
        
        conn.commit()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 YENİ GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("💰 BAKİYEMİ GÖR", callback_data="my_balance"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    bot.edit_message_text(
        f"""<b>✅ GÖREV BAŞARIYLA TAMAMLANDI!</b>

🎉 <b>Tebrikler {user['first_name']}!</b> Görevi eksiksiz tamamladın.

📊 <b>Detaylar:</b>
💰 <b>Kazandığın Miktar:</b> +{format_money(reward)}
💰 <b>Yeni Bakiyen:</b> {format_money(user['balance'])}
🎯 <b>Toplam Tamamlanan Görev:</b> {user['tasks_completed']}
📌 <b>Görev Başlığı:</b> {task['title']}

🚀 <b>Hemen yeni görev yapmaya devam edebilirsin!</b>

<i>Slogan: "Görev Yap, Para Kazan, Kampanya Oluştur!"</i>""",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, f"✅ +{format_money(reward)} kazandın! Tebrikler!")

# ================= 8. KAMPANYA OLUŞTURMA =================
def create_campaign_menu(user_id, message_id):
    """Kampanya oluşturma menüsü"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT KAMPANYASI (2.50 ₺/görüntü)", callback_data="create_bot"),
        types.InlineKeyboardButton("📢 KANAL KAMPANYASI (1.50 ₺/görüntü)", callback_data="create_kanal"),
        types.InlineKeyboardButton("👥 GRUP KAMPANYASI (1.00 ₺/görüntü)", callback_data="create_grup")
    )
    markup.add(types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu"))
    
    text = """<b>📢 KAMPANYA OLUŞTUR - REKLAM YAP</b>

🚀 <b>Kendi kampanyanı oluştur, görevlerin hemen görünsün!</b>

<b>Kampanya Tipleri:</b>

🤖 <b>BOT KAMPANYASI</b>
• Maliyet: <b>2.50 ₺ / görüntülenme</b>
• Min. Bakiye: 25 ₺ (10 görüntü)
• Hedef: Kullanıcılar botuna /start atar

📢 <b>KANAL KAMPANYASI</b>  
• Maliyet: <b>1.50 ₺ / görüntülenme</b>
• Min. Bakiye: 15 ₺ (10 görüntü)
• Hedef: Kullanıcılar kanalına katılır

👥 <b>GRUP KAMPANYASI</b>
• Maliyet: <b>1.00 ₺ / görüntülenme</b>
• Min. Bakiye: 10 ₺ (10 görüntü)
• Hedef: Kullanıcılar grubuna katılır
• Şart: Botun grupta admin olmalı

💰 <b>Mevcut Bakiyen:</b> {format_money(user['balance'])}

👇 <i>Hangi kampanyayı oluşturmak istiyorsun? Birini seç:</i>""".format(format_money=format_money)
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def ask_campaign_details(user_id, task_type, message_id):
    """Kampanya detaylarını iste"""
    cost = PRICES[task_type]
    min_needed = cost * 10
    
    type_names = {
        "bot": "🤖 Bot Kampanyası",
        "kanal": "📢 Kanal Kampanyası", 
        "grup": "👥 Grup Kampanyası"
    }
    
    requirements = {
        "bot": "• Bot linki geçerli olmalı\n• Bot /start komutuna cevap vermeli",
        "kanal": "• Kanal linki geçerli olmalı\n• Kanal public (herkese açık) olmalı",
        "grup": "• Grup linki geçerli olmalı\n• Grup public olmalı\n• Bot grupta admin olmalı"
    }
    
    bot.edit_message_text(
        f"""<b>{type_names[task_type]} Oluştur</b>

💰 <b>Görüntülenme Başına Maliyet:</b> {format_money(cost)}
💳 <b>Minimum Gerekli Bakiye:</b> {format_money(min_needed)}

⚠️ <b>Gereksinimler:</b>
{requirements[task_type]}

📝 <b>Kampanya bilgilerini şu formatta gönder:</b>

<code>Kampanya Başlığı
Link
Kampanya Açıklaması</code>

<b>Örnek Format:</b>
<code>Teknoloji Haberleri Kanalı
https://t.me/teknolojihaberleri
En güncel teknoloji haberleri için bize katılın! Her gün yeni içerikler!</code>

👇 <i>Lütfen kampanya bilgilerini yukarıdaki formatta gönder:</i>""",
        user_id,
        message_id
    )
    
    bot.register_next_step_handler_by_chat_id(
        user_id, 
        process_campaign_details, 
        task_type, 
        message_id
    )

def process_campaign_details(message, task_type, message_id):
    """Kampanya detaylarını işle"""
    user_id = message.from_user.id
    text = message.text.strip().split('\n')
    
    if len(text) < 3:
        bot.send_message(
            user_id,
            "❌ <b>Hatalı format!</b> Lütfen başlık, link ve açıklama olacak şekilde 3 satır gönder."
        )
        show_main_menu(user_id)
        return
    
    title = text[0].strip()
    link = text[1].strip()
    desc = text[2].strip()
    
    # Link kontrolü
    if not link.startswith('https://t.me/'):
        bot.send_message(
            user_id,
            "❌ <b>Geçersiz link!</b> Link https://t.me/ ile başlamalı."
        )
        show_main_menu(user_id)
        return
    
    cost = PRICES[task_type]
    min_needed = cost * 10
    
    # Bakiye kontrolü
    user = get_user(user_id)
    if user['balance'] < min_needed:
        bot.send_message(
            user_id,
            f"""❌ <b>Yetersiz bakiye!</b>

Kampanya oluşturmak için minimum {format_money(min_needed)} bakiyen olmalı.

💰 <b>Mevcut Bakiyen:</b> {format_money(user['balance'])}
💡 <b>Öneri:</b> Önce görev yaparak bakiye kazanabilirsin!"""
        )
        show_main_menu(user_id)
        return
    
    # Grup kampanyası için bot admin kontrolü
    if task_type == "grup":
        try:
            bot_id = bot.get_me().id
            chat_username = link.replace('https://t.me/', '').replace('@', '')
            
            try:
                chat = bot.get_chat('@' + chat_username)
                chat_member = bot.get_chat_member(chat.id, bot_id)
                
                if chat_member.status not in ['administrator', 'creator']:
                    bot.send_message(
                        user_id,
                        "❌ <b>Bot grupta admin değil!</b>\n\nLütfen önce botu gruba admin yapın, sonra tekrar deneyin."
                    )
                    show_main_menu(user_id)
                    return
            except Exception as e:
                bot.send_message(
                    user_id,
                    f"❌ <b>Grup kontrolü hatası!</b>\n\nHata: {str(e)}\n\nLütfen linkin doğru olduğundan ve botun grupta olduğundan emin olun."
                )
                show_main_menu(user_id)
                return
        except Exception as e:
            bot.send_message(
                user_id,
                f"❌ <b>Grup doğrulama hatası!</b>\n\nHata: {str(e)}"
            )
            show_main_menu(user_id)
            return
    
    # Kampanya ve görev oluştur
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Kampanya oluştur
        cursor.execute('''INSERT INTO campaigns 
                       (user_id, title, description, budget, status)
                       VALUES (?, ?, ?, ?, ?)''',
                       (user_id, title, desc, min_needed, 'active'))
        
        campaign_id = cursor.lastrowid
        
        # Görev oluştur
        cursor.execute('''INSERT INTO tasks 
                       (user_id, task_type, title, link, description, cost_per_view)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                       (user_id, task_type, title, link, desc, cost))
        
        task_id = cursor.lastrowid
        conn.commit()
    
    # Başarı mesajı
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREVLERE BAK", callback_data="do_task"),
        types.InlineKeyboardButton("📊 KAMPANYALARIM", callback_data="my_campaigns"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    type_emojis = {"bot": "🤖", "kanal": "📢", "grup": "👥"}
    
    bot.send_message(
        user_id,
        f"""<b>✅ KAMPANYA BAŞARIYLA OLUŞTURULDU!</b>

{type_emojis[task_type]} <b>Kampanya Detayları:</b>

📌 <b>Başlık:</b> {title}
🔗 <b>Link:</b> {link}
📝 <b>Açıklama:</b> {desc}

💰 <b>Maliyet Bilgileri:</b>
• Görüntülenme Başına: {format_money(cost)}
• Tahmini Maks. Görüntü: {int(user['balance'] / cost)}
• Toplam Bütçe: {format_money(min_needed)}

🆔 <b>Kampanya ID:</b> {campaign_id}
🆔 <b>Görev ID:</b> {task_id}

✅ <b>Kampanyanız aktif!</b> Kullanıcılar şimdi görevinizi görebilir ve tamamlayabilir.

⚠️ <b>Önemli Not:</b>
• Her tamamlanan görev için {format_money(cost)} bakiyenizden düşülecek
• Bakiye {format_money(cost)}'ın altına düştüğünde kampanya otomatik durdurulacak
• Kampanya performansını "Kampanyalarım" bölümünden takip edebilirsiniz

🚀 <i>Kampanyanız başarılı olsun! Unutmayın: "Görev Yap, Para Kazan, Kampanya Oluştur!"</i>""",
        reply_markup=markup
    )
    
    show_main_menu(user_id)

def show_my_campaigns(user_id, message_id):
    """Kullanıcının kampanyalarını göster"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM campaigns 
                       WHERE user_id = ? 
                       ORDER BY created_at DESC LIMIT 10''', (user_id,))
        campaigns = cursor.fetchall()
    
    if not campaigns:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_campaign"),
            types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
        )
        
        bot.edit_message_text(
            """<b>📊 KAMPANYALARIM</b>

❌ <b>Henüz kampanya oluşturmadınız.</b>

🚀 <b>İlk kampanyanızı oluşturarak:</b>
• Botunuzu, kanalınızı veya grubunuzu tanıtın
• Hedef kitlenize ulaşın
• Etkili reklam yapın

👇 <i>Hemen ilk kampanyanızı oluşturun:</i>""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    # İlk kampanyayı göster
    campaign = campaigns[0]
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT COUNT(*) as task_count, 
                       SUM(views) as total_views,
                       SUM(cost_spent) as total_spent
                       FROM tasks WHERE user_id = ?''', (user_id,))
        stats = cursor.fetchone()
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 YENİ KAMPANYA", callback_data="create_campaign"),
        types.InlineKeyboardButton("🔄 YENİLE", callback_data="my_campaigns"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    text = f"""<b>📊 KAMPANYA İSTATİSTİKLERİM</b>

📌 <b>Son Kampanya:</b> {campaign['title']}
📝 <b>Açıklama:</b> {campaign['description'][:100]}...
📊 <b>Durum:</b> {campaign['status']}
💰 <b>Bütçe:</b> {format_money(campaign['budget'])}
💸 <b>Harcanan:</b> {format_money(campaign['spent'])}
👁️ <b>Tıklanma:</b> {campaign['clicks']}

📈 <b>Genel İstatistikler:</b>
• Toplam Kampanya: {len(campaigns)}
• Toplam Görev: {stats['task_count'] or 0}
• Toplam Görüntülenme: {stats['total_views'] or 0}
• Toplam Harcama: {format_money(stats['total_spent'] or 0)}

🚀 <i>Kampanyalarınızı yönetin, hedef kitlenize ulaşın!</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 9. BAKİYE BİLGİSİ =================
def show_my_balance(user_id, message_id):
    """Bakiye bilgisi"""
    user = get_user(user_id)
    
    # Son 24 saatteki kazanç
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT SUM(earned) as daily_earned 
                       FROM completions 
                       WHERE user_id = ? AND 
                       created_at >= datetime('now', '-1 day')''',
                       (user_id,))
        daily = cursor.fetchone()
        
        cursor.execute('''SELECT COUNT(*) as active_campaigns 
                       FROM campaigns 
                       WHERE user_id = ? AND status = 'active' ''',
                       (user_id,))
        active = cursor.fetchone()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("📢 KAMPANYA OLUŞTUR", callback_data="create_campaign")
    )
    markup.add(
        types.InlineKeyboardButton("👥 REFERANS", callback_data="my_refs"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    text = f"""<b>💰 HESAP DETAYLARI</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
🆔 <b>ID:</b> <code>{user_id}</code>

💵 <b>Güncel Bakiye:</b> <b>{format_money(user['balance'])}</b>
📈 <b>Toplam Kazanç:</b> {format_money(user['total_earned'])}
📊 <b>24 Saatlik Kazanç:</b> {format_money(daily['daily_earned'] or 0)}

🎯 <b>Görev İstatistikleri:</b>
• Tamamlanan Görev: {user['tasks_completed']}
• Aktif Kampanya: {active['active_campaigns'] or 0}
• Referans Sayısı: {user['referrals']}
• Referans Kazancı: {format_money(user['ref_earned'])}

📅 <b>Kayıt Tarihi:</b> {user['joined_date']}
⏰ <b>Son Aktiflik:</b> {user['last_active']}

💡 <b>Bakiye Artırma Yolları:</b>
1. Görev yap (1-2.5 ₺)
2. Kampanya oluştur (gelir getirir)
3. Referans getir (1 ₺/kişi)
4. Günlük bonuslar (yakında!)

🚀 <i>Hemen görev yaparak para kazanmaya başla!</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 10. REFERANS SİSTEMİ =================
def show_my_refs(user_id, message_id):
    """Referans bilgisi"""
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    # Referans istatistikleri
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT COUNT(*) as total_refs,
                       SUM(earned) as total_earned
                       FROM referrals 
                       WHERE referrer_id = ?''',
                       (user_id,))
        ref_stats = cursor.fetchone()
        
        cursor.execute('''SELECT first_name, joined_date 
                       FROM users 
                       WHERE referred_by = ? 
                       ORDER BY joined_date DESC LIMIT 5''',
                       (user_id,))
        recent_refs = cursor.fetchall()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan%20Kampanya%20Oluştur!%20%40GorevYapsamBot%20ile%20hemen%20başla!"),
        types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu"))
    
    # Son referanslar listesi
    recent_list = ""
    if recent_refs:
        recent_list = "\n<b>📋 Son Referanslar:</b>\n"
        for ref in recent_refs:
            recent_list += f"• {ref['first_name']} - {ref['joined_date'][:10]}\n"
    
    text = f"""<b>👥 REFERANS SİSTEMİ</b>

💰 <b>Referans Başına Kazanç:</b> 1.00 ₺
👥 <b>Toplam Referans:</b> {ref_stats['total_refs'] or 0} kişi
📈 <b>Referans Kazancı:</b> {format_money(ref_stats['total_earned'] or 0)}

🔗 <b>Referans Linkin:</b>
<code>{ref_link}</code>

🎯 <b>Nasıl Çalışır?</b>
1. Yukarıdaki linki arkadaşlarına paylaş
2. Arkadaşların linke tıklasın
3. Onlar /start yaptığında otomatik olarak 1.00 ₺ hesabına yüklenecek
4. Arkadaşların da görev yaparak para kazanmaya başlayacak

🔥 <b>Bonus Sistemi:</b>
• 5 referansta: +2 ₺ bonus
• 10 referansta: +5 ₺ bonus  
• 25 referansta: +15 ₺ bonus
• 50 referansta: +35 ₺ bonus

📊 <b>Referans Hedefleri:</b>
{recent_list}

🚀 <i>Ne kadar çok referans, o kadar çok kazanç! Hemen paylaşmaya başla!</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

# ================= 11. ADMIN PANEL - TAM ÖZELLİKLİ =================
def show_admin_panel(user_id, message_id):
    """Admin panel ana sayfa"""
    if user_id != ADMIN_ID:
        return
    
    # İstatistikleri al
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Temel istatistikler
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= datetime('now', '-1 day')")
        active_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_earned) FROM users")
        total_earned = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'active'")
        active_tasks = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = cursor.fetchone()[0]
        
        # Bugünkü işlemler
        cursor.execute('''SELECT COUNT(*) as today_tasks, 
                       SUM(earned) as today_earned 
                       FROM completions 
                       WHERE created_at >= date('now')''')
        today_stats = cursor.fetchone()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Üst satır
    markup.add(
        types.InlineKeyboardButton("📊 DETAYLI İSTATİSTİK", callback_data="admin_stats_detailed"),
        types.InlineKeyboardButton("👤 KULLANICI YÖNETİMİ", callback_data="admin_user_manage")
    )
    
    # Orta satır
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE YÖNETİMİ", callback_data="admin_balance_manage"),
        types.InlineKeyboardButton("📢 KAMPANYA YÖNETİMİ", callback_data="admin_campaign_manage")
    )
    
    # Alt satır
    markup.add(
        types.InlineKeyboardButton("📝 SİSTEM AYARLARI", callback_data="admin_system_settings"),
        types.InlineKeyboardButton("📋 LOG KAYITLARI", callback_data="admin_logs_view")
    )
    
    # En alt
    markup.add(
        types.InlineKeyboardButton("📢 TOPLU DUYURU", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu")
    )
    
    text = f"""<b>👑 YÖNETİCİ PANELİ</b>

🎯 <b>Hoş Geldin Yönetici!</b>

📊 <b>Sistem Özeti:</b>
👥 <b>Toplam Kullanıcı:</b> {total_users}
🟢 <b>Bugün Aktif:</b> {active_today}
💰 <b>Toplam Bakiye:</b> {format_money(total_balance)}
📈 <b>Toplam Kazanç:</b> {format_money(total_earned)}

📢 <b>Aktif İçerik:</b>
🎯 <b>Aktif Görev:</b> {active_tasks}
📊 <b>Aktif Kampanya:</b> {active_campaigns}

📅 <b>Bugünkü İstatistik:</b>
• Tamamlanan Görev: {today_stats['today_tasks'] or 0}
• Bugünkü Kazanç: {format_money(today_stats['today_earned'] or 0)}

🛠️ <b>Yönetim Araçları:</b>
Aşağıdaki butonlardan yapmak istediğiniz işlemi seçin.

⏰ <b>Son Güncelleme:</b> {datetime.now().strftime('%H:%M:%S')}"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def handle_admin_action(call):
    """Admin işlemlerini yönet"""
    user_id = call.from_user.id
    action = call.data
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Yetkiniz yok!")
        return
    
    if action == "admin_stats_detailed":
        show_detailed_stats(user_id, call.message.message_id)
    
    elif action == "admin_user_manage":
        show_user_management(user_id, call.message.message_id)
    
    elif action == "admin_balance_manage":
        show_balance_management(user_id, call.message.message_id)
    
    elif action == "admin_campaign_manage":
        show_campaign_management(user_id, call.message.message_id)
    
    elif action == "admin_system_settings":
        show_system_settings(user_id, call.message.message_id)
    
    elif action == "admin_logs_view":
        show_admin_logs(user_id, call.message.message_id)
    
    elif action == "admin_broadcast":
        start_broadcast(user_id, call.message.message_id)
    
    elif action == "admin_back":
        show_admin_panel(user_id, call.message.message_id)

def show_detailed_stats(user_id, message_id):
    """Detaylı istatistikler"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Kullanıcı istatistikleri
        cursor.execute('''SELECT 
                       COUNT(*) as total,
                       SUM(balance) as total_balance,
                       AVG(balance) as avg_balance,
                       SUM(total_earned) as total_earned,
                       SUM(tasks_completed) as total_tasks,
                       SUM(referrals) as total_refs
                       FROM users''')
        user_stats = cursor.fetchone()
        
        # Görev istatistikleri
        cursor.execute('''SELECT 
                       COUNT(*) as total_tasks,
                       SUM(views) as total_views,
                       SUM(cost_spent) as total_spent,
                       AVG(cost_per_view) as avg_cost
                       FROM tasks''')
        task_stats = cursor.fetchone()
        
        # Günlük büyüme
        cursor.execute('''SELECT 
                       COUNT(*) as new_today 
                       FROM users 
                       WHERE joined_date >= date('now')''')
        new_today = cursor.fetchone()[0]
        
        # Aktiflik oranı
        cursor.execute('''SELECT 
                       COUNT(*) as active_week 
                       FROM users 
                       WHERE last_active >= datetime('now', '-7 days')''')
        active_week = cursor.fetchone()[0]
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back"))
    
    text = f"""<b>📊 DETAYLI SİSTEM İSTATİSTİKLERİ</b>

👥 <b>KULLANICI İSTATİSTİKLERİ:</b>
• Toplam Kullanıcı: {user_stats['total']}
• Bugün Kayıtlı: {new_today}
• Son 7 Gün Aktif: {active_week}
• Ortalama Bakiye: {format_money(user_stats['avg_balance'] or 0)}

💰 <b>FİNANSAL İSTATİSTİKLER:</b>
• Toplam Sistem Bakiyesi: {format_money(user_stats['total_balance'] or 0)}
• Toplam Kazanç: {format_money(user_stats['total_earned'] or 0)}
• Toplam Referans Kazancı: {format_money((user_stats['total_refs'] or 0) * 1.0)}

🎯 <b>GÖREV İSTATİSTİKLERİ:</b>
• Toplam Görev İlanı: {task_stats['total_tasks'] or 0}
• Toplam Görüntülenme: {task_stats['total_views'] or 0}
• Toplam Harcama: {format_money(task_stats['total_spent'] or 0)}
• Ortalama Maliyet: {format_money(task_stats['avg_cost'] or 0)}

📈 <b>PERFORMANS METRİKLERİ:</b>
• Toplam Tamamlanan Görev: {user_stats['total_tasks'] or 0}
• Ortalama Görev/Kullanıcı: {(user_stats['total_tasks'] or 0) / max(user_stats['total'], 1):.2f}
• Aktiflik Oranı: {(active_week / max(user_stats['total'], 1) * 100):.1f}%

⏰ <b>Son Güncelleme:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_user_management(user_id, message_id):
    """Kullanıcı yönetimi"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 KULLANICI ARA", callback_data="admin_user_search"),
        types.InlineKeyboardButton("📋 SON KAYITLAR", callback_data="admin_recent_users")
    )
    markup.add(
        types.InlineKeyboardButton("📊 EN AKTİFLER", callback_data="admin_top_active"),
        types.InlineKeyboardButton("💰 EN ZENGİNLER", callback_data="admin_top_balance")
    )
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back"))
    
    text = """<b>👤 KULLANICI YÖNETİM PANELİ</b>

📋 <b>Kullanıcı yönetimi araçları:</b>

1. <b>Kullanıcı Ara:</b> ID veya kullanıcı adı ile kullanıcı bul
2. <b>Son Kayıtlar:</b> Son kayıt olan kullanıcıları listele
3. <b>En Aktifler:</b> En aktif kullanıcıları göster
4. <b>En Zenginler:</b> En yüksek bakiyeli kullanıcılar

👇 <i>Yapmak istediğiniz işlemi seçin:</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_user_search")
def ask_user_search(call):
    """Kullanıcı arama iste"""
    user_id = call.from_user.id
    
    bot.edit_message_text(
        "🔍 <b>Kullanıcı Arama</b>\n\nKullanıcı ID'si veya kullanıcı adı girin:\n\nÖrnek: <code>123456789</code> veya <code>@kullaniciadi</code>",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.register_next_step_handler_by_chat_id(user_id, process_user_search)

def process_user_search(message):
    """Kullanıcı arama işlemi"""
    admin_id = message.from_user.id
    query = message.text.strip()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # ID ile ara
        if query.isdigit():
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (int(query),))
            user = cursor.fetchone()
        # Username ile ara
        elif query.startswith('@'):
            username = query[1:]
            cursor.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{username}%",))
            user = cursor.fetchone()
        else:
            # İsim ile ara
            cursor.execute("SELECT * FROM users WHERE first_name LIKE ?", (f"%{query}%",))
            user = cursor.fetchone()
    
    if not user:
        bot.send_message(admin_id, "❌ Kullanıcı bulunamadı!")
        show_admin_panel(admin_id, None)
        return
    
    # Kullanıcı bilgilerini göster
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE EKLE/ÇIKAR", callback_data=f"admin_balance_user_{user['user_id']}"),
        types.InlineKeyboardButton("📊 İSTATİSTİK", callback_data=f"admin_stats_user_{user['user_id']}")
    )
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_user_manage"))
    
    # Son aktiflik hesapla
    last_active = user['last_active'] or user['joined_date']
    
    text = f"""<b>👤 KULLANICI DETAYLARI</b>

🆔 <b>ID:</b> <code>{user['user_id']}</code>
👤 <b>Ad:</b> {user['first_name']}
📛 <b>Kullanıcı Adı:</b> {user['username'] or 'Belirtilmemiş'}

💰 <b>Bakiye:</b> {format_money(user['balance'])}
📈 <b>Toplam Kazanç:</b> {format_money(user['total_earned'])}
🎯 <b>Tamamlanan Görev:</b> {user['tasks_completed']}
👥 <b>Referans:</b> {user['referrals']}

📅 <b>Kayıt Tarihi:</b> {user['joined_date']}
⏰ <b>Son Aktiflik:</b> {last_active}

💼 <b>Durum:</b> {'🟢 Aktif' if user['balance'] > 0 else '🔴 Pasif'}"""
    
    bot.send_message(admin_id, text, reply_markup=markup)
    show_admin_panel(admin_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_balance_user_"))
def balance_user_management(call):
    """Kullanıcı bakiye yönetimi"""
    admin_id = call.from_user.id
    target_id = int(call.data.replace("admin_balance_user_", ""))
    
    bot.edit_message_text(
        f"💰 <b>Bakiye Yönetimi</b>\n\nKullanıcı ID: <code>{target_id}</code>\n\nEkleme veya çıkarma için miktarı girin:\n\nÖrnek: <code>+10.50</code> (ekle)\nÖrnek: <code>-5.00</code> (çıkar)",
        call.message.chat.id,
        call.message.message_id
    )
    
    bot.register_next_step_handler_by_chat_id(admin_id, process_balance_change, target_id)

def process_balance_change(message, target_id):
    """Bakiye değişikliği işlemi"""
    admin_id = message.from_user.id
    amount_text = message.text.strip()
    
    try:
        if amount_text.startswith('+'):
            amount = float(amount_text[1:])
            operation = "eklendi"
        elif amount_text.startswith('-'):
            amount = -float(amount_text[1:])
            operation = "çıkarıldı"
        else:
            amount = float(amount_text)
            operation = "güncellendi" if amount >= 0 else "çıkarıldı"
        
        user = get_user(target_id)
        if not user:
            bot.send_message(admin_id, "❌ Kullanıcı bulunamadı!")
            return
        
        update_balance(target_id, amount, f"Admin bakiye {operation}")
        add_admin_log(admin_id, "balance_update", target_id, f"{amount} {operation}")
        
        new_balance = get_user(target_id)['balance']
        
        # Kullanıcıya bildir
        try:
            bot.send_message(
                target_id,
                f"""<b>💰 BAKİYE GÜNCELLEMESİ</b>

Yönetici tarafından hesabınıza işlem yapıldı:

💵 <b>İşlem:</b> {format_money(amount)} {operation}
💰 <b>Yeni Bakiye:</b> {format_money(new_balance)}
⏰ <b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📞 <b>Destek:</b> @AlperenTHE"""
            )
        except:
            pass
        
        bot.send_message(
            admin_id,
            f"""✅ <b>Bakiye Güncellendi!</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
🆔 <b>ID:</b> {target_id}
💰 <b>İşlem:</b> {format_money(amount)} {operation}
💰 <b>Yeni Bakiye:</b> {format_money(new_balance)}

✅ <b>İşlem başarıyla kaydedildi.</b>"""
        )
        
    except ValueError:
        bot.send_message(admin_id, "❌ Geçersiz miktar! Lütfen sayısal bir değer girin.")
    
    show_admin_panel(admin_id, None)

def show_balance_management(user_id, message_id):
    """Bakiye yönetimi paneli"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(balance) as total_balance FROM users")
        total = cursor.fetchone()[0] or 0
        
        cursor.execute('''SELECT COUNT(*) as rich_users 
                       FROM users WHERE balance >= 50''')
        rich = cursor.fetchone()[0]
        
        cursor.execute('''SELECT COUNT(*) as zero_balance 
                       FROM users WHERE balance = 0''')
        zero = cursor.fetchone()[0]
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 BAKİYE DAĞILIMI", callback_data="admin_balance_dist"),
        types.InlineKeyboardButton("💰 TOPLU BAKİYE EKLE", callback_data="admin_bulk_balance")
    )
    markup.add(
        types.InlineKeyboardButton("📈 GÜNLÜK KAZANÇ", callback_data="admin_daily_earnings"),
        types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back")
    )
    
    text = f"""<b>💰 BAKİYE YÖNETİM PANELİ</b>

📊 <b>Sistem Bakiyesi Özeti:</b>
💰 <b>Toplam Bakiye:</b> {format_money(total)}
👥 <b>50+ ₺ Bakiye:</b> {rich} kullanıcı
🔴 <b>0 Bakiye:</b> {zero} kullanıcı

🛠️ <b>Bakiye Yönetimi Araçları:</b>

1. <b>Bakiye Dağılımı:</b> Kullanıcı bakiyelerinin dağılımını gör
2. <b>Toplu Bakiye Ekle:</b> Birden fazla kullanıcıya toplu bakiye ekle
3. <b>Günlük Kazanç:</b> Günlük kazanç istatistiklerini gör

⚠️ <b>Not:</b> Tüm bakiye işlemleri loglanır ve geri alınamaz.

👇 <i>Yapmak istediğiniz işlemi seçin:</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_campaign_management(user_id, message_id):
    """Kampanya yönetimi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM campaigns")
        total_campaigns = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(budget) FROM campaigns")
        total_budget = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(spent) FROM campaigns")
        total_spent = cursor.fetchone()[0] or 0
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📋 AKTİF KAMPANYALAR", callback_data="admin_active_campaigns"),
        types.InlineKeyboardButton("📊 KAMPANYA İSTATİSTİK", callback_data="admin_campaign_stats")
    )
    markup.add(
        types.InlineKeyboardButton("🔍 KAMPANYA ARA", callback_data="admin_search_campaign"),
        types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back")
    )
    
    text = f"""<b>📢 KAMPANYA YÖNETİM PANELİ</b>

📊 <b>Kampanya Özeti:</b>
📋 <b>Toplam Kampanya:</b> {total_campaigns}
🟢 <b>Aktif Kampanya:</b> {active_campaigns}
💰 <b>Toplam Bütçe:</b> {format_money(total_budget)}
💸 <b>Toplam Harcama:</b> {format_money(total_spent)}
📈 <b>Kullanım Oranı:</b> {(total_spent / total_budget * 100) if total_budget > 0 else 0:.1f}%

🛠️ <b>Kampanya Yönetimi Araçları:</b>

1. <b>Aktif Kampanyalar:</b> Şu anda aktif olan kampanyaları listele
2. <b>Kampanya İstatistik:</b> Detaylı kampanya performans raporu
3. <b>Kampanya Ara:</b> Kampanya ID veya başlığı ile arama yap

👇 <i>Yapmak istediğiniz işlemi seçin:</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_system_settings(user_id, message_id):
    """Sistem ayarları"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 FİYAT AYARLARI", callback_data="admin_price_settings"),
        types.InlineKeyboardButton("⚙️ SİSTEM AYARLARI", callback_data="admin_system_config")
    )
    markup.add(
        types.InlineKeyboardButton("📢 KANAL AYARLARI", callback_data="admin_channel_settings"),
        types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back")
    )
    
    text = """<b>⚙️ SİSTEM AYARLARI PANELİ</b>

🛠️ <b>Sistem Konfigürasyonu:</b>

1. <b>Fiyat Ayarları:</b> Görev fiyatlarını düzenle
   - Bot Görevi: 2.50 ₺
   - Kanal Görevi: 1.50 ₺
   - Grup Görevi: 1.00 ₺

2. <b>Sistem Ayarları:</b> Genel sistem ayarları
   - Hoşgeldin bonusu
   - Referans bonusu
   - Minimum bakiye limitleri

3. <b>Kanal Ayarları:</b> Zorunlu kanal ayarları
   - Kanal ID
   - Kontrol mekanizması

⚠️ <b>Uyarı:</b> Bu ayarlar sistemin çalışmasını doğrudan etkiler. Dikkatli değiştirin.

👇 <i>Yapmak istediğiniz ayarı seçin:</i>"""
    
    bot.edit_message_text(text, user_id, message_id, reply_markup=markup)

def show_admin_logs(user_id, message_id):
    """Admin logları"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM admin_logs 
                       ORDER BY created_at DESC 
                       LIMIT 20''')
        logs = cursor.fetchall()
    
    if not logs:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back"))
        
        bot.edit_message_text(
            "<b>📋 LOG KAYITLARI</b>\n\n❌ Henüz log kaydı bulunmuyor.",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    log_text = "<b>📋 SON 20 ADMIN LOG KAYDI</b>\n\n"
    
    for log in logs[:10]:  # İlk 10'u göster
        action_map = {
            "balance_update": "💰 Bakiye Güncelleme",
            "user_created": "👤 Kullanıcı Oluşturma",
            "task_completed": "✅ Görev Tamamlama",
            "campaign_created": "📢 Kampanya Oluşturma"
        }
        
        action_text = action_map.get(log['action'], log['action'])
        timestamp = log['created_at'][:19] if log['created_at'] else "N/A"
        
        log_text += f"📅 {timestamp}\n"
        log_text += f"🔧 {action_text}\n"
        log_text += f"👤 Admin ID: {log['admin_id']}\n"
        
        if log['target_id']:
            log_text += f"🎯 Hedef ID: {log['target_id']}\n"
        
        if log['details']:
            log_text += f"📝 Detay: {log['details'][:50]}...\n"
        
        log_text += "─" * 30 + "\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 GERİ", callback_data="admin_back"))
    
    bot.edit_message_text(log_text, user_id, message_id, reply_markup=markup)

def start_broadcast(user_id, message_id):
    """Toplu duyuru başlat"""
    bot.edit_message_text(
        """<b>📢 TOPLU DUYURU PANELİ</b>

Tüm kullanıcılara göndermek istediğiniz mesajı yazın:

⚠️ <b>Dikkat:</b>
• Mesaj HTML formatında gönderilecek
• Tüm aktif kullanıcılara ulaşacak
• İşlem biraz zaman alabilir
• İptal edilemez

✍️ <b>Mesajınızı yazın:</b>""",
        user_id,
        message_id
    )
    
    bot.register_next_step_handler_by_chat_id(user_id, process_broadcast_message)

def process_broadcast_message(message):
    """Toplu duyuru işlemi"""
    admin_id = message.from_user.id
    broadcast_text = message.text
    
    # Kullanıcıları al
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    
    total = len(users)
    success = 0
    failed = 0
    
    bot.send_message(admin_id, f"📢 <b>Duyuru başlatılıyor...</b>\n\nToplam {total} kullanıcıya gönderilecek.")
    
    for i, user in enumerate(users):
        try:
            bot.send_message(
                user[0],
                f"""<b>📢 SİSTEM DUYURUSU</b>

{broadcast_text}

⏰ <b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📞 <b>Destek:</b> @AlperenTHE

🚀 <i>Görev Yap, Para Kazan, Kampanya Oluştur!</i>"""
            )
            success += 1
            
            # Her 50 mesajda bir dur
            if (i + 1) % 50 == 0:
                time.sleep(1)
            
        except Exception as e:
            failed += 1
        
        # İlerlemeyi göster
        if (i + 1) % 100 == 0 or (i + 1) == total:
            try:
                bot.edit_message_text(
                    f"""📢 <b>Duyuru Devam Ediyor...</b>

✅ Başarılı: {success}
❌ Başarısız: {failed}
📊 İlerleme: {i + 1}/{total} ({((i + 1) / total * 100):.1f}%)

⏰ Tahmini kalan: {(total - i - 1) * 0.1:.1f} saniye""",
                    admin_id,
                    message.message_id + 1
                )
            except:
                pass
    
    # Log ekle
    add_admin_log(admin_id, "broadcast", None, f"Toplu duyuru: {success}/{total}")
    
    # Sonuç mesajı
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 YÖNETİCİ PANELİ", callback_data="admin_back"))
    
    bot.send_message(
        admin_id,
        f"""✅ <b>DUYURU TAMAMLANDI!</b>

📊 <b>Sonuçlar:</b>
✅ <b>Başarılı:</b> {success} kullanıcı
❌ <b>Başarısız:</b> {failed} kullanıcı
📈 <b>Başarı Oranı:</b> {(success / total * 100):.1f}%

⏰ <b>Süre:</b> Yaklaşık {total * 0.1:.1f} saniye
📅 <b>Tarih:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ <b>Duyuru başarıyla tamamlandı.</b>""",
        reply_markup=markup
    )

# ================= 12. FLASK SERVER =================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Görev Yapsam Bot</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                margin-top: 50px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }
            h1 {
                font-size: 3em;
                margin-bottom: 20px;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            }
            .emoji {
                font-size: 4em;
                margin: 20px 0;
            }
            .status {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
            }
            .button {
                display: inline-block;
                background: white;
                color: #667eea;
                padding: 15px 30px;
                border-radius: 50px;
                text-decoration: none;
                font-weight: bold;
                margin: 10px;
                transition: all 0.3s ease;
            }
            .button:hover {
                transform: translateY(-3px);
                box-shadow: 0 10px 20px rgba(0, 0, 0, 0.2);
            }
            .stats {
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                margin: 30px 0;
            }
            .stat-item {
                background: rgba(255, 255, 255, 0.15);
                padding: 15px;
                border-radius: 10px;
                margin: 10px;
                flex: 1;
                min-width: 150px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🤖</div>
            <h1>Görev Yapsam Bot</h1>
            <div class="status">
                <h2>🚀 Sistem Aktif ve Çalışıyor!</h2>
                <p>Telegram botumuz şu anda aktif bir şekilde çalışmaktadır.</p>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <h3>🎯 Slogan</h3>
                    <p>Görev Yap, Para Kazan, Kampanya Oluştur!</p>
                </div>
                <div class="stat-item">
                    <h3>📢 Kanal</h3>
                    <p>@GorevYapsam</p>
                </div>
                <div class="stat-item">
                    <h3>👤 Developer</h3>
                    <p>@AlperenTHE</p>
                </div>
            </div>
            
            <a href="https://t.me/GorevYapsamBot" class="button">🤖 Botu Başlat</a>
            <a href="https://t.me/GorevYapsam" class="button">📢 Kanalımız</a>
            
            <p style="margin-top: 30px; opacity: 0.8;">
                © 2024 Görev Yapsam Bot - Tüm hakları saklıdır.
            </p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'active'")
        task_count = cursor.fetchone()[0]
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "users": user_count,
        "active_tasks": task_count,
        "service": "GorevYapsamBot"
    }

@app.route('/stats')
def stats_api():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance) FROM users")
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(total_earned) FROM users")
        total_earned = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'active'")
        active_tasks = cursor.fetchone()[0]
    
    return {
        "total_users": total_users,
        "total_balance": float(total_balance),
        "total_earned": float(total_earned),
        "active_tasks": active_tasks,
        "timestamp": datetime.now().isoformat()
    }

# ================= 13. BOT ÇALIŞTIRMA =================
def run_bot():
    print("🤖 Görev Yapsam Bot başlatılıyor...")
    print("🚀 Slogan: 'Görev Yap, Para Kazan, Kampanya Oluştur!'")
    print(f"📢 Zorunlu Kanal: {ZORUNLU_KANAL}")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    
    try:
        # Webhook'u temizle
        bot.remove_webhook()
        time.sleep(1)
        
        # Botu başlat
        print("🔄 Bot polling başlatılıyor...")
        bot.polling(
            none_stop=True,
            interval=3,
            timeout=60,
            skip_pending=True
        )
        
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
        print("🔄 10 saniye bekleniyor ve yeniden deneniyor...")
        time.sleep(10)
        run_bot()

def run_flask():
    print("🌐 Flask sunucusu başlatılıyor...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Flask thread (web arayüzü için)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Ana thread'de botu çalıştır
    run_bot()
