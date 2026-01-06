"""
🤖 GÖREV YAPSAM BOTU v3.0 - TAM PAKET
Telegram: @GorevYapsam
Developer: Alperen
Token: 8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co
"""

import telebot
from telebot import types, apihelper
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
SUPPORT_GROUP = "@GorevYapsamDestek"

# Bot instance - Thread conflict hatasını çözmek için
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# ================= 2. VERİTABANI SİSTEMİ (GELİŞMİŞ) =================
def get_db():
    """Thread-safe database connection"""
    conn = sqlite3.connect('gorev_v3.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize all database tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
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
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            banned INTEGER DEFAULT 0,
            daily_streak INTEGER DEFAULT 0,
            last_daily TIMESTAMP
        )''')
        
        # Sources/Görevler table
        cursor.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            title TEXT,
            description TEXT,
            link TEXT,
            reward REAL DEFAULT 0.0,
            budget REAL DEFAULT 0.0,
            total_reward REAL DEFAULT 0.0,
            owner_id INTEGER,
            is_active INTEGER DEFAULT 1,
            task_type TEXT DEFAULT 'channel',
            required_members INTEGER DEFAULT 100,
            current_members INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            clicks INTEGER DEFAULT 0,
            completions INTEGER DEFAULT 0
        )''')
        
        # Completed tasks
        cursor.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source_id INTEGER,
            earned REAL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (source_id) REFERENCES sources(source_id)
        )''')
        
        # Transactions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
            tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            type TEXT,
            description TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')
        
        # Payout requests
        cursor.execute('''CREATE TABLE IF NOT EXISTS payouts (
            payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            details TEXT,
            status TEXT DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')
        
        # User stats
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_clicks INTEGER DEFAULT 0,
            total_earned REAL DEFAULT 0.0,
            daily_claims INTEGER DEFAULT 0,
            weekly_earned REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )''')
        
        conn.commit()
    print("✅ Database initialized successfully")

# Initialize database on start
init_database()

# ================= 3. ORTAK FONKSİYONLAR =================
def format_number(num):
    """Format numbers with thousand separators"""
    return f"{float(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def kanal_kontrol(user_id):
    """Check if user is member of required channel"""
    try:
        member = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Kanal kontrol hatası: {e}")
        return True  # Geçici olarak true döndür

def get_user_info(user_id):
    """Get complete user info"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT u.*, 
                         COALESCE(us.total_clicks, 0) as total_clicks,
                         COALESCE(us.daily_claims, 0) as daily_claims
                         FROM users u
                         LEFT JOIN user_stats us ON u.user_id = us.user_id
                         WHERE u.user_id = ?''', (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None

def update_user_balance(user_id, amount, description="", tx_type="earned"):
    """Update user balance and create transaction record"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        if amount > 0:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           total_earned = total_earned + ?,
                           last_active = CURRENT_TIMESTAMP
                           WHERE user_id = ?''', (amount, amount, user_id))
        else:
            cursor.execute('''UPDATE users SET 
                           balance = balance + ?,
                           last_active = CURRENT_TIMESTAMP
                           WHERE user_id = ?''', (amount, user_id))
        
        # Add transaction record
        cursor.execute('''INSERT INTO transactions 
                       (user_id, amount, type, description) 
                       VALUES (?, ?, ?, ?)''', 
                       (user_id, amount, tx_type, description))
        
        # Update stats
        if tx_type == "earned":
            cursor.execute('''INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)''', (user_id,))
            cursor.execute('''UPDATE user_stats SET 
                           total_earned = total_earned + ?
                           WHERE user_id = ?''', (amount, user_id))
        
        conn.commit()

def get_available_tasks(user_id):
    """Get available tasks for user"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT s.* FROM sources s
                        WHERE s.is_active = 1 
                        AND s.budget >= s.reward
                        AND NOT EXISTS (
                            SELECT 1 FROM completed_tasks ct 
                            WHERE ct.user_id = ? AND ct.source_id = s.source_id
                        )
                        ORDER BY s.reward DESC
                        LIMIT 20''', (user_id,))
        tasks = cursor.fetchall()
        return [dict(task) for task in tasks]

# ================= 4. ANA KOMUTLAR =================
@bot.message_handler(commands=['start'])
def start_command(message):
    """Start command handler"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Kullanıcı"
    
    # Check channel membership
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"),
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        bot.send_message(
            user_id,
            f"""👋 <b>Merhaba {first_name}!</b>

🚀 <b>GÖREV YAPSAM BOT</b>'a hoş geldin!

⚠️ <b>Devam etmek için zorunlu kanalımıza katılmalısın:</b>
{ZORUNLU_KANAL}

📌 Katıldıktan sonra <b>✅ KATILDIM</b> butonuna tıkla.""",
            reply_markup=markup
        )
        return
    
    # Referral system
    ref_id = 0
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            ref_id = int(args[1].replace('ref_', ''))
        except:
            ref_id = 0
    
    # Register user
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            # New user registration
            cursor.execute('''INSERT INTO users 
                           (user_id, username, first_name, referred_by, balance) 
                           VALUES (?, ?, ?, ?, ?)''',
                           (user_id, username, first_name, ref_id, 0.0))
            
            # Add to stats
            cursor.execute('''INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)''', (user_id,))
            
            # Give referral bonus if valid
            if ref_id and ref_id != user_id:
                cursor.execute('''UPDATE users SET 
                               balance = balance + 0.10,
                               ref_count = ref_count + 1,
                               ref_earned = ref_earned + 0.10
                               WHERE user_id = ?''', (ref_id,))
                
                # Send notification to referrer
                try:
                    bot.send_message(
                        ref_id,
                        f"""🎉 <b>REFERANS KAZANCI!</b>

👤 Yeni bir üye senin linkinle katıldı!
💰 <b>+0.10₺</b> referans kazancı hesabına eklendi!

🔗 Referans linkini paylaşmaya devam et!"""
                    )
                except:
                    pass
            
            conn.commit()
            
            # Welcome message for new users
            bot.send_message(
                user_id,
                f"""🎊 <b>HOŞ GELDİN {first_name}!</b>

✅ Başarıyla kaydoldun!
💰 <b>Hoşgeldin bonusu: +0.50₺</b> hesabına yüklendi!

🎯 Görev yaparak para kazanmaya hemen başla!"""
            )
            update_user_balance(user_id, 0.50, "Hoşgeldin bonusu")
    
    # Show main menu
    show_main_menu(user_id)

def show_main_menu(user_id):
    """Display main menu"""
    user = get_user_info(user_id)
    
    if not user:
        bot.send_message(user_id, "❌ Kullanıcı bulunamadı. Lütfen /start yazın.")
        return
    
    # Custom keyboard
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 GÖREVLER", "💰 BAKİYEM")
    markup.add("👥 REFERANSLARIM", "🎁 GÜNLÜK BONUS")
    markup.add("💸 PARA ÇEK", "💳 BAKİYE YÜKLE")
    markup.add("📊 İSTATİSTİKLER", "ℹ️ YARDIM")
    
    if user_id == ADMIN_ID:
        markup.add("👑 ADMIN PANEL")
    
    welcome_text = f"""🏠 <b>ANA MENÜ</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
💰 <b>Bakiye:</b> {format_number(user['balance'])}₺
🎯 <b>Tamamlanan Görev:</b> {user['tasks_completed']}
👥 <b>Referanslar:</b> {user['ref_count']}

🚀 <b>Özellikler:</b>
• Sosyal medya görevleri
• Günlük bonuslar
• Referans sistemi
• Para çekim"""

    bot.send_message(user_id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎯 GÖREVLER")
def show_tasks(message):
    """Show available tasks"""
    user_id = message.from_user.id
    
    if not kanal_kontrol(user_id):
        bot.send_message(user_id, f"❌ Görev yapmak için önce kanalımıza katılmalısın: {ZORUNLU_KANAL}")
        return
    
    tasks = get_available_tasks(user_id)
    
    if not tasks:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 YENİLE", callback_data="refresh_tasks"))
        
        bot.send_message(
            user_id,
            """📭 <b>GÖREV BULUNAMADI</b>

Şu anda yapabileceğin yeni görev bulunmuyor.
• Daha sonra tekrar kontrol et
• Kanal bildirimlerini aç
• Yeni görevler eklenecek""",
            reply_markup=markup
        )
        return
    
    # Show first task
    task = tasks[0]
    show_task_details(user_id, task)

def show_task_details(user_id, task):
    """Display task details"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 KANALA GİT", url=task['link']),
        types.InlineKeyboardButton("✅ TAMAMLADIM", callback_data=f"complete_{task['source_id']}")
    )
    markup.add(
        types.InlineKeyboardButton("🔄 FARKLI GÖREV", callback_data="next_task"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    task_text = f"""🎯 <b>YENİ GÖREV</b>

📌 <b>{task['title']}</b>

📝 <b>Açıklama:</b>
{task.get('description', 'Kanalı takip et ve görevi tamamla')}

💰 <b>Ödül:</b> {format_number(task['reward'])}₺
👥 <b>Gereken Üye:</b> {task['required_members']}
⏰ <b>Süre:</b> 10 dakika

⚠️ <b>Talimatlar:</b>
1. Kanala katıl
2. En az 5 dakika kal
3. Tamamladım butonuna bas
4. Ödülü al!"""
    
    bot.send_message(user_id, task_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("complete_"))
def complete_task(call):
    """Complete task handler"""
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[1])
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if already completed
        cursor.execute('''SELECT * FROM completed_tasks 
                       WHERE user_id = ? AND source_id = ?''', 
                       (user_id, task_id))
        if cursor.fetchone():
            bot.answer_callback_query(call.id, "❌ Bu görevi zaten tamamladın!", show_alert=True)
            return
        
        # Get task details
        cursor.execute('''SELECT * FROM sources WHERE source_id = ?''', (task_id,))
        task = cursor.fetchone()
        
        if not task:
            bot.answer_callback_query(call.id, "❌ Görev bulunamadı!", show_alert=True)
            return
        
        # Check channel membership
        try:
            member = bot.get_chat_member(task['chat_id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                bot.answer_callback_query(
                    call.id, 
                    "❌ Kanala katılımınız doğrulanamadı!", 
                    show_alert=True
                )
                return
        except:
            bot.answer_callback_query(call.id, "❌ Kanal doğrulama hatası!", show_alert=True)
            return
        
        # Complete task
        reward = task['reward']
        
        # Add to completed tasks
        cursor.execute('''INSERT INTO completed_tasks 
                       (user_id, source_id, earned, verified) 
                       VALUES (?, ?, ?, ?)''', 
                       (user_id, task_id, reward, 1))
        
        # Update source stats
        cursor.execute('''UPDATE sources SET 
                       completions = completions + 1,
                       budget = budget - ?
                       WHERE source_id = ?''', 
                       (reward, task_id))
        
        # Update user
        cursor.execute('''UPDATE users SET 
                       tasks_completed = tasks_completed + 1,
                       last_active = CURRENT_TIMESTAMP
                       WHERE user_id = ?''', (user_id,))
        
        conn.commit()
    
    # Give reward
    update_user_balance(user_id, reward, f"Görev: {task['title']}")
    
    # Update stats
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''UPDATE user_stats SET 
                       total_clicks = total_clicks + 1
                       WHERE user_id = ?''', (user_id,))
        conn.commit()
    
    # Success message
    user = get_user_info(user_id)
    
    success_text = f"""✅ <b>GÖREV TAMAMLANDI!</b>

🎉 Tebrikler! Görevi başarıyla tamamladın.

💰 <b>Kazanç:</b> +{format_number(reward)}₺
💰 <b>Yeni Bakiye:</b> {format_number(user['balance'])}₺
🎯 <b>Toplam Görev:</b> {user['tasks_completed']}

🚀 Hemen yeni görev yapmaya devam et!"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 YENİ GÖREV", callback_data="new_task"),
        types.InlineKeyboardButton("💰 BAKİYEM", callback_data="my_balance")
    )
    
    bot.edit_message_text(
        success_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    
    bot.answer_callback_query(call.id, f"✅ +{format_number(reward)}₺ kazandınız!")

@bot.message_handler(func=lambda m: m.text == "💰 BAKİYEM")
def show_balance(message):
    """Show user balance"""
    user_id = message.from_user.id
    user = get_user_info(user_id)
    
    if not user:
        bot.send_message(user_id, "❌ Kullanıcı bulunamadı.")
        return
    
    balance_text = f"""💰 <b>BAKİYE DETAYLARI</b>

