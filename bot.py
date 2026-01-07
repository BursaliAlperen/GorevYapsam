"""
🚀 GÖREV YAPSAM BOT PRO v16.0 - TAM VERSİYON
Telegram: @GorevYapsamBot
Developer: Alperen
Database: Firebase Firestore v2
Ödeme: Yakında (Papara & Kripto)
Dil: Türkçe & Azerbaycan Türkçesi
Render Optimized - Async fix
"""

import os
import asyncio
import telebot
from telebot import types
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiException
import threading
import time
from datetime import datetime, timedelta
import requests
import json
import pytz
from dotenv import load_dotenv
import cachetools
import firebase_admin
from firebase_admin import credentials, firestore
import schedule
import uuid
from typing import Dict, List, Optional

# ================= 1. ÇEVRE DEĞİŞKENLERİ =================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7904032877"))
MANDATORY_CHANNEL = os.getenv("MANDATORY_CHANNEL", "GY_Refim")

# ================= 2. FIREBASE FIRESTORE BAĞLANTISI =================
db = None
try:
    firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS")
    
    if firebase_creds_json:
        cred_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(cred_dict)
        
        # Firebase'i başlat (eğer henüz başlatılmadıysa)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'projectId': cred_dict.get('project_id', 'gorev-yapsam-bot'),
            })
        
        db = firestore.client()
        print("✅ Firebase Firestore bağlantısı başarılı!")
    else:
        print(f"⚠️ Firebase credentials bulunamadı, local modda çalışıyor.")
        db = None
except Exception as e:
    print(f"❌ Firebase bağlantı hatası: {e}")
    db = None

# ================= 3. BOT KONFİGÜRASYONU =================
bot = AsyncTeleBot(TOKEN, parse_mode='HTML')

# ================= 4. CACHE VE DURUM SİSTEMİ =================
price_cache = cachetools.TTLCache(maxsize=100, ttl=30)
user_cache = cachetools.TTLCache(maxsize=1000, ttl=60)
user_states = {}
task_cache = cachetools.TTLCache(maxsize=100, ttl=60)

# ================= 5. FİYAT SİSTEMİ =================
def get_trx_price():
    """Canlı TRX/TRY fiyatını al"""
    try:
        if 'trx_price' in price_cache:
            return price_cache['trx_price']
        
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=TRXTRY",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['price'])
            price_cache['trx_price'] = price
            return price
        
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=try",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            price = float(data['tron']['try'])
            price_cache['trx_price'] = price
            return price
        
    except Exception as e:
        print(f"Fiyat çekme hatası: {e}")
    
    return 0.35

