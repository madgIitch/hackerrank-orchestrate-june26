import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { execSync } from "node:child_process";
import { runAgent, extractJson } from "./runner.mjs";
import { readInterview, writeInterview, renderInterview, interviewPath, answersHash } from "./interview.mjs";

const SPEC = "spec.json";
const SPECDIR = "spec";
const DIMENSIONS = [
  "data_model", "error_states", "edge_cases", "auth_secrets",
  "external_contracts", "ui_states", "rollback_compat", "tests",
];

const sh = (cmd) => execSync(cmd, { stdio: "pipe", encoding: "utf8" });
const tryCommit = (paths, msg) => { try { sh(`git add ${paths}`); sh(`git commit -q -m ${JSON.stringify(msg)} -- ${paths}`); } catch {} };
const loadSpec = () => JSON.parse(readFileSync(SPEC, "utf8"));
const saveSpec = (s) => writeFileSync(SPEC, JSON.stringify(s, null, 2) + "\n");
const ask = (prompt) => extractJson(runAgent(prompt, { write: false }).text);

function normalizeList(v) {
  if (Array.isArray(v)) return v.map((x) => String(x).trim()).filter(Boolean);
  if (!v) return [];
  return String(v).split(/\n/).map((s) => s.replace(/^[-*]\s*/, "").trim()).filter(Boolean);
}

function parseNumberedSection(md, heading) {
  if (!md) return [];
  const section = (md.split(`## ${heading}`)[1] || "").split("\n## ")[0];
  const items = [];
  let current = null;
  for (const rawLine of section.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const numbered = line.match(/^\d+\.\s+(.*)$/);
    if (numbered) {
      if (current) items.push(current.trim());
      current = numbered[1];
    } else if (current) {
      current += ` ${line}`;
    }
  }
  if (current) items.push(current.trim());
  return items;
}

function parseScopeSection(md) {
  if (!md) return [];
  const section = (md.split("## Scope propuesto")[1] || "").split("\n## ")[0];
  return section.split("\n")
    .map((l) => l.trim().match(/^-\s+`?([^`]+)`?$/)?.[1]?.trim())
    .filter(Boolean);
}

function normalizeGuesses(v) {
  const guesses = Array.isArray(v) ? v : (v ? [v] : []);
  return guesses.map((g) => {
    if (typeof g === "string") return g;
    if (g && typeof g === "object") {
      const vals = ["question", "point", "text", "reason"].map((k) => g[k]).filter((x) => typeof x === "string" && x.trim());
      return vals.length ? vals.join(" — ") : JSON.stringify(g);
    }
    return String(g);
  }).map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean);
}

// Garantiza que las 8 dimensiones existan (un dim ausente = sin cubrir, con pregunta).
function fillDims(dims = {}) {
  const out = {};
  for (const d of DIMENSIONS) out[d] = dims[d] ?? { addressed: false, question: "Aclara esta dimensión (el agente no la cubrió)." };
  return out;
}

function feature(spec, id) {
  const f = spec.features.find((x) => String(x.id) === String(id));
  if (!f) throw new Error(`Feature ${id} no existe`);
  return f;
}
function dimList(intv, dims) {
  if (!intv?.dimensions) return [];
  return dims.filter((d) => intv.dimensions[d] && (intv.dimensions[d].notes || intv.dimensions[d].addressed))
    .map((d) => `- **${d}:** ${intv.dimensions[d].notes || "ok"}`);
}

// Escribe el spec aprobado a spec/<id>-<name>/ con requirements.md, design.md y tasks.md.
function writeSpecFolder(f, intv) {
  const dir = `${SPECDIR}/${f.id}-${f.name}`;
  mkdirSync(dir, { recursive: true });
  const meta = `- name: \`${f.name}\` · priority: ${f.priority ?? "-"} · sdd: ${f.sdd === false ? "false" : "true"}\n- aprobado por: ${f.approved_by} · ${f.approved_at}`;

  const req = [`# ${f.id} · ${f.title} — Requisitos`, "", meta, "", "## Contexto", "", f.description ?? "", ""];
  if (f.acceptance?.length) { req.push("## Requisitos funcionales", ""); f.acceptance.forEach((a, i) => req.push(`R${i + 1}. ${a}`)); req.push(""); }
  const cons = dimList(intv, ["error_states", "auth_secrets", "rollback_compat"]);
  if (cons.length) req.push("## Restricciones", "", ...cons, "");
  writeFileSync(`${dir}/requirements.md`, req.join("\n") + "\n");

  const des = [`# ${f.id} · ${f.title} — Diseño`, ""];
  if (f.scope?.length) des.push("## Scope (archivos que puede tocar)", "", ...f.scope.map((s) => `- \`${s}\``), "");
  const dd = dimList(intv, ["data_model", "external_contracts", "edge_cases", "ui_states"]);
  if (dd.length) des.push("## Enfoque", "", ...dd, "");
  if (intv?.answers && Object.keys(intv.answers).length) des.push("## Decisiones de la entrevista", "", ...Object.entries(intv.answers).map(([k, v]) => `- **${k}:** ${v}`), "");
  writeFileSync(`${dir}/design.md`, des.join("\n") + "\n");

  const tk = [`# ${f.id} · ${f.title} — Tareas`, "", "Checklist de implementación. El agente marca [x] al completar; los gates verifican.", ""];
  if (f.acceptance?.length) f.acceptance.forEach((a, i) => tk.push(`- [ ] (T${i + 1}) ${a}  ↔ R${i + 1}`));
  else tk.push(`- [ ] ${f.description ?? f.title}`);
  tk.push("- [ ] Tests que cubran los criterios de aceptación");
  writeFileSync(`${dir}/tasks.md`, tk.join("\n") + "\n");
  return dir;
}