👤 <b>Kullanıcı:</b> {user['first_name']}
🆔 <b>ID:</b> <code>{user_id}</code>

💵 <b>Cari Bakiye:</b> {format_number(user['balance'])}₺
📈 <b>Toplam Kazanç:</b> {format_number(user['total_earned'])}₺

🎯 <b>Görev İstatistikleri:</b>
• Tamamlanan: {user['tasks_completed']} görev
• Tıklamalar: {user.get('total_clicks', 0)}
• Günlük Bonus: {user.get('daily_claims', 0)} kez

👥 <b>Referans:</b>
• Toplam: {user['ref_count']} kişi
• Kazanç: {format_number(user['ref_earned'])}₺"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💸 PARA ÇEK", callback_data="withdraw"),
        types.InlineKeyboardButton("💳 BAKİYE YÜKLE", callback_data="deposit")
    )
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİKLER", callback_data="stats"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(user_id, balance_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 REFERANSLARIM")
def show_referrals(message):
    """Show referral information"""
    user_id = message.from_user.id
    user = get_user_info(user_id)
    
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
    
    ref_text = f"""👥 <b>REFERANS SİSTEMİ</b>

💰 <b>Her referans başına:</b> 0.10₺
👤 <b>Toplam referans:</b> {user['ref_count']} kişi
📈 <b>Referans kazancı:</b> {format_number(user['ref_earned'])}₺

🔗 <b>Referans linkin:</b>
<code>{ref_link}</code>

📝 <b>Nasıl çalışır?</b>
1. Linkini paylaş
2. Arkadaşların linke tıklasın
3. Onlar kayıt olduğunda otomatik +0.10₺
4. Onlar da görev yaparak kazansın!"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 LİNKİ PAYLAŞ", url=f"https://t.me/share/url?url={ref_link}&text=Para%20kazanmak%20için%20bu%20botu%20kullanın!"),
        types.InlineKeyboardButton("📋 LİNKİ KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(user_id, ref_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎁 GÜNLÜK BONUS")
def daily_bonus(message):
    """Daily bonus system"""
    user_id = message.from_user.id
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check last claim
        cursor.execute('''SELECT last_daily, daily_streak FROM users 
                       WHERE user_id = ?''', (user_id,))
        user_data = cursor.fetchone()
        
        now = datetime.now()
        last_claim = None
        
        if user_data and user_data['last_daily']:
            last_claim = datetime.strptime(user_data['last_daily'], '%Y-%m-%d %H:%M:%S')
        
        can_claim = True
        streak = 1
        
        if last_claim:
            # Check if already claimed today
            if last_claim.date() == now.date():
                can_claim = False
            
            # Check streak
            days_diff = (now.date() - last_claim.date()).days
            if days_diff == 1:
                streak = user_data['daily_streak'] + 1
            elif days_diff > 1:
                streak = 1
        
        if not can_claim:
            bot.send_message(
                user_id,
                """⏳ <b>BUGÜNLÜK BONUSUNU ALDIN</b>

