import { spawnSync } from "node:child_process";

const AGENT = (process.env.HARNESS_AGENT || "claude").toLowerCase(); // "claude" | "codex"
const UNATTENDED = process.env.HARNESS_UNATTENDED === "1";
const IS_WIN = process.platform === "win32";
const TIMEOUT = Number(process.env.HARNESS_TIMEOUT_MS || 900000); // 15 min por corrida

const bin = (name) => process.env[`HARNESS_${name.toUpperCase()}_BIN`] || name;

// Lanza el CLI pasando el PROMPT POR STDIN (input), no como argumento:
//  - evita problemas de comillas/saltos de línea (sobre todo en Windows/cmd.exe);
//  - al cerrar stdin se entrega EOF, lo que evita el cuelgue conocido de `codex exec`
//    cuando lo invoca un proceso hijo no interactivo.
// shell:true en Windows resuelve los shims .cmd/.exe (cmd.exe usa PATHEXT).
function exec(name, args, prompt) {
  const cmd = bin(name);
  const res = spawnSync(cmd, args, {
    input: prompt, encoding: "utf8", shell: IS_WIN, timeout: TIMEOUT,
    maxBuffer: 64 * 1024 * 1024, stdio: ["pipe", "pipe", "inherit"],
  });
  if (res.error) {
    const U = name.toUpperCase();
    throw new Error(`No se pudo lanzar '${cmd}'. ¿Está en el PATH? Fija la ruta con HARNESS_${U}_BIN ` +
      `(p.ej. PowerShell: $env:HARNESS_${U}_BIN='C:\\ruta\\${cmd}.exe').\nDetalle: ${res.error.message}`);
  }
  if (res.status !== 0) throw new Error(`'${cmd}' salió con código ${res.status}:\n${res.stdout || ""}`);
  return res.stdout || "";
}

export function runAgent(prompt, { write = false } = {}) {
  return AGENT === "codex" ? runCodex(prompt, write) : runClaude(prompt, write);
}
function runClaude(prompt, write) {
  const tools = write ? "Edit,Write,Bash,Read,Grep,Glob" : "Read,Grep,Glob";
  const args = ["-p", "--output-format", "json", "--max-turns", String(write ? 30 : 8), "--allowedTools", tools];
  if (write && UNATTENDED) args.push("--dangerously-skip-permissions");
  const j = JSON.parse(exec("claude", args, prompt));
  return { text: j.result ?? "", cost: j.total_cost_usd ?? j.cost?.total_cost ?? null };
}
function runCodex(prompt, write) {
  const sandbox = write ? "workspace-write" : "read-only";
  const args = ["exec", "-s", sandbox];
  if (UNATTENDED || write) args.push("-c", "approval_policy='never'");
  args.push("-"); // '-' = leer el prompt completo desde stdin
  return { text: exec("codex", args, prompt).trim(), cost: null };
}

export function extractJson(text) {
  const clean = text.replace(/```json|```/g, "").trim();
  const a = clean.indexOf("{"), b = clean.lastIndexOf("}");
  if (a === -1 || b === -1) throw new Error("El agente no devolvió JSON:\n" + text.slice(0, 500));
  return JSON.parse(clean.slice(a, b + 1));
}
