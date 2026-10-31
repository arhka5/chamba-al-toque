"""Cursos gratuitos con certificado para lo que pide cada oferta.

Lee site/cursos.json (lo genera `python -m scraper.cursos`) y, por cada oferta, busca
en sus campos de especialización y conocimientos los temas de TEMAS. Cada tema dice
qué cursos del catálogo lo cubren (regex sobre el título y, si hace falta, la fuente).
Solo se sugieren temas con un curso gratuito y certificado comprobado: SIAF y SIGA no
están porque el MEF no ofrece uno abierto al público (revisado el 30-10-2026).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

ENAP_CATALOGO = "https://www.gob.pe/cursosmooc"
MAX_TEMAS = 3
MAX_CURSOS = 2

# oferta: regex sobre ESPECIALIZACIÓN + CONOCIMIENTOS (sin tildes, en mayúsculas)
# cursos: regex sobre el título del curso (sin tildes, en minúsculas), en orden de preferencia
TEMAS = [
    {"slug": "excel", "nombre": "Excel",
     "oferta": r"\bEXCEL\b|HOJAS? DE CALCULO",
     "cursos": [r"^excel basico$", r"^excel intermedio$", r"^word y excel para el trabajo"]},
    {"slug": "word", "nombre": "Word",
     "oferta": r"\bWORD\b|PROCESADOR(ES)? DE TEXTO",
     "cursos": [r"^word basico$", r"^word intermedio$"]},
    {"slug": "ofimatica", "nombre": "Ofimática",
     "oferta": r"OFIMATICA|OFFICE|COMPUTACION|INFORMATICA (BASICA|A NIVEL|NIVEL)|MANEJO DE (PC|COMPUTADORA)",
     "cursos": [r"^word y excel para el trabajo", r"^computacion facil", r"^excel basico$"]},
    {"slug": "gestion-publica", "nombre": "Gestión pública",
     "oferta": r"GESTION PUBLICA|ADMINISTRACION PUBLICA|MODERNIZACION|ESTADO PERUANO|FUNCION PUBLICA",
     "cursos": [r"enap:.*gestion publica", r"enap:."], "enap": True},
    {"slug": "recursos-humanos", "nombre": "Recursos humanos",
     "oferta": r"RECURSOS HUMANOS|GESTION DE PERSONAS|SERVICIO CIVIL|BIENESTAR SOCIAL|PLANILLAS?",
     "cursos": [r"enap:.*recursos humanos", r"^gestion del desempeno", r"^direccion de personal"], "enap": True},
    {"slug": "transformacion-digital", "nombre": "Transformación digital e IA",
     "oferta": r"TRANSFORMACION DIGITAL|GOBIERNO DIGITAL|INTELIGENCIA ARTIFICIAL",
     "cursos": [r"enap:.*transformacion digital", r"enap:.*inteligencia artificial",
                r"^descripcion general de la ia"], "enap": True},
    {"slug": "atencion-al-ciudadano", "nombre": "Atención al ciudadano",
     "oferta": r"ATENCION AL (CIUDADANO|CLIENTE|USUARIO|PUBLICO)|SERVICIO AL (CLIENTE|CIUDADANO)",
     "cursos": [r"^orientacion al cliente", r"^la experiencia del cliente"]},
    {"slug": "seguridad-y-salud", "nombre": "Seguridad y salud en el trabajo",
     "oferta": r"SEGURIDAD Y SALUD EN EL TRABAJO|\bSST\b|PREVENCION DE RIESGOS",
     "cursos": [r"^prevencion de riesgos laborales", r"^salud y seguridad para ambientes"]},
    {"slug": "ingles", "nombre": "Inglés",
     "oferta": r"\bINGLES\b",
     "cursos": [r"^ingles basico para el trabajo", r"^basic a1"]},
    {"slug": "redes", "nombre": "Redes y soporte",
     "oferta": r"\bREDES (DE (DATOS|COMPUTADORAS|COMUNICACION)|INFORMATICAS)|CISCO|SOPORTE TECNICO|HARDWARE",
     "cursos": [r"^conceptos basicos de redes", r"^conceptos basicos de hardware"]},
    {"slug": "ciberseguridad", "nombre": "Ciberseguridad",
     "oferta": r"CIBERSEGURIDAD|SEGURIDAD DE LA INFORMACION|SEGURIDAD INFORMATICA",
     "cursos": [r"^introduccion a ciberseguridad", r"^administracion de amenazas"]},
    {"slug": "analisis-de-datos", "nombre": "Análisis de datos",
     "oferta": r"POWER ?BI|ANALISIS DE DATOS|CIENCIA DE DATOS|\bPYTHON\b",
     "cursos": [r"^introduccion al power bi", r"^analisis de datos con power bi", r"^fundamentos de python 1"]},
    {"slug": "logistica", "nombre": "Logística",
     "oferta": r"LOGISTICA|ALMACEN|ABASTECIMIENTO|CADENA DE SUMINISTRO",
     "cursos": [r"^logistica 360"]},
    {"slug": "hostigamiento-sexual", "nombre": "Prevención del hostigamiento sexual",
     "oferta": r"HOSTIGAMIENTO SEXUAL",
     "cursos": [r"^prevencion y reporte del hostigamiento"]},
]


def plano(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn")


def horas_minimas(texto: str) -> int | None:
    """'NO MENOR A (20) HORAS', 'MÍNIMO 12 HORAS LECTIVAS' → la mayor cifra pedida."""
    cifras = [int(n) for n in re.findall(r"\(?(\d{1,3})\)?\s*HORAS", plano(texto).upper())]
    return max(cifras) if cifras else None


class Catalogo:
    def __init__(self, cursos: list[dict], hoy: date):
        vigentes, vistos = [], {}
        for c in cursos:
            if c.get("hasta") and c["hasta"] < hoy.isoformat():
                continue  # MOOC de la ENAP ya cerrado
            clave = (c["fuente"], plano(c["titulo"]).lower().rstrip(" *"))
            # Capacíta-T repite algunos cursos (versión vieja marcada con "*"): queda el de más horas
            if clave in vistos and (vistos[clave].get("horas") or 0) >= (c.get("horas") or 0):
                continue
            vistos[clave] = c
        for c in vistos.values():
            c = dict(c, titulo=c["titulo"].rstrip(" *"))
            c["_clave"] = (f"enap:{plano(c['titulo']).lower()}" if c["fuente"] == "enap"
                           else plano(c["titulo"]).lower())
            vigentes.append(c)
        self.cursos = vigentes
        self.temas = []
        for t in TEMAS:
            elegidos = []
            for patron in t["cursos"]:
                for c in self.cursos:
                    if c not in elegidos and re.search(patron, c["_clave"]):
                        elegidos.append(c)
                        break
            if elegidos or t.get("enap"):  # los temas de la ENAP siempre tienen su catálogo como respaldo
                self.temas.append(dict(t, lista=elegidos[:MAX_CURSOS], _re=re.compile(t["oferta"])))

    @classmethod
    def cargar(cls, path: Path, hoy: date) -> "Catalogo":
        try:
            datos = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            datos = {}
        return cls(datos.get("cursos", []), hoy)

    def para_oferta(self, o: dict) -> dict | None:
        texto = plano(f"{o.get('especializacion') or ''} {o.get('conocimientos') or ''}").upper()
        temas = [t for t in self.temas if t["_re"].search(texto)]
        # Si piden Excel o Word, "ofimática" sobra
        if any(t["slug"] in ("excel", "word") for t in temas):
            temas = [t for t in temas if t["slug"] != "ofimatica"]
        if not temas:
            return None
        return {"temas": temas[:MAX_TEMAS], "horas_min": horas_minimas(o.get("especializacion") or "")}
