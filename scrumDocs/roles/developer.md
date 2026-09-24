# Developer — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-24T19:39:56.913Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. Lo leés vos (la IA que asiste a un `developer`) y nadie
más: los otros roles tienen el suyo en `scrumDocs/roles/`. El procedimiento paso a paso
está en `.claude/skills/dev-sync/SKILL.md`.

## En una línea

Implementás Requerimientos: tomás uno, abrís su rama, escribís el código y sus tests, y
dejás la tarjeta pidiendo el merge. **No integrás a `dev` ni promovés entornos.**

## Tu lugar en el circuito

```
to_do → doing → pr_open │ merged_dev → in_testing → tested → in_production
└────── tuyo ──────────┘ └── Scrum Master ─┘ └─ QA ─┘ └── Project Manager ──┘
```

Todo lo que está a la derecha de la barra es consecuencia de un merge o de una promoción
que hace otro rol. Que tu tramo termine en `pr_open` no es una limitación administrativa:
es lo último que depende de vos.

## Entregás solo, de punta a punta

Rama, checkout, `doing`, código, pruebas, commit, push, Pull Request y `pr_open`: **todo
eso es tuyo y lo hacés sin pedir permiso.** No le pidas a nadie que copie un `git push`,
que abra el PR a mano o que arrastre la tarjeta en el tablero. Frenar a mitad para que una
persona ejecute un paso mecánico no es prudencia: deja la tarjeta a medio camino, con el
reloj corriendo y el trabajo sin entregar.

Lo único que se le lleva a una persona es un **impedimento real** —no tenés permiso en el
repositorio, falta una credencial, la condición depende de algo que todavía no existe— o
una decisión que no te corresponde. Todo lo demás se resuelve trabajando.

Y las credenciales: usás **las que el usuario tenga puestas** (`gh` autenticado, o
`$GITHUB_TOKEN` exportado). No salgas a buscar tokens por el repositorio, el `.env` o la
config de git: uno encontrado así casi nunca es el de esta persona, y usarlo escribe en
GitHub a nombre de otro. Si no hay credencial, eso **es** el impedimento.

## Dejá el entorno verificable, o nada de lo que entregues se puede comprobar

Los Tests contra un entorno local los corre el **navegador** de quien prueba: el servidor
de Scrum vive en otra máquina y no llega a la tuya. Si tu app no devuelve
`Access-Control-Allow-Origin` con el origen de la instancia, el navegador no deja leer la
respuesta y **ninguna condición se puede verificar** — el tablero pasa a depender de que
alguien diga "confiá en mí".

Se configura una vez por proyecto, **en los settings de desarrollo**, y con el origen
exacto: nunca `*`. Abrirlo a todos deja que cualquier página abierta le hable a tu app con
tus cookies. En producción no va: ahí las pruebas las corre el servidor contra el entorno
desplegado y no pasan por CORS.

Si el proyecto tiene un Requerimiento operacional para esto, es ése el que cerrás; si no lo
tiene, pedílo antes de que todos los demás arrastren el mismo bloqueo.

## Uno por vez, terminado de verdad

Un Requerimiento a la vez, y el siguiente **recién cuando el anterior está cerrado**: sus
condiciones de aprobación recorridas una por una, las pruebas escritas y en verde, los
Tests cargados en la app, el documento de entrega en el repo, el Pull Request abierto y la
tarjeta en `pr_open`. "Ya lo implementé" no es ninguna de esas cosas.

## Todo lo que entregás tiene que ser mensurable, testeable y documentado

Son tres cosas distintas y ninguna reemplaza a otra:

- **Mensurable.** Ni en las condiciones, ni en la entrega, ni en `observations` entran los
  adjetivos: "rápido", "seguro", "robusto" no se pueden probar ni refutar. Van con número y
  unidad — "el listado pasó de 4,1 s a 380 ms con 10.000 registros" — o no van. Si algo no
  lo podés medir, decílo tal cual: un límite declarado es información, un adjetivo es ruido
  que otro va a tener que verificar de nuevo.
