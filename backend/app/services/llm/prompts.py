"""Prompts centralizados para todas las features de IA.

Cada prompt tiene nombre, versión y template con slots de contexto dinámico.
El campo `version` permite rastrear qué versión produjo cada análisis guardado en BD
(junto al campo `modelo_usado` de la tabla correspondiente).

Convención de slots: $variable (string.Template). Las llaves del JSON en el template
no requieren escape porque Template solo procesa tokens que empiezan con $.
"""

from dataclasses import dataclass
from string import Template


@dataclass(frozen=True)
class Prompt:
    """Prompt versionado con template de sustitución de variables."""

    nombre: str
    version: int
    template: str

    def render(self, **kwargs: str) -> str:
        """Sustituye los slots del template.

        Lanza KeyError si falta alguna variable requerida.
        """
        return Template(self.template).substitute(**kwargs)


# ── Módulo 1: Auto-análisis de bases técnicas ─────────────────────────────────

ANALISIS_BASES = Prompt(
    nombre="analisis_bases",
    version=1,
    template="""Sos un experto en licitaciones públicas chilenas de Mercado Público
con más de 10 años de experiencia evaluando bases técnicas.

Analizá el contenido de las bases de la siguiente licitación e identificá con precisión:

LICITACIÓN:
- Código: $codigo
- Nombre: $nombre
- Organismo: $organismo

CRITERIOS DE EVALUACIÓN REGISTRADOS EN EL SISTEMA (complementar con lo que aparezca en las bases):
$criterios

CONTENIDO DE LAS BASES TÉCNICAS:
$contenido_bases

Respondé ÚNICAMENTE con un objeto JSON válido. Sin texto previo ni posterior al JSON.

{
  "requisitos_tecnicos": [
    {
      "descripcion": "descripción breve del requisito",
      "tipo": "obligatorio | deseable",
      "detalle": "extracto textual exacto de las bases que define este requisito"
    }
  ],
  "criterios_extraidos": [
    {
      "nombre": "nombre del criterio",
      "peso_pct": 0,
      "descripcion": "cómo se evalúa este criterio según las bases"
    }
  ],
  "documentos_obligatorios": [
    {
      "nombre": "nombre del documento",
      "descripcion": "para qué sirve y cómo debe presentarse",
      "obligatorio": true
    }
  ],
  "plazos_clave": [
    {
      "tipo": "visita_terreno | preguntas | cierre_ofertas | apertura | adjudicacion | otro",
      "fecha_texto": "texto de la fecha tal como aparece en las bases",
      "descripcion": "descripción del hito"
    }
  ],
  "restricciones": [
    "descripción de cada restricción o condición que descalifica automáticamente"
  ],
  "resumen_ejecutivo": "párrafo de 3-5 oraciones con los puntos más críticos
    para decidir si postular"
}""",
)


# ── Módulo 2: Borrador de propuesta técnica ───────────────────────────────────

BORRADOR_PROPUESTA = Prompt(
    nombre="borrador_propuesta",
    version=1,
    template="""Sos un experto redactor de propuestas técnicas para licitaciones públicas chilenas.
Usás lenguaje formal licitatorio chileno. Sabés qué secciones tienen más peso en la evaluación.

ANÁLISIS DE LAS BASES:
$analisis_bases

PERFIL DE LA EMPRESA POSTULANTE:
$perfil_empresa

Generá un borrador de propuesta técnica alineado a los criterios de evaluación de esta licitación.
Dejá marcados con [COMPLETAR: descripción] los campos que el usuario debe llenar manualmente
(precios, firmas, datos únicos que no se pueden inferir del perfil).

Respondé ÚNICAMENTE con un objeto JSON válido:

{
  "titulo": "título sugerido para la propuesta",
  "secciones": [
    {
      "nombre": "nombre de la sección",
      "contenido": "texto de la sección, puede incluir [COMPLETAR: ...] para datos pendientes",
      "es_placeholder": false
    }
  ],
  "documentos_pendientes": [
    "lista de documentos obligatorios que el usuario debe adjuntar manualmente"
  ],
  "notas_revision": [
    "aspectos que el usuario debe revisar antes de presentar la propuesta"
  ]
}""",
)
