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

# Middleware ve Conflict hataları için özel bot tanımlaması
bot = telebot.TeleBot(TOKEN, threaded=False, use_class_middlewares=True)
app = Flask(__name__)

# ================= SİSTEM DURUMLARI =================
MAINTENANCE_MODE = False
setup_steps = {} # Reklamveren girişleri için
admin_action = {} # Admin bakiye işlemleri için

# ================= VERİTABANI SİSTEMİ =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_v20_final.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Kullanıcılar
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, 
            referred_by INTEGER DEFAULT 0, ref_count INTEGER DEFAULT 0
        )''')
        # Kanallar/Görevler
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz Görev', description TEXT DEFAULT 'Açıklama yok',
            link TEXT, reward REAL DEFAULT 0.5, budget REAL DEFAULT 0, 
            owner_id INTEGER, is_active INTEGER DEFAULT 0
        )''')
        # Tamamlanan Görevler
        self.c.execute('CREATE TABLE IF NOT EXISTS completed_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER)')
        self.conn.commit()

db = Database()

# ================= BAKIM MODU (MIDDLEWARE) =================
@bot.middleware_handler(update_types=['message'])
def check_maintenance(bot_instance, message):
    if MAINTENANCE_MODE and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 **BOT BAKIMDADIR**\n\nŞu an hizmet veremiyoruz, lütfen daha sonra tekrar deneyin.")
        return False

# ================= KONTROL ARAÇLARI =================
def kanal_kontrol(user_id):
    try:
        uye = bot.get_chat_member(ZORUNLU_KANAL, user_id)
        return uye.status in ['member', 'administrator', 'creator']
    except: return False

