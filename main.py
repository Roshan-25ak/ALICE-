import os
from fastapi import FastAPI, Request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
import httpx
from dotenv import load_dotenv

# Load .env if running locally
if os.environ.get("RENDER") != "true":
    load_dotenv()

# Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, update_queue=None, workers=4, use_context=True)
verified_users = set()

# Command: /start
def start(update, context):
    update.message.reply_text(
        "👋 Welcome! Use /ask to talk to AI, /unlock to pay via QR, /verify TXN_ID to verify payment, then /getfile to download."
    )

# Command: /ask <question>
def ask(update, context):
    question = " ".join(context.args)
    if not question:
        update.message.reply_text("⚠️ Usage: /ask What is AI?")
        return

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ]
    }
    try:
        res = httpx.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        reply = res.json()["choices"][0]["message"]["content"]
        update.message.reply_text(reply)
    except Exception as e:
        update.message.reply_text(f"❌ DeepSeek API Error: {e}")

# Command: /unlock
def unlock(update, context):
    with open("qr.jpg", "rb") as qr:
        update.message.reply_photo(qr, caption="📥 Scan and pay using Paytm.\nThen use /verify <transaction_id>")

# Command: /verify <TXN_ID>
def verify(update, context):
    user_id = update.message.from_user.id
    txn_id = " ".join(context.args).strip()

    if not txn_id:
        update.message.reply_text("⚠️ Usage: /verify TXN12345678")
        return

    if is_txn_valid(txn_id):
        verified_users.add(user_id)
        mark_txn_used(txn_id)
        update.message.reply_text("✅ Verified! Use /getfile to download your notes.")
    else:
        update.message.reply_text("❌ Invalid or already used TXN ID.")

# Command: /getfile
def getfile(update, context):
    user_id = update.message.from_user.id
    if user_id in verified_users:
        with open("enotes.zip", "rb") as f:
            update.message.reply_document(f)
    else:
        update.message.reply_text("❌ Please verify payment first using /unlock and /verify.")

# Helpers
def is_txn_valid(txn_id):
    with open("txn_ids.txt", "r") as f:
        valid = set(line.strip() for line in f)
    with open("used_ids.txt", "r") as f:
        used = set(line.strip() for line in f)
    return txn_id in valid and txn_id not in used

def mark_txn_used(txn_id):
    with open("used_ids.txt", "a") as f:
        f.write(txn_id + "\n")

# FastAPI webhook endpoint
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return {"ok": True}

@app.get("/")
async def health_check():
    return {"status": "running"}

@app.on_event("startup")
async def on_start():
    await bot.set_webhook(WEBHOOK_URL)

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("ask", ask))
dispatcher.add_handler(CommandHandler("unlock", unlock))
dispatcher.add_handler(CommandHandler("verify", verify))
dispatcher.add_handler(CommandHandler("getfile", getfile))
