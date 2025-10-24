from flask import Flask, jsonify, request, make_response
from flask_cors import CORS, cross_origin
import uuid
from datetime import datetime
import json 
from users import regisztral_felhasznalo, bejelentkezes_felhasznalo 
from flask_sqlalchemy import SQLAlchemy 
from flask_bcrypt import Bcrypt 

app = Flask(__name__)
CORS(app) 

# --------------------------
# ADATBÁZIS KONFIGURÁCIÓ (SQLAlchemy)
# --------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e_ceruza.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'ez_egy_nagyon_eros_titkos_kulcs_es_nagyon_fontos_a_biztonsaghoz'

db = SQLAlchemy(app) 
bcrypt = Bcrypt(app) 

# --------------------------
# ADATBÁZIS MODELL (User) - FIGYELD AZ EMAIL OSZLOPOT
# --------------------------
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False) # <--- Ezt keresi
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

# --------------------------
# IN-MEMORY "ADATBÁZIS" TÁROLÓK
# --------------------------
groups = {}
group_members = {} 
tasks = {}
messages = {}

# --------------------------
# SEGÉDFÜGGVÉNYEK
# --------------------------

def get_tasks_by_group(group_id):
    """Visszaadja egy adott csoporthoz (group_id) tartozó feladatokat."""
    return [task for task in tasks.values() if task.get('group_id') == group_id]

