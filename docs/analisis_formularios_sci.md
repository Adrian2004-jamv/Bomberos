# Análisis técnico de formularios SCI

## 1. Ubicación analizada y método

Se analizó, de forma recursiva y exclusivamente de lectura, la carpeta:

`Total de Formularios SCI/`

La carpeta no contiene subcarpetas. Se registraron tamaño, fecha y huella SHA-256 de cada original antes del análisis. Los DOC/DOCX se abrieron con Microsoft Word en modo de solo lectura para consultar paginación, secciones, texto, tablas, controles y objetos. Los XLSX se inspeccionaron directamente como OOXML porque Excel rechazó la automatización; no se instalaron dependencias ni se convirtieron originales. No se realizó OCR.

Las páginas de XLSX son estimaciones basadas en hojas, áreas de impresión y ajustes de página. En esos tres archivos el tamaño de papel no está fijado en OOXML y depende de la impresora; debe confirmarse manualmente antes de construir plantillas finales.

## 2. Resumen general

- **21 archivos:** 12 formularios y 9 instructivos.
- **15 DOCX, 3 DOC y 3 XLSX; 0 PDF e imágenes independientes.**
- Todos contienen texto seleccionable; **0 parecen escaneados**.
- No existen PDF originales, por tanto **0 contienen campos PDF interactivos**.
- Los 18 documentos Word tampoco contienen controles de formulario ni controles de contenido.
- Predominan tablas, celdas vacías y líneas destinadas a escritura manual.
- Se identificaron croquis en SCI-201, listas repetibles en varios formularios y firmas/aprobaciones en SCI-201, SCI-214, SCI-215, SCI-221 y SCI-222.
- Los XLSX SCI-203 y SCI-222 tienen referencias de área de impresión `#REF!` que deben resolverse manualmente.

## 3. Inventario completo

“Campos” es una estimación de entradas lógicas, no el número de celdas físicas. “Interactivo” se refiere a campos PDF: todos son **No**, porque no hay PDF.

