# AGENTS.md

## Propósito del proyecto

Free Win es una herramienta comunitaria para jugadores de Yu-Gi-Oh! que facilita la compra de cartas difíciles de conseguir en el país. No es un producto corporativo ni busca introducir procesos empresariales por defecto. Prioriza soluciones sencillas, mantenibles y útiles para la comunidad y para las personas que administran Free Win.

Antes de proponer una abstracción, dependencia o servicio nuevo, comprueba que resuelva una necesidad actual. Evita sobrearquitectura, flujos burocráticos y optimizaciones especulativas. Aun así, preserva límites claros cuando ayuden a que una parte del sistema pueda evolucionar de forma independiente.

## Vocabulario del dominio

Usa estos conceptos de forma consistente en código, documentación y conversaciones:

- **Pedido**: período abierto por los administradores durante el cual los usuarios pueden enviar las cartas que desean comprar. Un Pedido suele permanecer abierto durante semanas; no representa una compra individual ni implica ejecución inmediata.
- **Orden**: envío individual de un usuario dentro de un Pedido. Un administrador revisa la Orden y puede aceptarla, rechazarla, procesarla parcialmente o actualizar su estado según las cartas que se logren comprar. El nombre todavía es provisional: no consolides terminología nueva ni hagas renombrados amplios sin discutirlo primero.
- **Pre-Pedido**: funcionalidad futura; no asumas todavía sus reglas de negocio.

El flujo mínimo esperado es:

1. Un administrador abre un Pedido.
2. Los usuarios rellenan la plantilla con las cartas que quieren y envían su Orden.
3. Un administrador toma y revisa la Orden.
4. El administrador actualiza su estado, incluyendo resultados parciales cuando corresponda.

No modeles una Orden como una compra instantánea ni asumas que todas sus cartas comparten necesariamente el mismo resultado.

## Prioridades funcionales

El núcleo del dominio son los Pedidos y las Órdenes. El núcleo técnico actual es el servicio de scraping en `src/apps/api/shared/services/scraper/`, que permite buscar cartas y que, progresivamente, debe alimentar una base de datos propia para evitar scraping innecesario.

Características previstas, pero no necesariamente diseñadas o comprometidas:

- trazabilidad de Pedidos y Órdenes;
- Pre-Pedidos;
- mapa de entrega;
- históricos de precios y de Pedidos.

Trata esta lista como orientación de producto, no como permiso para implementar alcance adicional en una tarea no relacionada.

## Estructura del repositorio

Este es un monorepo Python:

- `src/apps/api/`: backend FastAPI;
- `src/apps/client/`: cliente HTML mínimo para pruebas iniciales;
- `src/settings/`: configuración compartida;
- `docs/`: documentación técnica y funcional detallada;
- `tests/`: pruebas automatizadas.

La API se organiza por componentes (`cards`, `collections`, `orders`, `users` y `shared`) siguiendo una arquitectura hexagonal pragmática:

- `domain/`: entidades y reglas de negocio, sin dependencias de FastAPI, SQLAlchemy ni detalles de red;
- `application/`: casos de uso y coordinación del dominio;
- `infrastructure/`: adaptadores de entrada y salida, incluido HTTP;
- `repository/`: persistencia, modelos SQLAlchemy y acceso a datos;
- `shared/`: capacidades realmente transversales. No lo conviertas en un cajón de sastre.

Respeta la dirección de dependencias: infraestructura y persistencia pueden depender de aplicación/dominio, pero el dominio no debe depender de ellas. Sigue el patrón del componente en el que trabajas y evita refactorizaciones amplias no solicitadas.

Nota: el README puede mencionar `members`, pero el componente presente en el código es `users`. Verifica la intención antes de renombrar o crear uno de los dos.

## Documentación del proyecto

`AGENTS.md` ofrece el contexto general y las reglas de trabajo para agentes. La documentación detallada debe vivir en `docs/`. Aunque la carpeta esté vacía o alguno de estos archivos todavía no exista, usa esta organización al crear documentación nueva:

- `docs/conventions.md`: convenciones generales de nombres, organización y colaboración;
- `docs/tech_context.md`: arquitectura, stack, dependencias y decisiones técnicas;
- `docs/testing.md`: estrategia, herramientas y criterios de pruebas;
- `docs/general_documentation.md`: explicación funcional y operativa de la aplicación;
- `docs/patterns.md`: patrones adoptados y ejemplos de implementación;
- `docs/formatting.md`: reglas de estilo y formato por lenguaje o tipo de archivo.

