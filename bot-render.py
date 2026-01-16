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
except:
    print("⚠️ Error iniciando Supabase (revisar keys)")

bot = telebot.TeleBot(TOKEN)
CREDITOS_INICIALES = 3

# --- 2. BASE DE DATOS ---
def get_user_credits(user_id):
    try:
        r = supabase.table('users').select("credits").eq("user_id", user_id).execute()
        if not r.data:
            supabase.table('users').insert({"user_id": user_id, "credits": CREDITOS_INICIALES}).execute()
            return CREDITOS_INICIALES
        return r.data[0]['credits']
    except: return 3 # Fallback por seguridad

def deduct_credit(user_id):
    try:
        c = get_user_credits(user_id)
        if c > 0: supabase.table('users').update({"credits": c - 1}).eq("user_id", user_id).execute()
    except: pass

def add_credits(user_id, amount):
    try:
        c = get_user_credits(user_id)
        supabase.table('users').update({"credits": c + amount}).eq("user_id", user_id).execute()
    except: pass

# --- 3. PARSEADOR INTELIGENTE (ADAPTADO A TU JSON) ---
def normalizar_datos(data):
    """
    Recibe el JSON y busca 'prediction', 'confidence_score', etc.
    Soporta tu formato nuevo (raíz) y el viejo (anidado).
    """
    # 1. CASO DIRECTO (Tu formato actual)
    if 'prediction' in data:
        return data # Ya es el objeto correcto
        
    # 2. CASO VIEJO (JSONprompt -> aiResponse)
    if 'JSONprompt' in data and 'aiResponse' in data['JSONprompt']:
        raw = data['JSONprompt']['aiResponse']
        if isinstance(raw, str):
            # Limpiar markdown si viene como string
            clean = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        return raw
        
    return None

# --- 4. SERVIDOR WEB + KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "🤖 Bot Online"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def ping_loop():
    while True:
        time.sleep(840)
        try: requests.get(f"{URL_API_VALERY}/ping", timeout=5)
        except: pass
        try: requests.get(URL_PROPIA_DEL_BOT, timeout=5)
        except: pass
def keep_alive():
    Thread(target=run_web).start()
    Thread(target=ping_loop).start()

# --- 5. INTERFAZ ---
def botones():
    m = InlineKeyboardMarkup(row_width=3)
    b = [InlineKeyboardButton(c, callback_data=f"a_{c}") for c in ["BTC", "ETH", "SOL", "RAY", "XRP", "SUI"]]
    m.add(*b)
    return m

def btn_pago():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💎 Recargar 10 Créditos", callback_data="buy"))
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
        bot.send_message(uid, "🎉 Créditos recargados.", reply_markup=botones())
        return

    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin saldo", show_alert=True)
            bot.send_message(uid, "⚠️ Sin créditos. Recarga:", reply_markup=btn_pago())
            return

        try:
            bot.answer_callback_query(call.id, f"Analizando {coin}...")
            deduct_credit(uid)
            
            # Request
            r = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
            
            if r.status_code == 200:
                raw_json = r.json()
                
                # USAMOS EL NORMALIZADOR NUEVO
                ai_data = normalizar_datos(raw_json)

                if ai_data and 'prediction' in ai_data:
                    # Extraer datos con seguridad (.get)
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
                    # Si falla, devolvemos el crédito y mostramos lo que llegó para debug
                    add_credits(uid, 1)
                    bot.send_message(uid, f"⚠️ Estructura desconocida.\nRecibido: `{str(raw_json)[:300]}`", parse_mode="Markdown")
            else:
                add_credits(uid, 1)
                bot.send_message(uid, f"⚠️ Error API: {r.status_code}")

        except Exception as e:
            add_credits(uid, 1)
            bot.send_message(uid, f"❌ Error: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