# ================= 6. DİL SİSTEMİ =================
TRANSLATIONS = {
    'tr': {
        'main_menu': {
            'title': '🚀 <b>GÖREV YAPSAM BOT</b>',
            'welcome': '👋 <b>Merhaba {name}!</b>',
            'balance_section': '💰 <b>BAKİYE DURUMU</b>',
            'stats_section': '📊 <b>İSTATİSTİKLER</b>',
            'total_balance': '• Toplam Bakiye:',
            'normal_balance': '• Normal Bakiye:',
            'ad_balance': '• Reklam Bakiyesi:',
            'tasks_completed': '• Tamamlanan Görev:',
            'referrals': '• Referans Sayısı:',
            'channel_info': '📢 <b>Zorunlu Kanal:</b>',
            'start_action': '⚡ <i>Aşağıdaki butonlardan işlemini seç!</i>'
        },
        
        'buttons': {
            'do_task': '🤖 GÖREV YAP',
            'create_task': '📢 GÖREV OLUŞTUR',
            'my_balance': '💰 BAKİYEM',
            'referrals': '👥 REFERANSLARIM',
            'deposit': '💳 BAKİYE YÜKLE',
            'ad_balance': '🔄 ÇEVİRİ YAP',
            'withdraw': '💸 PARA ÇEK',
            'support': '🛠 DESTEK',
            'faq': '❓ YARDIM',
            'language': '🌐 DİL',
            'back_menu': '🏠 ANA MENÜ',
            'refresh': '🔄 YENİLE',
            'copy': '📋 KOPYALA',
            'confirm': '✅ ONAYLA',
            'cancel': '❌ İPTAL'
        },
        
        'deposit': {
            'title': '💳 <b>BAKİYE YÜKLEME</b>',
            'soon_title': '⏳ <b>YAKINDA AKTİF!</b>',
            'soon_message': 'Bakiye yükleme sistemi çok yakında aktif edilecektir.\n\nÖdeme yöntemleri:\n• Papara\n• Kripto Para (TRX, USDT)\n• Banka Havalesi\n\nLütfen kısa bir süre bekleyin.',
            'back_button': '🔙 Ana Menüye Dön'
        },
        
        'tasks': {
            'select_type': '📋 <b>GÖREV TİPİ SEÇİMİ</b>',
            'bot_task': '🤖 BOT GÖREVİ ({price} ₺)',
            'channel_task': '📢 KANAL GÖREVİ ({price} ₺)',
            'group_task': '👥 GRUP GÖREVİ ({price} ₺)',
            'no_tasks': '📭 <b>Şu anda görev bulunmuyor</b>',
            'create_your_own': '💡 Kendi görevini oluşturabilirsin!',
            'instructions': '📌 <b>YÖNERGELER:</b>\n1. "GİT" butonuna tıkla\n2. Görevi tamamla\n3. 3 dakika bekle\n4. "TAMAMLA" butonuna bas'
        },
        
        'support': {
            'title': '🛠 <b>TEKNİK DESTEK</b>',
            'contact': '📞 <b>İletişim:</b> @AlperenTHE',
            'ticket_system': '🎫 <b>Bilet Sistemi:</b> Yakında aktif!',
            'response_time': '⏰ <b>Yanıt Süresi:</b> 24 saat',
            'user_id': '🆔 <b>Kullanıcı ID:</b>'
        },
        
        'faq': {
            'title': '❓ <b>SIKÇA SORULAN SORULAR</b>',
            'q1': '💰 <b>Bakiye nasıl yüklenir?</b>',
            'a1': 'Bakiye yükleme sistemi çok yakında aktif olacak. Papara ve kripto para seçenekleriyle bakiye yükleyebileceksin.',
            'q2': '🤖 <b>Görev nasıl yapılır?</b>',
            'a2': '1. "GÖREV YAP" butonuna tıkla\n2. Görev seç\n3. Linke git ve görevi tamamla\n4. 3 dakika bekle ve tamamla',
            'q3': '🎁 <b>Bonus sistemi nedir?</b>',
            'a3': '• Her referans için 1 ₺\n• Görev tamamlayarak para kazan\n• Özel bonus kampanyaları',
            'q4': '💸 <b>Para nasıl çekilir?</b>',
            'a4': 'Minimum 20 ₺ ile para çekim sistemi yakında aktif olacak.',
            'q5': '📢 <b>Kanal zorunluluğu nedir?</b>',
            'a5': f'Botu kullanmak için @{MANDATORY_CHANNEL} kanalına katılmalısın.'
        },
        
        'withdraw': {
            'title': '💸 <b>PARA ÇEKME</b>',
            'soon_message': 'Para çekme sistemi çok yakında aktif edilecektir.\n\n• Minimum çekim: 20 ₺\n• İşlem süresi: 24 saat\n• Yöntemler: Papara, Banka Havalesi\n\nLütfen kısa bir süre bekleyin.'
        },
        
        'referral': {
            'title': '👥 <b>REFERANS SİSTEMİ</b>',
            'earn_per_ref': '💰 <b>Her referans:</b> 1 ₺',
            'total_refs': '👤 <b>Toplam referans:</b>',
            'total_earned': '📈 <b>Referans kazancı:</b>',
            'your_link': '🔗 <b>Referans linkin:</b>',
            'bonus_tiers': '🎁 <b>REFERANS BONUSLARI:</b>',
            'bonus_5': '• 5 referans: +2 ₺',
            'bonus_10': '• 10 referans: +5 ₺',
            'bonus_25': '• 25 referans: +15 ₺',
            'bonus_50': '• 50 referans: +35 ₺',
            'how_it_works': '💡 <b>Nasıl çalışır?</b>',
            'step1': '1. Linkini paylaş',
            'step2': '2. Biri linkten katılır',
            'step3': '3. 1 ₺ kazanırsın',
            'step4': '4. Bonusları topla'
        },
        
        'ad_balance': {
            'title': '🔄 <b>REKLAM BAKİYESİ ÇEVİRİMİ</b>',
            'current_normal': '💰 <b>Normal Bakiyen:</b>',
            'current_ad': '💰 <b>Reklam Bakiyen:</b>',
            'bonus_25': '🎁 <b>%25 BONUS!</b>',
            'bonus_example': '<i>Örnek: 100 ₺ normal bakiye → 125 ₺ reklam bakiyesi</i>',
            'select_amount': '👇 <b>Çevirmek istediğin miktarı seç:</b>'
        }
    },
    
    'az': {
        'main_menu': {
            'title': '🚀 <b>TAPŞIRIQ EDƏM BOT</b>',
            'welcome': '👋 <b>Salam {name}!</b>',
            'balance_section': '💰 <b>BALANS VƏZİYYƏTİ</b>',
            'stats_section': '📊 <b>STATİSTİKA</b>',
            'total_balance': '• Ümumi Balans:',
            'normal_balance': '• Normal Balans:',
            'ad_balance': '• Reklam Balansı:',
            'tasks_completed': '• Tamamlanan Tapşırıq:',
            'referrals': '• Referans Sayı:',
            'channel_info': '📢 <b>Məcburi Kanal:</b>',
            'start_action': '⚡ <i>Aşağıdakı düymələrdən əməliyyatını seç!</i>'
        },
        
        'buttons': {
            'do_task': '🤖 TAPŞIRIQ ET',
            'create_task': '📢 TAPŞIRIQ YARAT',
            'my_balance': '💰 BALANSIM',
            'referrals': '👥 REFERANSLARIM',
            'deposit': '💳 BALANS ARTIR',
            'ad_balance': '🔄 ÇEVİR ET',
            'withdraw': '💸 PUL ÇIXART',
            'support': '🛠 DƏSTƏK',
            'faq': '❓ KÖMƏK',
            'language': '🌐 DİL',
            'back_menu': '🏠 ƏSAS MENYU',
            'refresh': '🔄 YENİLƏ',
            'copy': '📋 KOPYALA',
            'confirm': '✅ TƏSDİQLƏ',
            'cancel': '❌ LƏĞV ET'
        },
        
        'deposit': {
            'title': '💳 <b>BALANS ARTIRMA</b>',
            'soon_title': '⏳ <b>TEZLİKDA AKTİV!</b>',
            'soon_message': 'Balans artırma sistemi tezlikdə aktiv ediləcək.\n\nÖdəniş üsulları:\n• Papara\n• Kripto Valyuta (TRX, USDT)\n• Bank köçürməsi\n\nZəhmət olmasa qısa müddət gözləyin.',
            'back_button': '🔙 Əsas Menyaya Qayıt'
        },
        
        'tasks': {
            'select_type': '📋 <b>TAPŞIRIQ NÖVÜ SEÇİMİ</b>',
            'bot_task': '🤖 BOT TAPŞIRIĞI ({price} ₺)',
            'channel_task': '📢 KANAL TAPŞIRIĞI ({price} ₺)',
            'group_task': '👥 QRUPPA TAPŞIRIĞI ({price} ₺)',
            'no_tasks': '📭 <b>Hal-hazırda tapşırıq yoxdur</b>',
            'create_your_own': '💡 Öz tapşırığını yarada bilərsən!',
            'instructions': '📌 <b>TƏLİMATLAR:</b>\n1. "GET" düyməsinə toxun\n2. Tapşırığı tamamla\n3. 3 dəqiqə gözlə\n4. "TAMAMLA" düyməsinə bas'
        },
        
        'support': {
            'title': '🛠 <b>TEKNİK DƏSTƏK</b>',
            'contact': '📞 <b>Əlaqə:</b> @AlperenTHE',
            'ticket_system': '🎫 <b>Bilet Sistemi:</b> Tezliklə aktiv!',
            'response_time': '⏰ <b>Cavab Müddəti:</b> 24 saat',
            'user_id': '🆔 <b>İstifadəçi ID:</b>'
        },
        
        'faq': {
            'title': '❓ <b>TEZ-TEZ VERİLƏN SUALLAR</b>',
            'q1': '💰 <b>Balans necə yüklənir?</b>',
            'a1': 'Balans artırma sistemi tezlikdə aktiv olacaq. Papara və kripto valyuta seçimləri ilə balans artıra biləcəksiniz.',
            'q2': '🤖 <b>Tapşırıq necə edilir?</b>',
            'a2': '1. "TAPŞIRIQ ET" düyməsinə toxun\n2. Tapşırıq seç\n3. Linkə get və tapşırığı tamamla\n4. 3 dəqiqə gözlə və tamamla',
            'q3': '🎁 <b>Bonus sistemi nədir?</b>',
            'a3': '• Hər referans üçün 1 ₺\n• Tapşırıq tamamlayaraq pul qazan\n• Xüsusi bonus kampanyaları',
            'q4': '💸 <b>Pul necə çıxarılır?</b>',
            'a4': 'Minimum 20 ₺ ilə pul çıxarış sistemi tezlikdə aktiv olacaq.',
            'q5': '📢 <b>Kanal məcburiyyəti nədir?</b>',
            'a5': f'Botu istifadə etmək üçün @{MANDATORY_CHANNEL} kanalına qoşulmalısınız.'
        },
        
        'withdraw': {
            'title': '💸 <b>PUL ÇIXARTMA</b>',
            'soon_message': 'Pul çıxarışı sistemi tezlikdə aktiv ediləcək.\n\n• Minimum çıxarma: 20 ₺\n• Əməliyyat müddəti: 24 saat\n• Üsullar: Papara, Bank köçürməsi\n\nZəhmət olmasa qısa müddət gözləyin.'
        },
        
        'referral': {
            'title': '👥 <b>REFERANS SİSTEMİ</b>',
            'earn_per_ref': '💰 <b>Hər referans:</b> 1 ₺',
            'total_refs': '👤 <b>Ümumi referans:</b>',
            'total_earned': '📈 <b>Referans qazancı:</b>',
            'your_link': '🔗 <b>Referans linkin:</b>',
            'bonus_tiers': '🎁 <b>REFERANS BONUSLARI:</b>',
            'bonus_5': '• 5 referans: +2 ₺',
            'bonus_10': '• 10 referans: +5 ₺',
            'bonus_25': '• 25 referans: +15 ₺',
            'bonus_50': '• 50 referans: +35 ₺',
            'how_it_works': '💡 <b>Necə işləyir?</b>',
            'step1': '1. Linkini paylaş',
            'step2': '2. Biri linkdən qoşulur',
            'step3': '3. 1 ₺ qazanırsan',
            'step4': '4. Bonusları topla'
        },
        
        'ad_balance': {
            'title': '🔄 <b>REKLAM BALANSININ ÇEVİRİLMƏSİ</b>',
            'current_normal': '💰 <b>Normal Balansın:</b>',
            'current_ad': '💰 <b>Reklam Balansın:</b>',
            'bonus_25': '🎁 <b>%25 BONUS!</b>',
            'bonus_example': '<i>Misal: 100 ₺ normal balans → 125 ₺ reklam balansı</i>',
            'select_amount': '👇 <b>Çevirmək istədiyin məbləği seç:</b>'
        }
    }
}

