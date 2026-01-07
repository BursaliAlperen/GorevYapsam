"""
🚀 GÖREV YAPSAM BOT - TAM VERSİYON
Telegram: @GorevYapsamBot
Developer: Alperen
Kanal: @GY_Refim
Tarih: 2026-01-07
Versiyon: 1.0.0
"""

import os
import time
import json
from datetime import datetime
import telebot
from telebot import types
from dotenv import load_dotenv

# ================= 1. AYARLAR =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")

print("=" * 50)
print("🤖 GÖREV YAPSAM BOT BAŞLATILIYOR")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"👑 Admin ID: {ADMIN_ID}")
print(f"📢 Zorunlu Kanal: @{MANDATORY_CHANNEL}")
print("=" * 50)

# ================= 2. VERİTABANI (JSON) =================
DB_FILE = "users_data.json"

def load_database():
    """Veritabanını yükle"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_database(data):
    """Veritabanını kaydet"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"💾 Kaydetme hatası: {e}")

# Veritabanını yükle
users_db = load_database()

# ================= 3. BOT OLUŞTURMA =================
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ================= 4. KANAL KONTROL FONKSİYONU =================
def check_channel_membership(user_id):
    """Kullanıcının kanalda olup olmadığını kontrol et"""
    try:
        chat = bot.get_chat(f"@{MANDATORY_CHANNEL}")
        member = bot.get_chat_member(chat.id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"📢 Kanal kontrol hatası: {e}")
        return False

# ================= 5. REFERANS SİSTEMİ =================
def add_referral(new_user_id, referrer_id):
    """Referans ekle (KANAL KONTROLLÜ)"""
    try:
        new_user_id = str(new_user_id)
        referrer_id = str(referrer_id)
        
        # 1. Referans yapan kanalda mı?
        if referrer_id not in users_db:
            print(f"⚠️ Referans yapan ({referrer_id}) kayıtlı değil")
            return False
        
        referrer_data = users_db[referrer_id]
        if not referrer_data.get('channel_joined', False):
            print(f"⚠️ Referans yapan ({referrer_id}) kanalda değil")
            return False
        
        # 2. Referans ekle
        referrer_data['referrals'] = referrer_data.get('referrals', 0) + 1
        referrer_data['ref_earned'] = referrer_data.get('ref_earned', 0) + 1.0
        referrer_data['balance'] = referrer_data.get('balance', 0) + 1.0
        
        # 3. Yeni kullanıcıya referans bilgisi ekle
        if new_user_id in users_db:
            users_db[new_user_id]['ref_by'] = referrer_id
        
        # 4. Bonus kontrolü
        check_referral_bonus(referrer_id)
        
        save_database(users_db)
        print(f"✅ Referans eklendi: {new_user_id} -> {referrer_id}")
        return True
        
    except Exception as e:
        print(f"❌ Referans ekleme hatası: {e}")
        return False

def check_referral_bonus(user_id):
    """Referans bonuslarını kontrol et"""
    try:
        user_id = str(user_id)
        if user_id not in users_db:
            return
        
        user = users_db[user_id]
        ref_count = user.get('referrals', 0)
        bonuses_given = user.get('bonuses_given', [])
        
        # Bonus seviyeleri
        bonus_levels = {
            5: 2.0,
            10: 5.0,
            25: 15.0,
            50: 35.0
        }
        
        total_bonus = 0
        for level, amount in bonus_levels.items():
            if ref_count >= level and level not in bonuses_given:
                user['balance'] = user.get('balance', 0) + amount
                bonuses_given.append(level)
                total_bonus += amount
                print(f"🎁 Bonus verildi: {user_id} - {level} referans için {amount}₺")
        
        if total_bonus > 0:
            user['bonuses_given'] = bonuses_given
            save_database(users_db)
            return total_bonus
        
        return 0
        
    except Exception as e:
        print(f"❌ Bonus kontrol hatası: {e}")
        return 0

