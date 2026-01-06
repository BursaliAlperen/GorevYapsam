"""
🤖 GÖREV YAPSAM BOTU v4.1 - FIXED
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
from flask import Flask
import random
import os

# ================= 1. KONFİGÜRASYON =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877 
ADMIN_USER = "@AlperenTHE"
ZORUNLU_KANAL = "@GorevYapsam"

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# ================= 2. VERİTABANI =================
def get_db():
    conn = sqlite3.connect('gorev_bot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            total_earned REAL DEFAULT 0.0,
            tasks_completed INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            ref_earned REAL DEFAULT 0.0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            reward REAL DEFAULT 1.0,
            task_level TEXT DEFAULT 'medium',
            is_active INTEGER DEFAULT 1
        )''')
        conn.commit()

init_db()

# ================= 3. TEMEL FONKSİYONLAR =================
def format_number(num):
    return f"{float(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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

def update_balance(user_id, amount):
    with get_db() as conn:
        cursor = conn.cursor()
        if amount > 0:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           total_earned = total_earned + ?
                           WHERE user_id = ?''', (amount, amount, user_id))
        else:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?
                           WHERE user_id = ?''', (amount, user_id))
        conn.commit()

# ================= 4. ANA MENÜ =================
def show_main_menu(user_id):
    """Sadece inline keyboard ile ana menü göster"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görevler", callback_data="menu_tasks"),
        types.InlineKeyboardButton("💰 Bakiye", callback_data="menu_balance"),
        types.InlineKeyboardButton("👥 Referans", callback_data="menu_referrals"),
        types.InlineKeyboardButton("🎁 Günlük Bonus", callback_data="menu_daily"),
        types.InlineKeyboardButton("📊 İstatistik", callback_data="menu_stats"),
        types.InlineKeyboardButton("ℹ️ Yardım", callback_data="menu_help")
    )
    
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 Admin", callback_data="menu_admin"))
    
    text = f"""🏠 <b>GÖREV YAPSAM BOTU</b>

👋 Hoş geldin <b>{user['first_name'] if user else 'Kullanıcı'}</b>!

💰 <b>Bakiye:</b> {format_number(user['balance']) if user else '0.00'}₺
🎯 <b>Görevler:</b> {user['tasks_completed'] if user else 0}
👥 <b>Referans:</b> {user['ref_count'] if user else 0}

🚀 <b>Yeni Özellikler:</b>
• Referans başına 1₺
• Günlük 2₺ bonus
• 3 seviyeli görev

👇 Aşağıdaki butonlardan birini seç:"""
    
    bot.send_message(user_id, text, reply_markup=markup)

# ================= 5. START KOMUTU =================
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
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
            f"""👋 <b>Merhaba {first_name}!</b>

Botu kullanmak için kanalımıza katılmalısın:

📢 <b>{ZORUNLU_KANAL}</b>

Katıldıktan sonra <b>✅ KATILDIM</b> butonuna bas.""",
            reply_markup=markup
        )
        return
    
    # Kullanıcı kaydı
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute('''INSERT INTO users 
                           (user_id, username, first_name, balance) 
                           VALUES (?, ?, ?, 2.0)''', 
                           (user_id, username, first_name))
            conn.commit()
            
            # Hoşgeldin bonusu
            update_balance(user_id, 2.0)
            
            bot.send_message(
                user_id,
                f"""🎉 <b>HOŞ GELDİN {first_name}!</b>

✅ Kaydın başarıyla oluşturuldu!
💰 <b>Hoşgeldin bonusu: 2₺</b> hesabına yüklendi.

Şimdi aşağıdaki menüden başlayabilirsin!"""
            )
    
    # Ana menüyü göster
    show_main_menu(user_id)