❌ Her kullanıcı günde sadece 1 kez bonus alabilir.

⏰ <b>Yeni bonus için:</b> 24 saat sonra tekrar gel!"""
            )
            return
        
        # Calculate bonus
        base_bonus = 0.50
        streak_bonus = min(streak * 0.10, 2.00)  # Max 2₺ streak bonus
        total_bonus = base_bonus + streak_bonus
        
        # Give bonus
        cursor.execute('''UPDATE users SET 
                       balance = balance + ?,
                       daily_streak = ?,
                       last_daily = CURRENT_TIMESTAMP,
                       last_active = CURRENT_TIMESTAMP
                       WHERE user_id = ?''', 
                       (total_bonus, streak, user_id))
        
        # Update stats
        cursor.execute('''UPDATE user_stats SET 
                       daily_claims = daily_claims + 1
                       WHERE user_id = ?''', (user_id,))
        
        conn.commit()
    
    # Transaction record
    update_user_balance(user_id, total_bonus, f"Günlük bonus ({streak}. gün)", "daily_bonus")
    
    # Success message
    user = get_user_info(user_id)
    
    bonus_text = f"""🎁 <b>GÜNLÜK BONUS KAZANDIN!</b>

✅ Bonus başarıyla hesabına yatırıldı!

📊 <b>Detaylar:</b>
• Seri: {streak}. gün
• Baz Bonus: {format_number(base_bonus)}₺
• Seri Bonusu: {format_number(streak_bonus)}₺
• Toplam: +{format_number(total_bonus)}₺
• Yeni Bakiye: {format_number(user['balance'])}₺

