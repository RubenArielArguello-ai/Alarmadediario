# 📋 Estándar de pruebas y evidencias

_Generado automáticamente el 2026-10-09T14:41:19.956Z -- no editar a mano, se sobreescribe en cada publicación._

Esto es **cómo se redacta y se certifica una prueba en este proyecto**. Aplica a quien
desarrolla (etapa `desarrollo`) y a quien hace QA (etapa `integracion`): los dos cargan
Tests, y un Test que no cumpla esto no alcanza para dar nada por entregado.

El objetivo es uno: que cada prueba sea **reproducible por otra persona, verificable
mirando la pantalla, y trazable** entre el código, la documentación y el gestor.

---

## 🧭 1. Regla de oro: inspeccioná la interfaz real. Cero suposiciones

1. **Nunca inventes nombres de botones, menús, modales ni rutas.** Antes de redactar un
   paso a paso, o de dar una prueba por válida, leé el código del frontend (layouts,
   barras de navegación, componentes, vistas) o mirá la pantalla real.
2. **El texto de cada elemento se COPIA de la interfaz, carácter por carácter.** No se
   traduce, no se completa, no se abrevia, no se reordena y no se le cambian las
   mayúsculas. Si el botón dice `+ Usuario`, el paso dice **`+ Usuario`** — con el `+`,
   con esa mayúscula y con ese espacio.

   Escribir "nuevo usuario" porque *significa* lo mismo es el error más común y el más
   caro: quien sigue la prueba busca en pantalla un botón "Nuevo usuario", no lo
   encuentra, y reporta un falso fallo contra una pantalla que funciona perfectamente.
   La prueba se volvió el problema.

   | En la interfaz dice | El paso escribe | |
   |---|---|---|
   | `+ Usuario` | `+ Usuario` | ✅ así |
   | `+ Usuario` | "Nuevo usuario" | ❌ reescrito: ese texto no existe en pantalla |
   | `+ Usuario` | "el botón de alta" | ❌ genérico: no dice qué apretar |
   | `Guardar` | "Guardar cambios" | ❌ completado de más |
   | `Sistema › Configuración › Usuarios` | "ir a configuración de usuarios" | ❌ la ruta es literal, con sus `›` |

3. **Todo literal va entre backticks y se verifica con una búsqueda, no de memoria.** El
   texto que escribiste tiene que aparecer igual en el código del frontend:

   ```bash
   grep -rnF '+ Usuario' src/        # si esto no devuelve nada, el paso está mal escrito
   ```

   Es la verificación más rápida que existe y cierra el agujero entero: un literal que
   no está en el código es, por definición, uno que inventaste.
4. **Botón sin texto (sólo ícono): nombralo por su `aria-label` o su `title`**, que es lo
   que el usuario ve en el tooltip, y aclarás el ícono entre paréntesis — ``el botón
   `Editar` (ícono de lápiz, al final de la fila)``. Un ícono descrito sin su etiqueta
   real ("el lapicito") no se puede buscar en pantalla ni en el código.
5. **Si no pudiste verificar un nombre, no lo escribas.** Decí qué no pudiste ver y por
   qué. Una prueba con un paso inventado es peor que una prueba de menos: la primera
   hace perder el tiempo buscando un botón que no existe.

## 🧩 Contra qué se prueba, en ESTE proyecto

**Este proyecto todavía no tiene entornos cargados**, así que no hay URL contra la
que probar ni para escribir en el Test. Pedísela al Project Manager: los carga en
"Editar Proyecto" → "Entornos de verificación". Mientras no estén, no inventes una
URL ni la pongas en `localhost`: la prueba tiene que poder correrla otra persona.

**Repositorio**: https://github.com/RubenArielArguello-ai/Alarmadediario — rama de integración `dev`.

Los enlaces a la guía visual se escriben con esta forma exacta (el formato es el de
GitHub; con el del otro proveedor el enlace da 404):

```
https://github.com/RubenArielArguello-ai/Alarmadediario/blob/dev/docs/pruebas/<carpeta-de-la-historia>/<CODIGO_REQ>-<nombre>.md#seccion
```

