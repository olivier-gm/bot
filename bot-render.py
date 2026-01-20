import telebot
import requests
import json
import os
import time
import re
# Importamos LabeledPrice para definir el precio de la factura
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from flask import Flask
from threading import Thread
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
TOKEN = '8556444811:AAF0m841XRL-35xSX6g5DNyr-DWoml0JYNA'

# Token de Ammer Pay integrado
PAYMENT_TOKEN = '6073714100:TEST:TG_VRtwi3GRe6srtlAUKl1Xk8gA'

URL_API_VALERY = 'http://167.86.80.129:3000' 
URL_PROPIA_DEL_BOT = "https://bot-sol7.onrender.com"
ADMIN_ID = 1183118456  # Tu ID para recargas gratis

# Supabase
SUPABASE_URL = "https://aodhfcpabmjvyusrohjh.supabase.co"
SUPABASE_KEY = "sb_publishable_4_8oRB_GIlwr1f1EskKn0A_YY0uMJPI"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    pass

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
    except: return 3 

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

# --- 3. PARSEADOR BLINDADO ---
def normalizar_datos(data):
    if isinstance(data, str):
        try:
            clean = data.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
            try:
                match = re.search(r'\{.*\}', data, re.DOTALL)
                if match: return json.loads(match.group())
            except:
                return None

    if isinstance(data, dict):
        if 'prediction' in data:
            return data
        if 'JSONprompt' in data:
            return normalizar_datos(data['JSONprompt'])
        if 'aiResponse' in data:
            return normalizar_datos(data['aiResponse'])
    return None

# --- 4. SERVIDOR WEB ---
app = Flask('')
@app.route('/')
def home(): return "🤖 Bot Fix Online"
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
    # Muestra el precio en USD, Ammer Pay hará la conversión a Cripto al pagar
    m.add(InlineKeyboardButton("💎 Recargar 10 Créditos ($1.99)", callback_data="buy"))
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    c = get_user_credits(msg.chat.id)
    bot.reply_to(msg, f"🤖 **Crypto AI**\n💰 Créditos: {c}\nElige:", reply_markup=botones(), parse_mode="Markdown")

# --- 6. LOGICA DE PAGOS Y CALLBACKS ---

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    data = call.data

    # --- LÓGICA DE RECARGA ---
    if data == "buy":
        # CASO 1: Admin (Tú) - Recarga Gratis
        if uid == ADMIN_ID:
            add_credits(uid, 10)
            bot.answer_callback_query(call.id, "✅ Modo Dios: Recargado Gratis")
            bot.send_message(uid, "👑 **Admin:** Te has dado 10 créditos gratis.", reply_markup=botones(), parse_mode="Markdown")
            return
        
        # CASO 2: Usuario Normal - Enviar Factura Ammer Pay
        else:
            bot.answer_callback_query(call.id, "Generando factura cripto...")
            bot.send_invoice(
                uid,
                title="Paquete de 10 Créditos",
                description="Acceso al bot de análisis Crypto AI.",
                invoice_payload="10_credits_pack", 
                provider_token=PAYMENT_TOKEN, 
                currency="USD", # Moneda base (Ammer cobrará el equivalente en cripto)
                prices=[LabeledPrice("10 Créditos", 199)], # 199 centavos = $1.99 USD
                start_parameter="create_invoice"
            )
            return

    # --- LÓGICA DEL BOT DE ANALISIS ---
    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin saldo", show_alert=True)
            bot.send_message(uid, "⚠️ **Sin créditos.**\nRecarga para continuar analizando.", reply_markup=btn_pago(), parse_mode="Markdown")
            return

        try:
            bot.answer_callback_query(call.id, f"Analizando {coin}...")
            deduct_credit(uid)
            
            # Request a tu API
            r = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
            
            if r.status_code == 200:
                raw_data = r.json() 
                ai_data = normalizar_datos(raw_data)

                if ai_data and isinstance(ai_data, dict) and 'prediction' in ai_data:
                    
                    pred = ai_data.get('prediction', {})
                    if isinstance(pred, str): pred = json.loads(pred)

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
                    add_credits(uid, 1) # Devolver crédito si falla el formato
                    debug_info = str(raw_data)[:300]
                    bot.send_message(uid, f"⚠️ Error de formato IA. Crédito devuelto.\n`{debug_info}`", parse_mode="Markdown")
            else:
                add_credits(uid, 1)
                bot.send_message(uid, f"⚠️ Error API: {r.status_code}")

        except Exception as e:
            add_credits(uid, 1)
            bot.send_message(uid, f"❌ Error Bot: {e}")

# --- 7. HANDLERS PARA PROCESAR EL PAGO ---

# A. Pre-checkout: Validar antes de cobrar
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True,
                                  error_message="Hubo un error al iniciar la transacción.")

# B. Pago Exitoso: Entregar créditos
@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.chat.id
    payment_info = message.successful_payment
    
    if payment_info.invoice_payload == "10_credits_pack":
        add_credits(uid, 10) 
        
        bot.send_message(uid, 
                         f"✅ **¡Pago Recibido!**\n\n"
                         f"Se han añadido **10 créditos** a tu cuenta.\n"
                         f"💰 Total: {payment_info.total_amount / 100} {payment_info.currency}\n"
                         f"Créditos actuales: {get_user_credits(uid)}",
                         parse_mode="Markdown",
                         reply_markup=botones())

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
