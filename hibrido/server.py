#!/usr/bin/env python3
"""
Servidor local de la Alarma de Diario (versión híbrida).

Arranca en http://localhost:8000 y:
  - captura de la cámara con OpenCV
  - corre el pipeline híbrido color + OWLv2 (detector.py)
  - sirve la UI web y transmite video + estado por WebSocket
  - registra cada alarma en capturas/detecciones.csv y, si está activo,
    dispara el webhook de n8n que ya usaba el proyecto original

Todo corre en localhost. No necesita internet una vez descargado el modelo.

Uso:
    python server.py
    python server.py --camara 1 --puerto 8080
    python server.py --modo solo_color      # sin modelo, como el proyecto viejo
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from detector import DetectorHibrido, Estado

RAIZ = Path(__file__).parent
RUTA_CONFIG = RAIZ / "config.json"

COLUMNAS_CSV = [
    "timestamp", "estado", "veredicto", "score_final",
    "color_ok", "color_delta_e", "color_papel", "color_area",
    "modelo_ok", "confianza", "captura",
]


class Aplicacion:
    def __init__(self, config: dict):
        self.cfg = config
        self.detector = DetectorHibrido(config)
        self.camara: cv2.VideoCapture | None = None
        self.ultimo_frame: np.ndarray | None = None
        self.ultimo_resultado = None
        self.clientes: set[WebSocket] = set()
        self.corriendo = False
        self.tarea_inferencia: asyncio.Task | None = None
        self.carpeta_capturas = RAIZ / config["guardado"]["carpeta"]
        self.carpeta_capturas.mkdir(exist_ok=True)

    # ------------------------------------------------------------- cámara
    def abrir_camara(self) -> None:
        idx = self.cfg["camara"]["indice"]
        cam = cv2.VideoCapture(idx)
        if not cam.isOpened():
            raise RuntimeError(
                f"No pude abrir la cámara {idx}.\n"
                "Probá otro índice con: python server.py --camara 1\n"
                "En macOS revisá Ajustes > Privacidad y seguridad > Cámara."
            )
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg["camara"]["ancho"])
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg["camara"]["alto"])
        self.camara = cam

        ok, frame = cam.read()
        if not ok:
            raise RuntimeError("La cámara abrió pero no devuelve imagen.")
        alto, ancho = frame.shape[:2]
        print(f"[camara] {ancho}x{alto} en índice {idx}")

        roi = self.cfg["roi"]
        if roi.get("activa"):
            self.detector.set_roi(roi["puntos"], alto, ancho)
            print("[roi] activa")

    # ------------------------------------------------------------ bucle
    async def bucle(self) -> None:
        self.corriendo = True
        intervalo = 1.0 / self.cfg["camara"]["fps_captura"]

        while self.corriendo:
            t0 = time.time()
            ok, frame = await asyncio.to_thread(self.camara.read)
            if not ok:
                await asyncio.sleep(0.5)
                continue

            self.ultimo_frame = frame
            try:
                resultado = await asyncio.to_thread(self.detector.procesar, frame)
            except Exception as e:
                # Una inferencia que falla no debe matar el bucle de captura.
                import traceback

                print(f"[error] fallo procesando el frame: {e}")
                traceback.print_exc()
                self.detector.confirmaciones = 0
                await asyncio.sleep(2.0)
                continue

            if self.detector.pedido_inferencia and self.tarea_inferencia is None:
                self.detector.pedido_inferencia = False
                self.detector.inferencia_activa = True
                self.detector.ultima_inferencia = time.time()
                self.tarea_inferencia = asyncio.create_task(self.inferir(frame.copy()))

            alarma_nueva = (
                resultado.estado == Estado.DIARIO
                and (self.ultimo_resultado is None
                     or self.ultimo_resultado.estado != Estado.DIARIO)
            )
            if alarma_nueva:
                ruta = self.guardar_captura(frame, resultado)
                self.registrar_csv(resultado, ruta)
                self.avisar_webhook(resultado)
                print(f"\a[ALARMA] {self.detector.nombre} detectado — "
                      f"{resultado.veredicto}")

            self.ultimo_resultado = resultado
            await self.transmitir(frame, resultado, alarma_nueva)

            demora = intervalo - (time.time() - t0)
            if demora > 0:
                await asyncio.sleep(demora)

    async def inferir(self, frame: np.ndarray) -> None:
        """Corre el modelo en un hilo aparte, sin frenar la captura de video."""
        t0 = time.time()
        try:
            conf, cajas = await asyncio.to_thread(
                self.detector.consultar_modelo, frame
            )
            self.detector.resolver_inferencia(conf, cajas)
            print(f"[inferencia] {time.time() - t0:.1f}s  conf={conf:.2f}  "
                  f"cajas={len(cajas)}")
        except Exception as e:
            import traceback

            print(f"[error] inferencia fallida: {e}")
            traceback.print_exc()
        finally:
            self.detector.inferencia_activa = False
            self.tarea_inferencia = None

    # ------------------------------------------------------------ registro
    def guardar_captura(self, frame: np.ndarray, resultado) -> str:
        if not self.cfg["guardado"]["guardar_capturas"]:
            return ""
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in self.detector.nombre)
        ruta = self.carpeta_capturas / f"{slug}_{sello}.jpg"
        cv2.imwrite(str(ruta), anotar(frame.copy(), resultado.cajas))
        print(f"[captura] guardada en {ruta}")
        return str(ruta)

    def registrar_csv(self, resultado, ruta_captura: str) -> None:
        if not self.cfg["guardado"].get("guardar_csv", True):
            return
        destino = self.carpeta_capturas / "detecciones.csv"
        nuevo = not destino.exists()
        with open(destino, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(COLUMNAS_CSV)
            w.writerow([
                datetime.now().isoformat(timespec="seconds"),
                resultado.estado.value, resultado.veredicto, resultado.score_final,
                resultado.color_ok, resultado.color_delta_e,
                resultado.color_papel, resultado.color_area,
                resultado.modelo_ok, resultado.confianza, ruta_captura,
            ])

    def avisar_webhook(self, resultado) -> None:
        cfg = self.cfg.get("webhook", {})
        if not cfg.get("activo"):
            return
        try:
            import requests

            requests.post(
                cfg["url"],
                json={
                    "estado": "Diario detectado",
                    "veredicto": resultado.veredicto,
                    "score": resultado.score_final,
                    "confianza_modelo": resultado.confianza,
                    "delta_e": resultado.color_delta_e,
                },
                timeout=5,
            )
        except Exception as e:
            print(f"[webhook] no pude avisar a n8n: {e}")

    # ------------------------------------------------------- transmisión
    async def transmitir(self, frame, resultado, alarma_nueva: bool) -> None:
        if not self.clientes:
            return

        chico = cv2.resize(frame, (640, int(640 * frame.shape[0] / frame.shape[1])))
        escala = 640 / frame.shape[1]
        ok, buf = cv2.imencode(".jpg", chico, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok:
            return

        payload = {
            "tipo": "frame",
            "imagen": base64.b64encode(buf).decode("ascii"),
            "estado": resultado.estado.value,
            "mensaje": resultado.mensaje,
            "movimiento": round(resultado.movimiento, 4),
            "diferencia_fondo": round(resultado.color_cobertura, 4),
            "color_cambio": resultado.color_cambio,
            "color_score": resultado.color_score,
            "color_delta_e": resultado.color_delta_e,
            "color_papel": resultado.color_papel,
            "color_area": resultado.color_area,
            "color_ok": resultado.color_ok,
            "confianza": round(resultado.confianza, 3),
            "modelo_ok": resultado.modelo_ok,
            "score_final": resultado.score_final,
            "veredicto": resultado.veredicto,
            "confirmaciones": resultado.confirmaciones,
            "alarma": alarma_nueva,
            "cajas": [
                {
                    "x1": c["x1"] * escala, "y1": c["y1"] * escala,
                    "x2": c["x2"] * escala, "y2": c["y2"] * escala,
                    "label": c["label"], "conf": c["conf"],
                    "origen": c.get("origen", "modelo"),
                }
                for c in resultado.cajas
            ],
        }
        mensaje = json.dumps(payload)
        muertos = set()
        for ws in self.clientes:
            try:
                await ws.send_text(mensaje)
            except Exception:
                muertos.add(ws)
        self.clientes -= muertos


def anotar(img: np.ndarray, cajas: list) -> np.ndarray:
    """Dibuja las cajas de los dos validadores: color en cian, modelo en verde."""
    for c in cajas:
        es_color = c.get("origen") == "color"
        tono = (255, 200, 0) if es_color else (0, 200, 0)
        p1 = (int(c["x1"]), int(c["y1"]))
        p2 = (int(c["x2"]), int(c["y2"]))
        cv2.rectangle(img, p1, p2, tono, 3)
        cv2.putText(
            img, f"{c['label']} {c['conf']:.2f}",
            (p1[0], max(20, p1[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, tono, 2,
        )
    return img


# ------------------------------------------------------------------ FastAPI
def crear_app(config: dict) -> tuple[FastAPI, Aplicacion]:
    estado = Aplicacion(config)
    app = FastAPI(title="Alarma de Diario — híbrido")

    def guardar_config() -> None:
        RUTA_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    @app.on_event("startup")
    async def arrancar():
        estado.detector.cargar_modelo()
        estado.abrir_camara()
        asyncio.create_task(estado.bucle())

    @app.on_event("shutdown")
    async def apagar():
        estado.corriendo = False
        if estado.camara:
            estado.camara.release()

    @app.get("/")
    async def index():
        return FileResponse(RAIZ / "static" / "index.html")

    @app.get("/api/config")
    async def get_config():
        return config

    @app.post("/api/roi")
    async def set_roi(datos: dict):
        puntos = datos.get("puntos", [])
        if estado.ultimo_frame is None:
            return {"ok": False, "error": "sin frame todavía"}
        alto, ancho = estado.ultimo_frame.shape[:2]
        estado.detector.set_roi(puntos, alto, ancho)
        config["roi"]["puntos"] = puntos
        config["roi"]["activa"] = bool(puntos)
        guardar_config()
        return {"ok": True}

    @app.post("/api/recalibrar")
    async def recalibrar():
        estado.detector.reiniciar_fondo()
        return {"ok": True}

    @app.post("/api/ajustes")
    async def ajustes(datos: dict):
        """Umbrales del modelo y del movimiento, en caliente."""
        d = estado.detector
        if "confianza_minima" in datos:
            d.conf_min = float(datos["confianza_minima"])
            config["modelo"]["confianza_minima"] = d.conf_min
        if "mostrar_debiles" in datos:
            d.owl.mostrar_debiles = bool(datos["mostrar_debiles"])
            config["modelo"]["mostrar_debiles"] = d.owl.mostrar_debiles
        if "umbral_movimiento" in datos:
            d.umbral_mov = float(datos["umbral_movimiento"])
            config["deteccion"]["umbral_movimiento"] = d.umbral_mov
        if "segundos_estabilidad" in datos:
            d.seg_estabilidad = float(datos["segundos_estabilidad"])
            config["deteccion"]["segundos_estabilidad"] = d.seg_estabilidad
        guardar_config()
        return {"ok": True}

    @app.post("/api/color")
    async def ajustes_color(datos: dict):
        """Umbrales del validador de color, en caliente."""
        c = estado.detector.color
        mapa = {
            "delta_e_minimo": ("delta_e_min", float),
            "area_minima": ("area_minima", int),
            "papel_minimo": ("papel_minimo", float),
            "ignorar_sombras": ("ignorar_sombras", bool),
        }
        for clave, (attr, tipo) in mapa.items():
            if clave in datos:
                setattr(c, attr, tipo(datos[clave]))
                config["color"][clave] = getattr(c, attr)
        guardar_config()
        return {"ok": True, "color": config["color"]}

    @app.post("/api/fusion")
    async def cambiar_fusion(datos: dict):
        """Cambia cómo se combinan los dos validadores."""
        f = estado.detector.fusion
        if "modo" in datos:
            from fusion import Modo

            try:
                f.modo = Modo(datos["modo"])
            except ValueError:
                return {"ok": False, "error": f"modo desconocido: {datos['modo']}"}
            config["fusion"]["modo"] = f.modo.value
        for clave, attr in (("peso_color", "peso_color"),
                            ("peso_modelo", "peso_modelo"),
                            ("umbral_ponderado", "umbral_ponderado")):
            if clave in datos:
                setattr(f, attr, float(datos[clave]))
                config["fusion"][clave] = getattr(f, attr)
        estado.detector.confirmaciones = 0
        guardar_config()
        print(f"[fusion] modo = {f.modo.value}")
        return {"ok": True, "fusion": config["fusion"]}

    @app.post("/api/objetivo")
    async def objetivo(datos: dict):
        """Cambia QUÉ busca el modelo, en caliente y sin reiniciar."""
        owl = estado.detector.owl
        prompts = [p.strip() for p in datos.get("prompts", []) if p.strip()]
        if prompts:
            owl.set_prompts(prompts)
            config["modelo"]["prompts"] = prompts
        if datos.get("nombre"):
            owl.nombre = datos["nombre"].strip()
            config["modelo"]["nombre_objeto"] = owl.nombre
        estado.detector.confirmaciones = 0
        estado.detector.ultima_alarma = 0.0
        guardar_config()
        print(f"[objetivo] ahora busco '{owl.nombre}': {', '.join(owl.prompts)}")
        return {"ok": True, "nombre": owl.nombre, "prompts": owl.prompts}

    @app.post("/api/resolucion")
    async def resolucion(datos: dict):
        owl = estado.detector.owl
        owl.aplicar_resolucion(int(datos.get("resolucion", 640)))
        config["modelo"]["resolucion"] = owl.resolucion
        guardar_config()
        return {"ok": True, "resolucion": owl.resolucion}

    @app.post("/api/modo")
    async def modo(datos: dict):
        """Modo prueba: analiza siempre, sin esperar movimiento."""
        d = estado.detector
        d.modo_continuo = bool(datos.get("continuo", False))
        if d.modo_continuo:
            d.ultima_inferencia = 0.0
        print(f"[modo] {'PRUEBA (continuo)' if d.modo_continuo else 'normal'}")
        return {"ok": True, "continuo": d.modo_continuo}

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        estado.clientes.add(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            estado.clientes.discard(ws)

    app.mount("/static", StaticFiles(directory=RAIZ / "static"), name="static")
    return app, estado


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--camara", type=int, help="índice de cámara (0, 1, 2…)")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--device", help="mps | cuda | cpu")
    ap.add_argument("--modo", help="cascada | and | or | ponderado | solo_color | solo_modelo")
    args = ap.parse_args()

    config = json.loads(RUTA_CONFIG.read_text())
    if args.camara is not None:
        config["camara"]["indice"] = args.camara
    if args.device:
        config["modelo"]["device"] = args.device
    if args.modo:
        config["fusion"]["modo"] = args.modo

    app, _ = crear_app(config)
    print(f"\n  Abrí  ->  http://localhost:{args.puerto}\n")
    uvicorn.run(app, host="127.0.0.1", port=args.puerto, log_level="warning")


if __name__ == "__main__":
    main()
