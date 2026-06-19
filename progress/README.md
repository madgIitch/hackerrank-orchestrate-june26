# progress/ — Memoria de ejecución

- `current.md` — snapshot de la sesión activa: feature en curso, estado y siguiente acción. Se sobrescribe.
- `history.md` — historial datado de cierres de feature. Se va anexando.
- `impl_<name>.md` — registro de implementación por feature: intentos, gate que falló, tiempo y coste.
- `review_<name>.md` — veredicto (APPROVED/BLOCKED) con checkpoints derivados de los gates y del spec SDD.

Lo genera el orquestador automáticamente. (`.harness/harness-state.json` es el log crudo por máquina y NO
se versiona; esto es el resumen curado que sí.)
