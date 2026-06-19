import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { loadSpec, loadState, saveState } from "./state.mjs";
import { runGates } from "./gates.mjs";
import { buildInitialPrompt, buildRetryPrompt } from "./prompt.mjs";
import { runAgent } from "./runner.mjs";
import { interviewPath, parseAnswers, answersHash } from "./interview.mjs";

const DRY = process.argv.includes("--dry-run");
const PRI = { P0: 0, P1: 1, P2: 2, P3: 3 };
const PDIR = "progress";
const sh = (cmd) => execSync(cmd, { stdio: "pipe", encoding: "utf8" });

function approvalStale(f) {
  if (f.sdd === false || !f.answers_hash) return false;
  try {
    const md = readFileSync(interviewPath(f), "utf8");
    return answersHash(parseAnswers(md)) !== f.answers_hash;
  } catch { return false; }
}
function consumable(f) {
  if (f.spec_approved !== true) return false;
  if (approvalStale(f)) return false;
  return f.status === "pending" || f.status === "spec_ready";
}

function attemptsTable(attempts) {
  const rows = attempts.map((a) => {
    const fg = a.verdict?.passed ? "—" : (String(a.verdict?.failureOutput || "").match(/Gate fallido: ([^\n]+)/)?.[1] ?? "?");
    return `| ${a.attempt} | ${a.verdict?.passed ? "OK" : "FALLO"} | ${fg} | ${a.tts != null ? a.tts.toFixed(1) : "?"} | ${a.cost ?? "—"} |`;
  }).join("\n");
  return `| intento | resultado | gate fallido | tts(s) | coste |\n|--:|--|--|--:|--:|\n${rows}`;
}

const gateNames = () => { try { return JSON.parse(readFileSync(".harness/gates.config.json", "utf8")).gates.map((g) => g.name); } catch { return []; } };

// review_<name>.md: veredicto + checkpoints derivados de los gates deterministas y del spec SDD.
function writeReview(task, attempts) {
  const last = attempts.at(-1)?.verdict;
  const passed = last?.passed === true;
  const failed = passed ? null : (String(last?.failureOutput || "").match(/Gate fallido: ([^\n]+)/)?.[1] ?? null);
  const names = gateNames();
  const i = failed ? names.indexOf(failed) : names.length;
  const rows = names.map((n, idx) => passed || idx < i ? `- [x] ${n}` : idx === i ? `- [ ] ${n} ← falló` : `- [ ] ${n} (no ejecutado)`);
  const L = [`# Review · ${task.id} · ${task.title}`, "", "## Veredicto", "",
    passed ? `APPROVED → \`${task.status}\`.` : `BLOCKED tras ${attempts.length} intento(s).`, "",
    "## Checkpoints — gates", "", ...rows, ""];
  if (task.sdd !== false) {
    const sd = `spec/${task.id}-${task.name}`;
    L.push("## Checkpoints — SDD", "", ...["requirements", "design", "tasks"].map((f) => `- [${existsSync(`${sd}/${f}.md`) ? "x" : " "}] ${sd}/${f}.md`), "");
    if (task.status === "review_pending") L.push("## Pendiente", "", "- [ ] Smoke test humano (por eso no pasa a `done` automáticamente)", "");
  }
  if (!passed) L.push("## Detalle del fallo", "", "```", String(last?.failureOutput || "").slice(0, 2000), "```", "");
  writeFileSync(`${PDIR}/review_${task.name}.md`, L.join("\n") + "\n");
}