# ================= 6. CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id)
            bot.answer_callback_query(call.id, "✅ Teşekkürler! Ana menüye yönlendiriliyorsun...")
        else:
            bot.answer_callback_query(call.id, "❌ Hala kanalda değilsin!", show_alert=True)
    
    elif call.data == "menu_tasks":
        show_task_levels(user_id, call.message.message_id)
    
    elif call.data == "menu_balance":
        show_balance(user_id, call.message.message_id)
    
    elif call.data == "menu_referrals":
        show_referrals(user_id, call.message.message_id)
    
    elif call.data == "menu_daily":
        daily_bonus(user_id, call.message.message_id)
    
    elif call.data == "menu_stats":
        show_stats(user_id, call.message.message_id)
    
    elif call.data == "menu_help":
        show_help(user_id, call.message.message_id)
    
    elif call.data == "menu_admin":
        if user_id == ADMIN_ID:
            admin_panel(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Yetkin yok!", show_alert=True)
    
    elif call.data.startswith("task_level_"):
        level = call.data.replace("task_level_", "")
        show_random_task(user_id, level, call.message.message_id)
    
    elif call.data == "main_menu":
        show_main_menu(user_id)

def show_task_levels(user_id, message_id=None):
    """Görev seviyelerini göster"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🐢 YAVAŞ (0.50-1.00₺)", callback_data="task_level_slow"),
        types.InlineKeyboardButton("🚀 ORTA (1.00-2.50₺)", callback_data="task_level_medium"),
        types.InlineKeyboardButton("⚡ HIZLI (2.50-5.00₺)", callback_data="task_level_fast"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = """🎯 <b>GÖREV SEVİYELERİ</b>

Hangi seviyede görev yapmak istersin?

🐢 <b>YAVAŞ</b>
• Ödül: 0.50-1.00₺
• Süre: 5 dakika
• Kolay görevler

🚀 <b>ORTA</b>
• Ödül: 1.00-2.50₺
• Süre: 3 dakika
• Normal görevler

⚡ <b>HIZLI</b>
• Ödül: 2.50-5.00₺
• Süre: 1 dakika
• Zor görevler

👇 Bir seviye seç:"""
    
    if message_id:
        bot.edit_message_text(
            text,
            user_id,
            message_id,
            reply_markup=markup
        )
    else:
        bot.send_message(user_id, text, reply_markup=markup)

def show_random_task(user_id, level, message_id):
    """Rastgele görev göster"""
    reward_range = {
        'slow': (0.50, 1.00),
        'medium': (1.00, 2.50),
        'fast': (2.50, 5.00)
    }
    
    min_reward, max_reward = reward_range.get(level, (1.00, 2.50))
    reward = round(random.uniform(min_reward, max_reward), 2)
    
    level_names = {
        'slow': '🐢 YAVAŞ',
        'medium': '🚀 ORTA',
        'fast': '⚡ HIZLI'
    }
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 KANALA GİT", url="https://t.me/GorevYapsam"),
        types.InlineKeyboardButton("✅ TAMAMLADIM", callback_data=f"complete_{reward}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 YENİ GÖREV", callback_data=f"task_level_{level}"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = f"""{level_names[level]} <b>GÖREV</b>

📌 <b>@GorevYapsam Kanalına Katıl</b>

📝 <b>Açıklama:</b>
@GorevYapsam kanalına katıl ve 5 dakika kal.

💰 <b>Ödül:</b> {format_number(reward)}₺
⏱️ <b>Süre:</b> 5 dakika
🎯 <b>Seviye:</b> {level_names[level]}

⚠️ <b>Talimatlar:</b>
1. Yukarıdaki butona tıkla
2. Kanala katıl
3. 5 dakika bekle
4. Tamamladım butonuna bas"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("complete_"))
def complete_task(call):
    user_id = call.from_user.id
    reward = float(call.data.replace("complete_", ""))
    
    # Kanal kontrolü
    if not kanal_kontrol(user_id):
        bot.answer_callback_query(call.id, "❌ Önce kanala katılmalısın!", show_alert=True)
        return
    
    # Görevi tamamla
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET 
                       balance = balance + ?,
                       total_earned = total_earned + ?,
                       tasks_completed = tasks_completed + 1
                       WHERE user_id = ?''', 
                       (reward, reward, user_id))
        conn.commit()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 YENİ GÖREV", callback_data="menu_tasks"),
        types.InlineKeyboardButton("💰 BAKİYEM", callback_data="menu_balance")
    )
    
    bot.edit_message_text(
        f"""✅ <b>GÖREV TAMAMLANDI!</b>

🎉 Tebrikler! Görevi başarıyla tamamladın.

💰 <b>Kazanç:</b> +{format_number(reward)}₺
💰 <b>Yeni Bakiye:</b> {format_number(user['balance'])}₺
🎯 <b>Toplam Görev:</b> {user['tasks_completed']}

🚀 Hemen yeni görev yap!""",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, f"✅ +{format_number(reward)}₺ kazandın!")

def show_balance(user_id, message_id):
    """Bakiye bilgilerini göster"""
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="menu_tasks"),
        types.InlineKeyboardButton("👥 Referans", callback_data="menu_referrals"),
        types.InlineKeyboardButton("🎁 Günlük Bonus", callback_data="menu_daily"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = f"""💰 <b>BAKİYE DETAYLARI</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
🆔 <b>ID:</b> <code>{user_id}</code>

💵 <b>Cari Bakiye:</b> {format_number(user['balance'])}₺
📈 <b>Toplam Kazanç:</b> {format_number(user['total_earned'])}₺
🎯 <b>Görevler:</b> {user['tasks_completed']}
👥 <b>Referans:</b> {user['ref_count']} (+{format_number(user['ref_earned'])}₺)

💸 <b>Para Çekim:</b>
• Minimum: 20₺
• Durum: YAKINDA AKTİF!

👇 Aşağıdaki seçeneklerden birini seç:"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def show_referrals(user_id, message_id):
    """Referans sistemini göster"""
    user = get_user(user_id)
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 LİNKİ PAYLAŞ", url=f"https://t.me/share/url?url={ref_link}&text=Günlük%202₺%20bonus%20ve%20referans%20başına%201₺%20kazan!%20{GorevYapsamBot}"),
        types.InlineKeyboardButton("📋 LİNKİ KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = f"""👥 <b>REFERANS SİSTEMİ</b>

💰 <b>Her referans başına:</b> 1.00₺
👤 <b>Toplam referans:</b> {user['ref_count']} kişi
📈 <b>Referans kazancı:</b> {format_number(user['ref_earned'])}₺

🔗 <b>Referans linkin:</b>
<code>{ref_link}</code>

📝 <b>Nasıl çalışır?</b>
1. Linkini paylaş
2. Arkadaşların linke tıklasın
3. Onlar /start yaptığında otomatik +1.00₺
4. Onlar da görev yaparak kazansın!

🔥 <b>Bonus:</b> Her 10 referansta +5₺ bonus!"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def daily_bonus(user_id, message_id):
    """Günlük bonus"""
    user = get_user(user_id)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
        last_daily = cursor.fetchone()['last_daily']
        
        can_claim = True
        if last_daily:
            last_date = datetime.strptime(last_daily, '%Y-%m-%d %H:%M:%S')
            if last_date.date() == datetime.now().date():
                can_claim = False
    
    if not can_claim:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🎯 Görev Yap", callback_data="menu_tasks"),
            types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
        )
        
        bot.edit_message_text(
            """⏳ <b>BUGÜNLÜK BONUSUNU ALDIN</b>

❌ Her kullanıcı günde sadece 1 kez bonus alabilir.

💰 <b>Günlük Bonus:</b> 2.00₺
⏰ <b>Yeni bonus için:</b> 24 saat sonra

💡 <b>İpucu:</b> Yarın tekrar gel!""",
            user_id,
            message_id,
            reply_markup=markup
        )
        return
    
    # 2₺ bonus ver
    bonus = 2.00
    update_balance(user_id, bonus)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET 
                       daily_streak = daily_streak + 1,
                       last_daily = CURRENT_TIMESTAMP
                       WHERE user_id = ?''', (user_id,))
        conn.commit()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="menu_tasks"),
        types.InlineKeyboardButton("💰 Bakiye", callback_data="menu_balance"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        f"""🎁 <b>GÜNLÜK BONUS KAZANDIN!</b>

✅ <b>2.00₺</b> bonus başarıyla hesabına yatırıldı!

📊 <b>Detaylar:</b>
• Günlük Bonus: 2.00₺
• Seri: {user['daily_streak']} gün
• Yeni Bakiye: {format_number(user['balance'])}₺

🔥 <b>Tebrikler!</b> Yarın tekrar gel!""",
        user_id,
        message_id,
        reply_markup=markup
    )