# ================= 6. START KOMUTU =================
@bot.message_handler(commands=['start', 'menu', 'basla'])
def handle_start(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "Kullanıcı"
    username = message.from_user.username or ""
    
    print(f"🆕 Yeni kullanıcı: {user_id} - {first_name}")
    
    # Kanal kontrolü
    in_channel = check_channel_membership(message.from_user.id)
    
    # Referans parametresi
    referrer_id = None
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('ref_'):
            try:
                referrer_id = param.replace('ref_', '')
                # Kendi kendine referans olmasın
                if referrer_id == user_id:
                    referrer_id = None
            except:
                referrer_id = None
    
    # Kullanıcı verilerini oluştur
    if user_id not in users_db:
        users_db[user_id] = {
            'first_name': first_name,
            'username': username,
            'balance': 0.0,
            'ad_balance': 0.0,
            'tasks_completed': 0,
            'referrals': 0,
            'ref_earned': 0.0,
            'total_earned': 0.0,
            'channel_joined': in_channel,
            'welcome_bonus': False,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'bonuses_given': [],
            'ref_by': referrer_id if referrer_id else None
        }
        
        # Hoşgeldin bonusu
        users_db[user_id]['balance'] += 2.0
        users_db[user_id]['welcome_bonus'] = True
        users_db[user_id]['total_earned'] += 2.0
        
        save_database(users_db)
        
        bot.send_message(
            user_id,
            f"""🎉 <b>Hoş Geldin {first_name}!</b>

✅ <b>2 ₺ Hoşgeldin Bonusu</b> hesabına yüklendi!
💰 <b>Yeni Bakiyen:</b> 2.00 ₺

<i>Hemen görev yapmaya başlayabilirsin!</i>"""
        )
    
    user_data = users_db[user_id]
    
    # REFERANS SİSTEMİ - KANAL KONTROLLÜ
    if referrer_id and in_channel:
        # Referans yapan kişi kanalda mı?
        if referrer_id in users_db and users_db[referrer_id].get('channel_joined', False):
            if add_referral(user_id, referrer_id):
                bot.send_message(
                    user_id,
                    f"""🎉 <b>Referans başarılı!</b>

👤 @{username if username else 'Kullanıcı'} seni referans etti!
💰 <b>1 ₺ referans bonusu</b> kazandın!

Artık sen de arkadaşlarını davet ederek para kazanabilirsin!"""
                )
    
    # KANAL KONTROLÜ
    if not in_channel:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}")
        )
        markup.row(
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        bot.send_message(
            user_id,
            f"""👋 <b>Merhaba {first_name}!</b>

Botu kullanabilmek için aşağıdaki kanala katılman gerekiyor:

👉 @{MANDATORY_CHANNEL}

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>

⚠️ <i>Kanalı terk edersen botu kullanamazsın!</i>

{"⚠️ <b>Referans bonusu almak için önce kanala katılmalısın!</b>" if referrer_id else ""}""",
            reply_markup=markup
        )
        return
    
    # ANA MENÜ
    show_main_menu(user_id, user_data)

# ================= 7. ANA MENÜ =================
def show_main_menu(user_id, user_data=None, edit_msg_id=None):
    """Ana menüyü göster"""
    user_id = str(user_id)
    
    if user_data is None:
        user_data = users_db.get(user_id, {})
    
    first_name = user_data.get('first_name', 'Kullanıcı')
    balance = user_data.get('balance', 0.0)
    ad_balance = user_data.get('ad_balance', 0.0)
    total_balance = balance + ad_balance
    tasks = user_data.get('tasks_completed', 0)
    refs = user_data.get('referrals', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Satır 1
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="do_task"),
        types.InlineKeyboardButton("📢 GÖREV OLUŞTUR", callback_data="create_task")
    )
    
    # Satır 2
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYEM", callback_data="my_balance"),
        types.InlineKeyboardButton("💳 BAKİYE YÜKLE", callback_data="deposit")
    )
    
    # Satır 3
    markup.add(
        types.InlineKeyboardButton("👥 REFERANSLARIM", callback_data="my_refs"),
        types.InlineKeyboardButton("🔄 ÇEVİRİ YAP", callback_data="convert_menu")
    )
    
    # Satır 4
    markup.add(
        types.InlineKeyboardButton("💸 PARA ÇEK", callback_data="withdraw"),
        types.InlineKeyboardButton("🛠 DESTEK", callback_data="support")
    )
    
    # Satır 5
    markup.add(
        types.InlineKeyboardButton("❓ YARDIM", callback_data="faq"),
        types.InlineKeyboardButton("🌐 DİL", callback_data="language")
    )
    
    # Satır 6
    markup.add(
        types.InlineKeyboardButton("🔄 YENİLE", callback_data="refresh"),
        types.InlineKeyboardButton("🏠 MENÜ", callback_data="main_menu")
    )
    
    # Admin butonu
    if int(user_id) == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel"))
    
    message = f"""🚀 <b>GÖREV YAPSAM BOT</b>

👋 <b>Merhaba {first_name}!</b>

══════════════════════════════

💰 <b>BAKİYE DURUMU</b>
• Toplam Bakiye: <code>{total_balance:.2f} ₺</code>
• Normal Bakiye: <code>{balance:.2f} ₺</code>
• Reklam Bakiyesi: <code>{ad_balance:.2f} ₺</code>

══════════════════════════════

📊 <b>İSTATİSTİKLER</b>
• Tamamlanan Görev: <code>{tasks}</code>
• Referans Sayısı: <code>{refs}</code>
• Referans Kazancı: <code>{user_data.get('ref_earned', 0):.2f} ₺</code>

══════════════════════════════

📢 <b>Zorunlu Kanal:</b> @{MANDATORY_CHANNEL}

══════════════════════════════

⚡ <i>Aşağıdaki butonlardan işlemini seç!</i>"""
    
    try:
        if edit_msg_id:
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=edit_msg_id,
                reply_markup=markup
            )
        else:
            bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"❌ Menü gönderme hatası: {e}")
        bot.send_message(user_id, message, reply_markup=markup)

