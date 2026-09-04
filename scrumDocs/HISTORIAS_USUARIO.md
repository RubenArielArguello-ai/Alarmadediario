# Historias de Usuario -- Alarmadediario

_Generado automaticamente el 2026-09-04T13:56:09.762Z -- no editar a mano, se sobreescribe en cada publicacion._

## HU-01: Deteccion automatica del diario

Como usuario quiero que el sistema detecte un objeto mediante la camara para poder identificarlo en tiempo real

### Criterios de Aceptacion

- Dado a que la camara esta disponible, cuando el sistema comienza la deteccion,  entonces debe procesar la imagen  de la camara y esta la  presencia del diario.
- Dado a que el diario se encuentra frente a la camara cuando el sistema lo detecta entonces debe indicar que el sistema fue detectado
- Dado a que el diario no se encuentra cuando se procesa la imagen entonces el sistema debe indicar que no fue detectado

### Detalle Tecnico y Reglas de Negocio

La funcionalidad utiliza Python y herramientas de procesamiento de imágenes como OpenCV para obtener y analizar los cuadros provenientes de la cámara.

La detección debe ejecutarse de manera controlada y no debe interrumpir la ejecución del sistema ante errores de captura de cámara.

Los cambios relacionados con esta funcionalidad deben validarse mediante los mecanismos automatizados del proyecto y mantenerse versionados en GitHub.

No se deben almacenar credenciales, tokens ni información sensible dentro del código fuente.

## HU-02: Evaluasion automatizada del sistema

Necesito disponer de la evaluacion automatizada del sistema para verificar que la deteccion del diario funciona bien

### Criterios de Aceptacion

- Dado a que el sistema esta disponible cuando se ejecuta la autoevaluasion automatizada, entonces debe realizar las verificasciones definidas y generar resulado.
- Dado a que finaliza la evaluacion, cuando se procesan los resultados de las pruebas

### Detalle Tecnico y Reglas de Negocio

La evaluacion utiliza Harness y los scripts de evaluacion del proyecto. Los resultados deben permitir verificar el funcionamiento de la deteccion y detectar posibles errores

## HU-03: Pipeline de integracion continua

Dispongo de un pipeline automatizado para validar los cambios del proyecto y asegurar la calidad del sofweare.

### Criterios de Aceptacion

- Dado a que se realiza un cambio en el repositorio, cuando se ejecuta el pipeline, entonces deben ejecutarse autonaticamnete las validaciones configuradas.
- Dado que se finalizan las validaciones ,cuando odas son correctas, entonces el pipeline debe finalizar exitosamente.
- Dado a que una validacion falla, cuando termina el pipeline, entonces debe  informar el fallo para permitir su correccion.

### Detalle Tecnico y Reglas de Negocio

El proyecto utiliza automatizaciones mediante pipeline para validar los cambios. Las ejecuciones deben quedar registradas y permitir identificar errores durante el proceso de integracion.

## HU-04: Gestion y documentacion del proyecto

Como project Manager quiero mantener organizada y actualizada la documentacion del proyecto para facilitar el seguimiento, mantenimiento y evaluacion del sistema.

### Criterios de Aceptacion

- Dado a que se realizan cambios importantes en el proyecto cuando se actualiza la documentacion, entonces la informacion debe mantenerse coherente con la implementacion.
- Dado a que un integrante necesita comprender el proyecto ,cuando consulta la documentacion , entonces debe poder identificar su funcionamiento estructura y processos principales.
- Dado que el proytecto utiliza git hub y automatizaciones, cuando se consulta la documentacion, entonces deben estar registrados los procesos relevantes  de desarrollo y validacion.

### Detalle Tecnico y Reglas de Negocio

La documentacion debe mantenerse versionada en git hub. No se debe incluir credenciales token ni informacion sensible. Los cambios relevantes deben registrarse mediante commits.
