# 4 · Prompting y logica de decision — Diseño

## Scope (archivos que puede tocar)

- `prompts/system_prompt.txt`
- `prompts/system_prompt_v2.txt`
- `code/prompt_builder.py`
- `code/parser_validator.py`
- `code/pipeline.py`
- `code/evaluation/main.py`
- `evaluation/evaluation_report.md`
- `tests/test_pipeline.py`
- `tests/test_parser_validator.py`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `spec/**`
- `progress/**`

## Enfoque

- **data_model:** PROMPT_VERSION='v2' como constante en código; el pipeline registra la versión en PipelineLog por ejecución. El prompt mejorado vive en prompts/system_prompt_v2.txt; prompts/system_prompt.txt se preserva sin modificar como baseline de feature 3. La versión NO se añade al output.csv (contrato de 14 columnas fijo); evaluation/evaluation_report.md debe indicar prompt_version tanto para el baseline v1 como para la estrategia v2.
- **external_contracts:** El prompt mejorado se guarda en prompts/system_prompt_v2.txt y se selecciona vía constante PROMPT_VERSION='v2' o parámetro en el prompt builder; v2 es el default del pipeline tras esta feature. prompts/system_prompt.txt se conserva sin reemplazar para reproducir el baseline v1. Evaluación y producción usan la misma selección por defecto; los scripts de evaluación pueden recibir versión explícita para correr comparativas.
- **edge_cases:** Flujo de dos pasadas máximo. Pasada 1: extracción/triage multimodal corto para identificar claim normalizada, issue_type candidato, object_part candidato, observaciones visuales e image_ids relevantes; con ese resultado se buscan los evidence_requirements exactos. Pasada 2: decisión final con transcript, imágenes, resumen de pasada 1, requisitos exactos e historial. Si la pasada 1 falla o devuelve valores inutilizables, se cae a requisitos generales y la pasada 2 debe poder producir not_enough_information. Máximo 2 llamadas por claim. El hardcode de issue_family_for_issue_type('unknown') se elimina; el flujo de dos pasadas es el mecanismo documentado en DECISIONS.md.
- **ui_states:** No hay UI. El output sigue siendo output.csv y evaluation/evaluation_report.md. Las justificaciones son campos de texto en el CSV.

## Decisiones de la entrevista

- **adv-586861b3e0:** supporting_image_ids validos son exclusivamente image_ids presentes en el ClaimRecord de entrada y cargados por ImageLoader. Si el modelo devuelve IDs que no pertenecen a esa claim, el post-proceso los elimina; si claim_status es supported o contradicted y no queda ningun image_id valido, se fuerza claim_status=not_enough_information y supporting_image_ids=none.
- **adv-322b0d62b7:** El post-proceso no depende de patrones de texto en evidence_standard_met_reason. Se activa por el booleano normalizado evidence_standard_met=false. El reason solo se usa como explicacion humana y no como condicion logica.
- **adv-c8b8a88dee:** Criterio binario: claim_status accuracy de v2 debe ser mayor o igual que el baseline v1 sobre sample_claims.csv, y si no mejora debe documentar categorias de error restantes sin empeorar issue_type ni object_part frente al baseline. Una mejora positiva en claim_status es deseable, pero no se exige delta minimo fijo porque el sample es pequeno y las llamadas reales pueden variar.
- **adv-6c32b43757:** No hace falta un ADR alternativo para esta feature: la regla queda fijada aqui. evidence_standard_met=false siempre fuerza not_enough_information, incluso si el modelo devuelve contradicted. Un futuro ADR podria cambiarlo, pero para la implementacion de feature 4 no hay excepcion.
- **adv-815c5bbcdd:** El log que cuenta para aceptar esta feature es PipelineLog en memoria, no stdout ni output.csv. Cada ejecucion de pipeline debe registrar prompt_version y, cuando aplique, decisiones de post-proceso relevantes. Los scripts de evaluacion pueden volcar ese log a evaluation/evaluation_report.md.
- **data_model:** La documentacion exige comparar estrategias/prompts y preservar trazabilidad de evaluacion, pero no define formato de version. Usaremos prompts/system_prompt_v2.txt como prompt mejorado y mantendremos prompts/system_prompt.txt como baseline de feature 3. En codigo habra una constante PROMPT_VERSION="v2" y el pipeline registrara esa version en PipelineLog; evaluation/evaluation_report.md debe indicar prompt_version para baseline y estrategia final. La version no se añade al output.csv porque el contrato de salida tiene exactamente 14 columnas.
- **error_states:** evidence_standard_met=false tiene precedencia sobre supported y contradicted. Si no se cumple la evidencia minima, el post-proceso fuerza claim_status=not_enough_information, supporting_image_ids=none si no hay imagen suficiente, y deja evidence_standard_met=false. contradicted solo es valido cuando hay evidencia visual suficiente para verificar una ausencia/discrepancia concreta del daño reclamado; sin esa suficiencia, la decision logica es not_enough_information.
- **edge_cases:** Usaremos un flujo de dos pasadas como maximo, sin añadir verbosidad innecesaria. Pasada 1: extraccion/triage multimodal corto para identificar claim normalizada, issue_type candidato, object_part candidato, observaciones visuales e image_ids relevantes. Con ese resultado se buscan los evidence_requirements exactos. Pasada 2: decision final con transcript, imagenes, resumen de pasada 1, requisitos exactos e historial. Si la pasada 1 falla o devuelve valores inutilizables, se cae a requisitos generales y la pasada final debe poder producir not_enough_information. No se haran mas de dos llamadas por claim en esta feature.
- **external_contracts:** El prompt mejorado se guarda en un archivo separado versionado, prompts/system_prompt_v2.txt, y se selecciona por constante o parametro del prompt builder; v2 sera el default del pipeline despues de la feature. prompts/system_prompt.txt se conserva sin reemplazar para reproducir el baseline. Evaluacion y produccion usan la misma seleccion por defecto, con posibilidad de pasar version explicitamente en scripts de evaluacion.
- **rollback_compat:** Los tests existentes pueden actualizarse solo cuando el nuevo comportamiento este documentado, pero no deben perder cobertura de fallback, validacion de enums ni escritura a tmp_path. No se requiere preservar un artefacto baseline previo si todavia no existe; para comparar, la evaluacion debe poder ejecutar o documentar baseline v1 usando prompts/system_prompt.txt y guardar resultados bajo evaluation/ cuando se implemente la evaluacion.
- **tests:** Metrica primaria: accuracy de claim_status sobre dataset/sample_claims.csv. Metricas secundarias: accuracy de issue_type, object_part y coherencia de supporting_image_ids. El spec se cumple si la evaluacion muestra mejora de claim_status frente al baseline v1, o si no mejora, documenta errores restantes con categorias accionables y no empeora issue_type/object_part de forma material. Deben existir tests unitarios deterministas para el post-proceso de not_enough_information independientes del modelo real, cubriendo supported, contradicted y not_enough_information.