🔥 <b>Tebrikler!</b> Yarın tekrar gel, serini bozma!"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎯 GÖREV YAP", callback_data="new_task"),
        types.InlineKeyboardButton("💰 BAKİYEM", callback_data="my_balance"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(user_id, bonus_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💸 PARA ÇEK")
def withdraw_money(message):
    """Withdrawal system"""
    user_id = message.from_user.id
    user = get_user_info(user_id)
    
    if user['balance'] < 20.00:
        bot.send_message(
            user_id,
            f"""❌ <b>YETERSİZ BAKİYE</b>

💰 <b>Minimum çekim:</b> 20.00₺
💵 <b>Mevcut bakiyen:</b> {format_number(user['balance'])}₺

💡 <b>Öneri:</b>
• Daha fazla görev yap
• Referans kazan
• Günlük bonusunu al"""
        )
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 BANK HAVALESİ", callback_data="withdraw_bank"),
        types.InlineKeyboardButton("📞 PAPARA", callback_data="withdraw_papara"),
        types.InlineKeyboardButton("💳 KREDİ KARTI", callback_data="withdraw_card")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(
        user_id,
        f"""💸 <b>PARA ÇEKİM SİSTEMİ</b>

💰 <b>Mevcut bakiyen:</b> {format_number(user['balance'])}₺
📊 <b>Minimum çekim:</b> 20.00₺
⏰ <b>İşlem süresi:</b> 1-24 saat

📋 <b>Talimatlar:</b>
1. Çekim yöntemini seç
2. Miktarı belirt
3. Hesap bilgilerini gir
4. Onayla

⚠️ <b>Not:</b> İlk çekimler manuel onay gerektirir.""",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "💳 BAKİYE YÜKLE")
def deposit_money(message):
    """Deposit system"""
    user_id = message.from_user.id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 BANK HAVALESİ", callback_data="deposit_bank"),
        types.InlineKeyboardButton("📞 PAPARA", callback_data="deposit_papara"),
        types.InlineKeyboardButton("💳 KREDİ KARTI", callback_data="deposit_card")
    )
    markup.add(
        types.InlineKeyboardButton("👤 DESTEK", url=f"https://t.me/{ADMIN_USER.replace('@', '')}"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(
        user_id,
        """💳 <b>BAKİYE YÜKLEME</b>

📊 <b>Paketler:</b>
• 20₺ Paket - 20₺ bakiye
• 50₺ Paket - 50₺ bakiye  
• 100₺ Paket - 100₺ bakiye
• 200₺ Paket - 200₺ bakiye

📋 <b>Talimatlar:</b>
1. Ödeme yöntemini seç
2. Yöneticiye yaz
3. Ödemeyi yap
4. Bakiye yüklensin

👤 <b>İletişim:</b> @AlperenTHE""",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "📊 İSTATİSTİKLER")
def show_stats(message):
    """Show statistics"""
    user_id = message.from_user.id
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get global stats
        cursor.execute('''SELECT 
                       COUNT(*) as total_users,
                       SUM(balance) as total_balance,
                       SUM(total_earned) as total_earned,
                       SUM(tasks_completed) as total_tasks
                       FROM users WHERE banned = 0''')
        global_stats = cursor.fetchone()
        
        # Get user rank
        cursor.execute('''SELECT COUNT(*) + 1 as rank FROM users 
                       WHERE balance > (SELECT balance FROM users WHERE user_id = ?)''', 
                       (user_id,))
        rank = cursor.fetchone()['rank']
        
        # Get active tasks
        cursor.execute('''SELECT COUNT(*) as active_tasks FROM sources 
                       WHERE is_active = 1 AND budget >= reward''')
        active_tasks = cursor.fetchone()['active_tasks']
    
    user = get_user_info(user_id)
    
    stats_text = f"""📊 <b>İSTATİSTİKLER</b>

👤 <b>Kişisel:</b>
• Sıralama: #{rank}
• Bakiye: {format_number(user['balance'])}₺
• Toplam Kazanç: {format_number(user['total_earned'])}₺
• Görevler: {user['tasks_completed']}
• Referanslar: {user['ref_count']}

🌍 <b>Global:</b>
• Toplam Kullanıcı: {global_stats['total_users']}
• Toplam Bakiye: {format_number(global_stats['total_balance'])}₺
• Toplam Kazanç: {format_number(global_stats['total_earned'])}₺
• Toplam Görev: {global_stats['total_tasks']}
• Aktif Görev: {active_tasks}

🔥 <b>En çok kazanan sen ol!</b>"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 YENİLE", callback_data="refresh_stats"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(user_id, stats_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "ℹ️ YARDIM")
def show_help(message):
    """Show help"""
    help_text = """ℹ️ <b>YARDIM MERKEZİ</b>

📌 <b>Temel Komutlar:</b>
/start - Botu başlat
/help - Bu mesajı göster

🎯 <b>Görev Sistemi:</b>
• Sosyal medya kanallarına katıl
• Her görev için ödül kazan
• Her görevi 1 kez yapabilirsin

💰 <b>Para Kazanma:</b>
1. Görev yap (0.10-5.00₺)
2. Günlük bonus al (0.50-2.50₺)
3. Referans kazan (0.10₺/kişi)

💸 <b>Para Çekme:</b>
• Minimum: 20₺
• Yöntemler: Banka, Papara
• Süre: 1-24 saat

⚠️ <b>Kurallar:</b>
• Sahte işlem yasak
• Çoklu hesap yasak
• Spam yasak

👤 <b>Destek:</b>
@GorevYapsamDestek
@AlperenTHE"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 KANALIMIZ", url=f"https://t.me/{ZORUNLU_KANAL.replace('@', '')}"),
        types.InlineKeyboardButton("👤 DESTEK", url=f"https://t.me/{ADMIN_USER.replace('@', '')}"),
        types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="main_menu")
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=markup)

