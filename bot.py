"""
🚀 GÖREV YAPSAM BOT - PROFESYONEL SÜRÜM
Telegram: @GorevYapsamBot
Developer: Alperen
Kanal: @GY_Refim

409 HATASI KESİN ÇÖZÜM - MANUAL POLLING
"""

import os
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
import signal
import sys
import threading
from urllib.parse import quote

# ================= 1. AYARLAR =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

print("=" * 60)
print("🤖 GÖREV YAPSAM BOT - MANUAL POLLING")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# ================= 2. VERİTABANLARI =================
DB_FOLDER = "data"
os.makedirs(DB_FOLDER, exist_ok=True)

USERS_DB = f"{DB_FOLDER}/users.json"
TASKS_DB = f"{DB_FOLDER}/tasks.json"
ACTIVE_TASKS_DB = f"{DB_FOLDER}/active_tasks.json"
USER_STATES_DB = f"{DB_FOLDER}/user_states.json"

def load_json(filename):
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_json(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"💾 Kaydetme hatası {filename}: {e}")

# Veritabanlarını yükle
users = load_json(USERS_DB)
tasks = load_json(TASKS_DB)
active_tasks = load_json(ACTIVE_TASKS_DB)
user_states = load_json(USER_STATES_DB)

# ================= 3. TELEGRAM API FONKSİYONLARI =================
def send_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    """Mesaj gönder"""
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
        print(f"📤 Mesaj gönderme hatası: {e}")
        return None

def answer_callback(callback_id, text=None, show_alert=False):
    """Callback cevabı"""
    url = BASE_URL + "answerCallbackQuery"
    data = {'callback_query_id': callback_id}
    
    if text:
        data['text'] = text
        data['show_alert'] = show_alert
    
    try:
        response = requests.post(url, json=data, timeout=5)
        return response.json()
    except:
        return None

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
    except Exception as e:
        print(f"✏️ Mesaj düzenleme hatası: {e}")
        return None

def delete_message(chat_id, message_id):
    """Mesaj sil"""
    url = BASE_URL + "deleteMessage"
    data = {
        'chat_id': chat_id,
        'message_id': message_id
    }
    
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

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

