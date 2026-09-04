---
name: qa-sync
description: Ayuda al Tester/QA a redactar y mantener scrumDocs/tests-manifest.json (los tests de endpoint que corre la app desde "Verificación en vivo"), leyendo el código real del proyecto para entender qué endpoints existen de verdad, y sincroniza ese archivo con los Requerimientos de Scrum Master AI vía la API. Solo crea/edita Tests -- nunca Requerimientos, Historias de Usuario, ramas ni estados de ejecución. Usar cuando el usuario pide "armar tests de este endpoint", "sincronizar tests", "actualizar el manifest de tests", "cargar los casos de prueba", o corre /qa-sync explícitamente.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(curl *)
  - Write
---

# /qa-sync — Redactar y sincronizar tests de endpoint como Tester/QA

Ayuda a un Tester o QA a mantener `scrumDocs/tests-manifest.json` (el formato de tests de
endpoint que ya corre la app desde "Verificación en vivo" y el botón "Correr todos") y
sincronizarlo con los Requerimientos de Scrum Master AI. A diferencia de escribir eso a
mano, este skill lee el **código real de este repo** (rutas, controllers, serializers)
para proponer pasos que apuntan a endpoints que efectivamente existen — con método, body
y código esperado reales, no inventados.

**Alcance deliberadamente angosto**: sólo crea/edita Tests (`name`, `type`,
`preconditions`, `expectedResult`, `verification.steps`). Lee los Requerimientos para
saber a cuál colgar cada test, pero nunca los crea ni edita — igual que `/po-sync` no
crea Historias de Usuario, este skill no crea Requerimientos. Tampoco toca status,
tiempos, asignado, dependencias ni ramas — la API lo rechaza (403) si se intenta, es
territorio de developer/Project Manager.

Argumentos: `$ARGUMENTS` — opcionalmente el código de un Requerimiento puntual (ej.
`RF-03`) para enfocar el trabajo en uno solo, o una ruta de código a inspeccionar (ej. un
archivo de rutas). Sin argumentos, trabaja sobre todos los Requerimientos del proyecto.

---

**Qué podés escribir y qué endpoints tenés está en `scrumDocs/roles/qa.md`**, generado desde el código del servidor. Este skill es el procedimiento; si los dos se
contradicen, manda el documento del rol.

---

## 0. Identidad y credenciales

- `SCRUM_API_KEY` — variable de entorno, para la cuenta con rol Tester o QA. Si falta,
  explicar que el Project Manager la genera desde "Usuarios Activos" en la app, y parar.
  **Nunca** escribir esta key a ningún archivo del repo.
- `SCRUM_API_URL` — la base de la instancia (ej. `https://scrum.tudominio.com`). **No es
  secreta y no hay que preguntarla todavía**: se resuelve en el paso 1 leyendo el manifest
  del repo. Sólo si el manifest tampoco la tiene se llega a pedírsela al usuario.

Todas las llamadas llevan `-H "Authorization: Bearer $SCRUM_API_KEY"`. Si `$SCRUM_API_URL`
tiene un `/` final, quitarlo antes de concatenar rutas.

**El cuerpo de todo POST/PATCH va en JSON estricto**: comillas dobles en claves y valores,
sin comas colgando. `{'name': 'x'}` y `{name: "x"}` no son JSON y la API los rechaza con
`400 {"error":"JSON invalido"}` -- eso es el cuerpo, **no** la key ni el rol, así que no
regeneres la key ni cambies de endpoint. Como los textos de este dominio traen apóstrofes,
comillas y saltos de línea, escribilos a un archivo y mandalo con `-d @archivo.json` en vez
de pegarlos dentro de `-d '...'`: es lo único que no depende del quoting del shell. Los
saltos de línea dentro de un valor van como `\n`, nunca literales. La referencia completa
está en `scrumDocs/SCRUM_MASTER_AI.md`, paso 5.

## 1. Leer o inicializar el manifest de trazabilidad

Leer `scrumDocs/scrum-manifest.json` (el mismo que usa `/dev-sync`, sólo para `apiUrl` y
`projectId` — no tocar sus `mappings`, son del developer). Si no está ahí pero existe `docs/scrum-manifest.json` (ubicación anterior a `scrumDocs/`), leerlo de ahí y reescribirlo ya en `scrumDocs/scrum-manifest.json` — el archivo viejo se deja donde está, no se borra.

