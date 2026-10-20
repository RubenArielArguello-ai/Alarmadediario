#!/usr/bin/env python3
"""
Descarga los pesos del modelo UNA SOLA VEZ (requiere internet).
Después de correr esto, el sistema funciona 100% offline.

Uso:
    python descargar_modelo.py            # el motor de config.json
    python descargar_modelo.py --todos    # YOLO-World y OWLv2
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).parent
RUTA_CONFIG = RAIZ / "config.json"
sys.path.insert(0, str(RAIZ))


def bajar_owlv2(cfg: dict) -> int:
    modelo_id = cfg["id"]
    destino = RAIZ / cfg.get("carpeta_local", "modelos")

    if (destino / "config.json").exists():
        print(f"[OK] OWLv2 ya está en {destino}")
        print("     Borrá esa carpeta si querés volver a descargarlo.")
        return 0

    print(f"Descargando {modelo_id}")
    print("Son ~1,2 GB. Requiere internet. Es la única vez.\n")

    try:
        from transformers import Owlv2ForObjectDetection, Owlv2Processor
    except ImportError:
        print("ERROR: faltan dependencias. Corré primero:")
        print("    pip install -r hibrido/requirements.txt")
        return 1

    destino.mkdir(exist_ok=True)
    proc = Owlv2Processor.from_pretrained(modelo_id)
    model = Owlv2ForObjectDetection.from_pretrained(modelo_id)
    proc.save_pretrained(str(destino))
    model.save_pretrained(str(destino))

    total = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file())
    print(f"\n[OK] OWLv2 guardado en {destino} ({total / 1e6:.0f} MB)")
    return 0


def bajar_yolo_world(cfg: dict) -> int:
    try:
        from modelo_yolo import DetectorYoloWorld
    except ImportError:
        print("ERROR: faltan dependencias. Corré primero:")
        print("    pip install -r hibrido/requirements.txt")
        return 1

    print("Descargando YOLO-World (~26 MB) y el codificador de texto CLIP (~340 MB).")
    print("Requiere internet. Es la única vez.\n")
    # Cargarlo y fijarle un prompt baja las dos cosas: los pesos a
    # modelos_yolo/ y CLIP a modelos_yolo/clip/.
    detector = DetectorYoloWorld({**cfg, "prompts": cfg.get("prompts") or ["newspaper"]})
    detector.cargar()
    print(f"\n[OK] YOLO-World listo en {detector.carpeta}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--todos", action="store_true", help="baja YOLO-World y OWLv2")
    args = ap.parse_args()

    from modelo import config_motor

    modelo = json.loads(RUTA_CONFIG.read_text())["modelo"]
    motores = ["yolo_world", "owlv2"] if args.todos else [modelo.get("motor", "owlv2")]

    for motor in motores:
        cfg = config_motor({**modelo, "motor": motor})
        error = bajar_yolo_world(cfg) if motor == "yolo_world" else bajar_owlv2(cfg)
        if error:
            return error

    print("\nYa podés desconectar internet. Para verificarlo:")
    print("    python hibrido/server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
