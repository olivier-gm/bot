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
ADMIN_ID = 1183118456 
ADMIN_ID = 1183118456 

# --- SISTEMA DE TRADUCCIÓN ---
TRANSLATIONS = {
    'es': {
        'welcome': "🤖 **Valery AI**\n💰 Créditos: {credits}\n\nSelecciona una criptomoneda para **proyectar su comportamiento** en las **próximas 1 a 3 horas**:",
        'wait_btn': "⏳ {coin} ({min}m)",
        'buy_btn': "⭐ 30 Créditos (100 Estrellas)",
        'wait_alert': "⚠️ Predicción vigente.\nEspera 1 hora para nuevos datos.",
        'admin_load': "✅ Admin Recargado",
        'invoice_title': "Paquete 30 Créditos",
        'invoice_desc': "Recarga estándar.",
        'no_balance_alert': "🚫 Sin saldo",
        'no_balance_msg': "⚠️ **Sin créditos.**",
        'cooldown_alert': "⏳ Espera un poco más.",
        'analyzing': "⏳ **Analizando {coin}...**\n\n📡 Conectando con red neuronal...\n🧠 Procesando datos de mercado...\n\n_Por favor espera, esto toma unos segundos._",
        'server_busy': "⚠️ Servidor saturado. Intenta en 1 min.",
        'retry_menu': "Intenta de nuevo:",
        'bullish': "🟢 ALCISTA",
        'bearish': "🔴 BAJISTA",
        'analysis_result': "📊 **Análisis {coin}**\n🔮 {trend}\n📈 {up}% | 📉 {down}%\n\n🧠 _{reason}_\n\n💰 Créditos: {credits}",
        'analyze_another': "🔎 **¿Analizar otra criptomoneda?**\n_Nota: Esta predicción tiene una vigencia estimada de 1 a 3 horas._",
        'error_format': "⚠️ Error formato IA. Crédito devuelto.",
        'error_api': "⚠️ Error API: {code}",
        'rebooting': "⚠️ **Servidor reiniciándose.**\nIntentando reconexión...",
        'error_generic': "❌ Error: {error}",
        'payment_success': "✅ **¡Pago Recibido!**\n\nSe han añadido **30 créditos** a tu cuenta.\n💰 Total: {amount} Estrellas\nCréditos actuales: {credits}"
    },
    'en': {
        'welcome': "🤖 **Valery AI**\n💰 Credits: {credits}\n\nSelect a cryptocurrency to **project its behavior** for the **next 1 to 3 hours**:",
        'wait_btn': "⏳ {coin} ({min}m)",
        'buy_btn': "⭐ 30 Credits (100 Stars)",
        'wait_alert': "⚠️ Prediction active.\nPlease wait 1 hour for new data.",
        'admin_load': "✅ Admin Recharged",
        'invoice_title': "30 Credits Pack",
        'invoice_desc': "Standard top-up.",
        'no_balance_alert': "🚫 No balance",
        'no_balance_msg': "⚠️ **No credits left.**",
        'cooldown_alert': "⏳ Please wait a bit more.",
        'analyzing': "⏳ **Analyzing {coin}...**\n\n📡 Connecting to neural network...\n🧠 Processing market data...\n\n_Please wait, this takes a few seconds._",
        'server_busy': "⚠️ Server busy. Try again in 1 min.",
        'retry_menu': "Try again:",
        'bullish': "🟢 BULLISH",
        'bearish': "🔴 BEARISH",
        'analysis_result': "📊 **{coin} Analysis**\n🔮 {trend}\n📈 {up}% | 📉 {down}%\n\n🧠 _{reason}_\n\n💰 Credits: {credits}",
        'analyze_another': "🔎 **Analyze another crypto?**\n_Note: This prediction is valid for approx 1 to 3 hours._",
        'error_format': "⚠️ AI format error. Credit returned.",
        'error_api': "⚠️ API Error: {code}",
        'rebooting': "⚠️ **Server rebooting.**\nAttempting reconnection...",
        'error_generic': "❌ Error: {error}",
        'payment_success': "✅ **Payment Received!**\n\n**30 credits** have been added to your account.\n💰 Total: {amount} Stars\nCurrent credits: {credits}"
    },
    'pt': {
        'welcome': "🤖 **Valery AI**\n💰 Créditos: {credits}\n\nSelecione uma criptomoeda para **projetar seu comportamento** nas **próximas 1 a 3 horas**:",
        'wait_btn': "⏳ {coin} ({min}m)",
        'buy_btn': "⭐ 30 Créditos (100 Estrelas)",
        'wait_alert': "⚠️ Previsão ativa.\nAguarde 1 hora para novos dados.",
        'admin_load': "✅ Admin Recarregado",
        'invoice_title': "Pacote 30 Créditos",
        'invoice_desc': "Recarga padrão.",
        'no_balance_alert': "🚫 Sem saldo",
        'no_balance_msg': "⚠️ **Sem créditos.**",
        'cooldown_alert': "⏳ Aguarde mais um pouco.",
        'analyzing': "⏳ **Analisando {coin}...**\n\n📡 Conectando à rede neural...\n🧠 Processando dados de mercado...\n\n_Por favor aguarde, isso leva alguns segundos._",
        'server_busy': "⚠️ Servidor ocupado. Tente em 1 min.",
        'retry_menu': "Tente novamente:",
        'bullish': "🟢 ALTA (BULLISH)",
        'bearish': "🔴 BAIXA (BEARISH)",
        'analysis_result': "📊 **Análise {coin}**\n🔮 {trend}\n📈 {up}% | 📉 {down}%\n\n🧠 _{reason}_\n\n💰 Créditos: {credits}",
        'analyze_another': "🔎 **Analisar outra cripto?**\n_Nota: Esta previsão é válida por aprox. 1 a 3 horas._",
        'error_format': "⚠️ Erro no formato da IA. Crédito devolvido.",
        'error_api': "⚠️ Erro API: {code}",
        'rebooting': "⚠️ **Servidor reiniciando.**\nTentando reconexão...",
        'error_generic': "❌ Erro: {error}",
        'payment_success': "✅ **Pagamento Recebido!**\n\n**30 créditos** foram adicionados à sua conta.\n💰 Total: {amount} Estrelas\nCréditos atuais: {credits}"
    }
}