**La URL del gestor (`SCRUM_API_URL`) no está acá a propósito**: sale de tu entorno,
igual que tu API key. Es el lugar a donde se manda la credencial, y este archivo lo
puede editar cualquiera con permiso de push.

---

## 🧪 2. Los cuatro bloques obligatorios de cada Test

Son los cuatro campos que viajan en el `POST`/`PATCH` de `/api/v1/tests`. Ninguno es
decorativo y ninguno se deja en blanco.

### A. Condiciones previas — `preconditions`

- **Acceso y credenciales**: la URL del entorno donde se prueba, el usuario y la clave
  con los que se entra. Escribilos como `Etiqueta: valor` (`DNI: 11111111`,
  `Clave: Prueba1234`): así la app los muestra con un botón para copiarlos, y la URL
  queda clickeable.
- **Rol y permisos**: con qué rol tiene que estar la sesión activa.
- **Dependencias**: qué tiene que existir antes. **Nombrá el Requerimiento del que
  depende por código**, no sólo el dato (`RF-03 mergeado; TC-01 aprobado; paciente base
  creado`).

> Las credenciales de prueba van **acá**, en el Test, que vive en la base del gestor. No
> las commitees en el repositorio: cualquiera con permiso de push las lee.

### B. Descripción / flujo — `description`

- **Enlaces de acceso rápido**, arriba, en dos líneas:
  - `🌐 Probar en:` la URL del entorno más la ruta del módulo.
  - `📄 Guía con capturas:` el enlace al `.md` de la guía visual en el repositorio.
- **Paso a paso, botón por botón**:
  1. La secuencia de navegación por el menú, con los nombres literales.
  2. Qué se aprieta, en orden.
  3. **Los datos exactos** a cargar en cada campo del formulario o modal.

Un paso que diga "completar el formulario" no es un paso: no se puede repetir igual dos
veces, y dos personas van a probar cosas distintas.

### C. Resultado esperado — `expectedResult`

Qué tiene que **verse** y qué tiene que **pasar**: el texto y el color del badge de
estado, la fila que aparece en la tabla, el gráfico o el mapa que se dibuja, el mensaje
de confirmación. Preciso al punto de que alguien que no escribió la prueba pueda decir
"pasó" o "no pasó" sin preguntarte nada.

### D. Evidencia — `evidence`

El enlace al `.md` de la guía visual en el repositorio, con las capturas de la prueba ya
corrida, más una línea de qué se corrió y qué se vio.

**La API rechaza con `400` marcar un Test `Aprobado` o `Fallido` sin `evidence`.** No es
un trámite: marcar Aprobado era la única forma de decir "esto funciona" sin mostrar nada.

---

## 📄 3. La documentación de respaldo en el repositorio

Por cada Historia de Usuario o Requerimiento entregado, dejá en el repositorio:

### 3.1. Dónde va la guía visual: `docs/pruebas/<historia>/<CODIGO_REQ>-<nombre>.md`

**Las guías no van sueltas en `docs/`.** La estructura es siempre esta, tres niveles:

```
docs/
└── pruebas/                             ← todas las pruebas, juntas y separadas del resto
    └── hu-03-plataforma-de-datos/       ← una carpeta por Historia de Usuario
        ├── RF-03-login.md               ← la guía de pruebas de un Requerimiento
        ├── RF-03-entrega.md             ← su documento de entrega (§3.3)
        ├── RF-03-entrega.sh             ← su script del flujo integrado (§3.3)
        ├── RF-04-recuperar-clave.md     ← otro Requerimiento, de la MISMA historia
        └── imagenes/
            ├── RF-03-paso-1.png
            └── RF-03-paso-2.png
```

**La carpeta de la Historia es el segmento del medio de tu rama**: si estás trabajando en
`feature/hu-03-plataforma-de-datos/req-1791168952324-login`, la carpeta es
`hu-03-plataforma-de-datos`. No hay nada que inventar ni que ir a consultar — es el mismo
nombre (código y nombre de la historia, en minúsculas y con guiones) que la app ya usó al
crear la rama.

