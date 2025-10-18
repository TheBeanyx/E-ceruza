import unidecode
import random
import re
# A Bcrypt objektumot az app.py-ban inicializáljuk!

def felhasznalonev_generalas(teljes_nev, db_felhasznalok):
    """Generál egy egyedi felhasználónevet a név és egy véletlen szám alapján."""
    
    # Ékezetek eltávolítása és kisbetűssé alakítás
    ekezet_nelkul = unidecode.unidecode(teljes_nev).lower()
    tisztitott_nev = re.sub(r'[^a-z\s]', '', ekezet_nelkul).strip()
    nev_reszek = tisztitott_nev.split()

    if len(nev_reszek) < 2:
        alap_resz = nev_reszek[0] if nev_reszek else "diak"
    else:
        # A kérésed szerinti formátum: vezetéknév_keresztnév
        vezeteknev = nev_reszek[-1]
        keresztnev = nev_reszek[0]
        alap_resz = f"{vezeteknev}_{keresztnev}"
        
    alap_resz = alap_resz.replace(' ', '_')

    max_probalkozas = 10 
    for _ in range(max_probalkozas):
        veletlen_szam = random.randint(10, 99)
        generalt_felhasznalonev = f"{alap_resz}{veletlen_szam}"
        
        # Ellenőrzés: megnézzük, hogy a generált felhasználónév már létezik-e az adatbázisban
        if generalt_felhasznalonev not in [u.username for u in db_felhasznalok]:
            return generalt_felhasznalonev
            
    return None

def regisztral_felhasznalo(nev, jelszo, adatbazis, User_modell, bcrypt_obj):
    """Végrehajtja a regisztrációt és elmenti a felhasználót az adatbázisba."""
    
    # 1. Felhasználónév generálása
    jelenlegi_felhasznalok = User_modell.query.all()
    username = felhasznalonev_generalas(nev, jelenlegi_felhasznalok)

    if not username:
        return {"hiba": "Nem sikerült egyedi felhasználónevet generálni, próbálkozz újra."}, 400

    # 2. Jelszó titkosítása (hash-elése) - a biztonság érdekében elengedhetetlen!
    hashed_password = bcrypt_obj.generate_password_hash(jelszo).decode('utf-8')

    # 3. Új felhasználó létrehozása az adatbázisban
    uj_felhasznalo = User_modell(
        full_name=nev, 
        username=username, 
        password_hash=hashed_password
    )
    adatbazis.session.add(uj_felhasznalo)
    adatbazis.session.commit()
    
    return uj_felhasznalo