import telebot
import requests
import json
import os
import time
import re
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from flask import Flask
from threading import Thread, Semaphore
from supabase import create_client, Client
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# --- 1. CONFIGURACIÓN ---
TOKEN = '8556444811:AAF0m841XRL-35xSX6g5DNyr-DWoml0JYNA'
PAYMENT_TOKEN = "" 
URL_API_VALERY = 'http://167.86.80.129:3000' 
URL_PROPIA_DEL_BOT = "https://bot-sol7.onrender.com"
ADMIN_ID = 1183118456 # id de admin para saltarse el metodo de pago
ADMIN_ID = 1183118456 # id random para eliminar acceso admin temporalmente


# --- GESTIÓN DE COOLDOWN (ENFRIAMIENTO) ---
# Estructura: { user_id: { 'BTC': tiempo_desbloqueo, 'ETH': tiempo_desbloqueo } }
USER_COOLDOWNS = {}
TIEMPO_ESPERA = 3600  # 1 hora en segundos

# --- CONFIGURACIÓN DE SEGURIDAD Y COLAS ---
backend_lock = Semaphore(1) 

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("http://", adapter)
http.mount("https://", adapter)

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
        if 'prediction' in data: return data
        if 'JSONprompt' in data: return normalizar_datos(data['JSONprompt'])
        if 'aiResponse' in data: return normalizar_datos(data['aiResponse'])
    return None

# --- 4. SERVIDOR WEB ---
app = Flask('')
@app.route('/')
def home(): return "🤖 Bot Fix Online"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def ping_loop():
    while True:
        time.sleep(840)
        try: http.get(f"{URL_API_VALERY}/ping", timeout=5)
        except: pass
        try: http.get(URL_PROPIA_DEL_BOT, timeout=5)
        except: pass
def keep_alive():
    Thread(target=run_web).start()
    Thread(target=ping_loop).start()

# --- 5. INTERFAZ DINÁMICA (COOLDOWN) ---
def botones(user_id):
    m = InlineKeyboardMarkup(row_width=3)
    coins = ["BTC", "ETH", "XRP", "SOL", "LTC", "RAY"]
    btns = []
    
    now = time.time()
    user_times = USER_COOLDOWNS.get(user_id, {})

    for c in coins:
        unlock_time = user_times.get(c, 0)
        
        # Si aun hay tiempo de espera
        if now < unlock_time:
            minutes_left = int((unlock_time - now) / 60)
            # Botón informativo (callback nulo o de alerta)
            # Mostramos el reloj y los minutos
            btns.append(InlineKeyboardButton(f"⏳ {c} ({minutes_left}m)", callback_data=f"wait_{c}"))
        else:
            # Botón normal
            btns.append(InlineKeyboardButton(c, callback_data=f"a_{c}"))
            
    m.add(*btns)
    return m

def btn_pago():
    m = InlineKeyboardMarkup(row_width=1)
    m.add(InlineKeyboardButton("⭐ 50 Créditos (100 Estrellas)", callback_data="buy_50"))
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    c = get_user_credits(msg.chat.id)
    bot.reply_to(
            msg, 
            f"🤖 **Valery AI**\n"
            f"💰 Créditos: {c}\n\n"
            f"Selecciona una criptomoneda para **proyectar su comportamiento** en las **próximas 1 a 3 horas**:", 
            reply_markup=botones(msg.chat.id), 
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['test_pay'])
def simular_pago(msg):
    if msg.chat.id != ADMIN_ID: return 
    add_credits(msg.chat.id, 50)
    bot.send_message(msg.chat.id, "✅ Simulacion OK", parse_mode="Markdown")

