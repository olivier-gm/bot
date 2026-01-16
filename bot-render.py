# coding: utf-8
import telebot
import requests
import json
import os
import time
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
TOKEN = '8556444811:AAF0m841XRL-35xSX6g5DNyr-DWoml0JYNA'
# Tu IP directa del VPS
URL_API_VALERY = 'http://167.86.80.129:3000' 
URL_PROPIA_DEL_BOT = "https://bot-sol7.onrender.com"

# Variables Supabase
SUPABASE_URL = "https://aodhfcpabmjvyusrohjh.supabase.co"
SUPABASE_KEY = "sb_publishable_4_8oRB_GIlwr1f1EskKn0A_YY0uMJPI"
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase conectado")
except Exception as e:
    print(f"❌ Error Supabase config: {e}")

bot = telebot.TeleBot(TOKEN)
app = Flask('')

# --- BASE DE DATOS SIMPLIFICADA PARA DEBUG ---
def get_credits_debug(uid):
    try:
        r = supabase.table('users').select("credits").eq("user_id", uid).execute()
        if not r.data:
            supabase.table('users').insert({"user_id": uid, "credits": 50}).execute() # Damos 50 pa probar
            return 50
        return r.data[0]['credits']
    except: return 99 # Fallback

# --- SERVIDOR WEB ---
@app.route('/')
def home(): return "🔍 MODO DEBUG ACTIVO"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- BOTONES ---
def botones():
    m = InlineKeyboardMarkup(row_width=3)
    b = [InlineKeyboardButton(c, callback_data=f"a_{c}") for c in ["BTC", "ETH", "SOL", "RAY", "XRP", "SUI"]]
    m.add(*b)
    return m

# --- COMANDOS ---
@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🛠 **MODO DEBUG**\nDale a un botón y te mostraré la respuesta CRUDA del servidor.", reply_markup=botones())

# --- HANDLER DEPURACIÓN ---
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    data = call.data

    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        try:
            bot.answer_callback_query(call.id, f"Debugueando {coin}...")
            
            # 1. Mensaje de inicio
            msg_debug = bot.send_message(uid, f"📡 Conectando a API para {coin}...")
            
            # 2. LA PETICIÓN
            start_time = time.time()
            try:
                r = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=60)
                duration = time.time() - start_time
            except Exception as conn_err:
                bot.send_message(uid, f"❌ **ERROR DE CONEXIÓN:**\n`{str(conn_err)}`", parse_mode="Markdown")
                return

            # 3. ANÁLISIS DEL STATUS
            info_status = f"⏱ Tiempo: {round(duration, 2)}s\npg Código: {r.status_code}\n"
            bot.edit_message_text(info_status + "📥 Leyendo respuesta...", uid, msg_debug.message_id)

            # 4. EXTRACCIÓN CRUDA (RAW TEXT)
            raw_text = r.text
            
            # Enviaremos el texto crudo (recortado a 3000 chars por límite de Telegram)
            bot.send_message(uid, f"📦 **RESPUESTA RAW (Primeros 3000 chars):**\n\n`{raw_text[:3000]}`", parse_mode="Markdown")

            # 5. INTENTO DE PARSEO MANUAL
            try:
                json_data = r.json()
                bot.send_message(uid, f"✅ **JSON VÁLIDO.**\nClaves encontradas en raíz: `{list(json_data.keys())}`", parse_mode="Markdown")
                
                # BÚSQUEDA DEL DATO
                prediction = None
                
                # Caso A: Está en la raíz
                if 'prediction' in json_data:
                    prediction = json_data['prediction']
                    bot.send_message(uid, "🔍 Encontrado 'prediction' en RAÍZ.")
                
                # Caso B: Está en JSONprompt -> aiResponse
                elif 'JSONprompt' in json_data:
                    jp = json_data['JSONprompt']
                    if 'aiResponse' in jp:
                        ai_res = jp['aiResponse']
                        bot.send_message(uid, f"🔍 Encontrado 'aiResponse'. Tipo: {type(ai_res)}")
                        
                        if isinstance(ai_res, str):
                            bot.send_message(uid, "⚠️ aiResponse es STRING. Intentando limpiar...")
                            # Limpieza agresiva
                            clean = ai_res.replace("```json", "").replace("```", "").strip()
                            prediction = json.loads(clean).get('prediction')
                        elif isinstance(ai_res, dict):
                             prediction = ai_res.get('prediction')
                    else:
                        bot.send_message(uid, "❌ JSONprompt existe, pero no tiene 'aiResponse'.")
                
                # RESULTADO FINAL DEL DEBUG
                if prediction:
                    bot.send_message(uid, f"🎉 **ÉXITO EXTRAYENDO:**\nSubida: {prediction.get('subida')}\nBajada: {prediction.get('bajada')}")
                else:
                    bot.send_message(uid, "💀 **FRACASO:** No pude encontrar la clave 'prediction' en ninguna parte.")

            except json.JSONDecodeError:
                bot.send_message(uid, "❌ **EL TEXTO NO ES JSON VÁLIDO.** Revisar salida RAW arriba.")
            except Exception as e:
                bot.send_message(uid, f"❌ **CRASH PARSEANDO:**\n`{traceback.format_exc()}`", parse_mode="Markdown")

        except Exception as e:
            bot.send_message(uid, f"🔥 **ERROR CRÍTICO DEL BOT:**\n{e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
