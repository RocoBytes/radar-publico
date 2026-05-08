# Modelo de datos — Radar Público

Documento de referencia que explica cada tabla del schema en `schema.sql`. Está organizado por dominio (mismo agrupamiento que el SQL) para facilitar la navegación.

## Decisiones generales

- **Postgres 16 con tres extensiones obligatorias**: `pgvector` (búsqueda semántica), `pg_trgm` (búsqueda fuzzy en nombres), `unaccent` (búsqueda en español ignorando tildes).
- **IDs internos en UUID v4** para todas las entidades de aplicación. Las entidades que vienen de Mercado Público mantienen su clave natural (`codigo` para licitaciones, `rut` para proveedores, `codigo_organismo` para organismos) — esto facilita upserts en la sincronización.
- **Timestamps en `timestamptz`** (siempre UTC en BD, conversión a zona horaria en la capa de presentación).
- **Soft delete con `deleted_at`** solo donde tiene sentido auditar (usuarios). El resto usa hard delete con `ON DELETE CASCADE`.
- **`raw_payload jsonb`** en tablas que sincronizan datos externos (licitaciones, OCs, plan anual). Guarda la respuesta original de la API por si necesitamos re-procesar sin volver a consultar.
- **Embeddings de 1024 dimensiones** asumiendo Voyage AI `voyage-3-large` o equivalente. Si cambias el modelo, hay que recrear los índices con la nueva dimensión.
- **Índices HNSW** sobre vectores (mejor rendimiento que IVFFlat para datasets pequeños-medianos).

## 1. Usuarios y empresas

### `usuarios`
Cuenta del sistema. Hay dos roles: `admin` (operador del SaaS, tú) y `proveedor` (cliente final). Un usuario `proveedor` está asociado 1:1 a una `empresa`.

Campos clave:
- `must_change_password`: en `true` cuando creas la cuenta con contraseña temporal; el primer login fuerza el cambio.
- `failed_login_attempts` + `locked_until`: implementan el rate-limit de US-2.1 (5 intentos en 15 min → bloqueo 30 min).
- `email_verified_at`: aunque las cuentas se crean por invitación, conviene confirmar el email en el primer login.

### `empresas`
Datos de la empresa proveedora. Relación 1:1 estricta con `usuarios` (tu regla de negocio: un usuario, una empresa). Si un cliente quiere asociar otra empresa, creas otra cuenta.

Campos clave:
- `regiones_operacion` y `comunas_operacion` como arrays de texto: simple, eficiente para filtros, sin necesidad de tablas pivot porque los valores vienen de catálogos cerrados.
- `certificaciones` como `jsonb`: estructura libre para guardar `[{tipo: "ISO 9001", numero: "...", vigencia: "..."}]`.
- `onboarding_completado`: bandera que el frontend usa para forzar el wizard del Epic 3.
- `contacto_telefono_verificado`: usado para validar OTP antes de activar WhatsApp.

## 2. Tickets de ChileCompra

### `tickets_api`
Cifrado y aislado en su propia tabla por seguridad. Relación 1:1 con `empresas`.

Campos clave:
- `ticket_cifrado`: cifrado con AES-256 usando una clave maestra en variable de entorno (`ENCRYPTION_KEY`). Nunca se descifra excepto en memoria al hacer una request a la API.
- `ticket_ultimos_4`: para mostrar en UI sin exponer el secreto.
- `cargado_por_admin_id`: trazabilidad. Quién cargó el ticket queda registrado.
- `ultima_validacion_at` + `ultimo_error`: cuando una request falla por ticket inválido, se marca aquí para que admin lo vea en su panel.

## 3. Intereses y radares

### `intereses`
Tabla flexible con `tipo` enumerado: el cliente puede agregar UNSPSC a cualquier nivel (segmento, familia, clase, commodity), keywords libres, o ejemplos (códigos de licitaciones a las que postuló antes).

Campos clave:
- `embedding`: solo se llena para `keyword` y `ejemplo_codigo`. Los UNSPSC se filtran por código exacto.
- `prioridad`: peso 1-10 que afecta el cálculo del `score` de relevancia.
- Constraint único `(empresa_id, tipo, valor)`: evita duplicados.

