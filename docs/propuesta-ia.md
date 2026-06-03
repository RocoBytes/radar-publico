# Propuesta de Valor: Módulos de Inteligencia Artificial

> Documento estratégico para los 3 módulos de IA que diferencian a Radar Público de la competencia.  
> Audiencia: fundadores, potenciales inversores, equipo de producto.  
> Última actualización: 2026-05-17

---

## Por qué la IA cambia el negocio

Las empresas que venden al Estado chileno pierden tiempo y dinero en tres momentos concretos:

1. **Leen bases de 40 páginas** para descubrir que no cumplen un requisito técnico mínimo.
2. **Escriben propuestas desde cero** para cada licitación, aunque el 70% del contenido se repite.
3. **Postulan a ciegas** sin saber qué precios ganaron en el pasado ni quiénes son sus competidores reales.

Los módulos de IA de Radar Público atacan exactamente esos tres puntos. No son features de catálogo — son ahorros de tiempo medibles que justifican la suscripción en la primera semana de uso.

---

## Módulo 1 — Auto-análisis de Bases Técnicas

### Qué hace
Cuando el sistema descarga las bases de una licitación en PDF, las procesa automáticamente con IA y extrae:

- **Requisitos técnicos obligatorios** — experiencia mínima, certificaciones, garantías.
- **Criterios de evaluación con pesos** — precio (X%), técnica (Y%), experiencia (Z%).
- **Documentos obligatorios** — lista exacta de lo que hay que presentar.
- **Plazos críticos** — visita a terreno, preguntas, cierre de ofertas, adjudicación esperada.
- **Restricciones y exclusiones** — condiciones que descalifican automáticamente.

Todo se presenta como un checklist accionable con semáforos: ✅ cumplís / ⚠️ revisar / ❌ no cumplís (cuando el perfil de la empresa está configurado).

### Qué le gusta al cliente
- **"Antes tardaba 3 horas en leer las bases, ahora en 2 minutos sé si vale la pena postular."**
- No más sorpresas en el último momento al descubrir un requisito que no se cumple.
- El checklist de documentos elimina errores de omisión que descalifican ofertas completas.

### Valor agregado al negocio
| Métrica | Sin el módulo | Con el módulo |
|---------|--------------|---------------|
| Tiempo de análisis por licitación | 2–4 horas | 5 minutos |
| Licitaciones evaluadas por semana | 3–5 | 20–30 |
| Postulaciones descartadas a tiempo | Pocas | La mayoría |

**Argumento de venta:** una empresa que factura $5M anuales al Estado paga su suscripción anual en el tiempo que ahorra analizando sus primeras 10 licitaciones del mes.

---

## Módulo 2 — Borrador de Propuesta Técnica

### Qué hace
Con las bases ya analizadas (Módulo 1) y el perfil de la empresa cargado en el sistema, genera automáticamente un primer borrador de propuesta técnica que incluye:

- **Estructura completa** alineada a los criterios de evaluación de esa licitación específica.
- **Secciones pre-llenadas** con la información de la empresa (experiencia, equipo, certificaciones).
- **Respuestas a requisitos técnicos** redactadas en tono formal licitatorio chileno.
- **Placeholders claros** para lo que el usuario debe completar manualmente (valores únicos, pricing, firma).
- **Tabla de documentos** con estado de cada uno (adjunto / pendiente / no aplica).

El borrador se exporta en formato editable (DOCX) o se puede seguir editando en el panel.

### Qué le gusta al cliente
- **"La IA me escribió el 60% de la propuesta. Solo tuve que revisar y agregar los precios."**
- Estandariza el lenguaje de las propuestas (elimina errores de redacción que bajan el puntaje técnico).
- Permite postular a 3x más licitaciones con el mismo equipo.

### Valor agregado al negocio
| Métrica | Sin el módulo | Con el módulo |
|---------|--------------|---------------|
| Tiempo de redacción por propuesta | 8–16 horas | 1–2 horas |
| Costo por propuesta (hora profesional) | $80.000–$160.000 | $10.000–$20.000 |
| Tasa de postulación efectiva | Baja (costo alto) | Alta (costo bajo) |

**Argumento de venta:** si una empresa gana 1 licitación adicional al año gracias a postular más, el ROI es de 10x–100x sobre la suscripción.

**Dependencia técnica:** requiere el Módulo 1 funcionando. El análisis de bases es el input del generador de propuestas.

---

## Módulo 3 — Inteligencia Competitiva

