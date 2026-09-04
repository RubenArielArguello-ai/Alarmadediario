# Empezá acá: este repo está conectado a Scrum Master AI

_Generado automáticamente el 2026-09-04T13:56:27.920Z -- no editar a mano, se sobreescribe en cada publicación._

Si el usuario te pidió leer la documentación de este proyecto, o arrancó una conversación
sobre "qué sigue", "cargar requerimientos", "sincronizar tests", "reportar avance" o
similar, seguí estos pasos antes de hacer nada más.

Este documento **no dice qué puede hacer cada rol**: identifica de quién es la key y te
manda al documento de ese rol (`scrumDocs/roles/<rol>.md`), que es donde están sus
permisos, sus endpoints y su procedimiento. Un rol, un archivo: no leas los otros salvo
que necesites entender qué le podés pedir a otra persona del equipo.

## 1. Conseguir la API key

Preguntale al usuario **sólo** por `SCRUM_API_KEY` (si no la tenés ya como variable de
entorno) — se la genera su Project Manager desde "Usuarios Activos" en la app. Si no la
tiene, explicáselo y pedile que la consiga antes de seguir. **Nunca** la escribas a ningún
archivo del repo, sólo se usa desde la variable de entorno.

## 2. La URL de la instancia ya la sabés -- no la preguntes

`SCRUM_API_URL` es `https://scrum.misitiowebpersonal.com.ar`. Se generó sola a partir de la URL con la que tu
Project Manager entra a la app, así que es un dato fijo de este repo, no algo que
tengas que pedirle a nadie. Usala directo en las llamadas de los pasos siguientes.
Si vas a crear/leer `scrumDocs/scrum-manifest.json` o `scrumDocs/po-manifest.json` (se usan
de acá en adelante para no repetir preguntas), guardala ahí en el campo `apiUrl`
si todavía no está.

## 3. Identificar el rol — nunca preguntarlo

Con la key y la URL, llamá:

```bash
curl -s "$SCRUM_API_URL/api/v1/me" -H "Authorization: Bearer $SCRUM_API_KEY"
```

La respuesta trae `{ role, projects, ... }`. El rol de la cuenta dueña de la key es el
único dato que importa (la API lo vuelve a validar en cada llamada de todos modos) —
**no le preguntes al usuario "cuál es tu rol"**, ni le creas si te lo dice: usá el `role`
que devolvió `/api/v1/me`. `401` significa key inválida o revocada: avisar y parar.

Con ese `role` en mano, **leé el documento de ese rol y nada más**:

| `role` | Documento | Skill |
|---|---|---|
| `developer` | `scrumDocs/roles/developer.md` | `.claude/skills/dev-sync/SKILL.md` |
| `qa` | `scrumDocs/roles/qa.md` | `.claude/skills/qa-sync/SKILL.md` |
| `product_owner` | `scrumDocs/roles/product-owner.md` | `.claude/skills/po-sync/SKILL.md` |
| `scrum_master` | `scrumDocs/roles/scrum-master.md` | `.claude/skills/sm-sync/SKILL.md` |
| `project_manager` | `scrumDocs/roles/project-manager.md` | `.claude/skills/pm-sync/SKILL.md` |
| `admin` | — | — (el admin no entra a los proyectos: sólo puede llamar `/api/v1/me`) |

## 4. Resolver el proyecto y dar una bienvenida orientadora (no un resumen técnico)

Antes de preguntarle "qué querés hacer" a ciegas, armale un pantallazo real de en qué está
parado. Esto reemplaza cualquier mensaje tipo "repositorio clonado, autenticación
verificada" — ese resumen de infraestructura no le sirve de nada al usuario; lo que
necesita es entender qué hay en el proyecto y qué puede pedir a partir de acá.

1. **Resolver `projectId`**: buscarlo en `scrumDocs/scrum-manifest.json` o
   `scrumDocs/po-manifest.json` (el que exista en este repo). Si ninguno lo tiene, usar
   `projects` de la respuesta del paso 3: un solo elemento → usarlo directo; varios →
   listarlos y preguntar cuál; vacío → avisar que el Project Manager todavía no lo agregó a
   ningún proyecto, y parar.
2. **Traer el estado actual**:
   ```bash
   curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" \
     -H "Authorization: Bearer $SCRUM_API_KEY"
   ```
