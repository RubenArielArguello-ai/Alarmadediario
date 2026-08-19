# Alarma de Diario — detector híbrido

Une los dos proyectos en un solo programa: la **diferencia de color sobre la
alfombra** decide *si apareció algo*, y **OWLv2** decide *si eso es un diario*.

Nada del proyecto original se modificó. `detect_diario.py`, `harness/run_eval.py`
y el workflow de CI siguen exactamente como los dejó el otro equipo; todo lo
nuevo vive en esta carpeta.

---

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r hibrido/requirements.txt
python hibrido/descargar_modelo.py     # ~620 MB, una sola vez
```

Los pesos quedan en `hibrido/modelos/` y están en `.gitignore`: no van al repo.
Después de bajarlos, todo funciona sin internet.

## Uso

**Con cámara, interfaz web:**

```bash
python hibrido/server.py
```

Abrí <http://localhost:8000>. Dibujá la zona de la alfombra, dejala vacía unos
segundos para que calibre, y listo.

**Sin cámara, comparando dos fotos:**

```bash
python hibrido/cli.py --fondo sin_diario.jpg --actual con_diario.jpg
```

Agregá `--comparar` para correr también el `detect_diario.py` original y ver los
dos resultados lado a lado.

**Evaluación automática:**

```bash
python harness/run_eval_hibrido.py                # rápido, solo color
python harness/run_eval_hibrido.py --con-modelo   # pipeline completo
```

---

## Cómo funciona

```
frame de cámara
     |
[1] movimiento (gris, ~1 ms)
     |   ¿alguien está pasando? -> esperar, no decidir nada
     v
[2] diferencia de color (LAB, ~5 ms)
     |   ¿apareció algo sobre la alfombra? ¿parece papel?
     |   si no ve nada, acá se corta y el modelo nunca se despierta
     v
[3] OWLv2 (~1-30 s según resolución)
     |   ¿eso que hay ahí es un diario?
     |   recibe SOLO el recorte que marcó el color, no el frame entero
     v
