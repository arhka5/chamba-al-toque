"""Descarga las ofertas vigentes de Talento Perú y escribe ofertas.json.

Uso: python -m scraper --previous data/ofertas.json --output out/ofertas.json

El detalle (requisitos, enlace a las bases, N° de oferta) cuesta una
petición por oferta, así que solo se pide para las ofertas nuevas y con un
tope por corrida; las demás reutilizan el detalle de la corrida anterior.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .client import Client
from .practicas import Practicas
from .talento import TalentoPeru

LIMA = timezone(timedelta(hours=-5))
DETAIL_KEYS = ("id", "experiencia", "formacion", "especializacion", "conocimientos",
               "competencias", "url_bases")
DETALLE_PRACTICA = ("actividades", "conocimientos", "condicion", "formacion", "carreras", "subvencion",
                    "duracion_meses", "horas_semana", "modo", "url_bases")


def load_previous(path: str | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def scrape_practicas(client: Client, previas: list[dict], today: str) -> tuple[list[dict], dict]:
    """Prácticas (13 páginas, ~130 avisos). El detalle se pide solo para las
    nuevas. No tienen N.° de SERVIR: su id es la clave de la lista. Si la
    corrida falla, se conservan las anteriores que sigan vigentes."""
    prev = {p["key"]: p for p in previas}
    crawler = Practicas(client)
    out: dict[str, dict] = {}
    vistas: dict[str, int] = {}
    error, nuevas = None, 0
    try:
        for page in crawler.pages():
            for p in page.offers:
                vistas[p["key"]] = vistas.get(p["key"], 0) + 1
                if vistas[p["key"]] > 1:
                    p["key"] = f"{p['key']}-{vistas[p['key']]}"
                anterior = prev.get(p["key"])
                if anterior and anterior.get("id"):
                    p.update({k: anterior[k] for k in DETALLE_PRACTICA if k in anterior})
                    p["visto"] = anterior.get("visto", today)
                else:
                    p["visto"] = today
                    try:
                        p.update(crawler.detail(p))
                        nuevas += 1
                    except Exception as exc:
                        print(f"  detalle de práctica falló ({p['cargo'][:40]}): {exc}", file=sys.stderr)
                p["id"] = p["key"]
                p.pop("_button", None)
                out[p["key"]] = p
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"ERROR en prácticas: {error}", file=sys.stderr)
        for k, p in prev.items():
            out.setdefault(k, p)
    vigentes = [p for p in out.values() if not p.get("fin") or p["fin"] >= today]
    vigentes.sort(key=lambda p: (p.get("inicio") or "", p.get("fin") or ""), reverse=True)
    return vigentes, {"ok": error is None, "error": error, "detailsFetched": nuevas}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous")
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-detalles", type=int, default=1500)
    ap.add_argument("--max-paginas", type=int)
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args(argv)

    previous = load_previous(args.previous)
    prev_by_key = {o["key"]: o for o in previous.get("offers", [])}
    today = datetime.now(LIMA).date().isoformat()

    client = Client(delay=args.delay)
    talento = TalentoPeru(client)
    offers: dict[str, dict] = {}
    budget = args.max_detalles
    fetched = reused = 0
    pages = total = 0
    error = None
    started = time.monotonic()
    repeticiones: dict[str, int] = {}
    try:
        for page in talento.pages(args.max_paginas):
            pages, total = page.number, page.total
            for o in page.offers:
                # SERVIR lista filas idénticas para plazas distintas (mismo
                # cargo y N.° de convocatoria): se numeran -2, -3... y al final
                # se deduplica por el N.° de oferta del detalle.
                base = o["key"]
                repeticiones[base] = repeticiones.get(base, 0) + 1
                if repeticiones[base] > 1:
                    o["key"] = f"{base}-{repeticiones[base]}"
                prev = prev_by_key.get(o["key"])
                if prev and prev.get("id"):
                    o.update({k: prev[k] for k in DETAIL_KEYS if k in prev})
                    o["visto"] = prev.get("visto", today)
                    reused += 1
                else:
                    o["visto"] = today
                    if budget > 0:
                        try:
                            o.update(talento.detail(o))
                            fetched += 1
                        except Exception as exc:  # un detalle roto no tumba la corrida
                            print(f"  detalle falló ({o['cargo'][:40]}): {exc}", file=sys.stderr)
                        budget -= 1
                o.pop("_button", None)
                offers[o["key"]] = o
            if page.number % 25 == 0:
                print(f"página {page.number}/{page.total} · {len(offers)} ofertas · "
                      f"{fetched} detalles nuevos · {client.requests} peticiones", flush=True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"ERROR en la página {pages + 1}: {error}", file=sys.stderr)

    complete = error is None and (pages == total or talento.total_reducido)
    if not complete:
        # Corrida incompleta: se completa con lo anterior que siga vigente.
        for key, o in prev_by_key.items():
            offers.setdefault(key, o)

    # Deduplicar por N.° de SERVIR (una fila repetida por paginación corrida
    # trae el mismo N.°).
    por_id: dict[str, dict] = {}
    unicas = []
    for o in offers.values():
        if o.get("id"):
            if o["id"] in por_id:
                continue
            por_id[o["id"]] = o
        unicas.append(o)
    vigentes = [o for o in unicas if not o.get("fin") or o["fin"] >= today]
    vigentes.sort(key=lambda o: (o.get("inicio") or "", o.get("fin") or ""), reverse=True)

    practicas, estado_practicas = scrape_practicas(client, previous.get("practicas", []), today)
    print(f"{len(practicas)} prácticas vigentes · {estado_practicas['detailsFetched']} detalles nuevos"
          + (f" · ERROR {estado_practicas['error']}" if estado_practicas["error"] else ""))

    result = {
        "generatedAt": datetime.now(LIMA).isoformat(timespec="seconds"),
        "source": {
            "name": "Talento Perú (SERVIR)",
            "url": "https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/ofertas_laborales.xhtml",
            "ok": complete,
            "error": error,
            "pages": pages,
            "totalPages": total,
            "requests": client.requests,
            "detailsFetched": fetched,
            "detailsReused": reused,
            "seconds": round(time.monotonic() - started),
        },
        "offers": vigentes,
        "practicasSource": estado_practicas,
        "practicas": practicas,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sin_detalle = sum(1 for o in vigentes if not o.get("id"))
    print(f"{len(vigentes)} ofertas vigentes ({sin_detalle} sin detalle aún) · "
          f"{pages}/{total} páginas · {client.requests} peticiones · completo={complete}")
    # Falla la corrida solo si no hay nada que publicar.
    return 0 if vigentes else 1


if __name__ == "__main__":
    sys.exit(main())