def forward_message(chat_id, from_chat_id, message_id):
    """Mesaj forward et"""
    url = BASE_URL + "forwardMessage"
    data = {
        'chat_id': chat_id,
        'from_chat_id': from_chat_id,
        'message_id': message_id
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except:
        return None

# ================= 4. POLLING SİSTEMİ (409 FIX) =================
def manual_polling():
    """Manuel polling - 409 hatasını çözer"""
    print("🔄 Manuel polling başlatıldı...")
    
    offset = 0
    error_count = 0
    max_errors = 10
    
    while True:
        try:
            # GetUpdates isteği
            url = BASE_URL + "getUpdates"
            params = {
                'offset': offset + 1,
                'timeout': 30,
                'allowed_updates': ['message', 'callback_query']
            }
            
            response = requests.get(url, params=params, timeout=35)
            
            if response.status_code == 409:
                print("⚠️ 409 Conflict - 5 saniye bekleniyor...")
                time.sleep(5)
                offset = 0
                continue
            
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                updates = data['result']
                
                for update in updates:
                    offset = update['update_id']
                    
                    try:
                        # Mesaj işleme
                        if 'message' in update:
                            handle_update_message(update['message'])
                        
                        # Callback işleme
                        elif 'callback_query' in update:
                            handle_callback_query(update['callback_query'])
                    except Exception as e:
                        print(f"⚠️ Update işleme hatası: {e}")
                        continue
            
            error_count = 0
            time.sleep(0.1)
            
        except requests.exceptions.Timeout:
            print("⏱️ Timeout - Yeniden deniyor...")
            continue
            
        except requests.exceptions.ConnectionError:
            print("🔌 Connection error - 5 saniye bekleniyor...")
            time.sleep(5)
            continue
            
        except Exception as e:
            error_count += 1
            print(f"❌ Hata ({error_count}/{max_errors}): {e}")
            
            if error_count >= max_errors:
                print("🚨 Çok fazla hata, yeniden başlatılıyor...")
                return False
            
            time.sleep(2)
    
    return True

# ================= 5. KULLANICI YÖNETİMİ =================
def get_user_state(user_id):
    """Kullanıcı state'ini getir"""
    user_id = str(user_id)
    return user_states.get(user_id, {})

def set_user_state(user_id, state, data=None):
    """Kullanıcı state'ini ayarla"""
    user_id = str(user_id)
    if data is None:
        data = {}
    
    user_states[user_id] = {
        'state': state,
        'data': data,
        'timestamp': time.time()
    }
    save_json(USER_STATES_DB, user_states)

def clear_user_state(user_id):
    """Kullanıcı state'ini temizle"""
    user_id = str(user_id)
    if user_id in user_states:
        del user_states[user_id]
        save_json(USER_STATES_DB, user_states)

# ================= 6. GÖREV SİSTEMİ =================
def create_task(task_data):
    """Yeni görev oluştur"""
    try:
        task_id = f"task_{int(time.time() * 1000)}"
        
        task_data['id'] = task_id
        task_data['created_at'] = datetime.now().isoformat()
        task_data['completed_by'] = []
        task_data['current_completions'] = 0
        task_data['status'] = 'active'
        
        # Fiyatları belirle
        if task_data['type'] == 'bot':
            task_data['price'] = 2.5
        elif task_data['type'] == 'channel':
            task_data['price'] = 1.5
        else:  # group
            task_data['price'] = 1.0
        
        tasks[task_id] = task_data
        save_json(TASKS_DB, tasks)
        
        print(f"✅ Görev oluşturuldu: {task_id}")
        return task_id
        
    except Exception as e:
        print(f"❌ Görev oluşturma hatası: {e}")
        return None

def complete_task(user_id, task_id):
    """Görevi tamamla"""
    try:
        user_id = str(user_id)
        
        if task_id not in tasks:
            return False, "Görev bulunamadı!"
        
        task = tasks[task_id]
        
        # Kontroller
        if user_id in task.get('completed_by', []):
            return False, "Bu görevi zaten tamamladın!"
        
        if task.get('status') != 'active':
            return False, "Bu görev artık aktif değil!"
        
        # Ödülü ver
        price = task.get('price', 0)
        
        if user_id in users:
            users[user_id]['balance'] = users[user_id].get('balance', 0) + price
            users[user_id]['tasks_completed'] = users[user_id].get('tasks_completed', 0) + 1
            users[user_id]['total_earned'] = users[user_id].get('total_earned', 0) + price
        
        # Görev güncelle
        tasks[task_id]['current_completions'] = task.get('current_completions', 0) + 1
        tasks[task_id]['completed_by'].append(user_id)
        
        save_json(USERS_DB, users)
        save_json(TASKS_DB, tasks)
        
        return True, f"✅ Görev tamamlandı! {price:.2f}₺ hesabınıza yüklendi."
        
    except Exception as e:
        print(f"❌ Görev tamamlama hatası: {e}")
        return False, "Bir hata oluştu!"

def get_available_tasks(task_type=None):
    """Mevcut görevleri getir"""
    available = []
    
    for task_id, task in tasks.items():
        if task.get('status') == 'active':
            if task_type is None or task.get('type') == task_type:
                available.append(task)
    
    available.sort(key=lambda x: x.get('price', 0), reverse=True)
    return available

# ================= 7. MESAJ HANDLER =================
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
                'ad_balance': 0.0,
                'tasks_completed': 0,
                'referrals': 0,
                'ref_earned': 0.0,
                'total_earned': 0.0,
                'in_channel': False,
                'welcome_bonus': False,
                'created_at': datetime.now().isoformat(),
                'tasks_created': 0
            }
            save_json(USERS_DB, users)
        
        user = users[user_id]
        
        # State kontrolü
        state_info = get_user_state(user_id)
        if state_info.get('state'):
            handle_user_state(user_id, message, state_info)
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
        
        # Diğer mesajlar için ana menü
        show_main_menu(user_id)
            
    except Exception as e:
        print(f"📨 Mesaj işleme hatası: {e}")

def handle_user_state(user_id, message, state_info):
    """Kullanıcı state'ini işle"""
    state = state_info.get('state')
    state_data = state_info.get('data', {})
    
    if state == 'waiting_task_type':
        handle_task_type_state(user_id, message, state_data)
    
    elif state == 'waiting_forward_message':
        handle_forward_state(user_id, message, state_data)
    
    elif state == 'waiting_task_link':
        handle_task_link_state(user_id, message, state_data)
    
    elif state == 'waiting_task_name':
        handle_task_name_state(user_id, message, state_data)
    
    elif state == 'waiting_task_description':
        handle_task_description_state(user_id, message, state_data)
    
    elif state == 'waiting_task_budget':
        handle_task_budget_state(user_id, message, state_data)

# ================= 8. GÖREV OLUŞTURMA STATE HANDLER'LARI =================
def handle_task_type_state(user_id, message, state_data):
    """Görev tipi state'i"""
    if 'text' in message:
        text = message['text'].lower()
        
        if text in ['bot', 'kanal', 'grup']:
            task_type_map = {'bot': 'bot', 'kanal': 'channel', 'grup': 'group'}
            task_type = task_type_map[text]
            
            # Fiyat bilgisi
            prices = {'bot': 2.5, 'channel': 1.5, 'group': 1.0}
            price = prices.get(task_type, 1.0)
            
            set_user_state(user_id, 'waiting_forward_message', {
                'task_type': task_type,
                'price': price
            })
            
            # Admin kontrolü mesajı
            admin_msg = ""
            if task_type in ['channel', 'group']:
                admin_msg = f"\n\n⚠️ <b>ÖNEMLİ:</b> Botun @GorevYapsamBot kanalda/grupta <b>ADMIN</b> olmalı!"
            
            send_message(
                user_id,
                f"✅ <b>Görev Tipi Seçildi:</b> {text.upper()}\n"
                f"💰 <b>Görev Başı Maliyet:</b> {price}₺{admin_msg}\n\n"
                f"📤 Şimdi <b>FORWARD MESAJ</b> gönderin:\n"
                f"• Bu görev için bir mesajı ileriye yönlendirin\n"
                f"• Mesaj görevde görünecek\n"
                f"• İptal için /menu yazın"
            )
        else:
            send_message(user_id, "❌ Geçersiz görev tipi! 'bot', 'kanal' veya 'grup' yazın.")