def get_msg(lang_code, key, **kwargs):
    # Normalizar idioma (ej: 'es-ES' -> 'es')
    lang = lang_code.split('-')[0] if lang_code else 'en'
    if lang not in TRANSLATIONS:
        lang = 'en' # Fallback a español si no es en/pt
    return TRANSLATIONS[lang].get(key, "Text missing").format(**kwargs)

# --- GESTIÓN DE COOLDOWN (ENFRIAMIENTO) ---
USER_COOLDOWNS = {}
TIEMPO_ESPERA = 3600  

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
CREDITOS_INICIALES = 5

# --- 2. BASE DE DATOS ---
def get_user_credits(user_id):
    try:
        r = supabase.table('users').select("credits").eq("user_id", user_id).execute()
        if not r.data:
            supabase.table('users').insert({"user_id": user_id, "credits": CREDITOS_INICIALES}).execute()
            return CREDITOS_INICIALES
        return r.data[0]['credits']
    except: return 5 

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
# Modificado para aceptar idioma
def botones(user_id, lang_code='es'):
    m = InlineKeyboardMarkup(row_width=3)
    coins = ["BTC", "ETH", "XRP", "SOL", "LTC", "RAY"]
    btns = []
    
    now = time.time()
    user_times = USER_COOLDOWNS.get(user_id, {})

    for c in coins:
        unlock_time = user_times.get(c, 0)
        
        if now < unlock_time:
            minutes_left = int((unlock_time - now) / 60)
            # Traducción del botón de espera
            txt = get_msg(lang_code, 'wait_btn', coin=c, min=minutes_left)
            btns.append(InlineKeyboardButton(txt, callback_data=f"wait_{c}"))
        else:
            btns.append(InlineKeyboardButton(c, callback_data=f"a_{c}"))
            
    m.add(*btns)
    return m

# Modificado para aceptar idioma
def btn_pago(lang_code='es'):
    m = InlineKeyboardMarkup(row_width=1)
    txt = get_msg(lang_code, 'buy_btn')
    m.add(InlineKeyboardButton(txt, callback_data="buy_30"))
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    c = get_user_credits(msg.chat.id)
    # Detectar idioma
    lang = msg.from_user.language_code
    
    bot.reply_to(
            msg, 
            get_msg(lang, 'welcome', credits=c), 
            reply_markup=botones(msg.chat.id, lang), 
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['test_pay'])
def simular_pago(msg):
    if msg.chat.id != ADMIN_ID: return 
    add_credits(msg.chat.id, 30)
    # Este mensaje es solo para admin, lo dejo hardcodeado o puedes traducirlo
    bot.send_message(msg.chat.id, "✅ Simulacion OK", parse_mode="Markdown")

