"""Аудит SPEC — шаг роли spec_auditor между сдачей SPEC аналитиком и гейтом SPEC: вход, бриф, глубина по сигналам, выход по вердикту, свежесть и привязка вердикта, возвраты аналитику, эскалация, вердикт на гейте, флаг approve и повторный аудит.

Группа: долгоживущий
Красен до реализации: состояния spec_audit нет — задача с TZ.md из spec_writing уходит сразу в spec_gate, роль spec_auditor не резолвится из config.STATE_ROLE (шаг аудитора не стартует), тип артефакта spec_audit и имя SPEC-AUDIT.md пульт не знает (автокоммит отбрасывает файл как посторонний), команды spec-audit и флага --accept-audit-fail нет; зелены с рождения только сценарии прежнего поведения — задача без ТЗ (AC-3), батч вопросов и SPEC без AC-разметки (AC-4), бюджет на approve (вторая половина AC-5), approve задачи без вердикта (часть AC-20).

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): главная копия
пульта с синтетическими скилами ролей и картой кодовой базы в `main`,
bare `origin` рядом, запись артели в `targets.yaml` называет его полем
`url`; клон проекта, ссылку документов задачи и её рабочую копию заводят
`init`/`new`. Задача с ТЗ заводится `catalog.cmd_new(<название>, <файл ТЗ>)`.
Шаг каждой роли (analyst, spec_auditor) — штатный `runner.cmd_run` с
подменённым запуском агента (`runner.spawn_agent`): подмена пишет документы
роли в каталог документов задачи и запоминает промпт шага, а переносит их в
ссылку документов автокоммит пульта по итогам шага — так «свежий вердикт»
(последний коммит `SPEC-AUDIT.md` — автокоммит шага spec_auditor после
входа) получается тем же путём, что в жизни. Правки Оператора в ссылке
документов (ответы, подмена файла) — коммитом в отдельной рабочей копии
ссылки и `update-ref`, с перефиксацией. Переходы — публичные
`fsm.cmd_advance`/`fsm.cmd_reject`; `approve` и `spec-audit` — через
диспетчер `artel.main` (разбор аргументов командной строки входит в
предмет); вывод `show`/`status` — `catalog.cmd_show`/`catalog.cmd_status`,
остановка цикла — `auto.cmd_auto`.

Роль `spec_auditor` в карте исполнителей — фикстурой сценария
(`use_role_map`), не боевым `roles.yaml`: запись роли в нём едет
приложением PLAN и проверяется отдельно.

Как планка читает поверхности, которые SPEC не фиксирует буквально:
- sha версии SPEC — sha содержимого файла SPEC в ссылке документов
  (`git rev-parse <ссылка>:<путь SPEC>`), запись журнала входа ищется среди
  записей задачи с последней записи `state -> spec_audit` включительно;
- глубина разбора — фраза брифа «полн… разбор/аудит» против «кратк…
  разбор/аудит», ровно одна из двух;
- сработавший сигнал «назван» в журнале, если запись входа несёт его
  имя: «Меняемое поведение» (а), «мандат» либо текст строки мандата (б),
  сам путь-признак либо имя его категории в константе `config` (в,
  пути), «защищ…» либо сам путь (в, защищённый путь), «приложени…» (в,
  приложение PLAN), «budget»/«бюджет» (г), «ADR» (д);
- вердикт в выводе — слово `pass`/`concerns`/`fail` отдельным словом.

Имена, метки текстов, бюджеты и выбор вариантов берутся из `random`; зерно
печатается и входит в текст каждого провала.

Планка провалидирована временным стабом реализации (состояние, вход и выход
аудита по журналу, свежесть по префиксу автокоммита и предку головы ссылки
на входе, привязка по sha содержимого, бриф аудитора, флаг approve,
команда spec-audit, вердикт в show/status/auto, перечни состояний): все
методы зелёные; мутации стаба — снятая свежесть, снятые сверки sha
содержимого и `spec_sha`, счётчик возвратов от последнего гейта, снятый
триггер возврата брифа, порог бюджета `>`, снятая ветка обязательного
артефакта, флаг за позиционный sha, sha головы ссылки в записи входа,
снятая проверка fail на approve, имя вне белого списка, глубина всегда
полная, мандат не сигнал, QUESTIONS в брифе, только последний ANSWER,
concerns как fail, escalate как «не готово», флаг в любом состоянии,
spec-audit из любого состояния, вердикт status из файла, бюджет только на
approve — красили соответствующие методы; стаб удалён, код не тронут.
"""
import contextlib
import hashlib
import io
import os
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (answer, artel, auto, catalog, config, fixation, fsm,
                          keychain, runner, stack, store)
from tests.sandbox import (FIXTURE_ROLES, FIXTURE_TIER, FakeProc, RealGitSandbox,
                           _stub_check_stack, capture, capture_new_task_id,
                           event, is_claude_call, resilient_tmp_cleanup)

ARTEL = config.DEFAULT_TARGET
AUDIT = "spec_audit"
AUDITOR = "spec_auditor"
AUDIT_FILE = "SPEC-AUDIT.md"
FLAG = "--accept-audit-fail"
DOCS_REF_PREFIX = "refs/artifacts/"
RETURN_HEADER = "Причина возврата"
MISSING = "шаг завершён без артефакта"
FULL_RE = re.compile(r"полн\w*\s+(разбор|аудит)", re.I)
SHORT_RE = re.compile(r"кратк\w*\s+(разбор|аудит)", re.I)
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
RESULT = event(type="result", subtype="success", is_error=False,
               result="готово", total_cost_usd=0.001)
NEUTRAL_ZONE = "app/core.py"
AUDIT_SECTIONS = ("ТЗ и SPEC", "Факты против кода", "Проверяемость критериев",
                  "Зоны", "Матрица неослабления", "Пути обхода гейтов",
                  "Вердикт")
MATRIX_TABLE = (
    "| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, "
    "проверка — файл:строка) | Остаётся ли свойство после изменения | Чем "
    "покрыто после (тест файл:строка) или «не покрыто» | Решение |\n"
    "|---|---|---|---|---|\n"
    "| Фикстура | Фикстура | Да | Фикстура | Фикстура |\n")

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: {budget}
---

# SPEC: фикстура аудита {marker}

## Контекст

Метка версии {marker}.

## Требования

1. Требование фикстуры {marker}.{extra}

## Критерии приёмки

{criteria}
{behavior}
## Не входит

Ничего.
"""

ANSWER_TEXT = """---
task: {task}
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-{n}: ответ Оператора

## Ответы

{body}
"""

QUESTIONS_TEXT = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Вопрос {marker}?**
   - A) да
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - B) нет
     - ломается: ничего, фикстура
     - ослабляется: ничего, фикстура
     - цена: нет
     - чьё решение: Оператор
   - дефолт: A.
"""


def word(rng: random.Random, length: int = 8) -> str:
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(length))


def blob_sha(text: str) -> str:
    """sha объекта git, которым станет `text` в дереве коммита."""
    data = text.encode("utf-8")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def path_signal_categories() -> dict:
    """Константа `config` с путями-признаками сигнала 7в: отображение
    «категория -> непустой перечень путей», среди путей которого есть
    `orchestrator/advance_gates/` и `gates.yaml`. Имя константы SPEC не
    называет — она ищется по содержимому."""
    found = {}
    for name in dir(config):
        value = getattr(config, name)
        if not isinstance(value, dict) or len(value) < 4:
            continue
        if not all(isinstance(v, (list, tuple, frozenset, set)) and v
                   for v in value.values()):
            continue
        paths = {p for v in value.values() for p in v if isinstance(p, str)}
        if {"orchestrator/advance_gates/", "gates.yaml"} <= paths:
            found[name] = value
    return found


