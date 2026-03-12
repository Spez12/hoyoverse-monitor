import requests
import sqlite3
import re
import time

# ─────────────────────────────────────────────
# CONFIGURAZIONE WEBHOOK DISCORD
# Inserisci il webhook per ricevere notifiche.
# Puoi usare lo stesso per entrambi i giochi,
# oppure uno diverso per ciascuno.
# Lascia vuoto ("") per disabilitare.
# ─────────────────────────────────────────────
DISCORD_WEBHOOK_HSR = "https://discordapp.com/api/webhooks/1481612180812992614/aRNFzNtzla6AJCqoaBCLsd3Q1igmWPlAcrYGPAWi5sLXpW7w83devpYP-Nx5pszrVgQ6"      # Honkai Star Rail
DISCORD_WEBHOOK_GENSHIN = "https://discordapp.com/api/webhooks/1481612218092228772/tz-hZPwHcX_1J-DtLPQWTgdtVoijb2E9HNhrj6ERzy8zeHjsZ41_-yyTLJC5o_g65a5k"  # Genshin Impact

# Regex per trovare codici redeem (8-12 caratteri alfanumerici maiuscoli)
CODICE_REGEX = re.compile(r'\b[A-Z0-9]{8,12}\b')

# Headers per le richieste HTTP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# FONTI DA MONITORARE PER GIOCO
# ─────────────────────────────────────────────
FONTI = [
    {"gioco": "Honkai Star Rail", "url": "https://www.hoyolab.com"},
    {"gioco": "Honkai Star Rail", "url": "https://www.pockettactics.com/honkai-star-rail/codes"},
    {"gioco": "Genshin Impact",   "url": "https://www.hoyolab.com"},
    {"gioco": "Genshin Impact",   "url": "https://www.pockettactics.com/genshin-impact/codes"},
]


def inizializza_db():
    """Crea il database SQLite e la tabella dei codici se non esistono."""
    conn = sqlite3.connect("codes.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codici (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codice TEXT NOT NULL,
            gioco TEXT NOT NULL,
            trovato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(codice, gioco)
        )
    """)
    conn.commit()
    conn.close()


def salva_codice(codice, gioco):
    """
    Salva un codice nel database associandolo al gioco.
    Restituisce True se è nuovo, False se era già presente.
    """
    conn = sqlite3.connect("codes.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO codici (codice, gioco) VALUES (?, ?)",
            (codice, gioco)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def invia_notifica_discord(codice, gioco):
    """Invia una notifica Discord tramite webhook se configurato."""
    if gioco == "Honkai Star Rail":
        webhook = DISCORD_WEBHOOK_HSR
    elif gioco == "Genshin Impact":
        webhook = DISCORD_WEBHOOK_GENSHIN
    else:
        webhook = ""

    if not webhook:
        return

    messaggio = {
        "content": f"🎮 **{gioco}** — Nuovo codice trovato!\n🎁 `{codice}`"
    }
    try:
        risposta = requests.post(webhook, json=messaggio, timeout=10)
        risposta.raise_for_status()
        print(f"    ✉  Notifica Discord inviata")
    except requests.RequestException as e:
        print(f"    ✗  Errore Discord: {e}")


def controlla_fonte(url):
    """Scarica il contenuto di una fonte e cerca codici redeem."""
    try:
        risposta = requests.get(url, headers=HEADERS, timeout=15)
        risposta.raise_for_status()
        codici_trovati = CODICE_REGEX.findall(risposta.text)
        return set(codici_trovati)
    except requests.RequestException as e:
        print(f"    ✗  Errore accesso: {e}")
        return set()


def main():
    """Loop principale del monitor."""
    print("╔══════════════════════════════════════╗")
    print("║     Monitor Codici Hoyoverse         ║")
    print("║  Honkai Star Rail  +  Genshin Impact ║")
    print("╚══════════════════════════════════════╝")
    print("Avviato — controllo ogni 12 ore. (Ctrl+C per fermare)\n")

    inizializza_db()

    while True:
        ora = time.strftime("%d/%m/%Y %H:%M:%S")
        print(f"┌─ Scansione iniziata: {ora}")

        nuovi_totali = 0
        gia_noti_totali = 0

        gioco_corrente = None
        for fonte in FONTI:
            gioco = fonte["gioco"]
            url = fonte["url"]

            # Stampa intestazione gioco solo quando cambia
            if gioco != gioco_corrente:
                print(f"│")
                print(f"│  ▶ {gioco}")
                gioco_corrente = gioco

            print(f"│    • {url}")
            codici = controlla_fonte(url)

            nuovi = []
            gia_noti = []

            for codice in codici:
                if salva_codice(codice, gioco):
                    nuovi.append(codice)
                else:
                    gia_noti.append(codice)

            # Mostra codici nuovi
            for codice in nuovi:
                print(f"│      ★ NUOVO  →  {codice}")
                invia_notifica_discord(codice, gioco)

            # Mostra quanti erano già noti (senza elencarli tutti)
            if gia_noti:
                print(f"│      ✓ Già noti: {len(gia_noti)} codici")

            nuovi_totali += len(nuovi)
            gia_noti_totali += len(gia_noti)

        # Riepilogo finale della scansione
        print(f"│")
        print(f"│  Riepilogo: {nuovi_totali} nuovi  |  {gia_noti_totali} già noti")
        print(f"└─ Prossima scansione tra 12 ore\n")

        time.sleep(43200)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitoraggio interrotto dall'utente.")