| Código | Nombre / función | Archivo | Formato | Páginas | Tamaño y orientación | Texto / escaneo | Interactivo | Estructura relevante | Campos aprox. | Dificultad |
|---|---|---|---:|---:|---|---|---|---|---:|---|
| 201 | Resumen del Incidente | `SCI - 201 formulario.docx` | DOCX | 4 | Carta 21,6×27,9 cm, vertical | Sí / No | No | 2 tablas; firma; mapa o croquis; páginas adicionales | 30–40 | Alta |
| 201 | Instructivo del Resumen del Incidente | `SCI - 201 instructivo.docx` | DOCX | 3 | Carta, vertical | Sí / No | No | Tabla explicativa; confirma croquis, firma y extensiones | 0 | Referencia |
| 202 | Plan de Acción del Incidente | `SCI - 202 formulario.docx` | DOCX | 2 | Carta, horizontal | Sí / No | No | 3 tablas; objetivos, estrategias, tácticas y recursos | 25–35 | Alta |
| 202 | Instructivo del PAI | `SCI - 202 instructivo.docx` | DOCX | 3 | Carta, vertical | Sí / No | No | Dependencias SCI-201, 205 y 206; aprobación manual | 0 | Referencia |
| 203 | Listado de Asignación en la Organización | `SCI - 203 formulario.xlsx` | XLSX | 2 hojas estimadas | Papel no fijado; SCI-203 vertical y hoja SCI-222 horizontal | Sí / No | No | Organigrama tabular; 148 combinaciones en hoja principal; contiene además SCI-222 visible | 45–60 | Muy alta / dudoso |
| 204 | Asignaciones Tácticas | `SCI - 204 formulario.docx` | DOCX | 1 | Carta, horizontal | Sí / No | No | Tabla fija; 17 objetos gráficos; una copia por rama/división/grupo/recurso | 30–45 | Alta |
| 204 | Instructivo de Asignaciones Tácticas | `SCI - 204 instructivo.docx` | DOCX | 3 | Carta, vertical | Sí / No | No | Casillas descritas; dependencia de SCI-202 | 0 | Referencia |
| 205 | Plan de Comunicaciones | `SCI - 205 formulario.docx` | DOCX | 1 | Carta, vertical | Sí / No | No | Tabla repetible de sistema, canal y asignación | 25–40 | Media |
| 205 | Instructivo del Plan de Comunicaciones | `SCI - 205 instructivo.docx` | DOCX | 1 | Carta, vertical | Sí / No | No | Vinculado al periodo operacional y SCI-202 | 0 | Referencia |
| 206 | Plan Médico | `SCI - 206 formulario.docx` | DOCX | 1 | Carta, vertical | Sí / No | No | Tabla de instalaciones, recursos y derivación | 35–50 | Media-alta |
| 206 | Instructivo del Plan Médico | `SCI - 206  instructivo.docx` | DOCX | 3 | Carta, vertical | Sí / No | No | Relación con SCI-202 y SCI-207; firma/aprobación descrita | 0 | Referencia |
| 207 | Registro de pacientes/víctimas | `SCI - 207 formulario.doc` | DOC | 1 | Carta, horizontal | Sí / No | No | Tabla de 161 celdas; casillas ACV/Unidad Médica y clasificación; filas repetibles | 10 por paciente | Media-alta |
| 207 | Instructivo del registro de pacientes | `SCI - 207 instructivo.docx` | DOCX | 1 | Carta, vertical | Sí / No | No | Confirma casilleros y datos personales sensibles | 0 | Referencia |
| 211 | Registro y Control de Recursos | `SCI - 211 formulario.xlsx` | XLSX | ≈2 | Papel no fijado, horizontal; área A1:Q44; ajuste a 2 páginas de ancho | Sí / No | No | Cuadrícula repetible; solicitud, arribo, estado y desmovilización | 12 por recurso | Media |
| 211 | Instructivo de Registro y Control de Recursos | `SCI - 211 instructivo.docx` | DOCX | 2 | Carta, vertical | Sí / No | No | Fuente maestra de recursos; múltiples puntos de registro | 0 | Referencia |
| 214 | Registro de Actividades | `SCI - 214 formulario.docx` | DOCX | 1 base | Carta, vertical | Sí / No | No | Tabla cronológica, firma y páginas adicionales numeradas | 10 + filas | Media |
| 214 | Instructivo del Registro de Actividades | `SCI - 214 instructivo.doc` | DOC | 1 | Carta, vertical | Sí / No | No | Confirma repetición por cargo y periodo | 0 | Referencia |
| 215 | Análisis de Seguridad del PAI | `SCI - 215 formulario.docx` | DOCX | 1 | Carta, horizontal | Sí / No | No | Tabla área/riesgo/mitigación; 2 objetos; preparado por | 6 + filas | Media |
| 221 | Verificación de la Desmovilización | `SCI - 221 formulario.doc` | DOC | 4 | Carta, vertical | Sí / No | No | Lista de verificación por secciones; firmas; varias páginas | 25–35 | Alta |
| 221 | Instructivo de Desmovilización | `SCI - 221 Instructivo.docx` | DOCX | 5 | Carta, vertical | Sí / No | No | Describe validaciones y firmas por responsables | 0 | Referencia |
| 222 | Prioridades y Asignación de Recursos | `SCI - 222 formulario.xlsx` | XLSX | ≈1 | Papel no fijado, horizontal | Sí / No | No | Matriz ancha por incidentes y recursos; preparado por; área de impresión `#REF!` | 10 + matriz | Muy alta / dudoso |

## 4. Clasificación técnica recomendada

| Código | Tecnología recomendada | Motivo | Prioridad |
|---|---|---|---|
| 201 | **D. Revisión especial** | El croquis situacional, posibles dibujos manuales, firma y anexos repetibles requieren decidir si se usará lienzo digital, imagen adjunta o página manual. Después puede combinar HTML con una página especial. | Alta, después del piloto |
| 202 | **A. WeasyPrint** | Objetivos, estrategias, tácticas y recursos pueden crecer; HTML/CSS ofrece mejor paginación y mantenibilidad que coordenadas fijas. | Media |
| 203 | **D. Revisión especial** | El libro mezcla SCI-203 y SCI-222 como hojas visibles y contiene una referencia de impresión dañada. Debe definirse cuál versión es oficial antes de diseñar. | Baja hasta resolver |
| 204 | **B. PyMuPDF sobre plantilla oficial** | Formato horizontal fijo con elementos gráficos y espacios precisos. Para conservar fidelidad deberá aprobarse primero un PDF maestro derivado del original, sin alterar este DOCX. | Media |
| 205 | **A. WeasyPrint** | Tabla sencilla y repetible; los canales y asignaciones pueden crecer. | Media |
| 206 | **A. WeasyPrint** | Tablas de instalaciones y derivaciones variables; conviene permitir filas y páginas adicionales. | Media |
| 207 | **A. WeasyPrint** | Registro tabular de pacientes con filas repetibles; requiere controles adicionales de privacidad. | Baja por sensibilidad |
| 211 | **A. WeasyPrint** | Recursos repetibles, datos ya presentes en inventario/despliegues y necesidad de impresión clara. | **Piloto** |
| 214 | **A. WeasyPrint** | Bitácora cronológica naturalmente repetible y multipágina. | Alta después del piloto |
| 215 | **A. WeasyPrint** | Matriz área–riesgo–acción mitigante extensible; estructura HTML directa. | Media |
| 221 | **A. WeasyPrint** | Lista de verificación multipágina que puede representarse con casillas y firmas registradas de forma explícita. | Baja / fase de cierre |
| 222 | **D. Revisión especial** | Matriz compleja, área de impresión rota y duplicación dentro del SCI-203. Tras elegir la fuente oficial podría convenir **B. PyMuPDF** para máxima fidelidad. | Baja hasta resolver |

