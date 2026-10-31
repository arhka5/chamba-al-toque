"""Catálogo de cursos gratuitos con certificado, para sugerirlos en cada oferta.

    python -m scraper.cursos [--out site/cursos.json]

Fuentes (ambas del Estado, robots.txt lo permite):
- Capacíta-T (MTPE): ~210 cursos permanentes, autoaprendizaje, certificado con QR.
  Lista desde su sitemap de WordPress; horas y certificador desde cada ficha.
- ENAP (SERVIR): cursos MOOC con fecha límite; se leen de gob.pe/cursosmooc.
Se corre desde la PC (gob.pe responde 418 a algunos bots) y el JSON se commitea:
el build solo lo lee.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup

from .client import Client

CAPACITAT_SITEMAP = "https://capacitacionlaboral.trabajo.gob.pe/wp-sitemap-posts-cursos-1.xml"
ENAP_URL = "https://www.gob.pe/cursosmooc"
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "septiembre", "octubre", "noviembre", "diciembre"], 1)}
# gob.pe responde 418 al UA del bot; con un UA de navegador responde normal.
UA_NAVEGADOR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0 Safari/537.36"


def texto(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def parse_ficha_capacitat(html: str, url: str) -> dict | None:
    """Ficha de un curso: título (h1/título de la página), 'N horas', 'Certificado de X', categoría."""
    s = BeautifulSoup(html, "html.parser")
    plano = re.sub(r"\s+", " ", s.get_text(" ", strip=True))
    titulo = texto(s.find("h1")) or texto(s.find("title")).split("»")[0].strip()
    if not titulo:
        return None
    horas = re.search(r"(\d{1,3})\s*horas", plano)
    cert = re.search(r"Certificado de ([^0-9]{3,80}?)\s+\d{1,3}\s*horas", plano)
    # La miga "Inicio › <categoría> › <curso>" va justo antes del título repetido
    # (el menú también empieza con "Inicio": se toma la última coincidencia)
    cat = ([m for m in re.finditer(r"Inicio\s+(.{3,80}?)\s+" + re.escape(titulo), plano)
            if "Rutas Formativas" not in m.group(1)] or [None])[-1]
    return {"fuente": "capacitat", "titulo": titulo, "url": url,
            "horas": int(horas.group(1)) if horas else None,
            "certifica": cert.group(1).strip() if cert else "Ministerio de Trabajo (Capacíta-T)",
            "categoria": cat.group(1).strip() if cat else "", "hasta": None}


def fecha_enap(txt: str, hoy: date) -> str | None:
    """'Disponible hasta el 6 de noviembre de 2026' / '... el 01 de noviembre' → ISO."""
    m = re.search(r"hasta el (\d{1,2}) de (\w+)(?: de (\d{4}))?", txt, re.I)
    if not m or m.group(2).lower() not in MESES:
        return None
    return date(int(m.group(3) or hoy.year), MESES[m.group(2).lower()], int(m.group(1))).isoformat()


def parse_enap(html: str, hoy: date) -> list[dict]:
    """Solo la lista 'Cursos disponibles' (la de 'culminados' ya no admite inscripciones)."""
    s = BeautifulSoup(html, "html.parser")
    titulo = next((d for d in s.find_all(["div", "p", "strong"]) if "Cursos disponibles" in d.get_text()), None)
    lista = titulo.find_next("ul") if titulo else None
    cursos = []
    for li in (lista.find_all("li") if lista else []):
        a = li.find("a")
        t = texto(li)
        horas = re.search(r"(\d{1,3})\s*horas", t)
        if not a or not a.get("href"):
            continue
        cursos.append({"fuente": "enap", "titulo": texto(a).replace("Curso MOOC:", "").strip(), "url": a["href"],
                       "horas": int(horas.group(1)) if horas else None,
                       "certifica": "ENAP – SERVIR", "categoria": "Gestión pública",
                       "hasta": fecha_enap(t, hoy)})
    return cursos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "site" / "cursos.json"))
    ap.add_argument("--max", type=int, default=0, help="tope de fichas de Capacíta-T (pruebas)")
    args = ap.parse_args(argv)
    hoy = date.today()
    c = Client(delay=1.0)
    c.session.headers["User-Agent"] = UA_NAVEGADOR

    cursos = parse_enap(c.request("GET", ENAP_URL).text, hoy)
    print(f"ENAP: {len(cursos)} cursos disponibles")
    urls = re.findall(r"<loc>([^<]+)</loc>", c.request("GET", CAPACITAT_SITEMAP).text)
    urls = [u for u in urls if "/cursos/" in u][: args.max or None]
    for i, u in enumerate(urls, 1):
        try:
            ficha = parse_ficha_capacitat(c.request("GET", u).text, u)
        except Exception as e:  # una ficha rota no frena el resto
            print(f"  ! {u}: {e}")
            continue
        if ficha:
            cursos.append(ficha)
        if i % 25 == 0:
            print(f"  Capacíta-T {i}/{len(urls)}")
    salida = {"actualizado": datetime.now().isoformat(timespec="seconds"), "cursos": cursos}
    Path(args.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(cursos)} cursos → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
