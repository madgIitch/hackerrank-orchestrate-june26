# 1 · Setup, reconocimiento de datos y esquema base — Tareas

Checklist de implementación. El agente marca [x] al completar; los gates verifican.

- [ ] (T1) Existe una estructura base versionada con `code/`, `code/evaluation/` cuando aplique, `evaluation/`, `prompts/` si se crean prompts, `docs/`, `tests/` y `README.md`, sin tocar `.harness/` ni mover `dataset/`.  ↔ R1
- [ ] (T2) Existe un script de perfilado ejecutable bajo `code/` que carga `dataset/sample_claims.csv`, `dataset/claims.csv`, `dataset/user_history.csv` y `dataset/evidence_requirements.csv`.  ↔ R2
- [ ] (T3) El perfilado genera o actualiza `evaluation/data_profile.md` con filas por CSV, columnas detectadas, incidencias/warnings y distribuciones de `claim_status`, `claim_object` e `issue_type` en `sample_claims.csv`.  ↔ R3
- [ ] (T4) Cada distribucion incluye conteos absolutos, porcentajes, total de filas, conteo de valores nulos/vacios y valores fuera del enum esperado, ordenados por conteo descendente y valor alfabetico en empates.  ↔ R4
- [ ] (T5) El perfilado valida todas las entradas de `image_paths` del sample contra archivos existentes y reporta claramente cualquier ruta faltante.  ↔ R5
- [ ] (T6) El contrato de `output.csv` esta documentado con exactamente 14 columnas en el orden aprobado.  ↔ R6
- [ ] (T7) Los enums aprobados para `claim_status`, `issue_type`, `object_part` por tipo de objeto, `risk_flags`, `valid_image`, `evidence_standard_met` y `severity` estan definidos en una unica fuente de verdad reutilizable.  ↔ R7
- [ ] (T8) Hay tests o comprobaciones automatizadas que verifican carga de CSV, existencia de imagenes del sample, contrato de columnas de `output.csv` y validez de enums centralizados.  ↔ R8
- [ ] Tests que cubran los criterios de aceptación