# ================= 8. CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)
    
    try:
        # KANAL KONTROLÜ (check_join hariç)
        if call.data != "check_join" and call.data != "main_menu":
            if not check_channel_membership(call.from_user.id):
                bot.answer_callback_query(
                    call.id,
                    f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}",
                    show_alert=True
                )
                return
        
        user_data = users_db.get(user_id, {})
        
        if call.data == "check_join":
            if check_channel_membership(call.from_user.id):
                if user_id in users_db:
                    users_db[user_id]['channel_joined'] = True
                    save_database(users_db)
                bot.answer_callback_query(call.id, "✅ Başarılı!")
                show_main_menu(user_id, user_data, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "❌ Hala kanala katılmadın!", show_alert=True)
        
        elif call.data == "refresh" or call.data == "main_menu":
            show_main_menu(user_id, user_data, call.message.message_id)
            bot.answer_callback_query(call.id, "🔄 Yenilendi!")
        
        elif call.data == "my_balance":
            total_balance = user_data.get('balance', 0) + user_data.get('ad_balance', 0)
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("💳 Yükle", callback_data="deposit"),
                types.InlineKeyboardButton("🔄 Çevir", callback_data="convert_menu")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""💰 <b>BAKİYE DETAYLARI</b>

══════════════════════════════

👤 <b>Kullanıcı:</b> {user_data.get('first_name', 'Kullanıcı')}
🆔 <b>ID:</b> <code>{user_id}</code>

══════════════════════════════

💵 <b>BAKİYE BİLGİLERİ:</b>
• Normal Bakiye: <code>{user_data.get('balance', 0):.2f} ₺</code>
• Reklam Bakiyesi: <code>{user_data.get('ad_balance', 0):.2f} ₺</code>
• Toplam Bakiye: <code>{total_balance:.2f} ₺</code>

