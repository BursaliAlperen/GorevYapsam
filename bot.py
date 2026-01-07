"""
🚀 GÖREV YAPSAM BOT - ULTRA SIMPLE
Telegram: @GorevYapsamBot
Developer: Alperen
Database: Memory (Geçici) - Sonra SQLite ekleriz
Dil: Türkçe
Kanal: @GY_Refim
"""

import os
import time
import json
from datetime import datetime
import telebot
from telebot import types
from dotenv import load_dotenv
import signal
import sys

# ================= 1. SETUP =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")

print(f"🤖 Bot başlatılıyor... {datetime.now()}")

# ================= 2. BASİT DATABASE (JSON) =================
users_file = "users.json"

def load_users():
    """Kullanıcıları yükle"""
    try:
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_users(users_data):
    """Kullanıcıları kaydet"""
    try:
        with open(users_file, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
    except:
        pass

users = load_users()

# ================= 3. BOT INIT =================
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ================= 4. KANAL KONTROLÜ =================
def check_channel(user_id):
    """Kanal üyeliğini kontrol et"""
    try:
        chat = bot.get_chat(f"@{MANDATORY_CHANNEL}")
        member = bot.get_chat_member(chat.id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# ================= 5. START HANDLER =================
@bot.message_handler(commands=['start', 'menu'])
def handle_start(message):
    user_id = str(message.from_user.id)
    name = message.from_user.first_name or "Kullanıcı"
    
    # Kanal kontrolü
    in_channel = check_channel(message.from_user.id)
    
    # Referans kontrolü
    referrer = None
    if len(message.text.split()) > 1:
        ref = message.text.split()[1]
        if ref.startswith('ref_'):
            referrer = ref.replace('ref_', '')
    
    # Kullanıcıyı kaydet
    if user_id not in users:
        users[user_id] = {
            'name': name,
            'username': message.from_user.username or '',
            'balance': 0.0,
            'ad_balance': 0.0,
            'tasks': 0,
            'refs': 0,
            'ref_earned': 0.0,
            'in_channel': in_channel,
            'welcome_bonus': False,
            'ref_parent': referrer if referrer and referrer != user_id else None
        }
        save_users(users)
    
    user = users[user_id]
    
    # Hoşgeldin bonusu
    if not user.get('welcome_bonus', False):
        user['balance'] += 2.0
        user['welcome_bonus'] = True
        bot.send_message(user_id, f"🎉 Hoşgeldin {name}!\n✅ 2₺ bonus yüklendi!\n💰 Yeni bakiyen: {user['balance']}₺")
        save_users(users)
    
    # REFERANS SİSTEMİ - KANAL KONTROLLÜ
    if referrer and referrer != user_id and in_channel:
        # Referans yapan kanalda mı?
        if referrer in users and users[referrer].get('in_channel', False):
            # Referans bonusu ver
            users[referrer]['refs'] += 1
            users[referrer]['ref_earned'] += 1.0
            users[referrer]['balance'] += 1.0
            user['ref_parent'] = referrer
            
            bot.send_message(user_id, "🎉 Referans başarılı! 1₺ bonus kazandın!")
            save_users(users)
    
    # Kanal katılımı kontrolü
    if not in_channel:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}")
        )
        markup.row(
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="joined")
        )
        
        msg = f"""👋 Merhaba {name}!

⚠️ Botu kullanmak için kanala katılmalısın:
👉 @{MANDATORY_CHANNEL}

Katıldıktan sonra "✅ KATILDIM" butonuna bas.

{"⚠️ Referans bonusu için önce kanala katıl!" if referrer else ""}
"""
        bot.send_message(user_id, msg, reply_markup=markup)
        return
    
    # Ana menüyü göster
    show_menu(user_id)

