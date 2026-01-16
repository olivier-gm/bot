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
SUPABASE_URL = os.environ.get("SUPABASE_URL", "TU_URL_HTTPS_SUPABASE_CO")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "TU_KEY_ANON")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CREDITOS_INICIALES = 3
PRECIO_PAQUETE = "5 USDT"

bot = telebot.TeleBot(TOKEN)

# --- 2. HERRAMIENTAS DE LIMPIEZA JSON ---

def limpiar_json_string(texto):
    """Limpia cadenas sucias con markdown o basura extra"""
    if not isinstance(texto, str): return texto
    
    # Intento 1: Limpieza básica
    limpio = texto.replace("```json", "").replace("```", "").strip()
    try: return json.loads(limpio)
    except: pass
    
    # Intento 2: Buscar { ... } con Regex
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match: return json.loads(match.group())
    except: pass
    
    return None

def buscar_datos_ia(data):
    """
    BUSCADOR INTELIGENTE:
    Busca los datos de predicción sin importar la estructura del JSON.
    """
    # 1. ¿Está la predicción directamente aquí? (Caso: API devuelve solo la respuesta IA)
    if isinstance(data, dict) and 'prediction' in data:
        return data

    # 2. ¿Está dentro de 'JSONprompt'? (Caso: API devuelve wrapper)
    if isinstance(data, dict) and 'JSONprompt' in data:
        return buscar_datos_ia(data['JSONprompt'])

    # 3. ¿Está dentro de 'aiResponse'? (Caso: Wrapper intermedio)
    if isinstance(data, dict) and 'aiResponse' in data:
        contenido = data['aiResponse']
        # Si aiResponse es un string, lo limpiamos y parseamos
        if isinstance(contenido, str):
            contenido_parseado = limpiar_json_string(contenido)
            if contenido_parseado:
                return buscar_datos_ia(contenido_parseado)
        else:
            return buscar_datos_ia(contenido)
            
    return None

# --- 3. BASE DE DATOS (SUPABASE) ---
# (Idéntico a antes, funciona bien)
def get_user_credits(user_id):
    try:
        response = supabase.table('users').select("credits").eq("user_id", user_id).execute()
        if not response.data:
            supabase.table('users').insert({"user_id": user_id, "credits": CREDITOS_INICIALES}).execute()
            return CREDITOS_INICIALES
        return response.data[0]['credits']
    except Exception as e:
        print(f"❌ Error Supabase: {e}")
        return 0

def deduct_credit(user_id):
    try:
        current = get_user_credits(user_id)
        if current > 0:
            supabase.table('users').update({"credits": current - 1}).eq("user_id", user_id).execute()
    except: pass

def add_credits(user_id, amount):
    try:
        current = get_user_credits(user_id)
        supabase.table('users').update({"credits": current + amount}).eq("user_id", user_id).execute()
    except: pass

# --- 4. SERVIDOR WEB + KEEP ALIVE ---
app = Flask('')

@app.route('/')
def home(): return "🤖 Bot Activo v3.0 (Smart Parser)"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def ping_services():
    while True:
        time.sleep(840)
        try: requests.get(f"{URL_API_VALERY}/ping", timeout=10)
        except: pass
        try: requests.get(URL_PROPIA_DEL_BOT, timeout=10)
        except: pass

def keep_alive():
    t = Thread(target=run_web)
    t.start()
    t2 = Thread(target=ping_services)
    t2.start()

# --- 5. LOGICA BOT ---
COINS = ["BTC", "ETH", "SOL", "RAY", "XRP", "SUI"]

def botones():
    m = InlineKeyboardMarkup(row_width=3)
    b = [InlineKeyboardButton(c, callback_data=f"a_{c}") for c in COINS]
    m.add(*b)
    return m

def btn_pago():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton(f"💎 Recargar ({PRECIO_PAQUETE})", callback_data="buy"))
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    c = get_user_credits(msg.chat.id)
    bot.reply_to(msg, f"🤖 **Crypto AI**\n💰 Créditos: {c}\nElige:", reply_markup=botones(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    data = call.data

    if data == "buy":
        add_credits(uid, 10)
        bot.answer_callback_query(call.id, "✅ Recargado")
        bot.send_message(uid, "🎉 Créditos añadidos.", reply_markup=botones())
        return

    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin saldo", show_alert=True)
            bot.send_message(uid, "⚠️ Sin créditos.", reply_markup=btn_pago())
            return

        try:
            bot.answer_callback_query(call.id, f"Analizando {coin}...")
            deduct_credit(uid)
            
            # Request
            print(f"📡 Solicitando {coin} a la API...")
            r = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
            
            if r.status_code == 200:
                raw_json = r.json()
                
                # --- AQUÍ ESTÁ LA MAGIA ---
                # Buscamos los datos usando la función inteligente
                ai_data = buscar_datos_ia(raw_json)

                if ai_data and 'prediction' in ai_data:
                    pred = ai_data.get('prediction', {})
                    subida = pred.get('subida', 0)
                    bajada = pred.get('bajada', 0)
                    score = ai_data.get('confidence_score', 0)
                    razon = ai_data.get('rationale', 'Sin detalle.')
                    tendencia = "🟢 ALCISTA" if subida > bajada else "🔴 BAJISTA"
                    
                    msg = (
                        f"📊 **Análisis {coin}**\n"
                        f"🔮 **Predicción:** {tendencia}\n"
                        f"📈 Subida: {subida}% | 📉 Bajada: {bajada}%\n"
                        f"🎯 Confianza: {score}/10\n\n"
                        f"🧠 _{razon}_\n\n"
                        f"💰 Créditos: {get_user_credits(uid)}"
                    )
                    bot.send_message(uid, msg, parse_mode="Markdown")
                    time.sleep(1)
                    bot.send_message(uid, "¿Otra?", reply_markup=botones())
                else:
                    # SI FALLA: Le mandamos al usuario lo que recibió el bot para debug
                    # (Esto te ayudará a ver qué está pasando realmente)
                    error_debug = f"⚠️ Estructura desconocida.\nRecibido: `{str(raw_json)[:300]}...`"
                    add_credits(uid, 1)
                    bot.send_message(uid, error_debug, parse_mode="Markdown")
            else:
                add_credits(uid, 1)
                bot.send_message(uid, f"⚠️ Error API: {r.status_code}")

        except Exception as e:
            print(f"ERROR: {e}")
            add_credits(uid, 1)
            bot.send_message(uid, f"❌ Error: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
