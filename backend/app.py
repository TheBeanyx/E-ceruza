from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime

# --- Konfiguráció ---
app = Flask(__name__)
# Itt beállíthatod a titkos kulcsot a session kezeléshez
app.config['SECRET_KEY'] = 'a_nagyon_hosszu_es_titkos_kulcs' 
# SQLite adatbázis beállítása
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///e_ceruza.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app) # Engedélyezi a Cross-Origin kéréseket a frontend számára

# --- Adatbázis Modellek (Táblák) ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100))
    tasks = db.relationship('Task', backref='owner', lazy='dynamic')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50)) # Pl. Dolgozat, Házifeladat, Beadandó feladat, Egyéb feljegyzések
    deadline = db.Column(db.DateTime, nullable=False)
    reminder_days = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    online_link = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.owner.public_id,
            'title': self.title,
            'type': self.type,
            'deadline': self.deadline.isoformat(),
            'reminder_days': self.reminder_days,
            'description': self.description,
            'online_link': self.online_link
        }
        
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- Adatbázis Létrehozása ---
with app.app_context():
    db.create_all()

# --- Útvonalak (API Endpoints) ---

# --- REGISZTRÁCIÓ ---
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')

    if not username or not password or not full_name:
        return jsonify({'hiba': 'Hiányzó felhasználónév, jelszó vagy teljes név.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'hiba': 'Ez a felhasználónév már foglalt.'}), 409

    new_user = User(username=username, full_name=full_name)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        'uzenet': 'Sikeres regisztráció!', 
        'user_id': new_user.public_id,
        'username': new_user.username
    }), 201

# --- BEJELENTKEZÉS ---
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({'hiba': 'Érvénytelen felhasználónév vagy jelszó.'}), 401

    return jsonify({
        'uzenet': 'Sikeres bejelentkezés!',
        'user_id': user.public_id,
        'username': user.username,
        'full_name': user.full_name
    }), 200

# --------------------------------------------------------------------------------------------------
# --- FELADAT KEZELÉS ---
# --------------------------------------------------------------------------------------------------

# --- ÚJ FELADAT LÉTREHOZÁSA ---
@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    user_public_id = data.get('user_id')
    title = data.get('title')
    deadline_str = data.get('deadline')
    
    user = User.query.filter_by(public_id=user_public_id).first()
    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404

    if not all([title, deadline_str]):
        return jsonify({'hiba': 'Hiányzó mezők: cím, határidő.'}), 400

    try:
        deadline = datetime.datetime.fromisoformat(deadline_str)
    except ValueError:
        return jsonify({'hiba': 'Érvénytelen határidő formátum.'}), 400
    
    # Ha a határidő a múltban van (csak egy egyszerű ellenőrzés)
    if deadline < datetime.datetime.utcnow():
        return jsonify({'hiba': 'A határidő nem lehet a múltban.'}), 400

    new_task = Task(
        user_id=user.id,
        title=title,
        type=data.get('type', 'Egyéb feljegyzések'),
        deadline=deadline,
        reminder_days=data.get('reminder_days', 0),
        description=data.get('description')
    )

    db.session.add(new_task)
    db.session.commit()
    return jsonify({'uzenet': 'A feladat sikeresen létrehozva!', 'task_id': new_task.id}), 201

# --- FELADATOK LISTÁZÁSA FELHASZNÁLÓNKÉNT ---
@app.route('/tasks/<public_id>', methods=['GET'])
def list_tasks(public_id):
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404

    tasks = user.tasks.order_by(Task.deadline).all() # Rendezés határidő szerint
    
    return jsonify([task.to_dict() for task in tasks]), 200

# --- FELADAT TÖRLÉSE ---
@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'hiba': 'A feladat nem található.'}), 404

    # JÓ GYAKORLAT: Ellenőrizd, hogy a törlést kérő felhasználó tulajdonosa-e a feladatnak.
    # Ezt a frontend most nem küldi, de a public_id-t le lehetne kérni a headerekből.
    
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'uzenet': 'Feladat sikeresen törölve.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'hiba': f'Hiba történt a törlés során: {str(e)}'}), 500

