import unidecode
import random
import re

def felhasznalonev_generalas(teljes_nev, db_felhasznalok):
    """Generál egy egyedi felhasználónevet a név és egy véletlen szám alapján."""
    
    ekezet_nelkul = unidecode.unidecode(teljes_nev).lower()
    # Csak betűk és szóköz engedélyezése
    tisztitott_nev = re.sub(r'[^a-z\s]', '', ekezet_nelkul).strip()
    nev_reszek = tisztitott_nev.split()

    if len(nev_reszek) < 2:
        alap_resz = nev_reszek[0] if nev_reszek else "diak"
    else:
        # Felcseréljük a nevet a vezeteknev_keresztnev formátumra
        vezeteknev = nev_reszek[-1]
        keresztnev = nev_reszek[0]
        alap_resz = f"{vezeteknev}_{keresztnev}"
        
    alap_resz = alap_resz.replace(' ', '_')

    max_probalkozas = 10 
    
    # Létrehozunk egy halmazt a meglévő felhasználónevekből a gyorsabb kereséshez
    meglevo_usernames = {u.username for u in db_felhasznalok} 
    
    for _ in range(max_probalkozas):
        # Generálunk egy 2 jegyű számot (10-99)
        veletlen_szam = random.randint(10, 99)
        generalt_felhasznalonev = f"{alap_resz}{veletlen_szam}"
        
        # Ellenőrizzük, hogy a generált felhasználónév ne szerepeljen a már létező felhasználók között
        if generalt_felhasznalonev not in meglevo_usernames:
            return generalt_felhasznalonev
            
    return None

def regisztral_felhasznalo(adatbazis, User_modell, bcrypt_obj, nev, email, jelszo):
    """Végrehajtja a regisztrációt és elmenti a felhasználót az adatbázisba, az email címmel együtt."""
    
    # 1. Lekérjük a jelenlegi felhasználókat a felhasználónév generáláshoz
    jelenlegi_felhasznalok = User_modell.query.all()
    username = felhasznalonev_generalas(nev, jelenlegi_felhasznalok)

    if not username:
        raise ValueError("Nem sikerült egyedi felhasználónevet generálni, próbálkozz újra.")

    # 2. Jelszó kódolása
    hashed_password = bcrypt_obj.generate_password_hash(jelszo).decode('utf-8')

    # 3. Új felhasználó létrehozása és adatbázishoz adása
    uj_felhasznalo = User_modell(
        full_name=nev, 
        email=email,
        username=username, 
        password_hash=hashed_password
    )
    adatbazis.session.add(uj_felhasznalo)
    adatbazis.session.commit()
    
    return uj_felhasznalo

def bejelentkezes_felhasznalo(User_modell, bcrypt_obj, felhasznalo_vagy_email, jelszo):
    """
    Keresés felhasználónév vagy e-mail alapján, és ellenőrzi a jelszót.
    """
    
    # Keresés felhasználónév alapján
    user = User_modell.query.filter_by(username=felhasznalo_vagy_email).first()
    
    # Ha nem találta felhasználónév alapján, próbálja meg e-mail alapján
    if user is None:
        user = User_modell.query.filter_by(email=felhasznalo_vagy_email).first()
    
    # Ha talált felhasználót ÉS a jelszó helyes
    if user and bcrypt_obj.check_password_hash(user.password_hash, jelszo):
        return user 
    
    return None