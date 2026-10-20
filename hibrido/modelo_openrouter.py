"""
Verificador en la nube a través de OpenRouter.

Igual que el motor "claude" (mismo prompt, mismo esquema de respuesta, mismas
validaciones: hereda de DetectorClaude), pero la consulta va a OpenRouter, que
con una sola clave da acceso a modelos de muchos proveedores: Claude, Gemini,
GPT, Qwen... Sirve para comparar modelos y quedarse con el más barato que
acierte.

Diferencias con el motor "claude":
  - el recorte pasa por OpenRouter además de por el proveedor del modelo;
  - no hay reintento automático en otro modelo si el modelo declina;
  - el costo de cada consulta lo informa OpenRouter en la respuesta.

Necesita OPENROUTER_API_KEY en el entorno del servidor.
"""

from __future__ import annotations

import json
import os
import time

from modelo_claude import ESQUEMA, SISTEMA, DetectorClaude

URL = "https://openrouter.ai/api/v1/chat/completions"


class DetectorOpenRouter(DetectorClaude):
    motor = "OpenRouter"

    def __init__(self, config_modelo: dict):
        super().__init__(config_modelo)
        self.modelo = config_modelo.get("modelo", "anthropic/claude-opus-5.5")
        self.clave: str | None = None

    @property
    def listo(self) -> bool:
        return self.clave is not None

    def cargar(self) -> None:
        self.clave = os.environ.get("OPENROUTER_API_KEY")
        if not self.clave:
            raise RuntimeError(
                "No hay clave de OpenRouter.\n"
                "Creá una en https://openrouter.ai/settings/keys y, en la MISMA\n"
                "Terminal donde arrancás el servidor, corré:\n"
                "    export OPENROUTER_API_KEY='...tu clave...'\n"
                "No la pegues en archivos del repo ni en el chat."
            )
        print(f"[modelo] OpenRouter ({self.modelo}) listo")
        print("[modelo] OJO: cada consulta sube el recorte de la imagen a OpenRouter "
              "y al proveedor del modelo")
        print(f"[modelo] Buscando: {self.nombre} ({', '.join(self.prompts)})")

    def _consultar(self, datos: str, w: int, h: int) -> dict | None:
        import requests

        cuerpo = {
            "model": self.modelo,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{datos}"}},
                    {"type": "text", "text": self._pregunta(w, h)},
                ]},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "veredicto", "strict": True, "schema": ESQUEMA}},
            # Solo proveedores que respeten el formato JSON pedido.
            "provider": {"require_parameters": True},
        }
        t0 = time.perf_counter()
        try:
            r = requests.post(
                URL, json=cuerpo, timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.clave}",
                         "X-Title": "Alarma de Diario"},
            )
        except requests.RequestException as e:
            raise RuntimeError(f"sin conexión con OpenRouter ({type(e).__name__})") from e

        if r.status_code != 200:
            try:
                detalle = r.json().get("error", {}).get("message", "")
            except ValueError:
                detalle = r.text[:200]
            motivo = {401: "la clave de OpenRouter es inválida",
                      402: "no hay crédito en la cuenta de OpenRouter",
                      429: "OpenRouter limitó la cantidad de pedidos"}.get(
                          r.status_code, f"OpenRouter respondió {r.status_code}")
            raise RuntimeError(f"{motivo}: {detalle}")

        data = r.json()
        u = data.get("usage") or {}
        self._sumar(float(u.get("cost") or 0.0), int(u.get("prompt_tokens") or 0),
                    int(u.get("completion_tokens") or 0))

        eleccion = (data.get("choices") or [{}])[0]
        if eleccion.get("finish_reason") == "length":
            raise RuntimeError(f"{self.modelo} no terminó la respuesta (max_tokens)")
        mensaje = eleccion.get("message") or {}
        if mensaje.get("refusal"):
            print(f"[openrouter] {self.modelo} declinó la consulta: {mensaje['refusal']}")
            return None
        texto = mensaje.get("content")
        if not texto:
            raise RuntimeError(f"{self.modelo} no devolvió el veredicto")
        texto = texto.strip()
        if texto.startswith("```"):          # por si algún modelo lo envuelve
            texto = texto.strip("`").removeprefix("json").strip()
        print(f"[openrouter] {time.perf_counter() - t0:.1f}s con {data.get('model', self.modelo)}")
        return json.loads(texto)
