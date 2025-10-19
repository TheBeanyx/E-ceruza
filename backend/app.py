import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import uuid
from datetime import datetime
import random # Szükséges a random szám generálásához

# --- Inicializáció ---
app = Flask(__name__)
# CORS engedélyezése az összes domainre (a frontend miatt)
CORS(app)

# Adatbázis konfiguráció: sqlite fájl az instance mappában
# Ezért kellett törölni a régi tanulo_naptar.db fájlt
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tanulo_naptar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Adatbázis Modellek ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False) # ÚJ: A teljes név tárolása
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    task_type = db.Column(db.String(50), nullable=False) # Dolgozat, Beadando, stb.
    deadline = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer, default=0)
    
# --- Munkamenet kezelés: Adatbázis létrehozása ---
with app.app_context():
    # Megpróbálja létrehozni az adatbázist, ha még nem létezik
    db.create_all()

# --- Útvonalak (API Endpoints) ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # 1. Teljes név feldolgozása
    full_name = data['name'].strip()
    
    # 2. Felhasználónév generálása
    name_parts = full_name.lower().split()
    
    if len(name_parts) >= 2:
        # Ha van legalább 2 név (keresztnév vezetéknév)
        # Az utolsó név a vezetéknév, az első a keresztnév (nem magyaros sorrend, de így biztonságos)
        first_name = name_parts[0]
        last_name = name_parts[-1] 
    elif len(name_parts) == 1:
        # Ha csak egy név van megadva
        first_name = name_parts[0]
        last_name = "user"
    else:
        # Ha üres
        first_name = "uj"
        last_name = "felhasznalo"
        
    # Felhasználónév alapja: keresztnév_vezetéknév (kisbetűsen, de ékezettel)
    # Változás: KIVETTEM az unidecode használatát
    base_username_str = f"{first_name}_{last_name}"
    
    username = base_username_str
    
    # 3. Random szám hozzáadása és egyediség ellenőrzése
    while User.query.filter_by(username=username).first():
        random_number = random.randint(10, 99) # Kétjegyű szám
        username = f"{base_username_str}{random_number}"

    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(
        public_id=str(uuid.uuid4()),
        name=full_name, # Teljes név mentése
        email=data['email'],
        username=username,
        password_hash=hashed_password
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'uzenet': 'Sikeres regisztráció!', 'felhasznalonev': username}), 201
    except Exception as e:
        db.session.rollback()
        # Ellenőrizhetjük, hogy az e-mail már foglalt-e
        return jsonify({'hiba': 'Az e-mail cím már használatban van.'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'hiba': 'Érvénytelen felhasználónév vagy jelszó'}), 401

    # FONTOS: Visszaküldjük a name (teljes név) mezőt is!
    return jsonify({
        'uzenet': 'Sikeres bejelentkezés',
        'user_id': user.public_id,
        'username': user.username,
        'name': user.name # Új mező a frontend számára
    }), 200

# --- Feladat Útvonalak (Tasks CRUD) ---

@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    public_id = data.get('user_id')
    
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    try:
        # A dátumot datetime objektummá alakítjuk
        deadline_dt = datetime.fromisoformat(data['deadline'].replace('Z', '+00:00'))

        new_task = Task(
            user_id=user.id,
            title=data['title'],
            description=data.get('description'),
            task_type=data['type'],
            deadline=deadline_dt,
            reminder_days=data['reminder_days']
        )
        db.session.add(new_task)
        db.session.commit()
        return jsonify({'uzenet': 'Feladat sikeresen mentve!'}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Hiba a feladat hozzáadásakor: {e}")
        return jsonify({'hiba': f'Hiba a feladat mentésekor. Ellenőrizd a dátum formátumot. {e}'}), 400

@app.route('/tasks/<public_id>', methods=['GET'])
def get_tasks(public_id):
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    # Feladatok lekérdezése határidő szerint rendezve
    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.deadline).all()
    
    result = []
    for task in tasks:
        task_data = {}
        task_data['id'] = task.id
        task_data['title'] = task.title
        task_data['description'] = task.description
        task_data['type'] = task.task_type
        # Dátum ISO formátumban
        task_data['deadline'] = task.deadline.isoformat() 
        task_data['reminder_days'] = task.reminder_days
        result.append(task_data)
        
    return jsonify(result)

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    # task_id-t a Task modell ID-je alapján keressük, ami integer
    task = Task.query.filter_by(id=task_id).first()

    if not task:
        return jsonify({'hiba': 'A feladat nem található.'}), 404

    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'uzenet': 'Feladat sikeresen törölve!'}), 200
    except:
        db.session.rollback()
        return jsonify({'hiba': 'Hiba történt a törlés során.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
