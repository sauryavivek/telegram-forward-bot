from telethon import TelegramClient, events
import sqlite3
from telethon.tl.types import DocumentAttributeFilename

# अपने API credentials यहाँ डालें
api_id = 20181163               # अपना API ID डालें
api_hash = '5c140b5bcb67ec70071b8caeb96afa85' # अपना API HASH डालें
channel_id = -1001865650854       # अपने चैनल का numeric ID

# डेटाबेस से कनेक्ट करें (इसी फोल्डर में database.sqlite)
conn = sqlite3.connect("database.sqlite", check_same_thread=False)
cursor = conn.cursor()

# Event handler: जब नया संदेश आए (वीडियो/फाइल)
async def new_message_handler(event):
    message = event.message
    # यदि संदेश में document है (वीडियो/फाइल)
    if message.document:
        file_name = "Unknown"
        if message.document.attributes:
            for attr in message.document.attributes:
                if hasattr(attr, "file_name"):
                    file_name = attr.file_name
                    break
        # कैप्शन प्राप्त करें (Telethon verson के अनुसार, caption या message)
        caption = getattr(message, "caption", None) or getattr(message, "message", "") or ""
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO videos (message_id, file_name, caption) VALUES (?, ?, ?)",
                (message.id, file_name, caption)
            )
            conn.commit()
            print(f"New file added: {file_name} | Caption: {caption}")
        except Exception as e:
            print(f"Error inserting message {message.id}: {e}")

# Telethon client setup
client = TelegramClient("session_name", api_id, api_hash)
client.start()

# Listen for new messages in the specified channel
client.add_event_handler(new_message_handler, events.NewMessage(chats=channel_id))

print("Auto-update running... Listening for new posts in the channel.")
client.run_until_disconnected()
