# Convenciones

- Metodología: SDD (una feature a la vez, spec aprobado antes de implementar).
- Sin ramas por feature: el harness trabaja en la rama actual y commitea cada feature ahí (`feat(<name>): <título>`). Para aislar una corrida entera, usa un `git worktree`.
- Una feature `sdd:true` queda en `review_pending` tras implementar; revisas el diff y la cierras con `spec.mjs done` (o `git revert` para descartarla).
- Tests obligatorios para cerrar una feature.

## Estilo de código

Lenguaje/framework principal:

Gestor de paquetes:

Comandos locales:

- Instalar:
- Lint:
- Typecheck/build:
- Test:
- Dev server:

Estructura relevante:

- (rellenar) Carpeta:
  - Propósito:

Reglas de diseño/API:

- (rellenar)

Reglas de tests:

- (rellenar)

Reglas de despliegue:

- (rellenar)
