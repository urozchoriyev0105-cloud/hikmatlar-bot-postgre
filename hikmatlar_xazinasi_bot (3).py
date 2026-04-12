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

app = Flask('')

@app.route('/')
def home():
    return "Bot faol ishlamoqda!" # UptimeRobot buni tekshiradi

def run():
    # PythonAnywhere bepul porti
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Telebot va Proxy uchun kerakli importlar
import telebot
from telebot import types, apihelper
from dotenv import load_dotenv



# 1. .env faylini to'g'ri yuklash (PythonAnywhere uchun eng xavfsiz yo'l)
base_dir = Path(__file__).resolve().parent
env_path = base_dir / '.env'
load_dotenv(dotenv_path=env_path)

# 3. .env faylidan ma'lumotlarni o'qib olish
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# Admin ID ni raqamga o'girib olamiz (agar u mavjud bo'lsa)
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

# 4. Botni ishga tushirish
if not TOKEN:
    raise ValueError("Xato: BOT_TOKEN .env faylidan topilmadi!")

bot = telebot.TeleBot(TOKEN)

# --- Sizning qolgan kodlaringiz (Bazaga ulanish va h.k.) ---

START_DATE = datetime(2026, 4, 12).date()

# Render'dan keladigan maxsus ulanish havolasi
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn


# 2-BLOK: Barcha jadvallarni yaratish
conn = get_db_connection()
cursor = conn.cursor()

