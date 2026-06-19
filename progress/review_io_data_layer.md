# Review - 2 - Capa de IO y datos

## Veredicto

REVIEW_PENDING.

## Checkpoints

- [x] Reutiliza `code/schema.py` como fuente de verdad.
- [x] `ClaimLoader` valida y parsea claims.
- [x] Enriquecimiento con `UserHistory` y defaults para usuario sin historial.
- [x] `EvidenceRequirements` implementa lookup y fallback determinista.
- [x] `ImageLoader` genera payload base64 y normaliza a `max_dimension=1024`.
- [x] `OutputWriter` escribe 14 columnas y corrige campos blandos.
- [x] Tests pytest con fixtures temporales y smoke test real.

## Pendiente

- [ ] Revision humana del diff.