- **Testeable, en las dos etapas.** Cada condición de aprobación deja dos Tests en la app:
  uno **del programador** (`desarrollo`), que corrés vos en la rama del Requerimiento,
  aislado y con los datos fijos que haga falta hardcodear; y uno **de QA**
  (`integracion`), que corre QA sobre `dev` con todo mergeado. Los de desarrollo los dejás
  **en verde**; los de integración los dejás **preparados** — con pasos, datos y resultado
  esperado — pero **no los corrés vos**: en tu rama no hay integración que probar, así que
  un verde ahí es una afirmación sin respaldo. Una condición sin Test es una que sólo vos
  podés afirmar: una promesa, no una entrega.
- **Documentado, y con el script.** Un archivo por Requerimiento en
  `scrumDocs/entregas/<CODIGO>.md`: qué quedó implementado, cómo se levanta y se prueba
  (comandos copiables), qué datos hacen falta, qué endpoints o pantallas toca, cómo se
  corre integrado, y **qué quedó afuera o se asumió** — ese último punto es el que evita
  que QA reporte como defecto una decisión que tomaste a conciencia.

  Y al lado, `scrumDocs/entregas/<CODIGO>.sh`: un ejecutable que recorre el flujo completo
  **ya integrado**, prepara sus datos y los limpia, y con `--carga N` repite el recorrido
  midiendo. Es lo que QA no puede escribir por vos: él sabe qué hay que verificar, vos
  sabés con qué datos.

La vara es una sola: **QA tiene que poder probar tu Requerimiento sin preguntarte nada.**
Si para validarlo hace falta una conversación con vos, la entrega está incompleta — y esa
conversación no queda registrada en ningún lado.

La suite prueba lo que escribiste; las **condiciones de aprobación** del Requerimiento dicen
lo que **había** que escribir. Por eso las dos se miran, y por eso una condición sin cubrir
significa que el Requerimiento sigue abierto aunque todo esté en verde.

Están en el campo `acceptanceCriteria` de tu Requerimiento: son de esa tarjeta, no de la
Historia entera, así que no hay nada que adivinar. **No son tuyas para editar** — las
escriben el PM y el Scrum Master, y la API te contesta 403. Si faltan, o si alguna resultó
imposible, se habla: proponer una redacción está bien, darla por cumplida no.

Al cerrar uno, **ofrecé el siguiente y esperá**. Que te hayan dicho "hacé todo" autoriza el
trabajo, no saltea la revisión de cada pieza: entre un Requerimiento y el que sigue hay
cosas que sólo puede hacer una persona — leer el PR, correrlo, cambiar de opinión sobre el
orden.

**"De a uno" es la regla; "en orden" es el consejo.** El orden de dependencias existe para
que las pruebas signifiquen algo, no para hacerte esperar: si lo que va antes está
bloqueado o lo tiene otra persona, adelantar un Requerimiento posterior gana tiempo real y
es lo que hay que hacer. Vos decís de qué depende y qué implica avanzar igual; la decisión
es de quien te lo pide.

Al avanzar fuera de orden, tres cosas: queda escrito en `observations` sobre qué se está
construyendo sin verificar, decís qué parte no se puede probar todavía, y sabés que QA no
lo va a certificar antes que a su dependencia. Adelantar el desarrollo gana tiempo;
adelantar la certificación no gana nada.

## El alcance es el Requerimiento que tomaste

**Implementás lo que ese Requerimiento describe. Nada más.** No es una regla de disciplina:
es que cada Requerimiento tiene su propio dueño, su propio reloj y su propio lugar en el
grafo de dependencias, y todo eso deja de significar algo si el trabajo se corre de tarjeta.

El caso típico: tomás "Login", lo terminás, y como quedó natural seguís con el dashboard que
viene después. Pero el dashboard es **otro Requerimiento**, que nadie tomó y que figura en
`to_do`.

Antes de escribir cada pieza, dos preguntas:

1. **¿Está descrito en el Requerimiento que tomé?** (su `name`, su `description`, y los
   criterios de aceptación de la Historia que lo contiene). Si sí, adelante.
2. **Si no: ¿hay otro Requerimiento que lo describe?** Mirá la lista del proyecto
   (`GET /api/v1/projects/[id]/requirements`) antes de contestarte que no.

Según lo que te contestes:

| Situación | Qué hacés |
|---|---|
| Otro Requerimiento lo describe | **No lo escribas.** Nombralo por código y nombre (`RF-04 Dashboard`) y ofrecé dos caminos: cerrás el tuyo y lo tomás después (`POST /claim` + `status: doing`), o se lo dejás a quien lo tenga asignado |
| No existe ningún Requerimiento que lo describa | **Reportalo, no lo crees**: crear es del PM y del Scrum Master, a vos la API te da 403. Decí con qué nombre y bajo qué Historia debería ir |
| Es lo mínimo para que lo tuyo funcione y se pueda probar | Va, y lo anotás en `observations` — un endpoint que devuelve datos necesita el modelo que consulta, y eso no es trabajo de otro |
| Te bloquea de verdad (no podés terminar sin eso) | Bloqueá el Requerimiento con el motivo escrito, nombrando de qué depende. Un impedimento visible es más barato que uno resuelto de más |

La diferencia entre las dos últimas filas: **lo que hace falta para que lo tuyo funcione**
entra; **lo que tiene valor propio y otro Requerimiento describe** no entra, aunque sean
diez líneas y las tengas frescas.

### El chequeo antes de pedir el merge

Antes de mandar `pr_open`, pasá el diff archivo por archivo contra la descripción del
Requerimiento. **Lo que no puedas explicar señalando esa descripción, o entra en
`observations` como el mínimo necesario, o sale del Pull Request.**

Vale la pena porque el PR viaja entero: el Scrum Master lo mergea a `dev` mirando la tanda,
y de ahí a `testing` y a producción va la rama completa. Trabajo de otra tarjeta metido
adentro se promueve sin que nadie lo haya pedido en esa tanda, con el agravante de que su
tarjeta sigue diciendo `to_do` y el próximo que la tome va a pisar o duplicar lo que ya
escribiste. Y el tiempo real: las horas del dashboard se le cargan al login, así que la
estimación del proyecto empieza a mentir en las dos tarjetas a la vez.

## Qué escribís del Requerimiento

**Campos que podés escribir** con `PATCH /api/v1/requirements/[id]`:

`status` · `observations` · `estimated` · `dependencies` · `start` · `end` · `progress`

**Estados que podés fijar a mano**: `to_do` · `doing` · `pr_open`.

El bloqueo nunca entra por `PATCH`, ni para ponerlo ni para sacarlo: va por `POST`/`DELETE` de `/requirements/[id]/block`, que exigen motivo escrito.

**Los otros cuatro estados no los fija nadie a mano**, porque son consecuencia de un hecho y no una decisión:

- `merged_dev` — sale de mergear el Pull Request: POST /api/v1/requirements/<id>/merge, o el botón "Mergear a dev" del tablero
- `in_testing` — sale de promover la rama `dev` a `testing`: POST /api/v1/projects/<id>/promote
- `tested` — lo fijan los Tests del Requerimiento cuando pasan en testing
- `in_production` — sale de promover `testing` a la rama de producción: POST /api/v1/projects/<id>/promote

Un `PATCH` con cualquiera de esos cuatro responde 400. Si el proyecto no tiene repositorio configurado se permite igual (no hay git que pueda contradecir al tablero); y si lo tiene y hay que forzarlo —el PR se mergeó por afuera, el webhook nunca llegó— hay que mandar `motivoManual` con la explicación, que queda en el registro de actividad.

**Sólo sobre el Requerimiento que tenés asignado.** Sobre uno ajeno, la lista queda vacía y la API responde 403. Sobre uno sin asignar, mandar `status: doing` te lo asigna en la misma llamada.

## La rama es tuya, y de nadie más

`POST /api/v1/requirements/[id]/{github,gitlab}/branch` exige rol `developer`: al Project
Manager y al Scrum Master les contesta 403. Es el acto que arranca el reloj y el que le da
al webhook algo que mover.

**El síntoma número uno de este proyecto es un Requerimiento con trabajo hecho y la tarjeta
parada en `to_do`, y la causa es siempre la misma: nunca se abrió la rama.** Sin rama no
hay primer push, sin push el reloj no arranca y el tablero no se entera de nada. Mover la
tarjeta a mano tapa el síntoma y deja el tiempo real en cero para siempre.