def get_translation(lang: str, key_path: str) -> str:
    """Çeviri metnini getir"""
    try:
        keys = key_path.split('.')
        current = TRANSLATIONS.get(lang, TRANSLATIONS['tr'])
        
        for key in keys:
            current = current[key]
        
        return str(current) if not isinstance(current, dict) else str(current)
    except:
        return f"[{key_path}]"

# ================= 7. FIRESTORE İŞLEMLERİ =================
async def get_user(user_id: int) -> Optional[Dict]:
    """Kullanıcı bilgilerini getir"""
    try:
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            return user_cache[cache_key]
        
        if db:
            user_ref = db.collection('users').document(str(user_id))
            user_doc = user_ref.get()
            
            if user_doc.exists:
                user_data = user_doc.to_dict()
                user_data['id'] = str(user_id)
                user_cache[cache_key] = user_data
                return user_data
        else:
            user_data = {
                'id': str(user_id),
                'first_name': '',
                'username': '',
                'language': 'tr',
                'balance': 0.0,
                'ad_balance': 0.0,
                'tasks_completed': 0,
                'referrals': 0,
                'ref_earned': 0.0,
                'total_earned': 0.0,
                'channel_joined': False,
                'welcome_bonus': False,
                'created_at': datetime.now().isoformat()
            }
            user_cache[cache_key] = user_data
            return user_data
            
    except Exception as e:
        print(f"Kullanıcı getirme hatası: {e}")
        return None

async def create_or_update_user(user_id: int, user_data: Dict) -> bool:
    """Kullanıcı oluştur veya güncelle"""
    try:
        if db:
            user_ref = db.collection('users').document(str(user_id))
            user_ref.set(user_data, merge=True)
        else:
            cache_key = f"user_{user_id}"
            user_cache[cache_key] = user_data
        
        return True
    except Exception as e:
        print(f"Kullanıcı güncelleme hatası: {e}")
        return False

