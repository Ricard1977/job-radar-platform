# Job Radar — Product Backlog / TODO

Este fichero centraliza los incrementos pendientes del producto para no perder ideas durante el desarrollo Agile.

## Nueva navegación principal / estructura de producto

- [ ] Crear un menú principal persistente de Job Radar con acceso a las áreas funcionales del producto.

### 1. Mi perfil de trabajo

- [ ] Crear pantalla `Mi perfil de trabajo`.
- [ ] Incorporar la información profesional extraída de la importación del CV del usuario y estructurarla para que pueda ser utilizada por el motor de evaluación y búsqueda.
- [ ] Organizar el perfil, inicialmente, en: objetivo/posicionamiento profesional; roles y nivel de seniority; experiencia profesional; sectores; competencias de gestión; competencias técnicas; tecnologías/herramientas; liderazgo/equipos; idiomas; formación/certificaciones; ubicaciones/movilidad; preferencias y restricciones de búsqueda.
- [ ] Permitir revisar y editar la información extraída del CV antes de considerarla parte activa del perfil.
- [ ] Mantener trazabilidad entre información procedente del CV y preferencias aprendidas posteriormente por Job Radar.
- [ ] Preparar el perfil para futuras reimportaciones/actualizaciones del CV sin perder información validada por el usuario.

### 2. Oportunidades

- [ ] Convertir la pantalla actual de revisión de ofertas en la sección `Oportunidades` del menú principal.
- [ ] Mantener en esta pantalla la bandeja de entrada, valoración humana, estado de aplicación, encaje IA, filtros avanzados y `Aplicar aprendizaje`.
- [ ] Preservar y mostrar la estructura original de la descripción de la oferta siempre que la fuente la proporcione: párrafos, encabezados, listas y bullets. Evitar presentar toda la descripción como un único bloque de texto plano.
- [ ] Cuando la fuente llegue sin estructura HTML utilizable, reconstruir una presentación legible de forma conservadora (párrafos/listas) sin alterar el contenido de la oferta.
- [ ] Añadir un `Resumen nuclear IA` de cada oferta: muy breve, factual, directo y sin lenguaje promocional. Debe permitir entender en segundos qué puesto es, misión principal, responsabilidades/requisitos realmente determinantes y cualquier condición relevante disponible; no repetir información secundaria ni inventar datos.
- [ ] Mostrar el `Resumen nuclear IA` antes de la descripción original completa para acelerar la revisión humana.

### 3. Búsquedas

- [ ] Crear pantalla `Búsquedas` para visualizar y administrar todas las búsquedas automáticas del Job Radar.
- [ ] Mostrar cada búsqueda de forma ordenada con: nombre; estado activa/inactiva; criterios/filtros; localización o localizaciones; alcance/fuente (`LinkedIn`, otra plataforma concreta o `Web / múltiples fuentes`); frecuencia/horario; fecha y hora de la última ejecución; número de ofertas encontradas en la última ejecución; número de ofertas que permanecieron después del filtrado; y estado/resultado de la ejecución.
- [ ] Permitir `Activar / Desactivar`, `Editar` y `Borrar` cada búsqueda.
- [ ] Permitir crear nuevas búsquedas manualmente desde el frontend.
- [ ] Diseñar los criterios/filtros como datos editables y no como configuración fija en código, para que puedan evolucionar sin modificar el repositorio.
- [ ] Añadir acción `Importar búsqueda / filtros` mediante fichero.
- [ ] Al importar un fichero, extraer automáticamente posibles criterios de búsqueda: puestos/roles, keywords, exclusiones, seniority, sectores, tecnologías/competencias, localizaciones, fuentes/plataformas, modalidad de trabajo y otros criterios detectables.
- [ ] Mostrar los filtros extraídos antes de guardarlos para que el usuario pueda aceptar, eliminar o editar individualmente cada criterio.
- [ ] No activar automáticamente una búsqueda importada hasta que el usuario confirme la configuración final.
- [ ] Registrar métricas por ejecución para poder mostrar el número de ofertas encontradas y filtradas en la última búsqueda y su fecha.
- [ ] Preparar el modelo para distinguir búsquedas limitadas a una plataforma de búsquedas abiertas a múltiples fuentes / Web.

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