**El archivo** lleva el código del Requerimiento adelante y su nombre atrás
(`RF-03-login.md`): el código los ordena solos en el listado del directorio. Si en esa
carpeta ya hay otro `.md` con el mismo código — pasa, el código sale de la secuencia y se
puede repetir dentro de una historia — agregale el id del Requerimiento al final.

Por qué así y no como antes: `docs/` es la documentación del producto, y las guías tiradas
ahí al mismo nivel la tapaban. Agrupadas por Historia se leen como lo que son —
**la unidad que se entrega y que el cliente aprueba**: abrís la carpeta de la historia y
tenés sus pruebas y sus capturas completas, sin ir a pescar archivos por prefijo.

> Las guías que ya están sueltas en `docs/` se mudan cuando se vuelva a tocar ese
> Requerimiento, no todas de golpe. Si movés una, **actualizá el `evidence` del Test**: el
> enlace viejo queda roto y ese enlace es la evidencia.

Adentro, la guía tiene:

- **Diagrama de flujo en Mermaid**: el circuito probado de punta a punta.
- **El paso a paso**, para que alguien que no participó recorra el flujo en cinco minutos.
  Cada paso escrito con la terminología **literal** de la UI (§1).
- **Una imagen por paso**, guardada en la carpeta `imagenes/` de esa misma historia, con
  **el elemento de ese paso resaltado** (§3.2) y la pantalla con los datos ya cargados. La
  imagen va inmediatamente debajo del paso que ilustra, no todas juntas al final: quien
  sigue la guía mira el texto y la foto en el mismo movimiento.

> **Si no tenés con qué sacar capturas** (sin navegador automatizable en tu entorno): dejá
> la guía escrita igual, con los pasos literales y el diagrama, marcá con
> `<!-- CAPTURA PENDIENTE: <qué hay que fotografiar> -->` cada lugar donde falta, y pedile
> las imágenes a quien corra la prueba. Lo que **no** se hace es inventar la evidencia ni
> marcar Aprobado sin ella.

### 3.2. El resaltado es obligatorio: sin color, la captura no sirve

**Toda imagen de un paso que manda apretar algo tiene el elemento resaltado en color.** No
es un adorno ni una mejora opcional: una captura de pantalla completa, sin nada marcado, le
deja a quien prueba el trabajo de adivinar cuál de los treinta controles visibles es el del
paso — que es exactamente el trabajo que la guía viene a ahorrar.

**Una guía cuyas capturas no tienen foco se devuelve sin revisar, y un `evidence` que
apunta a esas imágenes no alcanza para marcar `Aprobado`.** Es tan rápido de verificar como
de cumplir: se abre la imagen y el recuadro magenta está o no está.

Y se resalta **antes** de capturar, en la página:

**Prohibido dibujar sobre la captura.** Ni cuadros, ni flechas, ni textos puestos arriba de
la imagen. Es trabajo manual que hay que repetir en cada foto, el recuadro nunca queda
centrado, y a la primera vez que la UI mueve un botón tres píxeles la anotación quedó
apuntando al lugar equivocado — con el agravante de que la imagen *parece* correcta.

**Lo que se hace es resaltar el elemento en la página y recién después capturar.** Se le
agrega una clase al botón que la prueba manda apretar, con una paleta que no existe en la
aplicación, así se distingue de un vistazo que es una marca de la guía y no parte del
producto. El resaltado sale perfectamente ajustado al botón porque **es** el botón, con lo
cual no hay nada que centrar nunca más.

**El CSS ya está en este repositorio**, en `scrumDocs/resaltado-de-capturas.css`: lo publica la app
junto a este documento, así que no hay nada que copiar ni que inventar. Es el mismo archivo
en todos los proyectos — que todas las guías se vean igual es parte del estándar: quien abre
la guía de otro equipo ya sabe qué está mirando. No lo edites, se sobreescribe en cada
publicación. Esto es lo que trae:

