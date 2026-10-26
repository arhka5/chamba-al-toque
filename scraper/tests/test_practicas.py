from pathlib import Path

from scraper import practicas as P

FIX = Path(__file__).parent / "fixtures"


def test_lista_de_practicas():
    lista = P.parse_list((FIX / "practicas_p1.html").read_text(encoding="utf-8"))
    assert len(lista) == 10
    p = lista[0]
    assert p["entidad"].endswith("SUNAT")
    assert p["modalidad"] == "Practicas Profesionales"
    assert (p["departamento"], p["provincia"]) == ("TACNA", "TACNA")
    assert (p["inicio"], p["fin"]) == ("2026-10-23", "2026-11-05")
    assert p["vacantes"] == 11
    assert p["_button"].startswith("frmLstModFormativas:idPnlRepeatPuestos:0:")
    # SERVIR repite filas idénticas (otra vacante del mismo aviso); __main__ las numera -2, -3…
    assert len({x["key"] for x in lista}) == 9


def test_detalle_de_practica():
    d = P.parse_detail((FIX / "practicas_detalle.html").read_text(encoding="utf-8"))
    assert d["condicion"] == "Egresado"
    assert d["formacion"] == "Carrera Universitaria"
    assert "DERECHO" in d["carreras"] and "Egresado" not in d["carreras"]
    assert d["subvencion"] == 1600.0
    assert (d["duracion_meses"], d["horas_semana"]) == (6, 40)
    assert d["modo"] == "Presencial"
    assert d["url_bases"].startswith("https://unete.sunat.gob.pe/")
    assert d["conocimientos"][0] == "Microsoft Word nivel intermedio"
    assert len(d["conocimientos"]) == 3
