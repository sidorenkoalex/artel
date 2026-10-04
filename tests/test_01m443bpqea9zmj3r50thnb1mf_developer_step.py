"""Шаг разработчика: указание Оператора в брифе (AC-6) и подтяжка `main` в
ветку задачи перед запуском агента (AC-9).

Группа: долгоживущий

Красен до реализации: `answer` в `in_dev` отказывает файлу без строк мандатов, а бриф разработчика несёт только последний `ANSWER-n.md` (AC-6); `run` в `in_dev` после захвата замка зоны сразу собирает промпт и запускает агента без подтяжки — у отставшей ветки агент стартует без коммита `origin/main`, конфликтующая ветка не эскалирует и агент запускается (AC-9).

Случай AC-9 «ветка не отстаёт» зелен и до реализации: он держит
нынешнее поведение против подтяжки, которая делает слияние безусловно.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): главная копия
пульта с кодом пульта, скилами и шаблонами в первом коммите, bare `origin`
рядом и `targets.yaml`, где запись артели называет его полем `url`; клон
проекта и рабочую копию задачи заводят `init`/`new`. Шаг разработчика —
штатный `runner.cmd_run` с подменённым запуском агента
(`runner.spawn_agent`): подмена пишет код в рабочий каталог и документы в
каталог документов задачи и запоминает, что видела на момент запуска
(голову рабочей копии, файлы). Чужие коммиты `origin/main` делаются из
вспомогательного клона. Имена файлов, тексты и порядок случаев берутся
случайно; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (answer, brief, catalog, config, keychain, pull,
                          runner, stack, store)
from tests.sandbox import (FakeProc, RealGitSandbox, _stub_check_stack,
                           capture, capture_new_task_id, is_claude_call,
                           resilient_tmp_cleanup)

REPO = Path(__file__).resolve().parent.parent
ARTEL = config.DEFAULT_TARGET
STEP_STARTED = "agent run started"

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

CODE_MAP_PLACEHOLDER = ("---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
                        "---\n\n# Карта\n")

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: kod/
budget_usd: 10
---

# SPEC: шаг разработчика {marker}

## Контекст

## Требования

## Критерии приёмки

AC-1. Код задачи лежит в ветке.

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: шаг разработчика {marker}

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

PLANK_FIXTURE = ("import unittest\n\n\nclass Fixture(unittest.TestCase):\n"
                 "    def test_ac1_fixture(self):\n"
                 "        self.assertTrue(True)\n")

WORDS = ("причина", "падение", "фикстура", "импорт", "порядок", "модуль",
         "ветка", "журнал", "проверка", "сборка", "карта", "шаг")


class DeveloperStepSandbox(RealGitSandbox):
    """Главная копия пульта с кодом пульта, bare `origin` артели,
    `targets.yaml` с его адресом; `init` заводит клон проекта. Ключи,
    pre-flight и стек ролей подменены."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role_patcher.start()
        self.addCleanup(role_patcher.stop)

        for name in ("scripts", "orchestrator", "templates", "skills"):
            shutil.copytree(REPO / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            CODE_MAP_PLACEHOLDER, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "test_green.py").write_text(
            "def test_green():\n    assert True\n", encoding="utf-8")

        origin_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, origin_tmp)
        self.scratch = Path(origin_tmp.name).resolve()
        self.origin = self.scratch / "artel.git"
        self.git("init", "-q", "--bare", "-b", config.MAIN_BRANCH, str(self.origin))
        config.TARGETS.write_text(
            "targets:\n" + TARGET_ENTRY.format(name=ARTEL, url=str(self.origin),
                                               base=config.MAIN_BRANCH),
            encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "пульт")
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

        self.helper = self.scratch / "pomoshchnik"
        self.git("clone", "-q", str(self.origin), str(self.helper))
        capture(catalog.cmd_init)
        self.use_role_map()
        self.spawned = []

    # ------------------------------------------------------------ git

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def is_ancestor(self, repo: Path, older: str, newer: str) -> bool:
        try:
            self.git("-C", str(repo), "merge-base", "--is-ancestor", older, newer)
        except AssertionError:
            return False
        return True

    def origin_main(self) -> str:
        return self.in_repo(self.origin, "rev-parse",
                            f"refs/heads/{config.MAIN_BRANCH}").strip()

    def branch_head(self, task: str) -> str:
        return self.in_repo(self.clone, "rev-parse",
                            f"refs/heads/{self.branch_of(task)}").strip()

    def push_foreign(self, rel: str, text: str) -> str:
        """Чужой коммит кода в origin/main из вспомогательного клона;
        возвращает новую голову origin/main."""
        self.in_repo(self.helper, "pull", "-q", "--ff-only", "origin",
                     config.MAIN_BRANCH)
        path = self.helper / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.in_repo(self.helper, "add", rel)
        self.in_repo(self.helper, "-c", "user.name=chuzhoy",
                     "-c", "user.email=c@example.invalid",
                     "commit", "-q", "-m", f"чужая правка {rel}")
        self.in_repo(self.helper, "push", "-q", "origin",
                     f"HEAD:{config.MAIN_BRANCH}")
        return self.origin_main()

    # ---------------------------------------------------------- задача

    def new_task(self) -> str:
        _, task = capture_new_task_id(
            lambda: catalog.cmd_new(f"Шаг {self.rng.randrange(10 ** 6)}"))
        return task

    def branch_of(self, task: str) -> str:
        return store.get_task(store.db(), task)["branch"]

    def set_state(self, task: str, state: str) -> None:
        store.update_task(store.db(), task, state=state)

    def state_of(self, task: str) -> str:
        return store.get_task(store.db(), task)["state"]

    def docs_dir(self, task: str) -> Path:
        return config.PROJECTS / ARTEL / "tasks" / task

    def task_docs(self, task: str) -> dict:
        marker = f"m{self.rng.randrange(10 ** 9)}"
        return {"SPEC.md": SPEC_READY.format(task=task, marker=marker),
                "PLAN.md": PLAN_READY.format(task=task, marker=marker),
                "acceptance_tests/test_ac1_fixture.py": PLANK_FIXTURE}

    def journal_rows(self, task: str) -> list:
        return list(store.task_steps(store.db(), task))

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in self.journal_rows(task))

    def developer_step(self, task: str, code: dict, docs: dict) -> str:
        """Шаг developer штатным `runner.cmd_run`: подменённый агент пишет
        `code` в рабочий каталог, `docs` — в каталог документов задачи, и
        запоминает в `self.spawned` голову и путь рабочего каталога на
        момент своего запуска."""
        def spawn(cmd, *args, **kwargs):
            if not is_claude_call(cmd):
                return subprocess.Popen(cmd, *args, **kwargs)
            cwd = Path(kwargs.get("cwd"))
            self.spawned.append({"cwd": cwd,
                                 "head": self.in_repo(cwd, "rev-parse", "HEAD").strip()})
            for rel, text in code.items():
                (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
                (cwd / rel).write_text(text, encoding="utf-8")
            docs_dir = self.docs_dir(task)
            for rel, text in docs.items():
                (docs_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (docs_dir / rel).write_text(text, encoding="utf-8")
            return FakeProc(["готово\n"])

        store.record_fixation(store.db(), task)
        self.set_state(task, "in_dev")
        out = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                runner.cmd_run(task)
            except SystemExit as exc:
                out.write(f"\nSystemExit(run): {exc.code}")
        return out.getvalue()

    def first_step(self, task: str, code: dict) -> str:
        """Первый шаг developer задачи — код `code` попадает в ветку
        коммитом пульта; провал шага — провал сценария."""
        spawned = len(self.spawned)
        out = self.developer_step(task, code, self.task_docs(task))
        self.assertEqual(spawned + 1, len(self.spawned),
                         self.msg(f"первый шаг не запустил агента:\n{out}\n"
                                  f"{self.journal(task)}"))
        self.assertEqual("in_dev", self.state_of(task),
                         self.msg(f"после первого шага:\n{out}\n{self.journal(task)}"))
        return out

    # ---------------------------------------------------------- answer

    def answer(self, task: str, text: str) -> str:
        path = self.scratch / f"otvet-{self.rng.randrange(1 << 40)}.txt"
        path.write_text(text, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                answer.cmd_answer(task, str(path))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    self.fail(self.msg(f"answer отказала: {exc.code}\n{out.getvalue()}"))
        return out.getvalue()

    def text(self) -> str:
        words = " ".join(self.rng.choice(WORDS)
                         for _ in range(self.rng.randrange(4, 10)))
        return f"Метка {self.rng.randrange(10 ** 9)}: {words}."

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"


# --------------------------------------------------------------------- AC-6

class InstructionInDeveloperBriefTest(DeveloperStepSandbox):

    def test_ac6_developer_brief_carries_instruction_and_unprocessed_answer(self):
        """Бриф разработчика после указания несёт его текст — и текст ответа на эскалацию, данного после старта прошлого шага.

        Задача прошла один шаг developer (штатный `run`). Случай без
        эскалации: в `in_dev` дано указание — `brief.developer_brief` несёт
        его текст. Случай с эскалацией (выбор случаен): после шага задача
        эскалирована, ответ `ANSWER-k.md` дан прежним путём, задача
        возвращена в `in_dev`, затем дано указание `ANSWER-(k+1).md` —
        бриф несёт текст обоих.

        Ловит мутацию: бриф по-прежнему несёт только последний
        `ANSWER-n.md` — указание вытесняет ответ на эскалацию, текста
        `ANSWER-k.md` в брифе нет; отбор «после старта прошлого шага»
        сравнивает с концом шага или с моментом последнего перехода
        состояния (возврат в `in_dev` — после ответа) — `ANSWER-k.md`
        отброшен; указание в `in_dev` не принимается — `answer` отказывает.
        """
        task = self.new_task()
        self.first_step(task, {f"kod/k_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"})
        escalation = bool(self.rng.randrange(2))
        expected = []
        if escalation:
            self.set_state(task, "escalated")
            reply = f"Ответ на эскалацию. {self.text()}"
            self.answer(task, reply + "\n")
            self.set_state(task, "in_dev")
            expected.append(reply)
        instruction = f"Указание Оператора. {self.text()}"
        self.answer(task, instruction + "\n")
        expected.append(instruction)

        text = brief.developer_brief(store.db(), task)

        case = "с ответом на эскалацию" if escalation else "без эскалации"
        for piece in expected:
            self.assertIn(piece, text,
                          self.msg(f"{case}: в брифе нет «{piece[:40]}…»"))


# --------------------------------------------------------------------- AC-9

class PullBeforeDeveloperStepTest(DeveloperStepSandbox):

    def test_ac9_behind_branch_gets_main_before_the_agent_starts(self):
        """Ветка, отставшая от `origin/main`, получает подтяжку до запуска агента; прежние коммиты ветки сохраняются.

        Первый шаг developer оставляет в ветке код задачи (коммит пульта
        по итогам шага — промежуточный коммит ветки). Затем в
        `origin/main` уезжает чужой коммит кода (случайный файл). Второй
        `run` в `in_dev`: на момент запуска агента чужой файл уже лежит в
        рабочем каталоге, а голова рабочей копии несёт чужой коммит; после
        шага `origin/main` и прежняя голова ветки — предки её головы.

        Ловит мутацию: подтяжки перед шагом нет (или она стоит после
        запуска агента — например, в `finally` шага) — на старте агента
        чужого файла нет и коммит `origin/main` не предок головы; подтяжка
        сделана сбросом ветки на `origin/main` (`reset --hard`) вместо
        слияния — прежний коммит ветки перестаёт быть предком.
        """
        task = self.new_task()
        own = f"kod/svoy_{self.rng.randrange(10 ** 6)}.py"
        self.first_step(task, {own: "OWN = 1\n"})
        before = self.branch_head(task)
        foreign_rel = f"chuzhoy_{self.rng.randrange(10 ** 6)}.py"
        foreign = self.push_foreign(foreign_rel, f"X = {self.rng.randrange(100)}\n")

        out = self.developer_step(task, {}, {})

        text = f"{out}\n{self.journal(task)}"
        self.assertEqual(2, len(self.spawned), self.msg(f"агент не запущен:\n{text}"))
        start = self.spawned[-1]
        self.assertTrue((start["cwd"] / foreign_rel).is_file(),
                        self.msg(f"на старте агента нет {foreign_rel}:\n{text}"))
        self.assertTrue(self.is_ancestor(self.clone, foreign, start["head"]),
                        self.msg(f"на старте агента origin/main не предок головы:\n{text}"))
        head = self.branch_head(task)
        self.assertTrue(self.is_ancestor(self.clone, foreign, head),
                        self.msg(f"origin/main не предок головы ветки:\n{text}"))
        self.assertTrue(self.is_ancestor(self.clone, before, head),
                        self.msg(f"прежняя голова ветки потеряна:\n{text}"))
        self.assertEqual("in_dev", self.state_of(task), self.msg(text))

    def test_ac9_fresh_branch_runs_without_merge(self):
        """Ветка, не отстающая от `origin/main`, — шаг без подтяжки: голова прежняя, коммита слияния нет.

        Задача только заведена (или уже прошла один шаг — выбор случаен),
        `origin/main` не двигался. `run` в `in_dev`, агент кода не пишет:
        голова рабочей копии на старте агента равна голове ветки до `run`,
        после шага голова ветки та же, коммитов слияния в ветке нет.

        Ловит мутацию: подтяжка перед шагом делается безусловно (`git
        merge --no-ff origin/main` без сверки отставания) — на старте
        агента голова ветки — новый коммит слияния.
        """
        task = self.new_task()
        stepped = bool(self.rng.randrange(2))
        docs = self.task_docs(task)
        if stepped:
            self.first_step(task, {f"kod/k_{self.rng.randrange(10 ** 6)}.py": "A = 1\n"})
            docs = {}
        before = self.branch_head(task)
        spawned = len(self.spawned)

        out = self.developer_step(task, {}, docs)

        text = f"{out}\n{self.journal(task)}"
        self.assertEqual(spawned + 1, len(self.spawned),
                         self.msg(f"агент не запущен:\n{text}"))
        self.assertEqual(before, self.spawned[-1]["head"],
                         self.msg(f"голова на старте агента сменилась:\n{text}"))
        self.assertEqual(before, self.branch_head(task),
                         self.msg(f"голова ветки сменилась:\n{text}"))
        merges = self.in_repo(self.clone, "rev-list", "--merges",
                              f"refs/heads/{self.branch_of(task)}").split()
        self.assertEqual([], merges, self.msg(f"коммиты слияния: {merges}\n{text}"))

    def test_ac9_unresolved_conflict_escalates_without_starting_the_agent(self):
        """Подтяжка с неразрешимым конфликтом перед шагом — эскалация с меткой «нужен шаг роли», агент не запущен.

        Первый шаг developer кладёт в ветку файл кода; затем в
        `origin/main` уезжает чужой коммит, создающий тот же путь с другим
        содержимым (не карта кодовой базы — авторазрешения нет). Второй
        `run` в `in_dev`: задача в `escalated`, у неё запись метки
        `pull.PULL_CONFLICT_ROLE_STEP_MARKER`, подмена агента не вызвана,
        новой записи «agent run started» нет.

        Ловит мутацию: исход подтяжки перед шагом не проверяется (шаг идёт
        дальше после `escalated`) — агент запущен и в журнале новая запись
        «agent run started»; подтяжка перед шагом зовёт свой `git merge`
        мимо общего узла — метки «нужен шаг роли» нет.
        """
        task = self.new_task()
        rel = f"kod/obshchiy_{self.rng.randrange(10 ** 6)}.py"
        self.first_step(task, {rel: f"OWN = {self.rng.randrange(100)}\n"})
        self.push_foreign(rel, f"FOREIGN = {self.rng.randrange(100, 200)}\n")
        rows_before = len(self.journal_rows(task))
        spawned = len(self.spawned)

        out = self.developer_step(task, {}, {})

        text = f"{out}\n{self.journal(task)}"
        new_rows = self.journal_rows(task)[rows_before:]
        self.assertEqual("escalated", self.state_of(task), self.msg(text))
        self.assertTrue(any(r["action"] == pull.PULL_CONFLICT_ROLE_STEP_MARKER
                            for r in new_rows),
                        self.msg(f"нет метки «нужен шаг роли»:\n{text}"))
        self.assertEqual(spawned, len(self.spawned),
                         self.msg(f"агент запущен при конфликте:\n{text}"))
        self.assertEqual([], [r for r in new_rows if r["action"] == STEP_STARTED],
                         self.msg(f"запись «{STEP_STARTED}» при конфликте:\n{text}"))


if __name__ == "__main__":
    unittest.main()