### Qué hace
Analiza el historial de adjudicaciones de Mercado Público para revelar la dinámica real del mercado en cada rubro y organismo:

- **Mapa de competidores** — quiénes ganan en el mismo UNSPSC, con qué frecuencia y con qué monto.
- **Rangos de precios adjudicados** — distribución de precios ganadores históricos para dimensionar ofertas.
- **Perfil de cada organismo comprador** — ¿compra mucho de un solo proveedor? ¿rota? ¿tiene proveedor dominante?
- **Alertas de renovación** — contratos que vencen próximamente donde la empresa tiene chance de entrar.
- **Score de viabilidad** — estimación de probabilidad de ganar basada en historial (monto, competidores típicos, requisitos).

### Qué le gusta al cliente
- **"Ahora sé exactamente a qué precio tengo que llegar para ganar en JUNAEB."**
- Identifica los "organismos fáciles" donde hay poca competencia en su rubro.
- Muestra las renovaciones antes de que se publiquen, dando tiempo de prepararse.

### Valor agregado al negocio
| Métrica | Sin el módulo | Con el módulo |
|---------|--------------|---------------|
| Estrategia de pricing | Intuición | Datos históricos reales |
| Organismos objetivo | Los que aparecen | Los que tienen mejor probabilidad |
| Anticipación a renovaciones | 0 días | 30–90 días |

**Argumento de venta:** una empresa que mejora su tasa de adjudicación del 15% al 25% en un mercado de $10M de pipeline aumenta sus ingresos en $1M. La suscripción anual representa menos del 1% de ese incremento.

---

## Estrategia de Implementación

### Orden de construcción (por dependencias y valor/esfuerzo)

```
Sprint A — Fundamentos IA (Plan 0)
  ├── Infraestructura de análisis de documentos
  ├── Pipeline PDF → chunks → embeddings en pgvector
  └── Tabla de resultados de análisis IA en BD

Sprint B — Módulo 1: Auto-análisis de Bases
  ├── Tarea Celery: analizar PDF con LLM al descargarlo
  ├── Endpoint: GET /licitaciones/{codigo}/analisis
  └── Frontend: panel de checklist de requisitos

Sprint C — Módulo 2: Borrador de Propuesta
  ├── Perfil de empresa extendido (experiencia, equipo, certs)
  ├── Tarea: generar borrador usando análisis + perfil
  ├── Endpoint: POST /licitaciones/{codigo}/propuesta
  └── Frontend: editor de propuesta + exportar DOCX

Sprint D — Módulo 3: Inteligencia Competitiva
  ├── Sync de adjudicaciones históricas desde ChileCompra
  ├── Vistas materializadas de analytics por organismo/rubro
  ├── Endpoints: ranking proveedores, precios históricos
  └── Frontend: dashboard de inteligencia competitiva
```

### Dependencias críticas
- **Módulo 2 depende de Módulo 1**: el borrador necesita el análisis estructurado de bases.
- **Módulo 3 es independiente**: puede construirse en paralelo con el 1 y 2.
- **Plan 0 desbloquea los 3**: hay fundamentos de infraestructura que los 3 módulos comparten.

### Recursos necesarios
- LLM: Anthropic API (Claude) — ya integrado vía LiteLLM.
- Embeddings: Voyage AI — ya configurado.
- Storage: Cloudflare R2 — ya integrado para PDFs.
- BD vectorial: pgvector — ya instalado.

**No se necesita stack nuevo.** Todo se construye sobre la infraestructura existente.

---

## Posicionamiento frente a la competencia

| Feature | Radar Público | LicitaLAB | LicitaPyme |
|---------|--------------|-----------|------------|
| Análisis automático de bases | ✅ (Módulo 1) | ❌ | ❌ |
| Generador de propuestas | ✅ (Módulo 2) | ❌ | ❌ |
| Inteligencia competitiva | ✅ (Módulo 3) | Parcial | ❌ |
| Chat con bases técnicas | ✅ (roadmap) | ❌ | ❌ |
| Precio estimado para ganar | ✅ (Módulo 3) | ❌ | ❌ |

**El diferenciador clave:** no somos un buscador de licitaciones con IA encima. Somos un sistema de inteligencia comercial que acompaña a la empresa desde "encontré una oportunidad" hasta "presenté mi oferta". Eso es lo que la competencia no tiene y lo que justifica un precio 2x–3x mayor.

---

*Documento vivo — actualizar con cada sprint completado.*
