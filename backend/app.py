import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import uuid
from datetime import datetime
import random 

# --- Inicializáció ---
app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tanulo_naptar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Adatbázis Modellek ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False) # Teljes név
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False) # Felhasználónév
    password_hash = db.Column(db.String(256), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user_submitted', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    task_type = db.Column(db.String(50), nullable=False) 
    deadline = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer, default=0)

# ÚJ MODELL: Visszajelzések és Kérdőívek tárolására
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Kitöltő user ID-je (ha be volt jelentkezve)
    username = db.Column(db.String(50), nullable=True) # Kitöltő felhasználóneve
    type = db.Column(db.String(50), nullable=False) # 'Bug' vagy 'Satisfaction'
    content = db.Column(db.Text, nullable=False) # Leírás / Megjegyzések
    rating = db.Column(db.Integer, nullable=True) # Értékelés (1-5)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) # Kitöltés időpontja
    
# --- Munkamenet kezelés: Adatbázis létrehozása és Admin felhasználó ---
with app.app_context():
    db.create_all()
    
    # JAVÍTVA: Admin felhasználónév ékezetesen
    ADMIN_USERNAME = 'buzás_benedek' 
    ADMIN_PASSWORD = 'Benedek11'
    
    if not User.query.filter_by(username=ADMIN_USERNAME).first():
        print(f"--- Admin user '{ADMIN_USERNAME}' creation initiated. ---")
        hashed_admin_password = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
        admin_user = User(
            public_id=str(uuid.uuid4()),
            name="Buzás Benedek (ADMIN)",
            email="admin@e-ceruza.hu",
            username=ADMIN_USERNAME,
            password_hash=hashed_admin_password
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"--- Admin user '{ADMIN_USERNAME}' created successfully. ---")

# --- Útvonalak (API Endpoints) ---

