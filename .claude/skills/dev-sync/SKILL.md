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

## La cadencia: de a una, validada antes de la siguiente

**Este skill no procesa lotes.** **Un Requerimiento** se trabaja de a una: se deja terminada, se le
muestra al usuario, él la valida, y **recién ahí** se ofrece la siguiente. Podés encadenar
varias en la misma corrida — lo que no podés es encadenarlas sin esa validación en el medio.

Que el usuario haya dicho "hacé todo" al principio **no saltea esto**: eso autoriza el
trabajo, no la revisión de cada pieza. Un lote entero aprobado de un saque es un lote que
nadie miró, y en el próximo Requerimiento vas a estar parado sobre código que nadie
verificó.

Si aun así te pide que sigas de largo sin validar una por una, es su decisión y se la
respetás — pero decíselo primero, con esa consecuencia por delante.

**Y acá la regla es más dura que en el resto de los skills: no se empieza el siguiente
hasta que el actual esté cerrado de verdad** — criterios de aceptación recorridos uno por
uno, pruebas escritas y corriendo en verde, documentación en el repo, Pull Request abierto
y la tarjeta en `pr_open`. No alcanza con "ya lo implementé". El paso 5.6 es esa puerta y
no se saltea.

Trabajar dos Requerimientos a la vez es el defecto que este skill más veces tuvo que
corregir: ramas apiladas, commits de una tarjeta adentro de otra, y un Pull Request que
promueve trabajo que nadie pidió en esa tanda.

**Ojo con no confundir dos cosas distintas.** "De a uno por vez" es una regla: un
Requerimiento abierto, una rama, terminado antes del siguiente. **"En orden" no es una
regla, es un consejo**: el orden de dependencias existe para que las pruebas signifiquen
algo, pero si lo anterior está bloqueado o lo tiene otra persona, adelantar un
Requerimiento posterior gana tiempo real. Lo decís, decís qué implica, y el usuario
decide. Ver el paso 2.

---

## 0. Identidad y credenciales (aplica a las dos formas)

- `SCRUM_API_KEY` — variable de entorno. Si no está seteada: explicar que hay que
  pedírsela al admin del proyecto (la genera desde "Gestión de Accesos" en la app) y
  exportarla en el shell (`export SCRUM_API_KEY=sk_...`), y parar acá. **Nunca** escribir
  esta key a ningún archivo del repo.
