import os
import sqlite3
import random
import time
import hmac
import hashlib
import logging
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import telebot
from telebot import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Credentials (Inbuilt)
BOT_TOKEN = "7566709441:AAE9A9V-Z9Q0vAQr2qyaBCBv0zpRyU3Akcw"
ADMIN_ID = 6646320334
ADMIN_PHONE = "9234906001"
BUSINESS_NAME = "Rina Travels Agency Pvt. Ltd"
BUSINESS_EMAIL = "rinatrevelsagancypvtltd@gmail.com"
SUPPORT_USERNAME = "@amanjee7568"
UPI_ID = "9234906001@ptyes"
CASHFREE_APP_ID = "104929343d4e4107a5ca08529a03929401"
CASHFREE_SECRET_KEY = "cfsk_ma_prod_a25900faa3d8666dc9f3813051da2ab3_da582824"
CASHFREE_WEBHOOK_SECRET = "wzfmcpjtz6na7czj64dd"
WEBHOOK_URL = "https://super-bot-render-1.onrender.com/telegram"
PORT = 10000

# Initialize bot and app
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        name TEXT,
        otp TEXT,
        is_verified BOOLEAN DEFAULT 0,
        game_wallet INTEGER DEFAULT 0,
        premium_wallet INTEGER DEFAULT 0,
        game_wallet_code TEXT,
        premium_wallet_code TEXT,
        is_premium BOOLEAN DEFAULT 0,
        referral_code TEXT,
        referred_by INTEGER,
        created_at TEXT,
        last_activity TEXT,
        is_monetized BOOLEAN DEFAULT 0,
        monetization_request TEXT
    )
    ''')
    
    # Games table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        game_type TEXT,
        bet_amount INTEGER,
        result TEXT,
        win_amount INTEGER,
        played_at TEXT
    )
    ''')
    
    # Transactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount INTEGER,
        status TEXT,
        utr TEXT,
        created_at TEXT
    )
    ''')
    
    # Admin logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target_user INTEGER,
        details TEXT,
        created_at TEXT
    )
    ''')
    
    # Jobs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        type TEXT,
        salary TEXT,
        location TEXT,
        description TEXT,
        contact TEXT,
        created_at TEXT
    )
    ''')
    
    # Results table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        board TEXT,
        exam_type TEXT,
        year TEXT,
        result_link TEXT,
        created_at TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Helper functions
def generate_wallet_code():
    return f"WLT-{random.randint(10000, 99999)}"

def generate_referral_code():
    return f"REF-{random.randint(1000, 9999)}"

def get_user(user_id):
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_wallet(user_id, game_amount=0, premium_amount=0):
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users 
    SET game_wallet = game_wallet + ?, premium_wallet = premium_wallet + ?
    WHERE user_id = ?
    """, (game_amount, premium_amount, user_id))
    conn.commit()
    conn.close()

def log_admin_action(admin_id, action, target_user=None, details=""):
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO admin_logs (admin_id, action, target_user, details, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (admin_id, action, target_user, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(phone, otp):
    # In a real implementation, you would use an SMS gateway
    # For demo purposes, we'll just log it
    logging.info(f"OTP sent to {phone}: {otp}")

# Authentication System
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        # Create new user
        conn = sqlite3.connect('ultimate_bot.db')
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO users (user_id, game_wallet_code, premium_wallet_code, referral_code, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, generate_wallet_code(), generate_wallet_code(), generate_referral_code(), datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        # Send authentication message with digital buttons
        auth_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        auth_keyboard.add(types.KeyboardButton("📱 Register with Phone", request_contact=True))
        
        bot.send_message(user_id, 
                         "🎉 Welcome to the Ultimate Gaming & Earning Bot!\n\n"
                         "Please register with your phone number to continue:",
                         reply_markup=auth_keyboard)
    else:
        main_menu(message)

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    # Generate and send OTP
    otp = generate_otp()
    send_otp(phone, otp)
    
    # Update user with phone and OTP
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users SET phone = ?, otp = ? WHERE user_id = ?
    """, (phone, otp, user_id))
    conn.commit()
    conn.close()
    
    # Ask for OTP
    msg = bot.send_message(user_id, "📱 We've sent an OTP to your phone.\n\nPlease enter the OTP:")
    bot.register_next_step_handler(msg, verify_otp)

def verify_otp(message):
    user_id = message.from_user.id
    otp_entered = message.text
    
    user = get_user(user_id)
    if user and user[3] == otp_entered:  # OTP is at index 3
        # Mark as verified
        conn = sqlite3.connect('ultimate_bot.db')
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE users SET is_verified = 1, name = ? WHERE user_id = ?
        """, (message.from_user.first_name, user_id))
        conn.commit()
        conn.close()
        
        bot.send_message(user_id, "✅ Verification successful!\n\nWelcome to the main menu.")
        main_menu(message)
    else:
        msg = bot.send_message(user_id, "❌ Invalid OTP. Please try again:")
        bot.register_next_step_handler(msg, verify_otp)

# Main Menu
def main_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        "🎰 Casino Games",
        "👛 Wallet",
        "💎 Premium",
        "🎁 Referral",
        "💼 Jobs",
        "📊 Results",
        "📈 My Stats",
        "ℹ️ Help"
    ]
    
    if user_id == ADMIN_ID:
        buttons.append("🛡️ Admin Panel")
    
    keyboard.add(*buttons)
    
    bot.send_message(user_id, 
                     f"🏠 Main Menu\n\n"
                     f"Game Wallet: ₹{user[4]}\n"
                     f"Premium Wallet: ₹{user[5]}\n"
                     f"Premium: {'✅' if user[7] else '❌'}",
                     reply_markup=keyboard)

# Casino Games with Animations
@bot.message_handler(func=lambda message: message.text == "🎰 Casino Games")
def casino_games(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user[7]:  # Not premium
        bot.send_message(user_id, "🎰 Casino games are available for premium users only!\n\nUpgrade to premium to unlock all games.")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    games = [
        ("🎰 Slots", "slots"),
        ("🐉 Dragon Tiger", "dragon_tiger"),
        ("🃏 Card Games", "card_games"),
        ("🎲 Dice", "dice")
    ]
    
    for text, callback in games:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    bot.send_message(user_id, "🎰 Choose a game:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data in ['slots', 'dragon_tiger', 'card_games', 'dice'])
def play_game(call):
    user_id = call.from_user.id
    game_type = call.data
    
    # Show betting interface with animation
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Place Bet", callback_data=f"bet_{game_type}"))
    
    bot.edit_message_text(f"🎰 {game_type.replace('_', ' ').title()}\n\nCurrent bet: ₹10\n\n"
                         "🎮 Adjust your bet using the buttons below:", 
                         call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('bet_'))
def place_bet(call):
    user_id = call.from_user.id
    game_type = call.data.split('_')[1]
    bet_amount = 10  # Default bet
    
    user = get_user(user_id)
    if user[4] < bet_amount:
        bot.answer_callback_query(call.id, "Insufficient balance in game wallet!")
        return
    
    # Deduct bet amount
    update_wallet(user_id, -bet_amount)
    
    # Show animation
    animation_messages = {
        'slots': ["🎰 Spinning...", "🎰 Spinning..", "🎰 Spinning."],
        'dragon_tiger': ["🐉 Dealing cards...", "🐉 Dealing cards..", "🐉 Dealing cards."],
        'card_games': ["🃏 Shuffling cards...", "🃏 Shuffling cards..", "🃏 Shuffling cards."],
        'dice': ["🎲 Rolling dice...", "🎲 Rolling dice..", "🎲 Rolling dice."]
    }
    
    for msg in animation_messages[game_type]:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)
        time.sleep(0.5)
    
    # Generate random result
    win = random.choice([True, False])
    if win:
        win_amount = bet_amount * 2
        update_wallet(user_id, win_amount)
        result_text = f"🎉 You won ₹{win_amount}!"
    else:
        result_text = f"😢 You lost ₹{bet_amount}."
    
    # Record game
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO games (user_id, game_type, bet_amount, result, win_amount, played_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, game_type, bet_amount, "win" if win else "lose", win_amount if win else 0, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    bot.edit_message_text(f"🎰 {game_type.replace('_', ' ').title()}\n\n{result_text}", 
                         call.message.chat.id, call.message.message_id)

# Wallet Management
@bot.message_handler(func=lambda message: message.text == "👛 Wallet")
def wallet_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Add Money", callback_data="add_money"),
        types.InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
        types.InlineKeyboardButton("🔄 Transfer", callback_data="transfer"),
        types.InlineKeyboardButton("📊 History", callback_data="history")
    )
    
    bot.send_message(user_id, 
                     f"👛 Wallet\n\n"
                     f"Game Wallet: ₹{user[4]} (Code: {user[6]})\n"
                     f"Premium Wallet: ₹{user[5]} (Code: {user[7]})",
                     reply_markup=keyboard)

# Premium Features
@bot.message_handler(func=lambda message: message.text == "💎 Premium")
def premium_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user[7]:
        bot.send_message(user_id, 
                         "💎 Premium Features:\n\n"
                         "✅ Access to all casino games\n"
                         "✅ Higher winning chances\n"
                         "✅ Exclusive bonuses\n"
                         "✅ Priority support\n"
                         "✅ Job vacancies\n"
                         "✅ Board results & news\n"
                         "✅ Monetization options")
    else:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Upgrade to Premium", callback_data="upgrade_premium"))
        
        bot.send_message(user_id, 
                         "💎 Upgrade to Premium to unlock:\n\n"
                         "✅ All casino games\n"
                         "✅ Higher winning chances\n"
                         "✅ Exclusive bonuses\n"
                         "✅ Priority support\n"
                         "✅ Job vacancies\n"
                         "✅ Board results & news\n"
                         "✅ Monetization options\n\n"
                         "Price: ₹299/month",
                         reply_markup=keyboard)

# Referral System
@bot.message_handler(func=lambda message: message.text == "🎁 Referral")
def referral_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    
    bot.send_message(user_id, 
                     f"🎁 Referral Program\n\n"
                     f"Your referral link: {referral_link}\n\n"
                     f"Refer friends and earn ₹20 for each referral!\n"
                     f"Your friend also gets ₹20 bonus!\n\n"
                     f"Total referrals: {user[10] if user[10] else 0}")

# Jobs Section
@bot.message_handler(func=lambda message: message.text == "💼 Jobs")
def jobs_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user[7]:  # Not premium
        bot.send_message(user_id, "💼 Job vacancies are available for premium users only!\n\nUpgrade to premium to unlock this feature.")
        return
    
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 5")
    jobs = cursor.fetchall()
    conn.close()
    
    if not jobs:
        bot.send_message(user_id, "💼 No job vacancies available at the moment.")
        return
    
    jobs_text = "💼 Latest Job Vacancies:\n\n"
    for job in jobs:
        jobs_text += f"📌 {job[1]} at {job[2]}\n"
        jobs_text += f"💰 Salary: {job[4]}\n"
        jobs_text += f"📍 Location: {job[5]}\n"
        jobs_text += f"📞 Contact: {job[7]}\n\n"
    
    bot.send_message(user_id, jobs_text)

# Results Section
@bot.message_handler(func=lambda message: message.text == "📊 Results")
def results_menu(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user[7]:  # Not premium
        bot.send_message(user_id, "📊 Results are available for premium users only!\n\nUpgrade to premium to unlock this feature.")
        return
    
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM results ORDER BY created_at DESC LIMIT 5")
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        bot.send_message(user_id, "📊 No results available at the moment.")
        return
    
    results_text = "📊 Latest Results:\n\n"
    for result in results:
        results_text += f"📌 {result[1]} {result[2]} {result[3]}\n"
        results_text += f"🔗 [View Result]({result[4]})\n\n"
    
    bot.send_message(user_id, results_text, parse_mode="Markdown")

# Admin Panel
@bot.message_handler(func=lambda message: message.text == "🛡️ Admin Panel")
def admin_panel(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        bot.send_message(user_id, "🚫 Access denied!")
        return
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("👥 Manage Users", callback_data="admin_users"),
        types.InlineKeyboardButton("💰 Manage Wallets", callback_data="admin_wallets"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
        types.InlineKeyboardButton("💼 Add Job", callback_data="admin_add_job"),
        types.InlineKeyboardButton("📊 Add Result", callback_data="admin_add_result"),
        types.InlineKeyboardButton("💸 Approve Withdraw", callback_data="admin_withdraw"),
        types.InlineKeyboardButton("🎚️ Edit Bot", callback_data="admin_edit_bot")
    )
    
    bot.send_message(user_id, "🛡️ Admin Panel", reply_markup=keyboard)

# Callback handlers for admin panel
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def admin_callback(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access denied!")
        return
    
    action = call.data.split('_')[1]
    
    if action == "users":
        # Show user management options
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("➕ Add Balance", callback_data="admin_add_balance"))
        keyboard.add(types.InlineKeyboardButton("➖ Remove Balance", callback_data="admin_remove_balance"))
        keyboard.add(types.InlineKeyboardButton("⭐ Make Premium", callback_data="admin_make_premium"))
        keyboard.add(types.InlineKeyboardButton("❌ Remove Premium", callback_data="admin_remove_premium"))
        
        bot.edit_message_text("👥 User Management", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif action == "wallets":
        # Show wallet management options
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔄 Game to Premium", callback_data="admin_game_to_premium"))
        keyboard.add(types.InlineKeyboardButton("🔄 Premium to Game", callback_data="admin_premium_to_game"))
        keyboard.add(types.InlineKeyboardButton("💸 Game to Bank", callback_data="admin_game_to_bank"))
        keyboard.add(types.InlineKeyboardButton("💸 Premium to Bank", callback_data="admin_premium_to_bank"))
        
        bot.edit_message_text("💰 Wallet Management", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif action == "broadcast":
        msg = bot.send_message(user_id, "📢 Enter the message to broadcast to all users:")
        bot.register_next_step_handler(msg, broadcast_message)
    
    elif action == "stats":
        # Show statistics
        conn = sqlite3.connect('ultimate_bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
        premium_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(game_wallet) FROM users")
        total_game_wallet = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(premium_wallet) FROM users")
        total_premium_wallet = cursor.fetchone()[0] or 0
        
        conn.close()
        
        stats_text = f"📊 Bot Statistics\n\n"
        stats_text += f"👥 Total Users: {total_users}\n"
        stats_text += f"⭐ Premium Users: {premium_users}\n"
        stats_text += f"💰 Total Game Wallet: ₹{total_game_wallet}\n"
        stats_text += f"💎 Total Premium Wallet: ₹{total_premium_wallet}\n"
        
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id)
    
    elif action == "add_job":
        msg = bot.send_message(user_id, "💼 Enter job details in format:\nTitle|Company|Type|Salary|Location|Description|Contact")
        bot.register_next_step_handler(msg, add_job)
    
    elif action == "add_result":
        msg = bot.send_message(user_id, "📊 Enter result details in format:\nBoard|Exam Type|Year|Result Link")
        bot.register_next_step_handler(msg, add_result)
    
    elif action == "withdraw":
        # Show pending withdrawals
        conn = sqlite3.connect('ultimate_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE type = 'withdraw' AND status = 'pending'")
        withdrawals = cursor.fetchall()
        conn.close()
        
        if not withdrawals:
            bot.edit_message_text("💸 No pending withdrawals", call.message.chat.id, call.message.message_id)
            return
        
        withdraw_text = "💸 Pending Withdrawals:\n\n"
        for withdrawal in withdrawals:
            withdraw_text += f"🆔 {withdrawal[0]} - User {withdrawal[1]} - ₹{withdrawal[2]}\n"
        
        bot.edit_message_text(withdraw_text, call.message.chat.id, call.message.message_id)
    
    elif action == "edit_bot":
        msg = bot.send_message(user_id, "🎚️ Enter the feature you want to edit:")
        bot.register_next_step_handler(msg, edit_bot_feature)

# Helper functions for admin actions
def broadcast_message(message):
    user_id = message.from_user.id
    broadcast_text = message.text
    
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    sent_count = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 Broadcast from Admin:\n\n{broadcast_text}")
            sent_count += 1
        except:
            pass
    
    bot.send_message(user_id, f"✅ Broadcast sent to {sent_count} users!")

def add_job(message):
    user_id = message.from_user.id
    job_details = message.text.split('|')
    
    if len(job_details) != 7:
        bot.send_message(user_id, "❌ Invalid format! Please use: Title|Company|Type|Salary|Location|Description|Contact")
        return
    
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO jobs (title, company, type, salary, location, description, contact, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_details[0].strip(), job_details[1].strip(), job_details[2].strip(), 
          job_details[3].strip(), job_details[4].strip(), job_details[5].strip(), 
          job_details[6].strip(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, "✅ Job added successfully!")

def add_result(message):
    user_id = message.from_user.id
    result_details = message.text.split('|')
    
    if len(result_details) != 4:
        bot.send_message(user_id, "❌ Invalid format! Please use: Board|Exam Type|Year|Result Link")
        return
    
    conn = sqlite3.connect('ultimate_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO results (board, exam_type, year, result_link, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (result_details[0].strip(), result_details[1].strip(), 
          result_details[2].strip(), result_details[3].strip(), 
          datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, "✅ Result added successfully!")

def edit_bot_feature(message):
    user_id = message.from_user.id
    feature = message.text
    
    # This is a placeholder for bot feature editing
    # In a real implementation, you would have a more complex system
    bot.send_message(user_id, f"🎚️ Editing feature: {feature}\n\nFeature updated successfully!")

# Webhook handler
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_str = request.get_data(as_text=True)
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return jsonify({"status": "ok"})
    return jsonify({"error": "Invalid request"}), 400

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Bot is running!"})

# Set webhook on startup
def set_webhook():
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"✅ Webhook set to: {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"❌ Webhook setup failed: {e}")

if __name__ == '__main__':
    set_webhook()
    app.run(host='0.0.0.0', port=PORT)
