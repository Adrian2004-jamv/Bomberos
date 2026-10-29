from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .esquemas_sci import (FECHA_HORA, FORMULARIOS_SCI_CONTINUOS, TABLA,
                          campos_periodo, obtener_esquema)
from .models import FormularioSCI, FormularioSCI211, RegistroRecursoSCI211

def nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username

@transaction.atomic
def crear_sci211_desde_emergencia(emergencia, usuario):
    # El punto de registro del SCI-211 es, casi siempre, el Puesto de Comando, y
    # dónde está el PC ya lo declaró el campo 8 del SCI-201. Volver a pedirlo era
    # pedir por segunda vez un dato que consta, con el riesgo de que las dos
    # copias no coincidan. Si el 201 aún no lo dice, queda el valor de siempre.
    del_201 = estado_del_incidente(emergencia)
    punto = (del_201.get("ubicacion_pc") or "").strip() or "Puesto de Comando"
    formulario = FormularioSCI211.objects.create(
        emergencia=emergencia,
        codigo=f"SCI-211-{emergencia.codigo}",
        punto_registro=punto,
        registrador_1=nombre_usuario(usuario),
        creado_por=usuario,
        modificado_por=usuario,
    )
    despliegues = emergencia.despliegues.select_related(
        "unidad__tipo__categoria", "estacion_procedencia__cuerpo_bomberos", "despachado_por"
    )
    for orden, despliegue in enumerate(despliegues, start=1):
        unidad = despliegue.unidad
        estado = RegistroRecursoSCI211.EstadoRecurso.DISPONIBLE
        if unidad.estado_operativo == "fuera_servicio":
            estado = RegistroRecursoSCI211.EstadoRecurso.FUERA_SERVICIO
        elif unidad.disponibilidad == "no_disponible":
            estado = RegistroRecursoSCI211.EstadoRecurso.NO_DISPONIBLE
        RegistroRecursoSCI211.objects.create(
            formulario=formulario, despliegue=despliegue, orden=orden,
            solicitado_por=nombre_usuario(despliegue.despachado_por),
            fecha_hora_solicitud=despliegue.fecha_asignacion,
            clase_recurso=unidad.tipo.categoria.nombre,
            tipo_recurso=unidad.tipo.nombre,
            fecha_hora_arribo=despliegue.fecha_llegada,
            institucion_procedencia=despliegue.estacion_procedencia.cuerpo_bomberos.nombre,
            matricula_identificacion=unidad.codigo_interno,
            numero_personas=1,
            estado_recurso=estado,
            asignado_a=emergencia.direccion if estado == "disponible" else "",
            desmovilizado_por=nombre_usuario(despliegue.despachado_por) if despliegue.fecha_retorno else "",
            fecha_hora_desmovilizacion=despliegue.fecha_retorno,
            observaciones=despliegue.observaciones,
        )
    return formulario

@transaction.atomic
def finalizar_sci211(formulario, usuario):
    actual = FormularioSCI211.objects.select_for_update().select_related(
        "emergencia__estacion_responsable__cuerpo_bomberos"
    ).get(pk=formulario.pk)
    if not actual.es_editable:
        raise ValidationError("El formulario SCI-211 ya está finalizado.")
    registros = list(actual.registros.all())
    if not registros:
        raise ValidationError("Debe registrar al menos un recurso antes de finalizar.")
    # El SCI-211 es la bitácora de control de recursos del incidente, no un
    # documento que se redacta una vez: mientras la emergencia siga abierta
    # pueden llegar más unidades y hay que poder anotarlas. Cerrarlo antes
    # dejaría fuera del acta todo lo que llegara después.
    if actual.emergencia.admite_despliegues:
        raise ValidationError(
            "El SCI-211 se cierra cuando la emergencia termina: hasta entonces "
            "siguen llegando recursos que deben quedar registrados."
        )
    actual.full_clean()
    for registro in registros:
        registro.full_clean()
    emergencia = actual.emergencia
    estacion = emergencia.estacion_responsable
    actual.emergencia_codigo_emitido = emergencia.codigo
    actual.incidente_nombre_emitido = emergencia.tipo_emergencia
    actual.incidente_fecha_emitida = emergencia.fecha_reporte
    actual.incidente_direccion_emitida = emergencia.direccion
    actual.institucion_emitida = estacion.cuerpo_bomberos.nombre
    actual.estacion_emitida = estacion.nombre
    if emergencia.latitud is not None and emergencia.longitud is not None:
        actual.coordenadas_emitidas = f"{emergencia.latitud}, {emergencia.longitud}"
    actual.estado = FormularioSCI211.Estado.FINALIZADO
    actual.finalizado_por = usuario
    actual.modificado_por = usuario
    actual.fecha_finalizacion = timezone.now()
    actual.save()
    return actual