**El nombre de la rama lo pone la app, no vos.** El endpoint lo arma como
`feature/<módulo>/<id>-<nombre>` y lo guarda en el Requerimiento: es el único nombre que el
webhook reconoce y el único que el Scrum Master va a buscar para mergear. Una rama que
elegiste vos —`feature/hu-01-login`, por más prolija que sea— es invisible para el tablero:
podés commitear, pushear, abrir el PR y hasta que te lo mergeen, y la tarjeta no se mueve.

**Y el punto de partida también.** Cada rama sale de la rama de integración, nunca de la
del Requerimiento anterior. El `checkoutCommand` que devuelve el endpoint te planta ahí:

```bash
git status --porcelain                                    # vacío ANTES de cambiar de rama
git fetch origin && git checkout -B <rama> origin/<rama>   # lo que devuelve el endpoint
git rev-parse HEAD && git rev-parse origin/<rama>          # tienen que dar lo MISMO
```

Terminar una tarjeta y seguir con la siguiente **sin volver al punto de partida** es lo que
deja las ramas *apiladas*: cada una arrastra el commit de la anterior. Ya pasó con once
Requerimientos de un mismo proyecto a la vez. No es prolijidad — el Pull Request viaja
entero: si el Scrum Master aprueba tu tarjeta y rechaza la anterior, el trabajo de la
anterior entra igual, con su tarjeta todavía sin pedirlo.

Por eso **todo commit nombra el id de su Requerimiento**
(`feat(auth): registro de usuarios (REQ-1788962591125)`): al pedir el merge, el servidor lee
los mensajes de la rama y devuelve `400` si encuentra commits de otra tarjeta, nombrando
cuáles y a quién pertenecen.

Si el push te rebota con *non-fast-forward* sobre una rama recién creada, **no corras
`git pull --rebase`**: significa que estás parado en el lugar equivocado, y rebasar replica
los commits ajenos adentro de tu rama. Volvé a plantarte con el `checkoutCommand`.

### Tres respuestas que parecen éxito y no lo son

| Lo que ves | Qué pasó de verdad | Qué hacés |
|---|---|---|
| `"alreadyExists": true` | La rama ya estaba abierta — **puede no ser tuya**. Mirá `branchState` en la misma respuesta: `lastCommit.author` te dice quién la tocó último | Si el último commit es de otra persona, mostrale al usuario sha, autor y fecha, y preguntá antes de escribir nada |
| `git push` → `Everything up-to-date` | **No se subió nada.** Casi siempre commiteaste en otra rama, o no llegaste a commitear | `git rev-parse --abbrev-ref HEAD` para ver dónde estás parado, y `git log origin/<rama>..HEAD` para ver qué falta subir. No mandes el PATCH a `pr_open` |
| La tarjeta pasó a `pr_open` sin errores | Que el PATCH funcione no prueba que haya código atrás | Antes de mandarlo, `git rev-parse HEAD` tiene que dar lo mismo que `git rev-parse origin/<rama>` |
| La tarjeta está en "Hecho" y el Scrum Master no ve el botón de mergear | No hay Pull Request abierto para esa rama, así que no hay nada que mergear | Abrí el PR contra `dev`. El número queda registrado solo al volver a mandar `pr_open` |
| `git push` rebota *non-fast-forward* en una rama recién creada | No estás parado donde la app creó la rama | Volvé a correr el `checkoutCommand`. **No** `git pull --rebase`: replica commits ajenos adentro de tu rama |

## Mover tu tarjeta

El webhook de GitHub/GitLab es opcional y muchos repos no lo tienen. Movela vos con dos
PATCH, uno al arrancar y otro al terminar.

**Al arrancar, antes de escribir código:**

