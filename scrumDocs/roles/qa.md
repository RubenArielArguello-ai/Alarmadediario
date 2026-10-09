# QA — qué podés hacer en este proyecto

_Generado automáticamente el 2026-10-09T16:54:35.448Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. El procedimiento paso a paso está en
`.claude/skills/qa-sync/SKILL.md`.

## En una línea

Escribís, ejecutás y **certificás** los Tests, y promovés `dev → testing`. Tu visto bueno
deja la Tarea en `tested`, listo para que el Project Manager lo lleve a producción.
**No tocás Tareas ni Historias de Usuario**: tu trabajo entra por las rutas de Tests.

Trabajás **desde tu IDE**. La interfaz gráfica hace lo mismo y podés usarla cuando te
convenga —para mirar la corrida dibujada, sobre todo—, pero no hace falta pasar por ahí: los
dos caminos terminan en el mismo lugar y con los mismos controles.

## Tu lugar en el circuito

```
merged_dev ──promote──▶ in_testing ──los tests deciden──▶ tested
           └── vos ──┘                └── vos ──┘
```

`tested` no lo fija nadie a mano: sale del resultado de los Tests. Si un test falla, la
Tarea vuelve a **Haciendo** y el developer lo retoma.

## El orden lo dicta la cadena, no vos

No se prueba una Tarea cuyas dependencias todavía no tienen sus Tests en verde. No
podés probar el login si no probaste antes la base y el registro: si ese test pasa, no
sabés si pasó por el login o de casualidad; y si falla, no sabés cuál de las tres cosas
falló.

Antes de escribir el primer test, ordená las Tareas por `dependencies` y arrancá
por los que no dependen de nada.

Esto ordena la **certificación**, no el desarrollo. Un developer puede adelantar una
Tarea posterior mientras el anterior está trabado — gana tiempo real y está bien
que lo haga. Lo que no se adelanta es el sello: mientras su dependencia no esté en verde,
lo que pruebes de él vale hasta ahí, y así hay que decirlo. Las `preconditions` de cada test **nombran la
Tarea del que dependen, por código** — "RF-01 (registro) probado y en verde", no
"usuario autenticado".

**Cómo se redacta cada Test está en `scrumDocs/ESTANDAR-DE-PRUEBAS.md`**, que la app publica en este repo con las URLs, el repositorio y la rama REALES del proyecto. Es obligatorio y manda sobre cualquier ejemplo de este documento: la regla de cero suposiciones (nombres literales de la UI, nunca inventados), los cuatro bloques del Test, la guía visual con capturas (una carpeta por Historia de Usuario bajo `docs/pruebas/`, con el elemento de cada paso resaltado en color) y el documento de entrega.

## Las tuyas son las de integración

Cada Tarea tiene dos juegos de pruebas. Las de **`desarrollo`** las corrió el
programador en su rama, aislado y con datos fijos: ya probaron lo que podían probar y no
hace falta repetirlas. Las de **`integracion`** son tuyas, sobre `dev` y con todo mergeado
— ahí aparece lo que la rama aislada no podía ver: dos Tareas escribiendo sobre la
misma tabla, un orden de migraciones que importa, el servicio de al lado devolviendo algo
distinto de lo que el mock devolvía.

## Tus tres clases de prueba

| Clase (`type`) | Qué es | De dónde sale la evidencia |
|---|---|---|
| `Integración` | pasos contra la API, los corre el motor | la salida de la corrida, se llena sola |
| `Estrés` | un script que escribís vos | la salida del script |
| `Manual` | lo verificás a ojo | qué miraste, dónde y qué viste |

Lo **manual** no es el plan B: es el único camino para una condición visual. Si el criterio
dice "la barra lateral izquierda ya no está", no hay paso HTTP que lo pruebe — y un test de
endpoint en verde al lado de ese criterio es peor que no tener ninguno, porque parece
cobertura.

La de **estrés** la escribís vos, en `scrumDocs/tests/<CODIGO>-carga.sh`, commiteada. Que
imprima cuántas corridas, cuántas fallaron y cuánto tardó la más lenta. No la confundas con
`docs/pruebas/<historia>/<CODIGO>-entrega.sh --carga N`: esa es del developer y estresa **su** flujo.

## Sin evidencia no hay veredicto

Marcar un Test `Aprobado` o `Fallido` **exige** mandar `evidence`: qué corriste y qué viste.
Sin eso la API contesta `400`. No es una formalidad ni una regla de buena conducta —es la
puerta a producción, y antes se abría sola.

```bash
cat > /tmp/veredicto.json <<'JSON'
{ "status": "Aprobado",
  "evidence": "Corrí los 4 pasos contra https://testing.cliente.com: 201, 200, 200, 204. La fila queda y se borra." }
JSON

curl -s -X PATCH "$SCRUM_API_URL/api/v1/tests/$TEST_ID" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/veredicto.json
```

Nadie puede comprobar que ese texto sea cierto: lo escribís vos y el sistema te cree. Lo que
sí queda es el rastro —en la tarjeta y en el registro de actividad— y lo lee el Project
Manager antes de promover. Aprobar sin haber corrido nada no es difícil, es **deshonesto**, y
queda firmado con tu nombre.

