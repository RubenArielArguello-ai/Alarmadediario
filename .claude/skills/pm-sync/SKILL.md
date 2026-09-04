---
name: pm-sync
description: Conduce un proyecto de Scrum Master AI desde el IDE del Project Manager -- pasa revista al estado (qué está bloqueado, qué espera merge, qué se prometió y para cuándo), carga o corrige el alcance (Historias, Requerimientos, Módulos, Entregas), integra a `dev` lo que ya pidió el merge, y promueve `testing → main` cuando todo lo de la tanda pasó sus pruebas. Usar cuando el usuario pide "cómo viene el proyecto", "qué está trabado", "cargá este requerimiento", "pasá esto a producción", "armá la entrega", o corre /pm-sync explícitamente. Requiere una key con rol project_manager.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(curl *)
  - Bash(git *)
  - Write
---

# /pm-sync — Conducir el proyecto como Project Manager

El Project Manager es el rol que cubre a todos los demás, así que este skill no es "otro
`/dev-sync` con más permisos": es el que asume que quien lo corre **decide**, y por lo
tanto le muestra primero lo que está detenido y lo que está por vencer, no lo que está
saliendo bien.

**Qué podés escribir y qué endpoints tenés está en `scrumDocs/roles/project-manager.md`**,
generado desde el código del servidor. Este skill es el procedimiento; si los dos se
contradicen, manda el documento del rol.

Argumentos: `$ARGUMENTS`.

- **(vacío)** → `estado`: el pantallazo de conducción.
- **`alcance`** → cargar o corregir Historias, Requerimientos, **operacionales**, Módulos y Entregas.
- **`integrar`** → mergear a `dev` los Requerimientos en `pr_open`.
- **`producción`** (o `produccion`) → promover `testing → main`.
- **`publicar`** → recordar cómo se republica la documentación en el repo.

---

## 0. Identidad y credenciales

- `SCRUM_API_KEY` — variable de entorno. Si no está, pedírsela al usuario y parar. **Nunca**
  escribirla a ningún archivo del repo.
- `SCRUM_API_URL` — sale de `.claude/settings.json` (`env.SCRUM_API_URL`) o del manifest
  del repo. Si no está en ninguno, preguntarla una vez y guardarla en el manifest.

## 1. Confirmar el rol antes de cualquier otra cosa

```bash
curl -s "$SCRUM_API_URL/api/v1/me" -H "Authorization: Bearer $SCRUM_API_KEY"
```

Si `role` **no** es `project_manager`, este no es el skill: derivá al que corresponde
(`sm-sync`, `dev-sync`, `qa-sync`, `po-sync`) y pará. No intentes las llamadas igual "por
si acaso": la API contesta 403 y el usuario se queda pensando que la key está mal.

Resolvé `projectId` como siempre: manifest del repo, o `projects` de la respuesta; si hay
varios, preguntá cuál.

## 2. Modo `estado` (el que corre sin argumentos)

Traé, en este orden, y resumí en **una** respuesta en prosa:

```bash
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/requirements" -H "Authorization: Bearer $SCRUM_API_KEY"
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/deliveries"   -H "Authorization: Bearer $SCRUM_API_KEY"
curl -s "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/members"      -H "Authorization: Bearer $SCRUM_API_KEY"
```

Y contá, en este orden de importancia:

1. **Lo bloqueado**: cada `blocked` con su motivo, quién lo tiene que destrabar y desde
   cuándo. Es lo único que no avanza solo.
2. **Lo que espera integración**: los `pr_open`. Si hay Scrum Master en el equipo
   (`members`), decilo pero no lo mergees vos: es su trabajo, y hacérselo le saca la única
   señal que tiene del ritmo del equipo. Si no hay, ofrecé `pm-sync integrar`.
3. **Las Entregas comprometidas** cuya fecha esté cerca, y qué Requerimiento las cierra:
   una Entrega cuyo Requerimiento está en `to_do` es un problema hoy, no la semana que
   viene.
4. **Lo que nadie puede empezar**: Historias sin ningún Requerimiento colgando, y
   Requerimientos sin asignar cuyas dependencias ya están resueltas.

Cerrá proponiendo **una** acción concreta, la de arriba de esa lista.

## 3. Modo `alcance`

Crear una Historia de Usuario, un Requerimiento adentro de ella, un Módulo o una Entrega.
Todo va con `-d @/tmp/cuerpo.json` (ver la sección 5 de `scrumDocs/EMPEZA-ACA-SEGUN-TU-ROL.md`:
el JSON en línea se rompe con los apóstrofes del castellano).