# ================= ANA KOMUTLAR =================
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
                    bot.send_message(ref_id, f"👥 **Yeni Referans!**\n\nBir kullanıcı davetinizle katıldı. +0.10₺ kazandınız!")
            except: ref_id = 0
        db.c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, ref_id))
        db.conn.commit()

    # Zorunlu Kanal Kontrolü
    if not kanal_kontrol(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Kanala Katıl", url=f"https://t.me/{ZORUNLU_KANAL.replace('@','')}"))
        markup.add(types.InlineKeyboardButton("🔄 Katıldım, Kontrol Et", callback_data="check_sub"))
        return bot.send_photo(user_id, WELCOME_IMG, caption=f"⚠️ Devam etmek için {ZORUNLU_KANAL} kanalımıza katılmalısın!", reply_markup=markup)

    # Menü Butonları
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim", "👥 Referanslarım")
    markup.add("💸 Ödeme Talebi", "💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    if user_id == ADMIN_ID:
        markup.add("👑 Admin Paneli")
    
    bot.send_photo(message.chat.id, WELCOME_IMG, caption="🚀 **GÖREV YAPSAM** - Kazanç Kapısına Hoş Geldiniz!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def sub_check(call):
    if kanal_kontrol(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Henüz kanala katılmamışsınız!", show_alert=True)

# ================= ADMIN PANELİ =================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Paneli" and m.from_user.id == ADMIN_ID)
def admin_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💰 Kullanıcıya Bakiye Yükle", callback_data="adm_pay"),
        types.InlineKeyboardButton("🛠 Bakım Modu Aç/Kapat", callback_data="adm_maint"),
        types.InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats")
    )
    bot.send_message(message.chat.id, "👑 **Admin Kontrol Paneli**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_logic(call):
    if call.data == "adm_maint":
        global MAINTENANCE_MODE
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        bot.answer_callback_query(call.id, f"Bakım Modu: {'AÇIK' if MAINTENANCE_MODE else 'KAPALI'}", show_alert=True)
    elif call.data == "adm_pay":
        admin_action[call.from_user.id] = {"step": "id"}
        bot.send_message(call.message.chat.id, "👤 Bakiye yüklenecek kullanıcının **ID** numarasını yazın:")
    elif call.data == "adm_stats":
        db.c.execute("SELECT COUNT(*) FROM users")
        u = db.c.fetchone()[0]
        db.c.execute("SELECT COUNT(*) FROM sources WHERE is_active=1")
        s = db.c.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📊 **İstatistikler**\n\nKullanıcı: {u}\nAktif Görev: {s}")

@bot.message_handler(func=lambda m: m.from_user.id in admin_action)
def admin_input_handler(message):
    data = admin_action[message.from_user.id]
    if data["step"] == "id":
        admin_action[message.from_user.id] = {"step": "amt", "target": message.text}
        bot.send_message(message.chat.id, "💰 Yüklenecek tutarı (₺) yazın:")
    else:
        try:
            amt = float(message.text)
            db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, data["target"]))
            db.conn.commit()
            bot.send_message(message.chat.id, f"✅ {data['target']} ID'sine {amt}₺ yüklendi.")
            bot.send_message(data["target"], f"🎉 Hesabınıza Admin tarafından {amt}₺ eklendi!")
        except: bot.send_message(message.chat.id, "❌ Hatalı giriş.")
        del admin_action[message.from_user.id]

# ================= GÖREV SİSTEMİ & BÜTÇE KONTROLÜ =================
@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def find_task(message):
    db.c.execute('''SELECT * FROM sources WHERE is_active=1 AND budget >= reward 
                    AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)''', (message.from_user.id,))
    res = db.c.fetchall()
    if not res: return bot.send_message(message.chat.id, "❌ Aktif görev kalmadı.")
    
    t = res[0]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Kanala Git", url=t[4]), 
               types.InlineKeyboardButton("✅ Katıldım / Onayla", callback_data=f"v_{t[0]}_{t[5]}"))
    bot.send_message(message.chat.id, f"📍 **{t[2]}**\n\nℹ️ {t[3]}\n💰 Ödül: {t[5]}₺", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def verify_task(call):
    _, sid, rew = call.data.split("_")
    db.c.execute("SELECT chat_id, budget, owner_id, title FROM sources WHERE source_id=?", (int(sid),))
    s = db.c.fetchone()
    
    if s[1] < float(rew):
        db.c.execute("UPDATE sources SET is_active=0 WHERE source_id=?", (int(sid),))
        bot.send_message(s[2], f"⚠️ **BÜTÇE BİTTİ:** '{s[3]}' göreviniz durduruldu.")
        return bot.answer_callback_query(call.id, "❌ Bu görev bütçesi tükendi!", show_alert=True)

    try:
        status = bot.get_chat_member(s[0], call.from_user.id).status
        if status in ['member', 'administrator', 'creator']:
            db.c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (float(rew), call.from_user.id))
            db.c.execute("UPDATE sources SET budget=budget-? WHERE source_id=?", (float(rew), int(sid)))
            db.c.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (call.from_user.id, int(sid)))
            db.conn.commit()
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ Tebrikler! Ödül bakiyenize eklendi.")
        else:
            bot.answer_callback_query(call.id, "❌ Henüz katılmamışsınız!", show_alert=True)
    except: bot.answer_callback_query(call.id, "❌ Bot kanalda admin değil!")

# ================= GÖREV YÖNETİMİ (REKLAMVEREN) =================
@bot.message_handler(func=lambda m: m.text == "⚙️ Görevlerimi Yönet")
def manage_tasks(message):
    db.c.execute("SELECT chat_id, title FROM sources WHERE owner_id=?", (message.from_user.id,))
    res = db.c.fetchall()
    if not res: return bot.send_message(message.chat.id, "❌ Admin olduğunuz bir kanal bulunamadı.")
    
    markup = types.InlineKeyboardMarkup()
    for r in res: markup.add(types.InlineKeyboardButton(f"📡 {r[1]}", callback_data=f"cfg_{r[0]}"))
    bot.send_message(message.chat.id, "Yönetmek istediğiniz görevi seçin:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cfg_"))
def config_menu(call):
    cid = call.data.split("_")[1]
    db.c.execute("SELECT title, description, budget, is_active FROM sources WHERE chat_id=?", (cid,))
    d = db.c.fetchone()
    durum = "✅ Yayında" if d[3] == 1 else "❌ Durduruldu"
    text = f"⚙️ **GÖREV AYARLARI**\n\n📌 Durum: {durum}\n📝 İsim: {d[0]}\nℹ️ Açıklama: {d[1]}\n💰 Bütçe: {d[2]}₺"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 İsim", callback_data=f"ed_title_{cid}"),
        types.InlineKeyboardButton("ℹ️ Açıklama", callback_data=f"ed_desc_{cid}"),
        types.InlineKeyboardButton("🔗 Link", callback_data=f"ed_link_{cid}"),
        types.InlineKeyboardButton("💰 Bütçe Aktar", callback_data=f"ed_bud_{cid}"),
        types.InlineKeyboardButton("🚀 YAYINLA", callback_data=f"pub_{cid}"),
        types.InlineKeyboardButton("🛑 DURDUR", callback_data=f"stop_{cid}")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ed_"))
