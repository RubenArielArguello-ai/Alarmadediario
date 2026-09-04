---
name: dev-sync
description: Sincroniza lo implementado en este repo con los Requerimientos de un proyecto en Scrum Master AI — lee la documentación local, decide con criterio qué requerimientos quedaron cubiertos, y actualiza esos Requerimientos y sus Tests vía la API. Si algo documentado no matchea ningún Requerimiento existente, puede crear uno nuevo (sólo con key de Project Manager, con confirmación explícita) colgado de la Historia de Usuario que corresponda. Mantiene el trabajo dentro del alcance del Requerimiento tomado: si aparece algo que corresponde a otra tarjeta, lo nombra y ofrece tomarla en vez de implementarla de contrabando. También puede decidir sola cuál es el siguiente Requerimiento a encarar leyendo el plan publicado en la rama principal, y dejar la rama/commit/push listos, moviendo la tarjeta a `doing` al arrancar y a `pr_open` al terminar. Usar cuando el usuario pide "sincronizar con scrum", "reportar al scrum master", "actualizar requerimientos", "crear un requerimiento", "avisarle al scrum lo que hice", "qué sigue", o corre /dev-sync explícitamente.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(curl *)
  - Bash(git *)
  - Write
---

# /dev-sync — Reportar avance a Scrum Master AI

Lee lo que este repo ya documenta como implementado, lo compara contra los Requerimientos
del proyecto en Scrum Master AI, y actualiza esos mismos Requerimientos/Tests vía la API
`/api/v1/*` — para que el programador no tenga que reportar nada a mano. El Requerimiento
es la unidad atómica (RF-01, RNF-01, etc.): no hay ningún nivel intermedio tipo
"Funcionalidad". La mayoría de las veces se actualiza un Requerimiento que ya existe (lo
cargó el Product Owner); si algo documentado no matchea ninguno, este skill también puede
crear el que falta (ver paso 4.5), colgado de la Historia de Usuario que corresponda, con
confirmación explícita del usuario antes de cada alta. También puede decidir cuál es el
siguiente Requerimiento a encarar.

**Qué podés escribir y qué endpoints tenés está en `scrumDocs/roles/developer.md`**, generado desde el código del servidor. Este skill es el procedimiento; si los dos se
contradicen, manda el documento del rol.

**Lo que se implementa es lo que describe el Requerimiento tomado, y nada más.** Si en el
medio aparece trabajo que corresponde a otro Requerimiento (el caso típico: terminaste el
login y seguís con el dashboard), ese trabajo **no se escribe en esta rama**: se nombra por
código y se ofrece tomarlo después. Ver el paso 3.5 y el chequeo previo al Pull Request.

**El tiempo real trabajado (`real_time`) no se arranca ni se para con un botón.** Lo mueve
el estado del Requerimiento: corre mientras está en `doing` y se congela al salir de ahí.
Ese estado cambia por dos caminos equivalentes — el push/PR que reporta el webhook o la
GitHub Action, y el PATCH que manda este skill. Los dos son idempotentes: reponer `doing`
sobre algo que ya estaba en `doing` no reinicia el reloj.

Argumentos: `$ARGUMENTS`. Dos formas:
- **(vacío) o una ruta** → sincronizar documentación (comportamiento por defecto, ver
  sección "Sincronizar documentación" más abajo). Si se pasa una ruta, se usa esa en vez
  de `docs/`.
- **`siguiente`** → decidir cuál Requerimiento encarar ahora, crear/retomar su rama y
  dejar el primer commit (o el de retoma) pusheado.

---

## 0. Identidad y credenciales (aplica a las dos formas)

- `SCRUM_API_KEY` — variable de entorno. Si no está seteada: explicar que hay que
  pedírsela al admin del proyecto (la genera desde "Gestión de Accesos" en la app) y
  exportarla en el shell (`export SCRUM_API_KEY=sk_...`), y parar acá. **Nunca** escribir
  esta key a ningún archivo del repo.
- `SCRUM_API_URL` — la base de la instancia (ej. `https://scrum.tudominio.com`). **No
  es secreta y no hay que preguntarla todavía**: se resuelve en el paso 1 leyendo el
  manifest del repo. Sólo si el manifest tampoco la tiene se llega a pedírsela al
  usuario.

Todas las llamadas a la API llevan `-H "Authorization: Bearer $SCRUM_API_KEY"`.

