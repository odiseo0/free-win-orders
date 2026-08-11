# Free Win - Guía de formato para documentación

## 1) Propósito

Este documento define el formato de los archivos Markdown de Free Win. Su objetivo es mantener una documentación consistente, fácil de consultar y alineada con el estado real del proyecto.

Esta guía es normativa para documentos dentro de `docs/`. Un documento puede apartarse de ella cuando su propósito lo requiera, pero debe hacerlo de forma intencional y evidente.

## 2) Alcance

Esta guía cubre:

- idioma, voz y terminología;
- estructura y jerarquía de secciones;
- representación del estado de funcionalidades;
- referencias a código y otros documentos;
- ejemplos, tablas y diagramas;
- glosarios, registros de decisiones y checklists de actualización;
- responsabilidad de cada documento principal.

Esta guía no define:

- convenciones del código Python, cubiertas por `docs/conventions.md`;
- arquitectura o patrones de implementación, cubiertos por `docs/system_patterns.md`;
- estrategia de pruebas, cubierta por `docs/testing.md`;
- reglas funcionales del dominio, documentadas en `docs/general_documentation.md` y documentos específicos futuros.

## 3) Idioma, voz y terminología

### 3.1 Idioma

- **Required** escribe la documentación en español.
- **Required** conserva en inglés los nombres propios de tecnologías, símbolos de código, rutas y términos cuyo equivalente pueda introducir ambigüedad, como FastAPI, SQLAlchemy, endpoint, router o DAO.
- **Recommended** explica en español un término técnico la primera vez que sea necesario para entenderlo.

### 3.2 Voz y tono

- **Required** usa lenguaje claro, directo y técnico.
- **Required** describe hechos actuales en presente.
- **Required** diferencia una intención futura de un comportamiento implementado.
- **Recommended** prefiere frases cortas y párrafos centrados en una sola idea.
- **Recommended** evita lenguaje corporativo, promocional o burocrático.

Ejemplo correcto:

> `CardListingReferenceDAO` consulta solamente las columnas necesarias para el snapshot de una Orden.

Ejemplo incorrecto:

> Nuestra solución de clase mundial ofrece una plataforma robusta y altamente escalable.

### 3.3 Vocabulario canónico

- **Required** usa las definiciones de `docs/general_documentation.md` y `AGENTS.md`.
- **Required** escribe **Pedido** para el período abierto por Free Win y **Orden** para el envío individual de un Usuario.
- **Required** aclara que **Orden** es un nombre provisional cuando esa condición sea relevante para la decisión documentada.
- **Required** no alternes sin explicación entre sinónimos para un mismo concepto.
- **Recommended** usa mayúscula inicial para conceptos del dominio cuando se refieran a su significado específico en Free Win.

## 4) Estado y certeza de la información

### 4.1 Etiquetas de estado

Cuando pueda existir ambigüedad, identifica la naturaleza de una afirmación con una de estas etiquetas:

- **Comportamiento actual**: está implementado y puede verificarse en el código.
- **Funcionalidad prevista**: forma parte de la dirección del producto, pero no está implementada completamente.
- **Restricción**: límite conocido del sistema o del contexto.
- **Decisión**: elección adoptada conscientemente y acompañada de contexto.
- **Propuesta**: alternativa todavía pendiente de aprobación.
- **Referencia**: fuente que respalda la afirmación.

Ejemplo:

```md
**Comportamiento actual**: la API registra routers para Usuarios, Direcciones y Roles.

**Funcionalidad prevista**: un administrador podrá abrir y cerrar Pedidos.
```

### 4.2 Afirmaciones verificables

- **Required** no describas código planeado como si ya existiera.
- **Required** respalda las afirmaciones técnicas importantes con rutas del repositorio.
- **Required** si una regla de negocio no está definida, declárala pendiente en lugar de inventarla.
- **Recommended** indica la fecha solamente cuando una decisión o dato pueda necesitar contexto temporal.
- **Recommended** elimina notas especulativas que ya no ayuden a tomar una decisión.

