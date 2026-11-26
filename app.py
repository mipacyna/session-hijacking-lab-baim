#!/usr/bin/env python3
"""
NovaBank - CELOWO PODATNA aplikacja do nauki Session Hijacking.

!!! TYLKO DO CELOW EDUKACYJNYCH, URUCHAMIAJ LOKALNIE !!!

Ta aplikacja to TYLKO ofiara (podatny bank). Caly atak wykonujesz
PRAWDZIWYMI narzedziami (DevTools, ncat/python http.server, curl, Wireshark).
Nie ma tu zadnych "magicznych przyciskow" - zobacz README.md.

Wektor XSS: TYTUL PRZELEWU. Atakujacy wysyla ofierze przelew ze zlosliwym
tytulem; skrypt odpala sie, gdy ofiara oglada swoja historie transakcji.

Tryb:
  SECURE=0 (domyslnie) -> cookie BEZ HttpOnly -> document.cookie widzi sesje -> atak dziala.
  SECURE=1             -> cookie z HttpOnly/SameSite -> JS nie widzi sesji -> atak pada.
"""

import http.server
import socketserver
import urllib.parse
import html
import os
import secrets
import datetime

SECURE = os.environ.get("SECURE", "0") == "0"
FIXATION = os.environ.get("FIXATION", "0") == "1"  # 1 = podatne na session fixation
PORT = int(os.environ.get("PORT", "5476"))

# --- "Baza danych" w pamieci ---------------------------------------------
USERS = {
    # OFIARA - bogate konto, ktore chcemy przejac
    "alice": {
        "password": "password123",
        "name": "Alicja Nowak",
        "iban": "PL61 1090 1014 0000 0712 1981 2874",
        "card": "4921",
        "secret": "7781",  # PIN do skrytki depozytowej
        "flag": "FLAG{sesja_przejeta_bez_hasla}",  # CTF: nagroda za przejecie sesji Alicji
    },
    # ATAKUJACY - zwykly, inny klient banku. Ma wlasne (ubogie) konto,
    # z ktorego wysle ofierze przelew ze zlosliwym tytulem (stored XSS).
    "mallory": {
        "password": "mallory123",
        "name": "Marek Zly",
        "iban": "PL27 1050 0099 0000 0001 2345 6789",
        "card": "6610",
        "secret": "0000",
        "flag": "FLAG{to_tylko_twoja_wlasna_sesja_nie_alicji}",  # zaslepka - konto atakujacego
    },
}

SESSIONS = {}  # sessionid -> username


def default_tx():
    # historia transakcji per uzytkownik (najnowsze na gorze)
    return {
        "alice": [
            {"title": "Wynagrodzenie - ACME Sp. z o.o.", "amt": "+6 200,00", "kind": "in"},
            {"title": "Netflix", "amt": "-43,00", "kind": "out"},
            {"title": "Biedronka 2317", "amt": "-137,80", "kind": "out"},
        ],
        "mallory": [
            {"title": "Doladowanie konta", "amt": "+20,00", "kind": "in"},
        ],
    }


def default_balances():
    # saldo w groszach (int), zeby liczyc bez bledow zmiennoprzecinkowych
    return {"alice": 4_250_000, "mallory": 1_230}


TX = default_tx()
BALANCES = default_balances()


def money_to_grosze(s):
    """'1 234,56' / '0,01' / '500' -> int groszy."""
    s = (s or "").strip().replace(" ", "").replace(" ", "").replace(".", "")
    s = s.replace(",", ".")
    try:
        return round(float(s) * 100)
    except ValueError:
        return 0