# ================= 6. ANA MENÜ =================
def show_menu(user_id, edit_msg_id=None):
    user_id = str(user_id)
    user = users.get(user_id, {})
    
    total = user.get('balance', 0) + user.get('ad_balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🤖 GÖREV YAP", callback_data="tasks"),
        types.InlineKeyboardButton("💰 BAKİYEM", callback_data="balance")
    )
    markup.add(
        types.InlineKeyboardButton("👥 REFERANSLAR", callback_data="refs"),
        types.InlineKeyboardButton("🔄 ÇEVİR", callback_data="convert")
    )
    markup.add(
        types.InlineKeyboardButton("💳 YÜKLE", callback_data="deposit"),
        types.InlineKeyboardButton("💸 ÇEK", callback_data="withdraw")
    )
    markup.add(
        types.InlineKeyboardButton("🛠 DESTEK", callback_data="help"),
        types.InlineKeyboardButton("🔄 YENİLE", callback_data="refresh")
    )
    
    if int(user_id) == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin"))
    
    msg = f"""🚀 GÖREV YAPSAM BOT

👋 Merhaba {user.get('name', 'Kullanıcı')}!

══════════════════════

💰 BAKİYE: {total:.2f}₺
• Normal: {user.get('balance', 0):.2f}₺
• Reklam: {user.get('ad_balance', 0):.2f}₺

📊 İSTATİSTİK
• Görevler: {user.get('tasks', 0)}
• Referans: {user.get('refs', 0)}
• Kazanç: {user.get('ref_earned', 0):.2f}₺

📢 Kanal: @{MANDATORY_CHANNEL}

══════════════════════

⚡ Aşağıdaki butonlardan seçim yap!"""
    
    try:
        if edit_msg_id:
            bot.edit_message_text(msg, user_id, edit_msg_id, reply_markup=markup)
        else:
            bot.send_message(user_id, msg, reply_markup=markup)
    except:
        bot.send_message(user_id, msg, reply_markup=markup)

# ================= 7. CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)
    
    try:
        if call.data == "joined":
            if check_channel(call.from_user.id):
                if user_id in users:
                    users[user_id]['in_channel'] = True
                    save_users(users)
                bot.answer_callback_query(call.id, "✅ Başarılı!")
                show_menu(user_id, call.message.message_id)
            else:
                bot.answer_callback_query(call.id, "❌ Hala katılmadın!", show_alert=True)
        
        elif call.data == "refresh":
            show_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "🔄")
        
        elif call.data == "balance":
            user = users.get(user_id, {})
            total = user.get('balance', 0) + user.get('ad_balance', 0)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = f"""💰 BAKİYE DETAY

👤 {user.get('name', 'Kullanıcı')}
🆔 {user_id}

══════════════════════

💵 BAKİYE
• Normal: {user.get('balance', 0):.2f}₺
• Reklam: {user.get('ad_balance', 0):.2f}₺
• Toplam: {total:.2f}₺

══════════════════════

📊 İSTATİSTİK
• Görev: {user.get('tasks', 0)}
• Referans: {user.get('refs', 0)}
• Ref Kazanç: {user.get('ref_earned', 0):.2f}₺
• Toplam Kazanç: {user.get('balance', 0) + user.get('ref_earned', 0):.2f}₺"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data == "refs":
            # KANAL KONTROLÜ
            if not check_channel(call.from_user.id):
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}"))
                markup.add(types.InlineKeyboardButton("✅ KATILDIM", callback_data="joined"))
                
                msg = f"""⚠️ REFERANS SİSTEMİ

❌ Referans linki almak için önce kanala katılmalısın!

👉 @{MANDATORY_CHANNEL}

Katıldıktan sonra referans linkini alabilirsin."""
                
                bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
                return
            
            user = users.get(user_id, {})
            ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📤 PAYLAŞ", 
                    url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
                types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = f"""👥 REFERANS SİSTEMİ

══════════════════════

💰 Her referans: 1₺
👤 Toplam: {user.get('refs', 0)}
📈 Kazanç: {user.get('ref_earned', 0):.2f}₺

══════════════════════

🔗 Linkin:
{ref_link}

══════════════════════

🎁 BONUSLAR
• 5 referans: +2₺
• 10 referans: +5₺
• 25 referans: +15₺
• 50 referans: +35₺

