# SDD – SaaS de Inteligencia para Licitaciones en Mercado Público

## 1. Contexto general del proyecto

Este proyecto corresponde al desarrollo de un SaaS especializado en licitaciones del Estado de Chile, enfocado principalmente en Mercado Público / ChileCompra. La idea central es crear una plataforma que ayude a empresas proveedoras a detectar, analizar, priorizar y gestionar oportunidades de negocio públicas de forma más rápida, inteligente y ordenada.

El objetivo no es construir solamente un buscador de licitaciones, sino una plataforma de inteligencia comercial para empresas que venden al Estado. El sistema debe ayudar a resolver los principales dolores que tienen las pymes y empresas proveedoras cuando trabajan con Mercado Público: exceso de información, poco tiempo para revisar bases, dificultad para entender requisitos, falta de seguimiento, incertidumbre sobre si conviene postular, desconocimiento de precios de mercado, poca visibilidad sobre competidores y pérdida de oportunidades por no enterarse a tiempo.

El producto debe inspirarse en el concepto de plataformas SaaS como LicitaPyme, pero con un enfoque propio: entregar tecnología, automatización, análisis de datos e inteligencia artificial para que las empresas puedan vender mejor, tomar decisiones más informadas y aumentar sus probabilidades de adjudicación.

---

## 2. Problema que resuelve

Las empresas que quieren vender al Estado enfrentan varios problemas operativos y estratégicos:

1. Deben revisar manualmente Mercado Público todos los días.
2. Pierden tiempo buscando licitaciones que realmente calcen con su rubro.
3. Muchas oportunidades relevantes pasan desapercibidas por mala clasificación o falta de alertas.
4. Leer bases administrativas y técnicas toma mucho tiempo.
5. No siempre saben si cumplen los requisitos de una licitación.
6. No tienen claridad sobre los documentos obligatorios para postular.
7. No conocen bien a sus competidores ni sus precios históricos.
8. No saben si una oportunidad es rentable o si tiene alto riesgo.
9. No tienen un sistema ordenado para hacer seguimiento de fechas, preguntas, respuestas, cierre y adjudicación.
10. Dependen de planillas, correos, recordatorios manuales o conocimiento informal de una persona.
11. Les cuesta convertir los datos públicos de Mercado Público en decisiones comerciales concretas.

El SaaS debe atacar directamente estos dolores con módulos funcionales claros, automatización y análisis inteligente.

---

## 3. Objetivo del producto

Construir una plataforma SaaS que permita a empresas proveedoras:

* Encontrar oportunidades relevantes en Mercado Público.
* Recibir alertas automáticas según rubro, palabras clave, región, comprador, monto, fechas y tipo de oportunidad.
* Analizar licitaciones con apoyo de inteligencia artificial.
* Resumir bases técnicas y administrativas.
* Identificar requisitos, documentos, garantías, fechas importantes y criterios de evaluación.
* Calcular un puntaje de oportunidad para decidir si conviene postular.
* Revisar precios históricos y comportamiento del mercado.
* Analizar competidores, proveedores adjudicados y compradores públicos.
* Gestionar el pipeline de oportunidades desde detección hasta adjudicación.
* Reducir el tiempo operativo de revisión y aumentar la calidad de la decisión comercial.

---

## 4. Enfoque del SaaS

El sistema debe funcionar como un SaaS multiusuario y eventualmente multitenant, donde cada empresa pueda tener su propio espacio de trabajo.

Cada empresa usuaria debe poder configurar su perfil comercial, rubros, palabras clave, regiones de interés, montos mínimos, tipos de oportunidad y criterios de búsqueda. A partir de esa configuración, el sistema debe detectar automáticamente oportunidades desde Mercado Público y presentarlas de forma priorizada.

El valor principal del sistema debe estar en transformar datos públicos en información accionable.

No basta con mostrar licitaciones. El sistema debe ayudar a responder preguntas como:

* ¿Esta licitación es relevante para mi empresa?
* ¿Cumplo los requisitos?
* ¿Cuáles son los documentos que debo preparar?
* ¿Cuánto tiempo queda para postular?
* ¿Quién suele ganar este tipo de licitaciones?
* ¿Qué precios se han adjudicado anteriormente?
* ¿Qué tan competitiva parece esta oportunidad?
* ¿Qué riesgo tiene?
* ¿Conviene postular o descartarla?
* ¿Qué acciones debo realizar antes del cierre?

---

## 5. Usuarios principales

### 5.1 Dueño o gerente de pyme

Busca oportunidades para vender al Estado, pero no tiene tiempo para revisar Mercado Público todos los días. Necesita una herramienta simple que le indique qué oportunidades son relevantes y cuáles conviene priorizar.

Dolores principales:

* Falta de tiempo.
* Poco conocimiento técnico de Mercado Público.
* Miedo a perder oportunidades.
* Dificultad para interpretar bases.
* Necesidad de decidir rápido.

Funcionalidades que lo ayudan:

* Dashboard ejecutivo.
* Alertas automáticas.
* Resumen con IA.
* Scoring de oportunidad.
* Recomendación de postular/no postular.
* Calendario de vencimientos.

---

### 5.2 Ejecutivo comercial o encargado de licitaciones

Es quien revisa oportunidades, descarga bases, analiza requisitos, prepara documentos y coordina postulaciones.

Dolores principales:

* Trabajo manual repetitivo.
* Muchas bases que leer.
* Fechas difíciles de controlar.
* Documentos dispersos.
* Falta de trazabilidad.
* Poco control sobre el estado de cada oportunidad.

Funcionalidades que lo ayudan:

