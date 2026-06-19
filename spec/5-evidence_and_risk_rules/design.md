# 5 · Suficiencia de evidencia y risk flags — Diseño

## Scope (archivos que puede tocar)

- `code/evidence_rules.py`
- `code/parser_validator.py`
- `code/pipeline.py`
- `code/schema.py`
- `tests/test_evidence_rules.py`
- `tests/test_parser_validator.py`
- `evaluation/evaluation_report.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `spec/**`
- `progress/**`

## Enfoque

- **data_model:** Las reglas deterministas se implementan como post-proceso: el modelo aporta la decisión normalizada (evidence_standard_met, evidence_standard_met_reason, risk_flags, supporting_image_ids, valid_image, claim_status), pero la capa determinista en code/evidence_rules.py prevalece para evidence_standard_met, valid_image, risk_flags estructurales y cualquier degradación de claim_status derivada de evidencia insuficiente. No se añade model_visual_observations al contrato de 10 campos ni al output.csv; el visual_summary de feature 4 puede usarse como contexto interno/log pero no como condición basada en parsing de texto libre. La frontera es explícita: el modelo propone, las reglas corrigen si entran en conflicto con evidence_requirements.csv o el contrato de schema.py.
- **external_contracts:** evidence_requirements.csv y user_history.csv ya tienen loaders en feature 2 con contratos fijados. No hay nuevas APIs ni servicios externos.
- **edge_cases:** valid_image=true si al menos una imagen nítida, relevante y usable muestra el objeto o pieza reclamada con suficiente contexto para revisar la condición. wrong_angle se trata como flag de calidad/reviewabilidad: si wrong_angle es el único problema pero otra imagen relevante permite evaluar la pieza, valid_image sigue true; si todas las imágenes relevantes tienen wrong_angle y no permiten inspeccionar la condición reclamada, valid_image=false. En sets multi-imagen, risk_flags visuales se emiten aunque afecten solo parte del set, pero no fuerzan valid_image=false si queda al menos una imagen usable para la pieza reclamada. valid_image=false solo cuando ninguna imagen cargada permite evaluar el objeto/parte reclamada. Los risk_flags multi-imagen se fusionan como unión ordenada de enums canónicos separados por punto y coma, sin prefijos por image_id; el detalle por imagen puede quedar en evidence_standard_met_reason o claim_status_justification como texto humano.
- **ui_states:** No hay interfaz de usuario. La salida es output.csv y métricas en evaluation_report.md.

## Decisiones de la entrevista

- **adv-60e2d7ad23:** ### [adv-24b0c96d72] El fallback cuando requirements=[] se especifica como (False, 'No evidence requirement matched for this claim type') «o el fallback documentado en DECISIONS.md», pero DECISIONS.md no documenta ningún fallback alternativo. El mensaje exacto importa para las aserciones de los tests unitarios: no se puede decidir PASA/FALLA si la implementación usa un string distinto.

**R:**
- **adv-a6689f03ae:** ### [adv-2bcfe65e6b] En sets multi-imagen, la spec dice que «los risk_flags individuales se emiten igualmente para las imágenes afectadas», pero el esquema de salida tiene una única columna risk_flags por fila (por claim, no por imagen). No se especifica si los flags per-imagen se fusionan en esa columna, se deduplicán, o requieren una estructura adicional no definida en el contrato de 14 columnas. Dos implementaciones divergirían en la serialización observable.

**R:**
- **adv-a4f0a96c3d:** ## Decisiones registradas
- **data_model:** Las reglas deterministas deben implementarse como post-proceso del resultado del modelo y deben corregirlo cuando entren en conflicto con los requisitos del proyecto. El modelo puede aportar observaciones visuales, image_ids relevantes y una propuesta inicial, pero la capa determinista prevalece para evidence_standard_met, valid_image, risk_flags estructurales y cualquier degradacion de claim_status derivada de evidencia insuficiente. Esto mantiene la decision alineada con evidence_requirements.csv, el contrato de salida de schema.py y la precedencia visual definida en feature 4.
- **error_states:** Usar primero history_flags del CSV como fuente explicita: se parsea por punto y coma, se mapea a enums risk_flags y se descartan valores invalidos. Si history_flags='none', derivar flags solo con umbrales conservadores para evitar sobre-penalizar: user_history_risk si rejected_claim >= 2, o last_90_days_claim_count >= 4, o manual_review_claim >= 2 con past_claim_count >= 5. manual_review_required si rejected_claim >= 3, o last_90_days_claim_count >= 5, o manual_review_claim >= 3. Estos flags nunca pueden elevar claim_status por si solos; solo agregan riesgo y justificacion.
- **edge_cases:** valid_image debe ser true si al menos una imagen nitida, relevante y usable muestra el objeto o la pieza reclamada con suficiente contexto para revisar la condicion. En sets multi-imagen, los risk_flags visuales se emiten aunque solo afecten a parte del set, pero no fuerzan valid_image=false si queda al menos una imagen usable para la pieza reclamada. valid_image=false solo cuando ninguna imagen cargada permite evaluar el objeto/parte reclamada, o cuando todas las imagenes relevantes estan inutilizables, son del objeto equivocado o no muestran la parte/dano necesario.
- **rollback_compat:** Añadir un modulo nuevo code/evidence_rules.py con funciones puras y llamarlo desde pipeline.py como post-proceso despues de la normalizacion/validacion existente. parser_validator.py solo debe extenderse si hace falta conectar la normalizacion con estas reglas, no como lugar principal de la logica. Los tests existentes pueden actualizarse cuando el nuevo comportamiento este documentado, pero deben conservar cobertura de fallback, enums, degradacion de claim_status, supporting_image_ids validos y escritura a tmp_path.
- **tests:** Los tests principales deben ser unitarios puros y deterministas, sin modelo real: entradas estructuradas con requirements, decision normalizada del modelo, image_ids validos, señales visuales/risk_flags e historial; salidas esperadas para evidence_standard_met, valid_image y risk_flags. Añadir tambien tests de integracion con pipeline usando mock del modelo para verificar que el post-proceso se aplica. Las metricas de sample se documentan en evaluation/evaluation_report.md existente, no en un artefacto nuevo, incluyendo distribucion de evidence_standard_met, frecuencia de risk_flags y ratio de valid_image.

