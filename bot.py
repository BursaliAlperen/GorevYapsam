import logging
import random
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import MessageToForwardNotFound
import firebase_admin
from firebase_admin import credentials, firestore, storage
import asyncio

# ================= CONFIG =================
TOKEN = "8465270393:AAGu8J5m8taovdjiffbU8LFc-9XbA1dv_co"
ADMIN_ID = 7904032877
FORCED_CHANNELS = ["@GorevYapsam"]  # Sadece bir kanal
FIREBASE_JSON = "firebase.json"
# ==========================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# ================= FIREBASE =================
cred = credentials.Certificate(FIREBASE_JSON)
firebase_admin.initialize_app(cred)
db = firestore.client()
# ============================================

# ================= HELPERS =================
async def is_member(user_id, channel):
    try:
        m = await bot.get_chat_member(channel, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

async def forced_check(user_id):
    for ch in FORCED_CHANNELS:
        if not await is_member(user_id, ch):
            return False
    return True

def user_ref(uid):
    return db.collection("users").document(str(uid))

def add_balance(uid, amount):
    ref = user_ref(uid)
    ref.set({"balance": firestore.Increment(amount)}, merge=True)

def get_balance(uid):
    doc = user_ref(uid).get()
    return doc.to_dict().get("balance", 0) if doc.exists else 0

def get_user(uid):
    doc = user_ref(uid).get()
    return doc.to_dict() if doc.exists else None
# ============================================

# ================= START =================
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = msg.from_user.id
    user_ref(uid).set({
        "joined": time.time(),
        "balance": 0,
        "username": msg.from_user.username,
        "first_name": msg.from_user.first_name,
        "last_active": time.time()
    }, merge=True)
    
    if not await forced_check(uid):
        kb = InlineKeyboardMarkup()
        for ch in FORCED_CHANNELS:
            kb.add(InlineKeyboardButton("📢 Kanalımıza Katıl", url=f"https://t.me/{ch[1:]}"))
        kb.add(InlineKeyboardButton("✅ Kontrol Et", callback_data="recheck"))
        await msg.answer("""🚫 <b>Görev yapmak için önce kanalımıza katılmalısın!</b>

📌 Kuralımız basit:
1️⃣ Aşağıdaki butondan kanala katıl
2️⃣ 'Kontrol Et' butonuna tıkla
3️⃣ Görev yapmaya başla 💰""", reply_markup=kb)
        return
    
    await main_menu(msg)

@dp.callback_query_handler(lambda c: c.data == "recheck")
async def recheck(c: types.CallbackQuery):
    uid = c.from_user.id
    if await forced_check(uid):
        await c.message.delete()
        await main_menu(c.message)
        await c.answer("✅ Teşekkürler! Şimdi görev yapabilirsin.", show_alert=True)
    else:
        await c.answer("❌ Hâlâ kanalda değilsin. Katıldıktan sonra tekrar dene.", show_alert=True)

async def main_menu(msg):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Görevler", callback_data="tasks"),
        InlineKeyboardButton("💰 Bakiyem", callback_data="balance"),
        InlineKeyboardButton("📢 Reklam Ver", callback_data="ads"),
        InlineKeyboardButton("🏆 Lider Tablosu", callback_data="lb"),
        InlineKeyboardButton("ℹ️ Yardım", callback_data="help"),
    )
    await msg.answer("""🏠 <b>Ana Menü</b>

Hoş geldin! Görev yaparak para kazanmaya hazır mısın?

💡 <b>Nasıl çalışır?</b>
1. Görev seç
2. İsteneni yap (kanala katıl, mesajı forward et, vb.)
3. Onayla
4. Para kazan! 🎉""", reply_markup=kb)
# ============================================

# ================= BALANCE =================
@dp.callback_query_handler(lambda c: c.data == "balance")
async def balance(c: types.CallbackQuery):
    await c.answer()
    uid = c.from_user.id
    bal = get_balance(uid)
    await c.message.answer(f"""💰 <b>Bakiyen:</b> <code>{bal}</code> TL

🔄 <b>Son işlemler:</b>
{get_recent_transactions(uid)}""")

def get_recent_transactions(uid):
    # Basit transaction log (ileride genişletilebilir)
    return "• Henüz işlem yok"
