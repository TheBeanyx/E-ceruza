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

# Many-to-Many (M:N) asszociációs tábla a felhasználók és csoportok között
group_members = db.Table('group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('study_group.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(100))
    tasks = db.relationship('Task', backref='owner', lazy='dynamic')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')
    # study_groups backref-et a StudyGroup modell hozza létre
    
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

class StudyGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False, unique=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Kapcsolat a User modellhez a group_members táblán keresztül
    members = db.relationship('User', secondary=group_members, lazy='dynamic',
                              backref=db.backref('study_groups', lazy='dynamic'))

    def to_dict(self, include_members=False):
        data = {
            'public_id': self.public_id,
            'name': self.name,
            # A belső creator_id-t lefordítjuk public_id-ra a kimenetben
            'creator_id': User.query.get(self.creator_id).public_id if self.creator_id else None,
            'created_at': self.created_at.isoformat()
        }
        if include_members:
            data['members'] = [
                {'username': member.username, 'public_id': member.public_id}
                for member in self.members.all()
            ]
        return data

# --- Adatbázis Létrehozása ---
with app.app_context():
    # Megpróbáljuk létrehozni a táblákat (beleértve az újakat is)
    # Ha már léteznek, ez a hívás nem csinál semmit.
    db.create_all()

# --- Útvonalak (API Endpoints) ---

# --- REGISZTRÁCIÓ és BEJELENTKEZÉS (Változatlanul hagytam) ---
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
# --- FELADAT KEZELÉS (Változatlanul hagytam) ---
# --------------------------------------------------------------------------------------------------

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

@app.route('/tasks/<public_id>', methods=['GET'])
def list_tasks(public_id):
    user = User.query.filter_by(public_id=public_id).first()
    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404

    tasks = user.tasks.order_by(Task.deadline).all() 
    
    return jsonify([task.to_dict() for task in tasks]), 200

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'hiba': 'A feladat nem található.'}), 404
    
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({'uzenet': 'Feladat sikeresen törölve.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'hiba': f'Hiba történt a törlés során: {str(e)}'}), 500

# --------------------------------------------------------------------------------------------------
# --- ÜZENET KEZELÉS (Változatlanul hagytam) ---
# --------------------------------------------------------------------------------------------------

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


# --------------------------------------------------------------------------------------------------
# --- ÚJ: TANULÓCSOPORT KEZELÉS ---
# --------------------------------------------------------------------------------------------------

# --- ÚJ CSOPORT LÉTREHOZÁSA (POST /study_groups) ---
@app.route('/study_groups', methods=['POST'])
def create_study_group():
    data = request.get_json()
    creator_public_id = data.get('creator_id') # A létrehozó public_id-ja
    group_name = data.get('name')
    member_usernames = data.get('members', []) # Opcionális: kezdeti tagok felhasználónevei

    creator = User.query.filter_by(public_id=creator_public_id).first()
    if not creator:
        return jsonify({'hiba': 'Létrehozó felhasználó nem található.'}), 404

    if not group_name:
        return jsonify({'hiba': 'Hiányzó csoportnév.'}), 400

    if StudyGroup.query.filter_by(name=group_name).first():
        return jsonify({'hiba': f'A "{group_name}" nevű csoport már létezik.'}), 409

    # 1. Csoport létrehozása
    new_group = StudyGroup(name=group_name, creator_id=creator.id)
    
    # 2. Létrehozó hozzáadása tagként
    new_group.members.append(creator)

    # 3. További tagok hozzáadása (usernames-ből belső ID-kre váltás)
    added_members = [creator.username]
    failed_members = []

    for username in member_usernames:
        if username == creator.username:
            continue
        member = User.query.filter_by(username=username).first()
        if member:
            # Csak akkor adjuk hozzá, ha még nem tagja
            if member not in new_group.members: 
                new_group.members.append(member)
                added_members.append(username)
        else:
            failed_members.append(username)

    db.session.add(new_group)
    db.session.commit()

    response = {
        'uzenet': f'Csoport sikeresen létrehozva: {group_name}',
        'group_id': new_group.public_id,
        'tagok': added_members
    }
    if failed_members:
        response['figyelmeztetes'] = f'A következő felhasználókat nem sikerült hozzáadni, mert nem léteznek: {", ".join(failed_members)}'

    return jsonify(response), 201

# --- EGY CSOPORT RÉSZLETEINEK LEKÉRDEZÉSE (GET /study_groups/<public_id>) ---
@app.route('/study_groups/<public_id>', methods=['GET'])
def get_study_group(public_id):
    group = StudyGroup.query.filter_by(public_id=public_id).first()
    if not group:
        return jsonify({'hiba': 'Tanulócsoport nem található.'}), 404
    
    # Visszaadja a tagok listáját (username és public_id formájában)
    return jsonify(group.to_dict(include_members=True)), 200

# --- CSATLAKOZÁS CSOPORTHOZ (POST /study_groups/<public_id>/join) ---
@app.route('/study_groups/<public_id>/join', methods=['POST'])
def join_study_group(public_id):
    data = request.get_json()
    user_public_id = data.get('user_id') # A csatlakozni kívánó felhasználó public_id-ja

    user = User.query.filter_by(public_id=user_public_id).first()
    group = StudyGroup.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404
    if not group:
        return jsonify({'hiba': 'Tanulócsoport nem található.'}), 404

    # Ellenőrzés, hogy a felhasználó már tag-e
    if user in group.members:
        return jsonify({'uzenet': 'A felhasználó már tagja a csoportnak.'}), 200
    
    group.members.append(user)
    db.session.commit()
    return jsonify({'uzenet': f'A felhasználó ({user.username}) sikeresen csatlakozott a csoporthoz: {group.name}'}), 200

# --- CSOPORT ELHAGYÁSA (POST /study_groups/<public_id>/leave) ---
@app.route('/study_groups/<public_id>/leave', methods=['POST'])
def leave_study_group(public_id):
    data = request.get_json()
    user_public_id = data.get('user_id') # A távozó felhasználó public_id-ja

    user = User.query.filter_by(public_id=user_public_id).first()
    group = StudyGroup.query.filter_by(public_id=public_id).first()

    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404
    if not group:
        return jsonify({'hiba': 'Tanulócsoport nem található.'}), 404
    
    # Ellenőrzés, hogy a felhasználó tag-e
    if user not in group.members:
        return jsonify({'uzenet': 'A felhasználó nem tagja ennek a csoportnak.'}), 200

    # Eltávolítás a members listából
    group.members.remove(user)
    db.session.commit()

    return jsonify({'uzenet': f'A felhasználó ({user.username}) sikeresen elhagyta a csoportot: {group.name}'}), 200

# --- FELHASZNÁLÓ CSOPORTJAINAK LISTÁZÁSA (GET /study_groups/user/<user_public_id>) ---
@app.route('/study_groups/user/<user_public_id>', methods=['GET'])
def list_user_groups(user_public_id):
    user = User.query.filter_by(public_id=user_public_id).first()
    if not user:
        return jsonify({'hiba': 'Felhasználó nem található.'}), 404

    # Lekéri az összes csoportot, aminek a felhasználó tagja
    groups = user.study_groups.all()

    return jsonify([group.to_dict() for group in groups]), 200


# --- Szerver indítása ---
if __name__ == '__main__':
    app.run(debug=True)
