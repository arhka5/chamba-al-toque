"""Avisa a Google (Indexing API) de las ofertas nuevas y de las que cerraron.

Google solo permite esta API para páginas con JobPosting (SEO_SPEC 5.5), así que se
avisa únicamente de URLs de oferta: las vigentes (con JobPosting en public/) que aún
no se avisaron, y las ya avisadas que perdieron el marcado al cerrar. Las cerradas
siguen respondiendo 200 con noindex, por eso van como URL_UPDATED (URL_DELETED es
para páginas que ya no existen): Google las vuelve a rastrear y las saca.

    python herramientas/indexing.py public out/state.json

Necesita GOOGLE_INDEXING_KEY (el JSON de la cuenta de servicio, agregada como
propietaria de la propiedad en Search Console). Sin ella no hace nada.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://indexing.googleapis.com/v3/urlNotifications:publish"
CUPO = int(os.environ.get("INDEXING_CUPO", "95"))  # por corrida; Google da 200 al día y hay 2 corridas
DIAS_NUEVA = 3  # al empezar, solo se avisan las publicadas hace poco: las demás ya están en el sitemap

LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def vigentes(sitio: Path) -> dict[str, str]:
    """URL -> datePosted de cada página con JobPosting."""
    salida = {}
    for f in sitio.rglob("index.html"):
        html = f.read_text(encoding="utf-8")
        if '"JobPosting"' not in html:
            continue
        for bloque in LD.findall(html):
            jp = json.loads(bloque)
            if jp.get("@type") == "JobPosting":
                salida[jp["url"]] = jp.get("datePosted") or ""
    return salida


def pendientes(vivas: dict[str, str], avisadas: dict[str, str], hoy: date) -> tuple[list[str], list[str], list[str]]:
    """(nuevas por avisar, cerradas por avisar, viejas que se marcan sin avisar)."""
    desde = (hoy - timedelta(days=DIAS_NUEVA)).isoformat()
    sin_avisar = [u for u in vivas if u not in avisadas]
    nuevas = sorted((u for u in sin_avisar if vivas[u] >= desde), key=lambda u: vivas[u], reverse=True)
    viejas = [u for u in sin_avisar if vivas[u] < desde]
    cerradas = sorted(u for u in avisadas if u not in vivas)
    return nuevas, cerradas, viejas


def token(clave: dict) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    cred = service_account.Credentials.from_service_account_info(
        clave, scopes=["https://www.googleapis.com/auth/indexing"])
    cred.refresh(Request())
    return cred.token


def avisar(url: str, tk: str) -> int:
    import urllib.error
    import urllib.request
    cuerpo = json.dumps({"url": url, "type": "URL_UPDATED"}).encode()
    pedido = urllib.request.Request(API, data=cuerpo, headers={"Content-Type": "application/json",
                                                               "Authorization": f"Bearer {tk}"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        if e.code != 429:
            print(f"  {e.code} {url}: {e.read().decode('utf-8', 'replace')[:200]}")
        return e.code


def main(argv: list[str]) -> int:
    sitio, estado = Path(argv[0]), Path(argv[1])
    clave = os.environ.get("GOOGLE_INDEXING_KEY")
    if not clave:
        print("Indexing API sin configurar (falta GOOGLE_INDEXING_KEY): no se avisa a Google.")
        return 0
    state = json.loads(estado.read_text(encoding="utf-8"))
    avisadas: dict[str, str] = state.setdefault("indexing", {})
    hoy = datetime.now(timezone(timedelta(hours=-5))).date()
    nuevas, cerradas, viejas = pendientes(vigentes(sitio), avisadas, hoy)
    for u in viejas:
        avisadas[u] = "sitemap"

    tk, enviadas, cupo_lleno = token(json.loads(clave)), {"nuevas": 0, "cerradas": 0}, False
    # primero las nuevas (más recientes antes); lo que sobre del cupo, para las cerradas
    for tipo, lista in (("nuevas", nuevas), ("cerradas", cerradas)):
        for url in lista:
            if sum(enviadas.values()) >= CUPO or cupo_lleno:
                break
            codigo = avisar(url, tk)
            if codigo == 429:
                cupo_lleno = True
                break
            if codigo == 200:
                enviadas[tipo] += 1
                if tipo == "nuevas":
                    avisadas[url] = hoy.isoformat()
                else:
                    del avisadas[url]
    estado.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Indexing API: {enviadas['nuevas']}/{len(nuevas)} nuevas y {enviadas['cerradas']}/{len(cerradas)} "
          f"cerradas avisadas; {len(viejas)} anteriores marcadas sin avisar"
          + (" · Google dijo que se acabó el cupo del día" if cupo_lleno else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
