# Transkriptiraj

Skida audio s YouTube videa i transkribira ga preko OpenAI Whisper API-ja.
Radi za hrvatski i 90+ drugih jezika. Nema servera, nema cloud hostinga —
sve se izvršava lokalno, samo poziva OpenAI API za transkripciju.

---

## Setup (jednom)

### 1. Instaliraj Python pakete

```bash
pip install -r requirements-cli.txt
```

### 2. Postavi OpenAI API key

**Windows:**
```cmd
set OPENAI_API_KEY=sk-tvoj-kljuc-ovdje
```

**Mac/Linux:**
```bash
export OPENAI_API_KEY=sk-tvoj-kljuc-ovdje
```

> Napomena: ova varijabla vrijedi samo za trenutni terminal. Ako zatvoriš
> terminal, trebat ćeš je postaviti opet. Za trajno rješenje dodaj liniju
> u `~/.bashrc` (Linux/Mac) ili Windows Environment Variables.

---

## Korištenje

```bash
python transkriptiraj.py "https://youtube.com/watch?v=XXXXXXXX"
```

Skripta će:
1. Skinuti audio s videa lokalno
2. Poslati ga na OpenAI Whisper API
3. Spremiti transkript kao `.txt` fajl u trenutnom folderu

---

## Cijena

OpenAI Whisper API naplaćuje **$0.006 po minuti** audia.

| Video | Cijena |
|---|---|
| 10 min | ~$0.06 |
| 1 sat | ~$0.36 |

Sa $5 kredita možeš transkribirati otprilike **800 minuta** (13+ sati) videa.

---

## Zašto lokalno, a ne kao web stranica?

YouTube blokira download requeste koji dolaze s cloud servera (Render,
Railway, AWS itd.) jer ih prepoznaje kao bot traffic. Pokretanjem skripte
na svom računalu, download dolazi s normalne kućne IP adrese pa YouTube
ne stvara probleme.
