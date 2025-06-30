# ========== IMPORTS ==========
import os
import csv
import pandas as pd
import logging
from datetime import datetime
from flask import Flask
from threading import Thread
import matplotlib.pyplot as plt

from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

# ========== SETUP ==========
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

CHOOSING = 1
DATA_FILE = "logs.csv"
WEIGHTS = {
    "🚕 Taxi": 1,
    "🍔 Food Delivery": 2,
    "🙌 No Spending Today": -3
}

# Create data file if it doesn't exist
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Username", "Datetime", "Choice", "Weight"])

# ========== KEEP ALIVE ==========
app_web = Flask('')

@app_web.route('/')
def home():
    return "🟢 HabitHack is alive", 200

def run():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# ========== HELPERS ==========
def save_user_id(chat_id):
    if not os.path.exists("users.txt"):
        with open("users.txt", "w") as f:
            f.write(str(chat_id) + "\n")
    else:
        with open("users.txt", "r+") as f:
            ids = [line.strip() for line in f.readlines()]
            if str(chat_id) not in ids:
                f.write(str(chat_id) + "\n")

def get_all_users():
    try:
        with open("users.txt", "r") as f:
            return list(set(int(line.strip()) for line in f))
    except FileNotFoundError:
        return []

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_id(update.effective_chat.id)
    keyboard = [["🚕 Taxi", "🍔 Food Delivery", "🙌 No Spending Today"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Welcome back to HabitHack 2.0!\nWhat did you do today?",
        reply_markup=reply_markup
    )
    return CHOOSING

async def log_spending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    choice = update.message.text
    username = f"@{user.username}" if user.username else user.first_name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weight = WEIGHTS.get(choice, 0)

    with open(DATA_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([username, now, choice, weight])

    actions = []
    total_score = 0
    now_dt = datetime.now()

    with open(DATA_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Username"] == username:
                action_time = datetime.strptime(row["Datetime"], "%Y-%m-%d %H:%M:%S")
                if (now_dt - action_time).days <= 6:
                    actions.append(row)
                    total_score += int(row["Weight"])

    if len(actions) < 3:
        msg = f"✅ Logged! You’ve started tracking. Keep it up!"
    elif total_score >= 5:
        msg = f"⚠️ Your laziness score this week is {total_score}. Try a no-spend challenge tomorrow?"
    elif 0 <= total_score < 5:
        msg = f"💡 Score: {total_score}. You can still reduce lazy spending this week!"
    else:
        msg = f"🔥 Great work! Your laziness score is {total_score}. Keep the saving streak alive!"

    await update.message.reply_text(msg)
    return ConversationHandler.END

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    now_dt = datetime.now()
    actions = {"🚕 Taxi": 0, "🍔 Food Delivery": 0, "🙌 No Spending Today": 0}
    score = 0

    with open(DATA_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Username"] == username:
                log_time = datetime.strptime(row["Datetime"], "%Y-%m-%d %H:%M:%S")
                if (now_dt - log_time).days <= 6:
                    actions[row["Choice"]] += 1
                    score += int(row["Weight"])

    total_logs = sum(actions.values())
    lazy_logs = actions["🚕 Taxi"] + actions["🍔 Food Delivery"]
    lazy_rate = round((lazy_logs / total_logs) * 100) if total_logs else 0

    await update.message.reply_text(
        f"📊 Your 7-Day Report:\n"
        f"🚕 Taxi: {actions['🚕 Taxi']} times\n"
        f"🍔 Food Delivery: {actions['🍔 Food Delivery']} times\n"
        f"🙌 No Spending: {actions['🙌 No Spending Today']} times\n"
        f"\n⚖️ Laziness Score: {score}\n"
        f"💡 Lazy Spending Rate: {lazy_rate}%"
    )

async def send_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}"
    if username != "@Rustamboyev_B":
        await update.message.reply_text("🚫 You’re not authorized to access this file.")
        return
    try:
        with open("logs.csv", "rb") as file:
            await update.message.reply_document(InputFile(file), filename="logs.csv")
    except FileNotFoundError:
        await update.message.reply_text("⚠️ logs.csv not found.")

async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = f"@{update.effective_user.username}"
    try:
        df = pd.read_csv("logs.csv")
        user_df = df[df["Username"] == username]
        if user_df.empty:
            await update.message.reply_text("🙁 You haven’t logged any actions yet.")
            return
        total_actions = len(user_df)
        total_score = user_df["Weight"].sum()
        action_counts = user_df["Choice"].value_counts()
        summary = f"📊 *Your Summary*\n\n👤 User: {username}\n🗓️ Actions Logged: {total_actions}\n💸 Laziness Score: {total_score}\n\n"
        for action, count in action_counts.items():
            summary += f"• {action}: {count}x\n"
        await update.message.reply_text(summary, parse_mode="Markdown")
    except FileNotFoundError:
        await update.message.reply_text("⚠️ No log found. Start using the bot to generate data.")

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_ids = get_all_users()
    for chat_id in user_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text="📅 Don’t forget to log your spending today in HabitHack!")
        except Exception as e:
            print(f"❌ Failed to send reminder to {chat_id}: {e}")

# ========== MAIN ==========
if __name__ == "__main__":
    print("✅ HabitHack is starting...")

    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_spending)]},
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("getcsv", send_csv))
    app.add_handler(CommandHandler("summary", send_summary))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_reminder, 'interval', seconds=60)  # TEMP TESTING
    scheduler.start()

    keep_alive()
    app.run_polling()