@transaction.atomic
def finalizar_sci(formulario, usuario):
    """Bloquea un formulario SCI genérico tras verificar que tenga contenido."""
    actual = FormularioSCI.objects.select_for_update().get(pk=formulario.pk)
    if not actual.es_editable:
        raise ValidationError(f"El formulario SCI-{actual.codigo_sci} ya está finalizado.")
    if not tiene_contenido(actual.datos):
        raise ValidationError("Complete al menos un campo antes de finalizar el formulario.")
    # Las bitácoras se escriben durante toda la intervención; cerrarlas antes
    # dejaría fuera del acta lo que ocurriera después.
    #
    # Esta comprobación va antes que la de los campos obligatorios a propósito:
    # a quien todavía no puede cerrar el formulario no se le pide que lo
    # complete. Sería un consejo inútil —aunque lo siguiera, seguiría sin poder
    # cerrarlo— y escondería el motivo verdadero.
    if (actual.codigo_sci in FORMULARIOS_SCI_CONTINUOS
            and actual.emergencia.admite_despliegues):
        raise ValidationError(
            f"El SCI-{actual.codigo_sci} se cierra cuando la emergencia "
            "termina: hasta entonces siguen ocurriendo cosas que registrar."
        )
    faltan = campos_obligatorios_vacios(actual)
    if faltan:
        raise ValidationError(
            "El formulario oficial no admite estos campos en blanco: "
            + ", ".join(faltan)
            + ". Complételos antes de finalizarlo."
        )
    actual.estado = FormularioSCI.Estado.FINALIZADO
    actual.finalizado_por = usuario
    actual.modificado_por = usuario
    actual.fecha_finalizacion = timezone.now()
    actual.save()
    return actual

def tiene_contenido(datos):
    for nombre, valor in (datos or {}).items():
        if str(nombre).startswith("_"):
            continue
        if isinstance(valor, list):
            if any(any(celda for celda in fila.values()) for fila in valor if isinstance(fila, dict)):
                return True
        elif str(valor or "").strip():
            return True
    return False

@transaction.atomic
def registrar_solicitud_en_sci211(emergencia, recursos, usuario):
    """Anota en el SCI-211 los recursos que el plan de acción pidió.

    Solicitar una unidad en el SCI-202 es pedirla; el SCI-211 es donde consta
    que se pidió, cuándo y a quién. Sin este paso había que copiar a mano en un
    formulario lo que ya se había escrito en el otro, y en una emergencia eso
    se olvida.

    No duplica: un recurso ya anotado se deja como está. Devuelve cuántas filas
    nuevas se crearon.
    """
    if not recursos:
        return 0

    formulario = emergencia.formulario_sci_211
    if formulario is None:
        formulario = crear_sci211_desde_emergencia(emergencia, usuario)
    if not formulario.es_editable:
        return 0

    ya_anotados = set(
        formulario.registros.filter(recurso_inventario__isnull=False)
        .values_list("recurso_inventario_id", flat=True)
    )
    orden = formulario.registros.count()
    creadas = 0
    for recurso in recursos:
        if recurso.pk in ya_anotados:
            continue
        orden += 1
        RegistroRecursoSCI211.objects.create(
            formulario=formulario, orden=orden,
            solicitado_por=nombre_usuario(usuario),
            fecha_hora_solicitud=timezone.now(),
            recurso_inventario=recurso,
            clase_recurso=recurso.tipo.categoria.nombre,
            tipo_recurso=recurso.tipo.nombre,
            institucion_procedencia=recurso.estacion.cuerpo_bomberos.nombre,
            matricula_identificacion=recurso.codigo_interno,
            numero_personas=1,
            asignado_a=f"Solicitado en el {formulario.codigo.replace('211', '202')}",
        )
        ya_anotados.add(recurso.pk)
        creadas += 1

    if creadas:
        formulario.modificado_por = usuario
        formulario.save(update_fields=["modificado_por"])
    return creadas

