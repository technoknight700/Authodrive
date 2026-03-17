from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# SQLite (local file database) 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///admins.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Admin Model
class Admin(db.Model):
    email_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Create table
with app.app_context():
    db.create_all()

# Registration API
@app.route('/signup', methods=['POST'])
def register():
    data = request.get_json()
    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')

    new_admin = Admin(
        name=data['name'],
        email=data['email'],
        mobile=data['mobile'],
        password=hashed_pw
    )

    try:
        db.session.add(new_admin)
        db.session.commit()
        return jsonify({"message": "Registration successful"}), 201
    except:
        return jsonify({"error": "Email or Mobile already exists"}), 400
   

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect("autho_drive.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins WHERE email=? AND password=?", (email, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401


if __name__ == "__main__":
    app.run(debug=True)