# --------------------------
# FELHASZNÁLÓ KEZELÉS (USER/AUTH)
# --------------------------

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')

    if not all([name, email, password]):
        return jsonify({"hiba": "Hiányzó adatok (név, e-mail vagy jelszó). "}), 400

    try:
        # DB-ből ellenőrizzük, létezik-e már az e-mail
        if User.query.filter_by(email=email).first():
            return jsonify({"hiba": "Ez az e-mail cím már regisztrálva van. "}), 409
        
        new_user = regisztral_felhasznalo(db, User, bcrypt, name, email, password)

        return jsonify({
            "uzenet": "Sikeres regisztráció!",
            "felhasznalonev": new_user.username
        }), 201

    except ValueError as e:
        return jsonify({"hiba": str(e)}), 400
    except Exception as e:
        print(f"Hiba regisztráció közben: {e}")
        return jsonify({"hiba": "Szerverhiba történt a regisztráció közben. "}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({"hiba": "Hiányzó adatok (felhasználónév vagy jelszó). "}), 400

    user = bejelentkezes_felhasznalo(User, bcrypt, username, password)

    if user:
        return jsonify({
            "uzenet": "Sikeres bejelentkezés!",
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name
        }), 200
    else:
        return jsonify({"hiba": "Érvénytelen felhasználónév vagy jelszó. "}), 401

# --------------------------
# CSOPORT KEZELÉS (GROUP)
# --------------------------

@app.route('/groups', methods=['POST'])
def create_group():
    data = request.json
    group_id = str(uuid.uuid4())
    
    # Ellenőrzés: A felhasználó létezik-e a DB-ben
    creator = User.query.filter_by(id=data.get('creator_id')).first() # <--- Itt történik a hiba a régi DB-vel
    if not creator:
        return jsonify({"hiba": "A csoport létrehozásához érvényes felhasználói azonosító szükséges. "}), 400

    new_group = {
        'id': group_id,
        'name': data.get('name'),
        'description': data.get('description', 'Nincs leírás megadva.'),
        'creator_id': creator.id,
        'creator_username': creator.username,
        'members': [creator.id]
    }
    
    groups[group_id] = new_group
    group_members[group_id] = [creator.id]

    return jsonify({"uzenet": "Csoport sikeresen létrehozva.", "group_id": group_id}), 201

@app.route('/groups/user/<user_id>', methods=['GET'])
def get_user_groups(user_id):
    user_groups = [group for group in groups.values() if user_id in group.get('members', [])]
    return jsonify(user_groups), 200

@app.route('/groups/<group_id>', methods=['DELETE'])
def delete_group(group_id):
    if group_id in groups:
        del groups[group_id]
        if group_id in group_members:
            del group_members[group_id]
        
        tasks_to_delete = [task_id for task_id, task in tasks.items() if task.get('group_id') == group_id]
        for task_id in tasks_to_delete:
            del tasks[task_id]
            
        return jsonify({"uzenet": "Csoport sikeresen törölve."}), 200
    return jsonify({"hiba": "Csoport nem található."}), 404

@app.route('/groups/<group_id>/join', methods=['POST'])
def join_group(group_id):
    data = request.json
    username = data.get('username')
    
    user_to_join = User.query.filter_by(username=username).first()

    if group_id not in groups:
        return jsonify({"hiba": "Csoport nem található. "}), 404
        
    if not user_to_join:
        return jsonify({"hiba": "Felhasználó nem található. "}), 404
        
    if user_to_join.id in groups[group_id]['members']:
         return jsonify({"uzenet": "A felhasználó már tagja a csoportnak. "}), 200 
         
    groups[group_id]['members'].append(user_to_join.id)
    group_members[group_id].append(user_to_join.id)
    
    return jsonify({"uzenet": f"Sikeresen csatlakoztál a(z) {groups[group_id]['name']} csoporthoz!"}), 200

# --------------------------
# FELADAT KEZELÉS (TASK)
# --------------------------

@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.json
    task_id = str(uuid.uuid4())
    
    group_id = data.get('group_id')
    
    creator = User.query.filter_by(id=data.get('creator_id')).first()
    if not creator:
        return jsonify({"hiba": "A feladat hozzáadásához érvényes felhasználói azonosító (creator_id) szükséges. "}), 400

    new_task = {
        'id': task_id,
        'group_id': group_id, 
        'title': data.get('title'),
        'type': data.get('type'),
        'deadline': data.get('deadline'),
        'reminder_days': data.get('reminder_days'),
        'description': data.get('description'),
        'online_link': data.get('online_link'),
        'creator_id': creator.id
    }
    
    tasks[task_id] = new_task
    
    return jsonify({"uzenet": "Feladat sikeresen hozzáadva.", "task_id": task_id}), 201

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    if task_id in tasks:
        del tasks[task_id]
        return jsonify({"uzenet": "Feladat sikeresen törölve."}), 200
    return jsonify({"hiba": "Feladat nem található."}), 404

@app.route('/tasks/group/<group_id>', methods=['GET'])
def get_group_tasks(group_id):
    found_tasks = get_tasks_by_group(group_id)
    return jsonify(found_tasks), 200

@app.route('/tasks/<user_id>', methods=['GET'])
def get_user_personal_tasks(user_id):
    found_tasks = get_tasks_by_group(None)
    personal_tasks = [task for task in found_tasks if task.get('creator_id') == user_id]
    return jsonify(personal_tasks), 200

# --------------------------
# ÜZENET KEZELÉS (MESSAGE)
# --------------------------

@app.route('/messages', methods=['POST'])
def send_message():
    data = request.json
    sender_id = data.get('sender_id')
    recipient_username = data.get('recipient_username')
    content = data.get('content')
    message_id = str(uuid.uuid4())
    
    recipient = User.query.filter_by(username=recipient_username).first()
    
    if not recipient:
        return jsonify({"hiba": "A címzett felhasználó nem található. "}), 404

    sender = User.query.filter_by(id=sender_id).first()
    if not sender:
        return jsonify({"hiba": "A feladó felhasználó nem található. "}), 400

    new_message = {
        "id": message_id,
        "sender_id": sender_id,
        "recipient_id": recipient.id,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "is_read": False
    }

    messages[message_id] = new_message
    
    return jsonify({"uzenet": "Üzenet sikeresen elküldve!"}), 201

@app.route('/messages/<user_id>', methods=['GET'])
def get_user_messages(user_id):
    user_messages = []
    
    db_users = User.query.all()
    user_lookup = {u.id: u.username for u in db_users}

    for msg in messages.values():
        if msg['sender_id'] == user_id or msg['recipient_id'] == user_id:
            is_sent_by_me = msg['sender_id'] == user_id
            
            sender_username = user_lookup.get(msg['sender_id'], 'Ismeretlen')
            recipient_username = user_lookup.get(msg['recipient_id'], 'Ismeretlen')
            
            user_messages.append({
                "id": msg['id'],
                "content": msg['content'],
                "timestamp": msg['timestamp'],
                "is_read": msg['is_read'],
                "is_sent_by_me": is_sent_by_me,
                "sender_username": sender_username,
                "recipient_username": recipient_username
            })
    
    user_messages.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify(user_messages), 200

@app.route('/messages/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    if message_id in messages:
        del messages[message_id] 
        return jsonify({"uzenet": "Üzenet olvasottnak jelölve (törölve az in-memory DB-ből). "}), 200
        
    return jsonify({"hiba": "Üzenet nem található."}), 404

# --------------------------
# ALKALMAZÁS INDÍTÁSA
# --------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Az adatbázis táblák ellenőrizve és létrehozva (ha szükséges).")

    app.run(debug=True)