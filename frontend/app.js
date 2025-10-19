// frontend/app.js - A weboldal dinamikus logikája
const API_URL = 'http://127.0.0.1:5000';

let currentUserId = null;
let currentUsername = null;

document.addEventListener('DOMContentLoaded', () => {
    // Feladat hozzáadása űrlap eseménykezelője
    document.getElementById('add-task-form').addEventListener('submit', addTask);
    
    // Ellenőrizzük, van-e session tárolva (Bejelentkezés megjegyzése)
    checkSession();
});

// E-mail formátum ellenőrző funkció (csak a formátumot nézi, nem a létezést)
function isValidEmail(email) {
    // Egyszerű regex a legtöbb szabványos e-mail formátum ellenőrzésére
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

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
    const name = document.getElementById('reg-name').value;
    const email = document.getElementById('reg-email').value; // ÚJ MEZŐ
    const password = document.getElementById('reg-password').value;
    const passwordConfirm = document.getElementById('reg-password-confirm').value; // ÚJ MEZŐ
    const msg = document.getElementById('auth-message');

    // 1. Üres mező ellenőrzés
    if (!name || !email || !password || !passwordConfirm) {
        msg.textContent = 'Kérjük, töltse ki az összes mezőt!';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        return;
    }

    // 2. E-mail formátum ellenőrzés
    if (!isValidEmail(email)) {
        msg.textContent = 'Érvénytelen e-mail cím formátum!';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        return;
    }

    // 3. Jelszó egyezés ellenőrzés
    if (password !== passwordConfirm) {
        msg.textContent = 'A jelszavak nem egyeznek!';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        return;
    }

    try {
        const response = await fetch(`${API_URL}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            // ELKÜLDJÜK AZ E-MAIL CÍMET ÉS CSAK EGY JELSZÓT
            body: JSON.stringify({ name, email, password }) 
        });
        const data = await response.json();

        if (response.status === 201) {
            msg.textContent = `Sikeres regisztráció! A generált felhasználóneved: ${data.felhasznalonev}. Jelentkezz be! (E-mailt küldtünk a címre: ${email})`;
            msg.style.backgroundColor = '#d4edda';
            msg.style.color = '#155724';
            
            // Töröljük a regisztrációs mezőket
            document.getElementById('reg-name').value = '';
            document.getElementById('reg-email').value = '';
            document.getElementById('reg-password').value = '';
            document.getElementById('reg-password-confirm').value = '';

        } else {
            msg.textContent = `Regisztráció sikertelen: ${data.hiba || data.uzenet}`;
            msg.style.backgroundColor = '#f8d7da';
            msg.style.color = '#721c24';
        }
    } catch (error) {
        msg.textContent = 'Hiba történt a szerverrel való kommunikáció során. Lehet, hogy a backend nem fut!';
        msg.style.backgroundColor = '#f8d7da';
        msg.style.color = '#721c24';
        console.error('Registration Error:', error);
    }
}

async function loginUser() {
    // ... (A bejelentkezési logika változatlan) ...
}

function logout() {
    // ... (A kijelentkezési logika változatlan) ...
}

// ----------------------------------------------------
// FELADATKEZELÉS (Hozzáadás/Lekérés/Törlés) - változatlan
// ----------------------------------------------------