# Product Owner — qué podés hacer en este proyecto

_Generado automáticamente el 2026-09-04T13:56:23.375Z -- no editar a mano, se sobreescribe en cada publicación._

Este es el documento de **tu** rol. El procedimiento paso a paso está en
`.claude/skills/po-sync/SKILL.md`.

## En una línea

Escribís las Historias de Usuario con sus criterios de aceptación. **Los Requerimientos no
son tuyos**: los desglosan el Project Manager y el Scrum Master a partir de lo que vos
escribís.

## Tu lugar en el circuito

Estás antes del tablero. Cuando una Historia queda escrita y con criterios claros, el PM o
el SM la desglosan en Requerimientos y ahí arranca la ejecución. Una Historia sin ningún
Requerimiento colgando es trabajo que nadie puede empezar: es lo primero que conviene
mirar.

## Qué escribís del Requerimiento

Este rol **no escribe ningún campo** del Requerimiento: un `PATCH` responde 403. Su trabajo entra por otras rutas (ver los endpoints de más abajo).

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
| `POST` | `/api/v1/projects/[id]/user-stories` | Crear una Historia de Usuario (`kind: "historia"`) o un **Requerimiento operacional** (`kind: "operacional"`): el trabajo real que no nace de una Historia — levantar la VM donde va a correr `testing`, preparar la de producción, una capacitación, una auditoría, una reunión con el cliente. El Product Owner sólo `historia`; el **Scrum Master sólo `operacional`**; el PM las dos. El operacional nace con su primer Requerimiento adentro, así que `estimated` y `assignee` del cuerpo van a ese hijo. |
| `DELETE` | `/api/v1/requirements/[id]/block` | Destrabar: saca el candado y devuelve la tarjeta al estado anterior. |
| `POST` | `/api/v1/requirements/[id]/block` | Bloquear un Requerimiento con motivo escrito y responsable. Congela el reloj. Cualquier miembro bloquea: el impedimento lo encuentra quien lo encuentra. `esRechazo: true` (review que pide cambios) es sólo del PM y del Scrum Master. |
| `GET` | `/api/v1/requirements/[id]/tests` | Los Tests de un Requerimiento, con su estado y su resultado. |
| `DELETE` | `/api/v1/user-stories/[id]` | Borrar una Historia de Usuario o un Requerimiento operacional con todo lo que cuelga. Mismo reparto por `kind` que el POST. |
| `PATCH` | `/api/v1/user-stories/[id]` | Editar una Historia de Usuario o un Requerimiento operacional. Mismo reparto por `kind` que el POST. Renombrar un operacional que tiene un solo hijo le propaga el nombre. Los campos de ejecución (fechas, Entrega) los escribe sólo el PM. |

Los tres primeros son los que usás todo el tiempo: crear, editar y borrar Historias
(`kind: historia`). Los contenedores operacionales — capacitaciones, auditorías, tareas sin
usuario final — **no son tuyos**: son del Scrum Master y del PM, y la API te contesta 403
si mandás `kind: operacional`.

## Lo que NO podés, y a quién pedírselo

| Querés | Te contesta | Se lo pedís a |
|---|---|---|
| Crear o editar un Requerimiento | 403 | el Project Manager o el Scrum Master |
| Mover una tarjeta del Kanban | 403 | el Scrum Master |
| Estimar o poner fechas | 403 | el Scrum Master agenda, el PM decide el alcance |
| Frenar algo que está mal entendido | — | eso **sí** podés: bloqueá el Requerimiento con el motivo |

Que un Requerimiento esté mal desglosado se arregla hablando con quien lo escribió, o
bloqueándolo con el motivo. Si el usuario te dicta un Requerimiento nuevo, **reportalo como
pendiente** con el texto que él dictó, no intentes crearlo.