# ================= 5. CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Handle all callbacks"""
    user_id = call.from_user.id
    
    # Update last active
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET last_active = CURRENT_TIMESTAMP 
                       WHERE user_id = ?''', (user_id,))
        conn.commit()
    
    if call.data == "check_join":
        if kanal_kontrol(user_id):
            show_main_menu(user_id)
            bot.answer_callback_query(call.id, "✅ Teşekkürler! Artık görev yapabilirsin.")
        else:
            bot.answer_callback_query(call.id, "❌ Hala kanalda değilsin!", show_alert=True)
    
    elif call.data == "main_menu":
        show_main_menu(user_id)
        bot.answer_callback_query(call.id)
    
    elif call.data == "new_task":
        tasks = get_available_tasks(user_id)
        if tasks:
            show_task_details(user_id, tasks[0])
        else:
            bot.answer_callback_query(call.id, "❌ Şu anda görev yok!", show_alert=True)
    
    elif call.data == "my_balance":
        user = get_user_info(user_id)
        bot.answer_callback_query(call.id, f"💰 Bakiye: {format_number(user['balance'])}₺")
    
    elif call.data.startswith("copy_"):
        link = call.data.replace("copy_", "")
        bot.answer_callback_query(call.id, "✅ Link panoya kopyalandı!")
    
    elif call.data == "refresh_tasks":
        tasks = get_available_tasks(user_id)
        if tasks:
            show_task_details(user_id, tasks[0])
        else:
            bot.answer_callback_query(call.id, "❌ Hala görev yok!", show_alert=True)
    
    elif call.data == "refresh_stats":
        user = get_user_info(user_id)
        bot.edit_message_text(
            f"📊 <b>İstatistikler Yenilendi</b>\n\n💰 Bakiye: {format_number(user['balance'])}₺",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id, "✅ Yenilendi!")

# ================= 6. ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 ADMIN PANEL" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    """Admin panel"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİK", callback_data="admin_stats"),
        types.InlineKeyboardButton("➕ GÖREV EKLE", callback_data="admin_add_task"),
        types.InlineKeyboardButton("💰 BAKİYE EKLE", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 DUYURU", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("👤 KULLANICI YÖNET", callback_data="admin_manage_user"),
        types.InlineKeyboardButton("⚙️ AYARLAR", callback_data="admin_settings")
    )
    
    bot.send_message(
        message.chat.id,
        """👑 <b>ADMIN PANEL</b>

Hoş geldin Yönetici! Yapmak istediğin işlemi seç:""",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    """Admin callback handler"""
    user_id = call.from_user.id
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Yetkin yok!", show_alert=True)
        return
    
    if call.data == "admin_stats":
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''SELECT 
                           COUNT(*) as total_users,
                           SUM(balance) as total_balance,
                           SUM(total_earned) as total_earned,
                           SUM(tasks_completed) as total_tasks,
                           SUM(ref_count) as total_refs
                           FROM users WHERE banned = 0''')
            stats = cursor.fetchone()
            
            # Active users (last 7 days)
            cursor.execute('''SELECT COUNT(*) as active_users FROM users 
                           WHERE last_active >= datetime('now', '-7 days')''')
            active = cursor.fetchone()['active_users']
            
            # Daily earnings
            cursor.execute('''SELECT SUM(amount) as daily_earnings FROM transactions 
                           WHERE type = 'earned' AND DATE(created_at) = DATE('now')''')
            daily = cursor.fetchone()['daily_earnings'] or 0
        
        stats_text = f"""📊 <b>ADMIN İSTATİSTİKLERİ</b>

👥 <b>Kullanıcılar:</b>
• Toplam: {stats['total_users']}
• Aktif (7 gün): {active}
  
💰 <b>Finansal:</b>
• Toplam Bakiye: {format_number(stats['total_balance'])}₺
• Toplam Kazanç: {format_number(stats['total_earned'])}₺
• Günlük Kazanç: {format_number(daily)}₺

🎯 <b>Görevler:</b>
• Tamamlanan: {stats['total_tasks']}
• Referanslar: {stats['total_refs']}

📈 <b>Verimlilik:</b>
• Ort. Kazanç/Kullanıcı: {format_number(stats['total_earned'] / stats['total_users'] if stats['total_users'] > 0 else 0)}₺
• Ort. Görev/Kullanıcı: {stats['total_tasks'] / stats['total_users'] if stats['total_users'] > 0 else 0:.2f}"""
        
        bot.edit_message_text(
            stats_text,
            call.message.chat.id,
            call.message.message_id
        )
    
    elif call.data == "admin_add_task":
        msg = bot.send_message(
            call.message.chat.id,
            """➕ <b>YENİ GÖREV EKLE</b>

Lütfen görev detaylarını şu formatta gönder:
<code>Kanal Adı | Kanal Linki | Ödül (₺) | Bütçe (₺) | Gereken Üye</code>

Örnek:
<code>Test Kanalı | https://t.me/test | 0.50 | 10.00 | 100</code>"""
        )
        bot.register_next_step_handler(msg, process_add_task)
    
    bot.answer_callback_query(call.id)

