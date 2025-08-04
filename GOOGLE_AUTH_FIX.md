# Hur du fixar Google-inloggningen

Det finns ett problem med hur Google OAuth-flödet är konfigurerat i applikationen. Här är en förklaring av problemet och hur du kan lösa det.

## Problemet

1. Frontend (`http://localhost:3000`) skickar användaren till Google för autentisering.
2. Google skickar tillbaka användaren till `http://localhost:3000` (frontend) efter autentisering.
3. Men frontend-koden har ingen hanterare för att ta emot denna callback och skicka den vidare till backend.

## Lösningen

Du har två alternativ:

### Alternativ 1: Ändra redirect URI i Google OAuth-konfigurationen

1. Ändra `GOOGLE_REDIRECT_URI` i `.env`-filen från `http://localhost:3000` till `http://localhost:8000/api/v1/auth/google/callback`.
2. Detta kommer att göra att Google skickar tillbaka användaren direkt till backend-servern, som redan har kod för att hantera denna callback.

### Alternativ 2: Implementera en callback-hanterare i frontend (rekommenderad)

Jag har skapat två nya filer för att hantera OAuth-callback i frontend:

1. `src/OAuthCallback.jsx`: En ny komponent som hanterar OAuth-callback från Google.
2. Uppdaterat `src/App.jsx` för att inkludera denna nya komponent.

Men för att detta ska fungera behöver du:

1. Installera React Router: `npm install react-router-dom`
2. Ändra `GOOGLE_REDIRECT_URI` i `.env`-filen från `http://localhost:3000` till `http://localhost:3000/oauth-callback`.

## Rekommendation

Jag rekommenderar Alternativ 2, eftersom det är en mer robust lösning som följer bästa praxis för OAuth-flöden i Single Page Applications (SPA).

## Steg för att implementera Alternativ 2

1. Installera React Router:
   ```bash
   npm install react-router-dom
   ```

2. Ändra `GOOGLE_REDIRECT_URI` i `.env`-filen:
   ```
   GOOGLE_REDIRECT_URI=http://localhost:3000/oauth-callback
   ```

3. Starta om både frontend- och backend-servern.

Nu bör Google-inloggningen fungera korrekt.