async def update_balance(user_id: int, amount: float, balance_type: str = 'balance') -> bool:
    """Bakiye güncelle"""
    try:
        user = await get_user(user_id)
        if not user:
            return False
        
        if balance_type == 'ad_balance':
            new_balance = user.get('ad_balance', 0) + amount
            update_data = {'ad_balance': new_balance}
        else:
            new_balance = user.get('balance', 0) + amount
            total_earned = user.get('total_earned', 0) + max(amount, 0)
            update_data = {
                'balance': new_balance,
                'total_earned': total_earned
            }
        
        await create_or_update_user(user_id, update_data)
        
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            del user_cache[cache_key]
        
        return True
    except Exception as e:
        print(f"Bakiye güncelleme hatası: {e}")
        return False

async def update_user_stats(user_id: int, stats_data: Dict) -> bool:
    """Kullanıcı istatistiklerini güncelle"""
    try:
        await create_or_update_user(user_id, stats_data)
        
        cache_key = f"user_{user_id}"
        if cache_key in user_cache:
            del user_cache[cache_key]
        
        return True
    except Exception as e:
        print(f"İstatistik güncelleme hatası: {e}")
        return False

# ================= 8. KANAL KONTROLÜ =================
async def check_channel_membership(user_id: int) -> bool:
    """Kanal üyeliğini kontrol et"""
    try:
        member = await bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Kanal kontrol hatası: {e}")
        return False

# ================= 9. ANA MENÜ SİSTEMİ =================
async def show_main_menu(user_id: int, message_id: int = None, edit: bool = True):
    """Ana menü göster"""
    user = await get_user(user_id)
    if not user:
        user = {
            'id': str(user_id),
            'first_name': 'Kullanıcı',
            'balance': 0.0,
            'ad_balance': 0.0,
            'tasks_completed': 0,
            'referrals': 0,
            'language': 'tr'
        }
        await create_or_update_user(user_id, user)
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    total_balance = user.get('balance', 0) + user.get('ad_balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.do_task'), callback_data="do_task"),
        types.InlineKeyboardButton(t('buttons.create_task'), callback_data="create_task_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.my_balance'), callback_data="my_balance"),
        types.InlineKeyboardButton(t('buttons.deposit'), callback_data="deposit_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.referrals'), callback_data="my_refs"),
        types.InlineKeyboardButton(t('buttons.ad_balance'), callback_data="ad_balance_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.support'), callback_data="support_menu"),
        types.InlineKeyboardButton(t('buttons.faq'), callback_data="faq_menu"),
        types.InlineKeyboardButton(t('buttons.language'), callback_data="language_menu")
    )
    
    markup.add(
        types.InlineKeyboardButton(t('buttons.withdraw'), callback_data="withdraw_menu"),
        types.InlineKeyboardButton(t('buttons.refresh'), callback_data="refresh_main")
    )
    
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel"))
    
    message = f"""
{t('main_menu.title')}

{t('main_menu.welcome').format(name=user.get('first_name', 'Kullanıcı'))}

<b>─────────────────────</b>

{t('main_menu.balance_section')}
• {t('main_menu.total_balance')} <code>{total_balance:.2f} ₺</code>
• {t('main_menu.normal_balance')} <code>{user.get('balance', 0):.2f} ₺</code>
• {t('main_menu.ad_balance')} <code>{user.get('ad_balance', 0):.2f} ₺</code>

<b>─────────────────────</b>

{t('main_menu.stats_section')}
• {t('main_menu.tasks_completed')} <code>{user.get('tasks_completed', 0)}</code>
• {t('main_menu.referrals')} <code>{user.get('referrals', 0)}</code>

<b>─────────────────────</b>

{t('main_menu.channel_info')} @{MANDATORY_CHANNEL}

{t('main_menu.start_action')}
"""
    
    try:
        if edit and message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(
                user_id,
                message,
                reply_markup=markup
            )
    except Exception as e:
        print(f"Menü gönderme hatası: {e}")

# ================= 10. START KOMUTU =================
@bot.message_handler(commands=['start', 'menu', 'yardım', 'help'])
async def handle_start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Kullanıcı"
    username = message.from_user.username or ""
    
    is_member = await check_channel_membership(user_id)
    
    user = await get_user(user_id)
    if not user:
        user_data = {
            'first_name': first_name,
            'username': username,
            'channel_joined': is_member,
            'language': 'tr',
            'balance': 0.0,
            'ad_balance': 0.0,
            'welcome_bonus': False,
            'created_at': datetime.now().isoformat()
        }
        await create_or_update_user(user_id, user_data)
        user = await get_user(user_id)
    
    if user and not user.get('welcome_bonus', False):
        await update_balance(user_id, 2.0)
        await create_or_update_user(user_id, {'welcome_bonus': True})
        
        welcome_msg = f"""
🎉 <b>Hoş Geldin {first_name}!</b>

✅ <b>2 ₺ Hoşgeldin Bonusu</b> hesabına yüklendi!
💰 <b>Yeni Bakiyen:</b> 2.00 ₺

<i>Hemen görev yapmaya başlayabilirsin!</i>
"""
        await bot.send_message(user_id, welcome_msg)
    
    if not is_member:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📢 KANALA KATIL", url=f"https://t.me/{MANDATORY_CHANNEL}")
        )
        markup.row(
            types.InlineKeyboardButton("✅ KATILDIM", callback_data="check_join")
        )
        
        channel_msg = f"""
👋 <b>Merhaba {first_name}!</b>

Botu kullanabilmek için aşağıdaki kanala katılman gerekiyor:

👉 @{MANDATORY_CHANNEL}

<b>Katıldıktan sonra "✅ KATILDIM" butonuna bas.</b>

⚠️ <i>Kanalı terk edersen botu kullanamazsın!</i>
"""
        await bot.send_message(user_id, channel_msg, reply_markup=markup)
        return
    
    await show_main_menu(user_id)

# ================= 11. CALLBACK HANDLER =================
@bot.callback_query_handler(func=lambda call: True)
async def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    message_id = call.message.message_id if call.message else None
    
    try:
        if data not in ["check_join", "set_lang_tr", "set_lang_az"]:
            if not await check_channel_membership(user_id):
                await bot.answer_callback_query(
                    call.id,
                    f"❌ Önce kanala katıl! @{MANDATORY_CHANNEL}",
                    show_alert=True
                )
                return
        
        if data == "check_join":
            if await check_channel_membership(user_id):
                await create_or_update_user(user_id, {'channel_joined': True})
                await show_main_menu(user_id, message_id)
                await bot.answer_callback_query(call.id, "✅ Başarılı!")
            else:
                await bot.answer_callback_query(
                    call.id,
                    "❌ Hala kanala katılmadın!",
                    show_alert=True
                )
        
        elif data == "refresh_main":
            await show_main_menu(user_id, message_id)
            await bot.answer_callback_query(call.id, "🔄 Yenilendi!")
        
        elif data == "back_menu":
            await show_main_menu(user_id, message_id)
        
        elif data == "deposit_menu":
            await show_deposit_menu(user_id, message_id)
        
        elif data == "withdraw_menu":
            await show_withdraw_menu(user_id, message_id)
        
        elif data.startswith("set_lang_"):
            lang = data.replace("set_lang_", "")
            await create_or_update_user(user_id, {'language': lang})
            await bot.answer_callback_query(call.id, f"✅ Dil {lang} olarak ayarlandı!")
            await show_main_menu(user_id, message_id)
        
        elif data == "language_menu":
            await show_language_menu(user_id, message_id)
        
        elif data == "support_menu":
            await show_support_menu(user_id, message_id)
        
        elif data == "faq_menu":
            await show_faq_menu(user_id, message_id)
        
        elif data == "my_balance":
            await show_balance_details(user_id, message_id)
        
        elif data == "do_task":
            await show_task_selection(user_id, message_id)
        
        elif data == "create_task_menu":
            await show_create_task_menu(user_id, message_id)
        
        elif data == "my_refs":
            await show_referral_info(user_id, message_id)
        
        elif data == "ad_balance_menu":
            await show_ad_balance_conversion(user_id, message_id)
        
        elif data.startswith("convert_"):
            if data.startswith("convert_"):
                if data == "convert_custom":
                    await ask_custom_conversion_amount(user_id, message_id)
                else:
                    try:
                        amount = float(data.replace("convert_", ""))
                        await handle_ad_conversion(user_id, message_id, amount)
                    except ValueError:
                        await bot.answer_callback_query(
                            call.id,
                            "❌ Geçersiz miktar!",
                            show_alert=True
                        )
        
        elif data == "admin_panel" and user_id == ADMIN_ID:
            await show_admin_panel(user_id, message_id)
        
        elif data.startswith("copy_"):
            text_to_copy = data.replace("copy_", "")
            await bot.answer_callback_query(call.id, "✅ Kopyalandı!")
        
    except Exception as e:
        print(f"Callback hatası: {e}")
        await bot.answer_callback_query(call.id, "❌ Bir hata oluştu!")

# ================= 12. BAKİYE YÜKLEME MENÜSÜ =================
async def show_deposit_menu(user_id: int, message_id: int = None):
    """Bakiye yükleme menüsü"""
    user = await get_user(user_id)
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('deposit.title')}