**El cuerpo de todo POST/PATCH va en JSON estricto**: comillas dobles en claves y valores,
sin comas colgando. `{'name': 'x'}` y `{name: "x"}` no son JSON y la API los rechaza con
`400 {"error":"JSON invalido"}` -- eso es el cuerpo, **no** la key ni el rol, así que no
regeneres la key ni cambies de endpoint. Como los textos de este dominio traen apóstrofes,
comillas y saltos de línea, escribilos a un archivo y mandalo con `-d @archivo.json` en vez
de pegarlos dentro de `-d '...'`: es lo único que no depende del quoting del shell. Los
saltos de línea dentro de un valor van como `\n`, nunca literales. La referencia completa
está en `scrumDocs/SCRUM_MASTER_AI.md`, paso 5.

## 1. Leer o inicializar el manifest (aplica a las dos formas)

Leer `scrumDocs/scrum-manifest.json` en la raíz del repo. Si no está ahí pero existe `docs/scrum-manifest.json` (ubicación anterior a `scrumDocs/`), leerlo de ahí y reescribirlo ya en `scrumDocs/scrum-manifest.json` — el archivo viejo se deja donde está, no se borra.

Si no existe en ninguno de los dos lugares, crearlo:

```json
{
  "apiUrl": null,
  "projectId": null,
  "lastSyncAt": null,
  "mappings": []
}
```

- **`apiUrl`**: a diferencia de la key, no es secreta — vive commiteada en el repo.
  Si el archivo ya la trae, usarla tal cual y no volver a preguntar. Si falta, antes de
  preguntarle nada al usuario, revisar si existe `scrumDocs/SCRUM_MASTER_AI.md` — el Project
  Manager la publica ahí ya resuelta (`SCRUM_API_URL es <url>`) porque el servidor la saca
  sola de su propia URL pública; si está, usar ese valor. Sólo si ninguna de las dos
  fuentes la tiene, preguntarle la URL al usuario. En cualquier caso, guardarla en el
  manifest para que el resto del equipo (developer/PO/QA que clonen este mismo repo) no
  tenga que repetirla nunca.
- **`projectId`**: si falta, no preguntarlo a ciegas todavía — se resuelve en el paso 1.5
  contra los proyectos que devuelve `/api/v1/me`.

Este archivo es el estado de trazabilidad — no decide qué existe (eso ya lo sabe la API,
los Requerimientos los crea el Project Manager), pero guarda `sourceRef` para que una
relectura futura entienda por qué se marcó cubierto cada Requerimiento. Recomendarle al
usuario commitearlo al repo (no tiene secretos, sólo IDs y la URL).

## 1.5. Confirmar identidad y rol (aplica a las dos formas)

```bash
curl -s "$SCRUM_API_URL/api/v1/me" -H "Authorization: Bearer $SCRUM_API_KEY"
```

- `401` → la key es inválida o fue revocada. Avisar al usuario que le pida al admin que
  le genere una nueva, y parar.
- `200` → `{ id, username, email, role, projects: [{ id, name }, ...] }`. Esto es lo que
  determina el rol de verdad — **nunca preguntarle al usuario "qué rol sos" ni asumirlo**,
  el rol de la cuenta dueña de la key es el único que importa (y la API lo vuelve a
  validar en cada llamada de todos modos, así que confiar en otra cosa acá no cambiaría
  nada salvo dar un error más tarde y más confuso).
  - Si `role` no es `developer` ni `project_manager`, avisar que esta key no corresponde a
    este skill (`/po-sync` es para `product_owner`, `/qa-sync` para `qa`) y
    sugerir el skill correcto en vez de seguir adelante.
  - Si el manifest no tenía `projectId`: si `projects` trae un solo elemento, usar ese
    `id` directamente sin preguntar; si trae varios, listarlos y preguntar cuál; si viene
    vacío, avisar que el Project Manager todavía no agregó a este usuario a ningún
    proyecto, y parar. Guardar el `projectId` elegido en el manifest.

---

## Dispatch según `$ARGUMENTS`

### Sin argumentos, o una ruta — sincronizar documentación

#### 2. Traer las Historias de Usuario y los Requerimientos del proyecto