Si no existe en ninguno de los dos lugares, crearlo con el mismo formato que usa
`/dev-sync` (`apiUrl`, `projectId`, `lastSyncAt`, `mappings`).

- **`apiUrl`**: no es secreta — si el archivo ya la trae, usarla y no volver a preguntar;
  si falta, antes de preguntarla revisar si existe `scrumDocs/SCRUM_MASTER_AI.md` (el Project
  Manager la publica ahí ya resuelta) y usar ese valor si está. Sólo si tampoco está ahí,
  preguntarla, guardarla acá y sugerir commitear el archivo.
- **`projectId`**: si falta, no preguntarlo a ciegas — se resuelve en el paso 1.5 contra
  los proyectos que devuelve `/api/v1/me`.

## 1.5. Confirmar identidad y rol

```bash
curl -s "$SCRUM_API_URL/api/v1/me" -H "Authorization: Bearer $SCRUM_API_KEY"
```

- `401` → la key es inválida o fue revocada. Avisar que se la pidan de nuevo al Project
  Manager, y parar.
- `200` → `{ id, username, email, role, projects: [{ id, name }, ...] }` — esto determina
  el rol de verdad, **nunca preguntarle al usuario "qué rol sos" ni asumirlo**.
  - Si `role` no es `qa`, avisar que esta key no corresponde a este skill
    (`/po-sync` es para `product_owner`, `/dev-sync` para `developer`) y sugerir el
    correcto.
  - Si el manifest no tenía `projectId`: un solo elemento en `projects` → usarlo directo;
    varios → listar y preguntar; vacío → avisar que el Project Manager todavía no agregó
    a este usuario a ningún proyecto, y parar. Guardar el elegido en el manifest.

## 2. Traer los Requerimientos existentes