function appendOnce(path, marker, lines) {
  mkdirSync("docs", { recursive: true });
  const current = existsSync(path) ? readFileSync(path, "utf8") : "";
  if (current.includes(marker)) return;
  writeFileSync(path, `${current.trimEnd()}\n\n${lines.join("\n")}\n`);
}

// Alimenta docs/ con contexto durable al aprobar specs. Esto evita que docs/ quede
// como placeholder eterno y convierte cada aprobación en memoria reutilizable.
function writeDocsFromSpec(f, intv) {
  const marker = `<!-- harness:${f.id} -->`;
  const title = f.title ?? f.name ?? f.id;
  const scope = (f.scope ?? []).map((s) => `  - \`${s}\``);
  const approach = dimList(intv, ["data_model", "external_contracts", "edge_cases", "ui_states"]);
  appendOnce("docs/ARCHITECTURE.md", marker, [
    marker,
    `## ${f.id} · ${title}`,
    "",
    f.description ?? "",
    "",
    "### Scope aprobado",
    "",
    ...(scope.length ? scope : ["  - (sin scope declarado)"]),
    "",
    ...(approach.length ? ["### Contexto técnico", "", ...approach, ""] : []),
  ]);

  const decisions = dimList(intv, ["auth_secrets", "rollback_compat", "tests"]);
  appendOnce("docs/DECISIONS.md", marker, [
    marker,
    `## ${new Date().toISOString().slice(0, 10)} · ${f.id} aprobado`,
    "",
    `Contexto: se aprobó el spec \`${f.id}\` (${title}).`,
    "",
    ...(decisions.length ? ["Decisiones registradas:", "", ...decisions] : ["Decisión: implementar según el spec aprobado."]),
    "",
    "Consecuencia: futuras features deben respetar este contrato salvo nuevo ADR.",
  ]);
}

