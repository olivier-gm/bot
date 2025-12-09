import telebot
import requests
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
from flask import Flask
from threading import Thread
import time

# --- 1. CONFIGURACIÓN ---
TOKEN = '8556444811:AAF0m841XRL-35xSX6g5DNyr-DWoml0JYNA' 

# URL de tu API (Valery)
URL_API_VALERY = 'https://valery-1.onrender.com' 

# ⚠️ URL DE ESTE MISMO BOT (Llénala cuando Render te la asigne)
# Ejemplo: 'https://mi-bot-telegram.onrender.com'
# Si la dejas vacía, el bot funcionará pero podría dormirse a los 15 min.
URL_PROPIA_DEL_BOT = "https://bot-sol7.onrender.com" 

bot = telebot.TeleBot(TOKEN)

# --- 2. SERVIDOR WEB (Para que Render detecte tráfico entrante) ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot Activo. Sistema Keep-Alive funcionando."

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- 3. FUNCIÓN MATAPÁJAROS (KEEP ALIVE DOBLE) ---
def ping_services():
    while True:
        # Esperamos 14 minutos (840 seg). Render duerme a los 15 min.
        time.sleep(840) 
        
        print("⏰ Iniciando ciclo de Keep-Alive...")
        
        try:
            # PÁJARO 1: Despertar a la API (Valery)
            # Asumiendo que tu API tiene una ruta '/' o '/ping' que responde rápido
            requests.get(f"{URL_API_VALERY}/", timeout=10)
            print("✅ Ping enviado a API Valery-1")
        except Exception as e:
            print(f"⚠️ Falló ping a Valery: {e}")

        try:
            # PÁJARO 2: Despertar al Bot (A sí mismo)
            # Esto es OBLIGATORIO para que Render sepa que el bot sigue vivo
            if URL_PROPIA_DEL_BOT.startswith("http"):
                requests.get(URL_PROPIA_DEL_BOT, timeout=10)
                print("✅ Auto-Ping enviado al Bot (Yo mismo)")
            else:
                print("ℹ️ URL del bot no configurada. Recuerda ponerla tras el deploy.")
        except Exception as e:
            print(f"⚠️ Falló Auto-Ping: {e}")

def keep_alive():
    t_server = Thread(target=run_web)
    t_server.start()
    
    t_ping = Thread(target=ping_services)
    t_ping.start()

# --- 4. LÓGICA DEL BOT ---
COINS = ["BTC", "ETH", "SOL", "RAY", "XRP", "SUI"]

def generar_botones():
    markup = InlineKeyboardMarkup()
    markup.row_width = 3
    botones = []
    for coin in COINS:
        botones.append(InlineKeyboardButton(coin, callback_data=coin))
    markup.add(*botones)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    try:
        bot.reply_to(message, "🤖 **Crypto Analizador AI**\n\nElige una moneda:", 
                     reply_markup=generar_botones(), parse_mode="Markdown")
    except Exception as e:
        print(f"Error start: {e}")

@bot.callback_query_handler(func=lambda call: call.data in COINS)
def callback_query(call):
    crypto = call.data
    try:
        bot.answer_callback_query(call.id, f"Consultando {crypto}...")
    except:
        pass 

    try:
        # Petición a la API
        response = requests.get(f"{URL_API_VALERY}/ask?crypto={crypto}", timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if 'JSONprompt' in data and data['JSONprompt'].get('aiResponse'):
                raw_ai = data['JSONprompt']['aiResponse']
                
                if isinstance(raw_ai, str):
                    ai_data = json.loads(raw_ai)
                else:
                    ai_data = raw_ai

                pred = ai_data.get('prediction', {})
                subida = pred.get('subida', 0)
                bajada = pred.get('bajada', 0)
                score = ai_data.get('confidence_score', 0)
                razon = ai_data.get('rationale', '...')
                
                tendencia = "🟢 ALCISTA" if subida > bajada else "🔴 BAJISTA"
                
                mensaje = (
                    f"📊 **{crypto}**\n"
                    f"🔮 **Predicción:** {tendencia}\n"
                    f"📈 Subida: {subida}% | 📉 Bajada: {bajada}%\n"
                    f"🎯 Confianza: {score}/10\n\n"
                    f"🧠 _{razon}_"
                )
                bot.send_message(call.message.chat.id, mensaje, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, "⚠️ Datos insuficientes.")
        else:
            bot.send_message(call.message.chat.id, f"⚠️ Error API: {response.status_code}")

    except Exception as e:
        print(f"ERROR: {e}")
        bot.send_message(call.message.chat.id, "❌ Error de conexión.")

# --- 5. ARRANQUE ---
if __name__ == "__main__":
    keep_alive() 
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
