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

# Görsel Linkleri
WELCOME_IMG = "https://i.ibb.co/vYV0YfL/welcome.jpg" 
PACKETS_IMG = "https://i.ibb.co/m0fXm2s/packets.jpg"

# ÖNEMLİ: Middleware hatasını düzeltmek için enable_middleware=True ekliyoruz
bot = telebot.TeleBot(TOKEN, threaded=False, use_class_middlewares=True)
app = Flask(__name__)

# ================= SİSTEM DURUMLARI =================
MAINTENANCE_MODE = False
setup_steps = {} 
admin_action = {} 

# ================= VERİTABANI =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_v18.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
            referred_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0
        )''')
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz Görev', description TEXT DEFAULT 'Yok',
            link TEXT, reward REAL DEFAULT 0.5, budget REAL DEFAULT 0, 
            owner_id INTEGER, is_active INTEGER DEFAULT 0
        )''')
        self.c.execute('CREATE TABLE IF NOT EXISTS completed_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER)')
        self.conn.commit()

db = Database()

# ================= BAKIM MODU (MIDDLEWARE) =================
# Loglardaki hatayı düzelten kısım:
@bot.middleware_handler(update_types=['message'])
def check_maintenance(bot_instance, message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **BOT BAKIMDADIR**\n\nŞu an hizmet veremiyoruz, lütfen daha sonra tekrar deneyin.")
        return False # İşlemi durdurur

# ================= ANA MENÜ VE START =================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    # Kayıt & Referans Sistemi
    db.c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not db.c.fetchone():
        args = message.text.split()
        ref_id = 0
        if len(args) > 1 and args[1].startswith('ref_'):
            try:
                ref_id = int(args[1].replace('ref_', ''))
                if ref_id != user_id:
                    db.c.execute("UPDATE users SET balance = balance + 0.10, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
                    bot.send_message(ref_id, "👥 **Referans Kazancı!**\n\nBir kullanıcı davetinle katıldı. +0.10₺ eklendi!")
            except: ref_id = 0
        db.c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, ref_id))
        db.conn.commit()

    # Zorunlu Kanal Kontrolü
    try:
        uye = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        if uye.status not in ['member', 'administrator', 'creator']:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANAL.replace('@','')}"))
            return bot.send_photo(user_id, WELCOME_IMG, caption=f"⚠️ Devam etmek için kanalımıza katılmalısın!", reply_markup=markup)
    except: pass

    # Menü Oluşturma
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim", "👥 Referanslarım")
    markup.add("💸 Ödeme Talebi", "💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    if user_id == ADMIN_ID:
        markup.add("👑 Admin Paneli")
    
    bot.send_photo(message.chat.id, WELCOME_IMG, caption="🚀 **GÖREV YAPSAM** - Hoş Geldin!", reply_markup=markup)

# ================= ADMIN PANELİ =================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Paneli" and m.from_user.id == ADMIN_ID)
def admin_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💰 Kullanıcıya Bakiye Yükle", callback_data="adm_pay"),
        types.InlineKeyboardButton("🛠 Bakım Modu Aç/Kapat", callback_data="adm_maint"),
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats")
    )
    bot.send_message(message.chat.id, "👑 **Yönetici Paneli**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_clicks(call):
    if call.data == "adm_maint":
        global MAINTENANCE_MODE
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.answer_callback_query(call.id, f"Bakım Modu: {'AKTİF' if MAINTENANCE_MODE else 'KAPALI'}", show_alert=True)
    
    elif call.data == "adm_pay":
        admin_action[call.from_user.id] = {"step": "id"}
        bot.send_message(call.message.chat.id, "👤 Kullanıcı ID numarasını gönderin:")

    elif call.data == "adm_stats":
        db.c.execute("SELECT COUNT(*) FROM users")
        total_u = db.c.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📊 **Bot Özeti**\n\nKullanıcı Sayısı: {total_u}")

# Admin Bakiye Giriş Yönetimi
@bot.message_handler(func=lambda m: m.from_user.id in admin_action)
def handle_admin_pay(message):
    action = admin_action[message.from_user.id]
    if action["step"] == "id":
        admin_action[message.from_user.id] = {"step": "amt", "target": message.text}
        bot.send_message(message.chat.id, "💰 Eklenecek bakiye miktarını yazın:")
    else:
        try:
            amt = float(message.text)
            db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, action["target"]))
            db.conn.commit()
            bot.send_message(message.chat.id, "✅ İşlem Başarılı!")
            bot.send_message(action["target"], f"🎁 Hesabınıza {amt}₺ bakiye eklendi!")
        except: bot.send_message(message.chat.id, "❌ Geçersiz miktar.")
        del admin_action[message.from_user.id]

# ================= STANDART ÖZELLİKLER =================
@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def profile(message):
    db.c.execute("SELECT balance, ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    d = db.c.fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFİL**\n\n💰 Bakiye: {d[0]:.2f}₺\n👥 Ref: {d[1]}\n🆔 ID: `{message.from_user.id}`")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def packages(message):
    text = "💎 **REKLAM PAKETLERİ**\n\n📦 20₺ | 50₺ | 100₺ | 200₺\n\nSatın almak için: @AlperenTHE"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Admin'e Yaz", url=f"https://t.me/{ADMIN_USER.replace('@','')}"))
    bot.send_photo(message.chat.id, PACKETS_IMG, caption=text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 Referanslarım")
def ref_link(message):
    link = f"https://t.me/{bot.get_me().username}?start=ref_{message.from_user.id}"
    bot.send_message(message.chat.id, f"👥 **Davet Linkin:**\n`{link}`\n\nHer üye için 0.10₺ kazanırsın.")

# ================= ÇALIŞTIRMA & HATA ÖNLEME =================
# Loglardaki 409 hatasını engellemek için polling interval artırıldı
def bot_run():
    # Çakışmayı önlemek için önce webhook varsa sileriz
    bot.remove_webhook()
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=30)
        except Exception as e:
            print(f"Polling Hatası: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot_run()
