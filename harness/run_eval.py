import os
import sys
import json
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from detect_diario import detectar_objeto_nuevo, cargar_y_preparar

TEST_DIR = os.path.join("data", "test_samples")
MANIFEST_PATH = os.path.join(TEST_DIR, "casos.json")
SALIDA_TEST = os.path.join("harness", "salidas_test")

EJEMPLO_MANIFEST = [
    {"nombre": "diario_llego", "fondo": "piso_vacio.jpg", "actual": "piso_con_diario.jpg", "esperado": True},
    {"nombre": "sin_cambios", "fondo": "piso_vacio.jpg", "actual": "piso_vacio.jpg", "esperado": False},
    {"nombre": "viceversa_diario_saco", "fondo": "piso_con_diario.jpg", "actual": "piso_vacio.jpg", "esperado": True},
]


def cargar_casos():
    if not os.path.exists(MANIFEST_PATH):
        return None
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluar_harness():
    print("🚀 Iniciando Test Harness para Alarmadediario...")

    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR, exist_ok=True)
        print(f"⚠️ Se creó la carpeta '{TEST_DIR}'. Coloca imágenes de prueba y un 'casos.json' allí.")
        return

    casos = cargar_casos()
    if not casos:
        print(f"⚠️ No encontré '{MANIFEST_PATH}'.")
        print("Creá ese archivo describiendo tus pares de fotos. Ejemplo:")
        print(json.dumps(EJEMPLO_MANIFEST, indent=2, ensure_ascii=False))
        return

    os.makedirs(SALIDA_TEST, exist_ok=True)

    reporte = {
        "fecha": datetime.datetime.now().isoformat(),
        "total_casos": len(casos),
        "pasaron": 0,
        "fallaron": 0,
        "detalles": [],
    }

    for caso in casos:
        nombre = caso.get("nombre", "caso_sin_nombre")
        ruta_fondo = os.path.join(TEST_DIR, caso["fondo"])
        ruta_actual = os.path.join(TEST_DIR, caso["actual"])
        esperado = caso["esperado"]

        print(f"Evaluando caso '{nombre}': fondo={caso['fondo']} actual={caso['actual']} (esperado detectado={esperado})")

        try:
            _, fondo_gris = cargar_y_preparar(ruta_fondo)
            img_actual, actual_gris = cargar_y_preparar(ruta_actual)

            detectado, ruta_binaria, ruta_marcado, detecciones = detectar_objeto_nuevo(
                imagen_original=img_actual,
                fondo_gris=fondo_gris,
                actual_gris=actual_gris,
                salida_dir=SALIDA_TEST,
                source_image_name=caso["actual"],
            )

            paso = detectado == esperado
            if paso:
                reporte["pasaron"] += 1
            else:
                reporte["fallaron"] += 1

            reporte["detalles"].append({
                "caso": nombre,
                "fondo": caso["fondo"],
                "actual": caso["actual"],
                "esperado": esperado,
                "detectado": detectado,
                "resultado": "PASS" if paso else "FAIL",
                "n_detecciones": len(detecciones),
                "imagen_marcada": ruta_marcado,
            })

        except Exception as err:
            reporte["fallaron"] += 1
            reporte["detalles"].append({
                "caso": nombre,
                "resultado": "ERROR",
                "error": str(err),
            })

    ruta_reporte = os.path.join("harness", "reporte_harness.json")
    with open(ruta_reporte, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Evaluación finalizada. Reporte guardado en '{ruta_reporte}'")
    print(f"Resultados: {reporte['pasaron']}/{reporte['total_casos']} casos pasaron.")
    if reporte["fallaron"]:
        print(f"⚠️ {reporte['fallaron']} caso(s) fallaron. Revisá el reporte para el detalle.")


if __name__ == "__main__":
    evaluar_harness()