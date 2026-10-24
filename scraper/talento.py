"""Talento Perú (SERVIR): ofertas laborales del sector público.

El portal es una aplicación JSF/PrimeFaces: la lista se pagina con un POST
AJAX ("Sig.") y el detalle de cada oferta se abre con un POST del botón
"¡Ver más!" de su fila. Las dos cosas funcionan reutilizando el mismo
ViewState de la página de lista, así que se recorre todo con una sola sesión.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from bs4 import BeautifulSoup, Tag

from .client import Client

URL = "https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/ofertas_laborales.xhtml"
FORM = "frmLstOfertsLabo"
AJAX_HEADERS = {"Faces-Request": "partial/ajax", "X-Requested-With": "XMLHttpRequest"}


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date(text: str) -> str | None:
    try:
        return datetime.strptime(clean(text), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def parse_money(text: str) -> float | None:
    m = re.search(r"[\d.,]+", clean(text).replace("S/.", "").replace("S/", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_int(text: str) -> int | None:
    m = re.search(r"\d+", clean(text))
    return int(m.group(0)) if m else None


def regimen(convocatoria: str) -> str:
    """Régimen laboral a partir del número de convocatoria."""
    c = convocatoria.upper()
    if "1057" in c:
        return "CAS"
    if "728" in c:
        return "728"
    if "30057" in c or "SERVICIO CIVIL" in c:
        return "Ley del Servicio Civil"
    if "276" in c:
        return "276"
    return ""


def offer_key(o: dict) -> str:
    """Identificador estable de una oferta a partir de los datos de la lista
    (el N° de SERVIR solo aparece en el detalle)."""
    raw = "|".join(clean(o.get(k, "")).upper() for k in ("entidad", "convocatoria", "cargo", "ubicacion"))
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _labeled(container: Tag) -> dict[str, str]:
    """Pares 'Etiqueta:' -> valor de los spans sub-titulo / detalle-sp."""
    out = {}
    for label in container.select("span.sub-titulo"):
        value = label.find_next_sibling("span", class_="detalle-sp")
        if value:
            out[clean(label.get_text()).rstrip(":").upper()] = clean(value.get_text())
    return out


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    offers = []
    for box in soup.select("div.cuadro-vacantes"):
        title = box.select_one(".titulo-vacante")
        entity = box.select_one(".nombre-entidad")
        fields = _labeled(box)
        ubicacion = fields.get("UBICACIÓN", "")
        dep, _, prov = (p.strip() for p in ubicacion.partition(" - "))
        convocatoria = fields.get("NÚMERO DE CONVOCATORIA", "")
        o = {
            "cargo": clean(title.get_text()) if title else "",
            "entidad": clean(entity.get_text()) if entity else "",
            "ubicacion": ubicacion,
            "departamento": dep,
            "provincia": prov,
            "convocatoria": convocatoria,
            "regimen": regimen(convocatoria),
            "vacantes": parse_int(fields.get("CANTIDAD DE VACANTES", "")),
            "sueldo": parse_money(fields.get("REMUNERACIÓN", "")),
            "inicio": parse_date(fields.get("FECHA INICIO DE PUBLICACIÓN", "")),
            "fin": parse_date(fields.get("FECHA FIN DE PUBLICACIÓN", "")),
        }
        btn = box.find("button", id=re.compile(r"idPnlRepeatPuestos:\d+:j_idt\d+$"), title=re.compile("Ver"))
        o["_button"] = btn["id"] if btn else None
        o["key"] = offer_key(o)
        offers.append(o)
    return offers


def parse_pages(html: str) -> tuple[int, int] | None:
    m = re.search(r"P[áa]gina\s+(\d+)\s+de\s+(\d+)", html)
    return (int(m.group(1)), int(m.group(2))) if m else None


DETAIL_FIELDS = {
    "EXPERIENCIA": "experiencia",
    "FORMACIÓN ACADÉMICA - PERFIL": "formacion",
    "ESPECIALIZACIÓN": "especializacion",
    "CONOCIMIENTO": "conocimientos",
    "COMPETENCIAS": "competencias",
}


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out: dict = {}
    for li in soup.select("#idDatosConvocatoria li"):
        label = li.select_one(".sub-titulo-2")
        value = li.select_one(".detalle-sp")
        if label and value:
            name = DETAIL_FIELDS.get(clean(label.get_text()).rstrip(":").upper())
            if name:
                out[name] = clean(value.get_text())
    link = soup.select_one("#idDatosConvocatoria a[href^=http]")
    if link:
        out["url_bases"] = link["href"].strip()
    # El N° de la oferta está en el recuadro lateral (no confundir con el
    # "Decreto Legislativo N° 1456" del menú).
    for box in soup.select(".cuadro-seccion-lat"):
        m = re.search(r"N°\s*(\d{4,})", box.get_text())
        if m:
            out["id"] = m.group(1)
    return out


def parse_viewstate(text: str) -> str | None:
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', text)
    if m:
        return m.group(1)
    m = re.search(r"ViewState[^>]*><!\[CDATA\[(.*?)\]\]>", text)
    return m.group(1) if m else None


def ajax_update(xml: str, target: str = FORM) -> str | None:
    m = re.search(rf'<update id="{re.escape(target)}"><!\[CDATA\[(.*?)\]\]></update>', xml, re.S)
    return m.group(1) if m else None


@dataclass
class Page:
    number: int
    total: int
    offers: list[dict]


class TalentoPeru:
    def __init__(self, client: Client):
        self.client = client
        self.viewstate: str | None = None
        self.form: dict[str, str] = {}
        self.next_button: str | None = None

    def _load_first(self) -> str:
        html = self.client.request("GET", URL).text
        soup = BeautifulSoup(html, "html.parser")
        self.viewstate = parse_viewstate(html)
        self.form = {i["name"]: i.get("value", "") for i in soup.select(f"#{FORM} input[name]")
                     if i.get("type") in ("hidden", "text", None) and i["name"] != "javax.faces.ViewState"}
        nxt = next((b for b in soup.select(f"#{FORM} button.btn-paginator") if "Sig" in b.get_text()), None)
        self.next_button = nxt["id"] if nxt else None
        if not self.viewstate or not self.next_button:
            raise RuntimeError("No se reconoció la página de Talento Perú (¿cambió el sitio?)")
        return html

    def _next(self) -> str:
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": self.next_button,
            "javax.faces.partial.execute": "@all",
            "javax.faces.partial.render": FORM,
            self.next_button: self.next_button,
            FORM: FORM,
            "javax.faces.ViewState": self.viewstate,
        }
        xml = self.client.request("POST", URL, data=data, headers=AJAX_HEADERS).text
        self.viewstate = parse_viewstate(xml) or self.viewstate
        html = ajax_update(xml)
        if html is None:
            raise RuntimeError("Respuesta AJAX inesperada al pasar de página")
        return html

    def pages(self, max_pages: int | None = None) -> Iterator[Page]:
        html = self._load_first()
        while True:
            pos = parse_pages(html)
            if not pos:
                raise RuntimeError("No se encontró el paginador")
            number, total = pos
            yield Page(number, total, parse_list(html))
            if number >= total or (max_pages and number >= max_pages):
                return
            html = self._next()

    def detail(self, offer: dict) -> dict:
        """Detalle de una oferta de la página actual (usa su botón "¡Ver más!")."""
        if not offer.get("_button"):
            return {}
        data = {**self.form, "javax.faces.ViewState": self.viewstate, offer["_button"]: ""}
        return parse_detail(self.client.request("POST", URL, data=data).text)