# ============================================

# ================= LEADERBOARD =================
@dp.callback_query_handler(lambda c: c.data == "lb")
async def leaderboard(c: types.CallbackQuery):
    users = db.collection("users").order_by("balance", direction=firestore.Query.DESCENDING).limit(15).stream()
    text = "🏆 <b>Top Kazananlar</b>\n\n"
    i = 1
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for u in users:
        user_data = u.to_dict()
        username = user_data.get('username', 'Kullanıcı')
        balance = user_data.get('balance', 0)
        emoji = emojis[i-1] if i <= len(emojis) else f"{i}."
        text += f"{emoji} @{username} — <b>{balance} TL</b>\n"
        i += 1
    
    text += f"\n💰 <b>Senin sıran:</b> #{get_user_rank(c.from_user.id)}"
    await c.message.answer(text)

def get_user_rank(uid):
    # Basit rank hesaplama
    return "?"
# ============================================

# ================= TASK SYSTEM =================
@dp.callback_query_handler(lambda c: c.data == "tasks")
async def task_select(c: types.CallbackQuery):
    if not await forced_check(c.from_user.id):
        await c.answer("❌ Önce kanala katılmalısın!", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("📢 Kanal Görevi", callback_data="task_channel"),
        InlineKeyboardButton("🤖 Bot Görevi", callback_data="task_bot"),
        InlineKeyboardButton("🔁 Forward Görevi", callback_data="task_forward"),
        InlineKeyboardButton("📝 Yazı Görevi", callback_data="task_text"),
    )
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="back_menu"))
    
    await c.message.edit_text("""🎯 <b>Görev Türü Seç</b>

Her görev türü farklı kazanç sağlar:

<b>📢 Kanal Görevi:</b> Kanala katıl → <code>+5-15 TL</code>
<b>🤖 Bot Görevi:</b> Bota katıl → <code>+3-10 TL</code>
<b>🔁 Forward Görevi:</b> Mesajı forward et → <code>+2-8 TL</code>
<b>📝 Yazı Görevi:</b> Yorum yap/like at → <code>+1-5 TL</code>""", reply_markup=kb)

async def random_task(task_type):
    docs = db.collection("tasks").where("type", "==", task_type).where("active", "==", True).stream()
    tasks = [d for d in docs]
    return random.choice(tasks) if tasks else None

@dp.callback_query_handler(lambda c: c.data.startswith("task_"))
async def do_task(c: types.CallbackQuery):
    await c.answer()
    ttype = c.data.split("_")[1]
    uid = c.from_user.id
    
    # Anti-spam kontrol
    last_task = db.collection("last_tasks").document(str(uid)).get()
    if last_task.exists:
        last_time = last_task.to_dict().get('time', 0)
        if time.time() - last_time < 30:  # 30 saniye bekle
            await c.message.answer("⏳ Lütfen 30 saniye bekleyip tekrar dene!")
            return
    
    task = await random_task(ttype)
    
    if not task:
        await c.message.answer("""📭 <b>Şu anda bu türde görev yok</b>

Başka görev türlerine bakabilir veya biraz sonra tekrar kontrol edebilirsin.

Görevler sürekli güncellenir! 🔄""")
        return
    
    data = task.to_dict()
    tid = task.id
    
    # Anti-cheat: Aynı görevi daha önce yaptı mı?
    if db.collection("completed").document(f"{uid}_{tid}").get().exists:
        await do_task(c)  # Farklı görev seç
        return
    
    # Son görevi kaydet
    db.collection("last_tasks").document(str(uid)).set({
        'time': time.time(),
        'task_id': tid
    })
    
    kb = InlineKeyboardMarkup()
    
    if ttype == "channel":
        kb.add(InlineKeyboardButton("📢 Kanala Katıl", url=data.get('url', '#')))
        kb.add(InlineKeyboardButton("✅ Görevi Tamamladım", callback_data=f"verify_{tid}_channel"))
    
    elif ttype == "bot":
        kb.add(InlineKeyboardButton("🤖 Bota Katıl", url=data.get('url', '#')))
        kb.add(InlineKeyboardButton("✅ Görevi Tamamladım", callback_data=f"verify_{tid}_bot"))
    
    elif ttype == "forward":
        # Admin kanalından mesajı al ve göster
        try:
            msg = await bot.forward_message(
                chat_id=uid,
                from_chat_id=data['channel_id'],
                message_id=data['message_id']
            )
            forward_msg_id = msg.message_id
            
            kb.add(InlineKeyboardButton("🔁 Forward Et", url=f"https://t.me/{c.message.chat.username}"))
            kb.add(InlineKeyboardButton("✅ Forward Ettim", callback_data=f"verify_{tid}_forward_{forward_msg_id}"))
            
        except Exception as e:
            await c.message.answer("❌ Görev yüklenemedi. Lütfen tekrar dene.")
            return
    
    elif ttype == "text":
        kb.add(InlineKeyboardButton("📝 Git", url=data.get('url', '#')))
        kb.add(InlineKeyboardButton("✅ Tamamladım", callback_data=f"verify_{tid}_text"))
    
    kb.add(InlineKeyboardButton("🔄 Farklı Görev", callback_data=f"task_{ttype}"))
    kb.add(InlineKeyboardButton("◀️ Geri", callback_data="tasks"))
    
    await c.message.edit_text(f"""🎯 <b>Yeni Görev!</b>

<b>Görev:</b> {data['text']}
<b>Ödül:</b> 🎁 <code>{data['reward']} TL</code>
<b>Süre:</b> ⏱️ 10 dakika

<i>Tamamladıktan sonra butona tıkla ve ödülünü al!</i>""", reply_markup=kb)

