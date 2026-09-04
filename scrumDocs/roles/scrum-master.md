# Scrum Master — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-04T13:56:22.182Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. El procedimiento paso a paso está en
`.claude/skills/sm-sync/SKILL.md`.

## En una línea

Repartís el trabajo, lo agendás, integrás a `dev` lo que ya pidió el merge, y destrabás lo
que está bloqueado. **No escribís código y no tocás git a mano**: el merge lo hace la app
con el token del Proyecto.

## Tu lugar en el circuito

```
to_do → doing → pr_open ──merge──▶ merged_dev │ in_testing → tested → in_production
└── el developer ─────┘  └── vos ──────────┘  └── QA ──────┘ └── Project Manager ─┘
```

Antes de eso está tu otra mitad, que no se ve en el tablero: decidir **quién** hace qué y
**en qué orden**, con las dependencias resueltas.

## Qué escribís del Requerimiento

**Campos que podés escribir** con `PATCH /api/v1/requirements/[id]`:

`assignee` · `status` · `deliveryId` · `estimated` · `dependencies` · `start` · `end` · `progress`

**Estados que podés fijar a mano**: `to_do` · `doing` · `pr_open`.

El bloqueo nunca entra por `PATCH`, ni para ponerlo ni para sacarlo: va por `POST`/`DELETE` de `/requirements/[id]/block`, que exigen motivo escrito.

**Los otros cuatro estados no los fija nadie a mano**, porque son consecuencia de un hecho y no una decisión:

- `merged_dev` — sale de mergear el Pull Request: POST /api/v1/requirements/<id>/merge, o el botón "Mergear a dev" del tablero
- `in_testing` — sale de promover la rama `dev` a `testing`: POST /api/v1/projects/<id>/promote
- `tested` — lo fijan los Tests del Requerimiento cuando pasan en testing
- `in_production` — sale de promover `testing` a la rama de producción: POST /api/v1/projects/<id>/promote

Un `PATCH` con cualquiera de esos cuatro responde 400. Si el proyecto no tiene repositorio configurado se permite igual (no hay git que pueda contradecir al tablero); y si lo tiene y hay que forzarlo —el PR se mergeó por afuera, el webhook nunca llegó— hay que mandar `motivoManual` con la explicación, que queda en el registro de actividad.

Fijate lo que no está en esa lista: `name`, `description` y `type` son del Project Manager
(el contenido no lo definís vos), y `observations` es de quien ejecuta (reporta lo que
hizo, y vos no ejecutás). Un PATCH con esos campos contesta 403 nombrándolos.

## Integrar a `dev`

El developer deja la tarjeta en `pr_open` (**⏳ PR abierto**) y ahí se queda: significa "de
mi lado está listo, falta que lo mergeen". El merge **no lo hace el developer**, y no hace
falta entrar al repositorio:

