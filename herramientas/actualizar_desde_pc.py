"""Descarga las ofertas desde esta PC y publica el sitio.

SERVIR responde 403 a las IP de GitHub Actions, pero no a una conexión de
casa. Esta tarea (programada en Windows con instalar_tarea.ps1) scrapea aquí,
sube ofertas.json a la rama "data" y lanza el workflow en modo "solo publicar",
que genera el sitio con esos datos.

    .venv/Scripts/python herramientas/actualizar_desde_pc.py [--log]

No toca la carpeta de trabajo: el commit en "data" se arma con comandos de
bajo nivel de git sobre el último commit remoto.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRABAJO = REPO / "out" / "pc"
MIN_PROPORCION = 0.5  # igual que build.py: si llega menos de la mitad, algo falló
# Corre con pythonw desde el Programador de tareas: sin esto, cada git/gh abre una consola.
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def git(*args: str, entrada: bytes | None = None) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, input=entrada, capture_output=True, check=True,
                       creationflags=SIN_VENTANA)
    return r.stdout.decode("utf-8").strip()


def workflow_en_curso() -> bool:
    r = subprocess.run(["gh", "run", "list", "--workflow", "actualizar.yml", "--limit", "5",
                        "--json", "status", "-q", '[.[] | select(.status != "completed")] | length'],
                       cwd=REPO, capture_output=True, text=True, check=True, creationflags=SIN_VENTANA)
    return r.stdout.strip() not in ("", "0")


def subir_a_data(archivo: Path, mensaje: str) -> str:
    """Reemplaza ofertas.json en la rama data conservando state.json."""
    git("fetch", "-q", "origin", "data")
    padre = git("rev-parse", "origin/data")
    blob = git("hash-object", "-w", str(archivo))
    filas = [f for f in git("ls-tree", padre).splitlines() if not f.endswith("\tofertas.json")]
    filas.append(f"100644 blob {blob}\tofertas.json")
    arbol = git("mktree", entrada=("\n".join(filas) + "\n").encode("utf-8"))
    commit = git("commit-tree", arbol, "-p", padre, "-m", mensaje)
    git("push", "-q", "origin", f"{commit}:refs/heads/data")
    return commit


def main() -> int:
    TRABAJO.mkdir(parents=True, exist_ok=True)
    anterior, nuevo = TRABAJO / "previous.json", TRABAJO / "ofertas.json"
    salida = None
    if "--log" in sys.argv:  # la tarea programada escribe aquí (pythonw no tiene consola)
        salida = open(TRABAJO / "actualizar.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = salida

    git("fetch", "-q", "origin", "data")
    anterior.write_text(git("show", "origin/data:ofertas.json"), encoding="utf-8")
    n_antes = len(json.loads(anterior.read_text(encoding="utf-8")).get("offers", []))
    log(f"Datos anteriores: {n_antes} ofertas. Descargando de Talento Perú…")

    r = subprocess.run([sys.executable, "-m", "scraper", "--previous", str(anterior),
                        "--output", str(nuevo)], cwd=REPO, stdout=salida, stderr=salida,
                       creationflags=SIN_VENTANA)
    if r.returncode != 0 or not nuevo.exists():
        log("El scraper terminó con error: no se publica nada.")
        return 1
    datos = json.loads(nuevo.read_text(encoding="utf-8"))
    n_ahora, fuente = len(datos["offers"]), datos["source"]
    if not fuente.get("ok"):
        log(f"Corrida incompleta ({fuente.get('error')}): no se publica.")
        return 1
    if n_antes and n_ahora < n_antes * MIN_PROPORCION:
        log(f"Llegaron {n_ahora} ofertas frente a {n_antes}: parece un error, no se publica.")
        return 1

    if workflow_en_curso():
        log("Hay una publicación en curso; se reintenta en la próxima ejecución.")
        return 1
    try:
        commit = subir_a_data(nuevo, f"Ofertas desde PC {datetime.now():%Y-%m-%d %H:%M}")
    except subprocess.CalledProcessError:
        log("La rama data cambió mientras tanto; se reintenta una vez.")
        commit = subir_a_data(nuevo, f"Ofertas desde PC {datetime.now():%Y-%m-%d %H:%M}")
    log(f"Subido a la rama data ({commit[:7]}): {n_ahora} ofertas, "
        f"{fuente['detailsFetched']} detalles nuevos, {fuente['seconds'] // 60} min.")

    subprocess.run(["gh", "workflow", "run", "actualizar.yml", "-f", "solo_publicar=true"],
                   cwd=REPO, check=True, capture_output=True, creationflags=SIN_VENTANA)
    log("Publicación lanzada en GitHub Actions.")
    avisar_a_bing()
    return 0


def avisar_a_bing() -> None:
    """IndexNow da 403 a GitHub Actions: se avisa desde aquí cuando la publicación terminó."""
    time.sleep(20)  # que la corrida recién lanzada aparezca en la lista
    rid = subprocess.run(["gh", "run", "list", "--workflow", "actualizar.yml", "--limit", "1",
                          "--json", "databaseId", "-q", ".[0].databaseId"], cwd=REPO, capture_output=True,
                         text=True, creationflags=SIN_VENTANA).stdout.strip()
    if not rid:
        log("IndexNow: no encontré la corrida; se avisa en la próxima ejecución.")
        return
    fin = subprocess.run(["gh", "run", "watch", rid, "--exit-status"], cwd=REPO, capture_output=True,
                         creationflags=SIN_VENTANA)
    if fin.returncode != 0:
        log("IndexNow: la publicación falló; no se avisa a Bing.")
        return
    r = subprocess.run([sys.executable, str(REPO / "herramientas" / "indexnow.py"), "--remoto",
                        "https://chambearhoy.toca.pe", str(TRABAJO / "indexnow.json")],
                       cwd=REPO, capture_output=True, text=True, creationflags=SIN_VENTANA)
    log((r.stdout or r.stderr).strip().replace("\n", " | "))


if __name__ == "__main__":
    sys.exit(main())