══════════════════════════════

📊 <b>İSTATİSTİKLER:</b>
• Toplam Kazanç: <code>{user_data.get('total_earned', 0):.2f} ₺</code>
• Tamamlanan Görev: <code>{user_data.get('tasks_completed', 0)}</code>
• Referans Sayısı: <code>{user_data.get('referrals', 0)}</code>
• Referans Kazancı: <code>{user_data.get('ref_earned', 0):.2f} ₺</code>

══════════════════════════════

💡 <b>Bilgi:</b>
• Normal bakiyenle para çekebilirsin
• Reklam bakiyenle görev oluşturabilirsin
• %25 bonusla reklam bakiyesine çevirebilirsin"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "my_refs":
            # KANAL KONTROLÜ - Referans linki için
            if not check_channel_membership(call.from_user.id):
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}"))
                markup.add(types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join"))
                
                message = f"""⚠️ <b>REFERANS SİSTEMİ</b>

══════════════════════════════

❌ <b>Referans linki oluşturamazsın!</b>

Önce kanala katılmalısın:
👉 @{MANDATORY_CHANNEL}

Katıldıktan sonra referans linkini alabilir ve arkadaşlarını davet edebilirsin!"""
                
                bot.edit_message_text(
                    message,
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=markup
                )
                return
            
            ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📤 PAYLAŞ", 
                    url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
                types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""👥 <b>REFERANS SİSTEMİ</b>

══════════════════════════════

💰 <b>Her referans:</b> 1.00 ₺
👤 <b>Toplam referans:</b> {user_data.get('referrals', 0)}
📈 <b>Referans kazancı:</b> {user_data.get('ref_earned', 0):.2f} ₺

══════════════════════════════

🔗 <b>Referans linkin:</b>
<code>{ref_link}</code>

══════════════════════════════

🎁 <b>REFERANS BONUSLARI:</b>
• 5 referans: +2 ₺
• 10 referans: +5 ₺
• 25 referans: +15 ₺
• 50 referans: +35 ₺

══════════════════════════════

💡 <b>Nasıl çalışır?</b>
1. Linkini paylaş
2. Biri linkten katılır
3. 1 ₺ kazanırsın
4. Bonusları topla

⚠️ <b>ÖNEMLİ:</b> Arkadaşların kanala katılmazsa referans bonusu alamazsın!"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data.startswith("copy_"):
            bot.answer_callback_query(call.id, "✅ Kopyalandı!")
        
        elif call.data == "convert_menu":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("10 ₺", callback_data="conv_10"),
                types.InlineKeyboardButton("25 ₺", callback_data="conv_25"),
                types.InlineKeyboardButton("50 ₺", callback_data="conv_50"),
                types.InlineKeyboardButton("100 ₺", callback_data="conv_100")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""🔄 <b>REKLAM BAKİYESİ ÇEVİRİMİ</b>

══════════════════════════════

💰 <b>Normal Bakiyen:</b> <code>{user_data.get('balance', 0):.2f} ₺</code>
💰 <b>Reklam Bakiyen:</b> <code>{user_data.get('ad_balance', 0):.2f} ₺</code>

══════════════════════════════

🎁 <b>%25 BONUS!</b>
<i>Örnek: 100 ₺ normal bakiye → 125 ₺ reklam bakiyesi</i>

══════════════════════════════

👇 <b>Çevirmek istediğin miktarı seç:</b>"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data.startswith("conv_"):
            amount = float(call.data.replace("conv_", ""))
            balance = user_data.get('balance', 0)
            
            if balance < amount:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Yetersiz bakiye! Mevcut: {balance:.2f} ₺",
                    show_alert=True
                )
                return
            
            bonus = amount * 0.25
            total = amount + bonus
            
            # Bakiye güncelle
            users_db[user_id]['balance'] = balance - amount
            users_db[user_id]['ad_balance'] = user_data.get('ad_balance', 0) + total
            save_database(users_db)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu"))
            
            message = f"""✅ <b>ÇEVİRİM BAŞARILI!</b>

══════════════════════════════

💰 <b>Çevrilen Miktar:</b> {amount:.2f} ₺
🎁 <b>Bonus (%25):</b> {bonus:.2f} ₺
💰 <b>Toplam Kazanç:</b> {total:.2f} ₺

══════════════════════════════

📊 <b>Yeni Bakiyeler:</b>
• Normal Bakiye: <code>{balance - amount:.2f} ₺</code>
• Reklam Bakiyesi: <code>{user_data.get('ad_balance', 0) + total:.2f} ₺</code>

══════════════════════════════

💡 <b>Artık reklam bakiyenle görev oluşturabilirsin!</b>"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "deposit":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = """💳 <b>BAKİYE YÜKLEME</b>

