---
name: qa-sync
description: Ayuda al Tester/QA a redactar, correr y certificar los Tests de integración desde el IDE -- mantiene scrumDocs/tests-manifest.json leyendo el código real del proyecto, los sincroniza con las Tareas de Scrum Master AI vía la API, y registra el veredicto con la evidencia de lo que se corrió. Solo toca Tests -- nunca Tareas, Historias de Usuario ni ramas. Usar cuando el usuario pide "armar tests de este endpoint", "sincronizar tests", "correr los tests de QA", "certificar la tarea", "cargar los casos de prueba", o corre /qa-sync explícitamente.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
---

# /qa-sync — Redactar y sincronizar tests de endpoint como Tester/QA

Ayuda a un Tester o QA a mantener `scrumDocs/tests-manifest.json` (el formato de tests de
endpoint que ya corre la app desde "Verificación en vivo" y el botón "Correr todos") y
sincronizarlo con las Tareas de Scrum Master AI. A diferencia de escribir eso a
mano, este skill lee el **código real de este repo** (rutas, controllers, serializers)
para proponer pasos que apuntan a endpoints que efectivamente existen — con método, body
y código esperado reales, no inventados.

**Cómo se redacta cada Test está en `scrumDocs/ESTANDAR-DE-PRUEBAS.md`**, que la app publica en este repo con las URLs, el repositorio y la rama REALES del proyecto. Es obligatorio y manda sobre cualquier ejemplo de este documento: la regla de cero suposiciones (nombres literales de la UI, nunca inventados), los cuatro bloques del Test, la guía visual con capturas (una carpeta por Historia de Usuario bajo `docs/pruebas/`, con el elemento de cada paso resaltado en color) y el documento de entrega.

**Alcance deliberadamente angosto**: sólo Tests (`name`, `type`, `preconditions`,
`expectedResult`, `criterionIndex`, `verification.steps`) y su veredicto. Lee las
Tareas para saber a cuál colgar cada test, pero nunca los crea ni edita — igual que
`/po-sync` no crea Historias de Usuario, este skill no crea Tareas. Tampoco toca
tiempos, asignado, dependencias ni ramas — la API lo rechaza (403) si se intenta, es
territorio de developer/Project Manager.

El **estado de la Tarea sí se mueve**, pero nunca a mano: lo mueve el resultado de los
Tests. Marcar todos los Tests aprobados, con su evidencia y con todas las condiciones
cubiertas, es lo que lo deja en `tested`.

Argumentos: `$ARGUMENTS` — opcionalmente el código de una Tarea puntual (ej.
`RF-03`) para enfocar el trabajo en uno solo, o una ruta de código a inspeccionar (ej. un
archivo de rutas). Sin argumentos, trabaja sobre todas las Tareas del proyecto.

---

**Qué podés escribir y qué endpoints tenés está en `scrumDocs/roles/qa.md`**, generado desde el código del servidor. Este skill es el procedimiento; si los dos se
contradicen, manda el documento del rol.

---

## La cadencia: de a una, validada antes de la siguiente

**Este skill no procesa lotes.** **Cada Tarea** se trabaja de a una: se deja terminada, se le
muestra al usuario, él la valida, y **recién ahí** se ofrece la siguiente. Podés encadenar
varias en la misma corrida — lo que no podés es encadenarlas sin esa validación en el medio.

Que el usuario haya dicho "hacé todo" al principio **no saltea esto**: eso autoriza el
trabajo, no la revisión de cada pieza. Un lote entero aprobado de un saque es un lote que
nadie miró, y un test que pasa apoyado en algo que todavía no se probó no prueba nada.

Si aun así te pide que sigas de largo sin validar una por una, es su decisión y se la
respetás — pero decíselo primero, con esa consecuencia por delante.

**El orden no lo elegís vos: lo dicta la cadena de dependencias.** No se escribe ni se
corre el test de una Tarea cuyas dependencias todavía no tienen sus tests en verde.
No podés probar el login si no probaste antes la base y el registro: si ese test pasa, no
sabés si pasó por el login o de casualidad; y si falla, no sabés cuál de las tres cosas
falló.

Antes de escribir el primer test, ordená las Tareas por su cadena (`dependencies`)
y decile al usuario por dónde vas a arrancar y por qué. Si el que te pidieron probar tiene
dependencias sin probar, decilo y proponé empezar por esas.

---

