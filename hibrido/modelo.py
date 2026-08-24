"""
Envoltorio de OWLv2 (detector de vocabulario abierto).

OWLv2 acepta descripciones en texto libre ("a rolled newspaper") y devuelve
cajas, sin necesidad de entrenar nada. Probado sobre fotos reales de una
entrada: 0.62 de confianza con diario, 0.00 sin diario.

El modelo se descarga una sola vez a modelos/ y despues funciona offline.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).parent


def elegir_device(preferencia: str = "auto") -> str:
    """Devuelve el mejor device disponible. 'auto' detecta solo."""
    if preferencia and preferencia != "auto":
        return preferencia
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"          # Apple Silicon
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class DetectorOWL:
    def __init__(self, config_modelo: dict):
        self.id = config_modelo["id"]
        self.carpeta = RAIZ / config_modelo.get("carpeta_local", "modelos")
        self.prompts = list(config_modelo["prompts"])
        self.nombre = config_modelo.get("nombre_objeto", "objeto")
        self.umbral = float(config_modelo["confianza_minima"])
        # Umbral mas bajo solo para DEVOLVER cajas: permite ver en pantalla las
        # detecciones debiles (en amarillo) y entender por que no dispara.
        self.umbral_vista = float(config_modelo.get("umbral_vista", 0.04))
        # Si es False solo se devuelven cajas que superan el umbral real.
        self.mostrar_debiles = bool(config_modelo.get("mostrar_debiles", False))
        # OJO: la cuantizacion int8 se probo y ARRUINA la deteccion en OWLv2
        # (0.62 -> 0.00 sobre las fotos de prueba) sin casi ganar velocidad.
        # Queda desactivada; no la actives salvo que la midas vos mismo.
        self.cuantizar = bool(config_modelo.get("cuantizar_cpu", False))
        # Resolucion de entrada. OWLv2 fue entrenado a 960, pero se puede bajar
        # interpolando los position embeddings. El tiempo escala ~cuadratico.
        self.resolucion = int(config_modelo.get("resolucion", 640))
        self.device = elegir_device(config_modelo.get("device", "auto"))
        self.proc = None
        self.model = None

    # ------------------------------------------------------------------ carga
    def cargar(self) -> None:
        import torch
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        origen = self.carpeta if (self.carpeta / "config.json").exists() else self.id
        if origen is self.id:
            print(
                f"[modelo] No encuentro pesos locales en {self.carpeta}.\n"
                "         Intentando descargar (requiere internet).\n"
                "         Para uso offline corré primero: python descargar_modelo.py"
            )
        else:
            # Con pesos locales, cortamos todo acceso a red.
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        # use_fast=True usa el preprocesador basado en torchvision, bastante
        # mas rapido que el "slow" de PIL.
        try:
            self.proc = Owlv2Processor.from_pretrained(str(origen), use_fast=True)
        except Exception:
            self.proc = Owlv2Processor.from_pretrained(str(origen))

        self.model = Owlv2ForObjectDetection.from_pretrained(str(origen)).eval()

        if self.device != "cpu":
            try:
                self.model = self.model.to(self.device)
            except Exception as e:
                print(f"[modelo] No pude usar {self.device} ({e}); vuelvo a CPU.")
                self.device = "cpu"

        if self.device == "cpu":
            # Usar todos los nucleos fisicos acelera bastante en Mac Intel.
            try:
                import os as _os

                nucleos = _os.cpu_count() or 4
                torch.set_num_threads(max(1, nucleos))
                print(f"[modelo] usando {max(1, nucleos)} hilos de CPU")
            except Exception:
                pass

            if self.cuantizar:
                try:
                    self.model = torch.quantization.quantize_dynamic(
                        self.model, {torch.nn.Linear}, dtype=torch.qint8
                    )
                    print("[modelo] cuantización int8 activada (más rápido en CPU)")
                except Exception as e:
                    print(f"[modelo] no pude cuantizar ({e}); sigo en float32")

        self.torch = torch
        self.aplicar_resolucion(self.resolucion)
        print(f"[modelo] OWLv2 cargado en device={self.device}")
        print(f"[modelo] Buscando: {', '.join(self.prompts)}")

    def aplicar_resolucion(self, res: int) -> None:
        """
        Cambia la resolucion de entrada. 960 es la nativa; por debajo hay que
        interpolar los position embeddings (lo hace transformers solo).
        Menos resolucion = mucho mas rapido, pero pierde objetos chicos.
        """
        res = max(224, min(960, int(res) // 16 * 16))   # multiplo del patch
        self.resolucion = res
        if self.proc is not None:
            self.proc.image_processor.size = {"height": res, "width": res}
        print(f"[modelo] resolución de entrada: {res}x{res}"
              f"{' (nativa)' if res == 960 else ''}")

    def set_prompts(self, prompts: list[str]) -> None:
        self.prompts = list(prompts)

    # ------------------------------------------------------------- inferencia
    def detectar(self, frame_bgr: np.ndarray) -> tuple[float, list[dict]]:
        """
        Recibe un frame BGR de OpenCV.
        Devuelve (mejor_confianza, [cajas]) en coordenadas del frame recibido.
        """
        if self.model is None:
            return 0.0, []

        import cv2
        from PIL import Image

        img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        entradas = self.proc(text=[self.prompts], images=img, return_tensors="pt")
        if self.device != "cpu":
            entradas = {k: v.to(self.device) for k, v in entradas.items()}

        with self.torch.no_grad():
            if self.resolucion != 960:
                try:
                    salida = self.model(**entradas, interpolate_pos_encoding=True)
                except TypeError:
                    # transformers viejo: no soporta interpolar -> volvemos a 960
                    print("[modelo] tu versión de transformers no permite bajar la "
                          "resolución; vuelvo a 960")
                    self.aplicar_resolucion(960)
                    entradas = self.proc(
                        text=[self.prompts], images=img, return_tensors="pt"
                    )
                    if self.device != "cpu":
                        entradas = {k: v.to(self.device) for k, v in entradas.items()}
                    salida = self.model(**entradas)
            else:
                salida = self.model(**entradas)

        tam = self.torch.tensor([img.size[::-1]])
        corte = (
            min(self.umbral, self.umbral_vista)
            if self.mostrar_debiles
            else self.umbral
        )
        res = self.proc.post_process_grounded_object_detection(
            salida, threshold=corte, target_sizes=tam
        )[0]

        cajas, mejor = [], 0.0
        for score, label, box in zip(res["scores"], res["labels"], res["boxes"]):
            conf = float(score)
            idx = int(label)
            x1, y1, x2, y2 = (float(v) for v in box.tolist())
            cajas.append(
                {
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "label": self.prompts[idx] if idx < len(self.prompts) else str(idx),
                    "conf": conf,
                    "origen": "modelo",
                }
            )
            mejor = max(mejor, conf)

        cajas.sort(key=lambda c: c["conf"], reverse=True)
        return mejor, cajas
