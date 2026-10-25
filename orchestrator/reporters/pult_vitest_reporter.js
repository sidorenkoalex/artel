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
// Форма API отчётчиков (`onTestRunEnd`, `TestModule`, `TestSuite`,
// `TestCase`) сверена с Vitest 4.1.5 пробой 25.10 (SPEC
// 01M5S6M2MZV68QH9QHWY0XP0YA, требование 2). Правила:
// а) хук упал — в `task.result.hooks` значение `"fail"` или `"run"` (Vitest 4
//    оставляет брошенному хуку `"run"`); у теста — `beforeEach`, затем
//    `afterEach`;
// б) тест без своей ошибки (`passed`/`skipped`), не `skip`/`todo` и без
//    упавшего хука своего уровня — провал с хуком ближайшего предка (до
//    модуля), у которого упал `beforeAll`/`afterAll` и `errors()` непуст;
// в) то же для `afterAll`: прошедший до него тест — провал;
// г) класс ошибки — из собственного `constructor` вида `Function<Имя>`
//    (кроме `Error`/`anonymous`), иначе из `name`;
// д) ошибка `.only` у теста или предка — `mode: "only"`, провал;
// е) упавший хук модуля при тестах в нём уходит в записи тестов по б), без
//    записи уровня файла; ошибка сбора — прежняя запись уровня файла;
// е2) `hook` — только у записи `fail`.
import fs from "node:fs";
import path from "node:path";

const TIMEOUT = /timed? ?out/i;
const TEST_HOOKS = ["beforeEach", "afterEach"];
const SUITE_HOOKS = ["beforeAll", "afterAll"];
const FILE_LEVEL_NAME = "<ошибка уровня файла>";
const ONLY_MESSAGE = "[Vitest] Unexpected .only modifier";
const CONSTRUCTOR = /^Function<(.+)>$/;

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

function failedHook(node, names) {
  const task = node && node.task;
  const hooks = (task && task.result && task.result.hooks) || {};
  for (const name of names) {
    if (hooks[name] === "fail" || hooks[name] === "run") {
      return name;
    }
  }
  return null;
}

function errorName(error) {
  const found = error || {};
  // Сериализованная ошибка несёт класс собственным полем `constructor`;
  // унаследованный `Object` у разобранного JSON — не класс ошибки.
  const own = Object.prototype.hasOwnProperty.call(found, "constructor")
    ? found.constructor : undefined;
  const match = typeof own === "string" ? CONSTRUCTOR.exec(own) : null;
  if (match && match[1] !== "Error" && match[1] !== "anonymous") {
    return match[1];
  }
  return found.name || null;
}

function nodeErrors(node) {
  return (node && typeof node.errors === "function" && node.errors()) || [];
}

function* ancestors(test) {
  let node = test.parent;
  while (node) {
    yield node;
    if (node.type === "module") {
      return;
    }
    node = node.parent;
  }
}

function isOnly(error) {
  return String((error && error.message) || "").startsWith(ONLY_MESSAGE);
}

function onlyErrors(test, own) {
  if (own.some(isOnly)) {
    return own;
  }
  for (const node of ancestors(test)) {
    const errors = nodeErrors(node);
    if (errors.some(isOnly)) {
      return errors;
    }
  }
  return null;
}

function suiteHookFailure(test) {
  for (const node of ancestors(test)) {
    const hook = failedHook(node, SUITE_HOOKS);
    const errors = nodeErrors(node);
    if (hook && errors.length) {
      return {hook, errors};
    }
  }
  return null;
}

function hasTimeout(errors) {
  return errors.some((e) => TIMEOUT.test(String(e.message || "")));
}

function record(test, root) {
  const result = test.result();
  const diagnostic = (test.diagnostic && test.diagnostic()) || {};
  const own = (result && result.errors) || [];
  const raw = result ? result.state : "skipped";
  const state = {passed: "pass", failed: "fail", skipped: "skip",
                 pending: "skip"}[raw] || "fail";
  const declared = (test.options && test.options.mode) || "run";
  const moduleId = test.module ? test.module.moduleId : "";
  const entry = {
    file: moduleId ? path.relative(root, moduleId) : "",
    name: fullName(test),
    state: declared === "todo" ? "todo" : state,
    mode: declared,
    fails: Boolean(test.options && test.options.fails),
    retry_count: Number(diagnostic.retryCount || 0),
    error_name: errorName(own[0]),
    timeout: hasTimeout(own),
    hook: null,
    duration_ms: Number(diagnostic.duration || 0),
  };
  const only = onlyErrors(test, own);
  if (only) {
    const error = only.find(isOnly);
    return {...entry, state: "fail", mode: "only", error_name: errorName(error),
            timeout: hasTimeout([error])};
  }
  const ownHook = failedHook(test, TEST_HOOKS);
  const clean = (raw === "passed" || raw === "skipped") && !own.length;
  if (clean && declared !== "skip" && declared !== "todo" && !ownHook) {
    const inherited = suiteHookFailure(test);
    if (inherited) {
      return {...entry, state: "fail", hook: inherited.hook,
              error_name: errorName(inherited.errors[0]),
              timeout: hasTimeout(inherited.errors)};
    }
  }
  if (entry.state === "fail") {
    entry.hook = ownHook;
  }
  return entry;
}

function moduleErrorRecord(mod, root, hasTests) {
  const errors = nodeErrors(mod);
  if (!errors.length || (hasTests && failedHook(mod, SUITE_HOOKS))) {
    return null;
  }
  const first = errors[0] || {};
  return {
    file: mod.moduleId ? path.relative(root, mod.moduleId) : "",
    name: FILE_LEVEL_NAME,
    state: "fail",
    file_level: true,
    error_name: errorName(first),
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
      const records = [...mod.children.allTests()].map((t) => record(t, root));
      tests.push(...records);
      const level = moduleErrorRecord(mod, root, records.length > 0);
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
