---
name: sm-sync
description: Ayuda al Scrum Master (o al Project Manager, mismo alcance de API) a coordinar la ejecución de un proyecto en Scrum Master AI desde este repo -- repartir Requerimientos entre developers, agendarlos (estimación, dependencias, fechas), mergear a `dev` las ramas con Pull Request abierto, crear un Requerimiento nuevo, dar de alta Requerimientos **operacionales** (la VM donde va a correr testing o producción, una capacitación, una auditoría), y bloquear/destrabar los que tienen un impedimento. No redacta contenido (nombre/descripción/tipo de un Requerimiento, eso es del Project Manager o del Product Owner) ni toca Historias de Usuario, Tests, ramas de git, promociones de entorno ni publicación de documentos. Usar cuando el usuario pide "coordinar el equipo", "repartir requerimientos", "asignar developers", "agendar", "mergear a dev", "integrar los PR abiertos", "bloquear/destrabar un requerimiento", "crear un requerimiento" (como Scrum Master), "levantar la máquina de testing", "cargar la preparación del servidor", "crear un operacional", o corre /sm-sync explícitamente.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(curl *)
  - Write
---

# /sm-sync — Coordinar la ejecución como Scrum Master

El Scrum Master coordina la ejecución de un proyecto en Scrum Master AI: decide quién
trabaja qué Requerimiento, lo agenda (estimación, dependencias, fechas), integra a `dev`
las ramas que ya tienen Pull Request abierto, da de alta un Requerimiento cuando hace
falta uno que no existía, y saca los impedimentos que bloquean el trabajo de alguien. Todo
vía `/api/v1/*` -- para no tener que entrar a la web a hacerlo a mano.

**Este skill no redacta contenido.** `name`, `description` y `type` de un Requerimiento son
del Project Manager (o del Product Owner en el caso de las Historias de Usuario, con
`/po-sync`); acá sólo se coordina la ejecución de Requerimientos que ya existen, o se crea
uno nuevo sin tocar su redacción más allá de lo mínimo para darlo de alta. Tampoco toca
Historias de Usuario, Tests, ramas de git (las crea el propio developer con `/dev-sync`),
promociones de entorno (`testing`→`main`, del Project Manager) ni publicación de documentos.

Antes de escribir nada, viene la tabla de lo que la API deja hacer -- **verificada contra
el código real**, no contra lo que este documento diga en otro lado si alguna vez
diverge:

| Qué | Endpoint | 403 si... |
|---|---|---|
| Ver el equipo del proyecto | `GET /api/v1/projects/$PROJECT_ID/members` | no sos miembro de ese proyecto |
| Ver las Entregas del proyecto | `GET /api/v1/projects/$PROJECT_ID/deliveries` | no sos miembro de ese proyecto |
| Asignar y agendar un Requerimiento | `PATCH /api/v1/requirements/$REQUIREMENT_ID` | no sos miembro del proyecto; o mandás `name`, `description`, `type`, o cualquier otro campo de ejecución que no es tuyo (`real`, `observations`, `position`, `moduleId`, `aiGenerated`, `rescheduleFromEstimate`): el 403 nombra el campo que sobra |
| Mergear a `dev` | `POST /api/v1/requirements/$REQUIREMENT_ID/merge` | no sos Scrum Master ni Project Manager, o no sos miembro del proyecto (y `409` si el Requerimiento no está en `pr_open` -- `to_do`/`doing`/`blocked` no tienen nada pendiente para mergear) |
| Crear un Requerimiento | `POST /api/v1/user-stories/$USER_STORY_ID/requirements` | no sos Scrum Master ni Project Manager, o no sos miembro del proyecto |
| Bloquear un Requerimiento | `POST /api/v1/requirements/$REQUIREMENT_ID/block` | no sos miembro del proyecto; o mandás `"esRechazo":true` sin ser Scrum Master ni Project Manager |
| Destrabar un Requerimiento | `DELETE /api/v1/requirements/$REQUIREMENT_ID/block` | no sos miembro del proyecto |

**Sobre bloquear/destrabar**: no son dos rutas distintas -- es el mismo recurso
`/api/v1/requirements/$REQUIREMENT_ID/block`, `POST` lo pone y `DELETE` lo saca. No existe
un endpoint `/unblock`.

