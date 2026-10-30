import { createBashToolDefinition as createPiBashToolDefinition } from "@earendil-works/pi-coding-agent";
/**
 * Guarded bash tool: blocks improvised host-side nmap/ping/docker probes.
 * Agents must use the skill wrapper scripts documented in their skill.
 */
const STAGE_SCRIPT = {
    discovery: /skills\/discovery\/scripts\/(nmap-discovery|parse-open-ports)\.sh/,
    vuln: /skills\/vuln-analysis\/scripts\/(nmap-vuln|parse-vuln-output)\.sh/,
    exploit: /skills\/exploitation\/scripts\/(nmap-exploit|parse-exploit-output)\.sh/,
};
const SETUP_ALLOWED = /^(mkdir|export|printenv|NMAP_|OPEN_PORTS=|TARGET=|OUTPUT_DIR=|echo|cat|printf|test|true|false|cd|pwd|if|fi|then|else)\b/;
export function createLabBashTool(cwd, stage) {
    const allowedScript = STAGE_SCRIPT[stage];
    return createPiBashToolDefinition(cwd, {
        spawnHook: ({ command, cwd: shellCwd, env }) => {
            const rejection = validateLabCommand(command, stage, allowedScript);
            if (rejection) {
                return {
                    command: `printf '%s\\n' ${shellQuote(rejection)} >&2; exit 1`,
                    cwd: shellCwd,
                    env,
                };
            }
            return { command, cwd: shellCwd, env };
        },
    });
}
function validateLabCommand(command, stage, allowedScript) {
    const trimmed = command.trim();
    if (!trimmed) {
        return null;
    }
    const lines = trimmed.split("\n").map((line) => line.trim()).filter(Boolean);
    const substantive = lines.filter((line) => !line.startsWith("#"));
    if (substantive.every((line) => isAllowedLine(line, stage, allowedScript))) {
        return null;
    }
    if (/\bnmap\b/i.test(trimmed) && !allowedScript.test(trimmed)) {
        return [
            "BLOCKED: bare host nmap is not allowed in this deployment.",
            `Read the ${stage} skill and use its wrapper scripts instead.`,
        ].join(" ");
    }
    if (/\bping\b/i.test(trimmed)) {
        return ["BLOCKED: ping is not needed. Follow your skill's workflow."].join(" ");
    }
    if (/\bdocker\s+(network|inspect|ps)\b/i.test(trimmed)) {
        return [
            "BLOCKED: docker network inspection is not needed.",
            "Follow your skill's wrapper scripts for scanner networking.",
        ].join(" ");
    }
    if (/\bdocker\s+run\b.*\bnmap\b/i.test(trimmed) && !allowedScript.test(trimmed)) {
        return [
            "BLOCKED: run nmap only through the skill wrapper scripts.",
            `Read the ${stage} skill for the correct workflow.`,
        ].join(" ");
    }
    return null;
}
function isAllowedLine(line, stage, allowedScript) {
    if (allowedScript.test(line)) {
        return true;
    }
    if (SETUP_ALLOWED.test(line)) {
        return true;
    }
    if (/^bash\s+skills\/(discovery|vuln-analysis|exploitation)\/scripts\//.test(line)) {
        return allowedScript.test(line);
    }
    if (/^\$/.test(line)) {
        return false;
    }
    if (/^OPEN_PORTS=\$\(/.test(line) && line.includes("parse-open-ports.sh")) {
        return true;
    }
    return !/\bnmap\b|\bping\b|\bdocker\b/i.test(line);
}
function shellQuote(value) {
    return `'${value.replace(/'/g, `'\"'\"'`)}'`;
}