⚠️ Arkadaşların kanala katılmazsa bonus alamazsın!"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data.startswith("copy_"):
            bot.answer_callback_query(call.id, "✅ Kopyalandı!")
        
        elif call.data == "convert":
            user = users.get(user_id, {})
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("10₺", callback_data="conv_10"),
                types.InlineKeyboardButton("25₺", callback_data="conv_25"),
                types.InlineKeyboardButton("50₺", callback_data="conv_50"),
                types.InlineKeyboardButton("100₺", callback_data="conv_100")
            )
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = f"""🔄 ÇEVİRİM

══════════════════════

💰 Normal: {user.get('balance', 0):.2f}₺
💰 Reklam: {user.get('ad_balance', 0):.2f}₺

══════════════════════

🎁 %25 BONUS!
100₺ normal → 125₺ reklam

══════════════════════

👇 Çevirmek istediğin miktar:"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data.startswith("conv_"):
            amount = float(call.data.replace("conv_", ""))
            user = users.get(user_id, {})
            
            if user.get('balance', 0) < amount:
                bot.answer_callback_query(call.id, f"❌ Yetersiz bakiye! Mevcut: {user.get('balance', 0):.2f}₺", show_alert=True)
                return
            
            bonus = amount * 0.25
            total = amount + bonus
            
            user['balance'] -= amount
            user['ad_balance'] += total
            
            save_users(users)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back"))
            
            msg = f"""✅ ÇEVİRİM BAŞARILI!

══════════════════════

💰 Çevrilen: {amount:.2f}₺
🎁 Bonus: {bonus:.2f}₺
💰 Toplam: {total:.2f}₺

══════════════════════

💳 Yeni Bakiyeler
• Normal: {user.get('balance', 0):.2f}₺
• Reklam: {user.get('ad_balance', 0):.2f}₺"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data == "deposit":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = """💳 BAKİYE YÜKLEME

══════════════════════

⏳ YAKINDA AKTİF!

══════════════════════

Ödeme yöntemleri:
• Papara
• Kripto Para
• Banka Havalesi

Lütfen bekleyin..."""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data == "withdraw":
            user = users.get(user_id, {})
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = f"""💸 PARA ÇEKME

══════════════════════

💰 Mevcut: {user.get('balance', 0):.2f}₺

══════════════════════

⏳ YAKINDA AKTİF!

══════════════════════

• Minimum: 20₺
• Süre: 24 saat
• Papara/Banka"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data == "admin" and int(user_id) == ADMIN_ID:
            total_users = len(users)
            total_balance = sum(u.get('balance', 0) for u in users.values())
            total_ad = sum(u.get('ad_balance', 0) for u in users.values())
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back"))
            
            msg = f"""👑 ADMIN PANEL

══════════════════════

📊 İSTATİSTİK
• Kullanıcı: {total_users}
• Normal Bakiye: {total_balance:.2f}₺
• Reklam Bakiye: {total_ad:.2f}₺
• Toplam: {total_balance + total_ad:.2f}₺"""
            
            bot.edit_message_text(msg, user_id, call.message.message_id, reply_markup=markup)
        
        elif call.data == "back":
            show_menu(user_id, call.message.message_id)
        
        else:
            show_menu(user_id, call.message.message_id)
            bot.answer_callback_query(call.id, "⚡")
    
    except Exception as e:
        print(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Hata!")
        except:
            pass

# ================= 8. DİĞER MESAJLAR =================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    show_menu(message.from_user.id)

# ================= 9. MANUEL POLLING (409 FIX) =================
def safe_polling():
    """409 hatasını çözen polling"""
    print("🤖 Bot polling başlatılıyor...")
    
    last_update_id = 0
    
    while True:
        try:
            # Manuel getUpdates kullan
            updates = bot.get_updates(offset=last_update_id + 1, timeout=20)
            
            for update in updates:
                last_update_id = update.update_id
                
                try:
                    if update.message:
                        bot.process_new_messages([update.message])
                    elif update.callback_query:
                        bot.process_new_callback_query([update.callback_query])
                except Exception as e:
                    print(f"Update işleme hatası: {e}")
            
            # 0.1 saniye bekle
            time.sleep(0.1)
            
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                print("⚠️ 409 hatası, 5 saniye bekleniyor...")
                time.sleep(5)
                # Update ID'yi sıfırla
                last_update_id = 0
            else:
                print(f"Polling hatası: {e}")
                time.sleep(2)

# ================= 10. MAIN =================
def main():
    """Ana fonksiyon"""
    print(f"""
    🚀 GÖREV YAPSAM BOT
    ═══════════════════════════════════════════
    📅 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    🔧 JSON Database
    🌍 Türkçe
    💰 Kanal Kontrollü Referans
    ⚡ Manuel Polling (409 FIXED)
    ═══════════════════════════════════════════
    """)
    
    # Manuel polling başlat
    safe_polling()

if __name__ == "__main__":
    main()
