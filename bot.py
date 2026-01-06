import telebot
from telebot import types
import sqlite3
import threading
from flask import Flask

# ================= AYARLAR =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_USER = "@AlperenTHE"
ADMIN_ID = 7904032877 
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ================= DATABASE =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_onay_sistemi.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        self.c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0)')
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz', description TEXT DEFAULT 'Yok',
            link TEXT, reward REAL DEFAULT 0.5, budget REAL DEFAULT 0, owner_id INTEGER, is_active INTEGER DEFAULT 0
        )''')
        self.c.execute('CREATE TABLE IF NOT EXISTS completed_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER)')
        self.conn.commit()

db = Database()

# ================= ADMİN BAKİYE YÜKLEME =================
admin_state = {}

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Kullanıcıya Bakiye Yükle", callback_data="adm_yukle"))
    bot.send_message(message.chat.id, "👑 *Yönetici Paneli*", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adm_yukle")
def adm_start(call):
    admin_state[call.from_user.id] = {"step": "id"}
    bot.send_message(call.message.chat.id, "👤 Kullanıcı ID'sini yazın:")

# ================= SESSİZ KANAL ALGILAMA =================
@bot.my_chat_member_handler()
def silent_detect(message: types.ChatMemberUpdated):
    if message.new_chat_member.status == 'administrator':
        db.c.execute('INSERT OR IGNORE INTO sources (chat_id, owner_id) VALUES (?, ?)', (message.chat.id, message.from_user.id))
        db.conn.commit()

# ================= ANA MENÜ =================
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🎯 Görev Yap", "💰 Profilim", "💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    return m

@bot.message_handler(commands=['start'])
def start(message):
    db.c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    db.conn.commit()
    bot.send_message(message.chat.id, "🚀 *Sisteme Hoş Geldin!*", parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def profile(message):
    db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    bal = db.c.fetchone()[0]
    bot.send_message(message.chat.id, f"👤 *Profil*\n\nBakiyeniz: {bal:.2f}₺\nID: `{message.from_user.id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def shop(message):
    bot.send_message(message.chat.id, f"💳 Bakiye paketleri için {ADMIN_USER} ile iletişime geçin. Ödeme sonrası ID numaranıza bakiye eklenecektir.")

# ================= GELİŞMİŞ GÖREV DÜZENLEME SİSTEMİ =================
setup_data = {}

@bot.message_handler(func=lambda m: m.text == "⚙️ Görevlerimi Yönet")
def manage_list(message):
    db.c.execute("SELECT chat_id, title FROM sources WHERE owner_id=?", (message.from_user.id,))
    res = db.c.fetchall()
    if not res:
        bot.send_message(message.chat.id, "❌ Admin olduğunuz kanal bulunamadı.")
        return
    markup = types.InlineKeyboardMarkup()
    for r in res:
        markup.add(types.InlineKeyboardButton(f"📍 {r[1]}", callback_data=f"sel_{r[0]}"))
    bot.send_message(message.chat.id, "Düzenlemek istediğiniz kanalı seçin:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("sel_"))
def show_config(call):
    cid = call.data.split("_")[1]
    db.c.execute("SELECT title, description, link, budget FROM sources WHERE chat_id=?", (cid,))
    d = db.c.fetchone()
    
    text = f"🛠 *GÖREV AYARLARI*\n\n" \
           f"📝 *İsim:* {d[0]}\n" \
           f"ℹ️ *Açıklama:* {d[1]}\n" \
           f"🔗 *Link:* {d[2] if d[2] else 'Eksik'}\n" \
           f"💰 *Kanal Bütçesi:* {d[3]}₺\n\n" \
           f"Değiştirmek istediğiniz alanı seçin veya 'Onayla' diyerek yayına alın."
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 İsim Yaz", callback_data=f"set_title_{cid}"),
        types.InlineKeyboardButton("ℹ️ Açıklama Yaz", callback_data=f"set_desc_{cid}"),
        types.InlineKeyboardButton("🔗 Link Ekle", callback_data=f"set_link_{cid}"),
        types.InlineKeyboardButton("💰 Bütçe Aktar", callback_data=f"set_bud_{cid}")
    )
    markup.add(types.InlineKeyboardButton("✅ HER ŞEYİ ONAYLA VE YAYINLA", callback_data=f"confirm_{cid}"))
    markup.add(types.InlineKeyboardButton("❌ İPTAL ET / REDDET", callback_data="cancel_edit"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

# Teker teker veri girişi
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def ask_input(call):
    _, field, cid = call.data.split("_")
    setup_data[call.from_user.id] = {"f": field, "c": cid}
    bot.send_message(call.message.chat.id, f"💬 Lütfen yeni *{field.upper()}* değerini yazıp gönderin:")

@bot.message_handler(func=lambda m: m.from_user.id in setup_data)
def save_input(message):
    data = setup_data[message.from_user.id]
    f, c, val = data["f"], data["c"], message.text
    
    try:
        if f == "bud":
            db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
            user_bal = db.c.fetchone()[0]
            if user_bal < float(val):
                bot.send_message(message.chat.id, "❌ Profil bakiyeniz yetersiz!")
            else:
                db.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (float(val), message.from_user.id))
                db.c.execute("UPDATE sources SET budget = budget + ? WHERE chat_id = ?", (float(val), c))
                bot.send_message(message.chat.id, "✅ Bütçe kanala aktarıldı.")
        else:
            db.c.execute(f"UPDATE sources SET {f if f!='title' else 'title'} = ? WHERE chat_id = ?", (val, c))
        db.conn.commit()
        bot.send_message(message.chat.id, "✅ Bilgi kaydedildi. 'Görevlerimi Yönet' menüsünden kontrol edip onaylayabilirsiniz.")
    except:
        bot.send_message(message.chat.id, "❌ Hata oluştu.")
    
    del setup_data[message.from_user.id]

# ONAYLAMA VE REDDETME (YAYINLAMA)
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def final_confirm(call):
    cid = call.data.split("_")[1]
    db.c.execute("SELECT link, budget FROM sources WHERE chat_id=?", (cid,))
    d = db.c.fetchone()
    
    if not d[0] or d[1] <= 0:
        bot.answer_callback_query(call.id, "❌ Link veya bütçe olmadan onaylanamaz!", show_alert=True)
    else:
        db.c.execute("UPDATE sources SET is_active=1 WHERE chat_id=?", (cid,))
        db.conn.commit()
        bot.edit_message_text("🚀 *BAŞARILI!*\nGörev onaylandı ve şu an tüm kullanıcılara gösteriliyor.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_edit")
def cancel(call):
    bot.edit_message_text("❌ İşlem iptal edildi.", call.message.chat.id, call.message.message_id)

# ================= GÖREV YAPMA VE ADMİN BAKİYE HANDLERS =================
@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id, {}).get("step") in ["id", "amount"])
def handle_admin(message):
    state = admin_state[message.from_user.id]
    if state["step"] == "id":
        admin_state[message.from_user.id] = {"step": "amount", "target": message.text}
        bot.send_message(message.chat.id, "Tutar yazın:")
    else:
        db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(message.text), state["target"]))
        db.conn.commit()
        bot.send_message(message.chat.id, "Yüklendi.")
        del admin_state[message.from_user.id]

@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def do_task(message):
    db.c.execute("SELECT * FROM sources WHERE is_active=1 AND budget >= reward AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)", (message.from_user.id,))
    res = db.c.fetchall()
    if not res: bot.send_message(message.chat.id, "Görev yok."); return
    t = res[0]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Kanala Git", url=t[4]), types.InlineKeyboardButton("✅ Onayla", callback_data=f"v_{t[0]}_{t[5]}"))
    bot.send_message(message.chat.id, f"📍 {t[2]}\nℹ️ {t[3]}\n💰 {t[5]}₺", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def verify(call):
    _, sid, rew = call.data.split("_")
    db.c.execute("SELECT chat_id, budget FROM sources WHERE source_id=?", (sid,))
    s = db.c.fetchone()
    try:
        if bot.get_chat_member(s[0], call.from_user.id).status in ['member', 'administrator', 'creator']:
            db.c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (float(rew), call.from_user.id))
            db.c.execute("UPDATE sources SET budget=budget-? WHERE source_id=?", (float(rew), sid))
            db.c.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (call.from_user.id, sid))
            db.conn.commit()
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Ödeme yapıldı!")
    except: bot.answer_callback_query(call.id, "Hata!")

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'my_chat_member'])
