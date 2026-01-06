import telebot
from telebot import types
import sqlite3
import threading
from flask import Flask

# ================= AYARLAR =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_USER = "@AlperenTHE"
ADMIN_ID = 7904032877 
MAIN_CHANNEL = "@GorevYapsam"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# ================= DATABASE MANTIĞI =================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('gorev_final_v10.db', check_same_thread=False)
        self.c = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Kullanıcılar
        self.c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0
        )''')
        # Görevler
        self.c.execute('''CREATE TABLE IF NOT EXISTS sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            chat_id INTEGER UNIQUE,
            title TEXT DEFAULT 'İsimsiz', 
            description TEXT DEFAULT 'Açıklama Yok',
            link TEXT, 
            reward REAL DEFAULT 0.5, 
            budget REAL DEFAULT 0, 
            owner_id INTEGER, 
            is_active INTEGER DEFAULT 0
        )''')
        # Tamamlananlar
        self.c.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, source_id INTEGER
        )''')
        self.conn.commit()

db = Database()

# ================= ADMİN PANELİ (MANUEL BAKİYE EKLEME) =================

admin_state = {}

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💰 Manuel Bakiye Yükle", callback_data="adm_yukle"))
    markup.add(types.InlineKeyboardButton("📊 İstatistikler", callback_data="adm_stats"))
    bot.send_message(message.chat.id, "👑 *Yönetici Paneli*", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adm_yukle")
def adm_step1(call):
    admin_state[call.from_user.id] = {"step": "id"}
    bot.send_message(call.message.chat.id, "👤 Bakiye yüklenecek kullanıcının **ID** numarasını yazın:")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id, {}).get("step") == "id")
def adm_step2(message):
    admin_state[message.from_user.id] = {"step": "amount", "target": message.text}
    bot.send_message(message.chat.id, f"💰 ID: `{message.text}` için eklenecek **TL tutarını** yazın:")

@bot.message_handler(func=lambda m: admin_state.get(m.from_user.id, {}).get("step") == "amount")
def adm_final(message):
    data = admin_state[message.from_user.id]
    try:
        amount = float(message.text)
        db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, data["target"]))
        db.conn.commit()
        bot.send_message(message.chat.id, f"✅ İşlem Başarılı! `{data['target']}` hesabına `{amount}₺` eklendi.")
        bot.send_message(data["target"], f"🎉 *Bakiyeniz Yüklendi!*\nAdmin tarafından hesabınıza `{amount}₺` tanımlandı.")
    except:
        bot.send_message(message.chat.id, "❌ Hata! ID veya miktar yanlış.")
    admin_state[message.from_user.id] = {}

# ================= OTOMATİK ADMİN ALGILAMA =================

@bot.my_chat_member_handler()
def handle_admin_added(message: types.ChatMemberUpdated):
    if message.new_chat_member.status == 'administrator':
        db.c.execute('INSERT OR IGNORE INTO sources (chat_id, owner_id) VALUES (?, ?)', (message.chat.id, message.from_user.id))
        db.conn.commit()
        bot.send_message(message.from_user.id, f"✅ *Kanal Algılandı:* {message.chat.title}\n\nBotu admin yaptığınız için teşekkürler. 'Görevlerimi Yönet' kısmından detayları girip yayına alabilirsiniz.")

# ================= ANA MENÜ VE GÖREVLER =================

def main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎯 Görev Yap", "💰 Profilim")
    markup.add("💳 Bakiye Satın Al", "⚙️ Görevlerimi Yönet")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    db.c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (message.from_user.id,))
    db.conn.commit()
    bot.send_message(message.chat.id, "🚀 *Görev Yapsam Sistemine Hoş Geldiniz!*", parse_mode="Markdown", reply_markup=main_markup())