Argumentos: `$ARGUMENTS`. Cinco modos, el primero de la lista que matchee gana:
- **`repartir`** → asignar Requerimientos sin developer a uno del equipo.
- **`agendar`** → estimar, ordenar dependencias y fechar Requerimientos.
- **`integrar`** (default si `$ARGUMENTS` está vacío) → listar los Requerimientos en
  `pr_open` y mergearlos a `dev` de a uno, con confirmación.
- **`crear <descripción>`** → dar de alta un Requerimiento nuevo.
- **`destrabar`** → revisar los Requerimientos bloqueados y sacarles el impedimento.

---

## 0. Identidad y credenciales (aplica a los seis modos)

- `SCRUM_API_KEY` — variable de entorno. Si no está seteada: explicar que hay que
  pedírsela al Project Manager (la genera desde "Usuarios Activos" en la app; sólo la ve
  una vez al generarla, así que si se perdió hay que pedirle que la rote) y exportarla en
  el shell (`export SCRUM_API_KEY=sk_...`), y parar acá. **Nunca** escribir esta key a
  ningún archivo del repo.
- `SCRUM_API_URL` — la base de la instancia (ej. `https://scrum.tudominio.com`). **No es
  secreta y no hay que preguntarla todavía**: se resuelve en el paso 1 leyendo el manifest
  del repo. Sólo si el manifest tampoco la tiene se llega a pedírsela al usuario.

Todas las llamadas a la API llevan `-H "Authorization: Bearer $SCRUM_API_KEY"`.

**El cuerpo de todo POST/PATCH va en JSON estricto**: comillas dobles en claves y valores,
sin comas colgando. `{'name': 'x'}` y `{name: "x"}` no son JSON y la API los rechaza con
`400 {"error":"JSON invalido"}` -- eso es el cuerpo, **no** la key ni el rol, así que no
regeneres la key ni cambies de endpoint. Como los textos de este dominio traen apóstrofes,
comillas y saltos de línea, escribilos a un archivo y mandalo con `-d @archivo.json` en vez
de pegarlos dentro de `-d '...'`: es lo único que no depende del quoting del shell. Los
saltos de línea dentro de un valor van como `\n`, nunca literales. La referencia completa
está en `scrumDocs/SCRUM_MASTER_AI.md`, paso 5.

## 1. Leer o inicializar el manifest (aplica a los seis modos)

Leer `scrumDocs/sm-manifest.json` en la raíz del repo. Si no está ahí pero existe
`docs/sm-manifest.json` (ubicación anterior a `scrumDocs/`), leerlo de ahí y reescribirlo
ya en `scrumDocs/sm-manifest.json` — el archivo viejo se deja donde está, no se borra.

Si no existe en ninguno de los dos lugares, crearlo:

```json
{
  "apiUrl": null,
  "projectId": null,
  "lastSyncAt": null
}
```

- **`apiUrl`**: a diferencia de la key, no es secreta — vive commiteada en el repo. Si el
  archivo ya la trae, usarla tal cual y no volver a preguntar. Si falta, antes de
  preguntarle nada al usuario, revisar si existe `scrumDocs/SCRUM_MASTER_AI.md` — el Project
  Manager la publica ahí ya resuelta (`SCRUM_API_URL es <url>`) porque el servidor la saca
  sola de su propia URL pública; si está, usar ese valor. Sólo si ninguna de las dos
  fuentes la tiene, preguntarle la URL al usuario. En cualquier caso, guardarla en el
  manifest para que el resto del equipo no tenga que repetirla nunca.
- **`projectId`**: si falta, no preguntarlo a ciegas todavía — se resuelve en el paso 1.5
  contra los proyectos que devuelve `/api/v1/me`.

Este archivo es sólo trazabilidad de sesión (URL, proyecto, última corrida) -- a diferencia
del manifest de `/dev-sync` o `/po-sync`, este skill no crea contenido que necesite
recordar de dónde salió, así que no lleva `mappings`. Recomendarle al usuario commitearlo
al repo (no tiene secretos, sólo IDs y la URL).