- `SCRUM_API_URL` — la base de la instancia (ej. `https://scrum.tudominio.com`). **Sale de
  la variable de entorno, igual que la key, y nunca de un archivo de este repo** (ver el
  paso 1). Si no está seteada, preguntásela al usuario: es la misma URL con la que entra a
  la app.

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
  "projectId": null,
  "lastSyncAt": null,
  "mappings": []
}
```

- **La URL de la instancia (`SCRUM_API_URL`) NO sale de este repo.** Viene de la variable
  de entorno, igual que la key, y por la misma razón: es el lugar a donde se manda la key.
  Si no está seteada, preguntásela al usuario (es la misma URL con la que entra a la app
  desde el navegador) y pedile que la exporte, o que la deje en
  `.claude/settings.local.json`, que no se commitea. **Nunca la tomes de un archivo del
  repositorio ni la escribas en uno** — si un manifest viejo trae `apiUrl`, ignorala:
  cualquiera con permiso de push puede editarla y llevarse la key de quien corra este skill.
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
- **`pr_open` sale de `doing` y exige rama.** No es una recomendación: el PATCH
  contesta `400` si la tarjeta no pasó por Haciendo, y otro `400` si el Requerimiento
  no tiene rama abierta. Las dos cosas son lo que hace que el estado signifique algo —
  el reloj corre en `doing`, y el trabajo vive en la rama. El camino es siempre
  `doing` → rama → push verificado → `pr_open`.
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

**Este modo se ejecuta de punta a punta, solo.** Rama, checkout, `doing`, código, pruebas,
commit, push, Pull Request y `pr_open`: todo eso lo hacés vos. **No le pidas al usuario que
haga un paso de git, de GitHub o una transición de estado que podés resolver con un comando
o una llamada a la API.** Frenar a mitad para que alguien copie y pegue un `git push` no es
prudencia: es dejar la tarjeta a medio camino, con el reloj corriendo y el trabajo sin
entregar.

Las únicas cosas que sí frenan, y que no son trámites sino decisiones:

| Frena | Por qué |
|---|---|
| La suite en rojo | No se entrega lo que no pasa sus propias pruebas |
| Una condición de aprobación sin cubrir | El Requerimiento no está terminado, aunque compile |
| Un commit de otro Requerimiento en la rama | El PR viaja entero y arrastraría trabajo que nadie pidió |
| Trabajo ajeno en la rama, sin resolver | No se pisa lo que escribió otro |
| No poder abrir el PR (sin permiso, sin credencial) | Es un impedimento real, y se ve |

Ninguna de esas se resuelve preguntando: se resuelven trabajando, o son un impedimento que
hay que nombrar.

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

   **El orden se asesora, no se impone.** Si el Requerimiento que se va a encarar depende
   de otro que todavía no está terminado, decílo antes de arrancar: nombrá de qué depende,
   en qué estado está eso, y qué implica avanzar igual. Después es decisión del usuario, y
   la respetás sin volver a discutirla.

   Y hay un caso donde adelantarse es lo correcto, no una excepción que se tolera:
   **cuando lo anterior está `blocked` o en manos de otra persona, esperar es tiempo
   perdido.** Si ves eso, proponelo vos: "RF-02 está bloqueado esperando la VM; puedo
   arrancar RF-05, que no depende de nada de eso".

   Lo que sí hacés al avanzar fuera de orden, siempre:

   - **Dejarlo escrito en `observations`**: sobre qué se está construyendo sin verificar.
     Es lo que va a leer quien revise el PR y quien lo pruebe.
   - **Decir qué parte no vas a poder probar todavía.** Si el login se apoya en un
     registro que aún no está verificado, sus pruebas se escriben igual, pero lo que
     certifiquen vale hasta ahí. Eso va en la tabla de criterios del paso 5.6.4.5, no
     escondido.
   - **Saber que QA no lo va a certificar antes que a su dependencia**, y con razón: un
     test que pasa apoyado en algo sin probar no dice si pasó por lo que probaba o de
     casualidad. Adelantar el desarrollo gana tiempo; adelantar la certificación no gana
     nada.

   Lo que no cambia es que sea **de a uno por vez**: avanzar fuera de orden significa
   elegir otro Requerimiento, no tener dos abiertos a la vez.
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
   - `{"alreadyExists":true,...}` → ya existía. **Acá no sigas de largo**: mirá
     `branchState`, que viene en la misma respuesta y dice qué hay adentro.
   - `409` → el proyecto no tiene el repositorio configurado; avisar y parar.
   Ejecutar el `checkoutCommand` devuelto tal cual.

   **Qué dice `branchState`.** "Ya existía" no distingue tu trabajo de ayer de una
   rama que dejó otra persona, y esa confusión ya costó una Historia entera: el dev
   leyó "ya está hecho", se paró sobre el commit de otro developer, y su `git push`
   contestó `Everything up-to-date` sin que nada se lo advirtiera.

   | `branchState` | Qué significa | Qué hacés |
   |---|---|---|
   | `existe: false` | La rama figura en la base pero **ya no está en el repositorio** | Avisale al usuario y pará: la rama la tiene que volver a abrir alguien, o el Requerimiento apunta a un repo que cambió |
   | `aheadBy: 0` | Recién nacida de la rama base, sin nada propio todavía | Es tu punto de partida limpio. Seguí |
   | `aheadBy > 0` y `lastCommit.author` **sos vos** | Estás retomando tu propio trabajo | Seguí desde ahí |
   | `aheadBy > 0` y `lastCommit.author` es **otra persona** | Alguien más ya trabajó en este Requerimiento | **Mostrale al usuario el sha, el autor, la fecha y el mensaje, y preguntá antes de escribir una línea.** Puede ser trabajo válido que hay que continuar, o un ensayo abandonado que hay que descartar. No lo decidís vos |
   | `null` | No se pudo consultar el repositorio (token sin permiso, proveedor caído) | Decilo, y mirá la rama con `git log` vos mismo antes de seguir |

   `behindBy` alto no frena nada, pero conviene decirlo: la rama arrancó hace mucho y
   el merge posterior va a traer conflictos.

4.1. **Plantate en la rama, no la construyas vos.** Antes de correr el
   `checkoutCommand`, `git status --porcelain` tiene que salir **vacío**: lo que quedó sin
   commitear del Requerimiento anterior se cuela en esta rama si te lo llevás puesto.
   Después de correrlo, verificá que quedaste donde la app creó la rama:

   ```bash
   git status --porcelain                                  # vacío ANTES de cambiar de rama
   git fetch origin && git checkout -B <rama> origin/<rama>  # el checkoutCommand
   git rev-parse HEAD && git rev-parse origin/<rama>         # tienen que dar lo MISMO
   ```

   **Nunca `git checkout -b <rama>` a secas ni `git branch <rama>` desde donde estés
   parado**, y nunca ramifiques de la rama del Requerimiento anterior. La rama sale de la
   rama de integración y de ningún otro lado — por eso el `checkoutCommand` de una rama
   nueva viene con `-B ... origin/<rama>` y no con un `checkout` pelado.

   Esto es lo que evita el defecto más caro que tuvo este flujo: en un proyecto real las
   **once ramas quedaron apiladas**, cada una arrastrando el commit del Requerimiento
   anterior, porque el developer siguió trabajando sobre su propia línea y el
   `git pull --rebase` posterior replicó ese commit adentro de la rama nueva. Mergear una
   arrastraba el trabajo de la otra, con su tarjeta todavía sin pedirlo.

   Si el push te rebota con *non-fast-forward* y la salida propone `git pull --rebase`:
   **pará.** Sobre una rama recién creada eso significa que estás parado en el lugar
   equivocado, y rebasar va a replicar commits ajenos adentro de tu rama. Volvé a plantarte
   con el `checkoutCommand` y traé tu trabajo con `git cherry-pick` de tus commits, o
   decíselo al usuario.
5. **Commit + push**. **Siempre a la rama del Requerimiento, nunca a `dev`, `testing` ni
   a la rama de producción — aunque tengas permiso de escritura sobre ellas, o seas dueño
   del repositorio.** Que git te deje no es una autorización. Si te encontrás parado en una
   de esas, volvé a la rama del Requerimiento antes de commitear: un commit directo en
   `dev` saltea la revisión de quien integra y deja el trabajo sin Pull Request, así que el
   webhook no tiene qué reportar, la tarjeta se queda en `to_do` y el tiempo real queda en
   cero para siempre.
   - **Todo commit nombra el id de su Requerimiento** (`REQ-...`), en el asunto o al
     final entre paréntesis: `feat(auth): registro de usuarios (REQ-1788962591125)`. No es
     cosmético — el PATCH del paso 7 lee los mensajes de la rama y **rechaza con `400` si
     encuentra commits que nombran a OTRO Requerimiento del proyecto**, que es cómo se
     detecta una rama apilada.
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
   - **Verificá que el push aterrizó, siempre.** `git push` puede contestar
     `Everything up-to-date` y eso **no es éxito**: es que no había nada que subir,
     casi siempre porque commiteaste en otra rama o porque nunca commiteaste. El
     chequeo son dos líneas:

     ```bash
     git rev-parse HEAD                  # tu commit
     git rev-parse origin/<rama>         # lo que quedó en el servidor
     git rev-parse --abbrev-ref HEAD     # ...y que sea la rama del Requerimiento
     ```

     Si los dos primeros no coinciden, o el tercero no es la rama que devolvió el
     paso 4: **pará y decíselo al usuario.** No mandes el PATCH a `pr_open` — la API
     lo va a rechazar igual, y con razón: pedir el merge de algo que no está pusheado
     deja la tarjeta afirmando un trabajo que nadie puede ver.
5.5. **Chequeo de alcance, antes de abrir el PR.** Corré `git log dev..<rama> --oneline` —
   ahí tienen que estar **tus commits de este Requerimiento y ninguno más**; si aparece uno
   de otra tarjeta, la rama está apilada (paso 4.1) y hay que rehacerla. Después
   `git diff dev...<rama> --stat` y
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
   4. **Las pruebas de la app son DOS juegos, y los dos son tuyos de preparar.** Cada
      condición de aprobación deja dos Tests cargados, y en la pestaña "Pruebas" se ven
      separados:

      | Etapa | La corre | Dónde | Contra qué |
      |---|---|---|---|
      | **Del programador** (`desarrollo`) | vos | la rama del Requerimiento | tu máquina, con datos fijos |
      | **De QA** (`integracion`) | QA | `dev`, con todo mergeado | el entorno desplegado |

      **Las de `desarrollo` las corrés y las dejás en verde.** Son tuyas de punta a punta:
      aisladas, con el contexto hardcodeado que haga falta (un usuario semilla, un registro
      fijo, un mock del servicio de al lado). Que dependan de datos fijos no es una
      trampa — es lo que las hace repetibles en una rama donde todavía no hay nada más.

      **Las de `integracion` las dejás PREPARADAS, no las corrés.** No podés: en tu rama no
      hay integración que probar. Preparadas significa con sus pasos escritos, sus datos
      reales indicados y el resultado esperado claro, de modo que QA las abra y le dé
      correr. Dejarlas vacías para que QA las redacte es devolverle el trabajo de entender
      lo que vos ya entendiste.

      **Y con su bloque `verification` completo, siempre**: `endpointUrl`, `notes` y los
      `steps` en orden, con método, URL (usando `{{baseUrl}}`), body y `expectedStatus`. Un
      Test sin pasos es un título: nadie lo puede correr, ni vos ni QA, y en la app aparece
      como una fila que no se puede verificar.

      **Apenas la suite local pasa, marcá los de `desarrollo` como Aprobados**
      (`PATCH /api/v1/tests/<id>` con `{"status":"Aprobado"}`). No lo dejes para después:
      el tablero calcula el avance con eso (`progress` = aprobados/total), así que un Test
      que pasó y quedó en Pendiente hace que la tarjeta muestre menos de lo que hay hecho.

      **Los de `integracion` quedan en Pendiente, siempre.** Marcarlos Aprobado desde tu
      rama es afirmar que algo funciona integrado sin haberlo visto integrado. Son de QA.

      Una condición sin Test es una condición que sólo vos podés afirmar, y eso no es una
      entrega: es una promesa. Si alguna no se puede traducir a pasos HTTP (es de pantalla,
      o de configuración), cargá el Test igual con los pasos manuales en `description` y
      `expectedResult` — que QA sepa QUÉ mirar y CÓMO, aunque lo haga a ojo.

   4.1.5. **Dejá el entorno verificable desde la app, la primera vez que toque.** Los
      Tests contra un entorno local los corre **el navegador** de quien prueba, no el
      servidor de Scrum —que vive en otra máquina y no llega a la tuya—. Si tu app no
      devuelve `Access-Control-Allow-Origin`, el navegador no deja leer la respuesta y
      **ninguna condición se puede verificar**: el tablero pasa a depender de que alguien
      diga "confiá en mí".

      Configuralo vos, una vez por proyecto, **en los settings de desarrollo**:

      ```python
      # Django -- settings de desarrollo, NUNCA los de producción
      # pip install django-cors-headers
      INSTALLED_APPS += ['corsheaders']
      MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')   # antes de CommonMiddleware
      CORS_ALLOWED_ORIGINS = ['https://scrum.tudominio.com']          # el origen de la instancia
      ```

      ```js
      // Express -- sólo en desarrollo
      app.use(require('cors')({ origin: 'https://scrum.tudominio.com' }));
      ```

      ```python
      # FastAPI
      app.add_middleware(CORSMiddleware, allow_origins=['https://scrum.tudominio.com'])
      ```

      **Tres límites que no se negocian:**

      1. **Sólo el origen de la instancia de Scrum**, nunca `*` ni
         `CORS_ALLOW_ALL_ORIGINS = True`. Abrirlo a todos significa que cualquier página
         que la persona tenga abierta puede hablarle a su app con sus cookies.
      2. **Sólo en los settings de desarrollo.** En producción esto no va: ahí las pruebas
         las corre el servidor contra el entorno desplegado y no pasan por CORS.
      3. **Anotalo en el documento de entrega**, en "cómo se levanta y cómo se prueba".
         El próximo que clone el repo tiene que saber que eso está y por qué.

      Si el proyecto ya tiene un Requerimiento operacional para esto, es ése el que estás
      cerrando: no lo hagas de contrabando dentro de otra tarjeta.

   4.2. **Y el script, que es lo que QA no puede escribir por vos.** Un archivo ejecutable
      en `scrumDocs/entregas/<CODIGO>.sh`, commiteado, que se corra con un comando y sin
      configurar nada:

      ```bash
      bash scrumDocs/entregas/RF-03.sh                  # el recorrido completo, integrado
      bash scrumDocs/entregas/RF-03.sh --carga 200      # el mismo recorrido, 200 veces
      ```

      Tiene que hacer tres cosas:

      1. **Preparar sus datos y limpiarlos al terminar.** Si deja basura, la segunda
         corrida da distinto que la primera y nadie sabe si eso es el sistema o el script.
      2. **Recorrer el flujo completo integrado**, no tu pedazo: si tu Requerimiento es el
         login, el script registra, entra, hace algo autenticado y sale. Ahí es donde
         aparece lo que tu rama no podía ver.
      3. **Aceptar un modo de carga** (`--carga N`): el mismo recorrido repetido, midiendo
         y reportando. No hace falta una herramienta de estrés — un `for` con `curl` y un
         promedio alcanza. Lo que importa es el **número**: cuántas corridas, cuántas
         fallaron, cuánto tardó la más lenta.

      Usá lo que el repo ya tenga (k6, autocannon, pytest, lo que sea) antes de sumar una
      dependencia. Si el Requerimiento no tiene endpoints, el script comprueba lo que
      corresponda —que el servicio levanta, que la configuración está aplicada— y lo dice.

      **El script es del programador porque conoce los datos que hacen falta.** QA sabe qué
      hay que verificar; vos sabés con qué. Escribirlo es lo que convierte tu entrega en
      algo que otro puede correr.

   5. **Dejá el documento de entrega en el repo**, en el mismo commit. No es "documentación"
      en abstracto: es lo que QA va a leer para poder probar sin preguntarte nada. Cinco
      cosas, en `scrumDocs/entregas/<CODIGO>.md` (ej. `scrumDocs/entregas/RF-03.md`):

      1. **Qué quedó implementado**, en una o dos frases, en lenguaje de lo que el sistema
         ahora hace — no de los archivos que tocaste.
      2. **Cómo se levanta y cómo se prueba**: los comandos exactos, copiables. Si hace
         falta una variable de entorno, un servicio o una migración, va acá con su valor de
         ejemplo.
      3. **Qué datos hacen falta**: usuario y rol con el que entrar, registros previos,
         cualquier precondición. Si QA tiene que crear algo antes, decilo con los pasos.
      4. **Qué endpoints o pantallas toca**, con método y ruta. Es lo que le permite a QA
         armar sus propios casos además de los tuyos.
      4.5. **Cómo se corre integrado**: el comando del script del paso 4.2, qué datos deja,
         y qué tiene que estar levantado para que funcione.
      5. **Qué quedó afuera y qué se asumió.** Los límites conocidos, lo que se pospuso, la
         decisión que tomaste cuando el Requerimiento no lo aclaraba. Esto es lo que evita
         que QA reporte como defecto algo que fue una decisión.

      Si el Requerimiento no tiene código (una No Funcional de política o configuración),
      este documento **es** la entrega, y el punto 2 pasa a ser cómo se comprueba que la
      política está aplicada.

   6. **Todo lo que afirmes acá tiene que ser mensurable.** Ni en las condiciones, ni en el
      documento de entrega, ni en `observations` entran los adjetivos: "rápido", "seguro",
      "robusto", "optimizado" no son verificables y nadie puede probarlos ni refutarlos.
      Van con número y unidad, o no van:

      | No sirve | Así sí |
      |---|---|
      | "Mejoré la performance" | "El listado pasó de 4,1 s a 380 ms con 10.000 registros" |
      | "Quedó seguro" | "La contraseña se guarda con bcrypt, costo 12; el endpoint rechaza sin token con 401" |
      | "Anda bien en móvil" | "Probado en Chrome Android 14 y Safari iOS 17, viewport 390px" |

      Si algo que implementaste no lo podés medir, decilo tal cual —"esto no lo pude
      medir"— en vez de adjetivarlo. Un límite declarado es información; un adjetivo es
      ruido que alguien va a tener que verificar de nuevo.

   4.5. **Recorré las condiciones de aprobación, una por una.** Están en el campo
      `acceptanceCriteria` **del Requerimiento** (`GET
      $SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements`) y son de esta tarjeta, no
      de la Historia entera: no hay nada que adivinar sobre cuáles te tocan. Armá una tabla
      corta: cada condición, si quedó cubierta, y **con qué prueba se demuestra** — el
      nombre del test que la ejercita, no "sí" a secas.

      | Condición de aprobación | ¿Cubierta? | Cómo se prueba |
      |---|---|---|
      | El alta rechaza un email ya registrado y lo dice en pantalla | sí | `test_registro_email_duplicado` |
      | La contraseña se guarda hasheada, nunca en texto plano | sí | `test_password_no_plana` |
      | Un alta exitosa deja al usuario logueado | **no** | — |

      **Una condición sin cubrir significa que el Requerimiento NO está terminado**, aunque
      la suite esté en verde: la suite prueba lo que escribiste, las condiciones dicen lo
      que había que escribir. Decílo y seguí trabajando, no lo cierres.

      Si el Requerimiento **no tiene condiciones cargadas**, decilo y pará antes de cerrar:
      sin ellas "listo" es una opinión tuya, y quien revisa no tiene contra qué comparar.
      Las escriben el Project Manager o el Scrum Master — a vos la API te contesta 403.
      Ofrecé redactar una propuesta a partir de lo que implementaste para que ellos la
      visen: **proponerlas no es cargarlas**, y menos aún darlas por cumplidas.

      Si alguna condición resultó imposible, o quedó mal planteada, tampoco la edites: eso
      se habla. Nombrala en el resumen con lo que encontraste.

   5. **Con las tres cosas de arriba en verde, seguí solo: PR y `pr_open`, sin preguntar.**

      Las tres son: la suite del repo pasa, las condiciones de aprobación están todas
      cubiertas, y la entrega quedó escrita (documento, script y Tests de integración
      preparados). Si eso se cumple, tu tramo terminó de verdad y no hay nada que consultar
      — seguí con el paso 6 (abrir el PR) y el 7 (`pr_open`).

      **Y `pr_open` va apenas el PR existe, no después.** Ese PATCH es el que **congela el
      reloj**, y el reloj tiene que parar cuando el trabajo para. Dejarlo corriendo
      mientras alguien contesta un mensaje no protege a nadie: le carga a la tarjeta horas
      en las que no se trabajó, que es exactamente la mentira que el cronómetro existe para
      evitar.

      Si **alguna de las tres no se cumple**, no preguntás tampoco: seguís trabajando.
      La suite en rojo se corrige, la condición sin cubrir se implementa, la entrega que
      falta se escribe. Sólo se le avisa al usuario cuando hay un **impedimento** que no
      podés resolver vos (no tenés permiso en el repositorio, falta una credencial, la
      condición depende de algo que no existe) — y ahí la tarjeta se queda en `doing`, que
      es la verdad, con el impedimento nombrado.

      La excepción es que el usuario te haya pedido explícitamente que le muestres antes de
      entregar. Eso se respeta: es su proyecto.

   5.5. **Contá el tiempo que quedó congelado, en el aviso final.** Se arma con dos campos
      de `GET /api/v1/projects/$PROJECT_ID/requirements`: **`real`** es lo acumulado hasta
      el último corte, y **`timerStartedAt`** es cuándo arrancó el tramo que venía
      corriendo. Sumale a `real` lo que va de `timerStartedAt` hasta el momento del
      `pr_open` — `real` solo es el número viejo, porque recién se escribe al congelar. Si
      `timerStartedAt` viene en `null`, el reloj ya estaba parado y no hay nada que cortar:
      decilo así.

      Si la suite quedó en rojo y el usuario **igual** te pidió entregar, es su decisión y
      se la respetás — pero **dejando dicho en `observations` qué quedó fallando**, no lo
      escondas.

6. **Abrir el Pull Request contra `dev`** — es el pedido de integración, y es lo último
   que hacés con la rama:

   **Abrilo vos.** No le pases el link al usuario para que lo apriete: es un paso mecánico
   y es tuyo. En orden, hasta que uno funcione:

   ```bash
   # 1. gh, que es el camino corto y usa la sesión que el usuario ya tiene
   gh pr create --base dev --head <rama> --fill

   # 2. sin gh: la API de GitHub, con el token que el USUARIO tenga exportado
   curl -s -X POST "https://api.github.com/repos/<owner>/<repo>/pulls" \
     -H "Authorization: Bearer $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github+json" \
     -d '{"title":"<REQ-id>: <nombre>","head":"<rama>","base":"dev","body":"<qué incluye>"}'
   ```

   **Con el token que el usuario exportó, y con ninguno más.** No salgas a buscar
   credenciales por el repositorio, el `.env`, la config de git ni el historial de la shell:
   un token encontrado así casi nunca es el que corresponde a esta persona, y usarlo escribe
   en GitHub a nombre de otro. Si `$GITHUB_TOKEN` no está y `gh` no está autenticado,
   **eso es el impedimento**: decilo, dejá el link de fallback
   (`https://github.com/<owner>/<repo>/compare/dev...<rama>`) y la tarjeta en `doing`.

   **No lo mergees vos**, aunque tengas permiso en el repo. El merge a `dev` es del Scrum
   Master (o del Project Manager, que lo cubre): es quien mira que lo que entra junto no se
   rompa entre sí, que es exactamente lo que tu rama aislada no puede ver. Si el PR tiene
   conflictos, resolverlos sí es tuyo, en tu rama.

   **Este paso no es opcional y no va después del 7.** El PATCH a `pr_open` consulta el
   proveedor y devuelve `400` si la rama no tiene commits propios o si no hay ningún Pull
   Request abierto para ella. El estado se llama "PR abierto": sin PR no describe nada, y
   deja al Scrum Master con una tarjeta en "Hecho" que no tiene qué mergear. Si no podés
   abrirlo (no tenés permiso en el repositorio, `gh` no está instalado y no hay navegador),
   **decíselo al usuario y dejá la tarjeta en `doing`** — el reloj sigue corriendo, que es
   la verdad, y el impedimento se ve.

   El número del PR queda registrado solo: el PATCH del paso 7 lo busca y lo guarda, así
   que el botón "Mergear a dev" del tablero funciona incluso en repos sin webhook.

   **Si tu rama quedó vieja porque se mergearon otras mientras trabajabas**, ponela al día
   vos, sin preguntar: `git fetch origin && git rebase origin/dev`. Eso es traer la
   integración a tu rama, y evita que el PR llegue con conflictos que sólo vos podés
   resolver.

   Ojo con no confundirlo con lo que el paso 4.1 prohíbe: lo vedado es
   `git pull --rebase` sobre una rama **recién creada** cuando el push rebota
   non-fast-forward — ahí el problema no es estar viejo, es estar **parado en el lugar
   equivocado**, y rebasar replica commits ajenos adentro de tu rama. Rebasar sobre
   `origin/dev` una rama donde ya venís trabajando es correcto y es tuyo.