class SpecAuditSandbox(RealGitSandbox):
    """Главная копия пульта со скилами и картой, bare `origin` артели,
    клон проекта от `init`; ключи, pre-flight и стек ролей подменены, роль
    `spec_auditor` — в карте исполнителей фикстуры."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)

        self.map_marker = f"karta{word(self.rng)}"
        skill_names = {name for fields in FIXTURE_ROLES.values()
                       for name in fields.get("skills", ())}
        for name in sorted(skill_names | {"spec-audit"}):
            path = self.root / "skills" / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# Скил {name} фикстуры\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        (self.root / NEUTRAL_ZONE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / NEUTRAL_ZONE).write_text("VALUE = 1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "пульт")
        base = self.git("rev-parse", "HEAD").strip()
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            f"---\nbuilt_at_sha: {base}\n---\n\n# Карта {self.map_marker}\n",
            encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "карта")

        origin_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, origin_tmp)
        self.scratch = Path(origin_tmp.name).resolve()
        self.origin = self.scratch / "artel.git"
        self.git("init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(self.origin))
        config.TARGETS.write_text(
            "targets:\n" + TARGET_ENTRY.format(name=ARTEL, url=str(self.origin),
                                               base=config.MAIN_BRANCH),
            encoding="utf-8")
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.git("fetch", "-q", "origin")
        self.clone = config.PROJECTS / ARTEL / "repo"

        for patcher in (mock.patch.object(stack, "check_stack", _stub_check_stack),
                        mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                        mock.patch("orchestrator.doctor.preflight_checks",
                                   lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        capture(catalog.cmd_init)
        self.use_role_map(roles={AUDITOR: {
            "executor": "agent", "token_slot": "artel-spec-auditor",
            "skills": ["conventions-core", "escalation-rules", "spec-audit"],
            "model_tier": FIXTURE_TIER}})
        self.prompts = []

    # ------------------------------------------------------------ обвязка

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def run_cmd(self, fn, *args, **kwargs) -> str:
        """Вывод команды вместе с текстом ненулевого `SystemExit`."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def cli(self, *argv: str) -> str:
        """Команда Оператора через диспетчер `artel.main`."""
        with mock.patch("sys.argv", ["artel.py", *argv]):
            return self.run_cmd(artel.main)

    def git_in_clone(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    # ------------------------------------------------------------ задача

    def new_task(self, tz: str | None = "") -> str:
        """Задача артели; `tz` — текст ТЗ (`None` — задача без ТЗ)."""
        title = f"Аудит {word(self.rng)}"
        if tz is None:
            _, task = capture_new_task_id(lambda: catalog.cmd_new(title))
            return task
        path = self.scratch / f"tz-{word(self.rng)}.txt"
        raw = tz or f"Хотим функцию {word(self.rng)} в отчёте задач.\n"
        path.write_text(raw, encoding="utf-8")
        _, task = capture_new_task_id(lambda: catalog.cmd_new(title, str(path)))
        return task

    def row(self, task: str):
        return store.get_task(store.db(), task)

    def state(self, task: str) -> str:
        return self.row(task)["state"]

    def set_state(self, task: str, state: str) -> None:
        store.update_task(store.db(), task, state=state)
        store.record_fixation(store.db(), task)

    def docs_dir(self, task: str) -> Path:
        return config.PROJECTS / ARTEL / "tasks" / task

    def ref(self, task: str) -> str:
        return DOCS_REF_PREFIX + task

    def rel(self, task: str, name: str) -> str:
        return "/".join(("tasks", task, name))

    def ref_head(self, task: str) -> str:
        return self.git_in_clone("for-each-ref", "--format=%(objectname)",
                                 self.ref(task)).strip()

    def ref_file_sha(self, task: str, name: str = "SPEC.md") -> str:
        return self.git_in_clone("rev-parse",
                                 f"{self.ref(task)}:{self.rel(task, name)}").strip()

    def ref_text(self, task: str, name: str) -> str | None:
        """Текст файла задачи в ссылке документов; `None` — файла там нет."""
        rel = self.rel(task, name)
        listed = self.git_in_clone("ls-tree", "--name-only", self.ref(task), "--", rel)
        if rel not in listed.splitlines():
            return None
        return self.git_in_clone("show", f"{self.ref(task)}:{rel}")

    def commit_docs(self, task: str, files: dict, message: str) -> None:
        """Правка Оператора в ссылке документов: отдельная рабочая копия на
        её голове, коммит `files` (имя внутри каталога задачи -> текст),
        `update-ref` и перефиксация."""
        old = self.ref_head(task)
        self.assertTrue(old, self.msg("ссылки документов нет"))
        scratch = self.scratch / f"docs-copy-{self.rng.randrange(1 << 40)}"
        self.git_in_clone("worktree", "add", "-q", "--detach", str(scratch), old)
        try:
            for name, text in files.items():
                target = scratch.joinpath("tasks", task, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m", message)
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git_in_clone("worktree", "remove", "--force", str(scratch))
        self.git_in_clone("update-ref", self.ref(task), new, old)
        store.record_fixation(store.db(), task)

    def add_answer(self, task: str, n: int, body: str) -> None:
        self.commit_docs(task, {f"ANSWER-{n}.md": ANSWER_TEXT.format(
            task=task, n=n, body=body)}, f"{task}: ANSWER-{n} — ответ Оператора")

    # ------------------------------------------------------------ журнал

    def steps(self, task: str) -> list:
        return list(store.task_steps(store.db(), task))

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.steps(task))

    def last_entry_id(self, task: str, state: str) -> int:
        ids = [r["id"] for r in self.steps(task)
               if r["action"] == f"state -> {state}"]
        self.assertTrue(ids, self.msg(f"записи state -> {state} нет:\n"
                                      f"{self.journal(task)}"))
        return ids[-1]

    def visit_text(self, task: str, state: str = AUDIT) -> str:
        """Записи журнала с последнего входа в `state` (включительно) до
        следующего перехода, без записей самого шага роли."""
        start = self.last_entry_id(task, state)
        lines = []
        for r in self.steps(task):
            if r["id"] < start or r["actor"] == AUDITOR:
                continue
            if r["id"] > start and r["action"].startswith("state -> "):
                break
            lines.append(f"{r['action']} | {r['detail'] or ''}")
        return "\n".join(lines)

    def text_since(self, task: str, start_id: int) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.steps(task)
                         if r["id"] > start_id and r["actor"] != AUDITOR)

    def max_step_id(self, task: str) -> int:
        rows = self.steps(task)
        return rows[-1]["id"] if rows else 0

    def state_entries(self, task: str) -> list:
        return [r["action"][len("state -> "):] for r in self.steps(task)
                if r["action"].startswith("state -> ")]

    # ------------------------------------------------------------ шаги

    def role_step(self, task: str, docs, lines=()) -> str:
        """Шаг роли текущего состояния штатным `runner.cmd_run`: подменённый
        агент пишет `docs` (имя -> текст; вызываемое — посчитать на старте
        агента) в каталог документов задачи и печатает `lines`."""
        before = len(self.prompts)

        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            stdin = kwargs.get("stdin")
            name = getattr(stdin, "name", None)
            self.prompts.append(Path(name).read_text(encoding="utf-8")
                                if name else "")
            files = docs() if callable(docs) else docs
            for rel, text in files.items():
                path = self.docs_dir(task) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return FakeProc([*lines, RESULT])

        out = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                runner.cmd_run(task)
            except SystemExit as exc:
                out.write(f"\nSystemExit(run): {exc.code}")
        self.assertEqual(len(self.prompts), before + 1, self.msg(
            f"агент шага не запущен (состояние {self.state(task)}):\n"
            f"{out.getvalue()}\n{self.journal(task)}"))
        return out.getvalue()

    def advance(self, task: str) -> str:
        return self.run_cmd(fsm.cmd_advance, task)

    def spec(self, task: str, *, zones: str = NEUTRAL_ZONE, budget: int = 30,
             behavior: bool = False, extra: str = "", ac_markup: bool = True,
             marker: str | None = None) -> str:
        marker = marker or word(self.rng)
        criteria = (f"AC-1. Критерий фикстуры {marker}." if ac_markup
                    else f"1. Критерий без разметки {marker}.")
        section = ""
        if behavior:
            section = ("\n## Меняемое поведение\n\n"
                       f"- `tests/test_fx_{word(self.rng)}.py::FxTest::test_value`: "
                       f"`1` → `2` (требование 1)\n")
        return SPEC_TEXT.format(task=task, zones=zones, budget=budget,
                                marker=marker, extra=extra, criteria=criteria,
                                behavior=section)

    def audit_text(self, task: str, verdict: str, spec_sha: str, *,
                   status: str = "ready", deviation: str = "",
                   escalation: str = "") -> str:
        body = "".join(f"## {name}\n\n{MATRIX_TABLE if name == 'Матрица неослабления' else 'Разбор фикстуры.'}\n\n"
                       for name in AUDIT_SECTIONS[:-1])
        body += f"## Вердикт\n\n{deviation or 'Отклонений нет.'}\n"
        if escalation:
            body += ("\n## Эскалация\n\n"
                     f"- **Вопросы** — {escalation}\n"
                     "- **Контекст** — фикстура песочницы.\n"
                     "- **Блокирует** — вердикт аудита.\n")
        return (f"---\ntask: {task}\ntype: spec_audit\nauthor_role: {AUDITOR}\n"
                f"status: {status}\nverdict: {verdict}\nsignals: нет\n"
                f"spec_sha: {spec_sha}\n---\n\n# SPEC-AUDIT: аудит фикстуры\n\n"
                f"{body}")

    def submit_spec(self, task: str, spec_text: str, extra_docs=None,
                    lines=()) -> str:
        """Шаг аналитика пишет SPEC (и `extra_docs`), затем `advance`."""
        docs = {"SPEC.md": spec_text, **(extra_docs or {})}
        out = self.role_step(task, docs, lines)
        return out + self.advance(task)

    def enter_audit(self, task: str, spec_text: str, **kwargs) -> str:
        out = self.submit_spec(task, spec_text, **kwargs)
        self.assertEqual(self.state(task), AUDIT, self.msg(
            f"задача не вошла в {AUDIT}:\n{out}\n{self.journal(task)}"))
        return out

    def audit_step(self, task: str, verdict: str, *, spec_sha: str | None = None,
                   status: str = "ready", deviation: str = "",
                   escalation: str = "", extra_docs=None) -> str:
        """Шаг аудитора: `SPEC-AUDIT.md` с `spec_sha` (по умолчанию — sha
        содержимого SPEC в ссылке на старте агента)."""
        def docs():
            sha = spec_sha or self.ref_file_sha(task)
            return {AUDIT_FILE: self.audit_text(task, verdict, sha, status=status,
                                                deviation=deviation,
                                                escalation=escalation),
                    **(extra_docs or {})}
        return self.role_step(task, docs)

    def audit(self, task: str, verdict: str, **kwargs) -> str:
        out = self.audit_step(task, verdict, **kwargs)
        return out + self.advance(task)

    def deviation(self) -> str:
        return (f"Отклонение {word(self.rng)}: критерий AC-1 непроверяем "
                f"(SPEC.md:{self.rng.randrange(10, 99)}).")

    def to_gate_after_fail_returns(self, task: str, returns: int,
                                   final: str = "pass") -> None:
        """`returns` возвратов по fail, затем визит с вердиктом `final`."""
        self.enter_audit(task, self.spec(task))
        for n in range(returns):
            out = self.audit(task, "fail", deviation=self.deviation())
            self.assertEqual(self.state(task), "spec_writing", self.msg(
                f"fail №{n + 1} не вернул аналитику:\n{out}\n{self.journal(task)}"))
            self.enter_audit(task, self.spec(task))
        out = self.audit(task, final, deviation=self.deviation())
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"вердикт {final} не довёл до spec_gate:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-2, AC-3