```bash
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

- `401` → la key es inválida o fue revocada. Avisar al usuario que le pida al admin
  que le genere una nueva, y parar.
- `403` → la key es válida pero el usuario dueño no pertenece a ese proyecto. Avisar
  que confirme el `projectId` con el admin, y parar.
- `200` en ambas → Historias de Usuario trae `{ id, code, name, description,
  acceptanceCriteria, ... }` (hace falta para el paso 4.5, si hay que crear un
  Requerimiento nuevo). Requerimientos trae `{ id, code, userStoryId, name, description,
  type, status, ... }` (`type` es `funcional` o `no_funcional`; `status` es el estado
  Kanban actual: `to_do`/`doing`/`blocked`/`pr_open`/`merged_dev`/`in_testing`/`tested`/`in_production`). Guardar ambas listas en
  memoria, son la base contra la que se va a razonar en el paso siguiente.

#### 3. Leer la documentación local y decidir qué requerimiento cubre cada cosa

Leer `$ARGUMENTS` si se pasó una ruta explícita (si no existe, avisar y no asumir
`docs/` en su lugar); si no hay argumento, leer todo `docs/`; si `docs/` no existe,
leer `README.md`.

**Esto es el corazón del skill y es un trabajo de criterio, no de matching de texto.**
No busques que el nombre del requerimiento aparezca literal en el doc. Leé la
documentación como lo haría un humano familiarizado con el proyecto: entendé qué
funcionalidad describe cada sección/endpoint/feature documentado, y decidí — comparando
contra la `description` de cada requerimiento, no sólo el `name` — cuáles quedaron
cubiertos. Si tenés dudas razonables sobre un match, es preferible dejarlo afuera
(reportarlo como "sin cobertura clara" en el resumen final) a inventar una relación —
distinto es cuando estás razonablemente seguro de que no matchea ningún Requerimiento
existente porque genuinamente no estaba trackeado: eso es candidato al paso 4.5, no
"cobertura dudosa".

Para cada match, quedate con una referencia corta a la fuente (`sourceRef`, ej.
`docs/api.md#POST /login` o `README.md#Autenticación`) — se guarda en el manifest y
sirve para que una relectura futura entienda por qué se marcó cubierto.

#### 4. Actualizar el Requerimiento cubierto

Para cada requerimiento con match, actualizarlo directamente (ya existe, normalmente
lo cargó el Product Owner):

**Este modo reporta avance: el estado que corresponde es `doing`, no `pr_open`.**

