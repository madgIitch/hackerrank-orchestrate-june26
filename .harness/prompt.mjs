export function buildInitialPrompt(task) {
  return [
    "Implementa esta feature (metodología SDD). El spec ya fue aprobado por el dev.",
    "Antes de empezar, lee docs/ARCHITECTURE.md, docs/CONVENTIONS.md y docs/DECISIONS.md si existen, y respétalos.",
    `Lee el spec completo en spec/${task.id}-${task.name}/ (requirements.md, design.md, tasks.md).`,
    `id: ${task.id}  name: ${task.name}`,
    `Título: ${task.title}`,
    `Descripción: ${task.description}`,
    task.scope?.length ? `SOLO puedes tocar: ${task.scope.join(", ")} (además de docs/ y spec/ para registrar decisiones y marcar tareas).` : "",
    "Criterios de aceptación:",
    ...(task.acceptance ?? []).map((a, i) => `  ${i + 1}. ${a}`),
    `Marca [x] en spec/${task.id}-${task.name}/tasks.md las tareas que completes.`,
    "Si tomas una decisión de arquitectura relevante, añádela como entrada nueva en docs/DECISIONS.md.",
    "Reglas: no hagas commits (lo hace el harness), no salgas del scope. Los gates verificarán tu trabajo.",
  ].filter(Boolean).join("\n");
}
export function buildRetryPrompt(task, failure, attempt) {
  return [
    buildInitialPrompt(task),
    `\n--- INTENTO ${attempt}: el anterior FALLÓ la verificación ---`,
    "Salida exacta de los gates. Corrige solo eso, no reescribas todo:",
    failure,
  ].join("\n");
}