* Pipeline de oportunidades.
* Checklist documental.
* Estados de gestión.
* Lectura y resumen de bases.
* Extracción automática de requisitos.
* Recordatorios y alertas.
* Historial de acciones.

---

### 5.3 Analista comercial o inteligencia de negocios

Necesita estudiar precios, competidores, compradores y comportamiento del mercado público.

Dolores principales:

* Información pública difícil de analizar.
* Falta de reportes comparativos.
* Dificultad para encontrar precios históricos.
* Desconocimiento de proveedores adjudicados.
* Necesidad de detectar nichos rentables.

Funcionalidades que lo ayudan:

* Reportes de órdenes de compra.
* Análisis de proveedores.
* Análisis de compradores.
* Histórico de precios.
* Tendencias por categoría.
* Exportación a Excel/CSV.
* Paneles de inteligencia comercial.

---

### 5.4 Administrador de cuenta SaaS

Gestiona usuarios, permisos, suscripción, configuración de empresa y criterios de búsqueda.

Dolores principales:

* Necesidad de controlar accesos.
* Diferentes roles dentro de la empresa.
* Configuración de alertas por equipo.
* Control de plan contratado.

Funcionalidades que lo ayudan:

* Gestión de usuarios.
* Roles y permisos.
* Configuración de empresa.
* Configuración de alertas.
* Administración de plan.
* Auditoría de actividad.

---

## 6. Estado actual conocido del desarrollo

Claude Code debe revisar el repositorio y comparar el desarrollo actual contra este SDD. Como referencia, el estado conocido del proyecto incluye:

* Existe un hito inicial relacionado con el cliente de ChileCompra / Mercado Público.
* Se ha trabajado un `MercadoPublicoClient`.
* El cliente usa `httpx async`.
* Se consideró rate limit de aproximadamente 5 requests por segundo.
* Se integraron retries con `tenacity`.
* Se consideró cifrado con `AES-256-GCM`.
* Existen modelos usando SQLAlchemy 2.0 async.
* Existen schemas con Pydantic 2.
* Existe un worker Celery llamado o similar a `sync_listado_diario`.
* Existe endpoint `/health`.
* Existe CLI o comando similar a `test_chilecompra`.
* Se mencionó una suite de tests exitosa de 44/44.
* El siguiente paso técnico mencionado era avanzar con autenticación.

Claude Code debe validar si estos elementos siguen existiendo, si están completos, si tienen tests, si están integrados en la arquitectura real y qué brechas existen respecto al producto objetivo.

---

## 7. Alcance funcional esperado

El SaaS debe organizarse en módulos. Cada módulo debe resolver un dolor concreto del cliente.

---

## 8. Módulo: Integración con Mercado Público / ChileCompra

### Dolor que resuelve

El cliente no quiere revisar manualmente Mercado Público todos los días ni depender de búsquedas manuales. Necesita que el sistema capture oportunidades y datos relevantes de forma automática.

### Objetivo

Construir una capa robusta de integración con fuentes públicas de Mercado Público / ChileCompra para sincronizar licitaciones, órdenes de compra, compradores, proveedores, categorías y otros datos relevantes.

### Funcionalidades esperadas

* Cliente HTTP asíncrono para consumir API pública.
* Manejo de rate limiting.
* Manejo de retries ante errores temporales.
* Manejo de timeouts.
* Manejo de errores de API.
* Logs estructurados de sincronización.
* Jobs programados para sincronización diaria.
* Posibilidad de sincronización manual desde CLI o panel admin.
* Persistencia de datos normalizados en base de datos.
* Separación clara entre datos crudos y datos procesados.
* Validación de respuestas mediante schemas.
* Tests unitarios y de integración.

### Entidades sugeridas

* `Tender`
* `TenderItem`
* `Buyer`
* `Supplier`
* `PurchaseOrder`
* `TenderDocument`
* `TenderSyncLog`
* `TenderCategory`
* `TenderStatus`

### Criterios de aceptación

* El sistema puede ejecutar una sincronización diaria sin intervención manual.
* Los errores quedan registrados y no detienen completamente el sistema.
* La API externa está desacoplada del dominio interno.
* Los datos relevantes quedan disponibles para búsqueda, alertas y análisis.
* Existen tests para respuestas exitosas, errores, timeouts y reintentos.

---

## 9. Módulo: Autenticación y gestión de usuarios

### Dolor que resuelve

Las empresas necesitan trabajar en equipo, controlar accesos y separar la información por organización.

### Objetivo

Permitir que usuarios y empresas accedan de forma segura al SaaS, con roles, permisos y configuración propia.

### Funcionalidades esperadas

* Registro de usuario.
* Login.
* Logout.
* Recuperación de contraseña.
* Refresh tokens o manejo seguro de sesión.
* Roles de usuario.
* Asociación de usuarios a una empresa.
* Gestión de permisos.
* Perfil de usuario.
* Perfil de empresa.
* Middleware de autorización.
* Protección de endpoints privados.

### Roles sugeridos

* `SUPER_ADMIN`
* `COMPANY_ADMIN`
* `MANAGER`
* `ANALYST`
* `VIEWER`

### Criterios de aceptación

* Un usuario solo puede ver información de su empresa.
* Un administrador puede invitar o gestionar usuarios de su empresa.
* Los endpoints sensibles requieren autenticación.
* Las contraseñas nunca se almacenan en texto plano.
* El sistema está preparado para escalar hacia un modelo multitenant.

---

## 10. Módulo: Perfil comercial de empresa

### Dolor que resuelve

El cliente no quiere recibir cualquier licitación, sino oportunidades alineadas con lo que realmente vende.

### Objetivo

Permitir que cada empresa configure su perfil de búsqueda y criterios comerciales.