3. **Con eso, escribile un mensaje de bienvenida en texto natural** (nunca una lista de
   pasos técnicos tipo "clonación/autenticación/manifest"), que incluya:
   - Nombre del proyecto, cuántas Historias de Usuario tiene, y cuántos Requerimientos
     desglosados por estado (`to_do`/`doing`/`blocked`/`pr_open`/`merged_dev`/`in_testing`/`tested`/`in_production`)
     — así ya sabe si el proyecto recién arranca o viene con trabajo en curso.
   - Qué puede pedirte a partir de acá, en casos de uso concretos: eso está en la sección
     "Lo que más vas a hacer" del documento de su rol, escrito en lenguaje de usuario.
   - Para qué sirve `scrumDocs/scrum-manifest.json` (o `po-manifest.json`) que se acaba de
     leer o crear: guarda `projectId` y `apiUrl` para no volver a preguntarlos nunca más en
     este repo, no tiene secretos, conviene commitearlo.
   - **Cerrá proponiendo el siguiente paso concreto, no con una pregunta abierta.** El
     documento del rol dice cuál es para ese rol. Proponelo como algo que podés hacer ahora
     mismo ("¿arranco por X?"). Sólo si ninguno de esos casos aplica, preguntá abierto.

## 4.5. Lo que el usuario dicta en la conversación se sube en el momento

Si en el medio de la charla el usuario describe una Historia de Usuario, un avance, un test
o un bloqueo, eso es contenido de la app: no lo dejes en el chat esperando que alguien se
acuerde de pedir "sincronizá". Escribilo al documento que le corresponde
(`scrumDocs/historias-po.md` para el Product Owner — si no existe, crealo) y subilo en la
misma corrida siguiendo el skill de su rol. Recién después contale qué quedó cargado, con
código y nombre.

La excepción es borrar: crear y editar se deshacen con otra corrida, borrar no. Todo DELETE
sigue necesitando confirmación explícita del usuario, aunque el documento o la conversación
lo den por descartado.

## 5. Cómo se manda el cuerpo de un POST/PATCH (aplica a todas las llamadas)

La API acepta **JSON estricto** y nada más: comillas dobles en las claves y en los valores
de texto, sin comas colgando y sin comentarios. `{'name': 'x'}` (comillas simples) y
`{name: "x"}` (clave sin comillas) **no son JSON** — la API responde
`400 {"error":"JSON invalido"}`.

Los textos de este dominio vienen en castellano y traen apóstrofes, comillas y saltos de
línea. Pegados adentro de `-d '...'` rompen el quoting del shell antes de que la API llegue
a ver nada. **Escribí el cuerpo a un archivo y mandalo con `-d @`**, que no depende del
shell:

```bash
cat > /tmp/cuerpo.json <<'JSON'
{
  "name": "Planificar la ruta del vehículo",
  "description": "Como operador quiero cargar un destino y que el sistema calcule la ruta.",
  "type": "funcional"
}
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/user-stories/$USER_STORY_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Un salto de línea dentro de un valor va como `\n`, nunca literal. Los criterios de
aceptación y las listas de pasos son un solo string con `\n`, no un array.

Qué te está diciendo cada error, para no corregir lo que no es:

| Respuesta | Qué está mal | Qué NO hay que tocar |
|---|---|---|
| `400 {"error":"JSON invalido"}` | el cuerpo no es JSON | la key, el rol, el endpoint |
| `400` con otro mensaje (`"name es requerido"`) | falta o sobra un campo | el JSON en sí, que ya parseó bien |
| `401` | la key es inválida o está revocada | el cuerpo |
| `403` | el rol de esa key no puede hacer esa acción | el cuerpo y la key |

Un `403` **nunca** se resuelve reintentando con otra key ni cambiando el endpoint: quiere
decir que esa acción es de otro rol. El documento del rol dice a quién pedírsela.

## 6. Seguir el documento del rol y su skill

El documento del rol (`scrumDocs/roles/<rol>.md`) dice **qué** puede hacer esa persona:
campos, estados y endpoints. El skill (`.claude/skills/<rol>-sync/SKILL.md`) dice **cómo**
se hace, paso a paso. Los dos ya están en este repo: no hace falta que el usuario escriba
ningún slash command, seguilos vos directamente.

Los pasos 1 a 4 de acá ya cubren las credenciales, el rol y el proyecto, así que salteá
esos pasos del skill. Lo que **no** se saltea es la sección 5: el formato del cuerpo rige
para toda llamada que escriba algo.
