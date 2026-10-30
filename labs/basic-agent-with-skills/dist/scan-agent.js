#!/usr/bin/env node
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { loadDotEnv, runPipeline, } from "./pipeline.js";
const STAGE_TAG = {
    discovery: "discovery",
    vuln: "vuln",
    exploit: "exploit",
};
async function main() {
    await loadDotEnv(path.join(process.cwd(), ".env"));
    const options = parseArgs(process.argv.slice(2));
    const onEvent = options.trace ? makeTracePrinter() : undefined;
    const report = await runPipeline({
        target: options.target,
        model: options.model,
        baseUrl: options.baseUrl,
        onEvent,
    });
    if (options.trace) {
        process.stderr.write(`\n[pipeline:done] ${report.open_ports.length} open ports, ${report.vulnerabilities.length} vulnerabilities, ${report.exploit_attempts.length} exploit attempts\n`);
    }
    const serialized = `${JSON.stringify(report, null, 2)}\n`;
    await mkdir(path.dirname(path.resolve(options.output)), { recursive: true });
    await writeFile(options.output, serialized, "utf8");
    process.stdout.write(serialized);
}
function makeTracePrinter() {
    return (event) => {
        if (event.type === "stage_start") {
            process.stderr.write(`\n[stage:${STAGE_TAG[event.stage]}] === ${event.label} ===\n`);
        }
        else if (event.type === "trace") {
            process.stderr.write(`[${STAGE_TAG[event.stage]}:${event.phase.toLowerCase()}] ${event.text}\n`);
        }
        else if (event.type === "stage_output") {
            process.stderr.write(`[stage:${STAGE_TAG[event.stage]}] output received\n`);
        }
        else if (event.type === "stage_end") {
            const suffix = event.error ? ` (${event.error})` : "";
            process.stderr.write(`[stage:${STAGE_TAG[event.stage]}] ${event.status}${suffix}\n`);
        }
    };
}
function parseArgs(argv) {
    const options = {
        target: "metasploitable",
        output: "reports/scan-report.json",
        trace: false,
    };
    for (let i = 0; i < argv.length; i += 1) {
        const arg = argv[i];
        if (arg === "--target") {
            options.target = requireValue(argv, ++i, arg);
        }
        else if (arg === "--output") {
            options.output = requireValue(argv, ++i, arg);
        }
        else if (arg === "--model") {
            options.model = requireValue(argv, ++i, arg);
        }
        else if (arg === "--base-url") {
            options.baseUrl = requireValue(argv, ++i, arg);
        }
        else if (arg === "--trace") {
            options.trace = true;
        }
        else if (arg === "--help" || arg === "-h") {
            printHelp();
            process.exit(0);
        }
        else {
            throw new Error(`unknown argument: ${arg}`);
        }
    }
    return options;
}
function requireValue(argv, index, flag) {
    const value = argv[index];
    if (!value || value.startsWith("--")) {
        throw new Error(`${flag} requires a value`);
    }
    return value;
}
function printHelp() {
    process.stdout.write(`Usage: npm run scan -- [options]

Runs the multi-agent nmap pipeline (discovery -> vulnerability analysis -> exploitation)
and writes a merged JSON report.

Options:
  --target <host>       Authorized host to scan (default: metasploitable)
  --output <path>       Report JSON path (default: reports/scan-report.json)
  --model <id>          Requesty model id (default: openai/gpt-5-mini)
  --base-url <url>      OpenAI-compatible URL (default: BASE_URL or https://router.requesty.ai/v1)
  --trace               Stream per-stage agent commands and output to stderr
`);
}
main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`error: ${message}\n`);
    process.exitCode = 1;
});
