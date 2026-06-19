# 1 · Setup, reconocimiento de datos y esquema base — Requisitos

- name: `setup_data_profiling` · priority: P0 · sdd: true
- aprobado por: peorr · 2026-06-19T09:04:51.029Z

## Contexto

Preparar la estructura del proyecto, perfilar los CSV de sample, revisar imagenes de ejemplo y definir el esquema de salida con los enums permitidos como fuente de verdad.

## Requisitos funcionales

R1. Existe una estructura base versionada con `code/`, `code/evaluation/` cuando aplique, `evaluation/`, `prompts/` si se crean prompts, `docs/`, `tests/` y `README.md`, sin tocar `.harness/` ni mover `dataset/`.
R2. Existe un script de perfilado ejecutable bajo `code/` que carga `dataset/sample_claims.csv`, `dataset/claims.csv`, `dataset/user_history.csv` y `dataset/evidence_requirements.csv`.
R3. El perfilado genera o actualiza `evaluation/data_profile.md` con filas por CSV, columnas detectadas, incidencias/warnings y distribuciones de `claim_status`, `claim_object` e `issue_type` en `sample_claims.csv`.
R4. Cada distribucion incluye conteos absolutos, porcentajes, total de filas, conteo de valores nulos/vacios y valores fuera del enum esperado, ordenados por conteo descendente y valor alfabetico en empates.
R5. El perfilado valida todas las entradas de `image_paths` del sample contra archivos existentes y reporta claramente cualquier ruta faltante.
R6. El contrato de `output.csv` esta documentado con exactamente 14 columnas en el orden aprobado.
R7. Los enums aprobados para `claim_status`, `issue_type`, `object_part` por tipo de objeto, `risk_flags`, `valid_image`, `evidence_standard_met` y `severity` estan definidos en una unica fuente de verdad reutilizable.
R8. Hay tests o comprobaciones automatizadas que verifican carga de CSV, existencia de imagenes del sample, contrato de columnas de `output.csv` y validez de enums centralizados.

## Restricciones

- **error_states:** CSV obligatorios ausentes, columnas obligatorias ausentes, CSV ilegible o fallo al escribir el reporte deben fallar con codigo de salida no cero. Rutas de imagen inexistentes, image_paths vacios tras normalizacion, valores inesperados en campos etiquetados o enums no contemplados deben registrarse en un reporte de incidencias y hacer fallar el gate de validacion del sample. Distribuciones y hallazgos no criticos pueden reportarse como warnings, sin ocultar fallos de contrato.
- **auth_secrets:** La feature se limita a CSV locales, imagenes de ejemplo, esquema, documentacion, perfilado y validaciones locales; no requiere autenticacion, secretos ni credenciales externas.
- **rollback_compat:** La implementacion debe ser aditiva y preservar archivos existentes. Si ya existen carpetas, scripts, docs o constantes, deben extenderse siguiendo la convencion local. No reemplazar ni borrar trabajo previo salvo que sea claramente placeholder generado por el harness y el cambio este limitado al scope aprobado. Mantener compatibilidad con las rutas canonicas del enunciado y no mover dataset/.

