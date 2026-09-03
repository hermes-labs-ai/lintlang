/** OpenCode 1.x post-tool adapter for LintLang. */

const SUPPORTED_SUFFIXES = new Set([".json", ".md", ".prompt", ".py", ".txt", ".yaml", ".yml"])
const EDIT_TOOLS = new Set(["edit", "multiedit", "patch", "write", "apply_patch"])
const MAX_FINDINGS = 8
const PINNED_VERSION = "0.5.2"

function pathsFrom(value) {
  if (!value || typeof value !== "object") return []
  const paths = []
  for (const key of ["filePath", "file_path", "path", "file"]) {
    if (typeof value[key] === "string") paths.push(value[key])
  }
  if (Array.isArray(value.files)) {
    for (const file of value.files) if (typeof file === "string") paths.push(file)
  }
  return paths
}

function candidatePaths(input, output) {
  return [...new Set([...pathsFrom(input.args), ...pathsFrom(output.metadata)])]
}

function formatResult(path, result) {
  if (result.input_error) return `LintLang could not scan ${path}: ${result.input_error}`
  const findings = result.structural_findings || []
  if (!findings.length) return ""
  const lines = [
    `LintLang found ${findings.length} issue(s) in ${path} (verdict: ${result.verdict || "unknown"}).`,
    "Repair the applicable findings, then keep the user's requested behavior intact:",
  ]
  for (const finding of findings.slice(0, MAX_FINDINGS)) {
    const code = finding.code || finding.pattern_id || "LintLang"
    const severity = String(finding.severity || "unknown").toUpperCase()
    let line = `- [${severity} ${code}] ${finding.location || "file"}: ${finding.description || "Issue detected."}`
    if (finding.suggestion) line += ` Suggested repair: ${finding.suggestion}`
    lines.push(line)
  }
  if (findings.length > MAX_FINDINGS) lines.push(`- ${findings.length - MAX_FINDINGS} additional finding(s) omitted; run \`lintlang scan -- ${path}\` for all details.`)
  return lines.join("\n")
}

async function scan(ctx, path) {
  const command = `lintlang scan --format json -- ${path}`
  try {
    const result = await ctx.$`lintlang --version`.quiet().nothrow().text()
    if (result.trim() !== `lintlang ${PINNED_VERSION}`) {
      return `LintLang could not check ${path} because lintlang ${PINNED_VERSION} is not available. Install it with \`pipx install lintlang==${PINNED_VERSION}\`.`
    }
    const output = await ctx.$`lintlang scan --format json -- ${path}`.quiet().nothrow().text()
    const parsed = JSON.parse(output)
    if (!Array.isArray(parsed) || !parsed[0]) throw new Error("LintLang returned no file result")
    return formatResult(path, parsed[0])
  } catch (error) {
    return `LintLang could not check ${path}: ${error instanceof Error ? error.message : String(error)}. Run \`${command}\` directly for diagnostics.`
  }
}

export const LintLang = async (ctx) => ({
  "tool.execute.after": async (input, output) => {
    if (!EDIT_TOOLS.has(input.tool)) return
    const paths = candidatePaths(input, output)
    for (const rawPath of paths) {
      const path = String(rawPath)
      if (!SUPPORTED_SUFFIXES.has(path.slice(path.lastIndexOf(".")).toLowerCase())) continue
      const context = await scan(ctx, path)
      if (context) output.output = `${output.output || ""}\n\n${context}`.trim()
    }
  },
})

export default LintLang
