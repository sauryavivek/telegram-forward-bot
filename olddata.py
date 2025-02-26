from telethon.sync import TelegramClient
from telethon.tl.types import InputMessagesFilterVideo, DocumentAttributeFilename
import sqlite3

# अपने API credentials डालें
api_id = 20181163                 # अपना API ID डालें
api_hash = '5c140b5bcb67ec70071b8caeb96afa85' # अपना API HASH डालें
channel_id = -1001865650854     # अपने चैनल का numeric ID

# database.sqlite से कनेक्ट करें
conn = sqlite3.connect("database.sqlite")
cursor = conn.cursor()

print("Fetching pre-existing videos from channel...")
with TelegramClient("session_name", api_id, api_hash) as client:
    for message in client.iter_messages(channel_id, filter=InputMessagesFilterVideo()):
        if message.video:
            file_name = "Unknown"
            if message.video.attributes:
                for attr in message.video.attributes:
                    if hasattr(attr, "file_name"):
                        file_name = attr.file_name
                        break
            # Caption प्राप्त करें (यदि उपलब्ध हो)
            caption = getattr(message, "caption", None) or getattr(message, "message", "") or ""
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO videos (message_id, file_name, caption) VALUES (?, ?, ?)",
                    (message.id, file_name, caption)
                )
                conn.commit()
                print(f"Added: {file_name}")
            except Exception as e:
                print(f"Skipping video (ID: {message.id}): {e}")

print("All pre-existing videos stored in database!")
conn.close()
