"""Talento Perú (SERVIR): prácticas preprofesionales y profesionales.

Misma aplicación JSF que las ofertas laborales (mismo ViewState para paginar y
abrir detalles), con otra página y otro formulario. Las etiquetas de la lista
son <div> en vez de <span> y el detalle tiene secciones con listas.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .talento import TalentoPeru, clean, offer_key, parse_date, parse_int

URL = "https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/modalidades_formativas.xhtml"
FORM = "frmLstModFormativas"


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for box in soup.select("div.cuadro-vacantes"):
        campos = {}
        for etiqueta in box.select(".sub-titulo"):
            valor = etiqueta.find_next_sibling(class_="detalle-sp")
            if valor:
                campos[clean(etiqueta.get_text()).rstrip(":").upper()] = clean(valor.get_text())
        titulo = box.select_one(".titulo-vacante label") or box.select_one(".titulo-vacante")
        entidad = box.select_one(".nombre-entidad")
        ubicacion = re.sub(r"\s*-\s*", " - ", campos.get("UBICACIÓN", ""))
        dep, _, prov = (p.strip() for p in ubicacion.partition(" - "))
        p = {
            "cargo": clean(titulo.get_text()) if titulo else "",
            "entidad": clean(entidad.get_text()) if entidad else "",
            "modalidad": campos.get("TIPO DE MODALIDAD", ""),
            "ubicacion": ubicacion,
            "departamento": dep,
            "provincia": prov,
            "convocatoria": campos.get("NÚMERO DE CONVOCATORIA", ""),
            "vacantes": parse_int(campos.get("NÚMERO DE VACANTE", "")),
            "inicio": parse_date(campos.get("INICIO DE PUBLICACIÓN", "")),
            "fin": parse_date(campos.get("CIERRE DE PUBLICACIÓN", "")),
        }
        btn = box.find("button", id=re.compile(r"idPnlRepeatPuestos:\d+:j_idt\d+$"), title=re.compile("Ver más"))
        p["_button"] = btn["id"] if btn else None
        p["key"] = offer_key(p)
        out.append(p)
    return out


def _secciones(soup: BeautifulSoup) -> dict[str, list[str]]:
    """'Actividades', 'Requerimientos', 'Beneficios'… -> lista de sus ítems."""
    out = {}
    for t in soup.select("span.sub-titulo-2"):
        fila = t.find_parent("div", class_="row")
        if not fila:
            continue
        items = [clean(li.get_text()) for li in fila.select("li")]
        if not items:
            texto = clean(fila.get_text(" ")).removeprefix(clean(t.get_text())).strip()
            items = [texto] if texto else []
        out[clean(t.get_text()).upper()] = [i for i in items if i]
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style"]):
        s.decompose()
    sec = _secciones(soup)
    texto = clean(soup.get_text(" "))
    out: dict = {
        "actividades": " ".join(sec.get("ACTIVIDADES", [])),
        # "-Word nivel intermedio. -Excel nivel intermedio." llega como un solo ítem
        "conocimientos": [x.strip(" .") for i in sec.get("CONOCIMIENTOS BÁSICOS", sec.get("CONOCIMIENTOS", []))
                          # "¿" es una viñeta mal codificada en la fuente
                          for x in re.split(r"(?:^|\s)[-•¿]\s*", i) if x.strip(" .")],
    }
    req = sec.get("REQUERIMIENTOS", [])
    out["condicion"] = next((i for i in req if re.match(r"(?i)(egresad|estudiant|bachiller|titulad)", i)), "")
    out["formacion"] = next((i for i in req if re.search(r"(?i)carrera|universitari|t[ée]cnic", i)), "")
    out["carreras"] = [i for i in req if i not in (out["condicion"], out["formacion"])]
    beneficios = " ".join(sec.get("BENEFICIOS", []))
    m = re.search(r"S/\.?\s*([\d.,]+)", beneficios)
    out["subvencion"] = float(m.group(1).replace(",", "")) if m else None
    m = re.search(r"(\d+)\s*mes", beneficios)
    out["duracion_meses"] = int(m.group(1)) if m else None
    m = re.search(r"(\d+)\s*horas", beneficios)
    out["horas_semana"] = int(m.group(1)) if m else None
    m = re.search(r"Modalidad:\s*([A-Za-zÁÉÍÓÚáéíóú]+)", texto)
    out["modo"] = m.group(1).capitalize() if m else ""
    m = re.search(r"P[áa]gina Web:\s*(https?://\S+)", texto)
    if m:
        out["url_bases"] = m.group(1).rstrip(".,")
    return out


class Practicas(TalentoPeru):
    url = URL
    form_id = FORM
    parse_list = staticmethod(parse_list)
    parse_detail = staticmethod(parse_detail)
