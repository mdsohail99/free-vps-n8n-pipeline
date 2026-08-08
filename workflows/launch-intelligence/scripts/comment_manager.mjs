#!/usr/bin/env node
/**
 * comment_manager.mjs
 * ------------------------------------------------------------------
 * Deterministic, agent-agnostic CLI for the LOCAL-ONLY
 * "Launch Intelligence" comments pipeline.
 *
 * This script replaces the old idea that n8n or a hidden script runs
 * the pipeline. It is pure Node.js (zero dependencies), cross-platform
 * (Windows + Linux + macOS) and never talks to an agent, a browser, or
 * the network. It only reads and writes JSON + Markdown files on disk.
 *
 * The host agent (Claude Code, Gemini, Cursor — any MCP-capable tool):
 *   1. scrapes comments with a real logged-in browser (Chrome DevTools)
 *      and saves the raw array to a file,
 *   2. runs this script to normalize/dedupe/analyze/approve/post-track.
 *
 * Usage:
 *   node comment_manager.mjs --launch <launch_id> <command> [options]
 *   node comment_manager.mjs <command> [options]   # auto-picks the
 *                                                  # only launch dir
 */

import { readFileSync, writeFileSync, renameSync, mkdirSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ------------------------------------------------------------------
// Path resolution helpers
// ------------------------------------------------------------------

/**
 * Resolve the root directory that contains the runtime/ tree.
 * Order: env LAUNCH_ROOT, ./runtime (cwd), ../runtime (when run from
 * the scripts dir), ../../runtime (when run from the repo root).
 */
function findRuntimeRoot() {
  if (process.env.LAUNCH_ROOT && existsSync(join(process.env.LAUNCH_ROOT, 'launches'))) {
    return process.env.LAUNCH_ROOT;
  }
  const candidates = [
    join(process.cwd(), 'runtime'),
    join(__dirname, '..', 'runtime'),
    join(__dirname, '..', '..', 'runtime'),
    join(__dirname, '..', '..', '..', 'runtime'),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return null;
}

/**
 * Resolve the launch directory for a given launch id (or null when the
 * launch does not exist).
 */
function launchDir(runtimeRoot, launchId) {
  if (!runtimeRoot) return null;
  return join(runtimeRoot, 'launches', launchId);
}

/**
 * When --launch is omitted: return the single launch id inside
 * runtime/launches/, or throw when zero/multiple launches exist.
 */
function autodetectLaunch(runtimeRoot) {
  const launchesRoot = join(runtimeRoot, 'launches');
  if (!existsSync(launchesRoot)) {
    throw new Error(`No launches directory found at ${launchesRoot}`);
  }
  const ids = readdirSync(launchesRoot).filter((name) => {
    try {
      return statSync(join(launchesRoot, name)).isDirectory();
    } catch {
      return false;
    }
  });
  if (ids.length === 0) {
    throw new Error('No launch directories found under runtime/launches/');
  }
  if (ids.length > 1) {
    throw new Error(
      `Multiple launches found (${ids.join(', ')}). Use --launch <id> to pick one.`,
    );
  }
  return ids[0];
}

// ------------------------------------------------------------------
// File helpers (atomic writes)
// ------------------------------------------------------------------

/**
 * Read a JSON file, returning its parsed value or null when the file is
 * missing or malformed.
 */
function readJson(file) {
  if (!existsSync(file)) return null;
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * Write a JSON file atomically (temp + rename) so concurrent readers
 * never observe a half-written file.
 */
function writeJsonAtomic(file, value) {
  mkdirSync(dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(value, null, 2) + '\n', 'utf8');
  renameSync(tmp, file);
}

/**
 * Read a text file (returns '' when missing).
 */
function readText(file) {
  if (!existsSync(file)) return '';
  return readFileSync(file, 'utf8');
}

/**
 * Write a text file atomically.
 */
function writeTextAtomic(file, content) {
  mkdirSync(dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, content, 'utf8');
  renameSync(tmp, file);
}

// ------------------------------------------------------------------
// Data model helpers
// ------------------------------------------------------------------

/**
 * Load launch_config.json (array of posts) or throw.
 */
function loadLaunchConfig(dir) {
  const file = join(dir, 'launch_config.json');
  const data = readJson(file);
  if (!Array.isArray(data)) {
    throw new Error(`launch_config.json missing or not an array at ${file}`);
  }
  return data;
}

/**
 * Load comments.json (array) or default to [].
 */
function loadComments(dir) {
  const data = readJson(join(dir, 'comments.json'));
  return Array.isArray(data) ? data : [];
}

/**
 * Load history.json or initialize the ledger shape.
 */
function loadHistory(dir) {
  const data = readJson(join(dir, 'history.json'));
  if (data && Array.isArray(data.processed_comment_ids)) return data;
  return { processed_comment_ids: [] };
}

/**
 * Normalize a raw scraped comment row into the canonical shape.
 * Unknown fields are dropped; required string fields default to ''.
 */
function normalizeComment(raw) {
  const row = raw && typeof raw === 'object' ? raw : {};
  return {
    id: String(row.id ?? ''),
    post_id: String(row.post_id ?? ''),
    platform: String(row.platform ?? ''),
    author: String(row.author ?? ''),
    text: String(row.text ?? ''),
    url: String(row.url ?? ''),
    subreddit: row.subreddit ? String(row.subreddit) : undefined,
  };
}

// ------------------------------------------------------------------
// Commands
// ------------------------------------------------------------------

/**
 * --scrape-agenda: print the JSON manifest of URLs an agent should
 * scrape, derived from launch_config.json.
 */
function cmdScrapeAgenda(dir) {
  const posts = loadLaunchConfig(dir);
  const agenda = posts.map((p) => ({
    id: p.id,
    platform: p.platform,
    url: p.url,
    title: p.title,
  }));
  console.log(JSON.stringify(agenda, null, 2));
}

/**
 * --ingest --comments <file>: normalize + merge raw comments into
 * comments.json, deduping against existing ids and history.json.
 * Idempotent: re-ingesting the same file never appends duplicates.
 */
function cmdIngest(dir, rawFile) {
  if (!rawFile) {
    throw new Error('--ingest requires --comments <file>');
  }
  const raw = readJson(rawFile);
  if (!Array.isArray(raw)) {
    throw new Error(`raw comments file ${rawFile} is missing or not an array`);
  }

  const existing = loadComments(dir);
  const history = loadHistory(dir);
  const known = new Set(existing.map((c) => c.id));
  history.processed_comment_ids.forEach((id) => known.add(String(id)));

  const added = [];
  const skipped = [];
  for (const item of raw) {
    const norm = normalizeComment(item);
    if (!norm.id) {
      skipped.push({ id: '(no-id)', reason: 'missing id' });
      continue;
    }
    if (known.has(norm.id)) {
      skipped.push({ id: norm.id, reason: 'already known' });
      continue;
    }
    known.add(norm.id);
    added.push(norm);
  }

  const merged = existing.concat(added);
  writeJsonAtomic(join(dir, 'comments.json'), merged);
  console.log(`Ingested ${added.length} new comment(s), skipped ${skipped.length}.`);
  if (skipped.length > 0) {
    console.log('Skipped:', skipped.map((s) => `${s.id} (${s.reason})`).join(', '));
  }
}

/**
 * --analyze [--prompt-file <file>]: build the AI clustering prompt from
 * comments.json (+ optional external prompt template) and print it to
 * stdout. The script never calls an LLM — the host agent pastes the
 * prompt — the host agent itself is the AI and can read this prompt
 * to drive its own model.
 */
function cmdAnalyze(dir, promptFile) {
  const comments = loadComments(dir);
  if (comments.length === 0) {
    console.log('No comments yet. Run --ingest first.');
    return;
  }
  const history = loadHistory(dir);
  const pending = comments.filter(
    (c) => !history.processed_comment_ids.includes(String(c.id)),
  );

  let extra = '';
  if (promptFile) {
    if (!existsSync(promptFile)) {
      throw new Error(`prompt file not found: ${promptFile}`);
    }
    extra = '\n\n' + readText(promptFile);
  }

  const prompt = `You are analyzing community feedback for a product launch.
Below are normalized comments (JSON). Group them into:

1) OPEN QUESTIONS -> draft reply rows for feedback_board.md,
   each as: - [*] ID: <comment id> - <reply text>
2) FEATURE REQUESTS & BUGS -> action cards for recommendations.md,
   each with: priority (LOW/MEDIUM/HIGH), name, summary, evidence
   (with comment permalinks), and status.
3) PRAISE -> testimonial quotes for launch_report.md.

Tone: casual, warm, developer-to-developer. No corporate-speak,
no repeated phrasing. Adapt to the platform (X = short and punchy,
LinkedIn = professional but friendly, Reddit/HN = direct and technical).

${pending.length} of ${comments.length} comment(s) are unprocessed.

COMMENTS (JSON):
${JSON.stringify(pending, null, 2)}${extra}
`;
  console.log(prompt);
}

/**
 * --board: print the current feedback_board.md.
 */
function cmdBoard(dir) {
  const content = readText(join(dir, 'feedback_board.md'));
  if (!content) {
    console.log('(no feedback_board.md yet — run --analyze with an LLM to generate one)');
    return;
  }
  console.log(content);
}

/**
 * --reply-approve: parse feedback_board.md and return ONLY the approved
 * ('[x]') rows as a JSON array [{ id, url, reply }].
 */
function cmdReplyApprove(dir) {
  const content = readText(join(dir, 'feedback_board.md'));
  const rows = parseBoardRows(content);
  const approved = rows.filter((r) => r.approved);
  console.log(JSON.stringify(approved, null, 2));
}

/**
 * --mark-posted --ids <list>: move approved board rows to the History
 * section and append their ids to history.json. Idempotent.
 */
function cmdMarkPosted(dir, idsRaw) {
  const ids = idsRaw.split(',').map((s) => s.trim()).filter(Boolean);
  if (ids.length === 0) {
    throw new Error('--mark-posted requires --ids <comma,list>');
  }
  const file = join(dir, 'feedback_board.md');
  let content = readText(file);
  if (!content) {
    throw new Error('feedback_board.md not found — nothing to mark');
  }
  const history = loadHistory(dir);
  const idSet = new Set(history.processed_comment_ids.map((i) => String(i)));
  let moved = 0;

  const rows = parseBoardRows(content);
  const approvedById = new Map(rows.filter((r) => r.approved).map((r) => [r.id, r]));

  for (const id of ids) {
    const row = approvedById.get(id);
    if (!row) {
      console.log(`- ${id}: not an approved row (skipping)`);
      continue;
    }
    if (idSet.has(id)) {
      console.log(`- ${id}: already processed (no-op)`);
      continue;
    }
    idSet.add(id);
    moved += 1;
  }

  // Rewrite the board: strip approved rows from Inbox, append them
  // (as posted rows) to the History section.
  const lines = content.split('\n');
  const out = [];
  const historyLines = [];
  let inHistory = false;
  let boardHasHistory = false;

  const isApprovedRow = (line) => /^\s*-\s*\[x\]/i.test(line);
  const isPendingRow = (line) => /^\s*-\s*\[[* ]\]/i.test(line);

  for (const line of lines) {
    if (/^##\s*History/i.test(line)) {
      inHistory = true;
      boardHasHistory = true;
      out.push(line);
      continue;
    }
    if (/^##\s/i.test(line)) inHistory = false;

    if (isApprovedRow(line)) {
      const row = parseBoardRow(line);
      if (row && idSet.has(row.id) && ids.includes(row.id)) {
        // Move this approved row into the history block as posted.
        historyLines.push(line.replace(/\[x\]/i, '[x] posted'));
        continue;
      }
      out.push(line);
      continue;
    }
    if (inHistory && isPendingRow(line)) {
      // Pre-existing history rows pass through unchanged.
      out.push(line);
      continue;
    }
    out.push(line);
  }

  // Rebuild history section at the end.
  const body = out.join('\n').replace(/\n+$/, '\n');
  let result;
  if (boardHasHistory) {
    result = body;
    // Append moved rows under the existing History heading (handled by
    // inserting before the last section close — simpler: re-append).
    result = body.replace(
      /(##\s*History[^\n]*\n)([\s\S]*)$/,
      (m, head, rest) => `${head}${historyLines.join('\n')}\n${rest}`,
    );
  } else {
    result = `${body}\n## History Log (Processed Comments)\n${historyLines.join('\n')}\n`;
  }

  writeTextAtomic(file, result);
  writeJsonAtomic(join(dir, 'history.json'), {
    processed_comment_ids: [...idSet],
  });

  console.log(`Marked ${moved} reply(ies) as posted (history now has ${idSet.size} total).`);
}

/**
 * --status: summary of the launch dir.
 */
function cmdStatus(dir) {
  const posts = loadLaunchConfig(dir).length;
  const comments = loadComments(dir).length;
  const history = loadHistory(dir);
  const board = readText(join(dir, 'feedback_board.md'));
  const rows = parseBoardRows(board);
  const pending = rows.filter((r) => !r.approved).length;
  const approved = rows.filter((r) => r.approved).length;

  console.log(`Launch dir : ${dir}`);
  console.log(`Posts      : ${posts}`);
  console.log(`Comments   : ${comments}`);
  console.log(`Pending    : ${pending}`);
  console.log(`Approved   : ${approved}`);
  console.log(`Posted     : ${history.processed_comment_ids.length}`);
  const files = ['launch_config.json', 'comments.json', 'history.json', 'feedback_board.md', 'recommendations.md', 'launch_report.md'];
  const present = files.filter((f) => existsSync(join(dir, f)));
  console.log(`Files      : ${present.join(', ') || '(none yet)'}`);
}

// ------------------------------------------------------------------
// feedback_board.md parsing
// ------------------------------------------------------------------

/**
 * Parse a single board row like "- [x] ID: 123 - reply text".
 * Returns { approved, id, reply } or null.
 */
function parseBoardRow(line) {
  const m = line.match(/^\s*-\s*\[([xX* ])\]\s*ID:\s*([^\s]+)\s*-\s*(.*)$/i);
  if (!m) return null;
  return { approved: /[xX]/.test(m[1]), id: m[2], reply: m[3].trim() };
}

/**
 * Parse all rows of the board. Returns [{ approved, id, reply, line }].
 */
function parseBoardRows(content) {
  const rows = [];
  for (const line of content.split('\n')) {
    const row = parseBoardRow(line);
    if (row) rows.push({ ...row, line });
  }
  return rows;
}

// ------------------------------------------------------------------
// CLI entry
// ------------------------------------------------------------------

const USAGE = `comment_manager.mjs — Launch Intelligence comment pipeline CLI

Usage:
  node comment_manager.mjs [--launch <launch_id>] <command> [options]

Commands:
  --scrape-agenda                 Print JSON manifest of URLs to scrape
                                  (from launch_config.json).
  --ingest --comments <file>      Normalize + merge raw scraped comments
                                  into comments.json (dedupes, idempotent).
  --analyze [--prompt-file <f>]   Print the AI clustering prompt to
                                  stdout (no API call).
  --board                         Print the current feedback_board.md.
  --reply-approve                 Print approved ('[x]') rows as JSON.
  --mark-posted --ids <a,b,c>     Move approved rows to History and
                                  record them as posted (idempotent).
  --status                        Print a summary of the launch dir.
  --help                          Show this help.

Options:
  --launch <launch_id>            Launch id under runtime/launches/.
                                  Omitted -> auto-detect a single launch.
  --comments <file>               Raw scraped comments JSON file.
  --prompt-file <file>            Optional external prompt template.
  --ids <comma,list>              Comment ids for --mark-posted.

Environment:
  LAUNCH_ROOT                     Absolute path to a runtime/ root.
`;

/**
 * Main entry point: parse argv, resolve launch dir, dispatch command.
 */
function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.length === 0) {
    console.log(USAGE);
    process.exit(args.length === 0 ? 1 : 0);
  }

  let launchId = null;
  let command = null;
  let commentsFile = null;
  let promptFile = null;
  let ids = null;

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    switch (arg) {
      case '--launch':
        launchId = args[++i];
        break;
      case '--comments':
        commentsFile = args[++i];
        break;
      case '--prompt-file':
        promptFile = args[++i];
        break;
      case '--ids':
        ids = args[++i];
        break;
      default:
        command = arg;
        break;
    }
  }

  const runtimeRoot = findRuntimeRoot();
  if (!runtimeRoot) {
    console.error('ERROR: could not locate runtime/ directory. Set LAUNCH_ROOT to the absolute path of a runtime root.');
    process.exit(1);
  }

  try {
    const id = launchId || autodetectLaunch(runtimeRoot);
    const dir = launchDir(runtimeRoot, id);
    if (!existsSync(dir)) {
      throw new Error(`launch directory not found: ${dir}`);
    }
    switch (command) {
      case '--scrape-agenda':
        cmdScrapeAgenda(dir);
        break;
      case '--ingest':
        cmdIngest(dir, commentsFile);
        break;
      case '--analyze':
        cmdAnalyze(dir, promptFile);
        break;
      case '--board':
        cmdBoard(dir);
        break;
      case '--reply-approve':
        cmdReplyApprove(dir);
        break;
      case '--mark-posted':
        cmdMarkPosted(dir, ids || '');
        break;
      case '--status':
        cmdStatus(dir);
        break;
      default:
        console.error(`Unknown command: ${command || '(none)'}\n`);
        console.error(USAGE);
        process.exit(1);
    }
  } catch (err) {
    console.error(`ERROR: ${err.message}`);
    process.exit(1);
  }
}

main();
