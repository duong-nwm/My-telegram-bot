import requests
import random
import string
import asyncio
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ===============================
# CONFIG
# ===============================
BOT_TOKEN = "8269822718:AAEz08EJ2AamKkwDU5TolzY9JKzLL4XuPgE"
ASIA_API_KEY = "7jkmE5NM2VS6GqJ9pzlI"
MAILTM_URL = "https://api.mail.tm"
FB_ACCESS_TOKEN = "YOUR_FB_GRAPH_API_TOKEN"

# ===============================
# DATA USER
# ===============================
user_data = {}            # user_id -> email/token/last_msg
user_data_checking = {}   # user_id -> True nếu auto check email
awaiting_uid = {}         # user_id -> True nếu chờ nhập UID FB

# ===============================
# EMAIL FUNCTIONS
# ===============================
def create_asia_email():
    try:
        resp = requests.get(f"https://v2.temp-mail.asia/api/random-email/{ASIA_API_KEY}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("email")
    except:
        pass
    return None

def create_mailtm_account():
    try:
        domains = requests.get(f"{MAILTM_URL}/domains").json()["hydra:member"]
        domain = random.choice(domains)["domain"]
        local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"{local}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        requests.post(f"{MAILTM_URL}/accounts", json={"address": email, "password": password})
        resp = requests.post(f"{MAILTM_URL}/token", json={"address": email, "password": password})
        if resp.status_code == 200:
            return email, resp.json()["token"]
    except:
        pass
    return None, None

def fetch_mailtm_messages(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{MAILTM_URL}/messages", headers=headers)
        if resp.status_code == 200:
            return resp.json().get("hydra:member", [])
    except:
        pass
    return []

def extract_otp(text):
    match = re.search(r"\b\d{4,8}\b", text)
    return match.group(0) if match else None

def get_2fa_lay2fa(email):
    try:
        resp = requests.get(f"https://lay2fa.com/api?email={email}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("2fa")
    except:
        pass
    return None

# ===============================
# AUTO CHECK MAIL
# ===============================
async def auto_check_mailtm(app: Application):
    while True:
        for user_id, data in user_data.items():
            if "mailtm_token" in data and user_data_checking.get(user_id):
                msgs = fetch_mailtm_messages(data["mailtm_token"])
                for m in msgs:
                    if m["id"] != data.get("last_msg"):
                        data["last_msg"] = m["id"]
                        body = m.get("text","") or m.get("intro","") or ""
                        otp = extract_otp(body)
                        text = f"📩 Mail từ *{m['from']['address']}*\n\n{m.get('subject','')}\n\n{body}"
                        if otp:
                            text += f"\n\n🔑 OTP: *{otp}*"
                        await app.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
        await asyncio.sleep(5)

# ===============================
# MENU KEYBOARD
# ===============================
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Tạo TempMail.Asia", callback_data="asia"),
         InlineKeyboardButton("📮 Tạo Mail.tm", callback_data="mailtm")],
        [InlineKeyboardButton("🔄 Tự động lấy OTP", callback_data="auto_otp"),
         InlineKeyboardButton("📲 Lấy 2FA", callback_data="get_2fa")],
        [InlineKeyboardButton("✅ Check live UID FB", callback_data="check_fb_uid")]
    ])

# ===============================
# START COMMAND
# ===============================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chọn hành động:", reply_markup=main_menu_keyboard())

# ===============================
# CALLBACK HANDLER
# ===============================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # --- Tạo TempMail.Asia ---
    if query.data == "asia":
        email = create_asia_email()
        if email:
            user_data[user_id] = {"asia_email": email}
            await query.message.reply_text(f"✅ Email TempMail.Asia:\n`{email}`", parse_mode="Markdown",
                                         reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ Lỗi tạo TempMail.Asia", reply_markup=main_menu_keyboard())

    # --- Tạo Mail.tm ---
    elif query.data == "mailtm":
        email, token = create_mailtm_account()
        if email:
            user_data[user_id] = {"mailtm_email": email, "mailtm_token": token}
            await query.message.reply_text(f"✅ Email Mail.tm:\n`{email}`\n(Đang auto check inbox)", parse_mode="Markdown",
                                         reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ Lỗi tạo Mail.tm", reply_markup=main_menu_keyboard())

    # --- Tự động lấy OTP ---
    elif query.data == "auto_otp":
        if user_data.get(user_id):
            user_data_checking[user_id] = True
            await query.message.reply_text("🔄 Bắt đầu tự động lấy OTP từ email...", reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ Chưa có email để lấy OTP", reply_markup=main_menu_keyboard())

    # --- Lấy 2FA ---
    elif query.data == "get_2fa":
        email = user_data.get(user_id, {}).get("asia_email") or user_data.get(user_id, {}).get("mailtm_email")
        if not email:
            await query.message.reply_text("❌ Chưa có email để lấy 2FA.", reply_markup=main_menu_keyboard())
            return
        otp = get_2fa_lay2fa(email)
        if otp:
            await query.message.reply_text(f"🔑 OTP 2FA:\n`{otp}`", parse_mode="Markdown",
                                         reply_markup=main_menu_keyboard())
        else:
            await query.message.reply_text("❌ Chưa có mã 2FA mới.", reply_markup=main_menu_keyboard())

    # --- Check live UID FB ---
    elif query.data == "check_fb_uid":
        awaiting_uid[user_id] = True
        await query.message.reply_text("🔄 Nhập UID Facebook cần check:", reply_markup=main_menu_keyboard())

# ===============================
# MESSAGE HANDLER (UID FB)
# ===============================
async def uid_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if awaiting_uid.get(user_id):
        uid = update.message.text.strip()
        awaiting_uid[user_id] = False
        try:
            url = f"https://graph.facebook.com/{uid}?access_token={FB_ACCESS_TOKEN}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if 'error' in data:
                    await update.message.reply_text(f"❌ UID {uid} không tồn tại hoặc bị khoá", reply_markup=main_menu_keyboard())
                else:
                    await update.message.reply_text(f"✅ UID {uid} còn sống\nTên: {data.get('name')}", reply_markup=main_menu_keyboard())
            else:
                await update.message.reply_text(f"❌ Không lấy được thông tin UID {uid}", reply_markup=main_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi: {e}", reply_markup=main_menu_keyboard())

# ===============================
# MAIN
# ===============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, uid_message_handler))

    async def on_startup(_):
        asyncio.create_task(auto_check_mailtm(app))
    app.post_init = on_startup
    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