function interview(id) {
  const spec = loadSpec();
  const f = feature(spec, id);
  if (f.sdd === false) { console.log(`Feature ${id} es sdd:false → sin entrevista. Apruébala: spec.mjs approve ${id}`); return; }
  const prior = readInterview(f);
  const res = ask([
    "Eres entrevistador de especificaciones (SDD). NO escribas código. Lee docs/ si existe. Devuelve SOLO JSON.",
    "Feature:", JSON.stringify({ id: f.id, name: f.name, title: f.title, description: f.description, acceptance: f.acceptance ?? [] }),
    `Respuestas previas del dev: ${JSON.stringify(prior.answers)}`,
    `Para CADA dimensión [${DIMENSIONS.join(", ")}] decide si la feature la deja resuelta.`,
    'Si NO, genera una pregunta concreta de alto valor (NADA de relleno tipo "¿qué color?").',
    'Propón "scope" (paths que puede tocar) y un "acceptance" refinado y testable.',
    'Formato EXACTO: {"dimensions":{"<dim>":{"addressed":bool,"notes":"...","question":"...si addressed=false"}},"scope":[],"acceptance":[]}',
  ].join("\n"));
  res.dimensions = fillDims(res.dimensions);
  writeInterview(f, renderInterview(f, res, prior.answers, []));
  const open = DIMENSIONS.filter((d) => !res.dimensions[d].addressed);
  if (open.length === 0) console.log(`Spec ${id}: dimensiones cubiertas de salida. Corre: spec.mjs answer ${id}`);
  else { console.log(`Entrevista en ${interviewPath(f)} — preguntas abiertas:`); open.forEach((d) => console.log(`  [${d}] ${res.dimensions[d].question}`)); console.log(`Responde los **R:** y corre: spec.mjs answer ${id}`); }
}

function answer(id) {
  const spec = loadSpec();
  const f = feature(spec, id);
  const prior = readInterview(f);
  const existingAC = parseNumberedSection(prior.md, "Acceptance propuesto");
  const existingScope = parseScopeSection(prior.md);
  const revised = ask([
    "Revisa esta spec integrando las respuestas del dev. NO escribas código. Devuelve SOLO JSON (mismo formato).",
    `Feature: ${JSON.stringify({ id: f.id, title: f.title, description: f.description })}`,
    `Cobertura previa: ${JSON.stringify(prior.dimensions)}`,
    `Respuestas del dev: ${JSON.stringify(prior.answers)}`,
    existingAC.length
      ? `Criterios de aceptación existentes (presérvalos salvo que una respuesta del dev los vuelva más precisos): ${JSON.stringify(existingAC)}`
      : "",
    existingScope.length
      ? `Scope existente (presérvalo salvo contradicción explícita): ${JSON.stringify(existingScope)}`
      : "",
    `Dimensiones: [${DIMENSIONS.join(", ")}]. Mismo formato JSON con dimensions/scope/acceptance.`,
  ].filter(Boolean).join("\n"));
  revised.dimensions = fillDims(revised.dimensions);
  const finalAcceptance = existingAC.length ? existingAC : normalizeList(revised.acceptance);
  const finalScope = existingScope.length ? existingScope : normalizeList(revised.scope);
  const adv = ask([
    "Eres QA de criterios de aceptación. Lista SOLO ambigüedades bloqueantes: casos donde no se puede decidir si el sistema PASA o FALLA sin una decisión de negocio adicional.",
    "NO reportes detalles internos de implementación, testIDs, props de componentes, librerías, estructura de carpetas ni configuración de CI si no cambian el comportamiento observable.",
    "SÍ reporta umbrales indefinidos, endpoints/rutas no especificadas, campos de request/response faltantes y comportamientos observables donde dos implementaciones razonables darían resultados distintos.",
    `Spec: ${JSON.stringify({ scope: finalScope, acceptance: finalAcceptance })}`,
    'Formato: {"guesses":["string"]} (vacío si no hay ninguno).',
  ].join("\n"));
  const guesses = normalizeGuesses(adv.guesses);
  const ready = DIMENSIONS.every((d) => revised.dimensions[d].addressed === true);
  writeInterview(f, renderInterview(f, { ...revised, scope: finalScope, acceptance: finalAcceptance }, prior.answers, guesses));
  if (!ready) {
    console.log(`Feature ${id} aún NO está lista — dimensiones sin cubrir:`);
    DIMENSIONS.filter((d) => !revised.dimensions[d].addressed).forEach((d) => console.log(`  [${d}] ${revised.dimensions[d].question ?? ""}`));
    if (guesses.length) console.log(`(${guesses.length} suposición(es) del implementador anotadas en el .md)`);
    return;
  }
  f.acceptance = finalAcceptance; f.scope = finalScope; f.status = "spec_ready";
  saveSpec(spec);
  console.log(`Feature ${id} → spec_ready (dimensiones cubiertas).`);
  if (guesses.length) { console.log("⚠️  Suposiciones del implementador a revisar antes de approve:"); guesses.forEach((g) => console.log(`  - ${g}`)); }
  console.log(`Aprueba con: spec.mjs approve ${id}`);
}