# ================= TASK VERIFICATION =================
@dp.callback_query_handler(lambda c: c.data.startswith("verify_"))
async def verify_task(c: types.CallbackQuery):
    await c.answer()
    parts = c.data.split("_")
    tid = parts[1]
    ttype = parts[2]
    uid = c.from_user.id
    
    task_doc = db.collection("tasks").document(tid).get()
    if not task_doc.exists:
        await c.message.answer("❌ Görev bulunamadı!")
        return
    
    task_data = task_doc.to_dict()
    
    # Zaten yapılmış mı kontrol
    if db.collection("completed").document(f"{uid}_{tid}").get().exists:
        await c.message.answer("❌ Bu görevi zaten tamamladın!")
        return
    
    verified = False
    
    if ttype == "channel":
        # Kanal kontrolü
        if await is_member(uid, task_data.get('target', '')):
            verified = True
    
    elif ttype == "bot":
        # Bot kontrolü (basit)
        verified = True  # İleride geliştirilecek
    
    elif ttype == "forward":
        # Forward kontrolü
        try:
            # Kullanıcının forward ettiği mesajı kontrol et
            forward_msg_id = int(parts[3]) if len(parts) > 3 else None
            
            # Burada admin kontrolü yapılacak
            # Şimdilik otomatik onay
            verified = True
            
            # Admin'e bildir
            await bot.send_message(
                ADMIN_ID,
                f"🔄 Forward Görev Onayı:\n"
                f"User: @{c.from_user.username}\n"
                f"Task: {tid}\n"
                f"Onayla: /approve_{uid}_{tid}"
            )
            
        except:
            verified = False
    
    elif ttype == "text":
        # Yazı görevi (şimdilik otomatik)
        verified = True
    
    if verified:
        # Ödülü ver
        reward = task_data['reward']
        add_balance(uid, reward)
        
        # Tamamlananlar listesine ekle
        db.collection("completed").document(f"{uid}_{tid}").set({
            'time': time.time(),
            'reward': reward,
            'type': ttype
        })
        
        # Kullanıcıya bildir
        await c.message.edit_text(f"""✅ <b>Görev Tamamlandı!</b>

🎉 Tebrikler! Görevi başarıyla tamamladın.

💰 <b>Kazandın:</b> +{reward} TL
💰 <b>Yeni Bakiye:</b> {get_balance(uid)} TL

🔄 Yeni görevler için /start""")
        
        # Leaderboard güncelle
        update_leaderboard(uid, reward)
        
    else:
        await c.message.answer("""❌ <b>Görev tamamlanmadı!</b>

Lütfen görevi doğru şekilde yaptığından emin ol:

1. Kanala gerçekten katıldın mı?
2. Botu başlattın mı?
3. Mesajı forward ettiğinden emin misin?

Tekrar dene! 🔄""")