def process_add_task(message):
    """Process new task addition"""
    try:
        data = message.text.split("|")
        if len(data) != 5:
            bot.send_message(message.chat.id, "❌ Hatalı format! Tekrar dene.")
            return
        
        title = data[0].strip()
        link = data[1].strip()
        reward = float(data[2].strip())
        budget = float(data[3].strip())
        required = int(data[4].strip())
        
        # Get chat ID from link
        chat_id = link.split("/")[-1]
        if chat_id.startswith("@"):
            chat_id = chat_id[1:]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO sources 
                           (chat_id, title, link, reward, budget, required_members, owner_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (chat_id, title, link, reward, budget, required, ADMIN_ID))
            conn.commit()
        
        bot.send_message(
            message.chat.id,
            f"""✅ <b>GÖREV EKLENDİ!</b>

📌 <b>{title}</b>
🔗 {link}
💰 Ödül: {reward}₺
💵 Bütçe: {budget}₺
👥 Gereken: {required} üye

🎯 Görev başarıyla eklendi!"""
        )
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Hata: {str(e)}")

# ================= 7. FLASK SERVER (RENDER İÇİN) =================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Görev Yapsam Bot</title>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 100vh;
                margin: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                color: white;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 20px;
                backdrop-filter: blur(10px);
                max-width: 600px;
                width: 90%;
            }
            h1 {
                font-size: 3em;
                margin-bottom: 20px;
            }
            .status {
                background: rgba(0, 255, 0, 0.3);
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                font-size: 1.2em;
            }
            .btn {
                display: inline-block;
                background: #0088cc;
                color: white;
                padding: 12px 24px;
                border-radius: 5px;
                text-decoration: none;
                margin: 10px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 GÖREV YAPSAM</h1>
            <div class="status">
                ✅ <strong>BOT AKTİF VE ÇALIŞIYOR</strong>
            </div>
            <p>Sosyal medya görevleriyle para kazanma botu</p>
            <p>Telegram: @GorevYapsam</p>
            <a href="https://t.me/GorevYapsamBot" class="btn" target="_blank">
                📲 Telegram'da Aç
            </a>
            <a href="https://t.me/GorevYapsam" class="btn" target="_blank" style="background: #ff6b6b;">
                📢 Kanalımıza Katıl
            </a>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "active", "time": datetime.now().isoformat()}