# --- 6. CALLBACKS Y PAGOS ---
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    mid = call.message.message_id
    data = call.data

    # --- INFORMACIÓN DE ESPERA (Botón con reloj) ---
    if data.startswith("wait_"):
        bot.answer_callback_query(call.id, "⚠️ Predicción vigente.\nEspera 1 hora para nuevos datos.", show_alert=True)
        return

    # --- PAGO ---
    if data == "buy_50":
        if uid == ADMIN_ID:
            add_credits(uid, 50)
            bot.answer_callback_query(call.id, "✅ Admin Recargado")
            return

        bot.send_invoice(uid, "Paquete 50 Créditos", "Recarga estándar.", "50_credits_pack", 
                         PAYMENT_TOKEN, "XTR", [LabeledPrice("50 Créditos", 100)])
        return

    # --- LÓGICA DE ANÁLISIS ---
    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        # 1. Verificar Créditos
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, "🚫 Sin saldo", show_alert=True)
            bot.send_message(uid, "⚠️ **Sin créditos.**", reply_markup=btn_pago(), parse_mode="Markdown")
            return

        # 2. Verificar Cooldown (Doble seguridad por si hackean la API de telegram)
        now = time.time()
        unlock_time = USER_COOLDOWNS.get(uid, {}).get(coin, 0)
        if now < unlock_time:
            bot.answer_callback_query(call.id, "⏳ Espera un poco más.", show_alert=True)
            return

        # --- UX: PANTALLA DE CARGA ---
        # Editamos el mensaje original quitando los botones.
        # Esto impide que el usuario toque nada más.
        bot.edit_message_text(
            chat_id=uid, 
            message_id=mid, 
            text=f"⏳ **Analizando {coin}...**\n\n📡 Conectando con red neuronal...\n🧠 Procesando datos de mercado...\n\n_Por favor espera, esto toma unos segundos._", 
            parse_mode="Markdown",
            reply_markup=None # Quitamos los botones
        )
        
        # Enviamos acción de escribiendo para más realismo
        bot.send_chat_action(uid, 'typing')

        def procesar_peticion():
            acquired = False
            try:
                # Intentamos entrar a la cola (Semáforo)
                acquired = backend_lock.acquire(blocking=True, timeout=100) 
                if not acquired:
                    bot.send_message(uid, "⚠️ Servidor saturado. Intenta en 1 min.")
                    # Restauramos el menú si falla
                    bot.send_message(uid, "Intenta de nuevo:", reply_markup=botones(uid))
                    return

                deduct_credit(uid)
                
                # Petición al Backend
                r = http.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
                
                if r.status_code == 200:
                    raw_data = r.json() 
                    ai_data = normalizar_datos(raw_data)
                    
                    if ai_data and isinstance(ai_data, dict) and 'prediction' in ai_data:
                        pred = ai_data.get('prediction', {})
                        razon = ai_data.get('rationale', 'Sin detalle.')
                        if isinstance(pred, str): pred = json.loads(pred)
                        tendencia = "🟢 ALCISTA" if pred.get('subida', 0) > pred.get('bajada', 0) else "🔴 BAJISTA"
                        
                        msg = (f"📊 **Análisis {coin}**\n🔮 {tendencia}\n"
                               f"📈 {pred.get('subida')}% | 📉 {pred.get('bajada')}%\n\n"
                               f"🧠 _{razon}_\n\n"
                               f"💰 Créditos: {get_user_credits(uid)}")
                        
                        bot.send_message(uid, msg, parse_mode="Markdown")
                        
                        # --- GUARDAR COOLDOWN ---
                        # Solo si fue exitoso, bloqueamos esa moneda 1 hora
                        if uid not in USER_COOLDOWNS: USER_COOLDOWNS[uid] = {}
                        USER_COOLDOWNS[uid][coin] = time.time() + TIEMPO_ESPERA
                        
                        # Pequeña pausa
                        time.sleep(1) 
                        
                        # Enviamos el menú actualizado (con la moneda bloqueada)
                        bot.send_message(
                            uid, 
                            "🔎 **¿Analizar otra criptomoneda?**\n"
                            "_Nota: Esta predicción tiene una vigencia estimada de 1 a 3 horas._", 
                            reply_markup=botones(uid), 
                            parse_mode="Markdown"
                        )
                    else:
                        add_credits(uid, 1)
                        bot.send_message(uid, "⚠️ Error formato IA. Crédito devuelto.", reply_markup=botones(uid))
                else:
                    add_credits(uid, 1)
                    bot.send_message(uid, f"⚠️ Error API: {r.status_code}", reply_markup=botones(uid))

            except Exception as e:
                add_credits(uid, 1)
                if "Connection refused" in str(e) or "Max retries" in str(e):
                    bot.send_message(uid, "⚠️ **Servidor reiniciándose.**\nIntentando reconexión...", reply_markup=botones(uid))
                else:
                    bot.send_message(uid, f"❌ Error: {e}", reply_markup=botones(uid))
            
            finally:
                if acquired:
                    backend_lock.release()

        Thread(target=procesar_peticion).start()

# --- 7. PROCESAR EL PAGO ---
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    uid = message.chat.id
    payment_info = message.successful_payment # Corregido: definimos la variable para usarla abajo
    
    if payment_info.invoice_payload == "50_credits_pack":
        add_credits(uid, 50)
        bot.send_message(uid, 
                         f"✅ **¡Pago Recibido!**\n\n"
                         f"Se han añadido **50 créditos** a tu cuenta.\n"
                         f"💰 Total: {payment_info.total_amount} Estrellas\n"
                         f"Créditos actuales: {get_user_credits(uid)}",
                         parse_mode="Markdown",
                         reply_markup=botones(uid))

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