Resultado actual: **8 formularios para WeasyPrint, 1 para PyMuPDF sobre plantilla, 0 para PyMuPDF con campos PDF y 3 para revisión especial**. No se recomienda la opción C porque no existe ningún PDF interactivo.

## 5. Relación con módulos existentes

| Código | Autocompletado posible desde el sistema actual | Información necesariamente manual o todavía no modelada |
|---|---|---|
| 201 | Emergencia, código/tipo, fecha, dirección, ubicación, estación responsable, unidades desplegadas, recursos e historial GPS | Evaluación, amenazas, áreas afectadas, objetivos, estrategias, organización inicial, narración, croquis, aprobaciones y firma |
| 202 | Emergencia, periodo derivable de fechas, institución, estación, unidades y cantidades de recursos desplegados | Objetivos, estrategias, tácticas, pronóstico, organización SCI, seguridad, aprobación del comandante |
| 203 | Usuarios responsables, institución y estación; unidades/recurso asignados parcialmente | Estructura completa de mando SCI, cargos ad hoc, representantes externos y nombres no usuarios |
| 204 | Emergencia, periodo, unidad, estación de procedencia, estado y horas del despliegue | Rama/división/grupo, instrucciones tácticas, responsable operativo, comunicaciones y aprobación |
| 205 | Emergencia, institución, estación, fechas/periodo | Frecuencias, canales, equipos, indicativos y asignaciones de comunicaciones |
| 206 | Emergencia, ubicación, institución/estación y recursos disponibles | Instalaciones médicas externas, contactos, rutas, capacidades clínicas y aprobación de seguridad |
| 207 | Emergencia, fecha/hora y lugar general | Identidad y condición clínica del paciente, clasificación, destino y medio de traslado; son datos especialmente sensibles |
| 211 | Emergencia, fecha, lugar, recursos, unidad, tipo, código, estación/institución, disponibilidad, despliegue, horas y responsable usuario | Solicitante externo, dotación de personas, matrícula si no está registrada, registradores y observaciones operativas |
| 214 | Emergencia, periodo, usuario responsable, institución, estación y marcas de tiempo | Personal asignado no usuario, relato cronológico, decisiones, novedades, aprobación y firma |
| 215 | Emergencia, fecha/hora y usuario que prepara | Áreas de trabajo, peligros, nivel de riesgo y acciones mitigantes |
| 221 | Emergencia, recursos/unidades, estados y horas de retorno, estación e institución | Verificaciones de planificación, logística, finanzas, comunicaciones, observaciones y firmas de liberación |
| 222 | Varias emergencias, prioridades, recursos requeridos/disponibles y estaciones, con agregación adicional | Criterio de prioridad del Comando de Área, reasignaciones, decisiones y aprobación |

El sistema no administra nóminas ni todo el organigrama SCI. Por ello, “personal asignado”, pacientes, representantes externos, cargos incidentales y firmas no deben inferirse a partir de `Usuario`.

## 6. Dependencias entre formularios

- **SCI-201** es la fuente inicial común del incidente y alimenta datos generales de los demás formularios.
- **SCI-202 (PAI)** integra o acompaña a SCI-205 y SCI-206; las asignaciones SCI-204 se relacionan con sus objetivos y tácticas.
- **SCI-203** describe la organización que luego aparece en SCI-202 y determina responsables de SCI-204/214.
- **SCI-206** se complementa con SCI-207 cuando existen pacientes atendidos o trasladados.
- **SCI-211** es el registro maestro de recursos y puede alimentar SCI-201, 202, 203, 204 y la desmovilización SCI-221.
- **SCI-214** conserva actividades que posteriormente sirven para el informe final y verificaciones de cierre.
- **SCI-215** aporta las consideraciones de seguridad del PAI SCI-202.
- **SCI-221** depende del estado final de recursos y despliegues registrados en SCI-211/214.
- **SCI-222** opera a nivel de múltiples incidentes y requiere agregación de recursos por encima de un incidente individual.

