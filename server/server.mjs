import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = path.join(appDir, "public");
const stateDir = path.join(process.env.APPDATA || appDir, "周报分析器");
const configPath = path.join(stateDir, "config.json");
const cachePath = path.join(stateDir, "report-cache.json");
const port = Number(process.env.PORT || 8787);
const defaultDir = path.join(appDir, "data");

let config = { sourceDir: defaultDir, dailyHour: 3 };
let cache = { ok: false, data: null, updatedAt: "", sourceSignature: "", error: "尚未读取周报" };
let refreshing = null;
let aggregateCache = { signature: "", data: null };
let detailAggregateCache = { signature: "", data: null };

function localIps() {
  return Object.values(os.networkInterfaces()).flat().filter((item) => item && item.family === "IPv4" && !item.internal).map((item) => item.address);
}

async function ensureState() {
  await fs.mkdir(stateDir, { recursive: true });
  for (const [file, fallback] of [[configPath, config], [cachePath, cache]]) {
    try {
      const parsed = JSON.parse(await fs.readFile(file, "utf8"));
      if (file === configPath) config = { ...config, ...parsed };
      else cache = { ...cache, ...parsed };
    } catch {
      await fs.writeFile(file, JSON.stringify(fallback, null, 2), "utf8");
    }
  }
}

async function listExcel(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.filter((entry) => entry.isFile() && /\.xlsx$/i.test(entry.name) && !entry.name.startsWith("~$")).map(async (entry) => {
    const filePath = path.join(dir, entry.name);
    const stat = await fs.stat(filePath);
    return { name: entry.name, path: filePath, mtimeMs: stat.mtimeMs, size: stat.size };
  }));
  files.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return files;
}

function runParser(command, sourceDir, fileName = "") {
  const parser = path.join(appDir, "server", "parser.py");
  const args = [parser, command, "--dir", sourceDir];
  if (fileName) args.push("--file", fileName);
  return new Promise((resolve, reject) => {
    execFile("python", args, { windowsHide: true, encoding: "utf8", maxBuffer: 40 * 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) return reject(new Error(stderr.trim() || error.message));
      try { resolve(JSON.parse(stdout.replace(/^\uFEFF/, ""))); }
      catch (parseError) { reject(new Error(`解析结果无效：${parseError.message}`)); }
    });
  });
}

