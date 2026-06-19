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

<!-- harness:2 -->
## 2026-06-19 · 2 aprobado

Contexto: se aprobó el spec `2` (Capa de IO y datos).

Decisiones registradas:

- **auth_secrets:** La feature es local y determinista sobre CSV e imagenes; no requiere modelo, red, autenticacion ni secretos.
- **rollback_compat:** La implementacion debe ser aditiva y compatible con la feature 1: reutilizar code/schema.py como fuente de verdad, mantener rutas canonicas, no mover dataset/ y no generar output.csv final de entrega.
- **tests:** Los tests principales usan fixtures temporales autocontenidas en tmp_path para fijar casos de borde sin depender de cambios futuros del dataset. Debe mantenerse al menos un smoke test con CSV/imagenes reales de dataset/. Debe incluirse un caso explicito de enum invalido para verificar la politica de OutputWriter y un caso de imagen faltante para verificar fail-fast de ImageLoader.

Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.

<!-- harness:3 -->
## 2026-06-19 · 3 aprobado

Contexto: se aprobó el spec `3` (Pipeline vertical de una reclamacion).

Decisiones registradas:

- **auth_secrets:** Credenciales solo desde variables de entorno (GEMINI_API_KEY, GEMINI_MODEL), nunca en el repo. Documentadas en README y .env.example.
- **rollback_compat:** El pipeline no escribe output.csv en la raiz. Devuelve OutputRow/dict validado por claim. Persistencia solo mediante path explicito pasado por parametro o tmp_path en tests. Generacion de output.csv final reservada para final_submission_package.
- **tests:** Tests unitarios deterministas con mock del modelo, sin credenciales ni coste en pytest/CI. Test de integracion real opcional, saltado por defecto, solo corre si RUN_MODEL_TESTS=1 y GEMINI_API_KEY definidos; no bloquea CI. Fixtures: car/laptop/package con respuesta valida, JSON no parseable/fallo de llamada, valores invalidos degradados, imagen faltante/parcial.

Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.

<!-- harness:4 -->
## 2026-06-19 · 4 aprobado

Contexto: se aprobó el spec `4` (Prompting y logica de decision).

Decisiones registradas:

- **auth_secrets:** Heredado de feature 3: credenciales solo desde variables de entorno (GEMINI_API_KEY, GEMINI_MODEL). Feature 4 no añade nuevas integraciones externas ni secretos adicionales.
- **rollback_compat:** Los tests existentes pueden actualizarse solo cuando el nuevo comportamiento esté documentado, pero no deben perder cobertura de fallback, validación de enums ni escritura a tmp_path. No se requiere preservar un artefacto baseline previo si aún no existe; para comparar, la evaluación debe poder ejecutar o documentar el baseline v1 usando prompts/system_prompt.txt y guardar resultados bajo evaluation/. El pipeline v2 no puede romper los contratos de salida (14 columnas, enums existentes).
- **tests:** Métrica primaria: accuracy de claim_status sobre dataset/sample_claims.csv. Métricas secundarias: accuracy de issue_type, object_part y coherencia de supporting_image_ids. El spec se cumple si la evaluación muestra mejora de claim_status frente al baseline v1, o si no mejora, documenta errores restantes con categorías accionables sin empeorar issue_type/object_part de forma material. Tests unitarios deterministas (sin modelo real) para el post-proceso de not_enough_information cubriendo al menos: modelo dice supported con evidencia insuficiente → not_enough_information; modelo dice contradicted con evidencia insuficiente → not_enough_information; modelo dice not_enough_information con evidencia suficiente → se preserva not_enough_information. Test determinista adicional: user_history_risk no puede cambiar claim_status de not_enough_information a supported o contradicted.

Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.

<!-- harness:5 -->
## 2026-06-19 · 5 aprobado

Contexto: se aprobó el spec `5` (Suficiencia de evidencia y risk flags).

Decisiones registradas:

- **auth_secrets:** La feature opera sobre CSV locales ya cargados por feature 2 y sobre output del modelo existente. No introduce nuevas dependencias externas ni credenciales.
- **rollback_compat:** Se añade code/evidence_rules.py con funciones puras; pipeline.py lo llama como post-proceso tras la normalización/validación existente, sin alterar el orden de pasos previos. parser_validator.py solo se extiende si hace falta conectar la normalización con las reglas, no como lugar principal de la lógica. Los tests existentes de features 3/4 se actualizan para reflejar el nuevo paso post-proceso, conservando cobertura de fallback, enums, degradación de claim_status, supporting_image_ids válidos y escritura a tmp_path.
- **tests:** Tests unitarios en tests/test_evidence_rules.py son deterministas y sin modelo real: entradas estructuradas con EvidenceLookupResult, fila normalizada del modelo, señales estructurales (supporting_image_ids filtrados, valid_image, image_errors/risk_flags) e historial; salidas esperadas para evidence_standard_met, valid_image y risk_flags. Tests de integración con pipeline usan mock del modelo para verificar que el post-proceso se aplica y prevalece. Métricas de sample se documentan en evaluation/evaluation_report.md existente (distribución de evidence_standard_met, frecuencia de cada risk_flag individual, ratio de valid_image=false comparado contra ground truth), no en artefacto nuevo.
- **implementation:** El orden final del pipeline es merge/validate, filter_supporting_image_ids, apply_evidence_rules, apply_evidence_precedence y apply_history_risk_flags. Los flags de historial se propagan desde history_flags validos; si history_flags='none', se derivan user_history_risk con rejected_claim >= 2, last_90_days_claim_count >= 4, o manual_review_claim >= 2 con past_claim_count >= 5, y manual_review_required con rejected_claim >= 3, last_90_days_claim_count >= 5, o manual_review_claim >= 3. El historial nunca cambia claim_status ni evidence_standard_met.

Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.
