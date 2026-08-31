"""Almacenamiento de archivos estáticos para el despliegue."""

from whitenoise.storage import CompressedManifestStaticFilesStorage

def sin_mapas_de_origen(patrones):
    """Quita las reglas que reescriben los comentarios `sourceMappingURL`.

    Devuelve la misma estructura de `patterns` sin esas reglas y sin las
    extensiones que se quedan sin ninguna.
    """
    resultado = []
    for extension, reglas in patrones:
        conservadas = tuple(
            regla
            for regla in reglas
            if "sourceMappingURL" not in (regla[0] if isinstance(regla, (tuple, list)) else regla)
        )
        if conservadas:
            resultado.append((extension, conservadas))
    return tuple(resultado)

class EstaticosConManifiesto(CompressedManifestStaticFilesStorage):
    """Almacenamiento con manifiesto que ignora los mapas de origen.

    Las bibliotecas de terceros incluidas en `static/vendor` vienen minificadas
    y conservan el comentario `sourceMappingURL`, pero sin el archivo `.map`
    correspondiente: son artefactos de depuración que no se distribuyen. El
    procesamiento estándar interpreta esa referencia como un archivo faltante y
    aborta `collectstatic`.

    Se omiten únicamente esas reglas. Las referencias `url()` y `@import` de las
    hojas de estilo se siguen verificando y reescribiendo, que es lo que da el
    versionado automático.
    """

    patterns = sin_mapas_de_origen(CompressedManifestStaticFilesStorage.patterns)
