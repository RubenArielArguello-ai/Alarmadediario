"""
Detector híbrido: une los dos proyectos en un solo pipeline.

    frame de cámara
         |
         v
    [1] movimiento (gris, ~1 ms)      ¿alguien está pasando? -> esperar
         |
         v
    [2] validador de color (LAB, ~5 ms)   ¿apareció algo sobre la alfombra?
         |                                 ¿ese algo parece papel?
         |  (si no ve nada, acá se corta y el modelo nunca se despierta)
         v
    [3] OWLv2 (~1-30 s según resolución)  ¿eso es un diario?
         |   <- recibe SOLO el recorte que marcó el color, no el frame entero
         v
    [4] fusión -> veredicto -> confirmaciones -> ALARMA

La idea de fondo es la misma que en el proyecto original: el diario NO se
mueve. Mientras hay movimiento no decidimos nada, porque es una persona
pasando. Recién cuando la escena se queda quieta y además cambió respecto de
la alfombra vacía, tiene sentido preguntar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np

from fusion import Fusion, Modo, Veredicto
from modelo import DetectorOWL
from validador_color import ValidadorColor, ResultadoColor


class Estado(str, Enum):
    CALIBRANDO = "calibrando"        # aprendiendo cómo es la alfombra vacía
    VIGILANDO = "vigilando"          # todo normal
    MOVIMIENTO = "movimiento"        # algo se mueve, esperamos
    ESTABILIZANDO = "estabilizando"  # apareció algo, esperando que se quede quieto
    VERIFICANDO = "verificando"      # consultando al modelo
    DIARIO = "diario"                # confirmado por los dos validadores
    DESCARTADO = "descartado"        # hay un objeto, pero no es un diario


@dataclass
class Resultado:
    estado: Estado
    mensaje: str
    movimiento: float = 0.0
    # --- validador de color ---
    color_cambio: bool = False
    color_score: float = 0.0
    color_cobertura: float = 0.0
    color_delta_e: float = 0.0
    color_papel: float = 0.0
    color_area: int = 0
    # --- modelo ---
    confianza: float = 0.0
    # --- fusión ---
    score_final: float = 0.0
    veredicto: str = ""
    color_ok: bool = False
    modelo_ok: bool = False
    # --- común ---
    cajas: list = field(default_factory=list)
    confirmaciones: int = 0

    # El proyecto original llamaba a esto "diferencia respecto del fondo".
    # Se mantiene el nombre para que la UI y el harness viejos no se rompan.
    @property
    def diferencia_fondo(self) -> float:
        return self.color_cobertura


class DetectorHibrido:
    def __init__(self, config: dict):
        self.cfg = config
        cfg_d = config["deteccion"]

        self.owl = DetectorOWL(config["modelo"])
        self.color = ValidadorColor(config.get("color", {}))
        self.fusion = Fusion(config.get("fusion", {}))

        self.umbral_mov = float(cfg_d["umbral_movimiento"])
        self.seg_estabilidad = float(cfg_d["segundos_estabilidad"])
        self.confirmaciones_necesarias = int(cfg_d["confirmaciones_necesarias"])
        self.seg_entre_inferencias = float(cfg_d["segundos_entre_inferencias"])
        self.cooldown = float(cfg_d["cooldown_alarma"])
        self.margen_recorte = int(cfg_d.get("margen_recorte", 40))

        # --- estado interno ---
        self.mascara_roi: np.ndarray | None = None
        self.bbox_roi: tuple[int, int, int, int] | None = None
        self.frame_anterior: np.ndarray | None = None
        self.quieto_desde: float | None = None
        self.confirmaciones = 0
        self.ultima_inferencia = 0.0
        self.ultima_alarma = 0.0
        self.estado = Estado.CALIBRANDO

        # --- inferencia asíncrona ---
        # procesar() NUNCA llama al modelo: solo levanta esta bandera. El
        # server corre la inferencia en otro hilo y devuelve el resultado por
        # resolver_inferencia(). Así el video nunca se congela.
        self.pedido_inferencia = False
        self.inferencia_activa = False

        # --- modo prueba: analiza siempre, sin esperar movimiento ---
        self.modo_continuo = False
        self.segundos_persistencia = 6.0
        self._cajas_modelo: list = []
        self._cajas_hasta = 0.0
        self._conf_ultima = 0.0
        self._ultimo_color = ResultadoColor()
        self._ultimo_veredicto: Veredicto | None = None

    # ------------------------------------------------------------------ atajos
    @property
    def conf_min(self) -> float:
        return self.owl.umbral

    @conf_min.setter
    def conf_min(self, v: float) -> None:
        self.owl.umbral = float(v)

    @property
    def device(self) -> str:
        return self.owl.device

    @property
    def nombre(self) -> str:
        return self.owl.nombre

    @property
    def usa_modelo(self) -> bool:
        return self.fusion.modo is not Modo.SOLO_COLOR

    @property
    def usa_color(self) -> bool:
        return self.fusion.modo is not Modo.SOLO_MODELO

    def cargar_modelo(self) -> None:
        if self.usa_modelo:
            self.owl.cargar()
        else:
            print("[modelo] modo solo_color: no cargo OWLv2")

    # -------------------------------------------------------------------- ROI
    def set_roi(self, puntos_rel: list, alto: int, ancho: int) -> None:
        """Define la zona a vigilar. puntos_rel en coordenadas 0-1."""
        if not puntos_rel or len(puntos_rel) < 3:
            self.mascara_roi = None
            self.bbox_roi = None
            self.color.set_roi(None)
            self.reiniciar_fondo()
            return

        pts = np.array(
            [[int(x * ancho), int(y * alto)] for x, y in puntos_rel], dtype=np.int32
        )
        mascara = np.zeros((alto, ancho), dtype=np.uint8)
        cv2.fillPoly(mascara, [pts], 255)
        self.mascara_roi = mascara

        margen = 25
        x1 = max(0, int(pts[:, 0].min()) - margen)
        y1 = max(0, int(pts[:, 1].min()) - margen)
        x2 = min(ancho, int(pts[:, 0].max()) + margen)
        y2 = min(alto, int(pts[:, 1].max()) + margen)
        self.bbox_roi = (x1, y1, x2, y2)
        self.color.set_roi(mascara)
        self.reiniciar_fondo()

    def reiniciar_fondo(self) -> None:
        """Olvida la referencia y vuelve a calibrar (usar al mover la cámara)."""
        self.color.reiniciar()
        self.frame_anterior = None
        self.quieto_desde = None
        self.confirmaciones = 0
        self._ultimo_color = ResultadoColor()
        self.estado = Estado.CALIBRANDO

    # ------------------------------------------------------------ pre-proceso
    def _gris(self, frame: np.ndarray) -> np.ndarray:
        """Gris + blur, recortado a la ROI. Solo se usa para medir movimiento."""
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gris = cv2.GaussianBlur(gris, (21, 21), 0)
        if self.mascara_roi is not None:
            gris = cv2.bitwise_and(gris, gris, mask=self.mascara_roi)
        return gris

    def _fraccion_distinta(self, a: np.ndarray, b: np.ndarray) -> float:
        """Fracción de píxeles de la zona que cambiaron entre dos frames."""
        delta = cv2.absdiff(a, b)
        _, thr = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)
        thr = cv2.dilate(thr, None, iterations=2)
        total = (
            int(np.count_nonzero(self.mascara_roi))
            if self.mascara_roi is not None
            else thr.size
        )
        if total == 0:
            return 0.0
        return float(np.count_nonzero(thr)) / total

    # ------------------------------------------------------------- inferencia
    def consultar_modelo(self, frame: np.ndarray) -> tuple[float, list]:
        """Lo llama el server desde otro hilo. Bloquea, pero no al video."""
        alto, ancho = frame.shape[:2]

        # Preferimos el recorte que marcó el validador de color: el objeto pasa
        # a ocupar casi todo el cuadro y OWLv2 sube bastante la confianza.
        caja = self.color.bbox_regiones(
            self._ultimo_color, self.margen_recorte, alto, ancho
        )
        if caja is None:
            caja = self.bbox_roi

        recorte, offset = frame, (0, 0)
        if caja is not None:
            x1, y1, x2, y2 = caja
            recorte = frame[y1:y2, x1:x2]
            offset = (x1, y1)
        if recorte.size == 0:
            return 0.0, []

        conf, cajas = self.owl.detectar(recorte)
        for c in cajas:
            c["x1"] += offset[0]; c["x2"] += offset[0]
            c["y1"] += offset[1]; c["y2"] += offset[1]
        return conf, cajas

    def _listo_para_inferir(self, ahora: float) -> bool:
        return (
            self.usa_modelo
            and not self.inferencia_activa
            and ahora - self.ultima_inferencia >= self.seg_entre_inferencias
        )

    def _fusionar(self, conf: float) -> Veredicto:
        return self.fusion.evaluar(
            score_color=self._ultimo_color.score,
            hay_cambio_color=self._ultimo_color.hay_cambio,
            papel=self._ultimo_color.papel,
            conf_modelo=conf,
            umbral_papel=self.color.papel_minimo,
            umbral_modelo=self.owl.umbral,
        )

    def resolver_inferencia(self, conf: float, cajas: list) -> None:
        """Aplica el resultado que devolvió el hilo de inferencia."""
        self._cajas_modelo = cajas
        self._conf_ultima = conf
        self._cajas_hasta = time.time() + self.segundos_persistencia

        veredicto = self._fusionar(conf)
        self._ultimo_veredicto = veredicto

        if self.modo_continuo:
            self.estado = Estado.DIARIO if veredicto.es_diario else Estado.VIGILANDO
            return

        if veredicto.es_diario:
            self.confirmaciones += 1
        else:
            self.confirmaciones = max(0, self.confirmaciones - 1)

        ahora = time.time()
        if self.confirmaciones >= self.confirmaciones_necesarias:
            if ahora - self.ultima_alarma >= self.cooldown:
                self.ultima_alarma = ahora
            self.estado = Estado.DIARIO
        elif self._ultimo_color.hay_cambio and not veredicto.modelo_ok:
            # Hay un objeto sobre la alfombra, pero no es un diario.
            self.estado = Estado.DESCARTADO

    # ---------------------------------------------------------------- público
    def procesar(self, frame: np.ndarray) -> Resultado:
        if self.modo_continuo:
            res = self._procesar_continuo(frame)
        else:
            res = self._procesar_normal(frame)

        # Las cajas del modelo se mantienen unos segundos para que no
        # parpadeen: entre inferencia e inferencia pasan varios frames.
        cajas_modelo = (
            self._cajas_modelo if time.time() < self._cajas_hasta else []
        )
        res.cajas = list(res.cajas) + list(cajas_modelo)
        if res.confianza == 0.0 and cajas_modelo:
            res.confianza = self._conf_ultima
        return res

    # ------------------------------------------------------------ modo prueba
    def _procesar_continuo(self, frame: np.ndarray) -> Resultado:
        """Analiza todo el tiempo, sin esperar movimiento. Sirve para calibrar."""
        ahora = time.time()

        if self.color.calibrado:
            self._ultimo_color = self.color.analizar(frame)
        else:
            self.color.alimentar_calibracion(frame)

        if self._listo_para_inferir(ahora):
            self.pedido_inferencia = True

        if self.inferencia_activa:
            msg = f"[prueba] analizando… (última conf {self._conf_ultima:.2f})"
        elif self._ultimo_veredicto is not None:
            msg = f"[prueba] {self._ultimo_veredicto.explicacion}"
        else:
            msg = "[prueba] sin resultados todavía"

        return self._armar(self.estado, msg, 0.0)

    # ----------------------------------------------------------- modo normal
    def _procesar_normal(self, frame: np.ndarray) -> Resultado:
        ahora = time.time()
        gris = self._gris(frame)

        # --- [0] calibración: aprendemos cómo es la alfombra vacía ---
        if not self.color.calibrado:
            self.frame_anterior = gris.copy()
            listo = self.color.alimentar_calibracion(frame)
            hechos, total = self.color.progreso
            if listo:
                self.estado = Estado.VIGILANDO
                return self._armar(Estado.VIGILANDO, "Calibrado. Vigilando.", 0.0)
            self.estado = Estado.CALIBRANDO
            return self._armar(
                Estado.CALIBRANDO,
                f"Calibrando alfombra vacía… {hechos}/{total}", 0.0,
            )

        # --- [1] movimiento ---
        movimiento = 0.0
        if self.frame_anterior is not None:
            movimiento = self._fraccion_distinta(self.frame_anterior, gris)
        self.frame_anterior = gris.copy()

        if movimiento > self.umbral_mov:
            self.quieto_desde = None
            self.confirmaciones = 0
            self.estado = Estado.MOVIMIENTO
            return self._armar(
                Estado.MOVIMIENTO, "Movimiento detectado, esperando…", movimiento
            )

        # --- [2] validador de color ---
        self._ultimo_color = self.color.analizar(frame)

        if not self._ultimo_color.hay_cambio:
            self.quieto_desde = None
            self.confirmaciones = 0
            self._ultimo_veredicto = None
            self.estado = Estado.VIGILANDO
            return self._armar(
                Estado.VIGILANDO, "Sin novedad sobre la alfombra.", movimiento
            )

        # En modo solo_color no hay etapa 3: el color decide y listo.
        if not self.usa_modelo:
            veredicto = self._fusionar(0.0)
            self._ultimo_veredicto = veredicto
            self.estado = Estado.DIARIO if veredicto.es_diario else Estado.DESCARTADO
            return self._armar(self.estado, veredicto.explicacion, movimiento)

        # --- ya confirmado: no volvemos a molestar al modelo ---
        if self.estado == Estado.DIARIO:
            return self._armar(
                Estado.DIARIO, f"{self.nombre.capitalize()} presente.", movimiento
            )

        # --- [2b] esperamos a que la escena se quede quieta ---
        if self.quieto_desde is None:
            self.quieto_desde = ahora

        estable = ahora - self.quieto_desde
        if estable < self.seg_estabilidad:
            self.estado = Estado.ESTABILIZANDO
            return self._armar(
                Estado.ESTABILIZANDO,
                f"Objeto nuevo (ΔE={self._ultimo_color.delta_e:.0f}, "
                f"papel={self._ultimo_color.papel:.2f}). "
                f"Estabilizando {estable:.1f}/{self.seg_estabilidad:.0f}s",
                movimiento,
            )

        # --- [3] pedimos inferencia (la corre el server en otro hilo) ---
        if self._listo_para_inferir(ahora):
            self.pedido_inferencia = True

        if self.estado != Estado.DESCARTADO:
            self.estado = Estado.VERIFICANDO

        if self.inferencia_activa:
            msg = "Objeto nuevo — preguntándole al modelo…"
        elif self._ultimo_veredicto is not None:
            msg = (f"{self._ultimo_veredicto.explicacion} — "
                   f"confirmaciones {self.confirmaciones}/"
                   f"{self.confirmaciones_necesarias}")
        else:
            msg = "Objeto nuevo — esperando al modelo"

        return self._armar(self.estado, msg, movimiento)

    # ------------------------------------------------------------- armado
    def _armar(self, estado: Estado, mensaje: str, movimiento: float) -> Resultado:
        col = self._ultimo_color
        ver = self._ultimo_veredicto
        return Resultado(
            estado=estado,
            mensaje=mensaje,
            movimiento=movimiento,
            color_cambio=col.hay_cambio,
            color_score=round(col.score, 3),
            color_cobertura=round(col.cobertura, 4),
            color_delta_e=round(col.delta_e, 1),
            color_papel=round(col.papel, 3),
            color_area=col.area_total,
            confianza=round(self._conf_ultima, 3) if ver is not None else 0.0,
            score_final=round(ver.score, 3) if ver else 0.0,
            veredicto=ver.explicacion if ver else "",
            color_ok=ver.color_ok if ver else col.hay_cambio,
            modelo_ok=ver.modelo_ok if ver else False,
            cajas=col.cajas,
            confirmaciones=self.confirmaciones,
        )
