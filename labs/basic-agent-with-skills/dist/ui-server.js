#!/usr/bin/env node
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import express from "express";
import { loadDotEnv, runPipeline, } from "./pipeline.js";
const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC_DIR = path.join(appRoot, "ui_static");
const DEFAULT_TARGET = process.env.SCAN_TARGET ?? "metasploitable";
const state = {
    status: "idle",
    target: DEFAULT_TARGET,
    events: [],
};
const clients = new Set();
function broadcast(event) {
    const payload = `data: ${JSON.stringify(event)}\n\n`;
    for (const client of clients) {
        client.write(payload);
    }
}
function startPipeline(target) {
    if (state.status === "running") {
        return;
    }
    state.status = "running";
    state.target = target;
    state.events = [];
    state.report = undefined;
    state.error = undefined;
    const onEvent = (event) => {
        state.events.push(event);
        if (event.type === "pipeline_end") {
            state.report = event.report;
        }
        broadcast(event);
    };
    runPipeline({ target, onEvent })
        .then((report) => {
        state.report = report;
        state.status = "done";
    })
        .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        state.status = "error";
        state.error = message;
        broadcast({ type: "pipeline_error", error: message });
    });
}
const app = express();
app.use(express.json());
app.use(express.static(STATIC_DIR));
app.get("/", (_req, res) => {
    res.sendFile(path.join(STATIC_DIR, "index.html"));
});
app.get("/api/status", (_req, res) => {
    res.json({
        status: state.status,
        target: state.target,
        report_ready: Boolean(state.report),
        error: state.error ?? null,
    });
});
app.post("/api/run", (req, res) => {
    if (state.status === "running") {
        res.status(409).json({ status: "running" });
        return;
    }
    const bodyTarget = typeof req.body?.target === "string" ? req.body.target.trim() : "";
    const target = bodyTarget || DEFAULT_TARGET;
    startPipeline(target);
    res.json({ status: "started", target });
});
app.get("/api/report", (_req, res) => {
    if (!state.report) {
        res.status(404).json({ error: "report not ready" });
        return;
    }
    res.json(state.report);
});
app.get("/api/stream", (req, res) => {
    res.set({
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
    });
    res.flushHeaders?.();
    // Sync with any run already in progress: send status, then replay the buffer.
    res.write(`data: ${JSON.stringify({
        type: "status",
        status: state.status,
        target: state.target,
        report_ready: Boolean(state.report),
    })}\n\n`);
    for (const event of state.events) {
        res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
    if (state.status === "error" && state.error) {
        res.write(`data: ${JSON.stringify({ type: "pipeline_error", error: state.error })}\n\n`);
    }
    clients.add(res);
    const heartbeat = setInterval(() => {
        res.write(": ping\n\n");
    }, 15000);
    req.on("close", () => {
        clearInterval(heartbeat);
        clients.delete(res);
    });
});
async function main() {
    await loadDotEnv(path.join(process.cwd(), ".env"));
    const host = process.env.UI_HOST ?? "0.0.0.0";
    const port = Number(process.env.UI_PORT ?? "8000");
    app.listen(port, host, () => {
        process.stdout.write(`\n  Multi-Agent Nmap Pipeline UI  ->  http://${host}:${port}\n\n`);
        if (!process.env.REQUESTY_API_KEY) {
            process.stderr.write("  warning: REQUESTY_API_KEY is not set. Add it to .env before running the pipeline.\n\n");
        }
    });
}
main().catch((error) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`error: ${message}\n`);
    process.exitCode = 1;
});
