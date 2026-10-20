"""
Detector híbrido: une los dos proyectos en un solo pipeline.

    frame de cámara (fija)
         |
    [0] ¿toca chequear?  cada `intervalo_chequeo` s (0 = todos los frames)
         |
         v
    [1] movimiento (gris, ~1 ms)      ¿alguien está pasando? -> esperar
         |
         v
    [2] validador de color (LAB, ~5 ms)   ¿cambió algo en la zona respecto
         |                                 de cuando estaba vacía?
         |  (si no ve nada, acá se corta y el modelo nunca se despierta)
         v
    [3] modelo: YOLO-World (~0.6 s) u OWLv2 (~4-9 s)   ¿eso es lo que dice el prompt?
         |   <- recibe SOLO el recorte que marcó el color, no el frame entero
         v
    [4] fusión -> veredicto -> confirmaciones -> ALARMA

La idea de fondo es la misma que en el proyecto original: el objeto, una vez
apoyado, NO se mueve. Mientras hay movimiento no decidimos nada, porque es
una mano o una persona pasando. Recién cuando la escena se queda quieta y
además cambió respecto de la zona vacía, tiene sentido preguntar.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum

import cv2
import numpy as np

from fusion import Fusion, Modo, Veredicto
from modelo import crear_motor
from validador_color import ValidadorColor, ResultadoColor


class Estado(str, Enum):
    CALIBRANDO = "calibrando"        # aprendiendo cómo es la zona vacía
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
    proximo_chequeo: float = -1.0   # segundos; -1 = chequeando ahora o continuo

    # El proyecto original llamaba a esto "diferencia respecto del fondo".
    # Se mantiene el nombre para que la UI y el harness viejos no se rompan.
    @property
    def diferencia_fondo(self) -> float:
        return self.color_cobertura


class DetectorHibrido:
    def __init__(self, config: dict):
        self.cfg = config
        cfg_d = config["deteccion"]

        # OWLv2 o YOLO-World, según config["modelo"]["motor"]
        self.motor = crear_motor(config["modelo"])
        self.color = ValidadorColor(config.get("color", {}))
        self.fusion = Fusion(config.get("fusion", {}))

        self.umbral_mov = float(cfg_d["umbral_movimiento"])
        self.seg_estabilidad = float(cfg_d["segundos_estabilidad"])
        self.confirmaciones_necesarias = int(cfg_d["confirmaciones_necesarias"])
        self.seg_entre_inferencias = float(cfg_d["segundos_entre_inferencias"])
        self.cooldown = float(cfg_d["cooldown_alarma"])
        self.margen_recorte = int(cfg_d.get("margen_recorte", 40))
        # Cada cuántos segundos se mira la zona. 0 = sin pausa, todos los
        # frames (el comportamiento original).
        self.intervalo_chequeo = float(cfg_d.get("intervalo_chequeo", 0))
        # Tope de un chequeo: si en este tiempo no se pudo concluir (alguien
        # con la mano encima de la hoja), se abandona hasta el próximo.
        self.max_seg_chequeo = float(cfg_d.get("max_segundos_chequeo", 30))

        # --- estado interno ---
        self.mascara_roi: np.ndarray | None = None
        self.bbox_roi: tuple[int, int, int, int] | None = None
        self.frame_anterior: np.ndarray | None = None
        self.quieto_desde: float | None = None
        self.confirmaciones = 0
        self.ultima_inferencia = 0.0
        self.ultima_alarma = float("-inf")   # nunca hubo alarma
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

        # --- chequeo periódico ---
        # Un "chequeo" es un ciclo corto: comparar la zona contra la
        # referencia y, si cambió, esperar a que quede quieta y consultar al
        # modelo hasta tener veredicto. Entre chequeo y chequeo no se analiza.
        self._ciclo_desde: float | None = None   # None = no hay chequeo abierto
        self._inferencias_ciclo = 0
        self._proximo_chequeo = 0.0              # 0 = chequear ya
        self._resultado_chequeo = ""
        # Cómo se veía la zona cuando se llegó al último veredicto. Entre
        # chequeos no se mira, así que es la única forma de saber si alguien
        # cambió el objeto mientras tanto.
        self._gris_conclusion: np.ndarray | None = None

        # --- concurrencia ---
        # procesar() corre en un hilo del pool (server.py hace
        # asyncio.to_thread), mientras que resolver_inferencia() se llama
        # directamente desde el loop de eventos cuando termina la inferencia
        # en OTRO hilo. Ambos leen y escriben self.estado, self.confirmaciones,
        # etc. al mismo tiempo. RLock (no Lock simple) porque set_roi() llama
        # a reiniciar_fondo() y las dos toman el lock.
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ atajos
    @property
    def conf_min(self) -> float:
        return self.motor.umbral

    @conf_min.setter
    def conf_min(self, v: float) -> None:
        self.motor.umbral = float(v)

    @property
    def device(self) -> str:
        return self.motor.device

    @property
    def nombre(self) -> str:
        return self.motor.nombre

    @property
    def usa_modelo(self) -> bool:
        return self.fusion.modo is not Modo.SOLO_COLOR

    @property
    def usa_color(self) -> bool:
        return self.fusion.modo is not Modo.SOLO_MODELO

    def cargar_modelo(self) -> None:
        if self.usa_modelo:
            self.motor.cargar()
        else:
            print("[modelo] modo solo_color: no cargo ningún modelo")

    # -------------------------------------------------------------------- ROI
    def set_roi(self, puntos_rel: list, alto: int, ancho: int) -> None:
        """Define la zona a vigilar. puntos_rel en coordenadas 0-1."""
        with self._lock:
            if not puntos_rel or len(puntos_rel) < 3:
                self.mascara_roi = None
                self.bbox_roi = None
                self.color.set_roi(None)
                self.reiniciar_fondo()
                return

            pts = np.array(
                [[int(x * ancho), int(y * alto)] for x, y in puntos_rel],
                dtype=np.int32,
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
        with self._lock:
            self.color.reiniciar()
            self.frame_anterior = None
            self.quieto_desde = None
            self.confirmaciones = 0
            self._ultimo_color = ResultadoColor()
            self.estado = Estado.CALIBRANDO
            # Recién calibrado se chequea enseguida, sin esperar el intervalo.
            self._ciclo_desde = None
            self._proximo_chequeo = 0.0
            self._resultado_chequeo = ""
            self._gris_conclusion = None

    # ------------------------------------------------------ chequeo periódico
    @property
    def periodico(self) -> bool:
        return self.intervalo_chequeo > 0

    def _abrir_ciclo(self, ahora: float, gris: np.ndarray) -> None:
        self._ciclo_desde = ahora
        self._inferencias_ciclo = 0
        self.confirmaciones = 0
        self.quieto_desde = None

        # Si desde el último veredicto la zona cambió (sacaron el lápiz y
        # pusieron otra cosa mientras no mirábamos), ese veredicto ya no vale:
        # hay que volver a preguntar. Si no cambió, se reutiliza tal cual.
        if self.estado in (Estado.DIARIO, Estado.DESCARTADO) and (
            self._gris_conclusion is None
            or self._fraccion_distinta(self._gris_conclusion, gris) > self.umbral_mov
        ):
            self.estado = Estado.VIGILANDO
            self._ultimo_veredicto = None

    def _cerrar_ciclo(self, ahora: float, resultado: str) -> None:
        """Termina el chequeo en curso y agenda el próximo."""
        if not self.periodico or self._ciclo_desde is None:
            return
        self._ciclo_desde = None
        self._proximo_chequeo = ahora + self.intervalo_chequeo
        self._resultado_chequeo = resultado
        if self.frame_anterior is not None:
            self._gris_conclusion = self.frame_anterior.copy()

    def chequear_ya(self, olvidar_veredicto: bool = False) -> None:
        """Adelanta el próximo chequeo a ahora mismo.

        Con olvidar_veredicto (se cambió el prompt), además descarta lo que
        se había concluido: un "lápiz presente" no dice nada si ahora se busca
        otra cosa, y sin esto el chequeo siguiente lo daría por bueno sin
        volver a consultar al modelo.
        """
        with self._lock:
            self.confirmaciones = 0
            self._ciclo_desde = None
            self._proximo_chequeo = 0.0
            if olvidar_veredicto:
                self.ultima_alarma = float("-inf")
                self._ultimo_veredicto = None
                self._resultado_chequeo = ""
                if self.estado in (Estado.DIARIO, Estado.DESCARTADO):
                    self.estado = Estado.VIGILANDO

    def segundos_para_chequeo(self, ahora: float) -> float:
        """Cuánto falta para el próximo chequeo. -1 si hay uno en curso o si
        no hay chequeo periódico."""
        if not self.periodico or self._ciclo_desde is not None:
            return -1.0
        return max(0.0, self._proximo_chequeo - ahora)

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

        # Tomamos una foto instantánea del color/ROI bajo lock (rápido), y
        # dejamos la inferencia del modelo (lenta, puede tardar varios
        # segundos) FUERA del lock: si no, congelaría también a procesar().
        with self._lock:
            ultimo_color = self._ultimo_color
            bbox_roi = self.bbox_roi

        # Preferimos el recorte que marcó el validador de color: el objeto pasa
        # a ocupar casi todo el cuadro y el modelo sube bastante la confianza.
        caja = self.color.bbox_regiones(ultimo_color, self.margen_recorte, alto, ancho)
        if caja is None:
            caja = bbox_roi

        recorte, offset = frame, (0, 0)
        if caja is not None:
            x1, y1, x2, y2 = caja
            recorte = frame[y1:y2, x1:x2]
            offset = (x1, y1)
        if recorte.size == 0:
            return 0.0, []

        conf, cajas = self.motor.detectar(recorte)
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

    def _puede_entrar_diario(self, ahora: float) -> bool:
        """
        Gatilla el cooldown_alarma. Si ya estábamos en DIARIO, siempre se
        puede (solo refresca el latido, no es una alarma nueva). Si es una
        entrada fresca —primera vez, o el diario se sacó y volvió a
        aparecer— solo se permite si ya pasó el tiempo mínimo configurado
        desde la última alarma. Usado tanto por el camino síncrono
        (solo_color) como por resolver_inferencia() (con modelo).
        """
        if self.estado == Estado.DIARIO:
            return True
        return ahora - self.ultima_alarma >= self.cooldown

    def _fusionar(self, conf: float) -> Veredicto:
        return self.fusion.evaluar(
            score_color=self._ultimo_color.score,
            hay_cambio_color=self._ultimo_color.hay_cambio,
            papel=self._ultimo_color.papel,
            conf_modelo=conf,
            umbral_papel=self.color.umbral_papel,
            umbral_modelo=self.motor.umbral,
            nombre=self.nombre,
        )

    def resolver_inferencia(self, conf: float, cajas: list) -> None:
        """Aplica el resultado que devolvió el hilo de inferencia."""
        with self._lock:
            self._cajas_modelo = cajas
            self._conf_ultima = conf
            self._cajas_hasta = time.time() + self.segundos_persistencia

            # Un resultado que llega cuando su chequeo ya se cerró (se
            # recalibró, o se venció el tiempo) solo se muestra: no decide.
            if (self.periodico and not self.modo_continuo
                    and self._ciclo_desde is None):
                return

            veredicto = self._fusionar(conf)
            self._ultimo_veredicto = veredicto

            if self.modo_continuo:
                self.estado = (
                    Estado.DIARIO if veredicto.es_diario else Estado.VIGILANDO
                )
                return

            self._inferencias_ciclo += 1
            if veredicto.es_diario:
                self.confirmaciones += 1
            else:
                self.confirmaciones = max(0, self.confirmaciones - 1)

            ahora = time.time()
            if self.confirmaciones >= self.confirmaciones_necesarias:
                if self._puede_entrar_diario(ahora):
                    self.ultima_alarma = ahora
                    self.estado = Estado.DIARIO
                # si no: seguimos en cooldown, no generamos un nuevo flanco
                # de alarma en el server. self.estado queda como estaba.
                self._cerrar_ciclo(ahora, f"{self.nombre.capitalize()} detectado.")
            elif self._ultimo_color.hay_cambio and not veredicto.modelo_ok:
                # Hay un objeto en la zona, pero no es el que buscamos.
                self.estado = Estado.DESCARTADO
                if self._inferencias_ciclo >= self.confirmaciones_necesarias:
                    self._cerrar_ciclo(
                        ahora, f"Hay algo en la zona, pero no es {self.nombre}."
                    )

    # ---------------------------------------------------------------- público
    def procesar(self, frame: np.ndarray) -> Resultado:
        # Corre en un hilo del pool (server.py: asyncio.to_thread). Todo lo
        # que toca estado compartido con resolver_inferencia() va bajo lock.
        with self._lock:
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

        # --- [0] calibración: aprendemos cómo es la zona vacía ---
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
                f"Calibrando zona vacía… {hechos}/{total}", 0.0,
            )

        # --- [0b] chequeo periódico ---
        if self.periodico:
            if self._ciclo_desde is None:
                # Entre chequeos no se analiza nada; solo se guarda el frame
                # para que el próximo chequeo pueda medir movimiento.
                self.frame_anterior = gris.copy()
                if ahora < self._proximo_chequeo:
                    falta = self._proximo_chequeo - ahora
                    return self._armar(
                        self.estado,
                        f"{self._resultado_chequeo} Próximo chequeo en {falta:.0f}s."
                        .strip(),
                        0.0,
                    )
                self._abrir_ciclo(ahora, gris)
            elif (ahora - self._ciclo_desde > self.max_seg_chequeo
                    and not self.inferencia_activa):
                # No se pudo concluir (había movimiento todo el tiempo).
                # Se conserva el último veredicto y se reintenta más tarde.
                if self.estado not in (Estado.DIARIO, Estado.DESCARTADO):
                    self.estado = Estado.VIGILANDO
                self._cerrar_ciclo(
                    ahora, "Chequeo sin conclusión: había movimiento en la zona."
                )
                return self._armar(self.estado, self._resultado_chequeo, 0.0)

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
            self._cerrar_ciclo(ahora, "Sin cambios en la zona.")
            return self._armar(
                Estado.VIGILANDO, "Sin cambios en la zona.", movimiento
            )

        # En modo solo_color no hay etapa 3: el color decide y listo.
        if not self.usa_modelo:
            veredicto = self._fusionar(0.0)
            self._ultimo_veredicto = veredicto
            if veredicto.es_diario:
                ahora = time.time()
                if self._puede_entrar_diario(ahora):
                    self.ultima_alarma = ahora
                    self.estado = Estado.DIARIO
                # si no: en cooldown, mantenemos el estado anterior (no
                # generamos un nuevo flanco de alarma).
            else:
                self.estado = Estado.DESCARTADO
            explic = veredicto.explicacion
            self._cerrar_ciclo(ahora, explic[:1].upper() + explic[1:] + ".")
            return self._armar(self.estado, veredicto.explicacion, movimiento)

        # --- ya confirmado: no volvemos a molestar al modelo ---
        if self.estado == Estado.DIARIO:
            msg = f"{self.nombre.capitalize()} presente."
            self._cerrar_ciclo(ahora, msg)
            return self._armar(Estado.DIARIO, msg, movimiento)

        # --- mismo objeto descartado que en el chequeo anterior ---
        # (_abrir_ciclo ya lo habría olvidado si la zona hubiera cambiado).
        # Solo al arrancar el chequeo: dentro de uno, DESCARTADO aparece tras
        # la primera inferencia negativa y todavía falta confirmarlo.
        if (self.periodico and self.estado == Estado.DESCARTADO
                and self._inferencias_ciclo == 0):
            msg = f"Sigue el mismo objeto: no es {self.nombre}."
            self._cerrar_ciclo(ahora, msg)
            return self._armar(Estado.DESCARTADO, msg, movimiento)

        # --- [2b] esperamos a que la escena se quede quieta ---
        if self.quieto_desde is None:
            self.quieto_desde = ahora

        estable = ahora - self.quieto_desde
        if estable < self.seg_estabilidad:
            self.estado = Estado.ESTABILIZANDO
            return self._armar(
                Estado.ESTABILIZANDO,
                f"Objeto nuevo (ΔE={self._ultimo_color.delta_e:.0f}). "
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
            proximo_chequeo=round(self.segundos_para_chequeo(time.time()), 1),
        )
