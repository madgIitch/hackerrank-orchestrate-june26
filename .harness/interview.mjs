// Entrevistas como Markdown editable + parseable. El dev responde en líneas **R:**.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { createHash } from "node:crypto";

const IDIR = ".harness/interviews";
export const interviewPath = (f) => `${IDIR}/${f.id}-${f.name}.md`;
export const answersHash = (answers) => "sha256:" + createHash("sha256").update(JSON.stringify(answers)).digest("hex");
const stableKey = (prefix, text) => `${prefix}-${createHash("sha1").update(String(text)).digest("hex").slice(0, 10)}`;

function normalizeList(v) {
  if (Array.isArray(v)) return v.map((x) => String(x).trim()).filter(Boolean);
  if (!v) return [];
  return String(v).split(/\n/).map((s) => s.replace(/^[-*]\s*/, "").trim()).filter(Boolean);
}

// Extrae { dim/clave: respuesta } de los bloques "### [clave] ...\n**R:** ...".
export function parseAnswers(md) {
  const out = {};
  const re = /### \[([^\]]+)\][^\n]*\n+\*\*R:\*\*\s*([\s\S]*?)(?=\n### |\n## )/g;
  let m;
  while ((m = re.exec(md))) { const a = m[2].trim(); if (a) out[m[1]] = a; }
  return out;
}
// Extrae cobertura { dim: {addressed, notes} } de los bullets "- ✅/❓ dim — nota".
export function parseDimensions(md) {
  const out = {};
  const after = (md.split("## Cobertura de dimensiones")[1] || "").split("\n## ")[0];
  const re = /^- (✅|❓) (\w+)\s*—\s*(.*)$/gm;
  let m;
  while ((m = re.exec(after))) out[m[2]] = { addressed: m[1] === "✅", notes: m[3].trim() };
  return out;
}
export function readInterview(f) {
  const p = interviewPath(f);
  if (!existsSync(p)) return { answers: {}, dimensions: {} };
  const md = readFileSync(p, "utf8");
  return { answers: parseAnswers(md), dimensions: parseDimensions(md), md };
}
export function writeInterview(f, md) { mkdirSync(IDIR, { recursive: true }); writeFileSync(interviewPath(f), md); }

// Renderiza la entrevista. res = { dimensions, scope, acceptance } del agente.
export function renderInterview(f, res, priorAnswers = {}, guesses = []) {
  const dims = res.dimensions || {};
  const open = Object.keys(dims).filter((d) => !dims[d].addressed);
  const ready = open.length === 0; // readiness = SOLO cobertura de dimensiones (los guesses no bloquean)
  const title = f.title ?? f.name ?? f.id;
  const L = [`# Entrevista · ${f.id} · ${title}`, "", `- name: \`${f.name ?? title}\``];
  L.push(ready ? `- estado: **dimensiones cubiertas** → aprueba con \`spec.mjs approve ${f.id}\``
               : `- estado: responde los **R:** y corre \`spec.mjs answer ${f.id}\``, "");
  if (open.length) {
    L.push("## Preguntas abiertas", "", "> Escribe tu respuesta en la línea `**R:**` de cada bloque.", "");
    open.forEach((d) => L.push(`### [${d}] ${dims[d].question ?? "Aclara esta dimensión"}`, "", `**R:** ${priorAnswers[d] ?? ""}`, ""));
  }
  if (guesses.length) {
    L.push("## Suposiciones del implementador", "", "> No bloquean la aprobación, pero conviene revisarlas. Puedes responder en su `**R:**` para fijarlas en el diseño.", "");
    guesses.forEach((g) => {
      const key = stableKey("adv", g);
      L.push(`### [${key}] ${g}`, "", `**R:** ${priorAnswers[key] ?? ""}`, "");
    });
  }
  if (ready) {
    const recorded = Object.entries(priorAnswers).filter(([k]) => !k.startsWith("adv"));
    if (recorded.length) { L.push("## Decisiones registradas", ""); recorded.forEach(([k, v]) => L.push(`### [${k}] (resuelto)`, "", `**R:** ${v}`, "")); }
  }
  L.push("## Cobertura de dimensiones", "");
  for (const [d, v] of Object.entries(dims)) L.push(`- ${v.addressed ? "✅" : "❓"} ${d} — ${v.notes || (v.addressed ? "ok" : "pendiente")}`);
  L.push("", "## Scope propuesto", "", ...normalizeList(res.scope).map((s) => `- \`${s}\``), "");
  L.push("## Acceptance propuesto", "", ...normalizeList(res.acceptance).map((a, i) => `${i + 1}. ${a}`), "");
  return L.join("\n") + "\n";
}