def handle_forward_state(user_id, message, state_data):
    """Forward mesaj state'i"""
    if 'forward_from_chat' in message or 'forward_from' in message:
        # Forward mesaj kaydet
        task_type = state_data.get('task_type')
        
        set_user_state(user_id, 'waiting_task_link', {
            'task_type': task_type,
            'price': state_data.get('price'),
            'forward_message_id': message.get('message_id')
        })
        
        send_message(
            user_id,
            f"✅ <b>Forward Mesaj Alındı!</b>\n\n"
            f"🔗 Şimdi görev <b>LİNK'ini</b> gönderin:\n"
            f"• Bot görevi için: @BotUsername\n"
            f"• Kanal görevi için: https://t.me/kanal\n"
            f"• Grup görevi için: https://t.me/grup\n\n"
            f"💡 <i>Link doğru çalışıyor mu kontrol edin!</i>\n"
            f"❌ İptal için /menu"
        )
    else:
        send_message(
            user_id,
            "❌ <b>FORWARD MESAJ</b> göndermelisiniz!\n\n"
            "1. Bir mesaj seçin\n"
            "2. 'Forward' butonuna basın\n"
            "3. Bu sohbeti seçin\n"
            "4. Gönderin\n\n"
            "❌ İptal için /menu"
        )

def handle_task_link_state(user_id, message, state_data):
    """Görev linki state'i"""
    if 'text' in message:
        link = message['text'].strip()
        
        # Link doğrulama
        if not (link.startswith('https://t.me/') or link.startswith('t.me/') or link.startswith('@')):
            send_message(user_id, "❌ Geçersiz link! Telegram linki olmalı.")
            return
        
        set_user_state(user_id, 'waiting_task_name', {
            'task_type': state_data.get('task_type'),
            'price': state_data.get('price'),
            'forward_message_id': state_data.get('forward_message_id'),
            'link': link
        })
        
        send_message(
            user_id,
            f"✅ <b>Link Kaydedildi:</b> {link}\n\n"
            f"📝 Şimdi görev için bir <b>İSİM</b> belirleyin:\n"
            f"• Kısa ve açıklayıcı olsun\n"
            f"• Örnek: 'Yeni Bot Katıl', 'Film Kanalı'\n\n"
            f"❌ İptal için /menu"
        )

def handle_task_name_state(user_id, message, state_data):
    """Görev ismi state'i"""
    if 'text' in message:
        task_name = message['text'].strip()[:100]  # Max 100 karakter
        
        if len(task_name) < 3:
            send_message(user_id, "❌ İsim çok kısa! Minimum 3 karakter.")
            return
        
        set_user_state(user_id, 'waiting_task_description', {
            'task_type': state_data.get('task_type'),
            'price': state_data.get('price'),
            'forward_message_id': state_data.get('forward_message_id'),
            'link': state_data.get('link'),
            'name': task_name
        })
        
        send_message(
            user_id,
            f"✅ <b>İsim Kaydedildi:</b> {task_name}\n\n"
            f"📋 Şimdi görev <b>AÇIKLAMASI</b> yazın:\n"
            f"• Görevle ilgili detaylar\n"
            f"• Ne yapılması gerekiyor?\n"
            f"• Önemli notlar\n\n"
            f"💡 <i>Boş bırakmak için 'geç' yazabilirsiniz</i>\n"
            f"❌ İptal için /menu"
        )

def handle_task_description_state(user_id, message, state_data):
    """Görev açıklaması state'i"""
    if 'text' in message:
        description = message['text'].strip()
        if description.lower() == 'geç':
            description = ""
        
        set_user_state(user_id, 'waiting_task_budget', {
            'task_type': state_data.get('task_type'),
            'price': state_data.get('price'),
            'forward_message_id': state_data.get('forward_message_id'),
            'link': state_data.get('link'),
            'name': state_data.get('name'),
            'description': description
        })
        
        user = users.get(user_id, {})
        ad_balance = user.get('ad_balance', 0)
        
        # Kota hesaplama
        task_count = int(ad_balance / state_data.get('price', 1))
        
        send_message(
            user_id,
            f"✅ <b>Açıklama Kaydedildi!</b>\n\n"
            f"💰 <b>Reklam Bakiyeniz:</b> {ad_balance:.2f}₺\n"
            f"💸 <b>Görev Başı Maliyet:</b> {state_data.get('price')}₺\n"
            f"📊 <b>Maksimum Kota:</b> {task_count} görev\n\n"
            f"🔢 Kaç görev oluşturmak istiyorsunuz?\n"
            f"• Sayı girin (1-{task_count})\n"
            f"• Tüm bakiye için 'max' yazın\n\n"
            f"❌ İptal için /menu"
        )

