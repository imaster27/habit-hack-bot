from flask import Flask
from threading import Thread

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


import matplotlib.pyplot as plt

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import csv

load_dotenv()

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Constants
CHOOSING = 1
DATA_FILE = "logs.csv"
WEIGHTS = {
    "🚕 Taxi": 1,
    "🍔 Food Delivery": 2,
    "🙌 No Spending Today": -3
}

# Create file if it doesn't exist
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Username", "Datetime", "Choice", "Weight"])

# ========== START COMMAND ========== #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🚕 Taxi", "🍔 Food Delivery", "🙌 No Spending Today"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Welcome back to HabitHack 2.0!\nWhat did you do today?",
        reply_markup=reply_markup
    )
    return CHOOSING

# ========== LOG SPENDING ========== #
async def log_spending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    choice = update.message.text
    username = f"@{user.username}" if user.username else user.first_name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weight = WEIGHTS.get(choice, 0)

    # Save to CSV
    with open(DATA_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([username, now, choice, weight])

    # Read last 7 days of data
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

    msg = ""

    # Nudge based on score
    if len(actions) < 3:
        msg = f"✅ Logged! You’ve started tracking. Keep it up!"
    else:
        if total_score >= 5:
            msg = f"⚠️ Your laziness score this week is {total_score}. Try a no-spend challenge tomorrow?"
        elif 0 <= total_score < 5:
            msg = f"💡 Score: {total_score}. You can still reduce lazy spending this week!"
        elif total_score < 0:
            msg = f"🔥 Great work! Your laziness score is {total_score}. Keep the saving streak alive!"

    await update.message.reply_text(msg)
    return ConversationHandler.END

# ========== WEEKLY REPORT ========== #
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    now_dt = datetime.now()

    actions = {"🚕 Taxi": 0, "🍔 Food Delivery": 0, "🙌 No Spending Today": 0}
    score = 0
    logs = []

    with open(DATA_FILE, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Username"] == username:
                log_time = datetime.strptime(row["Datetime"], "%Y-%m-%d %H:%M:%S")
                if (now_dt - log_time).days <= 6:
                    actions[row["Choice"]] += 1
                    score += int(row["Weight"])
                    logs.append(row)

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

# ========== MAIN APP ========== #
if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_spending)]},
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("report", report))

    print("✅ HabitHack is running...")
    keep_alive()

    app.run_polling()