@app.route('/stats')
def stats():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as users FROM users')
        users = cursor.fetchone()['users']
    return {"users": users, "status": "online"}

# ================= 8. POLLING SİSTEMİ (HATA KORUMALI) =================
def start_polling():
    """Start bot polling with error handling"""
    print("🤖 GÖREV YAPSAM BOTU v3.0")
    print("=" * 50)
    print(f"👤 Admin: {ADMIN_ID}")
    print(f"📢 Kanal: {ZORUNLU_KANAL}")
    print("🚀 Bot başlatılıyor...")
    
    # Remove any existing webhook
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    # Start polling with restart on error
    while True:
        try:
            print("🔄 Polling başlatılıyor...")
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                logger_level=30,  # ERROR level
                restart_on_change=True,
                skip_pending=True
            )
        except Exception as e:
            print(f"❌ Polling hatası: {e}")
            print("🔄 10 saniye sonra yeniden başlatılıyor...")
            time.sleep(10)

def start_flask():
    """Start Flask server for Render"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ================= 9. ANA ÇALIŞTIRMA =================
if __name__ == "__main__":
    # Start Flask server in separate thread (for Render)
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server başlatıldı (Port: 5000)")
    
    # Add some sample tasks on first run
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM sources")
        if cursor.fetchone()['count'] == 0:
            sample_tasks = [
                ("Test Kanalı 1", "@testkanal1", 0.50, 50.00, 100),
                ("Test Kanalı 2", "@testkanal2", 0.75, 100.00, 200),
                ("Test Kanalı 3", "@testkanal3", 1.00, 150.00, 300),
            ]
            for title, link, reward, budget, required in sample_tasks:
                cursor.execute('''INSERT INTO sources 
                               (chat_id, title, link, reward, budget, required_members, owner_id)
                               VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (link.replace('@', ''), title, f"https://t.me/{link.replace('@', '')}", 
                                reward, budget, required, ADMIN_ID))
            conn.commit()
            print("✅ Örnek görevler eklendi")
    
    # Start bot polling
    try:
        start_polling()
    except KeyboardInterrupt:
        print("\n👋 Bot durduruluyor...")
    except Exception as e:
        print(f"❌ Kritik hata: {e}")