# REGISZTRÁCIÓ (változatlan a korábbi javítás óta)
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    full_name = data['name'].strip()
    name_parts = full_name.lower().split()
    
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1] 
    elif len(name_parts) == 1:
        first_name = name_parts[0]
        last_name = "user"
    else:
        first_name = "uj"
        last_name = "felhasznalo"
        
    # Kisbetűs, ékezetes felhasználónév alapja
    base_username_str = f"{first_name}_{last_name}"
    username = base_username_str
    
    while User.query.filter_by(username=username).first():
        random_number = random.randint(10, 99) 
        username = f"{base_username_str}{random_number}"

    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(
        public_id=str(uuid.uuid4()),
        name=full_name,
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
        return jsonify({'hiba': 'Az e-mail cím már használatban van.'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'hiba': 'Érvénytelen felhasználónév vagy jelszó'}), 401
    
    # Admin jogosultság ellenőrzése az ékezetes felhasználónévvel
    is_admin = (username == ADMIN_USERNAME) 

    return jsonify({
        'uzenet': 'Sikeres bejelentkezés',
        'user_id': user.public_id,
        'username': user.username,
        'name': user.name,
        'is_admin': is_admin
    }), 200

# --- FELHASZNÁLÓ FRISSÍTÉSE ---
@app.route('/user/update', methods=['PUT'])
def update_user():
    data = request.get_json()
    public_id = data.get('user_id')
    
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    try:
        if 'new_name' in data and data['new_name'].strip():
            user.name = data['new_name'].strip()
        
        if 'new_password' in data and data['new_password']:
            if len(data['new_password']) < 6:
                 return jsonify({'hiba': 'A jelszónak legalább 6 karakter hosszúnak kell lennie.'}), 400
            user.password_hash = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')

        db.session.commit()
        return jsonify({'uzenet': 'Sikeres módosítás!', 'new_name': user.name}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Hiba a felhasználó frissítésekor: {e}")
        return jsonify({'hiba': 'Hiba történt a felhasználói adatok frissítésekor.'}), 500

# --- FEEDBACK / KÉRDŐÍV ÚTVONALAK ---

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    
    public_id = data.get('user_id')
    user = User.query.filter_by(public_id=public_id).first() if public_id else None
    
    try:
        new_feedback = Feedback(
            user_id=user.id if user else None,
            username=user.username if user else 'Anonymous',
            type=data['type'], # 'Bug' vagy 'Satisfaction'
            content=data['content'],
            rating=data.get('rating') # Lehet None (pl. Bug esetén)
        )
        db.session.add(new_feedback)
        db.session.commit()
        return jsonify({'uzenet': 'Visszajelzés sikeresen rögzítve! Köszönjük a segítséged!'}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Hiba a feedback mentésekor: {e}")
        return jsonify({'hiba': 'Hiba történt a visszajelzés rögzítésekor.'}), 400

@app.route('/feedback/all', methods=['GET'])
def get_all_feedback():
    public_id = request.args.get('user_id')
    
    # Admin jogosultság ellenőrzése
    user = User.query.filter_by(public_id=public_id).first()
    if not user or user.username != ADMIN_USERNAME: # JAVÍTVA: ADMIN_USERNAME használata
        return jsonify({'hiba': 'Nincs jogosultság a válaszok megtekintéséhez.'}), 403

    feedbacks = Feedback.query.order_by(Feedback.timestamp.desc()).all()
    
    result = []
    for f in feedbacks:
        result.append({
            'id': f.id,
            'type': f.type,
            'user': f.username,
            'content': f.content,
            'rating': f.rating,
            'timestamp': f.timestamp.isoformat()
        })
        
    return jsonify(result)


# FELADAT ÚTVONALAK (Változatlanul hagyva)
@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    public_id = data.get('user_id')
    
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    try:
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

    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.deadline).all()
    
    result = []
    for task in tasks:
        task_data = {}
        task_data['id'] = task.id
        task_data['title'] = task.title
        task_data['description'] = task.description
        task_data['type'] = task.task_type
        task_data['deadline'] = task.deadline.isoformat() 
        task_data['reminder_days'] = task.reminder_days
        result.append(task_data)
        
    return jsonify(result)

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id).first()

    if not task:
        return jsonify({'hiba': 'A feladat nem található.'}), 404

    try:
        db.session.delete(task)
        db.session.commit()
      import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import uuid
from datetime import datetime
import random 

# --- Inicializáció ---
app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tanulo_naptar.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# --- Adatbázis Modellek ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False) # Teljes név
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False) # Felhasználónév
    password_hash = db.Column(db.String(256), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user_submitted', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    task_type = db.Column(db.String(50), nullable=False) 
    deadline = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer, default=0)

# ÚJ MODELL: Visszajelzések és Kérdőívek tárolására
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Kitöltő user ID-je (ha be volt jelentkezve)
    username = db.Column(db.String(50), nullable=True) # Kitöltő felhasználóneve
    type = db.Column(db.String(50), nullable=False) # 'Bug' vagy 'Satisfaction'
    content = db.Column(db.Text, nullable=False) # Leírás / Megjegyzések
    rating = db.Column(db.Integer, nullable=True) # Értékelés (1-5)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow) # Kitöltés időpontja
    
# --- Munkamenet kezelés: Adatbázis létrehozása és Admin felhasználó ---
with app.app_context():
    db.create_all()
    
    # JAVÍTVA: Admin felhasználónév ékezetesen
    ADMIN_USERNAME = 'buzás_benedek' 
    ADMIN_PASSWORD = 'Benedek11'
    
    if not User.query.filter_by(username=ADMIN_USERNAME).first():
        print(f"--- Admin user '{ADMIN_USERNAME}' creation initiated. ---")
        hashed_admin_password = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
        admin_user = User(
            public_id=str(uuid.uuid4()),
            name="Buzás Benedek (ADMIN)",
            email="admin@e-ceruza.hu",
            username=ADMIN_USERNAME,
            password_hash=hashed_admin_password
        )
        db.session.add(admin_user)
        db.session.commit()
        print(f"--- Admin user '{ADMIN_USERNAME}' created successfully. ---")

# --- Útvonalak (API Endpoints) ---

