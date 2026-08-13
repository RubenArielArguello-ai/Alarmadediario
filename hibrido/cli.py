#!/usr/bin/env python3
"""
Modo dos fotos: mismo flujo que el `detect_diario.py` original, pero pasando
por los dos validadores.

    python hibrido/cli.py --fondo sin_diario.jpg --actual con_diario.jpg

Sirve para probar sin cámara y para comparar contra el detector viejo:

    python hibrido/cli.py --fondo a.jpg --actual b.jpg --comparar

`--comparar` corre además el `detectar_objeto_nuevo()` del proyecto original
(el de escala de grises, sin tocar) y muestra los dos resultados lado a lado.
Es la forma rápida de ver qué aporta cada etapa.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parent
for p in (str(AQUI), str(RAIZ_REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fusion import Fusion  # noqa: E402
from modelo import DetectorOWL  # noqa: E402
from validador_color import ValidadorColor  # noqa: E402


def cargar(ruta: str):
    img = cv2.imread(ruta)
    if img is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta}")
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fondo", required=True, help="Foto de la alfombra vacía")
    ap.add_argument("--actual", required=True, help="Foto con el posible diario")
    ap.add_argument("--config", default=str(AQUI / "config.json"))
    ap.add_argument("--modo", help="cascada | and | or | ponderado | solo_color | solo_modelo")
    ap.add_argument("--sin-modelo", action="store_true",
                    help="Atajo para --modo solo_color (no carga OWLv2)")
    ap.add_argument("--salida", default=str(AQUI / "capturas"))
    ap.add_argument("--comparar", action="store_true",
                    help="Corre también el detector original en escala de grises")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    if args.sin_modelo:
        cfg["fusion"]["modo"] = "solo_color"
    elif args.modo:
        cfg["fusion"]["modo"] = args.modo

    try:
        fondo = cargar(args.fondo)
        actual = cargar(args.actual)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 2

    if fondo.shape != actual.shape:
        print(f"AVISO: las fotos tienen distinto tamaño "
              f"({fondo.shape[1]}x{fondo.shape[0]} vs "
              f"{actual.shape[1]}x{actual.shape[0]}). Redimensiono el fondo.")
        fondo = cv2.resize(fondo, (actual.shape[1], actual.shape[0]))

    # ---------------------------------------------------- [1] validador color
    color = ValidadorColor(cfg["color"])
    color.fijar_fondo(fondo)
    res_color = color.analizar(actual)

    print("\n--- 1. Diferencia de color sobre la alfombra ---")
    print(f"  ¿apareció algo?  {'sí' if res_color.hay_cambio else 'no'}")
    print(f"  regiones         {len(res_color.regiones)}")
    print(f"  área total       {res_color.area_total} px")
    print(f"  cobertura        {res_color.cobertura * 100:.2f}% de la zona")
    print(f"  ΔE color         {res_color.delta_e:.1f}")
    print(f"  ¿parece papel?   {res_color.papel:.2f}  "
          f"(umbral {color.papel_minimo:.2f})")
    for i, r in enumerate(res_color.regiones, 1):
        print(f"    región {i}: {r.x2 - r.x1}x{r.y2 - r.y1} px en ({r.x1},{r.y1}), "
              f"área {r.area}, ΔL {r.delta_luz:+.1f}, croma {r.delta_croma:.1f}, "
              f"papel {r.papel:.2f}")

    # ---------------------------------------------------------- [2] modelo
    fusion = Fusion(cfg["fusion"])
    conf, cajas_modelo = 0.0, []
    usa_modelo = cfg["fusion"]["modo"] != "solo_color"

    if usa_modelo and (res_color.hay_cambio or cfg["fusion"]["modo"] != "cascada"):
        owl = DetectorOWL(cfg["modelo"])
        print("\n--- 2. OWLv2 ---")
        print("  cargando modelo…")
        owl.cargar()

        alto, ancho = actual.shape[:2]
        caja = color.bbox_regiones(
            res_color, cfg["deteccion"].get("margen_recorte", 40), alto, ancho
        )
        recorte, offset = actual, (0, 0)
        if caja is not None:
            x1, y1, x2, y2 = caja
            recorte = actual[y1:y2, x1:x2]
            offset = (x1, y1)
            print(f"  recorto a la región del color: {x2 - x1}x{y2 - y1} px")
        else:
            print("  sin región de color: le paso la foto entera")

        conf, cajas_modelo = owl.detectar(recorte)
        for c in cajas_modelo:
            c["x1"] += offset[0]; c["x2"] += offset[0]
            c["y1"] += offset[1]; c["y2"] += offset[1]

        print(f"  mejor confianza  {conf:.3f}  (umbral {owl.umbral:.2f})")
        for c in cajas_modelo[:5]:
            print(f"    {c['label']}: {c['conf']:.3f}")
        umbral_modelo = owl.umbral
    else:
        if not usa_modelo:
            print("\n--- 2. OWLv2 — salteado (modo solo_color) ---")
        else:
            print("\n--- 2. OWLv2 — salteado: el color no vio nada (modo cascada) ---")
        umbral_modelo = float(cfg["modelo"]["confianza_minima"])

    # ---------------------------------------------------------- [3] fusión
    veredicto = fusion.evaluar(
        score_color=res_color.score,
        hay_cambio_color=res_color.hay_cambio,
        papel=res_color.papel,
        conf_modelo=conf,
        umbral_papel=color.papel_minimo,
        umbral_modelo=umbral_modelo,
    )

    print(f"\n--- 3. Veredicto (modo {cfg['fusion']['modo']}) ---")
    print(f"  color  dice: {'DIARIO' if veredicto.color_ok else 'no'}")
    print(f"  modelo dice: {'DIARIO' if veredicto.modelo_ok else 'no'}")
    print(f"  score final: {veredicto.score:.3f}")
    print(f"  razón:       {veredicto.explicacion}")
    print(f"\n{'✅ DIARIO ENTREGADO' if veredicto.es_diario else '❌ No hay diario'}\n")

    # ------------------------------------------------- comparación con el viejo
    if args.comparar:
        from detect_diario import detectar_objeto_nuevo, cargar_y_preparar

        _, fondo_gris = cargar_y_preparar(args.fondo)
        img_orig, actual_gris = cargar_y_preparar(args.actual)
        detectado, _, _, dets = detectar_objeto_nuevo(
            img_orig, fondo_gris, actual_gris, salida_dir=args.salida
        )
        print("--- Comparación con detect_diario.py (gris, sin modelo) ---")
        print(f"  original: {'detecta algo' if detectado else 'no detecta nada'}"
              f"  ({len(dets)} región/es)")
        print(f"  híbrido:  {'DIARIO' if veredicto.es_diario else 'no'}"
              f"  ({len(res_color.regiones)} región/es de color, "
              f"conf modelo {conf:.2f})\n")

    # ---------------------------------------------------------- salida visual
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    marcado = actual.copy()
    for c in res_color.cajas + cajas_modelo:
        es_color = c.get("origen") == "color"
        tono = (255, 200, 0) if es_color else (0, 200, 0)
        cv2.rectangle(marcado, (int(c["x1"]), int(c["y1"])),
                      (int(c["x2"]), int(c["y2"])), tono, 3)
        cv2.putText(marcado, f"{c['label']} {c['conf']:.2f}",
                    (int(c["x1"]), max(20, int(c["y1"]) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, tono, 2)

    destino = salida / f"hibrido_{Path(args.actual).stem}.jpg"
    cv2.imwrite(str(destino), marcado)
    print(f"Imagen marcada: {destino}")
    print("  cian = lo que vio el color, verde = lo que reconoció el modelo\n")

    return 0 if veredicto.es_diario else 1


if __name__ == "__main__":
    raise SystemExit(main())
