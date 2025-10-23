from flask import Flask, jsonify, request, make_response
from flask_cors import CORS, cross_origin
import uuid
from datetime import datetime
import json # Kellhet, ha komplexebb struktúrákat tárolunk stringként

app = Flask(__name__)
# A CORS engedélyezése az összes útvonalra. Ez kezeli a Cross-Origin kéréseket.
CORS(app) 

# In-memory "adatbázis" tárolók
# FIGYELEM: Újraindításkor ezek az adatok elvesznek!
users = {}
groups = {}
group_members = {} # group_id: [user_id, user_id, ...]
tasks = {}
messages = {}

# --------------------------
# SEGÉDFÜGGVÉNYEK
# --------------------------

def get_tasks_by_group(group_id):
    """Visszaadja egy adott csoporthoz (group_id) tartozó feladatokat. 
    A group_id=None a személyes feladatokat jelenti.
    """
    # A group_id lehet string vagy None (ha a kliens 'null'-t küld, az None-ként érkezik be)
    return [task for task in tasks.values() if task.get('group_id') == group_id]

# --------------------------
# FELHASZNÁLÓ KEZELÉS (USER/AUTH)
# --------------------------

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')

    if not username or not password or not full_name:
        return jsonify({"hiba": "Hiányzó felhasználónév, jelszó vagy teljes név."}), 400

    # Ellenőrzi, hogy a felhasználónév foglalt-e
    if username in [u['username'] for u in users.values()]:
        return jsonify({"hiba": "Ez a felhasználónév már foglalt."}), 409

    user_id = str(uuid.uuid4())
    users[user_id] = {
        "id": user_id,
        "username": username,
        "password": password,  # Éles környezetben hashelve kellene tárolni!
        "full_name": full_name
    }

    print(f"Új felhasználó regisztrálva: {username}, ID: {user_id}")
    return jsonify({
        "uzenet": "Sikeres regisztráció.",
        "user_id": user_id,
        "username": username,
        "full_name": full_name
    }), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Keresés a felhasználók között
    user = next((u for u in users.values() if u['username'] == username and u['password'] == password), None)

    if user:
        return jsonify({
            "uzenet": "Sikeres bejelentkezés.",
            "user_id": user['id'],
            "username": user['username'],
            "full_name": user['full_name']
        }), 200
    else:
        return jsonify({"hiba": "Érvénytelen felhasználónév vagy jelszó."}), 401

# --------------------------
# CSOPORT KEZELÉS (GROUP)
# --------------------------

@app.route('/groups', methods=['POST'])
def create_group():
    data = request.get_json()
    user_id = data.get('user_id')
    name = data.get('name')
    
    if not name or not user_id:
        return jsonify({"hiba": "Hiányzó csoportnév vagy felhasználói azonosító."}), 400

    if user_id not in users:
        return jsonify({"hiba": "Érvénytelen felhasználói azonosító."}), 404

    group_id = str(uuid.uuid4())
    groups[group_id] = {
        "id": group_id,
        "name": name,
        "owner_id": user_id,
        "created_at": datetime.now().isoformat()
    }
    # Az alapértelmezett, hogy a létrehozó taggá válik
    group_members[group_id] = [user_id] 
    
    print(f"Csoport létrehozva: {name}, ID: {group_id} (Tulajdonos: {user_id})")
    
    return jsonify({
        "uzenet": f"Csoport '{name}' sikeresen létrehozva.",
        "group_id": group_id
    }), 201

@app.route('/groups/user/<user_id>', methods=['GET'])
def get_groups_by_user(user_id):
    """Visszaadja azokat a csoportokat, amelyeknek a felhasználó tagja."""
    if user_id not in users:
        return jsonify({"hiba": "Felhasználó nem található."}), 404

    user_groups = []
    for group_id, members in group_members.items():
        if user_id in members and group_id in groups:
            # Csak a tagsággal rendelkező létező csoportokat adjuk vissza
            user_groups.append(groups[group_id])

    return jsonify(user_groups), 200

# --------------------------
# FELADAT KEZELÉS (TASK)
# --------------------------

@app.route('/tasks', methods=['POST'])
def create_task():
    data = request.get_json()
    user_id = data.get('user_id')
    group_id = data.get('group_id') # Lehet null (saját feladatok)
    
    if not user_id or not data.get('title') or not data.get('deadline'):
        return jsonify({"hiba": "Hiányzó kötelező mezők: cím, határidő vagy felhasználói azonosító."}), 400

    # Biztosítjuk, hogy a group_id None legyen, ha a kliens valami hamis értéket küld (pl. üres string)
    # A kliens a személyes feladatokhoz null-t küld, ami None-ként érkezik.
    if group_id == 'null' or group_id == '':
        group_id = None

    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "user_id": user_id,
        "group_id": group_id, # Most már garantáltan string ID vagy None
        "title": data.get('title'),
        "type": data.get('type'),
        "deadline": data.get('deadline'),
        "reminder_days": data.get('reminder_days'),
        "description": data.get('description'),
        "online_link": data.get('online_link'),
        "is_completed": False, # Hozzáadva az alapértelmezett befejezetlenségi állapot
        "created_at": datetime.now().isoformat()
    }
    tasks[task_id] = task_data
    print(f"Feladat mentve: {task_data['title']} (ID: {task_id})")
    return jsonify({"uzenet": "Feladat sikeresen mentve.", "task_id": task_id}), 201