### Funcionalidades esperadas

* Configuración de rubros.
* Palabras clave principales.
* Palabras clave negativas.
* Regiones de interés.
* Monto mínimo y máximo.
* Tipos de oportunidad.
* Compradores públicos de interés.
* Categorías preferidas.
* Exclusiones.
* Nivel de riesgo aceptado.
* Configuración de frecuencia de alertas.

### Ejemplo

Una empresa TI podría configurar:

* Palabras clave: software, soporte, ciberseguridad, licencias, infraestructura, nube, desarrollo web, mesa de ayuda.
* Regiones: Metropolitana, Valparaíso, Biobío.
* Monto mínimo: $1.000.000 CLP.
* Oportunidades excluidas: aseo, alimentación, construcción, vehículos.
* Compradores preferidos: municipalidades, hospitales, universidades, servicios públicos.

### Criterios de aceptación

* El sistema puede filtrar oportunidades según el perfil de la empresa.
* El usuario puede editar criterios sin intervención técnica.
* El perfil impacta directamente en alertas, scoring y dashboard.
* Se pueden guardar múltiples criterios o búsquedas.

---

## 11. Módulo: Buscador inteligente de oportunidades

### Dolor que resuelve

Buscar licitaciones manualmente toma tiempo y muchas veces entrega resultados poco relevantes.

### Objetivo

Entregar un buscador avanzado que permita encontrar oportunidades por texto, categoría, comprador, estado, fecha, monto, región y relevancia.

### Funcionalidades esperadas

* Búsqueda por palabra clave.
* Filtros por fecha de publicación.
* Filtros por fecha de cierre.
* Filtros por estado.
* Filtros por comprador.
* Filtros por región.
* Filtros por monto estimado.
* Filtros por categoría.
* Filtros por tipo de oportunidad.
* Ordenamiento por relevancia.
* Ordenamiento por fecha de cierre.
* Ordenamiento por monto.
* Guardado de búsquedas.
* Exportación de resultados.

### Criterios de aceptación

* El usuario puede encontrar oportunidades relevantes en pocos segundos.
* El buscador respeta criterios de empresa.
* Las oportunidades muestran información resumida y accionable.
* El sistema permite marcar oportunidades como favoritas, descartadas o en análisis.

---

## 12. Módulo: Alertas automáticas

### Dolor que resuelve

Las empresas pierden oportunidades porque no revisan Mercado Público todos los días o porque se enteran tarde.

### Objetivo

Notificar automáticamente oportunidades relevantes según el perfil de la empresa.

### Funcionalidades esperadas

* Alertas por email.
* Alertas dentro de la plataforma.
* Alertas diarias.
* Alertas inmediatas para oportunidades críticas.
* Alertas por vencimiento cercano.
* Alertas por cambios de estado.
* Alertas por respuestas a preguntas.
* Alertas por adjudicación.
* Configuración de frecuencia.
* Configuración de destinatarios.

### Criterios de aceptación

* El usuario recibe oportunidades relevantes sin buscarlas manualmente.
* Las alertas no deben ser excesivas ni irrelevantes.
* Cada alerta debe explicar por qué la oportunidad fue seleccionada.
* El usuario puede activar, pausar o modificar alertas.

---

## 13. Módulo: Resumen de licitaciones con IA

### Dolor que resuelve

Leer bases administrativas y técnicas puede tomar horas. Muchas empresas descartan oportunidades por falta de tiempo o postulan sin entender completamente los requisitos.

### Objetivo

Usar inteligencia artificial para resumir documentos, extraer requisitos y entregar una lectura ejecutiva de cada oportunidad.

### Funcionalidades esperadas

* Carga o descarga de documentos de licitación.
* Extracción de texto desde PDF, Word u otros formatos soportados.
* Resumen ejecutivo.
* Resumen técnico.
* Resumen administrativo.
* Identificación de fechas clave.
* Identificación de documentos solicitados.
* Identificación de garantías.
* Identificación de criterios de evaluación.
* Identificación de requisitos excluyentes.
* Identificación de riesgos.
* Preguntas y respuestas sobre las bases.
* Chat contextual sobre la licitación.

### Ejemplos de preguntas que el usuario debería poder hacer

* ¿Cuál es el objeto de esta licitación?
* ¿Qué documentos debo presentar?
* ¿Hay garantía de seriedad de la oferta?
* ¿Cuál es la fecha de cierre?
* ¿Cuáles son los criterios de evaluación?
* ¿Hay requisitos técnicos excluyentes?
* ¿Qué riesgos tiene esta licitación?
* ¿Mi empresa cumple con lo solicitado?
* ¿Conviene postular?

### Criterios de aceptación

* El resumen debe ser claro, útil y accionable.
* La IA debe indicar cuando no puede determinar algo con certeza.
* Los resultados deben estar vinculados al documento fuente cuando sea posible.
* El usuario debe ahorrar tiempo real en la lectura de bases.
* La IA no debe reemplazar la decisión final, sino apoyar el análisis.

---

## 14. Módulo: Scoring de oportunidad

### Dolor que resuelve

El cliente no sabe qué licitaciones priorizar. Puede perder tiempo en oportunidades poco rentables o con baja probabilidad de éxito.

### Objetivo

Calcular un puntaje de oportunidad para cada licitación, ayudando a decidir si conviene postular, analizar o descartar.

### Variables sugeridas para el scoring

* Coincidencia con palabras clave de la empresa.
* Coincidencia con rubro o categoría.
* Monto estimado.
* Tiempo restante para postular.
* Complejidad documental.
* Cantidad de requisitos excluyentes.
* Historial del comprador.
* Competencia esperada.
* Experiencia previa de la empresa.
* Región.
* Tipo de producto o servicio.
* Riesgo contractual.
* Margen comercial estimado.
* Probabilidad de cumplimiento.

