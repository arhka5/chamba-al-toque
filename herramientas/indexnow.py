"""Avisa a Bing (IndexNow) de las páginas nuevas o cambiadas del sitio publicado.

La búsqueda de ChatGPT usa el índice de Bing, y ChatGPT ya trae más visitas que Google
a las ofertas: cuanto antes Bing conozca una oferta, antes puede citarse. IndexNow
avisa también a Yandex, Seznam y Naver con la misma llamada.

    python herramientas/indexnow.py public out/state.json

Lee los sitemaps de public/ y avisa las URL cuyo lastmod cambió desde el último aviso
(guardado en state["indexnow"]). La clave es pública por diseño: el archivo
<CLAVE>.txt en la raíz del sitio prueba que el dominio es nuestro.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CLAVE = "74f7eed25ace672aa6a6690f93c1e6a5"  # = site/static/<CLAVE>.txt
API = "https://api.indexnow.org/indexnow"
LOTE = 10000  # máximo de URL por llamada según el protocolo
URL_LASTMOD = re.compile(r"<url><loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?")


def urls_del_sitemap(sitio: Path) -> dict[str, str]:
    salida = {}
    for f in sitio.glob("sitemap*.xml"):
        for loc, lastmod in URL_LASTMOD.findall(f.read_text(encoding="utf-8")):
            salida[loc] = lastmod or ""
    return salida


def pendientes(actuales: dict[str, str], avisadas: dict[str, str]) -> list[str]:
    return [u for u, lm in actuales.items() if avisadas.get(u) != lm]


def avisar(urls: list[str]) -> int:
    host = urlparse(urls[0]).netloc
    cuerpo = json.dumps({"host": host, "key": CLAVE, "keyLocation": f"https://{host}/{CLAVE}.txt",
                         "urlList": urls}).encode()
    req = urllib.request.Request(API, data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main(argv=None) -> int:
    args = argv or sys.argv[1:]
    sitio, state_path = Path(args[0]), Path(args[1])
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    avisadas = state.setdefault("indexnow", {})
    actuales = urls_del_sitemap(sitio)
    lista = pendientes(actuales, avisadas)
    if not lista:
        print("IndexNow: nada nuevo")
        return 0
    enviadas = 0
    for i in range(0, len(lista), LOTE):
        lote = lista[i:i + LOTE]
        estado = avisar(lote)
        print(f"IndexNow: {len(lote)} URL → HTTP {estado}")
        if estado not in (200, 202):  # 403 clave no encontrada, 422 URL de otro host, 429 demasiadas
            break
        for u in lote:
            avisadas[u] = actuales[u]
        enviadas += len(lote)
    # Las URL que ya no están en el sitemap se olvidan para que el estado no crezca
    for u in [u for u in avisadas if u not in actuales]:
        del avisadas[u]
    state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"IndexNow: {enviadas} de {len(lista)} avisadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
