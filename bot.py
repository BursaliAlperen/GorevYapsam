"""
🤖 GÖREV BOTU - RENDER FİNAL SÜRÜM
Telegram: @GorevYapsam
Özellikler: Kanal/Grup Admin Kontrolü, Web Server, Otomatik Temizleme
"""

import telebot
from telebot import types
import sqlite3
import time
import threading
import os
import sys
from flask import Flask, request

# ================= AYARLAR =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co" # Token buraya
ADMIN_ID = 7904032877
MAIN_CHANNEL = "@GorevYapsam"

# 409 Hatasını Önlemek İçin Webhook Temizliği
bot = telebot.TeleBot(TOKEN, threaded=False)
try:
    bot.remove_webhook()
    time.sleep(0.1)
except Exception as e:
    print(f"Webhook temizleme hatası (önemsiz): {e}")

app = Flask(__name__)

# ================= DATABASE =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Kullanıcılar
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            tasks_completed INTEGER DEFAULT 0
        )''')
        
        # Eklenen Kanallar/Gruplar (Botun Admin Olduğu Yerler)
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            title TEXT,
            type TEXT,
            link TEXT,
            reward REAL,
            is_active INTEGER DEFAULT 1
        )''')
        
        # Tamamlanan Görevler
        self.c.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source_id INTEGER,
            earned REAL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()

    def add_user(self, user_id, username, first_name):
        self.c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)', 
                      (user_id, username, first_name))
        self.conn.commit()

    def add_source(self, chat_id, title, chat_type, link, reward):
        self.c.execute('INSERT OR REPLACE INTO sources (chat_id, title, type, link, reward, is_active) VALUES (?, ?, ?, ?, ?, 1)',
                      (chat_id, title, chat_type, link, reward))
        self.conn.commit()
        return self.c.lastrowid

    def get_active_tasks(self, user_id):
        # Kullanıcının yapmadığı aktif görevleri getir
        self.c.execute('''
            SELECT * FROM sources 
            WHERE is_active = 1 
            AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id = ?)
        ''', (user_id,))
        return self.c.fetchall()

    def complete_task(self, user_id, source_id, reward):
        self.c.execute('INSERT INTO completed_tasks (user_id, source_id, earned) VALUES (?, ?, ?)', (user_id, source_id, reward))
        self.c.execute('UPDATE users SET balance = balance + ?, tasks_completed = tasks_completed + 1 WHERE user_id = ?', (reward, user_id))
        self.conn.commit()

    def get_user(self, user_id):
        self.c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.c.fetchone()

db = Database()

# ================= FLASK WEB SERVER (Render İçin Zorunlu) =================
@app.route('/')
def home():
    return "🤖 Bot Çalışıyor! (Status: Active)", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    # Render PORT'u otomatik atar, yoksa 5000 kullanır
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False çifte başlatmayı önler
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ================= BOT MANTIĞI =================

# 1. BOT BİR GRUBA/KANALA EKLENDİĞİNDE TETİKLENİR (Admin Algılama)
@bot.my_chat_member_handler()
def on_bot_status_change(message: types.ChatMemberUpdated):
    new_status = message.new_chat_member.status
    chat = message.chat
    
    # Sadece Admin yapıldığında işlem yap
    if new_status == 'administrator':
        chat_type = chat.type # channel, group, supergroup
        invite_link = ""
        
        try:
            # Link almaya çalış (Botun link oluşturma yetkisi olmalı)
            link_obj = bot.create_chat_invite_link(chat.id)
            invite_link = link_obj.invite_link
        except:
            invite_link = f"https://t.me/{chat.username}" if chat.username else "Link Yok"

        # Fiyat Belirleme
        reward = 2.0 if chat_type == 'channel' else 1.5
        
        # Veritabanına kaydet (Görev olarak eklenir)
        db.add_source(chat.id, chat.title, chat_type, invite_link, reward)
        
        try:
            bot.send_message(chat.id, f"✅ Bot Admin Oldu!\n\nBu {chat_type} artık görev listesine eklendi.\n💰 Kullanıcı başına ödül: {reward}₺")
            bot.send_message(ADMIN_ID, f"📢 Yeni Görev Eklendi!\n\nYer: {chat.title}\nTür: {chat_type}\nÖdül: {reward}₺")
        except:
            pass
            
    # Bot atıldıysa veya yetkisi alındıysa
    elif new_status in ['left', 'kicked', 'restricted']:
        # Veritabanında pasif yap (kod eklenebilir)
        pass

# 2. START KOMUTU
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    db.add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Görev Yap", callback_data="tasks"),
        types.InlineKeyboardButton("💰 Bakiye", callback_data="balance"),
        types.InlineKeyboardButton("➕ Botu Ekle (Admin)", url=f"https://t.me/{bot.get_me().username}?startgroup=true")
    )
    
    text = f"""
    👋 *Merhaba {message.from_user.first_name}!*
    
    Para kazanmak için görevleri yapabilirsin.
    
    📢 *Fiyatlar:*
    • Kanal Katılım: 2.00 ₺
    • Grup Katılım: 1.50 ₺
    • Bot Başlatma: 1.00 ₺
    
    👇 Menüden seçim yap:
    """
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# 3. BUTON İŞLEMLERİ
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    if call.data == "balance":
        user = db.get_user(user_id) # (id, user, name, balance, tasks)
        bot.answer_callback_query(call.id, f"💰 Bakiyen: {user[3]:.2f} ₺")
        
    elif call.data == "tasks":
        tasks = db.get_active_tasks(user_id)
        
        if not tasks:
            bot.edit_message_text("🎉 Tüm görevleri tamamladın! Yeni görevler için beklemede kal.", call.message.chat.id, call.message.message_id)
            return
            
        # İlk görevi göster
        task = tasks[0] # (id, chat_id, title, type, link, reward, active)
        source_id = task[0]
        chat_id = task[1]
        link = task[4]
        reward = task[5]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Git ve Katıl", url=link))
        markup.add(types.InlineKeyboardButton("✅ Kontrol Et", callback_data=f"check_{source_id}_{chat_id}_{reward}"))
        
        text = f"""
        📋 *GÖREV:*
        
        📍 *{task[2]}* ({task[3]})
        💰 *Ödül:* {reward} ₺
        
        Katıl ve 'Kontrol Et' butonuna bas.
        """
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("check_"):
        # check_sourceID_chatID_reward
        _, source_id, chat_id, reward = call.data.split("_")
        source_id = int(source_id)
        chat_id = int(chat_id)
        reward = float(reward)
        
        try:
            # KULLANICI KONTROLÜ (Get Chat Member)
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                db.complete_task(user_id, source_id, reward)
                bot.answer_callback_query(call.id, f"✅ Onaylandı! +{reward}₺", show_alert=True)
                
                # Menüye dön
                start(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ Henüz katılmamışsın!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ Kontrol edilemedi (Bot yetkisi yok veya hata).", show_alert=True)

# ================= BAŞLATMA =================
if __name__ == "__main__":
    print("🚀 Sistem Başlatılıyor...")
    
    # 1. Thread: Flask Sunucusu
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # 2. Ana Döngü: Bot Polling
    # 409 Hatasını engellemek için infinity_polling ve restart koruması
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Bot bağlantı hatası: {e}")
            time.sleep(5)
