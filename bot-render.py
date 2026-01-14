# coding: utf-8
import telebot
import requests
import json
import os
import time
import re  # <--- NUEVO: Para limpiar la respuesta de la IA con Regex
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
TOKEN = '8556444811:AAF0m841XRL-35xSX6g5DNyr-DWoml0JYNA' 
URL_API_VALERY = 'http://167.86.80.129:3000' 
URL_PROPIA_DEL_BOT = "https://bot-sol7.onrender.com" 

# --- CONFIGURACIÓN SUPABASE ---
# En Render, es mejor poner esto en "Environment Variables", pero puedes pegarlo aquí para probar.
SUPABASE_URL = "https://aodhfcpabmjvyusrohjh.supabase.co" 
SUPABASE_KEY = "sb_publishable_4_8oRB_GIlwr1f1EskKn0A_YY0uMJPI"

# Inicializamos el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CREDITOS_INICIALES = 3
PRECIO_PAQUETE = "5 USDT"

bot = telebot.TeleBot(TOKEN)

# --- HELPER: LIMPIEZA DE JSON ---
def parsear_respuesta_ia(texto_sucio):
    """
    Intenta extraer y convertir el JSON incluso si la IA manda texto extra
    o bloques de código Markdown (```json ... ```).
    """
    if not isinstance(texto_sucio, str):
        return texto_sucio # Ya es un objeto, lo devolvemos tal cual
    
    try:
        # 1. Intento directo
        return json.loads(texto_sucio)
    except:
        pass

    try:
        # 2. Limpieza de Markdown (```json ... ```)
        limpio = texto_sucio.replace("```json", "").replace("```", "").strip()
        return json.loads(limpio)
    except:
        pass

    try:
        # 3. Búsqueda con Regex (Busca el primer '{' y el último '}')
        match = re.search(r'\{.*\}', texto_sucio, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    
    # Si todo falla, lanzamos error para devolver el crédito
    raise ValueError(f"No se pudo parsear JSON: {texto_sucio[:50]}...")

# --- 2. GESTIÓN DE BASE DE DATOS ---

def get_user_credits(user_id):
    try:
        response = supabase.table('users').select("credits").eq("user_id", user_id).execute()
        if not response.data:
            supabase.table('users').insert({"user_id": user_id, "credits": CREDITOS_INICIALES}).execute()
            return CREDITOS_INICIALES
        return response.data[0]['credits']
    except Exception as e:
        print(f"❌ Error Supabase (Get): {e}")
        return 0

def deduct_credit(user_id):
    try:
        current = get_user_credits(user_id)
        if current > 0:
            supabase.table('users').update({"credits": current - 1}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"❌ Error Supabase (Deduct): {e}")

def add_credits(user_id, amount):
    try:
        current = get_user_credits(user_id)
        supabase.table('users').update({"credits": current + amount}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"❌ Error Supabase (Add): {e}")

# --- 3. SERVIDOR WEB + KEEP ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot Activo v2.0"

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
    t_server = Thread(target=run_web)
    t_server.start()
    t_ping = Thread(target=ping_services)
    t_ping.start()

# --- 4. BOTONES ---
COINS = ["BTC", "ETH", "SOL", "RAY", "XRP", "SUI"]

def generar_botones_monedas():
    markup = InlineKeyboardMarkup()
    markup.row_width = 3
    botones = []
    for coin in COINS:
        botones.append(InlineKeyboardButton(coin, callback_data=f"analyze_{coin}"))
    markup.add(*botones)
    return markup

def generar_boton_pago():
    markup = InlineKeyboardMarkup()
    btn_pagar = InlineKeyboardButton(f"💎 Comprar 10 Créditos ({PRECIO_PAQUETE})", callback_data="buy_pack")
    markup.add(btn_pagar)
    return markup

# --- 5. COMANDOS ---

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    uid = message.chat.id
    creditos = get_user_credits(uid)
    texto = f"🤖 **Crypto Analizador AI**\n👤 ID: `{uid}`\n💰 Créditos: **{creditos}**\n\nElige una moneda:"
    bot.reply_to(message, texto, reply_markup=generar_botones_monedas(), parse_mode="Markdown")

@bot.message_handler(commands=['saldo', 'comprar'])
def check_balance(message):
    uid = message.chat.id
    creditos = get_user_credits(uid)
    bot.reply_to(message, f"💰 Tienes **{creditos}** créditos.\n¿Recargar?", reply_markup=generar_boton_pago(), parse_mode="Markdown")

# --- 6. HANDLER PRINCIPAL ---

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = call.message.chat.id
    data = call.data

    if data == "buy_pack":
        add_credits(uid, 10)
        bot.answer_callback_query(call.id, "✅ +10 Créditos")
        bot.send_message(uid, "🎉 **¡Recarga exitosa!**", reply_markup=generar_botones_monedas(), parse_mode="Markdown")
        return

    if data.startswith("analyze_"):
        coin = data.split("_")[1]
        
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin créditos", show_alert=True)
            bot.send_message(uid, "⚠️ **Sin créditos.** Recarga para continuar.", reply_markup=generar_boton_pago(), parse_mode="Markdown")
            return

        try:
            bot.answer_callback_query(call.id, f"Analizando {coin}...")
            deduct_credit(uid) # Cobramos
            
            # Request a tu API
            # IMPORTANTE: Asegúrate que tu API http://167.86.80.129:3000 es accesible desde Render
            response = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90) # Aumenté timeout a 90s por si acaso
            
            if response.status_code == 200:
                data_json = response.json()
                
                # --- DEBUG LOGGING ---
                # Si falla, mira los logs de Render, ahí saldrá qué respondió la API
                print(f"DEBUG {coin}: {str(data_json)[:200]}...") 

                if 'JSONprompt' in data_json and data_json['JSONprompt'].get('aiResponse'):
                    # USAMOS LA NUEVA FUNCIÓN DE LIMPIEZA AQUÍ
                    raw_ai = data_json['JSONprompt']['aiResponse']
                    ai_data = parsear_respuesta_ia(raw_ai)

                    pred = ai_data.get('prediction', {})
                    subida = pred.get('subida', 0)
                    bajada = pred.get('bajada', 0)
                    score = ai_data.get('confidence_score', 0)
                    razon = ai_data.get('rationale', 'Sin razón disponible.')
                    tendencia = "🟢 ALCISTA" if subida > bajada else "🔴 BAJISTA"
                    
                    saldo_restante = get_user_credits(uid)
                    
                    mensaje = (
                        f"📊 **Análisis {coin}**\n"
                        f"🔮 **Predicción:** {tendencia}\n"
                        f"📈 Subida: {subida}% | 📉 Bajada: {bajada}%\n"
                        f"🎯 Confianza: {score}/10\n\n"
                        f"🧠 _{razon}_\n\n"
                        f"💰 _Créditos: {saldo_restante}_"
                    )
                    bot.send_message(call.message.chat.id, mensaje, parse_mode="Markdown")
                    
                    time.sleep(1)
                    bot.send_message(call.message.chat.id, "¿Otra moneda?", reply_markup=generar_botones_monedas())
                else:
                    raise ValueError("Estructura JSONprompt incorrecta o aiResponse vacío")
            else:
                raise ConnectionError(f"Status {response.status_code}")

        except Exception as e:
            print(f"❌ ERROR FATAL en {coin}: {e}")
            add_credits(uid, 1) # Devolvemos crédito
            bot.send_message(call.message.chat.id, f"⚠️ Error en el análisis. Crédito devuelto.\nInfo: {str(e)[:50]}")

# --- ARRANQUE ---
if __name__ == "__main__":
    keep_alive()
    # restart_on_change=True a veces ayuda si el script se congela
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
