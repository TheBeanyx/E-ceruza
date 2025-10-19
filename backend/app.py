from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
import datetime
import re # Reguláris kifejezések az email ellenőrzéshez

from users import regisztral_felhasznalo, bejelentkezes_felhasznalo, get_user_by_id # <<< ITT VOLT AZ ImportError!

# ----------------------------------------------------------------------
# 1. FLASK ALKALMAZÁS ÉS DB KONFIGURÁCIÓ
# ----------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# Konfiguráció
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tanulo_naptar.db'
app.config['SECRET_KEY'] = 'ez-egy-nagyon-hosszu-titkos-kulcs-es-feltetlenul-csereld-ki-a-sajat-todra'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app) 

# ----------------------------------------------------------------------
# 2. ADATBÁZIS MODELLEK (TÁBLÁK)
# ----------------------------------------------------------------------

class User(db.Model):
    """Felhasználók (tanulók) táblája."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False) 
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Task(db.Model):
    """Feladatok táblája."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    type = db.Column(db.String(50)) 
    deadline = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer)
    description = db.Column(db.Text)

    def to_dict(self):
        """Konvertálja a feladatot szótárrá JSON válaszhoz."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'type': self.type,
            'deadline': self.deadline.isoformat(),
            'reminder_days': self.reminder_days,
            'description': self.description
        }
        
# ----------------------------------------------------------------------
# 3. KÉZELŐK ÉS VÉGPONTOK (API ROUTES)
# ----------------------------------------------------------------------

@app.route('/register', methods=['POST'])
def register():
    """Végpont: Új felhasználó regisztrálása (email formátum és egyediség ellenőrzés)."""
    data = request.get_json()
    if not data or 'name' not in data or 'email' not in data or 'password' not in data:
        return jsonify({'hiba': 'Hiányzó adatok: teljes név, e-mail vagy jelszó.'}), 400

    full_name = data['name']
    email = data['email']
    password = data['password']

    # Server-side e-mail formátum ellenőrzés
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.fullmatch(email_regex, email):
        return jsonify({'hiba': 'Érvénytelen e-mail cím formátum.'}), 400
    
    # E-mail cím létezésének adatbázis ellenőrzése (ne regisztráljon kétszer)
    if User.query.filter_by(email=email).first():
        return jsonify({'hiba': 'Ez az e-mail cím már regisztrálva van.'}), 400

    try:
        new_user = regisztral_felhasznalo(db, User, bcrypt, full_name, email, password)
        
        return jsonify({
            'uzenet': 'Sikeres regisztráció!',
            'felhasznalonev': new_user.username,
            'user_id': new_user.id
        }), 201
    except ValueError as e:
        return jsonify({'hiba': str(e)}), 400
    except Exception as e:
        return jsonify({'hiba': f'Adatbázis hiba: {str(e)}'}), 500


@app.route('/login', methods=['POST'])
def login():
    """Végpont: Felhasználó bejelentkezése."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'hiba': 'Hiányzó adatok: felhasználónév vagy jelszó.'}), 400

    try:
        user = bejelentkezes_felhasznalo(User, bcrypt, username, password) # <<< Helyes függvényhívás!
        
        if user:
            return jsonify({
                'uzenet': 'Sikeres bejelentkezés!',
                'user_id': user.id,
                'username': user.username
            }), 200
        else:
            return jsonify({'hiba': 'Érvénytelen felhasználónév vagy jelszó.'}), 401
    except Exception as e:
        print(f"Login Error: {e}")
        return jsonify({'hiba': f'Hiba a bejelentkezés során: {str(e)}'}), 500

@app.route('/tasks', methods=['POST'])
def add_task():
    """Végpont: Új feladat hozzáadása."""
    data = request.get_json()
    
    required_fields = ['user_id', 'title', 'type', 'deadline', 'reminder_days']
    if not all(field in data for field in required_fields):
        return jsonify({'hiba': 'Hiányzó adatok.'}), 400

    try:
        deadline_dt = datetime.datetime.fromisoformat(data['deadline'])
    except ValueError:
        return jsonify({'hiba': 'Érvénytelen határidő formátum. Használd az ISO formátumot.'}), 400

    new_task = Task(
        user_id=data['user_id'],
        title=data['title'],
        type=data['type'],
        deadline=deadline_dt,
        reminder_days=data['reminder_days'],
        description=data.get('description')
    )

    db.session.add(new_task)
    db.session.commit()

    return jsonify({'uzenet': 'Feladat sikeresen hozzáadva!', 'task_id': new_task.id}), 201

@app.route('/tasks/<int:user_id>', methods=['GET'])
def get_tasks(user_id):
    """Végpont: Egy felhasználó összes feladatának lekérdezése, határidő szerint rendezve."""
    tasks = Task.query.filter_by(user_id=user_id).order_by(Task.deadline).all()
    
    if not tasks:
        return jsonify([]), 200

    return jsonify([task.to_dict() for task in tasks]), 200

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Végpont: Feladat törlése azonosító alapján."""
    task = Task.query.get(task_id)

    if not task:
        return jsonify({'hiba': 'A feladat nem található.'}), 404

    db.session.delete(task)
    db.session.commit()
    
    return jsonify({'uzenet': f'A {task_id} azonosítójú feladat sikeresen törölve.'}), 200

# ----------------------------------------------------------------------
# 4. ALKALMAZÁS INDÍTÁSA
# ----------------------------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    
    print(">>> Flask szerver indul: http://127.0.0.1:5000")
    app.run(debug=True)