def handle_task_budget_state(user_id, message, state_data):
    """Görev bütçesi state'i"""
    if 'text' in message:
        text = message['text'].strip().lower()
        
        user = users.get(user_id, {})
        ad_balance = user.get('ad_balance', 0)
        price = state_data.get('price', 1)
        max_tasks = int(ad_balance / price)
        
        if max_tasks < 1:
            send_message(
                user_id,
                f"❌ <b>Yetersiz Bakiye!</b>\n\n"
                f"💰 Reklam Bakiyeniz: {ad_balance:.2f}₺\n"
                f"💸 Görev Maliyeti: {price}₺\n"
                f"📊 Gerekli Minimum: {price}₺\n\n"
                f"💡 Normal bakiyenizi reklam bakiyesine çevirin!"
            )
            clear_user_state(user_id)
            return
        
        if text == 'max':
            task_count = max_tasks
            total_cost = task_count * price
        else:
            try:
                task_count = int(text)
                if task_count < 1:
                    send_message(user_id, "❌ Minimum 1 görev!")
                    return
                if task_count > max_tasks:
                    send_message(user_id, f"❌ Maksimum {max_tasks} görev oluşturabilirsiniz!")
                    return
                total_cost = task_count * price
            except:
                send_message(user_id, "❌ Geçersiz sayı! Sayı veya 'max' yazın.")
                return
        
        # Bakiye kontrolü
        if ad_balance < total_cost:
            send_message(user_id, "❌ Yetersiz bakiye!")
            clear_user_state(user_id)
            return
        
        # Görev bilgilerini göster
        task_info = f"""
✅ <b>GÖREV BİLGİLERİ</b>

📋 <b>Tip:</b> {state_data.get('task_type').upper()}
🔗 <b>Link:</b> {state_data.get('link')}
📝 <b>İsim:</b> {state_data.get('name')}
📄 <b>Açıklama:</b> {state_data.get('description') or 'Yok'}
💰 <b>Görev Başı:</b> {price}₺
📊 <b>Görev Sayısı:</b> {task_count}
💸 <b>Toplam Maliyet:</b> {total_cost:.2f}₺
🏦 <b>Kalan Bakiye:</b> {ad_balance - total_cost:.2f}₺

<b>Onaylıyor musunuz?</b>
"""
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': '✅ ONayla', 'callback_data': f'confirm_task_{total_cost}'},
                    {'text': '❌ İptal Et', 'callback_data': 'cancel_task'}
                ]
            ]
        }
        
        # State data'yı geçici kaydet
        state_data['task_count'] = task_count
        state_data['total_cost'] = total_cost
        set_user_state(user_id, 'waiting_task_confirmation', state_data)
        
        send_message(user_id, task_info, markup)

# ================= 9. START KOMUTU =================
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

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>

{"⚠️ <b>Referans bonusu için önce kanala katıl!</b>" if referrer else ""}"""
        
        send_message(user_id, msg, markup)
        return
    
    # Ana menü
    show_main_menu(user_id)

# ================= 10. CALLBACK HANDLER =================
def handle_callback_query(callback):
    """Callback query işle"""
    try:
        user_id = str(callback['from']['id'])
        data = callback['data']
        callback_id = callback['id']
        message_id = callback['message']['message_id']
        
        # Cevap gönder
        answer_callback(callback_id)
        
        user = users.get(user_id, {})
        
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
        if data not in ["joined", "refresh", "menu", "cancel_task"]:
            if not get_chat_member(MANDATORY_CHANNEL, int(user_id)):
                answer_callback(callback_id, f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}", True)
                return
        
        if data == "refresh" or data == "menu":
            show_main_menu(user_id)
        
        elif data == "do_task":
            show_task_selection(user_id, message_id)
        
        elif data == "create_task":
            start_create_task_flow(user_id, message_id)
        
        elif data == "balance":
            show_balance_menu(user_id, message_id)
        
        elif data == "refs":
            show_refs_menu(user_id, message_id)
        
        elif data == "convert_menu":
            show_convert_menu(user_id, message_id)
        
        elif data.startswith("conv_"):
            handle_conversion(user_id, data, message_id)
        
        elif data == "deposit":
            show_deposit_menu(user_id, message_id)
        
        elif data == "withdraw":
            show_withdraw_menu(user_id, message_id)
        
        elif data == "payment_request":
            show_payment_request(user_id, message_id)
        
        elif data.startswith("confirm_task_"):
            confirm_task_creation(user_id, data, message_id)
        
        elif data == "cancel_task":
            cancel_task_creation(user_id, message_id)
        
        elif data == "admin" and int(user_id) == ADMIN_ID:
            show_admin_panel(user_id, message_id)
        
        else:
            show_main_menu(user_id)
            
    except Exception as e:
        print(f"❌ Callback hatası: {e}")
        try:
            answer_callback(callback['id'], "❌ Hata oluştu!")
        except:
            pass

# ================= 11. GÖREV OLUŞTURMA AKIŞI =================
def start_create_task_flow(user_id, edit_msg_id=None):
    """Görev oluşturma akışını başlat"""
    user = users.get(user_id, {})
    ad_balance = user.get('ad_balance', 0)
    
    if ad_balance <= 0:
        markup = {
            'inline_keyboard': [[
                {'text': '🔄 Bakiye Çevir', 'callback_data': 'convert_menu'},
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]]
        }
        
        msg = f"""❌ <b>REKLAM BAKİYESİ YOK!</b>

