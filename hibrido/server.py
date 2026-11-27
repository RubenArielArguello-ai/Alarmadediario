#!/usr/bin/env python3
"""
Servidor local de la Alarma de Diario (versión híbrida).

Arranca en http://localhost:8000 y:
  - captura de la cámara con OpenCV
  - corre el pipeline híbrido: color + modelo (YOLO-World u OWLv2), en detector.py
  - sirve la UI web y transmite video + estado por WebSocket
  - registra cada alarma en capturas/detecciones.csv y, si está activo,
    dispara el webhook de n8n que ya usaba el proyecto original
  - si está activo, manda la foto de la alarma por Telegram (notificador_telegram.py):
    vía el workflow de n8n y, si n8n falla, directo con el bot
  - la imagen sale de una webcam (OpenCV) o de una cámara Blink (camara_blink.py),
    que saca una foto cada 60 s desde cualquier WiFi

Todo corre en localhost. No necesita internet una vez descargado el modelo.

Uso:
    python server.py
    python server.py --camara 1 --puerto 8080
    python server.py --blink                  # la Blink de config.json en vez de la webcam
    python server.py --modo solo_color      # sin modelo, como el proyecto viejo
    python server.py --modo-prueba          # servidor web sin modelo ni cámara
    python server.py --motor claude         # verifica con Claude (necesita ANTHROPIC_API_KEY)
    python server.py --motor openrouter     # verifica vía OpenRouter (necesita OPENROUTER_API_KEY)
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
from camara_blink import RUTA_SESION as RUTA_SESION_BLINK
from camara_blink import CamaraBlink
from notificador_telegram import NotificadorTelegram

RAIZ = Path(__file__).parent
RUTA_CONFIG = RAIZ / "config.json"

COLUMNAS_CSV = [
    "timestamp", "estado", "veredicto", "score_final",
    "color_ok", "color_delta_e", "color_papel", "color_area",
    "modelo_ok", "confianza", "captura",
]


class Aplicacion:
    def __init__(self, config: dict, crear_carpeta_capturas: bool = True):
        self.cfg = config
        self.detector = DetectorHibrido(config)
        self.telegram = NotificadorTelegram(config)
        self.camara: cv2.VideoCapture | None = None
        self.ultimo_frame: np.ndarray | None = None
        self.ultimo_resultado = None
        self.clientes: set[WebSocket] = set()
        self.corriendo = False
        self.tarea_inferencia: asyncio.Task | None = None
        self._foto_vista: float | None = None   # última foto de la Blink ya chequeada
        self.pausado = False   # vigilancia pausada desde la UI: no analiza ni avisa
        self.carpeta_capturas = RAIZ / config["guardado"]["carpeta"]
        if crear_carpeta_capturas:
            self.carpeta_capturas.mkdir(exist_ok=True)

    # ------------------------------------------------------------- cámara
    async def iniciar_camara(self, reintento_s: float = 300) -> None:
        """Abre la cámara y arranca la vigilancia. Si la cámara no responde
        (Blink desconectada, sin internet), la web sigue andando y se reintenta
        cada `reintento_s`: sin esto el servidor se caía y Docker lo reiniciaba
        en loop, entrando a la cuenta de Blink una y otra vez."""
        avisado = False
        while True:
            try:
                await asyncio.to_thread(self.abrir_camara)
                break
            except Exception as e:
                print(f"[camara] no pude abrirla: {e}. Reintento en {reintento_s:.0f} s")
                if not avisado:
                    self.telegram.avisar_texto(
                        f"⚠️ La alarma no puede usar la cámara: {e}. "
                        f"Reintenta cada {reintento_s / 60:.0f} min.")
                    avisado = True
                await asyncio.sleep(reintento_s)
        if avisado:
            self.telegram.avisar_texto("✅ La cámara volvió a responder: la alarma está vigilando.")
        await self.bucle()

    def abrir_camara(self) -> None:
        self.camara, frame = self.abrir_fuente(self.cfg["camara"])
        alto, ancho = frame.shape[:2]
        self.activar_roi(alto, ancho)
        self.resolucion_de_camara()
        self.detector.usar_chequeo_por_foto(self.cfg["camara"].get("tipo") == "blink")

    def seccion_motor(self) -> dict:
        m = self.cfg["modelo"]
        return m.setdefault(m["motor"], {}) if m.get("motor") else m

    def resolucion_de_camara(self) -> int | None:
        """Pone la resolución del modelo que corresponde al tipo de cámara.

        La webcam manda video y el modelo corre seguido: conviene rápido (320).
        La Blink manda una foto por minuto, más lejana: sobra tiempo y el
        objeto queda chico, así que conviene 640. Se toma de
        <motor>.resolucion_por_camara; si el motor no la tiene, no se toca.
        """
        motor = self.detector.motor
        por_camara = self.seccion_motor().get("resolucion_por_camara")
        if not por_camara or not hasattr(motor, "aplicar_resolucion"):
            return None
        tipo = self.cfg["camara"].get("tipo", "local")
        res = por_camara.get(tipo)
        if res and int(res) != motor.resolucion:
            print(f"[modelo] cámara {tipo}: paso a resolución {res}")
            motor.aplicar_resolucion(int(res))
        self.seccion_motor()["resolucion"] = motor.resolucion
        return motor.resolucion

    def abrir_fuente(self, cam_cfg: dict):
        """Abre la webcam o la Blink que diga cam_cfg. Devuelve (cámara, primer frame)."""
        if cam_cfg.get("tipo") == "blink":
            cam = CamaraBlink(cam_cfg.get("blink", {}), al_fallar=self.telegram.avisar_texto)
            print(f"[camara] esperando la primera foto de la Blink '{cam.nombre}'…")
            try:
                cam.esperar_primera(timeout=cam.espera_max + 60)
            except Exception:
                cam.release()
                raise
            _, frame = cam.read()
            alto, ancho = frame.shape[:2]
            print(f"[camara] Blink '{cam.nombre}' {ancho}x{alto}, "
                  f"una foto cada {cam.intervalo} s")
            return cam, frame

        idx = cam_cfg["indice"]
        cam = cv2.VideoCapture(idx)
        if not cam.isOpened():
            raise RuntimeError(
                f"No pude abrir la cámara {idx}.\n"
                "Probá otro índice con: python server.py --camara 1\n"
                "En macOS revisá Ajustes > Privacidad y seguridad > Cámara."
            )
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg["ancho"])
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg["alto"])
        ok, frame = cam.read()
        if not ok:
            cam.release()
            raise RuntimeError("La cámara abrió pero no devuelve imagen.")
        alto, ancho = frame.shape[:2]
        print(f"[camara] {ancho}x{alto} en índice {idx}")
        return cam, frame

    @staticmethod
    def clave_camara(cam_cfg: dict) -> str:
        if cam_cfg.get("tipo") == "blink":
            return "blink:" + cam_cfg.get("blink", {}).get("nombre", "")
        return f"local:{cam_cfg.get('indice', 0)}"

    @staticmethod
    def texto_camara(c: dict) -> str:
        if c.get("tipo") == "blink":
            b = c.get("blink", {})
            return (f"Blink «{b.get('nombre', '')}» · una foto cada "
                    f"{max(60, int(b.get('intervalo_s', 60)))} s")
        return f"Cámara de la notebook (índice {c.get('indice', 0)})"

    def describir_camara(self) -> dict:
        c = self.cfg["camara"]
        # Las dos únicas opciones: la webcam de la notebook y LA Blink de config.json.
        opciones = {"local": "Cámara de la notebook",
                    "blink": f"Blink «{c.get('blink', {}).get('nombre', '')}»"}
        if c.get("tipo") == "blink":
            return {"tipo": "blink", "nombre": c.get("blink", {}).get("nombre", ""),
                    "texto": self.texto_camara(c), "opciones": opciones}
        return {"tipo": "local", "indice": c.get("indice", 0),
                "texto": self.texto_camara(c), "opciones": opciones}

    async def cambiar_camara(self, tipo: str) -> dict:
        """Cambia en caliente entre la webcam y la Blink de config.json.

        No se elige otra Blink de la cuenta ni otro índice: el nombre y el
        índice son los de config.json. Si la nueva no abre, sigue la anterior.
        """
        import copy

        nuevo = copy.deepcopy(self.cfg["camara"])
        nuevo["tipo"] = tipo
        clave_vieja, clave_nueva = self.clave_camara(self.cfg["camara"]), self.clave_camara(nuevo)
        if clave_vieja == clave_nueva and self.camara is not None:
            return {"ok": True, "camara": self.describir_camara(), "roi": self.cfg["roi"]}

        try:
            cam, frame = await asyncio.to_thread(self.abrir_fuente, nuevo)
        except Exception as e:
            return {"ok": False, "error": str(e)}

        # Cada cámara ve otra imagen: guarda la zona de la vieja y trae la de la nueva.
        zonas = self.cfg.setdefault("roi_por_camara", {})
        zonas[clave_vieja] = dict(self.cfg["roi"])
        vieja, self.camara = self.camara, cam
        self.cfg["camara"] = nuevo
        if vieja is not None:
            vieja.release()
        self.cfg["roi"] = dict(zonas.get(clave_nueva, {"activa": False, "puntos": []}))
        alto, ancho = frame.shape[:2]
        roi = self.cfg["roi"]
        self.detector.set_roi(roi["puntos"] if roi.get("activa") else [], alto, ancho)
        self.detector.reiniciar_fondo()
        self.detector.usar_chequeo_por_foto(tipo == "blink")
        self._foto_vista = None
        if hasattr(cam, "pausada"):
            cam.pausada = self.pausado
        self.ultimo_frame = frame
        print(f"[camara] cambio a {self.describir_camara()['texto']}")
        res = self.resolucion_de_camara()
        return {"ok": True, "camara": self.describir_camara(), "roi": self.cfg["roi"],
                "resolucion": res}

    def activar_roi(self, alto: int, ancho: int) -> None:
        roi = self.cfg["roi"]
        if roi.get("activa"):
            self.detector.set_roi(roi["puntos"], alto, ancho)
            print("[roi] activa")

    def pausar(self, pausa: bool) -> None:
        """Pausa o reanuda la vigilancia. En pausa no se analiza ni se avisa,
        y a la Blink no se le piden fotos."""
        self.pausado = bool(pausa)
        if hasattr(self.camara, "pausada"):
            self.camara.pausada = self.pausado
        if not self.pausado:
            # Mientras estuvo en pausa pudo cambiar todo: se mira enseguida.
            self.detector.chequear_ya()
        print(f"[vigilancia] {'PAUSADA' if self.pausado else 'reanudada'}")

    # ------------------------------------------------------------ bucle
    async def bucle(self) -> None:
        self.corriendo = True

        while self.corriendo:
            if self.pausado:
                await asyncio.sleep(0.5)
                continue
            t0 = time.time()
            # Se recalcula en cada vuelta: la cámara se puede cambiar desde la UI.
            intervalo = 1.0 / self.cfg["camara"]["fps_captura"]
            if self.cfg["camara"].get("tipo") == "blink":
                intervalo = 1.0  # la imagen cambia una vez por minuto: no hace falta más
            ok, frame = await asyncio.to_thread(self.camara.read)
            if not ok:
                await asyncio.sleep(0.5)
                continue

            self.ultimo_frame = frame
            # Blink: el chequeo va al ritmo de las fotos (ver detector.foto_nueva).
            llegada = getattr(self.camara, "ultima_foto", None)
            if llegada is not None and llegada != self._foto_vista:
                self._foto_vista = llegada
                self.detector.foto_nueva(self.camara.proxima_foto())
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
                self.telegram.avisar(self.detector.nombre, resultado.veredicto, ruta)
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
            "proximo_chequeo": resultado.proximo_chequeo,
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
def crear_app(config: dict, modo_prueba: bool = False) -> tuple[FastAPI, Aplicacion]:
    estado = Aplicacion(config, crear_carpeta_capturas=not modo_prueba)
    app = FastAPI(title="Alarma de Diario — híbrido")

    def guardar_config() -> None:
        RUTA_CONFIG.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    def seccion_motor() -> dict:
        """Dónde se guardan umbral y resolución: cada motor tiene los suyos."""
        m = config["modelo"]
        return m.setdefault(m["motor"], {}) if m.get("motor") else m

    @app.on_event("startup")
    async def arrancar():
        if modo_prueba:
            print("[prueba] modo de prueba: no cargo modelos ni abro la cámara")
            return
        estado.detector.cargar_modelo()
        asyncio.create_task(estado.iniciar_camara())

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

    @app.get("/api/vigilancia")
    async def get_vigilancia():
        return {"activa": not estado.pausado}

    @app.post("/api/vigilancia")
    async def set_vigilancia(datos: dict):
        """{"activa": false} pausa la vigilancia; {"activa": true} la reanuda."""
        estado.pausar(not bool(datos.get("activa", True)))
        return {"ok": True, "activa": not estado.pausado}

    @app.get("/api/telegram")
    async def get_telegram():
        return estado.telegram.estado()

    @app.post("/api/telegram")
    async def set_telegram(datos: dict):
        """{"activo": true/false} prende o apaga el aviso por Telegram."""
        activo = bool(datos.get("activo"))
        estado.telegram.activo = activo
        config.setdefault("telegram", {})["activo"] = activo
        guardar_config()
        print(f"[telegram] {estado.telegram.describir()}")
        return estado.telegram.estado()

    @app.post("/api/telegram/prueba")
    async def probar_telegram():
        """Manda un mensaje de prueba (sin foto) y dice si llegó."""
        n = estado.telegram
        falta = n.configurado()
        if falta:
            return {"ok": False, "error": falta}
        ok = await asyncio.to_thread(
            n._enviar, n.texto(estado.detector.nombre, "Mensaje de prueba de la Alarma de Diario"))
        return {"ok": ok, "error": None if ok else "no llegó: mirá la terminal del servidor"}

    @app.get("/api/camara")
    async def get_camara():
        """La cámara actual y las dos opciones (webcam o la Blink de config.json)."""
        return {"actual": estado.describir_camara(),
                "blink_configurada": RUTA_SESION_BLINK.exists()}

    @app.post("/api/camara")
    async def set_camara(datos: dict):
        tipo = datos.get("tipo", "local")
        if tipo not in ("local", "blink"):
            return {"ok": False, "error": "tipo tiene que ser local o blink"}
        r = await estado.cambiar_camara(tipo)
        if r["ok"]:
            guardar_config()
        return r

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
            seccion_motor()["confianza_minima"] = d.conf_min
        if "mostrar_debiles" in datos:
            d.motor.mostrar_debiles = bool(datos["mostrar_debiles"])
            config["modelo"]["mostrar_debiles"] = d.motor.mostrar_debiles
        if "umbral_movimiento" in datos:
            d.umbral_mov = float(datos["umbral_movimiento"])
            config["deteccion"]["umbral_movimiento"] = d.umbral_mov
        if "segundos_estabilidad" in datos:
            d.seg_estabilidad = float(datos["segundos_estabilidad"])
            config["deteccion"]["segundos_estabilidad"] = d.seg_estabilidad
        if "intervalo_chequeo" in datos:
            d.intervalo_chequeo = max(0.0, float(datos["intervalo_chequeo"]))
            d.chequear_ya()
            config["deteccion"]["intervalo_chequeo"] = d.intervalo_chequeo
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
            "exigir_papel": ("exigir_papel", bool),
            "sombra_luz_min": ("sombra_luz_min", float),
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
        motor = estado.detector.motor
        prompts = [p.strip() for p in datos.get("prompts", []) if p.strip()]
        if prompts:
            # Con YOLO-World tarda ~1 s (CLIP codifica los textos): en un
            # hilo, para no congelar el video ni la página mientras tanto.
            await asyncio.to_thread(motor.set_prompts, prompts)
            config["modelo"]["prompts"] = prompts
        if datos.get("nombre"):
            motor.nombre = datos["nombre"].strip()
            config["modelo"]["nombre_objeto"] = motor.nombre
        # El veredicto anterior era sobre OTRO objeto: no vale más.
        estado.detector.chequear_ya(olvidar_veredicto=True)
        guardar_config()
        print(f"[objetivo] ahora busco '{motor.nombre}': {', '.join(motor.prompts)}")
        return {"ok": True, "nombre": motor.nombre, "prompts": motor.prompts}

    @app.post("/api/resolucion")
    async def resolucion(datos: dict):
        motor = estado.detector.motor
        motor.aplicar_resolucion(int(datos.get("resolucion", 640)))
        seccion_motor()["resolucion"] = motor.resolucion
        # Elegida a mano, queda como la de este tipo de cámara.
        por_camara = seccion_motor().get("resolucion_por_camara")
        if por_camara is not None:
            por_camara[config["camara"].get("tipo", "local")] = motor.resolucion
        guardar_config()
        return {"ok": True, "resolucion": motor.resolucion}

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
    ap.add_argument("--blink", nargs="?", const="", metavar="NOMBRE",
                    help="usar la cámara Blink de config.json (camara.blink.nombre). "
                         "Si se da un nombre, tiene que ser ese: no se usa otra Blink.")
    ap.add_argument("--puerto", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1",
                    help="interfaz de escucha (default: 127.0.0.1)")
    ap.add_argument("--device", help="mps | cuda | cpu")
    ap.add_argument("--modo", help="cascada | and | or | ponderado | solo_color | solo_modelo")
    ap.add_argument("--modo-prueba", action="store_true",
                    help="sirve FastAPI sin cargar modelos, abrir la cámara ni capturar")
    ap.add_argument("--motor", choices=("owlv2", "yolo_world", "claude", "openrouter"),
                    help="qué modelo reconoce el objeto (default: el de config.json)")
    args = ap.parse_args()

    config = json.loads(RUTA_CONFIG.read_text())
    if args.camara is not None:
        config["camara"]["indice"] = args.camara
        config["camara"]["tipo"] = "local"
    if args.blink is not None:
        permitida = config["camara"].get("blink", {}).get("nombre", "")
        if args.blink.strip() and args.blink.strip() != permitida:
            raise SystemExit(f"La única cámara Blink habilitada es «{permitida}» "
                             "(camara.blink.nombre en config.json).")
        config["camara"]["tipo"] = "blink"
    if args.device:
        config["modelo"]["device"] = args.device
    if args.modo:
        config["fusion"]["modo"] = args.modo
    if args.motor:
        config["modelo"]["motor"] = args.motor

    app, _ = crear_app(config, modo_prueba=args.modo_prueba)
    print(f"\n  Abrí  ->  http://localhost:{args.puerto}\n")
    print(f"[telegram] {NotificadorTelegram(config).describir()}")
    uvicorn.run(app, host=args.host, port=args.puerto, log_level="warning")


if __name__ == "__main__":
    main()