```css
/* Resaltado de la guía de pruebas. Magenta y cian a propósito: no son colores de
   producto, así nadie confunde la marca con la interfaz. */
.scrum-qa-foco {
  outline: 4px solid #ff00a8 !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 0 9px rgba(255, 0, 168, 0.25), 0 0 22px 6px rgba(0, 229, 255, 0.55) !important;
  border-radius: 6px !important;
  position: relative !important;
  z-index: 2147483647 !important;   /* por encima de modales y overlays */
}
/* Opcional, cuando la pantalla está muy cargada: apaga el resto para que el foco cante. */
body.scrum-qa-atenuar *:not(.scrum-qa-foco):not(:has(.scrum-qa-foco)) {
  opacity: 0.45 !important;
  filter: grayscale(0.6) !important;
}
```

**Cómo se aplica**, según con qué estés trabajando:

```js
// Playwright / Puppeteer, antes de screenshot()
await page.addStyleTag({ path: 'scrumDocs/resaltado-de-capturas.css' });
await page.locator('button:has-text("Crear")').evaluate(el => el.classList.add('scrum-qa-foco'));
await page.screenshot({ path: 'docs/pruebas/hu-03-plataforma-de-datos/imagenes/RF-03-paso-2.png', fullPage: false });
```

```js
// A mano, desde la consola del navegador (F12), si la captura la saca una persona
document.querySelector('button.btn-primary').classList.add('scrum-qa-foco');
```

Tres reglas del resaltado:

1. **Un solo elemento resaltado por imagen.** Dos focos en la misma foto no dicen qué hay
   que apretar primero. Si el paso toca dos campos y un botón, son tres imágenes o es un
   paso mal cortado.
2. **El selector sale del DOM real**, mirándolo. Es la misma regla de §1 y acá se verifica
   sola: un selector inventado no resalta nada y la captura sale sin foco, lo cual se ve.
3. **No copies el CSS a ningún lado**: referencialo desde `scrumDocs/resaltado-de-capturas.css`, que
   ya está publicado. Una copia por repositorio, puesta por la app, no una por guía.

**Nombre de archivo**: `docs/pruebas/<historia>/imagenes/<CODIGO_REQ>-paso-<n>.png` (ej.
`docs/pruebas/hu-03-plataforma-de-datos/imagenes/RF-03-paso-2.png`). Las imágenes viajan en
la carpeta de su historia, al lado de las guías que las usan (§3.1); el código adelante las
agrupa solas en el listado del directorio, y el número dice a qué paso pertenece sin abrir
nada.

### 3.3. Documento de entrega y su script — en la MISMA carpeta de la Historia

```
docs/pruebas/<historia>/<CODIGO_REQ>-entrega.md     ← qué se entregó
docs/pruebas/<historia>/<CODIGO_REQ>-entrega.sh     ← cómo se vuelve a correr
```

En el `.md`: qué quedó implementado, cómo se levanta y se prueba, qué datos hacen falta, qué
endpoints o pantallas toca, qué quedó afuera o se asumió, los tests unitarios y de
integración en verde, y el enlace a la guía visual — que está **al lado, en la misma
carpeta**. El `.sh` recorre el flujo completo ya integrado, prepara sus datos y los limpia,
y con `--carga N` repite el recorrido midiendo:

```bash
bash docs/pruebas/hu-03-plataforma-de-datos/RF-03-entrega.sh
bash docs/pruebas/hu-03-plataforma-de-datos/RF-03-entrega.sh --carga 200
```

**Antes vivían en `scrumDocs/entregas/`**, lejos de la guía y de las capturas de esa misma
prueba. No había razón: **la evidencia de una Historia es una sola cosa** y se revisa de una
sentada — la guía con las capturas, el documento que dice qué se entregó y el script que lo
vuelve a correr. Ahora es una carpeta, y están los tres juntos: quien valida la Historia
abre una sola y no sale a buscar nada por el repo.