## 1.5. Confirmar identidad y rol (aplica a los seis modos)

```bash
curl -s "$SCRUM_API_URL/api/v1/me" -H "Authorization: Bearer $SCRUM_API_KEY"
```

- `401` → la key es inválida o fue revocada. Avisar al usuario que le pida al Project
  Manager que le genere una nueva, y parar.
- `200` → `{ id, username, email, role, projects: [{ id, name }, ...] }`. Esto es lo que
  determina el rol de verdad — **nunca preguntarle al usuario "qué rol sos" ni asumirlo**,
  el rol de la cuenta dueña de la key es el único que importa (y la API lo vuelve a
  validar en cada llamada de todos modos, así que confiar en otra cosa acá no cambiaría
  nada salvo dar un error más tarde y más confuso).
  - Si `role` no es `scrum_master` ni `project_manager`, avisar que esta key no
    corresponde a este skill y derivar al que sí: `/dev-sync` para `developer`,
    `/po-sync` para `product_owner`, `/qa-sync` para `qa`. No sugerir seguir adelante con
    `sm-sync` en ninguno de esos casos.
  - Si el manifest no tenía `projectId`: si `projects` trae un solo elemento, usar ese
    `id` directamente sin preguntar; si trae varios, listarlos y preguntar cuál; si viene
    vacío, avisar que el Project Manager todavía no agregó a este usuario a ningún
    proyecto, y parar. Guardar el `projectId` elegido en el manifest.

---

## Tres trampas de los campos que escribís

**Qué campos podés escribir y qué endpoints tenés está en `scrumDocs/roles/scrum-master.md`**,
generado desde `lib/permisos.ts`: no se repite acá para que no haya dos verdades. Lo que sí
va acá es lo que ese documento no puede saber, porque es procedimiento:

- **`assignee` va por `username`, nunca por `id`.** El servidor resuelve
  `SELECT id FROM users WHERE username = $1`: si le mandás un `id` no resuelve a nadie, el
  `UPDATE` conserva el asignado anterior y responde `200` -- no hay error que lo delate. La
  única verificación real es releer el `assignee` de la respuesta y confirmar que cambió al
  que pediste. Es el corazón del modo `repartir`.
- **`blocked` no entra por `PATCH`**, ni para ponerlo ni para sacarlo: un
  `"status":"blocked"`, o cambiar el `status` de algo que ya está `blocked`, devuelve `409`.
  Va por `POST`/`DELETE` de `/api/v1/requirements/$REQUIREMENT_ID/block` (modo `destrabar`),
  que además exige el motivo y congela/reanuda el reloj.
- **`progress` no se manda a mano.** Se calcula desde los Tests (`aprobados / total`), pero
  ese cálculo sólo viaja en las respuestas de `/api/*` (el tablero web); las de `/api/v1/*`
  -- todas las que este skill lee -- devuelven el valor crudo guardado. Un `progress` que
  mandes sobrevive en lo que este skill relee, dando la sensación de que funcionó, mientras
  el tablero muestra otra cosa (y **`0`** si el Requerimiento no tiene Tests).

**El estado no es la forma de integrar.** `merged_dev` sale de mergear el Pull Request —el
modo `integrar` de este skill, o el botón "Mergear a dev" del tablero— y un `PATCH` con ese
estado responde 400. Igual `in_testing`, `tested` e `in_production`. Si el PR se mergeó por
afuera o el webhook nunca llegó, mandá `motivoManual` con la explicación: queda en el
registro de actividad a tu nombre. En un proyecto sin repositorio configurado se permite sin
motivo, porque ahí no hay git que pueda contradecir al tablero.

---

## Dispatch según `$ARGUMENTS`

### 2. Traer el equipo y los Requerimientos del proyecto (aplica a todos los modos)

