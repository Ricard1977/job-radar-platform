# Job Radar — Product Backlog / TODO

Este fichero centraliza los incrementos pendientes del producto para no perder ideas durante el desarrollo Agile.

## Prioridad inmediata

- [ ] Persistir las acciones rápidas del frontend en SQLite en lugar de `localStorage`.
- [ ] UX simplificada: valoración humana únicamente `Me interesa` / `No me interesa`.
- [ ] Candidatura simplificada: un único estado accionable `He aplicado` y fecha de aplicación.
- [ ] Mantener en la tarjeta, fuera de la ficha detallada, los accesos rápidos `Me interesa`, `No me interesa` y `He aplicado`.
- [ ] Filtros humanos simples: `Todas` / `Me interesa` / `He aplicado`; combinables con filtros de encaje IA.
- [ ] Cuando una oferta se marque `No me interesa`, mostrar acción `Eliminar`.
- [ ] Al confirmar `Eliminar`, retirar la oferta activa de la BBDD principal conservando en una tabla de ofertas tratadas los identificadores y metadatos mínimos necesarios para deduplicación y para impedir su reaparición.
- [ ] Diseñar tabla `processed_jobs` / `treated_jobs`: Job Radar ID, IDs externos por fuente, fuente, URL/huella de deduplicación, fecha, decisión humana y los datos mínimos necesarios para aprendizaje y bloqueo de reingesta.
- [ ] El borrado no debe destruir señales útiles para learning: conservar la valoración `No me interesa` y referencia a la evaluación IA antes de purgar datos innecesarios.
- [ ] Completar Frontend V1 y revisar UX/diseño visual después de uso real.
- [ ] Continuar generando resumen y análisis en castellano conservando la descripción original.

## Learning / calibración

- [ ] Mantener independientes `USER_INTEREST` y `APPLICATION_STATUS`: una oferta puede interesar y no haberse aplicado, o haberse aplicado aunque el interés posterior cambie.
- [ ] Cruzar `Me interesa` / `No me interesa` y `He aplicado` con score, decisión y dimensiones de `AI_EVALUATIONS`.
- [ ] Detectar patrones de preferencias y comportamiento antes de modificar criterios automáticamente.
- [ ] Crear proceso de calibración versionado (`candidate_profile_v1`, criterios v1, etc.) y conservar trazabilidad de qué versión evaluó cada oferta.
- [ ] Recuperar el módulo/entrevista pendiente para extraer criterios profesionales más profundos y combinar sus resultados con el comportamiento real.

## CV / ATS / aplicación

- [ ] Crear, en una fase posterior, un módulo Oferta ↔ CV cuando una posición vaya a ser aplicada.
- [ ] Analizar requisitos, keywords y posibles gaps ATS de la oferta frente al CV.
- [ ] Proponer adaptaciones del CV específicas para la posición sin inventar experiencia ni competencias.
- [ ] Investigar herramientas/ideas tipo Kickresume como referencia funcional para ATS y adaptación de CV, priorizando una solución propia y gratuita cuando sea posible.

## Nuevas fuentes de ofertas

Objetivo: investigar cuáles aportan ofertas relevantes para un perfil senior de Project Management + Engineering + Automation/OT + Critical Infrastructure/Data Centers, y cuáles permiten integración automática, fiable y gratuita o sin coste obligatorio.

- [ ] LinkedIn — mantener como fuente principal actual y mejorar el conector.
- [ ] Remote OK (`remoteok.io`).
- [ ] We Work Remotely (`weworkremotely.com`).
- [ ] Remotive (`remotive.com`).
- [ ] JustRemote (`justremote.com`).
- [ ] Working Nomads (`workingnomads.com`).
- [ ] FlexJobs (`flexjobs.com`) — comprobar limitaciones por acceso de pago antes de considerar integración.
- [ ] Virtual Vocations (`virtualvocations.com`).
- [ ] SkipTheDrive (`skipthedrive.com`).
- [ ] Hired (`hired.com`) — estudiar el modelo inverso en el que las empresas contactan al candidato.
- [ ] Wellfound / antiguo AngelList Talent (`angel.co` en la referencia recibida) — revisar fuente actual y utilidad para posiciones senior/startups.
- [ ] Toptal (`toptal.com`) — valorar por separado por su orientación freelance y proceso de admisión.
- [ ] Upwork (`upwork.com`) — valorar por separado por su orientación freelance/proyectos.

Para cada fuente candidata evaluar: volumen de puestos relevantes, geografía, seniority, calidad, presencia de engineering/automation/data center/OT, búsqueda sin login, disponibilidad de RSS/API/feed, restricciones técnicas y legales, coste, facilidad de extracción, identificador externo estable y capacidad de deduplicar la misma oferta encontrada en varias fuentes.

## Arquitectura multi-fuente

- [ ] Utilizar `sources` + `job_sources.external_job_id` para incorporar nuevos conectores sin duplicar `jobs`.
- [ ] Mejorar deduplicación cross-source para relacionar la misma vacante encontrada en LinkedIn y otros portales con un único Job Radar ID.
- [ ] Conservar todas las fuentes/orígenes de una oferta y permitir verlas desde la ficha.
- [ ] Consultar la tabla de ofertas tratadas durante la ingesta para bloquear ofertas previamente eliminadas aunque vuelvan a aparecer en una fuente.

## Seguimiento de candidaturas — fase posterior

- [ ] Cuando el MVP esté estabilizado, valorar evolución de `He aplicado` a pipeline: en proceso / entrevista / descartada por empresa / oferta recibida / cerrada-retirada.
- [ ] Registrar contactos, próxima acción y notas cuando aporten valor.
- [ ] Crear métricas: ofertas relevantes, aplicaciones, entrevistas y conversiones.

## Pendientes aparcados

- [ ] Revisar/activar estrategia de búsqueda remota cuando el producto base esté estabilizado.
- [ ] Seguir refinando criterios y filtros con datos reales en lugar de intentar cerrarlos teóricamente antes de usar el producto.