def edit_logic(call):
    _, fld, cid = call.data.split("_")
    setup_steps[call.from_user.id] = {"f": fld, "c": cid}
    bot.send_message(call.message.chat.id, f"💬 Yeni **{fld}** bilgisini yazıp gönderin:")

@bot.message_handler(func=lambda m: m.from_user.id in setup_steps)
def save_edit(message):
    s = setup_steps[message.from_user.id]
    f, c, val = s["f"], s["c"], message.text
    if f == "bud":
        try:
            amt = float(val)
            db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
            if db.c.fetchone()[0] < amt: bot.send_message(message.chat.id, "❌ Bakiye yetersiz.")
            else:
                db.c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amt, message.from_user.id))
                db.c.execute("UPDATE sources SET budget=budget+? WHERE chat_id=?", (amt, c))
                bot.send_message(message.chat.id, "✅ Bütçe yüklendi.")
        except: bot.send_message(message.chat.id, "❌ Sayı giriniz.")
    else:
        db.c.execute(f"UPDATE sources SET {f if f!='title' else 'title'}=? WHERE chat_id=?", (val, c))
    db.conn.commit()
    del setup_steps[message.from_user.id]
    bot.send_message(message.chat.id, "✅ Bilgi kaydedildi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("pub_", "stop_")))
def status_toggle(call):
    mode = 1 if call.data.startswith("pub_") else 0
    cid = call.data.split("_")[1]
    db.c.execute("UPDATE sources SET is_active=? WHERE chat_id=?", (mode, cid))
    db.conn.commit()
    bot.answer_callback_query(call.id, "Başarılı!", show_alert=True)

# ================= KULLANICI FONKSİYONLARI =================
@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def profile(message):
    db.c.execute("SELECT balance, ref_count FROM users WHERE user_id=?", (message.from_user.id,))
    d = db.c.fetchone()
    bot.send_message(message.chat.id, f"👤 **PROFİL**\n\n💰 Bakiye: {d[0]:.2f}₺\n👥 Toplam Referans: {d[1]}\n🆔 ID: `{message.from_user.id}`")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def shop(message):
    text = "💎 **BAKİYE PAKETLERİ**\n\n📦 BRONZ: 20₺\n📦 GÜMÜŞ: 50₺\n📦 ALTIN: 100₺\n📦 ELMAS: 200₺\n\nSatın almak için: @AlperenTHE"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Admin'e Yaz & Dekont Gönder", url=f"https://t.me/{ADMIN_USER.replace('@','')}"))
    bot.send_photo(message.chat.id, PACKETS_IMG, caption=text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 Referanslarım")
def ref_panel(message):
    link = f"https://t.me/{bot.get_me().username}?start=ref_{message.from_user.id}"
    bot.send_message(message.chat.id, f"👥 **Davet Linkiniz:**\n`{link}`\n\nHer aktif üye için 0.10₺ kazanırsınız!")

@bot.message_handler(func=lambda m: m.text == "💸 Ödeme Talebi")
def cashout(message):
    bot.send_message(message.chat.id, "⏳ **YAKINDA!**\nSistem güncelleniyor. 20₺ bakiyeye ulaştığınızda admin'e başvurabilirsiniz.")

@bot.my_chat_member_handler()
def auto_detect(message: types.ChatMemberUpdated):
    if message.new_chat_member.status == 'administrator':
        db.c.execute('INSERT OR IGNORE INTO sources (chat_id, owner_id, title) VALUES (?, ?, ?)', 
                      (message.chat.id, message.from_user.id, message.chat.title))
        db.conn.commit()

# ================= BOTU BAŞLAT =================
def run_bot():
    bot.remove_webhook() # 409 Conflict çözümünün anahtarı
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=30)
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    run_bot()
