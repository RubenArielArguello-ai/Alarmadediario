"""
Cámara Blink como fuente de imagen del detector.

Blink no da video en vivo: le pedimos una foto cada `intervalo_s` segundos
(60 por defecto, menos no conviene porque Blink limita las consultas) y el
detector analiza siempre la última foto que llegó. Funciona con la cámara en
cualquier WiFi: todo pasa por la nube de Blink.

Se usa desde config.json:

    "camara": { "tipo": "blink", "blink": { "nombre": "Oficina Juan", "intervalo_s": 60 } }

o desde la línea de comandos:  python server.py --blink "Oficina Juan"

La sesión de Blink se guarda en hibrido/.blink_sesion.json (no se sube a
GitHub, solo la lee tu usuario). La primera vez hay que crearla a mano:

    python hibrido/camara_blink.py --login                 # pide mail, clave y código
    python hibrido/camara_blink.py --foto "Oficina Juan"    # prueba una foto
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import threading
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

RAIZ = Path(__file__).parent
RUTA_SESION = RAIZ / ".blink_sesion.json"


class CamaraBlink:
    """Imita lo que el servidor usa de cv2.VideoCapture: read(), isOpened(), release()."""

    def __init__(self, cfg: dict, al_fallar: Callable[[str], None] | None = None):
        self.nombre = cfg.get("nombre", "")
        self.intervalo = max(60, int(cfg.get("intervalo_s", 60)))
        self.espera_max = int(cfg.get("espera_max_s", 60))
        self.fallas_para_avisar = int(cfg.get("fallas_para_avisar", 3))
        self.al_fallar = al_fallar
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._primera = threading.Event()
        self._error: str | None = None
        self._corriendo = True
        self.pausada = False   # la vigilancia está pausada: no pedir fotos
        self.fallas = 0
        self.ultima_foto: float | None = None
        if not self.nombre:
            raise RuntimeError("Falta camara.blink.nombre en config.json")
        if not RUTA_SESION.exists():
            raise RuntimeError(
                "No hay sesión de Blink. Creala con:  python hibrido/camara_blink.py --login"
            )
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()

    # ---- interfaz tipo VideoCapture
    def esperar_primera(self, timeout: float = 120) -> None:
        if not self._primera.wait(timeout):
            raise RuntimeError(f"La cámara Blink '{self.nombre}' no mandó la primera foto "
                               f"en {timeout:.0f} s. ¿Está en línea?")
        if self._frame is None:
            raise RuntimeError(self._error or "Blink no devolvió imagen.")

    def isOpened(self) -> bool:
        return self._frame is not None

    def read(self) -> tuple[bool, np.ndarray | None]:
        with self._lock:
            if self._frame is None:
                return False, None
            return True, self._frame.copy()

    def release(self) -> None:
        self._corriendo = False

    def proxima_foto(self) -> float | None:
        """Cuándo se espera la próxima foto (epoch). Las fotos salen cada
        `intervalo` s contando desde el pedido, y cada una tarda más o menos lo
        mismo en llegar: la próxima llega ~intervalo s después de la última."""
        return None if self.ultima_foto is None else self.ultima_foto + self.intervalo

    # ---- hilo con su propio event loop (blinkpy es asíncrono)
    def _correr(self) -> None:
        asyncio.run(self._bucle())

    async def _bucle(self) -> None:
        from aiohttp import ClientSession

        async with ClientSession() as session:
            try:
                blink = await conectar(session)
            except Exception as e:  # sesión vencida, sin internet…
                self._error = f"No pude entrar a Blink: {e}"
                print(f"[blink] {self._error}")
                self._primera.set()
                return
            cam = blink.cameras.get(self.nombre)
            if cam is None:
                self._error = (f"No hay ninguna cámara Blink '{self.nombre}'. "
                               f"Las que hay: {', '.join(blink.cameras)}")
                print(f"[blink] {self._error}")
                self._primera.set()
                return
            print(f"[blink] conectado a '{self.nombre}', una foto cada {self.intervalo} s")

            while self._corriendo:
                # En pausa no se le piden fotos (cada foto gasta batería de la cámara).
                if self.pausada:
                    await asyncio.sleep(1.0)
                    continue
                t0 = time.time()
                try:
                    frame = await foto_nueva(blink, cam, self.espera_max)
                    with self._lock:
                        self._frame = frame
                    self.ultima_foto = time.time()
                    print(f"[blink] foto nueva de '{self.nombre}' "
                          f"({self.ultima_foto - t0:.0f} s)")
                    if self.fallas >= self.fallas_para_avisar:
                        print(f"[blink] '{self.nombre}' volvió a responder")
                    self.fallas = 0
                except Exception as e:
                    self.fallas += 1
                    self._error = str(e)
                    print(f"[blink] falla {self.fallas}: {e}")
                    if self.fallas == self.fallas_para_avisar and self.al_fallar:
                        self.al_fallar(f"⚠️ La cámara Blink '{self.nombre}' no responde "
                                       f"({self.fallas} intentos seguidos): {e}")
                self._primera.set()
                # Espera hasta la próxima foto de a 1 s, para cortarla al pausar.
                while (self._corriendo and not self.pausada
                       and time.time() - t0 < self.intervalo):
                    await asyncio.sleep(1.0)


async def conectar(session, interactivo: bool = False):
    """Entra a Blink con la sesión guardada (o pide los datos si interactivo)."""
    from blinkpy.auth import Auth, BlinkTwoFARequiredError
    from blinkpy.blinkpy import Blink
    from blinkpy.helpers.util import json_load

    blink = Blink(session=session)
    if RUTA_SESION.exists():
        blink.auth = Auth(await json_load(str(RUTA_SESION)), no_prompt=True, session=session)
    elif interactivo:
        usuario = input("Mail de la cuenta Blink: ").strip()
        clave = getpass.getpass("Clave de Blink (no se ve al escribir): ")
        blink.auth = Auth({"username": usuario, "password": clave},
                          no_prompt=True, session=session)
    else:
        raise RuntimeError("no hay sesión guardada (correr camara_blink.py --login)")

    try:
        ok = await blink.start()
    except BlinkTwoFARequiredError:
        if not interactivo:
            raise RuntimeError("Blink pide un código nuevo: correr camara_blink.py --login")
        codigo = input("Código que mandó Blink: ").strip()
        ok = await blink.send_2fa_code(codigo)
        if ok and not blink.available:
            ok = await blink.setup_post_verify()
    if not ok or not blink.available:
        raise RuntimeError("Blink rechazó el ingreso")

    # Blink renueva el token: se guarda siempre la sesión vigente.
    await guardar_sesion(blink)
    return blink


async def guardar_sesion(blink) -> None:
    """Guarda la sesión SIN la clave: blinkpy la deja en texto plano.

    Para seguir entrando alcanzan el token y el refresh_token. Si Blink los
    invalida, el servidor avisa y hay que volver a correr --login.
    """
    import json

    await blink.save(str(RUTA_SESION))
    datos = json.loads(RUTA_SESION.read_text())
    datos.pop("password", None)
    RUTA_SESION.write_text(json.dumps(datos))
    os.chmod(RUTA_SESION, 0o600)


def listar_camaras() -> list[dict]:
    """Nombres y estado de las cámaras de la cuenta, para elegir desde la UI."""
    from aiohttp import ClientSession

    async def _listar():
        async with ClientSession() as session:
            blink = await conectar(session)
            hs = blink.homescreen or {}
            estados = {c.get("name"): c.get("status")
                       for lista in ("owls", "cameras", "doorbells")
                       for c in hs.get(lista, [])}
            return [{"nombre": n,
                     "modelo": c.attributes.get("type"),
                     "en_linea": estados.get(n, "online" if c.attributes.get("online") else None)
                     in ("online", True)}
                    for n, c in blink.cameras.items()]

    if not RUTA_SESION.exists():
        raise RuntimeError("no hay sesión de Blink (correr camara_blink.py --login)")
    return asyncio.run(_listar())


async def foto_nueva(blink, cam, espera_max: int = 60) -> np.ndarray:
    """Pide una foto y espera a que la miniatura de la nube sea la nueva."""
    from blinkpy import api

    anterior = cam.thumbnail
    t0 = time.time()
    respuesta = await cam.snap_picture()
    if isinstance(respuesta, dict) and respuesta.get("code") and not respuesta.get("id"):
        raise RuntimeError(respuesta.get("message") or f"Blink respondió {respuesta}")
    if isinstance(respuesta, dict) and respuesta.get("id"):
        await api.wait_for_command(blink, respuesta)

    while time.time() - t0 < espera_max:
        await blink.refresh(force=True)
        if cam.thumbnail and cam.thumbnail != anterior:
            break
        await asyncio.sleep(5)
    else:
        raise RuntimeError(f"en {espera_max} s no llegó una foto nueva (¿cámara offline?)")

    r = await cam.get_thumbnail()
    if not r or r.status != 200:
        raise RuntimeError("no pude bajar la foto")
    datos = np.frombuffer(await r.read(), np.uint8)
    frame = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("la foto llegó pero no se pudo decodificar")
    return frame


async def _cli(args) -> None:
    from aiohttp import ClientSession

    async with ClientSession() as session:
        blink = await conectar(session, interactivo=args.login)
        print(f"✅ Sesión de Blink guardada en {RUTA_SESION}")
        for nombre, cam in blink.cameras.items():
            print(f"  • {nombre}  ({cam.attributes.get('type')})")
        if args.foto:
            cam = blink.cameras.get(args.foto)
            if cam is None:
                raise SystemExit(f"No hay ninguna cámara '{args.foto}'")
            t0 = time.time()
            frame = await foto_nueva(blink, cam)
            ruta = RAIZ / "capturas" / f"blink_prueba_{int(t0)}.jpg"
            ruta.parent.mkdir(exist_ok=True)
            cv2.imwrite(str(ruta), frame)
            print(f"✅ Foto nueva de {frame.shape[1]}x{frame.shape[0]} en "
                  f"{time.time() - t0:.0f} s: {ruta}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sesión y prueba de la cámara Blink.")
    ap.add_argument("--login", action="store_true", help="pide mail, clave y código de Blink")
    ap.add_argument("--foto", metavar="CAMARA", help="pide una foto nueva a esa cámara")
    asyncio.run(_cli(ap.parse_args()))
