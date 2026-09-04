# QA — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-04T13:56:25.643Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. El procedimiento paso a paso está en
`.claude/skills/qa-sync/SKILL.md`.

## En una línea

Escribís y ejecutás los Tests, y promovés `dev → testing`. **No tocás Requerimientos ni
Historias de Usuario**: tu trabajo entra por las rutas de Tests.

## Tu lugar en el circuito

```
merged_dev ──promote──▶ in_testing ──los tests deciden──▶ tested
           └── vos ──┘                └── vos ──┘
```

`tested` no lo fija nadie a mano: sale del resultado de los Tests. Si un test falla, el
Requerimiento vuelve a **Haciendo** y el developer lo retoma.

## Qué escribís del Requerimiento

Este rol **no escribe ningún campo** del Requerimiento: un `PATCH` responde 403. Su trabajo entra por otras rutas (ver los endpoints de más abajo).

Que no escribas ningún campo del Requerimiento es deliberado, no un permiso que falte: lo
que QA aporta son Tests y su resultado, y eso mueve la tarjeta solo.

## Tus endpoints

| Método | Ruta | Para qué |
|---|---|---|
| `GET` | `/api/v1/me` | Quién sos: id, username, rol y los proyectos de los que sos miembro. Es la primera llamada de cualquier skill. |
| `GET` | `/api/v1/projects/[id]` | Datos del proyecto: nombre, repositorio, rama por defecto, guía de estilo. |
| `GET` | `/api/v1/projects/[id]/deliveries` | Las Entregas comprometidas con el cliente y su fecha. |
| `GET` | `/api/v1/projects/[id]/environments` | Las URLs de los entornos (dev, testing, producción) para verificar pruebas contra el que corresponda. |
| `GET` | `/api/v1/projects/[id]/members` | El equipo del proyecto con el rol de cada uno. Es de dónde sale el `assignee` al repartir. |
| `GET` | `/api/v1/projects/[id]/modules` | Los Módulos del proyecto. |
| `POST` | `/api/v1/projects/[id]/promote` | Promover la rama entera de un entorno al siguiente: `dev → testing` o `testing → main`. `dev → testing` lo hacen QA y el PM; `testing → main`, sólo el PM. El pase a producción se rechaza si queda algo sin testear (`force` es del PM y queda logueado). |
| `GET` | `/api/v1/projects/[id]/requirements` | Todos los Requerimientos del proyecto con su estado, asignado, estimación y dependencias. |
| `GET` | `/api/v1/projects/[id]/user-stories` | Historias de Usuario y contenedores operacionales, con sus Requerimientos colgando. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de un Requerimiento, con su estado y su resultado. |
| `POST` | `/api/v1/requirements/[id]/tests` | Crear un Test de un Requerimiento. |
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

Viaja la rama entera, no un Requerimiento: todo lo que esté en `merged_dev` pasa a
`in_testing` en la misma llamada. `{"yaAlDia": true}` significa que `testing` ya tenía todo
lo de `dev` y no se movió ninguna tarjeta — no es un error.

`testing → main` **no es tuyo**: contesta 403, lo hace el Project Manager.

## Lo que NO podés, y a quién pedírselo

| Querés | Te contesta | Se lo pedís a |
|---|---|---|
| Corregir el texto de un Requerimiento | 403 | el Project Manager |
| Mover una tarjeta a mano | 403 | el Scrum Master, si el proyecto no tiene webhook |
| Promover a producción | 403 | el Project Manager |
| Que se arregle lo que falló | — | bloqueá el Requerimiento con el motivo escrito |