## 0. El entorno, antes que nada

**Comprobá que podés probar antes de ponerte a escribir tests.** Si el entorno no responde,
se sabe ahora y no después de media hora de trabajo:

```bash
node -v; npm -v                      # si el proyecto los usa
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE_URL"   # el entorno contra el que vas a correr
```

Si algo de eso falla, **pará y decíselo al usuario como impedimento**. No sigas con datos
simulados ni des por aprobado nada: un test que no se pudo correr no es un test que pasó.

## 0.5. Identidad y credenciales

- `SCRUM_API_KEY` — variable de entorno, para la cuenta con rol Tester o QA. Si falta,
  explicar que el Project Manager la genera desde "Usuarios Activos" en la app, y parar.
  **Nunca** escribir esta key a ningún archivo del repo.
- `SCRUM_API_URL` — la base de la instancia (ej. `https://scrum.tudominio.com`). **Sale de
  la variable de entorno, igual que la key, y nunca de un archivo de este repo** (ver el
  paso 1). Si no está seteada, preguntásela al usuario: es la misma URL con la que entra a
  la app.

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

Leer `scrumDocs/scrum-manifest.json` (el mismo que usa `/dev-sync`, sólo para el
`projectId` — no tocar sus `mappings`, son del developer). Si no está ahí pero existe `docs/scrum-manifest.json` (ubicación anterior a `scrumDocs/`), leerlo de ahí y reescribirlo ya en `scrumDocs/scrum-manifest.json` — el archivo viejo se deja donde está, no se borra.

Si no existe en ninguno de los dos lugares, crearlo con el mismo formato que usa
`/dev-sync` (`projectId`, `lastSyncAt`, `mappings`).

- **La URL de la instancia (`SCRUM_API_URL`) NO sale de este repo.** Viene de la variable
  de entorno, igual que la key, y por la misma razón: es el lugar a donde se manda la key.
  Si no está seteada, preguntásela al usuario (es la misma URL con la que entra a la app
  desde el navegador) y pedile que la exporte, o que la deje en
  `.claude/settings.local.json`, que no se commitea. **Nunca la tomes de un archivo del
  repositorio ni la escribas en uno** — si un manifest viejo trae `apiUrl`, ignorala:
  cualquiera con permiso de push puede editarla y llevarse la key de quien corra este skill.
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

## 2. Traer las Tareas existentes