```bash
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/members" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

- `401` → key inválida o revocada. Avisar y parar.
- `403` → la key es válida pero el usuario no pertenece a ese proyecto. Avisar que
  confirme el `projectId`, y parar.
- `200` en ambas → equipo trae `{ id, username, role }` por miembro; Requerimientos trae
  `{ id, code, userStoryId, name, description, type, status, assignee, assigneeId, ... }`
  (`assignee` es el username, o el string `"Unassigned"` si no tiene; `status` es el
  estado Kanban: `to_do`/`doing`/`blocked`/`pr_open`/`merged_dev`/`in_testing`/`tested`/
  `in_production`). Guardar ambas listas en memoria.

### `repartir` — asignar Requerimientos sin developer

1. De la lista del paso 2, filtrar los Requerimientos con `assignee: "Unassigned"` (o con
   un `assigneeId` que ya no aparece en el equipo del paso 2 -- gente que salió del
   proyecto).
2. Para cada uno, proponer un developer del equipo con criterio (carga de trabajo actual:
   cuántos Requerimientos `to_do`/`doing` ya tiene asignados cada developer del equipo;
   preferí el que tenga menos). Si hay empate real, preguntarle al usuario.
3. Confirmarle al usuario la propuesta completa (Requerimiento → developer) antes de
   escribir nada -- a diferencia de un PATCH que sólo toca `observations` o `progress`,
   reasignar mueve trabajo de una persona a otra.
4. Con la confirmación, para cada uno:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"assignee":"nombre.de.usuario"}
   JSON
   curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
5. Resumen final: qué se asignó y a quién, qué quedó sin asignar por falta de un developer
   disponible (avisar, no forzar una asignación al azar).

### `agendar` — estimar, ordenar dependencias y fechar

1. De la lista del paso 2, identificar los Requerimientos sin estimación (`estimated`
   vacío) o con `dependencies` que no reflejan lo que el usuario describe.
2. Para cada uno que el usuario quiera agendar, armar el PATCH con sólo los campos que
   cambian:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"estimated":"3d","dependencies":["REQ-1700000000000"],"start":"2026-08-25","end":"2026-08-28"}
   JSON
   curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   - `dependencies` es una lista de `id` de otros Requerimientos del mismo proyecto -- el
     servidor valida que existan y que no arme un ciclo (`400` con el detalle si falla; no
     reintentar con otro shape, es el grafo el que está mal).
   - No mandes `progress` acá (ver la nota de la sección anterior): lo que escribas
     sobrevive en lo que releés por `/api/v1`, pero el tablero web siempre muestra
     `aprobados/total` -- `0` si todavía no tiene Tests -- así que tu valor no se ve
     reflejado ahí.
3. Resumen final: qué Requerimientos quedaron agendados y con qué valores, cuáles no se
   pudieron agendar por una dependencia inválida.

### `integrar` (default) — mergear a `dev` los Pull Request abiertos

Este es el modo central: `dev` es donde se integra lo que cada developer ya probó a su
nivel, y el Scrum Master es quien decide cuándo entra.

1. De la lista del paso 2, filtrar los Requerimientos con `status: "pr_open"`.
2. Si no hay ninguno, avisar y terminar -- no hay nada para integrar.
3. Para cada uno, **antes de mergear, confirmarle al usuario** código + nombre del
   Requerimiento y a quién está asignado -- un merge escribe en el repositorio del cliente
   y no se deshace con otra corrida de este skill.
4. Con la confirmación:
   ```bash
   curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/merge" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   ```
   - `200` → mergeado, o confirmado. Si la respuesta trae `"yaEstabaMergeado":true`, no se
     tocó el proveedor: o el Requerimiento ya estaba integrado a `dev` (o más adelante) y
     no había nada que mergear, o el Pull Request ya se había mergeado por otro lado (la
     app, el propio proveedor) y el servidor sólo confirmó el estado -- ninguno de los dos
     casos es un error.
   - `409` → o el proyecto todavía no tiene configurado el repositorio, o el Requerimiento
     no está en `pr_open`: todavía no pidió el merge, o quedó `blocked` -- por un review que
     pidió cambios (el PR sigue abierto pero con código rechazado) o por un test que falló
     después de integrar (ahí el PR se mergeó hace rato). En ninguno de los casos hay algo
     para mergear. Avisar con el estado real que trae el mensaje de error y seguir con el
     resto de la lista, no reintentar este.
   - Cualquier otro error de la API del proveedor (permisos del token, conflicto de
     merge) llega tal cual en `{"error": "..."}` -- mostrarlo, no reinterpretarlo, y no
     reintentar sin que el usuario resuelva la causa (normalmente en GitHub/GitLab
     directamente).