def update_leaderboard(uid, amount):
    # Leaderboard güncelleme
    pass

@dp.callback_query_handler(lambda c: c.data == "back_menu")
async def back_to_menu(c: types.CallbackQuery):
    await c.answer()
    await main_menu(c.message)
# ============================================

# ================= ADS SYSTEM =================
@dp.callback_query_handler(lambda c: c.data == "ads")
async def ads_menu(c: types.CallbackQuery):
    await c.answer()
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📢 Kanal Reklamı", callback_data="ad_channel"),
        InlineKeyboardButton("🤖 Bot Reklamı", callback_data="ad_bot"),
        InlineKeyboardButton("🔁 Forward Reklam", callback_data="ad_forward"),
        InlineKeyboardButton("ℹ️ Reklam Kuralları", callback_data="ad_rules"),
        InlineKeyboardButton("◀️ Geri", callback_data="back_menu"),
    )
    
    await c.message.edit_text("""📢 <b>Reklam Paneli</b>

Kendi reklamını yayınla, görev olarak çıksın!

<b>Fiyatlar:</b>
• Kanal Reklamı: 50 TL
• Bot Reklamı: 30 TL
• Forward Reklamı: 20 TL

<b>Nasıl çalışır?</b>
1. Reklam türü seç
2. Linkini ve açıklamanı gir
3. Ödeme yap (bakiyenden)
4. Reklamın görevlerde çıkmaya başlar!""", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("ad_"))
async def ad_type_select(c: types.CallbackQuery):
    ad_type = c.data.split("_")[1]
    
    if ad_type == "rules":
        await c.message.edit_text("""📜 <b>Reklam Kuralları</b>

1. ❌ Sahte/aldatıcı linkler yasak
2. ❌ Yetişkin içerik yasak
3. ❌ Spam/zararlı içerik yasak
4. ✅ Reklam en az 24 saat yayında kalır
5. ✅ Minimum 10 kişi görevi tamamlamalı
6. ✅ Admin onayı gerekir

İhlal durumunda reklam iptal edilir, para iade edilmez.""")
        return
    
    # Reklam oluşturma formu
    await c.message.edit_text(f"""📝 <b>{ad_type.upper()} Reklamı Oluştur</b>

Lütfen aşağıdaki bilgileri sırayla gönder:

1. <b>Reklam başlığı</b> (max 50 karakter)
2. <b>Link/Hedef</b> (@kanal veya t.me/link)
3. <b>Açıklama</b> (görev açıklaması)
4. <b>Ödül miktarı</b> (ne kadar ödeyeceksin)

Her adımı ayrı mesaj olarak gönder.

İptal için /start""")
    
    # Kullanıcıyı reklam moduna al
    db.collection("ad_creation").document(str(c.from_user.id)).set({
        'step': 1,
        'type': ad_type,
        'data': {}
    })

