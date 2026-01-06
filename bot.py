import telebot
from telebot import types
import sqlite3
import threading
import time
from flask import Flask

# ================= AYARLAR =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877 
ADMIN_USER = "@AlperenTHE"
ZORUNLU_KANAL = "@GorevYapsam"

# Botun görselliğini artırmak için (Bu linkleri kendi görsellerinle değiştirebilirsin)
WELCOME_IMG = "https://i.ibb.co/vYV0YfL/welcome.jpg" 
PACKETS_IMG = "https://i.ibb.co/m0fXm2s/packets.jpg"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ================= SİSTEM DURUMLARI =================
MAINTENANCE_MODE = False
setup_steps = {} # Reklamveren giriş takibi

# ================= VERİTABANI =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_final_ultra_v16.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
            referred_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0
        )''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz Görev', description TEXT DEFAULT 'Açıklama Yok',
            link TEXT, reward REAL DEFAULT 0.5, budget REAL DEFAULT 0, 
            owner_id INTEGER, is_active INTEGER DEFAULT 0
        )''')
        self.c.execute('CREATE TABLE IF NOT EXISTS completed_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER)')
        self.conn.commit()

db = Database()

# ================= ARA KATMANLAR (MIDDLEWARE) =================

@bot.middleware_handler(update_types=['message'])
def check_maintenance(bot_instance, message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **BAKIM MODU**\n\nBot şu an güncelleme aşamasındadır. Lütfen daha sonra tekrar deneyin.")
        return False

# ================= KONTROL FONKSİYONLARI =================

def kanal_kontrol(user_id):
    try:
        uye = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return uye.status in ['member', 'administrator', 'creator']
    except: return False

# ================= KOMUTLAR VE MENÜLER =================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    # Veritabanı Kayıt & Referans Sistemi
    db.c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not db.c.fetchone():
        ref_id = 0
        if len(args) > 1 and args[1].startswith('ref_'):
            try:
                ref_id = int(args[1].replace('ref_', ''))
                if ref_id != user_id:
                    # Referans verene ödül ve bildirim
                    db.c.execute("UPDATE users SET balance = balance + 0.10, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
                    bot.send_message(ref_id, f"👥 **Yeni Referans!**\n\n{message.from_user.first_name} davetinizle katıldı. +0.10₺ kazandınız!")
            except: ref_id = 0
        
        db.c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, ref_id))
        db.conn.commit()

    # Zorunlu Kanal Kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANAL.replace('@','')}"))
        markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data="check_sub"))
        return bot.send_photo(user_id, WELCOME_IMG, caption=f"⚠️ Devam etmek için {ZORUNLU_KANAL} kanalımıza katılmalısın!", reply_markup=markup)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim", "👥 Referanslarım")
    markup.add("💸 Ödeme Talebi", "💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    bot.send_photo(message.chat.id, WELCOME_IMG, caption="🚀 **GÖREV YAPSAM** - Hoş Geldiniz!\nMenüden dilediğiniz işlemi seçebilirsiniz.", reply_markup=markup)

@bot.message_handler(commands=['bakim'])
def toggle_bakim(message):
    if message.from_user.id == ADMIN_ID:
        global MAINTENANCE_MODE
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.send_message(message.chat.id, f"⚙️ Bakım Modu: {'AKTİF' if MAINTENANCE_MODE else 'KAPALI'}")

# ================= BUTON İŞLEMLERİ =================

@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def profile(message):
    db.c.execute("SELECT balance, ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    d = db.c.fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFİL**\n\n💰 Bakiye: {d[0]:.2f}₺\n👥 Referanslar: {d[1]}\n🆔 ID: `{message.from_user.id}`")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def shop(message):
    text = (
        "💎 **BAKİYE PAKETLERİ**\n\n"
        "📦 BRONZ: 20₺ (1 TRC)\n"
        "📦 GÜMÜŞ: 50₺ (2.5 TRX)\n"
        "📦 ALTIN: 100₺ (5 TRX)\n"
        "📦 ELMAS: 200₺ (10 TRX)\n\n"
        "Satın almak için admin'e yazın."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Admin'e Mesaj At", url=f"https://t.me/{ADMIN_USER.replace('@','')}"))
    bot.send_photo(message.chat.id, PACKETS_IMG, caption=text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💸 Ödeme Talebi")
def payout(message):
    bot.send_message(message.chat.id, "⏳ **YAKINDA!**\n\nÖdeme talebi sistemi şu an hazırlanıyor. 20₺ bakiye sonrası admin'e yazabilirsiniz.")

@bot.message_handler(func=lambda m: m.text == "👥 Referanslarım")
def ref_system(message):
    bot_name = bot.get_me().username
    link = f"https://t.me/{bot_name}?start=ref_{message.from_user.id}"
    bot.send_message(message.chat.id, f"👥 **REFERANS LİNKİNİZ:**\n\n`{link}`\n\nHer yeni üye için 0.10₺ kazanırsınız!")

# ================= GÖREV SİSTEMİ (OTOMATİK BÜTÇE UYARISI) =================

@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def tasks(message):
    db.c.execute('''SELECT * FROM sources WHERE is_active=1 AND budget >= reward 
                    AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)''', (message.from_user.id,))
    t = db.c.fetchall()
    if not t: return bot.send_message(message.chat.id, "❌ Şu an aktif görev bulunmuyor.")
    
    x = t[0]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Kanala Git", url=x[4]), types.InlineKeyboardButton("✅ Onayla", callback_data=f"v_{x[0]}_{x[5]}"))
    bot.send_message(message.chat.id, f"📍 **{x[2]}**\n\n📝 {x[3]}\n💰 Ödül: {x[5]}₺", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def verify(call):
    _, sid, rew = call.data.split("_")
    sid, rew = int(sid), float(rew)
    db.c.execute("SELECT chat_id, budget, owner_id, title FROM sources WHERE source_id=?", (sid,))
    s = db.c.fetchone()

    # Bütçe Kontrolü & Uyarı
    if s[1] < rew:
        bot.answer_callback_query(call.id, "❌ Görev bütçesi bitti!", show_alert=True)
        db.c.execute("UPDATE sources SET is_active=0 WHERE source_id=?", (sid,))
        bot.send_message(s[2], f"⚠️ **BÜTÇE UYARISI**\n\n'{s[3]}' görevinizin bütçesi bitti ve yayından kaldırıldı.")
        return

    try:
        status = bot.get_chat_member(s[0], call.from_user.id).status
        if status in ['member', 'administrator', 'creator']:
            db.c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (rew, call.from_user.id))
            db.c.execute("UPDATE sources SET budget=budget-? WHERE source_id=?", (rew, sid))
            db.c.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (call.from_user.id, sid))
            db.conn.commit()
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Ödül verildi!")
        else:
            bot.answer_callback_query(call.id, "❌ Katılmamışsınız!", show_alert=True)
    except: bot.answer_callback_query(call.id, "❌ Hata!")

# ================= GÖREV YÖNETİMİ =================

@bot.message_handler(func=lambda m: m.text == "⚙️ Görevlerimi Yönet")
def manage(message):
    db.c.execute("SELECT chat_id, title FROM sources WHERE owner_id=?", (message.from_user.id,))
    res = db.c.fetchall()
    if not res: return bot.send_message(message.chat.id, "❌ Önce botu kanalınıza admin yapın.")
    
    markup = types.InlineKeyboardMarkup()
    for r in res: markup.add(types.InlineKeyboardButton(f"📡 {r[1]}", callback_data=f"cfg_{r[0]}"))
    bot.send_message(message.chat.id, "Düzenlenecek görev:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cfg_"))
def config(call):
    cid = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 İsim", callback_data=f"ed_title_{cid}"),
        types.InlineKeyboardButton("ℹ️ Açıklama", callback_data=f"ed_desc_{cid}"),
        types.InlineKeyboardButton("🔗 Link", callback_data=f"ed_link_{cid}"),
        types.InlineKeyboardButton("💰 Bütçe Aktar", callback_data=f"ed_bud_{cid}"),
        types.InlineKeyboardButton("✅ YAYINLA", callback_data=f"pub_{cid}")
    )
    bot.edit_message_text("🛠 Görev ayarlarını yapın:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ed_"))
def ed_input(call):
    _, fld, cid = call.data.split("_")
    setup_steps[call.from_user.id] = {"f": fld, "c": cid}
    bot.send_message(call.message.chat.id, f"💬 Yeni {fld} bilgisini gönderin:")

@bot.message_handler(func=lambda m: m.from_user.id in setup_steps)
def save_ed(message):
    data = setup_steps[message.from_user.id]
    f, c, val = data["f"], data["c"], message.text
    if f == "bud":
        db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
        if db.c.fetchone()[0] < float(val): bot.send_message(message.chat.id, "❌ Yetersiz bakiye.")
        else:
            db.c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (float(val), message.from_user.id))
            db.c.execute("UPDATE sources SET budget=budget+? WHERE chat_id=?", (float(val), c))
            bot.send_message(message.chat.id, "✅ Bütçe yüklendi.")
    else:
        db.c.execute(f"UPDATE sources SET {f if f!='title' else 'title'}=? WHERE chat_id=?", (val, c))
    db.conn.commit()
    del setup_steps[message.from_user.id]
    bot.send_message(message.chat.id, "✅ Başarıyla kaydedildi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def publish(call):
    cid = call.data.split("_")[1]
    db.c.execute("UPDATE sources SET is_active=1 WHERE chat_id=?", (cid,))
    db.conn.commit()
    bot.answer_callback_query(call.id, "🚀 Görev yayına girdi!", show_alert=True)

# ================= ADMİN SESSİZ ALGILAMA =================

@bot.my_chat_member_handler()
def detect(message: types.ChatMemberUpdated):
    if message.new_chat_member.status == 'administrator':
        db.c.execute('INSERT OR IGNORE INTO sources (chat_id, owner_id, title) VALUES (?, ?, ?)', 
                      (message.chat.id, message.from_user.id, message.chat.title))
        db.conn.commit()

# ================= RUN & HATA ÖNLEME =================

def run():
    while True:
        try: bot.polling(none_stop=True, interval=2)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    run()