<b>─────────────────────</b>

{t('deposit.soon_title')}

<b>─────────────────────</b>

{t('deposit.soon_message')}

<b>─────────────────────</b>

💡 <b>Öneri:</b> Şimdilik görev yaparak para kazanabilirsin!
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Deposit menu hatası: {e}")

# ================= 13. PARA ÇEKME MENÜSÜ =================
async def show_withdraw_menu(user_id: int, message_id: int = None):
    """Para çekme menüsü"""
    user = await get_user(user_id)
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    user_data = await get_user(user_id)
    current_balance = user_data.get('balance', 0) if user_data else 0
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('withdraw.title')}

<b>─────────────────────</b>

💰 <b>Mevcut Bakiye:</b> <code>{current_balance:.2f} ₺</code>

<b>─────────────────────</b>

{t('withdraw.soon_message')}

<b>─────────────────────</b>

💡 <b>İpucu:</b> Bakiyeni reklam bakiyesine çevirip görev oluşturabilirsin!
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Withdraw menu hatası: {e}")

# ================= 14. DİL SEÇİM MENÜSÜ =================
async def show_language_menu(user_id: int, message_id: int = None):
    """Dil seçim menüsü"""
    user = await get_user(user_id)
    current_lang = user.get('language', 'tr') if user else 'tr'
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "🇹🇷 Türkçe" + (" ✅" if current_lang == 'tr' else ""),
            callback_data="set_lang_tr"
        ),
        types.InlineKeyboardButton(
            "🇦🇿 Azərbaycan" + (" ✅" if current_lang == 'az' else ""),
            callback_data="set_lang_az"
        )
    )
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_menu"))
    
    message = """
🌐 <b>DİL SEÇİMİ</b>

<b>─────────────────────</b>

Aşağıdaki dillerden birini seçin:

🇹🇷 <b>Türkçe</b> - Türkiye Türkçesi
🇦🇿 <b>Azərbaycan</b> - Azerbaycan Türkçesi

<b>─────────────────────</b>

<i>Seçiminiz tüm menüleri ve mesajları değiştirecektir.</i>
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Language menu hatası: {e}")

# ================= 15. DESTEK MENÜSÜ =================
async def show_support_menu(user_id: int, message_id: int = None):
    """Teknik destek menüsü"""
    user = await get_user(user_id)
    lang = user.get('language', 'tr') if user else 'tr'
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('support.title')}

<b>─────────────────────</b>

{t('support.contact')}
{t('support.ticket_system')}
{t('support.response_time')}

<b>─────────────────────</b>

{t('support.user_id')} <code>{user_id}</code>

<b>─────────────────────</b>

📝 <b>Destek talebi formatı:</b>
1. Kullanıcı ID: {user_id}
2. Sorun açıklaması
3. Ekran görüntüsü (varsa)
4. Tarih ve saat

<b>─────────────────────</b>

<i>Destek için @AlperenTHE adresine mesaj gönderin.</i>
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Support menu hatası: {e}")

# ================= 16. SSS MENÜSÜ =================
async def show_faq_menu(user_id: int, message_id: int = None):
    """Sıkça sorulan sorular menüsü"""
    user = await get_user(user_id)
    lang = user.get('language', 'tr') if user else 'tr'
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('faq.title')}

<b>─────────────────────</b>

{t('faq.q1')}
{t('faq.a1')}

<b>─────────────────────</b>

{t('faq.q2')}
{t('faq.a2')}

<b>─────────────────────</b>

{t('faq.q3')}
{t('faq.a3')}

<b>─────────────────────</b>

{t('faq.q4')}
{t('faq.a4')}

<b>─────────────────────</b>

{t('faq.q5')}
{t('faq.a5')}

<b>─────────────────────</b>

💡 <b>Ek Bilgiler:</b>
• Minimum görev ücreti: 1.00 ₺
• Referans başına: 1.00 ₺
• Minimum para çekme: 20.00 ₺
• Kanal: @{MANDATORY_CHANNEL}
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"FAQ menu hatası: {e}")

# ================= 17. BAKİYE DETAYLARI =================
async def show_balance_details(user_id: int, message_id: int = None):
    """Bakiye detaylarını göster"""
    user = await get_user(user_id)
    if not user:
        return
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    total_balance = user.get('balance', 0) + user.get('ad_balance', 0)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(t('buttons.deposit'), callback_data="deposit_menu"),
        types.InlineKeyboardButton(t('buttons.ad_balance'), callback_data="ad_balance_menu")
    )
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
💰 <b>BAKİYE DETAYLARI</b>

<b>─────────────────────</b>

👤 <b>Kullanıcı:</b> {user.get('first_name', 'Kullanıcı')}
🆔 <b>ID:</b> <code>{user_id}</code>

<b>─────────────────────</b>

💵 <b>BAKİYE BİLGİLERİ:</b>
• <b>Normal Bakiye:</b> <code>{user.get('balance', 0):.2f} ₺</code>
• <b>Reklam Bakiyesi:</b> <code>{user.get('ad_balance', 0):.2f} ₺</code>
• <b>Toplam Bakiye:</b> <code>{total_balance:.2f} ₺</code>

<b>─────────────────────</b>

📊 <b>İSTATİSTİKLER:</b>
• <b>Toplam Kazanç:</b> <code>{user.get('total_earned', 0):.2f} ₺</code>
• <b>Tamamlanan Görev:</b> <code>{user.get('tasks_completed', 0)}</code>
• <b>Referans Sayısı:</b> <code>{user.get('referrals', 0)}</code>
• <b>Referans Kazancı:</b> <code>{user.get('ref_earned', 0):.2f} ₺</code>

<b>─────────────────────</b>

💡 <b>Bilgi:</b>
• Normal bakiyenle para çekebilirsin (yakında)
• Reklam bakiyenle görev oluşturabilirsin
• %25 bonusla reklam bakiyesine çevirebilirsin
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Balance details hatası: {e}")

# ================= 18. REFERANS SİSTEMİ =================
async def show_referral_info(user_id: int, message_id: int = None):
    """Referans bilgilerini göster"""
    user = await get_user(user_id)
    if not user:
        return
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📤 PAYLAŞ", 
            url=f"https://t.me/share/url?url={ref_link}&text=Görev%20Yap%20Para%20Kazan!%20@GorevYapsamBot"),
        types.InlineKeyboardButton("📋 KOPYALA", callback_data=f"copy_{ref_link}")
    )
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('referral.title')}

<b>─────────────────────</b>

{t('referral.earn_per_ref')} <code>1.00 ₺</code>
{t('referral.total_refs')} <code>{user.get('referrals', 0)}</code>
{t('referral.total_earned')} <code>{user.get('ref_earned', 0):.2f} ₺</code>

<b>─────────────────────</b>

{t('referral.your_link')}
<code>{ref_link}</code>

<b>─────────────────────</b>

{t('referral.bonus_tiers')}
{t('referral.bonus_5')}
{t('referral.bonus_10')}
{t('referral.bonus_25')}
{t('referral.bonus_50')}

<b>─────────────────────</b>

{t('referral.how_it_works')}
{t('referral.step1')}
{t('referral.step2')}
{t('referral.step3')}
{t('referral.step4')}
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Referral info hatası: {e}")

# ================= 19. GÖREV SİSTEMİ =================
async def show_task_selection(user_id: int, message_id: int = None):
    """Görev seçim menüsü"""
    user = await get_user(user_id)
    lang = user.get('language', 'tr') if user else 'tr'
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t('tasks.bot_task').format(price="2.50"), callback_data="task_bot"),
        types.InlineKeyboardButton(t('tasks.channel_task').format(price="1.50"), callback_data="task_channel"),
        types.InlineKeyboardButton(t('tasks.group_task').format(price="1.00"), callback_data="task_group")
    )
    markup.add(types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu"))
    
    message = f"""
{t('tasks.select_type')}

