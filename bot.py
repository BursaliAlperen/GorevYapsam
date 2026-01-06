import telebot
from telebot import types
import sqlite3
import threading
import random
import os
from flask import Flask

# ================= AYARLAR =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_USER = "@AlperenTHE" # Destek için admin
MAIN_CHANNEL = "@GorevYapsam" # Zorunlu kanal

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ================= DATABASE =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_final_system.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Kullanıcılar (Referans dahil)
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT 0
        )''')
        # Görevler (İsim, Açıklama, Link, Bütçe, Hız)
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz Görev',
            description TEXT DEFAULT 'Açıklama girilmedi.',
            link TEXT,
            reward REAL DEFAULT 0.5,
            budget REAL DEFAULT 0,
            speed TEXT DEFAULT 'Medium',
            owner_id INTEGER,
            is_active INTEGER DEFAULT 0
        )''')
        # Tamamlananlar
        self.c.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER
        )''')
        self.conn.commit()

db = Database()

# ================= OTOMATİK ADMİN ALGILAMA =================

@bot.my_chat_member_handler()
def on_bot_admin_status(message: types.ChatMemberUpdated):
    new_status = message.new_chat_member.status
    chat = message.chat
    owner_id = message.from_user.id 
    
    if new_status == 'administrator':
        # Veritabanına taslak olarak ekle
        db.c.execute('INSERT OR IGNORE INTO sources (chat_id, owner_id) VALUES (?, ?)', (chat.id, owner_id))
        db.conn.commit()
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚙️ Kurulum Panelini Aç", callback_data=f"setup_{chat.id}"))
        
        bot.send_message(owner_id, f"✅ *Bot '{chat.title}' kanalına admin olarak eklendi!*\n\nGörevin yayına girmesi için aşağıdaki butondan İsim, Link, Açıklama ve Bütçe ayarlarını yapmalısın.", 
                         parse_mode="Markdown", reply_markup=markup)

# ================= KURULUM VE YÖNETİM PANELİ =================

@bot.callback_query_handler(func=lambda call: call.data.startswith(("setup_", "manage_")))
def task_panel(call):
    chat_id = call.data.split("_")[1]
    db.c.execute("SELECT title, description, link, budget, reward, is_active FROM sources WHERE chat_id = ?", (chat_id,))
    data = db.c.fetchone()
    
    status = "✅ Yayında" if data[5] == 1 else "❌ Kurulum Bekliyor / Durduruldu"
    
    text = f"🛠 *GÖREV DÜZENLEME PANELİ*\n\n" \
           f"📍 *Durum:* {status}\n" \
           f"📝 *İsim:* {data[0]}\n" \
           f"ℹ️ *Açıklama:* {data[1]}\n" \
           f"🔗 *Link:* {data[2] if data[2] else 'Eksik'}\n" \
           f"💰 *Bütçe:* {data[3]}₺\n" \
           f"💸 *Üye Başı Ödül:* {data[4]}₺\n\n" \
           f"Düzenlemek istediğiniz alanı seçin:"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 İsim Değiştir", callback_data=f"inp_title_{chat_id}"),
        types.InlineKeyboardButton("ℹ️ Açıklama Yaz", callback_data=f"inp_desc_{chat_id}"),
        types.InlineKeyboardButton("🔗 Link Ekle", callback_data=f"inp_link_{chat_id}"),
        types.InlineKeyboardButton("💰 Bütçe Yükle", callback_data=f"inp_budget_{chat_id}"),
        types.InlineKeyboardButton("⚡ Hız (Ödül) Ayarla", callback_data=f"inp_reward_{chat_id}"),
        types.InlineKeyboardButton("🚀 GÖREVİ YAYINLA", callback_data=f"pub_{chat_id}")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

# ================= VERİ GİRİŞ SİSTEMİ =================

waiting_input = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("inp_"))
def request_input(call):
    _, field, chat_id = call.data.split("_")
    waiting_input[call.from_user.id] = {"field": field, "chat_id": chat_id}
    bot.send_message(call.message.chat.id, f"💬 Lütfen yeni *{field.upper()}* değerini yazıp gönderin:")

@bot.message_handler(func=lambda m: m.from_user.id in waiting_input)
def get_input(message):
    data = waiting_input[message.from_user.id]
    field, chat_id = data['field'], data['chat_id']
    val = message.text

    try:
        if field == "title": db.c.execute('UPDATE sources SET title = ? WHERE chat_id = ?', (val, chat_id))
        elif field == "desc": db.c.execute('UPDATE sources SET description = ? WHERE chat_id = ?', (val, chat_id))
        elif field == "link": db.c.execute('UPDATE sources SET link = ? WHERE chat_id = ?', (val, chat_id))
        elif field == "budget": db.c.execute('UPDATE sources SET budget = budget + ? WHERE chat_id = ?', (float(val), chat_id))
        elif field == "reward": db.c.execute('UPDATE sources SET reward = ? WHERE chat_id = ?', (float(val), chat_id))
        db.conn.commit()
        bot.send_message(message.chat.id, "✅ Bilgi güncellendi! Paneli tekrar açmak için 'Görevlerimi Yönet' butonuna basın.")
    except:
        bot.send_message(message.chat.id, "❌ Hatalı giriş yaptınız.")
    
    del waiting_input[message.from_user.id]

# ================= YAYINLAMA VE GÖREV YAPMA =================

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def publish(call):
    chat_id = call.data.split("_")[1]
    db.c.execute("SELECT link, budget FROM sources WHERE chat_id = ?", (chat_id,))
    d = db.c.fetchone()
    
    if not d[0] or d[1] <= 0:
        bot.answer_callback_query(call.id, "❌ Link veya Bütçe eksik! Yayınlanamaz.", show_alert=True)
    else:
        db.c.execute("UPDATE sources SET is_active = 1 WHERE chat_id = ?", (chat_id,))
        db.conn.commit()
        bot.answer_callback_query(call.id, "🚀 Görev başarıyla yayına alındı!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def verify(call):
    _, s_id, reward = call.data.split("_")
    s_id, reward = int(s_id), float(reward)
    user_id = call.from_user.id
    
    db.c.execute("SELECT chat_id, budget, owner_id, title FROM sources WHERE source_id=?", (s_id,))
    s = db.c.fetchone()
    
    if s[1] < reward:
        bot.answer_callback_query(call.id, "❌ Görevin bütçesi yetersiz!", show_alert=True)
        db.c.execute("UPDATE sources SET is_active = 0 WHERE source_id=?", (s_id,))
        bot.send_message(s[2], f"⚠️ *BAKİYE BİTTİ!*\n'{s[3]}' göreviniz bütçesi tükendiği için durduruldu.")
        return

    try:
        member = bot.get_chat_member(s[0], user_id)
        if member.status in ['member', 'administrator', 'creator']:
            db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
            db.c.execute("UPDATE sources SET budget = budget - ? WHERE source_id = ?", (reward, s_id))
            db.c.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (user_id, s_id))
            db.conn.commit()
            bot.answer_callback_query(call.id, f"✅ Onaylandı! +{reward}₺", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Henüz katılmamışsın!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Bot yetki hatası!")

# ================= ANA MENÜ =================

@bot.message_handler(commands=['start'])
def start(message):
    db.c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    db.conn.commit()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim", "📢 Reklam Ver", "⚙️ Görevlerimi Yönet")
    bot.send_message(message.chat.id, f"🚀 *GÖREV YAPSAM* sistemine hoş geldin!\n\nDestek: {ADMIN_USER}", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def tasks_list(message):
    db.c.execute("SELECT * FROM sources WHERE is_active=1 AND budget >= reward AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)", (message.from_user.id,))
    tasks = db.c.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "❌ Şu an yapılacak görev bulunmuyor.")
        return
    
    for t in tasks[:3]: # İlk 3 görevi göster
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔗 Göreve Git", url=t[4]))
        markup.add(types.InlineKeyboardButton("✅ Kontrol Et", callback_data=f"v_{t[0]}_{t[5]}"))
        bot.send_message(message.chat.id, f"📋 *GÖREV:* {t[2]}\nℹ️ *Açıklama:* {t[3]}\n💰 *Ödül:* {t[5]}₺", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⚙️ Görevlerimi Yönet")
def manage_mine(message):
    db.c.execute("SELECT chat_id, title FROM sources WHERE owner_id = ?", (message.from_user.id,))
    mine = db.c.fetchall()
    if not mine:
        bot.send_message(message.chat.id, "❌ Henüz bir göreviniz yok.")
        return
    
    markup = types.InlineKeyboardMarkup()
    for m in mine:
        markup.add(types.InlineKeyboardButton(f"📍 {m[1]}", callback_data=f"setup_{m[0]}"))
    bot.send_message(message.chat.id, "Düzenlemek istediğiniz görevi seçin:", reply_markup=markup)

# ================= SUNUCU VE BAŞLATMA =================
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'my_chat_member'])