class EntryRouteTest(SpecAuditSandbox):

    def test_ac2_task_with_tz_goes_to_spec_audit_not_spec_gate(self):
        """Задача с ТЗ, SPEC ready и чистым guard после advance — в spec_audit.

        Сценарий: задача заведена с ТЗ, шаг аналитика пишет годный SPEC
        (`status: ready`, AC-разметка), `advance` из `spec_writing`.
        Задача в `spec_audit`, записи `state -> spec_gate` в журнале нет.

        Ловит мутацию: аудит пропущен — переход по-прежнему
        `set_state(..., "spec_gate")` (или маршрут выбирается по признаку,
        которого у задачи с ТЗ нет) — задача оказывается в `spec_gate`.
        """
        task = self.new_task()
        out = self.submit_spec(task, self.spec(task))
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), AUDIT, context)
        self.assertNotIn("spec_gate", self.state_entries(task), context)

    def test_ac3_task_without_tz_goes_to_spec_gate_as_before(self):
        """Задача без ТЗ (SPEC пишет Оператор) после advance — в spec_gate, мимо аудита.

        Сценарий: задача заведена без ТЗ, годный SPEC коммитит Оператор в
        ссылку документов, `advance` из `spec_writing`. Задача в
        `spec_gate`, записи `state -> spec_audit` нет.

        Ловит мутацию: признак ТЗ не проверяется — аудит навязан и задаче
        Оператора, она уходит в `spec_audit`.
        """
        task = self.new_task(tz=None)
        self.commit_docs(task, {"SPEC.md": self.spec(task)}, "SPEC Оператора")
        out = self.advance(task)
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), "spec_gate", context)
        self.assertNotIn(AUDIT, self.state_entries(task), context)


# ---------------------------------------------------------------- AC-4

