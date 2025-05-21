# 🤖 Sonora

> Sonora Bot è un bot Discord per riprodurre musica da YouTube utilizzando un nodo Lavalink.

[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)  
[![Discord.py](https://img.shields.io/badge/discord.py-%7E2.0-green)](https://github.com/Rapptz/discord.py)

## 📋 Sommario

- [🚀 Caratteristiche](#caratteristiche)
- [🛠️ Requisiti](#requisiti)
- [📥 Installazione](#installazione)
- [⚙️ Configurazione](#configurazione)
- [🎹 Comandi disponibili](#comandi-disponibili)
- [✨ Funzioni Extra](#funzioni-extra)
- [🔧 Personalizzazione](#personalizzazione)
- [🤝 Contribuire](#contribuire)
- [📄 Licenza](#licenza)

<h2 id="caratteristiche">🚀 Caratteristiche</h2>

- Riproduzione di singoli brani e playlist YouTube  
- Controllo della coda e sistema di loop  
- Pause/Riprendi, Skip e Stop  
- Controllo del volume (incluso volume manuale)  
- Creazione e gestione di playlist locali (pubbliche e private)  
- Comando segreto `secretvolume` per boost dei bassi  

<h2 id="requisiti">🛠️ Requisiti</h2>

1. Python 3.11  
2. Un bot Discord (token)  
3. Un nodo Lavalink in esecuzione  

<h2 id="installazione">📥 Installazione</h2>

Clona il repository o scarica i file:

```bash
git clone https://github.com/MikeRend19/SonoraBot.git
cd SonoraBot
```

Installa le dipendenze:

```bash
pip install -r requirements.txt
```

Avvia il bot:

```
python bot.py
```

<h2 id="configurazione">⚙️ Configurazione</h2>

Crea un file .env nella cartella principale con il seguente formato:

```
DISCORD_TOKEN="IlTuoToken"
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=IlTuoPassword
LAVALINK_SECURE=false
```

⚠️ Non condividere il file .env pubblicamente!

<h2 id="comandi-disponibili">🎹 Comandi disponibili</h2>

Comando	Descrizione
- `/play <link> | <nome>`:	Riproduci un brano o playlist da YouTube
- `/playplaylist`:	Seleziona e avvia una playlist locale
- `/gestisciplaylist`:	Gestisci le tue playlist o quelle pubbliche
- Controlli interattivi:	Pause, Riprendi, Skip, Stop, Loop, Volume +/-, ecc.

<h2 id="funzioni-extra">✨ Funzioni Extra</h2>

   - `/secretvolume`: aumenta il volume al massimo e potenzia i bassi.
      -  La password per eseguire secretvolume si trova alla riga 818 del file bot.py.

<h2 id="personalizzazione">🔧 Personalizzazione</h2>

  - Puoi modificare i comandi, i prefissi o gli stili delle embed direttamente in `bot.py`.

  -  Per cambiare la password del comando `secretvolume`, cerca la definizione del comando e modifica la stringa al rigo 818.

<h2 id="contribuire">🤝 Contribuire</h2>

PR e issue sono benvenuti! Segui questi passaggi:

 1. Fork del repository

 2. Crea un branch feature:

```git checkout -b feature/AmazingFeature```

 3. Commit delle modifiche:

```git commit -m "Add some AmazingFeature"```

 4. Push al branch:

```git push origin feature/AmazingFeature```

 5. Apri una Pull Request

<h2 id="licenza">📄 Licenza</h2>

Il progetto è rilasciato sotto licenza MIT. Questo significa che puoi utilizzare, modificare e distribuire liberamente il software, anche in progetti commerciali, a condizione di:

  1. Includere copia della licenza MIT originale in tutte le copie o parti sostanziali del software.

  2. Non fornire alcuna garanzia; il software viene fornito “COSÌ COM’È”, senza alcuna dichiarazione esplicita o implicita.

Per il testo completo della licenza, consulta il file LICENSE incluso nel repository.

```
MIT License

Copyright (c) 2025 Mike_Rend

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in 
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN 
THE SOFTWARE.

```
