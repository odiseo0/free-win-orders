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
└─ presentation/
```

## Arranque

```bash
pdm install
pdm run uvicorn src.applicacion:app --reload
```

## Estado

Este scaffold deja lista la base para seguir implementando el flujo principal:

1. Buscar cartas.
2. Anadir cartas a una coleccion.
3. Marcar items como `requested`.
4. Consolidar pedidos.