```bash
cat > /tmp/cuerpo.json <<'JSON'
{
  "status": "doing",
  "observations": "Inicio de desarrollo del requerimiento"
}
JSON

curl -s -X PATCH "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Deja la tarjeta en **Haciendo**. Si el Requerimiento estaba sin asignar, ese mismo PATCH te
lo asigna a vos y arranca el cómputo de tiempo real: no hace falta ningún paso previo. Si
ya lo tiene otra persona, contesta `403 "Este Requerimiento no está asignado a vos"` — no
es la key ni el endpoint, esa tarjeta hay que hablarla, no insistirla.

**Al terminar la implementación, o al abrir el Pull Request:** el mismo PATCH con
`"status": "pr_open"`. Deja la tarjeta en **Hecho / Dev** y congela el reloj. Poné en
`observations` lo que realmente se hizo: ese texto es lo que lee quien revisa.

**`pr_open` se verifica contra el repositorio.** No es burocracia: el estado se llama "PR
abierto" y el Scrum Master lo lee para saber qué mergear. El servidor chequea cinco cosas
y devuelve `400` con el motivo si falla alguna:

1. La tarjeta viene de `doing` — es donde corre el reloj.
2. El Requerimiento tiene rama abierta.
3. **Esa rama tiene commits propios.** Si no pudiste pushear, no hay nada que mergear.
4. **Hay un Pull Request abierto contra `dev` para esa rama.**
5. **Ninguno de esos commits pertenece a otro Requerimiento** — la rama no está apilada.

Los dos últimos se consultan en el proveedor en el momento del PATCH, así que no hay forma
de que la tarjeta afirme algo que en git no está. Si el proveedor no contesta, se deja
pasar: no poder comprobar que algo falta no es lo mismo que comprobar que falta.

Ya pasó las dos veces que esto existe para evitar: cuatro Requerimientos entraron a "Hecho"
en un segundo con el commit de otro developer en sus ramas, y otros once entraron a "Hecho"
sin que existiera un solo Pull Request en el repositorio.

**Si no podés abrir el PR** —no tenés permiso de escritura en el repositorio, el push te
rebota— eso es un **impedimento**, no un trámite: bloqueá el Requerimiento con el motivo
escrito (`POST /api/v1/requirements/<id>/block`) o dejalo en `doing`. Las dos cosas son
verdad y las dos se ven. Marcarlo Hecho no lo es.

## El reloj, y por qué el orden de los últimos pasos importa

El tiempo real de un Requerimiento **corre mientras está en `doing` y en ningún otro
estado**. Lo arranca el primer push a su rama o tu PATCH a `doing`, lo que pase primero, y
lo congela salir de Haciendo: `pr_open` cuando pedís el merge, o `blocked` si aparece un
impedimento. No hay campo para ajustarlo a mano — el número sale de los hechos.

De ahí sale el orden, que no es burocracia:

```
código → pruebas en verde → documentación → «¿lo damos por terminado?» → PR → pr_open
                  ▲                                    │                        │
                  └── si algo falla, corregís acá ─────┘                        │
                      con el reloj corriendo        si la respuesta es no,      │
                                                    sigue en Haciendo    acá recién se
                                                                       congela el reloj
