"""Publica en el canal de Telegram las convocatorias nuevas de la última corrida.

site/build.py deja el mensaje en out/telegram.json; esto lo envía y marca esas
ofertas en state.json ("anunciadas") para no repetirlas en la próxima corrida.

    python herramientas/telegram.py out/telegram.json out/state.json

Necesita TELEGRAM_BOT_TOKEN (del bot creado con @BotFather, administrador del
canal) y TELEGRAM_CHAT ("@nombre_del_canal"). Sin ellos no hace nada.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

LIMITE = 4096  # caracteres por mensaje en Telegram


def recortar(mensaje: str) -> str:
    """Quita ofertas del final (nunca el pie con los enlaces) hasta que quepa."""
    lineas = mensaje.split("\n")
    while len("\n".join(lineas)) > LIMITE and len(lineas) > 4:
        del lineas[-3]  # la última oferta: después solo van la línea vacía y el pie
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    aviso, estado = Path(argv[0]), Path(argv[1])
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if not token or not chat:
        print("Telegram sin configurar (faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT): no se publica.")
        return 0
    if not aviso.exists():
        print("No hay convocatorias nuevas por anunciar.")
        return 0
    datos = json.loads(aviso.read_text(encoding="utf-8"))
    cuerpo = json.dumps({"chat_id": chat, "text": recortar(datos["mensaje"]), "parse_mode": "HTML",
                         "link_preview_options": {"is_disabled": True}}).encode("utf-8")
    pedido = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=cuerpo,
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            ok = json.load(r).get("ok")
    except urllib.error.HTTPError as e:  # el cuerpo dice qué falló (chat mal escrito, bot sin permiso…)
        print(f"Telegram rechazó el mensaje: {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
        return 1
    if not ok:
        print("Telegram no confirmó el envío.")
        return 1

    state = json.loads(estado.read_text(encoding="utf-8"))
    state["anunciadas"] = list(dict.fromkeys(state.get("anunciadas", []) + datos["ids"]))
    estado.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Publicado en {chat}: {len(datos['ids'])} convocatorias nuevas.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