### `radares`
Búsquedas guardadas con configuración de alertas. Hasta 20 por empresa (validado en aplicación, no en BD).

Campos clave:
- `filtros jsonb`: contiene la estructura completa de filtros tal como los selecciona el usuario en UI. Ejemplo:
  ```json
  {
    "unspsc": ["43", "72151500"],
    "estado": ["publicada"],
    "regiones": ["Metropolitana"],
    "monto_min": 5000000,
    "monto_max": 50000000,
    "tipos": ["LP", "LE"],
    "keywords": ["mantención", "soporte"]
  }
  ```
- `notif_canal`, `notif_frecuencia`, `notif_score_minimo`: configuración por radar (puede diferir de las preferencias globales del usuario).

## 4. Catálogos

### `organismos`
Catálogo de organismos compradores. Se sincroniza desde la API de Mercado Público (`BuscarComprador`).

### `proveedores`
Catálogo de proveedores. Se sincroniza desde la API y desde Datos Abiertos.

### `unspsc_codigos`
Catálogo jerárquico de UNSPSC. Se carga una vez desde el archivo oficial (descarga de `unspsc.org`) o desde el catálogo que publica ChileCompra.

Campos clave:
- `nivel`: 2 (segmento), 4 (familia), 6 (clase), 8 (commodity).
- `parent_codigo`: auto-referencia para construir árbol jerárquico.
- `embedding`: para matching semántico contra título de licitación.

### `regiones` y `comunas`
Catálogos cerrados de Chile. Se llenan con seed inicial y no cambian.

## 5. Licitaciones

### `licitaciones`
Tabla principal del producto. La PK es el `codigo` natural de Mercado Público (ej: `1509-5-L114`), no un UUID, porque permite hacer upserts directos durante la sincronización sin lookups.

Campos clave:
- `estado`: enum aplicación. `estado_codigo` guarda el código numérico original de la API (5, 6, 7, 8, 18, 19) por trazabilidad.
- `monto_estimado`: en la unidad indicada por `moneda` (CLP, UF, USD, EUR, CLF).
- `es_renovable` + `unidad_tiempo_contrato` + `tiempo_contrato`: campos crudos de la API.
- `duracion_estimada_meses`: campo derivado calculado durante ingesta para facilitar queries de renovación.
- `fecha_estimada_termino_contrato`: derivado = `fecha_adjudicacion + duracion_estimada_meses`. Es el campo clave para el feed de "Renovaciones detectadas" del Epic 9.
- `search_vector tsvector`: actualizado por trigger ante cambios en `nombre` o `descripcion`. Usa configuración `es_unaccent` (español + sin tildes).
- `embedding`: vector del título + descripción. Generado en post-sincronización por un worker.
- `hash_contenido`: SHA-256 del payload normalizado. Permite detectar cambios sin comparar campo por campo.
- `detalle_sincronizado_at`, `bases_descargadas_at`, `bases_procesadas_at`: timestamps de control para el pipeline asíncrono. Si `detalle_sincronizado_at` es null, hay que llamar al endpoint por código. Si `bases_descargadas_at` es null, hay que correr el scraper.

### `licitacion_items`
Cada licitación puede tener N items. Cada item tiene su UNSPSC propio (importante: el filtro principal de búsqueda por rubro se hace sobre `licitacion_items.unspsc_codigo`, no sobre la licitación completa, porque una licitación puede combinar rubros).

### `criterios_evaluacion`
Criterios con sus ponderaciones. La suma debería ser 100. Esta tabla se llena con dos fuentes:
1. La API si los expone estructurados.
2. Extracción IA desde el PDF de bases si la API no los entrega.

### `licitacion_fechas`
Tabla normalizada de todas las fechas del calendario (Epic 6.3). Permite query simple "dame todas las fechas futuras de esta licitación" y triggerea las notificaciones de recordatorio.

## 6. Documentos y RAG

### `documentos_bases`
Cada PDF/anexo descargado del portal. El binario va en R2; la BD guarda solo el path y metadata.

Campos clave:
- `texto_extraido`: texto completo extraído del PDF (con pymupdf). Útil para búsquedas full-text simples sin necesidad de embeddings.
- `status`: `pendiente` → `descargado` → `procesado`. Permite reintentar fallos.
- `hash_contenido`: si un documento se actualiza (caso "aclaración"), permite detectarlo.