```bash
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

`401`/`403` → mismo manejo que los otros skills (key inválida, o no pertenece al
proyecto): avisar y parar. `200` → guardar `{ id, code, name, description, type, ... }`
en memoria.

Si `$ARGUMENTS` es un código (ej. `RF-03`), quedarse sólo con ese Requerimiento.

## 3. Entender el endpoint real leyendo el código

**Esto es lo que diferencia a este skill de escribir el manifest a mano.** Para cada
Requerimiento (o el que se pasó por argumento), buscá en el código de este repo qué
endpoint(s) lo implementan: rutas/urls.py, controllers, routers de la API. Usá Grep/Glob
para encontrar el archivo de rutas del proyecto y leé el handler correspondiente para
saber:

- Método HTTP real y path real (con sus parámetros).
- Si requiere autenticación, y de qué tipo (session, Basic Auth, JWT, API key propia del
  proyecto) — sólo Basic Auth funciona con el toggle "Con usuario/contraseña" del test;
  para otros esquemas, anotalo en la descripción del test en vez de fingir que
  funcionaría.
- Qué body espera (campos requeridos) y qué códigos de estado devuelve en éxito/error.
- Si la operación tiene efectos secundarios reales (crear un registro, mandar un mail,
  cobrar algo) — en ese caso, preferí armar el paso contra datos claramente de prueba
  (igual que ya se hizo para "recuperar contraseña": un email inventado que no exista,
  para no disparar un mail real) en vez de contra datos reales del sistema.

Si no encontrás el código que implementa un Requerimiento (todavía no está hecho, o no es
un endpoint HTTP sino una regla de negocio interna), no inventes un test para eso —
dejalo afuera y reportalo en el resumen final.

## 4. Armar o actualizar el test en `scrumDocs/tests-manifest.json`

Si el archivo todavía está en `docs/tests-manifest.json` (ubicación anterior a
`scrumDocs/`), leerlo de ahí y reescribirlo ya en `scrumDocs/`.

Formato (ver también la sección correspondiente en el skill `/dev-sync`, que es quien
originalmente lee este archivo desde el lado del developer):

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

- Si el archivo ya existe, agregar o actualizar la entrada de este `requirementCode`
  (matcheando por `requirementCode` + `title`) sin pisar entradas de otros
  Requerimientos.
- `type` usa los valores que ya existen en la app: `Unitario`, `Integración`, `E2E`.
- `description`: en prosa, el flujo que describe el test (qué hace y en qué orden) — es
  el campo que la app muestra como "Descripción / Flujo de Ejecución" en cada test.
  **Siempre completarlo** — no se infiere de `steps`, hay que redactarlo aparte, y si
  falta queda en blanco en la app.
- `steps`: `name`, `method`, `url` (con `{{baseUrl}}` al principio, nunca un dominio
  fijo), `body` opcional, `expectedStatus` opcional. Un paso puede reusar el resultado de
  uno anterior con `{{nombreDelPaso.campo}}`, y `{{now}}` da un valor único por corrida.
  **No resolver `{{baseUrl}}` ni pedirle la URL real al usuario** — lo resuelve la app
  contra la Base URL de verificación que ya configuró el Project Manager.

## 5. Sincronizar con la API

Igual que el paso 5 de `/dev-sync`, pero corriéndolo vos mismo como Tester/QA en vez de
delegarlo:

- Resolver `requirementCode` contra la lista del paso 2 (por `code`, nunca por nombre).
- No confiar sólo en el `testId` de `scrumDocs/scrum-manifest.json` para decidir si el test ya
  existe — ese archivo puede faltar, no estar commiteado, o venir de otro clon. Antes de
  crear, traer los tests que la API ya tiene registrados para este Requerimiento y
  matchear por `title` exacto:
  ```bash
  curl -s "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/tests" \
    -H "Authorization: Bearer $SCRUM_API_KEY"
  ```
- Si ya existe (por el manifest o por esa respuesta), actualizarlo — con esto también se
  puede refrescar el contenido, no sólo los pasos, por si el endpoint cambió desde la
  última corrida:
  ```bash
  cat > /tmp/cuerpo.json <<'JSON'
  {"preconditions":"...","description":"...","expectedResult":"...","verification":{"steps":[...]}}
  JSON
  curl -s -X PATCH "$SCRUM_API_URL/api/v1/tests/$TEST_ID" \
    -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/cuerpo.json
  ```
- Si no existe en ninguna de las dos, crearlo con test + pasos juntos (**incluí siempre
  `description`** — ver por qué en el paso 4):
  ```bash
  cat > /tmp/cuerpo.json <<'JSON'
  {"title":"...","type":"Integración","preconditions":"...","description":"...","expectedResult":"...","isAutoGenerated":true,"verification":{"steps":[...]}}
  JSON
  curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/tests" \
    -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
    -d @/tmp/cuerpo.json
  ```
  y guardar el `id` devuelto (o el que salió de la reconciliación) en el manifest.
- **Nunca mandar `status` en `Aprobado`/`Fallido`** — el test queda en `Pendiente`; correr
  los pasos y decidir si pasaron de verdad se hace desde "Verificar Funcionamiento" o
  "Correr todos" en la app, con la Base URL real configurada ahí.
- Si la reconciliación contra la API encuentra más de un test con el mismo `title` para el
  mismo Requerimiento (duplicados de corridas viejas, de antes de que este paso
  existiera), no elegir uno a ciegas: reportarlo en el resumen final para que el Tester
  decida cuál borrar (`DELETE $SCRUM_API_URL/api/v1/tests/$TEST_ID`).

## 6. Guardar el manifest y resumen final

Reescribir `scrumDocs/tests-manifest.json` completo (viejas entradas + nuevas/actualizadas) y
`scrumDocs/scrum-manifest.json` con los `testIds` que falten. Reportar, en texto:
- Cuántos tests se crearon o actualizaron, y para qué Requerimientos.
- Qué Requerimientos quedaron sin test porque no se encontró el código que los
  implementa.
- Cualquier endpoint que requiera un esquema de auth que el test no puede simular
  (para que el Tester sepa que ese paso hay que correrlo con cuidado o a mano).

---

## Notas de implementación

- Nunca inventar un endpoint o un código de estado esperado sin haberlo visto en el
  código — es preferible dejar un Requerimiento sin test a inventar uno que dé un falso
  verde o falso rojo.
- Nunca crear ni editar Requerimientos ni Historias de Usuario desde este skill.
- Nunca reintentar con otro shape de body si la API devuelve 403 al tocar un campo de
  ejecución — es intencional, no un error a esquivar.
- Si un paso tiene efectos secundarios reales (mails, cobros, borrados), usar datos de
  prueba que no afecten al sistema real, igual que ya se hizo antes para el endpoint de
  recuperación de contraseña.
- Todas las respuestas de error de la API vienen como `{"error": "..."}` — mostrar ese
  mensaje tal cual.
