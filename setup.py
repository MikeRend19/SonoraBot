import os
import subprocess
import sys

ENV_PATH = ".env"
REQUIRED_KEYS = [
    "DISCORD_TOKEN",
    "LAVALINK_HOST",
    "LAVALINK_PORT",
    "LAVALINK_PASSWORD",
    "SECRET_KEY"
]

def leggi_env_iniziale(chiave):
    if not os.path.isfile(ENV_PATH):
        return None

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for riga in f:
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            if riga.startswith(f"{chiave}="):
                return riga.split("=", 1)[1]
    return None

def prompt_env(chiave, valore_esistente):
    if valore_esistente:
        risposta = input(f"Inserisci {chiave} [{valore_esistente}]: ").strip()
        return risposta or valore_esistente
    else:
        while True:
            risposta = input(f"Inserisci {chiave}: ").strip()
            if risposta:
                return risposta
            print("❗ Il valore non può essere vuoto.")

def crea_o_aggiorna_env(force_update=False):
    print("=== Configurazione file .env per SonoraBot ===\n")

    valori = {}
    for key in REQUIRED_KEYS:
        valori[key] = leggi_env_iniziale(key)

    if not force_update:
        mancanti = [k for k, v in valori.items() if not v]
        if not mancanti:
            print("✅ Non ci sono chiavi mancanti. Salto la creazione/aggiornamento.")
            return
        print("⚠️ Mancano queste chiavi nel .env: " + ", ".join(mancanti))
    else:
        print("⚠️ Hai scelto di aggiornare il file .env. Ti verranno mostrati i valori correnti come default.\n")

    for key in REQUIRED_KEYS:
        if force_update or not valori[key]:
            valori[key] = prompt_env(key, valori[key])

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for key in REQUIRED_KEYS:
            f.write(f"{key}={valori[key]}\n")

    print("\n✅ File .env creato/aggiornato con i valori inseriti.")

def main():
    if not os.path.isfile(ENV_PATH):
        crea_o_aggiorna_env(force_update=True)
    else:
        mancanti = [k for k in REQUIRED_KEYS if not leggi_env_iniziale(k)]
        if mancanti:
            crea_o_aggiorna_env(force_update=False)
        else:
            risposta = input("✅ File .env già completo. Vuoi aggiornarlo? (y/N): ").strip().lower()
            if risposta.startswith("y"):
                crea_o_aggiorna_env(force_update=True)
            else:
                print("ℹ️ Salto aggiornamento e avvio diretto di bot.py.\n")

    print("▶️ Avvio di bot.py...\n")
    try:
        subprocess.run([sys.executable, "bot.py"])
    except FileNotFoundError:
        print("❌ Errore: non ho trovato il file bot.py nella cartella corrente.")
    except Exception as e:
        print(f"❌ Errore durante l’avvio di bot.py: {e}")

if __name__ == "__main__":
    main()