# REGISZTRÁCIÓ (változatlan a korábbi javítás óta)
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    full_name = data['name'].strip()
    name_parts = full_name.lower().split()
    
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1] 
    elif len(name_parts) == 1:
        first_name = name_parts[0]
        last_name = "user"
    else:
        first_name = "uj"
        last_name = "felhasznalo"
        
    # Kisbetűs, ékezetes felhasználónév alapja
    base_username_str = f"{first_name}_{last_name}"
    username = base_username_str
    
    while User.query.filter_by(username=username).first():
        random_number = random.randint(10, 99) 
        username = f"{base_username_str}{random_number}"

    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(
        public_id=str(uuid.uuid4()),
        name=full_name,
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
        return jsonify({'hiba': 'Az e-mail cím már használatban van.'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'hiba': 'Érvénytelen felhasználónév vagy jelszó'}), 401
    
    # Admin jogosultság ellenőrzése az ékezetes felhasználónévvel
    is_admin = (username == ADMIN_USERNAME) 

    return jsonify({
        'uzenet': 'Sikeres bejelentkezés',
        'user_id': user.public_id,
        'username': user.username,
        'name': user.name,
        'is_admin': is_admin
    }), 200

# --- FELHASZNÁLÓ FRISSÍTÉSE ---
@app.route('/user/update', methods=['PUT'])
def update_user():
    data = request.get_json()
    public_id = data.get('user_id')
    
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    try:
        if 'new_name' in data and data['new_name'].strip():
            user.name = data['new_name'].strip()
        
        if 'new_password' in data and data['new_password']:
            if len(data['new_password']) < 6:
                 return jsonify({'hiba': 'A jelszónak legalább 6 karakter hosszúnak kell lennie.'}), 400
            user.password_hash = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')

        db.session.commit()
        return jsonify({'uzenet': 'Sikeres módosítás!', 'new_name': user.name}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Hiba a felhasználó frissítésekor: {e}")
        return jsonify({'hiba': 'Hiba történt a felhasználói adatok frissítésekor.'}), 500

# --- FEEDBACK / KÉRDŐÍV ÚTVONALAK ---

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    
    public_id = data.get('user_id')
    user = User.query.filter_by(public_id=public_id).first() if public_id else None
    
    try:
        new_feedback = Feedback(
            user_id=user.id if user else None,
            username=user.username if user else 'Anonymous',
            type=data['type'], # 'Bug' vagy 'Satisfaction'
            content=data['content'],
            rating=data.get('rating') # Lehet None (pl. Bug esetén)
        )
        db.session.add(new_feedback)
        db.session.commit()
        return jsonify({'uzenet': 'Visszajelzés sikeresen rögzítve! Köszönjük a segítséged!'}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Hiba a feedback mentésekor: {e}")
        return jsonify({'hiba': 'Hiba történt a visszajelzés rögzítésekor.'}), 400

@app.route('/feedback/all', methods=['GET'])
def get_all_feedback():
    public_id = request.args.get('user_id')
    
    # Admin jogosultság ellenőrzése
    user = User.query.filter_by(public_id=public_id).first()
    if not user or user.username != ADMIN_USERNAME: # JAVÍTVA: ADMIN_USERNAME használata
        return jsonify({'hiba': 'Nincs jogosultság a válaszok megtekintéséhez.'}), 403

    feedbacks = Feedback.query.order_by(Feedback.timestamp.desc()).all()
    
    result = []
    for f in feedbacks:
        result.append({
            'id': f.id,
            'type': f.type,
            'user': f.username,
            'content': f.content,
            'rating': f.rating,
            'timestamp': f.timestamp.isoformat()
        })
        
    return jsonify(result)


# FELADAT ÚTVONALAK (Változatlanul hagyva)
@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    public_id = data.get('user_id')
    
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404

    try:
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

    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.deadline).all()
    
    result = []
    for task in tasks:
        task_data = {}
        task_data['id'] = task.id
        task_data['title'] = task.title
        task_data['description'] = task.description
        task_data['type'] = task.task_type
        task_data['deadline'] = task.deadline.isoformat() 
        task_data['reminder_days'] = task.reminder_days
        result.append(task_data)
        
    return jsonify(result)

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
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