def grosze_to_money(g):
    """int groszy -> '42 500,00' (ze spacja jako separatorem tysiecy)."""
    sign = "-" if g < 0 else ""
    g = abs(g)
    whole = "{:,}".format(g // 100).replace(",", " ")
    return "%s%s,%02d" % (sign, whole, g % 100)


def new_session(username):
    sid = secrets.token_hex(16)
    SESSIONS[sid] = username
    return sid


def parse_cookies(header):
    jar = {}
    if header:
        for part in header.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                jar[k] = v
    return jar


def current_user(handler):
    jar = parse_cookies(handler.headers.get("Cookie"))
    sid = jar.get("SESSIONID")
    if sid and sid in SESSIONS:
        return SESSIONS[sid]
    return None


# --- Style ---------------------------------------------------------------
CSS = """
<style>
  :root{--bg:#0b1020;--card:#151b2e;--card2:#1b2238;--line:#273150;
        --txt:#e7ecf5;--mut:#8b97b5;--acc:#5b8cff;--grn:#3ad29f;--red:#ff6b7d}
  *{box-sizing:border-box}
  body{font-family:'Segoe UI',system-ui,Arial,sans-serif;margin:0;
       background:radial-gradient(1100px 500px at 75% -10%,#1b2748,transparent),var(--bg);
       color:var(--txt);min-height:100vh}
  a{color:var(--acc);text-decoration:none}
  .wrap{max-width:860px;margin:0 auto;padding:22px}
  .topbar{display:flex;align-items:center;justify-content:space-between;
          padding:14px 0;border-bottom:1px solid var(--line)}
  .logo{font-weight:800;font-size:20px;letter-spacing:.5px}
  .logo span{color:var(--acc)}
  .mode{font-size:12px;font-weight:700;padding:5px 10px;border-radius:999px}
  .nav{display:flex;gap:16px;font-size:14px;color:var(--mut);margin:16px 0}
  .grid{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}
  @media(max-width:720px){.grid{grid-template-columns:1fr}}
  .card{background:linear-gradient(180deg,var(--card),var(--card2));
        border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px}
  .muted{color:var(--mut);font-size:13px}
  h1{font-size:22px;margin:.2rem 0}h2{font-size:16px;margin:0 0 12px}
  .balance{font-size:34px;font-weight:800;letter-spacing:.5px}
  .bankcard{background:linear-gradient(135deg,#2a3566,#3f2f73 60%,#5b8cff);
        border-radius:16px;padding:18px;height:170px;position:relative;
        display:flex;flex-direction:column;justify-content:space-between;
        box-shadow:0 10px 30px rgba(0,0,0,.4)}
  .bankcard .num{font-size:20px;letter-spacing:3px;font-family:monospace}
  .bankcard .chip{width:38px;height:28px;border-radius:6px;
        background:linear-gradient(135deg,#e9d08a,#b8922f)}
  .row{display:flex;justify-content:space-between;align-items:center;
       padding:11px 0;border-bottom:1px solid var(--line)}
  .row:last-child{border-bottom:0}
  .amt.in{color:var(--grn)}.amt.out{color:var(--red)}.amt{font-weight:700;font-family:monospace}
  input,textarea{width:100%;padding:11px;margin:6px 0 12px;border:1px solid var(--line);
        border-radius:10px;background:#0e1424;color:var(--txt);font-size:15px}
  button{background:var(--acc);color:#fff;border:0;padding:11px 16px;border-radius:10px;
        font-size:15px;font-weight:600;cursor:pointer}
  .pill{display:inline-block;background:#0e1424;border:1px solid var(--line);
        border-radius:8px;padding:2px 8px;font-family:monospace;font-size:13px}
  .danger{color:var(--red);font-weight:700}
  .center{min-height:100vh;display:flex;align-items:center;justify-content:center}
  .login{width:380px}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  pre{background:#0e1424;border:1px solid var(--line);border-radius:10px;padding:12px;
      overflow:auto;font-size:13px}
</style>
"""


def shell(title, inner, chrome=True):
    if SECURE:
        badge = "<span class='mode' style='background:#10351f;color:#3ad29f'>SECURE - HttpOnly ON</span>"
    else:
        badge = "<span class='mode' style='background:#3a1018;color:#ff6b7d'>VULNERABLE - no HttpOnly</span>"
    nav = ""
    if chrome:
        nav = ("<div class='nav'><a href='/dashboard'>Pulpit</a>"
               "<a href='/logout'>Wyloguj</a><a href='/reset'>Reset labu</a></div>")
    return ("<!doctype html><html lang='pl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + html.escape(title) + " - NovaBank</title>" + CSS + "</head><body><div class='wrap'>"
            "<div class='topbar'><div class='logo'>Nova<span>Bank</span></div>" + badge + "</div>"
            + nav + inner + "</div></body></html>")


def view_login(msg=""):
    note = "<p class='danger'>" + html.escape(msg) + "</p>" if msg else ""
    inner = ("<div class='center'><div class='card login'>"
             "<h1>Zaloguj sie</h1><p class='muted'>Bankowosc internetowa NovaBank24</p>" + note +
             "<form method='POST' action='/login'>"
             "<label class='muted'>Identyfikator</label><input name='username' value='alice' autofocus>"
             "<label class='muted'>Haslo</label><input name='password' type='password' value='password123'>"
             "<button type='submit' style='width:100%'>Zaloguj</button></form>"
             "<p class='muted' style='margin-top:14px'>Konto demo: <span class='pill'>alice</span> / "
             "<span class='pill'>password123</span></p></div></div>")
    return shell("Logowanie", inner, chrome=False)


def view_dashboard(username):
    u = USERS[username]
    tx_html = ""
    for t in TX.get(username, []):
        # !!! PODATNOSC: tytul przelewu (title) NIE jest escapowany -> stored XSS !!!
        # kwota i rodzaj sa bezpieczne, ale 'title' trafia do HTML surowo:
        tx_html += ("<div class='row'><div>" + t["title"] +
                    "</div><div class='amt " + t["kind"] + "'>" +
                    html.escape(t["amt"]) + " PLN</div></div>")
    inner = (
        "<h1>Czesc, " + html.escape(u["name"]) + " 👋</h1>"
        "<div class='grid'>"
          "<div class='card'><div class='muted'>Rachunek osobisty</div>"
          "<div class='balance'>" + grosze_to_money(BALANCES.get(username, 0)) + " PLN</div>"
          "<div class='muted' style='margin-top:6px'>" + html.escape(u["iban"]) + "</div></div>"
          "<div class='bankcard'><div class='chip'></div>"
          "<div><div class='num'>**** **** **** " + html.escape(u["card"]) + "</div>"
          "<div style='display:flex;justify-content:space-between;margin-top:8px;font-size:12px'>"
          "<span>" + html.escape(u["name"].upper()) + "</span><span>08/27</span></div></div></div>"
        "</div>"
        "<div class='card'><h2>Historia transakcji</h2>" + tx_html + "</div>"
        "<div class='card'><h2>Dane wrazliwe</h2>"
          "<div class='row'><div class='muted'>PIN do skrytki depozytowej</div>"
          "<div class='danger pill'>" + html.escape(u["secret"]) + "</div></div></div>"
        "<div class='card' style='border:1px solid #3ad29f'><h2>🚩 Flaga (CTF)</h2>"
          "<div class='muted' style='margin-bottom:10px'>Widoczna tylko dla zalogowanego "
          "wlasciciela konta. Flage Alicji zdobedziesz WYLACZNIE majac jej sesje (cookie).</div>"
          "<div class='pill' style='font-size:16px;color:#3ad29f;letter-spacing:.5px'>"
          + html.escape(u["flag"]) + "</div></div>"
        "<div class='card'><h2>Wyslij przelew</h2>"
          "<form method='POST' action='/transfer'>"
          "<div class='two'>"
            "<div><label class='muted'>Odbiorca (login)</label>"
            "<input name='to' value='alice'></div>"
            "<div><label class='muted'>Kwota (PLN)</label>"
            "<input name='amount' value='0,01'></div>"
          "</div>"
          "<label class='muted'>Tytul przelewu</label>"
          "<input name='title' placeholder='np. Za obiad'>"
          "<button type='submit'>Wyslij przelew</button></form></div>"
    )
    return shell("Pulpit", inner)


# --- HTTP ----------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), fmt % a))

    def html(self, body, cookie=None, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def redirect(self, loc, cookie=None):
        self.send_response(303)
        self.send_header("Location", loc)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def session_cookie(self, sid):
        # JEDYNA roznica miedzy trybem podatnym i bezpiecznym:
        if SECURE:
            return "SESSIONID=" + sid + "; Path=/; HttpOnly; SameSite=Strict"
        return "SESSIONID=" + sid + "; Path=/"  # brak HttpOnly -> JS odczyta cookie

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        # SESSION FIXATION: atakujacy podsadza ofierze znany SID przez link ?sid=...
        # (dziala tylko w trybie podatnym FIXATION=1)
        if FIXATION and "sid" in qs:
            return self.redirect(path, cookie="SESSIONID=" + qs["sid"][0] + "; Path=/")
        user = current_user(self)
        if path == "/":
            return self.redirect("/dashboard" if user else "/login")
        if path == "/login":
            return self.html(view_login())
        if path == "/logout":
            jar = parse_cookies(self.headers.get("Cookie"))
            SESSIONS.pop(jar.get("SESSIONID", ""), None)
            return self.redirect("/login")
        if path == "/dashboard":
            if not user:
                return self.redirect("/login")
            return self.html(view_dashboard(user))
        if path == "/reset":
            SESSIONS.clear()
            TX.clear()
            TX.update(default_tx())
            BALANCES.clear()
            BALANCES.update(default_balances())
            return self.redirect("/login")
        self.html(shell("404", "<div class='card'>Nie znaleziono.</div>"), status=404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
        if self.path == "/login":
            un = data.get("username", [""])[0]
            pw = data.get("password", [""])[0]
            u = USERS.get(un)
            if u and u["password"] == pw:
                existing = parse_cookies(self.headers.get("Cookie")).get("SESSIONID")
                if FIXATION and existing:
                    # !!! PODATNOSC: brak regeneracji - sesja zostaje na SID narzuconym ofierze
                    SESSIONS[existing] = un
                    sid = existing
                else:
                    # OBRONA: regeneracja SID po zalogowaniu (nowy, losowy identyfikator)
                    sid = new_session(un)
                return self.redirect("/dashboard", cookie=self.session_cookie(sid))
            return self.html(view_login("Bledny identyfikator lub haslo."))
        if self.path == "/transfer":
            sender = current_user(self)
            if not sender:
                return self.redirect("/login")
            to = data.get("to", [""])[0].strip()
            grosze = money_to_grosze(data.get("amount", ["0,01"])[0])
            title = data.get("title", [""])[0]  # <- tytul; trafi do HTML ofiary surowo
            if to in USERS and to != sender and grosze > 0:
                # REALNE ksiegowanie: hajs ubywa nadawcy, przybywa odbiorcy
                BALANCES[sender] = BALANCES.get(sender, 0) - grosze
                BALANCES[to] = BALANCES.get(to, 0) + grosze
                disp = grosze_to_money(grosze)
                TX.setdefault(to, []).insert(0, {"title": title, "amt": "+" + disp, "kind": "in"})
                TX.setdefault(sender, []).insert(0, {
                    "title": "Przelew do " + html.escape(to) + ": " + title,
                    "amt": "-" + disp, "kind": "out"})
            return self.redirect("/dashboard")
        self.redirect("/")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    print("=" * 56)
    print(" NovaBank - LAB Session Hijacking")
    print(" Tryb:", "SECURE (HttpOnly)" if SECURE else "VULNERABLE (brak HttpOnly)")
    print(" Session fixation:", "WLACZONA (podatne)" if FIXATION else "wylaczona (regeneracja SID)")
    print(" http://localhost:%d/" % PORT)
    print("=" * 56)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
