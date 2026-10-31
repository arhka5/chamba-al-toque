from datetime import date

import cursos as C

HOY = date(2026, 10, 30)
CATALOGO = [
    {"fuente": "capacitat", "titulo": "Excel básico *", "url": "u/excel-viejo", "horas": None, "certifica": "MTPE"},
    {"fuente": "capacitat", "titulo": "Excel básico", "url": "u/excel", "horas": 10, "certifica": "MTPE"},
    {"fuente": "capacitat", "titulo": "Excel intermedio", "url": "u/excel2", "horas": 20, "certifica": "MTPE"},
    {"fuente": "capacitat", "titulo": "Word y Excel para el trabajo – nivel básico", "url": "u/wye", "horas": 6,
     "certifica": "MTPE"},
    {"fuente": "enap", "titulo": "Gestión Pública para la inclusión", "url": "u/gp", "horas": 24,
     "certifica": "ENAP", "hasta": "2026-11-01"},
    {"fuente": "enap", "titulo": "Gestión de los recursos humanos", "url": "u/rh", "horas": 16,
     "certifica": "ENAP", "hasta": "2026-10-01"},
]


def cat():
    return C.Catalogo(CATALOGO, HOY)


def slugs(r):
    return [t["slug"] for t in r["temas"]]


def test_excel_quita_ofimatica_y_prefiere_version_con_horas():
    r = cat().para_oferta({"especializacion": "CURSO DE OFIMÁTICA", "conocimientos": "EXCEL INTERMEDIO"})
    assert slugs(r) == ["excel"]
    assert [c["url"] for c in r["temas"][0]["lista"]] == ["u/excel", "u/excel2"]


def test_ofimatica_generica():
    r = cat().para_oferta({"especializacion": "DESEABLE: CURSOS EN OFIMÁTICA", "conocimientos": "."})
    assert slugs(r) == ["ofimatica"]
    assert r["temas"][0]["lista"][0]["url"] == "u/wye"


def test_enap_vencido_no_aparece_pero_queda_el_tema():
    r = cat().para_oferta({"especializacion": "", "conocimientos": "GESTIÓN DE RECURSOS HUMANOS"})
    rh = r["temas"][0]
    assert rh["slug"] == "recursos-humanos" and rh["lista"] == [] and rh["enap"]


def test_gestion_publica_enap_vigente():
    r = cat().para_oferta({"especializacion": "CURSO EN GESTIÓN PÚBLICA", "conocimientos": ""})
    assert r["temas"][0]["lista"][0]["url"] == "u/gp"


def test_horas_minimas_y_sin_tema():
    assert C.horas_minimas("CURSOS NO MENOR A (20) HORAS ACADÉMICAS O 12 HORAS") == 20
    assert cat().para_oferta({"especializacion": "DERECHO PENAL", "conocimientos": "LEY 27444"}) is None