```bash
cat > /tmp/cuerpo.json <<'JSON'
{"status":"doing","observations":"<qué se encontró implementado y dónde (sourceRef)>"}
JSON
curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

- **`pr_open` se manda DESPUÉS de abrir el Pull Request, nunca para reportar avance.** No
  es una convención: `pr_open` **congela el reloj**. Mandarlo con trabajo todavía por
  delante -- los tests que faltan escribir, la documentación, las correcciones -- para el
  cronómetro mientras el trabajo sigue, y todo lo que venga después se pierde: el tiempo
  real de esa tarjeta pasa a decir menos de lo que costó, para siempre. Si el Requerimiento
  ya está terminado de verdad, el camino es el modo `siguiente` desde el paso 5.5: chequeo
  de alcance, pruebas y documentación en verde, PR, y recién ahí `pr_open`.
- Si sólo encontraste evidencia parcial y no sabés si esa tarjeta se está trabajando,
  **dejá el `status` afuera del PATCH** (no lo toques) y volcá el detalle en `observations`
  nomás.
- Un developer sólo puede dejar el Requerimiento en `to_do`, `doing` o `pr_open`. Las
  etapas siguientes (`merged_dev`, `in_testing`, `tested`, `in_production`) las fija el
  repositorio cuando se mergea o se promueve una rama: mandarlas a mano devuelve 400.
- Si el Requerimiento estaba sin asignar, un PATCH con `"status":"doing"` te lo asigna
  solo (la cuenta dueña de la key). Cualquier otro PATCH sobre algo que no es tuyo
  contesta `403 "Este Requerimiento no está asignado a vos: ..."` -- no es la key ni el
  endpoint, así que no los toques: tomalo con `doing` primero, o esa tarjeta no es tuya.
- **Antes de mover el estado a `doing` o `pr_open`, asegurá la rama.** El paso 2 ya te trajo
  `githubBranch` y `gitlabBranch` de cada Requerimiento: si los dos vienen en `null`, ese
  Requerimiento **no tiene rama**: el PATCH mueve la tarjeta igual, pero después el
  webhook no tiene qué reportar y el trabajo queda sin trazabilidad en git. Abrila con el
  mismo curl del **paso 4 de `siguiente`** (es idempotente, se
  puede llamar aunque ya exista), corré el `checkoutCommand` que devuelve, y pusheá ahí lo
  que hiciste — **ahí y no en `dev`**. Recién después mandá el PATCH.
  Si el trabajo ya está commiteado en otra rama, **decíselo al usuario en vez de inventar
  el push**: la rama que la app mira es la del Requerimiento, y mover la tarjeta a mano deja
  el tiempo real en cero para siempre.
- Guardar en el manifest una entrada `{ requirementId, sourceRef, testIds }` (crear si
  es la primera vez que se matchea ese Requerimiento, actualizar `sourceRef` si ya
  existía).
- **Sólo si encontrás evidencia real de tests en el repo** (archivos de test existentes
  que cubren ese requerimiento — nunca inventar esto) crear un Test:
  ```bash
  cat > /tmp/cuerpo.json <<'JSON'
  {"title":"<nombre del test>","isAutoGenerated":true,"status":"Aprobado"}
  JSON
  curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/tests" \
    -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/cuerpo.json
  ```
  Guardar el `id` (`TEST-...`) en `testIds` de esa entrada del manifest.
  Si el repo tiene `scrumDocs/tests-manifest.json` (ver paso 5), no crear tests sueltos acá
  para lo que ya esté cubierto por ese archivo — dejarle el trabajo al paso 5, que es
  más rico (guarda los pasos de verificación, no sólo el nombre).

#### 4.5. Crear un Requerimiento que no existe todavía (con confirmación explícita)

Dos disparadores posibles:
- Algo que la documentación describe con claridad no matchea ningún Requerimiento del
  paso 2 -- genuinamente no estaba trackeado, no es un caso dudoso de cobertura.
- El usuario pide directamente, en la conversación, crear un Requerimiento puntual (por
  nombre/descripción), sin pasar por el flujo de sincronización de documentación.

En cualquiera de los dos casos, antes de crear nada:

1. **Resolver a qué Historia de Usuario cuelga**, comparando contra `name` +
   `description` + `acceptanceCriteria` de las Historias del paso 2 (nunca por
   coincidencia literal de texto). Si no hay ninguna Historia razonable, **no la
   inventes** — avisar que hace falta que el Product Owner (o vos mismo, si tenés
   permiso) cargue esa Historia primero, y no crear el Requerimiento suelto.
2. **Confirmarle al usuario, antes de llamar a la API**: nombre propuesto, tipo
   (`funcional`/`no_funcional`) y bajo qué Historia va a quedar. Esperar confirmación
   explícita -- a diferencia de actualizar un Requerimiento existente (reversible con
   otra corrida), crear uno de más ensucia el backlog y hay que borrarlo a mano después.
3. Con la confirmación:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"name":"...","description":"...","type":"funcional"}
   JSON
   curl -s -X POST "$SCRUM_API_URL/api/v1/user-stories/$USER_STORY_ID/requirements" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   - `403` → **crear un Requerimiento es sólo del Project Manager y del Scrum Master**
     (`puedeCrearRequerimiento` en `lib/permisos.ts`): con una key de `developer` la API
     contesta `Sólo el Project Manager o el Scrum Master pueden crear Requerimientos`. Antes
     esta ruta aceptaba developer y Product Owner y se cerró a propósito, así que **no
     reintentes ni cambies de endpoint**: avisale al usuario que se lo pida a quien coordina
     (por la web, o con `/sm-sync` si el Scrum Master lo tiene), y seguí con el resto de la
     sincronización.
   - `201` → guardar en el manifest una entrada `{ requirementId, sourceRef, testIds: [] }`
     igual que en el paso 4, para que una relectura futura no lo vuelva a crear. **Nace en
     `to_do` y sin rama**: si el código que lo motivó ya está escrito, seguí con el punto de
     la rama del paso 4 antes de cerrar. Un Requerimiento recién creado y sin rama queda
     parado en el backlog sin que nadie se entere de que su trabajo ya está hecho.

#### 5. Sincronizar `scrumDocs/tests-manifest.json` (tests de endpoint)

Si el repo tiene `scrumDocs/tests-manifest.json` (o `docs/tests-manifest.json`, la
ubicación anterior), es la fuente de tests de endpoint que el
programador mantiene junto con su código — un archivo por proyecto, con un test por
endpoint/flujo, pensado para que QA los corra desde "Verificación en vivo" en la app sin
tener que tipear URLs a mano. Formato:

```json
{
  "tests": [
    {
      "requirementCode": "RF-03",
      "title": "Alta de profesional",
      "type": "Integración",
      "preconditions": "Usuario autenticado con rol admin",
      "description": "Autentica como admin, da de alta un profesional nuevo y confirma que se puede volver a leer.",
      "expectedResult": "Devuelve 201 y el profesional creado con id",
      "steps": [
        { "name": "crear", "method": "POST", "url": "{{baseUrl}}/api/professionals", "body": "{\"name\":\"Juan\"}", "expectedStatus": 201 },
        { "name": "leer", "method": "GET", "url": "{{baseUrl}}/api/professionals/{{crear.id}}", "expectedStatus": 200 }
      ]
    }
  ]
}
```

- `requirementCode` se resuelve contra la lista de Requerimientos traída en el paso 2
  (por `code`, ej. `RF-03`, nunca por nombre). Si no matchea ninguno, dejarlo afuera y
  avisar en el resumen final — no crear el Requerimiento ni adivinar cuál es.
- `type` usa los mismos valores que ya existen en la app: `Unitario`, `Integración`, `E2E`.
- `description`: en prosa, el flujo que describe el test (qué hace y en qué orden) — es
  el campo que la app muestra como "Descripción / Flujo de Ejecución" en cada test.
  **Siempre completarlo** — no se infiere de `steps`, y si falta queda en blanco en la app.
- `steps` es una lista de llamadas HTTP en orden (`name`, `method`, `url`, `body`
  opcional, `expectedStatus` opcional). Un paso puede reusar el resultado de uno anterior
  con `{{nombreDelPaso.campo}}` (o `{{nombreDelPaso.status}}`), y `{{now}}` da un valor
  único por corrida. **No resolver `{{baseUrl}}` acá ni pedirle la URL real al usuario**
  — lo resuelve la app cuando QA corre el test, contra la Base URL de verificación que el
  Project Manager ya configuró para el proyecto (este skill no necesita conocerla).
- No confiar sólo en el `testId` de `scrumDocs/scrum-manifest.json` para saber si el test ya
  existe — ese archivo puede faltar, no estar commiteado, o venir de otro clon. Antes de
  crear, traer los tests que la API ya tiene registrados para este Requerimiento y
  matchear por `title` exacto:
  ```bash
  curl -s "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/tests" \
    -H "Authorization: Bearer $SCRUM_API_KEY"
  ```
- Si ya existe (por el manifest o por esa respuesta), actualizarlo en vez de crear uno
  nuevo — con esto también se puede refrescar el contenido, no sólo los pasos, por si el
  endpoint cambió desde la última corrida:
  ```bash
  cat > /tmp/cuerpo.json <<'JSON'
  {"preconditions":"...","description":"...","expectedResult":"...","verification":{"steps":[...]}}
  JSON
  curl -s -X PATCH "$SCRUM_API_URL/api/v1/tests/$TEST_ID" \
    -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/cuerpo.json
  ```
- Si no existe en ninguna de las dos, crearlo con una sola llamada (test + pasos juntos,
  **incluyendo siempre `description`**):
  ```bash
  cat > /tmp/cuerpo.json <<'JSON'
  {"title":"...","type":"Integración","preconditions":"...","description":"...","expectedResult":"...","isAutoGenerated":true,"verification":{"steps":[...]}}
  JSON
  curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/tests" \
    -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/cuerpo.json
  ```
  y guardar el `id` devuelto (o el que salió de la reconciliación) en `testIds` de esa
  entrada del manifest de trazabilidad.
- **Nunca mandar `status` en `Aprobado`/`Fallido` desde acá** — crear/actualizar deja el
  test en `Pendiente`; que alguien haya escrito los pasos no significa que ya se
  corrieron y se revisaron. Eso lo decide QA corriéndolos desde la app.
- Si la reconciliación contra la API encuentra más de un test con el mismo `title` para el
  mismo Requerimiento (duplicados de corridas viejas), no elegir uno a ciegas: reportarlo
  en el resumen final para que QA decida cuál borrar
  (`DELETE $SCRUM_API_URL/api/v1/tests/$TEST_ID`).

#### 6. Guardar el manifest actualizado

Reescribir `scrumDocs/scrum-manifest.json` con `lastSyncAt` en la fecha/hora actual (ISO) y
todas las entradas de `mappings` (viejas + nuevas, incluyendo los `testIds` del paso 5).

#### 7. Resumen final

Reportarle al usuario, en texto, no en JSON crudo:
- Cuántos Requerimientos se actualizaron (y a qué estado, si cambió).
- Cuántos Requerimientos se crearon (paso 4.5), y bajo qué Historia de Usuario cada uno.
- Cuántos Tests se crearon o actualizaron desde `scrumDocs/tests-manifest.json`.
- Qué Requerimientos quedaron sin cobertura clara (para que sepa qué falta implementar o
  documentar mejor).

### `siguiente` — decidir qué Requerimiento encarar y dejarlo listo para trabajar

Este modo asume el flujo: pull a la rama principal → leer el plan → decidir con
criterio cuál sigue → **marcar el Requerimiento como `doing`** → asegurar la rama →
commit + push. El push también dispara el pase a "Haciendo" por webhook o GitHub Action,
pero **no todos los proyectos lo tienen configurado**, así que el PATCH del paso 3 es lo
que garantiza que la tarjeta se mueva. Los dos caminos son idempotentes: el reloj arranca
una sola vez y no se reinicia.

1. **Traer el plan actualizado**: correr `git pull` sobre la rama principal del repo (si
   el working tree tiene cambios sin commitear, avisar y parar — no pisar trabajo en
   curso). Leer `scrumDocs/scrum-plan.md`. Si no existe, avisar que el Project Manager
   todavía no publicó el plan desde la app ("Publicar Plan") y parar.
2. **Elegir el Requerimiento**: el archivo trae una tabla ya ordenada por dependencias
   (columna "Orden") con columnas Código/Estado/Desarrollador/Depende de/Rechazos. Con
   criterio, elegir la primera fila que cumpla:
   - Estado no es `Hecho ✓ Visado` ni `Hecho` (ya está en revisión, no hay nada para
     arrancar).
   - Todos los Requerimientos listados en "Depende de" ya están en `Hecho ✓ Visado`.
   - Si la columna "Desarrollador" tiene nombres cargados, preferir uno asignado al
     usuario actual (`git config user.name` o preguntar) antes que uno sin asignar o de
     otra persona.
   - A igualdad de las condiciones anteriores, preferir una fila con "Rechazos" > 0
     (retrabajo pendiente: ya se encaró antes y volvió con observaciones) por sobre una
     que nunca se tocó — es la más urgente de resolver.
   Si hay empate real entre varias candidatas razonables, preguntarle al usuario cuál
   prefiere — no adivinar.
3. **Mover la tarjeta a "Haciendo" antes de escribir una línea de código**:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"status":"doing","observations":"Inicio de desarrollo del requerimiento"}
   JSON
   curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   Si el Requerimiento estaba **sin asignar**, este mismo PATCH te lo asigna a vos (la
   cuenta dueña de la key) y arranca el cómputo de tiempo real -- no hace falta el POST
   `/claim` aparte. Si ya lo tiene otra persona, contesta
   `403 {"error":"Este Requerimiento no está asignado a vos: ..."}`: **no reintentes ni
   regeneres la key**, no es un problema de credenciales. Avisale al usuario y elegí otra
   fila, o que se lo pidan a quien lo tiene. El mismo 403 sale para cualquier otro PATCH
   sobre algo que no es tuyo -- sólo `"status":"doing"` te lo asigna solo.
3.5. **Fijar el alcance antes de escribir una línea.** Con el Requerimiento ya en `doing`,
   releé su `name`, su `description` y los criterios de aceptación de la Historia que lo
   contiene, y **decile al usuario en dos líneas qué entra y qué no**. La lista completa de
   Requerimientos del proyecto (paso 2) es lo que te dice qué NO es tuyo: si algo que
   estabas por escribir ya está descrito en otra tarjeta, esa tarjeta tiene dueño, reloj y
   lugar propio en el grafo.

   Durante la implementación, cada vez que aparezca algo que no está en la descripción:

   - **Otro Requerimiento lo describe** → no lo escribas. Nombralo (`RF-04 Dashboard`) y
     ofrecé cerrar el actual y tomarlo después con `POST /api/v1/requirements/<id>/claim` +
     `status: doing`. Si ya lo tiene otra persona, avisá y seguí con lo tuyo.
   - **No existe ninguno que lo describa** → reportalo con nombre e Historia sugerida. Vos
     no lo creás: la API le da 403 a un `developer` (lo crean el PM y el Scrum Master).
   - **Es lo mínimo para que lo tuyo funcione y se pueda probar** → va, y se anota en
     `observations` al cerrar.
   - **Te impide terminar** → bloqueá con `POST /api/v1/requirements/<id>/block` nombrando
     de qué depende, en vez de resolverlo por afuera.

4. **Asegurar la rama** (idempotente, se puede llamar aunque ya exista). Primero
   consultar `GET $SCRUM_API_URL/api/v1/projects/$PROJECT_ID` para saber `vcsProvider`
   del proyecto (`github` o `gitlab`), y pegarle al endpoint que corresponda:
   ```bash
   curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/github/branch" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   # o, si vcsProvider es 'gitlab':
   curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/gitlab/branch" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   ```
   - `{"alreadyExists":false,...,"checkoutCommand":"git fetch && git checkout <rama>"}`
     → rama nueva, recién creada en el repo a partir de la rama base del proyecto.
   - `{"alreadyExists":true,...}` → ya existía (se está retomando trabajo previo).
   - `409` → el proyecto no tiene el repositorio configurado; avisar y parar.
   Ejecutar el `checkoutCommand` devuelto tal cual.
