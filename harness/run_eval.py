import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Importamos ambas funciones
from detect_diario import detectar_objeto_nuevo, cargar_y_preparar


def evaluar_harness():
    print("🚀 Iniciando Test Harness para Alarmadediario...")

    test_dir = os.path.join("data", "test_samples")

    if not os.path.exists(test_dir):
        os.makedirs(test_dir, exist_ok=True)
        print(f"⚠️ Se creó la carpeta '{test_dir}'. Coloca imágenes de prueba allí.")
        return

    imagenes = [
        f for f in os.listdir(test_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not imagenes:
        print(
            f"⚠️ No hay imágenes en '{test_dir}'. Agrega algunas imágenes para probar."
        )
        return

    reporte = {
        "total_procesadas": len(imagenes),
        "exitosas": 0,
        "fallidas": 0,
        "detalles": [],
    }

    # Casos de prueba: fondo sin diario y escena con diario
    casos = [
        {
            "imagen": "PHOTO-sindiario.jpg",
            "esperado": False,
            "descripcion": "Escena sin diario",
        },
        {
            "imagen": "PHOTO-diario.jpg",
            "esperado": True,
            "descripcion": "Escena con diario",
        },
    ]

    reporte["total_procesadas"] = len(casos)

    # La escena sin diario se usa como fondo de referencia
    ruta_fondo = os.path.join(test_dir, "PHOTO-sindiario.jpg")
    _, fondo_gris = cargar_y_preparar(ruta_fondo)

    for caso in casos:
        img_name = caso["imagen"]
        ruta_img = os.path.join(test_dir, img_name)
        print(f"Evaluando: {img_name}...")

        try:
            img_original, actual_gris = cargar_y_preparar(ruta_img)

            resultado = detectar_objeto_nuevo(
                imagen_original=img_original,
                fondo_gris=fondo_gris,
                actual_gris=actual_gris,
            )

            detectado = resultado[0]
            esperado = caso["esperado"]
            acierto = detectado == esperado

            if acierto:
                reporte["exitosas"] += 1
            else:
                reporte["fallidas"] += 1

            reporte["detalles"].append(
                {
                    "imagen": img_name,
                    "descripcion": caso["descripcion"],
                    "esperado_detectado": esperado,
                    "detectado": detectado,
                    "acierto": acierto,
                    "estado": "OK" if acierto else "ERROR",
                    "resultado": str(resultado),
                }
            )

        except Exception as err:
            reporte["fallidas"] += 1
            reporte["detalles"].append(
                {
                    "imagen": img_name,
                    "descripcion": caso["descripcion"],
                    "esperado_detectado": caso["esperado"],
                    "estado": "ERROR",
                    "error": str(err),
                }
            )
    ruta_reporte = os.path.join("harness", "reporte_harness.json")
    with open(ruta_reporte, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Evaluación finalizada. Reporte guardado en '{ruta_reporte}'")
    print(
        f"Resultados: {reporte['exitosas']}/{reporte['total_procesadas']} pasaron la prueba."
    )


if __name__ == "__main__":
    evaluar_harness()
