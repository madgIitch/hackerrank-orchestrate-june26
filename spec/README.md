# spec/ — Specs aprobados (durables, versionados)

`spec.json` (raíz) es la cola viva. Aquí queda el spec **aprobado** de cada feature, en una subcarpeta
`<id>-<name>/` con tres archivos (estructura SDD):

- `requirements.md` — el QUÉ: contexto, requisitos funcionales (R1, R2…) y restricciones.
- `design.md` — el CÓMO: scope, enfoque por dimensión y decisiones de la entrevista.
- `tasks.md` — el desglose: checklist que el agente marca al implementar.

Los genera `spec.mjs approve`.
