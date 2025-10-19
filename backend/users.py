import unidecode
import random
import re

def felhasznalonev_generalas(teljes_nev, db_felhasznalok):
    """Generál egy egyedi felhasználónevet a név és egy véletlen szám alapján."""
    
    ekezet_nelkul = unidecode.unidecode(teljes_nev).lower()
    tisztitott_nev = re.sub(r'[^a-z\s]', '', ekezet_nelkul).strip()
    nev_reszek = tisztitott_nev.split()

    if len(nev_reszek) < 2:
        alap_resz = nev_reszek[0] if nev_reszek else "diak"
    else:
        vezeteknev = nev_reszek[-1]
        keresztnev = nev_reszek[0]
        alap_resz = f"{vezeteknev}_{keresztnev}"
        
    alap_resz = alap_resz.replace(' ', '_')

    max_probalkozas = 10 
    for _ in range(max_probalkozas):
        veletlen_szam = random.randint(10, 99)
        generalt_felhasznalonev = f"{alap_resz}{veletlen_szam}"
        
        if generalt_felhasznalonev not in [u.username for u in db_felhasznalok]:
            return generalt_felhasznalonev
            
    return None

def regisztral_felhasznalo(adatbazis, User_modell, bcrypt_obj, nev, email, jelszo):
    """Végrehajtja a regisztrációt és elmenti a felhasználót az adatbázisba, az email címmel együtt."""
    
    jelenlegi_felhasznalok = User_modell.query.all()
    username = felhasznalonev_generalas(nev, jelenlegi_felhasznalok)

    if not username:
        raise ValueError("Nem sikerült egyedi felhasználónevet generálni, próbálkozz újra.")

    hashed_password = bcrypt_obj.generate_password_hash(jelszo).decode('utf-8')

    uj_felhasznalo = User_modell(
        full_name=nev, 
        email=email,
        username=username, 
        password_hash=hashed_password
    )
    adatbazis.session.add(uj_felhasznalo)
    adatbazis.session.commit()
    
    return uj_felhasznalo

def bejelentkezes_felhasznalo(User_modell, bcrypt_obj, username, password):
    """Ellenőrzi a felhasználónevet és a jelszót az adatbázisban."""
    
    user = User_modell.query.filter_by(username=username).first()
    
    if user and bcrypt_obj.check_password_hash(user.password_hash, password):
        return user
    
    return None

def get_user_by_id(User_modell, user_id):
    """Lekérdez egy felhasználót azonosító alapján."""
    return User_modell.query.get(user_id)