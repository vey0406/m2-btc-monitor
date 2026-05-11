"""
M2 GLOBAL vs BITCOIN MONITOR + TELEGRAM NOTIF
Untuk Deploy di Render (24/7, gratis, Mac bisa mati)
"""

import os
import time
import threading
import requests
from datetime import datetime
from flask import Flask, jsonify

# ============================================
# KONFIGURASI TELEGRAM (SUDAH DIISI)
# ============================================
TELEGRAM_BOT_TOKEN = "8626071822:AAHwc0M-NGQhP-4SERByL7ffDrMLIB__jos"
TELEGRAM_CHAT_ID = "1522792088"

# ============================================
# KONFIGURASI LAINNYA
# ============================================
REFRESH_INTERVAL = 60  # Detik (60 = 1 menit)
ALERT_COOLDOWN = 3600  # 1 jam cooldown

# Data M2 Global (UPDATE MANUAL SETIAP BULAN)
# Sumber: https://fred.stlouisfed.org/series/M2SL
M2_DATA = {
    'value_trillion': 22.69,      # <-- SUDAH DIUPDATE
    'date': '2026-05-11',         # <-- SUDAH DIUPDATE
}

# Flask app untuk health check (biar Render tidak sleep)
app = Flask(__name__)

# State untuk tracking
last_alert_time = {'buy': 0, 'sell': 0}
previous_signal = None
last_change = 0

# ============================================
# FUNGSI TELEGRAM
# ============================================

def send_telegram_message(message, message_type='info'):
    """Kirim pesan ke Telegram"""
    global last_alert_time
    
    current_time = time.time()
    
    if message_type in ['buy', 'sell']:
        if current_time - last_alert_time.get(message_type, 0) < ALERT_COOLDOWN:
            print(f"Cooldown: Notifikasi {message_type} ditunda")
            return
        last_alert_time[message_type] = current_time
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"[{timestamp}]\n\n{message}"
    
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': full_message, 'parse_mode': 'HTML'}
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Telegram: Pesan terkirim")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def send_test_message():
    """Kirim pesan test saat pertama jalan"""
    send_telegram_message(f"""
🚀 <b>M2 vs BTC Monitor Aktif!</b>

Monitor telah berhasil di-deploy di Render!
Akan berjalan 24/7 tanpa perlu Mac menyala.

📊 Data M2: ${M2_DATA['value_trillion']:.2f} Trillion
📅 Tanggal data: {M2_DATA['date']}

✅ Monitor berjalan 24/7...
""", 'info')

# ============================================
# FUNGSI BTC & M2
# ============================================

def fetch_btc():
    """Ambil harga BTC real-time dari CoinGecko"""
    global last_change
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'bitcoin',
            'vs_currencies': 'usd',
            'include_market_cap': 'true',
            'include_24hr_change': 'true'
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            btc = data.get('bitcoin', {})
            last_change = btc.get('usd_24h_change', 0)
            return {
                'success': True,
                'price': btc.get('usd', 0),
                'market_cap': btc.get('usd_market_cap', 0),
                'change_24h': btc.get('usd_24h_change', 0)
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def calculate_fair_value():
    """Hitung fair value BTC berdasarkan M2 (historical range 2-5%)"""
    m2_total = M2_DATA['value_trillion'] * 1_000_000_000_000
    fair_low = (m2_total * 0.02) / 21_000_000
    fair_high = (m2_total * 0.05) / 21_000_000
    return fair_low, fair_high

def send_alert(price, status, signal, fair_low, fair_high):
    """Kirim alert ke Telegram saat sinyal muncul"""
    signal_emoji = "🟢 BUY SIGNAL" if signal == 'buy' else "🔴 SELL SIGNAL"
    saran = '✅ Mulai akumulasi Bitcoin secara bertahap' if signal == 'buy' else '⚠️ Pertimbangkan untuk mengambil keuntungan'
    
    message = f"""
🚨 <b>SINYAL DETEKSI!</b>

{signal_emoji}

💰 <b>Bitcoin Price:</b> ${price:,.2f}
<b>24h Change:</b> {last_change:+.2f}%

📊 <b>Valuation Status:</b> {status}
<b>Fair Value Range:</b> ${fair_low:,.0f} - ${fair_high:,.0f}

<b>Saran:</b>
{saran}
"""
    send_telegram_message(message, signal)

# ============================================
# MONITOR LOOP (DI THREAD TERPISAH)
# ============================================

def monitor_loop():
    """Loop monitoring yang berjalan di background"""
    global previous_signal
    
    print("="*60)
    print("🌍 M2 GLOBAL vs BITCOIN MONITOR - RENDER")
    print("="*60)
    print(f"📡 M2 Data: ${M2_DATA['value_trillion']:.2f} Trillion")
    print(f"🔄 Update interval: {REFRESH_INTERVAL} detik")
    print("="*60)
    
    # Kirim pesan test saat pertama jalan
    send_test_message()
    print("✅ Pesan test terkirim! Cek Telegram kamu.")
    
    while True:
        try:
            btc = fetch_btc()
            fair_low, fair_high = calculate_fair_value()
            
            if btc['success']:
                price = btc['price']
                
                # Tentukan status dan sinyal
                if price < fair_low:
                    status = "🔴 UNDERVALUED - BUY"
                    signal = "buy"
                elif price > fair_high:
                    status = "🟢 OVERVALUED - TAKE PROFIT"
                    signal = "sell"
                else:
                    status = "🟡 FAIR VALUE - HOLD"
                    signal = "hold"
                
                # Kirim alert jika status berubah ke buy/sell
                if previous_signal != signal and signal in ['buy', 'sell']:
                    send_alert(price, status, signal, fair_low, fair_high)
                
                previous_signal = signal
                
                # Print log
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] BTC: ${price:,.2f} | {status}")
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {btc.get('error')}")
            
            time.sleep(REFRESH_INTERVAL)
            
        except Exception as e:
            print(f"Error in monitor loop: {e}")
            time.sleep(REFRESH_INTERVAL)

# ============================================
# FLASK ENDPOINTS (UNTUK HEALTH CHECK)
# ============================================

@app.route('/')
def home():
    """Root endpoint - cek status monitor"""
    return jsonify({
        'status': 'running',
        'm2_value': M2_DATA['value_trillion'],
        'm2_date': M2_DATA['date'],
        'last_signal': previous_signal,
        'message': 'M2 vs BTC Monitor is running 24/7'
    })

@app.route('/health')
def health():
    """Health check endpoint untuk Render"""
    return jsonify({'status': 'ok', 'monitor': 'active'})

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    # Jalankan monitor loop di thread terpisah
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Jalankan Flask server (untuk health check)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
