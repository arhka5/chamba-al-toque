"""Convierte los datos de SERVIR (todo en MAYÚSCULAS, textos largos) en
textos legibles: nombres, slugs y un resumen simple de requisitos.

Todo sale de los campos oficiales; no se inventa nada."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from pathlib import Path

MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "u", "en", "para", "por",
              "con", "a", "al", "sin", "un", "una"}

# Siglas que se dejan en mayúsculas. Solo siglas que no son palabras comunes
# (nada de "MAS", "ANA" o "PRODUCE", que también aparecen como palabras).
SIGLAS = {
    "CAS", "SERVIR", "UGEL", "DRE", "DIRESA", "GERESA", "MINSA", "ESSALUD", "SUNAT", "SUNARP",
    "PNP", "ONP", "INEI", "OCI", "SIS", "RENIEC", "JNE", "ONPE", "SUNAFIL", "OSINERGMIN",
    "OSIPTEL", "SUNASS", "INDECOPI", "MEF", "MTPE", "MINEDU", "MIDIS", "MIMP", "MINAM", "MINEM",
    "MIDAGRI", "MINCETUR", "SENASA", "SENAMHI", "SERNANP", "SUCAMEC", "SUTRAN", "INPE", "INABIF",
    "OEFA", "SBS", "BCRP", "PCM", "MTC", "MVCS", "MINJUSDH", "TI", "TIC", "RRHH", "SST", "SIAF",
    "SIGA", "SEACE", "OSCE", "UNI", "UNMSM", "SAC", "EPS", "SEDAPAL", "EMAPE", "FONCODES",
    "PRONABEC", "DEVIDA", "CENEPRED", "INDECI", "COFOPRI", "ATU", "MML", "SAT", "SATT", "DNI",
    "CTS", "IGV", "ONG", "PNUD", "CEPLAN", "FAP", "CEM", "DEMUNA", "OMAPED", "CIAM", "ULE",
    "AIS", "UTES", "PAD", "EESS", "IPRESS", "SAMU", "PRONIS", "PROVIAS", "SERFOR", "ANA", "AAA",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
}
# Palabras con mayúscula interna o forma propia.
FORMAS = {"essalud": "EsSalud", "pronied": "Pronied", "proinversion": "ProInversión"}

# La fuente suele venir sin tildes. Palabras frecuentes de cargos y
# entidades; los topónimos van con mayúscula. Se amplía con
# data/correcciones.csv.
TILDES = {
    "tecnico": "técnico", "tecnica": "técnica", "tecnicos": "técnicos", "mecanico": "mecánico",
    "psicologo": "psicólogo", "psicologa": "psicóloga", "psicologia": "psicología",
    "medico": "médico", "medica": "médica", "quimico": "químico", "quimica": "química",
    "biologo": "biólogo", "biologa": "bióloga", "economico": "económico", "economia": "economía",
    "juridico": "jurídico", "juridica": "jurídica", "publico": "público", "publica": "pública",
    "publicos": "públicos", "publicas": "públicas", "logistica": "logística",
    "estadistica": "estadística", "informatica": "informática", "ingenieria": "ingeniería",
    "enfermeria": "enfermería", "auditoria": "auditoría", "tesoreria": "tesorería",
    "contraloria": "contraloría", "procuraduria": "procuraduría", "policia": "policía",
    "odontologia": "odontología", "odontologo": "odontólogo", "topografo": "topógrafo",
    "cartografo": "cartógrafo", "geografo": "geógrafo", "agronomo": "agrónomo",
    "electronico": "electrónico", "electrica": "eléctrica", "electrico": "eléctrico",
    "vehiculo": "vehículo", "vehiculos": "vehículos", "maquina": "máquina", "maquinas": "máquinas",
    "albanil": "albañil", "basico": "básico", "basica": "básica", "academico": "académico",
    "academica": "académica", "pedagogico": "pedagógico", "pedagogica": "pedagógica",
    "pedagogia": "pedagogía", "tecnologia": "tecnología", "metodologia": "metodología",
    "energia": "energía", "mineria": "minería", "almacen": "almacén", "region": "región",
    "credito": "crédito", "creditos": "créditos", "tramite": "trámite", "tramites": "trámites",
    "analisis": "análisis", "diagnostico": "diagnóstico", "especifico": "específico",
    "especifica": "específica", "telefonico": "telefónico", "telefonica": "telefónica",
    "camara": "cámara", "unico": "único", "unica": "única", "practicas": "prácticas",
    "pagina": "página", "ambito": "ámbito", "transito": "tránsito", "mas": "más",
    "obstetra": "obstetra", "quirurgico": "quirúrgico", "clinico": "clínico", "clinica": "clínica",
    "radiologia": "radiología", "laboratorio": "laboratorio", "nutricion": "nutrición",
    "computo": "cómputo", "sistematizacion": "sistematización", "chofer": "chofer",
    "guardian": "guardián", "jardineria": "jardinería", "carpinteria": "carpintería",
    "cobranza": "cobranza", "fiscalizacion": "fiscalización", "linea": "línea", "lineas": "líneas",
    "pais": "país", "rio": "río", "vias": "vías", "via": "vía", "dias": "días",
    "matematica": "matemática", "matematicas": "matemáticas", "fisica": "física", "fisico": "físico",
    "musica": "música", "artistico": "artístico", "historico": "histórico", "turistico": "turístico",
    "ecologico": "ecológico", "geologo": "geólogo", "hidraulico": "hidráulico",
    "hidraulica": "hidráulica", "mecanica": "mecánica", "automotriz": "automotriz",
    "estrategico": "estratégico", "estrategica": "estratégica", "politica": "política",
    "politicas": "políticas", "codigo": "código", "deposito": "depósito",
    "gestion": "gestión", "cuestion": "cuestión", "oncologo": "oncólogo", "oncologa": "oncóloga",
    "cardiologo": "cardiólogo", "neurologo": "neurólogo", "ginecologo": "ginecólogo",
    "pediatria": "pediatría", "anestesiologo": "anestesiólogo", "radiologo": "radiólogo",
    "tecnologo": "tecnólogo", "tecnologa": "tecnóloga", "arqueologo": "arqueólogo",
    "sociologo": "sociólogo", "antropologo": "antropólogo", "educacion": "educación",
    "medicos": "médicos", "basicos": "básicos", "tecnicas": "técnicas", "unidad": "unidad",
    "numero": "número", "despues": "después", "telefono": "teléfono", "tactico": "táctico",
    "transito": "tránsito", "rapido": "rápido", "rapida": "rápida", "util": "útil",
    "aerea": "aérea", "aereo": "aéreo", "tecnologico": "tecnológico", "tecnologica": "tecnológica",
    "organico": "orgánico", "patrimonio": "patrimonio", "arqueologico": "arqueológico",
    "geologico": "geológico", "hidrografico": "hidrográfico", "periodico": "periódico",
    # Departamentos y topónimos frecuentes
    "ancash": "Áncash", "apurimac": "Apurímac", "huanuco": "Huánuco", "junin": "Junín",
    "martin": "Martín", "pachacamac": "Pachacámac", "canete": "Cañete", "rimac": "Rímac",
    "peru": "Perú", "jaen": "Jaén", "lurin": "Lurín", "ferrenafe": "Ferreñafe",
    "camana": "Camaná", "huancane": "Huancané", "vilcashuaman": "Vilcashuamán",
    "concepcion": "Concepción", "asuncion": "Asunción", "ascension": "Ascensión",
    "zarate": "Zárate", "nanay": "Nanay", "maranon": "Marañón", "chancay": "Chancay",
    "carhuaz": "Carhuaz", "yungay": "Yungay", "bolivar": "Bolívar", "sucre": "Sucre",
    "paucar": "Páucar", "huamanga": "Huamanga", "andres": "Andrés", "ramon": "Ramón",
    "maria": "María", "jesus": "Jesús", "jose": "José", "tupac": "Túpac", "amaru": "Amaru",
    "angeles": "Ángeles", "lopez": "López", "perez": "Pérez", "gonzalez": "González",
    "garcia": "García", "rodriguez": "Rodríguez", "fernandez": "Fernández", "sanchez": "Sánchez",
    "ramirez": "Ramírez", "martinez": "Martínez", "vasquez": "Vásquez", "gomez": "Gómez",
    "hernandez": "Hernández", "chavez": "Chávez", "jimenez": "Jiménez", "diaz": "Díaz",
    "ruiz": "Ruiz", "alvarez": "Álvarez", "cesar": "César", "victor": "Víctor", "nicolas": "Nicolás",
    "tomas": "Tomás", "simon": "Simón", "agustin": "Agustín", "sebastian": "Sebastián",
    "joaquin": "Joaquín", "ines": "Inés", "belen": "Belén", "jeronimo": "Jerónimo",
    "huancavelica": "Huancavelica", "tumbes": "Tumbes",
}

SIN_DICCIONARIO: Counter = Counter()


def cargar_correcciones(path) -> int:
    """Lee pares 'ORIGINAL,Corrección' (una por línea) y los suma a TILDES."""
    p = Path(path)
    if not p.exists():
        return 0
    n = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "," not in line:
            continue
        a, b = (x.strip() for x in line.split(",", 1))
        if a and b:
            TILDES[a.lower()] = b
            n += 1
    return n


def _es_sigla(w: str) -> bool:
    bare = w.strip("()[],;:\"'-/")
    if not bare or bare.lower() in MINUSCULAS:  # "Y", "O", "E" no son siglas
        return False
    if bare.upper() in SIGLAS or re.search(r"\d", bare):
        return True
    if "." in bare.strip("."):
        # "R.D.", "S.A.C." sí; "DIREC.REGIONAL" no (son palabras abreviadas).
        return all(len(s) <= 3 for s in bare.split(".") if s)
    # Siglas sin vocales: "PJ", "MPL", "DGPR".
    return len(bare) <= 5 and not re.search(r"[AEIOUÁÉÍÓÚaeiouáéíóú]", bare)


def _acentuar(low: str) -> str:
    """Pone tildes a una palabra en minúsculas, si viene sin ellas. Los
    topónimos del diccionario vuelven con su mayúscula."""
    if re.search(r"[áéíóúñü]", low):
        return low
    m = re.match(r"^([^a-z]*)([a-z]+)([^a-z]*)$", low)
    if not m:
        return low
    pre, core, post = m.groups()
    if core in FORMAS:
        return pre + FORMAS[core] + post
    if core in TILDES:
        return pre + TILDES[core] + post
    if len(core) > 4 and core.endswith("cion"):
        return pre + core[:-4] + "ción" + post
    if len(core) > 4 and core.endswith("sion"):
        return pre + core[:-4] + "sión" + post
    if len(core) > 3:
        SIN_DICCIONARIO[core] += 1
    return low


def _capital(w: str) -> str:
    low = _acentuar(w.lower())
    i = next((k for k, ch in enumerate(low) if ch.isalpha()), None)
    return low if i is None else low[:i] + low[i].upper() + low[i + 1:]


def _palabras(texto: str) -> list[str]:
    return re.sub(r"\s+", " ", texto or "").strip().split(" ")


def _sigla(w: str) -> str:
    bare = w.strip("()[],;:\"'-/").lower()
    return w.replace(w.strip("()[],;:\"'-/"), FORMAS[bare]) if bare in FORMAS else w.upper()


def _titulo_palabra(w: str, primera: bool, prev: str) -> str:
    # Palabras unidas por guion o punto ("PUBLICO-GERENCIA", "DIREC.REGIONAL"):
    # cada parte se trata por separado.
    for sep in ("-", "."):
        if sep in w.strip(sep) and not _es_sigla(w):
            partes = w.split(sep)
            return sep.join(_titulo_palabra(p, primera and k == 0, prev) if p else p
                            for k, p in enumerate(partes))
    bare = w.strip("()[],;:\"'")
    if _es_sigla(w) or bare.lower() in FORMAS:
        return _sigla(w)
    # Sigla corta tras un guion al final de un cargo: "... - ODM".
    if (prev in {"-", "–"} and 2 <= len(bare) <= 4 and bare.isalpha() and bare.lower() not in TILDES
            and len(re.findall(r"[AEIOUaeiou]", bare)) <= 1):
        return w.upper()
    if not primera and w.lower() in MINUSCULAS and not prev.endswith(("-", "(")):
        return w.lower()
    return _capital(w)


def nombre_propio(texto: str) -> str:
    """Formato título: 'MUNICIPALIDAD  DISTRITAL DE PACHACAMAC' ->
    'Municipalidad Distrital de Pachacámac'. Se usa para cargos y entidades."""
    out = []
    prev = ""
    for i, w in enumerate(_palabras(texto)):
        if not w:
            continue
        out.append(_titulo_palabra(w, i == 0, prev))
        prev = w
    return " ".join(out)


def oracion(texto: str) -> str:
    """Formato oración para textos largos: 'LIMPIEZA DE AMBIENTES; DESINFECCIÓN'
    -> 'Limpieza de ambientes; desinfección' (respeta siglas y topónimos)."""
    out = []
    inicio = True  # tras un punto o una viñeta empieza otra oración
    for w in _palabras(texto):
        if not w:
            continue
        if w in {"•", "-", "*"}:
            out.append(w)
            inicio = True
            continue
        if _es_sigla(w) or w.strip("()").lower() in FORMAS:
            out.append(_sigla(w))
        elif inicio or w.startswith("•"):
            out.append(_capital(w))
        else:
            out.append(_acentuar(w.lower()))
        inicio = w.endswith(".") and not _es_sigla(w)
    return " ".join(out)


def normalizar_entidad(texto: str) -> str:
    """'UNIDAD DE GESTION EDUCATIVA LOCAL # 01' -> 'UGEL 01' (así se busca)."""
    t = re.sub(r"\s+", " ", texto or "").strip()
    return re.sub(r"^UNIDAD DE GESTI[OÓ]N EDUCATIVA LOCAL\s*(?:N[°º.]*|#|NRO\.?)?\s*(\d+)",
                  r"UGEL \1", t, flags=re.I)


def slug(texto: str, max_len: int = 80) -> str:
    s = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rsplit("-", 1)[0]
    return s or "oferta"


ABREVIATURAS_SLUG = [
    ("municipalidad-distrital-de-", "muni-distrital-"),
    ("municipalidad-provincial-de-", "muni-provincial-"),
    ("municipalidad-metropolitana-de-", "muni-metropolitana-"),
    ("municipalidad-distrital-", "muni-distrital-"),
    ("municipalidad-provincial-", "muni-provincial-"),
    ("municipalidad-de-", "muni-"),
    ("gobierno-regional-de-", "gore-"),
    ("gobierno-regional-", "gore-"),
    ("unidad-de-gestion-educativa-local-", "ugel-"),
    ("direccion-regional-de-", "dir-regional-"),
    ("universidad-nacional-", "un-"),
    ("ministerio-de-", "min-"),
]


COLGANTES = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "en", "a", "al", "para", "con", "n"}


def _recortar_slug(s: str, maximo: int) -> str:
    partes = s.split("-")
    out = []
    for p in partes:
        if len("-".join(out + [p])) > maximo:
            break
        out.append(p)
    while out and out[-1] in COLGANTES:
        out.pop()
    return "-".join(out)


def slug_oferta(cargo: str, entidad: str, id_: str) -> str:
    """'{cargo}-{entidad corta}-{id}': cargo hasta 45 caracteres, total hasta 70 + id."""
    c = _recortar_slug(slug(cargo, 200), 45) or "oferta"
    e = slug(normalizar_entidad(entidad), 200) + "-"
    for largo, corto in ABREVIATURAS_SLUG:
        if e.startswith(largo):
            e = corto + e[len(largo):]
            break
    e = _recortar_slug(e.strip("-"), max(10, 70 - len(c) - 1))
    return "-".join(x for x in (c, e, id_) if x)


def _vacio(t: str | None) -> bool:
    """Campo sin llenar ('-', '.', '1', 'según las bases'): no se sabe qué piden."""
    t = re.sub(r"\s+", " ", (t or "")).strip().upper().strip(".-_ \"'")
    return (not t or t.isdigit() or len(t) < 3
            or bool(re.match(r"^(SEG[UÚ]N|CONFORME|DE ACUERDO)\b.*\b(PERFIL|BASES?|T[EÉ]RMINOS)", t)))


def _no_aplica(t: str | None) -> bool:
    """Dice expresamente que no se pide (o el campo está vacío)."""
    if _vacio(t):
        return True
    t = re.sub(r"[.\s]+$", "", (t or "").strip().upper())
    return t in {"NO APLICA", "NO", "NINGUNA", "NINGUNO", "N/A", "NA", "NO REQUIERE",
                 "SIN EXPERIENCIA", "NO SE REQUIERE", "NO INDISPENSABLE", "NO APLICA."}


def experiencia_resumen(texto: str | None) -> tuple[str, bool, int | None]:
    """('Sin experiencia', True, 0), ('2 años de experiencia', False, 24) o,
    si el campo está vacío, ('', False, None): no se sabe y no se adivina."""
    if _vacio(texto):
        return "", False, None
    if _no_aplica(texto):
        return "Sin experiencia", True, 0
    t = texto.upper()
    anios = [int(x) for x in re.findall(r"(\d+)\s*\(?[A-Z]*\)?\s*AÑOS?", t)]
    meses = [int(x) for x in re.findall(r"(\d+)\s*\(?[A-Z]*\)?\s*MES(?:ES)?", t)]
    # La experiencia general suele ser la mayor; se muestra esa.
    if anios and max(anios) == 0 and not meses:
        return "Sin experiencia", True, 0
    if anios and max(anios) > 0:
        n = max(anios)
        return f"{n} año{'s' if n != 1 else ''} de experiencia", False, n * 12
    if meses:
        n = max(meses)
        return (f"{n} meses de experiencia" if n != 1 else "1 mes de experiencia"), False, n
    return "Con experiencia", False, None


# (patrón, etiqueta, nivel). El nivel sirve para el tema "solo secundaria".
NIVELES = [
    (r"PRIMARIA", "Primaria", 0),
    (r"SECUNDARIA", "Secundaria completa", 1),
    (r"T[EÉ]CNIC|INSTITUTO|CETPRO", "Técnico", 2),
    (r"ESTUDIANTE|ESTUDIOS UNIVERSITARIOS", "Estudios universitarios", 3),
    (r"EGRESAD", "Egresado universitario", 3),
    (r"BACHILLER", "Bachiller", 4),
    (r"T[IÍ]TULO|TITULAD|LICENCIAD|PROFESIONAL", "Título profesional", 5),
    # Profesiones que en la práctica exigen título universitario.
    (r"M[EÉ]DICO|CIRUJANO|ABOGAD|OBSTETR|ENFERMER[OA]|BI[OÓ]LOG|INGENIER[OA]|QU[IÍ]MICO|"
     r"PSIC[OÓ]LOG|CONTADOR|ECONOMISTA|ARQUITECT|NUTRICIONISTA|TECN[OÓ]LOGO M[EÉ]DICO|ODONT[OÓ]LOG|"
     r"VETERINARI|TRABAJADOR[A]? SOCIAL|COMUNICADOR|DOCENTE|PROFESOR", "Título profesional", 5),
    (r"SECRETARIAD", "Técnico", 2),
    (r"MAESTR|MAGISTER", "Maestría", 6),
    (r"DOCTOR", "Doctorado", 7),
]


def formacion_resumen(texto: str | None) -> tuple[str, int | None]:
    """Nivel mínimo pedido: ('Secundaria completa', 1)."""
    if _vacio(texto) or _no_aplica(texto):
        return "", None
    t = texto.upper()
    hits = [(label, nivel) for pat, label, nivel in NIVELES if re.search(pat, t)]
    # "TÍTULO TÉCNICO" es técnico, no título profesional.
    if re.search(r"T[IÍ]TULO\s+(PROFESIONAL\s+)?T[EÉ]CNIC", t):
        hits = [h for h in hits if h[0] != "Título profesional"]
    if not hits:
        return "", None
    return min(hits, key=lambda h: h[1])


# Cómo se dice cada nivel dentro de una frase ("Pide ... y ...").
FRASE_FORMACION = {
    "Primaria": "primaria", "Secundaria completa": "secundaria completa",
    "Técnico": "estudios técnicos", "Estudios universitarios": "estudios universitarios",
    "Egresado universitario": "ser egresado universitario", "Bachiller": "grado de bachiller",
    "Título profesional": "título profesional", "Maestría": "maestría", "Doctorado": "doctorado",
}


def requisitos(o: dict) -> dict:
    """Resumen simple y banderas para los temas. Solo con datos de detalle."""
    exp, sin_exp, meses = experiencia_resumen(o.get("experiencia"))
    form, nivel = formacion_resumen(o.get("formacion"))
    # "Solo secundaria" exige que lo digan; un campo vacío no cuenta.
    sin_formacion = _no_aplica(o.get("formacion")) and not _vacio(o.get("formacion"))
    f = FRASE_FORMACION.get(form, form.lower())
    if form and sin_exp:
        frase = f"Pide {f} y no exige experiencia."
    elif form and exp and exp != "Con experiencia":
        frase = f"Pide {f} y {exp.lower()}."
    elif form and exp:
        frase = f"Pide {f} y experiencia."
    elif form:
        frase = f"Pide {f}."
    elif sin_exp:
        frase = "No exige experiencia."
    elif exp and exp != "Con experiencia":
        frase = f"Pide {exp.lower()}."
    else:
        frase = ""
    return {
        "corto": " · ".join(p for p in (form, exp) if p),
        "frase": frase,
        "sin_experiencia": sin_exp,
        "meses_experiencia": meses,
        "nivel": nivel,
        "formacion": form,
        "experiencia": exp,
        "solo_secundaria": (nivel is not None and nivel <= 1) or sin_formacion,
        "hasta_un_anio": meses is not None and meses <= 12,
        "experiencia_vacia": _vacio(o.get("experiencia")),
        "formacion_vacia": _vacio(o.get("formacion")),
    }


PREFIJOS_CARGO = re.compile(
    r"^(?:CONVOCATORIA\s+(?:PARA\s+)?(?:LA\s+)?)?(?:CONTRATACI[OÓ]N\s+(?:ADMINISTRATIVA\s+DE\s+SERVICIOS|CAS)\s+"
    r"(?:DE\s+|PARA\s+)?)?(?:PROCESO\s+CAS\s+N[°º.]?\s*[\w-]+\s*[-:]?\s*)?", re.I)
CANTIDAD_CARGO = re.compile(
    r"^(?:\(?\d{1,2}\)?\s*)?(?:\(?(?:UN|UNA|UN\s*\(A\)|UN/A|UNO|DOS|TRES|CUATRO|CINCO)\)?\s+)?(?:\(?\d{1,2}\)?\s+)?",
    re.I)


def limpiar_cargo(cargo: str) -> str:
    """Quita del cargo el trámite y la cantidad: 'CONTRATACIÓN ADMINISTRATIVA DE
    SERVICIOS DE UN(A) ASESOR(A)...' -> 'ASESOR(A)...'; '(01) ESPECIALISTA' ->
    'ESPECIALISTA'. No toca el resto."""
    c = re.sub(r"\s+", " ", (cargo or "").replace('"', " ").replace("“", " ").replace("”", " ")).strip()
    c = c.lstrip(" .,;:-–•*)")
    original = c
    c = PREFIJOS_CARGO.sub("", c).strip(" -:")
    c = CANTIDAD_CARGO.sub("", c).strip(" -:")
    return c if len(c) >= 3 else original


def cargo_titulo(cargo_legible: str, maximo: int = 70) -> str:
    """Versión corta para títulos: varios cargos -> 'X y otros cargos'; si es
    muy largo, se corta antes de 'para la/el...' o de un guion."""
    c = cargo_legible
    # Paréntesis largos con detalles del trámite ("(Aplicable para Procesos CAS
    # por Suplencia – Temporal)") no van en el título.
    sin_paren = re.sub(r"\s*\([^)]{18,}\)", "", c).strip()
    if len(sin_paren) >= 3:
        c = sin_paren
    if ", " in c:
        primero = re.split(r",\s+", c)[0].strip(" .-")
        if len(primero) >= 3:
            c = f"{primero} y otros cargos"
    if len(c) > maximo:
        m = re.search(r"\s+(?:para\s+(?:el|la|los|las)|de\s+la\s+(?:unidad|oficina|direcci[oó]n|gerencia|subgerencia))\s+|\s+[-–]\s+",
                      c[15:], re.I)
        if m:
            c = c[:15 + m.start()]
    if len(c) > maximo:
        c = c[:maximo].rsplit(" ", 1)[0].rstrip(",;:-")
    return c.rstrip(" .")