# 1. Users jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT,
    username TEXT,
    phone TEXT,
    time1 TEXT DEFAULT '07:00',
    last_sent_index INTEGER DEFAULT -1
)''')

# Hikmatlar jadvali (PostgreSQL varianti)
cursor.execute('''CREATE TABLE IF NOT EXISTS hikmatlar (
    id SERIAL PRIMARY KEY,
    secret_id INTEGER,
    status TEXT DEFAULT 'queue',
    is_posted_to_channel INTEGER DEFAULT 0,
    public_id INTEGER
)''')

# 3. Random limits jadvali (Skrinshotdagi xato aynan shu yerda edi)
cursor.execute('''CREATE TABLE IF NOT EXISTS random_limits (
    user_id INTEGER,
    last_key TEXT,
    PRIMARY KEY (user_id, last_key)
)''')

# 4. Seen hikmatlar jadvali
cursor.execute('''CREATE TABLE IF NOT EXISTS seen_hikmatlar (
    user_id INTEGER,
    hikmat_id INTEGER,
    PRIMARY KEY (user_id, hikmat_id)
)''')

conn.commit()
conn.close() # HAMMA ISH TUGAGACH, FAQAT BIR MARTA YOPING!

def add_user_to_db(user_id, first_name, username, phone):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Bot ishga tushganidan beri o'tgan kunlarni hisoblaymiz
        today = datetime.now().date()
        days_passed = (today - START_DATE).days

        # 2. Yangi foydalanuvchini joriy kunga tenglab bazaga qo'shamiz
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

# 1. Majburiy obuna kanali
CHECK_CHANNELS = [
    {"id": -1003729356888, "link": "https://t.me/my_botstg"}
]

# 2. Kanal sozlamalari
ARCHIVE_CHANNEL_ID = -1003821513746 # Arxiv kanal ID (Linkdan olindi)
ARCHIVE_LINK = "https://t.me/hikmatlar_xazinasi_tg"
SECRET_STORAGE_ID = -1003790411151
def get_clock_emoji(time_str):
    # time_str masalan "08:30" formatida keladi
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
    return clocks.get(time_str, "⏰") # Agar ro'yxatda bo'lmasa, oddiy budilnik emojisi


# 3. Salomlashish matni
def get_welcome_text(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT time1 FROM users WHERE user_id = %s", (user_id,))
    res = cursor.fetchone()
    conn.close()

    t1 = res[0] if res else "07:00"
    emoji1 = get_clock_emoji(t1)

    text = (
        "<b>Assalamu alaykum va rohmatullohi va barokatuh!</b> 🌿\n\n"
        "<b>\"Hikmatlar Xazinasi\" botiga xush kelibsiz!</b> ✨\n\n"
        "<b>📅 Ishga tushirildi: 12.04.2026 ✅</b>\n\n"
        f"<b>{emoji1} {t1} yuborish 🇺🇿 vaqti</b>\n\n"
        "<b>🗓 Bot 🤖 har kuni sizga kunlik hikmatni taqdim etadi ✅</b>"
    )
    return text


# --- FUNKSIYALAR ---
def is_subscribed(user_id):
    for channel in CHECK_CHANNELS:
        try:
            status = bot.get_chat_member(channel['id'], user_id).status
            if status in ['left', 'kicked']: return False
        except: return False
    return True



def time_settings_markup(step=1, show_cancel=False):
    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []
    for h in range(5, 23):
        times.append(f"{h:02d}:00")
        if h < 22:
            times.append(f"{h:02d}:30")

    buttons = [types.InlineKeyboardButton(text=t, callback_data=f"st_{step}_{t}") for t in times]
    markup.add(*buttons)

    # Faqat vaqtni o'zgartirishda chiqadi, yangi foydalanuvchida emas
    if show_cancel:
        markup.add(types.InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cancel_time_change"))

    return markup


# --- KLAVIATURALAR--- #
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("/start"))
    markup.add("📚 Saqlangan hikmatlar", "🎲 Tasodifiy hikmat")
    markup.add("👥 Ulashish ⤴️", "🆘 Yordam")
    markup.add("⏰ Vaqtni o‘zgartirish") # Bu qatorni ichkariga oldik

    if int(user_id) == ADMIN_ID:
        markup.add("⚙️ Admin Panel")
    return markup


# --- ULASHISH TUGMASI UCHUN JAVOB ---
@bot.message_handler(func=lambda m: m.text == "👥 Ulashish ⤴️")
def share_bot(message):
    markup = types.InlineKeyboardMarkup()

        # Siz xohlagan chiroyli format: 2 ta yangi qator tashlaydi
    share_text = (
        "\n\n👆👆👆👆👆👆👆👆\n\n"
        "Har kuni hikmatlar ulashuvchi botni sizga ham tavsiya qilaman. ✨"
    )


    # switch_inline_query_chosen_chat orqali bot nomi chiqmaydigan qildik
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




def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("➕ Hikmat qo'shish", "📝 Navbatni boshqarish")
    markup.add("📊 Statistika", "📢 Xabar yuborish")
    markup.add("📂 Bazani yuklab olish","⬅️ Orqaga")
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


# --- START VA OBUNA ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    # 1. Majburiy obunani tekshirish
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

    # 2. SQLite bazasidan foydalanuvchini tekshirish
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
    user_exists = cursor.fetchone()
    conn.close()

    if user_exists:
        # Foydalanuvchi bazada bo'lsa: Qarzni tekshirish va uzish


        bot.send_message(
            message.chat.id,
            get_welcome_text(user_id),
            reply_markup=main_keyboard(user_id),
            parse_mode="HTML"
        )
    else:
        # Yangi foydalanuvchi bo'lsa: Kontakt so'rash
        ask_for_contact(message.chat.id)


@bot.callback_query_handler(func=lambda call: call.data == "check")
def check_callback(call):
    user_id = call.from_user.id
    if is_subscribed(user_id):
        bot.delete_message(call.message.chat.id, call.message.message_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
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


# --- OBUNA BO'LMAGANLAR UCHUN CHEKLOV ---
@bot.message_handler(func=lambda message: not is_subscribed(message.from_user.id))
def restricted_access(message):
    if message.from_user.id == ADMIN_ID:
        return False

    markup = types.InlineKeyboardMarkup()
    for ch in CHECK_CHANNELS:
        markup.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=ch['link']))
    markup.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))

    bot.send_message(
        message.chat.id,
        "Kechirasiz, davom etish uchun kanalga a'zo bo'lishingiz kerak:",
        reply_markup=markup
    )


# --- ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and m.from_user.id == ADMIN_ID)
def admin_menu(message):
    bot.send_message(message.chat.id, "🔧 Admin Panel:", reply_markup=admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id == ADMIN_ID)
def show_stats(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Foydalanuvchilar soni
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        # 2. Kanalga hali chiqmagan (navbatdagi) hikmatlar soni
        cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE is_posted_to_channel = 0")
        navbat = cursor.fetchone()[0]

        # 3. Oxirgi 15 ta ro'yxatdan o'tgan foydalanuvchi
        cursor.execute("SELECT user_id, first_name, username FROM users ORDER BY ROWID DESC LIMIT 15")
        last_users = cursor.fetchall()

        stats_text = (
            f"📊 <b>Statistika:</b>\n\n"
            f"👥 <b>Azolar:</b> {total_users}\n"
            f"⏳ <b>Navbatda:</b> {navbat} ta \n\n"
            f"👤 <b>Oxirgi 15 foydalanuvchi:</b>\n"
        )

        for u in last_users:
            u_id, name, uname = u
            display_name = name if name else "Ismsiz"
            display_username = uname if uname else "Usernamesiz"
            stats_text += f"🔹 <code>{u_id}</code> | {display_name} | {display_username}\n"

        # MUHIM: Xabarni yuborish try blokining ichida bo'lishi kerak
        bot.send_message(message.chat.id, stats_text, parse_mode="HTML")

    except Exception as e:
        print(f"Statistika xatosi: {e}")
        bot.send_message(message.chat.id, "❌ Statistika yuklanishida xatolik yuz berdi.")

    finally:
        # Baza ulanishini har doim yopish
        conn.close()


@bot.message_handler(func=lambda m: m.text == "📝 Navbatni boshqarish" and m.from_user.id == ADMIN_ID)
def manage_queue(message):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # O'ZGARISH: statusidan qat'iy nazar, hali kanalga chiqmaganlarni olish
        cursor.execute("SELECT id, secret_id FROM hikmatlar WHERE is_posted_to_channel = 0")
        hikmatlar = cursor.fetchall()
        conn.close()

        if not hikmatlar:
            bot.send_message(message.chat.id, "📭 Navbatda hikmatlar yo'q.")
            return

        bot.send_message(message.chat.id, f"📝 Navbatda {len(hikmatlar)} ta hikmat bor.")

        for row in hikmatlar:
            db_id, secret_id = row
            try:
                markup = types.InlineKeyboardMarkup()
                # O'chirish tugmasi shu yerda yaratiladi
                delete_btn = types.InlineKeyboardButton("❌ O'chirish", callback_data=f"sql_del_{db_id}")
                markup.add(delete_btn)

                bot.copy_message(message.chat.id, SECRET_STORAGE_ID, secret_id, reply_markup=markup)
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Xabar yuklanmadi (ID: {db_id})")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik: {e}")


# Navbatdagi hikmatni bazadan o'chirish handler'i
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
        bot.answer_callback_query(call.id, "✅ Hikmat navbatdan o'chirildi.")
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ O'chirishda xato: {e}")



@bot.message_handler(func=lambda m: m.text == "➕ Hikmat qo'shish" and m.from_user.id == ADMIN_ID)
def add_h(message):
    msg = bot.send_message(message.chat.id, "✍️ Postni yuboring:")
    bot.register_next_step_handler(msg, save_h)

def save_h(message):
    if message.text == "⬅️ Orqaga":
        return

    try:
        # 1. Xabarni maxfiy kanalga nusxalash
        sent_msg = bot.copy_message(SECRET_STORAGE_ID, message.chat.id, message.message_id)
        secret_id = sent_msg.message_id

        # 2. Agar rasm bo'lsa, uning file_id sini aniqlash
        f_id = None
        if message.content_type == 'photo':
            f_id = message.photo[-1].file_id
        elif message.content_type == 'video':
            f_id = message.video.file_id

        conn = get_db_connection()
        cursor = conn.cursor()

        # 3. Bazaga saqlash
        # Agar rasm bo'lsa f_id ni, bo'lmasa 'queue' ni yozamiz
        # Lekin o'chirish tugmasi chiqishi uchun baribir 'status' ustunidan foydalanamiz
        status_value = f_id if f_id else 'queue'

        cursor.execute("INSERT INTO hikmatlar (secret_id, status) VALUES (%s, %s)", (secret_id, status_value))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, "✅ Hikmat saqlandi va navbatga qo'shildi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")



@bot.message_handler(func=lambda m: m.text == "📂 Bazani yuklab olish")
def send_db_file_button(message):
    # ADMIN_ID ni .env dan olingan qiymat bilan tekshirish
    if ADMIN_ID and int(message.from_user.id) == ADMIN_ID:
        try:
            if backup_db():
                with open('backup.db', 'rb') as f:
                    bot.send_document(
                        message.chat.id,
                        f,
                        caption=f"📂 Baza backup fayli\n⏰ Vaqt: {datetime.now().strftime('%H:%M:%S')}",
                        visible_file_name="hikmat_base_backup.db"
                    )
            else:
                bot.send_message(message.chat.id, "❌ Backup yaratishda xatolik yuz berdi.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Faylni yuborishda xato: {e}")



@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def start_broadcast(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    back_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back_markup.add("⬅️ Orqaga")

    msg = bot.send_message(
        message.chat.id,
        "📢 Xabarni yuboring:",
        reply_markup=back_markup
    )
    # MUHIM: Bu yerdagi nom pastdagi funksiya nomi bilan bir xil bo'lishi shart!
    bot.register_next_step_handler(msg, broad_send)

def broad_send(message):
    # 1. Orqaga qaytishni tekshirish
    if message.text == "⬅️ Orqaga":
        bot.send_message(
            message.chat.id,
            "Bekor qilindi.",
            reply_markup=admin_keyboard() # Admin panelga qaytish
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
        for user in users:
            try:
                # user[0] SQLite tuple formatini to'g'irlaydi
                bot.send_message(user[0], msg_text)
                count += 1
            except:
                continue

        bot.send_message(
            message.chat.id,
            f"✅ Xabar {count} ta foydalanuvchiga yuborildi.",
            reply_markup=admin_keyboard()
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xatolik yuz berdi: {str(e)}", reply_markup=admin_keyboard())



        # 3. Yuborgandan keyin Admin paneliga qaytarish
        bot.send_message(message.chat.id, "Admin paneli:", reply_markup=admin_keyboard())

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Bazadan o'qishda xatolik: {e}")



@bot.message_handler(func=lambda m: m.text == "📚 Saqlangan hikmatlar")
def show_archive(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌐 Arxivni ko'rish", url=ARCHIVE_LINK))
    # Siz bergan matn HTML formatida:
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


    # ASOSIY MENYUNI CHIQARISH (Sizda aynan shu qismi yo'q edi)
    reply_markup=main_keyboard(user_id)

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    if message.contact:
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        # Username bor-yo'qligini tekshirish
        username = f"@{message.from_user.username}" if message.from_user.username else "Usernamesiz"
        phone = message.contact.phone_number

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Avval user bor-yo‘qligini tekshiramiz
        cursor.execute("SELECT last_sent_index FROM users WHERE user_id = ?", (user_id,))
        existing_user = cursor.fetchone()

        if existing_user:
            # 2. Agar user bo'lsa, faqat ism va raqamni yangilaymiz (indexga tegmaymiz!)
            cursor.execute("""
                UPDATE users
                SET first_name = %s, username = %s, phone = %s
                WHERE user_id = %s
            """, (first_name, username, phone, user_id))
            print(f"🔄 User yangilandi: {user_id}")
        else:
            # 3. Agar yangi user bo'lsa, uni bazaga qo'shamiz
            # last_sent_index = -1 qilsangiz, timer 0-indexdan (1-hikmatdan) boshlaydi
            cursor.execute("""
                INSERT INTO users (user_id, first_name, username, phone, last_sent_index)
                VALUES (%s, %s, %s, %s, -1)
            """, (user_id, first_name, username, phone))
            print(f"🆕 Yangi user qo'shildi: {user_id}")

        conn.commit()
        conn.close()

        # Tugmani o‘chirish (ReplyKeyboardRemove)
        remove_kb = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "✅ Muvaffaqiyatli tasdiqlandi!", reply_markup=remove_kb)

        # Vaqt tanlash bosqichiga o'tkazish
        bot.send_message(
            message.chat.id,
            "Endi hikmatlar yuboriladigan vaqtni tanlang:",
            reply_markup=time_settings_markup(step=1, show_cancel=False)
        )





@bot.message_handler(func=lambda message: "Vaqtni o‘zgartirish" in message.text)
def change_time_start(message):
    user_id = message.chat.id

    # DB ulanish
    conn = get_db_connection()
    cursor = conn.cursor()

    # Hozirgi vaqtni olish
    cursor.execute("SELECT time1 FROM users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()

    conn.close()

    msg_text = "🔄 <b>Vaqtni o‘zgartirish</b>\n\n"

    if user_data:
        msg_text += f"Hozirgi vaqtingiz: <b>{user_data[0]}</b>\n\n"

    msg_text += "Hikmat yuboriladigan yangi vaqtni tanlang:"

    bot.send_message(
        message.chat.id,
        msg_text,
        # Bu yerda True yozilgani uchun 'Bekor qilish' tugmasi CHIQADI
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
        # 1. Bazada vaqtni yangilash
        cursor.execute("UPDATE users SET time1 = ? WHERE user_id = %s", (selected_time, user_id))
        conn.commit()

        # 2. Eski tugmali xabarni o'chirish
        bot.delete_message(call.message.chat.id, call.message.message_id)

        # 3. Muvaffaqiyatli xabarni yuborish
        welcome_text = get_welcome_text(user_id)
        bot.send_message(
            user_id,
            f"✅ Vaqt <b>{selected_time}</b> ga muvaffaqiyatli sozlandi!\n\n{welcome_text}",
            reply_markup=main_keyboard(user_id), # Asosiy menyu tugmalari
            parse_mode="HTML"
        )
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi")
    finally:
        conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "cancel_time_change")
def cancel_time(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(
        call.message.chat.id,
         "Bekor qilindi.",
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
        # 0. ARXIV TO'LGANINI TEKSHIRISH (YANGI QISM)
        cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE is_posted_to_channel = 1")
        count = cursor.fetchone()[0]

        if count < 30: # <--- Bu qator tepadagi 'cursor' bilan bir chiziqda bo'lishi kerak
            qolgan_kun = 30 - count
            ogohlantirish = (
                f"⚠️ Arxivda kamida 30 ta hikmat boʻlishi kerak\n\n"
                f"⏳ Bu funksiya ochilishiga {qolgan_kun} kun qoldi"
            )
            bot.answer_callback_query(call.id, text=ogohlantirish, show_alert=True)
            conn.close()
            return # Funksiyani shu yerda to'xtatadi



        # ✅ 1. LIMIT TEKSHIRISH
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

        # ✅ 2. FOYDALANUVCHI KO‘RMAGAN HIKMAT
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

        # ✅ 3. AGAR HAMMASINI KO‘RGAN BO‘LSA
        if not res:
            cursor.execute("""
                SELECT id, secret_id FROM hikmatlar
                WHERE is_posted_to_channel = 1
                ORDER BY RANDOM()
                LIMIT 1
            """)
            res = cursor.fetchone()

            if res:
                  hikmat_id, secret_id = res

            # --- YANGI QO'SHILADIGAN QISMI ---
            cursor.execute("SELECT COUNT(*) FROM hikmatlar WHERE id < ?", (hikmat_id,))
            h_idx = cursor.fetchone()[0]

                        # Xabarni yangilash
            # 1. Avval yangi hikmatni tugma bilan yuboramiz
            bot.copy_message(call.message.chat.id, SECRET_STORAGE_ID, secret_id, reply_markup=markup)

            # 2. Keyin eski "Hikmatni ko'rish" tugmasi bor xabarni o'chiramiz
            bot.delete_message(call.message.chat.id, call.message.message_id)

            # Xabarni yangilash
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.copy_message(call.message.chat.id, SECRET_STORAGE_ID, secret_id)

            # ✅ 4. LIMITNI YOZISH
            cursor.execute(
                "INSERT OR IGNORE INTO random_limits (user_id, last_key) VALUES (%s, %s)",
                (user_id, today_key)
            )

            # ✅ 5. KO‘RILGAN HIKMATNI YOZISH (MUHIM!)
            cursor.execute(
                "INSERT OR IGNORE INTO seen_hikmatlar (user_id, hikmat_id) VALUES (%s, %s)",
                (user_id, hikmat_id)
            )

            conn.commit()

        else:
            bot.answer_callback_query(call.id, "📭 Arxivda hikmat topilmadi", show_alert=True)

    except Exception as e:
        print(f"Xato: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi")

    finally:
        conn.close()

# --- BU YERDAN SMART TIMER BOSHLANADI ---



def get_hikmat_by_index(idx):

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT secret_id FROM hikmatlar LIMIT 1 OFFSET %s", (idx,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None



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

            # 🟢 1. USERLARNI RO'YXATINI OLISH
            # Bazani loop ichida qayta-qayta qiynamaslik uchun hammasini birdan olamiz
            cursor.execute("SELECT user_id, time1, last_sent_index FROM users")
            users = cursor.fetchall()

            # Telegram limitini boshqarish uchun counter
            msg_counter = 0

            for u_id, u_time, last_idx in users:
                try:
                    # 🆕 YANGI USER (last_idx == -1)
                    if last_idx == -1:
                        target_index = days_passed
                        cursor.execute("SELECT secret_id FROM hikmatlar ORDER BY id ASC LIMIT 1 OFFSET ?", (target_index,))
                        hikmat = cursor.fetchone()

                        if hikmat:
                            bot.copy_message(u_id, SECRET_STORAGE_ID, hikmat[0])
                            cursor.execute("UPDATE users SET last_sent_index = %s WHERE user_id = %s", (target_index, u_id))
                            conn.commit()
                            msg_counter += 1

                    # 🔁 QARZ LOGIKA (Agar vaqti kelsa yoki qarzi juda ko'p bo'lsa)
                    elif last_idx < days_passed:
                        if current_time_str >= u_time or last_idx < days_passed - 1:
                            next_index = last_idx + 1
                            cursor.execute("SELECT secret_id FROM hikmatlar ORDER BY id ASC LIMIT 1 OFFSET ?", (next_index,))
                            hikmat = cursor.fetchone()

                            if hikmat:
                                bot.copy_message(u_id, SECRET_STORAGE_ID, hikmat[0])
                                cursor.execute("UPDATE users SET last_sent_index = %s WHERE user_id = %s", (next_index, u_id))
                                conn.commit()
                                msg_counter += 1

                    # 🔥 LIMITLARNI BOSHQARISH:
                    # Har 20 ta xabardan keyin biroz to'xtaymiz (5000 ta odamda bot qotib qolmasligi uchun)
                    if msg_counter >= 20:
                        time.sleep(1) # Telegram Flood limitdan qochish
                        msg_counter = 0
                    else:
                        time.sleep(0.04) # Kichik pauza (sekundiga ~25-30 xabar)

                except Exception as e:
                    # Bloklagan userlarni o'tkazib yuboramiz
                    continue

            # 🔵 2. ARXIV (07:00 dan keyin)
            archive_index = days_passed - 1
            if archive_index >= 0 and now.hour >= 7:
                cursor.execute("""
                    SELECT id, secret_id FROM hikmatlar
                    WHERE is_posted_to_channel = 0 ORDER BY id ASC LIMIT 1
                """)
                hikmat = cursor.fetchone()

                if hikmat and hikmat[0] <= archive_index + 1:
                    try:
                        sent_msg = bot.copy_message(ARCHIVE_CHANNEL_ID, SECRET_STORAGE_ID, hikmat[1], disable_notification=True)
                        cursor.execute("UPDATE hikmatlar SET is_posted_to_channel = 1, public_id = ? WHERE id = %s", (sent_msg.message_id, hikmat[0]))
                        conn.commit()
                    except: pass

            conn.close()
        except Exception as e:
            print(f"🔥 Timer xato: {e}")
            if 'conn' in locals(): conn.close()

        time.sleep(60)


# --- BOTNI ISHGA TUSHIRISH QISMI ---
if __name__ == "__main__":
    # 1. Flask serverni (UptimeRobot uchun) ishga tushirish
    keep_alive()

    # 2. Smart timerni alohida oqimda ishga tushirish
    # threading.Thread emas, shunchaki Thread deb yozamiz
    timer_thread = Thread(target=smart_timer, daemon=True)
    timer_thread.start()

    # 3. Admin xabarnomasi
    try:
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, "🟢 Bot serverda muvaffaqiyatli ishga tushdi!")
    except Exception as e:
        print(f"Xabarnoma yuborishda xato: {e}")

    print("Bot muvaffaqiyatli ishga tushdi...")

    # 4. Botni tinimsiz ishlatish (Polling)
    bot.infinity_polling(timeout=20, long_polling_timeout=10)




