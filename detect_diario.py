#!/usr/bin/env python3
"""Detección comparando dos fotos fijas (versión mejorada).

Uso rápido:
  pip install -r requirements.txt
  python detect_diario.py --fondo sin_diario.jpg --actual con_diario.jpg

El script compara una foto de referencia (fondo) con una foto actual y guarda
las imágenes de salida en la carpeta `capturas` (se crea si no existe).
"""
from __future__ import annotations

import argparse
import datetime
import csv
import logging
import os
import sys
from typing import Tuple

import cv2
import numpy as np
import requests

DEFAULT_THRESHOLD = 30
DEFAULT_MIN_AREA = 1500
DEFAULT_OUTPUT_DIR = "capturas"


def ensure_output_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def cargar_y_preparar(ruta: str) -> Tuple[np.ndarray, np.ndarray]:
    """Carga una imagen y devuelve (imagen_color, imagen_gris_blurred).

    Lanza FileNotFoundError si no existe el archivo.
    """
    imagen = cv2.imread(ruta)
    if imagen is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen: {ruta}")

    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.GaussianBlur(gris, (21, 21), 0)
    return imagen, gris


def detectar_objeto_nuevo(
    imagen_original: np.ndarray,
    fondo_gris: np.ndarray,
    actual_gris: np.ndarray,
    umbral: int = DEFAULT_THRESHOLD,
    area_minima: int = DEFAULT_MIN_AREA,
    salida_dir: str = DEFAULT_OUTPUT_DIR,
    save_crops: bool = False,
    save_csv: bool = False,
    source_image_name: str = "",
) -> Tuple[bool, str, str, list]:
    """Detecta cambios entre `fondo_gris` y `actual_gris`.

    Devuelve (detectado, ruta_binaria, ruta_marcado).
    """
    diferencia = cv2.absdiff(fondo_gris, actual_gris)
    _, binaria = cv2.threshold(diferencia, umbral, 255, cv2.THRESH_BINARY)
    binaria = cv2.dilate(binaria, None, iterations=2)

    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detectado = False
    detecciones = []  # lista de dicts con metadata
    crops_dir = os.path.join(salida_dir, "crops")
    if save_crops:
        os.makedirs(crops_dir, exist_ok=True)

    for idx, contorno in enumerate(contornos, start=1):
        area = cv2.contourArea(contorno)
        if area < area_minima:
            continue

        detectado = True
        x, y, w, h = cv2.boundingRect(contorno)
        cv2.rectangle(imagen_original, (x, y), (x + w, y + h), (0, 255, 0), 2)
        logging.info(
            "Objeto detectado - área: %.0f px, posición: (%d,%d), tamaño: %dx%d",
            area,
            x,
            y,
            w,
            h,
        )

        # guardar crop si se solicita
        crop_path = ""
        if save_crops:
            crop = imagen_original[y : y + h, x : x + w]
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            crop_name = f"diario_{ts}_{idx}.jpg"
            crop_path = os.path.join(crops_dir, crop_name)
            cv2.imwrite(crop_path, crop)

        detecciones.append({
            "area": int(area),
            "x": int(x),
            "y": int(y),
            "w": int(w),
            "h": int(h),
            "crop": crop_path,
            "source_image": source_image_name,
        })

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_binaria = os.path.join(salida_dir, f"resultado_binaria_{timestamp}.png")
    ruta_marcado = os.path.join(salida_dir, f"resultado_marcado_{timestamp}.jpg")

    cv2.imwrite(ruta_binaria, binaria)
    cv2.imwrite(ruta_marcado, imagen_original)

    # guardar CSV con metadata si se solicita
    if save_csv and detecciones:
        csv_path = os.path.join(salida_dir, "detecciones.csv")

        # Si el csv existe pero su encabezado no tiene 'source_image', lo normalizamos
        if os.path.exists(csv_path):
            with open(csv_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
            if "source_image" not in first_line:
                # Leemos todas las líneas existentes y reescribimos con la nueva cabecera
                with open(csv_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                with open(csv_path, "w", encoding="utf-8", newline="") as f:
                    f.write("timestamp,area,x,y,w,h,crop_path,source_image\n")
                    for line in lines[1:]:
                        line = line.rstrip("\n")
                        f.write(line + ",\n")

        write_header = not os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["timestamp", "area", "x", "y", "w", "h", "crop_path", "source_image"])
            ts = datetime.datetime.now().isoformat()
            for d in detecciones:
                writer.writerow([ts, d["area"], d["x"], d["y"], d["w"], d["h"], d["crop"], d.get("source_image", "")])

    return detectado, ruta_binaria, ruta_marcado, detecciones


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detección por diferencia entre dos imágenes fijas")
    p.add_argument("--fondo", required=True, help="Ruta a la foto sin el diario (fondo de referencia)")
    p.add_argument("--actual", required=True, help="Ruta a la foto con posible diario")
    p.add_argument("--umbral", type=int, default=DEFAULT_THRESHOLD, help="Umbral de diferencia (default: 30)")
    p.add_argument("--area-minima", type=int, default=DEFAULT_MIN_AREA, help="Área mínima en píxeles (default: 1500)")
    p.add_argument("--salida", default=DEFAULT_OUTPUT_DIR, help="Carpeta de salida (default: capturas)")
    p.add_argument("--verbose", action="store_true", help="Muestra logs adicionales")
    p.add_argument("--save-crops", action="store_true", help="Guarda recortes de cada detección en subcarpeta 'crops'")
    p.add_argument("--save-csv", action="store_true", help="Guarda/adjunta metadatos de detecciones en 'detecciones.csv'")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    ensure_output_dir(args.salida)

    try:
        logging.info("Cargando foto fondo: %s", args.fondo)
        _, fondo_gris = cargar_y_preparar(args.fondo)

        logging.info("Cargando foto actual: %s", args.actual)
        imagen_actual, actual_gris = cargar_y_preparar(args.actual)
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return 2

    source_name = os.path.basename(args.actual)
    detectado, ruta_binaria, ruta_marcado, _= detectar_objeto_nuevo(
        imagen_actual,
        fondo_gris,
        actual_gris,
        args.umbral,
        args.area_minima,
        args.salida,
        args.save_crops,
        args.save_csv,
        source_name
    )

    if detectado:
        logging.info("\n✅ Diario detectado.")
        logging.info("Imágenes guardadas: %s, %s", ruta_marcado, ruta_binaria)
        try:
            requests.post(
                "http://localhost:5678/webhook-test/4388a0a2-d83e-4102-ba86-34c5660e8092",
                json={"estado": "Diario detectado"}
            )
        except Exception as e:
            logging.error("Error al enviar webhook a n8n: %s", str(e))
    else:
        logging.info("\n❌ No se detectó ningún diario nuevo.")
    logging.info("Imágenes guardadas: %s, %s", ruta_marcado, ruta_binaria)
    if args.save_csv:
        logging.info("CSV guardado: %s", os.path.join(args.salida, "detecciones.csv"))
    #return 1

if __name__ == "__main__":
    raise SystemExit(main())