@bot.message_handler(func=lambda m: m.text == "🎯 Görev Yap")
def show_tasks(message):
    db.c.execute('''SELECT * FROM sources WHERE is_active=1 AND budget >= reward 
                    AND source_id NOT IN (SELECT source_id FROM completed_tasks WHERE user_id=?)''', (message.from_user.id,))
    tasks = db.c.fetchall()
    if not tasks:
        bot.send_message(message.chat.id, "❌ Şu an aktif görev yok.")
        return
    t = tasks[0]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔗 Göreve Git", url=t[4]))
    markup.add(types.InlineKeyboardButton("✅ Onayla", callback_data=f"check_{t[0]}_{t[5]}"))
    bot.send_message(message.chat.id, f"📋 *GÖREV:* {t[2]}\n📝 *Açıklama:* {t[3]}\n💰 *Ödül:* {t[5]}₺", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Profilim")
def profile(message):
    db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    bal = db.c.fetchone()[0]
    bot.send_message(message.chat.id, f"👤 *Profil Bilgilerin*\n\n💰 Bakiye: {bal:.2f}₺\n🆔 ID: `{message.from_user.id}`\n\nDestek: {ADMIN_USER}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💳 Bakiye Satın Al")
def buy_bal(message):
    text = f"💎 *REKLAM PAKETLERİ*\n\n📦 20₺ (1 TRC)\n📦 50₺ (2.5 TRX)\n📦 100₺ (5 TRX)\n📦 200₺ (10 TRX)\n\nBakiye almak için {ADMIN_USER} adresine yazın. Ödeme sonrası ID numaranıza manuel yükleme yapılacaktır."
    bot.send_message(message.chat.id, text)

# ================= GÖREV AYARLAMA SİSTEMİ =================

user_setup = {}

@bot.message_handler(func=lambda m: m.text == "⚙️ Görevlerimi Yönet")
def manage_tasks(message):
    db.c.execute("SELECT chat_id, title FROM sources WHERE owner_id=?", (message.from_user.id,))
    res = db.c.fetchall()
    if not res:
        bot.send_message(message.chat.id, "❌ Botu admin yaptığınız bir kanal bulunamadı.")
        return
    markup = types.InlineKeyboardMarkup()
    for r in res:
        markup.add(types.InlineKeyboardButton(f"⚙️ {r[1]}", callback_data=f"edit_{r[0]}"))
    bot.send_message(message.chat.id, "Düzenlemek istediğiniz kanalı seçin:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def edit_panel(call):
    c_id = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 İsim", callback_data=f"set_title_{c_id}"),
        types.InlineKeyboardButton("ℹ️ Açıklama", callback_data=f"set_desc_{c_id}"),
        types.InlineKeyboardButton("🔗 Link", callback_data=f"set_link_{c_id}"),
        types.InlineKeyboardButton("💰 Bütçe Aktar", callback_data=f"set_bud_{c_id}"),
        types.InlineKeyboardButton("🚀 YAYINLA", callback_data=f"pub_{c_id}")
    )
    bot.edit_message_text("🛠 Görev ayarlarını yapın:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def setup_input(call):
    _, field, c_id = call.data.split("_")
    user_setup[call.from_user.id] = {"field": field, "chat_id": c_id}
    bot.send_message(call.message.chat.id, f"Lütfen *{field}* değerini gönderin:")

@bot.message_handler(func=lambda m: m.from_user.id in user_setup)
def save_setup(message):
    data = user_setup[message.from_user.id]
    field, c_id = data["field"], data["chat_id"]
    val = message.text
    
    if field == "bud":
        db.c.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
        u_bal = db.c.fetchone()[0]
        if u_bal < float(val):
            bot.send_message(message.chat.id, "❌ Profil bakiyeniz yetersiz!")
        else:
            db.c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (float(val), message.from_user.id))
            db.c.execute("UPDATE sources SET budget = budget + ? WHERE chat_id = ?", (float(val), c_id))
            bot.send_message(message.chat.id, "✅ Bakiye başarıyla göreve aktarıldı.")
    else:
        mapping = {"title": "title", "desc": "description", "link": "link"}
        db.c.execute(f"UPDATE sources SET {mapping[field]} = ? WHERE chat_id = ?", (val, c_id))
    
    db.conn.commit()
    del user_setup[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def publish_now(call):
    c_id = call.data.split("_")[1]
    db.c.execute("UPDATE sources SET is_active=1 WHERE chat_id=?", (c_id,))
    db.conn.commit()
    bot.answer_callback_query(call.id, "🚀 Görev Yayına Alındı!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def final_verify(call):
    _, s_id, reward = call.data.split("_")
    s_id, reward = int(s_id), float(reward)
    db.c.execute("SELECT chat_id, budget, owner_id FROM sources WHERE source_id=?", (s_id,))
    s = db.c.fetchone()
    
    if s[1] < reward:
        bot.answer_callback_query(call.id, "❌ Bakiye bitti!", show_alert=True)
        db.c.execute("UPDATE sources SET is_active=0 WHERE source_id=?", (s_id,))
        return

    try:
        if bot.get_chat_member(s[0], call.from_user.id).status in ['member', 'administrator', 'creator']:
            db.c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, call.from_user.id))
            db.c.execute("UPDATE sources SET budget = budget - ? WHERE source_id = ?", (reward, s_id))
            db.c.execute("INSERT INTO completed_tasks (user_id, source_id) VALUES (?, ?)", (call.from_user.id, s_id))
            db.conn.commit()
            bot.answer_callback_query(call.id, "✅ Onaylandı!")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Katılmamışsınız!", show_alert=True)
    except:
        bot.answer_callback_query(call.id, "❌ Bot yetki hatası!")

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000)).start()
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'my_chat_member'])