### Resultado esperado

El sistema debería clasificar oportunidades en niveles como:

* Alta prioridad.
* Prioridad media.
* Baja prioridad.
* Descartar.
* Requiere revisión manual.

### Criterios de aceptación

* Cada oportunidad tiene un puntaje explicable.
* El usuario puede entender por qué una licitación fue recomendada.
* El scoring debe ser ajustable a futuro.
* El scoring no debe ser una caja negra.
* El sistema debe permitir recalcular el puntaje cuando cambie el perfil de empresa.

---

## 15. Módulo: Pipeline de gestión de oportunidades

### Dolor que resuelve

Las empresas gestionan licitaciones con planillas, correos o memoria. Esto genera desorden, pérdida de fechas y poca trazabilidad.

### Objetivo

Permitir que cada oportunidad avance por un flujo de gestión comercial y operativo.

### Estados sugeridos

* Nueva.
* Relevante.
* En análisis.
* Pendiente de documentos.
* En preparación.
* Lista para postular.
* Postulada.
* En evaluación.
* Adjudicada.
* Perdida.
* Descartada.

### Funcionalidades esperadas

* Cambiar estado de oportunidad.
* Asignar responsable.
* Agregar notas internas.
* Agregar tareas.
* Agregar documentos.
* Agregar checklist.
* Ver historial de cambios.
* Registrar decisión de postular o descartar.
* Registrar motivo de descarte.
* Registrar resultado final.

### Criterios de aceptación

* El usuario puede saber en qué etapa está cada oportunidad.
* El sistema permite priorizar trabajo diario.
* Existen responsables y fechas claras.
* Se evita depender de planillas externas.

---

## 16. Módulo: Checklist documental

### Dolor que resuelve

Las postulaciones fallan muchas veces por documentos incompletos, vencidos o mal preparados.

### Objetivo

Crear checklist automático y manual para controlar los documentos requeridos por cada licitación.

### Funcionalidades esperadas

* Checklist generado desde IA según bases.
* Checklist editable por usuario.
* Estado por documento.
* Responsable por documento.
* Fecha límite interna.
* Adjuntar archivo.
* Comentarios.
* Marcar como completado.
* Alertas por documentos pendientes.

### Estados sugeridos

* Pendiente.
* En preparación.
* En revisión.
* Completado.
* No aplica.
* Riesgo.

### Criterios de aceptación

* Cada licitación puede tener su propio checklist.
* El usuario puede controlar documentos críticos antes del cierre.
* El sistema ayuda a evitar postulaciones incompletas.
* Los documentos se relacionan con la oportunidad correspondiente.

---

## 17. Módulo: Calendario y vencimientos

### Dolor que resuelve

Las empresas pierden oportunidades por no controlar fechas de preguntas, respuestas, cierre, visitas técnicas o adjudicación.

### Objetivo

Centralizar fechas importantes y generar recordatorios.

### Fechas relevantes

* Fecha de publicación.
* Fecha de inicio de preguntas.
* Fecha límite de preguntas.
* Fecha de respuestas.
* Fecha de cierre.
* Fecha de apertura técnica.
* Fecha de apertura económica.
* Fecha estimada de adjudicación.
* Fechas internas definidas por el equipo.

### Funcionalidades esperadas

* Calendario mensual/semanal.
* Vista de próximos vencimientos.
* Recordatorios automáticos.
* Alertas por oportunidades críticas.
* Sincronización futura con Google Calendar u Outlook.
* Fechas internas de preparación.

### Criterios de aceptación

* El usuario visualiza claramente qué vence hoy, esta semana y este mes.
* El sistema alerta antes de fechas críticas.
* Las fechas se relacionan con oportunidades específicas.

---

## 18. Módulo: Análisis de competidores

### Dolor que resuelve

El cliente no sabe contra quién compite ni qué proveedores suelen ganar.

### Objetivo

Mostrar información histórica sobre proveedores adjudicados, frecuencia de adjudicación, montos, categorías y compradores.

### Funcionalidades esperadas

* Buscar proveedor.
* Ver adjudicaciones históricas.
* Ver montos adjudicados.
* Ver compradores frecuentes.
* Ver categorías donde participa.
* Comparar proveedores.
* Detectar proveedores dominantes por rubro.
* Ver participación por región o tipo de compra.

### Criterios de aceptación

* El usuario puede identificar competidores relevantes.
* El sistema permite comprender el comportamiento del mercado.
* La información ayuda a tomar decisiones comerciales y de precio.

---

## 19. Módulo: Histórico de precios y órdenes de compra

### Dolor que resuelve

Las empresas no siempre saben qué precio ofertar. Esto puede hacer que postulen caro y pierdan, o demasiado barato y reduzcan margen.

### Objetivo

Entregar referencias históricas de precios, órdenes de compra y adjudicaciones para apoyar decisiones comerciales.

### Funcionalidades esperadas

* Buscar productos o servicios similares.
* Ver precios históricos.
* Ver órdenes de compra asociadas.
* Ver compradores.
* Ver proveedores adjudicados.
* Ver montos unitarios y totales.
* Ver tendencias.
* Exportar información.
* Comparar por período.

### Criterios de aceptación

* El usuario puede encontrar referencias de precio antes de postular.
* El sistema ayuda a mejorar la competitividad.
* La información debe estar presentada de forma clara y filtrable.

---

## 20. Módulo: Recomendador de postulación

### Dolor que resuelve

El cliente necesita una recomendación ejecutiva rápida para decidir si invierte tiempo en una oportunidad.