Si corriste algo y falló, marcalo `Fallido` con el defecto preciso y **bloqueá** la
Tarea (`POST /api/v1/requirements/[id]/block`) con el motivo escrito. Un `Fallido`
solo ya lo manda a `blocked`, pero el motivo que escribas vos es lo que le dice a Desarrollo
qué corregir.

## Ninguna condición sin su Test

Cada Test se cuelga de una **condición de aprobación** de la Tarea, por posición:
`criterionIndex` (0 para la primera). La Tarea **no llega a `tested`** mientras
alguna condición no tenga al menos un Test aprobado apuntándole — por más que todos los Tests
cargados estén en verde.

Los Tests que la app genera desde las condiciones ya vienen con la suya puesta. Los que
escribas a mano, asignásela vos: sin eso no cuentan para la cobertura y la Tarea se
queda corto sin que se vea por qué.

## Lo que tenés derecho a recibir

Una Tarea entregada trae tres cosas: el documento `docs/pruebas/<historia>/<CODIGO>-entrega.md`,
el script `docs/pruebas/<historia>/<CODIGO>-entrega.sh` —que recorre el flujo integrado y con `--carga N`
lo repite midiendo— y **sus Tests de integración ya preparados**, con pasos y datos, listos
para que les des correr. La vara del developer es que vos puedas probar sin preguntarle
nada.

Si falta, no lo suplas en silencio: nombralo. Una entrega que sólo se puede validar
conversando es una entrega incompleta, y esa conversación no queda registrada para el
próximo.

## De dónde salen los Tests

De las **condiciones de aprobación** de la Tarea (`acceptanceCriteria`), no de tu
criterio sobre qué conviene probar. Una condición, al menos un Test. Si alguna no se puede
traducir a un Test, está mal escrita o lo que describe todavía no existe — las dos cosas se
dicen, no se saltean.

## Qué escribís de la Tarea

Este rol **no escribe ningún campo** de la Tarea: un `PATCH` responde 403. Su trabajo entra por otras rutas (ver los endpoints de más abajo).

Que no escribas ningún campo de la Tarea es deliberado, no un permiso que falte: lo
que QA aporta son Tests y su resultado, y eso mueve la tarjeta solo.

## Tus endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/api/v1/me` | Quién sos: id, username, rol y los proyectos de los que sos miembro. Es la primera llamada de cualquier skill. |
| `GET` | `/api/v1/projects/[id]` | Datos del proyecto: nombre, repositorio, rama por defecto, guía de estilo. |
| `GET` | `/api/v1/projects/[id]/deliveries` | Los Sprints comprometidos con el cliente y su fecha. |
| `GET` | `/api/v1/projects/[id]/environments` | Las URLs de los entornos (dev, testing, producción) para verificar pruebas contra el que corresponda. |
| `GET` | `/api/v1/projects/[id]/members` | El equipo del proyecto con el rol de cada uno. Es de dónde sale el `assignee` al repartir. |
| `GET` | `/api/v1/projects/[id]/modules` | Los Módulos del proyecto. |
| `POST` | `/api/v1/projects/[id]/promote` | Promover la rama entera de un entorno al siguiente: `dev → testing` o `testing → main`. `dev → testing` lo hacen QA y el PM; `testing → main`, sólo el PM. El pase a producción se rechaza si queda algo sin testear (`force` es del PM y queda logueado). |
| `GET` | `/api/v1/projects/[id]/requirements` | Todas las Tareas del proyecto con su estado, su responsable, su estimación y sus dependencias. |
| `GET` | `/api/v1/projects/[id]/user-stories` | Historias de Usuario y contenedores operacionales, con sus Tareas colgando. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear una Tarea con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de una Tarea, con su estado y su resultado. |
| `POST` | `/api/v1/requirements/[id]/tests` | Crear un Test de una Tarea. |
| `DELETE` | `/api/v1/tests/[id]` | Borrar un Test. |
| `PATCH` | `/api/v1/tests/[id]` | Editar un Test o marcar su resultado. |

## Cómo se promueve a testing

```bash
cat > /tmp/cuerpo.json <<'JSON'
{ "from": "dev", "to": "testing" }
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/promote" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Viaja la rama entera, no una Tarea: todo lo que esté en `merged_dev` pasa a
`in_testing` en la misma llamada. `{"yaAlDia": true}` significa que `testing` ya tenía todo
lo de `dev` y no se movió ninguna tarjeta — no es un error.

`testing → main` **no es tuyo**: contesta 403, lo hace el Project Manager.

## Lo que NO podés, y a quién pedírselo

| Querés | Te contesta | Se lo pedís a |
|---|---|---|
| Corregir el texto de una Tarea | 403 | el Project Manager |
| Mover una tarjeta a mano | 403 | el Scrum Master, si el proyecto no tiene webhook |
| Promover a producción | 403 | el Project Manager |
| Que se arregle lo que falló | — | marcá `Fallido` con evidencia y bloqueá con el motivo escrito |
| Aprobar sin haber corrido nada | 400 | correlo; sin `evidence` la API no te deja |