def desplegar_recursos_del_sci211(formulario, usuario):
    """Despacha las unidades que el SCI-211 registra y aún no están desplegadas.

    El SCI-211 es la fuente maestra de recursos del incidente, de modo que
    anotar una unidad allí es la decisión de enviarla: obligar además a
    despacharla por otra pantalla duplicaba el trabajo y dejaba las dos vistas
    contradiciéndose.

    Solo se despachan las unidades desplegables. El formulario también registra
    equipos —un ERA, por ejemplo—, que no salen como unidad y no generan
    despliegue.

    Devuelve ``(despachadas, avisos)``. Un recurso que no se pueda despachar no
    detiene al resto ni impide guardar el formulario: se informa y el usuario
    decide.
    """
    from .models import DespliegueUnidad
    from .services import desplegar_unidad

    despachadas = 0
    avisos = []
    registros = formulario.registros.select_related(
        "recurso_inventario__tipo", "despliegue"
    ).filter(recurso_inventario__isnull=False, despliegue__isnull=True)

    for registro in registros:
        recurso = registro.recurso_inventario
        if not recurso.tipo.es_unidad_desplegable:
            continue
        # Si la unidad ya está atendiendo esta misma emergencia, se enlaza en
        # lugar de intentar un despacho que la restricción rechazaría.
        existente = DespliegueUnidad.objects.filter(
            emergencia=formulario.emergencia, unidad=recurso,
            estado__in=DespliegueUnidad.ESTADOS_ACTIVOS,
        ).first()
        if existente is not None:
            registro.despliegue = existente
            registro.save(update_fields=["despliegue"])
            sincronizar_responsable(registro, existente)
            continue
        try:
            despliegue = desplegar_unidad(
                formulario.emergencia, recurso, usuario,
                observaciones=f"Despacho registrado en el {formulario.codigo}.",
            )
        except ValidationError as error:
            avisos.append(
                f"No se pudo despachar {recurso.codigo_interno}: "
                f"{' '.join(error.messages)}"
            )
            continue
        registro.despliegue = despliegue
        registro.save(update_fields=["despliegue"])
        sincronizar_responsable(registro, despliegue)
        despachadas += 1

    # Un recurso escrito a mano queda en el papel y no sale nunca. Antes eso
    # ocurría en silencio y la emergencia aparecía sin unidades sin explicar
    # por qué; conviene decirlo en el momento de guardar.
    a_mano = formulario.registros.filter(
        recurso_inventario__isnull=True, despliegue__isnull=True
    ).count()
    if a_mano:
        avisos.append(
            f"{a_mano} recurso(s) se anotaron a mano y no generan despliegue. "
            "Elíjalos de la lista del inventario para que la unidad salga."
        )

    return despachadas, avisos


def sincronizar_responsable(registro, despliegue):
    """Lleva al despliegue el chofer que el SCI-211 asignó a la unidad.

    El formulario es donde se decide quién va en la unidad; el despliegue
    necesita saberlo porque de ahí cuelga el permiso para transmitir la
    ubicación. Se copia en cada guardado para que un cambio de conductor a
    mitad de la operación llegue también al despliegue.
    """
    if registro.responsable_unidad_id == despliegue.responsable_unidad_id:
        return
    despliegue.responsable_unidad_id = registro.responsable_unidad_id
    despliegue.save(update_fields=["responsable_unidad"])


# ==========================================
# VALIDACIÓN ESTRICTA DE LOS FORMULARIOS
# ==========================================

