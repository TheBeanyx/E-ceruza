const API_URL = 'http://127.0.0.1:5000';

let currentUserId = null;
let currentUsername = null;

document.addEventListener('DOMContentLoaded', () => {
    // Feladat hozzáadása űrlap eseménykezelője
    document.getElementById('add-task-form').addEventListener('submit', addTask);
    
    // Ellenőrizzük, van-e session tárolva (Bejelentkezés megjegyzése)
    checkSession();
});

// ----------------------------------------------------
// FELHASZNÁLÓKEZELÉS (Regisztráció/Bejelentkezés/Kijelentkezés)
// ----------------------------------------------------

function checkSession() {
    currentUserId = localStorage.getItem('user_id');
    currentUsername = localStorage.getItem('username');

    if (currentUserId && currentUsername) {
        showCalendar(currentUsername);
        fetchTasks(); // Ha be van jelentkezve, lekérjük a feladatokat
    } else {
        showAuth();
    }
}

function showAuth() {
    document.getElementById('auth-container').style.display = 'block';
    document.getElementById('calendar-container').style.display = 'none';
}

function showCalendar(username) {
    document.getElementById('auth-container').style.display = 'none';
    document.getElementById('calendar-container').style.display = 'block';
    document.getElementById('welcome-username').textContent = username;
}

async function registerUser() {
    const name = document.getElementById('auth-name').value;
    const password = document.getElementById('auth-password').value;
    const msg = document.getElementById('auth-message');

    if (!name || !password) {
        msg.textContent = 'Kérjük, adja meg a nevét és jelszavát!';
        return;
    }

    try {
        const response = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, password })
        });
        const data = await response.json();

        if (response.status === 201) {
            msg.textContent = `Sikeres regisztráció! Felhasználóneved: ${data.felhasznalonev}. Jelentkezz be!`;
            msg.style.backgroundColor = '#d4edda';
            msg.style.color = '#155724';
        } else {
            msg.textContent = `Regisztráció sikertelen: ${data.hiba || data.uzenet}`;
            msg.style.backgroundColor = '#f8d7da';
            msg.style.color = '#721c24';
        }
    } catch (error) {
        msg.textContent = 'Hiba történt a szerverrel való kommunikáció során.';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        console.error('Registration Error:', error);
    }
}

async function loginUser() {
    const username = document.getElementById('auth-username').value;
    const password = document.getElementById('auth-password').value;
    const msg = document.getElementById('auth-message');

    if (!username || !password) {
        msg.textContent = 'Kérjük, adja meg a felhasználónevét és jelszavát!';
        return;
    }

    try {
        const response = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (response.status === 200) {
            // Sikeres bejelentkezés, mentjük a session-t
            currentUserId = data.user_id;
            currentUsername = data.username;
            localStorage.setItem('user_id', currentUserId);
            localStorage.setItem('username', currentUsername);
            
            showCalendar(currentUsername);
            fetchTasks(); // Feladatok lekérése bejelentkezés után
        } else {
            msg.textContent = `Bejelentkezés sikertelen: ${data.hiba}`;
            msg.style.backgroundColor = '#f8d7da';
            msg.style.color = '#721c24';
        }
    } catch (error) {
        msg.textContent = 'Hiba történt a szerverrel való kommunikáció során.';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        console.error('Login Error:', error);
    }
}

function logout() {
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    currentUserId = null;
    currentUsername = null;
    showAuth();
    document.getElementById('auth-message').textContent = 'Sikeresen kijelentkeztél.';
    document.getElementById('auth-message').style.backgroundColor = '#d1ecf1';
    document.getElementById('auth-message').style.color = '#0c5460';
}

// ----------------------------------------------------
// FELADATKEZELÉS (Hozzáadás/Lekérés/Törlés)
// ----------------------------------------------------

async function fetchTasks() {
    const tasksListDiv = document.getElementById('tasks-list');
    tasksListDiv.innerHTML = 'Feladatok betöltése...';

    try {
        const response = await fetch(`${API_URL}/tasks/${currentUserId}`);
        const tasks = await response.json();

        tasksListDiv.innerHTML = '';
        if (tasks.length === 0) {
            tasksListDiv.innerHTML = '<p>Nincsenek feladatok a naptárban.</p>';
            return;
        }

        tasks.forEach(task => {
            const taskElement = document.createElement('div');
            taskElement.className = 'task-item';
            
            // Dátum formázása
            const deadline = new Date(task.deadline);
            const formattedDeadline = deadline.toLocaleString('hu-HU', {
                year: 'numeric', month: 'long', day: 'numeric', 
                hour: '2-digit', minute: '2-digit'
            });

            taskElement.innerHTML = `
                <div class="task-info">
                    <strong>${task.title}</strong> (${task.type})<br>
                    Határidő: ${formattedDeadline}<br>
                    Emlékeztető: ${task.reminder_days} nappal előtte.<br>
                    <small>${task.description || 'Nincs leírás'}</small>
                </div>
                <button class="task-delete" data-task-id="${task.id}" onclick="deleteTask(${task.id})">Törlés</button>
            `;
            tasksListDiv.appendChild(taskElement);
        });

    } catch (error) {
        tasksListDiv.innerHTML = '<p style="color: red;">Hiba történt a feladatok betöltése során.</p>';
        console.error('Fetch Tasks Error:', error);
    }
}

async function addTask(e) {
    e.preventDefault();
    const msg = document.getElementById('task-message');
    
    // Dátum formázása ISO-ra, ahogy a backend várja (YYYY-MM-DDTHH:MM:SS)
    const deadlineInput = document.getElementById('task-deadline').value;
    const deadline = deadlineInput ? new Date(deadlineInput).toISOString().slice(0, 19).replace('T', 'T') : null;
    
    if (!deadline) {
        msg.textContent = 'Kérjük, adja meg a határidőt!';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        return;
    }

    const taskData = {
        user_id: currentUserId,
        title: document.getElementById('task-title').value,
        type: document.getElementById('task-type').value,
        deadline: deadline,
        reminder_days: parseInt(document.getElementById('task-reminder').value) || 1,
        description: document.getElementById('task-description').value
    };

    try {
        const response = await fetch(`${API_URL}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
        const data = await response.json();

        if (response.status === 201) {
            msg.textContent = 'Feladat sikeresen hozzáadva!';
            msg.style.backgroundColor = '#d4edda';
            msg.style.color = '#155724';
            document.getElementById('add-task-form').reset(); // Űrlap törlése
            fetchTasks(); // Feladatok frissítése
        } else {
            msg.textContent = `Hozzáadás sikertelen: ${data.hiba || data.uzenet}`;
            msg.style.backgroundColor = '#f8d7da';
            msg.style.color = '#721c24';
        }
    } catch (error) {
        msg.textContent = 'Hiba történt a szerverrel való kommunikáció során.';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        console.error('Add Task Error:', error);
    }
}

async function deleteTask(taskId) {
    if (!confirm('Biztosan törölni szeretnéd ezt a feladatot?')) {
        return;
    }

    try {
        const response = await fetch(`${API_URL}/tasks/${taskId}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (response.status === 200) {
            alert(data.uzenet);
            fetchTasks(); // Feladatok frissítése a törlés után
        } else {
            alert(`Törlés sikertelen: ${data.hiba || data.uzenet}`);
        }
    } catch (error) {
        alert('Hiba történt a szerverrel való kommunikáció során.');
        console.error('Delete Task Error:', error);
    }
}