import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import indexing  # noqa: E402

HOY = date(2026, 10, 27)


def pagina(carpeta: Path, nombre: str, ld: dict) -> None:
    (carpeta / nombre).mkdir(parents=True)
    (carpeta / nombre / "index.html").write_text(
        f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>', encoding="utf-8")


def test_vigentes_solo_lee_jobposting(tmp_path):
    pagina(tmp_path, "oferta/a", {"@type": "JobPosting", "url": "https://x/oferta/a/", "datePosted": "2026-10-26"})
    pagina(tmp_path, "entidad/b", {"@type": "BreadcrumbList"})
    assert indexing.vigentes(tmp_path) == {"https://x/oferta/a/": "2026-10-26"}


def test_nuevas_recientes_primero_y_viejas_sin_avisar():
    vivas = {"u1": "2026-10-27", "u2": "2026-10-25", "u3": "2026-10-01"}
    nuevas, cerradas, viejas = indexing.pendientes(vivas, {}, HOY)
    assert nuevas == ["u1", "u2"]
    assert viejas == ["u3"]
    assert cerradas == []


def test_cerradas_son_las_avisadas_que_perdieron_el_marcado():
    nuevas, cerradas, viejas = indexing.pendientes({"u1": "2026-10-27"}, {"u1": "2026-10-27", "u9": "2026-10-20"}, HOY)
    assert (nuevas, cerradas, viejas) == ([], ["u9"], [])


def test_sin_clave_no_hace_nada(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_INDEXING_KEY", raising=False)
    estado = tmp_path / "state.json"
    estado.write_text("{}", encoding="utf-8")
    assert indexing.main([str(tmp_path), str(estado)]) == 0
    assert estado.read_text(encoding="utf-8") == "{}"
    assert "sin configurar" in capsys.readouterr().out
