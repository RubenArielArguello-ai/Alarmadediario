#!/usr/bin/env python3
"""
Harness de evaluación del detector híbrido.

Corre tres bancos de casos y arma una matriz de confusión:

  1. Diario sobre alfombra, sintético con semilla fija. Test de regresión
     del perfil "diario" (exige que el objeto parezca papel): cubre sombra,
     objeto de otro color y ruido de sensor.

  2. Hoja blanca sobre escritorio, sintético con semilla fija. Prueba SOLO la
     etapa de color con el perfil genérico (sin exigir papel): que un lápiz y
     una birome negra se vean como cambio, y que la sombra de una mano no. Qué
     objeto es lo decide el modelo con el prompt de la web; eso no se evalúa
     acá porque depende de cada prompt.

  3. Pares reales, si los hay. Poné carpetas en data/pares/ así:

        data/pares/diario_lluvia/fondo.jpg   + actual.jpg
        data/pares/vacio_noche/fondo.jpg     + actual.jpg

     El prefijo de la carpeta es la etiqueta: `diario_` = tendría que
     disparar, `vacio_` = no.

Uso:
    python harness/run_eval_hibrido.py                # solo color, rápido
    python harness/run_eval_hibrido.py --con-modelo   # carga OWLv2 (lento)
    python harness/run_eval_hibrido.py --modo and
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "hibrido"))

from fusion import Fusion  # noqa: E402
from validador_color import ValidadorColor  # noqa: E402


Caso = tuple[str, np.ndarray, np.ndarray, bool, str]   # (..., perfil)


def casos_sinteticos() -> list[Caso]:
    """Genera el banco del diario. Semilla fija => siempre el mismo resultado."""
    rng = np.random.default_rng(7)
    H, W = 480, 854

    alfombra = np.zeros((H, W, 3), np.uint8)
    alfombra[:] = (120, 70, 45)                       # BGR azulado
    alfombra = np.clip(
        alfombra + rng.normal(0, 9, (H, W, 3)), 0, 255
    ).astype(np.uint8)

    # (a) diario: rectángulo claro, poco saturado, con "texto" impreso
    diario = alfombra.copy()
    x1, y1, x2, y2 = 340, 200, 600, 320
    papel = np.full((y2 - y1, x2 - x1, 3), 205, np.uint8)
    papel = np.clip(papel + rng.normal(0, 6, papel.shape), 0, 255).astype(np.uint8)
    for fila in range(10, papel.shape[0] - 6, 13):
        papel[fila:fila + 4, 8:-8] = 55
    diario[y1:y2, x1:x2] = papel

    # (b) sombra: se oscurece media escena sin cambiar el tono
    sombra = alfombra.copy()
    sombra[:, W // 2:] = (sombra[:, W // 2:] * 0.65).astype(np.uint8)

    # (c) objeto saturado que NO es papel
    rojo = alfombra.copy()
    cv2.circle(rojo, (460, 260), 75, (35, 30, 190), -1)

    # (d) misma escena, solo ruido de sensor
    igual = np.clip(
        alfombra + rng.normal(0, 4, (H, W, 3)), 0, 255
    ).astype(np.uint8)

    return [
        ("sint: diario sobre la alfombra", alfombra, diario, True, "diario"),
        ("sint: solo una sombra", alfombra, sombra, False, "diario"),
        ("sint: objeto rojo (no es papel)", alfombra, rojo, False, "diario"),
        ("sint: escena igual + ruido", alfombra, igual, False, "diario"),
    ]


def casos_hoja() -> list[Caso]:
    """Hoja blanca sobre un escritorio de madera, con distintos objetos."""
    rng = np.random.default_rng(11)
    H, W = 480, 854

    def foto(img):
        return np.clip(img + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)

    mesa = np.zeros((H, W, 3), np.float32)
    mesa[:] = (60, 105, 150)
    vacia = mesa.copy()
    vacia[90:400, 260:595] = (232, 236, 240)          # la hoja

    # lápiz amarillo con goma rosa y punta de madera, inclinado
    lapiz = vacia.copy()
    cuerpo = np.array([[330, 235], [500, 265], [497, 280], [327, 250]], np.int32)
    cv2.fillPoly(lapiz, [cuerpo], (30, 195, 240))
    cv2.fillPoly(lapiz, [np.array([[315, 232], [330, 235], [327, 250],
                                   [312, 247]], np.int32)], (170, 150, 235))
    cv2.fillPoly(lapiz, [np.array([[500, 265], [530, 276], [497, 280]],
                                  np.int32)], (140, 185, 215))

    # birome negra: oscura y SIN color, lo que la regla de sombras de antes
    # confundía con una sombra
    birome = vacia.copy()
    cv2.fillPoly(birome, [np.array([[345, 300], [530, 260], [533, 270],
                                    [348, 310]], np.int32)], (28, 28, 30))

    # sombra de una mano: oscurece ~38% y suave, sin cambiar el tono
    sombra = vacia.copy()
    m = np.zeros((H, W), np.float32)
    cv2.ellipse(m, (470, 220), (110, 75), 20, 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (61, 61), 0)
    sombra *= 1 - 0.38 * m[..., None]

    fondo = foto(vacia)
    return [
        ("hoja: lápiz apoyado", fondo, foto(lapiz), True, "hoja"),
        ("hoja: birome negra", fondo, foto(birome), True, "hoja"),
        ("hoja: sombra de una mano", fondo, foto(sombra), False, "hoja"),
        ("hoja: vacía + ruido", fondo, foto(vacia), False, "hoja"),
    ]


def casos_reales(carpeta: Path) -> list[Caso]:
    if not carpeta.exists():
        return []
    fuera = []
    for sub in sorted(p for p in carpeta.iterdir() if p.is_dir()):
        fondo = next((f for f in sub.glob("fondo.*")), None)
        actual = next((f for f in sub.glob("actual.*")), None)
        if not fondo or not actual:
            print(f"  aviso: {sub.name} no tiene fondo.* y actual.*, lo salteo")
            continue
        a, b = cv2.imread(str(fondo)), cv2.imread(str(actual))
        if a is None or b is None:
            print(f"  aviso: no pude leer las imágenes de {sub.name}")
            continue
        if a.shape != b.shape:
            a = cv2.resize(a, (b.shape[1], b.shape[0]))
        fuera.append((f"real: {sub.name}", a, b, sub.name.startswith("diario"),
                      "diario"))
    return fuera


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(RAIZ / "hibrido" / "config.json"))
    ap.add_argument("--modo", default=None,
                    help="cascada | and | or | ponderado | solo_color | solo_modelo")
    ap.add_argument("--con-modelo", action="store_true",
                    help="carga OWLv2 (lento). Sin esto corre en modo solo_color.")
    ap.add_argument("--pares", default=str(RAIZ / "data" / "pares"))
    ap.add_argument("--reporte", default=str(RAIZ / "harness" / "reporte_hibrido.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    cfg["fusion"]["modo"] = args.modo or ("cascada" if args.con_modelo else "solo_color")
    modo = cfg["fusion"]["modo"]

    owl = None
    if args.con_modelo and modo != "solo_color":
        from modelo import DetectorOWL

        print("Cargando OWLv2… (puede tardar)")
        owl = DetectorOWL(cfg["modelo"])
        owl.cargar()

    print(f"\nHarness híbrido — modo de fusión: {modo}")
    casos = casos_sinteticos() + casos_hoja() + casos_reales(Path(args.pares))
    print(f"{len(casos)} caso(s)\n")

    fusion = Fusion(cfg["fusion"])
    solo_color = Fusion({"modo": "solo_color"})
    vp = vn = fp = fn = 0
    detalles = []

    print(f"{'caso':40} {'espera':7} {'da':7} {'ΔE':>6} {'papel':>6} {'conf':>6}")
    print("-" * 82)

    for nombre, fondo, actual, esperado, perfil in casos:
        es_hoja = perfil == "hoja"
        color = ValidadorColor({**cfg["color"], "exigir_papel": not es_hoja})
        color.fijar_fondo(fondo)
        rc = color.analizar(actual)

        conf = 0.0
        if owl is not None and not es_hoja and (rc.hay_cambio or modo != "cascada"):
            alto, ancho = actual.shape[:2]
            caja = color.bbox_regiones(
                rc, cfg["deteccion"].get("margen_recorte", 40), alto, ancho
            )
            recorte = actual if caja is None else actual[caja[1]:caja[3], caja[0]:caja[2]]
            if recorte.size:
                conf, _ = owl.detectar(recorte)

        ver = (solo_color if es_hoja else fusion).evaluar(
            rc.score, rc.hay_cambio, rc.papel, conf,
            color.umbral_papel, float(cfg["modelo"]["confianza_minima"]),
        )

        if ver.es_diario and esperado:
            vp += 1; marca = "OK"
        elif not ver.es_diario and not esperado:
            vn += 1; marca = "OK"
        elif ver.es_diario and not esperado:
            fp += 1; marca = "FALSO POSITIVO"
        else:
            fn += 1; marca = "FALSO NEGATIVO"

        print(f"{('[' + ('OK' if marca == 'OK' else 'XX') + '] ') + nombre:40} "
              f"{str(esperado):7} {str(ver.es_diario):7} "
              f"{rc.delta_e:6.1f} {rc.papel:6.2f} {conf:6.2f}")
        if marca != "OK":
            print(f"       -> {marca}: {ver.explicacion}")

        detalles.append({
            "caso": nombre, "esperado": esperado, "obtenido": ver.es_diario,
            "resultado": marca, "delta_e": round(rc.delta_e, 2),
            "papel": round(rc.papel, 3), "area": rc.area_total,
            "confianza_modelo": round(conf, 3),
            "score_final": round(ver.score, 3), "explicacion": ver.explicacion,
        })

    total = len(casos)
    aciertos = vp + vn
    precision = vp / (vp + fp) if (vp + fp) else 0.0
    recall = vp / (vp + fn) if (vp + fn) else 0.0

    print("-" * 82)
    print(f"aciertos {aciertos}/{total}   "
          f"VP={vp} VN={vn} FP={fp} FN={fn}")
    print(f"precisión {precision:.2f}   recall {recall:.2f}")
    if not args.con_modelo:
        print("\n(corrió sin OWLv2: agregá --con-modelo para evaluar el pipeline completo)")

    reporte = {
        "modo_fusion": modo, "con_modelo": bool(owl), "total": total,
        "aciertos": aciertos, "vp": vp, "vn": vn, "fp": fp, "fn": fn,
        "precision": round(precision, 3), "recall": round(recall, 3),
        "detalles": detalles,
    }
    Path(args.reporte).write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nReporte: {args.reporte}\n")

    return 0 if aciertos == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