@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    if task_id in tasks:
        del tasks[task_id]
        print(f"Feladat törölve: {task_id}")
        return jsonify({"uzenet": "Feladat sikeresen törölve."}), 200
    return jsonify({"hiba": "Feladat nem található."}), 404

# A feladatok listázása (személyes)
@app.route('/tasks/personal/<user_id>', methods=['GET'])
def get_personal_tasks(user_id):
    """Visszaadja a felhasználó személyes feladatait (group_id == None).
    FIGYELEM: A korábbi /tasks/<user_id> útvonalat átneveztem, hogy egyértelmű legyen.
    """
    if user_id not in users:
        return jsonify({"hiba": "Felhasználó nem található."}), 404
        
    # Csak azokat a feladatokat adjuk vissza, amelyeket a felhasználó hozott létre (user_id egyezik)
    # ÉS amelyek nem tartoznak csoporthoz (group_id == None).
    personal_tasks = [
        task for task in tasks.values() 
        if task.get('group_id') is None and task.get('user_id') == user_id
    ]

    return jsonify(personal_tasks), 200

@app.route('/tasks/group/<group_id>', methods=['GET'])
def get_group_tasks(group_id):
    """Visszaadja egy adott csoport feladatait."""
    if group_id not in groups:
        return jsonify({"hiba": "Csoport nem található."}), 404

    group_tasks = get_tasks_by_group(group_id)
    return jsonify(group_tasks), 200

# --------------------------
# ÜZENET KEZELÉS (MESSAGE)
# --------------------------

@app.route('/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    sender_id = data.get('sender_id')
    recipient_username = data.get('recipient_username')
    content = data.get('content')
    
    # Ellenőrizzük, hogy a küldő létezik-e
    if sender_id not in users:
        return jsonify({"hiba": "Érvénytelen küldő azonosító."}), 404

    # Címzett felhasználó azonosítója felhasználónév alapján
    recipient = next((u for u in users.values() if u['username'] == recipient_username), None)

    if not recipient:
        return jsonify({"hiba": f"Nincs ilyen felhasználó: {recipient_username}"}), 404

    message_id = str(uuid.uuid4())
    messages[message_id] = {
        "id": message_id,
        "sender_id": sender_id,
        "recipient_id": recipient['id'],
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "is_read": False 
    }
    
    print(f"Üzenet elküldve: {users[sender_id]['username']} -> {recipient_username}")
    return jsonify({"uzenet": "Üzenet sikeresen elküldve."}), 201

@app.route('/messages/<user_id>', methods=['GET'])
def get_messages(user_id):
    """Visszaadja a felhasználóhoz kapcsolódó összes üzenetet (küldött és fogadott), 
    rendezve időbélyeg szerint (legújabb elöl)."""
    
    user_messages = []
    for msg in messages.values():
        is_sent_by_me = msg['sender_id'] == user_id
        is_received_by_me = msg['recipient_id'] == user_id
        
        if is_sent_by_me or is_received_by_me:
            
            # Címzett és küldő nevének lekérése
            sender_username = users.get(msg['sender_id'], {}).get('username', 'Ismeretlen')
            recipient_username = users.get(msg['recipient_id'], {}).get('username', 'Ismeretlen')
            
            user_messages.append({
                "id": msg['id'],
                "content": msg['content'],
                "timestamp": msg['timestamp'],
                "is_read": msg['is_read'],
                "is_sent_by_me": is_sent_by_me,
                "sender_username": sender_username,
                "recipient_username": recipient_username
            })
    
    # Rendezés időbélyeg szerint (legújabb üzenet elöl: reverse=True)
    user_messages.sort(key=lambda x: x['timestamp'], reverse=True)

    return jsonify(user_messages), 200

@app.route('/messages/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    """Törli az üzenetet a rendszerből (a kliensoldalon jelölheti olvasottnak)."""
    if message_id in messages:
        # Törlés az in-memory DB-ből
        del messages[message_id] 
        print(f"Üzenet törölve/olvasottnak jelölve: {message_id}")
        return jsonify({"uzenet": "Üzenet olvasottnak jelölve (törölve az in-memory DB-ből)."}), 200
        
    return jsonify({"hiba": "Üzenet nem található."}), 404

# --------------------------
# FUTTATÁS
# --------------------------

if __name__ == '__main__':
    # Helyi fejlesztői környezethez, a kliens (pl. a React/HTML alkalmazás) hívhatja
    # host='0.0.0.0' minden interfészen elérhetővé teszi, ha távolról tesztelnéd
    app.run(debug=True, host='0.0.0.0', port=5000)