class EntryChecksKeptTest(SpecAuditSandbox):

    def test_ac4_questions_escalate_from_spec_writing_and_bad_spec_refused(self):
        """Батч вопросов задачи с ТЗ эскалирует из spec_writing; SPEC без AC-разметки остаётся в spec_writing.

        Сценарий (две задачи с ТЗ): (а) шаг аналитика пишет
        `QUESTIONS.md` рядом с годным SPEC — `advance` переводит задачу в
        `escalated` с `escalated_from = spec_writing`, в `spec_audit` она не
        входит; (б) шаг аналитика пишет SPEC `status: ready` без AC-разметки
        критериев — `advance` отказывает, задача в `spec_writing`, вывод
        называет AC-разметку.

        Ловит мутацию: новая ветка маршрута поставлена раньше проверки
        батча вопросов (вопросы не эскалируют — задача уходит в аудит) или
        минует guard SPEC (SPEC без разметки уходит в `spec_audit`).
        """
        task = self.new_task()
        out = self.submit_spec(task, self.spec(task), extra_docs={
            "QUESTIONS.md": QUESTIONS_TEXT.format(task=task, marker=word(self.rng))})
        context = self.msg(f"вопросы:\n{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), "escalated", context)
        self.assertEqual(self.row(task)["escalated_from"], "spec_writing", context)
        self.assertNotIn(AUDIT, self.state_entries(task), context)

        task = self.new_task()
        out = self.submit_spec(task, self.spec(task, ac_markup=False))
        context = self.msg(f"без разметки:\n{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), "spec_writing", context)
        self.assertIn("AC-", out + self.journal(task), context)


# ---------------------------------------------------------------- AC-5

class SpecBudgetTest(SpecAuditSandbox):

    def test_ac5_spec_budget_applies_on_entry_to_audit_and_on_approve(self):
        """Потолок задачи — budget_usd SPEC уже на входе в аудит и снова на approve гейта.

        Сценарий: SPEC с `budget_usd`, отличным от `config.DEFAULT_BUDGET_USD`
        (случайное значение ниже порога сигнала); сразу после `advance` в
        `spec_audit`, до шага аудитора, `budget_usd` строки задачи равен
        значению SPEC. Затем аудит `pass` ведёт на `spec_gate`, потолок
        задачи сдвигается на иное значение (правка вне SPEC), `approve`
        гейта возвращает потолку значение SPEC.

        Ловит мутацию: `budget.apply_spec_budget` остался только на
        approve гейта (вход в аудит идёт под потолком по умолчанию) либо
        снят с approve после переноса на вход в аудит.
        """
        values = [v for v in range(20, 45) if v != int(config.DEFAULT_BUDGET_USD)]
        budget = self.rng.choice(values)
        task = self.new_task()
        out = self.enter_audit(task, self.spec(task, budget=budget))
        self.assertEqual(self.row(task)["budget_usd"], budget,
                         self.msg(f"потолок на входе в аудит:\n{out}"))

        out = self.audit(task, "pass")
        self.assertEqual(self.state(task), "spec_gate", self.msg(out))
        store.update_task(store.db(), task, budget_usd=budget + 7)
        out = self.cli("approve", task)
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertNotEqual(self.state(task), "spec_gate", context)
        self.assertEqual(self.row(task)["budget_usd"], budget, context)


# ---------------------------------------------------------------- AC-7

class AuditorBriefTest(SpecAuditSandbox):

    def test_ac7_brief_carries_inputs_and_entry_sha_not_questions_or_logs(self):
        """Промпт шага аудитора несёт ТЗ, SPEC, каждый ANSWER, карту и sha SPEC входа — без QUESTIONS и логов агента.

        Сценарий: задача с ТЗ (метка в тексте), два ответа Оператора
        `ANSWER-1.md`/`ANSWER-2.md` с метками, шаг аналитика печатает в
        лог метку и пишет SPEC с меткой; после входа в `spec_audit` в
        ссылку документов добавлен `QUESTIONS.md` с меткой. Промпт шага
        `spec_auditor` непуст и содержит метки ТЗ, SPEC, обоих ответов,
        карты кодовой базы и sha содержимого SPEC в ссылке на входе; меток
        `QUESTIONS.md` и лога шага аналитика в нём нет.

        Ловит мутацию: миссия `spec_auditor` пуста (роль идёт веткой
        ревьювера/аналитика) — нет ТЗ или SPEC; в бриф берётся только
        последний ANSWER — нет метки первого; бриф собирает все файлы
        каталога задачи — в нём метка QUESTIONS; sha взят от головы ссылки,
        а не от содержимого SPEC — sha содержимого в промпте нет.
        """
        marks = {k: f"{k}{word(self.rng)}" for k in
                 ("tz", "spec", "otvet1", "otvet2", "vopros", "log")}
        task = self.new_task(tz=f"ТЗ с меткой {marks['tz']}.\n")
        self.add_answer(task, 1, f"Ответ один {marks['otvet1']}.")
        self.add_answer(task, 2, f"Ответ два {marks['otvet2']}.")
        self.enter_audit(task, self.spec(task, marker=marks["spec"]),
                         lines=(f"лог аналитика {marks['log']}\n",))
        entry_sha = self.ref_file_sha(task)
        self.commit_docs(task, {"QUESTIONS.md": QUESTIONS_TEXT.format(
            task=task, marker=marks["vopros"])}, "вопросы в ссылке")

        self.audit_step(task, "pass")
        prompt = self.prompts[-1]
        context = self.msg(f"промпт аудитора:\n{prompt[:6000]}")
        self.assertTrue(prompt.strip(), context)
        for key in ("tz", "spec", "otvet1", "otvet2"):
            self.assertIn(marks[key], prompt, context)
        self.assertIn(self.map_marker, prompt, context)
        self.assertIn(entry_sha, prompt, context)
        self.assertNotIn(marks["vopros"], prompt, context)
        self.assertNotIn(marks["log"], prompt, context)


# ---------------------------------------------------------------- AC-8, AC-9

class SignalDepthTest(SpecAuditSandbox):
    """Глубина разбора и журнал сигналов на входе в аудит."""

    NAMES = {
        "а": ("Меняемое поведение",),
        "б": ("мандат", "Ослабление тестов разрешено", "Расширение зон разрешено"),
        "приложение": ("приложени",),
        "г": ("budget", "бюджет"),
        "д": ("ADR",),
        "защищённый": ("защищ",),
    }

    def assert_depth(self, task: str, full: bool, names: tuple, case: str) -> str:
        """Шаг аудитора стартует; глубина промпта и имя сигнала в журнале входа."""
        entry = self.visit_text(task)
        self.audit_step(task, "pass")
        prompt = self.prompts[-1]
        context = self.msg(f"{case}: журнал входа:\n{entry}\nпромпт:\n{prompt[:4000]}")
        self.assertEqual(bool(FULL_RE.search(prompt)), full, context)
        self.assertEqual(bool(SHORT_RE.search(prompt)), not full, context)
        if names:
            self.assertTrue(any(n.lower() in entry.lower() for n in names), context)
        return entry

    def test_ac8_behavior_section_full_review_and_no_signal_short_review(self):
        """SPEC с непустым «Меняемое поведение» — полный разбор и сигнал в журнале; SPEC без сигналов — краткий разбор и «нет».

        Сценарий: задача (а) — SPEC с разделом «Меняемое поведение», иначе
        без сигналов; задача (б) — SPEC без единого сигнала требования 7
        (нейтральная зона, бюджет ниже порога, ТЗ без ADR, ответов нет).
        Промпт аудитора (а) требует полного разбора, журнал входа называет
        «Меняемое поведение»; промпт (б) требует краткого разбора, журнал
        входа пишет «нет».

        Ловит мутацию: глубина не зависит от сигналов (всегда полный или
        всегда краткий разбор); раздел «Меняемое поведение» не считается
        сигналом (задача (а) получает краткий разбор); перечень сигналов
        не пишется в журнал на входе.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task, behavior=True))
        self.assert_depth(task, True, self.NAMES["а"], "Меняемое поведение")

        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        entry = self.assert_depth(task, False, (), "без сигналов")
        self.assertIn("нет", entry, self.msg(f"журнал входа:\n{entry}"))

    def test_ac9_each_signal_alone_switches_to_full_review(self):
        """Каждый признак сигнала по отдельности переключает бриф на полный разбор и называется в журнале; бюджет 44 — нет.

        Сценарий: на SPEC, иначе не дающем ни одного сигнала, по одному
        признаку на задачу — мандат в ANSWER (б); путь-признак каждой из
        четырёх категорий константы `config` в зонах SPEC (в); защищённый
        путь в зонах (в); упоминание приложения PLAN в требованиях (в);
        `budget_usd: 45` (г); `ADR-0022` в ТЗ (д). Каждый вход даёт полный
        разбор и называет сигнал в журнале; `budget_usd: 44` — краткий
        разбор.

        Ловит мутацию: признак одной из категорий не проверяется (пустая
        категория, путь гейтов без `orchestrator/advance_gates/`); порог
        бюджета сравнивается строго (`> 45`) — 45 даёт краткий разбор; или
        нестрого не на том пороге — 44 даёт полный; ADR ищется в SPEC, а
        не в ТЗ; мандат ищется только в последнем ANSWER или не ищется
        вовсе; защищённый путь сверяется не `config.is_protected_path`.
        """
        constants = path_signal_categories()
        self.assertEqual(len(constants), 1, self.msg(
            f"константа путей-признаков сигнала 7в в config не найдена или не "
            f"одна: {sorted(constants)}"))
        categories = next(iter(constants.values()))
        cases = []
        for category, paths in categories.items():
            path = self.rng.choice(sorted(paths))
            cases.append((f"путь {category}", {"zones": f"{NEUTRAL_ZONE}, {path}"},
                          None, None, (path, str(category))))
        protected = self.rng.choice([p for p in config.PROTECTED_PATHS
                                     if "*" not in p])
        self.assertTrue(config.is_protected_path(protected), protected)
        cases.append(("защищённый путь",
                      {"zones": f"{NEUTRAL_ZONE}, {protected}"}, None, None,
                      self.NAMES["защищённый"] + (protected,)))
        cases.append(("приложение PLAN",
                      {"extra": "\n2. Правка шаблона едет приложением PLAN."},
                      None, None, self.NAMES["приложение"]))
        cases.append(("бюджет 45", {"budget": 45}, None, None, self.NAMES["г"]))
        cases.append(("ADR в ТЗ", {}, f"ТЗ по ADR-0022: {word(self.rng)}.\n",
                      None, self.NAMES["д"]))
        mandate = self.rng.choice([f"Расширение зон разрешено: {NEUTRAL_ZONE}",
                                   f"Ослабление тестов разрешено: "
                                   f"tests/test_fx_{word(self.rng)}.py"])
        cases.append(("мандат в ANSWER", {}, None, mandate, self.NAMES["б"]))
        self.rng.shuffle(cases)
        for case, spec_kwargs, tz, answer_body, names in cases:
            with self.subTest(признак=case):
                task = self.new_task(tz=tz or "")
                if answer_body:
                    self.add_answer(task, 1, answer_body)
                self.enter_audit(task, self.spec(task, **spec_kwargs))
                self.assert_depth(task, True, names, case)

        with self.subTest(признак="бюджет 44"):
            task = self.new_task()
            self.enter_audit(task, self.spec(task, budget=44))
            self.assert_depth(task, False, (), "бюджет 44")


# ---------------------------------------------------------------- AC-11

class AuditArtifactCommitTest(SpecAuditSandbox):

    def test_ac11_auditor_step_commits_spec_audit_but_not_other_names(self):
        """Автокоммит шага аудитора переносит SPEC-AUDIT.md в ссылку документов; SPEC-AUDIT2.md остаётся посторонним.

        Сценарий: задача в `spec_audit`, шаг аудитора пишет в каталог
        документов `SPEC-AUDIT.md` и `SPEC-AUDIT2.md`. После шага
        `SPEC-AUDIT.md` есть в ссылке документов с текстом шага, журнал не
        называет его посторонним; `SPEC-AUDIT2.md` в ссылку не попал.

        Ловит мутацию: белый список `.md` каталога задачи не дополнен —
        автокоммит отбрасывает `SPEC-AUDIT.md` как посторонний (файла в
        ссылке нет, журнал называет его); белый список расширен маской
        (`SPEC-AUDIT.*\\.md`) — в ссылку уезжает и `SPEC-AUDIT2.md`.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        start = self.max_step_id(task)
        stray = f"# посторонний {word(self.rng)}\n"
        out = self.audit_step(task, "pass", extra_docs={"SPEC-AUDIT2.md": stray})
        text = self.ref_text(task, AUDIT_FILE)
        journal = self.text_since(task, start)
        context = self.msg(f"{out}\n{journal}")
        self.assertIsNotNone(text, context)
        self.assertIn("type: spec_audit", text, context)
        for line in journal.splitlines():
            if AUDIT_FILE in line and "SPEC-AUDIT2" not in line:
                self.assertNotIn("посторон", line, context)
        self.assertIsNone(self.ref_text(task, "SPEC-AUDIT2.md"), context)


# ---------------------------------------------------------------- AC-12

class RequiredArtifactTest(SpecAuditSandbox):

    def run_once(self, task: str, role: str, files: dict) -> tuple:
        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            for rel, text in files.items():
                path = self.docs_dir(task) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return FakeProc([RESULT])

        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(io.StringIO()):
            return runner.run_agent_once(store.db(), task, role, "промпт шага", 1)

    def test_ac12_auditor_step_without_spec_audit_is_not_success(self):
        """Шаг spec_auditor с кодом 0 без SPEC-AUDIT.md — тот же отказ, что у reviewer без REVIEW.md; с файлом — успех.

        Сценарий: задача в `spec_audit`, агент аудитора завершается rc=0,
        ничего не написав, — `run_agent_once` возвращает тот же исход и
        класс отказа, что шаг `reviewer` задачи в `review` без
        `REVIEW.md` (исход `failed`, «шаг завершён без артефакта»), и
        пояснение называет `SPEC-AUDIT.md`. Повтор с `SPEC-AUDIT.md` в
        каталоге документов — исход `ok`.

        Ловит мутацию: ветка `spec_auditor` в проверке обязательного
        артефакта не заведена (функция возвращает `None` для неизвестной
        роли) — шаг без файла засчитан как `ok`; файл ищется в рабочей копии
        кода, а не в каталоге документов — шаг с файлом отказан.
        """
        reviewed = self.new_task(tz=None)
        self.set_state(reviewed, "review")
        reviewer = self.run_once(reviewed, "reviewer", {})

        task = self.new_task()
        self.set_state(task, AUDIT)
        refused = self.run_once(task, AUDITOR, {})
        context = self.msg(f"reviewer: {reviewer}; spec_auditor: {refused}")
        self.assertEqual(reviewer[0], "failed", context)
        self.assertIn(MISSING, reviewer[1], context)
        self.assertEqual(refused[0], reviewer[0], context)
        self.assertEqual(refused[2], reviewer[2], context)
        self.assertIn(MISSING, refused[1], context)
        self.assertIn(AUDIT_FILE, refused[1], context)

        accepted = self.run_once(task, AUDITOR, {AUDIT_FILE: self.audit_text(
            task, "pass", self.ref_file_sha(task))})
        self.assertEqual(accepted[0], "ok", self.msg(f"с файлом: {accepted}"))


# ---------------------------------------------------------------- AC-13

class AuditExitTest(SpecAuditSandbox):

    def test_ac13_pass_and_concerns_lead_to_gate_draft_stays(self):
        """Свежий SPEC-AUDIT.md pass или concerns ведёт в spec_gate с записью вердикта; draft оставляет в spec_audit.

        Сценарий: на каждый вердикт `pass`/`concerns` (порядок случаен) —
        своя задача: шаг аудитора с `status: draft` — `advance` оставляет
        задачу в `spec_audit`; повторный шаг с `status: ready` — `advance`
        ведёт в `spec_gate`, и среди записей журнала после входа есть
        запись с этим вердиктом.

        Ловит мутацию: выход не сверяет статус файла (draft продвигает
        задачу); `concerns` трактуется как `fail` (возврат в
        `spec_writing`); выход не журналирует вердикт.
        """
        verdicts = ["pass", "concerns"]
        self.rng.shuffle(verdicts)
        for verdict in verdicts:
            with self.subTest(вердикт=verdict):
                task = self.new_task()
                self.enter_audit(task, self.spec(task))
                start = self.last_entry_id(task, AUDIT)
                out = self.audit(task, verdict, status="draft")
                self.assertEqual(self.state(task), AUDIT,
                                 self.msg(f"draft:\n{out}\n{self.journal(task)}"))
                out = self.audit(task, verdict)
                context = self.msg(f"{verdict}:\n{out}\n{self.journal(task)}")
                self.assertEqual(self.state(task), "spec_gate", context)
                self.assertRegex(self.text_since(task, start),
                                 rf"\b{verdict}\b", context)


# ---------------------------------------------------------------- AC-14

class FailReturnTest(SpecAuditSandbox):

    def test_ac14_two_fails_return_third_goes_to_gate_with_return_reason(self):
        """Два fail возвращают задачу аналитику с отклонениями в «Причине возврата», третий fail ведёт в spec_gate.

        Сценарий: первый шаг аналитика — промпт без раздела «Причина
        возврата». Аудит `fail` (отклонение со случайной меткой) —
        задача в `spec_writing`, промпт следующего шага аналитика несёт
        «Причину возврата» с этой меткой; так дважды. Третий `fail` —
        задача в `spec_gate`.

        Ловит мутацию: счётчик возвратов не ограничен (третий fail снова
        возвращает) или ограничен одним возвратом; возврат
        `spec_audit -> spec_writing` не триггер раздела «Причина
        возврата»; раздел несёт текст перехода без отклонений
        `SPEC-AUDIT.md`; раздел ошибочно получает и первый вход.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        self.assertNotIn(RETURN_HEADER, self.prompts[-1],
                         self.msg("первый вход аналитика несёт «Причину возврата»"))
        for n in (1, 2):
            deviation = self.deviation()
            out = self.audit(task, "fail", deviation=deviation)
            self.assertEqual(self.state(task), "spec_writing", self.msg(
                f"fail №{n}:\n{out}\n{self.journal(task)}"))
            self.enter_audit(task, self.spec(task))
            prompt = self.prompts[-1]
            context = self.msg(f"промпт аналитика после возврата №{n}:\n{prompt[:5000]}")
            self.assertIn(RETURN_HEADER, prompt, context)
            self.assertIn(deviation.split(":")[0], prompt, context)
        out = self.audit(task, "fail", deviation=self.deviation())
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"третий fail:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-15

class FreshnessTest(SpecAuditSandbox):

    def test_ac15_previous_visit_pass_does_not_advance(self):
        """SPEC-AUDIT.md pass прошлого визита после возврата по fail и повторной сдачи SPEC задачу не продвигает.

        Сценарий: визит 1 — `fail`, возврат; аналитик сдаёт тот же SPEC;
        визит 2 — `pass`, задача на `spec_gate`; `reject` — аналитик снова
        сдаёт тот же SPEC (sha содержимого совпадает с `spec_sha` файла);
        визит 3 — шага аудитора нет, `advance` оставляет задачу в
        `spec_audit`.

        Ловит мутацию: свежесть не проверяется (засчитывается любой
        `SPEC-AUDIT.md` в ссылке) — задача уходит в `spec_gate`; свежесть
        сверяется только по автору коммита, без «после последнего входа».
        """
        task = self.new_task()
        spec_text = self.spec(task)
        self.enter_audit(task, spec_text)
        self.audit(task, "fail", deviation=self.deviation())
        self.assertEqual(self.state(task), "spec_writing", self.msg(self.journal(task)))
        self.enter_audit(task, spec_text)
        self.audit(task, "pass")
        self.assertEqual(self.state(task), "spec_gate", self.msg(self.journal(task)))
        self.run_cmd(fsm.cmd_reject, task, f"переписать {word(self.rng)}")
        self.assertEqual(self.state(task), "spec_writing", self.msg(self.journal(task)))
        self.enter_audit(task, spec_text)
        out = self.advance(task)
        self.assertEqual(self.state(task), AUDIT, self.msg(
            f"файл прошлого визита продвинул задачу:\n{out}\n{self.journal(task)}"))

    def test_ac15_spec_audit_written_by_analyst_does_not_advance(self):
        """SPEC-AUDIT.md pass, записанный аналитиком в шаге spec_writing, задачу из spec_audit не продвигает.

        Сценарий: шаг аналитика пишет SPEC и рядом `SPEC-AUDIT.md`
        (`verdict: pass`, `status: ready`, `spec_sha` — sha содержимого
        этого SPEC); `advance` — задача в `spec_audit`; второй `advance`
        без шага аудитора оставляет её в `spec_audit`.

        Ловит мутацию: последний коммит файла не сверяется с автокоммитом
        роли `spec_auditor` (аналитик может сам выписать себе вердикт) —
        задача уходит в `spec_gate`.
        """
        task = self.new_task()
        spec_text = self.spec(task)
        forged = self.audit_text(task, "pass", blob_sha(spec_text))
        self.enter_audit(task, spec_text, extra_docs={AUDIT_FILE: forged})
        out = self.advance(task)
        self.assertEqual(self.state(task), AUDIT, self.msg(
            f"вердикт аналитика продвинул задачу:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-16

class ShaBindingTest(SpecAuditSandbox):

    def test_ac16_entry_journal_carries_spec_content_sha_not_ref_head(self):
        """Журнал входа в spec_audit несёт sha содержимого SPEC в ссылке, а не sha головы ссылки.

        Сценарий: после входа в `spec_audit` sha содержимого SPEC
        (`git rev-parse <ссылка>:<путь SPEC>`) есть в записях входа, и ни
        одна запись, несущая его, не несёт как sha версии SPEC sha головы
        ссылки (запись фиксации перехода, называющая голову ссылки, — не
        предмет). Затем шаг аудитора (`pass`, совпадающий `spec_sha`)
        сдвигает голову ссылки своим автокоммитом, содержимое SPEC
        прежнее — `advance` ведёт в `spec_gate`.

        Ловит мутацию: на входе пишется `rev-parse <ссылка>` (sha коммита
        головы) — в журнале sha головы, содержимого нет; привязка
        сравнивает голову ссылки — собственный автокоммит аудитора даёт
        отказ.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        content = self.ref_file_sha(task)
        head = self.ref_head(task)
        entry = self.visit_text(task)
        context = self.msg(f"содержимое {content}, голова {head}:\n{entry}")
        carrying = [line for line in entry.splitlines() if content in line]
        self.assertTrue(carrying, context)
        for line in carrying:
            self.assertNotIn(head, SHA_RE.findall(line), context)

        out = self.audit(task, "pass")
        self.assertNotEqual(self.ref_head(task), head, self.msg("голова не сдвинулась"))
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"собственный автокоммит аудитора дал отказ:\n{out}\n{self.journal(task)}"))

    def test_ac16_spec_changed_in_audit_step_refuses_with_both_sha(self):
        """Правка SPEC шагом аудитора — advance отказывает, состояние прежнее, отказ называет оба sha.

        Сценарий: после входа шаг аудитора пишет `SPEC-AUDIT.md` (`pass`,
        `spec_sha` — sha входа) и правит SPEC (новая метка). `advance`
        оставляет задачу в `spec_audit`; вывод и журнал называют sha входа
        и новый sha содержимого SPEC.

        Ловит мутацию: на выходе сверяется только `spec_sha` файла с sha
        входа, а не текущее содержимое SPEC — задача уходит в `spec_gate`;
        отказ называет один sha.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        entry_sha = self.ref_file_sha(task)
        changed = self.spec(task)
        out = self.audit(task, "pass", spec_sha=entry_sha,
                         extra_docs={"SPEC.md": changed})
        new_sha = self.ref_file_sha(task)
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertNotEqual(new_sha, entry_sha, context)
        self.assertEqual(self.state(task), AUDIT, context)
        text = out + "\n" + self.journal(task)
        self.assertIn(entry_sha, text, context)
        self.assertIn(new_sha, text, context)

    def test_ac16_spec_sha_mismatch_refuses_and_match_passes(self):
        """spec_sha в SPEC-AUDIT.md не равен sha входа — отказ с обоими sha; совпадающий — проход.

        Сценарий: шаг аудитора пишет `pass` со случайным 40-значным
        `spec_sha` — `advance` оставляет задачу в `spec_audit`, вывод и
        журнал называют оба sha; следующий шаг с `spec_sha` входа —
        `advance` ведёт в `spec_gate`.

        Ловит мутацию: поле `spec_sha` не сверяется вовсе — задача уходит в
        `spec_gate` с вердиктом о другой версии SPEC; сверка по префиксу
        или без учёта поля — совпадающий sha тоже отказан.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        entry_sha = self.ref_file_sha(task)
        wrong = "".join(self.rng.choice("0123456789abcdef") for _ in range(40))
        out = self.audit(task, "pass", spec_sha=wrong)
        text = out + "\n" + self.journal(task)
        context = self.msg(text)
        self.assertEqual(self.state(task), AUDIT, context)
        self.assertIn(wrong, text, context)
        self.assertIn(entry_sha, text, context)
        out = self.audit(task, "pass", spec_sha=entry_sha)
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"совпадающий sha:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-17

