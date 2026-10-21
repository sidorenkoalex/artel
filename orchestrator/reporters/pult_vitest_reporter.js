// Отчётчик пульта для компонента `report: pult-vitest` (SPEC
// 01M590GJAF0EDV4NBC4C99MFVH, требование 5; форма JSON — ANSWER-2, В2).
//
// Пульт подключает файл флагом `--reporter=<путь>` (подстановка
// `{pult_reporter}` в `report_args` компонента), путь отчёта — флагом
// `--outputFile=<путь>` (`{path}`) и переменной `PULT_VITEST_REPORT`. Итог
// прогона пульт читает только из этого JSON: по каждому тесту — файл (от
// `workdir`), полное имя, состояние, `mode`, признак `it.fails`, число
// повторов, имя ошибки, признак таймаута, падение хука и время. Ошибка
// самого модуля (импорт, сбор) — отдельная запись уровня файла
// (`file_level: true`, имя и сообщение первой ошибки; SPEC
// 01M5EDW6KD1ESCEVRSV2WPNXAP, требование 1): иначе файл пропал бы из отчёта.
//
// API отчётчиков Vitest 3/4 (`onTestRunEnd`, `TestModule`, `TestCase`);
// соответствие версии подтверждает проба этапа 2 (перевод записи sled).
import fs from "node:fs";
import path from "node:path";

const TIMEOUT = /timed? ?out/i;
const HOOKS = ["beforeAll", "beforeEach", "afterEach", "afterAll"];
const FILE_LEVEL_NAME = "<ошибка уровня файла>";

function outputPath(ctx) {
  if (process.env.PULT_VITEST_REPORT) {
    return process.env.PULT_VITEST_REPORT;
  }
  const out = ctx && ctx.config ? ctx.config.outputFile : undefined;
  if (typeof out === "string") {
    return out;
  }
  if (out && typeof out === "object") {
    const values = Object.values(out).filter((v) => typeof v === "string");
    return values.length ? values[0] : undefined;
  }
  return undefined;
}

function fullName(test) {
  const names = [];
  let node = test;
  while (node && node.type !== "module") {
    names.unshift(node.name);
    node = node.parent;
  }
  return names.join(" > ");
}

function failedHook(task) {
  const hooks = (task && task.result && task.result.hooks) || {};
  for (const name of HOOKS) {
    if (hooks[name] === "fail") {
      return name;
    }
  }
  return null;
}

function record(test, root) {
  const result = test.result();
  const diagnostic = (test.diagnostic && test.diagnostic()) || {};
  const errors = (result && result.errors) || [];
  const first = errors[0] || {};
  const state = {passed: "pass", failed: "fail", skipped: "skip",
                 pending: "skip"}[result ? result.state : "skipped"] || "fail";
  const mode = (test.options && test.options.mode) || "run";
  const moduleId = test.module ? test.module.moduleId : "";
  return {
    file: moduleId ? path.relative(root, moduleId) : "",
    name: fullName(test),
    state: mode === "todo" ? "todo" : state,
    mode,
    fails: Boolean(test.options && test.options.fails),
    retry_count: Number(diagnostic.retryCount || 0),
    error_name: first.name || null,
    timeout: errors.some((e) => TIMEOUT.test(String(e.message || ""))),
    hook: failedHook(test.task),
    duration_ms: Number(diagnostic.duration || 0),
  };
}

function moduleErrorRecord(mod, root) {
  const errors = (typeof mod.errors === "function" && mod.errors()) || [];
  if (!errors.length) {
    return null;
  }
  const first = errors[0] || {};
  return {
    file: mod.moduleId ? path.relative(root, mod.moduleId) : "",
    name: FILE_LEVEL_NAME,
    state: "fail",
    file_level: true,
    error_name: first.name || null,
    error_message: String(first.message || ""),
  };
}

export default class PultVitestReporter {
  onInit(ctx) {
    this.ctx = ctx;
  }

  onTestRunEnd(testModules) {
    const root = process.cwd();
    const tests = [];
    for (const mod of testModules || []) {
      for (const test of mod.children.allTests()) {
        tests.push(record(test, root));
      }
      const level = moduleErrorRecord(mod, root);
      if (level) {
        tests.push(level);
      }
    }
    const target = outputPath(this.ctx);
    if (!target) {
      return;
    }
    fs.mkdirSync(path.dirname(target), {recursive: true});
    fs.writeFileSync(target, JSON.stringify({tests}));
  }
}
