from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

# --- Database setup ---
def init_db():
    conn = sqlite3.connect("authodrive.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- API Route ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    email = data["email"]
    mobile = data["mobile"]
    password = data["password"]  # 👉 later we’ll hash this (security)

    try:
        conn = sqlite3.connect("authodrive.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO admins (name, email, mobile, password) VALUES (?, ?, ?, ?)",
                       (name, email, mobile, password))
        conn.commit()
        conn.close()
        return jsonify({"message": "Admin registered successfully!"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 400
if __name__ == "__main__":
    app.run(debug=True)
