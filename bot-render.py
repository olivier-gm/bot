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

# --- 3. PARSEADOR BLINDADO (AQUÍ ESTÁ EL ARREGLO) ---
def normalizar_datos(data):
    """
    Convierte cualquier cosa que parezca JSON en un Diccionario de Python real.
    Evita el error 'str object has no attribute get'.
    """
    # 1. Si ya es un String, intentamos convertirlo a Diccionario sí o sí
    if isinstance(data, str):
        try:
            # Limpiamos basura markdown
            clean = data.replace("```json", "").replace("```", "").strip()
            return json.loads(clean) # Convertimos texto -> dict
        except:
            # Si falla json.loads, intentamos regex por si hay basura alrededor
            try:
                match = re.search(r'\{.*\}', data, re.DOTALL)
                if match: return json.loads(match.group())
            except:
                return None # No se pudo salvar

    # 2. Si ya es un Diccionario (Dict)
    if isinstance(data, dict):
        # Opción A: Es el formato nuevo directo
        if 'prediction' in data:
            return data
            
        # Opción B: Formato viejo (anidado)
        if 'JSONprompt' in data:
            return normalizar_datos(data['JSONprompt']) # Recursividad
            
        if 'aiResponse' in data:
            return normalizar_datos(data['aiResponse']) # Recursividad

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
            bot.send_message(uid, "⚠️ Sin créditos.", reply_markup=btn_pago())
            return

        try:
            bot.answer_callback_query(call.id, f"Analizando {coin}...")
            deduct_credit(uid)
            
            # Request
            r = requests.get(f"{URL_API_VALERY}/ask?crypto={coin}", timeout=90)
            
            if r.status_code == 200:
                # OJO: r.json() a veces devuelve un STRING si la API hizo un doble stringify
                raw_data = r.json() 
                
                # Pasamos por el normalizador blindado
                ai_data = normalizar_datos(raw_data)

                # Verificamos que sea un DICCIONARIO antes de usar .get()
                if ai_data and isinstance(ai_data, dict) and 'prediction' in ai_data:
                    
                    pred = ai_data.get('prediction', {})
                    # Si 'prediction' también vino como string (raro pero posible), lo arreglamos
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
                    # Si falla, devolvemos el crédito
                    add_credits(uid, 1)
                    debug_info = str(raw_data)[:300]
                    bot.send_message(uid, f"⚠️ Error de formato IA. Crédito devuelto.\n`{debug_info}`", parse_mode="Markdown")
            else:
                add_credits(uid, 1)
                bot.send_message(uid, f"⚠️ Error API: {r.status_code}")

        except Exception as e:
            add_credits(uid, 1)
            bot.send_message(uid, f"❌ Error Bot: {e}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
