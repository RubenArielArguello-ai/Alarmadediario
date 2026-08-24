"""
Validador 1: ¿apareció algo sobre la alfombra?

Es la evolución del `detect_diario.py` original, con un cambio de fondo:
aquel comparaba en ESCALA DE GRISES, y en gris una sombra y un diario se
parecen demasiado. Acá comparamos en espacio LAB, que separa la luz (L) del
color (a, b), y eso permite dos cosas que en gris no se pueden:

  1. Descartar sombras. Una sombra baja L pero casi no mueve a/b. Un objeto
     nuevo de otro color mueve a/b sí o sí.
  2. Medir si lo que apareció "parece papel de diario": poco saturado, más
     claro que la alfombra y con mucho contraste interno (el texto impreso).

No usa red neuronal: es OpenCV puro, corre en milisegundos y es la etapa
barata que decide si vale la pena despertar al modelo pesado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# Un delta-E de ~2.3 es el mínimo que el ojo humano distingue. Por debajo de
# 10 estamos en el terreno del ruido de sensor y los cambios de iluminación.
DELTA_E_APENAS_VISIBLE = 2.3


def a_lab(bgr: np.ndarray) -> np.ndarray:
    """BGR de 8 bits -> LAB en unidades reales (L 0-100, a/b -128..127).

    OpenCV devuelve LAB de 8 bits reescalado; sin esta corrección los
    delta-E no son comparables con la literatura ni entre sí.
    """
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1] -= 128.0
    lab[..., 2] -= 128.0
    return lab


@dataclass
class Region:
    """Una mancha de color nuevo sobre la alfombra."""

    x1: int
    y1: int
    x2: int
    y2: int
    area: int
    delta_e: float          # cuán distinto es el color respecto del fondo
    delta_luz: float        # + = más claro que el fondo, - = más oscuro
    delta_croma: float      # cuánto cambió el tono (0 = solo cambió la luz)
    papel: float            # 0-1, qué tanto el color/textura parece diario

    def a_caja(self) -> dict:
        """Mismo formato que las cajas del modelo, para dibujarlas juntas."""
        return {
            "x1": float(self.x1), "y1": float(self.y1),
            "x2": float(self.x2), "y2": float(self.y2),
            "label": f"color Δ{self.delta_e:.0f}",
            "conf": round(self.papel, 3),
            "origen": "color",
        }


@dataclass
class ResultadoColor:
    hay_cambio: bool = False
    score: float = 0.0          # 0-1, confianza de "apareció algo tipo diario"
    cobertura: float = 0.0      # fracción de la zona vigilada que cambió
    area_total: int = 0
    delta_e: float = 0.0        # delta-E de la región más grande
    papel: float = 0.0          # score de "parece papel" de la región más grande
    regiones: list[Region] = field(default_factory=list)
    motivo: str = ""

    @property
    def cajas(self) -> list[dict]:
        return [r.a_caja() for r in self.regiones]


class ValidadorColor:
    """Compara el frame actual contra una referencia de la alfombra vacía."""

    def __init__(self, cfg: dict):
        self.delta_e_min = float(cfg.get("delta_e_minimo", 16.0))
        self.area_minima = int(cfg.get("area_minima", 1500))
        self.ignorar_sombras = bool(cfg.get("ignorar_sombras", True))
        self.croma_sombra = float(cfg.get("croma_sombra", 6.0))
        self.frames_calibracion = int(cfg.get("frames_calibracion", 15))
        # Umbrales del score "parece papel"
        self.sat_max = float(cfg.get("saturacion_maxima", 90.0))
        self.brillo_min = float(cfg.get("brillo_minimo", 90.0))
        self.contraste_ref = float(cfg.get("contraste_referencia", 45.0))
        self.papel_minimo = float(cfg.get("papel_minimo", 0.35))

        self.fondo_bgr: np.ndarray | None = None
        self.fondo_lab: np.ndarray | None = None
        self.mascara_roi: np.ndarray | None = None
        self._buffer: list[np.ndarray] = []

    # ------------------------------------------------------------- calibración
    @property
    def calibrado(self) -> bool:
        return self.fondo_lab is not None

    @property
    def progreso(self) -> tuple[int, int]:
        return len(self._buffer), self.frames_calibracion

    def reiniciar(self) -> None:
        self.fondo_bgr = None
        self.fondo_lab = None
        self._buffer.clear()

    def set_roi(self, mascara: np.ndarray | None) -> None:
        self.mascara_roi = mascara
        self.reiniciar()

    def alimentar_calibracion(self, frame: np.ndarray) -> bool:
        """Acumula frames de la alfombra vacía. Devuelve True cuando terminó.

        Usamos la MEDIANA y no el promedio: si alguien cruza durante la
        calibración, la mediana lo ignora y el promedio se lo come.
        """
        self._buffer.append(frame.copy())
        if len(self._buffer) < self.frames_calibracion:
            return False
        pila = np.stack(self._buffer, axis=0)
        self.fondo_bgr = np.median(pila, axis=0).astype(np.uint8)
        self.fondo_lab = a_lab(self.fondo_bgr)
        self._buffer.clear()
        return True

    def fijar_fondo(self, frame: np.ndarray) -> None:
        """Fija la referencia de un solo frame (modo dos fotos, sin cámara)."""
        self.fondo_bgr = frame.copy()
        self.fondo_lab = a_lab(self.fondo_bgr)
        self._buffer.clear()

    # ------------------------------------------------------------- "es papel?"
    def _score_papel(self, frame: np.ndarray, x1: int, y1: int,
                     x2: int, y2: int, mascara: np.ndarray) -> float:
        """0-1 según cuánto lo que apareció se parece a papel de diario.

        Tres señales, ninguna concluyente sola:
          - poca saturación  (el papel es acromático; una toalla roja no)
          - buen brillo      (el papel refleja más que casi cualquier alfombra)
          - mucho contraste  (el texto impreso genera negros sobre blanco)

        Se mide SOLO sobre los píxeles que cambiaron, no sobre el rectángulo
        entero: un diario enrollado ocupa menos de la mitad de su bounding box
        y el resto es alfombra, que ensucia las tres medidas.
        """
        recorte = frame[y1:y2, x1:x2]
        if recorte.size == 0 or not mascara.any():
            return 0.0

        hsv = cv2.cvtColor(recorte, cv2.COLOR_BGR2HSV)
        sat = float(hsv[..., 1][mascara].mean())
        val = float(hsv[..., 2][mascara].mean())
        gris = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
        contraste = float(gris[mascara].std())

        f_sat = np.clip(1.0 - sat / max(self.sat_max, 1.0), 0.0, 1.0)
        f_brillo = np.clip(
            (val - self.brillo_min) / max(255.0 - self.brillo_min, 1.0), 0.0, 1.0
        )
        f_contraste = np.clip(contraste / max(self.contraste_ref, 1.0), 0.0, 1.0)

        return float(0.45 * f_sat + 0.35 * f_brillo + 0.20 * f_contraste)

    # ---------------------------------------------------------------- análisis
    def analizar(self, frame: np.ndarray) -> ResultadoColor:
        if self.fondo_lab is None:
            return ResultadoColor(motivo="sin calibrar")

        actual = a_lab(frame)
        d = actual - self.fondo_lab
        d_luz = d[..., 0]
        d_croma = np.sqrt(d[..., 1] ** 2 + d[..., 2] ** 2)
        delta_e = np.sqrt(d_luz ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)

        cambio = delta_e > self.delta_e_min

        if self.ignorar_sombras:
            # Sombra = se oscureció sin cambiar de tono. Un diario, al revés,
            # aclara la zona (dL > 0) o cambia el tono (croma alto).
            sombra = (d_luz < 0) & (d_croma < self.croma_sombra)
            cambio &= ~sombra

        mascara = (cambio.astype(np.uint8)) * 255
        if self.mascara_roi is not None:
            mascara = cv2.bitwise_and(mascara, self.mascara_roi)

        # Abrir mata el ruido sal-y-pimienta; cerrar une el diario que quedó
        # partido por un reflejo o un pliegue.
        nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, nucleo)
        mascara = cv2.morphologyEx(
            mascara, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)),
        )

        total_zona = (
            int(np.count_nonzero(self.mascara_roi))
            if self.mascara_roi is not None
            else int(mascara.size)
        )
        cobertura = (
            float(np.count_nonzero(mascara)) / total_zona if total_zona else 0.0
        )

        contornos, _ = cv2.findContours(
            mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        alto, ancho = frame.shape[:2]
        regiones: list[Region] = []
        area_total = 0

        for c in contornos:
            area = int(cv2.contourArea(c))
            if area < self.area_minima:
                continue
            x, y, w, h = cv2.boundingRect(c)
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(ancho, x + w), min(alto, y + h)

            recorte_mask = mascara[y1:y2, x1:x2] > 0
            if not recorte_mask.any():
                continue

            regiones.append(
                Region(
                    x1=x1, y1=y1, x2=x2, y2=y2, area=area,
                    delta_e=float(delta_e[y1:y2, x1:x2][recorte_mask].mean()),
                    delta_luz=float(d_luz[y1:y2, x1:x2][recorte_mask].mean()),
                    delta_croma=float(d_croma[y1:y2, x1:x2][recorte_mask].mean()),
                    papel=self._score_papel(frame, x1, y1, x2, y2, recorte_mask),
                )
            )
            area_total += area

        if not regiones:
            return ResultadoColor(
                cobertura=cobertura,
                motivo="sin regiones por encima del área mínima",
            )

        regiones.sort(key=lambda r: r.area, reverse=True)
        principal = regiones[0]

        # El score mezcla "qué tan distinto es el color" con "qué tanto parece
        # papel". Una mancha enorme de color rarísimo no debería disparar la
        # alarma de diario, y una manchita muy papel tampoco.
        f_delta = float(
            np.clip(
                (principal.delta_e - self.delta_e_min)
                / max(self.delta_e_min, DELTA_E_APENAS_VISIBLE),
                0.0, 1.0,
            )
        )
        score = float(np.clip(0.4 * f_delta + 0.6 * principal.papel, 0.0, 1.0))

        return ResultadoColor(
            hay_cambio=True,
            score=score,
            cobertura=cobertura,
            area_total=area_total,
            delta_e=principal.delta_e,
            papel=principal.papel,
            regiones=regiones,
            motivo=(
                f"{len(regiones)} región(es), ΔE={principal.delta_e:.1f}, "
                f"papel={principal.papel:.2f}"
            ),
        )

    def bbox_regiones(self, res: ResultadoColor, margen: int,
                      alto: int, ancho: int) -> tuple[int, int, int, int] | None:
        """Caja que envuelve todas las regiones, para recortar antes del modelo.

        Darle al modelo solo la zona que cambió, en vez del frame entero,
        sube mucho la confianza: el objeto pasa a ocupar casi todo el recorte.
        """
        if not res.regiones:
            return None
        x1 = max(0, min(r.x1 for r in res.regiones) - margen)
        y1 = max(0, min(r.y1 for r in res.regiones) - margen)
        x2 = min(ancho, max(r.x2 for r in res.regiones) + margen)
        y2 = min(alto, max(r.y2 for r in res.regiones) + margen)
        if x2 <= x1 or y2 <= y1:
            return None
        return x1, y1, x2, y2