### Objetivo

Combinar scoring, requisitos, historial, documentos, precios y perfil de empresa para entregar una recomendación.

### Recomendaciones posibles

* Postular.
* Analizar con prioridad.
* Postular solo si se cumplen documentos críticos.
* Descartar por bajo calce.
* Descartar por poco tiempo.
* Descartar por alto riesgo.
* Revisar manualmente.

### La recomendación debe explicar

* Motivos a favor.
* Motivos en contra.
* Riesgos detectados.
* Documentos críticos.
* Tiempo restante.
* Nivel de calce con la empresa.
* Posibles competidores.
* Referencia de precios si existe.

### Criterios de aceptación

* La recomendación debe ser entendible para un usuario no técnico.
* Debe estar basada en datos disponibles.
* Debe permitir decisión rápida.
* Debe dejar claro que la decisión final es del usuario.

---

## 21. Módulo: Dashboard ejecutivo

### Dolor que resuelve

El cliente necesita una visión rápida del estado de sus oportunidades sin entrar a revisar todo manualmente.

### Objetivo

Entregar una vista ejecutiva con indicadores clave.

### Indicadores sugeridos

* Oportunidades nuevas.
* Oportunidades de alta prioridad.
* Oportunidades por vencer.
* Oportunidades en análisis.
* Oportunidades postuladas.
* Oportunidades adjudicadas.
* Oportunidades perdidas.
* Monto potencial total.
* Monto potencial por estado.
* Tasa de postulación.
* Tasa de adjudicación.
* Principales compradores.
* Principales categorías.

### Criterios de aceptación

* El dashboard debe mostrar el estado del negocio en pocos segundos.
* Los indicadores deben ser filtrables por período.
* Los datos deben estar conectados al pipeline real de oportunidades.

---

## 22. Módulo: Reportes y exportación

### Dolor que resuelve

Las empresas necesitan reportar oportunidades, resultados y análisis a gerencia o equipos internos.

### Objetivo

Permitir exportar información y generar reportes comerciales.

### Funcionalidades esperadas

* Exportar oportunidades a Excel/CSV.
* Exportar histórico de precios.
* Exportar competidores.
* Exportar pipeline.
* Reporte mensual de oportunidades.
* Reporte de licitaciones postuladas.
* Reporte de adjudicaciones.
* Reporte de motivos de descarte.
* Reporte de oportunidades perdidas.

### Criterios de aceptación

* El usuario puede descargar información sin apoyo técnico.
* Los reportes deben ser útiles para toma de decisiones.
* La exportación debe respetar permisos y empresa.

---

## 23. Módulo: Administración SaaS

### Dolor que resuelve

El negocio necesita operar como SaaS, controlar clientes, planes, usuarios y uso de la plataforma.

### Objetivo

Crear una base administrativa para gestión comercial del producto.

### Funcionalidades esperadas

* Gestión de empresas cliente.
* Gestión de usuarios.
* Gestión de planes.
* Activar/desactivar cuenta.
* Ver uso de API o consumo.
* Ver número de oportunidades procesadas.
* Ver número de documentos analizados con IA.
* Ver logs de sincronización.
* Ver errores.
* Configurar límites por plan.
* Panel de superadministrador.

### Planes sugeridos

#### Plan Básico

* Búsqueda de oportunidades.
* Alertas simples.
* Dashboard básico.
* Guardado de oportunidades.
* Filtros principales.

#### Plan Intermedio

* Todo lo del plan básico.
* Perfil comercial avanzado.
* Alertas configurables.
* Pipeline de oportunidades.
* Checklist documental.
* Calendario de vencimientos.
* Exportaciones básicas.

#### Plan PRO

* Todo lo de planes anteriores.
* Resumen de bases con IA.
* Chat con documentos.
* Scoring de oportunidad.
* Recomendador de postulación.
* Análisis de competidores.
* Histórico de precios.
* Reportes avanzados.
* Automatizaciones.
* Mayor cantidad de usuarios.
* Mayor volumen de oportunidades procesadas.
* Soporte prioritario.

#### Plan Empresa

* Todo lo del Plan PRO.
* Multiempresa o múltiples unidades de negocio.
* Roles avanzados.
* Integraciones.
* API privada.
* Reportes personalizados.
* Acompañamiento especializado.
* SLA.
* Configuración a medida.

### Criterios de aceptación

* El SaaS puede limitar funcionalidades según plan.
* El administrador puede gestionar empresas y usuarios.
* El sistema debe estar preparado para monetización por suscripción.

---

## 24. Arquitectura técnica esperada

La arquitectura debe ser modular, escalable y separada por responsabilidades.

### Componentes sugeridos

* Backend API.
* Frontend web.
* Base de datos relacional.
* Workers para procesos asíncronos.
* Cola de tareas.
* Servicio de integración con Mercado Público.
* Servicio de IA.
* Servicio de notificaciones.
* Servicio de autenticación.
* Servicio de reportes.
* Almacenamiento de documentos.
* Sistema de logs y monitoreo.

### Separación lógica sugerida

* `auth`
* `companies`
* `users`
* `tenders`
* `marketplace`
* `sync`
* `alerts`
* `ai_analysis`
* `scoring`
* `documents`
* `pipeline`
* `reports`
* `admin`
* `billing`

---

## 25. Backend esperado

El backend debe exponer una API clara, segura y documentada.

### Requerimientos

* Endpoints REST o arquitectura compatible.
* Validación con schemas.
* Manejo consistente de errores.
* Autenticación y autorización.
* Paginación.
* Filtros.
* Ordenamiento.
* Logs.
* Tests.
* Documentación OpenAPI/Swagger si aplica.
* Separación entre routers, services, repositories y models.

