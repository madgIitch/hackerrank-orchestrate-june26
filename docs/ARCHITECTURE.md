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