Antes de implementar un cambio, consulta los archivos de `docs/` relevantes que ya existan. Si una decisión necesita explicación extensa o específica, documéntala en el archivo correspondiente y mantén `AGENTS.md` como guía concisa, evitando duplicar información que pueda divergir.

## Scraping y datos externos

El scraper ya está diseñado e implementado en `src/apps/api/shared/services/scraper/` como el núcleo técnico actual de la aplicación. Trátalo como un pipeline existente y conserva la separación de sus responsabilidades de obtención, transformación, validación y persistencia. No lo rediseñes ni reemplaces sin una necesidad explícita. Aunque hoy viva dentro de la API, mantén su lógica desacoplada de FastAPI y de interfaces concretas para conservar la posibilidad de extraerlo a un servicio independiente en el futuro.

Al modificarlo:

- conserva el comportamiento asíncrono y limita explícitamente la concurrencia;
- establece timeouts y maneja errores de red, respuestas incompletas y cartas no encontradas;
- no dependas de que el HTML externo sea estable;
- añade fixtures o muestras locales a las pruebas; las pruebas unitarias no deben depender de la red;
- normaliza y valida datos antes de persistirlos;
- favorece consultar datos almacenados y actualizar solo cuando sea necesario;
- no registres datos personales, credenciales ni contenido excesivo de respuestas externas;
- respeta las condiciones de uso y límites razonables del sitio de origen.

## Stack y decisiones técnicas

El stack actual incluye Python 3.13, FastAPI, SQLAlchemy 2, PostgreSQL/asyncpg y PDM. Alembic forma parte de la dirección prevista para migraciones, aunque la infraestructura correspondiente puede no estar aún creada en el repositorio.

El frontend definitivo no está decidido. El HTML, CSS y JavaScript actuales sirven para pruebas iniciales; Astro es una preferencia, no una decisión cerrada. No incorpores un framework de frontend ni cambies el stack sin que la tarea lo requiera explícitamente.

Mantén I/O asíncrono de extremo a extremo en rutas que accedan a red o base de datos. No ocultes operaciones bloqueantes dentro de funciones `async`.

## Forma de trabajar

Antes de editar:

1. Lee el README y los archivos cercanos al cambio.
2. Comprueba el estado del árbol de trabajo y conserva cambios ajenos.
3. Identifica la capa responsable y el vocabulario de dominio involucrado.

Durante la implementación:

- entrega el cambio mínimo completo que resuelva la necesidad;
- conserva compatibilidad salvo que se solicite lo contrario;
- usa nombres de dominio claros; los comentarios deben explicar decisiones, no repetir el código;
- añade tipos a interfaces y funciones nuevas;
- no añadas dependencias sin una justificación concreta;
- no incluyas secretos ni valores locales en el repositorio;
- para cambios de esquema, usa migraciones Alembic cuando esa infraestructura exista; no dependas de creación implícita de tablas en producción.

## Validación

Instala y ejecuta herramientas mediante PDM. Comandos habituales:

```bash
pdm install
pdm run pytest
pdm run fastapi dev src/applicacion.py
```

Al terminar un cambio, ejecuta al menos las pruebas relacionadas; si el alcance lo permite, ejecuta toda la suite con `pdm run pytest`. Para errores corregidos o reglas nuevas, añade una prueba que falle antes del cambio y pase después.

En el scraper, cubre como mínimo transformaciones, resultados vacíos, cartas inexistentes y HTML inesperado. En el dominio, prioriza pruebas de estados y transiciones de Pedido/Orden. En endpoints y repositorios, prueba los límites de integración sin hacer que la suite dependa de servicios externos no controlados.

Si no puedes ejecutar una validación, indícalo claramente junto con el motivo; no afirmes que una prueba pasó si no fue ejecutada.

## Criterio de producto

Cuando falte una regla de negocio, no inventes comportamiento irreversible. Expón la ambigüedad y elige, si es seguro, la opción más simple y reversible. Presta especial atención a:

- quién puede abrir, cerrar o administrar un Pedido;
- qué estados existen y qué transiciones son válidas;
- cómo se representa una Orden parcialmente procesada;
- moneda, envío, disponibilidad y momento del precio;
- datos personales necesarios para entrega y sus límites de acceso y retención.

La meta es reducir el trabajo manual de Free Win y dar a los jugadores una experiencia centralizada y comprensible. Evalúa cada cambio por su utilidad real para esas personas.
