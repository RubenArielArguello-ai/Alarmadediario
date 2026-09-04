# Project Manager — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-04T13:56:21.040Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. El procedimiento paso a paso está en
`.claude/skills/pm-sync/SKILL.md`.

## En una línea

Sos el dueño del proyecto: definís el contenido, configurás el repositorio y los entornos,
gestionás las cuentas de tu equipo y sos el único que promueve a producción. **Cubrís a
todos los demás roles**, así que el 403 casi nunca es tu problema — el tuyo es decidir qué
hacer vos y qué delegar.

## Tu lugar en el circuito

Estás en las dos puntas: al principio, definiendo el alcance (Historias, Requerimientos,
Módulos, Entregas) y, al final, promoviendo `testing → main` y desplegando. En el medio
conviene dejar trabajar a los demás: si hacés vos el merge a `dev`, el Scrum Master se
entera del estado del equipo por el tablero y no por su propia tarea.

## Cómo arranca un proyecto (el orden importa)

1. **Creá el proyecto** en la web y conectale el repositorio (GitHub o GitLab) y su rama
   por defecto. Sin repositorio no hay ramas, ni PRs, ni publicación de documentos.
2. **Configurá los entornos** (`PUT /projects/[id]/environments`): las URLs de dev, testing
   y producción son las que usa la verificación de pruebas.
3. **Sumá a tu equipo** y generá **una API key por persona**, desde "Usuarios Activos".
   Nunca compartas la tuya: la key **es** el rol, y la de un PM deja hacer todo.
4. **Cargá el alcance**: Historias de Usuario y sus Requerimientos, con estimación y
   dependencias.
5. **Apretá "Publicar"**: eso deja en el repositorio del proyecto los documentos y los
   skills, incluido este que estás leyendo. Recién ahí la IA de cada integrante puede
   trabajar contra la app desde su IDE.
6. **Repetí el paso 5 cuando cambie el alcance.** Los cuatro documentos derivados
   (plan, Historias, Requerimientos, grafo) se republican solos en cada cambio; los skills
   y los documentos de rol, no.

## Qué escribís del Requerimiento

**Campos que podés escribir** con `PATCH /api/v1/requirements/[id]`:

`name` · `description` · `type` · `status` · `assignee` · `estimated` · `real` · `observations` · `dependencies` · `position` · `start` · `end` · `rescheduleFromEstimate` · `moduleId` · `progress` · `aiGenerated` · `deliveryId` · `approvalStatus`

**Estados que podés fijar a mano**: `to_do` · `doing` · `pr_open`.

El bloqueo nunca entra por `PATCH`, ni para ponerlo ni para sacarlo: va por `POST`/`DELETE` de `/requirements/[id]/block`, que exigen motivo escrito.

**Los otros cuatro estados no los fija nadie a mano**, porque son consecuencia de un hecho y no una decisión:

- `merged_dev` — sale de mergear el Pull Request: POST /api/v1/requirements/<id>/merge, o el botón "Mergear a dev" del tablero
- `in_testing` — sale de promover la rama `dev` a `testing`: POST /api/v1/projects/<id>/promote
- `tested` — lo fijan los Tests del Requerimiento cuando pasan en testing
- `in_production` — sale de promover `testing` a la rama de producción: POST /api/v1/projects/<id>/promote

Un `PATCH` con cualquiera de esos cuatro responde 400. Si el proyecto no tiene repositorio configurado se permite igual (no hay git que pueda contradecir al tablero); y si lo tiene y hay que forzarlo —el PR se mergeó por afuera, el webhook nunca llegó— hay que mandar `motivoManual` con la explicación, que queda en el registro de actividad.

## Los Requerimientos operacionales

El trabajo real que no nace de una Historia de Usuario también se carga y se agenda:
levantar la VM donde corre `testing` para que QA valide, la de `tested` para mostrarle el
avance al cliente, o la máquina de producción donde va a correr `main` con su dominio y su
certificado. También capacitaciones, auditorías y reuniones.

Lo creás vos o el Scrum Master (al Product Owner la API le contesta 403), con el mismo
endpoint que una Historia y `kind: "operacional"`:

```bash
cat > /tmp/cuerpo.json <<'JSON'
{
  "kind": "operacional",
  "name": "Preparar la máquina de producción",
  "description": "Dominio, certificado, variables de entorno y backups para la rama main.",
  "estimated": "8h",
  "assignee": "jlopez",
  "deliveryId": "DEL-3"
}
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

- **Nace con su primer Requerimiento adentro**: `estimated` y `assignee` van a ese hijo, que
  es el que se ve en el Kanban y en el Grafo. Para sumarle más tareas, colgale otro
  Requerimiento con `POST /api/v1/user-stories/$CONTENEDOR_ID/requirements`.
- **Se numera `RO-01`, `RO-02`… por proyecto**; sus hijos llevan código de Requerimiento
  normal (`RF-NN`). Desde la 029 *operacional* es el `kind` del contenedor, no un `type`.
- **`deliveryId` es tuyo** (el Scrum Master no lo puede setear): un operacional puede cerrar
  una Entrega igual que cualquier otro trabajo — la demo al cliente **es** la entrega.
- **Usalo como dependencia.** Una promoción a `testing` que espera una máquina que nadie
  levantó tiene que estar dibujada como dependencia, no vivir en la cabeza de alguien.

## Tus endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `DELETE` | `/api/v1/deliveries/[id]` | Borrar una Entrega. |
| `GET` | `/api/v1/me` | Quién sos: id, username, rol y los proyectos de los que sos miembro. Es la primera llamada de cualquier skill. |
| `DELETE` | `/api/v1/modules/[id]` | Borrar un Módulo. |
| `GET` | `/api/v1/projects/[id]` | Datos del proyecto: nombre, repositorio, rama por defecto, guía de estilo. |
| `GET` | `/api/v1/projects/[id]/deliveries` | Las Entregas comprometidas con el cliente y su fecha. |
| `POST` | `/api/v1/projects/[id]/deliveries` | Crear una Entrega comprometida con el cliente. |
| `GET` | `/api/v1/projects/[id]/environments` | Las URLs de los entornos (dev, testing, producción) para verificar pruebas contra el que corresponda. |
| `PUT` | `/api/v1/projects/[id]/environments` | Configurar las URLs de los entornos del proyecto. |
| `GET` | `/api/v1/projects/[id]/members` | El equipo del proyecto con el rol de cada uno. Es de dónde sale el `assignee` al repartir. |
| `GET` | `/api/v1/projects/[id]/modules` | Los Módulos del proyecto. |
| `POST` | `/api/v1/projects/[id]/modules` | Crear un Módulo para agrupar Requerimientos. |
| `POST` | `/api/v1/projects/[id]/promote` | Promover la rama entera de un entorno al siguiente: `dev → testing` o `testing → main`. `dev → testing` lo hacen QA y el PM; `testing → main`, sólo el PM. El pase a producción se rechaza si queda algo sin testear (`force` es del PM y queda logueado). |
| `POST` | `/api/v1/projects/[id]/publish` | Publicar la documentación del proyecto en el repositorio. _(sesión web, no API key)_ Usa la cookie de la app: desde el IDE con API key responde 401. Se aprieta el botón "Publicar" en la web. |
| `GET` | `/api/v1/projects/[id]/publish/preview` | Ver qué documentos cambiaron antes de publicarlos. _(sesión web, no API key)_ |
| `GET` | `/api/v1/projects/[id]/requirements` | Todos los Requerimientos del proyecto con su estado, asignado, estimación y dependencias. |
| `GET` | `/api/v1/projects/[id]/user-stories` | Historias de Usuario y contenedores operacionales, con sus Requerimientos colgando. |
| `POST` | `/api/v1/projects/[id]/user-stories` | Crear una Historia de Usuario (`kind: "historia"`) o un **Requerimiento operacional** (`kind: "operacional"`): el trabajo real que no nace de una Historia — levantar la VM donde va a correr `testing`, preparar la de producción, una capacitación, una auditoría, una reunión con el cliente. El Product Owner sólo `historia`; el **Scrum Master sólo `operacional`**; el PM las dos. El operacional nace con su primer Requerimiento adentro, así que `estimated` y `assignee` del cuerpo van a ese hijo. |
| `DELETE` | `/api/v1/requirements/[id]` | Borrar un Requerimiento. |
| `PATCH` | `/api/v1/requirements/[id]` | Editar un Requerimiento: mover la tarjeta, asignar, estimar, anotar observaciones, agendar. Qué campos podés tocar depende del rol, y el developer sólo sobre lo que tiene asignado. Ver la sección "Campos" de este documento. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `POST` | `/api/v1/requirements/[id]/merge` | Integrar a `dev` el PR de un Requerimiento que está en `pr_open`. Decide por estado: los ya integrados responden 200 idempotente, el resto 409. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de un Requerimiento, con su estado y su resultado. |
| `POST` | `/api/v1/requirements/[id]/tests` | Crear un Test de un Requerimiento. |
| `DELETE` | `/api/v1/tests/[id]` | Borrar un Test. |
| `PATCH` | `/api/v1/tests/[id]` | Editar un Test o marcar su resultado. |
| `DELETE` | `/api/v1/user-stories/[id]` | Borrar una Historia de Usuario o un Requerimiento operacional con todo lo que cuelga. Mismo reparto por `kind` que el POST. |
| `PATCH` | `/api/v1/user-stories/[id]` | Editar una Historia de Usuario o un Requerimiento operacional. Mismo reparto por `kind` que el POST. Renombrar un operacional que tiene un solo hijo le propaga el nombre. Los campos de ejecución (fechas, Entrega) los escribe sólo el PM. |
| `POST` | `/api/v1/user-stories/[id]/requirements` | Crear un Requerimiento dentro de una Historia de Usuario **o dentro de un contenedor operacional** (la segunda y siguientes tareas de ese operacional). El Scrum Master lo crea con los campos que puede escribir; el contenido (nombre, descripción, tipo) es del PM. |

## Lo único que no podés

| Querés | Te contesta | Quién |
|---|---|---|
| Abrir la rama de un Requerimiento | 403 | el developer, y sólo él. Es lo que arranca el reloj |
| Crear otra cuenta de Project Manager | 403 | el admin. Un PM no puede dar de alta un PM |
| Ajustar el tiempo real de una tarjeta | no existe el campo | nadie: sale de los hechos de git |

**Los cuatro estados de consecuencia no los fija nadie a mano, vos tampoco**: `merged_dev`
sale del merge del PR, `in_testing` e `in_production` de `/promote`, `tested` de los Tests.
Un `PATCH` con cualquiera de ellos responde 400. Con el proyecto sin repositorio
configurado se permite igual, y con repositorio se puede forzar mandando `motivoManual`, que
queda registrado. El tablero no puede afirmar lo que git no respalda, y tu rol no es la
excepción: es el que más lo mira.

## Promover a producción

```bash
cat > /tmp/cuerpo.json <<'JSON'
{ "from": "testing", "to": "main" }
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/promote" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Se rechaza si queda algún Requerimiento en `in_testing`: git arrastra la rama entera, así
que promover con pruebas pendientes haría que el tilde de producción mienta. `force: true`
existe, es sólo tuyo y queda anotado en el registro de actividad como `PROMOTE_FORCED` —
usalo cuando sepas por qué, no para saltear el aviso.