5. **Commit + push**. **Siempre a la rama del Requerimiento, nunca a `dev`, `testing` ni
   a la rama de producción — aunque tengas permiso de escritura sobre ellas, o seas dueño
   del repositorio.** Que git te deje no es una autorización. Si te encontrás parado en una
   de esas, volvé a la rama del Requerimiento antes de commitear: un commit directo en
   `dev` saltea la revisión de quien integra y deja el trabajo sin Pull Request, así que el
   webhook no tiene qué reportar, la tarjeta se queda en `to_do` y el tiempo real queda en
   cero para siempre.
   - Si la rama era nueva: hacer un commit inicial marcador (ej. mensaje
     `"Inicio de trabajo en $REQUIREMENT_ID: <nombre>"`, aunque sea vacío con
     `git commit --allow-empty` si todavía no hay cambios de código) y
     `git push -u origin <rama>`. Es lo que le da al webhook algo que reportar; el reloj
     ya venía corriendo desde el PATCH del paso 3.
   - Si ya existía: si hay cambios locales sin commitear, commitearlos con un mensaje
     tipo `"Retomo $REQUIREMENT_ID: <nombre>"`; si no hay nada para commitear, hacer un
     commit vacío con el mismo mensaje. Después `git push`.
   - **Si el Requerimiento no tiene código asociado** (ej. una No Funcional de
     configuración/política, como "qué tipo de seguridad se adoptó"): el commit igual
     tiene que llevar algo tangible — un archivo de documentación en el propio repo
     describiendo la decisión tomada (no un commit vacío sin explicación). Usar criterio
     sobre dónde documentarlo (`docs/`, un README de la carpeta relevante, etc.).