def campos_obligatorios_vacios(formulario):
    """Los campos que el formulario oficial no admite en blanco y lo están.

    Se comprueba al finalizar y no al guardar. Guardar a medias es lo normal en
    plena intervención —se anota lo que se sabe y se vuelve al rato—; lo que no
    puede ocurrir es que un documento incompleto quede sellado como definitivo y
    pase así a la Unidad de Documentación.

    Qué es obligatorio lo declara el propio esquema con ``obligatorio``, de modo
    que la lista vive junto a la estructura del formulario y no repartida por el
    código. Las firmas van aparte porque no son secciones: un documento SCI sin
    la firma de quien lo preparó no es un documento, y los que el manual manda
    aprobar —el SCI-202 por el CI, el SCI-204 por el JSO— tampoco valen sin ella.
    """
    esquema = obtener_esquema(formulario.codigo_sci)
    if esquema is None:
        return []
    datos = formulario.datos or {}
    faltan = []
    for seccion in esquema["secciones"]:
        if not seccion.get("obligatorio"):
            continue
        valor = datos.get(seccion["nombre"])
        if seccion["tipo"] == TABLA:
            lleno = any(
                any(str(celda or "").strip() for celda in fila.values())
                for fila in (valor or []) if isinstance(fila, dict)
            )
        else:
            lleno = bool(str(valor or "").strip())
        if not lleno:
            faltan.append(f"{seccion.get('numero', '')}. {seccion['etiqueta']}".strip())

    if not formulario.preparado_por.strip():
        faltan.append(f"Preparado por ({esquema['preparado_por']})")
    if esquema.get("aprobado_por") and not formulario.aprobado_por.strip():
        faltan.append(f"Aprobado por ({esquema['aprobado_por']})")
    return faltan


def fecha_de_referencia(emergencia):
    """El instante antes del cual ningún formulario del incidente puede fechar.

    Es la creación del SCI-201, que es el documento que abre el expediente: nada
    de lo que se registre puede ser anterior a que el incidente se documentara.

    Mientras no exista ese SCI-201 la referencia es la fecha de reporte de la
    emergencia. Sin ese respaldo la regla no se aplicaría hasta que alguien
    creara el 201, que es justo cuando menos falta hace —al principio es cuando
    se teclean las horas a mano y con prisa—.
    """
    primero = (
        FormularioSCI.objects
        .filter(emergencia=emergencia, codigo_sci="201")
        .order_by("periodo__numero", "pk")
        .first()
    )
    crudo = primero.fecha_creacion if primero is not None else emergencia.fecha_reporte
    # Al minuto, y no es un detalle: los controles «datetime-local» solo guardan
    # horas y minutos, de modo que escribir la hora exacta de apertura da las
    # 20:14:00 mientras el expediente se abrio a las 20:14:16. Sin truncar, el
    # sistema rechazaba una fecha que su propio «min» ofrecia como valida y el
    # mensaje de error era incomprensible: senalaba dos horas identicas.
    return crudo.replace(second=0, microsecond=0)


def _momento(valor):
    """Interpreta lo que entrega un control «datetime-local», o ``None``."""
    crudo = str(valor or "").strip()
    if not crudo:
        return None
    try:
        fecha = timezone.datetime.fromisoformat(crudo)
    except ValueError:
        # Un valor escrito antes de que la columna tuviera tipo. No se juzga:
        # quien lo escribió ya no está para corregirlo y perderlo sería peor.
        return None
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.get_default_timezone())
    return fecha


def fechas_anteriores_al_inicio(esquema, datos, referencia):
    """Las fechas del formulario que caen antes de que el expediente se abriera.

    Recorre las tres del periodo operacional y las columnas de fecha de cada
    tabla. Devuelve etiquetas, no valores, porque es lo que hay que decirle a
    quien está delante de la pantalla para que sepa cuál corregir.
    """
    malas = []
    datos = datos or {}
    for campo in campos_periodo(esquema):
        momento = _momento(datos.get(campo["nombre"]))
        if momento is not None and momento < referencia:
            malas.append(f"{campo['numero']}. {campo['etiqueta']}")
    for seccion in esquema["secciones"]:
        if seccion["tipo"] == TABLA:
            columnas = [c for c in seccion["columnas"] if c.get("tipo") == FECHA_HORA]
            for numero, fila in enumerate(datos.get(seccion["nombre"]) or [], start=1):
                if not isinstance(fila, dict):
                    continue
                for columna in columnas:
                    momento = _momento(fila.get(columna["nombre"]))
                    if momento is not None and momento < referencia:
                        malas.append(
                            f"{seccion['etiqueta']}, fila {numero}: {columna['etiqueta']}"
                        )
        elif seccion.get("tipo") == FECHA_HORA:
            momento = _momento(datos.get(seccion["nombre"]))
            if momento is not None and momento < referencia:
                malas.append(f"{seccion.get('numero', '')}. {seccion['etiqueta']}".strip())
    return malas


