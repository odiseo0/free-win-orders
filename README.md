# Free Win

Base del monorepo para la aplicacion web de gestion de pedidos comunitarios de cartas.

## Estructura

- `src/apps/api`: backend principal con arquitectura hexagonal y empaquetado por componente.
- `src/apps/client`: cliente HTML minimo.
- `src/settings`: configuracion compartida.
- `tests`: pruebas del proyecto.

## Componentes de API

- `cards`
- `collections`
- `orders`
- `members`
- `shared`

Cada componente sigue esta estructura:

```text
<component>/
├─ domain/
├─ application/
├─ infrastructure/
└─ repository/
```
