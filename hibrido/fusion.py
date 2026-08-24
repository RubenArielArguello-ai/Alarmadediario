"""
Cómo se combinan los dos validadores para dar un veredicto único.

  Validador A (color)  -> "apareció algo sobre la alfombra y parece papel"
  Validador B (OWLv2)  -> "eso que hay ahí es un diario"

Ninguno alcanza solo. El de color no distingue un diario de una caja blanca.
El modelo, si le pasás la escena vacía, a veces alucina un diario en el dibujo
de la alfombra. Juntos se tapan los agujeros mutuos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Modo(str, Enum):
    CASCADA = "cascada"        # color filtra, modelo decide  (default)
    AND = "and"                # los dos tienen que decir que sí
    OR = "or"                  # con que uno diga que sí, alcanza
    PONDERADO = "ponderado"    # promedio pesado de los dos scores
    SOLO_COLOR = "solo_color"  # apaga el modelo (equivale al proyecto original)
    SOLO_MODELO = "solo_modelo"


@dataclass
class Veredicto:
    es_diario: bool
    score: float               # 0-1
    explicacion: str
    color_ok: bool = False
    modelo_ok: bool = False


def _normalizar(valor: float, umbral: float) -> float:
    """Lleva un score a 0-1 tomando su umbral como el 0.5.

    Los scores de OWLv2 no son probabilidades: 0.62 ya es una detección
    fortísima. Anclar el umbral en 0.5 permite mezclarlo con el score de
    color, que sí es 0-1, sin que uno aplaste al otro.
    """
    if umbral <= 0:
        return 1.0 if valor > 0 else 0.0
    if valor <= umbral:
        return 0.5 * (valor / umbral)
    return min(1.0, 0.5 + 0.5 * (valor - umbral) / max(1.0 - umbral, 1e-6))


class Fusion:
    def __init__(self, cfg: dict):
        self.modo = Modo(cfg.get("modo", "cascada"))
        self.peso_color = float(cfg.get("peso_color", 0.35))
        self.peso_modelo = float(cfg.get("peso_modelo", 0.65))
        self.umbral_ponderado = float(cfg.get("umbral_ponderado", 0.55))

    def evaluar(self, score_color: float, hay_cambio_color: bool,
                papel: float, conf_modelo: float, umbral_papel: float,
                umbral_modelo: float) -> Veredicto:

        color_ok = bool(hay_cambio_color and papel >= umbral_papel)
        modelo_ok = bool(conf_modelo >= umbral_modelo)

        n_color = score_color if hay_cambio_color else 0.0
        n_modelo = _normalizar(conf_modelo, umbral_modelo)

        if self.modo is Modo.SOLO_COLOR:
            return Veredicto(
                color_ok, n_color,
                f"solo color: score {n_color:.2f} (papel {papel:.2f})",
                color_ok, modelo_ok,
            )

        if self.modo is Modo.SOLO_MODELO:
            return Veredicto(
                modelo_ok, n_modelo,
                f"solo modelo: conf {conf_modelo:.2f} vs umbral {umbral_modelo:.2f}",
                color_ok, modelo_ok,
            )

        if self.modo is Modo.OR:
            score = max(n_color, n_modelo)
            return Veredicto(
                color_ok or modelo_ok, score,
                f"OR: color={'sí' if color_ok else 'no'} "
                f"modelo={'sí' if modelo_ok else 'no'}",
                color_ok, modelo_ok,
            )

        if self.modo is Modo.PONDERADO:
            total = self.peso_color + self.peso_modelo or 1.0
            score = (self.peso_color * n_color + self.peso_modelo * n_modelo) / total
            return Veredicto(
                score >= self.umbral_ponderado, score,
                f"ponderado: {score:.2f} vs umbral {self.umbral_ponderado:.2f} "
                f"(color {n_color:.2f}·{self.peso_color:g} + "
                f"modelo {n_modelo:.2f}·{self.peso_modelo:g})",
                color_ok, modelo_ok,
            )

        # CASCADA y AND coinciden en el resultado; se diferencian en que la
        # cascada ni siquiera llega a consultar al modelo si el color dice que
        # no hay nada. Esa decisión la toma el detector, no esta función.
        score = min(n_color, n_modelo) if (color_ok and modelo_ok) else \
            0.5 * (n_color + n_modelo)
        if not hay_cambio_color:
            explic = "el color no ve nada nuevo sobre la alfombra"
        elif not color_ok:
            explic = (f"hay algo nuevo pero no parece papel "
                      f"({papel:.2f} < {umbral_papel:.2f})")
        elif not modelo_ok:
            explic = (f"hay algo tipo papel pero el modelo no lo reconoce "
                      f"como diario ({conf_modelo:.2f} < {umbral_modelo:.2f})")
        else:
            explic = (f"color y modelo coinciden "
                      f"(papel {papel:.2f} · conf {conf_modelo:.2f})")

        return Veredicto(color_ok and modelo_ok, score, explic, color_ok, modelo_ok)
