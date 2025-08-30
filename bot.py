import requests
import random
import string
import re
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===============================
# CONFIG
# ===============================
BOT_TOKEN = "8269822718:AAEz08EJ2AamKkwDU5TolzY9JKzLL4XuPgE"   # Bot token
ASIA_API_KEY = "7jkmE5NM2VS6GqJ9pzlI"                          # Temp-mail.asia API key
MAILTM_URL = "https://api.mail.tm"

# Lưu email + token + last_msg theo user
user_data = {}

# ===============================
# HÀM TẠO EMAIL RANDOM (temp-mail.asia)
# ===============================
def create_asia_email():
    try:
        url = f"https://v2.temp-mail.asia/api/random-email/{ASIA_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("email")
    except:
        return None
    return None

# ===============================
# HÀM TẠO MAIL.TM ACCOUNT
# ===============================
def create_mailtm_account():
    try:
        # lấy domain
        domains = requests.get(f"{MAILTM_URL}/domains").json()["hydra:member"]
        domain = random.choice(domains)["domain"]

        local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{local}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        # tạo account
        requests.post(f"{MAILTM_URL}/accounts", json={
            "address": email,
            "password": password
        })

        # lấy token
        resp = requests.post(f"{MAILTM_URL}/token", json={
            "address": email,
            "password": password
        })
        if resp.status_code == 200:
            token = resp.json()["token"]
            return email, token
    except Exception as e:
        print("❌ Lỗi mail.tm:", e)
    return None, None

# ===============================
# CHECK INBOX MAIL.TM
# ===============================
def fetch_mailtm_messages(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{MAILTM_URL}/messages", headers=headers)
        if resp.status_code == 200:
            return resp.json().get("hydra:member", [])
    except:
        pass
    return []

# ===============================
# BẮT OTP TỪ EMAIL
# ===============================
def extract_otp(text):
    match = re.search(r"\b\d{4,8}\b", text)
    return match.group(0) if match else None

# ===============================
# AUTO CHECK MAIL (5s)
# ===============================
async def auto_check_mailtm(app: Application):
    while True:
        for user_id, data in user_data.items():
            if "mailtm_token" in data:
                msgs = fetch_mailtm_messages(data["mailtm_token"])
                for m in msgs:
                    if m["id"] != data.get("last_msg"):
                        data["last_msg"] = m["id"]

                        body = m.get("text", "") or m.get("intro", "") or ""
                        otp = extract_otp(body)

                        text = f"📩 New mail from *{m['from']['address']}*\n\n{m.get('subject','')}\n\n{body}"
                        if otp:
                            text += f"\n\n🔑 OTP: *{otp}*"

                        await app.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        await asyncio.sleep(5)

# ===============================
# COMMANDS
# ===============================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📧 TempMail.Asia", callback_data="asia"),
        InlineKeyboardButton("📮 Mail.tm", callback_data="mailtm")
    ]]
    await update.message.reply_text("Chọn dịch vụ email:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "asia":
        email = create_asia_email()
        if email:
            user_data[user_id] = {"asia_email": email}
            await query.edit_message_text(f"✅ Email TempMail.Asia:\n`{email}`", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Lỗi tạo email Asia")

    elif query.data == "mailtm":
        email, token = create_mailtm_account()
        if email:
            user_data[user_id] = {"mailtm_email": email, "mailtm_token": token}
            await query.edit_message_text(f"✅ Email Mail.tm:\n`{email}`\n\n(Đang auto check inbox)", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Lỗi tạo email Mail.tm")

# ===============================
# MAIN
# ===============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def on_startup(_):
        asyncio.create_task(auto_check_mailtm(app))

    app.post_init = on_startup

    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
