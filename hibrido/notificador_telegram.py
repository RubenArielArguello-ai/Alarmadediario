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

Si en config.json se completa telegram.notificador_url, en vez de hablar
directo con Telegram se le manda el texto a la API Alarmadediario-notificador
(POST /api/notificarTelegram), y las credenciales las tiene ella.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
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
        self.timeout = cfg.get("timeout_s", 15)
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def configurado(self) -> str | None:
        """None si está todo para mandar; si no, qué falta."""
        if self.notificador_url:
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
        return f"activo, al chat {self.chat_id}"

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
        threading.Thread(
            target=self._enviar,
            args=(self.texto(objeto, veredicto), ruta_foto),
            daemon=True,
        ).start()

    def _enviar(self, texto: str, ruta_foto: str = "") -> bool:
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
