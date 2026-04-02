import sqlite3
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor

# 🔑 CONFIG
API_TOKEN = "8682590310:AAFWOq9qOPjURFaHh_Tm2sZp5TiH4O3nrHA"

# 👇 ADD ADMINS HERE
ADMINS = [7824185710]

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 🗄️ DATABASE
conn = sqlite3.connect("reports.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id TEXT,
    reported_user TEXT,
    description TEXT,
    proof_file_id TEXT,
    proof_type TEXT,
    reporter_id INTEGER,
    reporter_username TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER
)
""")

conn.commit()

# 🧠 TEMP STATE
user_state = {}

# 🚀 START
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚨 Report Scammer", callback_data="start_report"))

    if msg.from_user.id in ADMINS:
        kb.add(InlineKeyboardButton("➕ Add Channel", callback_data="add_channel_btn"))

    await msg.reply("Welcome! Choose an option:", reply_markup=kb)

# 🔘 BUTTONS
@dp.callback_query_handler(lambda c: c.data == "start_report")
async def start_report_btn(call: CallbackQuery):
    user_state[call.from_user.id] = {}
    await call.message.reply("Send scammer username or ID")

@dp.callback_query_handler(lambda c: c.data == "add_channel_btn")
async def add_channel_btn(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    user_state[call.from_user.id] = {"adding_channel": True}
    await call.message.reply("Send channel ID like: -100xxxx")

# ➕ SAVE CHANNEL
@dp.message_handler(lambda m: m.from_user.id in user_state and user_state[m.from_user.id].get("adding_channel"))
async def save_channel(msg: types.Message):
    if msg.from_user.id not in ADMINS:
        return

    try:
        channel_id = int(msg.text)
    except:
        await msg.reply("❌ Invalid ID")
        return

    cursor.execute("SELECT COUNT(*) FROM channels")
    count = cursor.fetchone()[0]

    if count >= 2:
        await msg.reply("❌ Max 2 channels allowed")
        return

    cursor.execute("INSERT INTO channels VALUES (?)", (channel_id,))
    conn.commit()

    await msg.reply("✅ Channel added")
    del user_state[msg.from_user.id]

# 📥 REPORT START
@dp.message_handler(lambda m: m.from_user.id in user_state and "username" not in user_state[m.from_user.id])
async def get_username(msg: types.Message):
    user_state[msg.from_user.id]["username"] = msg.text
    await msg.reply("Send proof (photo or video)")

# 📎 PROOF
@dp.message_handler(content_types=['photo', 'video'])
async def get_proof(msg: types.Message):
    if msg.from_user.id in user_state:
        if msg.photo:
            file_id = msg.photo[-1].file_id
            proof_type = "photo"
        else:
            file_id = msg.video.file_id
            proof_type = "video"

        user_state[msg.from_user.id]["proof"] = file_id
        user_state[msg.from_user.id]["proof_type"] = proof_type

        await msg.reply("Describe what happened")

# 📝 DESCRIPTION
@dp.message_handler(lambda m: m.from_user.id in user_state and "proof" in user_state[m.from_user.id])
async def get_desc(msg: types.Message):
    data = user_state[msg.from_user.id]
    report_id = str(uuid.uuid4())[:8]

    cursor.execute("INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
        report_id,
        data["username"],
        msg.text,
        data["proof"],
        data["proof_type"],
        msg.from_user.id,
        msg.from_user.username,
        "pending"
    ))
    conn.commit()

    text = f"""⚠️ NEW REPORT (#{report_id})

👤 Reported: {data['username']}
📝 {msg.text}

📢 Reporter: @{msg.from_user.username} ({msg.from_user.id})
"""

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{report_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{report_id}")
    )

    # SEND TO ADMINS
    for admin in ADMINS:
        if data["proof_type"] == "photo":
            await bot.send_photo(admin, data["proof"], caption=text, reply_markup=kb)
        else:
            await bot.send_video(admin, data["proof"], caption=text, reply_markup=kb)

    await msg.reply("✅ Report submitted")
    del user_state[msg.from_user.id]

# ✅ APPROVE
@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    report_id = call.data.split("_")[1]

    cursor.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    data = cursor.fetchone()

    if not data:
        return

    cursor.execute("UPDATE reports SET status='approved' WHERE id=?", (report_id,))
    conn.commit()

    text = f"""⚠️ SCAMMER ALERT

👤 {data[1]}
📝 {data[2]}

⚠️ User-submitted report. Verify before dealing.
"""

    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()

    for ch in channels:
        if data[4] == "photo":
            await bot.send_photo(ch[0], data[3], caption=text)
        else:
            await bot.send_video(ch[0], data[3], caption=text)

    await call.message.edit_caption(call.message.caption + "\n\n✅ Approved")

# ❌ REJECT
@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    report_id = call.data.split("_")[1]

    cursor.execute("UPDATE reports SET status='rejected' WHERE id=?", (report_id,))
    conn.commit()

    await call.message.edit_caption(call.message.caption + "\n\n❌ Rejected")

# ▶️ RUN
if __name__ == "__main__":
    executor.start_polling(dp)