@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def handle_ad_creation(msg: types.Message):
    uid = msg.from_user.id
    ad_doc = db.collection("ad_creation").document(str(uid)).get()
    
    if not ad_doc.exists:
        return  # Reklam modunda değil
    
    data = ad_doc.to_dict()
    step = data['step']
    ad_type = data['type']
    ad_data = data['data']
    
    if step == 1:
        # Başlık
        if len(msg.text) > 50:
            await msg.answer("❌ Başlık çok uzun! Max 50 karakter.")
            return
        
        ad_data['title'] = msg.text
        await msg.answer("✅ Başlık kaydedildi.\n\nŞimdi <b>link/hedef</b> gönder (örn: @kanaladi):")
        
    elif step == 2:
        # Link
        ad_data['target'] = msg.text
        await msg.answer("✅ Link kaydedildi.\n\nŞimdi <b>açıklama</b> gönder:")
        
    elif step == 3:
        # Açıklama
        ad_data['description'] = msg.text
        await msg.answer("✅ Açıklama kaydedildi.\n\nŞimdi <b>ödül miktarı</b> gönder (örn: 5):")
        
    elif step == 4:
        # Ödül
        try:
            reward = int(msg.text)
            if reward < 1 or reward > 100:
                await msg.answer("❌ Ödül 1-100 TL arası olmalı!")
                return
            
            ad_data['reward'] = reward
            
            # Fiyat hesapla
            prices = {'channel': 50, 'bot': 30, 'forward': 20}
            cost = prices.get(ad_type, 50)
            
            # Bakiye kontrol
            if get_balance(uid) < cost:
                await msg.answer(f"❌ Yetersiz bakiye! Gerekli: {cost} TL")
                db.collection("ad_creation").document(str(uid)).delete()
                return
            
            # Onay için göster
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("✅ Onayla ve Öde", callback_data=f"ad_pay_{ad_type}"),
                InlineKeyboardButton("❌ İptal", callback_data="back_menu")
            )
            
            await msg.answer(f"""💰 <b>Reklam Özeti</b>

Tür: {ad_type}
Başlık: {ad_data['title']}
Hedef: {ad_data['target']}
Açıklama: {ad_data['description']}
Ödül: {ad_data['reward']} TL

<b>Toplam Maliyet:</b> {cost} TL
<b>Mevcut Bakiyen:</b> {get_balance(uid)} TL

Onaylıyor musun?""", reply_markup=kb)
            
            # Geçici veriyi kaydet
            ad_data['cost'] = cost
            db.collection("ad_creation").document(str(uid)).set({
                'step': 5,  # Ödeme bekliyor
                'type': ad_type,
                'data': ad_data
            })
            return
            
        except ValueError:
            await msg.answer("❌ Geçerli bir sayı gir!")
            return
    
    # Sonraki adıma geç
    db.collection("ad_creation").document(str(uid)).set({
        'step': step + 1,
        'type': ad_type,
        'data': ad_data
    })

@dp.callback_query_handler(lambda c: c.data.startswith("ad_pay_"))
async def pay_for_ad(c: types.CallbackQuery):
    uid = c.from_user.id
    ad_doc = db.collection("ad_creation").document(str(uid)).get()
    
    if not ad_doc.exists:
        await c.answer("❌ Süre doldu!", show_alert=True)
        return
    
    data = ad_doc.to_dict()
    ad_data = data['data']
    cost = ad_data['cost']
    
    # Bakiyeden düş
    current = get_balance(uid)
    if current < cost:
        await c.answer("❌ Yetersiz bakiye!", show_alert=True)
        return
    
    # Ödeme
    add_balance(uid, -cost)
    
    # Reklamı oluştur
    new_ad = {
        'type': data['type'],
        'title': ad_data['title'],
        'target': ad_data['target'],
        'text': ad_data['description'],
        'reward': ad_data['reward'],
        'owner': uid,
        'created': time.time(),
        'active': False,  # Admin onayı bekliyor
        'completed_by': [],
        'total_spent': 0
    }
    
    # Firebase'e kaydet
    db.collection("ads").add(new_ad)
    
    # Temizle
    db.collection("ad_creation").document(str(uid)).delete()
    
    # Admin'e bildir
    await bot.send_message(
        ADMIN_ID,
        f"📢 <b>Yeni Reklam Talebi!</b>\n\n"
        f"Kullanıcı: @{c.from_user.username}\n"
        f"Tür: {data['type']}\n"
        f"Başlık: {ad_data['title']}\n"
        f"Hedef: {ad_data['target']}\n"
        f"Ödül: {ad_data['reward']} TL\n\n"
        f"Onayla: /approve_ad_{uid}"
    )
    
    await c.message.edit_text("""✅ <b>Reklam talebin alındı!</b>

💰 <b>Ödeme yapıldı:</b> -{cost} TL
💰 <b>Yeni bakiyen:</b> {balance} TL

📋 Reklamın admin onayından sonra aktif olacak.
⏳ Onay genellikle 1-24 saat sürer.

Teşekkürler! 🙏""".format(cost=cost, balance=get_balance(uid)))
# ============================================