async function refresh(force = false) {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      const files = await listExcel(config.sourceDir);
      if (!files.length) throw new Error("读取目录中没有 .xlsx 周报文件");
      const latest = files[0];
      const signature = `${latest.path}|${latest.mtimeMs}|${latest.size}`;
      if (!force && cache.data && cache.sourceSignature === signature) return cache;
      const data = await runParser("data", config.sourceDir);
      cache = { ok: true, data, updatedAt: new Date().toISOString(), sourceSignature: signature, error: "" };
      aggregateCache = { signature: "", data: null };
      detailAggregateCache = { signature: "", data: null };
      await fs.writeFile(cachePath, JSON.stringify(cache, null, 2), "utf8");
      return cache;
    } catch (error) {
      cache = { ...cache, ok: Boolean(cache.data), error: error.message };
      await fs.writeFile(cachePath, JSON.stringify(cache, null, 2), "utf8");
      return cache;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

async function aggregate() {
  const files = await listExcel(config.sourceDir);
  const signature = files.map((file) => `${file.name}:${file.mtimeMs}:${file.size}`).join("|");
  if (aggregateCache.data && aggregateCache.signature === signature) return aggregateCache.data;
  const data = await runParser("aggregate", config.sourceDir);
  aggregateCache = { signature, data };
  return data;
}

async function detailAggregate() {
  const files = await listExcel(config.sourceDir);
  const signature = files.map((file) => `${file.name}:${file.mtimeMs}:${file.size}`).join("|");
  if (detailAggregateCache.data && detailAggregateCache.signature === signature) return detailAggregateCache.data;
  const data = await runParser("detail-aggregate", config.sourceDir);
  detailAggregateCache = { signature, data };
  return data;
}

function csvDownload(response, fileName, tables) {
  const rows = [];
  for (const table of tables) {
    rows.push([table.title]);
    rows.push(table.headers);
    rows.push(...table.rows.map((row) => table.headers.map((header) => row[header] ?? "")));
    rows.push([]);
  }
  const csv = "\uFEFF" + rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\r\n");
  response.writeHead(200, { "content-type": "text/csv; charset=utf-8", "content-disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`, "cache-control": "no-store" });
  response.end(csv);
}

function scheduleDailyRefresh() {
  const schedule = () => {
    const now = new Date();
    const next = new Date(now);
    next.setHours(Number(config.dailyHour) || 3, 0, 0, 0);
    if (next <= now) next.setDate(next.getDate() + 1);
    setTimeout(async () => { await refresh(); schedule(); }, next - now);
  };
  schedule();
}

function json(response, status, payload) {
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(JSON.stringify(payload));
}

async function readBody(request) {
  let text = "";
  for await (const chunk of request) text += chunk;
  return text ? JSON.parse(text) : {};
}

function contentType(file) {
  return file.endsWith(".html") ? "text/html; charset=utf-8" : file.endsWith(".js") ? "text/javascript; charset=utf-8" : file.endsWith(".css") ? "text/css; charset=utf-8" : "application/octet-stream";
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  try {
    if (url.pathname === "/api/health") return json(response, 200, { ok: true, service: "weekly-report-lan", port });
    if (url.pathname === "/api/status") { await refresh(); return json(response, 200, { ok: true, sourceDir: config.sourceDir, cache: { hasData: Boolean(cache.data), updatedAt: cache.updatedAt, error: cache.error }, lanUrls: localIps().map((ip) => `http://${ip}:${port}/`) }); }
    if (url.pathname === "/api/files") return json(response, 200, { ok: true, items: (await listExcel(config.sourceDir)).map((file) => ({ name: file.name, updatedAt: new Date(file.mtimeMs).toISOString() })) });
    if (url.pathname === "/api/data") {
      const selectedFile = url.searchParams.get("file") || "";
      const latestCache = selectedFile ? cache : await refresh();
      const report = selectedFile ? await runParser("data", config.sourceDir, selectedFile) : latestCache.data;
      return json(response, 200, { ok: Boolean(report), report, cache: { updatedAt: cache.updatedAt, error: cache.error, refreshing: Boolean(refreshing) } });
    }
    if (url.pathname === "/api/aggregate") return json(response, 200, { ok: true, aggregate: await aggregate() });
    if (url.pathname === "/api/aggregate/detail-export") return csvDownload(response, "游戏详情收益汇总.csv", (await detailAggregate()).modules || []);
    if (url.pathname === "/api/refresh" && request.method === "POST") return json(response, 200, { ok: true, ...(await refresh(true)) });
    if (url.pathname === "/api/config" && request.method === "POST") {
      const body = await readBody(request);
      if (!body.sourceDir || typeof body.sourceDir !== "string") return json(response, 400, { ok: false, error: "请输入有效读取目录" });
      const nextDir = body.sourceDir.trim();
      const nextFiles = await listExcel(nextDir);
      if (!nextFiles.length) return json(response, 400, { ok: false, error: "目录中没有可读取的 .xlsx 周报文件" });
      config = { ...config, sourceDir: nextDir };
      await fs.writeFile(configPath, JSON.stringify(config, null, 2), "utf8");
      const nextCache = await refresh(true);
      return json(response, 200, { ok: Boolean(nextCache.data), sourceDir: config.sourceDir, cache: nextCache });
    }
    const relative = url.pathname === "/" ? "index.html" : url.pathname.replace(/^\/+/, "");
    const file = path.resolve(publicDir, relative);
    if (!file.startsWith(publicDir)) return json(response, 403, { ok: false, error: "无权访问" });
    const content = await fs.readFile(file);
    response.writeHead(200, { "content-type": contentType(file) });
    response.end(content);
  } catch (error) {
    json(response, 500, { ok: false, error: error.message });
  }
});

await ensureState();
server.listen(port, "0.0.0.0", async () => {
  console.log(`周报服务已启动：http://localhost:${port}/`);
  for (const url of localIps().map((ip) => `http://${ip}:${port}/`)) console.log(`局域网访问：${url}`);
  await refresh();
  scheduleDailyRefresh();
});