# --------------------------------------------------------------------------------------------------
# --- ÜZENET KEZELÉS (CHAT) ---
# --------------------------------------------------------------------------------------------------

# --- ÜZENET KÜLDÉSE ---
@app.route('/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    sender_public_id = data.get('sender_id')
    recipient_username = data.get('recipient_username')
    content = data.get('content')

    sender = User.query.filter_by(public_id=sender_public_id).first()
    recipient = User.query.filter_by(username=recipient_username).first()

    if not sender:
        return jsonify({'hiba': 'Érvénytelen feladó ID.'}), 400

    if not recipient:
        return jsonify({'hiba': f'A címzett felhasználónév ("{recipient_username}") nem létezik.'}), 404

    if sender.id == recipient.id:
        return jsonify({'hiba': 'Nem küldhetsz üzenetet saját magadnak.'}), 400

    if not content:
        return jsonify({'hiba': 'Az üzenet tartalma hiányzik.'}), 400

    new_message = Message(
        sender_id=sender.id,
        recipient_id=recipient.id,
        content=content,
        timestamp=datetime.datetime.utcnow()
    )

    db.session.add(new_message)
    db.session.commit()
    
    return jsonify({'uzenet': f'Üzenet sikeresen elküldve a felhasználónak: {recipient_username}'}), 201

# --- ÖSSZES ÜZENET LEKÉRDEZÉSE (ELŐZMÉNYEK) ---
# Ezt az útvonalat módosítottuk, hogy a küldött és fogadott üzeneteket is visszaadja.
@app.route('/messages/<public_id>', methods=['GET'])
def get_messages(public_id):
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'A felhasználó nem található.'}), 404
    
    user_id = user.id

    # 1. Lekérdezés: Üzenetek, ahol a user a CÍMZETT (received_messages)
    received_messages = db.session.query(
        Message.id, Message.content, Message.timestamp, 
        User.username.label('sender_username')
    ).join(User, Message.sender_id == User.id
    ).filter(Message.recipient_id == user_id
    ).all()

    # 2. Lekérdezés: Üzenetek, ahol a user a FELADÓ (sent_messages)
    sent_messages = db.session.query(
        Message.id, Message.content, Message.timestamp, 
        User.username.label('recipient_username') 
    ).join(User, Message.recipient_id == User.id
    ).filter(Message.sender_id == user_id
    ).all()
    
    output = []
    
    # Fogadott üzenetek formázása
    for message_id, content, timestamp, sender_username in received_messages:
        output.append({
            "id": message_id,
            "sender_username": sender_username,
            "recipient_username": user.username, 
            "content": content,
            "timestamp": timestamp.isoformat(),
            "is_sent_by_me": False # Fontos jelzés a frontendnek: BEJÖVŐ
        })
        
    # Küldött üzenetek formázása
    for message_id, content, timestamp, recipient_username in sent_messages:
        output.append({
            "id": message_id,
            "sender_username": user.username, 
            "recipient_username": recipient_username,
            "content": content,
            "timestamp": timestamp.isoformat(),
            "is_sent_by_me": True # Fontos jelzés a frontendnek: KÜLDÖTT
        })

    # Rendezés időbélyeg szerint
    output.sort(key=lambda x: x['timestamp'])

    return jsonify(output), 200

# --- ÜZENET TÖRLÉSE (Olvasottnak Jelölés) ---
# Ez a funkció csak a bejövő üzeneteket érinti, a küldött üzeneteket megőrizzük.
@app.route('/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    message = Message.query.get(message_id)

    if not message:
        return jsonify({'hiba': 'Az üzenet nem található.'}), 404

    try:
        db.session.delete(message)
        db.session.commit()
        return jsonify({'uzenet': 'Üzenet sikeresen törölve (olvasottnak jelölve).'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'hiba': f'Hiba történt a törlés során: {str(e)}'}), 500


# --- Szerver indítása ---
if __name__ == '__main__':
    app.run(debug=True)