## 7. Duplicados, versiones dudosas y calidad de fuente

- No existen duplicados binarios: las 21 huellas SHA-256 son diferentes.
- Cada par “formulario/instructivo” es complementario, no duplicado.
- `SCI - 203 formulario.xlsx` contiene dos hojas visibles: `SCI 203` y una `Hoja de trabajo` con contenido SCI-222.
- Esa hoja coincide funcionalmente con `SCI - 222 formulario.xlsx`, aunque los archivos no son idénticos.
- Las áreas de impresión de la hoja SCI-222 incluida en SCI-203 y del archivo SCI-222 contienen `#REF!`; no debe asumirse una plantilla oficial hasta revisarlas en Excel.
- SCI-207, SCI-214 y SCI-221 usan formato DOC legado; conviene conservarlos como referencia inmutable y definir más adelante una copia maestra controlada.
- SCI-215 se identifica internamente como `SCI-215a`; debe confirmarse si esa variante es la oficial requerida.

## 8. Formulario piloto recomendado

### SCI-211 — Registro y Control de Recursos

Se recomienda como primer piloto porque:

1. Es útil desde el inicio y durante la evolución de una emergencia.
2. Se relaciona directamente con los modelos ya existentes de emergencia, recurso, tipo, estación, institución, despliegue, estados y usuarios responsables.
3. Su estructura es tabular, clara y repetible; permite probar altas, edición, validación, guardado e impresión.
4. Puede autocompletar una parte importante sin implementar organigrama completo, pacientes, firmas digitales ni todo el PAI.
5. Expone un problema real de paginación (filas variables) que sirve para validar la arquitectura documental.

## 9. Tecnología recomendada para el piloto

**Formulario Django + PDF mediante WeasyPrint**, en una futura etapa.

La interfaz debería manejar un encabezado del incidente y una colección repetible de recursos. WeasyPrint es preferible a coordenadas fijas porque la cantidad de recursos cambia, la tabla puede ocupar varias páginas y debe conservar encabezados legibles. Antes de implementarlo se deberá confirmar visualmente el tamaño de papel y la paginación del XLSX, pues el archivo no fija el papel y solicita hasta dos páginas de ancho.

## 10. Riesgos y observaciones

- No existe un PDF oficial listo para superposición ni campos interactivos; usar PyMuPDF exigirá aprobar previamente una plantilla PDF maestra.
- “Firma” puede significar firma manuscrita, nombre del responsable o aprobación institucional; su validez debe definirse antes de digitalizar.
- SCI-207 contiene datos de salud y exige permisos, retención y auditoría más estrictos.
- El sistema actual no representa periodos operacionales, organigrama SCI, canales, pacientes ni aprobaciones formales.
- Los formularios con croquis no deben reducirse a un campo de texto.
- La paginación de XLSX es estimada y debe validarse manualmente en Excel.
- Los documentos son de 2022 según metadatos del sistema de archivos; se debe confirmar vigencia normativa y versión institucional sin reemplazarlos por fuentes externas.
- No se recomienda digitalizar todos los campos literalmente antes de acordar qué datos son obligatorios y quién puede editarlos.

## 11. Orden sugerido de implementación

1. **SCI-211** — piloto de recursos e integración con inventario/despliegues.
2. **SCI-214** — bitácora cronológica y páginas repetibles.
3. **SCI-215** — análisis de seguridad sencillo y extensible.
4. **SCI-205** — comunicaciones, después de definir catálogo o ingreso manual.
5. **SCI-206** — plan médico institucional, sin pacientes.
6. **SCI-202** — PAI, cuando existan periodos operacionales y objetivos/tácticas.
7. **SCI-204** — asignaciones tácticas sobre plantilla aprobada.
8. **SCI-201** — resumen completo y solución para croquis.
9. **SCI-221** — cierre y desmovilización.
10. **SCI-207** — solo después de definir protección de datos de salud.
11. **SCI-203 y SCI-222** — después de resolver duplicación, versión oficial y áreas de impresión.

## 12. Conteo final de clasificación

| Indicador | Resultado |
|---|---:|
| Archivos encontrados y analizados | 21 |
| Formularios distintos por código | 12 |
| Archivos PDF | 0 |
| PDF con campos interactivos | 0 |
| Documentos que parecen escaneados | 0 |
| Formularios recomendados para WeasyPrint | 8 |
| Formularios recomendados directamente para PyMuPDF sobre plantilla | 1 |
| Formularios recomendados para PyMuPDF con campos existentes | 0 |
| Formularios en revisión especial | 3 |
| Piloto | SCI-211 Registro y Control de Recursos |