## 5) Estructura de los documentos

### 5.1 Orden recomendado

Los documentos principales deben usar este orden, salvo que exista una razón clara para modificarlo:

1. Propósito.
2. Alcance.
3. Contenido específico del documento.
4. Referencias.
5. Glosario, cuando sea necesario.
6. Decisiones y restricciones, cuando corresponda.
7. Checklist de actualización.

Los documentos pequeños pueden combinar Propósito y Alcance. No añadas secciones vacías únicamente para cumplir la plantilla.

### 5.2 Jerarquía de encabezados

- **Required** usa un único `#` para el título del documento.
- **Required** usa `##` para secciones principales numeradas.
- **Required** usa `###` para subsecciones numeradas según su sección principal.
- **Recommended** evita superar el nivel `####`.
- **Required** no añadas puntuación al final de un encabezado.
- **Recommended** conserva encabezados estables para evitar romper enlaces internos.

Ejemplo:

```md
# Free Win - Contexto técnico

## 1) Propósito

## 2) Alcance

## 3) Configuración

### 3.1 API

### 3.2 Base de datos
```

### 5.3 Títulos

- **Required** usa el formato `Free Win - <Tema>` para documentos principales.
- **Recommended** usa títulos breves que describan el contenido, no el nombre de una tarea.
- **Recommended** evita palabras genéricas como “Notas” o “Información” cuando pueda elegirse un tema concreto.

## 6) Plantilla para documentos nuevos

Usa esta plantilla como punto de partida, eliminando secciones que no sean necesarias:

```md
# Free Win - <Título>

## 1) Propósito

<Por qué existe este documento y para quién resulta útil.>

## 2) Alcance

Este documento cubre:

- <tema incluido>;
- <tema incluido>.

Este documento no cubre:

- <tema excluido>.

## 3) <Contenido principal>

### 3.1 <Subtema>

<Comportamiento, regla o explicación.>

## 4) Referencias

- `src/ruta/al/archivo.py`: <relación con el documento>.

## 5) Glosario

- **Término**: definición breve.

## 6) Decisiones y restricciones

### DEC-YYYYMMDD-descripcion-breve

- **Fecha**: YYYY-MM-DD.
- **Contexto**: <situación que originó la decisión>.
- **Decisión**: <elección adoptada>.
- **Impacto**: <consecuencias>.
- **Evidencia**: `<ruta>`.
- **Revisión**: <condición que obliga a reconsiderarla>.

## 7) Checklist de actualización

- [ ] <condición que requiere revisar el documento>.
```

## 7) Formato del contenido

### 7.1 Párrafos y listas

- **Recommended** usa párrafos breves para contexto y listas para conjuntos de elementos equivalentes.
- **Required** cada elemento de una lista expresa una idea principal.
- **Recommended** usa listas numeradas cuando el orden sea significativo y viñetas cuando no lo sea.
- **Recommended** introduce una lista con una oración que explique qué representa.
- **Recommended** evita listas con un único elemento salvo que formen parte de una plantilla.

### 7.2 Énfasis

- **Required** usa negritas para conceptos o etiquetas importantes, no para decorar frases completas.
- **Required** usa código inline para rutas, símbolos, comandos, variables y valores literales.
- **Recommended** usa cursiva con moderación para matices lingüísticos, no para reglas.
- **Required** no uses bloques de cita como sustituto de encabezados o listas.

### 7.3 Bloques de código

- **Required** especifica el lenguaje del bloque cuando sea conocido: `python`, `bash`, `text`, `json` o `md`.
- **Required** los ejemplos deben ser mínimos y centrarse en la idea documentada.
- **Required** no incluyas secretos, credenciales ni datos personales reales.
- **Recommended** indica explícitamente cuando un ejemplo sea ilustrativo y no represente código existente.
- **Recommended** usa comentarios dentro del ejemplo solamente cuando expliquen una decisión no evidente.

### 7.4 Tablas

