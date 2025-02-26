import sqlite3

conn = sqlite3.connect("database.sqlite")
cursor = conn.cursor()

# videos टेबल बनाएँ (यदि पहले से मौजूद नहीं है)
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
conn.close()
print("Database setup complete!")
