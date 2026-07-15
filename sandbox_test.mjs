#!/usr/bin/env node
/*
 * Local sandbox test for the public n8n workflow.
 *
 * This uses only mock data and local files. It does not call OpenRouter,
 * Notion, Slack, Docker, or any private/original repository.
 *
 * Run from the repo root:
 *   node sandbox_test.mjs
 */

import fs from "node:fs";
import assert from "node:assert/strict";

const WORKFLOW_PATH = "ai_daily_briefing_workflow.json";
const workflow = JSON.parse(fs.readFileSync(WORKFLOW_PATH, "utf8"));
const nodes = new Map(workflow.nodes.map((node) => [node.name, node]));

function pass(message) {
  console.log(`PASS ${message}`);
}

function getNode(name) {
  const node = nodes.get(name);
  assert.ok(node, `Missing workflow node: ${name}`);
  return node;
}

function makeNow(date = new Date("2026-07-12T07:00:00Z")) {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const pad = (value) => String(value).padStart(2, "0");
  return {
    get weekday() {
      const day = date.getUTCDay();
      return day === 0 ? 7 : day;
    },
    toSeconds() {
      return Math.floor(date.getTime() / 1000);
    },
    minus({ days = 0 } = {}) {
      const next = new Date(date);
      next.setUTCDate(next.getUTCDate() - days);
      return makeNow(next);
    },
    toFormat(format) {
      const yyyy = String(date.getUTCFullYear());
      const yy = yyyy.slice(-2);
      const MM = pad(date.getUTCMonth() + 1);
      const dd = pad(date.getUTCDate());
      const LLL = months[date.getUTCMonth()];
      return format
        .replaceAll("yyyy", yyyy)
        .replaceAll("yy", yy)
        .replaceAll("LLL", LLL)
        .replaceAll("MMM", LLL)
        .replaceAll("MM", MM)
        .replaceAll("dd", dd);
    },
  };
}

const mockNow = makeNow();
const mockEnv = {
  NOTION_DATABASE_ID: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  NOTION_INTEGRATION_TOKEN: "ntn_mock_token",
  SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/mock/webhook/url",
};

const outputs = new Map();

function dollar(nodeName) {
  assert.ok(outputs.has(nodeName), `No mock output registered for ${nodeName}`);
  return {
    first() {
      return { json: outputs.get(nodeName) };
    },
  };
}

function inputFrom(json) {
  return {
    first() {
      return { json };
    },
  };
}

function expressionBody(expression) {
  assert.ok(expression.startsWith("={{"), `Expected n8n expression, got: ${expression.slice(0, 30)}`);
  return expression.replace(/^=\{\{/, "").replace(/\}\}\s*$/, "");
}

function evaluateExpression(expression, { json = {}, input = inputFrom(json) } = {}) {
  const body = expressionBody(expression);
  return Function("$", "$env", "$json", "$input", `return (${body});`)(
    dollar,
    mockEnv,
    json,
    input,
  );
}

async function runCodeNode(name, inputJson, helpers = {}) {
  const code = getNode(name).parameters.jsCode;
  assert.ok(code, `Node has no jsCode: ${name}`);

  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  const fn = new AsyncFunction("$input", "$now", "$env", "$json", "$", "Buffer", code);
  const context = {
    helpers: {
      async httpRequest(request) {
        if (helpers.httpRequest) {
          return helpers.httpRequest(request);
        }
        throw new Error(`Unexpected mock HTTP request from ${name}: ${request.method} ${request.url}`);
      },
    },
  };

  const result = await fn.call(context, inputFrom(inputJson), mockNow, mockEnv, inputJson, dollar, Buffer);
  assert.ok(Array.isArray(result), `${name} should return an array`);
  assert.ok(result[0] && result[0].json, `${name} should return [{ json: ... }]`);
  return result[0].json;
}

