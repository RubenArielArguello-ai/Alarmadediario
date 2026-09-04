# Developer — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-04T13:56:24.408Z -- no editar a mano, se sobreescribe en cada publicación._

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
- **El paso a Hecho lo decide la persona, no vos.** Con las pruebas corridas, mostrale el
  resultado (cuántas pasaron, cuántas fallaron), qué implementaste y cuánto lleva corrido el
  reloj, y preguntale si lo damos por terminado — diciendo explícitamente que abrir el PR y
  pasar a Hecho **corta el reloj**. Si dice que no, o pide cambios, o no contesta: la
  tarjeta se queda en `doing` y el reloj sigue. Esa confirmación no se saltea aunque te
  hayan dicho "hacé todo" al principio: es la única acción que congela el cronómetro, y una
  vez congelado, el tiempo que se siga trabajando no se lo cobra nadie.
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
| `PATCH` | `/api/v1/requirements/[id]` | Editar un Requerimiento: mover la tarjeta, asignar, estimar, anotar observaciones, agendar. Qué campos podés tocar depende del rol, y el developer sólo sobre lo que tiene asignado. Ver la sección "Campos" de este documento. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `POST` | `/api/v1/requirements/[id]/claim` | Tomar para vos un Requerimiento libre, o quitárselo a otro developer. Si mandás `status: doing` por PATCH sobre uno sin asignar, la toma es automática y este POST no hace falta. |
| `POST` | `/api/v1/requirements/[id]/github/branch` | Abrir la rama de trabajo del Requerimiento en GitHub. Es el acto que arranca el reloj. |
| `POST` | `/api/v1/requirements/[id]/gitlab/branch` | Abrir la rama de trabajo del Requerimiento en GitLab. Es el acto que arranca el reloj. |
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
