"""
╔══════════════════════════════════════════════════════════╗
║                  GÖREV YAPSAM BOT v4.0                   ║
║              PROFESYONEL ARRAYÜZ & TÜM SİSTEMLER         ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import time
import json
import requests
from datetime import datetime, timedelta
import signal
import sys
import threading
import random
from flask import Flask, jsonify, request
from enum import Enum

# ================= 1. KONFİGÜRASYON =================
class Dil(Enum):
    TURKCE = "tr"
    AZERBAYCAN = "az"

class Sistem:
    # Sabitler
    TASK_PRICES = {
        'bot': 2.5,
        'channel': 1.5,
        'group': 1.0
    }
    
    MIN_WITHDRAWAL = 20.0
    DAILY_BONUS_RANGE = (1.0, 5.0)
    REFERRAL_BONUS = 1.0
    WELCOME_BONUS = 2.0
    
    # Renk kodları
    RENKLER = {
        'kirmizi': '🔴',
        'yesil': '🟢',
        'sari': '🟡',
        'mavi': '🔵',
        'mor': '🟣',
        'turuncu': '🟠'
    }

# ================= 2. DİL SİSTEMİ =================
class DilSistemi:
    @staticmethod
    def get_text(dil: Dil, key: str, **kwargs) -> str:
        """Dil çevirileri"""
        texts = {
            Dil.TURKCE: {
                # Ana menü
                'main_menu_title': "🚀 <b>GÖREV YAPSAM BOT</b>",
                'welcome': "👋 <b>Hoşgeldin {name}!</b>",
                'balance': "💰 <b>BAKİYE:</b> {balance:.2f}₺",
                'tasks_completed': "📊 <b>Görevler:</b> {count}",
                'referrals': "👥 <b>Referans:</b> {count}",
                'daily_bonus_available': "🎁 <b>Günlük Bonus:</b> MEVCUT",
                'daily_bonus_claimed': "🎁 <b>Günlük Bonus:</b> ALINDI",
                
                # Butonlar
                'btn_profile': "👤 PROFİL",
                'btn_tasks': "🤖 GÖREV YAP",
                'btn_create_task': "📢 GÖREV OLUŞTUR",
                'btn_daily_bonus': "🎁 GÜNLÜK BONUS",
                'btn_referral': "👥 REFERANS",
                'btn_withdraw': "💸 PARA ÇEK",
                'btn_balance': "💰 BAKİYE",
                'btn_menu': "🏠 MENÜ",
                'btn_admin': "👑 ADMIN",
                'btn_refresh': "🔄 YENİLE",
                'btn_settings': "⚙️ AYARLAR",
                'btn_support': "📞 DESTEK",
                'btn_statistics': "📈 İSTATİSTİK",
                'btn_help': "❓ YARDIM",
                
                # Görev menüsü
                'task_menu_title': "📋 <b>GÖREV SEÇİMİ</b>",
                'bot_task': "🤖 BOT GÖREVİ",
                'bot_price': "2.5₺",
                'channel_task': "📢 KANAL GÖREVİ",
                'channel_price': "1.5₺",
                'group_task': "👥 GRUP GÖREVİ",
                'group_price': "1.0₺",
                'select_task': "👇 <b>Görev tipini seçin:</b>",
                
                # Profil
                'profile_title': "👤 <b>PROFİL BİLGİLERİ</b>",
                'user_id': "🆔 <b>ID:</b> {id}",
                'username': "👤 <b>Kullanıcı:</b> {username}",
                'registration_date': "📅 <b>Kayıt Tarihi:</b> {date}",
                'total_earned': "💰 <b>Toplam Kazanç:</b> {amount:.2f}₺",
                'task_stats': "📊 <b>Görev İstatistikleri:</b>",
                'tasks_done': "• Tamamlanan: {done}",
                'tasks_created': "• Oluşturulan: {created}",
                'ref_stats': "👥 <b>Referans İstatistikleri:</b>",
                'ref_count': "• Sayı: {count}",
                'ref_earned': "• Kazanç: {earned:.2f}₺",
                
                # Günlük bonus
                'daily_title': "🎁 <b>GÜNLÜK BONUS</b>",
                'daily_available': "✅ <b>Bugünkü bonusunuz hazır!</b>",
                'daily_claimed': "⏳ <b>Bir sonraki bonus:</b> {time}",
                'daily_amount': "💰 <b>Bonus Miktarı:</b> {amount:.2f}₺",
                'daily_streak': "🔥 <b>Üst üste gün:</b> {days}",
                'daily_total': "🏆 <b>Toplam Bonus:</b> {total:.2f}₺",
                
                # Referans
                'referral_title': "👥 <b>REFERANS SİSTEMİ</b>",
                'referral_link': "🔗 <b>Referans Linkin:</b>",
                'referral_stats': "📊 <b>İstatistikler:</b>",
                'bonus_tiers': "🏆 <b>Bonus Seviyeleri:</b>",
                'tier_5': "• 5 referans: +2₺",
                'tier_10': "• 10 referans: +5₺",
                'tier_25': "• 25 referans: +15₺",
                'tier_50': "• 50 referans: +35₺",
                'share': "📤 PAYLAŞ",
                'copy': "📋 KOPYALA",
                
                # Para çekme
                'withdraw_title': "💸 <b>PARA ÇEKME</b>",
                'current_balance': "💰 <b>Mevcut Bakiye:</b> {balance:.2f}₺",
                'min_withdraw': "📊 <b>Minimum Çekim:</b> {min:.2f}₺",
                'processing_time': "⏰ <b>İşlem Süresi:</b> 24-48 saat",
                'coming_soon': "🎯 <b>YAKINDA AKTİF:</b>",
                'payment_methods': "• ₿ Kripto Para (USDT)\n• 📱 Papara\n• 🏦 Banka Havalesi",
                'withdraw_note': "⚠️ <b>Not:</b> Ödeme işlemleri manuel olarak yapılmaktadır.",
                'request_button': "💸 ÖDEME TALEP ET",
                'min_not_met': "❌ Minimum: {min:.2f}₺",
                
                # Ödeme talep
                'request_title': "✅ <b>ÖDEME TALEBI OLUŞTURULDU!</b>",
                'request_id': "📋 <b>Talep No:</b> <code>{id}</code>",
                'request_amount': "💰 <b>Tutar:</b> {amount:.2f}₺",
                'request_name': "👤 <b>Adınız:</b> {name}",
                'request_date': "📅 <b>Tarih:</b> {date}",
                'request_status': "⏳ <b>DURUM:</b> Admin onayı bekleniyor...",
                'request_time': "🕐 <b>Süre:</b> 24-48 saat",
                'request_notification': "⚠️ <i>Lütfen bildirimleri açık tutun!</i>",
                
                # Admin
                'admin_title': "👑 <b>ADMIN PANELİ</b>",
                'total_users': "👥 <b>Toplam Kullanıcı:</b> {count}",
                'total_balance': "💰 <b>Toplam Bakiye:</b> {amount:.2f}₺",
                'total_tasks': "📊 <b>Toplam Görev:</b> {count}",
                'active_tasks': "⚡ <b>Aktif Görev:</b> {count}",
                'system_status': "🖥️ <b>Sistem Durumu:</b>",
                'bot_status': "• Bot: 🟢 AKTİF",
                'db_status': "• Veritabanı: 🟢 ÇALIŞIYOR",
                'api_status': "• API: 🟢 BAĞLI",
                
                # Hata mesajları
                'error_channel': "❌ <b>Önce kanala katıl!</b> @{channel}",
                'error_balance': "❌ <b>Yetersiz bakiye!</b>",
                'error_minimum': "❌ <b>Minimum tutar:</b> {amount}₺",
                'error_invalid': "❌ <b>Geçersiz işlem!</b>",
                'error_already_claimed': "❌ <b>Bugünkü bonusu zaten aldın!</b>",
                
                # Başarı mesajları
                'success_welcome': "🎉 <b>Hoşgeldin bonusu yüklendi!</b>",
                'success_referral': "🎉 <b>Referans bonusu yüklendi!</b>",
                'success_daily': "🎉 <b>Günlük bonus yüklendi!</b>",
                'success_task': "✅ <b>Görev başarıyla oluşturuldu!</b>",
                'success_withdraw': "✅ <b>Ödeme talebi oluşturuldu!</b>",
                
                # Diğer
                'channel': "📢 <b>Kanal:</b> @{name}",
                'separator': "══════════════════════════════",
            },
            
            Dil.AZERBAYCAN: {
                # Ana menü
                'main_menu_title': "🚀 <b>TAPŞIRIQ EDƏN BOT</b>",
                'welcome': "👋 <b>Xoş gəldin {name}!</b>",
                'balance': "💰 <b>BALANS:</b> {balance:.2f}₺",
                'tasks_completed': "📊 <b>Tapşırıqlar:</b> {count}",
                'referrals': "👥 <b>Referans:</b> {count}",
                'daily_bonus_available': "🎁 <b>Gündəlik Bonus:</b> MÖVCUD",
                'daily_bonus_claimed': "🎁 <b>Gündəlik Bonus:</b> GÖTÜRÜLÜB",
                
                # Butonlar
                'btn_profile': "👤 PROFİL",
                'btn_tasks': "🤖 TAPŞIRIQ ET",
                'btn_create_task': "📢 TAPŞIRIQ YARAT",
                'btn_daily_bonus': "🎁 GÜNDƏLİK BONUS",
                'btn_referral': "👥 REFERANS",
                'btn_withdraw': "💸 PUL ÇƏK",
                'btn_balance': "💰 BALANS",
                'btn_menu': "🏠 MENYU",
                'btn_admin': "👑 ADMIN",
                'btn_refresh': "🔄 YENİLƏ",
                'btn_settings': "⚙️ AYARLAR",
                'btn_support': "📞 DƏSTƏK",
                'btn_statistics': "📈 STATİSTİKA",
                'btn_help': "❓ KÖMƏK",
                
                # Görev menüsü
                'task_menu_title': "📋 <b>TAPŞIRIQ SEÇİMİ</b>",
                'bot_task': "🤖 BOT TAPŞIRIĞI",
                'bot_price': "2.5₺",
                'channel_task': "📢 KANAL TAPŞIRIĞI",
                'channel_price': "1.5₺",
                'group_task': "👥 QRUPPA TAPŞIRIĞI",
                'group_price': "1.0₺",
                'select_task': "👇 <b>Tapşırıq növünü seçin:</b>",
                
                # Profil
                'profile_title': "👤 <b>PROFİL MƏLUMATI</b>",
                'user_id': "🆔 <b>ID:</b> {id}",
                'username': "👤 <b>İstifadəçi:</b> {username}",
                'registration_date': "📅 <b>Qeydiyyat Tarixi:</b> {date}",
                'total_earned': "💰 <b>Ümumi Qazanç:</b> {amount:.2f}₺",
                'task_stats': "📊 <b>Tapşırıq Statistika:</b>",
                'tasks_done': "• Tamamlanan: {done}",
                'tasks_created': "• Yaradılan: {created}",
                'ref_stats': "👥 <b>Referans Statistika:</b>",
                'ref_count': "• Sayı: {count}",
                'ref_earned': "• Qazanç: {earned:.2f}₺",
                
                # Günlük bonus
                'daily_title': "🎁 <b>GÜNDƏLİK BONUS</b>",
                'daily_available': "✅ <b>Bugünkü bonusunuz hazırdır!</b>",
                'daily_claimed': "⏳ <b>Növbəti bonus:</b> {time}",
                'daily_amount': "💰 <b>Bonus Məbləği:</b> {amount:.2f}₺",
                'daily_streak': "🔥 <b>Ard-arda gün:</b> {days}",
                'daily_total': "🏆 <b>Ümumi Bonus:</b> {total:.2f}₺",
                
                # Referans
                'referral_title': "👥 <b>REFERANS SİSTEMİ</b>",
                'referral_link': "🔗 <b>Referans Linkiniz:</b>",
                'referral_stats': "📊 <b>Statistika:</b>",
                'bonus_tiers': "🏆 <b>Bonus Səviyyələri:</b>",
                'tier_5': "• 5 referans: +2₺",
                'tier_10': "• 10 referans: +5₺",
                'tier_25': "• 25 referans: +15₺",
                'tier_50': "• 50 referans: +35₺",
                'share': "📤 PAYLAŞ",
                'copy': "📋 KOPYALA",
                
                # Para çekme
                'withdraw_title': "💸 <b>PUL ÇƏKMƏ</b>",
                'current_balance': "💰 <b>Cari Balans:</b> {balance:.2f}₺",
                'min_withdraw': "📊 <b>Minimum Çəkmə:</b> {min:.2f}₺",
                'processing_time': "⏰ <b>Emal Müddəti:</b> 24-48 saat",
                'coming_soon': "🎯 <b>TEZLİKLƏ AKTİV:</b>",
                'payment_methods': "• ₿ Kripto Valyuta (USDT)\n• 📱 Papara\n• 🏦 Bank Köçürməsi",
                'withdraw_note': "⚠️ <b>Qeyd:</b> Ödəniş əməliyyatları manual olaraq aparılır.",
                'request_button': "💸 ÖDƏNİŞ TƏLƏB ET",
                'min_not_met': "❌ Minimum: {min:.2f}₺",
                
                # Ödeme talep
                'request_title': "✅ <b>ÖDƏNİŞ TƏLƏBİ YARADILDI!</b>",
                'request_id': "📋 <b>Tələb №:</b> <code>{id}</code>",
                'request_amount': "💰 <b>Məbləğ:</b> {amount:.2f}₺",
                'request_name': "👤 <b>Adınız:</b> {name}",
                'request_date': "📅 <b>Tarix:</b> {date}",
                'request_status': "⏳ <b>VƏZİYYƏT:</b> Admin təsdiqi gözlənilir...",
                'request_time': "🕐 <b>Müddət:</b> 24-48 saat",
                'request_notification': "⚠️ <i>Xahiş edirik bildirişləri açıq saxlayın!</i>",
                
                # Admin
                'admin_title': "👑 <b>ADMIN PANELİ</b>",
                'total_users': "👥 <b>Ümumi İstifadəçi:</b> {count}",
                'total_balance': "💰 <b>Ümumi Balans:</b> {amount:.2f}₺",
                'total_tasks': "📊 <b>Ümumi Tapşırıq:</b> {count}",
                'active_tasks': "⚡ <b>Aktiv Tapşırıq:</b> {count}",
                'system_status': "🖥️ <b>Sistem Vəziyyəti:</b>",
                'bot_status': "• Bot: 🟢 AKTİV",
                'db_status': "• Verilənlər Bazası: 🟢 İŞLƏYİR",
                'api_status': "• API: 🟢 BAĞLI",
                
                # Hata mesajları
                'error_channel': "❌ <b>Əvvəlcə kanala qoşul!</b> @{channel}",
                'error_balance': "❌ <b>Kifayət qədər balans yoxdur!</b>",
                'error_minimum': "❌ <b>Minimum məbləğ:</b> {amount}₺",
                'error_invalid': "❌ <b>Yanlış əməliyyat!</b>",
                'error_already_claimed': "❌ <b>Bugünkü bonusu artıq götürmüsünüz!</b>",
                
                # Başarı mesajları
                'success_welcome': "🎉 <b>Xoş gəldin bonusu yükləndi!</b>",
                'success_referral': "🎉 <b>Referans bonusu yükləndi!</b>",
                'success_daily': "🎉 <b>Gündəlik bonus yükləndi!</b>",
                'success_task': "✅ <b>Tapşırıq uğurla yaradıldı!</b>",
                'success_withdraw': "✅ <b>Ödəniş tələbi yaradıldı!</b>",
                
                # Diğer
                'channel': "📢 <b>Kanal:</b> @{name}",
                'separator': "══════════════════════════════",
            }
        }
        
        text = texts.get(dil, texts[Dil.TURKCE]).get(key, key)
        return text.format(**kwargs) if kwargs else text

# ================= 3. FLASK APP =================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Görev Yapsam Bot v4.0",
        "version": "4.0",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

# ================= 4. VERİTABANI SİSTEMİ =================
class Veritabani:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_databases()
        return cls._instance
    
    def init_databases(self):
        """Veritabanlarını yükle"""
        self.files = {
            'users': 'users.json',
            'tasks': 'tasks.json',
            'withdrawals': 'withdrawals.json',
            'daily_bonuses': 'daily_bonuses.json',
            'settings': 'settings.json'
        }
        
        self.data = {}
        for key, filename in self.files.items():
            self.data[key] = self.load_json(filename)
    
    def load_json(self, filename):
        """JSON dosyasını yükle"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
    
    def save_json(self, filename, data):
        """JSON dosyasına kaydet"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def save_all(self):
        """Tüm veritabanlarını kaydet"""
        for key, filename in self.files.items():
            self.save_json(filename, self.data[key])
    
    def get_user(self, user_id):
        """Kullanıcıyı getir veya oluştur"""
        user_id = str(user_id)
        if user_id not in self.data['users']:
            self.data['users'][user_id] = self.create_user_template(user_id)
            self.save_json(self.files['users'], self.data['users'])
        return self.data['users'][user_id]
    
    def create_user_template(self, user_id):
        """Yeni kullanıcı şablonu"""
        return {
            'id': user_id,
            'name': '',
            'username': '',
            'balance': 0.0,
            'ref_balance': 0.0,  # Referans bakiyesi
            'total_earned': 0.0,
            'tasks_completed': 0,
            'tasks_created': 0,
            'referrals': 0,
            'ref_earned': 0.0,
            'daily_streak': 0,
            'daily_total': 0.0,
            'last_daily': None,
            'language': 'tr',
            'created_at': datetime.now().isoformat(),
            'state': None,
            'state_data': {},
            'is_admin': user_id == os.getenv("ADMIN_ID", "7904032877")
        }
    
    def update_user(self, user_id, data):
        """Kullanıcıyı güncelle"""
        user_id = str(user_id)
        if user_id in self.data['users']:
            self.data['users'][user_id].update(data)
            self.save_json(self.files['users'], self.data['users'])
            return True
        return False
    
    def add_balance(self, user_id, amount, balance_type='main'):
        """Bakiye ekle"""
        user = self.get_user(user_id)
        if balance_type == 'main':
            user['balance'] += amount
        elif balance_type == 'ref':
            user['ref_balance'] += amount
        user['total_earned'] += amount
        self.update_user(user_id, user)
        return user['balance'] if balance_type == 'main' else user['ref_balance']

# ================= 5. TELEGRAM API =================
class TelegramAPI:
    def __init__(self, token):
        self.base_url = f"https://api.telegram.org/bot{token}/"
    
    def send_message(self, chat_id, text, reply_markup=None):
        """Mesaj gönder"""
        url = self.base_url + "sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        
        try:
            response = requests.post(url, json=data, timeout=10)
            return response.json()
        except:
            return None
    
    def answer_callback(self, callback_id, text=None, show_alert=False):
        """Callback'e cevap ver"""
        url = self.base_url + "answerCallbackQuery"
        data = {'callback_query_id': callback_id}
        
        if text:
            data['text'] = text
            data['show_alert'] = show_alert
        
        try:
            requests.post(url, json=data, timeout=5)
        except:
            pass
    
    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        """Mesajı düzenle"""
        url = self.base_url + "editMessageText"
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
    
    def get_chat_member(self, channel, user_id):
        """Kanal üyeliğini kontrol et"""
        url = self.base_url + "getChatMember"
        data = {
            'chat_id': f"@{channel}",
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

# ================= 6. ARAYÜZ SİSTEMİ =================
class Arayuz:
    @staticmethod
    def create_inline_keyboard(buttons, columns=2):
        """Inline keyboard oluştur"""
        keyboard = []
        row = []
        
        for i, button in enumerate(buttons):
            row.append(button)
            if (i + 1) % columns == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        return {'inline_keyboard': keyboard}
    
    @staticmethod
    def main_menu(user, dil=Dil.TURKCE):
        """Ana menü butonları"""
        t = lambda key: DilSistemi.get_text(dil, key)
        
        buttons = [
            {'text': t('btn_profile'), 'callback_data': 'profile'},
            {'text': t('btn_tasks'), 'callback_data': 'tasks'},
            {'text': t('btn_create_task'), 'callback_data': 'create_task'},
            {'text': t('btn_daily_bonus'), 'callback_data': 'daily_bonus'},
            {'text': t('btn_referral'), 'callback_data': 'referral'},
            {'text': f"{t('btn_balance')} {user.get('balance', 0):.2f}₺", 'callback_data': 'balance'},
            {'text': t('btn_withdraw'), 'callback_data': 'withdraw'},
            {'text': t('btn_statistics'), 'callback_data': 'statistics'},
            {'text': t('btn_settings'), 'callback_data': 'settings'},
            {'text': t('btn_support'), 'callback_data': 'support'},
            {'text': t('btn_help'), 'callback_data': 'help'},
            {'text': t('btn_refresh'), 'callback_data': 'refresh'},
        ]
        
        # Admin butonu
        if user.get('is_admin'):
            buttons.append({'text': t('btn_admin'), 'callback_data': 'admin'})
        
        return Arayuz.create_inline_keyboard(buttons, columns=2)
    
    @staticmethod
    def task_menu(dil=Dil.TURKCE):
        """Görev menüsü butonları"""
        t = lambda key: DilSistemi.get_text(dil, key)
        
        buttons = [
            {'text': f"{t('bot_task')} ({t('bot_price')})", 'callback_data': 'task_bot'},
            {'text': f"{t('channel_task')} ({t('channel_price')})", 'callback_data': 'task_channel'},
            {'text': f"{t('group_task')} ({t('group_price')})", 'callback_data': 'task_group'},
            {'text': "🔙 Geri", 'callback_data': 'menu'}
        ]
        
        return Arayuz.create_inline_keyboard(buttons, columns=2)
    
    @staticmethod
    def profile_menu(dil=Dil.TURKCE):
        """Profil menüsü butonları"""
        t = lambda key: DilSistemi.get_text(dil, key)
        
        buttons = [
            {'text': "💰 Ana Bakiye", 'callback_data': 'balance_main'},
            {'text': "👥 Referans Bakiye", 'callback_data': 'balance_ref'},
            {'text': "📊 İstatistik", 'callback_data': 'stats_detailed'},
            {'text': "🔙 Geri", 'callback_data': 'menu'}
        ]
        
        return Arayuz.create_inline_keyboard(buttons, columns=2)
    
    @staticmethod
    def referral_menu(ref_link, dil=Dil.TURKCE):
        """Referans menüsü butonları"""
        t = lambda key: DilSistemi.get_text(dil, key)
        
        buttons = [
            [
                {'text': t('share'), 'url': f'https://t.me/share/url?url={ref_link}&text=Görev Yap Para Kazan!'},
                {'text': t('copy'), 'callback_data': f'copy_{ref_link}'}
            ],
            [
                {'text': "👥 Referans Listesi", 'callback_data': 'ref_list'},
                {'text': "💰 Bonuslar", 'callback_data': 'ref_bonuses'}
            ],
            [
                {'text': "🔙 Geri", 'callback_data': 'menu'}
            ]
        ]
        
        return {'inline_keyboard': buttons}
    
    @staticmethod
    def withdraw_menu(balance, min_withdraw, dil=Dil.TURKCE):
        """Para çekme menüsü butonları"""
        t = lambda key: DilSistemi.get_text(dil, key)
        
        buttons = []
        
        if balance >= min_withdraw:
            buttons.append([
                {'text': t('request_button'), 'callback_data': 'request_withdraw'}
            ])
        else:
            buttons.append([
                {'text': t('min_not_met').format(min=min_withdraw), 'callback_data': 'none'}
            ])
        
        buttons.append([
            {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'},
            {'text': "🔙 Geri", 'callback_data': 'menu'}
        ])
        
        return {'inline_keyboard': buttons}

# ================= 7. BOT SİSTEMİ =================
class BotSistemi:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.admin_id = os.getenv("ADMIN_ID", "7904032877")
        self.mandatory_channel = os.getenv("MANDATORY_CHANNEL", "GY_Refim")
        
        self.api = TelegramAPI(self.token)
        self.db = Veritabani()
        self.running = False
        
        print("🤖 Bot sistemi başlatılıyor...")
    
    def start_polling(self):
        """Polling başlat"""
        self.running = True
        offset = 0
        
        print("🔄 Polling başlatıldı...")
        
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                params = {
                    'offset': offset,
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
                        offset = update['update_id'] + 1
                        
                        if 'message' in update:
                            self.handle_message(update['message'])
                        elif 'callback_query' in update:
                            self.handle_callback(update['callback_query'])
                
            except Exception as e:
                print(f"❌ Polling hatası: {e}")
                time.sleep(2)
    
    def handle_message(self, message):
        """Mesaj işle"""
        try:
            if 'from' not in message:
                return
            
            user_id = str(message['from']['id'])
            user = self.db.get_user(user_id)
            
            # Kullanıcı bilgilerini güncelle
            if not user.get('name'):
                user['name'] = message['from'].get('first_name', 'Kullanıcı')
                user['username'] = message['from'].get('username', '')
                self.db.update_user(user_id, user)
            
            # /start komutu
            if 'text' in message and message['text'].startswith('/start'):
                self.handle_start(user_id, message['text'])
                return
            
            # State kontrolü
            if user.get('state'):
                self.handle_user_state(user_id, message)
                return
            
            # Diğer komutlar
            if 'text' in message:
                text = message['text'].lower()
                
                if text == '/menu':
                    self.show_main_menu(user_id)
                elif text == '/help':
                    self.show_help(user_id)
                elif text == '/profile':
                    self.show_profile(user_id)
                elif text == '/balance':
                    self.show_balance(user_id)
            
        except Exception as e:
            print(f"❌ Mesaj işleme hatası: {e}")
    
    def handle_callback(self, callback):
        """Callback işle"""
        try:
            user_id = str(callback['from']['id'])
            data = callback['data']
            callback_id = callback['id']
            
            # Cevap gönder
            self.api.answer_callback(callback_id)
            
            # Kanal kontrolü (bazı işlemler için)
            if data not in ['joined', 'refresh', 'menu']:
                if not self.api.get_chat_member(self.mandatory_channel, int(user_id)):
                    self.api.answer_callback(
                        callback_id,
                        DilSistemi.get_text(Dil.TURKCE, 'error_channel', channel=self.mandatory_channel),
                        True
                    )
                    return
            
            user = self.db.get_user(user_id)
            dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
            
            # Callback işlemleri
            if data == 'joined':
                self.handle_joined(user_id)
            elif data == 'refresh' or data == 'menu':
                self.show_main_menu(user_id)
            elif data == 'profile':
                self.show_profile(user_id)
            elif data.startswith('task_'):
                self.handle_task_selection(user_id, data.replace('task_', ''))
            elif data == 'create_task':
                self.start_task_creation(user_id)
            elif data == 'daily_bonus':
                self.handle_daily_bonus(user_id)
            elif data == 'referral':
                self.show_referral(user_id)
            elif data == 'balance':
                self.show_balance(user_id)
            elif data == 'withdraw':
                self.show_withdraw(user_id)
            elif data == 'request_withdraw':
                self.request_withdrawal(user_id)
            elif data == 'admin':
                self.show_admin_panel(user_id)
            elif data == 'statistics':
                self.show_statistics(user_id)
            elif data == 'settings':
                self.show_settings(user_id)
            elif data == 'support':
                self.show_support(user_id)
            elif data == 'help':
                self.show_help(user_id)
            elif data.startswith('balance_'):
                self.show_balance_detail(user_id, data.replace('balance_', ''))
            elif data == 'stats_detailed':
                self.show_detailed_stats(user_id)
            elif data == 'ref_list':
                self.show_ref_list(user_id)
            elif data == 'ref_bonuses':
                self.show_ref_bonuses(user_id)
            elif data == 'deposit':
                self.show_deposit(user_id)
            
        except Exception as e:
            print(f"❌ Callback işleme hatası: {e}")
    
    def handle_start(self, user_id, text):
        """Start komutunu işle"""
        # Kanal kontrolü
        in_channel = self.api.get_chat_member(self.mandatory_channel, int(user_id))
        
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        # Hoşgeldin bonusu
        if not user.get('welcome_bonus', False):
            self.db.add_balance(user_id, Sistem.WELCOME_BONUS)
            user['welcome_bonus'] = True
            self.db.update_user(user_id, user)
            
            self.api.send_message(
                user_id,
                f"{t('success_welcome')}\n\n"
                f"{t('balance', balance=Sistem.WELCOME_BONUS)}"
            )
        
        # Referans kontrolü
        if ' ' in text:
            parts = text.split()
            if len(parts) > 1:
                ref_code = parts[1]
                if ref_code.startswith('ref_'):
                    referrer_id = ref_code.replace('ref_', '')
                    if referrer_id != user_id and referrer_id in self.db.data['users']:
                        # Referans bonusu
                        self.db.add_balance(referrer_id, Sistem.REFERRAL_BONUS, 'ref')
                        self.db.data['users'][referrer_id]['referrals'] += 1
                        self.db.data['users'][referrer_id]['ref_earned'] += Sistem.REFERRAL_BONUS
                        
                        # Referans kaydet
                        user['referred_by'] = referrer_id
                        self.db.update_user(user_id, user)
                        
                        self.api.send_message(
                            user_id,
                            f"{t('success_referral')}\n\n"
                            f"{t('balance', balance=Sistem.REFERRAL_BONUS)}"
                        )
        
        # Kanal kontrolü
        if not in_channel:
            markup = {
                'inline_keyboard': [
                    [
                        {'text': '📢 KANALA KATIL', 'url': f'https://t.me/{self.mandatory_channel}'}
                    ],
                    [
                        {'text': '✅ KATILDIM', 'callback_data': 'joined'}
                    ]
                ]
            }
            
            self.api.send_message(
                user_id,
                f"{t('welcome', name=user.get('name', 'Kullanıcı'))}\n\n"
                f"📢 <b>Botu kullanmak için kanala katılmalısın:</b>\n"
                f"👉 @{self.mandatory_channel}\n\n"
                f"<i>Katıldıktan sonra '✅ KATILDIM' butonuna bas.</i>",
                markup
            )
            return
        
        # Ana menü
        self.show_main_menu(user_id)
    
    def handle_joined(self, user_id):
        """Kanal katılımını kontrol et"""
        if self.api.get_chat_member(self.mandatory_channel, int(user_id)):
            user = self.db.get_user(user_id)
            user['in_channel'] = True
            self.db.update_user(user_id, user)
            self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        """Ana menüyü göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        # Günlük bonus durumu
        last_daily = user.get('last_daily')
        daily_status = t('daily_bonus_available')
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            if last_date == datetime.now().date():
                daily_status = t('daily_bonus_claimed')
        
        message = (
            f"{t('main_menu_title')}\n"
            f"{t('separator')}\n"
            f"{t('welcome', name=user.get('name', 'Kullanıcı'))}\n\n"
            f"{t('balance', balance=user.get('balance', 0))}\n"
            f"{t('tasks_completed', count=user.get('tasks_completed', 0))}\n"
            f"{t('referrals', count=user.get('referrals', 0))}\n"
            f"{daily_status}\n\n"
            f"{t('channel', name=self.mandatory_channel)}\n"
            f"{t('separator')}\n"
            f"<i>⬇️ Aşağıdaki butonlardan seçim yapın:</i>"
        )
        
        markup = Arayuz.main_menu(user, dil)
        self.api.send_message(user_id, message, markup)
    
    def show_profile(self, user_id):
        """Profili göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        # Kayıt tarihini formatla
        created_at = datetime.fromisoformat(user.get('created_at', datetime.now().isoformat()))
        reg_date = created_at.strftime('%d.%m.%Y %H:%M')
        
        message = (
            f"{t('profile_title')}\n"
            f"{t('separator')}\n"
            f"{t('user_id', id=user_id)}\n"
            f"{t('username', username=user.get('username', 'Belirtilmemiş'))}\n"
            f"{t('registration_date', date=reg_date)}\n"
            f"{t('total_earned', amount=user.get('total_earned', 0))}\n\n"
            f"{t('task_stats')}\n"
            f"{t('tasks_done', done=user.get('tasks_completed', 0))}\n"
            f"{t('tasks_created', created=user.get('tasks_created', 0))}\n\n"
            f"{t('ref_stats')}\n"
            f"{t('ref_count', count=user.get('referrals', 0))}\n"
            f"{t('ref_earned', earned=user.get('ref_earned', 0))}\n"
            f"{t('separator')}"
        )
        
        markup = Arayuz.profile_menu(dil)
        self.api.send_message(user_id, message, markup)
    
    def show_balance(self, user_id):
        """Bakiyeyi göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        message = (
            f"💰 <b>BAKİYE DETAYLARI</b>\n"
            f"{t('separator')}\n"
            f"👤 {user.get('name', 'Kullanıcı')}\n"
            f"🆔 {user_id}\n\n"
            f"💵 <b>ANA BAKİYE</b>\n"
            f"• Mevcut: {user.get('balance', 0):.2f}₺\n"
            f"• Minimum Çekim: {Sistem.MIN_WITHDRAWAL}₺\n\n"
            f"👥 <b>REFERANS BAKİYESİ</b>\n"
            f"• Mevcut: {user.get('ref_balance', 0):.2f}₺\n"
            f"• Toplam Kazanç: {user.get('ref_earned', 0):.2f}₺\n\n"
            f"🏆 <b>TOPLAM BAKİYE</b>\n"
            f"• {user.get('balance', 0) + user.get('ref_balance', 0):.2f}₺\n"
            f"{t('separator')}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💸 Para Çek", 'callback_data': 'withdraw'},
                    {'text': "💰 Bakiye Yükle", 'callback_data': 'deposit'}
                ],
                [
                    {'text': "🔄 Bakiye Transferi", 'callback_data': 'transfer_balance'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_balance_detail(self, user_id, balance_type):
        """Detaylı bakiye göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        
        if balance_type == 'main':
            balance = user.get('balance', 0)
            title = "💰 ANA BAKİYE"
        else:
            balance = user.get('ref_balance', 0)
            title = "👥 REFERANS BAKİYESİ"
        
        message = (
            f"{title}\n"
            f"══════════════════════════════\n\n"
            f"• Mevcut: {balance:.2f}₺\n"
            f"• Minimum Çekim: {Sistem.MIN_WITHDRAWAL}₺\n\n"
            f"<i>Bu bakiyeyi para çekme için kullanabilirsiniz.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💸 Para Çek", 'callback_data': 'withdraw'},
                    {'text': "🔙 Geri", 'callback_data': 'profile'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def handle_task_selection(self, user_id, task_type):
        """Görev seçimini işle"""
        dil = Dil.TURKCE  # Varsayılan dil
        
        prices = {
            'bot': ("🤖 BOT GÖREVİ", "2.5₺"),
            'channel': ("📢 KANAL GÖREVİ", "1.5₺"),
            'group': ("👥 GRUP GÖREVİ", "1₺")
        }
        
        task_name, price = prices.get(task_type, ("Görev", "0₺"))
        
        message = (
            f"🎯 <b>{task_name} SEÇİLDİ</b>\n"
            f"══════════════════════════════\n\n"
            f"💰 <b>Görev Ücreti:</b> {price}\n"
            f"📊 <b>Kota Hesaplama:</b>\n"
            f"• 100₺ bütçe ile {int(100/float(price.replace('₺', '')))} görev\n\n"
            f"👇 <b>Devam etmek için:</b>\n"
            f"1. Görev oluştur butonuna bas\n"
            f"2. Adımları takip et\n"
            f"3. Bütçeni belirle\n\n"
            f"⚠️ <i>Her görev için ayrı oluşturma yapılır.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📝 Görev Oluştur", 'callback_data': f'create_{task_type}'},
                    {'text': "🔙 Geri", 'callback_data': 'tasks'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def start_task_creation(self, user_id):
        """Görev oluşturma başlat"""
        message = (
            "📢 <b>GÖREV OLUŞTURMA</b>\n"
            "══════════════════════════════\n\n"
            "🤖 <b>BOT GÖREVİ</b> - 2.5₺/görev\n"
            "• Forward mesaj ZORUNLU\n"
            "• Bot username ile çalışır\n\n"
            "📢 <b>KANAL GÖREVİ</b> - 1.5₺/görev\n"
            "• Bot kanalda ADMIN olmalı\n"
            "• Forward gerekmez\n\n"
            "👥 <b>GRUP GÖREVİ</b> - 1₺/görev\n"
            "• Bot grupta ADMIN olmalı\n"
            "• Forward gerekmez\n\n"
            "👇 <b>Görev tipini seçin:</b>"
        )
        
        markup = Arayuz.task_menu()
        self.api.send_message(user_id, message, markup)
    
    def handle_daily_bonus(self, user_id):
        """Günlük bonusu işle"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        last_daily = user.get('last_daily')
        now = datetime.now()
        
        # Bonus kontrolü
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            if last_date == now.date():
                # Bugün zaten alınmış
                next_bonus = now + timedelta(days=1)
                next_time = next_bonus.strftime('%d.%m.%Y %H:%M')
                
                message = (
                    f"{t('daily_title')}\n"
                    f"{t('separator')}\n"
                    f"{t('error_already_claimed')}\n\n"
                    f"{t('daily_claimed', time=next_time)}\n"
                    f"{t('daily_streak', days=user.get('daily_streak', 0))}\n"
                    f"{t('daily_total', total=user.get('daily_total', 0))}"
                )
                
                markup = {
                    'inline_keyboard': [
                        [{'text': "🔙 Geri", 'callback_data': 'menu'}]
                    ]
                }
                
                self.api.send_message(user_id, message, markup)
                return
        
        # Bonus ver
        bonus_amount = round(random.uniform(*Sistem.DAILY_BONUS_RANGE), 2)
        
        # Streak güncelleme
        if last_daily:
            last_date = datetime.fromisoformat(last_daily).date()
            yesterday = (now - timedelta(days=1)).date()
            
            if last_date == yesterday:
                # Üst üste gün
                user['daily_streak'] += 1
            else:
                # Streak kırıldı
                user['daily_streak'] = 1
        else:
            # İlk bonus
            user['daily_streak'] = 1
        
        # Bonusu ekle
        self.db.add_balance(user_id, bonus_amount)
        user['last_daily'] = now.isoformat()
        user['daily_total'] = user.get('daily_total', 0) + bonus_amount
        self.db.update_user(user_id, user)
        
        # Streak bonusu
        streak_bonus = 0
        if user['daily_streak'] >= 7:
            streak_bonus = 5.0
        elif user['daily_streak'] >= 30:
            streak_bonus = 20.0
        
        if streak_bonus > 0:
            self.db.add_balance(user_id, streak_bonus)
            bonus_amount += streak_bonus
        
        message = (
            f"{t('daily_title')}\n"
            f"{t('separator')}\n"
            f"🎉 <b>TEBRİKLER! Günlük bonusunuz yüklendi!</b>\n\n"
            f"{t('daily_amount', amount=bonus_amount)}\n"
            f"{t('daily_streak', days=user['daily_streak'])}\n"
            f"{t('daily_total', total=user['daily_total'])}\n\n"
            f"{'🔥 +' + str(streak_bonus) + '₺ streak bonusu!' if streak_bonus > 0 else ''}\n"
            f"{t('balance', balance=user.get('balance', 0))}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "💰 Bakiye", 'callback_data': 'balance'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_referral(self, user_id):
        """Referans sistemini göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        ref_link = f"https://t.me/GorevYapsamBot?start=ref_{user_id}"
        
        message = (
            f"{t('referral_title')}\n"
            f"{t('separator')}\n"
            f"💰 <b>Her referans:</b> 1₺\n"
            f"👤 <b>Toplam referans:</b> {user.get('referrals', 0)}\n"
            f"📈 <b>Referans kazancı:</b> {user.get('ref_earned', 0):.2f}₺\n\n"
            f"{t('referral_link')}\n"
            f"<code>{ref_link}</code>\n\n"
            f"{t('bonus_tiers')}\n"
            f"{t('tier_5')}\n"
            f"{t('tier_10')}\n"
            f"{t('tier_25')}\n"
            f"{t('tier_50')}\n\n"
            f"⚠️ <b>Arkadaşların kanala katılmazsa bonus alamazsın!</b>"
        )
        
        markup = Arayuz.referral_menu(ref_link, dil)
        self.api.send_message(user_id, message, markup)
    
    def show_withdraw(self, user_id):
        """Para çekme menüsünü göster"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        total_balance = user.get('balance', 0) + user.get('ref_balance', 0)
        
        message = (
            f"{t('withdraw_title')}\n"
            f"{t('separator')}\n"
            f"{t('current_balance', balance=total_balance)}\n"
            f"{t('min_withdraw', min=Sistem.MIN_WITHDRAWAL)}\n"
            f"{t('processing_time')}\n\n"
            f"{t('coming_soon')}\n"
            f"{t('payment_methods')}\n\n"
            f"{t('withdraw_note')}\n"
            f"<i>'ÖDEME TALEP ET' butonuna bastıktan sonra admin onayı bekleyin.</i>"
        )
        
        markup = Arayuz.withdraw_menu(total_balance, Sistem.MIN_WITHDRAWAL, dil)
        self.api.send_message(user_id, message, markup)
    
    def request_withdrawal(self, user_id):
        """Para çekme talebi oluştur"""
        user = self.db.get_user(user_id)
        dil = Dil.TURKCE if user.get('language') == 'tr' else Dil.AZERBAYCAN
        t = lambda key: DilSistemi.get_text(dil, key)
        
        total_balance = user.get('balance', 0) + user.get('ref_balance', 0)
        
        if total_balance < Sistem.MIN_WITHDRAWAL:
            self.api.send_message(user_id, t('error_minimum', amount=Sistem.MIN_WITHDRAWAL))
            return
        
        # Talep ID oluştur
        request_id = str(int(time.time() * 1000))
        
        # Çekim kaydı
        withdrawal = {
            'id': request_id,
            'user_id': user_id,
            'user_name': user.get('name', 'Kullanıcı'),
            'amount': total_balance,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'payment_method': 'pending'
        }
        
        self.db.data['withdrawals'][request_id] = withdrawal
        self.db.save_json(self.db.files['withdrawals'], self.db.data['withdrawals'])
        
        # Admin'e bildir
        admin_msg = (
            f"🔔 <b>YENİ ÖDEME TALEBİ</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 <b>Kullanıcı:</b> {user.get('name', 'Kullanıcı')}\n"
            f"🆔 <b>ID:</b> {user_id}\n"
            f"💰 <b>Tutar:</b> {total_balance:.2f}₺\n"
            f"📅 <b>Tarih:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🔢 <b>Talep No:</b> {request_id}\n\n"
            f"💳 <i>Ödeme yöntemi seçin:</i>"
        )
        
        admin_markup = {
            'inline_keyboard': [
                [
                    {'text': "₿ USDT", 'callback_data': f'admin_withdraw_{request_id}_usdt'},
                    {'text': "📱 Papara", 'callback_data': f'admin_withdraw_{request_id}_papara'}
                ],
                [
                    {'text': "🏦 Banka", 'callback_data': f'admin_withdraw_{request_id}_bank'},
                    {'text': "❌ Reddet", 'callback_data': f'admin_withdraw_{request_id}_reject'}
                ]
            ]
        }
        
        self.api.send_message(self.admin_id, admin_msg, admin_markup)
        
        # Kullanıcıya bilgi
        message = (
            f"{t('request_title')}\n"
            f"{t('separator')}\n"
            f"{t('request_id', id=request_id)}\n"
            f"{t('request_amount', amount=total_balance)}\n"
            f"{t('request_name', name=user.get('name', 'Kullanıcı'))}\n"
            f"{t('request_date', date=datetime.now().strftime('%d.%m.%Y %H:%M'))}\n\n"
            f"{t('request_status')}\n"
            f"{t('request_time')}\n\n"
            f"{t('request_notification')}"
        )
        
        markup = {
            'inline_keyboard': [
                [{'text': "🏠 Ana Menü", 'callback_data': 'menu'}]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_admin_panel(self, user_id):
        """Admin panelini göster"""
        user = self.db.get_user(user_id)
        if not user.get('is_admin'):
            return
        
        total_users = len(self.db.data['users'])
        total_balance = sum(u.get('balance', 0) for u in self.db.data['users'].values())
        total_tasks = len(self.db.data['tasks'])
        active_tasks = sum(1 for t in self.db.data['tasks'].values() if t.get('status') == 'active')
        
        message = (
            f"👑 <b>ADMIN PANELİ</b>\n"
            f"══════════════════════════════\n\n"
            f"📊 <b>GENEL İSTATİSTİKLER</b>\n"
            f"• Kullanıcı: {total_users}\n"
            f"• Toplam Bakiye: {total_balance:.2f}₺\n"
            f"• Toplam Görev: {total_tasks}\n"
            f"• Aktif Görev: {active_tasks}\n\n"
            f"🖥️ <b>SİSTEM DURUMU</b>\n"
            f"• Bot: 🟢 AKTİF\n"
            f"• Veritabanı: 🟢 ÇALIŞIYOR\n"
            f"• API: 🟢 BAĞLI\n\n"
            f"🔧 <b>ADMIN ARAÇLARI</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📊 Detaylı İstatistik", 'callback_data': 'admin_stats'},
                    {'text': "👥 Kullanıcı Listesi", 'callback_data': 'admin_users'}
                ],
                [
                    {'text': "💰 Bakiye Yönetimi", 'callback_data': 'admin_balance'},
                    {'text': "📢 Bildirim Gönder", 'callback_data': 'admin_broadcast'}
                ],
                [
                    {'text': "💸 Ödeme Talepleri", 'callback_data': 'admin_withdrawals'},
                    {'text': "⚙️ Sistem Ayarları", 'callback_data': 'admin_settings'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_statistics(self, user_id):
        """İstatistikleri göster"""
        user = self.db.get_user(user_id)
        
        message = (
            f"📈 <b>DETAYLI İSTATİSTİKLER</b>\n"
            f"══════════════════════════════\n\n"
            f"👤 <b>PROFİL</b>\n"
            f"• Kayıt Tarihi: {datetime.fromisoformat(user.get('created_at')).strftime('%d.%m.%Y')}\n"
            f"• Toplam Süre: {(datetime.now() - datetime.fromisoformat(user.get('created_at'))).days} gün\n\n"
            f"💰 <b>FİNANSAL</b>\n"
            f"• Toplam Kazanç: {user.get('total_earned', 0):.2f}₺\n"
            f"• Ortalama Günlük: {user.get('total_earned', 0) / max(1, (datetime.now() - datetime.fromisoformat(user.get('created_at'))).days):.2f}₺\n"
            f"• En Yüksek Bakiye: {user.get('highest_balance', 0):.2f}₺\n\n"
            f"📊 <b>GÖREV İSTATİSTİKLERİ</b>\n"
            f"• Tamamlanan: {user.get('tasks_completed', 0)}\n"
            f"• Oluşturulan: {user.get('tasks_created', 0)}\n"
            f"• Başarı Oranı: %{user.get('success_rate', 0)}\n\n"
            f"👥 <b>REFERANS İSTATİSTİKLERİ</b>\n"
            f"• Toplam Referans: {user.get('referrals', 0)}\n"
            f"• Aktif Referans: {user.get('active_refs', 0)}\n"
            f"• Referans Kazancı: {user.get('ref_earned', 0):.2f}₺"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📅 Günlük Rapor", 'callback_data': 'stats_daily'},
                    {'text': "📊 Aylık Rapor", 'callback_data': 'stats_monthly'}
                ],
                [
                    {'text': "🏆 Sıralama", 'callback_data': 'stats_ranking'},
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_settings(self, user_id):
        """Ayarları göster"""
        user = self.db.get_user(user_id)
        
        message = (
            f"⚙️ <b>AYARLAR</b>\n"
            f"══════════════════════════════\n\n"
            f"🌐 <b>DİL AYARLARI</b>\n"
            f"• Mevcut Dil: {'Türkçe' if user.get('language') == 'tr' else 'Azerbaycan'}\n\n"
            f"🔔 <b>BİLDİRİM AYARLARI</b>\n"
            f"• Görev Bildirimleri: {'✅ Açık' if user.get('notify_tasks', True) else '❌ Kapalı'}\n"
            f"• Bonus Bildirimleri: {'✅ Açık' if user.get('notify_bonus', True) else '❌ Kapalı'}\n"
            f"• Referans Bildirimleri: {'✅ Açık' if user.get('notify_ref', True) else '❌ Kapalı'}\n\n"
            f"🔒 <b>GÜVENLİK AYARLARI</b>\n"
            f"• İki Faktörlü Doğrulama: {'❌ Kapalı'}\n"
            f"• Çıkış Tüm Cihazlardan: {'❌ Kapalı'}\n\n"
            f"📱 <b>GÖRÜNÜM AYARLARI</b>\n"
            f"• Koyu Mod: {'❌ Kapalı'}\n"
            f"• Kompakt Görünüm: {'❌ Kapalı'}"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "🇹🇷 Türkçe", 'callback_data': 'set_lang_tr'},
                    {'text': "🇦🇿 Azerbaycan", 'callback_data': 'set_lang_az'}
                ],
                [
                    {'text': "🔔 Bildirimler", 'callback_data': 'notifications'},
                    {'text': "🔒 Güvenlik", 'callback_data': 'security'}
                ],
                [
                    {'text': "🗑️ Veri Temizle", 'callback_data': 'clear_data'},
                    {'text': "📋 Veri İndir", 'callback_data': 'download_data'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_support(self, user_id):
        """Destek menüsünü göster"""
        message = (
            f"📞 <b>DESTEK SİSTEMİ</b>\n"
            f"══════════════════════════════\n\n"
            f"👨‍💻 <b>TEKNİK DESTEK</b>\n"
            f"• Sorun: Görev tamamlanmıyor\n"
            f"• Sorun: Para çekilemiyor\n"
            f"• Sorun: Bonus alınamıyor\n"
            f"• Sorun: Kanal katılımı\n\n"
            f"📢 <b>İLETİŞİM</b>\n"
            f"• Admin: @AlperenAdmin\n"
            f"• Kanal: @GY_Refim\n"
            f"• Grup: @GY_Destek\n\n"
            f"⏰ <b>ÇALIŞMA SAATLERİ</b>\n"
            f"• Hafta içi: 09:00 - 18:00\n"
            f"• Hafta sonu: 10:00 - 16:00\n\n"
            f"⚠️ <i>Sorunlarınızı direkt mesaj atarak bildirebilirsiniz.</i>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📩 Mesaj Gönder", 'url': 'https://t.me/AlperenAdmin'},
                    {'text': "📢 Kanal", 'url': f'https://t.me/{self.mandatory_channel}'}
                ],
                [
                    {'text': "❓ SSS", 'callback_data': 'faq'},
                    {'text': "📋 Kurallar", 'callback_data': 'rules'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_help(self, user_id):
        """Yardım menüsünü göster"""
        message = (
            f"❓ <b>YARDIM & KULLANIM KILAVUZU</b>\n"
            f"══════════════════════════════\n\n"
            f"📋 <b>TEMEL KOMUTLAR</b>\n"
            f"• /start - Botu başlat\n"
            f"• /menu - Ana menü\n"
            f"• /profile - Profilim\n"
            f"• /balance - Bakiyem\n"
            f"• /help - Yardım\n\n"
            f"🤖 <b>GÖREV SİSTEMİ</b>\n"
            f"1. 'GÖREV YAP' butonuna bas\n"
            f"2. Görev tipini seç\n"
            f"3. Görevi tamamla\n"
            f"4. Paranı al\n\n"
            f"📢 <b>GÖREV OLUŞTURMA</b>\n"
            f"1. 'GÖREV OLUŞTUR' butonu\n"
            f"2. Görev tipi seç\n"
            f"3. Adımları takip et\n"
            f"4. Bütçeni belirle\n\n"
            f"💰 <b>PARA KAZANMA YOLLARI</b>\n"
            f"• Görev yaparak\n"
            f"• Günlük bonus\n"
            f"• Referans sistemi\n"
            f"• Özel görevler\n\n"
            f"⚠️ <b>ÖNEMLİ KURALLAR</b>\n"
            f"• Sahte görev yasak\n"
            f"• Çoklu hesap yasak\n"
            f"• Spam yasak\n"
            f"• Kurallara uymayanlar banlanır"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📚 Detaylı Kılavuz", 'callback_data': 'guide'},
                    {'text': "🎥 Video Anlatım", 'callback_data': 'tutorial'}
                ],
                [
                    {'text': "❓ SSS", 'callback_data': 'faq'},
                    {'text': "📞 Destek", 'callback_data': 'support'}
                ],
                [
                    {'text': "🔙 Geri", 'callback_data': 'menu'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def show_deposit(self, user_id):
        """Bakiye yükleme menüsü"""
        message = (
            f"💰 <b>BAKİYE YÜKLEME</b>\n"
            f"══════════════════════════════\n\n"
            f"🎯 <b>YAKINDA AKTİF!</b>\n\n"
            f"💳 <b>ÖDEME YÖNTEMLERİ</b>\n"
            f"• Papara\n"
            f"• Kripto Para (USDT)\n"
            f"• Banka Havalesi\n\n"
            f"📊 <b>PAKETLER</b>\n"
            f"• 50₺ Paket: +5₺ bonus\n"
            f"• 100₺ Paket: +15₺ bonus\n"
            f"• 250₺ Paket: +50₺ bonus\n"
            f"• 500₺ Paket: +125₺ bonus\n\n"
            f"⏳ <b>Lütfen bekleyin...</b>"
        )
        
        markup = {
            'inline_keyboard': [
                [
                    {'text': "📞 Destek", 'callback_data': 'support'},
                    {'text': "🔙 Geri", 'callback_data': 'balance'}
                ]
            ]
        }
        
        self.api.send_message(user_id, message, markup)
    
    def handle_user_state(self, user_id, message):
        """Kullanıcı state'ini işle"""
        pass  # Görev oluşturma state'leri burada işlenecek

# ================= 8. ANA PROGRAM =================
def main():
    """Ana program"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                  GÖREV YAPSAM BOT v4.0                   ║
    ║              PROFESYONEL ARRAYÜZ & TÜM SİSTEMLER         ║
    ╚══════════════════════════════════════════════════════════╝
    
    ✅ Profesyonel Arayüz
    ✅ Çoklu Dil Desteği (TR/AZ)
    ✅ Gelişmiş Buton Sistemi
    ✅ Detaylı Profil Sistemi
    ✅ Günlük Bonus Sistemi
    ✅ Referans Bakiye Sistemi
    ✅ Para Çekme Sistemi
    ✅ Admin Paneli
    ✅ İstatistik Sistemi
    ✅ Ayarlar Menüsü
    ✅ Destek Sistemi
    ✅ Help & Kılavuz
    """)
    
    # Botu başlat
    bot = BotSistemi()
    
    # Flask app'ini döndür (gunicorn için)
    return app

# WSGI entry point
def create_app():
    return main()

# Development için direkt çalıştırma
if __name__ == "__main__":
    # Flask app'ini al
    app_instance = main()
    
    # Bot polling'i thread'de başlat
    bot_thread = threading.Thread(target=BotSistemi().start_polling, daemon=True)
    bot_thread.start()
    
    # Flask'ı başlat
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Web server başlatılıyor: http://0.0.0.0:{port}")
    app_instance.run(host='0.0.0.0', port=port, debug=False)