7. **Con el PR abierto, cerrar el tramo en el acto** poniendo la tarjeta en `pr_open`:
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

   **Los tres `400` que puede contestar este PATCH, y qué significa cada uno:**

   | Dice | Qué pasó | Qué hacés |
   |---|---|---|
   | *"el pedido de merge sale de `doing`"* | La tarjeta nunca estuvo en Haciendo | Mandá `{"status":"doing"}` primero. Si el trabajo ya está hecho, decilo: el reloj va a contar sólo desde ahora |
   | *"no tiene ningún commit propio"* | La rama está vacía: no se pusheó nada | Volvé al paso 5. Casi siempre commiteaste en otra rama, o no tenés permiso de escritura en el repositorio — eso último es un impedimento real, no algo que se resuelva reintentando |
   | *"no hay ningún Pull Request abierto"* | Falta el paso 6 | Abrí el PR con el link que trae el propio error, y volvé a mandar el PATCH |
   | *"trae N commit(s) de otro Requerimiento"* | La rama está apilada sobre otra tarjeta (paso 4.1). El error nombra cada commit y a qué Requerimiento pertenece | Rehacé la rama desde la de integración con tus commits solamente: `git checkout -B <rama> origin/dev`, `git cherry-pick <tus shas>`, `git push --force-with-lease`. **Decíselo al usuario antes**: reescribe la rama |

   Ninguno de los tres es un problema de la key ni del endpoint: **no los reintentes con
   otro cuerpo ni con otra credencial.** Son hechos de git que faltan.
