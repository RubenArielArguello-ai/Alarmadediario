"""
Envoltorio de Claude (API de Anthropic) como verificador del objeto.

Cuando el validador de color ve algo nuevo en la zona, se le manda a Claude el
recorte de la imagen junto con el objeto buscado, y responde con un veredicto
estructurado: si está, con qué confianza, dónde, y qué ve.

A diferencia de OWLv2 y YOLO-World:
  - entiende la descripción en español ("birome", "lápiz");
  - distingue objetos parecidos (una birome no es un lápiz);
  - necesita internet y una credencial de la API, y cada consulta cuesta;
  - las imágenes del recorte salen de la máquina hacia Anthropic.

Como el color filtra antes, solo se consulta cuando apareció algo, no en cada
frame. Expone la misma interfaz que DetectorOWL y DetectorYoloWorld.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np

# USD por millón de tokens (entrada, salida). Solo para estimar el gasto en el
# log; el valor real está en la consola de Anthropic.
PRECIOS = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SISTEMA = (
    "Sos el verificador de una alarma con cámara fija. Una etapa previa "
    "detectó que apareció algo nuevo en la zona vigilada y te pasa un recorte "
    "de la imagen. Tenés que decidir si en ese recorte está el objeto buscado. "
    "Respondé solo con el JSON pedido."
)

ESQUEMA = {
    "type": "object",
    "properties": {
        "presente": {"type": "boolean"},
        "confianza": {"type": "number"},
        "caja": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
            },
            "required": ["x1", "y1", "x2", "y2"],
            "additionalProperties": False,
        },
        "descripcion": {"type": "string"},
    },
    "required": ["presente", "confianza", "caja", "descripcion"],
    "additionalProperties": False,
}


def hay_credenciales() -> bool:
    """Lo mismo que busca el SDK: variable de entorno o perfil de `ant`."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or (Path.home() / ".config" / "anthropic").exists()
    )


