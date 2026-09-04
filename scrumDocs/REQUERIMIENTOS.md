# Requerimientos -- Alarmadediario

_Generado automaticamente el 2026-09-04T13:56:10.843Z -- no editar a mano, se sobreescribe en cada publicacion._

## RO-01: Captura de imagen mediante camara

### RF-01: Captura de imagen mediante camara (Funcional)

El sistema debe obtener imagenes en tiempo real mediante la camara para disponer de os datos necesarios para el procesamiento y posterior deteccion del diario


## RO-02: Procesamiento de imagen con Open cv

### RF-01: Procesamiento de imagen con Open cv (Funcional)

El sistema debe procesar los cuadros obtenidos desde la camara utilizando open cv para preparar la imagen y permitir la identificacion del diario 

## RO-03: Deteccion automatica de diario

### RF-01: Deteccion automatica de diario (Funcional)

El siatema deve analizar las imagenes procesadas y detrerminar si el diario se encuentra presente frente a la amara , informando de la deteccion.

## RO-04: Evaluacion automatizada mediante harness

### RF-01: Evaluacion automatizada mediante harness (Funcional)

El proyecto debe ejecutar una evaluacion automatizada mediante harness para verificar el funcionamiento de la deteccion del diario y validar los resultados obtenidos.

## RO-05: Generacion de reporte de evaluacion

### RF-01: Generacion de reporte de evaluacion (Funcional)

el sistema de evaluacion debe generar un reporte con los resultadfos obtenidos para facilitar el analisis seguimiento y verificacion del funcionamiento del proyecto.

## RO-06: Pipeline integracion ciontinua

### RF-01: Pipeline integracion ciontinua (Funcional)

El proyecto debe contar con un pipeline automatizado que ejecute las validaciones configuradas cuando se ejecuten cambios en el repositorio, permitiendo detectar errores antes de integrar los cambios.

## RO-07: Documentacion y mantenimiento del proyecto

### RF-01: Documentacion y mantenimiento del proyecto (Funcional)

La documentacion del proyecto debe mantenerse actualizada y versionada junto con el codigo para facilitar el seguimiento, mantrenimiento y comprension del sistema.