8. **Avisá qué quedó hecho, con los cinco datos que importan**: qué Requerimiento,
   en qué rama, las pruebas en verde (cuántas), el Pull Request abierto (con su link), y
   el cronómetro detenido con el tiempo que quedó registrado. Es un informe de lo hecho, no
   un pedido de permiso. El cómputo de tiempo real arrancó con el PATCH a `doing` (o con el
   primer push, lo que haya pasado antes) y se congela solo al pasar a `pr_open` -- no
   hay nada que tenga que "parar" a mano.

9. **Y ahí termina este Requerimiento. Ofrecé el siguiente, no lo empieces.** Decí cuál
   sería (con el mismo criterio del paso 2) y preguntá si arrancamos. Esperá la respuesta.

   El que proponés no tiene por qué ser el próximo de la fila: si el que sigue está
   bloqueado, o lo tiene otra persona, o depende de algo que todavía no existe, proponé uno
   posterior que se pueda empezar hoy y decí por qué lo salteaste. El orden manda mientras
   no cueste tiempo muerto.

   **No vuelvas al paso 1 por tu cuenta**, aunque el usuario haya dicho "hacé todos los
   requerimientos" al principio y aunque el siguiente parezca obvio. Entre un Requerimiento
   y el que sigue hay cosas que no pasan en esta corrida y que el humano necesita poder
   hacer: leer el Pull Request, correrlo él mismo, cambiar de opinión sobre el orden. Si
   arrancás solo, la primera vez que se entera es cuando ya hay cinco ramas abiertas.

   La única excepción es que el usuario, viendo el Requerimiento cerrado y el siguiente
   propuesto, te diga que sigas. Eso es una validación, que es justo lo que se estaba
   pidiendo.

