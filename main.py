import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, FileResponse
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
import requests

app = FastAPI()

# Load secrets from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Files and data
QR_IMAGE_PATH = "qr.png"
ENOTES_PATH = "enotes.zip"
TXN_IDS_FILE = "txn_ids.txt"
USED_IDS_FILE = "used_ids.txt"

# In-memory sets for transaction IDs
with open(TXN_IDS_FILE, "r") as f:
    valid_txns = set(line.strip() for line in f if line.strip())

try:
    with open(USED_IDS_FILE, "r") as f:
        used_txns = set(line.strip() for line in f if line.strip())
except FileNotFoundError:
    used_txns = set()

# /start command
def start(update, context):
    update.message.reply_text(
        "Hi! Send /unlock to get the Paytm QR code for payment."
    )

# /unlock command - sends payment QR
def unlock(update, context):
    chat_id = update.message.chat_id
    bot.send_photo(chat_id=chat_id, photo=open(QR_IMAGE_PATH, "rb"),
                   caption="Please scan this Paytm QR and pay. After payment, send me your Transaction ID.")

# After /unlock, user sends TXN ID - handle text messages
def handle_message(update, context):
    text = update.message.text.strip()

    if text.upper().startswith("TXN"):
        if text in valid_txns:
            if text in used_txns:
                update.message.reply_text("This Transaction ID has already been used.")
            else:
                used_txns.add(text)
                with open(USED_IDS_FILE, "a") as f:
                    f.write(text + "\n")
                update.message.reply_text(
                    "Payment verified! You can now download the e-notes with /getfile"
                )
        else:
            update.message.reply_text(
                "Invalid Transaction ID. Please check and send again."
            )
    else:
        # If not TXN ID, forward to DeepSeek API
        response = call_deepseek_api(text)
        update.message.reply_text(response)

# /getfile command - sends e-notes if payment done
def getfile(update, context):
    chat_id = update.message.chat_id
    # We need a way to verify if user paid, for demo we skip user-level check
    # If you want user-specific payment tracking, you need a DB or mapping chat_id->paid
    # Here, we simply check if at least one TXN was used (simple demo)
    if used_txns:
        update.message.reply_document(open(ENOTES_PATH, "rb"), filename="e-notes.zip")
    else:
        update.message.reply_text("You must pay first with /unlock and verify your TXN ID.")

# DeepSeek API call
def call_deepseek_api(query):
    url = "https://api.deepseek.ai/your_endpoint"  # replace with actual endpoint
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        # Extract answer from DeepSeek response - adjust according to their actual response schema
        answer = data.get("answer") or "Sorry, I could not find an answer."
        return answer
    except Exception as e:
        return "Error contacting DeepSeek API."

# Telegram webhook endpoint for FastAPI
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return JSONResponse({"status": "ok"})

# Setup command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("unlock", unlock))
dispatcher.add_handler(CommandHandler("getfile", getfile))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

# On startup, set webhook
@app.on_event("startup")
def on_start():
    bot.set_webhook(WEBHOOK_URL)

# Health check root endpoint (useful for UptimeRobot)
@app.get("/")
async def root():
    return {"status": "Alice Bot is running"}