```bash
# Historia de Usuario
curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json          # { "name": "...", "description": "...", "kind": "historia" }

# Requerimiento adentro de esa Historia
curl -s -X POST "$SCRUM_API_URL/api/v1/user-stories/$USER_STORY_ID/requirements" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json          # { "name": "...", "description": "...", "type": "funcional" }
```

**El trabajo que no nace de una Historia de Usuario va como operacional** (`kind:
"operacional"`): la VM donde va a correr `testing` para que QA valide, la de `tested` para
mostrarle el avance al cliente, la máquina de producción donde corre `main` con su dominio y
su certificado, una capacitación, una auditoría. Lo creás vos o el Scrum Master.

```bash
cat > /tmp/cuerpo.json <<'JSON'
{
  "kind": "operacional",
  "name": "Preparar la máquina de producción",
  "description": "Dominio, certificado, variables de entorno y backups para la rama main.",
  "estimated": "8h",
  "assignee": "jlopez",
  "deliveryId": "DEL-3"
}
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/user-stories" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Nace con su primer Requerimiento adentro (`estimated` y `assignee` van a ese hijo, que es el
que se ve en el Kanban y en el Grafo). Para sumarle tareas, colgale más Requerimientos al
contenedor con `POST /api/v1/user-stories/$CONTENEDOR_ID/requirements`. Y engancharlo como
`dependencies` de lo que lo necesita es la mitad del valor: una demo al cliente que espera
una máquina que nadie levantó tiene que verse en el Grafo.

Reglas que evitan el ida y vuelta:

- **Un Requerimiento cuelga siempre de una Historia**: si el usuario dicta uno suelto,
  resolvé primero bajo cuál va, o creá la Historia.
- **`type`** de un Requerimiento es `funcional` o `no_funcional`. Lo *operacional* no es un `type`: es el `kind` del contenedor, como arriba.
- **Antes de borrar cualquier cosa, confirmación explícita.** Crear y editar se deshacen
  con otra corrida; borrar arrastra todo lo que cuelga y no se deshace.
- Las Entregas son sólo tuyas (`POST /projects/$PROJECT_ID/deliveries`). Qué Requerimiento
  cierra una Entrega se marca con `deliveryId` en ese Requerimiento — vinculá **sólo** el
  que la cierra: lo que ése necesita entra solo por sus dependencias.

## 4. Modo `integrar`

Igual que `/sm-sync integrar`, con tu key: listar los `pr_open` y ofrecer mergear de a uno,
con confirmación antes de cada merge.

```bash
curl -s -X POST "$SCRUM_API_URL/api/v1/requirements/$REQUIREMENT_ID/merge" \
  -H "Authorization: Bearer $SCRUM_API_KEY"
```

`409` significa que ese Requerimiento no está en `pr_open` (nadie pidió el merge, o el
review pidió cambios y quedó `blocked`): no es un error a reintentar.
`{"yaEstabaMergeado": true}` significa que el PR ya había entrado.

## 5. Modo `producción`

Sos el único que promueve `testing → main`.

```bash
cat > /tmp/cuerpo.json <<'JSON'
{ "from": "testing", "to": "main" }
JSON

curl -s -X POST "$SCRUM_API_URL/api/v1/projects/$PROJECT_ID/promote" \
  -H "Authorization: Bearer $SCRUM_API_KEY" -H "Content-Type: application/json" \
  -d @/tmp/cuerpo.json
```

Si responde que faltan pruebas, **nombrá los Requerimientos que devolvió y pará**. `force`
existe y es tuyo, pero se pregunta antes: git arrastra la rama entera, así que forzar hace
que el tilde de producción diga algo que nadie verificó. Queda anotado como
`PROMOTE_FORCED` en el registro de actividad.

`{"yaAlDia": true}` significa que producción ya tenía todo lo de `testing`: no se movió
ninguna tarjeta y no hay nada que desplegar.

## 6. Modo `publicar`

Los cuatro documentos derivados (plan, Historias, Requerimientos, grafo) se republican
solos cada vez que cambia un Requerimiento o una Historia. **Los skills y los documentos de
rol, no**: esos se publican desde la web, con el botón "Publicar" del proyecto, y hay que
volver a apretarlo cuando la instancia se actualiza. Es una ruta de sesión web: con la API
key contesta 401, así que no la intentes por curl — decíselo al usuario y pará.

## Cierre de cualquier modo

Contá qué cambió con código y nombre (`RF-03 Alta de pacientes → merged_dev`), no
"operación completada". Y si quedó algo que depende de otra persona, nombrala: el valor de
este skill es que el PM sepa a quién le toca lo próximo.
