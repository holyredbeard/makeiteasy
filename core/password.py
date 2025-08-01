from passlib.context import CryptContext
import hashlib
import secrets

# Konfigurera passlib för bcrypt, som är industristandard
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifierar ett lösenord mot en hash.
    Försöker först verifiera med den säkra bcrypt-metoden. Om det misslyckas,
    faller den tillbaka till att kontrollera det gamla, osäkra formatet (salt:hash)
    för bakåtkompatibilitet.
    """
    try:
        # Försök först med den nya, säkra metoden
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except (ValueError, TypeError):
        # Om verifieringen misslyckas med ett undantag kan det vara det gamla formatet.
        # Ett vanligt ValueError här är "not a valid bcrypt hash".
        pass

    # Fallback till det gamla, osäkra formatet
    if ":" in hashed_password:
        try:
            salt, password_hash = hashed_password.split(":")
            verify_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
            return password_hash == verify_hash
        except ValueError:
            # Ogiltigt gammalt format
            return False
            
    return False

def get_password_hash(password: str) -> str:
    """
    Genererar en säker bcrypt-hash för ett nytt lösenord.
    Används vid nyregistrering och när gamla lösenord uppdateras.
    """
    return pwd_context.hash(password)

def needs_rehash(hashed_password: str) -> bool:
    """
    Kontrollerar om ett lösenord är hashat med en gammal metod och behöver
    uppdateras. En hash behöver hashas om ifall den inte är i det nya
    bcrypt-formatet.
    """
    return not hashed_password.startswith("$2b$")