══════════════════════════════

💰 <b>Reklam Bakiyeniz:</b> {ad_balance:.2f}₺

══════════════════════════════

💡 Görev oluşturmak için reklam bakiyesi gerekli!

1. Normal bakiyenizi reklam bakiyesine çevirin
2. %25 BONUS alın
3. Görev oluşturun"""
        
        if edit_msg_id:
            edit_message(user_id, edit_msg_id, msg, markup)
        else:
            send_message(user_id, msg, markup)
        return
    
    set_user_state(user_id, 'waiting_task_type', {})
    
    markup = {
        'inline_keyboard': [[
            {'text': '❌ İptal', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""📝 <b>GÖREV OLUŞTURMA</b>

══════════════════════════════

💰 <b>Reklam Bakiyeniz:</b> {ad_balance:.2f}₺

══════════════════════════════

📋 Görev tipini seçin:

<b>🤖 BOT GÖREVİ</b>
• Maliyet: 2.5₺/görüntü
• Forward mesaj gerekli

<b>📢 KANAL GÖREVİ</b>
• Maliyet: 1.5₺/görüntü
• Forward mesaj gerekli
• Bot kanalda ADMIN olmalı

<b>👥 GRUP GÖREVİ</b>
• Maliyet: 1₺/görüntü
• Forward mesaj gerekli
• Bot grupta ADMIN olmalı

══════════════════════════════

Lütfen görev tipini yazın: <b>bot</b>, <b>kanal</b> veya <b>grup</b>"""
    
    if edit_msg_id:
        edit_message(user_id, edit_msg_id, msg, markup)
    else:
        send_message(user_id, msg, markup)

def confirm_task_creation(user_id, data, edit_msg_id):
    """Görev oluşturmayı onayla"""
    try:
        total_cost = float(data.replace('confirm_task_', ''))
        
        state_info = get_user_state(user_id)
        if state_info.get('state') != 'waiting_task_confirmation':
            edit_message(user_id, edit_msg_id, "❌ Görev bilgileri eksik!", None)
            return
        
        state_data = state_info.get('data', {})
        user = users.get(user_id, {})
        
        # Bakiye kontrolü
        if user.get('ad_balance', 0) < total_cost:
            edit_message(user_id, edit_msg_id, "❌ Yetersiz bakiye!", None)
            clear_user_state(user_id)
            return
        
        # Bakiye düş
        user['ad_balance'] = user.get('ad_balance', 0) - total_cost
        user['tasks_created'] = user.get('tasks_created', 0) + state_data.get('task_count', 0)
        save_json(USERS_DB, users)
        
        # Görevi oluştur
        task_data = {
            'type': state_data.get('task_type'),
            'link': state_data.get('link'),
            'name': state_data.get('name'),
            'description': state_data.get('description', ''),
            'creator_id': user_id,
            'creator_name': user.get('name', 'Kullanıcı'),
            'max_completions': state_data.get('task_count', 1),
            'forward_message_id': state_data.get('forward_message_id')
        }
        
        task_id = create_task(task_data)
        
        # State'i temizle
        clear_user_state(user_id)
        
        if task_id:
            markup = {
                'inline_keyboard': [[
                    {'text': '🤖 Görev Yap', 'callback_data': 'do_task'},
                    {'text': '📢 Yeni Görev', 'callback_data': 'create_task'}
                ]]
            }
            
            msg = f"""🎉 <b>GÖREV OLUŞTURULDU!</b>

══════════════════════════════

📌 <b>Görev ID:</b> <code>{task_id}</code>
📋 <b>Tip:</b> {state_data.get('task_type').upper()}
🔗 <b>Link:</b> {state_data.get('link')}
📝 <b>İsim:</b> {state_data.get('name')}
📄 <b>Açıklama:</b> {state_data.get('description') or 'Yok'}
📊 <b>Görev Sayısı:</b> {state_data.get('task_count', 0)}
💸 <b>Toplam Maliyet:</b> {total_cost:.2f}₺
🏦 <b>Kalan Bakiye:</b> {user.get('ad_balance', 0):.2f}₺

══════════════════════════════

✅ Göreviniz aktif görevler listesinde görünecek!
👥 Diğer kullanıcılar görevinizi tamamlayarak para kazanacak."""
            
            edit_message(user_id, edit_msg_id, msg, markup)
        else:
            # Bakiye iade
            user['ad_balance'] = user.get('ad_balance', 0) + total_cost
            save_json(USERS_DB, users)
            
            edit_message(user_id, edit_msg_id, "❌ Görev oluşturulamadı! Tekrar deneyin.", None)
    
    except Exception as e:
        print(f"❌ Görev onaylama hatası: {e}")
        edit_message(user_id, edit_msg_id, "❌ Bir hata oluştu!", None)