```bash
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

`401`/`403` → mismo manejo que los otros skills (key inválida, o no pertenece al
proyecto): avisar y parar. `200` → guardar `{ id, code, name, description, type, ... }`
en memoria.

Si `$ARGUMENTS` es un código (ej. `RF-03`), quedarse sólo con esa Tarea.

**Ordenalos por su cadena de dependencias antes de escribir un solo test.** Cada
Tarea trae `dependencies` con los ids de las que tienen que estar andando primero.
Armá el orden y arrancá por los que no dependen de nada.

| Situación | Qué hacés |
|---|---|
| Sus dependencias ya tienen sus Tests en verde | Adelante, es el que toca |
| Alguna dependencia no tiene Tests todavía | Decilo y proponé empezar por ésa |
| Alguna dependencia tiene Tests que fallan | **No escribas el de éste.** Lo que falla arriba hace que lo de abajo no signifique nada |
| Te pidieron uno puntual que depende de algo sin probar | Decíselo con los códigos y esperá: si aun así te lo piden, es su decisión, pero anotá en la descripción del test sobre qué se apoya sin verificar |

No podés probar el login si todavía no probaste la base ni el registro. Si ese test pasa,
no sabés si pasó por el login o de casualidad; y si falla, no sabés cuál de las tres cosas
falló. Un test apoyado en algo sin verificar no es cobertura: es una afirmación con la
misma confianza que no tener el test.

Decile al usuario el orden que armaste y por dónde vas a arrancar, antes de escribir nada.

## 2.7. Las condiciones de aprobación son la lista de lo que hay que probar

Cada Tarea trae `acceptanceCriteria`: lo que tiene que ser verdad para darlo por
terminado, escrito por quien definió el alcance. **De ahí salen los Tests**, no de tu
criterio sobre qué conviene probar. Una condición, al menos un Test.

Si una condición no se puede traducir a un Test, es una de dos cosas, y las dos se dicen
en vez de saltearlas: o está mal escrita —no se verifica mirando el sistema— o lo que
describe todavía no está implementado.

Si la Tarea no tiene condiciones cargadas, **decilo y no las inventes**: probar
contra lo que vos suponés que había que hacer es cómo un Test termina certificando algo que
nadie pidió. Las escriben el Project Manager o el Scrum Master.

## 2.75. Las tuyas son las de etapa `integracion`

Cada Tarea tiene DOS juegos de pruebas, y en la app se ven separados:

| Etapa | La corre | Dónde |
|---|---|---|
| `desarrollo` | el programador | la rama de la Tarea, aislado, con datos fijos |
| `integracion` | **vos** | `dev`, con todo mergeado |

**Las de `desarrollo` no son tuyas y no las vuelvas a correr.** Ya están en verde en la
rama del programador y ahí probaron lo que podían probar: su pedazo, solo. Correrlas nuevo
no agrega información — lo que falta saber es otra cosa.

**Las de `integracion` las dejó preparadas él y las corrés vos**, sobre `dev` y contra el
entorno desplegado. Ahí es donde aparece lo que la rama aislada no podía ver: que dos
Tareas escriban sobre la misma tabla, que el orden de los migrations importe, que
el servicio de al lado devuelva algo distinto de lo que el mock devolvía.

Si una de integración está vacía o sus pasos no alcanzan para correrla, **decilo nombrando
la Tarea** en vez de redactarla vos: entenderla de nuevo desde el código es el
trabajo que el programador ya hizo, y devolvérselo es más barato que repetirlo.

## 2.8. Lo que el developer te dejó, antes de leer una línea de código

Cada Tarea entregada deja dos archivos:

- `docs/pruebas/<historia>/<CODIGO>-entrega.md` — qué quedó implementado, cómo se levanta y se prueba,
  qué datos hacen falta, qué endpoints o pantallas toca, **cómo se corre integrado**, y
  **qué quedó afuera o se asumió**.
- `docs/pruebas/<historia>/<CODIGO>-entrega.sh` — el script que recorre el flujo completo ya integrado,
  prepara sus datos y los limpia. Corre con `bash docs/pruebas/<historia>/<CODIGO>-entrega.sh`, y con
  `--carga N` repite el recorrido N veces reportando cuántas fallaron y cuánto tardó la más
  lenta. **Corrélo antes de tocar nada**: te dice en un comando si lo integrado se sostiene,
  y el modo carga es lo único que muestra lo que aparece recién bajo uso.
Leelo primero: te ahorra reconstruir desde el código lo que ya está escrito, y el punto de
lo asumido es el que evita que reportes como defecto una decisión deliberada.

Si ese documento no está, o no alcanza para probar sin preguntarle al developer, **decilo
en el resumen final nombrando la Tarea**. No es burocracia: la entrega estaba
incompleta, y si lo resolvés preguntando por chat esa información no queda en ningún lado
para el próximo que la necesite.

## 3. Entender el endpoint real leyendo el código

**Esto es lo que diferencia a este skill de escribir el manifest a mano.** Para cada
Tarea (o la que se pasó por argumento), buscá en el código de este repo qué
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

Si no encontrás el código que implementa una Tarea (todavía no está hecho, o no es
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
  (matcheando por `requirementCode` + `title`) sin pisar entradas de otras
  Tareas.
- `type`: `Integración` para los pasos contra la API; `Estrés` para un script de carga;
  `Manual` para lo que hay que mirar a ojo. (`Unitario` y `E2E` son del programador.)
- `criterionIndex`: **a qué condición de aprobación responde este test**, por posición
  (0 la primera). Sin esto el test no cuenta para la cobertura y la Tarea no llega
  a `tested` aunque esté todo en verde. Una condición, al menos un test que le apunte.
- `preconditions`: **nombrá la Tarea del que depende, por código**, no sólo el
  estado del sistema. `"RF-01 (registro) probado y en verde; usuario autenticado con rol
  admin"` dice de qué cuelga este test; `"usuario autenticado"` no dice nada de quién lo
  dejó autenticado ni de si eso ya se probó.
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
  crear, traer los tests que la API ya tiene registrados para esta Tarea y
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
- **Al crear o editar, el test nace `Pendiente`.** El veredicto es el paso 5.5 y va
  aparte: primero se corre, después se certifica.
