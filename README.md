# Bot de Telegram para análisis cripto

Bot de Telegram escrito en Python que responde con análisis de criptomonedas, maneja créditos por usuario, aplica cooldown por moneda y procesa pagos con Telegram Stars. También incluye una estrategia de `keep_alive` pensada para evitar que un servicio gratuito de Render se suspenda por inactividad.

## Funcionalidades

- Comando `/start` con saludo multilenguaje.
- Botones para analizar BTC, ETH, XRP, SOL, LTC y ASTER.
- Sistema de créditos por usuario almacenado en Supabase.
- Cooldown de 1 hora por criptomoneda para usuarios normales.
- Soporte de pago con Telegram Stars para recargar créditos.
- Manejo de errores con reintentos HTTP.
- Endpoint web mínimo para mantener el proceso activo en Render.

## Cómo funciona `keep_alive`

El archivo `bot-render.py` levanta un pequeño servidor Flask con una ruta `/` que devuelve una respuesta simple. Además, inicia un hilo en segundo plano que hace ping cada 14 minutos a dos destinos:

- La URL pública del propio bot en Render.
- El backend externo que responde a las consultas de análisis.

Esto ayuda a que el plan gratuito de Render no entre en reposo por falta de tráfico. En la práctica, la idea es simple: mientras el proceso reciba tráfico periódico, Render lo mantiene despierto.

Importante: esto no elimina todas las causas posibles de caída, pero sí evita el problema más común del free tier, que es el “sleep” por inactividad.

## Requisitos

- Python 3.10 o superior.
- Un bot creado con BotFather.
- Una base de datos Supabase accesible desde el script.
- Un servicio en Render configurado como Web Service si quieres usar `keep_alive`.

## Variables de entorno

Configura al menos estas variables:

- `TELEGRAM_TOKEN`: token del bot de Telegram.
- `PORT`: puerto que usará Flask en Render. Normalmente Render lo define solo.

Si vas a adaptar el proyecto, también conviene mover a variables de entorno cualquier URL o clave sensible que hoy esté fija en el código.

## Instalación local

```bash
pip install -r requirements.txt
```

## Ejecución local

```bash
python bot-render.py
```

El bot arrancará el servidor web auxiliar y después comenzará el polling de Telegram.

## Despliegue en Render

1. Crea un nuevo Web Service en Render.
2. Conecta este repositorio.
3. Define `TELEGRAM_TOKEN` en las variables de entorno.
4. Usa un comando de arranque que ejecute el script principal, por ejemplo:

```bash
python bot-render.py
```

5. Verifica que la URL pública del servicio coincida con la que se usa dentro del script para el `keep_alive`.

## Estructura del proyecto

- `bot-render.py`: lógica principal del bot, el servidor Flask y el `keep_alive`.
- `requirements.txt`: dependencias del proyecto.

## Notas

- El bot usa Supabase para persistir usuarios y créditos.
- El cooldown se maneja en memoria, así que se reinicia si el proceso se cae o Render lo reinicia.
- Si vas a cambiar la URL pública del servicio, actualiza también la constante correspondiente en el script para que el ping apunte al lugar correcto.