class ReturnCounterTest(SpecAuditSandbox):

    def test_ac17_reject_does_not_reset_return_counter(self):
        """После двух возвратов reject на spec_gate и новый fail ведут задачу в spec_gate.

        Сценарий: два `fail` — два возврата; третий визит `pass` — задача
        на `spec_gate`; `reject` возвращает аналитику, он сдаёт SPEC;
        аудит `fail` — задача в `spec_gate`, не в `spec_writing`.

        Ловит мутацию: счётчик считается с последнего входа в
        `spec_writing` или сбрасывается `reject` — fail снова возвращает
        аналитику.
        """
        task = self.new_task()
        self.to_gate_after_fail_returns(task, 2)
        self.run_cmd(fsm.cmd_reject, task, f"переписать {word(self.rng)}")
        self.assertEqual(self.state(task), "spec_writing", self.msg(self.journal(task)))
        self.enter_audit(task, self.spec(task))
        out = self.audit(task, "fail", deviation=self.deviation())
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"fail после reject:\n{out}\n{self.journal(task)}"))

    def test_ac17_spec_audit_command_does_not_reset_return_counter(self):
        """После двух возвратов spec-audit с гейта и новый fail ведут задачу в spec_gate.

        Сценарий: два `fail` — два возврата; третий визит `pass` — задача
        на `spec_gate`; `artel.py spec-audit <id>` — задача в
        `spec_audit`; аудит `fail` — задача в `spec_gate`.

        Ловит мутацию: команда повторного аудита обнуляет счётчик (или
        счётчик ведётся от записи команды) — fail возвращает аналитику.
        """
        task = self.new_task()
        self.to_gate_after_fail_returns(task, 2)
        out = self.cli("spec-audit", task)
        self.assertEqual(self.state(task), AUDIT, self.msg(f"{out}\n{self.journal(task)}"))
        out = self.audit(task, "fail", deviation=self.deviation())
        self.assertEqual(self.state(task), "spec_gate", self.msg(
            f"fail после spec-audit:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-18

class AuditEscalationTest(SpecAuditSandbox):

    def test_ac18_escalate_status_escalates_and_returns_to_audit(self):
        """SPEC-AUDIT.md со status escalate и разделом «Эскалация» — escalated с возвратом в spec_audit после ответа.

        Сценарий: шаг аудитора пишет `status: escalate` с разделом
        «Эскалация» (Вопросы, Контекст, Блокирует); `advance` — задача в
        `escalated`, `escalated_from = spec_audit`. Оператор отвечает
        `answer` (и, если задача ещё ждёт, `approve`) — задача снова в
        `spec_audit`.

        Ловит мутацию: `status: escalate` трактуется как «не готово» —
        задача остаётся в `spec_audit`; `escalated_from` не пишется —
        возврат уходит в `in_dev`.
        """
        task = self.new_task()
        self.enter_audit(task, self.spec(task))
        out = self.audit(task, "concerns", status="escalate",
                         escalation=f"Как понимать {word(self.rng)}?")
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), "escalated", context)
        self.assertEqual(self.row(task)["escalated_from"], AUDIT, context)

        reply = self.scratch / f"otvet-{word(self.rng)}.txt"
        reply.write_text(f"Понимать как {word(self.rng)}.\n", encoding="utf-8")
        out = self.run_cmd(answer.cmd_answer, task, str(reply))
        if self.state(task) == "escalated":
            out += self.cli("approve", task)
        self.assertEqual(self.state(task), AUDIT, self.msg(
            f"возврат после ответа:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-19

class GateVerdictTest(SpecAuditSandbox):

    def test_ac19_show_status_auto_name_journal_verdict(self):
        """show, status и остановка auto на spec_gate называют вердикт из журнала; подмена файла их не меняет.

        Сценарий: ТЗ ссылается на ADR (сигнал д); визит 1 — `fail`
        (возврат), визит 2 — `pass`, задача на `spec_gate`. Затем Оператор
        подменяет `SPEC-AUDIT.md` в ссылке документов и на диске
        `verdict: concerns`. `show` выводит `pass`, строку с числом
        возвратов 1 и сигнал ADR; строка задачи в `status` и вывод
        `auto` несут `pass`; слова `concerns` нет ни в одном выводе.

        Ловит мутацию: вердикт берётся из файла `SPEC-AUDIT.md` (выводы
        несут `concerns`); `show` не печатает число возвратов или сигналы;
        `status`/`auto` не называют вердикт.
        """
        task = self.new_task(tz=f"ТЗ по ADR-0022, метка {word(self.rng)}.\n")
        self.to_gate_after_fail_returns(task, 1, final="pass")
        forged = self.audit_text(task, "concerns", self.ref_file_sha(task))
        self.commit_docs(task, {AUDIT_FILE: forged}, "подмена вердикта")
        self.docs_dir(task).mkdir(parents=True, exist_ok=True)
        (self.docs_dir(task) / AUDIT_FILE).write_text(forged, encoding="utf-8")

        show = self.run_cmd(catalog.cmd_show, task)
        status_lines = [line for line in self.run_cmd(catalog.cmd_status).splitlines()
                        if line.startswith(task)]
        stop = self.run_cmd(auto.cmd_auto, task)
        context = self.msg(f"show:\n{show}\nstatus:\n{status_lines}\nauto:\n{stop}")
        self.assertEqual(self.state(task), "spec_gate", context)
        self.assertRegex(show, r"\bpass\b", context)
        self.assertRegex(show, r"(?im)^.*возврат.*\b1\b.*$", context)
        self.assertIn("ADR", show, context)
        self.assertEqual(len(status_lines), 1, context)
        self.assertRegex(status_lines[0], r"\bpass\b", context)
        self.assertRegex(stop, r"\bpass\b", context)
        for text in (show, status_lines[0], stop):
            self.assertNotIn("concerns", text, context)


# ---------------------------------------------------------------- AC-20

class AcceptAuditFailTest(SpecAuditSandbox):

    def fail_gate(self) -> str:
        task = self.new_task()
        self.to_gate_after_fail_returns(task, 2, final="fail")
        return task

    def live_sha(self, task: str) -> str:
        current, _clean = fixation.read(task, ARTEL)
        self.assertTrue(current, self.msg("фиксации нет"))
        return current

    def test_ac20_fail_verdict_needs_flag_in_both_forms(self):
        """approve при последнем fail без флага — отказ с именем флага; с флагом в обеих формах — проход и запись о принятии fail.

        Сценарий: задача на `spec_gate` после третьего `fail`. `approve
        <id>` — отказ, текст называет `--accept-audit-fail`, состояние
        `spec_gate`. Затем (форма выбирается случайно для первой задачи,
        вторая задача — другой формой) `approve <id> --accept-audit-fail`
        либо `approve <id> <sha> --accept-audit-fail` — задача уходит с
        гейта, в журнале после approve есть запись о принятии `fail`. Во
        второй форме sha разобран как sha: заведомо чужой sha той же длины
        даёт отказ «не совпадает», живой — проход.

        Ловит мутацию: approve не смотрит вердикт журнала (fail проходит
        без флага); флаг не разбирается диспетчером; позиционный sha берёт
        флаг за sha (вторая форма отказывает «sha --accept-audit-fail не
        совпадает»); sha второй формы игнорируется (чужой sha проходит);
        принятие fail не журналируется.
        """
        forms = ["short", "sha"]
        self.rng.shuffle(forms)
        for form in forms:
            with self.subTest(форма=form):
                task = self.fail_gate()
                out = self.cli("approve", task)
                context = self.msg(f"без флага:\n{out}\n{self.journal(task)}")
                self.assertEqual(self.state(task), "spec_gate", context)
                self.assertIn(FLAG, out, context)
                start = self.max_step_id(task)
                if form == "sha":
                    sha = self.live_sha(task)
                    wrong = "".join("0" if c != "0" else "1" for c in sha)
                    out = self.cli("approve", task, wrong, FLAG)
                    context = self.msg(f"чужой sha:\n{out}\n{self.journal(task)}")
                    self.assertEqual(self.state(task), "spec_gate", context)
                    self.assertIn("не совпадает", out, context)
                    out = self.cli("approve", task, sha, FLAG)
                else:
                    out = self.cli("approve", task, FLAG)
                after = self.text_since(task, start)
                context = self.msg(f"с флагом ({form}):\n{out}\n{after}")
                self.assertNotEqual(self.state(task), "spec_gate", context)
                self.assertTrue(any(re.search(r"\bfail\b", line) and "operator" in line
                                    for line in after.splitlines()), context)

    def test_ac20_flag_outside_spec_gate_refused_and_no_verdict_passes(self):
        """Флаг вне spec_gate — отказ без смены состояния; задача без вердикта в журнале проходит approve на spec_gate без флага.

        Сценарий: (а) задача в `escalated` (возврат в `spec_audit`) —
        `approve <id> --accept-audit-fail` отказывает, текст называет флаг,
        задача остаётся в `escalated`; (б) задача без ТЗ на `spec_gate`
        (вердикта в журнале нет) — `approve <id>` уводит её с гейта.

        Ловит мутацию: флаг вне `spec_gate` молча игнорируется (задача
        возвращается из эскалации) или разбирается как позиционный sha
        (отказ «sha --accept-audit-fail не совпадает» вместо отказа по
        флагу); проверка вердикта отказывает и задаче без записи вердикта
        (трактует отсутствие как fail).
        """
        task = self.new_task()
        store.update_task(store.db(), task, state="escalated", escalated_from=AUDIT)
        store.record_fixation(store.db(), task)
        out = self.cli("approve", task, FLAG)
        context = self.msg(f"escalated:\n{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), "escalated", context)
        self.assertIn(FLAG, out, context)
        self.assertNotIn("не совпадает", out, context)

        task = self.new_task(tz=None)
        self.commit_docs(task, {"SPEC.md": self.spec(task)}, "SPEC Оператора")
        self.advance(task)
        self.assertEqual(self.state(task), "spec_gate", self.msg(self.journal(task)))
        out = self.cli("approve", task)
        self.assertNotEqual(self.state(task), "spec_gate", self.msg(
            f"без вердикта:\n{out}\n{self.journal(task)}"))


# ---------------------------------------------------------------- AC-21

class SpecAuditCommandTest(SpecAuditSandbox):

    def test_ac21_spec_audit_command_from_gate_and_refusal_elsewhere(self):
        """spec-audit на spec_gate переводит задачу в spec_audit с записью журнала, в том числе без ТЗ; вне spec_gate — отказ.

        Сценарий: (а) задача без ТЗ на `spec_gate` — `artel.py spec-audit
        <id>` переводит её в `spec_audit`, журнал несёт запись
        `state -> spec_audit`; (б) задача с ТЗ в состоянии вне `spec_gate`
        (случайно из `spec_writing`, `tests_writing`, `in_dev`) — команда
        отказывает, состояние прежнее.

        Ловит мутацию: команда не проверяет состояние (переводит в аудит
        из любого); команда доступна только задаче с ТЗ.
        """
        task = self.new_task(tz=None)
        self.commit_docs(task, {"SPEC.md": self.spec(task)}, "SPEC Оператора")
        self.advance(task)
        self.assertEqual(self.state(task), "spec_gate", self.msg(self.journal(task)))
        start = self.max_step_id(task)
        out = self.cli("spec-audit", task)
        context = self.msg(f"{out}\n{self.journal(task)}")
        self.assertEqual(self.state(task), AUDIT, context)
        self.assertTrue(any(r["action"] == f"state -> {AUDIT}" and r["id"] > start
                            for r in self.steps(task)), context)

        other = self.new_task()
        state = self.rng.choice(["spec_writing", "tests_writing", "in_dev"])
        self.set_state(other, state)
        out = self.cli("spec-audit", other)
        self.assertEqual(self.state(other), state, self.msg(
            f"{state}:\n{out}\n{self.journal(other)}"))


if __name__ == "__main__":
    unittest.main()
