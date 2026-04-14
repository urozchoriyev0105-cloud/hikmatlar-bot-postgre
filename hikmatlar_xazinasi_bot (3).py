import os
import psycopg2
import threading
import time
import random
import pytz
from datetime import datetime
from pathlib import Path
from flask import Flask
from threading import Thread 
from db_update import update_db 
import csv 
import psutil

def get_system_stats():
    process = psutil.Process(os.getpid())

    # RAM (MB da)
    ram = process.memory_info().rss / 1024 / 1024

    # CPU %
    cpu = psutil.cpu_percent(interval=1)

    return round(ram, 2), cpu

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot faol ishlamoqda!"

def run():
    app.run(host='0.0.0.0', port=10000)  # Render uchun 10000

def keep_alive():
    t = Thread(target=run)
    t.start()

# Telebot
import telebot
from telebot import types, apihelper
from dotenv import load_dotenv

# .env yuklash
base_dir = Path(__file__).resolve().parent
env_path = base_dir / '.env'
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")

bot = telebot.TeleBot(TOKEN)

START_DATE = datetime(2026, 4, 12).date()

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# TABLE yaratish
conn = get_db_connection()
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    phone TEXT,
    time1 TEXT DEFAULT '07:00',
    last_sent_index INTEGER DEFAULT -1,
    daily_count INTEGER DEFAULT 0,
    random_count INTEGER DEFAULT 0
)''') 

cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_count INTEGER DEFAULT 0")
cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS random_count INTEGER DEFAULT 0")
     
cursor.execute('''CREATE TABLE IF NOT EXISTS hikmatlar (
    id SERIAL PRIMARY KEY,
    secret_id INTEGER,
    status TEXT DEFAULT 'queue',
    is_posted_to_channel INTEGER DEFAULT 0,
    public_id INTEGER
)''') 

cursor.execute("ALTER TABLE hikmatlar ADD COLUMN IF NOT EXISTS random_count INTEGER DEFAULT 0")

cursor.execute('''CREATE TABLE IF NOT EXISTS random_limits (
    user_id BIGINT,
    last_key TEXT,
    PRIMARY KEY (user_id, last_key)
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS seen_hikmatlar (
    user_id BIGINT,
    hikmat_id INTEGER,
    PRIMARY KEY (user_id, hikmat_id)
)''')

conn.commit()
conn.close()

def add_user_to_db(user_id, first_name, username, phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        today = datetime.now().date()
        days_passed = (today - START_DATE).days

        cursor.execute('''
        INSERT INTO users (user_id, first_name, username, phone, last_sent_index)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
        first_name = EXCLUDED.first_name,
        username = EXCLUDED.username,
        phone = EXCLUDED.phone
        ''', (user_id, first_name, username, phone, days_passed))

        conn.commit()
    except Exception as e:
        print(f"Saqlashda xato: {e}")
    finally:
        conn.close()

# --- SOZLAMALAR ---

CHECK_CHANNELS = [
    {"id": -1003729356888, "link": "https://t.me/my_botstg"}
]

ARCHIVE_CHANNEL_ID = -1003821513746
ARCHIVE_LINK = "https://t.me/hikmatlar_xazinasi_tg"
SECRET_STORAGE_ID = -1003790411151


def get_clock_emoji(time_str):
    clocks = {
        "05:00": "🕔", "05:30": "🕠", "06:00": "🕕", "06:30": "🕡",
        "07:00": "🕖", "07:30": "🕢", "08:00": "🕗", "08:30": "🕣",
        "09:00": "🕘", "09:30": "🕤", "10:00": "🕙", "10:30": "🕥",
        "11:00": "🕚", "11:30": "🕦", "12:00": "🕛", "12:30": "🕧",
        "13:00": "🕐", "13:30": "🕜", "14:00": "🕑", "14:30": "🕝",
        "15:00": "🕒", "15:30": "🕞", "16:00": "🕓", "16:30": "🕟",
        "17:00": "🕔", "17:30": "🕠", "18:00": "🕕", "18:30": "🕡",
        "19:00": "🕖", "19:30": "🕢", "20:00": "🕗", "20:30": "🕣",
        "21:00": "🕘", "21:30": "🕤", "22:00": "🕙"
    }
    return clocks.get(time_str, "⏰")


def get_welcome_text(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT time1 FROM users WHERE user_id = %s", (user_id,))
    res = cursor.fetchone()

    conn.close()

    t1 = res[0] if res else "07:00"
    emoji1 = get_clock_emoji(t1)

    return (
        "<b>Assalamu alaykum va rohmatullohi va barokatuh!</b> 🌿\n\n"
        "<b>\"Hikmatlar Xazinasi\" botiga xush kelibsiz!</b> ✨\n\n"
        "<b>📅 Ishga tushirildi: 12.04.2026 ✅</b>\n\n"
        f"<b>{emoji1} {t1} yuborish 🇺🇿 vaqti</b>\n\n"
        "<b>🗓 Bot 🤖 har kuni sizga kunlik hikmatni taqdim etadi ✅</b>"
    )


# --- FUNKSIYALAR ---

def is_subscribed(user_id):
    for channel in CHECK_CHANNELS:
        try:
            status = bot.get_chat_member(channel['id'], user_id).status
            if status in ['left', 'kicked']:
                return False
        except:
            return False
    return True


def time_settings_markup(step=1, show_cancel=False):
    markup = types.InlineKeyboardMarkup(row_width=4)

    times = []
    for h in range(5, 23):
        times.append(f"{h:02d}:00")
        if h < 22:
            times.append(f"{h:02d}:30")

    buttons = [
        types.InlineKeyboardButton(text=t, callback_data=f"st_{step}_{t}")
        for t in times
    ]
    markup.add(*buttons)

    if show_cancel:
        markup.add(
            types.InlineKeyboardButton(
                text="⬅️ Bekor qilish",
                callback_data="cancel_time_change"
            )
        )

    return markup


# --- KLAVIATURALAR--- #
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    markup.add(types.KeyboardButton("/start"))
    markup.add("📚 Saqlangan hikmatlar", "🎲 Tasodifiy hikmat")
    markup.add("👥 Ulashish ⤴️", "🆘 Yordam")
    markup.add("⏰ Vaqtni o‘zgartirish")

    if user_id == ADMIN_ID:
        markup.add("⚙️ Admin Panel")

    return markup


# --- ULASHISH ---
@bot.message_handler(func=lambda m: m.text == "👥 Ulashish ⤴️")
def share_bot(message):
    markup = types.InlineKeyboardMarkup()

    share_text = (
        "\n\n👆👆👆👆👆👆👆👆\n\n"
        "Har kuni hikmatlar ulashuvchi botni sizga ham tavsiya qilaman. ✨"
    )

    markup.add(types.InlineKeyboardButton(
        text="🚀 Do'stlarga yuborish",
        switch_inline_query_chosen_chat=types.SwitchInlineQueryChosenChat(
            query=share_text,
            allow_user_chats=True,
            allow_group_chats=True
        )
    ))

    bot.send_message(
        message.chat.id,
        "Botni do'stlaringizga yuborish uchun pastdagi tugmani bosing:",
        reply_markup=markup
    )


# --- ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        "⚙️ Admin panelga xush kelibsiz",
        reply_markup=admin_keyboard()
    )


def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("➕ Hikmat qo'shish", "📝 Navbatni boshqarish")
    markup.add("📊 Statistika", "📢 Xabar yuborish") 
    markup.add("🏆 TOP Random","📂 Bazani yuklab olish")
    markup.add("📥 Zaxira tiklash","⬅️ Orqaga")
    return markup


def ask_for_contact(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Tasdiqlash ✅", request_contact=True))

    text = (
        "<b>Xavfsizlik tekshiruvi!</b> 🛡\n\n"
        "Botni spam-botlardan himoya qilish va sizning haqiqiy inson ekanligingizni tasdiqlash uchun pastdagi tugmani bosing. 👇\n\n"
        "<i>Xavotir olmang! Raqamingiz faqat inson ekanligingizni tasdiqlash uchun.</i>"
    )

    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back_to_main(message):
    bot.send_message(
        message.chat.id,
        "Asosiy menyu",
        reply_markup=main_keyboard(message.from_user.id)
    )
# --- START VA OBUNA ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id 
    # ✅ USERNI DB GA YOZISH
    add_user_to_db(
        user_id,
        message.from_user.first_name,
        f"@{message.from_user.username}" if message.from_user.username else "Usernamesiz",
        None  # telefon keyin olinadi
    )


    if not is_subscribed(user_id):
        markup = types.InlineKeyboardMarkup()
        for ch in CHECK_CHANNELS:
            markup.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=ch['link']))
        markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))

        bot.send_message(
            message.chat.id,
            "Botdan foydalanish uchun kanalga a'zo bo'ling:",
            reply_markup=markup
        )
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
    user_exists = cursor.fetchone()
    conn.close()

    if user_exists:
        bot.send_message(
            message.chat.id,
            get_welcome_text(user_id),
            reply_markup=main_keyboard(user_id), 
            parse_mode="HTML"
        )
    else:
        ask_for_contact(message.chat.id)
# --- OBUNA BO'LMAGANLAR UCHUN CHEKLOV ---
@bot.message_handler(func=lambda message: not is_subscribed(message.from_user.id))
def restricted_access(message):
    if message.from_user.id == ADMIN_ID:
        return

    markup = types.InlineKeyboardMarkup()
    for ch in CHECK_CHANNELS:
        markup.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=ch['link']))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))

    bot.send_message(
        message.chat.id,
        "Kechirasiz, davom etish uchun kanalga a'zo bo'lishingiz kerak:",
        reply_markup=markup
    ) 


@bot.callback_query_handler(func=lambda call: call.data == "check")
def check_callback(call):
    user_id = call.from_user.id

    if is_subscribed(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user_exists = cursor.fetchone()
        conn.close()

        if user_exists:
            bot.send_message(
                call.message.chat.id,
                get_welcome_text(user_id),
                reply_markup=main_keyboard(user_id),
                parse_mode="HTML"
            )
        else:
            ask_for_contact(call.message.chat.id)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali a'zo bo'lmadingiz!", show_alert=True)

@bot.message_handler(commands=['debug'])
def admin_debug(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 📌 Oxirgi 5 ta arxiv
        cursor.execute("""
            SELECT id, public_id 
            FROM hikmatlar 
            WHERE is_posted_to_channel = 1
            ORDER BY id DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.send_message(message.chat.id, "❌ Arxiv yo‘q")
            return

        text = "🔐 <b>OXIRGI 5 TA ARXIV</b>\n\n"

        for i, (hid, pub_id) in enumerate(rows, 1):
            # 🔗 LINK (kanal username bo‘lishi kerak)
            link = f"https://t.me/hikmatlar_xazinasi_tg/{pub_id}"

            text += f"{i}) ID: {hid}\n"
            text += f"🔗 <a href='{link}'>Xabarni ochish</a>\n\n"

        bot.send_message(message.chat.id, text, parse_mode="HTML")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")
           
@bot.message_handler(func=lambda m: m.text == "📝 Navbatni boshqarish" and m.from_user.id == ADMIN_ID)
def manage_queue(message):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, secret_id FROM hikmatlar WHERE is_posted_to_channel = 0")
        hikmatlar = cursor.fetchall()

        if not hikmatlar:
            bot.send_message(message.chat.id, "📭 Navbatda hikmatlar yo'q.")
            conn.close()
            return

        bot.send_message(message.chat.id, f"📝 Navbatda {len(hikmatlar)} ta hikmat bor.")

        for db_id, secret_id in hikmatlar:
            try:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    "❌ O'chirish",
                    callback_data=f"sql_del_{db_id}"
                ))

                bot.copy_message(
                    message.chat.id,
                    SECRET_STORAGE_ID,
                    secret_id,
                    reply_markup=markup
                )
            except:
                bot.send_message(message.chat.id, f"❌ Xabar yuklanmadi (ID: {db_id})")

        conn.close()

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {e}") 



@bot.message_handler(content_types=['document'])
def handle_backup_file(message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.document.file_name.endswith('.csv'):
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = 'temp_restore.csv'
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Ha, tiklash", callback_data="confirm_restore"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_restore"))

    bot.send_message(
        message.chat.id,
        "📄 Fayl qabul qilindi.\n\nBazani tiklaysizmi?",
        reply_markup=markup
    )

def make_user_link(name, uname, user_id):
    # Ism bo‘lmasa
    if not name:
        name = "Ismsiz"

    # Username bor bo‘lsa
    if uname and uname != "Usernamesiz":
        uname_clean = uname.replace("@", "")
        return f'<a href="https://t.me/{uname_clean}">{name}</a> | @{uname_clean}'

    # Username yo‘q bo‘lsa (faqat ism bosiladigan)
    return f'<a href="tg://user?id={user_id}">{name}</a>'


@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor() 
       
        # 👥 Jami user
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # 📚 Hikmatlar
        cursor.execute("SELECT COUNT(*) FROM hikmatlar")
        total_h = cursor.fetchone()[0]

        # ⌛ Navbat
        cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE is_posted_to_channel = 0")
        navbat = cursor.fetchone()[0]

        # 📦 Arxiv
        cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE is_posted_to_channel = 1")
        arxiv = cursor.fetchone()[0]

        # 🏆 TOP 10 (daily)
        cursor.execute("""
            SELECT user_id, first_name, username, daily_count 
            FROM users 
            ORDER BY daily_count DESC 
            LIMIT 10
        """)
        top_daily = cursor.fetchall()

        # 🎯 TOP 10 (random)
        cursor.execute("""
            SELECT user_id, first_name, username, random_count 
            FROM users 
            ORDER BY random_count DESC 
            LIMIT 10
        """)
        top_random = cursor.fetchall()

        # 🆕 Oxirgi 15 ta user
        cursor.execute("""
            SELECT user_id, first_name, username 
            FROM users 
            ORDER BY user_id DESC 
            LIMIT 15
        """)
        last_users = cursor.fetchall()

        conn.close()

        # 🔥 TEXT
        text = (
            "📊 <b>STATISTIKA</b>\n"
            "━━━━━━━━━━━━━━━\n\n"

            f"👥 <b>Foydalanuvchilar:</b> {total_users}\n"
            f"📚 <b>Hikmatlar:</b> {total_h}\n"
            f"⌛ <b>Navbatda:</b> {navbat}\n"
            f"📦 <b>Arxivda:</b> {arxiv}\n\n"

            "━━━━━━━━━━━━━━━\n"
            "🏆 <b>TOP 10 (Kunlik hikmat)</b>\n\n"
        )

        # 🏆 Daily TOP
        if top_daily:
            for i, (u_id, name, uname, count) in enumerate(top_daily, 1):
                text += f"{i}. {make_user_link(name, uname, u_id)} — <b>{count}</b>\n"
        else:
            text += "❌ Ma'lumot yo‘q\n"

        text += "\n━━━━━━━━━━━━━━━\n"
        text += "🎯 <b>TOP 10 (Tasodifiy hikmat)</b>\n\n"

        # 🎯 Random TOP
        if top_random:
            for i, (u_id, name, uname, count) in enumerate(top_random, 1):
                text += f"{i}. {make_user_link(name, uname, u_id)} — <b>{count}</b>\n"
        else:
            text += "❌ Ma'lumot yo‘q\n"

        # 🆕 Oxirgi userlar
        text += "\n━━━━━━━━━━━━━━━\n"
        text += "🕒 <b>Oxirgi 15 ta foydalanuvchi</b>\n\n"

        if last_users:
            for i, (u_id, name, uname) in enumerate(last_users, 1):
                text += f"{i}. {make_user_link(name, uname, u_id)}\n"
        else:
            text += "❌ Ma'lumot yo‘q\n"

        bot.send_message(message.chat.id, text, parse_mode="HTML")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")
@bot.message_handler(func=lambda m: m.text == "🏆 TOP Random")
def top_hikmatlar_admin(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, public_id, random_count 
            FROM hikmatlar
            WHERE is_posted_to_channel = 1
            ORDER BY random_count DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.send_message(message.chat.id, "❌ TOP Random hikmatlar yo‘q")
            return

        text = "🏆 <b>TOP 10 RANDOM HIKMATLAR</b>\n\n"
        markup = types.InlineKeyboardMarkup()

        for i, (hid, pub_id, count) in enumerate(rows, 1):

            text += f"{i}) Hikmat #{hid} — {count} marta\n"

            if pub_id:
                link = f"https://t.me/hikmatlar_xazinasi_tg/{pub_id}"

                markup.add(
                    types.InlineKeyboardButton(
                        text=f"{i}-ochish",
                        url=link
                    )
                )
            else:
                markup.add(
                    types.InlineKeyboardButton(
                        text=f"{i}-qayta tiklash 🔄",
                        callback_data=f"fix_{hid}"
                    )
                )

        bot.send_message(
            message.chat.id,
            text,
            parse_mode="HTML",
            reply_markup=markup
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}") 


@bot.message_handler(commands=['server'])
def server_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    ram, cpu = get_system_stats()

    bot.send_message(
        message.chat.id,
        f"🖥 Server holati\n\n💾 RAM: {ram} MB\n⚙️ CPU: {cpu}%"
    )
# --- O‘CHIRISH ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("sql_del_"))
def delete_sql_hikmat(call):
    db_id = int(call.data.split("_")[2])

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM hikmatlar WHERE id = %s", (db_id,))
        conn.commit()
        conn.close()

        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "✅ O‘chirildi")

    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Xato") 


        
@bot.message_handler(func=lambda m: m.text == "➕ Hikmat qo'shish" and m.from_user.id == ADMIN_ID)
def add_h(message):
    msg = bot.send_message(message.chat.id, "✍️ Postni yuboring:")
    bot.register_next_step_handler(msg, save_h)


def save_h(message):
    if message.text == "⬅️ Orqaga":
        return

    try:
        sent_msg = bot.copy_message(
            SECRET_STORAGE_ID,
            message.chat.id,
            message.message_id
        )
        secret_id = sent_msg.message_id

        f_id = None
        if message.content_type == 'photo':
            f_id = message.photo[-1].file_id
        elif message.content_type == 'video':
            f_id = message.video.file_id

        conn = get_db_connection()
        cursor = conn.cursor()

        status_value = f_id if f_id else 'queue'

        cursor.execute(
            "INSERT INTO hikmatlar (secret_id, status) VALUES (%s, %s)",
            (secret_id, status_value)
        )

        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, "✅ Hikmat saqlandi")

    except Exception as e:
        bot.send_message(message.chat.id, "❌ Xato")

@bot.message_handler(func=lambda m: m.text == "📂 Bazani yuklab olish") 
def send_db_file_button(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        import csv

        conn = get_db_connection()
        cursor = conn.cursor()

        file_name = f"full_backup_{datetime.now().strftime('%Y%m%d')}.csv"

        with open(file_name, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # USERS
            writer.writerow([
                'users','user_id','first_name','username','phone',
                'time1','last_sent_index','daily_count','random_count'
            ])

            cursor.execute("""
                SELECT user_id, first_name, username, phone, time1, last_sent_index, daily_count, random_count 
                FROM users
            """)

            for row in cursor.fetchall():
                writer.writerow(['users', *row])

            # HIKMATLAR
            writer.writerow(['hikmatlar','id','secret_id','status','is_posted_to_channel','public_id'])
            cursor.execute("SELECT id, secret_id, status, is_posted_to_channel, public_id FROM hikmatlar")
            for row in cursor.fetchall():
                writer.writerow(['hikmatlar', *row])

            # RANDOM LIMITS
            writer.writerow(['random_limits','user_id','last_key'])
            cursor.execute("SELECT user_id, last_key FROM random_limits")
            for row in cursor.fetchall():
                writer.writerow(['random_limits', *row])

            # SEEN HIKMATLAR
            writer.writerow(['seen_hikmatlar','user_id','hikmat_id'])
            cursor.execute("SELECT user_id, hikmat_id FROM seen_hikmatlar")
            for row in cursor.fetchall():
                writer.writerow(['seen_hikmatlar', *row])

        with open(file_name, "rb") as doc:
            bot.send_document(message.chat.id, doc, caption="🔥 FULL BACKUP")

        cursor.close()
        conn.close()
        os.remove(file_name)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")  

@bot.callback_query_handler(func=lambda call: call.data == "confirm_restore")
def confirm_restore(call):
    try:
        import csv
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. TIKLASHDAN OLDIN BAZANI TOZALASH (TRUNCATE)
        # Bu buyruq jadvallarni bo'shatadi va ID raqamlarni nollaydi
        cursor.execute("TRUNCATE TABLE users, hikmatlar, random_limits, seen_hikmatlar RESTART IDENTITY;")
        
        with open("temp_restore.csv", 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            for row in reader:
                if not row or len(row) < 2:
                    continue
                
                # Sarlavhalarni o'tkazib yuborish
                if not str(row[1]).replace('-', '').isdigit():
                    continue

                try:
                    if row[0] == 'users':
                        cursor.execute("""
                            INSERT INTO users (
                                user_id, first_name, username, phone,
                                time1, last_sent_index, daily_count, random_count
                            )
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (
                            int(row[1]), row[2], row[3], row[4], 
                            row[5], int(row[6]), int(row[7]), int(row[8])
                        ))

                    elif row[0] == 'hikmatlar':
                        p_id = int(row[5]) if len(row) > 5 and row[5] and row[5].isdigit() else None
                        cursor.execute("""
                            INSERT INTO hikmatlar (id, secret_id, status, is_posted_to_channel, public_id)
                            VALUES (%s,%s,%s,%s,%s)
                        """, (int(row[1]), int(row[2]), row[3], int(row[4]), p_id))

                    elif row[0] == 'random_limits':
                        cursor.execute("INSERT INTO random_limits (user_id, last_key) VALUES (%s,%s)", (int(row[1]), row[2]))

                    elif row[0] == 'seen_hikmatlar':
                        cursor.execute("INSERT INTO seen_hikmatlar (user_id, hikmat_id) VALUES (%s,%s)", (int(row[1]), int(row[2])))

                except Exception as row_error:
                    continue

        conn.commit()
        cursor.close()
        conn.close()

        bot.edit_message_text("✅ Baza tozalandi va TO‘LIQ qayta tiklandi!", call.message.chat.id, call.message.message_id)

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Xato: {e}")


        
@bot.message_handler(func=lambda m: m.text == "📥 Zaxira tiklash")
def restore_menu(message):
    if message.from_user.id != ADMIN_ID:
        return

    bot.send_message(
        message.chat.id,
        "📤 Iltimos, .csv zaxira faylni yuboring.\n\n⚠️ Bu amal bazani o‘zgartiradi!"
    ) 

@bot.callback_query_handler(func=lambda call: call.data == "cancel_restore")
def cancel_restore(call):
    try:
        bot.edit_message_text(
            "❌ Tiklash bekor qilindi",
            call.message.chat.id,
            call.message.message_id
        )
    except:
        bot.answer_callback_query(call.id, "Bekor qilindi")  
        
@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def start_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return

    back_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back_markup.add("⬅️ Orqaga")

    msg = bot.send_message(
        message.chat.id,
        "📢 Xabarni yuboring:",
        reply_markup=back_markup
    )

    bot.register_next_step_handler(msg, broad_send)


def broad_send(message):
    if message.text == "⬅️ Orqaga":
        bot.send_message(
            message.chat.id,
            "Bekor qilindi.",
            reply_markup=admin_keyboard()
        )
        return

    msg_text = message.text

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        conn.close()

        count = 0

        for (user_id,) in users:
            try:
                bot.send_message(user_id, msg_text)
                count += 1
            except:
                continue

        bot.send_message(
            message.chat.id,
            f"✅ {count} ta foydalanuvchiga yuborildi",
            reply_markup=admin_keyboard()
        )

    except Exception:
        bot.send_message(
            message.chat.id,
            "❌ Xatolik",
            reply_markup=admin_keyboard()
        )

    bot.send_message(
        message.chat.id,
        "Admin paneli:",
        reply_markup=admin_keyboard()
    )
       

            
@bot.message_handler(func=lambda m: m.text == "📚 Saqlangan hikmatlar")
def show_archive(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌐 Arxivni ko'rish", url=ARCHIVE_LINK))

    archive_text = (
        "📚 <b>Hikmatlar xazinasi arxivi</b>\n\n"
        "Barcha hikmatlar arxiv kanalda tartib bilan saqlanadi.\n\n"
        "💡 <b>Muhim eslatma:</b>\n\n"
        "<i>Bot 🤖 hikmatlarni har kuni Toshkent vaqti bilan 🕖 07:00 da arxiv kanalga joylaydi. "
        "Tizim \"-1\" rejimida ishlaydi: ya'ni kechagi hikmat bugun, bugungi hikmat esa ertaga joylanadi.</i>\n\n"
        "<b>Nega bunday tartib tanlangan?</b>\n\n"
        "<b>Shaxsiy vaqt ustuvorligi:</b> <i>Foydalanuvchilar hikmatlarni o‘zlari belgilagan vaqtlarda "
        "qabul qilishadi. Bot arxivga ularni vaqtidan oldin tashlab qo‘ymasligi uchun bu rejimdan foydalanamiz ✅</i>\n\n"
        "<b>Mustahkamlash:</b>\n"
        "<i>Bu usul kechagi o'qilgan hikmatni yana bir bor ko'zdan kechirib, takrorlash vazifasini ham bajaradi. ✨</i>"
    )

    bot.send_message(
        message.chat.id,
        archive_text,
        parse_mode="HTML",
        reply_markup=markup
    )

    
    

@bot.message_handler(func=lambda message: message.text == "🆘 Yordam")
def help_handler(message):
    # Siz bergan matn aynan o'zidek:
    help_text = (
        "⚠️ <b>Texnik ogohlantirish:</b>\n\n"
        "Bot server orqali avtomatik rejimda ishlaydi. Ba'zida texnik sabablar yoki internet nosozliklari "
        "tufayli xabarlar belgilangan vaqtdan biroz kechikishi mumkin. Bunday holatlarda to'g'ri "
        "tushunasiz degan umiddaman.\n\n"
        "📩 <b>Aloqa va murojaat:</b>\n\n"
        "Agar bot ishlamay qolsa yoki fikr-mulohaza takliflaringiz bo'lsa, aloqa botimiz orqali murojaat qilishingiz mumkin."
    )

    # Matn tagidagi inline tugma
    markup = types.InlineKeyboardMarkup()
    btn_contact = types.InlineKeyboardButton(text="✍️ Aloqa botiga o'tish", url="https://t.me/my_botstg_aloqabot")
    markup.add(btn_contact)

    bot.send_message(message.chat.id, help_text, parse_mode='HTML', reply_markup=markup)


@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    if not message.contact:
        return

    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Usernamesiz"
    phone = message.contact.phone_number

    conn = get_db_connection()
    cursor = conn.cursor()

    # ❗ %s ishlatildi (PostgreSQL uchun)
    cursor.execute("SELECT last_sent_index FROM users WHERE user_id = %s", (user_id,))
    existing_user = cursor.fetchone()

    if existing_user:
        cursor.execute("""
            UPDATE users
            SET first_name = %s, username = %s, phone = %s
            WHERE user_id = %s
        """, (first_name, username, phone, user_id))
    else:
        cursor.execute("""
            INSERT INTO users (user_id, first_name, username, phone, last_sent_index)
            VALUES (%s, %s, %s, %s, -1)
        """, (user_id, first_name, username, phone))

    conn.commit()
    conn.close()

    remove_kb = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "✅ Tasdiqlandi", reply_markup=remove_kb)

    bot.send_message(
        message.chat.id,
        "Vaqtni tanlang:",
        reply_markup=time_settings_markup(step=1, show_cancel=False)
        )


@bot.message_handler(func=lambda message: message.text and "Vaqtni o‘zgartirish" in message.text)
def change_time_start(message):
    user_id = message.from_user.id

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT time1 FROM users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()

    conn.close()

    msg_text = "🔄 <b>Vaqtni o‘zgartirish</b>\n\n"

    if user_data:
        msg_text += f"Hozirgi vaqtingiz: <b>{user_data[0]}</b>\n\n"

    msg_text += "Yangi vaqtni tanlang:"

    bot.send_message(
        message.chat.id,
        msg_text,
        reply_markup=time_settings_markup(step=1, show_cancel=True),
        parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("st_"))
def handle_time_selection(call):
    user_id = call.from_user.id
    data_parts = call.data.split("_")

    if len(data_parts) < 3:
        return

    selected_time = data_parts[2]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ❗ %s ishlatildi
        cursor.execute(
            "UPDATE users SET time1 = %s WHERE user_id = %s",
            (selected_time, user_id)
        )
        conn.commit()

        bot.delete_message(call.message.chat.id, call.message.message_id)

        bot.send_message(
            user_id,
            f"✅ Vaqt {selected_time} ga sozlandi",
            reply_markup=main_keyboard(user_id)
        )

    except:
        bot.answer_callback_query(call.id, "❌ Xato")

    finally:
        conn.close()


@bot.callback_query_handler(func=lambda call: call.data == "cancel_time_change")
def cancel_time(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)

    bot.send_message(
        call.message.chat.id,
        "Bekor qilindi",
        reply_markup=main_keyboard(call.from_user.id)
) 



@bot.message_handler(func=lambda m: m.text == "🎲 Tasodifiy hikmat")
def ask_for_random_hikmat(message):
    # Bu yerda foydalanuvchiga tushuntirish xati va Inline tugma yuboramiz
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("✨ Hikmatni ko'rish", callback_data="get_random_hikmat")
    markup.add(btn)

    text = (
        "📝 **Eslatma:** Ushbu hikmatlar shu vaqtgacha bot tomonidan taqdim etilgan (arxivdagi) xabarlar ichidan tasodifiy olinadi.\n\n"
        "🎯 **Eng muhimi:** Bot har bir foydalanuvchiga turlicha hikmatlar beradi va bir marta taqdim etilgan hikmatni sizga qayta yubormaydi.\n\n"
        "💡 *Ushbu tasodifiy hikmat balki siz uchun muhim eslatma bo‘lishi mumkin!!!*"
         )

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back(message):
    bot.send_message(message.chat.id, "Asosiy menyu", reply_markup=main_keyboard(message.from_user.id))


@bot.callback_query_handler(func=lambda call: call.data == "get_random_hikmat")
def handle_random_hikmat_callback(call):
    user_id = call.from_user.id
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    now = datetime.now(tashkent_tz)

    # 07:00 limit logikasi
    if now.hour < 7:
        from datetime import timedelta
        report_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        report_date = now.strftime("%Y-%m-%d")

    today_key = f"{report_date}_cycle07"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # --- 0. ARXIV + KUN HISOBI ---
        cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE is_posted_to_channel = 1")
        count = cursor.fetchone()[0]

        today = datetime.now(tashkent_tz).date()
        days_passed = (today - START_DATE).days + 1

        # ENG MUHIM (kun bilan sync)
        real_days = min(count, days_passed)

        if real_days < 30:
            qolgan_kun = 30 - real_days

            bot.answer_callback_query(
                call.id,
                text=f"⚠️ Arxivda kamida 30 ta hikmat boʻlishi kerak.\n\n⏳ Bu funsiya ochilishiga {qolgan_kun} kun qoldi",
                show_alert=True
            )
            return

        # --- 1. LIMIT TEKSHIRISH ---
        cursor.execute(
            "SELECT 1 FROM random_limits WHERE user_id = %s AND last_key = %s",
            (user_id, today_key)
        )

        if cursor.fetchone():
            bot.answer_callback_query(
                call.id,
                "⚠️ Siz bugungi tasodifiy hikmatni oldingiz!\n\n⏳ Limit har kuni 07:00 da yangilanadi",
                show_alert=True
            )
            return

        # --- 2. FOYDALANUVCHI KO‘RMAGAN HIKMAT ---
        cursor.execute("""
            SELECT id, secret_id FROM hikmatlar
            WHERE is_posted_to_channel = 1
            AND id NOT IN (
                SELECT hikmat_id FROM seen_hikmatlar WHERE user_id = %s
            )
            ORDER BY RANDOM()
            LIMIT 1
        """, (user_id,))

        res = cursor.fetchone()

        # --- 3. AGAR HAMMASINI KO‘RGAN BO‘LSA ---
        if not res:
            cursor.execute("""
                SELECT id, secret_id FROM hikmatlar
                WHERE is_posted_to_channel = 1
                ORDER BY RANDOM()
                LIMIT 1
            """)
            res = cursor.fetchone()

        if not res:
            bot.answer_callback_query(call.id, "📭 Arxivda hikmat topilmadi", show_alert=True)
            return

        hikmat_id, secret_id = res

        # --- 4. HIKMATNI YUBORISH ---
        bot.copy_message(call.message.chat.id, SECRET_STORAGE_ID, secret_id)

        # eski tugmali xabarni o‘chirish
        bot.delete_message(call.message.chat.id, call.message.message_id)

        # --- 5. LIMITNI YOZISH ---
        cursor.execute(
            """
            INSERT INTO random_limits (user_id, last_key)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, today_key)
        )

        # --- 6. KO‘RILGAN HIKMATNI YOZISH ---
        cursor.execute(
            """
            INSERT INTO seen_hikmatlar (user_id, hikmat_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, hikmat_id)
        ) 
        # ✅ RANDOM STATISTIKA
        cursor.execute(
            "UPDATE users SET random_count = random_count + 1 WHERE user_id = %s",
            (user_id,)
        )

        conn.commit()

    except Exception as e:
        print(f"Xato: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi")

    finally:
        conn.close()



def auto_backup():
    print("📦 Auto backup ishga tushdi...")

    tashkent_tz = pytz.timezone('Asia/Tashkent')
    last_backup_date = None

    while True:
        try:
            now = datetime.now(tashkent_tz)

            if now.strftime("%H:%M") == "00:00":
                today_str = now.strftime("%Y-%m-%d")

                if last_backup_date != today_str:
                    last_backup_date = today_str

                    import csv
                    conn = get_db_connection()
                    cursor = conn.cursor()

                    file_name = f"auto_backup_{now.strftime('%Y%m%d')}.csv"

                    with open(file_name, "w", newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)

                        # USERS
                        writer.writerow([
                            'users','user_id','first_name','username','phone',
                            'time1','last_sent_index','daily_count','random_count'
                        ])

                        cursor.execute("""
                        SELECT user_id, first_name, username, phone, time1, last_sent_index, daily_count, random_count 
                        FROM users
                        """)
                        for row in cursor.fetchall():
                            writer.writerow(['users', *row])

                        # HIKMATLAR
                        writer.writerow(['hikmatlar','id','secret_id','status','is_posted_to_channel','public_id'])
                        cursor.execute("SELECT id, secret_id, status, is_posted_to_channel, public_id FROM hikmatlar")
                        for row in cursor.fetchall():
                            writer.writerow(['hikmatlar', *row])

                        # RANDOM LIMITS
                        writer.writerow(['random_limits','user_id','last_key'])
                        cursor.execute("SELECT user_id, last_key FROM random_limits")
                        for row in cursor.fetchall():
                            writer.writerow(['random_limits', *row])

                        # SEEN
                        writer.writerow(['seen_hikmatlar','user_id','hikmat_id'])
                        cursor.execute("SELECT user_id, hikmat_id FROM seen_hikmatlar")
                        for row in cursor.fetchall():
                            writer.writerow(['seen_hikmatlar', *row])

                    with open(file_name, "rb") as doc:
                        bot.send_document(ADMIN_ID, doc, caption="📦 Auto backup")

                    cursor.close()
                    conn.close()
                    os.remove(file_name)

                    print("✅ Backup yuborildi")

        except Exception as e:
            print(f"❌ Backup xato: {e}")

        time.sleep(60)


def smart_timer():
    print("🚀 Smart timer ishga tushdi...")
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    START_DATE_TIMER = datetime(2026, 4, 12).date()

    while True:
        try:
            now = datetime.now(tashkent_tz)
            today = now.date()
            current_time_str = now.strftime("%H:%M")
            days_passed = (today - START_DATE_TIMER).days

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT user_id, time1, last_sent_index FROM users")
            users = cursor.fetchall()

            msg_counter = 0

            # ================== USERLARGA YUBORISH ==================
            for u_id, u_time, last_idx in users:
                try:
                    # 🆕 YANGI USER
                    if last_idx == -1:
                        target_index = days_passed

                        cursor.execute(
                            "SELECT id, secret_id FROM hikmatlar ORDER BY id ASC LIMIT 1 OFFSET %s",
                            (target_index,)
                        )
                        hikmat = cursor.fetchone()

                        if hikmat:
                            bot.copy_message(u_id, SECRET_STORAGE_ID, hikmat[1])

                            cursor.execute(
                                "UPDATE users SET daily_count = daily_count + 1, last_sent_index = %s WHERE user_id = %s",
                                (target_index, u_id)
                            )

                            conn.commit()
                            msg_counter += 1

                    # 🔁 QARZ + NORMAL
                    elif last_idx < days_passed:
                        if current_time_str >= u_time or last_idx < days_passed - 1:
                            next_index = last_idx + 1

                            cursor.execute(
                                "SELECT id, secret_id FROM hikmatlar ORDER BY id ASC LIMIT 1 OFFSET %s",
                                (next_index,)
                            )
                            hikmat = cursor.fetchone()

                            if hikmat:
                                bot.copy_message(u_id, SECRET_STORAGE_ID, hikmat[1])

                                cursor.execute(
                                    "UPDATE users SET daily_count = daily_count + 1, last_sent_index = %s WHERE user_id = %s",
                                    (next_index, u_id)
                                )

                                conn.commit()
                                msg_counter += 1

                    # ⚡ FLOOD CONTROL
                    if msg_counter >= 15:
                        time.sleep(1)
                        msg_counter = 0
                    else:
                        time.sleep(0.05)

                except Exception as e:
                    print(f"User error: {e}")
                    continue

            # ================== ARXIV (100% SAFE) ==================
            while True:
                cursor.execute("""
                    SELECT id, secret_id FROM hikmatlar
                    WHERE is_posted_to_channel = 0
                    AND id <= %s
                    ORDER BY id ASC
                    LIMIT 1
                """, (days_passed,))

                hikmat = cursor.fetchone()

                if not hikmat:
                    break

                try:
                    sent_msg = bot.copy_message(
                        ARCHIVE_CHANNEL_ID,
                        SECRET_STORAGE_ID,
                        hikmat[1],
                        disable_notification=True
                    )

                    # 🔥 DOUBLE-PROTECTION (race condition yo‘q)
                    cursor.execute("""
                        UPDATE hikmatlar 
                        SET is_posted_to_channel = 1, public_id = %s 
                        WHERE id = %s AND is_posted_to_channel = 0
                    """, (sent_msg.message_id, hikmat[0]))

                    # agar boshqa thread oldin yozgan bo‘lsa — skip
                    if cursor.rowcount == 0:
                        conn.rollback()
                        continue

                    conn.commit()
                    time.sleep(0.5)

                except Exception as e:
                    print(f"Arxiv xatosi: {e}")
                    break

            conn.close()

        except Exception as e:
            print(f"🔥 Timer xato: {e}")
            try:
                conn.close()
            except:
                pass

        # ================== SMART SLEEP ==================
        if now.hour in [6, 7, 8]:
            time.sleep(15)
        else:
            time.sleep(60)

                                
if __name__ == "__main__":
    # 1. Flask (UptimeRobot)
    keep_alive()

    update_db()

    # 2. Threadlar
    timer_thread = Thread(target=smart_timer, daemon=True)
    timer_thread.start()

    backup_thread = Thread(target=auto_backup, daemon=True)
    backup_thread.start()

    # ❗ ENG MUHIM QATOR
    bot.remove_webhook()

    time.sleep(1)

    # 3. Admin xabar
    try:
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, "🟢 Bot serverda muvaffaqiyatli ishga tushdi!")
    except Exception as e:
        print(f"Xabarnoma xato: {e}")

    print("Bot ishga tushdi...")

    # 4. Polling (faqat 1 marta)
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
    



