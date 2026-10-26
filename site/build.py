"""Genera el sitio estático de Chamba al Toque a partir de ofertas.json.

Uso: python site/build.py --data out/ofertas.json --out public [--state state.json]

Sigue docs/SEO_SPEC.md: una página por oferta con JobPosting, listados por
departamento, entidad y tema, ofertas cerradas con noindex durante 30 días,
sitemaps con lastmod real y validaciones antes de publicar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import textos as T  # noqa: E402

LIMA = timezone(timedelta(hours=-5))
BASE_URL = "https://chambearhoy.toca.pe"
REPO = "https://github.com/arhka5/chamba-al-toque"
FUENTE_URL = "https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/ofertas_laborales.xhtml"

POR_PAGINA = 25
UMBRAL_ENTIDAD = 3
UMBRAL_TEMA = 20
UMBRAL_DEP_TEMA = 10
DIAS_CERRADA = 30
MIN_PROPORCION = 0.5  # salvaguarda: no publicar si llega menos de la mitad
PORTADA_ULTIMAS = 24
SUELDO_MINIMO_CREIBLE = 300  # por debajo es un error de carga (hay ofertas con "S/ 1")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]

DEPARTAMENTOS = {
    "AMAZONAS": "Amazonas", "ANCASH": "Áncash", "APURIMAC": "Apurímac", "AREQUIPA": "Arequipa",
    "AYACUCHO": "Ayacucho", "CAJAMARCA": "Cajamarca", "CALLAO": "Callao", "CUSCO": "Cusco",
    "HUANCAVELICA": "Huancavelica", "HUANUCO": "Huánuco", "ICA": "Ica", "JUNIN": "Junín",
    "LA LIBERTAD": "La Libertad", "LAMBAYEQUE": "Lambayeque", "LIMA": "Lima", "LORETO": "Loreto",
    "MADRE DE DIOS": "Madre de Dios", "MOQUEGUA": "Moquegua", "PASCO": "Pasco", "PIURA": "Piura",
    "PUNO": "Puno", "SAN MARTIN": "San Martín", "TACNA": "Tacna", "TUMBES": "Tumbes",
    "UCAYALI": "Ucayali",
}

REGIMENES = {
    "CAS": ("CAS (D.Leg. 1057)", "Convocatoria CAS", ["FULL_TIME"]),
    "728": ("Régimen laboral privado (D.Leg. 728)", "Convocatoria D.Leg. 728", ["FULL_TIME"]),
    "276": ("Carrera administrativa (D.Leg. 276)", "Convocatoria D.Leg. 276", ["FULL_TIME"]),
    "Ley del Servicio Civil": ("Ley del Servicio Civil (Ley 30057)", "Convocatoria del Servicio Civil", ["FULL_TIME"]),
}

TEMAS = [
    {
        "slug": "convocatorias-cas", "nombre": "Convocatorias CAS",
        "title": "Convocatorias CAS {anio}: ofertas vigentes en el Estado",
        "h1": "Convocatorias CAS {anio}",
        "intro": "Convocatorias del régimen CAS (Decreto Legislativo 1057), el más usado por municipalidades, "
                 "ministerios y hospitales para contratar personal.",
        "filtro": lambda o: o["regimen"] == "CAS",
    },
    {
        "slug": "sin-experiencia", "nombre": "Sin experiencia",
        "title": "Trabajos en el Estado sin experiencia {anio}",
        "h1": "Trabajos sin experiencia en entidades públicas {anio}",
        "intro": "Convocatorias públicas donde la entidad no pide experiencia laboral previa.",
        "filtro": lambda o: o["req"]["sin_experiencia"],
    },
    {
        "slug": "hasta-un-ano-de-experiencia", "nombre": "Hasta 1 año de experiencia",
        "title": "Trabajos en el Estado con poca experiencia {anio}: hasta 1 año",
        "h1": "Convocatorias que piden hasta 1 año de experiencia {anio}",
        "intro": "Casi todas las plazas del Estado piden algo de experiencia. Aquí están las que piden un año "
                 "o menos, o ninguna.",
        "filtro": lambda o: o["req"]["hasta_un_anio"],
    },
    {
        "slug": "secundaria-completa", "nombre": "Solo secundaria",
        "title": "Trabajos en el Estado con secundaria completa {anio}",
        "h1": "Convocatorias que piden solo secundaria completa {anio}",
        "intro": "Convocatorias públicas que piden como máximo secundaria completa, o que no piden un nivel de estudios.",
        "filtro": lambda o: o["req"]["solo_secundaria"],
    },
]


# Páginas informativas. lastmod: cambiarlo al editar el texto de la plantilla.
INFO = [
    {"slug": "acerca", "title": "Acerca de Chamba al Toque", "h1": "Acerca de Chamba al Toque", "indexable": True,
     "lastmod": "2026-10-23",
     "desc": "Qué es Chamba al Toque, quién lo hace, de dónde salen las convocatorias (Talento Perú, SERVIR) "
             "y cada cuánto se actualizan."},
    {"slug": "aviso-legal", "title": "Aviso legal | Chamba al Toque", "h1": "Aviso legal", "indexable": True,
     "lastmod": "2026-10-23",
     "desc": "Datos tomados de Talento Perú, sin cobros y sin pedir datos personales. Cómo corregir o retirar "
             "una convocatoria publicada en Chamba al Toque."},
    {"slug": "privacidad", "title": "Privacidad | Chamba al Toque", "h1": "Privacidad", "indexable": False,
     "lastmod": "2026-10-23",
     "desc": "Chamba al Toque no usa cookies ni pide datos personales. Qué datos técnicos puede registrar el "
             "alojamiento del sitio."},
    {"slug": "contacto", "title": "Contacto | Chamba al Toque", "h1": "Contacto", "indexable": True,
     "lastmod": "2026-10-23",
     "desc": "Cómo reportar un error o una convocatoria sospechosa en Chamba al Toque. Respondemos en 48 horas."},
]


# ---------------------------------------------------------------- formato

def fecha_larga(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]}"


def soles(n: float | None) -> str:
    if not n:
        return ""
    return f"S/ {n:,.0f}" if float(n).is_integer() else f"S/ {n:,.2f}"


def miles(n: int) -> str:
    return f"{n:,}"


def plural(n: int, uno: str, varios: str) -> str:
    return f"{miles(n)} {uno if n == 1 else varios}"


def cortar(texto: str, maximo: int) -> str:
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo].rsplit(" ", 1)[0].rstrip(",;:")
    return corte if corte.endswith(".") else corte + "…"


def armar(frases: list[str], maximo: int = 155) -> str:
    """Junta frases completas en orden de prioridad mientras quepan; nunca
    corta una frase a la mitad (salvo la primera, si sola no cabe)."""
    frases = [f for f in frases if f]
    if not frases:
        return ""
    out = [frases[0] if len(frases[0]) <= maximo else cortar(frases[0], maximo)]
    for f in frases[1:]:
        if len(" ".join(out + [f])) <= maximo:
            out.append(f)
    return " ".join(out)


def lista_cargos(cargos: list[str], maximo: int = 70) -> str:
    """'chofer, secretaria y otros' con cargos completos hasta 3."""
    unicos = list(dict.fromkeys(cargos))
    tomados = []
    for c in unicos[:3]:
        if len(", ".join(tomados + [c])) > maximo:
            break
        tomados.append(c)
    if not tomados:
        return ""
    if len(tomados) < len(unicos):
        return ", ".join(tomados) + " y otros"
    return tomados[0] if len(tomados) == 1 else ", ".join(tomados[:-1]) + " y " + tomados[-1]


def cierre_texto(dias: int, fin: str) -> str:
    if dias < 0:
        return f"Cerró el {fecha_corta(fin)}"
    if dias == 0:
        return "Cierra hoy"
    if dias == 1:
        return "Cierra mañana"
    if dias <= 7:
        return f"Cierra en {dias} días"
    return f"Cierra el {fecha_corta(fin)}"


def num_convocatoria(conv: str) -> str:
    m = re.findall(r"\d+", conv or "")
    return m[-1] if m else ""


def con_articulo(entidad: str) -> str:
    """'Municipalidad Distrital de X' -> 'la Municipalidad Distrital de X'."""
    w = entidad.split(" ")[0].lower() if entidad else ""
    femeninas = {"municipalidad", "universidad", "dirección", "superintendencia", "unidad",
                 "autoridad", "oficina", "red", "contraloría", "defensoría", "procuraduría",
                 "beneficencia", "sociedad", "empresa", "corte", "fiscalía", "presidencia",
                 "agencia", "escuela", "comisión", "junta", "gerencia", "zona", "intendencia"}
    masculinos = {"gobierno", "ministerio", "hospital", "instituto", "seguro", "servicio",
                  "programa", "poder", "banco", "fondo", "organismo", "centro", "consejo",
                  "proyecto", "tribunal", "jurado", "registro", "archivo", "despacho"}
    if w in femeninas:
        return "la " + entidad
    if w in masculinos:
        return "el " + entidad
    return entidad


def de_articulo(entidad: str) -> str:
    """'de la Municipalidad...', 'del Ministerio...' (nunca 'de el')."""
    con = con_articulo(entidad)
    return "del " + con[3:] if con.startswith("el ") else "de " + con


# ---------------------------------------------------------------- estado

def cargar_json(path: Path, defecto):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defecto


def hash_contenido(o: dict) -> str:
    campos = ("cargo", "entidad", "ubicacion", "convocatoria", "vacantes", "sueldo", "inicio", "fin",
              "experiencia", "formacion", "especializacion", "conocimientos", "competencias", "url_bases")
    raw = json.dumps([o.get(k) for k in campos], ensure_ascii=False)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- modelo

class Sitio:
    def __init__(self, data: dict, state: dict, base_url: str, hoy: date, ahora: datetime):
        self.base_url = base_url.rstrip("/")
        self.base_path = urlparse(self.base_url).path.rstrip("/")
        self.hoy = hoy
        self.ahora = ahora
        self.anio = hoy.year
        self.state = state
        self.state.setdefault("ofertas", {})
        self.state.setdefault("entidades", {})
        self.state.setdefault("entidad_slugs", {})
        self.state.setdefault("listados", {})
        self.generado = data.get("generatedAt") or ahora.isoformat(timespec="seconds")
        self.fuente = data.get("source", {})
        self.errores: list[str] = []
        self.paginas: list[dict] = []  # para sitemaps: {path, lastmod, indexable}

        crudas = {}
        self.descartadas = 0
        for o in data.get("offers", []):
            if not o.get("id") or o["id"] in crudas:  # sin detalle aún: se publica en la próxima
                continue
            # Registros rotos en la fuente (cargo "1", sin letras): no se publican.
            if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", T.limpiar_cargo(o.get("cargo", ""))):
                self.descartadas += 1
                continue
            o = dict(o)
            if o.get("sueldo") is not None and o["sueldo"] < SUELDO_MINIMO_CREIBLE:
                o["sueldo"] = None  # "S/ 1": dato mal cargado, se muestra como no indicado
            crudas[o["id"]] = o
        self.sin_detalle = sum(1 for o in data.get("offers", []) if not o.get("id"))

        hoy_iso = hoy.isoformat()
        self.vigentes = []
        for id_, o in crudas.items():
            if o.get("fin") and o["fin"] < hoy_iso:
                continue
            self.vigentes.append(self.preparar(o))
        ids_vigentes = {o["id"] for o in self.vigentes}

        # Ofertas cerradas: vencidas o retiradas de SERVIR. Se conservan 30 días.
        self.cerradas = []
        for id_, st in list(self.state["ofertas"].items()):
            if id_ in ids_vigentes:
                st.pop("closed_at", None)
                continue
            st.setdefault("closed_at", hoy_iso)
            if (hoy - date.fromisoformat(st["closed_at"])).days > DIAS_CERRADA:
                del self.state["ofertas"][id_]
                continue
            if st.get("snapshot"):
                o = self.preparar(st["snapshot"], cerrada=True)
                o["cerrada_el"] = min(st["closed_at"], st["snapshot"].get("fin") or st["closed_at"])
                self.cerradas.append(o)

        orden = lambda o: (o.get("inicio") or "", int(o["id"]))  # noqa: E731
        self.vigentes.sort(key=orden, reverse=True)

        # Duplicados de cargo dentro de una entidad: se distinguen con el N° corto.
        grupos = defaultdict(list)
        for o in self.vigentes:
            grupos[(o["entidad_txt"], o["cargo_txt"])].append(o)
        for lista in grupos.values():
            convs = Counter(x["conv_corto"] for x in lista)
            for o in lista:
                if len(lista) == 1:
                    o["sufijo"] = ""
                elif o["conv_corto"] and convs[o["conv_corto"]] == 1:
                    o["sufijo"] = f" ({'CAS' if o.get('regimen') == 'CAS' else 'N.°'} {o['conv_corto']})"
                else:  # mismo N.° de convocatoria: se distingue por el N.° de SERVIR
                    o["sufijo"] = f" (N.° {o['id']})"

        self.por_dep = defaultdict(list)
        self.por_entidad = defaultdict(list)
        for o in self.vigentes:
            self.por_dep[o["dep_slug"]].append(o)
            self.por_entidad[o["entidad_slug"]].append(o)

        # Entidades indexables con histéresis: entran con 3+, salen solo al quedar en 0.
        self.entidad_indexable = {}
        for slug_, lista in self.por_entidad.items():
            st = self.state["entidades"].setdefault(slug_, {})
            idx = len(lista) >= UMBRAL_ENTIDAD or (st.get("indexable") and len(lista) > 0)
            st["indexable"] = bool(idx)
            self.entidad_indexable[slug_] = bool(idx)
        for slug_ in list(self.state["entidades"]):
            if slug_ not in self.por_entidad:
                del self.state["entidades"][slug_]

        self.temas = []
        for t in TEMAS:
            lista = [o for o in self.vigentes if t["filtro"](o)]
            self.temas.append({**t, "ofertas": lista, "indexable": len(lista) >= UMBRAL_TEMA,
                               "path": f"/{t['slug']}/"})

    # -- URLs
    def url(self, path: str) -> str:
        return self.base_path + path

    def abs(self, path: str) -> str:
        return self.base_url + path

    def entidad_slug(self, nombre_upper: str, nombre_txt: str) -> str:
        slugs = self.state["entidad_slugs"]
        if nombre_upper in slugs:
            return slugs[nombre_upper]
        base = T.slug(nombre_txt, 90)
        usados = set(slugs.values())
        s, n = base, 2
        while s in usados:
            s, n = f"{base}-{n}", n + 1
        slugs[nombre_upper] = s
        return s

    def preparar(self, o: dict, cerrada: bool = False) -> dict:
        p = dict(o)
        # El título usa una versión corta y limpia del cargo; el texto completo
        # se muestra en la página ("Puesto según la convocatoria").
        cargo = T.nombre_propio(T.limpiar_cargo(o["cargo"]))
        p["cargo_completo"] = cargo
        p["cargo_txt"] = T.cargo_titulo(cargo)
        p["entidad_txt"] = T.nombre_propio(T.normalizar_entidad(o["entidad"]))
        dep = (o.get("departamento") or "").upper().strip()
        p["dep_txt"] = DEPARTAMENTOS.get(dep, T.nombre_propio(dep) or "Perú")
        p["dep_slug"] = T.slug(p["dep_txt"])
        p["localidad_txt"] = T.nombre_propio(o.get("provincia") or "")
        if p["localidad_txt"].upper() == p["dep_txt"].upper():
            p["lugar_txt"] = p["dep_txt"]
        else:
            p["lugar_txt"] = ", ".join(x for x in (p["localidad_txt"], p["dep_txt"]) if x)
        p["entidad_slug"] = self.entidad_slug(o["entidad"].upper(), p["entidad_txt"])
        p["req"] = T.requisitos(o)
        p["especializacion_txt"] = "" if T._no_aplica(o.get("especializacion")) else T.oracion(o["especializacion"])
        p["conocimientos_txt"] = "" if T._no_aplica(o.get("conocimientos")) else T.oracion(o["conocimientos"])
        p["competencias_txt"] = "" if T._no_aplica(o.get("competencias")) else T.oracion(o["competencias"])
        p["experiencia_original"] = "" if T._no_aplica(o.get("experiencia")) else T.oracion(o["experiencia"]).strip(' "-')
        p["formacion_original"] = "" if T._no_aplica(o.get("formacion")) else T.oracion(o["formacion"]).strip(' "-')
        p["sueldo_txt"] = soles(o.get("sueldo"))
        p["fin_txt"] = fecha_larga(o.get("fin"))
        p["inicio_txt"] = fecha_larga(o.get("inicio"))
        dias = (date.fromisoformat(o["fin"]) - self.hoy).days if o.get("fin") else None
        p["dias"] = dias
        p["cierre_txt"] = cierre_texto(dias, o["fin"]) if dias is not None else ""
        p["urgente"] = dias is not None and 0 <= dias <= 3
        reg = REGIMENES.get(o.get("regimen") or "")
        p["regimen_txt"] = reg[0] if reg else (o.get("convocatoria") or "")
        p["regimen_corto"] = o.get("regimen") or ""
        p["conv_corto"] = num_convocatoria(o.get("convocatoria"))
        conv = (o.get("convocatoria") or "").upper()
        detalles = [x for x in (o.get("regimen") if reg else "",
                                "plazo indeterminado" if "INDETERMINADO" in conv else
                                "plazo determinado" if "DETERMINADO" in conv else "") if x]
        p["conv_txt"] = (f"N.° {p['conv_corto']}" + (f" ({', '.join(detalles)})" if detalles else "")
                         if reg and p["conv_corto"] else (o.get("convocatoria") or ""))
        p["vacantes"] = o.get("vacantes") or 1

        st = self.state["ofertas"].get(o["id"])
        if not cerrada:
            h = hash_contenido(o)
            hoy = self.hoy.isoformat()
            if not st:
                st = {"slug": T.slug_oferta(p["cargo_txt"], p["entidad_txt"], o["id"]),
                      "first_seen": hoy, "lastmod": hoy, "hash": h}
                self.state["ofertas"][o["id"]] = st
            elif st.get("hash") != h:
                st["hash"], st["lastmod"] = h, hoy
            st["last_seen"] = hoy
            st["snapshot"] = {k: v for k, v in o.items() if not k.startswith("_")}
        p["slug"] = st["slug"] if st else T.slug_oferta(p["cargo_txt"], p["entidad_txt"], o["id"])
        p["lastmod"] = (st or {}).get("lastmod", self.hoy.isoformat())
        p["path"] = f"/oferta/{p['slug']}/"
        p["cerrada"] = cerrada
        p["fuente_url"] = FUENTE_URL
        return p

    # -- textos generados con datos
    def resumen_listado(self, ofertas: list[dict], lugar: str | None) -> dict:
        sueldos = [o["sueldo"] for o in ofertas if o.get("sueldo")]
        sin_exp = sum(1 for o in ofertas if o["req"]["sin_experiencia"])
        secu = sum(1 for o in ofertas if o["req"]["solo_secundaria"])
        top = Counter(o["entidad_slug"] for o in ofertas).most_common(3)
        nombres = {o["entidad_slug"]: o["entidad_txt"] for o in ofertas}
        top_ent = [{"nombre": nombres[s], "slug": s, "n": n,
                    "indexable": self.entidad_indexable.get(s, False)} for s, n in top]
        return {
            "n": len(ofertas),
            "min": soles(min(sueldos)) if sueldos else "",
            "max": soles(max(sueldos)) if sueldos else "",
            "sin_exp": sin_exp,
            "secundaria": secu,
            "top": top_ent,
            "lugar": lugar,
        }

    def similares(self, o: dict, n: int = 6) -> list[dict]:
        def tokens(x):
            return tuple(T.slug(x["cargo_txt"]).split("-")[:2])
        vistos, out = {o["id"]}, []
        candidatos = (
            self.por_entidad.get(o["entidad_slug"], []),
            [x for x in self.por_dep.get(o["dep_slug"], []) if tokens(x) == tokens(o)],
            [x for x in self.vigentes if tokens(x) == tokens(o)],
            self.por_dep.get(o["dep_slug"], []),
        )
        for grupo in candidatos:
            for x in grupo:
                if x["id"] not in vistos:
                    vistos.add(x["id"])
                    out.append(x)
                    if len(out) >= n:
                        return out
        return out

    # -- JSON-LD
    def jobposting(self, o: dict) -> dict | None:
        def item(etiqueta, texto):
            return f"<li>{etiqueta}: {texto.rstrip(' .;,')}.</li>"

        desc = ["<p>", con_articulo(o["entidad_txt"])[:1].upper() + con_articulo(o["entidad_txt"])[1:],
                f" convoca {plural(o['vacantes'], 'plaza', 'plazas')} de <strong>{o['cargo_txt']}</strong>"]
        if o["regimen_txt"] and o.get("regimen"):
            desc.append(f" bajo el régimen {o['regimen_txt']}")
        desc.append(".</p><ul>")
        desc.append(item("Lugar de trabajo", f"{o['lugar_txt']}, Perú"))
        if o["sueldo_txt"]:
            desc.append(item("Remuneración mensual", o["sueldo_txt"]))
        desc.append(item("Formación académica", o["formacion_original"] or "no indicada en la convocatoria"))
        desc.append(item("Experiencia", o["experiencia_original"] or (
            "no se exige" if o["req"]["sin_experiencia"] else "no indicada en la convocatoria")))
        if o["especializacion_txt"]:
            desc.append(item("Especialización", o["especializacion_txt"]))
        if o["conocimientos_txt"]:
            desc.append(item("Conocimientos", o["conocimientos_txt"]))
        if o["competencias_txt"]:
            desc.append(item("Competencias", o["competencias_txt"]))
        desc.append("</ul><p>Las funciones, el cronograma y el formulario de postulación están en las bases "
                    f"publicadas por la entidad. Convocatoria registrada en Talento Perú (SERVIR) con el N.° {o['id']}.</p>")
        jp = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": o["cargo_txt"],
            "description": "".join(desc),
            "datePosted": o.get("inicio"),
            "hiringOrganization": {"@type": "Organization", "name": o["entidad_txt"]},
            "jobLocation": {"@type": "Place", "address": {
                "@type": "PostalAddress", "addressRegion": o["dep_txt"], "addressCountry": "PE"}},
            "identifier": {"@type": "PropertyValue", "name": "Talento Perú (SERVIR)", "value": o["id"]},
            "directApply": False,
            "totalJobOpenings": o["vacantes"],
            "url": self.abs(o["path"]),
        }
        if o["localidad_txt"] and o["localidad_txt"] != o["dep_txt"]:
            jp["jobLocation"]["address"]["addressLocality"] = o["localidad_txt"]
        if o.get("fin") and (not o.get("inicio") or o["fin"] >= o["inicio"]):
            jp["validThrough"] = f"{o['fin']}T23:59:59-05:00"
        reg = REGIMENES.get(o.get("regimen") or "")
        if reg:
            jp["employmentType"] = reg[2]
        if o.get("sueldo") and o["sueldo"] > 0:
            jp["baseSalary"] = {"@type": "MonetaryAmount", "currency": "PEN", "value": {
                "@type": "QuantitativeValue",
                "value": int(o["sueldo"]) if float(o["sueldo"]).is_integer() else o["sueldo"],
                "unitText": "MONTH"}}
        meses = o["req"]["meses_experiencia"]
        if meses is not None:
            jp["experienceRequirements"] = {"@type": "OccupationalExperienceRequirements",
                                            "monthsOfExperience": meses}
        credencial = {1: "high school", 2: "associate degree", 4: "bachelor degree", 5: "bachelor degree",
                      6: "postgraduate degree", 7: "postgraduate degree"}.get(o["req"]["nivel"])
        if credencial:
            jp["educationRequirements"] = {"@type": "EducationalOccupationalCredential",
                                           "credentialCategory": credencial}
        # Validaciones (SEO_SPEC 3.6): mejor sin marcado que con marcado falso.
        problema = None
        if not jp["title"] or jp["title"] == jp["description"]:
            problema = "title vacío"
        elif not jp.get("datePosted"):
            problema = "sin datePosted"
        elif "validThrough" in jp and jp["validThrough"][:10] < self.hoy.isoformat():
            problema = "validThrough pasado"
        elif not jp["hiringOrganization"]["name"]:
            problema = "sin entidad"
        if problema:
            self.errores.append(f"JobPosting omitido en {o['id']}: {problema}")
            return None
        return jp

    def breadcrumbs(self, items: list[tuple[str, str | None]]) -> dict:
        return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i, "name": n, **({"item": self.abs(p)} if p else {})}
            for i, (n, p) in enumerate(items, 1)]}


# ---------------------------------------------------------------- render

def minificar_css(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


def ld_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def construir(sitio: Sitio, out: Path) -> None:
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    css = minificar_css((HERE / "static" / "estilos.css").read_text(encoding="utf-8-sig"))
    deps_count = sorted(((DEPARTAMENTOS.get(k.upper(), None) or v[0]["dep_txt"], k, len(v))
                         for k, v in sitio.por_dep.items()), key=lambda x: x[0])
    departamentos = [{"nombre": n, "slug": s, "n": c, "path": f"/departamento/{s}/"} for n, s, c in deps_count]
    actualizado = datetime.fromisoformat(sitio.generado)
    env.globals.update(
        url=sitio.url, abs=sitio.abs, anio=sitio.anio, ld_json=ld_json, miles=miles, plural=plural,
        fecha_larga=fecha_larga, soles=soles, departamentos=departamentos, temas=sitio.temas,
        css=css, repo=REPO, fuente_url=FUENTE_URL, hoy=sitio.hoy.isoformat(),
        actualizado_txt=f"{fecha_larga(actualizado.date().isoformat())}, {actualizado:%H:%M}",
        actualizado_corto=fecha_corta(actualizado.date().isoformat()),
        total_vigentes=len(sitio.vigentes),
        total_entidades=len(sitio.por_entidad),
        entidad_indexable=sitio.entidad_indexable,
        con_articulo=con_articulo,
        de_articulo=de_articulo,
        reportar=lambda o: (f"{REPO}/issues/new?title=" + quote(f"Reporte: oferta {o['id']}") + "&body="
                            + quote(f"Oferta: {sitio.abs(o['path'])}\nN.° SERVIR: {o['id']}\n\nQué está mal:\n")),
    )

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    def escribir(path: str, plantilla: str, indexable: bool, lastmod: str | None = None, **ctx):
        html = env.get_template(plantilla).render(path=path, canonical=sitio.abs(path), indexable=indexable, **ctx)
        rel = path.strip("/")
        destino = (out / rel / "index.html") if path.endswith("/") else (out / rel)
        if out.resolve() not in destino.resolve().parents:
            raise RuntimeError(f"ruta fuera del sitio: {path}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8")
        sitio.paginas.append({"path": path, "indexable": indexable, "lastmod": lastmod, "plantilla": plantilla})

    def lastmod_listado(clave: str, ofertas: list[dict]) -> str:
        h = hashlib.sha1(",".join(o["id"] + o["lastmod"] for o in ofertas).encode()).hexdigest()[:16]
        st = sitio.state["listados"].setdefault(clave, {})
        if st.get("hash") != h:
            st["hash"], st["lastmod"] = h, sitio.hoy.isoformat()
        return st["lastmod"]

    def listado(path: str, ofertas: list[dict], indexable: bool, titulo: str, h1: str, descripcion: str,
                migas: list, intro: str = "", extra: dict | None = None):
        paginas = max(1, math.ceil(len(ofertas) / POR_PAGINA))
        lm = lastmod_listado(path, ofertas)
        for n in range(1, paginas + 1):
            p = path if n == 1 else f"{path}pagina/{n}/"
            trozo = ofertas[(n - 1) * POR_PAGINA:n * POR_PAGINA]
            desc_n = descripcion if n == 1 else armar([descripcion.split(". ")[0] + ".", f"Página {n}."])
            escribir(p, "listado.html", indexable, lm if n == 1 else None,
                     titulo=titulo + (f" (página {n})" if n > 1 else ""), h1=h1, descripcion=desc_n,
                     ofertas=trozo, pagina=n, paginas=paginas, base_listado=path, migas=migas,
                     intro=intro if n == 1 else "", extra=extra or {}, total=len(ofertas),
                     ld=[sitio.breadcrumbs(migas)])

    def con_marca(titulo: str, limite: int = 65) -> str:
        return f"{titulo} | Chamba al Toque" if len(titulo) + 18 <= limite else titulo

    hoy_txt = fecha_corta(sitio.hoy.isoformat())

    # Portada
    portada_ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "name": "Chamba al Toque",
         "url": sitio.abs("/"), "inLanguage": "es-PE"},
        {"@context": "https://schema.org", "@type": "Organization", "name": "Chamba al Toque",
         "url": sitio.abs("/"), "logo": sitio.abs("/img/logo-512.png")},
    ]
    top_entidades = sorted(((len(v), s) for s, v in sitio.por_entidad.items() if sitio.entidad_indexable[s]),
                           reverse=True)[:12]
    escribir("/", "portada.html", True, sitio.vigentes[0]["lastmod"] if sitio.vigentes else None,
             titulo=f"Convocatorias CAS y trabajos en el Estado {sitio.anio} | Chamba al Toque",
             descripcion=armar([f"{plural(len(sitio.vigentes), 'convocatoria vigente', 'convocatorias vigentes')} "
                                f"en entidades públicas del Perú, con sueldo, requisitos y fecha límite.",
                                f"Fuente: Talento Perú (SERVIR), al {hoy_txt}."]),
             ultimas=sitio.vigentes[:PORTADA_ULTIMAS],
             top_entidades=[{"nombre": sitio.por_entidad[s][0]["entidad_txt"], "slug": s, "n": n}
                            for n, s in top_entidades],
             por_vencer=sum(1 for o in sitio.vigentes if o["dias"] is not None and o["dias"] <= 3),
             ld=portada_ld)

    # Ofertas vigentes
    for o in sitio.vigentes:
        idx_ent = sitio.entidad_indexable[o["entidad_slug"]]
        migas = [("Inicio", "/"), (o["dep_txt"], f"/departamento/{o['dep_slug']}/")]
        if idx_ent:
            migas.append((o["entidad_txt"], f"/entidad/{o['entidad_slug']}/"))
        migas.append((o["cargo_txt"], None))
        h1 = f"{o['cargo_txt']} en {o['entidad_txt']}{o['sufijo']}"
        titulo = h1
        if len(titulo) + 5 <= 70:
            titulo += f" {sitio.anio}"
        titulo = con_marca(titulo)
        # Prioridad: qué y dónde, sueldo, fecha límite y, si cabe, requisitos.
        regimen = REGIMENES.get(o.get("regimen") or "", ("", "Convocatoria", None))[1]
        a_largo = f"{regimen} para {o['cargo_txt']} en {con_articulo(o['entidad_txt'])} ({o['lugar_txt']})."
        a_corto = f"{regimen} para {o['cargo_txt']} en {o['entidad_txt']} ({o['dep_txt']})."
        b = plural(o["vacantes"], "vacante", "vacantes") + (f", {o['sueldo_txt']} al mes." if o["sueldo_txt"] else ".")
        c = f"Postula hasta el {fecha_corta(o['fin'])}." if o.get("fin") else ""
        d = f"Requisitos: {o['req']['corto'].replace(' · ', ', ').lower()}." if o["req"]["corto"] else ""
        a_min = f"{regimen} para {o['cargo_txt']} en {o['dep_txt']}."
        a = next((x for x in (a_largo, a_corto, a_min) if len(" ".join(y for y in (x, b, c) if y)) <= 155), a_min)
        descripcion = armar([a, b, c, d])
        jp = sitio.jobposting(o)
        misma_entidad = [x for x in sitio.por_entidad[o["entidad_slug"]] if x["id"] != o["id"]][:5]
        escribir(o["path"], "oferta.html", True, o["lastmod"], titulo=titulo, h1=h1,
                 descripcion=descripcion, o=o, migas=migas,
                 misma_entidad=misma_entidad, n_entidad=len(sitio.por_entidad[o["entidad_slug"]]),
                 similares=[x for x in sitio.similares(o, 12) if x not in misma_entidad][:6],
                 temas_oferta=[t for t in sitio.temas if t["filtro"](o)],
                 ld=[x for x in (jp, sitio.breadcrumbs(migas)) if x])

    # Ofertas cerradas (noindex, sin JobPosting)
    for o in sitio.cerradas:
        migas = [("Inicio", "/"), (o["dep_txt"], f"/departamento/{o['dep_slug']}/"), (o["cargo_txt"], None)]
        escribir(o["path"], "oferta.html", False, None,
                 titulo=f"{o['cargo_txt']} en {o['entidad_txt']} (cerrada)",
                 h1=f"{o['cargo_txt']} en {o['entidad_txt']}",
                 descripcion=f"Esta convocatoria cerró el {fecha_larga(o['cerrada_el'])}.",
                 o=o, migas=migas, misma_entidad=[], n_entidad=len(sitio.por_entidad.get(o["entidad_slug"], [])),
                 similares=sitio.similares(o, 6), temas_oferta=[], ld=[sitio.breadcrumbs(migas)])

    # Departamentos
    for d in departamentos:
        ofertas = sitio.por_dep[d["slug"]]
        r = sitio.resumen_listado(ofertas, d["nombre"])
        titulo = con_marca(f"Trabajos en {d['nombre']} {sitio.anio}: convocatorias del Estado")
        if "|" not in titulo:
            titulo = f"Trabajos en {d['nombre']} {sitio.anio}: convocatorias CAS y del Estado"
        desc = armar([
            f"{plural(r['n'], 'convocatoria vigente', 'convocatorias vigentes')} en {d['nombre']}"
            + (f", con sueldos desde {r['min']} hasta {r['max']} al mes." if r["min"] and r["min"] != r["max"] else "."),
            f"{plural(r['sin_exp'], 'no pide', 'no piden')} experiencia." if r["sin_exp"] else "",
            f"Actualizado el {hoy_txt}.",
            "Municipalidades, hospitales, UGEL y más.",
        ])
        cierran = sorted((o for o in ofertas if o["dias"] is not None and o["dias"] <= 7),
                         key=lambda o: (o["dias"], o["cargo_txt"]))[:8]
        listado(d["path"], ofertas, len(ofertas) > 0, titulo, f"Trabajos en el Estado en {d['nombre']} {sitio.anio}",
                desc, [("Inicio", "/"), (d["nombre"], None)],
                extra={"tipo": "departamento", "resumen": r, "cierran": cierran, "dep": d,
                       "poca_exp": sum(1 for o in ofertas if o["req"]["hasta_un_anio"]) >= UMBRAL_DEP_TEMA})
        # Departamento + poca experiencia, solo si hay suficientes
        poca = [o for o in ofertas if o["req"]["hasta_un_anio"]]
        if len(poca) >= UMBRAL_DEP_TEMA:
            listado(f"{d['path']}hasta-un-ano-de-experiencia/", poca, True,
                    f"Trabajo en {d['nombre']} con poca experiencia {sitio.anio}: Estado",
                    f"Trabajos con hasta 1 año de experiencia en {d['nombre']} {sitio.anio}",
                    armar([f"{miles(len(poca))} convocatorias del Estado en {d['nombre']} que piden un año de "
                           "experiencia o menos.", "Sueldo, requisitos y fecha límite de cada una.",
                           f"Actualizado el {hoy_txt}."]),
                    [("Inicio", "/"), (d["nombre"], d["path"]), ("Hasta 1 año de experiencia", None)],
                    extra={"tipo": "tema", "resumen": sitio.resumen_listado(poca, d["nombre"])})

    # Entidades
    for s, ofertas in sitio.por_entidad.items():
        nombre = ofertas[0]["entidad_txt"]
        dep = Counter((o["dep_txt"], o["dep_slug"]) for o in ofertas).most_common(1)[0][0]
        r = sitio.resumen_listado(ofertas, None)
        titulo = f"Convocatorias {nombre} {sitio.anio}: {plural(len(ofertas), 'plaza vigente', 'plazas vigentes')}"
        if len(titulo) > 70:
            titulo = f"Convocatorias {nombre} {sitio.anio}"
        cargos = lista_cargos([o["cargo_txt"].lower() for o in ofertas])
        primera = min((o["fin"] for o in ofertas if o.get("fin")), default=None)
        desc = armar([
            f"{plural(len(ofertas), 'convocatoria vigente', 'convocatorias vigentes')} en {nombre} ({dep[0]}).",
            f"Sueldos desde {r['min']}." if r["min"] else "",
            f"Cargos: {cargos}." if cargos else "",
            f"Cierran desde el {fecha_corta(primera)}." if primera else "",
        ])
        listado(f"/entidad/{s}/", ofertas, sitio.entidad_indexable[s], titulo, f"Convocatorias de {nombre} {sitio.anio}",
                desc, [("Inicio", "/"), (dep[0], f"/departamento/{dep[1]}/"), (nombre, None)],
                extra={"tipo": "entidad", "resumen": r, "entidad": nombre, "primera": fecha_larga(primera)})

    # Temas nacionales
    for t in sitio.temas:
        r = sitio.resumen_listado(t["ofertas"], None)
        listado(t["path"], t["ofertas"], t["indexable"], t["title"].format(anio=sitio.anio),
                t["h1"].format(anio=sitio.anio),
                armar([f"{plural(r['n'], 'convocatoria vigente', 'convocatorias vigentes')}.", t["intro"],
                       f"Sueldos desde {r['min']} hasta {r['max']} al mes." if r["min"] else ""]),
                [("Inicio", "/"), (t["nombre"], None)], intro=t["intro"],
                extra={"tipo": "tema", "resumen": r})

    # Nuevas y por vencer (cambian a diario: noindex)
    nuevas = [o for o in sitio.vigentes if sitio.state["ofertas"][o["id"]]["first_seen"] == sitio.hoy.isoformat()]
    listado("/nuevas/", nuevas, False, "Convocatorias nuevas de hoy",
            "Convocatorias nuevas de hoy", "Convocatorias del Estado que aparecieron hoy en Talento Perú.",
            [("Inicio", "/"), ("Nuevas", None)], extra={"tipo": "tema"})
    pv = sorted((o for o in sitio.vigentes if o["dias"] is not None and o["dias"] <= 3),
                key=lambda o: (o["dias"], o["cargo_txt"]))
    listado("/por-vencer/", pv, False, "Convocatorias que cierran pronto", "Cierran en los próximos 3 días",
            "Convocatorias del Estado que cierran en los próximos 3 días.",
            [("Inicio", "/"), ("Por vencer", None)], extra={"tipo": "tema"})

    # Búsqueda (mejora progresiva con JS; sin JS muestra departamentos y temas)
    indice = [{"u": o["path"], "c": o["cargo_txt"], "e": o["entidad_txt"], "d": o["dep_slug"],
               "l": o["lugar_txt"], "s": o.get("sueldo") or 0, "f": o.get("fin") or "",
               "x": 1 if o["req"]["sin_experiencia"] else 0, "q": 1 if o["req"]["solo_secundaria"] else 0,
               "h": 1 if o["req"]["hasta_un_anio"] else 0,
               "r": o["req"]["frase"]}
              for o in sitio.vigentes]
    (out / "buscar.json").write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    escribir("/buscar/", "buscar.html", False, None, titulo="Buscar convocatorias", h1="Buscar convocatorias",
             descripcion="Busca convocatorias del Estado por cargo o entidad.", ld=[])

    # Páginas informativas
    for p in INFO:
        escribir(f"/{p['slug']}/", f"info/{p['slug']}.html", p["indexable"], p["lastmod"],
                 titulo=p["title"], h1=p["h1"], descripcion=p["desc"],
                 migas=[("Inicio", "/"), (p["h1"], None)], ld=[])

    # 404 (GitHub Pages la sirve desde la raíz del proyecto)
    html = env.get_template("404.html").render(path="/404.html", canonical=sitio.abs("/404.html"), indexable=False,
                                               titulo="Página no encontrada", h1="Esta página no existe o ya cerró",
                                               descripcion="", ld=[])
    (out / "404.html").write_text(html, encoding="utf-8")

    # Estáticos
    static = HERE / "static"
    for f in static.rglob("*"):
        if f.is_file() and f.name != "estilos.css":
            dest = out / f.relative_to(static)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    (out / ".nojekyll").write_text("", encoding="utf-8")

    escribir_sitemaps(sitio, out)


def escribir_sitemaps(sitio: Sitio, out: Path) -> None:
    def urlset(paginas):
        filas = []
        for p in paginas:
            lm = f"<lastmod>{p['lastmod']}</lastmod>" if p.get("lastmod") else ""
            filas.append(f"<url><loc>{sitio.abs(p['path'])}</loc>{lm}</url>")
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + "".join(filas) + "</urlset>\n")

    indexables = [p for p in sitio.paginas if p["indexable"] and "/pagina/" not in p["path"]]
    ofertas = [p for p in indexables if p["plantilla"] == "oferta.html"]
    info = [p for p in indexables if p["plantilla"].startswith("info/")]
    listados = [p for p in indexables if p not in ofertas and p not in info]
    archivos = []  # (nombre, lastmod más reciente de sus URLs)

    def guardar(nombre, grupo):
        (out / nombre).write_text(urlset(grupo), encoding="utf-8")
        archivos.append((nombre, max((p["lastmod"] for p in grupo if p.get("lastmod")), default=None)))

    for i in range(0, max(1, len(ofertas)), 2000):
        guardar(f"sitemap-ofertas-{i // 2000 + 1}.xml", ofertas[i:i + 2000])
    guardar("sitemap-listados.xml", listados)
    guardar("sitemap-info.xml", info)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<sitemap><loc>{sitio.abs('/' + a)}</loc>" + (f"<lastmod>{lm}</lastmod>" if lm else "")
                  + "</sitemap>" for a, lm in archivos)
        + "</sitemapindex>\n", encoding="utf-8")
    # robots.txt solo sirve en la raíz del host (dominio propio, no subcarpeta de github.io)
    if not sitio.base_path:
        (out / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\n\nSitemap: {sitio.abs('/sitemap.xml')}\n", encoding="utf-8")


def verificar(sitio: Sitio, out: Path) -> list[str]:
    """Comprobaciones sobre el sitio generado (SEO_SPEC 3.6 y 10)."""
    problemas = []
    ofertas_vigentes = {sitio.abs(o["path"]) for o in sitio.vigentes}
    prohibidas = ["descubre", "sumérgete", "en un solo lugar", "experiencia única", "—"]
    titulos = Counter()
    for f in out.rglob("*.html"):
        html = f.read_text(encoding="utf-8")
        m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        canon = m.group(1) if m else ""
        if '"@type":"JobPosting"' in html and canon not in ofertas_vigentes:
            problemas.append(f"JobPosting fuera de una oferta vigente: {f}")
        t = re.search(r"<title>(.*?)</title>", html, re.S)
        if t and 'content="index' in html:
            titulos[t.group(1)] += 1
        texto = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)).lower()
        for p in prohibidas:
            if p in texto:
                problemas.append(f"Frase prohibida '{p}' en {f.relative_to(out)}")
    dup = [t for t, n in titulos.items() if n > 1]
    if dup:
        print(f"aviso: {len(dup)} títulos repetidos entre páginas indexables (ej.: {dup[0][:80]})")
    return problemas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", default=None, help="state.json (por defecto, junto a --data)")
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--hoy", help="fecha de construcción AAAA-MM-DD (pruebas)")
    args = ap.parse_args(argv)

    data = cargar_json(Path(args.data), {})
    state_path = Path(args.state) if args.state else Path(args.data).with_name("state.json")
    state = cargar_json(state_path, {})
    ahora = datetime.now(LIMA)
    hoy = date.fromisoformat(args.hoy) if args.hoy else ahora.date()

    T.cargar_correcciones(HERE.parent / "data" / "correcciones.csv")
    sitio = Sitio(data, state, args.base_url, hoy, ahora)

    previas = state.get("vigentes_ultima_publicacion") or 0
    if previas and len(sitio.vigentes) < previas * MIN_PROPORCION:
        print(f"ABORTADO: solo {len(sitio.vigentes)} ofertas frente a {previas} de la publicación anterior. "
              "Se conserva el sitio publicado.", file=sys.stderr)
        return 2
    if not sitio.vigentes:
        print("ABORTADO: no hay ofertas vigentes con detalle.", file=sys.stderr)
        return 2

    construir(sitio, Path(args.out))
    problemas = verificar(sitio, Path(args.out))
    for e in sitio.errores[:20]:
        print("aviso:", e)
    if problemas:
        for p in problemas[:30]:
            print("ERROR:", p, file=sys.stderr)
        return 1

    state["vigentes_ultima_publicacion"] = len(sitio.vigentes)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    faltan = [w for w, _ in T.SIN_DICCIONARIO.most_common(50)]
    (Path(args.data).parent / "palabras-sin-diccionario.txt").write_text("\n".join(faltan), encoding="utf-8")
    n_idx = sum(1 for p in sitio.paginas if p["indexable"])
    print(f"{len(sitio.vigentes)} ofertas vigentes · {sitio.descartadas} descartadas por datos rotos · "
          f"{len(sitio.cerradas)} cerradas · "
          f"{len(sitio.paginas)} páginas ({n_idx} indexables) · {sitio.sin_detalle} sin detalle aún")
    return 0


if __name__ == "__main__":
    sys.exit(main())