### Endpoints sugeridos

#### Health

* `GET /health`

#### Auth

* `POST /auth/register`
* `POST /auth/login`
* `POST /auth/logout`
* `POST /auth/refresh`
* `POST /auth/forgot-password`
* `POST /auth/reset-password`

#### Companies

* `GET /companies/me`
* `PATCH /companies/me`
* `GET /companies/me/profile`
* `PATCH /companies/me/profile`

#### Users

* `GET /users`
* `POST /users/invite`
* `PATCH /users/{id}`
* `DELETE /users/{id}`

#### Tenders

* `GET /tenders`
* `GET /tenders/{id}`
* `POST /tenders/{id}/favorite`
* `POST /tenders/{id}/discard`
* `POST /tenders/{id}/assign`
* `PATCH /tenders/{id}/status`

#### Search

* `GET /search/tenders`
* `POST /search/saved`
* `GET /search/saved`

#### Alerts

* `GET /alerts`
* `POST /alerts/config`
* `PATCH /alerts/config/{id}`
* `DELETE /alerts/config/{id}`

#### AI Analysis

* `POST /tenders/{id}/analyze`
* `GET /tenders/{id}/analysis`
* `POST /tenders/{id}/chat`
* `GET /tenders/{id}/requirements`
* `GET /tenders/{id}/risks`

#### Scoring

* `POST /tenders/{id}/score`
* `GET /tenders/{id}/score`
* `POST /tenders/bulk-score`

#### Pipeline

* `GET /opportunities`
* `POST /opportunities`
* `GET /opportunities/{id}`
* `PATCH /opportunities/{id}`
* `POST /opportunities/{id}/notes`
* `POST /opportunities/{id}/tasks`

#### Documents

* `GET /opportunities/{id}/checklist`
* `POST /opportunities/{id}/checklist`
* `PATCH /checklist-items/{id}`
* `POST /checklist-items/{id}/upload`

#### Reports

* `GET /reports/dashboard`
* `GET /reports/opportunities`
* `GET /reports/prices`
* `GET /reports/competitors`
* `GET /reports/export`

#### Admin

* `GET /admin/companies`
* `GET /admin/users`
* `GET /admin/sync-logs`
* `GET /admin/usage`
* `PATCH /admin/companies/{id}/plan`

---

## 26. Frontend esperado

El frontend debe ser simple, moderno y orientado a productividad.

### Vistas principales

* Login.
* Registro.
* Recuperar contraseña.
* Dashboard.
* Buscador de oportunidades.
* Detalle de licitación.
* Análisis con IA.
* Chat con bases.
* Pipeline de oportunidades.
* Checklist documental.
* Calendario.
* Alertas.
* Reportes.
* Configuración de empresa.
* Gestión de usuarios.
* Administración SaaS.

### Principios de UX

* El usuario debe entender rápidamente qué oportunidades requieren atención.
* Las fechas críticas deben ser visibles.
* El scoring debe ser fácil de interpretar.
* La IA debe entregar respuestas accionables.
* El dashboard debe priorizar claridad sobre exceso de gráficos.
* La plataforma debe reducir trabajo, no agregar complejidad.
* Las acciones principales deben estar a uno o dos clics.

---

## 27. Modelo de datos sugerido

### Company

Representa una empresa cliente del SaaS.

Campos sugeridos:

* `id`
* `name`
* `rut`
* `industry`
* `plan`
* `status`
* `created_at`
* `updated_at`

---

### User

Representa un usuario de una empresa.

Campos sugeridos:

* `id`
* `company_id`
* `name`
* `email`
* `password_hash`
* `role`
* `status`
* `last_login_at`
* `created_at`
* `updated_at`

---

### CompanyProfile

Representa el perfil comercial usado para filtrar y recomendar oportunidades.

Campos sugeridos:

* `id`
* `company_id`
* `keywords`
* `negative_keywords`
* `categories`
* `regions`
* `min_amount`
* `max_amount`
* `preferred_buyers`
* `excluded_buyers`
* `risk_preference`
* `alert_frequency`
* `created_at`
* `updated_at`

---

### Tender

Representa una licitación u oportunidad sincronizada desde Mercado Público.

Campos sugeridos:

* `id`
* `external_id`
* `code`
* `name`
* `description`
* `status`
* `buyer_id`
* `published_at`
* `closing_at`
* `estimated_amount`
* `currency`
* `region`
* `category`
* `source`
* `raw_data`
* `created_at`
* `updated_at`

---

### Buyer

Representa un organismo comprador.

Campos sugeridos:

* `id`
* `external_id`
* `name`
* `rut`
* `region`
* `sector`
* `created_at`
* `updated_at`

---

### Opportunity

Representa una licitación gestionada por una empresa dentro del SaaS.

Campos sugeridos:

* `id`
* `company_id`
* `tender_id`
* `assigned_user_id`
* `status`
* `priority`
* `score`
* `decision`
* `decision_reason`
* `internal_deadline`
* `created_at`
* `updated_at`

---

### AIAnalysis

Representa el análisis generado por IA para una licitación.

Campos sugeridos:

* `id`
* `tender_id`
* `company_id`
* `summary`
* `technical_summary`
* `administrative_summary`
* `requirements`
* `documents_required`
* `evaluation_criteria`
* `risks`
* `recommendation`
* `model_used`
* `created_at`
* `updated_at`

---

### OpportunityScore

Representa el puntaje de una oportunidad.

Campos sugeridos:

* `id`
* `opportunity_id`
* `total_score`
* `relevance_score`
* `amount_score`
* `deadline_score`
* `risk_score`
* `competition_score`
* `explanation`
* `created_at`
* `updated_at`

