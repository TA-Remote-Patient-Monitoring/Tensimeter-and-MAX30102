import sqlite3

def add_column():
    conn = sqlite3.connect('omron.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE spo2_measurements ADD COLUMN blood_sugar FLOAT;")
        print("Kolom blood_sugar berhasil ditambahkan ke database!")
    except sqlite3.OperationalError as e:
        print(f"Info: {e} (Mungkin kolom sudah ada)")
    finally:
        conn.commit()
        conn.close()

if __name__ == '__main__':
    add_column()