══════════════════════════════

⏳ <b>YAKINDA AKTİF!</b>

══════════════════════════════

Bakiye yükleme sistemi çok yakında aktif edilecektir.

<b>Ödeme yöntemleri:</b>
• Papara
• Kripto Para (TRX, USDT)
• Banka Havalesi

══════════════════════════════

💡 <b>Öneri:</b> Şimdilik görev yaparak para kazanabilirsin!"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "withdraw":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""💸 <b>PARA ÇEKME</b>

══════════════════════════════

💰 <b>Mevcut Bakiye:</b> <code>{user_data.get('balance', 0):.2f} ₺</code>

══════════════════════════════

Para çekme sistemi çok yakında aktif edilecektir.

<b>Özellikler:</b>
• Minimum çekim: 20 ₺
• İşlem süresi: 24 saat
• Yöntemler: Papara, Banka Havalesi

══════════════════════════════

💡 <b>İpucu:</b> Bakiyeni reklam bakiyesine çevirip görev oluşturabilirsin!"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "support":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""🛠 <b>TEKNİK DESTEK</b>

══════════════════════════════

📞 <b>İletişim:</b> @AlperenTHE
🎫 <b>Bilet Sistemi:</b> Yakında aktif!
⏰ <b>Yanıt Süresi:</b> 24 saat

══════════════════════════════

🆔 <b>Kullanıcı ID:</b> <code>{user_id}</code>

══════════════════════════════

📝 <b>Destek talebi formatı:</b>
1. Kullanıcı ID: {user_id}
2. Sorun açıklaması
3. Ekran görüntüsü (varsa)
4. Tarih ve saat

══════════════════════════════

<i>Destek için @AlperenTHE adresine mesaj gönderin.</i>"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "faq":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""❓ <b>SIKÇA SORULAN SORULAR</b>

══════════════════════════════

<b>1. Bakiye nasıl yüklenir?</b>
Bakiye yükleme sistemi çok yakında aktif olacak. Papara ve kripto para seçenekleriyle bakiye yükleyebileceksin.

══════════════════════════════

<b>2. Görev nasıl yapılır?</b>
1. "GÖREV YAP" butonuna tıkla
2. Görev seç
3. Linke git ve görevi tamamla
4. 3 dakika bekle ve tamamla

══════════════════════════════

<b>3. Bonus sistemi nedir?</b>
• Her referans için 1 ₺
• Görev tamamlayarak para kazan
• Özel bonus kampanyaları

══════════════════════════════

<b>4. Para nasıl çekilir?</b>
Minimum 20 ₺ ile para çekim sistemi yakında aktif olacak.

══════════════════════════════

<b>5. Kanal zorunluluğu nedir?</b>
Botu kullanmak için @{MANDATORY_CHANNEL} kanalına katılmalısın."""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "admin_panel" and int(user_id) == ADMIN_ID:
            total_users = len(users_db)
            total_balance = sum(u.get('balance', 0) for u in users_db.values())
            total_ad = sum(u.get('ad_balance', 0) for u in users_db.values())
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = f"""👑 <b>ADMIN PANEL</b>