5. Resumen final: cuántos Requerimientos se mergearon a `dev`, cuáles quedaron pendientes
   (sin PR, o con error del proveedor) y por qué.

### `crear <descripción>` — dar de alta un Requerimiento nuevo

Igual alcance que el paso 4.5 de `/dev-sync` para el developer, pero corrido por el
Scrum Master.

1. **Resolver a qué Historia de Usuario cuelga**, comparando la descripción contra `name`
   + `description` + `acceptanceCriteria` de las Historias de Usuario del proyecto
   (`GET /api/v1/projects/$PROJECT_ID/user-stories`, con el mismo manejo de `401`/`403`
   que el paso 2). Si no hay ninguna Historia razonable, **no la inventes** -- avisar que
   hace falta que el Product Owner (o el Project Manager) cargue esa Historia primero, y
   no crear el Requerimiento suelto.
2. **Confirmarle al usuario, antes de llamar a la API**: nombre propuesto, tipo
   (`funcional`/`no_funcional`) y bajo qué Historia va a quedar -- a diferencia de
   reasignar o reagendar (reversibles con otra corrida), crear un Requerimiento de más
   ensucia el backlog y sólo el Project Manager puede borrarlo después.
3. Con la confirmación:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"name":"...","description":"...","type":"funcional"}
   JSON
   curl -s -X POST "$SCRUM_API_URL/api/v1/user-stories/$USER_STORY_ID/requirements" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   - `201` → creado, con `code` (`RF-...`/`RNF-...`) asignado por la API. El Requerimiento
     nace con el tag de quién lo armó -- no hace falta "visarlo" aparte, eso ya no existe.
   - `403` → no debería pasar si el paso 1.5 confirmó el rol, pero si pasa, no
     reintentar: revisar que la key no haya sido rotada a otro rol entre medio.
4. Resumen final: qué Requerimiento se creó, con qué código y bajo qué Historia.

### `operacional <descripción>` — dar de alta trabajo que no nace de una Historia

Levantar la VM donde va a correr `testing` para que QA valide, la de `tested` para
mostrarle el avance al cliente, preparar la máquina de producción donde corre `main` con su
dominio y su certificado, una capacitación, una auditoría, una reunión. **Crearlos es tuyo y
del Project Manager**: al Product Owner la API le contesta 403.

Es un contenedor propio, no cuelga de ninguna Historia de Usuario — por eso va por otro
endpoint que el modo `crear`.

1. **Confirmarle al usuario** nombre, qué incluye, estimación y a quién se lo asignás.
   Borrarlo después es sólo del Project Manager.
2. Con la confirmación:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {
     "kind": "operacional",
     "name": "Levantar la VM de testing",
     "description": "Instancia con Docker y el proxy, apuntando la rama testing, para que QA valide la tanda antes de mostrarla.",
     "estimated": "6h",
     "assignee": "jlopez"
   }
   JSON

   curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   - `201` → devuelve el contenedor. **Nace con su primer Requerimiento adentro**, y ese
     hijo es el que se ve en el Kanban y en el Grafo: por eso `estimated` y `assignee` van
     al hijo y no al contenedor.
   - `403 "Sólo el Project Manager o el Scrum Master pueden crear Requerimientos
     operacionales"` → la key no es de ninguno de los dos roles. No es el cuerpo.
