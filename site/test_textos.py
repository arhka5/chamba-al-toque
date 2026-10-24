from textos import (experiencia_resumen, formacion_resumen, nombre_propio, normalizar_entidad, oracion,
                    requisitos, slug, slug_oferta)


def test_nombres():
    assert nombre_propio("MUNICIPALIDAD  DISTRITAL DE PACHACAMAC") == "Municipalidad Distrital de Pachacámac"
    assert nombre_propio("OPERARIO DE LIMPIEZA INTERNA") == "Operario de Limpieza Interna"
    assert nombre_propio("ESPECIALISTA EN CONTRATACIONES II") == "Especialista en Contrataciones II"
    assert nombre_propio("ASISTENTE ADMINISTRATIVO - CAS") == "Asistente Administrativo - CAS"
    assert nombre_propio("UGEL 03 - LIMA") == "UGEL 03 - Lima"
    assert nombre_propio("SEGURO SOCIAL DE SALUD - ESSALUD") == "Seguro Social de Salud - EsSalud"
    assert nombre_propio("TECNICO EN ADMINISTRACION") == "Técnico en Administración"
    assert nombre_propio("GOBIERNO REGIONAL SAN MARTIN") == "Gobierno Regional San Martín"
    assert nombre_propio("JEFE DE MERCADOS Y FERIAS") == "Jefe de Mercados y Ferias"
    assert nombre_propio(normalizar_entidad("UNIDAD DE GESTION EDUCATIVA LOCAL # 01")) == "UGEL 01"
    assert slug_oferta("Especialista", "UGEL 03", "821420") == "especialista-ugel-03-821420"
    assert not slug_oferta("Sub Gerente de Servicios Orientacion y Control", "X", "1").split("-1")[0].endswith("-y")


def test_oracion():
    assert oracion("SECUNDARIA COMPLETA") == "Secundaria completa"
    assert oracion("LIMPIEZA DE AMBIENTES; DESINFECCIÓN; SIAF") == "Limpieza de ambientes; desinfección; SIAF"
    assert oracion("• MANEJO DE SISTEMAS. • MANEJO DE OFFICE") == "• Manejo de sistemas. • Manejo de office"


def test_slug():
    assert slug("Municipalidad Distrital de Pachacámac") == "municipalidad-distrital-de-pachacamac"
    assert slug("Áncash") == "ancash"
    assert (slug_oferta("Operario de Limpieza Interna", "Municipalidad Distrital de Pachacámac", "821548")
            == "operario-de-limpieza-interna-muni-distrital-pachacamac-821548")


def test_experiencia():
    assert experiencia_resumen("NO APLICA") == ("Sin experiencia", True, 0)
    assert experiencia_resumen("EXPERIENCIA GENERAL DE 2 AÑOS; ESPECÍFICA 1 AÑO")[:2] == ("2 años de experiencia", False)
    assert experiencia_resumen("06 MESES EN EL SECTOR")[:2] == ("6 meses de experiencia", False)
    assert experiencia_resumen("EN LABORES SIMILARES")[:2] == ("Con experiencia", False)


def test_formacion():
    assert formacion_resumen("SECUNDARIA COMPLETA (NO INDISPENSABLE)") == ("Secundaria completa", 1)
    assert formacion_resumen("TÍTULO TÉCNICO O BACHILLER EN CONTABILIDAD") == ("Técnico", 2)
    assert formacion_resumen("TITULADO EN DERECHO, COLEGIADO Y HABILITADO") == ("Título profesional", 5)
    assert formacion_resumen("NO APLICA") == ("", None)


def test_requisitos():
    r = requisitos({"experiencia": "NO APLICA", "formacion": "SECUNDARIA COMPLETA"})
    assert r["frase"] == "Pide secundaria completa y no exige experiencia."
    assert r["corto"] == "Secundaria completa · Sin experiencia"
    assert r["solo_secundaria"] and r["sin_experiencia"]
