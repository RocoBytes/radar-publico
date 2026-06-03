# Product

## Register

product

## Users

Empresas chilenas proveedoras del Estado: equipos comerciales, de operaciones y licitaciones que revisan Mercado Público diariamente. Usuarios que trabajan en oficina o desde notebook, horario laboral, contexto de alta presión por plazos. Su trabajo depende de no perderse una licitación relevante y de postular a tiempo.

## Product Purpose

SaaS B2B de inteligencia comercial sobre Mercado Público de Chile. Permite a proveedores del Estado detectar licitaciones relevantes, hacer seguimiento en un pipeline propio, y anticipar oportunidades futuras. El diferenciador central: tres horizontes de tiempo (pasado, presente, futuro) y filtrado multi-capa (UNSPSC + texto + semántica con embeddings).

## Brand Personality

Preciso, confiable, eficiente. Como Bloomberg para licitaciones chilenas: la información es densa, estructurada y accionable. No hay espacio para decoración que no sea funcional.

## Anti-references

- LicitaLAB, LicitaPyme: interfaces anticuadas y saturadas de información sin jerarquía
- SaaS cream genérico (#F5F5F5 + Inter, hero-metric con gradiente azul)
- Dashboards con cards idénticas repetidas en grid sin variación
- Interfaces que priorizan lo visual sobre la densidad de datos

## Design Principles

1. **Densidad útil sobre decoración**: Los usuarios necesitan ver mucha información de un vistazo. La UI debe maximizar la cantidad de datos legibles en pantalla, no la cantidad de espacio vacío.
2. **La urgencia siempre visible**: Las fechas de cierre son el corazón del negocio. Todo lo que esté próximo a vencer debe comunicarlo visualmente con claridad inmediata.
3. **Confianza por precisión**: La plataforma toca dinero real y plazos legales. Nada debe parecer aproximado, decorativo o ambiguo.
4. **Un flujo, una acción primaria**: Cada pantalla tiene una tarea central. La jerarquía visual refuerza eso; nunca compite.
5. **El sistema sobre el override**: Usar los tokens del design system. Hardcodear valores crea drift que erosiona la coherencia.

## Accessibility & Inclusion

WCAG AA mínimo. Soporte para navegación por teclado en todas las tablas e interacciones. Nunca depender solo del color para comunicar estado urgente (siempre acompañar con texto o icono). Respetar `prefers-reduced-motion`.
