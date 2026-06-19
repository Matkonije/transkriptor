# Transkriptor

Skida audio s YouTube videa lokalno i šalje na server za transkripciju
preko OpenAI Whisper API-ja. Radi za hrvatski i 90+ drugih jezika.

## Arhitektura

```
Lokalna skripta              Server (Render)
─────────────────            ───────────────
1. Skine YouTube audio   →
2. Uploada audio file    →   3. Transkribira preko OpenAI
                          ←   4. Vrati transkript
5. Spremi .txt fajl
```

YouTube download se radi **lokalno** (zaobilazi YouTube bot-detection na
cloud serverima). OpenAI API key živi **samo na serveru** - korisnici
skripte ga nikad ne vide niti ne trebaju imati svoj.

---

## Za korisnike skripte (kolege)

### Setup (jednom)

```bash
pip install -r requirements-cli.txt
```

### Korištenje

```bash
python3 transkriptiraj.py "https://youtube.com/watch?v=XXXXXXXX"
```

Transkript se sprema u `transkripti/` folder pored skripte.

Nema potrebe za API keyom, Whisper modelom, ničim - sve teško posla
radi server.

---

## Za vlasnika servera (deployment)

### Render setup

1. Push `main.py` i `requirements.txt` na GitHub
2. Render → New Web Service → odaberi repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Environment Variables: `OPENAI_API_KEY=sk-...`

### Cijena

OpenAI Whisper API: **$0.006/min** audia. Server (Render free tier): **$0**.

| Korištenje | Cijena |
|---|---|
| 10 sati/mjesec (cijela grupa) | ~$3.60 |

Postavi **Usage Limit** na platform.openai.com → Settings → Limits da
spriječiš neočekivane troškove.