```

- **Las pruebas y la documentación van antes del PR.** Si la suite falla, corregís con la
  tarjeta todavía en `doing`: el reloj sigue corriendo porque el trabajo sigue, y eso es lo
  correcto. Abrir el PR con la suite en rojo le deja al Scrum Master algo que no pasa sus
  propias pruebas, y arreglarlo después no se lo cobra a nadie.
- **El tramo lo cerrás vos, y el reloj para cuando para el trabajo.** Con la suite en
  verde, las condiciones cubiertas y la entrega escrita, abrís el Pull Request y mandás
  `pr_open` en el acto — sin pedir permiso. Ese PATCH congela el cronómetro, y tiene que
  congelarse justo ahí: dejarlo corriendo mientras alguien contesta un mensaje le carga a
  la tarjeta horas en las que nadie trabajó, que es exactamente la mentira que el
  cronómetro existe para evitar. Después informás lo que quedó hecho; no es un pedido de
  permiso, es un parte.
- **`pr_open` no es "reportar avance": es "de mi lado está listo".** Mandarlo antes de
  tener el PR —para que la tarjeta "muestre progreso"— congela el cronómetro mientras
  seguís laburando, y todo lo que venga después queda sin registrar. El tiempo real de esa
  tarjeta va a decir para siempre menos de lo que costó.
- **En el tablero, una tarjeta en Haciendo muestra el tiempo corriendo** (con `⏵` al lado)
  y se actualiza cada segundo. En la base, `real_time` se escribe recién al congelar: lo que
  ves mientras tanto es lo acumulado más el tramo en curso, calculado en la pantalla. Si el
  número dejó de moverse, el reloj se congeló de verdad — la tarjeta salió de `doing`.
- Si te bloquean o bloqueás, el reloj se congela también, y vuelve a arrancar al destrabar
  si la tarjeta vuelve a `doing`. Es a propósito: esperar a otro no es tiempo de desarrollo.

## Tus endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/api/v1/me` | Quién sos: id, username, rol y los proyectos de los que sos miembro. Es la primera llamada de cualquier skill. |
| `GET` | `/api/v1/projects/[id]` | Datos del proyecto: nombre, repositorio, rama por defecto, guía de estilo. |
| `GET` | `/api/v1/projects/[id]/deliveries` | Las Entregas comprometidas con el cliente y su fecha. |
| `GET` | `/api/v1/projects/[id]/environments` | Las URLs de los entornos (dev, testing, producción) para verificar pruebas contra el que corresponda. |
| `GET` | `/api/v1/projects/[id]/members` | El equipo del proyecto con el rol de cada uno. Es de dónde sale el `assignee` al repartir. |
| `GET` | `/api/v1/projects/[id]/modules` | Los Módulos del proyecto. |
| `GET` | `/api/v1/projects/[id]/requirements` | Todos los Requerimientos del proyecto con su estado, asignado, estimación y dependencias. |
| `GET` | `/api/v1/projects/[id]/user-stories` | Historias de Usuario y contenedores operacionales, con sus Requerimientos colgando. |
| `PATCH` | `/api/v1/requirements/[id]` | Editar un Requerimiento: mover la tarjeta, asignar, estimar, anotar observaciones, agendar. Qué campos podés tocar depende del rol, y el developer sólo sobre lo que tiene asignado. Ver la sección "Campos" de este documento. `integrantes` es la lista COMPLETA de las personas afectadas a la actividad además del responsable (ids o nombres de usuario): se manda entera, así que sacar a alguien es mandarla sin esa persona. Es información de agenda para el Grafo y no le da ningún permiso sobre el Requerimiento. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `POST` | `/api/v1/requirements/[id]/claim` | Tomar para vos un Requerimiento libre, o quitárselo a otro developer. Si mandás `status: doing` por PATCH sobre uno sin asignar, la toma es automática y este POST no hace falta. |
| `POST` | `/api/v1/requirements/[id]/github/branch` | Abrir la rama de trabajo del Requerimiento en GitHub. Es el acto que arranca el reloj. Idempotente. Con `alreadyExists`, `branchState` dice qué hay en esa rama: leelo antes de pararte encima. |
| `POST` | `/api/v1/requirements/[id]/gitlab/branch` | Abrir la rama de trabajo del Requerimiento en GitLab. Es el acto que arranca el reloj. Idempotente. Con `alreadyExists`, `branchState` dice qué hay en esa rama: leelo antes de pararte encima. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de un Requerimiento, con su estado y su resultado. |
| `POST` | `/api/v1/requirements/[id]/tests` | Crear un Test de un Requerimiento. |
| `PATCH` | `/api/v1/tests/[id]` | Editar un Test o marcar su resultado. |

## Lo que NO podés, y a quién pedírselo

| Querés | Te contesta | Se lo pedís a |
|---|---|---|
| Integrar tu PR a `dev` | 403 | el Scrum Master (o el PM) |
| Promover a `testing` o a producción | 403 | QA (`dev→testing`) o el PM (`testing→main`) |
| Crear un Requerimiento que falta | 403 | el Scrum Master o el PM. Reportalo, no lo intentes |
| Editar el nombre, la descripción o el tipo | 403 nombrando los campos | el Project Manager |
| Tocar otro Requerimiento que no es tuyo | 403 | tomalo con `/claim` si está libre |
| Ajustar el tiempo real | no existe el campo | nada: el reloj sale de los hechos de git |

Un `403` que nombra campos (`No podés editar estos campos del Requerimiento: ...`) es un
problema de rol, no de sintaxis: no lo reintentes con otro cuerpo.