3. **Si el operacional tiene varias tareas**, colgale las que faltan al contenedor que
   acabás de crear (una por tarea: "instalar Docker", "configurar el proxy", "cargar las
   variables de entorno"):
   ```bash
   curl -s -X POST "$SCRUM_API_URL/api/v1/user-stories/$CONTENEDOR_ID/requirements" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   Con un solo hijo, renombrar el contenedor le propaga el nombre; con dos o más, cada uno
   conserva el suyo.
4. **Enganchalo como dependencia de lo que lo necesita**, con el modo `agendar`: si la
   tanda que va a `testing` depende de esa VM, el Requerimiento que se prueba ahí lleva el
   operacional en `dependencies`. Es la mitad del valor de cargarlo: una promoción que
   espera una máquina que nadie levantó pasa a ser un bloqueo visible en el Grafo en vez de
   una nota en la cabeza de alguien.

### `destrabar` — revisar y sacar impedimentos

1. De la lista del paso 2, filtrar los Requerimientos con `status: "blocked"`.
2. Si no hay ninguno, avisar y terminar.
3. Para cada uno, mostrarle al usuario el motivo del bloqueo (`blockedReason`) y quién lo
   bloqueó/quién es el responsable de destrabarlo, si la API los trae en la respuesta del
   paso 2. Preguntar cuáles ya están resueltos.
4. Para los que el usuario confirme:
   ```bash
   curl -s -X DELETE "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/block" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   ```
   - `200` → destrabado, vuelve al estado en que estaba antes de bloquearse (o a `doing`
     si el bloqueo había sido un rechazo). El reloj se reanuda solo si ese estado es
     `doing`.
   - `409` → ya no estaba bloqueado (alguien más lo destrabó, o la lista del paso 2 estaba
     desactualizada) -- refrescarla y seguir.
5. Si en cambio hace falta **bloquear** uno nuevo (el usuario lo pide directo, no es el
   flujo por defecto de este modo pero la misma ruta lo permite):
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"reason":"...","ownerId":null,"esRechazo":false}
   JSON
   curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/block" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   - `reason` es obligatorio (`400` si falta o viene vacío) -- un bloqueo sin explicación
     no se puede levantar después sin volver a preguntar de qué se trataba.
   - `ownerId` (opcional) tiene que ser un `id` de alguien del equipo del paso 2 -- otro
     id devuelve `400`.
   - `esRechazo:true` es "esto no está listo, hay que retrabajarlo": suma al contador de
     rechazos y, al destrabarse, la tarjeta vuelve a `doing` en vez de continuar donde
     estaba. Es lo mismo que dispara un review pidiendo cambios -- sólo Scrum Master y
     Project Manager pueden marcarlo (`403 rechazo_ajeno` si otro rol lo intenta).
6. Resumen final: qué Requerimientos se destrabaron y a qué estado volvieron, cuáles
   siguen bloqueados y por qué motivo.

---

## Notas de implementación

- Nunca reintentar con otro shape de body si la API devuelve `403` al tocar un campo que
  no es de este rol (`name`/`description`/`type`, o un campo de ejecución que no está en
  la lista de arriba) -- ese rechazo es intencional (ver `EXECUTION_FIELDS`/
  `CAMPOS_POR_ROL` en `lib/permisos.ts`), no un error a esquivar.
- Nunca crear un Requerimiento (modo `crear`) sin haberle confirmado antes al usuario
  nombre, tipo e Historia de Usuario destino, y sin haber recibido una confirmación
  explícita.
- Nunca mergear (modo `integrar`) sin confirmación explícita por Requerimiento -- un merge
  escribe en el repositorio del cliente y no lo deshace otra corrida de este skill.
- Nunca inventar una Historia de Usuario para colgar un Requerimiento nuevo -- si no hay
  ninguna razonable, avisar y no crear el Requerimiento suelto.
- `status: "blocked"` nunca se pone ni se saca con `PATCH` -- siempre `POST`/`DELETE`
  `/api/v1/requirements/$REQUIREMENT_ID/block`. Un intento de hacerlo por `PATCH` da
  `409`, no es un bug a reportar.
- `progress` no hace falta mandarlo -- lo que escribas sólo sobrevive en las respuestas de
  `/api/v1` (las que este skill lee); el tablero web siempre muestra `aprobados/total`,
  y `0` si el Requerimiento todavía no tiene Tests.
- Si `$SCRUM_API_URL` tiene un `/` final, quitarlo antes de concatenar rutas.
- Todas las respuestas de error de la API vienen como `{"error": "..."}` -- mostrar ese
  mensaje tal cual, no reinterpretarlo.
- `scrumDocs/sm-manifest.json` es propio de este skill -- no confundirlo ni fusionarlo con
  `scrumDocs/scrum-manifest.json` (developer) ni `scrumDocs/po-manifest.json` (Product
  Owner/Project Manager), que guardan trazabilidad de contenido que este skill no crea.
