import requests
import sqlite3
import re
import time
import os

# ─────────────────────────────────────────────
# CONFIGURAZIONE WEBHOOK DISCORD
# Puoi inserirli qui oppure come GitHub Secrets
# con i nomi DISCORD_WEBHOOK_HSR e DISCORD_WEBHOOK_GENSHIN
# ─────────────────────────────────────────────
DISCORD_WEBHOOK_HSR     = os.getenv("DISCORD_WEBHOOK_HSR", "")
DISCORD_WEBHOOK_GENSHIN = os.getenv("DISCORD_WEBHOOK_GENSHIN", "")

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
    {"gioco": "Honkai Star Rail", "url": "https://gamesradar.com/honkai-star-rail-codes/"},
    {"gioco": "Honkai Star Rail", "url": "https://dotesports.com/honkai-star-rail/news/all-honkai-star-rail-codes"},
    {"gioco": "Genshin Impact",   "url": "https://www.hoyolab.com"},
    {"gioco": "Genshin Impact",   "url": "https://www.pockettactics.com/genshin-impact/codes"},
    {"gioco": "Genshin Impact",   "url": "https://gamesradar.com/genshin-impact-codes/"},
    {"gioco": "Genshin Impact",   "url": "https://dotesports.com/genshin-impact/news/genshin-impact-codes"},
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


def invia_notifica_discord(gioco, codici_nuovi):
    """Invia un unico messaggio Discord con tutti i nuovi codici del gioco."""
    if gioco == "Honkai Star Rail":
        webhook = DISCORD_WEBHOOK_HSR
        emoji = "🚂"
    elif gioco == "Genshin Impact":
        webhook = DISCORD_WEBHOOK_GENSHIN
        emoji = "🌸"
    else:
        return

    if not webhook or not codici_nuovi:
        return

    # Costruisce la lista codici formattata
    lista = "\n".join([f"🎁 `{c}`" for c in sorted(codici_nuovi)])

    messaggio = {
        "content": (
            f"{emoji} **{gioco}** — Nuovi codici trovati!\n"
            f"{lista}"
        )
    }
    try:
        risposta = requests.post(webhook, json=messaggio, timeout=10)
        risposta.raise_for_status()
        print(f"│      ✉  Notifica Discord inviata ({len(codici_nuovi)} codici)")
    except requests.RequestException as e:
        print(f"│      ✗  Errore Discord: {e}")


def codice_sembra_scaduto(codice, testo):
    """
    Controlla se la parola 'expired' appare vicino al codice nel testo.
    Se sì, il codice è probabilmente scaduto.
    """
    pos = testo.find(codice)
    if pos == -1:
        return False
    # Guarda 300 caratteri prima e dopo il codice
    contesto = testo[max(0, pos - 300): pos + len(codice) + 300].lower()
    return "expired" in contesto


def controlla_fonte(url):
    """Scarica il contenuto di una fonte e cerca codici redeem validi."""
    try:
        risposta = requests.get(url, headers=HEADERS, timeout=15)
        risposta.raise_for_status()
        testo = risposta.text

        codici_trovati = CODICE_REGEX.findall(testo)

        # Filtra i codici che sembrano scaduti in base al contesto
        codici_validi = set()
        for codice in codici_trovati:
            if codice_sembra_scaduto(codice, testo):
                print(f"│      ✗  Scaduto (ignorato): {codice}")
            else:
                codici_validi.add(codice)

        return codici_validi

    except requests.RequestException as e:
        print(f"│      ✗  Errore accesso: {e}")
        return set()


def main():
    """Esegue una singola scansione (GitHub Actions la lancia ogni 12 ore)."""
    ora = time.strftime("%d/%m/%Y %H:%M:%S")
    print("╔══════════════════════════════════════╗")
    print("║     Monitor Codici Hoyoverse         ║")
    print("║  Honkai Star Rail  +  Genshin Impact ║")
    print("╚══════════════════════════════════════╝")

    inizializza_db()

    print(f"┌─ Scansione iniziata: {ora}")

    # Dizionario per raccogliere tutti i codici nuovi per gioco
    nuovi_per_gioco = {}
    gia_noti_totali = 0
    gioco_corrente = None

    for fonte in FONTI:
        gioco = fonte["gioco"]
        url = fonte["url"]

        if gioco != gioco_corrente:
            print(f"│")
            print(f"│  ▶ {gioco}")
            gioco_corrente = gioco
            if gioco not in nuovi_per_gioco:
                nuovi_per_gioco[gioco] = set()

        print(f"│    • {url}")
        codici = controlla_fonte(url)

        for codice in codici:
            if salva_codice(codice, gioco):
                nuovi_per_gioco[gioco].add(codice)
                print(f"│      ★ NUOVO  →  {codice}")
            else:
                gia_noti_totali += 1

        gia_noti_fonte = len(codici) - len([c for c in codici if c in nuovi_per_gioco[gioco]])
        if gia_noti_fonte > 0:
            print(f"│      ✓ Già noti: {gia_noti_fonte} codici")

    # Invia UN solo messaggio Discord per gioco con tutti i nuovi codici
    print(f"│")
    for gioco, codici in nuovi_per_gioco.items():
        if codici:
            invia_notifica_discord(gioco, codici)

    nuovi_totali = sum(len(c) for c in nuovi_per_gioco.values())
    print(f"│  Riepilogo: {nuovi_totali} nuovi  |  {gia_noti_totali} già noti")
    print(f"└─ Scansione completata")


if __name__ == "__main__":
    main()
