"""
Aviso por Telegram cuando suena la alarma.

Manda la foto anotada de la alarma (o solo el texto) a un chat de Telegram,
usando un bot. Las credenciales NO van en config.json: se leen de las
variables de entorno o de hibrido/.env, que no se sube a GitHub.

    TELEGRAM_BOT_TOKEN=123456789:ABC...   (lo da @BotFather al crear el bot)
    TELEGRAM_CHAT_ID=-1001234567890       (el chat o grupo que recibe el aviso)

Probar la conexión sin esperar una alarma:

    python hibrido/notificador_telegram.py --chats    # lista los chats del bot
    python hibrido/notificador_telegram.py --prueba   # manda un mensaje de prueba

Camino principal: n8n. Si hay una dirección de n8n (N8N_WEBHOOK_URL en
hibrido/.env, nunca en config.json) se le manda al workflow
"Webhook a Telegram - enviar-telegram" {"mensaje": ..., "imagen": <foto en
base64>} y n8n la reenvía al grupo. Si n8n no contesta o contesta error, el
aviso sale directo por Telegram con el bot de hibrido/.env (respaldo).

Si en config.json se completa telegram.notificador_url, en vez de hablar
directo con Telegram se le manda el texto a la API Alarmadediario-notificador
(POST /api/notificarTelegram), y las credenciales las tiene ella.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).parent
RUTA_ENV = RAIZ / ".env"
API = "https://api.telegram.org/bot{token}/{metodo}"


def cargar_env(ruta: Path = RUTA_ENV) -> None:
    """Lee CLAVE=valor de hibrido/.env sin pisar lo que ya está en el entorno."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip("'\""))


class NotificadorTelegram:
    def __init__(self, config: dict):
        cargar_env()
        cfg = config.get("telegram", {})
        self.activo = bool(cfg.get("activo"))
        self.enviar_foto = cfg.get("enviar_foto", True)
        self.mensaje = cfg.get("mensaje", "🚨 {objeto} detectado — {hora}")
        self.notificador_url = (cfg.get("notificador_url") or "").strip()
        # Solo de hibrido/.env: config.json se sube a GitHub y la UI lo lee entero.
        self.n8n_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
        self.timeout = cfg.get("timeout_s", 15)
        # Si el objeto aparece y desaparece seguido, no llenar el grupo de avisos.
        self.espera = float(cfg.get("espera_entre_avisos_s", 60))
        self._ultimo_aviso = 0.0
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def configurado(self) -> str | None:
        """None si está todo para mandar; si no, qué falta."""
        if self.notificador_url or self.n8n_url:
            return None
        if not self.token:
            return "falta TELEGRAM_BOT_TOKEN en hibrido/.env"
        if not self.chat_id:
            return "falta TELEGRAM_CHAT_ID en hibrido/.env"
        return None

    def describir(self) -> str:
        if not self.activo:
            return "desactivado (telegram.activo en config.json)"
        falta = self.configurado()
        if falta:
            return f"activo pero {falta}"
        if self.notificador_url:
            return f"activo, vía {self.notificador_url}"
        directo = f"directo al chat {self.chat_id}" if self.token and self.chat_id else ""
        if self.n8n_url:
            respaldo = f"; si falla, {directo}" if directo else "; sin respaldo directo"
            return f"activo, vía n8n{respaldo}"
        return f"activo, {directo}"

    def estado(self) -> dict:
        """Para la página: sin token ni chat, solo si está listo y por dónde sale."""
        falta = self.configurado()
        if self.notificador_url:
            via = "la API notificador"
        elif self.n8n_url:
            via = "n8n (con respaldo directo)" if self.token and self.chat_id else "n8n"
        else:
            via = "directo con el bot"
        return {"activo": self.activo, "falta": falta, "via": via,
                "espera_s": self.espera}

    def texto(self, objeto: str, veredicto: str = "") -> str:
        hora = datetime.now().strftime("%d/%m %H:%M:%S")
        base = self.mensaje.format(objeto=objeto, hora=hora)
        return f"{base}\n{veredicto}" if veredicto else base

    def avisar(self, objeto: str, veredicto: str, ruta_foto: str = "") -> None:
        """Manda el aviso en un hilo aparte: si Telegram tarda, el video no se frena."""
        if not self.activo:
            return
        falta = self.configurado()
        if falta:
            print(f"[telegram] no mando el aviso: {falta}")
            return
        ahora = time.time()
        if ahora - self._ultimo_aviso < self.espera:
            print(f"[telegram] no repito el aviso: el anterior salió hace "
                  f"{ahora - self._ultimo_aviso:.0f} s (espera_entre_avisos_s={self.espera:.0f})")
            return
        self._ultimo_aviso = ahora
        threading.Thread(
            target=self._enviar,
            args=(self.texto(objeto, veredicto), ruta_foto),
            daemon=True,
        ).start()

    def avisar_texto(self, texto: str) -> None:
        """Aviso suelto (por ejemplo, que la cámara Blink dejó de responder)."""
        if self.activo and not self.configurado():
            threading.Thread(target=self._enviar, args=(texto,), daemon=True).start()

    def _enviar(self, texto: str, ruta_foto: str = "") -> bool:
        if self.n8n_url and not self.notificador_url:
            if self._enviar_n8n(texto, ruta_foto):
                return True
            if not (self.token and self.chat_id):
                return False
            print("[telegram] uso el respaldo: directo a Telegram")
        return self._enviar_directo(texto, ruta_foto)

    def _enviar_n8n(self, texto: str, ruta_foto: str = "") -> bool:
        """Workflow n8n: exige "mensaje"; "imagen" en base64 es opcional."""
        cuerpo = {"mensaje": html.escape(texto, quote=False)}  # n8n lo manda como HTML
        if self.enviar_foto and ruta_foto and Path(ruta_foto).exists():
            cuerpo["imagen"] = base64.b64encode(Path(ruta_foto).read_bytes()).decode("ascii")
        try:
            r = requests.post(self.n8n_url, json=cuerpo, timeout=self.timeout)
            if r.ok:
                print("[telegram] aviso enviado vía n8n")
                return True
            print(f"[telegram] n8n respondió {r.status_code}: {_detalle(r)}")
        except Exception as e:
            print(f"[telegram] n8n no contesta: {e}")
        return False

    def _enviar_directo(self, texto: str, ruta_foto: str = "") -> bool:
        try:
            if self.notificador_url:
                r = requests.post(self.notificador_url, json={"texto": texto},
                                  timeout=self.timeout)
            elif self.enviar_foto and ruta_foto and Path(ruta_foto).exists():
                with open(ruta_foto, "rb") as foto:
                    r = requests.post(
                        API.format(token=self.token, metodo="sendPhoto"),
                        data={"chat_id": self.chat_id, "caption": texto},
                        files={"photo": foto},
                        timeout=self.timeout,
                    )
            else:
                r = requests.post(
                    API.format(token=self.token, metodo="sendMessage"),
                    data={"chat_id": self.chat_id, "text": texto},
                    timeout=self.timeout,
                )
            if r.ok:
                print("[telegram] aviso enviado")
                return True
            print(f"[telegram] Telegram respondió {r.status_code}: {_detalle(r)}")
        except Exception as e:
            print(f"[telegram] no pude mandar el aviso: {e}")
        return False


