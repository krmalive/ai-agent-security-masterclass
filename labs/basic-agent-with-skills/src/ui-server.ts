#!/usr/bin/env node
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import express, { type Request, type Response } from "express";
import {
  loadDotEnv,
  runPipeline,
  type MergedReport,
  type PipelineEvent,
} from "./pipeline.js";

/**
 * Thin web console for the multi-agent nmap pipeline.
 *
 * It runs the SAME `runPipeline` used by the CLI, buffers every pipeline event,
 * and streams them to the browser over Server-Sent Events. The pipeline stages
 * run automatically one after another; the UI shows each stage's live trace and
 * output in its own tab, and the merged report in the Final Report tab.
 */

type RunStatus = "idle" | "running" | "done" | "error";

type StreamEvent = PipelineEvent | { type: "pipeline_error"; error: string };

type RunState = {
  status: RunStatus;
  target: string;
  events: PipelineEvent[];
  report?: MergedReport;
  error?: string;
};

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const STATIC_DIR = path.join(appRoot, "ui_static");
const DEFAULT_TARGET = process.env.SCAN_TARGET ?? "metasploitable";

const state: RunState = {
  status: "idle",
  target: DEFAULT_TARGET,
  events: [],
};

const clients = new Set<Response>();

function broadcast(event: StreamEvent): void {
  const payload = `data: ${JSON.stringify(event)}\n\n`;
  for (const client of clients) {
    client.write(payload);
  }
}

function startPipeline(target: string): void {
  if (state.status === "running") {
    return;
  }
  state.status = "running";
  state.target = target;
  state.events = [];
  state.report = undefined;
  state.error = undefined;

  const onEvent = (event: PipelineEvent) => {
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
    .catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      state.status = "error";
      state.error = message;
      broadcast({ type: "pipeline_error", error: message });
    });
}

const app = express();
app.use(express.json());
app.use(express.static(STATIC_DIR));

app.get("/", (_req: Request, res: Response) => {
  res.sendFile(path.join(STATIC_DIR, "index.html"));
});

app.get("/api/status", (_req: Request, res: Response) => {
  res.json({
    status: state.status,
    target: state.target,
    report_ready: Boolean(state.report),
    error: state.error ?? null,
  });
});

app.post("/api/run", (req: Request, res: Response) => {
  if (state.status === "running") {
    res.status(409).json({ status: "running" });
    return;
  }
  const bodyTarget = typeof req.body?.target === "string" ? req.body.target.trim() : "";
  const target = bodyTarget || DEFAULT_TARGET;
  startPipeline(target);
  res.json({ status: "started", target });
});

app.get("/api/report", (_req: Request, res: Response) => {
  if (!state.report) {
    res.status(404).json({ error: "report not ready" });
    return;
  }
  res.json(state.report);
});

app.get("/api/stream", (req: Request, res: Response) => {
  res.set({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
  });
  res.flushHeaders?.();

  // Sync with any run already in progress: send status, then replay the buffer.
  res.write(
    `data: ${JSON.stringify({
      type: "status",
      status: state.status,
      target: state.target,
      report_ready: Boolean(state.report),
    })}\n\n`,
  );
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

async function main(): Promise<void> {
  await loadDotEnv(path.join(process.cwd(), ".env"));
  const host = process.env.UI_HOST ?? "0.0.0.0";
  const port = Number(process.env.UI_PORT ?? "8000");
  app.listen(port, host, () => {
    process.stdout.write(`\n  Multi-Agent Nmap Pipeline UI  ->  http://${host}:${port}\n\n`);
    if (!process.env.REQUESTY_API_KEY) {
      process.stderr.write(
        "  warning: REQUESTY_API_KEY is not set. Add it to .env before running the pipeline.\n\n",
      );
    }
  });
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`error: ${message}\n`);
  process.exitCode = 1;
});