// Memoria de ejecución: impl_<name>.md (append), current.md (snapshot), history.md (append), review_<name>.md.
function writeProgress(task, state, branch) {
  mkdirSync(PDIR, { recursive: true });
  const attempts = state.tasks[task.id]?.attempts ?? [];
  const ts = new Date().toISOString();
  const agent = process.env.HARNESS_AGENT || "claude";
  const table = attemptsTable(attempts);

  const impl = `${PDIR}/impl_${task.name}.md`;
  const prior = existsSync(impl) ? readFileSync(impl, "utf8") : `# Implementación · ${task.id} · ${task.title}\n`;
  writeFileSync(impl, `${prior}\n## ${ts} — estado: ${task.status}\n\n- agente: ${agent} · rama: \`${branch}\` · intentos: ${attempts.length}\n\n${table}\n`);

  const next = task.status === "review_pending" ? `Revisar el diff del commit \`feat(${task.name})\` y cerrar con \`node .harness/spec.mjs done ${task.id}\` (o \`git revert\` para descartarlo).`
    : task.status === "blocked" ? `Revisar \`${impl}\`, ajustar spec o repo y reintentar.`
    : "Feature cerrada. Continúa con la siguiente en cola.";
  writeFileSync(`${PDIR}/current.md`, [`# Sesión actual`, "",
    `Feature: **${task.id} · ${task.name}** — estado: \`${task.status}\`.`, "",
    `- agente: ${agent}`, `- rama: \`${branch}\``, `- intentos: ${attempts.length}`, "",
    "## Siguiente acción", "", `- ${next}`, "", "## Último resultado", "", table, ""].join("\n"));

  const hist = `${PDIR}/history.md`;
  const h0 = existsSync(hist) ? readFileSync(hist, "utf8") : "# Historial de sesiones\n";
  writeFileSync(hist, `${h0}\n## ${ts} — #${task.id} ${task.name} → ${task.status}\n- ${attempts.length} intento(s) · agente ${agent}\n`);

  writeReview(task, attempts);

  try { sh(`git add ${PDIR} spec.json`); sh(`git commit -q -m "docs(progress): #${task.id} ${task.name} → ${task.status}" -- ${PDIR} spec.json`); } catch {}
}

async function main() {
  const spec = loadSpec();
  const state = loadState();
  const maxAttempts = spec.rules?.max_attempts ?? 3;
  const queue = spec.features.filter(consumable).sort((a, b) => (PRI[a.priority] ?? 9) - (PRI[b.priority] ?? 9));

  if (DRY) {
    console.log(`Cola (aprobadas y pendientes): ${queue.length}`);
    queue.forEach((f) => console.log(`  - [${f.priority}] ${f.id} ${f.name}${f.sdd ? "" : " (sdd:false)"}`));
    const waiting = spec.features.filter((f) => f.sdd && f.status === "spec_ready" && !f.spec_approved);
    if (waiting.length) console.log(`Esperando aprobación: ${waiting.map((f) => f.id).join(", ")}`);
    return;
  }

  const dirty = sh("git status --porcelain").trim();
  if (dirty) {
    console.error("⚠️  Working tree no limpio. Commitea o descarta los cambios antes de correr el harness:\n" + dirty);
    process.exit(1);
  }
  const branch = sh("git rev-parse --abbrev-ref HEAD").trim(); // se trabaja EN ESTA rama (sin ramas por feature)

  for (const task of queue) {
    let lastFailure = null, ok = false;
    task.status = "in_progress";
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      const t0 = Date.now();
      const prompt = lastFailure ? buildRetryPrompt(task, lastFailure, attempt) : buildInitialPrompt(task);
      const run = runAgent(prompt, { write: true });
      const verdict = await runGates(task);
      record(state, task.id, { attempt, verdict, tts: (Date.now() - t0) / 1000, cost: run.cost });
      if (verdict.passed) {
        sh(`git add -A && git commit -q -m "feat(${task.name}): ${task.objective ?? task.name}"`);
        task.status = task.sdd === false ? "done" : "review_pending";
        if (task.status === "review_pending") console.log(`Feature ${task.id} commiteada en '${branch}' → review_pending. Revisa el diff y cierra con: spec.mjs done ${task.id}`);
        ok = true; break;
      }
      lastFailure = verdict.failureOutput;
      sh("git reset -q --hard HEAD"); sh("git clean -fdq"); // descarta el intento fallido (no toca lo ignorado)
    }
    if (!ok) { task.status = "blocked"; console.error(`⚠️  BLOCKED: ${task.id} ${task.name} falló ${maxAttempts} veces.`); console.error(state.tasks[task.id]?.attempts.at(-1)?.verdict?.failureOutput ?? ""); }
    saveState(state);
    writeFileSync("spec.json", JSON.stringify(spec, null, 2));
    writeProgress(task, state, branch);
  }
}

function record(state, id, entry) { state.tasks[id] ??= { attempts: [] }; state.tasks[id].attempts.push(entry); }
main().catch((e) => { console.error("Harness error:", e); process.exit(1); });
