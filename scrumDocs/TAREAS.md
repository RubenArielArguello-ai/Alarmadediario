# Tareas -- Alarmadediario

_Generado automaticamente el 2026-10-31T13:34:48.838Z -- no editar a mano, se sobreescribe en cada publicacion._

## HU-01: Deteccion automatica del diario

### RF-01: Validacion de la detección automática del diario (Funcional)

Verificar que el sistema detecte el diario mediante la cámara, registre el resultado y permita comprobar su funcionamiento con pruebas reproducibles. Documentar los casos probados y los errores encontrados.

**Condiciones de aprobación**

- El sistema procesa una imagen de prueba y muestra el resultado de la detección.
- Se registra el resultado de cada caso probado.
- Se documentan los falsos positivos, falsos negativos y errores encontrados, si los hay.
- Las pruebas pueden repetirse siguiendo instrucciones documentadas.

### RF-02: Integracion y verificación del detector hibrido (Funcional)

Verificar la integración del detector hibrido incorporado al proyecto, incluyendo la detección por modelo, la configuración del objeto buscado y el funcionamiento del chequeo periódico . registrar errores y resultados de las pruebas.

**Condiciones de aprobación**

.El servidor inicia correctamente 
.El detector procesa imágenes y muestra el resultado  del chequeo
.Se documentan los errores encontrados y las pruebas realizadas.

## HU-02: Evaluasion automatizada del sistema

### RF-01: Verificacion de resultado del harness hibrido (Funcional)

Revisar la ejecución  del hartes hibrido, comprobar los resultados registrados y documentar los casos exitosos, los errores y las limitaciones de la evaluación.

**Condiciones de aprobación**

.El harness se ejecuta sin errores 
.Se genera o actualiza el reporte de evaluación
.Los resultados y los casos de prueba quedan documentados

## HU-03: Pipeline de integracion continua

### RF-01: Verificacion del pipeline CI/CD (Funcional)

Revisar que el pipeline del repositorio ejecute las verificaciones configuradas ante los cambios, registrar el resultado y documentar cualquier fallo.

**Condiciones de aprobación**

.El pipeline se ejecuta ante un cambio o PR
.Las verificaciones configuradas finalizan correctamente o dejan el error identificado.
.El resultado queda documentado.

## HU-04: Gestion y documentacion del proyecto

### RF-01: Actualizacion de documentación tecnica y resultados. (Funcional)

Revisar y actualizar el README del repositorio para describir el detector hibrido, los requisitos de instalación, la ejecución, las pruebas realizadas, los resultados obtenidos y las limitaciones conocidas.

**Condiciones de aprobación**

.EL README explica como instalar y ejecutar el proyecto
.Se documentan los modelos utilizandos y sus requisitos 
.Se incluyen los resultados de evaluación y sus limitaciones. 

## RO-01: Captura de imagen mediante camara

### RF-01: Captura de imagen mediante camara (Funcional)

El sistema debe obtener imagenes en tiempo real mediante la camara para disponer de os datos necesarios para el procesamiento y posterior deteccion del diario


**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-02: Procesamiento de imagen con Open cv

### RF-01: Procesamiento de imagen con Open cv (Funcional)

El sistema debe procesar los cuadros obtenidos desde la camara utilizando open cv para preparar la imagen y permitir la identificacion del diario 

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-03: Deteccion automatica de diario

### RF-01: Deteccion automatica de diario (Funcional)

El siatema deve analizar las imagenes procesadas y detrerminar si el diario se encuentra presente frente a la amara , informando de la deteccion.

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-04: Evaluacion automatizada mediante harness

### RF-01: Evaluacion automatizada mediante harness (Funcional)

El proyecto debe ejecutar una evaluacion automatizada mediante harness para verificar el funcionamiento de la deteccion del diario y validar los resultados obtenidos.

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-05: Generacion de reporte de evaluacion

### RF-01: Generacion de reporte de evaluacion (Funcional)

el sistema de evaluacion debe generar un reporte con los resultadfos obtenidos para facilitar el analisis seguimiento y verificacion del funcionamiento del proyecto.

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-06: Pipeline integracion ciontinua

### RF-01: Pipeline integracion ciontinua (Funcional)

El proyecto debe contar con un pipeline automatizado que ejecute las validaciones configuradas cuando se ejecuten cambios en el repositorio, permitiendo detectar errores antes de integrar los cambios.

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._

## RO-07: Documentacion y mantenimiento del proyecto

### RF-01: Documentacion y mantenimiento del proyecto (Funcional)

La documentacion del proyecto debe mantenerse actualizada y versionada junto con el codigo para facilitar el seguimiento, mantrenimiento y comprension del sistema.

**Condiciones de aprobación**

_Sin condiciones de aprobación cargadas: pedíselas al Project Manager o al Scrum Master antes de darlo por terminado._