<b>─────────────────────</b>

{t('tasks.bot_task').format(price="2.50")}
<i>Botlara katılma/start atma görevi</i>

<b>─────────────────────</b>

{t('tasks.channel_task').format(price="1.50")}
<i>Kanallara katılma görevi</i>

<b>─────────────────────</b>

{t('tasks.group_task').format(price="1.00")}
<i>Gruplara katılma görevi</i>

<b>─────────────────────</b>

💡 <b>Her görev için 3 dakika beklemen gerekiyor.</b>
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Task selection hatası: {e}")

async def show_create_task_menu(user_id: int, message_id: int = None):
    """Görev oluşturma menüsü"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 BOT GÖREVİ OLUŞTUR (2.50 ₺/görüntü)", callback_data="create_bot"),
        types.InlineKeyboardButton("📢 KANAL GÖREVİ OLUŞTUR (1.50 ₺/görüntü)", callback_data="create_channel"),
        types.InlineKeyboardButton("👥 GRUP GÖREVİ OLUŞTUR (1.00 ₺/görüntü)", callback_data="create_group")
    )
    markup.add(types.InlineKeyboardButton("🔙 Geri", callback_data="back_menu"))
    
    message = """
📢 <b>GÖREV OLUŞTURMA</b>

<b>─────────────────────</b>

