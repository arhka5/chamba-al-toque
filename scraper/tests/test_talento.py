from pathlib import Path

from scraper.talento import (ajax_update, offer_key, parse_detail, parse_list, parse_pages,
                             parse_viewstate, regimen)

FIX = Path(__file__).parent / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_lista_primera_pagina():
    html = read("lista_p1.html")
    offers = parse_list(html)
    assert len(offers) == 10
    o = offers[0]
    assert o["cargo"] == "OPERARIO DE LIMPIEZA INTERNA"
    assert o["entidad"] == "MUNICIPALIDAD DISTRITAL DE PACHACAMAC"
    assert (o["departamento"], o["provincia"]) == ("LIMA", "PACHACAMAC")
    assert o["convocatoria"] == "D.LEG 1057 - INDETERMINADO-033"
    assert o["regimen"] == "CAS"
    assert o["vacantes"] == 4
    assert o["sueldo"] == 1720.0
    assert (o["inicio"], o["fin"]) == ("2026-10-23", "2026-11-05")
    assert o["_button"].endswith(":0:j_idt78")
    assert len({x["key"] for x in offers}) == 10
    assert parse_pages(html) == (1, 381)
    assert parse_viewstate(html)


def test_lista_por_ajax():
    xml = read("lista_p2_ajax.xml")
    html = ajax_update(xml)
    assert html
    offers = parse_list(html)
    assert len(offers) == 10
    assert offers[0]["entidad"] == "MUNICIPALIDAD PROVINCIAL JAUJA"
    assert parse_pages(html) == (2, 381)


def test_detalle():
    d = parse_detail(read("detalle.html"))
    assert d["id"] == "821548"  # no el "N° 1456" del menú
    assert d["experiencia"] == "NO APLICA"
    assert d["formacion"] == "SECUNDARIA COMPLETA (NO INDISPENSABLE)"
    assert d["conocimientos"].startswith("LIMPIEZA DE AMBIENTES")
    assert d["url_bases"] == "https://munipachacamac.gob.pe/convocatorias.html"


def test_regimen_y_clave():
    assert regimen("D.LEG 1057 - DETERMINADO-006") == "CAS"
    assert regimen("D.L. 728 - 001") == "728"
    a = offer_key({"entidad": "X", "convocatoria": "1", "cargo": "A", "ubicacion": "LIMA"})
    b = offer_key({"entidad": " x ", "convocatoria": "1", "cargo": "a", "ubicacion": "lima"})
    assert a == b
