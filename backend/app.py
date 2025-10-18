from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import datetime
from users import regisztral_felhasznalo # Importáljuk a felhasználókezelő modult

app = Flask(__name__)
# Konfiguráció: SQLite adatbázis fájlként tárolva a tanulo_naptar.db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tanulo_naptar.db'
app.config['SECRET_KEY'] = 'ez_egy_nagyon_hosszu_titkos_kulcs_es_feltetlenul_csereld_ki_a_sajatodra' 

db = SQLAlchemy(app)
bcrypt = Bcrypt(app) # Jelszó titkosító inicializálása

# -----------------
# 1. Adatbázis Modellek (Táblák)
# -----------------

class User(db.Model):
    """Felhasználók (tanulók) táblája."""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False) # A generált felhasználónév
    password_hash = db.Column(db.String(120), nullable=False) # Titkosított jelszó
    # Kapcsolat a feladatokkal (Task)
    tasks = db.relationship('Task', backref='owner', lazy=True)

class Task(db.Model):
    """Dolgozatok, házifeladatok, beadandók táblája."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # Tulajdonos
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False) # 'Dolgozat', 'Házi', 'Beadandó'
    deadline = db.Column(db.DateTime, nullable=False) 
    reminder_days = db.Column(db.Integer, default=1) # Hány nappal előtte jelezzen
    description = db.Column(db.Text)
    
class SharedTask(db.Model):
    """Köztes tábla a feladatok megosztásához felhasználók között."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# -----------------
# 2. API ÚTVONALAK (Végpontok)
# -----------------

@app.route('/register', methods=['POST'])
def register():
    """Új felhasználó regisztrálása: generálja a felhasználónevet és hasheli a jelszót."""
    data = request.get_json()
    nev = data.get('name')
    jelszo = data.get('password')

    if not nev or not jelszo:
        return jsonify({"hiba": "Hiányzó név vagy jelszó."}), 400

    eredmeny = regisztral_felhasznalo(nev, jelszo, db, User, bcrypt)
    
    if isinstance(eredmeny, User):
        return jsonify({
            "uzenet": "Sikeres regisztráció!",
            "felhasznalonev": eredmeny.username
        }), 201
    else:
        return jsonify(eredmeny), eredmeny[1]

@app.route('/login', methods=['POST'])
def login():
    """Felhasználó bejelentkezése."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    # Ellenőrzés: létezik a felhasználó ÉS egyezik a titkosított jelszó a megadottal
    if user and bcrypt.check_password_hash(user.password_hash, password):
        # Sikeres bejelentkezés
        return jsonify({
            "uzenet": "Sikeres bejelentkezés!",
            "user_id": user.id, 
            "username": user.username
        }), 200
    else:
        return jsonify({"hiba": "Érvénytelen felhasználónév vagy jelszó."}), 401

@app.route('/tasks', methods=['POST'])
def add_task():
    """Új feladat hozzáadása a naptárhoz."""
    data = request.get_json()
    
    # A 'user_id' a bejelentkezéskor kapott azonosító
    user_id = data.get('user_id') 
    
    if not user_id or not User.query.get(user_id):
        return jsonify({"hiba": "Érvénytelen felhasználó."}), 401

    try:
        new_task = Task(
            user_id=user_id,
            title=data['title'],
            type=data['type'],
            # A határidőt YYYY-MM-DDTHH:MM:SS formátumban várjuk
            deadline=datetime.datetime.strptime(data['deadline'], '%Y-%m-%dT%H:%M:%S'), 
            reminder_days=data.get('reminder_days', 1),
            description=data.get('description')
        )
        db.session.add(new_task)
        db.session.commit()
        return jsonify({"uzenet": "Feladat sikeresen hozzáadva!"}), 201
    except Exception as e:
        return jsonify({"hiba": f"Hiba történt a feladat mentésekor: {e}"}), 400

# ----------------------------------------------------
# ÚJ API VÉGPONTOK A FELADATOK LEKÉRÉSÉRE ÉS TÖRLÉSÉRE
# ----------------------------------------------------

@app.route('/tasks/<int:user_id>', methods=['GET'])
def get_user_tasks(user_id):
    """Lekéri egy adott felhasználóhoz tartozó ÖSSZES feladatot."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"hiba": "Felhasználó nem található."}), 404

    # Lekérdezzük az összes feladatot az adott user_id-hoz
    tasks = Task.query.filter_by(user_id=user_id).all()
    
    tasks_list = []
    for task in tasks:
        tasks_list.append({
            "id": task.id,
            "title": task.title,
            "type": task.type,
            # Az időt stringként adjuk vissza a JSON-ban
            "deadline": task.deadline.isoformat(), 
            "reminder_days": task.reminder_days,
            "description": task.description
        })
        
    return jsonify(tasks_list), 200

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Töröl egy feladatot az azonosítója alapján."""
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({"hiba": "Feladat nem található."}), 404
        
    db.session.delete(task)
    db.session.commit()
    
    return jsonify({"uzenet": f"Feladat (ID: {task_id}) sikeresen törölve."}), 200


if __name__ == '__main__':
    # Adatbázis inicializálása és táblák létrehozása az indítás előtt
    with app.app_context():
        db.create_all()
    print(">>> Flask szerver indul: http://127.0.0.1:5000")
    app.run(debug=True)