import os
import logging
import asyncio
import nest_asyncio  # pip install nest_asyncio
import sqlite3
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

nest_asyncio.apply()

# --------------------- CONFIGURATION ---------------------
# Read sensitive data from environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
# ---------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --------------------- HELPER FUNCTIONS ---------------------
def clean_text(text: str) -> str:
    """
    Removes '@' handles and long alphanumeric IDs (20+ characters) from the text.
    """
    if not text:
        return ""
    text = re.sub(r'@\w+', '', text)  # Remove @ handles
    text = re.sub(r'\b[a-fA-F0-9]{20,}\b', '', text)  # Remove long alphanumeric IDs
    return text.strip()

def parse_series_name(file_name: str) -> str:
    """
    Extracts the series name from a file name.
    Example: "Mahabharat.e267.2014.WEB-DL.1080p.mkv" returns "Mahabharat".
    If the pattern doesn't match, returns the cleaned file name.
    """
    file_name = clean_text(file_name)
    match = re.match(r'^(.*?)\.e\d+\.', file_name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return file_name.strip()

def parse_quality(file_name: str) -> str:
    """
    Extracts the quality (480p, 720p, 1080p) from the file name.
    """
    match = re.search(r'(480p|720p|1080p)', file_name, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "Unknown"

def generate_group_key(file_name: str) -> str:
    """
    Generates a group key based on the series name and quality.
    Example: "Mahabharat - 1080p"
    """
    series = parse_series_name(file_name)
    quality = parse_quality(file_name)
    group_key = f"{series} - {quality}"
    return group_key[:50]  # Truncate to 50 characters if needed

# --------------------- DATABASE SETUP ---------------------
conn = sqlite3.connect("database.sqlite", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER UNIQUE,
        file_name TEXT,
        caption TEXT
    )
    """
)
conn.commit()

# --------------------- BOT HANDLERS ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Video Bot!\n"
        "Type a series name (e.g., 'Mahabharat' or 'Pushpa') to see all episodes grouped by quality.\n"
        "For a full series, use 'Send All'. For a specific episode, click 'Search Episode' and then enter the episode number."
    )

async def search_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    if not query:
        await update.message.reply_text("Please provide a search keyword. Example: Mahabharat")
        return

    cursor.execute(
        "SELECT message_id, file_name FROM videos WHERE file_name LIKE ? OR caption LIKE ?",
        ('%' + query + '%', '%' + query + '%')
    )
    results = cursor.fetchall()
    if not results:
        await update.message.reply_text("No files found with that keyword.")
        return

    # Group by generated group key (series name and quality)
    groups = {}
    for message_id, file_name in results:
        group_key = generate_group_key(file_name)
        groups.setdefault(group_key, []).append(message_id)

    keyboard = []
    for group_key, msg_ids in groups.items():
        if len(msg_ids) == 1:
            keyboard.append([InlineKeyboardButton(group_key, callback_data=f"single_{msg_ids[0]}")])
        else:
            # For groups with multiple records, show "Send All" and "Search Episode" buttons.
            keyboard.append([
                InlineKeyboardButton(group_key, callback_data=f"single_{msg_ids[0]}"),
                InlineKeyboardButton("Send All", callback_data=f"all_{group_key.replace(' ', '_')}"),
                InlineKeyboardButton("Search Episode", callback_data=f"searchep_{group_key.replace(' ', '_')}")
            ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a quality group:", reply_markup=reply_markup)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    await search_videos(update, context, query)

async def auto_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("search_episode_group"):
        await episode_search_handler(update, context)
    else:
        query = update.message.text.strip()
        await search_videos(update, context, query)

async def episode_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_key = context.user_data.get("search_episode_group")
    if not group_key:
        return
    episode_query = update.message.text.strip().lower()
    cursor.execute("SELECT message_id, file_name, caption FROM videos")
    rows = cursor.fetchall()
    selected = []
    for msg_id, fname, cap in rows:
        current_group = generate_group_key(fname)
        if current_group == group_key:
            if episode_query in fname.lower() or episode_query in (cap or "").lower():
                selected.append((msg_id, cap))
    if not selected:
        await update.message.reply_text(
            f"No episode matching '{episode_query}' found for series '{group_key}'.\nSending all episodes instead."
        )
        cursor.execute("SELECT message_id, caption, file_name FROM videos")
        rows = cursor.fetchall()
        selected = []
        for msg_id, cap, fname in rows:
            if generate_group_key(fname) == group_key:
                selected.append((msg_id, cap))
    for msg_id, cap in selected:
        cleaned_caption = clean_text(cap)
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id,
                caption=cleaned_caption
            )
        except Exception as e:
            await update.message.reply_text(f"Error sending file (ID: {msg_id}): {e}")
    context.user_data.pop("search_episode_group", None)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    await update.callback_query.answer()
    if data.startswith("single_"):
        message_id = int(data.split("_")[1])
        cursor.execute("SELECT caption FROM videos WHERE message_id = ?", (message_id,))
        row = cursor.fetchone()
        caption = row[0] if row and row[0] is not None else ""
        cleaned_caption = clean_text(caption)
        try:
            await context.bot.copy_message(
                chat_id=update.effective_chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=message_id,
                caption=cleaned_caption
            )
        except Exception as e:
            await update.callback_query.message.reply_text(
                f"Error sending file (ID: {message_id}): {e}\nFile may have been deleted."
            )
    elif data.startswith("all_"):
        group_key_raw = data.split("_", 1)[1]
        group_key = group_key_raw.replace('_', ' ')
        cursor.execute("SELECT message_id, caption, file_name FROM videos")
        rows = cursor.fetchall()
        selected = []
        for msg_id, cap, fname in rows:
            if generate_group_key(fname) == group_key:
                selected.append((msg_id, cap))
        if not selected:
            await update.callback_query.message.reply_text("No files found for this group.")
            return
        for msg_id, cap in selected:
            cleaned_caption = clean_text(cap)
            try:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=CHANNEL_ID,
                    message_id=msg_id,
                    caption=cleaned_caption
                )
            except Exception as e:
                await update.callback_query.message.reply_text(
                    f"Error sending file (ID: {msg_id}): {e}\nFile may have been deleted."
                )
    elif data.startswith("searchep_"):
        group_key_raw = data.split("_", 1)[1]
        group_key = group_key_raw.replace('_', ' ')
        context.user_data["search_episode_group"] = group_key
        await update.callback_query.message.reply_text(
            f"Enter the episode number (or part of it) for series '{group_key}':"
        )

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_search))
    app.add_handler(CallbackQueryHandler(button))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
