# Arquitectura

> El agente lo lee antes de implementar. Mantén aquí el contexto que no cabe en una feature concreta.

## Visión general

Producto/proyecto:

Usuarios principales:

Objetivo no negociable:

## Componentes

- (rellenar) Componente:
  - Responsabilidad:
  - Entradas/salidas:
  - Dueño/riesgo:

## Flujo de datos

1. (rellenar)

## Integraciones externas

- (rellenar) Servicio/API:
  - Contrato:
  - Credenciales/config:
  - Entorno local/CI:

## Restricciones conocidas

- (rellenar) Rendimiento, seguridad, compatibilidad, despliegue, coste, etc.

## Decisiones abiertas

- (rellenar) Preguntas que bloquean diseño futuro.

<!-- Los specs aprobados se anexan debajo con marcadores harness:<id>. -->

<!-- harness:1 -->
## 1 · Setup, reconocimiento de datos y esquema base

Preparar la estructura del proyecto, perfilar los CSV de sample, revisar imagenes de ejemplo y definir el esquema de salida con los enums permitidos como fuente de verdad.

### Scope aprobado

  - `dataset/**`
  - `evaluation/**`
  - `prompts/**`
  - `code/**`
  - `docs/**`
  - `tests/**`
  - `README.md`
  - `pyproject.toml`
  - `requirements.txt`

### Contexto técnico

- **data_model:** El contrato de salida queda fijado con exactamente 14 columnas en este orden: user_id, image_paths, user_claim, claim_object, evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part, claim_status, claim_status_justification, supporting_image_ids, valid_image, severity. Los enums aprobados son fuente de verdad centralizada: claim_status = supported, contradicted, not_enough_information; claim_object = car, laptop, package; issue_type = dent, scratch, crack, glass_shatter, broken_part, missing_part, torn_packaging, crushed_packaging, water_damage, stain, none, unknown; object_part por claim_object: car = front_bumper, rear_bumper, door, hood, windshield, side_mirror, headlight, taillight, fender, quarter_panel, body, unknown; laptop = screen, keyboard, trackpad, hinge, lid, corner, port, base, body, unknown; package = box, package_corner, package_side, seal, label, contents, item, unknown; risk_flags = none, blurry_image, cropped_or_obstructed, low_light_or_glare, wrong_angle, wrong_object, wrong_object_part, damage_not_visible, claim_mismatch, possible_manipulation, non_original_image, text_instruction_present, user_history_risk, manual_review_required; severity = none, low, medium, high, unknown. valid_image y evidence_standard_met son booleanos serializados en CSV como true/false.
- **external_contracts:** Rutas canonicas: dataset/sample_claims.csv, dataset/claims.csv, dataset/user_history.csv, dataset/evidence_requirements.csv, dataset/images/sample/** y dataset/images/test/**. Salidas de esta feature: codigo bajo code/ si se usa esa estructura, tests bajo tests/ si se crean, reporte de perfilado bajo evaluation/ o code/evaluation/ segun la estructura elegida, y documentacion en README.md/docs. La salida final del reto sera output.csv en la raiz, pero esta feature no debe generar predicciones finales; si se genera una plantilla, debe ser solo para validar columnas y no confundirse con la entrega final. CSV en UTF-8, con cabecera, delimitador coma, quoting estandar de csv/pandas y preservando los textos originales de user_claim.
- **edge_cases:** image_paths multiples se separan por punto y coma, recortando espacios y descartando segmentos vacios accidentales; si no queda ninguna ruta, la fila del sample es invalida. image_id se deriva del nombre de archivo sin extension. Los valores categoricos se normalizan con trim y lowercase solo para validar/perfilar; el output debe usar exactamente los enums canonicos. claim_object solo permite car, laptop o package. object_part se valida contra el enum correspondiente al claim_object y, si no puede determinarse en fases posteriores, se usara unknown. No existe claim_id en el contrato y no debe asumirse. Filas duplicadas se reportan como hallazgo, pero no se deduplican automaticamente.
- **ui_states:** No hay interfaz de usuario en esta feature; el resultado esperado son estructura de proyecto, scripts/notebooks, documentacion, reporte de perfilado y validaciones locales.

<!-- harness:2 -->
## 2 · Capa de IO y datos

Construir loaders y writers deterministas para claims, historial, requisitos de evidencia, imagenes y salida CSV valida, sin depender todavia del modelo.

### Scope aprobado

  - `code/schema.py`
  - `code/profile_data.py`
  - `code/io_data.py`
  - `tests/test_io_data.py`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISIONS.md`
  - `spec/**`
  - `progress/**`

### Contexto técnico

- **data_model:** Los loaders exponen dataclasses tipadas propias del proyecto y solo serializan a dict en los bordes CSV. ClaimLoader devuelve ClaimRecord con user_id, image_paths normalizados, image_ids, user_claim y claim_object. El enriquecimiento devuelve EnrichedClaim con claim y history. El historial ausente se representa de forma determinista como UserHistory(user_id=<claim user_id>, past_claim_count=0, accept_claim=0, manual_review_claim=0, rejected_claim=0, last_90_days_claim_count=0, history_flags="none", history_summary="No history available").
- **external_contracts:** ImageLoader devuelve ImagePayload con image_id, source_path, media_type, width, height, base64_data, resized, original_width, original_height y byte_size. El payload no es data URL: usa base64 crudo y media_type separado. max_dimension=1024. Si ancho y alto son <= 1024, no reescala y conserva bytes/formato originales. Si alguna dimension supera 1024, reescala manteniendo aspect ratio, convierte a JPEG RGB quality=85 y media_type="image/jpeg". Las rutas relativas se resuelven contra dataset/. No hay llamadas a modelo ni red.
- **edge_cases:** EvidenceRequirements.lookup recibe claim_object y una issue_family normalizada por el caller. En esta feature no se infiere familia desde texto libre, salvo helper permitido issue_family_for_issue_type(issue_type) con mapeo inicial: dent/scratch -> "dent or scratch"; crack/glass_shatter/broken_part/missing_part -> "crack, broken, or missing part"; torn_packaging/crushed_packaging -> "torn or crushed packaging"; water_damage/stain -> "water damage or stain"; none/unknown -> "general claim review". Precedencia: 1) claim_object exacto y applies_to exacto; 2) claim_object=all y applies_to exacto; 3) claim_object exacto y applies_to="general claim review"; 4) claim_object=all y applies_to="general claim review". Multiples coincidencias en el mismo nivel se devuelven todas en orden original del CSV.
- **ui_states:** No hay UI para esta feature; es capa de IO/datos con tests automatizados.

