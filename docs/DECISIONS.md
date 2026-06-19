# Decisiones (ADR)

Formato por entrada: **fecha · título** — contexto, decisión y consecuencias.
El harness añade entradas cuando se aprueba un spec; el agente también debe añadir entradas cuando toma
una decisión de arquitectura relevante durante implementación.

## Pendientes de decisión

- (rellenar) Decisiones que aún no deben asumirse automáticamente.

<!-- Nuevas entradas debajo -->

<!-- harness:1 -->
## 2026-06-19 · 1 aprobado

Contexto: se aprobó el spec `1` (Setup, reconocimiento de datos y esquema base).

Decisiones registradas:

- **auth_secrets:** La feature se limita a CSV locales, imagenes de ejemplo, esquema, documentacion, perfilado y validaciones locales; no requiere autenticacion, secretos ni credenciales externas.
- **rollback_compat:** La implementacion debe ser aditiva y preservar archivos existentes. Si ya existen carpetas, scripts, docs o constantes, deben extenderse siguiendo la convencion local. No reemplazar ni borrar trabajo previo salvo que sea claramente placeholder generado por el harness y el cambio este limitado al scope aprobado. Mantener compatibilidad con las rutas canonicas del enunciado y no mover dataset/.
- **tests:** Deben quedar automatizadas como minimo estas comprobaciones: los cuatro CSV canonicos existen y cargan; las columnas de entrada requeridas existen; todas las rutas de image_paths en sample_claims.csv existen; el contrato de output.csv tiene exactamente las 14 columnas en orden; los enums centralizados coinciden con los valores permitidos del enunciado; no hay duplicados dentro de cada enum; claim_object solo permite car, laptop, package; el reporte de perfilado puede calcular distribuciones de claim_status, claim_object e issue_type para sample_claims.csv. Si no hay framework de tests, crear una prueba ligera ejecutable por pytest o un script de validacion documentado.

Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.