class DetectorClaude:
    motor = "Claude"

    def __init__(self, config_modelo: dict):
        self.modelo = config_modelo.get("modelo", "claude-opus-5-5")
        self.esfuerzo = config_modelo.get("esfuerzo", "low")
        self.prompts = list(config_modelo["prompts"])
        self.nombre = config_modelo.get("nombre_objeto", "objeto")
        self.umbral = float(config_modelo["confianza_minima"])
        self.mostrar_debiles = bool(config_modelo.get("mostrar_debiles", False))
        self.umbral_vista = float(config_modelo.get("umbral_vista", 0.0))
        # Lado máximo del recorte que se sube, en píxeles. Más chico = menos
        # tokens y menos demora; el recorte ya viene centrado en el objeto.
        self.resolucion = int(config_modelo.get("resolucion", 768))
        self.timeout = float(config_modelo.get("timeout_s", 30))
        self.calidad_jpeg = int(config_modelo.get("calidad_jpeg", 85))
        self.device = "nube"
        self.client = None
        self.gasto_usd = 0.0
        self.consultas = 0
        self._lock = threading.Lock()   # para el contador de gasto

    # ------------------------------------------------------------------ carga
    def cargar(self) -> None:
        import anthropic

        if not hay_credenciales():
            raise RuntimeError(
                "No hay credencial de la API de Anthropic.\n"
                "Creá una clave en https://console.anthropic.com/settings/keys y,\n"
                "en la MISMA Terminal donde arrancás el servidor, corré:\n"
                "    export ANTHROPIC_API_KEY='...tu clave...'\n"
                "No la pegues en archivos del repo ni en el chat."
            )
        # Un reintento: si falla igual, el chequeo se reintenta en el próximo.
        self.client = anthropic.Anthropic(timeout=self.timeout, max_retries=1)
        print(f"[modelo] Claude ({self.modelo}, esfuerzo {self.esfuerzo}) listo")
        print("[modelo] OJO: cada consulta sube el recorte de la imagen a la API de "
              "Anthropic")
        print(f"[modelo] Buscando: {self.nombre} ({', '.join(self.prompts)})")

    def aplicar_resolucion(self, res: int) -> None:
        self.resolucion = max(256, min(1568, int(res)))
        print(f"[modelo] Claude: el recorte se sube con lado máximo {self.resolucion} px")

    def set_prompts(self, prompts: list[str]) -> None:
        self.prompts = list(prompts)

    # ------------------------------------------------------------- inferencia
    def _preparar(self, frame_bgr: np.ndarray) -> tuple[str, float, int, int]:
        """Achica el recorte si hace falta y lo codifica en JPEG base64."""
        alto, ancho = frame_bgr.shape[:2]
        escala = min(1.0, self.resolucion / max(alto, ancho))
        img = frame_bgr
        if escala < 1.0:
            img = cv2.resize(frame_bgr, (round(ancho * escala), round(alto * escala)),
                             interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, self.calidad_jpeg])
        if not ok:
            raise RuntimeError("no pude codificar el recorte en JPEG")
        h, w = img.shape[:2]
        return base64.standard_b64encode(buf.tobytes()).decode("ascii"), escala, w, h

    def _pregunta(self, w: int, h: int) -> str:
        return (
            f"Objeto buscado: {self.nombre}.\n"
            f"Descripciones: {'; '.join(self.prompts)}.\n"
            f"La imagen mide {w}x{h} píxeles.\n\n"
            "- presente: true solo si el objeto buscado está en la imagen. Un "
            "objeto parecido pero distinto (por ejemplo, una birome cuando se "
            "busca un lápiz) es false.\n"
            "- confianza: probabilidad de 0 a 1 de que el objeto buscado esté.\n"
            "- caja: el rectángulo del objeto en píxeles de esta imagen (x1, y1 "
            "arriba a la izquierda). Si no está, todo en 0.\n"
            "- descripcion: qué ves, en pocas palabras y en español."
        )

    def detectar(self, frame_bgr: np.ndarray) -> tuple[float, list[dict]]:
        """Recibe un recorte BGR. Devuelve (confianza, [caja]) como los otros
        motores. Un error de red o de la API se propaga: el server lo registra
        y el chequeo se reintenta, en vez de tomarlo como "no está"."""
        if self.client is None:
            return 0.0, []
        import anthropic

        datos, escala, w, h = self._preparar(frame_bgr)
        params = dict(
            model=self.modelo,
            max_tokens=4096,
            system=SISTEMA,
            output_config={"effort": self.esfuerzo,
                           "format": {"type": "json_schema", "schema": ESQUEMA}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": datos}},
                {"type": "text", "text": self._pregunta(w, h)},
            ]}],
        )
        # Si el modelo declina la consulta, la API la reintenta en otro modelo
        # en el mismo pedido. Haiku no tiene ese respaldo.
        if not self.modelo.startswith("claude-haiku"):
            params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")

        t0 = time.perf_counter()
        try:
            r = self.client.beta.messages.create(**params)
        except anthropic.AuthenticationError as e:
            raise RuntimeError("la clave de la API de Anthropic es inválida o "
                               "fue revocada") from e
        except anthropic.APIConnectionError as e:
            raise RuntimeError("sin conexión con la API de Anthropic") from e
        demora = time.perf_counter() - t0
        self._registrar(r, demora)

        if r.stop_reason == "refusal":
            print(f"[claude] la consulta fue declinada ({getattr(r.stop_details, 'category', None)})")
            return 0.0, []
        if r.stop_reason == "max_tokens":
            raise RuntimeError("Claude no terminó la respuesta (max_tokens)")

        texto = next((b.text for b in r.content if b.type == "text"), None)
        if texto is None:
            raise RuntimeError("Claude no devolvió el veredicto")
        v = json.loads(texto)

        conf = float(np.clip(v["confianza"], 0.0, 1.0))
        print(f"[claude] {demora:.1f}s  presente={v['presente']}  conf={conf:.2f}  "
              f"«{v['descripcion']}»")
        if not v["presente"] and not self.mostrar_debiles:
            return conf, []

        # Caja en píxeles de la imagen que se subió -> del recorte original.
        c = v["caja"]
        x1, y1, x2, y2 = (float(c[k]) / escala for k in ("x1", "y1", "x2", "y2"))
        alto, ancho = frame_bgr.shape[:2]
        x1, x2 = sorted((np.clip(x1, 0, ancho), np.clip(x2, 0, ancho)))
        y1, y2 = sorted((np.clip(y1, 0, alto), np.clip(y2, 0, alto)))
        if x2 - x1 < 4 or y2 - y1 < 4:
            # Sin caja usable: el recorte entero, que ya está centrado en lo nuevo.
            x1, y1, x2, y2 = 0.0, 0.0, float(ancho), float(alto)

        return conf, [{
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "label": f"{self.nombre}: {v['descripcion']}"[:60],
            "conf": conf,
            "origen": "modelo",
        }]

    def _registrar(self, r, demora: float) -> None:
        u = r.usage
        entrada, salida = PRECIOS.get(self.modelo, (0.0, 0.0))
        costo = (u.input_tokens * entrada + u.output_tokens * salida) / 1e6
        with self._lock:
            self.consultas += 1
            self.gasto_usd += costo
            total, n = self.gasto_usd, self.consultas
        print(f"[claude] {u.input_tokens} tok entrada, {u.output_tokens} tok salida, "
              f"~US$ {costo:.4f} (acumulado ~US$ {total:.3f} en {n} consultas)")
