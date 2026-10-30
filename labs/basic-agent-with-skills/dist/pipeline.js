import { mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { AuthStorage, createAgentSession, DefaultResourceLoader, defineTool, loadSkillsFromDir, ModelRegistry, SessionManager, SettingsManager, } from "@earendil-works/pi-coding-agent";
import { Type } from "@earendil-works/pi-ai";
import { createLabBashTool } from "./lab-bash.js";
/* ---------------------------------------------------------------------------
 * Stage schemas (the structured artifact each agent emits)
 * ------------------------------------------------------------------------- */
const openPortSchema = Type.Object({
    port: Type.Number(),
    protocol: Type.String(),
    service: Type.String(),
    version: Type.Optional(Type.String()),
    notes: Type.Optional(Type.String()),
});
export const discoverySchema = Type.Object({
    target: Type.String(),
    scanned_at: Type.String(),
    scan_type: Type.String(),
    open_ports: Type.Array(openPortSchema),
    summary: Type.String(),
});
const vulnerabilitySchema = Type.Object({
    port: Type.Number(),
    service: Type.String(),
    version: Type.Optional(Type.String()),
    nse_script: Type.String(),
    severity: Type.String(),
    evidence: Type.String(),
    cve: Type.Optional(Type.String()),
});
export const vulnSchema = Type.Object({
    target: Type.String(),
    analyzed_at: Type.String(),
    vulnerabilities: Type.Array(vulnerabilitySchema),
    summary: Type.String(),
});
const exploitAttemptSchema = Type.Object({
    port: Type.Number(),
    service: Type.String(),
    technique: Type.String(),
    outcome: Type.String(),
    evidence: Type.String(),
    cve: Type.Optional(Type.String()),
});
export const exploitSchema = Type.Object({
    target: Type.String(),
    exploited_at: Type.String(),
    exploit_attempts: Type.Array(exploitAttemptSchema),
    summary: Type.String(),
});
const execFileAsync = promisify(execFile);
const PI_PROVIDER = "requesty";
const DEFAULT_MODEL = "openai/gpt-5-mini";
const DEFAULT_BASE_URL = "https://router.requesty.ai/v1";
const STAGE_LABELS = {
    discovery: "Discovery",
    vuln: "Vulnerability Analysis",
    exploit: "Exploitation",
};
const STAGE_SPECS = {
    discovery: {
        key: "discovery",
        skillName: "discovery",
        emitToolName: "emit_discovery",
        emitToolLabel: "Emit Discovery",
        emitToolDescription: "Submit the structured discovery result (open ports with services/versions) for the authorized target.",
        schema: discoverySchema,
    },
    vuln: {
        key: "vuln",
        skillName: "vuln-analysis",
        emitToolName: "emit_vuln_analysis",
        emitToolLabel: "Emit Vulnerability Analysis",
        emitToolDescription: "Submit the structured vulnerability-analysis result (evidence-backed vulnerabilities from NSE) for the authorized target.",
        schema: vulnSchema,
    },
    exploit: {
        key: "exploit",
        skillName: "exploitation",
        emitToolName: "emit_exploitation",
        emitToolLabel: "Emit Exploitation",
        emitToolDescription: "Submit the structured exploitation result (NSE-only exploit attempts with outcomes and evidence) for the authorized target.",
        schema: exploitSchema,
    },
};
/* ---------------------------------------------------------------------------
 * Public entry point
 * ------------------------------------------------------------------------- */
export async function runPipeline(options) {
    const emit = options.onEvent ?? (() => { });
    const model = options.model ?? DEFAULT_MODEL;
    const baseUrl = options.baseUrl ?? process.env.BASE_URL ?? DEFAULT_BASE_URL;
    const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
    await loadScanLabConfig(appRoot);
    const scanTarget = normalizeScanTarget(options.target);
    await preflightLabTarget((phase, text) => emit({ type: "trace", stage: "discovery", phase, text }));
    const skills = localSkills(appRoot);
    const runtimeRoot = await mkdtemp(path.join(tmpdir(), "basic-agent-skill-"));
    const agentDir = path.join(runtimeRoot, "pi-auth");
    const scanOutputDir = path.join(runtimeRoot, "nmap-output");
    await mkdir(agentDir, { recursive: true });
    await mkdir(scanOutputDir, { recursive: true });
    const authStorage = AuthStorage.create(path.join(agentDir, "auth.json"));
    const apiKey = process.env.REQUESTY_API_KEY;
    if (apiKey) {
        authStorage.setRuntimeApiKey(PI_PROVIDER, apiKey);
    }
    const modelRegistry = ModelRegistry.create(authStorage, path.join(agentDir, "models.json"));
    modelRegistry.registerProvider(PI_PROVIDER, {
        name: "Requesty",
        baseUrl,
        apiKey: "REQUESTY_API_KEY",
        api: "openai-completions",
        authHeader: true,
        models: [
            {
                id: model,
                name: model,
                api: "openai-completions",
                reasoning: false,
                input: ["text"],
                cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                contextWindow: 128000,
                maxTokens: 8192,
                compat: {
                    supportsStore: false,
                    supportsDeveloperRole: false,
                    supportsReasoningEffort: false,
                },
            },
        ],
    });
    const resolvedModel = modelRegistry.find(PI_PROVIDER, model);
    if (!resolvedModel) {
        throw new Error(`model not registered: ${PI_PROVIDER}/${model}`);
    }
    const settingsManager = SettingsManager.inMemory({
        compaction: { enabled: true, reserveTokens: 8000, keepRecentTokens: 16000 },
        retry: { enabled: true, maxRetries: 2 },
    });
    const ctx = {
        target: scanTarget,
        skills,
        authStorage,
        modelRegistry,
        model: resolvedModel,
        settingsManager,
        scanOutputDir,
        agentDir,
        emit,
    };
    try {
        const discovery = (await runStage(STAGE_SPECS.discovery, ctx, {}));
        const vuln = (await runStage(STAGE_SPECS.vuln, ctx, { discovery }));
        const exploit = (await runStage(STAGE_SPECS.exploit, ctx, { discovery, vuln }));
        const report = mergeReport(scanTarget, discovery, vuln, exploit);
        emit({ type: "pipeline_end", report });
        return report;
    }
    finally {
        await rm(runtimeRoot, { recursive: true, force: true });
    }
}
async function runStage(spec, ctx, prior) {
    ctx.emit({ type: "stage_start", stage: spec.key, label: STAGE_LABELS[spec.key] });
    const trace = (phase, text) => ctx.emit({ type: "trace", stage: spec.key, phase, text });
    trace("SYS", `Starting ${STAGE_LABELS[spec.key]} agent for target ${ctx.target}`);
    trace("SYS", `Skill: ${spec.skillName} | output dir: ${ctx.scanOutputDir}`);
    const stageSkill = ctx.skills.find((skill) => skill.name === spec.skillName);
    if (!stageSkill) {
        const error = `skill not found: ${spec.skillName}`;
        trace("SYS", error);
        ctx.emit({ type: "stage_end", stage: spec.key, status: "error", error });
        throw new Error(error);
    }
    let artifact;
    const emitTool = defineTool({
        name: spec.emitToolName,
        label: spec.emitToolLabel,
        description: spec.emitToolDescription,
        promptSnippet: `${spec.emitToolName}: submit the final structured ${spec.key} result.`,
        parameters: spec.schema,
        async execute(_toolCallId, params) {
            artifact = params;
            ctx.emit({ type: "stage_output", stage: spec.key, output: params });
            return {
                content: [{ type: "text", text: `${STAGE_LABELS[spec.key]} result accepted.` }],
                details: {},
            };
        },
    });
    const resourceLoader = new DefaultResourceLoader({
        cwd: process.cwd(),
        agentDir: ctx.agentDir,
        settingsManager: ctx.settingsManager,
        skillsOverride: (current) => ({
            // Each agent sees ONLY its own skill.
            skills: [stageSkill],
            diagnostics: current.diagnostics,
        }),
        systemPromptOverride: () => systemPrompt(spec, ctx.scanOutputDir, ctx.target),
    });
    await resourceLoader.reload();
    const { session } = await createAgentSession({
        cwd: process.cwd(),
        agentDir: ctx.agentDir,
        authStorage: ctx.authStorage,
        modelRegistry: ctx.modelRegistry,
        model: ctx.model,
        thinkingLevel: "off",
        tools: ["bash", "read", "ls", "find", "grep", spec.emitToolName],
        customTools: [emitTool, createLabBashTool(process.cwd(), spec.key)],
        resourceLoader,
        sessionManager: SessionManager.inMemory(process.cwd()),
        settingsManager: ctx.settingsManager,
    });
    attachTrace(session, spec, trace);
    try {
        await session.prompt(userPrompt(spec, ctx.target, ctx.scanOutputDir, prior));
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        trace("SYS", `Stage error: ${message}`);
        ctx.emit({ type: "stage_end", stage: spec.key, status: "error", error: message });
        session.dispose();
        throw error;
    }
    session.dispose();
    if (artifact === undefined) {
        const error = `${STAGE_LABELS[spec.key]} agent did not call ${spec.emitToolName} with a structured result.`;
        trace("SYS", error);
        ctx.emit({ type: "stage_end", stage: spec.key, status: "error", error });
        throw new Error(error);
    }
    ctx.emit({ type: "stage_end", stage: spec.key, status: "done" });
    return artifact;
}
/* ---------------------------------------------------------------------------
 * Trace: turn session events into pipeline "trace" events
 * ------------------------------------------------------------------------- */
function attachTrace(session, spec, trace) {
    const bashLineCounts = new Map();
    let assistantBuffer = "";
    const flushAssistant = () => {
        const lines = assistantBuffer.split("\n");
        assistantBuffer = lines.pop() ?? "";
        for (const line of lines) {
            const text = line.trim();
            if (text) {
                trace("AGENT", text);
            }
        }
    };
    session.subscribe((event) => {
        if (event.type === "message_update") {
            const update = event.assistantMessageEvent;
            if (update?.type === "text_delta" && update.delta) {
                assistantBuffer += update.delta;
                if (assistantBuffer.includes("\n")) {
                    flushAssistant();
                }
            }
            return;
        }
        if (event.type === "tool_execution_start") {
            // Flush any pending assistant text before the tool line.
            if (assistantBuffer.trim()) {
                trace("AGENT", assistantBuffer.trim());
                assistantBuffer = "";
            }
            const args = isRecord(event.args) ? event.args : {};
            if (event.toolName === "bash") {
                const command = stringValue(args.command) ?? stringValue(args.cmd) ?? "(command unavailable)";
                trace("TOOL", `$ ${command}`);
            }
            else if (event.toolName === "read") {
                const file = stringValue(args.file) ?? stringValue(args.path) ?? "(path unavailable)";
                trace("READ", file);
            }
            else if (event.toolName === spec.emitToolName) {
                trace("REPORT", `emitting ${spec.key} result`);
            }
            else if (event.toolName === "grep" || event.toolName === "find" || event.toolName === "ls") {
                trace("TOOL", `${event.toolName} ${compactArgs(args)}`);
            }
            return;
        }
        if (event.type === "tool_execution_update" && event.toolName === "bash") {
            const id = String(event.toolCallId);
            const text = extractToolText(event.partialResult);
            if (!text) {
                return;
            }
            const lines = text.split("\n");
            while (lines.length > 0 && lines[lines.length - 1] === "") {
                lines.pop();
            }
            const seen = bashLineCounts.get(id) ?? 0;
            for (const line of lines.slice(seen)) {
                trace("OUT", line);
            }
            bashLineCounts.set(id, lines.length);
            return;
        }
        if (event.type === "tool_execution_end") {
            const id = String(event.toolCallId);
            bashLineCounts.delete(id);
            const status = event.isError ? "failed" : "done";
            if (event.toolName === "bash") {
                // Final flush of any bash output not already streamed.
                const text = extractToolText(event.result);
                if (text && (bashLineCounts.get(id) ?? 0) === 0) {
                    for (const line of text.split("\n")) {
                        if (line.trim()) {
                            trace("OUT", line);
                        }
                    }
                }
                trace("RESULT", `bash ${status}`);
            }
            else if (event.toolName === "read") {
                trace("RESULT", `read ${status}`);
            }
            else if (event.toolName === spec.emitToolName) {
                trace("RESULT", `${spec.key} result ${status}`);
            }
            return;
        }
    });
}
/* ---------------------------------------------------------------------------
 * Prompts — orchestration only; all scan workflow lives in skills
 * ------------------------------------------------------------------------- */
function defaultScanTarget() {
    return process.env.SCAN_TARGET?.trim() || "metasploitable";
}
function normalizeScanTarget(target) {
    const labTarget = defaultScanTarget();
    const trimmed = target.trim();
    if (!trimmed || trimmed === labTarget || /^172\.(1[6-9]|2\d|3[01])\./.test(trimmed)) {
        return labTarget;
    }
    return trimmed;
}
async function preflightLabTarget(trace) {
    const labTarget = defaultScanTarget();
    try {
        const { stdout } = await execFileAsync("docker", [
            "ps",
            "--filter",
            `name=^${labTarget}$`,
            "--format",
            "{{.Names}}",
        ]);
        if (!stdout.trim().includes(labTarget)) {
            throw new Error(`Scan target container is not running. Start it with: npm run target:up`);
        }
        trace("SYS", `Preflight OK: ${labTarget} container is running`);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(message);
    }
}
function systemPrompt(spec, scanOutputDir, target) {
    return [
        `You are the ${STAGE_LABELS[spec.key]} agent.`,
        `Authorized target: ${target}`,
        `Output directory for scan artifacts: ${scanOutputDir}`,
        `Read and follow the ${spec.skillName} skill — it is your only workflow guide.`,
        `When finished, call ${spec.emitToolName} exactly once with your structured result.`,
    ].join("\n");
}
function userPrompt(spec, target, scanOutputDir, prior) {
    const parts = [
        `Run the ${STAGE_LABELS[spec.key]} stage for target ${target}.`,
        `Store artifacts in: ${scanOutputDir}`,
        `Follow the ${spec.skillName} skill, then call ${spec.emitToolName}.`,
    ];
    if (spec.key === "vuln" && prior.discovery) {
        parts.push("Input from the discovery stage:", "```json", JSON.stringify(prior.discovery, null, 2), "```");
    }
    if (spec.key === "exploit") {
        if (prior.vuln) {
            parts.push("Input from the vulnerability-analysis stage:", "```json", JSON.stringify(prior.vuln, null, 2), "```");
        }
        if (prior.discovery) {
            parts.push("Discovery context (reference):", "```json", JSON.stringify(prior.discovery, null, 2), "```");
        }
    }
    return parts.join("\n\n");
}
/* ---------------------------------------------------------------------------
 * Report merge + helpers
 * ------------------------------------------------------------------------- */
function mergeReport(target, discovery, vuln, exploit) {
    const findings = vuln.vulnerabilities.map((v) => {
        const confirmed = exploit.exploit_attempts.find((a) => a.port === v.port && a.outcome === "confirmed");
        const evidence = confirmed
            ? `${v.evidence} Exploitation: ${confirmed.outcome} via ${confirmed.technique} — ${confirmed.evidence}`
            : v.evidence;
        return {
            title: `${v.service} on port ${v.port}: ${v.nse_script}${v.cve ? ` (${v.cve})` : ""}`,
            severity: confirmed ? "high" : v.severity,
            evidence,
            recommendation: recommendationFor(v.service),
        };
    });
    const confirmedCount = exploit.exploit_attempts.filter((a) => a.outcome === "confirmed").length;
    const summary = [
        `Discovery: ${discovery.summary}`,
        `Vulnerabilities: ${vuln.summary}`,
        `Exploitation: ${exploit.summary}`,
        `Totals: ${discovery.open_ports.length} open ports, ${vuln.vulnerabilities.length} vulnerabilities, ${confirmedCount} confirmed exploit(s).`,
    ].join(" ");
    return {
        target,
        scanned_at: discovery.scanned_at || new Date().toISOString(),
        scan_type: "Multi-agent nmap pipeline (discovery TCP connect + -sV, NSE vuln analysis, NSE exploit confirmation)",
        open_ports: discovery.open_ports,
        vulnerabilities: vuln.vulnerabilities,
        exploit_attempts: exploit.exploit_attempts,
        findings,
        summary,
        stage_summaries: {
            discovery: discovery.summary,
            vuln: vuln.summary,
            exploit: exploit.summary,
        },
        output_directory: "temporary scan directory cleaned up after run",
    };
}
function recommendationFor(service) {
    const s = service.toLowerCase();
    if (s.includes("ftp"))
        return "Disable anonymous FTP, upgrade the FTP daemon, and prefer SFTP/FTPS.";
    if (s.includes("telnet"))
        return "Disable telnet; use SSH and restrict management access.";
    if (s.includes("smb") || s.includes("netbios") || s.includes("microsoft-ds"))
        return "Patch Samba, restrict SMB to trusted hosts, and audit shares.";
    if (s.includes("irc"))
        return "Remove or upgrade the IRC daemon; verify no backdoored build is in use.";
    if (s.includes("distcc"))
        return "Disable distccd on untrusted networks.";
    if (s.includes("mysql") || s.includes("postgres") || s.includes("mariadb"))
        return "Bind the database to localhost/VPN, enforce strong auth, and upgrade.";
    if (s.includes("http") || s.includes("tomcat") || s.includes("ajp"))
        return "Patch/upgrade the web/app server and remove default credentials.";
    return "Patch or disable the affected service and restrict network exposure.";
}
function localSkills(root) {
    const result = loadSkillsFromDir({ dir: path.join(root, "skills"), source: "basic-agent-skill" });
    if (result.diagnostics.length > 0) {
        throw new Error(result.diagnostics.map((diagnostic) => diagnostic.message).join("; "));
    }
    return result.skills;
}
/* ---------------------------------------------------------------------------
 * .env loading (shared with the CLI)
 * ------------------------------------------------------------------------- */
export async function loadScanLabConfig(appRoot) {
    await loadDotEnv(path.join(appRoot, "config", "scan-lab.env"));
}
export async function loadDotEnv(filePath) {
    let content;
    try {
        content = await readFile(filePath, "utf8");
    }
    catch {
        return;
    }
    for (const rawLine of content.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith("#")) {
            continue;
        }
        const normalized = line.startsWith("export ") ? line.slice("export ".length).trim() : line;
        const equalsIndex = normalized.indexOf("=");
        if (equalsIndex <= 0) {
            continue;
        }
        const key = normalized.slice(0, equalsIndex).trim();
        const value = normalized.slice(equalsIndex + 1).trim().replace(/^['"]|['"]$/g, "");
        if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) && process.env[key] === undefined) {
            process.env[key] = value;
        }
    }
}
/* ---------------------------------------------------------------------------
 * Small utilities
 * ------------------------------------------------------------------------- */
function extractToolText(result) {
    if (!isRecord(result)) {
        return "";
    }
    const content = result.content;
    if (!Array.isArray(content)) {
        return "";
    }
    return content
        .map((item) => (isRecord(item) && item.type === "text" ? stringValue(item.text) ?? "" : ""))
        .filter((text) => text.length > 0)
        .join("\n")
        .trim();
}
function compactArgs(args) {
    const pairs = Object.entries(args)
        .filter(([, value]) => value !== undefined && value !== null && value !== "")
        .map(([key, value]) => `${key}=${JSON.stringify(value)}`);
    return pairs.length > 0 ? pairs.join(" ") : "(no args)";
}
function stringValue(value) {
    return typeof value === "string" && value.length > 0 ? value : undefined;
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