# --- 6. CALLBACKS Y PAGOS ---
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    uid = call.message.chat.id
    mid = call.message.message_id
    data = call.data
    # Detectar idioma del usuario que hizo clic
    lang = call.from_user.language_code

    # --- INFORMACIÓN DE ESPERA ---
    if data.startswith("wait_"):
        bot.answer_callback_query(call.id, get_msg(lang, 'wait_alert'), show_alert=True)
        return

    # --- PAGO ---
    if data == "buy_30":
        if uid == ADMIN_ID:
            add_credits(uid, 30)
            bot.answer_callback_query(call.id, get_msg(lang, 'admin_load'))
            return

        bot.send_invoice(uid, 
                         get_msg(lang, 'invoice_title'), 
                         get_msg(lang, 'invoice_desc'), 
                         "30_credits_pack", 
                         PAYMENT_TOKEN, "XTR", [LabeledPrice("30 Credits", 100)])
        return

    # --- LÓGICA DE ANÁLISIS ---
    if data.startswith("a_"):
        coin = data.split("_")[1]
        
        # 1. Verificar Créditos
        if get_user_credits(uid) <= 0:
            bot.answer_callback_query(call.id, get_msg(lang, 'no_balance_alert'), show_alert=True)
            bot.send_message(uid, get_msg(lang, 'no_balance_msg'), reply_markup=btn_pago(lang), parse_mode="Markdown")
            return

        # 2. Verificar Cooldown
        now = time.time()
        unlock_time = USER_COOLDOWNS.get(uid, {}).get(coin, 0)
        if now < unlock_time:
            bot.answer_callback_query(call.id, get_msg(lang, 'cooldown_alert'), show_alert=True)
            return

        # --- UX: PANTALLA DE CARGA ---
        bot.edit_message_text(
            chat_id=uid, 
            message_id=mid, 
            text=get_msg(lang, 'analyzing', coin=coin), 
            parse_mode="Markdown",
            reply_markup=None 
        )
        
        bot.send_chat_action(uid, 'typing')

        def procesar_peticion():
            acquired = False
            try:
                acquired = backend_lock.acquire(blocking=True, timeout=100) 
                if not acquired:
                    bot.send_message(uid, get_msg(lang, 'server_busy'))
                    bot.send_message(uid, get_msg(lang, 'retry_menu'), reply_markup=botones(uid, lang))
                    return

                deduct_credit(uid)
                
                # Petición al Backend
                r = http.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
                
                if r.status_code == 200:
                    raw_data = r.json() 
                    ai_data = normalizar_datos(raw_data)
                    
                    if ai_data and isinstance(ai_data, dict) and 'prediction' in ai_data:
                        pred = ai_data.get('prediction', {})
                        # Nota: La 'razon' viene del backend. Si el backend no soporta idioma,
                        # vendrá en el idioma original de la IA (probablemente español o inglés).
                        razon = ai_data.get('rationale', 'Sin detalle.')
                        if isinstance(pred, str): pred = json.loads(pred)
                        
                        tendencia = get_msg(lang, 'bullish') if pred.get('subida', 0) > pred.get('bajada', 0) else get_msg(lang, 'bearish')
                        
                        msg = get_msg(lang, 'analysis_result', 
                                      coin=coin, 
                                      trend=tendencia, 
                                      up=pred.get('subida'), 
                                      down=pred.get('bajada'), 
                                      reason=razon, 
                                      credits=get_user_credits(uid))
                        
                        bot.send_message(uid, msg, parse_mode="Markdown")
                        
                        # --- GUARDAR COOLDOWN ---
                        if uid not in USER_COOLDOWNS: USER_COOLDOWNS[uid] = {}
                        USER_COOLDOWNS[uid][coin] = time.time() + TIEMPO_ESPERA
                        
                        time.sleep(1) 
                        
                        bot.send_message(
                            uid, 
                            get_msg(lang, 'analyze_another'), 
                            reply_markup=botones(uid, lang), 
                            parse_mode="Markdown"
                        )
                    else:
                        add_credits(uid, 1)
                        bot.send_message(uid, get_msg(lang, 'error_format'), reply_markup=botones(uid, lang))
                else:
                    add_credits(uid, 1)
                    bot.send_message(uid, get_msg(lang, 'error_api', code=r.status_code), reply_markup=botones(uid, lang))

            except Exception as e:
                add_credits(uid, 1)
                if "Connection refused" in str(e) or "Max retries" in str(e):
                    bot.send_message(uid, get_msg(lang, 'rebooting'), reply_markup=botones(uid, lang))
                else:
                    bot.send_message(uid, get_msg(lang, 'error_generic', error=e), reply_markup=botones(uid, lang))
            
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
    lang = message.from_user.language_code
    payment_info = message.successful_payment
    
    if payment_info.invoice_payload == "30_credits_pack":
        add_credits(uid, 30)
        bot.send_message(uid, 
                         get_msg(lang, 'payment_success', amount=payment_info.total_amount, credits=get_user_credits(uid)),
                         parse_mode="Markdown",
                         reply_markup=botones(uid, lang))

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()