---

## Notas de implementación

- Nunca crear un Requerimiento (paso 4.5) sin haberle confirmado antes al usuario nombre,
  tipo e Historia de Usuario destino, y sin haber recibido una confirmación explícita --
  a diferencia de actualizar uno existente, crear de más ensucia el backlog.
- **Nunca mandes `pr_open` sin que exista el Pull Request y sin la suite en verde** (paso
  5.6.5). `pr_open` congela el reloj: mandarlo antes de terminar le regala horas a la
  tarjeta, y mandarlo sin PR deja al Scrum Master con algo en "Hecho" que no tiene qué
  mergear.
- **Nunca frenes a pedirle al usuario un paso de git, de GitHub o una transición de estado
  que podés resolver vos.** Crear la rama, commitear, pushear, abrir el PR, mover la
  tarjeta: todo eso es tuyo. Lo único que se le lleva al usuario es un impedimento real o
  una decisión que no te corresponde.
- **Nunca arranques un Requerimiento nuevo sin que el usuario haya validado el anterior**
  (paso 9). "Hacé todo" autoriza el trabajo, no saltea la revisión de cada pieza. Eso es
  sobre la validación, no sobre el orden: cuál encarar después lo elige el usuario, y
  adelantarse a un Requerimiento posterior porque el anterior está trabado es una decisión
  razonable que vos mismo podés proponer.
- **Nunca cierres un Requerimiento con una condición de aprobación sin cubrir**
  (paso 5.6.4.5), por más que la suite esté en verde: la suite prueba lo que escribiste,
  las condiciones dicen lo que había que escribir.
- **Nunca corras vos los Tests de etapa `integracion`** ni los marques Aprobados: en tu
  rama no hay integración que probar, así que un verde ahí es una afirmación sin respaldo.
  Los preparás; los corre QA sobre `dev`.
- **Nunca entregues sin el documento de entrega, sin los Tests cargados ni sin el script**
  (pasos 5.6.4, 5.6.4.2 y 5.6.5). Son lo que QA necesita para probar sin preguntarte: sin eso, la validación no es
  una etapa del proceso sino una conversación, y la conversación no queda en ningún lado.
- **Nunca uses un adjetivo donde va un número** (paso 5.6.6). "Rápido" no se puede probar
  ni refutar; "380 ms con 10.000 registros" sí.
- **Nunca escribas ni edites `acceptanceCriteria`**: son de quien define el alcance (PM y
  Scrum Master), y la API te contesta 403. Proponerlas cuando faltan, sí; darlas por
  cumplidas o corregirlas para que cierren, no -- eso es moverse el arco.
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