### `documento_chunks`
Chunks semánticos del PDF para RAG. Cada chunk tiene su embedding y se referencia con `pagina_inicio`/`pagina_fin` para citar al usuario qué parte del PDF original contiene la respuesta del chat.

## 7. OCs y adjudicaciones

### `ordenes_compra`
Igual a licitaciones: PK natural, raw_payload, estado dual.

### `adjudicaciones`
Una licitación puede tener múltiples adjudicaciones (un adjudicado por item, o adjudicaciones parciales). Cada fila vincula `licitacion_codigo` con `rut_proveedor`.

Esta tabla es central para el Epic 7 (análisis de mercado) y para detectar competencia.

## 8. Pipeline de seguimiento

### `pipeline_items`
Una entrada por cada licitación que el cliente decide trackear. Constraint único `(empresa_id, licitacion_codigo)` garantiza una sola entrada por par.

Campos clave:
- `estado`: ver enum del Epic 10.
- `score` y `score_justificacion`: se calculan al detectar la oportunidad. Ejemplo de `score_justificacion`:
  ```json
  {
    "match_unspsc": 40,
    "match_region": 15,
    "match_keywords": 25,
    "experiencia_organismo": 10,
    "rango_monto": 10,
    "total": 100,
    "explicacion": "Coincide con tu interés en UNSPSC 43, opera en RM, y has postulado antes a este organismo"
  }
  ```
- `detected_by_radar_id`: si la oportunidad vino de un radar específico, queda anotado.

### `pipeline_notas` y `pipeline_archivos`
Comentarios y archivos adjuntos por el usuario sobre cada licitación de su pipeline. Los archivos van a R2 y aquí queda solo el path.

## 9. Plan anual

### `plan_anual_lineas`
Una fila por línea del plan anual de cada organismo. La carga es masiva una vez al año (descarga de Datos Abiertos) y luego se actualiza cuando los organismos publican modificaciones.

Campo clave: `licitacion_codigo` (FK opcional). Cuando una línea del plan se "materializa" en una licitación real, se actualiza este campo, lo que permite mostrar al cliente el ciclo completo (planeada → publicada → adjudicada).

## 10. Notificaciones

### `notificaciones`
Cola unificada para los tres canales (email, WhatsApp, in-app). Worker periódico levanta las que están `pendiente` con `programada_para <= now()` y las envía.

Campos clave:
- `programada_para`: permite agendar (ej: recordatorio 24h antes del cierre).
- `datos jsonb`: payload con datos para renderizar la plantilla.
- `radar_id`: si la notificación vino de un radar, queda enlazada para analytics.

### `preferencias_notificaciones`
Configuración por empresa, separada de la tabla de empresas para no inflar el row principal y para tener su propio updated_at.

## 11. Conversaciones IA

### `conversaciones_ia` y `conversacion_mensajes`
Cada conversación tiene contexto opcional de una licitación específica (chat con bases). Los mensajes guardan el rol estilo OpenAI/Anthropic, las citas que generó el modelo (referenciando chunks del PDF), y métricas de uso para facturación interna.

## 12. Auditoría y cuotas

### `eventos_auditoria`
Log de acciones sensibles: login, cambio de password, creación de cuenta, suspensión, modificación de ticket, etc. Tabla append-only, particionable por mes en producción.

### `api_quota_log`
Una fila por cada llamada a la API de Mercado Público. Permite:
- Mostrar al cliente y al admin el consumo del día.
- Detectar saturación antes de los 10K.
- Debuggear errores específicos.
- Facturar uso si en el futuro hay planes por consumo.

En producción esta tabla crece rápido. Estrategia: particionar por día y mantener solo 30 días en línea, archivar el resto.

### `llm_usage_log`
Equivalente para consumo de IA. Crítico para controlar costos por cliente y por feature.

## 13. Sesiones

### `refresh_tokens`
Tokens de refresh hasheados (nunca guardamos el token en claro). Permite revocar sesiones individualmente desde admin.

### `password_reset_tokens`
Mismo patrón. Token hasheado con expiración de 30 minutos.

---

## Patrones de query típicos

A modo de validación, estas son las queries más importantes del producto y cómo el schema las soporta eficientemente:

### "Dame oportunidades activas para el cliente X ordenadas por score"

```sql
SELECT l.*, pi.score, pi.estado as pipeline_estado
FROM licitaciones l
LEFT JOIN pipeline_items pi
  ON pi.licitacion_codigo = l.codigo AND pi.empresa_id = $1
WHERE l.estado = 'publicada'
  AND l.fecha_cierre > now()
  AND EXISTS (
    SELECT 1 FROM licitacion_items li
    JOIN intereses i ON i.empresa_id = $1
    WHERE li.licitacion_codigo = l.codigo
      AND i.tipo IN ('unspsc_segmento','unspsc_familia','unspsc_clase','unspsc_commodity')
      AND li.unspsc_codigo LIKE i.valor || '%'
  )
ORDER BY pi.score DESC NULLS LAST, l.fecha_cierre ASC
LIMIT 25;
```

Usa: `idx_licitaciones_estado`, `idx_licitaciones_fecha_cierre`, `idx_items_unspsc`, `idx_intereses_empresa`.

### "Búsqueda full-text en español"

```sql
SELECT l.codigo, l.nombre, ts_rank(l.search_vector, query) as rank
FROM licitaciones l, plainto_tsquery('es_unaccent', $1) query
WHERE l.search_vector @@ query
ORDER BY rank DESC
LIMIT 25;
```

Usa: `idx_licitaciones_search`.

### "Búsqueda semántica (vecinos del embedding del query)"

```sql
SELECT l.codigo, l.nombre,
       1 - (l.embedding <=> $1::vector) as similarity
FROM licitaciones l
WHERE l.estado = 'publicada'
ORDER BY l.embedding <=> $1::vector
LIMIT 25;
```

Usa: `idx_licitaciones_embedding` (HNSW).

### "Renovaciones próximas a vencer en mis rubros"

```sql
SELECT l.codigo, l.nombre, l.fecha_estimada_termino_contrato,
       a.rut_proveedor as proveedor_actual, a.monto_adjudicado
FROM licitaciones l
JOIN adjudicaciones a ON a.licitacion_codigo = l.codigo
WHERE l.es_renovable = true
  AND l.estado = 'adjudicada'
  AND l.fecha_estimada_termino_contrato BETWEEN now() AND now() + interval '6 months'
  AND EXISTS (
    SELECT 1 FROM licitacion_items li
    JOIN intereses i ON i.empresa_id = $1
    WHERE li.licitacion_codigo = l.codigo
      AND i.tipo LIKE 'unspsc_%'
      AND li.unspsc_codigo LIKE i.valor || '%'
  )
ORDER BY l.fecha_estimada_termino_contrato ASC;
```

Usa: `idx_licitaciones_renovacion`, `idx_adj_licitacion`.

### "Histórico de precios de servicios similares"

```sql
SELECT l.codigo, l.nombre, a.monto_adjudicado, l.monto_estimado,
       a.fecha_adjudicacion, p.razon_social as proveedor
FROM licitaciones l
JOIN adjudicaciones a ON a.licitacion_codigo = l.codigo
JOIN proveedores p ON p.rut = a.rut_proveedor
JOIN licitacion_items li ON li.licitacion_codigo = l.codigo
WHERE li.unspsc_codigo LIKE $1 || '%'
  AND l.fecha_adjudicacion > now() - interval '24 months'
ORDER BY l.fecha_adjudicacion DESC
LIMIT 100;
```

Usa: `idx_items_unspsc`, `idx_adj_licitacion`.

---

## Migraciones futuras previsibles

Cosas que no están en v1 pero que conviene tener presentes para no romper compatibilidad:

- **Multi-usuario por empresa**: agregar tabla pivot `usuario_empresa_roles`. La columna `usuarios.empresa_id` actual habría que migrarla.
- **Plantillas de propuesta técnica**: una tabla `plantillas_propuesta` con secciones, y `propuestas_generadas` con el output del agente IA.
- **Equipos profesionales del cliente**: tabla `profesionales` que se cruza contra requisitos de experiencia mínima.
- **Histórico de búsquedas**: tabla `busquedas_log` para personalizar el ranking con ML.

Todas estas adiciones son aditivas y no requieren cambios disruptivos al schema base.