```bash
curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/merge" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

Mergea el Pull Request y deja la tarjeta en `merged_dev` (**✓ dev**) en la misma llamada.
No hay PATCH que mandar después, y no queda ninguna ventana donde el tablero afirme algo
que el repositorio todavía no respalda.

Lo que no es un error: `409` si el Requerimiento no está en `pr_open` — nadie pidió el
merge, o el review pidió cambios y quedó `blocked` —, y `{"yaEstabaMergeado": true}` si el
PR ya había entrado, así que reintentar es inofensivo.

Lo mismo se hace desde la web sin escribir ningún curl: la tarjeta en "Hecho / Dev" trae el
botón **"✓ Marcar mergeado a dev"**.

## Que el tablero no mienta

El síntoma típico es un Requerimiento con trabajo real hecho y la tarjeta parada en
`to_do`. Casi siempre es la misma causa: **nunca se abrió la rama**, así que el webhook no
tuvo qué mover. Se arregla en el repo donde está el código, no en el tablero: el developer
corre `/dev-sync siguiente` sobre ese Requerimiento, que abre la rama y deja el primer
push. Mover la tarjeta a mano tapa el síntoma y además deja el reloj en cero para siempre.

El otro reporte que te va a llegar del developer es **trabajo que apareció fuera del
alcance de su Requerimiento** ("para terminar el login hacía falta el dashboard, que no está
en ninguna tarjeta"). Él no lo puede crear —la API le da 403— así que la tarjeta que falta
la creás vos, y ahí decidís si va en esta tanda o después. Que te lo reporte en vez de
escribirlo de contrabando es lo que hace que el tablero siga sirviendo.

Antes de repartir, mirá tres cosas: qué está en `blocked` y hace cuánto, qué está en
`pr_open` esperando integración, y qué Requerimiento sin asignar todavía no tiene sus
dependencias resueltas. Ese último no se reparte: se agenda.

## Los Requerimientos operacionales son tuyos

Es la mitad del trabajo de un proyecto que no aparece en ninguna Historia de Usuario, y
**crearlo es tuyo y del Project Manager, de nadie más** (`kind: "operacional"`; al Product
Owner la API le contesta 403). Lo típico:

- **Levantar la VM donde va a correr `testing`** para que QA pruebe contra algo real, o la
  de `tested` para mostrarle el avance al cliente sin tocar producción.
- **Preparar la máquina de producción** donde va a correr `main`: dominio, certificado,
  variables de entorno, backups.
- Una capacitación, una auditoría, una reunión con el cliente, una validación del PO.

Sin esto, ese trabajo se cargaba inventando una Historia de Usuario que no describe a ningún
usuario, o directamente no se cargaba y no lo veía nadie.

```bash
cat > /tmp/cuerpo.json <<'JSON'
{
  "kind": "operacional",
  "name": "Levantar la VM de testing",
  "description": "Instancia con Docker y el proxy, apuntando la rama testing. Sirve para que QA valide la tanda antes de mostrarla.",
  "estimated": "6h",
  "assignee": "jlopez"
}
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Cuatro cosas que conviene saber antes de mandarlo:

1. **Nace con su primer Requerimiento adentro.** El contenedor agrupa, el hijo ejecuta: por
   eso `estimated` y `assignee` del cuerpo van al hijo, y es el hijo el que se ve en el
   Kanban y en el Grafo. Un operacional sin hijo no aparecería en ninguna de las dos vistas.
2. **El contenedor se numera `RO-01`, `RO-02`… por proyecto**, y sus hijos llevan código de
   Requerimiento normal (`RF-NN`): desde la migración 029 *operacional* es el `kind` del
   contenedor, no un `type` de Requerimiento. Nombralos por su código cuando le reportes al
   usuario.
3. **Para sumarle más tareas al mismo operacional**, colgale otro Requerimiento con
   `POST /api/v1/user-stories/$CONTENEDOR_ID/requirements` (por ejemplo: "instalar Docker",
   "configurar el proxy", "cargar las variables de entorno" adentro de "VM de testing").
4. **Mientras tenga un solo hijo, renombrar el contenedor le renombra el hijo.** Con dos o
   más, cada hijo conserva su nombre.
5. **Es dependencia como cualquier otro Requerimiento**, y ahí está la mitad del valor:
   poné la VM de testing como `dependencies` del primer Requerimiento que haya que probar
   ahí, y el tablero deja de mentir sobre qué se puede empezar. Un despliegue que espera una
   máquina que nadie levantó es un bloqueo real, no una nota suelta.

El `deliveryId` (colgar el operacional de una Entrega) es del Project Manager: si lo mandás
vos, se ignora.