[4] fusión -> veredicto -> N confirmaciones seguidas -> ALARMA
```

La premisa, igual que en el proyecto original: **el diario no se mueve**.
Mientras hay movimiento no se decide nada, porque es una persona pasando. Recién
cuando la escena se queda quieta *y* además cambió respecto de la alfombra
vacía, tiene sentido preguntar.

### Validador 1 — color (`validador_color.py`)

El detector original comparaba en **escala de grises**. El problema es que en
gris una sombra y un diario se parecen demasiado. Este compara en espacio
**LAB**, que separa la luz (L) del color (a, b), y eso habilita dos cosas:

- **Descartar sombras.** Una sombra baja L pero casi no mueve a/b. Un objeto
  nuevo cambia el tono, o aclara la zona. La regla es: si se oscureció *sin*
  cambiar de tono, es sombra. (Configurable con `ignorar_sombras`; ponelo en
  `false` si tu alfombra es blanca.)
- **Medir si parece papel.** Score 0-1 que mezcla tres señales: poca saturación
  (el papel es acromático, una toalla roja no), buen brillo (el papel refleja
  más que casi cualquier alfombra) y mucho contraste interno (el texto impreso
  genera negros sobre blanco). Se mide **solo sobre los píxeles que cambiaron**,
  no sobre el rectángulo entero: un diario enrollado ocupa menos de la mitad de
  su bounding box y el resto es alfombra, que ensucia las tres medidas.

### Validador 2 — OWLv2 (`modelo.py`)

Detector de vocabulario abierto: acepta descripciones en texto libre
(`"a rolled newspaper"`) y devuelve cajas, sin entrenar nada. Se puede cambiar
qué busca desde la UI, en caliente.

### Fusión (`fusion.py`)

| modo | qué hace | cuándo usarlo |
|---|---|---|
| `cascada` | el color filtra, el modelo decide. El modelo **solo corre** si el color vio algo | **default**. Lo más barato y lo que menos falsos positivos da |
| `and` | los dos tienen que coincidir | igual de estricto, pero el modelo corre siempre |
| `or` | con que uno diga que sí, alcanza | más sensible, más falsos positivos |
| `ponderado` | promedio pesado de los dos scores | si querés que una señal fuerte compense a la otra |
| `solo_color` | apaga OWLv2 | equivale al proyecto original, pero en color |
| `solo_modelo` | apaga la validación de color | para medir cuánto aporta el color |

Se cambia desde la UI o con `python hibrido/server.py --modo and`.

---

## Qué gana cada uno con el otro

**El color le recorta la escena al modelo.** En vez de mandarle el frame
entero, le manda solo la región que cambió, con un margen. El objeto pasa a
ocupar casi todo el cuadro y la confianza sube muchísimo:

| entrada a OWLv2 | resolución | confianza |
|---|---|---|
| foto entera | 960 (nativa, lenta) | 0.62 |
| foto entera | 640 | 0.32 |
| **recorte del validador de color** | **640** | **0.90** |

Medido sobre la foto real de la entrada. Es decir: con el recorte, a 640 se
obtiene *mejor* confianza que con la foto entera a 960, y bastante más rápido.

**El modelo tapa los falsos positivos del color.** El validador de color no
distingue un diario de una caja, un zapato o un paquete. Cuando el color dice
"apareció algo" pero el modelo dice "no es un diario", el sistema pasa al estado
`descartado` en vez de disparar la alarma.

## Resultados del harness

`python harness/run_eval_hibrido.py` (sin `--con-modelo`) — 4/4, precisión 1.00,
recall 1.00:

| caso | espera | ΔE | papel | resultado |
|---|---|---|---|---|
| diario sobre la alfombra | sí | 55.0 | 0.78 | detecta |
| solo una sombra | no | 0.0 | — | descarta |
| objeto rojo saturado | no | 90.3 | 0.21 | descarta (cambió mucho, pero no es papel) |
| misma escena + ruido de sensor | no | 0.0 | — | descarta |

El caso del objeto rojo es el interesante: el color cambió muchísimo (ΔE 90) y
aun así no dispara, porque el score de papel queda en 0.21 contra un umbral de
0.35.

**Ojo con este número: valida solo el validador de color, no el pipeline
híbrido completo.** Sin `--con-modelo`, `run_eval_hibrido.py` fuerza el modo de
fusión a `solo_color` y OWLv2 nunca se instancia. Los 4 casos son sintéticos
(generados en código, no fotos reales) porque `data/pares/` no existe en el
repo. "1.00 / 1.00" es un buen resultado de regresión para la parte de color,
pero no es evidencia de que la fusión con el modelo funcione — para eso hay que
correr `--con-modelo` y, mejor todavía, agregar pares de fotos reales en
`data/pares/`. Como referencia, sí probamos la fusión completa (los 4 modos:
`cascada`, `and`, `or`, `ponderado`) con OWLv2 real sobre fotos reales de la
entrada — ver "Verificación" más abajo.

---

## Ajustes

Todo está en `config.json`, comentado con claves `_nota`. Los que más importan:

- `color.delta_e_minimo` (16) — cuánto tiene que cambiar el color. ΔE 2.3 es lo
  mínimo que ve el ojo; por debajo de 10 es ruido de sensor.
- `color.papel_minimo` (0.35) — cuán "papel" tiene que parecer. Diario real: 0.59.
  Objeto rojo: 0.21.
- `modelo.confianza_minima` (0.37) — **los scores de OWLv2 no son
  probabilidades calibradas**. Ruido hasta 0.05, diario 0.32–0.90 según recorte
  y resolución. No lo subas de 0.5 o deja de detectar.
- `deteccion.confirmaciones_necesarias` (2) — veredictos positivos seguidos
  antes de disparar.

## Estados

| estado | significa |
|---|---|
| `calibrando` | aprendiendo cómo es la alfombra vacía (15 frames, se usa la mediana para que una persona que cruce no arruine la referencia) |
| `vigilando` | todo normal |
| `movimiento` | algo se mueve, no se decide nada |
| `estabilizando` | apareció algo, esperando que se quede quieto |
| `verificando` | consultando al modelo |
| `diario` | confirmado por los dos validadores → alarma |
| `descartado` | hay un objeto sobre la alfombra, pero no es un diario |

## Salidas

- `hibrido/capturas/` — foto anotada de cada alarma (cian = color, verde = modelo)
- `hibrido/capturas/detecciones.csv` — una fila por alarma con las dos señales
- webhook a n8n — desactivado por defecto; se prende en `config.json`
  (`webhook.activo`). Es el mismo endpoint que usaba `detect_diario.py`.

## Verificación (rama `fix/hibrido-robustez`)

Se corrigieron dos bugs reales encontrados en revisión de código, y se
verificó todo con ejecuciones reales (no solo lectura), sobre `detector.py`:

**1. `cooldown_alarma` no frenaba nada.** El estado pasaba a `diario` sin
mirar el cooldown; solo se usaba para decidir si actualizar el reloj interno.
Si el diario se sacaba y se volvía a poner (o alguien probaba el sistema
moviéndolo), cada ciclo disparaba una alarma nueva sin importar el tiempo
mínimo configurado. Afectaba **dos** caminos del código: el de
`resolver_inferencia()` (con modelo) y el síncrono de `solo_color` — cada uno
tenía su propia copia del bug. Se centralizó en `_puede_entrar_diario()` y se
verificó con un test que simula: aparece el diario (alarma 1) → se retira → 
reaparece enseguida (NO debe generar alarma 2, sigue en cooldown) → se espera
el cooldown → reaparece (ahora sí, alarma 2). Resultado: `2 alarmas nuevas`,
como se esperaba.

**2. Estado compartido sin lock entre hilos.** `procesar()` corre en un hilo
del pool (`asyncio.to_thread`, llamado en cada frame) mientras
`resolver_inferencia()` se llama desde el loop de eventos cuando termina una
inferencia que corrió en OTRO hilo. Los dos leían y escribían `self.estado`,
`self.confirmaciones`, `self._ultimo_color`, etc. sin ninguna sincronización.
Se agregó un `threading.RLock()` que protege ambos caminos, dejando **fuera**
del lock la parte lenta (la inferencia de OWLv2 en sí, que puede tardar varios
segundos) para no bloquear la captura de video.

**Integración color + modelo**, probada con OWLv2 real sobre las fotos reales
de la entrada, en los 4 modos de fusión:

| modo | estado | color_ok | modelo_ok | confianza | cajas |
|---|---|---|---|---|---|
| `cascada` | diario | sí | sí | 0.81 | 2 |
| `and` | diario | sí | sí | 0.81 | 2 |
| `or` | diario | sí | sí | 0.81 | 2 |
| `ponderado` | diario | sí | sí | 0.83 (0.35·color + 0.65·modelo) | 2 |

Y sobre la foto vacía (repetida, sin objeto nuevo): `estado=vigilando`, sin
alarma, en los 4 modos.

## Límite conocido

La etapa de movimiento sigue usando escala de grises con un umbral fijo de 25,
heredada del proyecto original. Es barata y alcanza para lo que hace, pero no ve
un objeto que tenga la misma luminancia que la alfombra aunque sea de otro
color. No es un problema en la práctica porque la etapa 2 sí lo ve —
simplemente ese frame no se marca como "movimiento".