def cancel_task_creation(user_id, edit_msg_id):
    """Görev oluşturmayı iptal et"""
    clear_user_state(user_id)
    edit_message(user_id, edit_msg_id, "❌ Görev oluşturma iptal edildi!", None)
    show_main_menu(user_id)

# ================= 12. MENÜ FONKSİYONLARI =================
def show_main_menu(user_id, edit_msg_id=None):
    """Ana menü göster"""
    user = users.get(user_id, {})
    name = user.get('name', 'Kullanıcı')
    balance = user.get('balance', 0.0)
    ad_balance = user.get('ad_balance', 0.0)
    total = balance + ad_balance
    tasks_done = user.get('tasks_completed', 0)
    refs = user.get('referrals', 0)
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 GÖREV YAP', 'callback_data': 'do_task'},
                {'text': '📢 GÖREV OLUŞTUR', 'callback_data': 'create_task'}
            ],
            [
                {'text': '💰 BAKİYEM', 'callback_data': 'balance'},
                {'text': '💳 YÜKLE', 'callback_data': 'deposit'}
            ],
            [
                {'text': '👥 REFERANSLAR', 'callback_data': 'refs'},
                {'text': '🔄 ÇEVİR', 'callback_data': 'convert_menu'}
            ],
            [
                {'text': '💸 PARA ÇEK', 'callback_data': 'withdraw'},
                {'text': '📋 ÖDEME TALEBİ', 'callback_data': 'payment_request'}
            ],
            [
                {'text': '🔄 YENİLE', 'callback_data': 'refresh'},
                {'text': '🏠 MENÜ', 'callback_data': 'menu'}
            ]
        ]
    }
    
    if int(user_id) == ADMIN_ID:
        markup['inline_keyboard'].append([
            {'text': '👑 ADMIN', 'callback_data': 'admin'}
        ])
    
    msg = f"""🚀 <b>GÖREV YAPSAM BOT</b>

👋 <b>Merhaba {name}!</b>

══════════════════════════════

💰 <b>BAKİYE:</b> {total:.2f}₺
• Normal: {balance:.2f}₺
• Reklam: {ad_balance:.2f}₺

══════════════════════════════

📊 <b>İSTATİSTİK</b>
• Görevler: {tasks_done}
• Referans: {refs}
• Kazanç: {user.get('ref_earned', 0):.2f}₺

══════════════════════════════

📢 <b>Kanal:</b> @{MANDATORY_CHANNEL}

══════════════════════════════

⚡ <i>Aşağıdaki butonlardan seçim yap!</i>"""
    
    if edit_msg_id:
        edit_message(user_id, edit_msg_id, msg, markup)
    else:
        send_message(user_id, msg, markup)