function forceReady(id) {
  const spec = loadSpec();
  const f = feature(spec, id);
  if (f.sdd === false) { console.log(`Feature ${id} es sdd:false; usa approve directo.`); return; }
  const prior = readInterview(f);
  const acceptance = parseNumberedSection(prior.md, "Acceptance propuesto");
  const scope = parseScopeSection(prior.md);
  if (!acceptance.length) throw new Error(`No hay "Acceptance propuesto" en ${interviewPath(f)}. Edita la entrevista o corre answer antes de force-ready.`);
  if (!scope.length) throw new Error(`No hay "Scope propuesto" en ${interviewPath(f)}. Edita la entrevista o corre answer antes de force-ready.`);
  f.acceptance = acceptance;
  f.scope = scope;
  f.status = "spec_ready";
  f.manual_spec_ready = true;
  f.manual_spec_ready_at = new Date().toISOString();
  f.manual_spec_ready_reason = "Dev override: Fase 0 marcada como suficientemente especificada pese a suposiciones pendientes.";
  saveSpec(spec);
  console.log(`Feature ${id} → spec_ready por override manual. Revisa y aprueba: spec.mjs approve ${id}`);
}

function approve(id) {
  const spec = loadSpec();
  const f = feature(spec, id);
  const by = process.env.USER || process.env.USERNAME || "dev";
  let intv = null;
  if (f.sdd !== false) {
    if (f.status !== "spec_ready") throw new Error(`Feature ${id} debe estar en spec_ready (está en ${f.status}). Completa la entrevista.`);
    intv = readInterview(f);
    f.answers_hash = answersHash(intv.answers);
  }
  f.spec_approved = true; f.approved_by = by; f.approved_at = new Date().toISOString();
  saveSpec(spec);
  const dir = writeSpecFolder(f, intv);
  writeDocsFromSpec(f, intv);
  tryCommit(`spec.json ${dir} docs`, `spec: approve #${f.id} ${f.name}`);
  console.log(`Feature ${id} aprobada por ${by}. Spec durable en ${dir}/ (requirements, design, tasks)`);
}

function done(id) {
  const spec = loadSpec();
  const f = feature(spec, id);
  if (f.status !== "review_pending") throw new Error(`Feature ${id} no está en review_pending (está en ${f.status}).`);
  f.status = "done"; saveSpec(spec);
  tryCommit("spec.json", `chore: #${f.id} ${f.name} → done`);
  console.log(`Feature ${id} → done. (Para descartarla en su lugar: git revert del commit feat(${f.name}).)`);
}

const [cmd, id] = process.argv.slice(2);
const cmds = { interview, answer, "force-ready": forceReady, approve, done };
if (!cmds[cmd] || !id) { console.log("Uso: node .harness/spec.mjs <interview|answer|force-ready|approve|done> <id>"); process.exit(1); }
cmds[cmd](id);