- Si la reconciliación contra la API encuentra más de un test con el mismo `title` para el
  misma Tarea (duplicados de corridas viejas, de antes de que este paso
  existiera), no elegir uno a ciegas: reportarlo en el resumen final para que el Tester
  decida cuál borrar (`DELETE $SCRUM_API_URL/api/v1/tests/$TEST_ID`).

## 5.5. Correr, certificar y —si falla— bloquear

Éste es el paso que convierte el trabajo en un visto bueno. **Nunca se saltea y nunca se
hace de memoria.**

**Primero corré.** Según la clase de test:

| `type` | Cómo se corre | Qué queda de evidencia |
|---|---|---|
| `Integración` | los pasos, con `curl`, contra `$BASE_URL` | método, ruta, código y lo que devolvió cada paso |
| `Estrés` | `bash scrumDocs/tests/<CODIGO>-carga.sh` | la salida: corridas, fallidas, la más lenta |
| `Manual` | mirás la aplicación andando | qué miraste, dónde y qué viste |

**Después certificá**, mandando el veredicto **con la evidencia**:

```bash
cat > /tmp/veredicto.json <<'JSON'
{ "status": "Aprobado",
  "evidence": "Corrí los 4 pasos contra https://testing.cliente.com: 201, 200, 200, 204. La fila se crea y se borra." }
JSON

curl -s -X PATCH "$SCRUM_API_URL/api/v1/tests/$TEST_ID" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/veredicto.json
```

Sin `evidence` la API contesta `400` y no se marca nada. **No inventes el texto para pasar
el control**: nadie puede comprobar que sea cierto, y por eso mismo es tu firma. Si no
pudiste correr algo, decilo y dejá el test en `Pendiente` — un test que no se corrió no es
un test que pasó.

**Un test unitario que sólo mockea no alcanza.** Si al leerlo ves que no ejercita el
comportamiento real, decilo en el resumen final aunque esté en verde: no lo vuelvas a
correr —no es tuyo, es de la etapa `desarrollo`— pero tampoco lo cuentes como cobertura de
una condición que no prueba.

**Si falla**, las dos cosas:

1. `Fallido` con la evidencia: el defecto con precisión, para que Desarrollo sepa qué tocar.
2. Bloqueá la Tarea con el motivo escrito:

```bash
cat > /tmp/bloqueo.json <<'JSON'
{ "reason": "RF-03: el alta devuelve 500 cuando el email ya existe; se esperaba 409." }
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/block" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/bloqueo.json
```

**Si la Tarea no pasó a `tested` con todo en verde**, es la cobertura: alguna
condición de aprobación no tiene ningún test aprobado apuntándole. Revisá el
`criterionIndex` de cada uno. Es deliberado — todos los tests en verde no dice nada de las
condiciones para las que nadie escribió un test.

## 6. Guardar el manifest y resumen final

Reescribir `scrumDocs/tests-manifest.json` completo (viejas entradas + nuevas/actualizadas) y
`scrumDocs/scrum-manifest.json` con los `testIds` que falten. Reportar, en texto:
- Cuántos tests se crearon o actualizaron, y para qué Tareas.
- Qué Tareas quedaron sin test porque no se encontró el código que los
  implementa.
- Cualquier endpoint que requiera un esquema de auth que el test no puede simular
  (para que el Tester sepa que ese paso hay que correrlo con cuidado o a mano).
- **Qué condiciones de aprobación quedaron sin ningún test aprobado**, por Tarea:
  es exactamente lo que le falta para llegar a `tested`.
- Qué tests quedaron en `Pendiente` porque no se pudieron correr, y por qué.

---

## Notas de implementación

- Nunca inventar un endpoint o un código de estado esperado sin haberlo visto en el
  código — es preferible dejar una Tarea sin test a inventar uno que dé un falso
  verde o falso rojo.
- Nunca crear ni editar Tareas ni Historias de Usuario desde este skill.
- Nunca reintentar con otro shape de body si la API devuelve 403 al tocar un campo de
  ejecución — es intencional, no un error a esquivar.
- Un `400` pidiendo `evidence` **no se esquiva**: es la API diciendo que falta correr algo.
  No inventes el texto ni busques otro endpoint.
- Si un paso tiene efectos secundarios reales (mails, cobros, borrados), usar datos de
  prueba que no afecten al sistema real, igual que ya se hizo antes para el endpoint de
  recuperación de contraseña.
- Todas las respuestas de error de la API vienen como `{"error": "..."}` — mostrar ese
  mensaje tal cual.