5.5. **Chequeo de alcance, antes de abrir el PR.** Corré `git diff dev...<rama> --stat` y
   pasá los archivos contra la descripción del Requerimiento. **Lo que no puedas explicar
   señalando esa descripción, o entra en `observations` como el mínimo necesario, o sale
   del Pull Request** (a otra rama, o se descarta). El PR viaja entero: el Scrum Master lo
   mergea a `dev` mirando la tanda, y de ahí a `testing` y a producción va la rama completa,
   así que trabajo de otra tarjeta metido adentro se promueve sin que nadie lo haya pedido —
   con su tarjeta todavía en `to_do` y el próximo que la tome pisando lo que ya escribiste.
   Si encontrás algo así, decíselo al usuario antes de sacarlo: es una decisión suya.

5.6. **Las pruebas y la documentación van ANTES del Pull Request, y el paso a Hecho lo
   confirma la persona.** En este orden, y ningún paso es opcional:

   1. **Escribí las pruebas unitarias de lo que implementaste** (las del repo, con su
      framework; no las confundas con los Tests de la app, que son otra cosa y van en el
      paso 5 del modo por defecto).
   2. **Corré la suite completa del repo**, no sólo las tuyas: `npm run verify`,
      `npm test`, `pytest`, lo que use ese repo — si no sabés cuál es, leé el `package.json`
      o el README antes de inventar un comando.
   3. **Si algo falla, corregilo y volvé a correrla.** No abras el PR con la suite en rojo,
      y **no mandes `pr_open`**: la tarjeta sigue en `doing` mientras corregís, que es
      exactamente lo que tiene que pasar — el reloj sigue corriendo porque el trabajo sigue.
      Arreglar después del PR le carga esas horas a nadie y deja al Scrum Master mergeando
      algo que no pasa sus propias pruebas.
   4. **Dejá la documentación respaldatoria en el repo**, en el mismo commit: qué hace lo
      que implementaste y cómo se verifica. Si el Requerimiento no tiene código (una No
      Funcional de política o configuración), el documento **es** la entrega.

   5. **Preguntale al usuario si lo damos por terminado, y esperá la respuesta.** Con la
      suite corrida, mostrale el resultado y pedí la confirmación en una sola pregunta:

      > Corrí las pruebas de `<Requerimiento>`: **N pasaron, M fallaron**. Implementé
      > `<qué>` y documenté `<dónde>`. ¿Está todo bien? Si me decís que sí, abro el Pull
      > Request y paso la tarjeta a **Hecho**, que **corta el reloj** (ahora lleva `<Xh Ym>`
      > y deja de contar).

      El tiempo que va a quedar congelado se arma con dos campos de
      `GET /api/v1/projects/$PROJECT_ID/requirements`: **`real`** es lo acumulado hasta el
      último corte, y **`timerStartedAt`** es cuándo arrancó el tramo que está corriendo
      ahora. Sumale a `real` lo que va de `timerStartedAt` hasta este momento — `real` solo
      es el número viejo, porque recién se escribe al congelar. Si `timerStartedAt` viene en
      `null`, el reloj ya estaba parado y no hay nada que cortar: decilo así.

      - **Sí** → seguí con el paso 6 (PR) y el 7 (`pr_open`).
      - **No**, o pide cambios, o no contesta → **no abras el PR y no mandes `pr_open`**. La
        tarjeta se queda en `doing` con el reloj corriendo, que es la verdad: el trabajo
        sigue. Seguís con lo que te pida.
      - **Con la suite en rojo**, la pregunta cambia: primero decile qué está fallando y
        ofrecé corregirlo. Si aun así te pide abrir el PR, es su decisión y se la respetás,
        pero **dejando dicho en `observations` qué quedó fallando** -- no lo escondas.

      Esta confirmación no se saltea aunque el usuario haya dicho "hacé todo" al principio:
      es la única acción de este skill que **congela el reloj**, y una vez congelado el
      tiempo que se siga trabajando no se lo cobra nadie.

