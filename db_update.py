import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

def update_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN daily_count INTEGER DEFAULT 0;")
        print("✅ daily_count qo‘shildi")
    except Exception as e:
        print("⚠️ daily_count allaqachon bor")

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN random_count INTEGER DEFAULT 0;")
        print("✅ random_count qo‘shildi")
    except Exception as e:
        print("⚠️ random_count allaqachon bor")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_db()