## Tus endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/api/v1/me` | Quién sos: id, username, rol y los proyectos de los que sos miembro. Es la primera llamada de cualquier skill. |
| `GET` | `/api/v1/projects/[id]` | Datos del proyecto: nombre, repositorio, rama por defecto, guía de estilo. |
| `GET` | `/api/v1/projects/[id]/deliveries` | Las Entregas comprometidas con el cliente y su fecha. |
| `GET` | `/api/v1/projects/[id]/environments` | Las URLs de los entornos (dev, testing, producción) para verificar pruebas contra el que corresponda. |
| `GET` | `/api/v1/projects/[id]/members` | El equipo del proyecto con el rol de cada uno. Es de dónde sale el `assignee` al repartir. |
| `GET` | `/api/v1/projects/[id]/modules` | Los Módulos del proyecto. |
| `POST` | `/api/v1/projects/[id]/modules` | Crear un Módulo para agrupar Requerimientos. |
| `POST` | `/api/v1/projects/[id]/publish` | Publicar la documentación del proyecto en el repositorio. _(sesión web, no API key)_ Usa la cookie de la app: desde el IDE con API key responde 401. Se aprieta el botón "Publicar" en la web. |
| `GET` | `/api/v1/projects/[id]/requirements` | Todos los Requerimientos del proyecto con su estado, asignado, estimación y dependencias. |
| `GET` | `/api/v1/projects/[id]/user-stories` | Historias de Usuario y contenedores operacionales, con sus Requerimientos colgando. |
| `POST` | `/api/v1/projects/[id]/user-stories` | Crear una Historia de Usuario (`kind: "historia"`) o un **Requerimiento operacional** (`kind: "operacional"`): el trabajo real que no nace de una Historia — levantar la VM donde va a correr `testing`, preparar la de producción, una capacitación, una auditoría, una reunión con el cliente. El Product Owner sólo `historia`; el **Scrum Master sólo `operacional`**; el PM las dos. El operacional nace con su primer Requerimiento adentro, así que `estimated` y `assignee` del cuerpo van a ese hijo. |
| `PATCH` | `/api/v1/requirements/[id]` | Editar un Requerimiento: mover la tarjeta, asignar, estimar, anotar observaciones, agendar. Qué campos podés tocar depende del rol, y el developer sólo sobre lo que tiene asignado. Ver la sección "Campos" de este documento. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `POST` | `/api/v1/requirements/[id]/merge` | Integrar a `dev` el PR de un Requerimiento que está en `pr_open`. Decide por estado: los ya integrados responden 200 idempotente, el resto 409. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de un Requerimiento, con su estado y su resultado. |
| `DELETE` | `/api/v1/user-stories/[id]` | Borrar una Historia de Usuario o un Requerimiento operacional con todo lo que cuelga. Mismo reparto por `kind` que el POST. |
| `PATCH` | `/api/v1/user-stories/[id]` | Editar una Historia de Usuario o un Requerimiento operacional. Mismo reparto por `kind` que el POST. Renombrar un operacional que tiene un solo hijo le propaga el nombre. Los campos de ejecución (fechas, Entrega) los escribe sólo el PM. |
| `POST` | `/api/v1/user-stories/[id]/requirements` | Crear un Requerimiento dentro de una Historia de Usuario **o dentro de un contenedor operacional** (la segunda y siguientes tareas de ese operacional). El Scrum Master lo crea con los campos que puede escribir; el contenido (nombre, descripción, tipo) es del PM. |

## Lo que NO podés, y a quién pedírselo

| Querés | Te contesta | Se lo pedís a |
|---|---|---|
| Cambiar nombre, descripción o tipo | 403 nombrando los campos | el Project Manager |
| Escribir `observations` | 403 | el developer asignado |
| Borrar un Requerimiento | 403 | el Project Manager |
| Abrir la rama de un Requerimiento | 403 | el developer, y sólo él |
| Promover `dev → testing` | 403 | QA o el Project Manager |
| Promover a producción | 403 | el Project Manager |
| Crear una Historia de Usuario | 403 | el Product Owner o el PM (vos sí creás contenedores `operacional`) |

**`merged_dev` no se pone a mano, y ya no se puede.** Es el resultado de mergear el Pull
Request: lo escribe el webhook, o la ruta `/merge` cuando el proveedor confirma. Un `PATCH`
con `merged_dev` responde 400 nombrando la ruta correcta. Lo mismo con `in_testing`,
`tested` e `in_production`, que salen de `/promote` y de los Tests.

No es desconfianza en el rol: es que el tablero no puede afirmar un merge que en git no
existe. Si el PR se mergeó por afuera o el webhook nunca llegó, el camino es mandar
`motivoManual` con la explicación —queda registrada con tu nombre en la actividad— o, si el
proyecto no tiene repositorio configurado, fijarlo a mano sin más, porque ahí no hay git que
pueda contradecir al tablero.