def exigir_fechas_coherentes(emergencia, esquema, datos):
    """Rechaza el guardado si alguna fecha es anterior a la apertura del expediente.

    La comprobación es del servidor aunque el editor ya ponga el «min» en cada
    control: el navegador puede no respetarlo, la cola sin conexión reenvía
    cuerpos guardados hace horas, y la API atiende a cualquier cliente. El
    control del navegador evita el error; esta comprobación lo impide.
    """
    referencia = fecha_de_referencia(emergencia)
    malas = fechas_anteriores_al_inicio(esquema, datos, referencia)
    if malas:
        raise ValidationError(
            "Estas fechas son anteriores a la apertura del expediente del "
            f"incidente ({timezone.localtime(referencia):%d/%m/%Y %H:%M}): "
            + "; ".join(malas)
            + ". Corríjalas antes de guardar."
        )


# ==========================================
# FUENTE ÚNICA DE VERDAD DEL INCIDENTE
# ==========================================

# Lo que un formulario declara y los demás repiten. La clave es el nombre del
# campo tal como lo nombra el esquema; el valor, de dónde sale.
#
# Hasta ahora cada documento pedía otra vez el nombre del Comandante, la
# ubicación y las fechas del periodo. Un bombero que llena cuatro formularios
# escribía el mismo nombre cuatro veces, y bastaba una errata para que el
# expediente dijera dos cosas distintas sobre la misma persona. Eso no es solo
# tiempo perdido: el SCI-221 verifica la desmovilización comparando documentos.
CAMPOS_COMPARTIDOS = ("lugar_incidente", "ubicacion_um")


def estado_del_incidente(emergencia):
    """Lo que ya consta del incidente y no hace falta volver a declarar.

    Se arma de lo más fiable a lo menos: primero lo que el sistema sabe por sí
    mismo —la dirección registrada, las unidades efectivamente desplegadas—, y
    después lo que alguien escribió en el
    SCI-201, que es el documento que fija el nombre del incidente y su mando.

    Nada de esto se impone: viaja al editor como valor inicial de un campo vacío
    y quien llena el formulario puede cambiarlo. Si hay otro
    Comandante, se escribe el otro.
    """
    del_201 = (
        FormularioSCI.objects
        .filter(emergencia=emergencia, codigo_sci="201")
        .order_by("-periodo__numero", "-pk")
        .first()
    )
    datos_201 = (del_201.datos if del_201 else {}) or {}

    unidades = emergencia.despliegues.count()
    estado = {
        "nombre_incidente": emergencia.tipo_emergencia,
        "lugar_incidente": datos_201.get("lugar_incidente") or emergencia.direccion,
        # El SCI-201 campo 13 es el Comandante del Incidente, y es ahí donde se
        # firma: por eso sale de «preparado_por» y no de una sección.
        "comandante_incidente": del_201.preparado_por if del_201 else "",
        "ubicacion_pc": datos_201.get("ubicacion_pc", ""),
        "ubicacion_e": datos_201.get("ubicacion_e", ""),
        "cantidad_unidades": unidades,
        "mensaje_seguridad": datos_201.get("mensaje_seguridad", ""),
    }
    return estado


def prepoblar(esquema, datos, estado):
    """Qué se le ofrece hecho a cada campo vacío de este formulario.

    Devuelve solo lo que el formulario pide y está en blanco. Un campo con valor
    propio no se toca nunca: lo que alguien escribió manda sobre lo que el
    sistema deduce.
    """
    datos = datos or {}
    ofrecido = {}
    nombres = {seccion["nombre"] for seccion in esquema["secciones"]}
    for nombre in nombres & set(CAMPOS_COMPARTIDOS):
        if not str(datos.get(nombre) or "").strip() and estado.get(nombre):
            ofrecido[nombre] = estado[nombre]
    return ofrecido