- **Recommended** usa tablas para comparar campos repetidos o mostrar mappings compactos.
- **Recommended** evita tablas para texto narrativo largo o listas simples.
- **Required** cada tabla debe tener encabezados claros y celdas que puedan leerse sin contexto oculto.

### 7.5 Diagramas

- **Recommended** usa diagramas únicamente cuando aclaren un flujo, dependencia o secuencia mejor que el texto.
- **Recommended** usa bloques `text` para flujos pequeños y Mermaid para relaciones complejas.
- **Required** acompaña el diagrama con una explicación breve.
- **Required** un diagrama no debe contradecir el estado descrito en el texto.

## 8) Referencias y enlaces

### 8.1 Rutas del repositorio

- **Required** usa rutas relativas a la raíz del repositorio y enciérralas en código inline.
- **Required** incluye el nombre exacto del archivo cuando respalde una afirmación concreta.
- **Recommended** referencia carpetas cuando se hable de una responsabilidad general y archivos cuando se hable de comportamiento.

Ejemplos:

- `src/api/users/`: componente completo.
- `src/api/users/infrastructure/users_api.py`: endpoints de Usuarios.
- `src/api/order_requests/repository/card_listings.py`: proyección externa de Publicaciones.

### 8.2 Referencias a símbolos y líneas

- **Recommended** nombra el símbolo relevante cuando sea más estable que una línea: `DAO.get_multi` en `src/core/db/dao.py`.
- **Recommended** usa números de línea solamente para revisiones puntuales o evidencia que requiera precisión.
- **Required** no dependas únicamente de líneas en documentación de larga duración, porque cambian con frecuencia.

### 8.3 Enlaces entre documentos

- **Required** usa rutas relativas como `docs/conventions.md` al mencionar otro documento desde el texto.
- **Recommended** enlaza al documento propietario del detalle en lugar de duplicar secciones extensas.
- **Required** verifica que el nombre mencionado coincida con el archivo real.

## 9) Glosarios

### 9.1 Cuándo incluirlos

Incluye un glosario cuando el documento:

- utiliza conceptos del dominio;
- introduce acrónimos o términos técnicos poco evidentes;
- usa una palabra con significado particular dentro de Free Win;
- necesita distinguir conceptos cercanos, como Pedido y Orden.

### 9.2 Formato

- **Required** usa un término por viñeta.
- **Required** aplica el formato `**Término**: definición`.
- **Recommended** mantén cada definición en una sola oración cuando sea posible.
- **Required** evita definiciones circulares.
- **Required** conserva consistencia con `docs/general_documentation.md`.

Ejemplo:

```md
- **Pedido**: período durante el cual Free Win recibe Órdenes de los jugadores.
- **Orden**: solicitud individual de un Usuario dentro de un Pedido.
```

## 10) Registro de decisiones

### 10.1 Cuándo registrar una decisión

Añade una decisión cuando:

- una elección arquitectónica tenga alternativas razonables;
- una limitación externa afecte el comportamiento;
- una regla provisional tenga consecuencias para varias partes del proyecto;
- se adopte o descarte una dependencia importante;
- una decisión de datos, seguridad u operación necesite contexto histórico.

No registres decisiones triviales ni uses el registro como diario de cambios.

### 10.2 Identificador

Usa el formato:

```text
DEC-YYYYMMDD-descripcion-breve
```

La descripción usa minúsculas y guiones. Si existen varias decisiones el mismo día, cada descripción debe ser única.

### 10.3 Campos

Cada decisión incluye:

- **Fecha**: día en que se adoptó.
- **Contexto**: problema o circunstancia.
- **Decisión** o **Restricción**: lo que se acepta como cierto.
- **Impacto**: consecuencias técnicas o funcionales.
- **Evidencia**: documentos o código relacionado.
- **Revisión**: cambio que obliga a reconsiderarla.

Ejemplo:

```md
### DEC-20260811-external-table-boundary

- **Fecha**: 2026-08-11.
- **Contexto**: dos servicios comparten una tabla relacionada.
- **Decisión**: declarar una proyección de lectura y respetar al propietario del esquema.
- **Impacto**: se conserva la FK sin duplicar migraciones.
- **Evidencia**: `src/api/order_requests/repository/card_listings.py`.
- **Revisión**: reevaluar si los servicios dejan de compartir base de datos.

## 11) Documentos temporales y propuestas

- **Required** un documento temporal debe declararlo al inicio.
- **Required** el contenido de cualquier documento temporal no es normativo hasta incorporarse al documento propietario correspondiente.
- **Required** una propuesta debe usar la etiqueta **Propuesta** y no mezclarse con comportamiento actual.
- **Recommended** elimina material temporal después de incorporarlo o descartarlo, cuando ya no aporte contexto.
- **Recommended** evita que notas de lluvia de ideas se conviertan accidentalmente en documentación oficial.

## 12) Responsabilidad de los documentos

Usa este mapa para evitar duplicación:

| Documento | Responsabilidad principal |
| --- | --- |
| `README.md` | Presentación breve, stack, estructura y entrada al proyecto |
| `AGENTS.md` | Contexto y reglas operativas para agentes |
| `docs/general_documentation.md` | Dominio, alcance, estado actual y navegación general |
| `docs/tech_context.md` | Runtime, dependencias, configuración, persistencia y operación |
| `docs/system_patterns.md` | Patrones de implementación e interacción entre capas |
| `docs/conventions.md` | Reglas de código y diseño para contribuciones |
| `docs/testing.md` | Estrategia, herramientas y criterios de pruebas |
| `docs/formatting.md` | Formato, estructura y mantenimiento de documentación |

Cuando un tema afecte varios documentos, mantén el detalle completo en el documento propietario y añade referencias breves desde los demás.

## 13) Mantenimiento y sincronización

### 13.1 Actualización junto con el código

- **Required** actualiza la documentación en el mismo cambio cuando una modificación vuelva incorrecta una afirmación vigente.
- **Required** mueve una característica de **Funcionalidad prevista** a **Comportamiento actual** solamente cuando esté implementada.
- **Required** revisa diagramas, ejemplos, rutas y glosarios después de renombrar componentes.
- **Recommended** evita documentar detalles internos inestables salvo que sean necesarios para comprender una decisión.

### 13.2 Revisión de referencias

Comprueba especialmente:

- rutas y nombres de archivos;
- nombres de componentes y recursos;
- endpoints y parámetros;
- clases, funciones y modelos mencionados;
- estado actual o futuro de cada funcionalidad;
- enlaces entre documentos.

## 14) Referencias

- `README.md`: presentación breve del repositorio.
- `AGENTS.md`: contexto del dominio y reglas para agentes.
- `docs/general_documentation.md`: vocabulario y visión general.
- `docs/conventions.md`: convenciones de código y diseño.
- `docs/system_patterns.md`: patrones del sistema.
- `docs/tech_context.md`: contexto técnico.
- `docs/testing.md`: estrategia de pruebas.

## 15) Glosario

- **Documento propietario**: archivo responsable de mantener el detalle principal de un tema.
- **Normativo**: contenido que establece una regla vigente para el proyecto.
- **Propuesta**: alternativa pendiente de aprobación o implementación.
- **Referencia**: código o documento que respalda una afirmación.
- **Restricción**: límite conocido que condiciona una decisión o comportamiento.

## 16) Checklist de actualización

Antes de integrar cambios documentales:

- [ ] ¿El título y los encabezados siguen la jerarquía acordada?
- [ ] ¿El documento distingue comportamiento actual, funcionalidad prevista y propuestas?
- [ ] ¿El vocabulario coincide con `docs/general_documentation.md`?
- [ ] ¿Las rutas y los símbolos mencionados existen?
- [ ] ¿Los ejemplos son mínimos, seguros y coherentes con el texto?
- [ ] ¿El detalle está en el documento propietario correcto?
- [ ] ¿Las decisiones importantes incluyen contexto, impacto, evidencia y revisión?
- [ ] ¿Los enlaces y referencias siguen siendo válidos?
- [ ] ¿El cambio requiere actualizar otro documento relacionado?