# ================= HELP =================
@dp.callback_query_handler(lambda c: c.data == "help")
async def help_menu(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text("""ℹ️ <b>Yardım Merkezi</b>

<b>❓ Sık Sorulan Sorular:</b>

<b>1. Para nasıl kazanılır?</b>
- Görevleri tamamla (kanal, bot, forward)
- Her görev için ödül al

<b>2. Para nasıl çekilir?</b>
- Şu anda sadece reklam vermek için kullanabilirsin
- Yakında çekim sistemi gelecek

<b>3. Görev neden onaylanmıyor?</b>
- Kanala gerçekten katıldığından emin ol
- Forward görevlerde mesajı doğru forward et
- Admin kontrolü gerekebilir

<b>4. Reklam nasıl verilir?</b>
- Bakiyenle reklam paneline git
- Reklam türünü seç ve bilgileri gir
- Admin onayından sonra aktif olur

<b>İletişim:</b> @GorevYapsam""")
# ============================================

# ================= ADMIN COMMANDS =================
@dp.message_handler(commands=["admin"])
async def admin_panel(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 İstatistikler", callback_data="admin_stats"),
        InlineKeyboardButton("➕ Görev Ekle", callback_data="admin_add_task"),
        InlineKeyboardButton("✅ Reklam Onay", callback_data="admin_approve_ads"),
        InlineKeyboardButton("👤 Kullanıcı Ara", callback_data="admin_find_user"),
        InlineKeyboardButton("💸 Bakiye Ekle", callback_data="admin_add_balance"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
    )
    
    await msg.answer("🔧 <b>Admin Paneli</b>", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_"))
async def admin_actions(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("❌ Yetkin yok!", show_alert=True)
        return
    
    action = c.data.split("_")[1]
    
    if action == "stats":
        # İstatistikler
        total_users = len([x for x in db.collection("users").stream()])
        total_tasks = len([x for x in db.collection("tasks").stream()])
        active_ads = len([x for x in db.collection("ads").where("active", "==", True).stream()])
        
        await c.message.edit_text(f"""📊 <b>İstatistikler</b>

👥 Toplam Kullanıcı: {total_users}
🎯 Toplam Görev: {total_tasks}
📢 Aktif Reklam: {active_ads}
💰 Toplam Dağıtılan: {get_total_distributed()} TL

🔄 Son 24 saat: {get_last_24h_stats()}""")
    
    elif action == "add_task":
        await c.message.answer("""➕ <b>Yeni Görev Ekle</b>

Görev eklemek için format:

<code>/add_task type:channel text:Kanala katıl reward:5 target:@kanal</code>

<b>Parametreler:</b>
• type: channel/bot/forward/text
• text: Görev açıklaması
• reward: Ödül miktarı
• target: Hedef (kanal/bot linki)
• channel_id: Sadece forward için (kanal ID)
• message_id: Sadece forward için""")
# ============================================

def get_total_distributed():
    # Toplam dağıtılan para
    return 0

def get_last_24h_stats():
    # Son 24 saat istatistik
    return "0 görev, 0 TL"

# ================= ANTI-CHEAT =================
@dp.message_handler()
async def anti_cheat(msg: types.Message):
    uid = msg.from_user.id
    now = time.time()
    
    # Son aktiviteyi kaydet
    db.collection("user_activity").document(str(uid)).set({
        'last_message': now,
        'username': msg.from_user.username,
        'text': msg.text[:100] if msg.text else ''
    }, merge=True)
    
    # Rate limit kontrol
    activity_ref = db.collection("user_activity").document(str(uid))
    activity = activity_ref.get()
    
    if activity.exists:
        last_time = activity.to_dict().get('last_message', 0)
        if now - last_time < 0.5:  # Çok hızlı mesaj
            # Spam şüphesi
            db.collection("flags").document(str(uid)).set({
                'spam_count': firestore.Increment(1),
                'last_flag': now
            }, merge=True)

# Periodik temizlik
async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # Her saat
        
        # Eski aktiviteleri temizle
        hour_ago = time.time() - 3600
        activities = db.collection("user_activity").where("last_message", "<", hour_ago).stream()
        for act in activities:
            act.reference.delete()
        
        # Eski ad_creation temizle (1 saatten eski)
        ad_creations = db.collection("ad_creation").where("step", "<", 5).stream()
        for ad in ad_creations:
            ad_data = ad.to_dict()
            if time.time() - ad_data.get('time', 0) > 3600:
                ad.reference.delete()

# ============================================

if __name__ == "__main__":
    # Periyodik görevleri başlat
    loop = asyncio.get_event_loop()
    loop.create_task(periodic_cleanup())
    
    executor.start_polling(dp, skip_updates=True)