def _detalle(r: requests.Response) -> str:
    try:
        return r.json().get("description") or r.json().get("mensaje") or r.text[:200]
    except ValueError:
        return r.text[:200]


def listar_chats(token: str) -> None:
    """Muestra los chats que le escribieron al bot, para sacar el TELEGRAM_CHAT_ID."""
    r = requests.get(API.format(token=token, metodo="getUpdates"), timeout=15)
    if not r.ok:
        print(f"Telegram respondió {r.status_code}: {_detalle(r)}")
        return
    chats = {}
    for u in r.json().get("result", []):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat")
        if chat:
            nombre = chat.get("title") or chat.get("first_name") or chat.get("username")
            chats[chat["id"]] = f"{nombre} ({chat.get('type')})"
    if not chats:
        print("El bot no tiene mensajes. Escribile algo (o agregalo al grupo y "
              "escribí en el grupo) y volvé a correr esto.")
        return
    print("Chats del bot (copiá el número a TELEGRAM_CHAT_ID):")
    for chat_id, nombre in chats.items():
        print(f"  {chat_id}   {nombre}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Prueba el aviso por Telegram.")
    ap.add_argument("--chats", action="store_true",
                    help="lista los chats del bot para sacar el TELEGRAM_CHAT_ID")
    ap.add_argument("--prueba", action="store_true", help="manda un mensaje de prueba")
    args = ap.parse_args()

    config = json.loads((RAIZ / "config.json").read_text())
    n = NotificadorTelegram(config)
    if args.chats:
        if not n.token:
            print("Falta TELEGRAM_BOT_TOKEN en hibrido/.env")
            return
        listar_chats(n.token)
    elif args.prueba:
        falta = n.configurado()
        if falta:
            print(f"No puedo probar: {falta}")
            return
        nombre = config.get("modelo", {}).get("nombre_objeto", "objeto")
        ok = n._enviar(n.texto(nombre, "Mensaje de prueba de la Alarma de Diario"))
        print("Listo, revisá Telegram." if ok else "No llegó: mirá el error de arriba.")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