function validateReferences() {
  for (const [source, connectionTypes] of Object.entries(workflow.connections || {})) {
    assert.ok(nodes.has(source), `Connection source does not exist: ${source}`);
    for (const outputsForType of Object.values(connectionTypes)) {
      for (const branch of outputsForType) {
        for (const connection of branch) {
          assert.ok(nodes.has(connection.node), `Connection target does not exist: ${source} -> ${connection.node}`);
        }
      }
    }
  }

  const text = fs.readFileSync(WORKFLOW_PATH, "utf8");
  const expressionRefs = [...text.matchAll(/\$\(\s*(['"])(.*?)\1\s*\)/g)].map((match) => match[2]);
  for (const ref of expressionRefs) {
    assert.ok(nodes.has(ref), `Expression references missing node: ${ref}`);
  }

  assert.equal(text.includes("Date.now("), false, "Workflow should use $now instead of Date.now()");
  assert.equal(text.includes("new Date("), false, "Workflow should use $now instead of new Date()");
  pass("workflow references and date usage");
}

async function main() {
  assert.equal(workflow.nodes.length, 18, "Expected 18 workflow nodes");
  validateReferences();

  const dateInfo = await runCodeNode("Node 2: Get Current Date", {});
  assert.equal(dateInfo.isoDate, "2026-07-12");
  assert.equal(dateInfo.date30DaysAgo, "2026-06-12");
  outputs.set("Node 2: Get Current Date", dateInfo);
  pass("Node 2 date output");

  const mockModels = {
    data: [
      {
        id: "openai/gpt-mock",
        name: "GPT Mock",
        pricing: { prompt: "0.000001", completion: "0.000002" },
        created: mockNow.toSeconds() - 3600,
        context_length: 128000,
      },
      {
        id: "meta-llama/mock-free:free",
        name: "Llama Mock Free",
        pricing: { prompt: "0", completion: "0" },
        created: mockNow.toSeconds() - 7200,
        context_length: 64000,
      },
    ],
  };
  const pricing = await runCodeNode("Node 5: Build Pricing Section", mockModels);
  assert.equal(pricing.selectedModel, "openrouter/free");
  assert.match(pricing.pricingSection, /Model Pricing Dashboard/);
  outputs.set("Node 5: Build Pricing Section", pricing);
  pass("Node 5 pricing dashboard and fixed OpenRouter route");

  outputs.set("Node 3: Run Research Engine", {
    stdout: [
      "# Research Results",
      "- **Mock model release**",
      "  URL: https://example.com/mock-model",
      "  Summary: A mock model update used only for sandbox testing.",
    ].join("\n"),
  });

  const node6Body = evaluateExpression(getNode("Node 6: AI Generate Report").parameters.jsonBody);
  assert.equal(node6Body.model, "openrouter/free");
  assert.equal(node6Body.messages[0].role, "user");
  assert.match(node6Body.messages[0].content, /RESEARCH DATA/);
  pass("Node 6 OpenRouter daily request body");

  const mockDailyAi = {
    choices: [
      {
        message: {
          content: [
            "```json",
            JSON.stringify({
              summary: "Mock daily summary.",
              category: ["Open Source"],
              topics: ["AI Agents"],
              providers: ["OpenAI"],
              featured_models: ["GPT"],
              importance: "High",
              new_model_released: true,
              pricing_changed: false,
              open_source: true,
              free_promotion: false,
              worth_installing: true,
              best_coding_model: "MockCoder",
              best_reasoning_model: "MockReasoner",
              best_local_model: "MockLocal",
              best_value_api: "MockValue",
              biggest_release: "Mock Release",
            }, null, 2),
            "```",
            "## Executive Summary",
            "Mock daily report paragraph.",
            "- First highlight",
            "- Second highlight",
            "## Sources",
            "- https://example.com/mock-model",
          ].join("\n"),
        },
      },
    ],
  };
  const parsedDaily = await runCodeNode("Node 7: Parse + markdownToBlocks", mockDailyAi);
  assert.equal(parsedDaily.importance, "High");
  assert.ok(parsedDaily.blockChunks.length > 0);
  assert.match(parsedDaily.sshCommand, /\/home\/ubuntu\/reports\//);
  outputs.set("Node 7: Parse + markdownToBlocks", parsedDaily);
  pass("Node 7 daily AI parsing and Notion block conversion");

  const node8Body = evaluateExpression(getNode("Node 8: Create Notion Page").parameters.jsonBody, {
    json: parsedDaily,
  });
  assert.equal(node8Body.parent.database_id, mockEnv.NOTION_DATABASE_ID);
  assert.ok(node8Body.properties.Name.title.length > 0);
  pass("Node 8 Notion page payload");

  outputs.set("Node 8: Create Notion Page", {
    id: "daily-page-id",
    url: "https://notion.so/mock-daily",
  });
  const appendCalls = [];
  const appendResult = await runCodeNode("Node 9: Append Block Chunks", {}, {
    async httpRequest(request) {
      appendCalls.push(request);
      assert.equal(request.method, "PATCH");
      assert.match(request.url, /\/v1\/blocks\/daily-page-id\/children$/);
      return { ok: true };
    },
  });
  assert.equal(appendResult.chunkErrors, 0);
  assert.equal(appendCalls.length, parsedDaily.blockChunks.length);
  outputs.set("Node 9: Append Block Chunks", {
    ...appendResult,
    notionPageUrl: "https://notion.so/mock-daily",
  });
  pass("Node 9 mocked Notion block append");

  const archiveResult = await runCodeNode("Node 11: Archive Old Notion Pages", {}, {
    async httpRequest(request) {
      if (request.method === "POST") {
        assert.match(request.url, /\/databases\/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\/query$/);
        const body = JSON.parse(request.body);
        assert.equal(body.filter.and[0].property, "Date");
        assert.equal(body.filter.and[1].property, "Report Type");
        return { results: [{ id: "old-page-1" }] };
      }
      if (request.method === "PATCH") {
        assert.match(request.url, /\/v1\/pages\/old-page-1$/);
        assert.deepEqual(JSON.parse(request.body), { archived: true });
        return { ok: true };
      }
      throw new Error(`Unexpected archive request: ${request.method} ${request.url}`);
    },
  });
  assert.equal(archiveResult.archived, 1);
  pass("Node 11 mocked Notion archive");

  const dailySlack = evaluateExpression(getNode("Node 12: Slack Morning Briefing").parameters.jsonBody);
  assert.equal(dailySlack.blocks[0].type, "header");
  assert.equal(dailySlack.blocks[2].elements[0].url, "https://notion.so/mock-daily");
  pass("Node 12 Slack daily Block Kit payload");

  const sundayCondition = getNode("Node 13: Is Sunday?").parameters.conditions.conditions[0];
  assert.equal(sundayCondition.leftValue, "={{ $now.weekday }}");
  assert.equal(sundayCondition.rightValue, 7);
  assert.equal(mockNow.weekday, 7);
  pass("Node 13 Sunday condition");

  const node14Body = evaluateExpression(getNode("Node 14: Query Past 7 Days").parameters.jsonBody);
  assert.equal(node14Body.filter.property, "Report Type");
  assert.equal(node14Body.page_size, 7);
  pass("Node 14 weekly Notion query payload");

  const weeklyPrompt = await runCodeNode("Node 15: Build Weekly Prompt", {
    results: [
      {
        properties: {
          Name: { title: [{ plain_text: "AI-Updates-12-07-26" }] },
          Summary: { rich_text: [{ plain_text: "Mock daily summary." }] },
          Importance: { select: { name: "High" } },
        },
      },
    ],
  });
  assert.match(weeklyPrompt.prompt, /weekly/i);
  outputs.set("Node 15: Build Weekly Prompt", weeklyPrompt);
  pass("Node 15 weekly prompt");

  const node16Body = evaluateExpression(getNode("Node 16: OpenRouter Weekly Report").parameters.jsonBody, {
    json: weeklyPrompt,
  });
  assert.equal(node16Body.model, "openrouter/free");
  assert.equal(node16Body.messages[0].content, weeklyPrompt.prompt);
  pass("Node 16 OpenRouter weekly request body");

  const mockWeeklyAi = {
    choices: [
      {
        message: {
          content: [
            "```json",
            JSON.stringify({
              summary: "Mock weekly summary.",
              category: ["AI Agents"],
              topics: ["MCP"],
              providers: ["OpenAI"],
              featured_models: ["GPT"],
              importance: "High",
              new_model_released: false,
              pricing_changed: false,
              open_source: false,
              free_promotion: false,
              worth_installing: false,
              best_coding_model: "MockCoder",
              best_reasoning_model: "MockReasoner",
              best_local_model: "MockLocal",
              best_value_api: "MockValue",
              biggest_release: "Mock Weekly Release",
            }, null, 2),
            "```",
            "## Weekly Executive Summary",
            "Mock weekly report paragraph.",
          ].join("\n"),
        },
      },
    ],
  };
  const weeklyResult = await runCodeNode("Node 17: Create Weekly Notion Page", mockWeeklyAi, {
    async httpRequest(request) {
      if (request.method === "POST") {
        assert.equal(request.url, "https://api.notion.com/v1/pages");
        const body = JSON.parse(request.body);
        assert.equal(body.parent.database_id, mockEnv.NOTION_DATABASE_ID);
        return { id: "weekly-page-id", url: "https://notion.so/mock-weekly" };
      }
      if (request.method === "PATCH") {
        assert.match(request.url, /\/v1\/blocks\/weekly-page-id\/children$/);
        return { ok: true };
      }
      throw new Error(`Unexpected weekly request: ${request.method} ${request.url}`);
    },
  });
  assert.equal(weeklyResult.chunkErrors, 0);
  outputs.set("Node 17: Create Weekly Notion Page", weeklyResult);
  pass("Node 17 mocked weekly Notion page");

  const weeklySlack = evaluateExpression(getNode("Node 18: Slack Weekly Briefing").parameters.jsonBody);
  assert.equal(weeklySlack.blocks[0].type, "header");
  assert.equal(weeklySlack.blocks[2].elements[0].url, "https://notion.so/mock-weekly");
  pass("Node 18 Slack weekly Block Kit payload");

  console.log("\nSandbox workflow test completed successfully.");
}

main().catch((error) => {
  console.error(`\nSandbox workflow test failed: ${error.message}`);
  if (process.env.DEBUG) {
    console.error(error);
  }
  process.exitCode = 1;
});