🤖 <b>BOT GÖREVİ</b>
• Maliyet: 2.50 ₺ / görüntü
• Forward mesaj zorunlu

<b>─────────────────────</b>

📢 <b>KANAL GÖREVİ</b>
• Maliyet: 1.50 ₺ / görüntü
• Forward mesaj zorunlu
• Bot kanalda admin olmalı

<b>─────────────────────</b>

👥 <b>GRUP GÖREVİ</b>
• Maliyet: 1.00 ₺ / görüntü
• Forward mesaj zorunlu
• Bot grupta admin olmalı

<b>─────────────────────</b>

💡 <b>İpucu:</b> Görev oluşturmak için Reklam Bakiyen olmalı.
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Create task menu hatası: {e}")

# ================= 20. REKLAM BAKİYESİ ÇEVİRİMİ =================
async def show_ad_balance_conversion(user_id: int, message_id: int = None):
    """Reklam bakiyesi çevirim menüsü"""
    user = await get_user(user_id)
    if not user:
        return
    
    lang = user.get('language', 'tr')
    t = lambda key: get_translation(lang, key)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("10 ₺", callback_data="convert_10"),
        types.InlineKeyboardButton("25 ₺", callback_data="convert_25"),
        types.InlineKeyboardButton("50 ₺", callback_data="convert_50"),
        types.InlineKeyboardButton("100 ₺", callback_data="convert_100")
    )
    markup.add(
        types.InlineKeyboardButton("250 ₺", callback_data="convert_250"),
        types.InlineKeyboardButton("500 ₺", callback_data="convert_500"),
        types.InlineKeyboardButton("Özel Miktar", callback_data="convert_custom"),
        types.InlineKeyboardButton(t('buttons.back_menu'), callback_data="back_menu")
    )
    
    message = f"""
{t('ad_balance.title')}

<b>─────────────────────</b>

{t('ad_balance.current_normal')} <code>{user.get('balance', 0):.2f} ₺</code>
{t('ad_balance.current_ad')} <code>{user.get('ad_balance', 0):.2f} ₺</code>

<b>─────────────────────</b>

{t('ad_balance.bonus_25')}
{t('ad_balance.bonus_example')}

<b>─────────────────────</b>

{t('ad_balance.select_amount')}
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Ad balance conversion hatası: {e}")

async def handle_ad_conversion(user_id: int, callback_query_id: int, amount: float):
    """Reklam bakiyesi çevirim işlemi"""
    user = await get_user(user_id)
    if not user:
        await bot.answer_callback_query(
            callback_query_id,
            "❌ Kullanıcı bulunamadı!",
            show_alert=True
        )
        return
    
    normal_balance = user.get('balance', 0)
    
    if normal_balance < amount:
        await bot.answer_callback_query(
            callback_query_id,
            f"❌ Yetersiz bakiye! Mevcut: {normal_balance:.2f} ₺",
            show_alert=True
        )
        return
    
    converted_amount = amount * 1.25
    
    await update_balance(user_id, -amount, 'balance')
    await update_balance(user_id, converted_amount, 'ad_balance')
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_menu"))
    
    message = f"""
✅ <b>ÇEVİRİM BAŞARILI!</b>

<b>─────────────────────</b>

💰 <b>Çevrilen Miktar:</b> {amount:.2f} ₺
🎁 <b>Bonus (%25):</b> {amount * 0.25:.2f} ₺
💰 <b>Toplam Kazanç:</b> {converted_amount:.2f} ₺

<b>─────────────────────</b>

📊 <b>Yeni Bakiyeler:</b>
• Normal Bakiye: <code>{normal_balance - amount:.2f} ₺</code>
• Reklam Bakiyesi: <code>{user.get('ad_balance', 0) + converted_amount:.2f} ₺</code>

<b>─────────────────────</b>

💡 <b>Artık reklam bakiyenle görev oluşturabilirsin!</b>
"""
    
    try:
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=callback_query_id,
            text=message,
            reply_markup=markup
        )
    except:
        await bot.send_message(user_id, message, reply_markup=markup)

async def ask_custom_conversion_amount(user_id: int, message_id: int):
    """Özel miktar çevirim için sor"""
    user = await get_user(user_id)
    if not user:
        return
    
    user_states[user_id] = 'waiting_conversion_amount'
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ İptal", callback_data="ad_balance_menu"))
    
    message = f"""
💰 <b>ÖZEL MİKTAR ÇEVİRİMİ</b>

<b>─────────────────────</b>

Mevcut Normal Bakiyen: <code>{user.get('balance', 0):.2f} ₺</code>

<b>─────────────────────</b>

