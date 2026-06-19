# docs/ — Memoria durable del proyecto

- `ARCHITECTURE.md` — visión general, componentes, flujo de datos.
- `DECISIONS.md` — registro de decisiones (ADR). El harness añade entradas al tomar decisiones relevantes.
- `CONVENTIONS.md` — convenciones de código, naming, ramas.

El agente lee esta carpeta antes de implementar. `spec.mjs approve` añade contexto mínimo automáticamente
a `ARCHITECTURE.md` y `DECISIONS.md`, pero el dev debe rellenar la parte de visión y convenciones del repo.

Mínimo útil antes de la primera feature:

1. En `ARCHITECTURE.md`, completa objetivo del producto, componentes existentes y restricciones conocidas.
2. En `CONVENTIONS.md`, completa cómo se ejecuta, testea y despliega este repo.
3. En `DECISIONS.md`, deja cualquier decisión que no deba redescubrir otro agente.
