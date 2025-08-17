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

# Bot Credentials (Inbuilt - Not visible to users)
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
WEBHOOK_URL = "https://lottery-88-game-bot.onrender.com/telegram"
PORT = int(os.environ.get('PORT', 10000))

# Initialize bot and app
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        monetization_request TEXT,
        auto_optimize BOOLEAN DEFAULT 1
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
    logger.info(f"OTP sent to {phone}: {otp}")

# Authentication System
@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"Start command received from user {message.from_user.id}")
    
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

# Webhook handler
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        logger.info("Webhook received")
        if request.headers.get('content-type') == 'application/json':
            json_str = request.get_data(as_text=True)
            logger.info(f"Webhook data: {json_str}")
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return jsonify({"status": "ok"})
        else:
            logger.error("Invalid content type")
            return jsonify({"error": "Invalid request"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Bot is running!"})

# Test endpoint
@app.route('/test', methods=['GET'])
def test():
    try:
        # Test bot functionality
        bot_info = bot.get_me()
        return jsonify({
            "status": "Bot is working!",
            "bot_info": {
                "id": bot_info.id,
                "first_name": bot_info.first_name,
                "username": bot_info.username
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Set webhook endpoint
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        logger.info("Setting webhook...")
        bot.remove_webhook()
        result = bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set result: {result}")
        return jsonify({"status": "Webhook set successfully", "url": WEBHOOK_URL})
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")
        return jsonify({"error": str(e)}), 500

# Webhook info endpoint
@app.route('/webhook_info', methods=['GET'])
def webhook_info():
    try:
        webhook_info = bot.get_webhook_info()
        return jsonify({
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Manual webhook set endpoint
@app.route('/set_webhook_manual', methods=['GET'])
def set_webhook_manual():
    try:
        logger.info("Manual webhook setup...")
        bot.remove_webhook()
        response = bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Manual webhook set response: {response}")
        
        if response:
            return jsonify({"status": "Webhook set successfully", "url": WEBHOOK_URL})
        else:
            return jsonify({"status": "Failed to set webhook"}), 500
    except Exception as e:
        logger.error(f"Manual webhook setup failed: {e}")
        return jsonify({"status": "Error", "error": str(e)}), 500

# Test message endpoint
@app.route('/send_test_message', methods=['GET'])
def send_test_message():
    try:
        # Send a test message to admin
        bot.send_message(ADMIN_ID, "🧪 Test message from bot")
        return jsonify({"status": "Test message sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Set webhook on startup
    try:
        logger.info("Starting bot...")
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Webhook set to: {WEBHOOK_URL}")
        
        # Send startup message to admin
        try:
            bot.send_message(ADMIN_ID, "🚀 Bot started successfully!")
        except:
            pass
        
    except Exception as e:
        logger.error(f"❌ Webhook setup failed: {e}")
    
    app.run(host='0.0.0.0', port=PORT)