Lütfen çevirmek istediğin miktarı yaz:
(Örnek: 15.50, 100, 250.75)

<b>─────────────────────</b>

💡 <b>Not:</b> %25 bonus otomatik eklenecektir.
"""
    
    await bot.edit_message_text(
        chat_id=user_id,
        message_id=message_id,
        text=message,
        reply_markup=markup
    )

# ================= 21. ADMIN PANEL =================
async def show_admin_panel(user_id: int, message_id: int = None):
    """Admin paneli"""
    if user_id != ADMIN_ID:
        return
    
    total_users = 0
    total_balance = 0
    total_ad_balance = 0
    
    try:
        if db:
            users_ref = db.collection('users')
            users = users_ref.limit(1000).stream()
            
            for user in users:
                user_data = user.to_dict()
                total_balance += user_data.get('balance', 0)
                total_ad_balance += user_data.get('ad_balance', 0)
                total_users += 1
    except Exception as e:
        print(f"Admin istatistik hatası: {e}")
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 İSTATİSTİKLER", callback_data="admin_stats"),
        types.InlineKeyboardButton("👤 KULLANICI BUL", callback_data="admin_find_user")
    )
    markup.add(
        types.InlineKeyboardButton("💰 BAKİYE EKLE", callback_data="admin_add_balance"),
        types.InlineKeyboardButton("📢 DUYURU GÖNDER", callback_data="admin_broadcast")
    )
    markup.add(types.InlineKeyboardButton("🏠 ANA MENÜ", callback_data="back_menu"))
    
    message = f"""
👑 <b>ADMIN PANEL</b>

<b>─────────────────────</b>

📊 <b>GENEL İSTATİSTİKLER:</b>
• Toplam Kullanıcı: <code>{total_users}</code>
• Toplam Normal Bakiye: <code>{total_balance:.2f} ₺</code>
• Toplam Reklam Bakiye: <code>{total_ad_balance:.2f} ₺</code>

<b>─────────────────────</b>

⚡ <b>HIZLI İŞLEMLER:</b>

<i>Altaki butonlardan işlem seçebilirsin.</i>
"""
    
    try:
        if message_id:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=message,
                reply_markup=markup
            )
        else:
            await bot.send_message(user_id, message, reply_markup=markup)
    except Exception as e:
        print(f"Admin panel hatası: {e}")

# ================= 22. MESAJ HANDLER =================
@bot.message_handler(func=lambda message: True)
async def handle_all_messages(message):
    user_id = message.from_user.id
    
    if user_id in user_states and user_states[user_id] == 'waiting_conversion_amount':
        try:
            amount = float(message.text)
            if amount <= 0:
                await bot.send_message(user_id, "❌ Geçersiz miktar! Pozitif bir sayı girin.")
                return
            
            user = await get_user(user_id)
            if user:
                normal_balance = user.get('balance', 0)
                if normal_balance < amount:
                    await bot.send_message(user_id, f"❌ Yetersiz bakiye! Mevcut: {normal_balance:.2f} ₺")
                    del user_states[user_id]
                    await show_main_menu(user_id)
                    return
            
            converted_amount = amount * 1.25
            
            await update_balance(user_id, -amount, 'balance')
            await update_balance(user_id, converted_amount, 'ad_balance')
            del user_states[user_id]
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🏠 Ana Menü", callback_data="back_menu"))
            
            success_msg = f"""
✅ <b>ÇEVİRİM BAŞARILI!</b>

<b>─────────────────────</b>

💰 <b>Çevrilen Miktar:</b> {amount:.2f} ₺
🎁 <b>Bonus (%25):</b> {amount * 0.25:.2f} ₺
💰 <b>Toplam Kazanç:</b> {converted_amount:.2f} ₺

<b>─────────────────────</b>

💡 <b>Artık reklam bakiyenle görev oluşturabilirsin!</b>
"""
            await bot.send_message(user_id, success_msg, reply_markup=markup)
            
        except ValueError:
            await bot.send_message(user_id, "❌ Geçersiz format! Sayı girin. (Örnek: 50.75)")
        except Exception as e:
            await bot.send_message(user_id, f"❌ Hata: {str(e)}")
            del user_states[user_id]
    else:
        await show_main_menu(user_id)

# ================= 23. FİYAT GÜNCELLEME =================
def update_prices():
    """TRX fiyatlarını güncelle"""
    get_trx_price()

def schedule_runner():
    """Schedule görevlerini çalıştır"""
    schedule.every(30).seconds.do(update_prices)
    while True:
        schedule.run_pending()
        time.sleep(1)

# ================= 24. ANA ÇALIŞTIRMA =================
async def run_bot_async():
    """Async bot'u çalıştır"""
    print(f"""
    🚀 GÖREV YAPSAM BOT PRO v16.0
    ═══════════════════════════════════════════
    📅 Başlatılıyor: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    🔧 Database: {'Firebase Firestore v2 ✅' if db else 'Local Cache ⚠️'}
    🌍 Dil Desteği: Türkçe & Azerbaycan
    💰 Ödeme Sistemi: Yakında (Papara & Kripto)
    🛡️ Veri Güvenliği: {'FIREBASE' if db else 'LOCAL'}
    ═══════════════════════════════════════════
    """)
    
    try:
        print("🤖 Bot polling başlatılıyor...")
        await bot.polling(non_stop=True, timeout=60, request_timeout=60)
    except Exception as e:
        print(f"❌ Bot hatası: {e}")
        await asyncio.sleep(10)
        await run_bot_async()

async def main_async():
    """Ana async çalıştırma fonksiyonu"""
    # Schedule thread'ini başlat
    schedule_thread = threading.Thread(target=schedule_runner, daemon=True)
    schedule_thread.start()
    
    # Bot'u başlat
    await run_bot_async()

def main():
    """Ana çalıştırma fonksiyonu"""
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
