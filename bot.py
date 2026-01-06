import telebot
from telebot import types, apihelper
import sqlite3
import threading
import time
from flask import Flask

# ================= 1. HATA ÖNLEYİCİ AYARLAR =================
apihelper.ENABLE_MIDDLEWARE = True # Middleware hatasını çözer

# ================= 2. KONFİGÜRASYON =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877 
ADMIN_USER = "@AlperenTHE"
ZORUNLU_KANAL = "@GorevYapsam"

# Görseller
WELCOME_IMG = "https://i.ibb.co/vYV0YfL/welcome.jpg" 
PACKETS_IMG = "https://i.ibb.co/m0fXm2s/packets.jpg"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Durum Değişkenleri
MAINTENANCE_MODE = False
admin_action = {} 
setup_steps = {}

# ================= 3. VERİTABANI YÖNETİMİ =================
def get_db_connection():
    conn = sqlite3.connect('gorev_final_v22.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
        referred_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sources (
        source_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE,
        title TEXT DEFAULT 'İsimsiz Görev', description TEXT DEFAULT 'Yok',
        link TEXT, reward REAL DEFAULT 0.5, budget REAL DEFAULT 0, 
        owner_id INTEGER, is_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# ================= 4. MIDDLEWARE (BAKIM MODU) =================
@bot.middleware_handler(update_types=['message'])
def check_maintenance(bot_instance, message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **BAKIM MODU**\n\nBot şu an geliştirme aşamasındadır. Lütfen daha sonra tekrar deneyin.")
        return False

# ================= 5. ANA FONKSİYONLAR =================

def check_sub(user_id):
    try:
        member = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kayıt & Ref
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        ref_id = 0
        args = message.text.split()
        if len(args) > 1 and args[1].startswith('ref_'):
            try:
                ref_id = int(args[1].replace('ref_', ''))
                if ref_id != uid:
                    c.execute("UPDATE users SET balance = balance + 0.10, ref_count = ref_count + 1 WHERE user_id = ?", (ref_id,))
                    bot.send_message(ref_id, "👥 **Yeni Referans!**\n\nBir kullanıcı linkinizle katıldı. +0.10₺ kazandınız!")
            except: pass
        c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (uid, ref_id))
        conn.commit()

    if not check_sub(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANAL.replace('@','')}"))
        markup.add(types.InlineKeyboardButton("🔄 Kontrol Et", callback_data="recheck"))
        return bot.send_photo(uid, WELCOME_IMG, caption=f"⚠️ Devam etmek için @{ZORUNLU_KANAL.replace('@','')} kanalına katılmalısın!", reply_markup=markup)

    # Menü
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim", "👥 Referanslarım")
    markup.add("💸 Ödeme Talebi", "💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    if uid == ADMIN_ID: markup.add("👑 Admin Paneli")
    
    bot.send_photo(message.chat.id, WELCOME_IMG, caption="🚀 **GÖREV YAPSAM**\nHoş geldiniz! Menüyü kullanarak hemen kazanmaya başlayın.", reply_markup=markup)
    conn.close()

# ================= 6. BUTON İŞLEMLERİ =================

@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def show_profile(message):
    conn = get_db_connection()
    u = conn.execute("SELECT balance, ref_count FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFİL**\n\n💰 Bakiye: {u['balance']:.2f}₺\n👥 Referanslar: {u['ref_count']}\n🆔 ID: `{message.from_user.id}`")
    conn.close()

@bot.message_handler(func=lambda m: m.text == "💸 Ödeme Talebi")
def payout_status(message):
    # İstediğin gibi şuanlık ödeme özelliğini pasif tutuyoruz
    bot.send_message(message.chat.id, "⏳ **ÖDEME SİSTEMİ YAKINDA**\n\nŞu an bakiye biriktirme aşamasındayız. Çok yakında otomatik çekim sistemimiz aktif olacaktır!")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def buy_balance(message):
    text = "💎 **REKLAM VERME PAKETLERİ**\n\n📦 20₺ | 50₺ | 100₺ | 200₺\n\nBakiyenizle kendi kanalınızın reklamını yapabilirsiniz.\nSatın alım için: @AlperenTHE"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Admin ile İletişim", url=f"https://t.me/{ADMIN_USER.replace('@','')}"))
    bot.send_photo(message.chat.id, PACKETS_IMG, caption=text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 Referanslarım")
def ref_info(message):
    link = f"https://t.me/{bot.get_me().username}?start=ref_{message.from_user.id}"
    bot.send_message(message.chat.id, f"👥 **REFERANS SİSTEMİ**\n\nLinkinizle her gelen üye için **0.10₺** kazanırsınız.\n\n🔗 Linkin:\n`{link}`")

# ================= 7. ADMİN PANELİ =================

@bot.message_handler(func=lambda m: m.text == "👑 Admin Paneli" and m.from_user.id == ADMIN_ID)
def admin_p(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💰 Kullanıcıya Bakiye Yükle", callback_data="ap_pay"),
        types.InlineKeyboardButton("🛠 Bakım Modu Aktif/Deaktif", callback_data="ap_maint"),
        types.InlineKeyboardButton("📊 Genel İstatistikler", callback_data="ap_stats")
    )
    bot.send_message(message.chat.id, "👑 **Yönetici Paneli**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ap_"))
def admin_calls(call):
    if call.data == "ap_maint":
        global MAINTENANCE_MODE
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.answer_callback_query(call.id, f"Bakım: {'AÇIK' if MAINTENANCE_MODE else 'KAPALI'}", show_alert=True)
    elif call.data == "ap_pay":
        admin_action[call.from_user.id] = "waiting_id"
        bot.send_message(call.message.chat.id, "👤 Bakiye yüklenecek kullanıcı ID:")
    elif call.data == "ap_stats":
        conn = get_db_connection()
        count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
        bot.send_message(call.message.chat.id, f"📊 **Bot Durumu**\n\nToplam Kayıtlı Üye: {count}")
        conn.close()

# Admin Giriş Yakalayıcı
@bot.message_handler(func=lambda m: m.from_user.id in admin_action)
def ap_input(message):
    state = admin_action[message.from_user.id]
    if state == "waiting_id":
        admin_action[message.from_user.id] = {"target": message.text, "step": "waiting_amt"}
        bot.send_message(message.chat.id, "💰 Eklenecek miktar (Sadece sayı):")
    else:
        try:
            amt = float(message.text)
            conn = get_db_connection()
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, admin_action[message.from_user.id]["target"]))
            conn.commit()
            conn.close()
            bot.send_message(message.chat.id, "✅ Başarıyla yüklendi.")
            bot.send_message(admin_action[message.from_user.id]["target"], f"🎁 Hesabınıza {amt}₺ bakiye tanımlandı!")
        except: bot.send_message(message.chat.id, "❌ Hata oluştu.")
        del admin_action[message.from_user.id]

# ================= 8. GÖREV YAPMA SİSTEMİ =================

@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def find_task(message):
    conn = get_db_connection()
    task = conn.execute('''SELECT * FROM sources WHERE is_active=1 AND budget >= reward 
                         AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)''', (message.from_user.id,)).fetchone()
    if not task:
        return bot.send_message(message.chat.id, "❌ Şu an yeni görev bulunmuyor.")
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Kanala Katıl", url=task['link']), 
               types.InlineKeyboardButton("✅ Kontrol Et", callback_data=f"check_{task['source_id']}_{task['reward']}"))
    bot.send_message(message.chat.id, f"📍 **{task['title']}**\n💰 Ödül: {task['reward']}₺", reply_markup=markup)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def verify_task(call):
    _, sid, rew = call.data.split("_")
    conn = get_db_connection()
    s = conn.execute("SELECT chat_id, title, owner_id FROM sources WHERE source_id=?", (sid,)).fetchone()
    
    try:
        status = bot.get_chat_member(s['chat_id'], call.from_user.id).status
        if status in ['member', 'administrator', 'creator']:
            conn.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (float(rew), call.from_user.id))
            conn.execute("UPDATE sources SET budget = budget - ? WHERE source_id = ?", (float(rew), sid))
            conn.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (call.from_user.id, sid))
            conn.commit()
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, f"✅ Kazandın: {rew}₺", show_alert=False)
        else:
            bot.answer_callback_query(call.id, "❌ Önce kanala katılmalısın!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Bot kanalda yetkili değil!", show_alert=True)
    conn.close()

# ================= 9. ÇALIŞTIRMA =================

def bot_polling():
    # 409 Conflict hatasını çözmek için polling başlatmadan önce temizlik
    bot.remove_webhook()
    time.sleep(1)
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=20)
        except Exception as e:
            print(f"Polling Hatası: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot_polling()
