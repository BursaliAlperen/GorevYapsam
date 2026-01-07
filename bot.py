"""
🚀 GÖREV YAPSAM BOT - PRODUCTION VERSION (gunicorn compatible)
Render için production WSGI server desteği eklendi
"""

import os
import time
import json
import requests
from datetime import datetime
import signal
import sys
import threading
import re
from flask import Flask, jsonify, request

# ================= 1. FLASK APP (WSGI COMPATIBLE) =================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Görev Yapsam Bot",
        "version": "3.1",
        "timestamp": datetime.now().isoformat(),
        "endpoints": ["/health", "/stats", "/webhook"]
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "bot_running": bot_running,
        "database": {
            "users": len(users),
            "tasks": len(tasks),
            "active_tasks": len(active_tasks),
            "withdrawals": len(withdrawals)
        }
    }), 200

@app.route('/stats')
def stats():
    return jsonify({
        "users": len(users),
        "tasks": len(tasks),
        "active_tasks": len(active_tasks),
        "withdrawals": len(withdrawals),
        "uptime": time.time() - start_time if 'start_time' in globals() else 0
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint (future use)"""
    try:
        data = request.get_json()
        return jsonify({"status": "received"}), 200
    except:
        return jsonify({"error": "Invalid data"}), 400

# ================= 2. AYARLAR =================
# Environment variables
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# Global değişkenler
bot_running = False
start_time = time.time()

print("=" * 60)
print("🤖 GÖREV YAPSAM BOT - PRODUCTION VERSION")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ================= 3. VERİTABANI SİSTEMİ =================
USERS_DB = "users.json"
TASKS_DB = "tasks.json"
ACTIVE_TASKS_DB = "active_tasks.json"
WITHDRAWALS_DB = "withdrawals.json"

def load_json(filename):
    """JSON dosyasını yükle"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"❌ {filename} yükleme hatası: {e}")
        return {}

def save_json(filename, data):
    """JSON dosyasına kaydet"""
    try:
        # Atomik kayıt için geçici dosya kullan
        temp_file = filename + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Geçici dosyayı asıl dosyaya taşı
        os.replace(temp_file, filename)
        return True
    except Exception as e:
        print(f"❌ {filename} kaydetme hatası: {e}")
        return False

# Veritabanlarını yükle
users = load_json(USERS_DB)
tasks = load_json(TASKS_DB)
active_tasks = load_json(ACTIVE_TASKS_DB)
withdrawals = load_json(WITHDRAWALS_DB)

print(f"📊 Veritabanı yüklendi: {len(users)} kullanıcı, {len(tasks)} görev")

# ================= 4. TELEGRAM API FONKSİYONLARI =================
def send_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    """Telegram'a mesaj gönder"""
    url = BASE_URL + "sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        print(f"❌ Mesaj gönderme hatası: {e}")
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    """Callback query'ye cevap ver"""
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
    
    if text:
        data['text'] = text
        data['show_alert'] = show_alert
    
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def edit_message(chat_id, message_id, text, reply_markup=None):
    """Mesajı düzenle"""
    url = BASE_URL + "editMessageText"
    data = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except:
        return None

def get_chat_member(chat_id, user_id):
    """Kanal üyeliğini kontrol et"""
    url = BASE_URL + "getChatMember"
    data = {
        'chat_id': f"@{MANDATORY_CHANNEL}",
        'user_id': user_id
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get('ok'):
            status = result['result']['status']
            return status in ['member', 'administrator', 'creator']
    except:
        pass
    return False

# ================= 5. POLLING SİSTEMİ (PRODUCTION) =================
def telegram_polling():
    """Production için polling sistemi"""
    global bot_running
    
    print("🔄 Telegram polling başlatıldı...")
    bot_running = True
    
    offset = 0
    error_count = 0
    max_errors = 10
    
    while bot_running:
        try:
            # GetUpdates isteği
            url = BASE_URL + "getUpdates"
            params = {
                'offset': offset,
                'timeout': 25,  # Production için daha kısa timeout
                'allowed_updates': ['message', 'callback_query']
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            # 409 Conflict kontrolü
            if response.status_code == 409:
                print("⚠️ 409 Conflict - Diğer bot instance'ı tespit edildi!")
                print("⏳ 10 saniye bekleniyor...")
                time.sleep(10)
                offset = 0
                error_count += 1
                continue
            
            if response.status_code != 200:
                print(f"⚠️ HTTP {response.status_code} - 5 saniye bekleniyor...")
                time.sleep(5)
                error_count += 1
                continue
            
            data = response.json()
            
            if not data.get('ok'):
                print(f"⚠️ Telegram API error: {data}")
                time.sleep(2)
                error_count += 1
                continue
            
            # Update'leri işle
            if data.get('result'):
                updates = data['result']
                
                for update in updates:
                    offset = update['update_id'] + 1
                    
                    # Mesaj işleme
                    if 'message' in update:
                        threading.Thread(
                            target=handle_update_message,
                            args=(update['message'],),
                            daemon=True
                        ).start()
                    
                    # Callback işleme
                    elif 'callback_query' in update:
                        threading.Thread(
                            target=handle_callback_query,
                            args=(update['callback_query'],),
                            daemon=True
                        ).start()
                
                # Başarılı işlem
                error_count = 0
            
            # Çok fazla hata kontrolü
            if error_count >= max_errors:
                print(f"🚨 Çok fazla hata ({error_count}), yeniden başlatılıyor...")
                time.sleep(30)
                offset = 0
                error_count = 0
            
        except requests.exceptions.Timeout:
            print("⏱️ Timeout - Yeniden deniyor...")
            error_count += 1
            continue
            
        except requests.exceptions.ConnectionError:
            print("🔌 Connection error - 10 saniye bekleniyor...")
            time.sleep(10)
            error_count += 1
            continue
            
        except KeyboardInterrupt:
            print("\n⏹️ Polling durduruluyor...")
            bot_running = False
            break
            
        except Exception as e:
            print(f"❌ Polling hatası: {e}")
            error_count += 1
            time.sleep(2)
        
        # CPU kullanımını azaltmak için kısa bekleme
        time.sleep(0.1)
    
    print("📴 Telegram polling durduruldu.")

# ================= 6. MESAJ HANDLER =================
def handle_update_message(message):
    """Gelen mesajı işle"""
    try:
        if 'from' not in message:
            return
            
        user_id = str(message['from']['id'])
        first_name = message['from'].get('first_name', 'Kullanıcı')
        
        # Kullanıcı kaydı
        if user_id not in users:
            users[user_id] = {
                'name': first_name,
                'username': message['from'].get('username', ''),
                'balance': 0.0,
                'tasks_completed': 0,
                'referrals': 0,
                'ref_earned': 0.0,
                'total_earned': 0.0,
                'in_channel': False,
                'welcome_bonus': False,
                'created_at': datetime.now().isoformat(),
                'tasks_created': 0,
                'state': None,
                'state_data': {},
                'forward_msg': None,
                'task_link': None,
                'task_name': None,
                'task_desc': None,
                'task_budget': None,
                'task_type': None
            }
            save_json(USERS_DB, users)
        
        user = users[user_id]
        
        # State kontrolü
        if user.get('state'):
            handle_user_state(user_id, message)
            return
        
        # Komut kontrolü
        if 'text' in message:
            text = message['text']
            
            if text.startswith('/start'):
                handle_start_command(user_id, first_name, text)
                return
                
            elif text.startswith('/menu'):
                show_main_menu(user_id)
                return
                
            elif text.startswith('/tasks'):
                show_task_selection(user_id)
                return
                
            elif text.startswith('/createtask'):
                check_bot_in_channel(user_id)
                return
                
            elif text.startswith('/help'):
                send_message(
                    user_id,
                    "🤖 <b>GÖREV YAPSAM BOT - YARDIM</b>\n\n"
                    "📋 <b>Komutlar:</b>\n"
                    "/start - Botu başlat\n"
                    "/menu - Ana menü\n"
                    "/tasks - Görev yap\n"
                    "/createtask - Görev oluştur\n"
                    "/help - Yardım\n\n"
                    "📢 <b>Kanal:</b> @GY_Refim"
                )
                return
                
            elif text.startswith('/iptal'):
                cancel_task_creation(user_id)
                return
        
        # Forward mesaj kontrolü
        if 'forward_from_chat' in message and user.get('state') == 'waiting_forward':
            user['forward_msg'] = {
                'chat_id': message['forward_from_chat']['id'],
                'message_id': message['message_id'],
                'chat_title': message['forward_from_chat'].get('title', '')
            }
            user['state'] = 'waiting_link'
            save_json(USERS_DB, users)
            
            send_message(
                user_id,
                "✅ <b>Forward mesaj alındı!</b>\n\n"
                "🔗 Şimdi görev linkini gönderin:\n"
                "(Örnek: https://t.me/OrnekKanal)\n\n"
                "❌ İptal: /iptal"
            )
            return
        
        show_main_menu(user_id)
            
    except Exception as e:
        print(f"❌ Mesaj işleme hatası: {e}")

def handle_user_state(user_id, message):
    """Kullanıcı state'ini işle"""
    user = users.get(user_id, {})
    state = user.get('state')
    
    if state == 'waiting_forward':
        if 'text' in message and message['text'] == '/iptal':
            cancel_task_creation(user_id)
            return
            
        send_message(
            user_id,
            "❌ <b>Lütfen bir mesaj FORWARD edin!</b>\n\n"
            "Görev oluşturmak için öncelikle mesajı forward etmelisiniz.\n\n"
            "❌ İptal: /iptal"
        )
    
    elif state == 'waiting_link':
        if 'text' in message:
            text = message['text'].strip()
            
            if text == '/iptal':
                cancel_task_creation(user_id)
                return
            
            # Link kontrolü
            if not (text.startswith(('https://t.me/', 't.me/', '@'))):
                send_message(
                    user_id,
                    "❌ Geçersiz link formatı!\n\n"
                    "Lütfen geçerli bir Telegram linki girin:\n"
                    "• https://t.me/OrnekKanal\n"
                    "• t.me/OrnekBot\n"
                    "• @OrnekKullanici\n\n"
                    "❌ İptal: /iptal"
                )
                return
            
            user['task_link'] = text
            user['state'] = 'waiting_name'
            save_json(USERS_DB, users)
            
            send_message(
                user_id,
                "✅ <b>Link kaydedildi!</b>\n\n"
                "📝 Şimdi görev için bir <b>isim</b> girin:\n"
                "(Örnek: Telegram Kanalına Katıl)\n\n"
                "❌ İptal: /iptal"
            )
    
    elif state == 'waiting_name':
        if 'text' in message:
            text = message['text'].strip()
            
            if text == '/iptal':
                cancel_task_creation(user_id)
                return
            
            if len(text) < 3 or len(text) > 50:
                send_message(
                    user_id,
                    "❌ İsim 3-50 karakter arasında olmalı!\n\n"
                    "📝 Lütfen tekrar girin:\n\n"
                    "❌ İptal: /iptal"
                )
                return
            
            user['task_name'] = text
            user['state'] = 'waiting_desc'
            save_json(USERS_DB, users)
            
            send_message(
                user_id,
                "✅ <b>İsim kaydedildi!</b>\n\n"
                "📄 Şimdi görev için bir <b>açıklama</b> girin:\n"
                "(Örnek: Bu kanala katılın ve 5 dakika kalın)\n\n"
                "❌ İptal: /iptal"
            )
    
    elif state == 'waiting_desc':
        if 'text' in message:
            text = message['text'].strip()
            
            if text == '/iptal':
                cancel_task_creation(user_id)
                return
            
            if len(text) < 10:
                send_message(
                    user_id,
                    "❌ Açıklama en az 10 karakter olmalı!\n\n"
                    "📄 Lütfen tekrar girin:\n\n"
                    "❌ İptal: /iptal"
                )
                return
            
            user['task_desc'] = text
            user['state'] = 'waiting_budget'
            save_json(USERS_DB, users)
            
            # Fiyat bilgisi
            prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
            task_type = user.get('task_type', 'channel')
            price_per_task = prices.get(task_type, 1.5)
            
            msg = f"""✅ <b>Açıklama kaydedildi!</b>

💰 Şimdi görev için <b>bütçe</b> girin:
(Minimum: {price_per_task}₺)

💸 <b>Mevcut Bakiyeniz:</b> {user.get('balance', 0):.2f}₺

📊 <b>HESAPLAMA:</b>
• 100₺ ÷ {price_per_task}₺ = {int(100/price_per_task)} görev

❌ İptal: /iptal"""
            
            send_message(user_id, msg)
    
    elif state == 'waiting_budget':
        if 'text' in message:
            text = message['text'].strip()
            
            if text == '/iptal':
                cancel_task_creation(user_id)
                return
            
            try:
                budget = float(text)
                task_type = user.get('task_type', 'channel')
                prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
                price_per_task = prices.get(task_type, 1.5)
                
                if budget < price_per_task:
                    send_message(
                        user_id,
                        f"❌ Minimum bütçe: {price_per_task}₺!\n\n"
                        f"💰 Lütfen {price_per_task}₺ veya üzeri girin:\n\n"
                        f"❌ İptal: /iptal"
                    )
                    return
                
                if user.get('balance', 0) < budget:
                    send_message(
                        user_id,
                        f"❌ Yetersiz bakiye!\n\n"
                        f"💸 Mevcut: {user.get('balance', 0):.2f}₺\n"
                        f"💰 Gerekli: {budget:.2f}₺\n\n"
                        f"❌ İptal: /iptal"
                    )
                    return
                
                user['task_budget'] = budget
                task_count = int(budget / price_per_task)
                show_task_confirmation(user_id, task_count)
                
            except ValueError:
                send_message(
                    user_id,
                    "❌ Geçersiz tutar!\n\n"
                    "💰 Lütfen sayı girin (Örnek: 50, 100.5):\n\n"
                    "❌ İptal: /iptal"
                )

# ================= 7. ANA KOMUTLAR =================
def handle_start_command(user_id, first_name, text):
    """Start komutunu işle"""
    # Kanal kontrolü
    in_channel = get_chat_member(MANDATORY_CHANNEL, int(user_id))
    
    # Referans kontrolü
    referrer = None
    if ' ' in text:
        parts = text.split()
        if len(parts) > 1:
            ref = parts[1]
            if ref.startswith('ref_'):
                referrer = ref.replace('ref_', '')
                if referrer == user_id:
                    referrer = None
    
    user = users.get(user_id, {})
    
    # Hoşgeldin bonusu
    if not user.get('welcome_bonus', False):
        user['balance'] = user.get('balance', 0) + 2.0
        user['welcome_bonus'] = True
        user['total_earned'] = user.get('total_earned', 0) + 2.0
        user['in_channel'] = in_channel
        save_json(USERS_DB, users)
        
        send_message(
            user_id,
            f"🎉 <b>Hoşgeldin {first_name}!</b>\n\n"
            f"✅ <b>2₺ hoşgeldin bonusu</b> yüklendi!\n"
            f"💰 <b>Yeni bakiyen:</b> {user['balance']:.2f}₺\n\n"
            f"⚡ <i>Hemen görev yapmaya başlayabilirsin!</i>"
        )
    
    # Referans kontrolü
    if referrer and in_channel:
        if referrer in users and users[referrer].get('in_channel', False):
            users[referrer]['referrals'] = users[referrer].get('referrals', 0) + 1
            users[referrer]['ref_earned'] = users[referrer].get('ref_earned', 0) + 1.0
            users[referrer]['balance'] = users[referrer].get('balance', 0) + 1.0
            user['ref_by'] = referrer
            save_json(USERS_DB, users)
            
            send_message(
                user_id,
                "🎉 <b>Referans başarılı!</b>\n\n"
                "💰 <b>1₺ referans bonusu</b> kazandın!\n\n"
                "👥 Artık sen de arkadaşlarını davet ederek para kazanabilirsin!"
            )
    
    # Kanal kontrolü
    if not in_channel:
        markup = {
            'inline_keyboard': [[
                {'text': '📢 KANALA KATIL', 'url': f'https://t.me/{MANDATORY_CHANNEL}'}
            ], [
                {'text': '✅ KATILDIM', 'callback_data': 'joined'}
            ]]
        }
        
        msg = f"""👋 <b>Merhaba {first_name}!</b>

Botu kullanabilmek için kanala katılmalısın:

👉 @{MANDATORY_CHANNEL}

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>"""
        
        send_message(user_id, msg, markup)
        return
    
    # Ana menü
    show_main_menu(user_id)

def handle_callback_query(callback):
    """Callback query işle"""
    try:
        user_id = str(callback['from']['id'])
        data = callback['data']
        callback_id = callback['id']
        
        # Cevap gönder
        answer_callback(callback_id)
        
        if data == "joined":
            in_channel = get_chat_member(MANDATORY_CHANNEL, int(user_id))
            if in_channel:
                if user_id in users:
                    users[user_id]['in_channel'] = True
                    save_json(USERS_DB, users)
                show_main_menu(user_id)
            else:
                answer_callback(callback_id, "❌ Hala kanala katılmadın!", True)
            return
        
        # Kanal kontrolü
        if data not in ["joined", "refresh", "menu"]:
            if not get_chat_member(MANDATORY_CHANNEL, int(user_id)):
                answer_callback(callback_id, f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}", True)
                return
        
        if data in ["refresh", "menu"]:
            show_main_menu(user_id)
        
        elif data == "do_task":
            show_task_selection(user_id)
        
        elif data == "create_task":
            check_bot_in_channel(user_id)
        
        elif data == "balance":
            show_balance_menu(user_id)
        
        elif data == "withdraw":
            show_withdraw_menu(user_id)
        
        elif data == "request_withdraw":
            request_withdrawal(user_id)
        
        elif data.startswith("create_type_"):
            task_type = data.replace("create_type_", "")
            start_create_task_flow(user_id, task_type)
        
        elif data == "confirm_task":
            confirm_and_create_task(user_id)
        
        elif data == "cancel_create":
            cancel_task_creation(user_id)
        
        else:
            show_main_menu(user_id)
            
    except Exception as e:
        print(f"❌ Callback hatası: {e}")

# ================= 8. GÖREV OLUŞTURMA =================
def check_bot_in_channel(user_id):
    """Görev oluşturma başlangıç"""
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 BOT GÖREVİ (2.5₺)', 'callback_data': 'create_type_bot'},
                {'text': '📢 KANAL GÖREVİ (1.5₺)', 'callback_data': 'create_type_channel'}
            ],
            [
                {'text': '👥 GRUP GÖREVİ (1₺)', 'callback_data': 'create_type_group'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = """📢 <b>GÖREV OLUŞTURMA</b>

🤖 <b>BOT GÖREVİ</b> - 2.5₺/görev
📢 <b>KANAL GÖREVİ</b> - 1.5₺/görev
👥 <b>GRUP GÖREVİ</b> - 1₺/görev

👇 <b>Görev tipini seçin:</b>"""
    
    send_message(user_id, msg, markup)

def start_create_task_flow(user_id, task_type):
    """Görev oluşturma akışını başlat"""
    user = users.get(user_id, {})
    
    user['task_type'] = task_type
    
    if task_type == 'bot':
        user['state'] = 'waiting_forward'
        save_json(USERS_DB, users)
        
        msg = """📝 <b>BOT GÖREVİ OLUŞTURMA</b>

📤 <b>ADIM 1: FORWARD MESAJ</b>

Lütfen mesajı <b>forward</b> edin.

❌ İptal: /iptal"""
        
    else:
        user['state'] = 'waiting_link'
        save_json(USERS_DB, users)
        
        task_type_text = "KANAL GÖREVİ" if task_type == 'channel' else "GRUP GÖREVİ"
        
        msg = f"""📝 <b>{task_type_text} OLUŞTURMA</b>

🔗 <b>ADIM 1: LİNK GÖNDERME</b>

Lütfen linki gönderin:

❌ İptal: /iptal"""
    
    send_message(user_id, msg)

def show_task_confirmation(user_id, task_count):
    """Görev onay ekranı"""
    user = users[user_id]
    task_type = user.get('task_type', 'channel')
    prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
    price_per_task = prices.get(task_type, 1.5)
    
    task_type_text = {
        'bot': '🤖 BOT GÖREVİ',
        'channel': '📢 KANAL GÖREVİ',
        'group': '👥 GRUP GÖREVİ'
    }.get(task_type, '📢 KANAL GÖREVİ')
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '✅ ONAYLA', 'callback_data': 'confirm_task'},
                {'text': '❌ İPTAL ET', 'callback_data': 'cancel_create'}
            ]
        ]
    }
    
    msg = f"""🎯 <b>GÖREV ÖZETİ</b>

📋 <b>Tip:</b> {task_type_text}
🔗 <b>Link:</b> {user.get('task_link', 'Belirtilmedi')}
📝 <b>İsim:</b> {user.get('task_name', 'Belirtilmedi')}

💰 <b>BÜTÇE</b>
• Toplam: {user.get('task_budget', 0):.2f}₺
• Görev Başı: {price_per_task}₺
• Görev Sayısı: {task_count} adet

💸 <b>BAKİYE</b>
• Mevcut: {user.get('balance', 0):.2f}₺
• Kalan: {user.get('balance', 0) - user.get('task_budget', 0):.2f}₺

⚠️ <b>Onaylıyor musunuz?</b>"""
    
    send_message(user_id, msg, markup)

def confirm_and_create_task(user_id):
    """Görevi onayla ve oluştur"""
    user = users.get(user_id, {})
    
    # Bakiye kontrolü
    budget = user.get('task_budget', 0)
    if user.get('balance', 0) < budget:
        send_message(user_id, f"❌ <b>Yetersiz bakiye!</b>\n\n💸 Mevcut: {user.get('balance', 0):.2f}₺")
        return
    
    task_type = user.get('task_type', 'channel')
    prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
    price_per_task = prices.get(task_type, 1.5)
    
    # Görev sayısını hesapla
    task_count = int(budget / price_per_task)
    
    # Görev ID oluştur
    task_id = str(int(time.time() * 1000))
    
    # Görevi oluştur
    task_data = {
        'id': task_id,
        'type': task_type,
        'price': price_per_task,
        'link': user.get('task_link'),
        'name': user.get('task_name'),
        'description': user.get('task_desc'),
        'creator_id': user_id,
        'creator_name': user.get('name', 'Kullanıcı'),
        'budget': budget,
        'task_count': task_count,
        'created_at': datetime.now().isoformat(),
        'completed_by': [],
        'max_completions': task_count,
        'current_completions': 0,
        'status': 'active'
    }
    
    tasks[task_id] = task_data
    
    # Bakiyeyi düş
    user['balance'] = user.get('balance', 0) - budget
    user['tasks_created'] = user.get('tasks_created', 0) + 1
    
    # State'i temizle
    user['state'] = None
    user['forward_msg'] = None
    user['task_link'] = None
    user['task_name'] = None
    user['task_desc'] = None
    user['task_budget'] = None
    user['task_type'] = None
    
    save_json(USERS_DB, users)
    save_json(TASKS_DB, tasks)
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 YENİ GÖREV', 'callback_data': 'create_task'},
                {'text': '🏠 MENÜ', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = f"""🎉 <b>GÖREV OLUŞTURULDU!</b>

📌 <b>ID:</b> <code>{task_id}</code>
📋 <b>Tip:</b> {task_type.upper()}
🔗 <b>Link:</b> {task_data['link']}

💰 <b>BÜTÇE</b>
• Toplam: {budget:.2f}₺
• Görev Başı: {price_per_task}₺
• Görev Sayısı: {task_count} adet
• Kalan Bakiye: {user.get('balance', 0):.2f}₺

✅ <b>Göreviniz aktif!</b>"""
    
    send_message(user_id, msg, markup)

def cancel_task_creation(user_id):
    """Görev oluşturmayı iptal et"""
    user = users.get(user_id, {})
    
    # State'i temizle
    user['state'] = None
    user['forward_msg'] = None
    user['task_link'] = None
    user['task_name'] = None
    user['task_desc'] = None
    user['task_budget'] = None
    user['task_type'] = None
    
    save_json(USERS_DB, users)
    
    send_message(
        user_id,
        "❌ <b>Görev oluşturma iptal edildi.</b>\n\n"
        "🏠 Ana menüye yönlendiriliyorsunuz..."
    )
    time.sleep(1)
    show_main_menu(user_id)

# ================= 9. ÖDEME SİSTEMİ =================
def show_withdraw_menu(user_id):
    """Para çekme menüsü"""
    user = users.get(user_id, {})
    balance = user.get('balance', 0)
    min_withdraw = 20.0
    
    markup = {
        'inline_keyboard': []
    }
    
    if balance >= min_withdraw:
        markup['inline_keyboard'].append([
            {'text': '💸 ÖDEME TALEP ET', 'callback_data': 'request_withdraw'}
        ])
    else:
        markup['inline_keyboard'].append([
            {'text': f'❌ Minimum: {min_withdraw}₺', 'callback_data': 'none'}
        ])
    
    markup['inline_keyboard'].append([
        {'text': '🔙 Geri', 'callback_data': 'menu'}
    ])
    
    msg = f"""💸 <b>PARA ÇEKME</b>

💰 <b>Mevcut Bakiye:</b> {balance:.2f}₺
📊 <b>Minimum Çekim:</b> {min_withdraw}₺
⏰ <b>İşlem Süresi:</b> 24-48 saat

⚠️ <i>"ÖDEME TALEP ET" butonuna basın.</i>"""
    
    send_message(user_id, msg, markup)

def request_withdrawal(user_id):
    """Para çekme talebi oluştur"""
    user = users.get(user_id, {})
    balance = user.get('balance', 0)
    min_withdraw = 20.0
    
    if balance < min_withdraw:
        send_message(user_id, f"❌ Minimum çekim: {min_withdraw}₺!")
        return
    
    # Talep ID oluştur
    request_id = str(int(time.time() * 1000))
    
    # Çekim kaydı oluştur
    withdrawal_data = {
        'id': request_id,
        'user_id': user_id,
        'user_name': user.get('name', 'Kullanıcı'),
        'amount': balance,
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    
    withdrawals[request_id] = withdrawal_data
    save_json(WITHDRAWALS_DB, withdrawals)
    
    # Admin'e bildir
    admin_msg = f"""🔔 <b>YENİ ÖDEME TALEBI</b>

👤 <b>Kullanıcı:</b> {user.get('name', 'Kullanıcı')}
🆔 <b>ID:</b> {user_id}
💰 <b>Tutar:</b> {balance:.2f}₺
📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}
🔢 <b>Talep No:</b> {request_id}"""
    
    send_message(ADMIN_ID, admin_msg)
    
    # Kullanıcıya bilgi ver
    markup = {
        'inline_keyboard': [[
            {'text': '🏠 Ana Menü', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""✅ <b>ÖDEME TALEBI OLUŞTURULDU!</b>

📋 <b>Talep No:</b> <code>{request_id}</code>
💰 <b>Tutar:</b> {balance:.2f}₺
👤 <b>Adınız:</b> {user.get('name', 'Kullanıcı')}
📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

⏳ <b>DURUM:</b> Admin onayı bekleniyor...
🕐 <b>Süre:</b> 24-48 saat"""
    
    send_message(user_id, msg, markup)

# ================= 10. MENÜ FONKSİYONLARI =================
def show_main_menu(user_id):
    """Ana menü göster"""
    user = users.get(user_id, {})
    name = user.get('name', 'Kullanıcı')
    balance = user.get('balance', 0.0)
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 GÖREV YAP', 'callback_data': 'do_task'},
                {'text': '📢 GÖREV OLUŞTUR', 'callback_data': 'create_task'}
            ],
            [
                {'text': f'💰 {balance:.2f}₺', 'callback_data': 'balance'},
                {'text': '💸 PARA ÇEK', 'callback_data': 'withdraw'}
            ],
            [
                {'text': '🔄 YENİLE', 'callback_data': 'refresh'},
                {'text': '🏠 MENÜ', 'callback_data': 'menu'}
            ]
        ]
    }
    
    if int(user_id) == ADMIN_ID:
        markup['inline_keyboard'].append([
            {'text': '👑 ADMIN', 'callback_data': 'admin_menu'}
        ])
    
    msg = f"""🚀 <b>GÖREV YAPSAM BOT</b>

👋 <b>Merhaba {name}!</b>

💰 <b>BAKİYE:</b> {balance:.2f}₺
📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}"""
    
    send_message(user_id, msg, markup)

def show_balance_menu(user_id):
    """Bakiye menüsü"""
    user = users.get(user_id, {})
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '💸 PARA ÇEK', 'callback_data': 'withdraw'},
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = f"""💰 <b>BAKİYE DETAY</b>

👤 {user.get('name', 'Kullanıcı')}
🆔 {user_id}

💵 <b>BAKİYE</b>
• Mevcut: {user.get('balance', 0):.2f}₺
• Minimum Çekim: 20₺"""
    
    send_message(user_id, msg, markup)

def show_task_selection(user_id):
    """Görev seçim menüsü"""
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 BOT GÖREVİ (2.5₺)', 'callback_data': 'task_type_bot'},
                {'text': '📢 KANAL GÖREVİ (1.5₺)', 'callback_data': 'task_type_channel'}
            ],
            [
                {'text': '👥 GRUP GÖREVİ (1₺)', 'callback_data': 'task_type_group'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = """📋 <b>GÖREV TİPİ SEÇİMİ</b>

🤖 <b>BOT GÖREVİ</b> - 2.5₺
📢 <b>KANAL GÖREVİ</b> - 1.5₺
👥 <b>GRUP GÖREVİ</b> - 1₺

👇 <b>Seçin:</b>"""
    
    send_message(user_id, msg, markup)

# ================= 11. TEMİZLEME =================
def cleanup_old_tasks():
    """Eski görevleri temizle"""
    while True:
        try:
            current_time = time.time()
            cleaned = 0
            
            for task_id, task in list(tasks.items()):
                created_at = task.get('created_at')
                if created_at:
                    try:
                        created_time = datetime.fromisoformat(created_at).timestamp()
                        if current_time - created_time > 7 * 24 * 3600:
                            del tasks[task_id]
                            cleaned += 1
                    except:
                        pass
            
            if cleaned > 0:
                save_json(TASKS_DB, tasks)
                print(f"🧹 {cleaned} eski görev temizlendi")
            
        except Exception as e:
            print(f"❌ Temizleme hatası: {e}")
        
        time.sleep(3600)

# ================= 12. ANA BAŞLATMA =================
def start_bot():
    """Botu başlat"""
    global start_time
    
    print("""
    ╔══════════════════════════════════════════╗
    ║    🚀 GÖREV YAPSAM BOT - PRODUCTION      ║
    ║    • Flask + gunicorn                    ║
    ║    • Production WSGI server              ║
    ║    • 409 Hata Fix                        ║
    ╚══════════════════════════════════════════╝
    """)
    
    # Bot kontrolü
    try:
        url = BASE_URL + "getMe"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            bot_name = data['result']['first_name']
            bot_username = data['result']['username']
            print(f"✅ Bot: @{bot_username} ({bot_name})")
            print(f"✅ Admin ID: {ADMIN_ID}")
            print(f"✅ Kanal: @{MANDATORY_CHANNEL}")
            print(f"✅ Kullanıcılar: {len(users)}")
            print(f"✅ Görevler: {len(tasks)}")
        else:
            print(f"❌ Bot token hatalı")
            return False
    
    except Exception as e:
        print(f"❌ Bot bağlantı hatası: {e}")
        return False
    
    # Temizleme thread'ini başlat
    cleanup_thread = threading.Thread(target=cleanup_old_tasks, daemon=True)
    cleanup_thread.start()
    
    # Telegram polling'i başlat
    polling_thread = threading.Thread(target=telegram_polling, daemon=True)
    polling_thread.start()
    
    print("✅ Bot başarıyla başlatıldı!")
    print("🌐 Web server çalışıyor...")
    
    return True

# ================= 13. PRODUCTION WSGI ENTRY POINT =================
# Bu fonksiyon gunicorn tarafından çağrılır
def create_app():
    """WSGI uygulamasını oluştur"""
    # Botu başlat
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    return app

# Development için direkt çalıştırma
if __name__ == "__main__":
    # Botu başlat
    if start_bot():
        # Flask'ı başlat (development için)
        port = int(os.environ.get('PORT', 8080))
        print(f"🚀 Development server başlatılıyor: http://0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, debug=False)
