#!/usr/bin/env python3
"""
Descarga los pesos de OWLv2 UNA SOLA VEZ (requiere internet).
Despues de correr esto, el sistema funciona 100% offline.

Uso:
    python descargar_modelo.py
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
RUTA_CONFIG = RAIZ / "config.json"


def main() -> int:
    config = json.loads(RUTA_CONFIG.read_text())
    modelo_id = config["modelo"]["id"]
    destino = RAIZ / config["modelo"].get("carpeta_local", "modelos")

    if (destino / "config.json").exists():
        print(f"[OK] El modelo ya está en {destino}")
        print("     Borrá esa carpeta si querés volver a descargarlo.")
        return 0

    print(f"Descargando {modelo_id}")
    print("Son ~1,2 GB. Requiere internet. Es la única vez.\n")

    try:
        from transformers import Owlv2ForObjectDetection, Owlv2Processor
    except ImportError:
        print("ERROR: faltan dependencias. Corré primero:")
        print("    pip install -r requirements.txt")
        return 1

    destino.mkdir(exist_ok=True)

    proc = Owlv2Processor.from_pretrained(modelo_id)
    model = Owlv2ForObjectDetection.from_pretrained(modelo_id)

    proc.save_pretrained(str(destino))
    model.save_pretrained(str(destino))

    total = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file())
    print(f"\n[OK] Modelo guardado en {destino} ({total / 1e6:.0f} MB)")
    print("\nYa podés desconectar internet. Para verificarlo:")
    print("    python server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
