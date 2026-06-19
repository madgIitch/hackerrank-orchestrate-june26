# 2 · Capa de IO y datos — Requisitos

- name: `io_data_layer` · priority: P0 · sdd: true
- aprobado por: peorr · 2026-06-19T09:28:49.431Z

## Contexto

Construir loaders y writers deterministas para claims, historial, requisitos de evidencia, imagenes y salida CSV valida, sin depender todavia del modelo.

## Requisitos funcionales

R1. Existe una capa de IO bajo `code/` que reutiliza `code/schema.py` como unica fuente de verdad para `OUTPUT_COLUMNS` y enums, sin duplicar contratos.
R2. `ClaimLoader` carga CSV UTF-8 con `csv.DictReader`, valida columnas requeridas `user_id`, `image_paths`, `user_claim` y `claim_object`, parsea `image_paths` separados por punto y coma recortando espacios y descartando segmentos vacios, deriva cada `image_id` desde el filename sin extension, preserva el orden de filas y no deduplica claims ni imagenes.
R3. El enriquecimiento une `user_history` por `user_id` y representa usuarios sin historial como `UserHistory(user_id=<claim user_id>, past_claim_count=0, accept_claim=0, manual_review_claim=0, rejected_claim=0, last_90_days_claim_count=0, history_flags="none", history_summary="No history available")`.
R4. `EvidenceRequirements.lookup` recibe `claim_object` e `issue_family` normalizada, o usa `issue_family_for_issue_type(issue_type)` con el mapeo aprobado, y aplica precedencia exacta: objeto+familia, all+familia, objeto+general, all+general; multiples coincidencias del mismo nivel se devuelven en orden CSV.
R5. Cuando no hay requisito coincidente, `EvidenceRequirements` devuelve `EvidenceLookupResult(requirements=[], matched_rule="none")` sin fallar.
R6. `ImageLoader` resuelve rutas relativas contra `dataset/`, falla si la imagen no existe, y devuelve `ImagePayload(image_id, source_path, media_type, width, height, base64_data, resized, original_width, original_height, byte_size)` con base64 crudo, no data URL.
R7. `ImageLoader` usa `max_dimension=1024`; si la imagen no supera ese limite conserva bytes/formato originales, y si lo supera redimensiona preservando aspect ratio, convierte a JPEG RGB quality=85, y reporta width/height normalizados mas original_width/original_height.
R8. `OutputWriter` escribe CSV UTF-8 con cabecera y exactamente las 14 columnas de `OUTPUT_COLUMNS` en orden estricto, preserva textos originales, serializa booleanos como `true`/`false`, y serializa solo `risk_flags` y `supporting_image_ids` como listas separadas por punto y coma.
R9. `OutputWriter` falla en errores estructurales (`claim_object` invalido, `object_part` incompatible con `claim_object`, columnas imposibles de completar) y corrige campos blandos: `claim_status` invalido -> `not_enough_information`, `issue_type` invalido -> `unknown`, `severity` invalido -> `unknown`, `risk_flags` invalidos se descartan con fallback `none`, booleanos invalidos -> `false`, `supporting_image_ids` vacio -> `none`.
R10. No se genera `output.csv` final de entrega en la raiz durante esta feature; cualquier salida de prueba se escribe en `tmp_path` o fixtures temporales de tests.
R11. Los tests pytest usan fixtures temporales autocontenidas para round-trip CSV, usuario sin historial, claims con una y multiples imagenes, lookup con fallback `all`, carga/normalizacion de imagen, enum invalido en `OutputWriter` e imagen faltante en `ImageLoader`, mas un smoke test con CSV/imagenes reales de `dataset/`.

## Restricciones

- **error_states:** La politica aprobada es fail-fast para entradas estructuralmente invalidas: CSV ausente o ilegible, columnas requeridas ausentes, claim_object fuera de enum, image_paths vacio tras normalizar en un claim cargado, imagen local inexistente en ImageLoader, u object_part incompatible con claim_object al escribir salida. OutputWriter corrige solo campos blandos de prediccion: claim_status invalido -> not_enough_information; issue_type invalido -> unknown; severity invalido -> unknown; risk_flags invalidos se descartan y si no queda ninguno -> none; booleanos invalidos -> false; supporting_image_ids vacio -> none. Si no se encuentra requisito de evidencia, EvidenceRequirements devuelve requirements=[] y matched_rule="none" sin fallar.
- **auth_secrets:** La feature es local y determinista sobre CSV e imagenes; no requiere modelo, red, autenticacion ni secretos.
- **rollback_compat:** La implementacion debe ser aditiva y compatible con la feature 1: reutilizar code/schema.py como fuente de verdad, mantener rutas canonicas, no mover dataset/ y no generar output.csv final de entrega.

