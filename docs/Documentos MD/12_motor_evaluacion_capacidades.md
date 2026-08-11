# Prompt 12: motor de evaluación de capacidades por estación

## Auditoría previa

Se confirmó que Git estaba limpio y sincronizado, todas las migraciones relacionadas estaban aplicadas y existían 0 capacidades y 0 estaciones en la base local. No había conflictos de datos.

## Evaluación histórica

Se creó `EvaluacionCapacidadEstacion` para conservar cada resultado como una fotografía histórica. Registra estación, capacidad, estado, porcentaje, detalles JSON de recursos y personal, observaciones, evaluador opcional y fecha automática.

No existe restricción única entre estación y capacidad, por lo que pueden conservarse múltiples evaluaciones en fechas diferentes. Las relaciones con estación, capacidad y evaluador usan `PROTECT`.

Los estados son cumple, cumplimiento parcial y no cumple. El porcentaje admite valores decimales entre 0 y 100.

## Servicio de evaluación

Se creó `operaciones/services.py` con `evaluar_capacidad_estacion`. La operación usa `transaction.atomic`, consulta el estado actual y crea una evaluación sin modificar recursos, personal ni calificaciones.

Una capacidad sin requisitos produce `ValidationError` y no genera una evaluación.

## Evaluación de recursos

Solo se cuentan recursos que pertenecen a la estación, están activos, operativos, disponibles y corresponden al tipo requerido.

El JSON registra requisito, tipo, nombre, cantidad requerida, cantidad disponible, obligatoriedad, cumplimiento y faltante.

## Evaluación del personal

Solo se cuenta personal de la estación que está activo y disponible, con una calificación activa, vigente y de la especialidad requerida.

La jerarquía explícita es:

```text
básico < intermedio < avanzado < instructor
```

La comparación utiliza valores numéricos internos, no orden alfabético. La consulta usa `distinct` para no contar una persona varias veces dentro de un requisito.

## Porcentaje y estado

Cada requisito aporta una cobertura `min(disponible / requerido, 1)`. El porcentaje es el promedio de las coberturas de todos los requisitos, incluidos los opcionales, multiplicado por 100 y limitado entre 0 y 100.

El estado se determina solo con requisitos obligatorios:

- cumple: todos tienen cobertura completa;
- parcial: alguno tiene cobertura mayor que cero, pero no todos están completos;
- no cumple: ninguno tiene cobertura útil.

Los opcionales influyen en el porcentaje y el detalle, pero no bloquean el estado cumple.

## Django Admin

Las evaluaciones pueden listarse, filtrarse, buscarse y consultarse con estación, Cuerpo de Bomberos, capacidad, estado, porcentaje, evaluador y fecha. Los JSON y demás campos son de solo lectura.

No se permite agregar ni editar resultados manualmente. La eliminación conserva el control normal de permisos de Django Admin.

## Pruebas

Se añadieron 13 pruebas para cumplimiento total, parcial y nulo; recursos no contabilizables; personal no disponible; certificados vencidos; jerarquía de niveles; requisitos opcionales; ausencia de requisitos; historial múltiple y conteo sin duplicados.

Junto con las pruebas anteriores se ejecutaron 35 pruebas de `operaciones`.

## Archivos creados o modificados

- `operaciones/models.py`
- `operaciones/services.py`
- `operaciones/admin.py`
- `operaciones/test_evaluacion_capacidades.py`
- `operaciones/migrations/0004_evaluacioncapacidadestacion.py`
- `docs/Documentos MD/README.md`
- `docs/Documentos MD/12_motor_evaluacion_capacidades.md`

## Verificación

```text
Applying operaciones.0004_evaluacioncapacidadestacion... OK
System check identified no issues (0 silenced).
Found 35 test(s).
Ran 35 tests
OK
No changes detected
```

No se desarrollaron interfaces, dashboard, emergencias, mapas ni API.
