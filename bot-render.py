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
# Usamos tu URL de producción
API_BASE_URL = 'https://valery-1.onrender.com/ask' 

bot = telebot.TeleBot(TOKEN)

# --- 2. TRUCO PARA MANTENERLO VIVO EN RENDER ---
# Render exige que abras un puerto web. Si no, mata la app.
app = Flask('')

@app.route('/')
def home():
    return "¡Bot funcionando OK!"

def run_web():
    # Render nos da el puerto en la variable de entorno PORT
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- 3. LÓGICA DEL BOT ---
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
        print(f"Error en start: {e}")

@bot.callback_query_handler(func=lambda call: call.data in COINS)
def callback_query(call):
    crypto = call.data
    # Usamos try-except para que el bot no muera si Telegram falla al responder
    try:
        bot.answer_callback_query(call.id, f"Consultando {crypto}...")
    except:
        pass # A veces falla si el usuario clickea muy rápido, lo ignoramos

    try:
        # IMPORTANTE: Aquí NO usamos proxies. En Render la conexión es limpia.
        print(f"Consultando API para {crypto}...")
        response = requests.get(f"{API_BASE_URL}?crypto={crypto}", timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            
            # Verificamos estructura
            if 'JSONprompt' in data and data['JSONprompt'].get('aiResponse'):
                raw_ai = data['JSONprompt']['aiResponse']
                
                # A veces la IA devuelve un objeto directo, a veces un string.
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
                bot.send_message(call.message.chat.id, "⚠️ La IA no devolvió datos válidos.")
        else:
            bot.send_message(call.message.chat.id, f"⚠️ Error API: {response.status_code}")

    except Exception as e:
        print(f"ERROR FATAL: {e}")
        bot.send_message(call.message.chat.id, "❌ Error de conexión con el servidor.")

# --- 4. ARRANQUE ---
if __name__ == "__main__":
    print("Iniciando Web Server...")
    keep_alive() # Arranca el servidor web falso
    print("Iniciando Polling...")
    # infinity_polling es más robusto que polling normal

    bot.infinity_polling(timeout=10, long_polling_timeout=5)