---

### ChecklistItem

Representa un documento o tarea necesaria para postular.

Campos sugeridos:

* `id`
* `opportunity_id`
* `title`
* `description`
* `status`
* `responsible_user_id`
* `due_date`
* `file_url`
* `created_at`
* `updated_at`

---

### Alert

Representa una alerta generada para una empresa o usuario.

Campos sugeridos:

* `id`
* `company_id`
* `user_id`
* `tender_id`
* `type`
* `title`
* `message`
* `status`
* `sent_at`
* `created_at`

---

### SyncLog

Representa logs de sincronización con Mercado Público.

Campos sugeridos:

* `id`
* `source`
* `status`
* `started_at`
* `finished_at`
* `records_processed`
* `records_created`
* `records_updated`
* `error_message`
* `created_at`

---

## 28. IA y análisis documental

El módulo de IA debe ser tratado como una capa de apoyo a la decisión. No debe reemplazar la revisión humana ni asumir información que no esté en los documentos.

### Reglas importantes

* La IA debe indicar incertidumbre cuando corresponda.
* La IA debe evitar respuestas inventadas.
* La IA debe trabajar con documentos fuente.
* Se debe guardar trazabilidad del análisis.
* Se debe evitar reprocesar innecesariamente el mismo documento.
* El análisis debe ser estructurado para uso posterior en scoring, checklist y reportes.

### Salida esperada del análisis IA

La salida ideal debe tener una estructura similar a:

* Resumen ejecutivo.
* Objeto de la licitación.
* Requisitos técnicos.
* Requisitos administrativos.
* Documentos obligatorios.
* Fechas clave.
* Garantías.
* Criterios de evaluación.
* Riesgos.
* Preguntas sugeridas.
* Recomendación preliminar.
* Nivel de confianza.

---

## 29. Seguridad

El SaaS debe manejar información sensible de empresas, usuarios, análisis internos y documentos.

### Requerimientos

* Contraseñas hasheadas.
* Tokens seguros.
* Cifrado de secretos.
* Variables de entorno para credenciales.
* Separación de datos por empresa.
* Validación de permisos en backend.
* Sanitización de entradas.
* Protección contra acceso cruzado entre tenants.
* Logs sin información sensible.
* Manejo seguro de documentos.
* Auditoría de acciones relevantes.

### Consideraciones

Si ya existe implementación de `AES-256-GCM`, Claude Code debe revisar:

* Dónde se usa.
* Qué datos cifra.
* Cómo se gestiona la llave.
* Si la llave viene desde variable de entorno.
* Si existen tests.
* Si hay riesgo de guardar secretos en texto plano.

---

## 30. Jobs y procesos asíncronos

El sistema debe usar workers para tareas pesadas o programadas.

### Jobs sugeridos

* Sincronización diaria de licitaciones.
* Sincronización de órdenes de compra.
* Sincronización de compradores.
* Procesamiento de documentos.
* Análisis IA.
* Cálculo de scoring.
* Envío de alertas.
* Generación de reportes.
* Limpieza de datos antiguos.
* Reintentos de tareas fallidas.

### Criterios de aceptación

* Los jobs deben ser idempotentes cuando sea posible.
* Los errores deben quedar registrados.
* Las tareas pesadas no deben bloquear la API.
* Debe existir trazabilidad del estado de cada proceso.

---

## 31. Testing esperado

Claude Code debe revisar el nivel de pruebas existente y detectar brechas.

### Tests esperados

* Tests unitarios para cliente Mercado Público.
* Tests de rate limit.
* Tests de retries.
* Tests de errores externos.
* Tests de schemas.
* Tests de modelos.
* Tests de endpoints.
* Tests de autenticación.
* Tests de permisos por empresa.
* Tests de scoring.
* Tests de alertas.
* Tests de jobs Celery.
* Tests de análisis IA con mocks.
* Tests de integración principales.

### Criterios de aceptación

* Los tests deben poder ejecutarse localmente.
* Deben existir fixtures o factories.
* No deben depender siempre de la API real.
* Las integraciones externas deben poder mockearse.
* La cobertura debe priorizar lógica crítica de negocio.

---

## 32. Observabilidad y logs

### Dolor que resuelve

Cuando una sincronización falla o una alerta no se envía, el equipo necesita saber qué ocurrió.

### Requerimientos

* Logs estructurados.
* Logs de sincronización.
* Logs de errores de API externa.
* Logs de jobs.
* Logs de envío de alertas.
* Métricas básicas.
* Health check.
* Registro de duración de procesos.
* Registro de cantidad de registros procesados.

### Criterios de aceptación

* Un administrador puede saber cuándo fue la última sincronización exitosa.
* Los errores deben ser diagnosticables.
* El endpoint `/health` debe indicar estado básico del sistema.

---

## 33. Criterios no funcionales

### Rendimiento

* La búsqueda debe ser rápida incluso con muchas licitaciones.
* Los endpoints deben paginar resultados.
* Las tareas pesadas deben ir a workers.
* Se deben usar índices en base de datos para campos de búsqueda frecuentes.

### Escalabilidad

* El sistema debe poder soportar múltiples empresas.
* Debe permitir crecimiento en volumen de licitaciones y documentos.
* Debe separar procesos de API y workers.

### Mantenibilidad

* Código organizado por módulos.
* Services con lógica de negocio.
* Repositories o capa de acceso a datos.
* Schemas claros.
* Tests.
* Documentación interna.
* Nombres consistentes.

### Seguridad

* Separación de tenants.
* Permisos por rol.
* Protección de endpoints.
* Cifrado cuando corresponda.
* No exponer secretos.

### Usabilidad