Y hay un segundo motivo, que es el que vuelve a esto una corrección y no un gusto:
**`scrumDocs/` es lo que escribe la app y se sobreescribe en cada publicación**; estos dos
archivos los escribe quien desarrolla. Guardar trabajo a mano en el territorio de lo
generado es pedir que algún día una publicación lo pise. `docs/` es del equipo: es donde van.

> Lo que ya está en `scrumDocs/entregas/` se mueve cuando se vuelva a tocar ese
> Requerimiento, igual que las guías (§3.1) — y la app sigue aceptando que se corra desde
> ahí, así que una entrega vieja no deja de poder validarse.

---

## 🔁 4. Regresión: de lo macro a lo micro, por módulo

Una función nueva no se entrega sólo porque sus propias pruebas pasen: se entrega cuando
**no rompió lo que ya funcionaba**. Esto lo corrés **vos, sin que nadie te lo pida**, como
último paso de la entrega, y con un alcance acotado a propósito: la batería entera del
proyecto es tiempo tirado en código que tu cambio no toca.

El orden es de lo macro a lo micro. Nunca al revés:

1. **Tus pruebas en verde.** Las de etapa `desarrollo` del Requerimiento que acabás de
   implementar. Si alguna falla, no hay regresión que correr todavía.
2. **Identificá el módulo.** El `moduleId` del Requerimiento. Es el radio de la regresión:
   lo que comparte módulo comparte código, datos y pantallas con lo que tocaste.
3. **Corré la integración DE ESE MÓDULO.** Los tests de etapa `integracion` de los
   Requerimientos del mismo módulo, los que tengan `verification.steps`. Son pocos pasos
   HTTP y los corrés con `curl` contra la URL del entorno.
   **No corras los de los otros módulos**: ese es el tiempo que no se quiere perder.
4. **Si todo pasa, terminaste.** Dejá una línea en la `evidence` del Test nuevo diciendo
   qué batería corriste y con qué resultado ("regresión de integración del módulo Turnos:
   6 tests, 6 en verde"). Eso es la constancia de que mirás más allá de tu cambio.
5. **Si algo falla, ahí sí bajás a lo micro.** Y sólo ahí: corré los tests de etapa
   `desarrollo` **del Requerimiento cuyo test de integración se rompió** — no los de todo
   el módulo. Son los que localizan la pieza que se partió, porque prueban cada parte
   aislada. El que falle nombra qué hay que arreglar.
6. **Lo que se rompió se registra.** Marcá `Fallido` **con evidencia** el test de
   integración que se cayó (es un hecho, no una opinión), nombralo por código en el
   documento de entrega, y arreglalo si está en tu alcance. Si no lo está, decilo: un
   Requerimiento que entrega sabiendo que rompió otro módulo y no lo dice es la peor
   entrega posible.
7. **Volvé al paso 1** después de cada arreglo.

### Lo que hace posible todo esto

**Dejá tus tests de `integracion` con `verification.steps` cargados.** Un test de
integración escrito sólo en prosa no lo puede correr nadie automáticamente: queda esperando
a que una persona lo lea y lo repita a mano, y en la práctica no se corre nunca. Los pasos
son método + URL + body, encadenables con `{{paso.campo}}`; con eso, **el próximo que toque
tu módulo re-prueba lo tuyo sin saber nada de tu código** — que es exactamente lo que vos
querés que pase cuando el que toca el módulo es otro.

## 🚀 5. El circuito, en orden

1. **Desarrollo y pruebas automatizadas.** La suite del proyecto, al 100% en verde.
2. **Evidencias reales.** Entrá al entorno desplegado y capturá las pantallas de la
   solución funcionando. No valen maquetas ni capturas de otra versión.
3. **Commit y push** del código, las imágenes y los `.md` en la rama de integración.
4. **Sincronización con el gestor.** `PATCH /api/v1/tests/<TEST_ID>` con tu propia key,
   actualizando `preconditions`, `description`, `expectedResult`, `evidence` y el
   `status`.

El orden importa: el `PATCH` va **último**, cuando los enlaces que escribís en el Test ya
existen en el repositorio. Un `evidence` que apunta a un archivo todavía no pusheado es un
enlace roto para el que lo abra.
