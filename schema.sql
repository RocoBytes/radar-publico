-- ============================================================
-- Radar Público - Schema inicial v1
-- Postgres 16 + pgvector
-- ============================================================
-- Convenciones:
-- - snake_case para tablas y columnas
-- - id en uuid v4 generado por defecto
-- - created_at / updated_at en timestamptz UTC
-- - soft delete con deleted_at donde aplique
-- - foreign keys con ON DELETE explícito según semántica
-- ============================================================

-- Extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Configuración de búsqueda en español
CREATE TEXT SEARCH CONFIGURATION es_unaccent (COPY = spanish);
ALTER TEXT SEARCH CONFIGURATION es_unaccent
  ALTER MAPPING FOR hword, hword_part, word
  WITH unaccent, spanish_stem;


-- ============================================================
-- 1. USUARIOS Y EMPRESAS
-- ============================================================

CREATE TYPE user_status AS ENUM ('pending_activation', 'active', 'suspended', 'deleted');
CREATE TYPE user_role AS ENUM ('admin', 'proveedor');
CREATE TYPE empresa_tamano AS ENUM ('micro', 'pequena', 'mediana', 'grande');

CREATE TABLE usuarios (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  email varchar(255) NOT NULL UNIQUE,
  password_hash varchar(255) NOT NULL,
  rol user_role NOT NULL DEFAULT 'proveedor',
  status user_status NOT NULL DEFAULT 'pending_activation',
  must_change_password boolean NOT NULL DEFAULT true,
  email_verified_at timestamptz,
  last_login_at timestamptz,
  failed_login_attempts int NOT NULL DEFAULT 0,
  locked_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

CREATE INDEX idx_usuarios_email ON usuarios (email) WHERE deleted_at IS NULL;
CREATE INDEX idx_usuarios_status ON usuarios (status) WHERE deleted_at IS NULL;

CREATE TABLE empresas (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  usuario_id uuid NOT NULL UNIQUE REFERENCES usuarios(id) ON DELETE CASCADE,
  rut varchar(20) NOT NULL UNIQUE,
  razon_social varchar(255) NOT NULL,
  nombre_fantasia varchar(255),
  giros text[],
  tamano empresa_tamano,
  ano_fundacion smallint,
  numero_empleados int,
  regiones_operacion text[] NOT NULL DEFAULT '{}',
  comunas_operacion text[] DEFAULT '{}',
  sello_empresa_mujer boolean NOT NULL DEFAULT false,
  inscrito_chileproveedores boolean NOT NULL DEFAULT false,
  certificaciones jsonb DEFAULT '[]'::jsonb,
  contacto_telefono varchar(30),
  contacto_telefono_verificado boolean NOT NULL DEFAULT false,
  contacto_direccion text,
  onboarding_completado boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_empresas_rut ON empresas (rut);
CREATE INDEX idx_empresas_usuario_id ON empresas (usuario_id);


-- ============================================================
-- 2. TICKETS DE CHILECOMPRA
-- ============================================================

CREATE TYPE ticket_status AS ENUM ('pending', 'active', 'error', 'rate_limited', 'expired');

CREATE TABLE tickets_api (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL UNIQUE REFERENCES empresas(id) ON DELETE CASCADE,
  ticket_cifrado text NOT NULL,
  ticket_ultimos_4 varchar(4) NOT NULL,
  status ticket_status NOT NULL DEFAULT 'pending',
  cuota_diaria_max int NOT NULL DEFAULT 10000,
  cargado_por_admin_id uuid REFERENCES usuarios(id),
  cargado_at timestamptz,
  ultima_validacion_at timestamptz,
  ultimo_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_tickets_status ON tickets_api (status);


-- ============================================================
-- 3. INTERESES (RUBROS) Y RADARES
-- ============================================================

CREATE TYPE interes_tipo AS ENUM ('unspsc_segmento', 'unspsc_familia', 'unspsc_clase', 'unspsc_commodity', 'keyword', 'ejemplo_codigo');

CREATE TABLE intereses (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  tipo interes_tipo NOT NULL,
  valor varchar(255) NOT NULL,
  prioridad smallint NOT NULL DEFAULT 5 CHECK (prioridad BETWEEN 1 AND 10),
  embedding vector(1024),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, tipo, valor)
);

CREATE INDEX idx_intereses_empresa ON intereses (empresa_id);
CREATE INDEX idx_intereses_tipo_valor ON intereses (tipo, valor);

CREATE TABLE radares (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  nombre varchar(100) NOT NULL,
  descripcion text,
  filtros jsonb NOT NULL,
  activo boolean NOT NULL DEFAULT true,
  notif_canal varchar(20) NOT NULL DEFAULT 'email',
  notif_frecuencia varchar(20) NOT NULL DEFAULT 'instantaneo',
  notif_score_minimo smallint DEFAULT 70,
  ultima_ejecucion_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_radares_empresa_activo ON radares (empresa_id, activo);


-- ============================================================
-- 4. CATÁLOGOS: ORGANISMOS, PROVEEDORES, UNSPSC, REGIONES
-- ============================================================

CREATE TABLE organismos (
  codigo_organismo int PRIMARY KEY,
  rut varchar(20),
  nombre varchar(500) NOT NULL,
  ministerio varchar(255),
  region varchar(100),
  comuna varchar(100),
  direccion text,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_organismos_nombre_trgm ON organismos USING gin (nombre gin_trgm_ops);
CREATE INDEX idx_organismos_region ON organismos (region);

CREATE TABLE proveedores (
  rut varchar(20) PRIMARY KEY,
  razon_social varchar(500) NOT NULL,
  nombre_fantasia varchar(500),
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_proveedores_razon_social_trgm ON proveedores USING gin (razon_social gin_trgm_ops);

CREATE TABLE unspsc_codigos (
  codigo varchar(8) PRIMARY KEY,
  nivel smallint NOT NULL CHECK (nivel IN (2, 4, 6, 8)),
  segmento varchar(2) NOT NULL,
  familia varchar(4),
  clase varchar(6),
  commodity varchar(8),
  nombre_es varchar(500) NOT NULL,
  nombre_en varchar(500),
  descripcion_es text,
  parent_codigo varchar(8) REFERENCES unspsc_codigos(codigo),
  embedding vector(1024)
);

CREATE INDEX idx_unspsc_segmento ON unspsc_codigos (segmento);
CREATE INDEX idx_unspsc_familia ON unspsc_codigos (familia);
CREATE INDEX idx_unspsc_parent ON unspsc_codigos (parent_codigo);
CREATE INDEX idx_unspsc_nombre_trgm ON unspsc_codigos USING gin (nombre_es gin_trgm_ops);

CREATE TABLE regiones (
  codigo varchar(10) PRIMARY KEY,
  nombre varchar(100) NOT NULL,
  numero_romano varchar(10),
  orden smallint NOT NULL
);

CREATE TABLE comunas (
  codigo varchar(10) PRIMARY KEY,
  region_codigo varchar(10) NOT NULL REFERENCES regiones(codigo),
  nombre varchar(100) NOT NULL
);

CREATE INDEX idx_comunas_region ON comunas (region_codigo);


-- ============================================================
-- 5. LICITACIONES
-- ============================================================

CREATE TYPE licitacion_estado AS ENUM (
  'publicada', 'cerrada', 'desierta', 'adjudicada', 'revocada', 'suspendida', 'desconocido'
);

CREATE TABLE licitaciones (
  codigo varchar(50) PRIMARY KEY,
  external_id varchar(100),
  nombre varchar(1000) NOT NULL,
  descripcion text,
  codigo_organismo int REFERENCES organismos(codigo_organismo),
  codigo_unidad int,
  unidad_compra varchar(500),
  rut_unidad varchar(20),
  estado licitacion_estado NOT NULL,
  estado_codigo smallint,
  tipo varchar(10),
  modalidad varchar(20),
  moneda varchar(10) DEFAULT 'CLP',
  monto_estimado numeric(18, 2),
  es_renovable boolean DEFAULT false,
  unidad_tiempo_contrato smallint,
  tiempo_contrato int,
  duracion_estimada_meses int,
  fecha_creacion timestamptz,
  fecha_publicacion timestamptz,
  fecha_cierre timestamptz,
  fecha_adjudicacion timestamptz,
  fecha_estimada_termino_contrato timestamptz,
  contacto_nombre varchar(255),
  contacto_email varchar(255),
  contacto_telefono varchar(50),
  raw_payload jsonb,
  search_vector tsvector,
  embedding vector(1024),
  hash_contenido varchar(64),
  detalle_sincronizado_at timestamptz,
  bases_descargadas_at timestamptz,
  bases_procesadas_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_licitaciones_estado ON licitaciones (estado);
CREATE INDEX idx_licitaciones_organismo ON licitaciones (codigo_organismo);
CREATE INDEX idx_licitaciones_fecha_cierre ON licitaciones (fecha_cierre) WHERE estado = 'publicada';
CREATE INDEX idx_licitaciones_fecha_publicacion ON licitaciones (fecha_publicacion DESC);
CREATE INDEX idx_licitaciones_search ON licitaciones USING gin (search_vector);
CREATE INDEX idx_licitaciones_embedding ON licitaciones USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_licitaciones_renovacion ON licitaciones (fecha_estimada_termino_contrato)
  WHERE es_renovable = true AND estado = 'adjudicada';

CREATE OR REPLACE FUNCTION update_licitacion_search_vector() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('es_unaccent', coalesce(NEW.nombre, '')), 'A') ||
    setweight(to_tsvector('es_unaccent', coalesce(NEW.descripcion, '')), 'B');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_licitaciones_search_vector
BEFORE INSERT OR UPDATE OF nombre, descripcion ON licitaciones
FOR EACH ROW EXECUTE FUNCTION update_licitacion_search_vector();


-- ============================================================
-- 6. ITEMS DE LICITACIÓN
-- ============================================================

CREATE TABLE licitacion_items (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  numero_item int NOT NULL,
  categoria varchar(255),
  unspsc_codigo varchar(8) REFERENCES unspsc_codigos(codigo),
  unspsc_nombre varchar(500),
  nombre_producto varchar(1000),
  descripcion text,
  cantidad numeric(18, 4),
  unidad varchar(100),
  monto_unitario_estimado numeric(18, 2),
  especificaciones text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (licitacion_codigo, numero_item)
);

CREATE INDEX idx_items_licitacion ON licitacion_items (licitacion_codigo);
CREATE INDEX idx_items_unspsc ON licitacion_items (unspsc_codigo);


-- ============================================================
-- 7. CRITERIOS DE EVALUACIÓN Y FECHAS
-- ============================================================

CREATE TABLE criterios_evaluacion (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  nombre varchar(500) NOT NULL,
  descripcion text,
  ponderacion numeric(5, 2) NOT NULL CHECK (ponderacion >= 0 AND ponderacion <= 100),
  tipo varchar(50),
  formula text,
  orden smallint,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_criterios_licitacion ON criterios_evaluacion (licitacion_codigo);

CREATE TYPE fecha_tipo AS ENUM (
  'creacion', 'publicacion', 'preguntas_inicio', 'preguntas_fin',
  'respuestas', 'visita_terreno', 'cierre', 'apertura_tecnica',
  'apertura_economica', 'adjudicacion', 'firma_contrato', 'estimada_termino'
);

CREATE TABLE licitacion_fechas (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  tipo fecha_tipo NOT NULL,
  fecha timestamptz NOT NULL,
  es_estimada boolean DEFAULT false,
  notas text,
  UNIQUE (licitacion_codigo, tipo)
);

CREATE INDEX idx_fechas_tipo_fecha ON licitacion_fechas (tipo, fecha);


-- ============================================================
-- 8. DOCUMENTOS DE BASES Y CHUNKS PARA RAG
-- ============================================================

CREATE TYPE documento_tipo AS ENUM (
  'bases_administrativas', 'bases_tecnicas', 'anexo', 'aclaracion',
  'consulta', 'respuesta', 'acta_apertura', 'acta_adjudicacion', 'otro'
);

CREATE TYPE documento_status AS ENUM ('pendiente', 'descargado', 'procesado', 'error');

CREATE TABLE documentos_bases (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  tipo documento_tipo NOT NULL,
  nombre_original varchar(500),
  url_origen text,
  storage_path text,
  storage_bucket varchar(100),
  mime_type varchar(100),
  tamano_bytes bigint,
  num_paginas int,
  status documento_status NOT NULL DEFAULT 'pendiente',
  texto_extraido text,
  hash_contenido varchar(64),
  error_mensaje text,
  descargado_at timestamptz,
  procesado_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_docs_licitacion ON documentos_bases (licitacion_codigo);
CREATE INDEX idx_docs_status ON documentos_bases (status);

CREATE TABLE documento_chunks (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  documento_id uuid NOT NULL REFERENCES documentos_bases(id) ON DELETE CASCADE,
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  chunk_orden int NOT NULL,
  contenido text NOT NULL,
  pagina_inicio int,
  pagina_fin int,
  tokens int,
  embedding vector(1024) NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_chunks_documento ON documento_chunks (documento_id);
CREATE INDEX idx_chunks_licitacion ON documento_chunks (licitacion_codigo);
CREATE INDEX idx_chunks_embedding ON documento_chunks USING hnsw (embedding vector_cosine_ops);


-- ============================================================
-- 9. ÓRDENES DE COMPRA Y ADJUDICACIONES
-- ============================================================

CREATE TYPE oc_estado AS ENUM ('emitida', 'aceptada', 'rechazada', 'cancelada', 'en_proceso', 'recepcion_conforme', 'pagada', 'desconocido');

CREATE TABLE ordenes_compra (
  codigo varchar(50) PRIMARY KEY,
  licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE SET NULL,
  codigo_organismo int REFERENCES organismos(codigo_organismo),
  rut_proveedor varchar(20) REFERENCES proveedores(rut),
  estado oc_estado NOT NULL,
  estado_codigo smallint,
  nombre varchar(1000),
  descripcion text,
  moneda varchar(10) DEFAULT 'CLP',
  total_neto numeric(18, 2),
  total_impuestos numeric(18, 2),
  total numeric(18, 2),
  fecha_envio timestamptz,
  fecha_aceptacion timestamptz,
  raw_payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_oc_licitacion ON ordenes_compra (licitacion_codigo);
CREATE INDEX idx_oc_organismo ON ordenes_compra (codigo_organismo);
CREATE INDEX idx_oc_proveedor ON ordenes_compra (rut_proveedor);
CREATE INDEX idx_oc_fecha_envio ON ordenes_compra (fecha_envio DESC);

CREATE TABLE adjudicaciones (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  rut_proveedor varchar(20) NOT NULL REFERENCES proveedores(rut),
  numero_item int,
  monto_adjudicado numeric(18, 2),
  cantidad numeric(18, 4),
  fecha_adjudicacion timestamptz,
  fundamento text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_adj_licitacion ON adjudicaciones (licitacion_codigo);
CREATE INDEX idx_adj_proveedor ON adjudicaciones (rut_proveedor);


-- ============================================================
-- 10. PIPELINE DE SEGUIMIENTO
-- ============================================================

CREATE TYPE pipeline_estado AS ENUM (
  'nueva', 'vista', 'interesado', 'postulando', 'postulada',
  'adjudicada', 'perdida', 'descartada'
);

CREATE TABLE pipeline_items (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  licitacion_codigo varchar(50) NOT NULL REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  estado pipeline_estado NOT NULL DEFAULT 'nueva',
  score smallint CHECK (score BETWEEN 0 AND 100),
  score_justificacion jsonb,
  razon_descarte text,
  monto_postulado numeric(18, 2),
  resultado_observaciones text,
  detected_by_radar_id uuid REFERENCES radares(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, licitacion_codigo)
);

CREATE INDEX idx_pipeline_empresa_estado ON pipeline_items (empresa_id, estado);
CREATE INDEX idx_pipeline_licitacion ON pipeline_items (licitacion_codigo);

CREATE TABLE pipeline_notas (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  pipeline_item_id uuid NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
  contenido text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notas_item ON pipeline_notas (pipeline_item_id, created_at DESC);

CREATE TABLE pipeline_archivos (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  pipeline_item_id uuid NOT NULL REFERENCES pipeline_items(id) ON DELETE CASCADE,
  nombre_original varchar(500) NOT NULL,
  storage_path text NOT NULL,
  mime_type varchar(100),
  tamano_bytes bigint,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_archivos_item ON pipeline_archivos (pipeline_item_id);


-- ============================================================
-- 11. PLAN ANUAL DE COMPRAS
-- ============================================================

CREATE TYPE plan_anual_status AS ENUM ('planificada', 'publicada', 'adjudicada', 'cancelada');

CREATE TABLE plan_anual_lineas (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  ano smallint NOT NULL,
  codigo_organismo int NOT NULL REFERENCES organismos(codigo_organismo),
  descripcion text NOT NULL,
  unspsc_codigo varchar(8) REFERENCES unspsc_codigos(codigo),
  unspsc_nombre varchar(500),
  monto_estimado numeric(18, 2),
  moneda varchar(10) DEFAULT 'CLP',
  mes_estimado smallint CHECK (mes_estimado BETWEEN 1 AND 12),
  modalidad varchar(50),
  status plan_anual_status NOT NULL DEFAULT 'planificada',
  licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE SET NULL,
  search_vector tsvector,
  embedding vector(1024),
  raw_payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_plan_organismo_ano ON plan_anual_lineas (codigo_organismo, ano);
CREATE INDEX idx_plan_unspsc ON plan_anual_lineas (unspsc_codigo);
CREATE INDEX idx_plan_status ON plan_anual_lineas (status);
CREATE INDEX idx_plan_search ON plan_anual_lineas USING gin (search_vector);
CREATE INDEX idx_plan_embedding ON plan_anual_lineas USING hnsw (embedding vector_cosine_ops);


-- ============================================================
-- 12. NOTIFICACIONES
-- ============================================================

CREATE TYPE notif_canal AS ENUM ('email', 'whatsapp', 'in_app');
CREATE TYPE notif_status AS ENUM ('pendiente', 'enviada', 'fallida', 'leida', 'cancelada');
CREATE TYPE notif_tipo AS ENUM (
  'nueva_oportunidad', 'recordatorio_cierre', 'cambio_estado',
  'adjudicacion_postulacion', 'oportunidad_futura', 'sistema'
);

CREATE TABLE notificaciones (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  tipo notif_tipo NOT NULL,
  canal notif_canal NOT NULL,
  status notif_status NOT NULL DEFAULT 'pendiente',
  titulo varchar(255) NOT NULL,
  cuerpo text NOT NULL,
  datos jsonb DEFAULT '{}'::jsonb,
  licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE SET NULL,
  radar_id uuid REFERENCES radares(id) ON DELETE SET NULL,
  programada_para timestamptz NOT NULL DEFAULT now(),
  enviada_at timestamptz,
  leida_at timestamptz,
  error_mensaje text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notif_empresa_status ON notificaciones (empresa_id, status);
CREATE INDEX idx_notif_programada ON notificaciones (programada_para) WHERE status = 'pendiente';
CREATE INDEX idx_notif_in_app ON notificaciones (empresa_id, leida_at) WHERE canal = 'in_app';


-- ============================================================
-- 13. CHAT CON BASES (CONVERSACIONES IA)
-- ============================================================

CREATE TABLE conversaciones_ia (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  empresa_id uuid NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  licitacion_codigo varchar(50) REFERENCES licitaciones(codigo) ON DELETE CASCADE,
  titulo varchar(255),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_conv_empresa ON conversaciones_ia (empresa_id);
CREATE INDEX idx_conv_licitacion ON conversaciones_ia (licitacion_codigo);

CREATE TYPE mensaje_rol AS ENUM ('user', 'assistant', 'system');

CREATE TABLE conversacion_mensajes (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  conversacion_id uuid NOT NULL REFERENCES conversaciones_ia(id) ON DELETE CASCADE,
  rol mensaje_rol NOT NULL,
  contenido text NOT NULL,
  citas jsonb DEFAULT '[]'::jsonb,
  modelo_usado varchar(50),
  tokens_input int,
  tokens_output int,
  costo_estimado numeric(10, 6),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_msg_conversacion ON conversacion_mensajes (conversacion_id, created_at);


-- ============================================================
-- 14. PREFERENCIAS DE NOTIFICACIONES
-- ============================================================

CREATE TABLE preferencias_notificaciones (
  empresa_id uuid PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
  email_activo boolean NOT NULL DEFAULT true,
  email_frecuencia varchar(20) NOT NULL DEFAULT 'instantaneo',
  email_score_minimo smallint DEFAULT 70,
  whatsapp_activo boolean NOT NULL DEFAULT false,
  whatsapp_solo_criticas boolean NOT NULL DEFAULT true,
  whatsapp_score_minimo smallint DEFAULT 90,
  whatsapp_pausado_hasta timestamptz,
  in_app_activo boolean NOT NULL DEFAULT true,
  tipos_activos jsonb DEFAULT '[
    "nueva_oportunidad",
    "recordatorio_cierre",
    "cambio_estado",
    "adjudicacion_postulacion",
    "oportunidad_futura"
  ]'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);


-- ============================================================
-- 15. AUDITORÍA Y CUOTAS
-- ============================================================

CREATE TABLE eventos_auditoria (
  id bigserial PRIMARY KEY,
  usuario_id uuid REFERENCES usuarios(id) ON DELETE SET NULL,
  empresa_id uuid REFERENCES empresas(id) ON DELETE SET NULL,
  accion varchar(100) NOT NULL,
  recurso_tipo varchar(50),
  recurso_id varchar(100),
  ip_address inet,
  user_agent text,
  metadata jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_usuario ON eventos_auditoria (usuario_id, created_at DESC);
CREATE INDEX idx_audit_empresa ON eventos_auditoria (empresa_id, created_at DESC);
CREATE INDEX idx_audit_accion ON eventos_auditoria (accion, created_at DESC);

CREATE TABLE api_quota_log (
  id bigserial PRIMARY KEY,
  ticket_id uuid REFERENCES tickets_api(id) ON DELETE SET NULL,
  empresa_id uuid REFERENCES empresas(id) ON DELETE SET NULL,
  endpoint varchar(255) NOT NULL,
  metodo varchar(10) NOT NULL,
  status_code int,
  ip_address inet,
  duracion_ms int,
  request_params jsonb,
  error_mensaje text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_quota_ticket_fecha ON api_quota_log (ticket_id, created_at DESC);
CREATE INDEX idx_quota_empresa_fecha ON api_quota_log (empresa_id, created_at DESC);

CREATE TABLE llm_usage_log (
  id bigserial PRIMARY KEY,
  empresa_id uuid REFERENCES empresas(id) ON DELETE SET NULL,
  feature varchar(50) NOT NULL,
  provider varchar(50) NOT NULL,
  modelo varchar(100) NOT NULL,
  tokens_input int NOT NULL DEFAULT 0,
  tokens_output int NOT NULL DEFAULT 0,
  costo_estimado numeric(10, 6),
  duracion_ms int,
  status varchar(20) NOT NULL,
  error_mensaje text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_empresa_fecha ON llm_usage_log (empresa_id, created_at DESC);
CREATE INDEX idx_llm_feature ON llm_usage_log (feature, created_at DESC);


-- ============================================================
-- 16. SESIONES Y TOKENS DE RECUPERACIÓN
-- ============================================================

CREATE TABLE refresh_tokens (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  token_hash varchar(255) NOT NULL UNIQUE,
  ip_address inet,
  user_agent text,
  expires_at timestamptz NOT NULL,
  revocado_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_usuario ON refresh_tokens (usuario_id) WHERE revocado_at IS NULL;
CREATE INDEX idx_refresh_expires ON refresh_tokens (expires_at) WHERE revocado_at IS NULL;

CREATE TABLE password_reset_tokens (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  token_hash varchar(255) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  usado_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_reset_token ON password_reset_tokens (token_hash) WHERE usado_at IS NULL;


-- ============================================================
-- 17. TRIGGERS DE updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  t text;
BEGIN
  FOR t IN
    SELECT table_name FROM information_schema.columns
    WHERE column_name = 'updated_at' AND table_schema = 'public'
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%I_updated_at BEFORE UPDATE ON %I
       FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t
    );
  END LOOP;
END $$;
