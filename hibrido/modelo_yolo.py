"""
Envoltorio de YOLO-World (detector de vocabulario abierto, de Ultralytics).

Igual que OWLv2, acepta descripciones en texto ("pencil") y devuelve cajas sin
entrenar nada, pero es mucho más liviano. Medido en una Mac Intel i7 de 2
núcleos, sobre el recorte que le pasa el validador de color:

    YOLO-World S @ 640  ~0.6 s por consulta    OWLv2 @ 640  ~9.4 s

A cambio sus puntajes son mucho más bajos: el diario real dio 0.12 y la alfombra
vacía 0.00, contra 0.95 y 0.00 de OWLv2. Por eso usa su propio umbral (0.05),
que no se puede comparar con el de OWLv2.

Expone la misma interfaz que DetectorOWL (cargar, detectar, set_prompts,
aplicar_resolucion, umbral, nombre...), así el detector no nota la diferencia.

La primera vez baja los pesos (~26 MB) y el codificador de texto CLIP
(~350 MB) a modelos_yolo/. Después funciona sin internet.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from modelo import elegir_device

RAIZ = Path(__file__).parent
ARTICULOS = ("a ", "an ", "the ")


def a_clase(prompt: str) -> str:
    """'a rolled newspaper' -> 'rolled newspaper'.

    YOLO-World se entrenó con nombres de clase, no con frases; el artículo
    del principio no aporta y los presets están escritos para OWLv2.
    """
    p = prompt.strip().lower()
    for art in ARTICULOS:
        if p.startswith(art):
            return p[len(art):].strip()
    return p


class DetectorYoloWorld:
    motor = "YOLO-World"

    def __init__(self, config_modelo: dict):
        self.pesos = config_modelo.get("pesos", "yolov8s-worldv2.pt")
        self.carpeta = RAIZ / config_modelo.get("carpeta_local", "modelos_yolo")
        self.prompts = list(config_modelo["prompts"])
        self.nombre = config_modelo.get("nombre_objeto", "objeto")
        self.umbral = float(config_modelo["confianza_minima"])
        # Umbral más bajo solo para DEVOLVER cajas (las débiles, en amarillo).
        self.umbral_vista = float(config_modelo.get("umbral_vista", 0.005))
        self.mostrar_debiles = bool(config_modelo.get("mostrar_debiles", False))
        self.resolucion = int(config_modelo.get("resolucion", 640))
        self.device = elegir_device(config_modelo.get("device", "auto"))
        self.model = None
        self._clases: list[str] = []
        # set_prompts() llega desde el server mientras otra inferencia puede
        # estar corriendo en un hilo: cambiar las clases a mitad de un
        # predict() mezclaría las etiquetas.
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ carga
    def cargar(self) -> None:
        import ultralytics.nn.text_model as text_model
        from ultralytics import YOLOWorld
        from ultralytics.utils import events as ul_events

        # Sin esto, Ultralytics guarda CLIP (~350 MB) en "weights/" relativo a
        # la raíz del repo git o a la carpeta desde donde se arrancó: lo bajaría
        # de nuevo según desde dónde se lance, y quedaría dentro del repo.
        text_model.WEIGHTS_DIR = self.carpeta
        # Ultralytics manda estadísticas de uso (CPU, versiones; no imágenes) a
        # Google Analytics en cada predicción. Esta app es local y se promete
        # offline: se apaga acá, solo para este proceso, sin tocar la
        # configuración global del usuario.
        ul_events.events.enabled = False

        self.carpeta.mkdir(exist_ok=True)
        ruta = self.carpeta / self.pesos
        if not ruta.exists():
            print(f"[modelo] No encuentro {ruta}. Lo bajo (requiere internet).")
        self.model = YOLOWorld(str(ruta))
        self._aplicar_clases()
        self.aplicar_resolucion(self.resolucion)
        print(f"[modelo] YOLO-World ({self.pesos}) cargado en device={self.device}")
        print(f"[modelo] Buscando: {', '.join(self._clases)}")

    def aplicar_resolucion(self, res: int) -> None:
        res = max(160, min(1280, int(res) // 32 * 32))   # múltiplo del stride
        self.resolucion = res
        print(f"[modelo] resolución de entrada: {res}x{res}")

    def set_prompts(self, prompts: list[str]) -> None:
        """Cambia qué se busca. Tarda ~1 s: CLIP codifica los textos."""
        self.prompts = list(prompts)
        if self.model is not None:
            self._aplicar_clases()

    def _aplicar_clases(self) -> None:
        clases = list(dict.fromkeys(a_clase(p) for p in self.prompts if p.strip()))
        with self._lock:
            self.model.set_classes(clases)
            self._clases = clases

    # ------------------------------------------------------------- inferencia
    def detectar(self, frame_bgr: np.ndarray) -> tuple[float, list[dict]]:
        """Recibe un frame BGR de OpenCV. Devuelve (mejor_confianza, [cajas])."""
        if self.model is None:
            return 0.0, []

        corte = (
            min(self.umbral, self.umbral_vista)
            if self.mostrar_debiles
            else self.umbral
        )
        device = "0" if self.device == "cuda" else self.device
        with self._lock:
            r = self.model.predict(
                frame_bgr, imgsz=self.resolucion, conf=corte,
                device=device, verbose=False,
            )[0]
            clases = list(self._clases)

        cajas, mejor = [], 0.0
        for box, conf, cls in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(),
                                  r.boxes.cls.tolist()):
            idx = int(cls)
            x1, y1, x2, y2 = (float(v) for v in box)
            cajas.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "label": clases[idx] if idx < len(clases) else str(idx),
                "conf": float(conf),
                "origen": "modelo",
            })
            mejor = max(mejor, float(conf))

        cajas.sort(key=lambda c: c["conf"], reverse=True)
        return mejor, cajas
