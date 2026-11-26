# Session Hijacking Lab — NovaBank

Celowo podatna aplikacja webowa (mini-bank) do nauki, jak działa **przejęcie sesji**
(*session hijacking*) i jak się przed nim bronić. Projekt edukacyjny.

> ⚠️ Materiał **wyłącznie edukacyjny**. Uruchamiaj tylko lokalnie, na własnej maszynie.

---

## 🚀 Szybki start

Potrzebujesz tylko **Pythona 3** — żadnych bibliotek, żadnego `pip install`.

```powershell
git clone https://github.com/mipacyna/session-hijacking-lab-baim.git
cd session-hijacking-lab-baim
python app.py
```

Otwórz w przeglądarce **http://localhost:5476** i zaloguj się:

| Konto | Login / hasło |
|---|---|
| Ofiara | `alice` / `password123` |
| Atakujący | `mallory` / `mallory123` |

Nie masz gita? Na GitHubie **Code → Download ZIP**, rozpakuj i w folderze uruchom `python app.py`.
Masz Dockera? Zamiast tego: `docker compose up --build`.

---

## Co pokazuje lab

Mini-bank, na którym można na żywo prześledzić przejęcie cudzej sesji i obronę:

- **XSS** — wstrzyknięty skrypt wykrada ciasteczko sesyjne.
- **Session Fixation** — atakujący narzuca ofierze znany identyfikator sesji.
- **Phishing AiTM** — reverse proxy (`aitm.py`) przechwytuje sesję w locie (jak Evilginx).
- **Tryb obrony** — bezpieczne `Set-Cookie` (`HttpOnly`, `SameSite`) i regeneracja identyfikatora sesji.

Na koncie Alicji ukryta jest **flaga CTF** (`FLAG{...}`) — zdobywasz ją tylko wtedy, gdy wejdziesz
na jej konto z przejętą sesją. To dowód, że atak się udał.

Myśl przewodnia: *sesja to „bilet na okaziciela" — kto ma ciasteczko `SESSIONID`, ten jest
zalogowanym użytkownikiem, bez hasła i bez 2FA.*

---

## Tryby uruchomienia

| Polecenie | Tryb |
|---|---|
| `python app.py` | podatny na XSS, z regeneracją SID |
| `$env:FIXATION=1; python app.py` | podatny na Session Fixation |
| `$env:SECURE=1; python app.py` | bezpieczne ciasteczko (HttpOnly + SameSite) |
| `python aitm.py` | proxy AiTM na porcie 7000 |

Reset stanu labu (salda, sesje): **http://localhost:5476/reset**

---

## Pliki

- `app.py` — podatny bank (czysty Python, bez zależności).
- `aitm.py` — reverse proxy AiTM (symulacja Evilginx).
- `Dockerfile`, `docker-compose.yml` — uruchomienie w kontenerze.
- `start.ps1` — skrót do uruchomienia bez Dockera.