def show_task_selection(user_id, edit_msg_id):
    """Görev seçim menüsü"""
    markup = {
        'inline_keyboard': [
            [
                {'text': '🤖 BOT GÖREVİ (2.5₺)', 'callback_data': 'task_type_bot'},
                {'text': '📢 KANAL GÖREVİ (1.5₺)', 'callback_data': 'task_type_channel'}
            ],
            [
                {'text': '👥 GRUP GÖREVİ (1₺)', 'callback_data': 'task_type_group'},
                {'text': '🔄 TÜM GÖREVLER', 'callback_data': 'task_type_all'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = """📋 <b>GÖREV TİPİ SEÇİMİ</b>

══════════════════════════════

🤖 <b>BOT GÖREVİ</b>
• Ödül: 2.5₺
• Botlara katılma/start atma

📢 <b>KANAL GÖREVİ</b>
• Ödül: 1.5₺
• Kanallara katılma

👥 <b>GRUP GÖREVİ</b>
• Ödül: 1₺
• Gruplara katılma

══════════════════════════════

💡 <b>YÖNERGELER:</b>
1. Görev seç
2. Linke git
3. Görevi tamamla
4. 3 dakika bekle
5. Tamamla butonuna bas"""
    
    edit_message(user_id, edit_msg_id, msg, markup)

def show_balance_menu(user_id, msg_id):
    """Bakiye menüsü"""
    user = users.get(user_id, {})
    total = user.get('balance', 0.0) + user.get('ad_balance', 0.0)
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '💳 Yükle', 'callback_data': 'deposit'},
                {'text': '🔄 Çevir', 'callback_data': 'convert_menu'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = f"""💰 <b>BAKİYE DETAY</b>

══════════════════════════════

👤 {user.get('name', 'Kullanıcı')}
🆔 {user_id}

══════════════════════════════

💵 <b>BAKİYE</b>
• Normal: {user.get('balance', 0):.2f}₺
• Reklam: {user.get('ad_balance', 0):.2f}₺
• Toplam: {total:.2f}₺

══════════════════════════════

📊 <b>İSTATİSTİK</b>
• Görev: {user.get('tasks_completed', 0)}
• Referans: {user.get('referrals', 0)}
• Ref Kazanç: {user.get('ref_earned', 0):.2f}₺"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_refs_menu(user_id, msg_id):
    """Referans menüsü"""
    # Kanal kontrolü
    if not get_chat_member(MANDATORY_CHANNEL, int(user_id)):
        markup = {
            'inline_keyboard': [
                [
                    {'text': '📢 KANALA KATIL', 'url': f'https://t.me/{MANDATORY_CHANNEL}'}
                ],
                [
                    {'text': '✅ KATILDIM', 'callback_data': 'joined'}
                ]
            ]
        }
        
        msg = f"""⚠️ <b>REFERANS SİSTEMİ</b>

══════════════════════════════

❌ <b>Referans linki almak için önce kanala katıl!</b>

👉 @{MANDATORY_CHANNEL}

Katıldıktan sonra referans linkini alabilirsin."""
        
        edit_message(user_id, msg_id, msg, markup)
        return
    
    user = users.get(user_id, {})
    ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '📤 PAYLAŞ', 'url': f'https://t.me/share/url?url={ref_link}&text=Görev Yap Para Kazan! @GorevYapsamBot'},
                {'text': '📋 KOPYALA', 'callback_data': f'copy_{ref_link}'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'menu'}
            ]
        ]
    }
    
    msg = f"""👥 <b>REFERANS SİSTEMİ</b>

══════════════════════════════

💰 <b>Her referans:</b> 1₺
👤 <b>Toplam:</b> {user.get('referrals', 0)}
📈 <b>Kazanç:</b> {user.get('ref_earned', 0):.2f}₺

══════════════════════════════

🔗 <b>Linkin:</b>
{ref_link}

══════════════════════════════

🎁 <b>BONUSLAR</b>
• 5 referans: +2₺
• 10 referans: +5₺
• 25 referans: +15₺
• 50 referans: +35₺

⚠️ <b>Arkadaşların kanala katılmazsa bonus alamazsın!</b>"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_convert_menu(user_id, msg_id):
    """Çevirim menüsü"""
    user = users.get(user_id, {})
    
    markup = {
        'inline_keyboard': [
            [
                {'text': '10₺', 'callback_data': 'conv_10'},
                {'text': '25₺', 'callback_data': 'conv_25'},
                {'text': '50₺', 'callback_data': 'conv_50'}
            ],
            [
                {'text': '100₺', 'callback_data': 'conv_100'},
                {'text': '250₺', 'callback_data': 'conv_250'},
                {'text': '500₺', 'callback_data': 'conv_500'}
            ],
            [
                {'text': '🔙 Geri', 'callback_data': 'balance'}
            ]
        ]
    }
    
    msg = f"""🔄 <b>BAKİYE ÇEVİRİMİ</b>

══════════════════════════════

💰 <b>Normal Bakiyen:</b> {user.get('balance', 0):.2f}₺
💰 <b>Reklam Bakiyen:</b> {user.get('ad_balance', 0):.2f}₺

══════════════════════════════

🎁 <b>%25 BONUS!</b>
100₺ normal → 125₺ reklam

══════════════════════════════

👇 <b>Çevirmek istediğin miktar:</b>"""
    
    edit_message(user_id, msg_id, msg, markup)

def handle_conversion(user_id, data, msg_id):
    """Bakiye çevirimi"""
    amount = float(data.replace('conv_', ''))
    user = users.get(user_id, {})
    
    if user.get('balance', 0) < amount:
        edit_message(user_id, msg_id, f"❌ Yetersiz bakiye! Mevcut: {user.get('balance', 0):.2f}₺", None)
        return
    
    bonus = amount * 0.25
    total = amount + bonus
    
    user['balance'] = user.get('balance', 0) - amount
    user['ad_balance'] = user.get('ad_balance', 0) + total
    save_json(USERS_DB, users)
    
    markup = {
        'inline_keyboard': [[
            {'text': '🏠 Ana Menü', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""✅ <b>ÇEVİRİM BAŞARILI!</b>

══════════════════════════════

💰 <b>Çevrilen:</b> {amount:.2f}₺
🎁 <b>Bonus (%25):</b> {bonus:.2f}₺
💰 <b>Toplam:</b> {total:.2f}₺

══════════════════════════════

💳 <b>Yeni Bakiyeler</b>
• Normal: {user.get('balance', 0):.2f}₺
• Reklam: {user.get('ad_balance', 0):.2f}₺"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_deposit_menu(user_id, msg_id):
    """Deposit menüsü"""
    markup = {
        'inline_keyboard': [[
            {'text': '🔙 Geri', 'callback_data': 'menu'}
        ]]
    }
    
    msg = """💳 <b>BAKİYE YÜKLEME</b>

══════════════════════════════

⏳ <b>YAKINDA AKTİF!</b>

══════════════════════════════

<u>Ödeme yöntemleri:</u>
• Papara
• Kripto Para
• Banka Havalesi

<u>Lütfen bekleyin...</u>"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_withdraw_menu(user_id, msg_id):
    """Withdraw menüsü"""
    user = users.get(user_id, {})
    
    markup = {
        'inline_keyboard': [[
            {'text': '🔙 Geri', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""💸 <b>PARA ÇEKME</b>

══════════════════════════════

💰 <b>Mevcut:</b> {user.get('balance', 0):.2f}₺

══════════════════════════════

⏳ <b>YAKINDA AKTİF!</b>

══════════════════════════════

<u>Özellikler:</u>
• Minimum: 20₺
• Süre: 24 saat
• Yöntem: Papara/Banka"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_payment_request(user_id, msg_id):
    """Ödeme talebi menüsü"""
    user = users.get(user_id, {})
    balance = user.get('balance', 0)
    
    markup = {
        'inline_keyboard': [[
            {'text': '🔙 Geri', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""📋 <b>ÖDEME TALEBİ</b>

══════════════════════════════

💰 <b>Mevcut Bakiye:</b> {balance:.2f}₺

══════════════════════════════

⏳ <b>YAKINDA AKTİF!</b>

══════════════════════════════

<u>Ödeme Yöntemleri:</u>
• Papara
• Kripto Para (TRX, USDT)
• Banka Havalesi

<u>Minimum Çekim:</u> 20₺

<u>İşlem Süresi:</u> 24 saat

══════════════════════════════

💡 Sistem çok yakında aktif olacak!"""
    
    edit_message(user_id, msg_id, msg, markup)

def show_admin_panel(user_id, msg_id):
    """Admin panel"""
    total_users = len(users)
    total_balance = sum(u.get('balance', 0) for u in users.values())
    total_ad = sum(u.get('ad_balance', 0) for u in users.values())
    total_tasks = len(tasks)
    active_tasks = sum(1 for t in tasks.values() if t.get('status') == 'active')
    
    markup = {
        'inline_keyboard': [[
            {'text': '🔙 Geri', 'callback_data': 'menu'}
        ]]
    }
    
    msg = f"""👑 <b>ADMIN PANEL</b>

══════════════════════════════

📊 <b>GENEL İSTATİSTİK</b>
• Kullanıcı: {total_users}
• Normal Bakiye: {total_balance:.2f}₺
• Reklam Bakiye: {total_ad:.2f}₺
• Toplam: {total_balance + total_ad:.2f}₺

══════════════════════════════

📈 <b>GÖREV İSTATİSTİĞİ</b>
• Toplam Görev: {total_tasks}
• Aktif Görev: {active_tasks}
• Tamamlanan: {total_tasks - active_tasks}

══════════════════════════════

⚡ <b>SİSTEM DURUMU</b>
• Manuel Polling: 🟢 AKTİF
• Database: 🟢 ÇALIŞIYOR
• 409 Error Fix: 🟢 AKTİF"""
    
    edit_message(user_id, msg_id, msg, markup)

# ================= 13. TEMİZLEME FONKSİYONU =================
def cleanup_old_data():
    """Eski verileri temizle"""
    while True:
        try:
            current_time = time.time()
            
            # Eski state'leri temizle (1 saat)
            for user_id, state_info in list(user_states.items()):
                timestamp = state_info.get('timestamp', 0)
                if current_time - timestamp > 3600:  # 1 saat
                    del user_states[user_id]
            
            # Eski aktif görevleri temizle (1 gün)
            for user_id, user_tasks in list(active_tasks.items()):
                for task_id, task_info in list(user_tasks.items()):
                    if current_time - task_info.get('start_time', 0) > 86400:  # 24 saat
                        del user_tasks[task_id]
                if not user_tasks:
                    del active_tasks[user_id]
            
            save_json(USER_STATES_DB, user_states)
            save_json(ACTIVE_TASKS_DB, active_tasks)
            
            time.sleep(300)  # 5 dakikada bir
            
        except Exception as e:
            print(f"🧹 Temizleme hatası: {e}")
            time.sleep(60)

# ================= 14. ANA PROGRAM =================
def main():
    print("""
    ╔══════════════════════════════════════════╗
    ║    🚀 GÖREV YAPSAM BOT - PROFESYONEL     ║
    ║    • 409 HATA FIX - MANUAL POLLING       ║
    ║    • GÖREV YAPMA SİSTEMİ                 ║
    ║    • GÖREV OLUŞTURMA SİSTEMİ             ║
    ║    • KANAL KONTROLLÜ REFERANS            ║
    ╚══════════════════════════════════════════╝
    """)
    
    # Sinyal handler
    def signal_handler(sig, frame):
        print("\n👋 Bot kapatılıyor...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Temizleme thread'ini başlat
    cleanup_thread = threading.Thread(target=cleanup_old_data, daemon=True)
    cleanup_thread.start()
    
    # Bot kontrolü
    try:
        url = BASE_URL + "getMe"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            bot_name = data['result']['first_name']
            bot_username = data['result']['username']
            print(f"✅ Bot bağlantısı: @{bot_username} ({bot_name})")
        else:
            print(f"❌ Bot token hatalı: {data}")
            return
    
    except Exception as e:
        print(f"❌ Bot bağlantı hatası: {e}")
        return
    
    print("🔄 Manuel polling başlatılıyor...")
    
    # Ana polling döngüsü
    while True:
        try:
            if not manual_polling():
                print("🔄 Polling durdu, yeniden başlatılıyor...")
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n👋 Bot kapatılıyor...")
            break
        except Exception as e:
            print(f"🚨 Kritik hata: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