══════════════════════════════

📊 <b>GENEL İSTATİSTİKLER:</b>
• Toplam Kullanıcı: <code>{total_users}</code>
• Toplam Normal Bakiye: <code>{total_balance:.2f} ₺</code>
• Toplam Reklam Bakiye: <code>{total_ad:.2f} ₺</code>
• Toplam Sistem Bakiyesi: <code>{total_balance + total_ad:.2f} ₺</code>

══════════════════════════════

📈 <b>AKTİVİTE:</b>
• Son 24 saat: <i>yakında</i>
• Aktif kullanıcılar: <i>yakında</i>

══════════════════════════════

⚡ <b>HIZLI İŞLEMLER:</b>
• Bakiye ekleme
• Duyuru gönderme
• Kullanıcı yönetimi

<i>Yakında aktif edilecek...</i>"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        elif call.data == "language":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🇹🇷 Türkçe", callback_data="lang_tr"),
                types.InlineKeyboardButton("🇦🇿 Azərbaycan", callback_data="lang_az")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="main_menu"))
            
            message = """🌐 <b>DİL SEÇİMİ</b>

══════════════════════════════

Aşağıdaki dillerden birini seçin:

🇹🇷 <b>Türkçe</b> - Türkiye Türkçesi
🇦🇿 <b>Azərbaycan</b> - Azerbaycan Türkçesi

══════════════════════════════

<i>Seçiminiz tüm menüleri ve mesajları değiştirecektir.</i>"""
            
            bot.edit_message_text(
                message,
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
        
        else:
            # Diğer tüm callback'ler için ana menü
            show_main_menu(user_id, user_data, call.message.message_id)
            bot.answer_callback_query(call.id, "⚡")
    
    except Exception as e:
        print(f"❌ Callback hatası: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Bir hata oluştu!")
        except:
            pass

# ================= 9. DİĞER MESAJLAR =================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Diğer tüm mesajlar için"""
    user_id = str(message.from_user.id)
    user_data = users_db.get(user_id, {})
    show_main_menu(user_id, user_data)

# ================= 10. POLLING (409 HATA ÇÖZÜMÜ) =================
def safe_polling():
    """Güvenli polling fonksiyonu"""
    print("🔄 Bot polling başlatılıyor...")
    
    while True:
        try:
            print("🟢 Bot aktif...")
            bot.polling(none_stop=True, timeout=30, interval=2)
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Hata: {error_msg}")
            
            # 409 Conflict hatası için özel işlem
            if "409" in error_msg or "Conflict" in error_msg:
                print("⚠️ 409 Conflict hatası tespit edildi!")
                print("⏳ 10 saniye bekleniyor...")
                time.sleep(10)
                
                # Update ID'yi sıfırla
                try:
                    bot.skip_updates()
                    print("✅ Update ID sıfırlandı")
                except:
                    pass
            
            # Diğer hatalar için kısa bekle
            else:
                time.sleep(5)
            
            print("🔄 Yeniden başlatılıyor...")

# ================= 11. ANA PROGRAM =================
if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║    🚀 GÖREV YAPSAM BOT - TAM VERSİYON    ║
    ║    Telegram: @GorevYapsamBot             ║
    ║    Developer: Alperen                    ║
    ║    Kanal: @GY_Refim                      ║
    ║    Tarih: 2026-01-07                     ║
    ╚══════════════════════════════════════════╝
    """)
    
    try:
        # Güvenli polling başlat
        safe_polling()
        
    except KeyboardInterrupt:
        print("\n\n👋 Bot kapatılıyor...")
        
    except Exception as e:
        print(f"\n\n❌ Kritik hata: {e}")
        print("🔄 10 saniye sonra yeniden başlatılacak...")
        time.sleep(10)
        
        # Programı yeniden başlat
        os.execv(sys.executable, ['python'] + sys.argv)