6. **Abrir el Pull Request contra `dev`** — es el pedido de integración, y es lo último
   que hacés con la rama:

   ```bash
   gh pr create --base dev --head <rama> --fill        # o, sin gh instalado:
   # https://github.com/<owner>/<repo>/compare/dev...<rama>
   ```

   **No lo mergees vos**, aunque tengas permiso en el repo. El merge a `dev` es del Scrum
   Master (o del Project Manager, que lo cubre): es quien mira que lo que entra junto no se
   rompa entre sí, que es exactamente lo que tu rama aislada no puede ver. Si el PR tiene
   conflictos, resolverlos sí es tuyo, en tu rama.

7. **Con el PR abierto y la confirmación del paso 5.6 en mano, cerrar el tramo** poniendo
   la tarjeta en `pr_open`:
   ```bash
   cat > /tmp/cuerpo.json <<'JSON'
   {"status":"pr_open","observations":"Implementación completada y verificada"}
   JSON
   curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
     -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
     -d @/tmp/cuerpo.json
   ```
   Reemplazá `observations` por lo que realmente se hizo -- ese texto es lo que lee quien
   revisa. **No mandes `pr_open` si todavía no terminaste**: significa "de mi lado está
   listo, falta que lo mergeen", es el último estado que un developer puede fijar, y es el
   que **congela el reloj**. Si después de mandarlo seguís tocando código, ese tiempo ya no
   lo cuenta nadie.
   `merged_dev`, `in_testing`, `tested` e `in_production` los fija el repositorio y
   devuelven `400` si los mandás a mano.