* Interfaz clara.
* Priorización visual.
* Menos pasos manuales.
* Información accionable.
* Lenguaje simple para usuarios no técnicos.

---

## 34. Comparación que debe realizar Claude Code

Claude Code debe leer este documento y comparar el repositorio actual contra el producto esperado.

La comparación debe responder:

1. ¿Qué módulos ya existen?
2. ¿Qué módulos están parcialmente implementados?
3. ¿Qué módulos faltan completamente?
4. ¿Qué código está bien estructurado?
5. ¿Qué código debería refactorizarse?
6. ¿Qué endpoints existen y cuáles faltan?
7. ¿Qué modelos existen y cuáles faltan?
8. ¿Qué tests existen y cuáles faltan?
9. ¿Qué funcionalidades actuales resuelven dolores reales del cliente?
10. ¿Qué funcionalidades son técnicas pero aún no entregan valor visible al usuario?
11. ¿Qué brechas impiden tener un MVP usable?
12. ¿Cuál debería ser el próximo sprint?

---

## 35. Prioridad de desarrollo sugerida

### Sprint 1 – Base técnica e integración Mercado Público

Objetivo: tener integración robusta con Mercado Público.

Incluye:

* Cliente API.
* Rate limit.
* Retries.
* Modelos base.
* Sincronización diaria.
* Logs.
* Health check.
* Tests.

Estado conocido: aparentemente avanzado o completado parcialmente. Claude debe validar.

---

### Sprint 2 – Autenticación y empresas

Objetivo: permitir uso real por empresas.

Incluye:

* Auth.
* Usuarios.
* Roles.
* Empresas.
* Perfil comercial.
* Protección de endpoints.
* Separación por empresa.

---

### Sprint 3 – Buscador y dashboard

Objetivo: que el usuario pueda ver oportunidades.

Incluye:

* Listado de licitaciones.
* Buscador.
* Filtros.
* Dashboard inicial.
* Guardado de oportunidades.
* Favoritos.
* Descartes.

---

### Sprint 4 – Alertas y pipeline

Objetivo: resolver pérdida de oportunidades y desorden operativo.

Incluye:

* Alertas.
* Estados de oportunidad.
* Responsables.
* Notas.
* Tareas.
* Calendario.
* Vencimientos.

---

### Sprint 5 – IA documental

Objetivo: reducir tiempo de análisis de bases.

Incluye:

* Procesamiento de documentos.
* Resumen IA.
* Extracción de requisitos.
* Checklist automático.
* Chat con bases.
* Riesgos.

---

### Sprint 6 – Scoring y recomendación

Objetivo: ayudar a decidir si conviene postular.

Incluye:

* Scoring.
* Explicación del puntaje.
* Recomendador.
* Clasificación por prioridad.
* Integración con perfil de empresa.

---

### Sprint 7 – Inteligencia comercial

Objetivo: entregar análisis avanzado de mercado.

Incluye:

* Competidores.
* Histórico de precios.
* Órdenes de compra.
* Compradores.
* Reportes.
* Exportaciones.

---

## 36. MVP recomendado

El MVP no debe intentar construir todo desde el inicio. La primera versión útil debe enfocarse en resolver tres dolores principales:

1. Encontrar oportunidades relevantes.
2. Entender rápidamente si conviene analizarlas.
3. No perder fechas importantes.

### MVP mínimo

* Login.
* Empresa.
* Perfil comercial.
* Sincronización de licitaciones.
* Buscador.
* Dashboard simple.
* Alertas básicas.
* Guardar oportunidad.
* Cambiar estado.
* Fecha de cierre visible.
* Resumen básico de oportunidad.
* Scoring inicial simple.
* Checklist manual.

### MVP ideal

* Todo lo anterior.
* Resumen IA de bases.
* Extracción de documentos requeridos.
* Checklist automático.
* Recomendación de postulación.
* Alertas por vencimiento.
* Reporte simple de oportunidades.

---

## 37. Definición de éxito del producto

El producto será exitoso si logra que una empresa:

* Encuentre más oportunidades relevantes.
* Dedique menos tiempo a revisar Mercado Público.
* Entienda más rápido las bases.
* Priorice mejor sus postulaciones.
* Evite perder fechas críticas.
* Mejore su orden interno.
* Tome decisiones con datos.
* Aumente sus postulaciones bien preparadas.
* Mejore sus probabilidades de adjudicación.

El valor del SaaS no está solamente en mostrar datos, sino en convertir datos públicos en decisiones comerciales accionables.

---

## 38. Instrucción final para Claude Code

Claude Code debe usar este documento como referencia funcional y técnica del producto esperado.

La tarea principal es comparar el estado actual del código contra este SDD y generar un diagnóstico claro con:

* Funcionalidades implementadas.
* Funcionalidades incompletas.
* Funcionalidades faltantes.
* Problemas técnicos.
* Riesgos de arquitectura.
* Recomendaciones de refactor.
* Próximas tareas priorizadas.
* Propuesta de siguiente sprint.
* Archivos específicos que deben modificarse o crearse.

Claude Code debe priorizar siempre las funcionalidades que resuelvan dolores reales del cliente antes que mejoras técnicas secundarias.

El orden de prioridad debe ser:

1. Seguridad y autenticación.
2. Separación por empresa.
3. Sincronización confiable de datos.
4. Búsqueda de oportunidades.
5. Alertas.
6. Pipeline.
7. IA para análisis de bases.
8. Scoring.
9. Inteligencia comercial.
10. Reportes avanzados.

El desarrollo debe avanzar hacia un SaaS usable, comercializable y escalable, enfocado en ayudar a empresas chilenas a vender mejor al Estado mediante Mercado Público.