def show_stats(user_id, message_id):
    """İstatistikleri göster"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT 
                       COUNT(*) as total_users,
                       SUM(balance) as total_balance,
                       SUM(total_earned) as total_earned
                       FROM users''')
        stats = cursor.fetchone()
    
    user = get_user(user_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 Yenile", callback_data="menu_stats"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = f"""📊 <b>İSTATİSTİKLER</b>

👤 <b>Kişisel:</b>
• Bakiye: {format_number(user['balance'])}₺
• Toplam Kazanç: {format_number(user['total_earned'])}₺
• Görevler: {user['tasks_completed']}
• Referanslar: {user['ref_count']}
• Seri: {user['daily_streak']} gün

🌍 <b>Global:</b>
• Toplam Kullanıcı: {stats['total_users']}
• Toplam Bakiye: {format_number(stats['total_balance'])}₺
• Toplam Kazanç: {format_number(stats['total_earned'])}₺

🔥 <b>En çok kazanan sen ol!</b>"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def show_help(user_id, message_id):
    """Yardım menüsü"""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 KANAL", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"),
        types.InlineKeyboardButton("👤 YÖNETİCİ", url=f"https://t.me/{ADMIN_USER.replace('@', '')}"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    text = """ℹ️ <b>YARDIM MERKEZİ</b>

🎯 <b>GÖREV SİSTEMİ:</b>
• 🐢 Yavaş: 0.50-1.00₺
• 🚀 Orta: 1.00-2.50₺  
• ⚡ Hızlı: 2.50-5.00₺

💰 <b>KAZANÇ:</b>
1. Görev yap (0.50-5.00₺)
2. Günlük bonus al (2.00₺)
3. Referans kazan (1.00₺/kişi)

👥 <b>REFERANS:</b>
• Her referans: 1.00₺
• Her 10 referans: +5₺ bonus

⚠️ <b>KURALLAR:</b>
• @GorevYapsam kanalı zorunlu
• Sahte işlem yasak
• Çoklu hesap yasak

📞 <b>DESTEK:</b>
@AlperenTHE"""
    
    bot.edit_message_text(
        text,
        user_id,
        message_id,
        reply_markup=markup
    )

def admin_panel(user_id, message_id):
    """Admin panel"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İstatistik", callback_data="admin_stats"),
        types.InlineKeyboardButton("💰 Bakiye Ekle", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 Duyuru", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        """👑 <b>ADMIN PANEL</b>

Hoş geldin Yönetici!""",
        user_id,
        message_id,
        reply_markup=markup
    )

# ================= 7. FLASK SERVER =================
@app.route('/')
def home():
    return "🤖 Görev Yapsam Bot Aktif!"

@app.route('/health')
def health():
    return {"status": "ok"}

# ================= 8. BOT ÇALIŞTIRMA =================
def run_bot():
    print("🤖 Bot başlatılıyor...")
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=60)
        except Exception as e:
            print(f"Bot hatası: {e}")
            time.sleep(5)

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == "__main__":
    # Flask thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Bot thread
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
