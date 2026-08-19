#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKIP_DIRECTORIES = new Set([
  ".git",
  ".agents",
  ".codex",
  ".gradle",
  "ads-audit-output",
  "build",
  "node_modules",
]);

export function discoverCsv(projectRoot, kind) {
  const root = path.resolve(projectRoot);
  const matches = [];
  const stack = [root];

  while (stack.length > 0) {
    const current = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch (error) {
      throw new Error(`Cannot read project directory ${current}: ${error.message}`);
    }

    for (const entry of entries) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!SKIP_DIRECTORIES.has(entry.name)) stack.push(entryPath);
        continue;
      }
      if (!entry.isFile() || path.extname(entry.name).toLowerCase() !== ".csv") continue;
      const normalized = entry.name.toLowerCase().replace(/[^a-z0-9]+/g, "");
      const isMatch = kind === "ads"
        ? normalized.includes("adsscripts")
        : normalized.includes("working") || normalized.includes("workfile");
      if (isMatch) matches.push(path.resolve(entryPath));
    }
  }

  matches.sort();
  const flag = kind === "ads" ? "--ads-script" : "--working-file";
  const label = kind === "ads" ? "ADS SCRIPTS" : "working-file";
  if (matches.length === 0) {
    throw new Error(
      `Could not find the ${label} document under ${root}.\n` +
      `Supply it with ${flag}, as either:\n` +
      `  - a Google Sheets/Docs share link (set to Anyone with the link, Viewer), or\n` +
      `  - a path to a CSV downloaded from that document.\n` +
      `If you do not have it, ask the partner for the ${label} document before ` +
      `auditing. Do not audit without it and do not substitute base values.`
    );
  }
  if (matches.length > 1) {
    const listed = matches.map((candidate) => `  - ${path.relative(root, candidate) || candidate}`).join("\n");
    throw new Error(
      `Found several ${label} candidates, so discovery will not choose one.\n${listed}\n` +
      `Pass the right one with ${flag}. If it is not obvious which is current, ` +
      `ask the partner before auditing — auditing the wrong revision is worse than asking.`
    );
  }
  return matches[0];
}

function explicitPath(projectRoot, value, flag) {
  if (value === "") throw new Error(`${flag} cannot be empty.`);
  const resolved = path.resolve(projectRoot, value);
  let stat;
  try {
    stat = fs.statSync(resolved);
  } catch {
    throw new Error(`File supplied to ${flag} was not found: ${resolved}`);
  }
  if (!stat.isFile()) throw new Error(`Path supplied to ${flag} is not a file: ${resolved}`);
  return resolved;
}

export function resolveInputs(projectRoot, adsScript, workingFile) {
  return {
    adsScript: adsScript === undefined ? discoverCsv(projectRoot, "ads") : explicitPath(projectRoot, adsScript, "--ads-script"),
    workingFile: workingFile === undefined ? discoverCsv(projectRoot, "working") : explicitPath(projectRoot, workingFile, "--working-file"),
  };
}

export function buildAuditArgs(project, adsScript, workingFile, extraArgs = [], scriptPath = "scripts/run_audit.py") {
  return [
    scriptPath,
    "--project",
    project,
    "--ads-script",
    adsScript,
    "--working-file",
    workingFile,
    ...extraArgs,
  ];
}

function readFlag(args, name) {
  const index = args.indexOf(name);
  if (index >= 0) return args[index + 1] ?? "";
  const prefix = `${name}=`;
  const inline = args.find((arg) => arg.startsWith(prefix));
  return inline === undefined ? undefined : inline.slice(prefix.length);
}

function removeFlag(args, name) {
  const result = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === name) {
      index += 1;
      continue;
    }
    if (arg.startsWith(`${name}=`)) continue;
    result.push(arg);
  }
  return result;
}

export function findPython() {
  const candidates = [
    process.env.PYTHON,
    "python3",
    "python3.14",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "python",
    "py",
  ].filter(Boolean);

  for (const command of candidates) {
    try {
      const version = spawnSync(command, ["--version"], { encoding: "utf8" });
      const output = `${version.stdout || ""}\n${version.stderr || ""}`;
      const match = output.match(/Python\s+(\d+)\.(\d+)/i);
      if (version.status === 0 && match) {
        const major = Number(match[1]);
        const minor = Number(match[2]);
        if (major > 3 || (major === 3 && minor >= 9)) {
          return command;
        }
      }
    } catch {
      // continue searching
    }
  }
  return null;
}

function printHelp() {
  process.stdout.write(`Infinity Ads Compliance Audit\n\nUsage:\n  npx -y github:NguyenMinhVu02/Skill_Ads_Audit audit [options]\n\nThe CLI auto-discovers one ADS SCRIPTS CSV and one working-file CSV under --project.\nPass explicit paths when there are multiple files:\n  --ads-script "path/to/ADS SCRIPTS.csv"\n  --working-file "path/to/working-file.csv"\n\nCommon options:\n  --project PATH       Android project root (default: .)\n  --no-webhook         Write local reports only\n  --output-dir PATH    Report directory (default: ads-audit-output)\n`);
}

export function main(argv = process.argv.slice(2)) {
  if (argv.length === 0 || argv.includes("--help") || argv.includes("-h")) {
    printHelp();
    return 0;
  }
  if (argv[0] !== "audit") {
    console.error("Unknown command. Use `audit` or `--help`.");
    return 2;
  }

  const auditArgs = argv.slice(1);
  const projectArg = readFlag(auditArgs, "--project") ?? ".";
  const projectRoot = path.resolve(projectArg);
  const adsScriptArg = readFlag(auditArgs, "--ads-script");
  const workingFileArg = readFlag(auditArgs, "--working-file");
  const extraArgs = removeFlag(removeFlag(removeFlag(auditArgs, "--project"), "--ads-script"), "--working-file");

  let inputs;
  try {
    inputs = resolveInputs(projectRoot, adsScriptArg, workingFileArg);
  } catch (error) {
    console.error(`Input error: ${error.message}`);
    return 1;
  }

  const python = findPython();
  if (!python) {
    console.error("Python 3.9 or newer is required. Install Python, then run this command again.");
    return 1;
  }

  const result = spawnSync(python, buildAuditArgs(projectRoot, inputs.adsScript, inputs.workingFile, extraArgs, path.join(PACKAGE_ROOT, "scripts", "run_audit.py")), {
    cwd: projectRoot,
    stdio: "inherit",
  });
  if (result.error) {
    console.error(`Could not start Python: ${result.error.message}`);
    return 1;
  }
  return result.status ?? 1;
}

if (process.argv[1]) {
  let invokedPath = path.resolve(process.argv[1]);
  let modulePath = fileURLToPath(import.meta.url);
  try {
    invokedPath = fs.realpathSync(invokedPath);
    modulePath = fs.realpathSync(modulePath);
  } catch {
    // Keep the resolved paths when the entry point is being inspected or tested.
  }
  if (invokedPath === modulePath) process.exitCode = main();
}
