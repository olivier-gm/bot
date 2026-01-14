# coding: utf-8
import telebot
import requests
import json
import os
import time
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
SUPABASE_URL = "aws-0-us-west-2.pooler.supabase.com" 
SUPABASE_KEY = "WEARECHARLIEKIRK27283922**"

# Inicializamos el cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CREDITOS_INICIALES = 3
PRECIO_PAQUETE = "5 USDT"

bot = telebot.TeleBot(TOKEN)

# --- 2. GESTIÓN DE BASE DE DATOS (SUPABASE) ---

def get_user_credits(user_id):
    """Obtiene los créditos desde Supabase o crea el usuario si no existe"""
    try:
        # 1. Consultamos si existe el usuario
        response = supabase.table('users').select("credits").eq("user_id", user_id).execute()
        
        # 2. Si la lista 'data' está vacía, el usuario es nuevo
        if not response.data:
            # Lo creamos con los créditos iniciales
            print(f"Usuario nuevo {user_id}, creando registro...")
            supabase.table('users').insert({
                "user_id": user_id, 
                "credits": CREDITOS_INICIALES
            }).execute()
            return CREDITOS_INICIALES
        
        # 3. Si existe, devolvemos sus créditos
        return response.data[0]['credits']
    
    except Exception as e:
        print(f"❌ Error Supabase (Get): {e}")
        return 0 # En caso de error, asumimos 0 por seguridad

def deduct_credit(user_id):
    """Resta 1 crédito al usuario"""
    try:
        # Primero obtenemos el saldo actual
        current = get_user_credits(user_id)
        if current > 0:
            new_balance = current - 1
            supabase.table('users').update({"credits": new_balance}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"❌ Error Supabase (Deduct): {e}")

def add_credits(user_id, amount):
    """Recarga créditos"""
    try:
        current = get_user_credits(user_id)
        new_balance = current + amount
        supabase.table('users').update({"credits": new_balance}).eq("user_id", user_id).execute()
    except Exception as e:
        print(f"❌ Error Supabase (Add): {e}")

# --- 3. SERVIDOR WEB + KEEP ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot Conectado a Supabase OK."

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def ping_services():
    while True:
        time.sleep(840) 
        print("⏰ Keep-Alive cycle...")
        try:
            requests.get(f"{URL_API_VALERY}/ping", timeout=10)
        except: pass
        try:
            if URL_PROPIA_DEL_BOT.startswith("http"):
                requests.get(URL_PROPIA_DEL_BOT, timeout=10)
        except: pass

def keep_alive():
    t_server = Thread(target=run_web)
    t_server.start()
    t_ping = Thread(target=ping_services)
    t_ping.start()

# --- 4. INTERFAZ Y BOTONES ---
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

# --- 5. COMANDOS PRINCIPALES ---

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    uid = message.chat.id
    creditos = get_user_credits(uid)
    
    texto = (
        f"🤖 **Crypto Analizador AI**\n"
        f"👤 ID: `{uid}`\n"
        f"💰 Tus Créditos: **{creditos}**\n\n"
        f"Elige una moneda para analizar (Costo: 1 crédito):"
    )
    bot.reply_to(message, texto, reply_markup=generar_botones_monedas(), parse_mode="Markdown")

@bot.message_handler(commands=['saldo', 'comprar'])
def check_balance(message):
    uid = message.chat.id
    creditos = get_user_credits(uid)
    bot.reply_to(message, f"💰 Tienes **{creditos}** créditos disponibles.\n\n¿Deseas recargar?", 
                 reply_markup=generar_boton_pago(), parse_mode="Markdown")

# --- 6. MANEJO DE CALLBACKS ---

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    uid = call.message.chat.id
    data = call.data

    if data == "buy_pack":
        add_credits(uid, 10)
        bot.answer_callback_query(call.id, "✅ ¡Pago exitoso! +10 Créditos")
        bot.send_message(uid, "🎉 **¡Recarga exitosa!**\nAhora tienes más créditos.", 
                         reply_markup=generar_botones_monedas(), parse_mode="Markdown")
        return

    if data.startswith("analyze_"):
        coin = data.split("_")[1] 
        
        creditos = get_user_credits(uid)
        
        if creditos <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin créditos", show_alert=True)
            bot.send_message(uid, "⚠️ **Te has quedado sin créditos.**\nRecarga para continuar.", 
                             reply_markup=generar_boton_pago(), parse_mode="Markdown")
            return

        try:
            bot.answer_callback_query(call.id, f"Consultando {coin} (-1 crédito)...")
            
            # Descontamos crédito
            deduct_credit(uid)
            
            response = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=60)
            
            if response.status_code == 200:
                data_json = response.json()
                if 'JSONprompt' in data_json and data_json['JSONprompt'].get('aiResponse'):
                    raw_ai = data_json['JSONprompt']['aiResponse']
                    ai_data = json.loads(raw_ai) if isinstance(raw_ai, str) else raw_ai

                    pred = ai_data.get('prediction', {})
                    subida = pred.get('subida', 0)
                    bajada = pred.get('bajada', 0)
                    score = ai_data.get('confidence_score', 0)
                    razon = ai_data.get('rationale', '...')
                    tendencia = "🟢 ALCISTA" if subida > bajada else "🔴 BAJISTA"
                    
                    saldo_restante = get_user_credits(uid)
                    
                    mensaje = (
                        f"📊 **Análisis {coin}**\n"
                        f"🔮 **Predicción:** {tendencia}\n"
                        f"📈 Subida: {subida}% | 📉 Bajada: {bajada}%\n"
                        f"🎯 Confianza: {score}/10\n\n"
                        f"🧠 _{razon}_\n\n"
                        f"💰 _Créditos restantes: {saldo_restante}_"
                    )
                    bot.send_message(call.message.chat.id, mensaje, parse_mode="Markdown")
                    
                    # Restauramos el menú
                    time.sleep(1)
                    bot.send_message(call.message.chat.id, "¿Consultar otra moneda?", 
                                     reply_markup=generar_botones_monedas())
                else:
                    add_credits(uid, 1) # Devolver crédito
                    bot.send_message(call.message.chat.id, "⚠️ La IA no respondió correctamente. Crédito devuelto.")
            else:
                add_credits(uid, 1) # Devolver crédito
                bot.send_message(call.message.chat.id, "⚠️ Error del servidor. Crédito devuelto.")

        except Exception as e:
            print(f"ERROR: {e}")
            add_credits(uid, 1)
            bot.send_message(call.message.chat.id, "❌ Error interno. Crédito devuelto.")

# --- 7. ARRANQUE ---
if __name__ == "__main__":
    keep_alive() 
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