8. Confirmarle al usuario qué Requerimiento quedó eligiendo, en qué rama y en qué estado
   quedó la tarjeta. El cómputo de tiempo real arrancó con el PATCH a `doing` (o con el
   primer push, lo que haya pasado antes) y se congela solo al pasar a `pr_open` -- no
   hay nada que tenga que "parar" a mano.

---

## Notas de implementación

- Nunca crear un Requerimiento (paso 4.5) sin haberle confirmado antes al usuario nombre,
  tipo e Historia de Usuario destino, y sin haber recibido una confirmación explícita --
  a diferencia de actualizar uno existente, crear de más ensucia el backlog.
- **Nunca mandes `pr_open` sin preguntarle antes al usuario si lo damos por terminado**
  (paso 5.6.5), y sin haber corrido las pruebas para que esa respuesta signifique algo.
  `pr_open` congela el reloj: lo que se trabaje después de ese PATCH no lo cuenta nadie.
  Vale lo mismo que la confirmación para crear o borrar -- es una acción que el usuario no
  puede deshacer con otra corrida.
- Nunca inventar una Historia de Usuario para colgar un Requerimiento nuevo -- si no hay
  ninguna razonable, avisar y no crear el Requerimiento suelto.
- Nunca marcar `isAutoGenerated`/crear un Test sin evidencia real de que existe en el
  repo — es preferible no reportar cobertura de tests a inventarla.
- Nunca fuerces `status` a `pr_open` sólo porque encontraste documentación que lo
  describe: `pr_open` afirma que de tu lado está terminado y sólo falta el merge. Si la
  evidencia es parcial, dejá el `status` afuera del PATCH y usá `observations` para dejar
  constancia de lo que se encontró.
- Si `$SCRUM_API_URL` tiene un `/` final, quitarlo antes de concatenar rutas.
- Todas las respuestas de error de la API vienen como `{"error": "..."}` — mostrar ese
  mensaje tal cual, no reinterpretarlo.
- `scrumDocs/scrum-plan.md` lo publica el Project Manager desde la app ("Publicar Plan") —
  este skill sólo lo lee, nunca lo escribe ni lo edita.
- `scrumDocs/tests-manifest.json` es al revés: lo escribe el programador (o este skill en su
  nombre) en el repo del proyecto, y este skill lo lee para sincronizar. Nunca inventar
  entradas ahí — sólo reflejar endpoints que realmente existen en el código.
