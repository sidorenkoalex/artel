"""Тесты системных инвариантов (см. tasks/T010/SPEC.md).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности). Каждый тест этого
модуля кодирует инвариант системы из README «Инварианты» и docs/design.md,
а не деталь реализации. Ослабить, отключить, «временно» заскипать или
удалить любой из них может только Оператор отдельным ADR; для роли
конвейера это blocker в ревью, а не правка. Перечень «инвариант → тест →
откуда» — docs/invariants.md.

Модуль идёт поверх существующих юнитов, а не вместо них: свежесть
вердикта проверяется здесь сквозным путём FSM (разбор iteration —
test_review_freshness.py), бюджет — невозможностью обойти потолок
переходами (учёт денег — test_step_cost.py), уборка — неприкосновенностью
main (сценарии уборки — test_kill_cleanup.py).

`subprocess.run` в FSM-тестах подменён на весь класс: тесты выясняют,
при каких условиях оркестратор зовёт git, поэтому настоящая git-команда
в рабочем репозитории им не нужна и запрещена.
"""
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artel, budget, catalog, ci, cleanup,  # noqa: E402
                          config, fsm, gitcmd, runner, store)
from scripts import guard  # noqa: E402
from tests.sandbox import FakeProc, capture, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# Головной коммит ветки задачи и зелёный ответ `gh` про его проверки.
# Ветка в песочнице FSM ненастоящая (git подменён), поэтому sha и статус
# CI подставляются: предмет свипов — переходы, а не разговор с GitHub.
# Проверку самого статуса ведёт MergeNeedsGreenCiTest.
FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"
GREEN_CI = json.dumps({"total_count": 3, "check_runs": [
    {"name": "guard", "status": "completed", "conclusion": "success"},
    {"name": "python", "status": "completed", "conclusion": "success"},
    {"name": "protected-paths", "status": "completed", "conclusion": "skipped"},
]})

# Проверок больше, чем пришло в теле ответа: `total_count` обещает 31,
# записей 30 и все зелёные. До T018 гейт читал первую страницу и такой
# ответ считал зелёным — единственный вход, где неизвестный статус
# проходил за годный (SPEC T018, требования 1–2).
TRUNCATED_CI = json.dumps({
    "total_count": 31,
    "check_runs": [{"name": f"check-{i}", "status": "completed",
                    "conclusion": "success"} for i in range(30)],
})

# Все состояния FSM (docs/design.md §6 в срезе Фазы 0, artel.py docstring).
# tests_writing — A4 (tasks/T023): приёмочные тесты до кода, между
# spec_gate и in_dev.
FSM_STATES = ("spec_writing", "spec_gate", "tests_writing", "in_dev",
              "review", "acceptance", "merge_gate", "done", "escalated",
              "killed")

# Заготовки артефактов — валидные по guard: с T017 он вызывается кодом на
# каждом переходе `advance`, и артефакт без обязательных секций задачу не
# двигает. Свипы этого модуля должны упираться в инвариант, который они
# проверяют, а не в сломанную структуру своей же фикстуры.
SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: {status}
schema_version: 1
---

# SPEC: инвариант

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# Frontmatter плана отдельно от секций: GuardKeepsTheIntegritySectionTest
# собирает план с произвольным набором секций и проверяет, какие из них
# guard требует.
PLAN_HEAD = """---
task: {task}
type: plan
author_role: developer
status: {status}
schema_version: 1
---

# PLAN: инвариант

"""

PLAN_MD = PLAN_HEAD + """## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: инвариант

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


class SpyRun:
    """Подмена `subprocess.run`: команда запоминается и не исполняется."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append(list(cmd))
        # `rev-parse --verify --quiet refs/heads/*` (`gitcmd.branch_exists`)
        # — отдельно, с отказом (SPEC T048, тот же приём, что и
        # `tests.sandbox.fake_git`): `cmd_new` теперь решает, заводить ли
        # задачу, по ответу этого вызова (AC-3) — отвечай он успехом на
        # всё подряд, `cmd_new` увидел бы любую ветку уже существующей.
        if (len(cmd) >= 4 and cmd[1] == "rev-parse" and cmd[2] == "--verify"
                and cmd[-1].startswith("refs/heads/")):
            return subprocess.CompletedProcess(list(cmd), 1, "", "")
        return subprocess.CompletedProcess(list(cmd), 0, "", "")

    def git_subcommands(self) -> list[str]:
        """Подкоманды git по порядку: ['checkout', 'pull', 'merge', ...]."""
        return [c[1] for c in self.calls if len(c) > 1 and c[0] == "git"]


class FsmTest(unittest.TestCase):
    """Песочница FSM: БД и артефакты во временном каталоге, git не исполняется."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            # `cmd_new` (SPEC T048) пишет TZ.md/SPEC.md в
                            # worktree — та же логика, что и у ROLE_HOME
                            # выше: в песочницу, не в `.artel/worktrees/`
                            # репозитория (ROOT ниже намеренно реальный).
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.git_spy = SpyRun()
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", self.git_spy)
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)

        # ROOT намеренно НЕ подменяется целиком (в отличие от прочих путей
        # выше): `cmd_run` читает роль/навыки/конвенции с РЕАЛЬНОГО
        # `config.ROOT` (skills/, CLAUDE.md — см. `runner.role_env`), и свип
        # `AgentRunsOnlyFromRunTest`/`CountersNeverResetTest` по всем
        # состояниям это использует. С T043 `fsm.cmd_approve` на
        # `merge_gate` пишет `docs/retro/<id>.md` прямым `Path.write_text`
        # (не через замоканный `subprocess.run` выше) — без изоляции этот
        # путь ушёл бы в РЕАЛЬНЫЙ `docs/retro/` репозитория, где гоняются
        # тесты. Подменяем ROOT только на время самого вызова
        # `fsm.cmd_approve` (единственная точка, что и пишет `docs/...` —
        # `_regenerate_and_commit_map`, T042, туда же), на синтетический
        # каталог с заглушкой карты (тем же приёмом, что и
        # `RegenerateAndCommitMapTest` в tests/test_fsm_map_regen.py) —
        # остальной код (`cmd_run` и всё прочее) продолжает видеть
        # настоящий ROOT.
        real_root = config.ROOT
        retro_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, retro_root, ignore_errors=True)
        (retro_root / "docs").mkdir(parents=True)
        (retro_root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0\n---\n\n# карта\n", encoding="utf-8")
        original_approve = fsm.cmd_approve

        def approve_with_isolated_root(*args, **kwargs):
            # Наследники (например `tasks/T043/acceptance_tests/
            # retro_sandbox.py::RetroSandboxTest`) подменяют `config.ROOT`
            # своим собственным синтетическим деревом ПОСЛЕ `super().setUp()`
            # — тогда к моменту вызова `config.ROOT` уже не `real_root`, и
            # эта обёртка не имеет права навязывать СВОЙ каталог поверх.
            if config.ROOT != real_root:
                return original_approve(*args, **kwargs)
            with mock.patch.object(config, "ROOT", retro_root):
                return original_approve(*args, **kwargs)

        approve_patcher = mock.patch.object(
            fsm, "cmd_approve", approve_with_isolated_root)
        approve_patcher.start()
        self.addCleanup(approve_patcher.stop)

        # Песочница не имеет права зависеть от реального keychain машины,
        # на которой гоняются тесты (тот же приём, что и `TmpRootTest`
        # в test_multitarget_invariants.py) — иначе pre-flight (A3, SPEC
        # T022 требование 2) блокирует `run` не по предмету свипа, а по
        # тому, что нашлось в связке ключей конкретного ноутбука.
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.set_ci(GREEN_CI)

        # `cmd_init`/`cmd_new` — единственные вызовы этого setUp, читающие
        # ROOT ДО того, как ниже он специально остаётся реальным для
        # `cmd_run` (см. комментарий выше): холодный старт (SPEC T049)
        # сканирует ROOT на счётчик номеров и программный расход —
        # непропатченный ROOT читал бы настоящие `tasks/`, `docs/retro/`
        # и git-историю ЭТОГО репозитория и раздувал бы то и другое, ломая
        # ожидание «первая заведённая задача — T001». Тем же приёмом, что
        # `approve_with_isolated_root` ниже — ROOT патчится СИНТЕТИЧЕСКИМ
        # каталогом только на время самого вызова.
        cold_start_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, cold_start_root, ignore_errors=True)
        shutil.copytree(REPO_ROOT / "templates", cold_start_root / "templates")
        with mock.patch.object(config, "ROOT", cold_start_root):
            self.capture(catalog.cmd_init)
            self.capture(catalog.cmd_new, "Инварианты системы")
        self.tdir = config.TASKS / self.TASK
        # С SPEC T048 `cmd_new` пишет артефакты в worktree, не на диск
        # main — тесты этого файла кладут SPEC.md/PLAN.md/... напрямую на
        # диск (симуляция ветко-корректного fallback), каталог заводит
        # сам файл.
        self.tdir.mkdir(parents=True, exist_ok=True)
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    def set_ci(self, stdout: str, returncode: int = 0) -> None:
        """Ответ `gh` про проверки коммита; sha ветки — фиксированный.

        Подменяется низ (`ci.gh`, `ci.head_sha`), а решение «зелёный ли CI»
        каждый раз принимает настоящий `ci.branch_status`.
        """
        for target, value in (("gh", lambda *a: subprocess.CompletedProcess(
                                  list(a), returncode, stdout, "")),
                              ("head_sha", lambda branch: (FAKE_SHA, ""))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str, **fields) -> None:
        """Ставит состояние (и, если нужно, счётчики) в обход переходов."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        for column, value in fields.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    def write_spec(self, status: str) -> None:
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK, status=status), encoding="utf-8")

    def write_plan(self, status: str) -> None:
        (self.tdir / "PLAN.md").write_text(
            PLAN_MD.format(task=self.TASK, status=status), encoding="utf-8")

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def write_answer(self, n: int) -> None:
        """ANSWER-n.md — вход гейта возврата из эскалации класса «вопрос
        роли» (SPEC T075, AC-3): без него `approve` из `escalated` для
        вердикта REVIEW.md `status: escalate` отказывает."""
        (self.tdir / f"ANSWER-{n}.md").write_text(
            f"---\ntask: {self.TASK}\ntype: answer\nauthor_role: operator\n"
            f"status: ready\nschema_version: 2\n---\n\n"
            f"# ANSWER-{n}: ответ Оператора\n\n## Ответы\n\nOK\n",
            encoding="utf-8")

    def commands(self) -> list[tuple[str, object]]:
        """Все команды CLI, кроме `init` и `new` (они не двигают задачу)."""
        return [
            ("advance", lambda: fsm.cmd_advance(self.TASK)),
            ("approve", lambda: fsm.cmd_approve(self.TASK)),
            ("reject", lambda: fsm.cmd_reject(self.TASK, "причина")),
            ("run", lambda: runner.cmd_run(self.TASK)),
            ("budget", lambda: budget.cmd_budget(self.TASK, "50")),
            ("kill", lambda: cleanup.cmd_kill(self.TASK)),
            ("status", catalog.cmd_status),
            ("show", lambda: catalog.cmd_show(self.TASK)),
            ("log", lambda: catalog.cmd_log(self.TASK)),
        ]

    def run_command(self, call) -> tuple[str, mock.Mock]:
        """Прогон команды с подменённым агентом; SystemExit — тоже исход."""
        out = ""
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            with contextlib.suppress(SystemExit):
                out = self.capture(call)
        return out, popen


class FsmStatesCoverTheCodeTest(unittest.TestCase):
    """Страховка свипов: `FSM_STATES` — список, а не производная от кода.

    Состояния Фазы 0 — строковые литералы в `cmd_*`, реестра состояний нет
    (PLAN «Риски»). Механически сверяемо одно: рабочие состояния из
    `STATE_ROLE`. Новое рабочее состояние, забытое в `FSM_STATES`, иначе
    молча выпало бы из всех свипов модуля — и инварианты в нём не
    проверялись бы вовсе.
    """

    def test_every_working_state_is_swept(self):
        self.assertLessEqual(set(config.STATE_ROLE), set(FSM_STATES))


class MergeOnlyFromMergeGateTest(FsmTest):
    """Инвариант 12 (ред. ADR-0006): в main мержит только `approve` из
    merge_gate.

    Источник: docs/design.md §2 (единственное право записи оркестратора —
    merge прошедшего гейты MR), §4 (ревью MR → merge — ручной гейт),
    CLAUDE.md (мерж делает оркестратор, никакая роль — нет); ADR-0006 —
    единственный merge вне гейта — актуализация ветки задачи от main
    (сверка свежести T051): в worktree задачи (`-C`), вливает main,
    ветку задачи в аргументах не упоминает, main не изменяет.
    """

    @staticmethod
    def _plain_args(call: list[str]) -> list[str]:
        """argv git-вызова без пар `-C <путь>` / `-c <ключ=значение>`.

        Свип до ADR-0006 брал подкоманду как `argv[1]` и не видел merge
        в форме `git -C <path> merge ...` (`gitcmd.in_repo`) — буква была
        уже намерения. Нормализация закрывает эту дыру: подкоманда и её
        аргументы читаются из любого фактического вида вызова.
        """
        args, i = [], 1
        while i < len(call):
            if call[i] in ("-C", "-c") and i + 1 < len(call):
                i += 2
                continue
            args.append(call[i])
            i += 1
        return args

    def setUp(self):
        super().setUp()
        # Артефакты готовы намеренно: команда, отвалившаяся на «SPEC не
        # ready», до кода перехода не доходит и про merge ничего не
        # доказывает. Свип должен проверять переходы, а не пустую задачу.
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)

    def test_no_other_state_and_no_other_command_merges(self):
        """Требование 2.1: другого пути влить что-либо в main нет.

        Вне merge_gate+approve merge допустим единственный (ADR-0006) —
        актуализация ветки задачи от main: обязан идти в `-C`-форме
        (worktree задачи, не рабочая копия пульта), вливать main и не
        упоминать ветку задачи в аргументах. Любой другой merge — красный.
        """
        for state in FSM_STATES:
            for name, call in self.commands():
                if name == "kill":
                    # Уборка сносит артефакты задачи, и остаток свипа гонялся
                    # бы по пустому каталогу. Неприкосновенность main при
                    # kill — свой инвариант, KillKeepsMainIntactTest.
                    continue
                if state == "merge_gate" and name == "approve":
                    continue
                with self.subTest(состояние=state, команда=name):
                    # reviewed_iter=0: вердикт снова свежий, иначе advance
                    # из review выходит на «уже учтён», не дойдя до перехода.
                    self.set_state(state, reviewed_iter=0)
                    self.git_spy.calls.clear()

                    self.run_command(call)

                    for raw in self.git_spy.calls:
                        if not raw or raw[0] != "git":
                            continue
                        args = self._plain_args(raw)
                        if not args or args[0] != "merge":
                            continue
                        why = f"{name} из {state}: git merge {raw}"
                        self.assertIn("-C", raw,
                                      f"{why} — merge вне worktree задачи")
                        self.assertIn(config.MAIN_BRANCH, args,
                                      f"{why} — вливается не main")
                        self.assertNotIn(self.branch, args,
                                         f"{why} — ветка задачи в merge "
                                         f"вне merge_gate")

    def test_merge_gate_approve_is_that_path(self):
        """Контроль: из merge_gate approve мержит ветку задачи и закрывает её."""
        self.set_state("merge_gate")

        self.capture(fsm.cmd_approve, self.TASK)

        # Ассерт по содержанию инварианта, а не по точному списку вызовов:
        # merge случается здесь, после обновления main, и мержит ветку задачи.
        # Равенство всей последовательности покраснело бы на безобидном
        # `git fetch --prune`, а ложный красный в неослабляемом тесте
        # провоцирует ровно то ослабление, ради запрета которого он написан.
        subcommands = self.git_spy.git_subcommands()
        self.assertIn("merge", subcommands)
        self.assertLess(subcommands.index("checkout"), subcommands.index("merge"))
        self.assertLess(subcommands.index("pull"), subcommands.index("merge"))
        merge = [c for c in self.git_spy.calls if c[:2] == ["git", "merge"]][0]
        self.assertIn(self.branch, merge)
        self.assertEqual(self.state(), "done")

    def test_merge_failure_leaves_the_task_in_the_gate(self):
        """Провал merge не закрывает задачу (инвариант 6/AC-6, T052):
        содержательный конфликт возвращает её в in_dev с диагностикой в
        журнале, не молча оставляет на гейте (SPEC T052, требование 2,
        AC-3) — задача НЕ переходит в `done`.
        """
        self.set_state("merge_gate")

        def failing(cmd, *args, **kwargs):
            self.git_spy(cmd, *args, **kwargs)
            argv = list(cmd)
            if argv[:3] == ["git", "merge", "--no-ff"]:
                return subprocess.CompletedProcess(argv, 1, "", "конфликт")
            if argv[:4] == ["git", "diff", "--name-only", "--diff-filter=U"]:
                return subprocess.CompletedProcess(argv, 0, "shared.txt\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(gitcmd.subprocess, "run", failing):
            self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "in_dev")
        self.assertNotEqual(self.state(), "done")
        journal = "\n".join(r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)))
        self.assertIn("shared.txt", journal,
                     "конфликтующий файл обязан попасть в журнал задачи")

    def test_merge_abort_failure_keeps_task_in_the_gate(self):
        """Отказ самого `git merge --abort` (SPEC T052, требование 5):
        main нельзя объявить чистым, когда он не чист — переход состояния
        не выполняется, задача остаётся в `merge_gate` инфраструктурным
        отказом, а не молча уходит в `in_dev`/`escalated` с грязным main.
        """
        self.set_state("merge_gate")

        def failing(cmd, *args, **kwargs):
            self.git_spy(cmd, *args, **kwargs)
            argv = list(cmd)
            if argv[:3] == ["git", "merge", "--no-ff"]:
                return subprocess.CompletedProcess(argv, 1, "", "конфликт")
            if argv[:4] == ["git", "diff", "--name-only", "--diff-filter=U"]:
                return subprocess.CompletedProcess(argv, 0, "shared.txt\n", "")
            if argv[:3] == ["git", "merge", "--abort"]:
                return subprocess.CompletedProcess(argv, 1, "", "не могу")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(gitcmd.subprocess, "run", failing):
            with self.assertRaises(SystemExit) as exit_:
                self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "merge_gate",
                         "abort не удался — задача обязана остаться на гейте")
        self.assertIn("abort", str(exit_.exception))
        journal = "\n".join(r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)))
        self.assertIn("не могу", journal,
                     "причина отказа abort обязана попасть в журнал")


class MergeNeedsGreenCiTest(FsmTest):
    """Инвариант: merge из merge_gate требует зелёного CI головного коммита.

    Источник: docs/design.md §4 (guards неотключаемы, смержить с красным CI
    нельзя), tasks/T017/SPEC.md, требование 6. До T017 «CI зелёный» проверял
    глазами Оператор — код мержил что дадут; инвариант в том, что теперь
    проверяет код и что неизвестный статус трактуется как запрет.

    Проверяются исходы, каждый из которых раньше давал бы merge: CI упал,
    CI ещё идёт, проверок нет вовсе, `gh` не отвечает, ответ не разобрать.
    """

    # (имя случая, ответ `gh`, код возврата)
    NOT_GREEN = (
        ("проверка упала",
         json.dumps({"check_runs": [
             {"name": "python", "status": "completed", "conclusion": "failure"}]}), 0),
        ("проверка отменена",
         json.dumps({"check_runs": [
             {"name": "guard", "status": "completed", "conclusion": "cancelled"}]}), 0),
        ("CI ещё идёт",
         json.dumps({"check_runs": [
             {"name": "guard", "status": "in_progress", "conclusion": None}]}), 0),
        ("проверок нет вовсе", json.dumps({"check_runs": []}), 0),
        ("проверок больше, чем в ответе", TRUNCATED_CI, 0),
        ("gh не ответил", "", 1),
        ("ответ не разобрать", "не-JSON", 0),
    )

    def setUp(self):
        super().setUp()
        self.write_spec("approved")
        self.write_plan("approved")
        self.write_review("approved", 1)

    def test_no_merge_without_a_green_ci(self):
        """Требование 6: не-зелёный и неизвестный статус merge не выполняют."""
        for name, stdout, returncode in self.NOT_GREEN:
            with self.subTest(случай=name):
                self.set_state("merge_gate")
                self.git_spy.calls.clear()
                self.set_ci(stdout, returncode)

                with self.assertRaises(SystemExit) as exit_:
                    self.capture(fsm.cmd_approve, self.TASK)

                self.assertNotIn("merge", self.git_spy.git_subcommands(),
                                 f"«{name}» дошло до git merge")
                self.assertEqual(self.state(), "merge_gate",
                                 "задача осталась на гейте merge")
                self.assertIn("merge отклонён", str(exit_.exception))

    def test_the_refusal_names_the_reason_in_the_journal(self):
        """Отказ разбирают по журналу: причина в нём, а не только на экране."""
        self.set_state("merge_gate")
        self.set_ci(json.dumps({"check_runs": [
            {"name": "python", "status": "completed", "conclusion": "failure"}]}))

        with contextlib.suppress(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK)

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (self.TASK, "статус CI ветки"))]
        self.assertTrue(any("python=failure" in d for d in details), details)

    def test_green_ci_merges(self):
        """Контроль: гейт проходим — зелёный CI мержит, как и раньше."""
        self.set_state("merge_gate")

        self.capture(fsm.cmd_approve, self.TASK)

        self.assertIn("merge", self.git_spy.git_subcommands())
        self.assertEqual(self.state(), "done")


class AgentRunsOnlyFromRunTest(FsmTest):
    """Инвариант README 1: оркестратор не думает — агента зовёт только `run`.

    Источник: README «Инварианты» 1, docs/design.md §2 (оркестратор
    никогда не исполняет работу сам), §4 (policy проверяет оркестратор,
    а не агент).
    """

    def setUp(self):
        super().setUp()
        # Как и в MergeOnlyFromMergeGateTest: без готовых артефактов все три
        # ветки cmd_advance выходят на проверке артефакта, и свип доказывал
        # бы «пустая задача никуда не движется», а не сам инвариант.
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)

    def test_no_fsm_command_starts_an_agent(self):
        for state in FSM_STATES:
            for name, call in self.commands():
                if name in ("run", "kill"):
                    # run — сам предмет инварианта; kill сносит каталог
                    # задачи, и остаток свипа шёл бы по пустой задаче.
                    continue
                with self.subTest(состояние=state, команда=name):
                    # reviewed_iter=0: иначе advance из review упирается
                    # в «вердикт уже учтён» и до перехода не доходит.
                    self.set_state(state, reviewed_iter=0)

                    _, popen = self.run_command(call)

                    popen.assert_not_called()

    def test_run_starts_the_agent_only_in_working_states(self):
        for state in FSM_STATES:
            with self.subTest(состояние=state):
                self.set_state(state)

                _, popen = self.run_command(lambda: runner.cmd_run(self.TASK))

                started = state in config.STATE_ROLE
                self.assertEqual(popen.called, started)


class FreshVerdictGuardsAcceptanceTest(FsmTest):
    """Инвариант: review → acceptance — только по свежему вердикту ревьювера.

    Источник: docs/design.md §4 (лимит итераций ревью и эскалация после
    него), artifacts.py `fresh_verdict_iteration`. Здесь — сквозной путь FSM
    и отсутствие обходных команд; разбор поля iteration покрыт юнитами
    tests/test_review_freshness.py.
    """

    def test_every_return_to_dev_requires_a_new_verdict(self):
        """Требование 2.2: путь SPEC → ревью → приёмка → возврат → ревью."""
        self.write_spec("ready")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "spec_gate")

        self.capture(fsm.cmd_approve, self.TASK)
        self.write_plan("ready")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review", "REVIEW.md ещё нет")
        self.assertIn("жду вердикта", out)

        self.write_review("approved", 1)
        self.capture(fsm.cmd_advance, self.TASK)
        # ADR-0009: маршрут review -> verifying -> acceptance (B1b, T079).
        # До мержа T079 advance ведёт из review сразу в acceptance — тест
        # принимает оба маршрута; охраняемое здесь — свежесть вердикта
        # и счётчики, строгость маршрута кодирует AC-4 задачи T079.
        if self.state() == "verifying":
            self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance")

        self.capture(fsm.cmd_reject, self.TASK, "критерий 2 не выполнен")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review", "вердикт #1 уже учтён")
        self.assertIn("уже учтён", out)

        self.write_review("approved", 2)
        self.capture(fsm.cmd_advance, self.TASK)
        if self.state() == "verifying":
            self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance")

    def test_stale_verdict_is_not_passed_by_any_command(self):
        """Обхода нет: approve и остальные команды вердикт не заменяют."""
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("review")
        self.capture(fsm.cmd_advance, self.TASK)
        self.capture(fsm.cmd_reject, self.TASK, "доработать")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        for name, call in self.commands():
            if name == "kill":  # kill switch — отдельный инвариант
                continue
            with self.subTest(команда=name):
                self.set_state("review")

                self.run_command(call)

                self.assertNotEqual(
                    self.state(), "acceptance",
                    f"{name} провела задачу в приёмку по учтённому вердикту")

    def test_escalation_and_return_do_not_make_the_verdict_fresh(self):
        """Возврат из escalated не обнуляет учтённую итерацию."""
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("review")
        self.capture(fsm.cmd_advance, self.TASK)
        if self.state() == "verifying":
            self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance")

        self.set_state("escalated")
        self.capture(fsm.cmd_approve, self.TASK)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "review")
        self.assertEqual(self.task_row()["reviewed_iter"], 1)


class ExhaustedBudgetIsNotBypassableTest(FsmTest):
    """Инвариант: исчерпанный бюджет блокирует агента до решения Оператора.

    Источник: README «Инварианты» 5 (потолок задачи = её бюджет),
    docs/design.md §6 (потолки жёсткие: пауза и эскалация, не деградация),
    §4 (увеличение бюджета — manual всегда).
    """

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev", budget_usd=1.0, spent_usd=1.0)

    def try_run(self) -> tuple[str, mock.Mock]:
        return self.run_command(lambda: runner.cmd_run(self.TASK))

    def test_run_refuses_and_no_agent_starts(self):
        """Требование 2.3: за потолком шаг не начинается."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            with self.assertRaises(SystemExit) as exit_:
                self.capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()
        self.assertIn("бюджет исчерпан", str(exit_.exception))

    def test_advance_does_not_unblock_the_run(self):
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        _, popen = self.try_run()

        popen.assert_not_called()

    def test_approve_from_escalated_does_not_unblock_the_run(self):
        """Возврат из эскалации — не деньги: шаг по-прежнему не стартует."""
        self.set_state("escalated", escalated_from="in_dev")

        self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "in_dev")
        _, popen = self.try_run()

        popen.assert_not_called()

    def test_transitions_do_not_reset_the_spent(self):
        for name, call in self.commands():
            if name in ("kill", "budget"):  # закрывают задачу или поднимают потолок
                continue
            with self.subTest(команда=name):
                self.set_state("in_dev")

                self.run_command(call)

                self.assertGreaterEqual(self.task_row()["spent_usd"], 1.0)

    def test_only_the_operator_ceiling_unblocks_the_run(self):
        """Контроль: блокировка не вечная — её снимает `budget` Оператора."""
        self.capture(budget.cmd_budget, self.TASK, "5")

        _, popen = self.try_run()

        popen.assert_called_once()


class ParallelTaskLimitIsNotBypassableTest(FsmTest):
    """Инвариант: `MAX_PARALLEL_TASKS` блокирует старт агентного шага, пока
    число других задач с живым lease не опустится ниже потолка — не
    обходится ни повторным `run`, ни `advance` следующим за отказавшим
    шагом (SPEC T060, требование 6, AC-6).
    """

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("in_dev")
        conn = store.db()
        for i in range(config.MAX_PARALLEL_TASKS):
            task_id = f"T90{i}"
            store.insert_task(conn, task_id, f"Другая задача {task_id}",
                              "in_dev", f"task/{task_id.lower()}-fake",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
            conn.execute(
                "INSERT INTO leases (task_id, session_id, pid, hostname,"
                " heartbeat_ts) VALUES (?,?,?,?,?)",
                (task_id, f"session-busy-{i}", os.getpid(),
                 socket.gethostname(), store.now()))
        conn.commit()

    def try_run(self) -> tuple[str, mock.Mock]:
        return self.run_command(lambda: runner.cmd_run(self.TASK))

    def test_run_refuses_and_no_agent_starts(self):
        with mock.patch.object(runner, "spawn_agent") as popen:
            with self.assertRaises(SystemExit) as exit_:
                self.capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()
        self.assertIn(str(config.MAX_PARALLEL_TASKS), str(exit_.exception))

    def test_advance_does_not_unblock_the_run(self):
        """`advance` — переход по готовности артефакта, лимитер run с ним не
        связан: продвижение состояния не снимает и не обходит его отказ."""
        self.try_run()
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

        _, popen = self.try_run()

        popen.assert_not_called()

    def test_retry_does_not_bypass_the_refusal(self):
        _, popen1 = self.try_run()
        popen1.assert_not_called()

        _, popen2 = self.try_run()
        popen2.assert_not_called()

    def test_refusal_is_journalled(self):
        journalled_before = len(store.task_steps(store.db(), self.TASK))

        self.try_run()

        new_steps = store.task_steps(store.db(), self.TASK)[journalled_before:]
        self.assertTrue(
            any("лимит параллельных задач" in s["action"] for s in new_steps),
            new_steps)

    def test_own_lease_does_not_count_against_the_task_itself(self):
        """Требование 2: собственный lease стартующей задачи — не в счёт."""
        conn = store.db()
        conn.execute("DELETE FROM leases WHERE task_id=?", (self.TASK,))
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "own-session", os.getpid(), socket.gethostname(),
             store.now()))
        # На потолке ровно MAX_PARALLEL_TASKS чужих — свой lease его не
        # усугубляет и не защищает: отказ остаётся тем же самым отказом.
        conn.commit()

        _, popen = self.try_run()

        popen.assert_not_called()

    def test_below_the_ceiling_run_starts(self):
        """Контроль: ниже потолка (одна чужая задача свободна) run проходит."""
        conn = store.db()
        conn.execute("DELETE FROM leases WHERE task_id=?", ("T900",))
        conn.commit()

        _, popen = self.try_run()

        popen.assert_called_once()


class CountersNeverResetTest(FsmTest):
    """Инвариант: счётчики итераций глобальные на задачу и не сбрасываются.

    Источник: docs/design.md §4 («все счётчики итераций — глобальные
    на задачу», повторный вход в фазу их не сбрасывает), README
    «Инварианты» 3 (после лимита — Оператор, не ретрай).
    """

    COUNTERS = ("review_iters", "accept_rejects", "reviewed_iter", "spent_usd")

    def setUp(self):
        super().setUp()
        self.write_plan("ready")
        self.set_state("review")
        patcher = mock.patch.object(runner.time, "sleep", lambda _: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def counters(self) -> dict:
        row = self.task_row()
        return {name: row[name] for name in self.COUNTERS}

    def step(self, label: str, fn, *args) -> None:
        """Переход, после которого ни один счётчик не стал меньше."""
        before = self.counters()
        with contextlib.suppress(SystemExit):
            self.capture(fn, *args)
        after = self.counters()
        for name, value in before.items():
            self.assertGreaterEqual(after[name], value,
                                    f"переход «{label}» сбросил {name}")

    def verdict(self, status: str, iteration: int) -> None:
        self.write_review(status, iteration)
        self.step(f"вердикт {status} #{iteration}", fsm.cmd_advance, self.TASK)

    def test_no_transition_of_the_full_cycle_resets_a_counter(self):
        """Требование 2.4: цикл с эскалациями, возвратами и лимитами."""
        self.verdict("changes_requested", 1)
        self.assertEqual(self.state(), "in_dev")
        self.step("in_dev -> review", fsm.cmd_advance, self.TASK)

        self.verdict("escalate", 2)
        self.assertEqual(self.state(), "escalated")
        # Вердикт REVIEW.md `status: escalate` — эскалация со
        # структурированным вопросом роли (SPEC T075, AC-3): `approve`
        # из escalated требует ANSWER-n.md, иначе отказывает.
        self.write_answer(1)
        self.step("возврат из эскалации", fsm.cmd_approve, self.TASK)
        self.step("in_dev -> review", fsm.cmd_advance, self.TASK)

        self.verdict("approved", 3)
        if self.state() == "verifying":
            self.step("verifying -> acceptance", fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "acceptance")
        self.step("отказ приёмки", fsm.cmd_reject, self.TASK, "не то")
        self.step("in_dev -> review", fsm.cmd_advance, self.TASK)

        self.verdict("approved", 4)
        if self.state() == "verifying":
            self.step("verifying -> acceptance", fsm.cmd_advance, self.TASK)
        self.step("лимит отказов приёмки", fsm.cmd_reject, self.TASK,
                  "снова не то")
        self.assertEqual(self.state(), "escalated")
        self.step("возврат из эскалации", fsm.cmd_approve, self.TASK)

        self.step("поднятие бюджета", budget.cmd_budget, self.TASK, "42")
        self.step("провал агента", self.failing_run)
        self.assertEqual(self.state(), "escalated")
        self.step("возврат из эскалации", fsm.cmd_approve, self.TASK)

        row = self.task_row()
        self.assertEqual(
            (row["review_iters"], row["accept_rejects"], row["reviewed_iter"]),
            (1, 1, 4), "счётчики прошли весь цикл без единого сброса")

    def failing_run(self) -> None:
        """Прогон, в котором агент падает все положенные попытки."""
        procs = [FakeProc(["упал\n"], 1) for _ in range(config.AGENT_ATTEMPTS)]
        with mock.patch.object(runner, "spawn_agent", side_effect=procs):
            runner.cmd_run(self.TASK)

    def test_exhausted_review_limit_is_not_reopened_by_escalation(self):
        """Эскалация по лимиту и возврат из неё не выдают новых итераций."""
        self.set_state("review", review_iters=config.LIMIT_REVIEW_ITERS - 1)

        self.verdict("changes_requested", 1)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.task_row()["review_iters"],
                         config.LIMIT_REVIEW_ITERS - 1)

        self.step("возврат из эскалации", fsm.cmd_approve, self.TASK)
        self.step("in_dev -> review", fsm.cmd_advance, self.TASK)
        self.verdict("changes_requested", 2)

        self.assertEqual(self.state(), "escalated", "лимит остался исчерпанным")


class ManualGatesNeedTheOperatorTest(FsmTest):
    """Инвариант: ручной гейт проходит только Оператор, и только явно.

    Источник: README «Инварианты» 4 (молчание ≠ согласие),
    docs/design.md §4 (два жёстких правила политики гейтов), §6
    (`awaiting-approval`: по таймауту напоминание, никогда автопроход).
    """

    GATES = ("spec_gate", "acceptance", "merge_gate")

    def setUp(self):
        super().setUp()
        # Все артефакты задачи готовы: гейт держится решением Оператора,
        # а не отсутствием документов.
        self.write_spec("approved")
        self.write_plan("approved")
        self.write_review("approved", 1)

    def test_advance_never_passes_a_manual_gate(self):
        """Требование 2.6: `advance` — не подтверждение."""
        for gate in self.GATES:
            with self.subTest(гейт=gate):
                self.set_state(gate)

                out = self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), gate)
                self.assertIn("двигается через approve/reject/run", out)

    def test_repeated_polling_does_not_pass_a_gate(self):
        """Повторный опрос — не согласие: гейт стоит, сколько его ни дёргай.

        Про «ни по времени» тест молчит осознанно: часов у FSM Фазы 0 нет
        (`advance` их не смотрит), автопроходить по таймауту нечему.
        Подмена `store.now` здесь создавала бы видимость покрытия — см.
        вторую таблицу docs/invariants.md.
        """
        for gate in self.GATES:
            with self.subTest(гейт=gate):
                self.set_state(gate)

                for _ in range(5):
                    self.capture(fsm.cmd_advance, self.TASK)

                self.assertEqual(self.state(), gate)
                self.assertNotIn("merge", self.git_spy.git_subcommands())

    def test_no_command_but_approve_and_reject_passes_a_gate(self):
        for gate in self.GATES:
            for name, call in self.commands():
                if name in ("approve", "reject", "kill"):
                    continue  # решения Оператора: они и есть проход гейта
                with self.subTest(гейт=gate, команда=name):
                    self.set_state(gate)

                    self.run_command(call)

                    self.assertEqual(self.state(), gate,
                                     f"{name} прошла гейт {gate} за Оператора")

    def test_operator_approve_passes_each_gate(self):
        """Контроль: гейты проходимы — но только командой Оператора."""
        for gate, expected in (("spec_gate", "in_dev"),
                               ("acceptance", "merge_gate"),
                               ("merge_gate", "done")):
            with self.subTest(гейт=gate):
                self.set_state(gate)

                self.capture(fsm.cmd_approve, self.TASK)

                self.assertEqual(self.state(), expected)

    def test_operator_reject_returns_acceptance_to_dev(self):
        self.set_state("acceptance")

        self.capture(fsm.cmd_reject, self.TASK, "критерий 3 не выполнен")

        self.assertEqual(self.state(), "in_dev")

    def test_run_does_not_start_an_agent_on_a_gate(self):
        """На ручном гейте задача ждёт человека и не жжёт токены."""
        for gate in self.GATES:
            with self.subTest(гейт=gate):
                self.set_state(gate)

                out, popen = self.run_command(lambda: runner.cmd_run(self.TASK))

                popen.assert_not_called()
                self.assertEqual(self.state(), gate)


class KillKeepsMainIntactTest(unittest.TestCase):
    """Инвариант: kill убирает хвосты, но не трогает main и его содержимое.

    Источник: docs/design.md §6 (kill switch; артефакты остаются
    в tasks/<id>/ как история), tasks/T008/SPEC.md. Git тут настоящий:
    ROOT уводится во временный репозиторий, рабочее дерево не трогается.
    Сценарии уборки покрыты tests/test_kill_cleanup.py — здесь проверяется
    только неприкосновенность main.
    """

    TASK = "T001"

    def setUp(self):
        self.repo = None
        self.fresh_repo()

    def fresh_repo(self) -> None:
        """Пустой репозиторий с созданной задачей; предыдущий закрывается тут же.

        Сценарии уборки несовместимы в одном дереве (смерженная ветка против
        неслитой), поэтому каждому нужен свой репозиторий. Стек закрывает
        предыдущий сразу, а не копит открытые каталоги и патчи до конца
        теста: по упавшему сценарию должно быть видно, чей это фикстур.
        """
        if self.repo is not None:
            self.repo.close()
        self.repo = contextlib.ExitStack()
        self.addCleanup(self.repo.close)  # ExitStack.close() идемпотентен

        tmp = tempfile.TemporaryDirectory()
        self.repo.callback(resilient_tmp_cleanup, tmp)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            # Worktree задачи (SPEC T045): kill убирает его —
                            # без патча ушёл бы в .artel/worktrees/ РЕАЛЬНОГО
                            # репозитория пульта, не песочницы.
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            self.repo.enter_context(mock.patch.object(config, attr, value))

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Инварианты системы")
        self.branch = store.db().execute(
            "SELECT branch FROM tasks WHERE id=?", (self.TASK,)).fetchone()[0]

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    capture = staticmethod(capture)

    def main_state(self) -> tuple[str, str]:
        """Коммит main и его дерево — то, что kill обязан оставить как есть."""
        return (self.git("rev-parse", config.MAIN_BRANCH),
                self.git("ls-tree", "-r", config.MAIN_BRANCH))

    def task_dir(self) -> Path:
        return config.TASKS / self.TASK

    def commit_artifacts_in_branch(self) -> None:
        """С SPEC T048 `cmd_new` уже коммитит SPEC.md в ветку задачи одним
        коммитом ("<id>: ТЗ Оператора (...)") — заводить его тут больше
        нечего; метод остаётся no-op ради вызовов ниже, вместо удаления
        (обратная совместимость сценариев `test_kill_never_commits_to_main`)."""

    def merge_branch_into_main(self) -> None:
        self.commit_artifacts_in_branch()
        self.git("merge", "--no-ff", self.branch, "-m", "merge")

    # ----------------------------------------------------------- сценарии

    def test_merged_artifacts_survive_the_kill(self):
        """Требование 2.5: попавшее в main — история, её kill не удаляет."""
        self.merge_branch_into_main()
        before = self.main_state()

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.main_state(), before, "kill изменил main")
        self.assertTrue((self.task_dir() / "SPEC.md").exists())
        self.assertEqual(self.git("status", "--porcelain"), "",
                         "содержимое main осталось на диске без изменений")

    def test_kill_never_commits_to_main(self):
        """main не двигается ни в одном сценарии уборки."""
        scenarios = {
            "до коммита": lambda: None,
            "артефакты только в ветке": self.commit_artifacts_in_branch,
            "ветка задачи под HEAD": lambda: (
                self.commit_artifacts_in_branch(),
                # Ветка задачи уже стоит в СВОЁМ worktree (SPEC T045/T048,
                # `cmd_new` заводит его сразу) — git не даст ту же ветку
                # ЕЩЁ и в главной копии, пока не убрать первый чекаут.
                self.git("worktree", "remove", "--force",
                        str(config.WORKTREES / self.TASK)),
                self.git("checkout", self.branch)),
            "смержено в main": self.merge_branch_into_main,
        }
        for name, prepare in scenarios.items():
            with self.subTest(сценарий=name):
                self.fresh_repo()
                prepare()
                before = self.main_state()

                self.capture(cleanup.cmd_kill, self.TASK)

                self.assertEqual(self.main_state(), before)

    def test_unmerged_branch_is_removed_without_touching_main(self):
        """Уборка работает: неслитая ветка уходит, main остаётся прежним."""
        self.commit_artifacts_in_branch()
        before = self.main_state()

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.main_state(), before)
        self.assertNotIn(self.branch,
                         self.git("branch", "--format=%(refname:short)").split())
        self.assertFalse(self.task_dir().exists())


class GuardKeepsTheIntegritySectionTest(unittest.TestCase):
    """Инвариант: оценка влияния на систему — артефакт, а не мысль.

    Источник: ADR-0002, производное правило 1 (секция «Влияние на систему»
    в PLAN.md обязательна и проверяется guard). Guard — автоматическое
    неотключаемое условие перехода (docs/design.md §4).
    """

    SECTIONS = ("Подход", "Шаги", "Покрытие требований", "Влияние на систему")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "PLAN.md"

    def write_plan(self, sections) -> Path:
        body = "".join(f"## {s}\n\nтекст\n\n" for s in sections)
        self.path.write_text(
            PLAN_HEAD.format(task="T001", status="ready") + body,
            encoding="utf-8")
        return self.path

    def test_plan_without_impact_assessment_is_rejected(self):
        without = [s for s in self.SECTIONS if s != "Влияние на систему"]

        errors = guard.check(self.write_plan(without))

        self.assertTrue(any("Влияние на систему" in e for e in errors), errors)

    def test_complete_plan_passes(self):
        self.assertEqual(guard.check(self.write_plan(self.SECTIONS)), [])


class MainCopyGuardTest(unittest.TestCase):
    """Инвариант: пульт исполняется только из главной копии, не из
    git-worktree (tasks/T056/SPEC.md). Инцидент 28.08 (T052, T055):
    `config.ROOT` резолвился внутрь `.artel/worktrees/<id>`, и код на
    ходу заводил там паразитную пустую `.artel/state.db`.

    Признак worktree из требования 2 SPEC — файл-ссылка `ROOT/.git`
    (`gitdir: <main>/.git/worktrees/<id>`), не каталог; фейкового файла
    достаточно, настоящий `git worktree add` не нужен — сквозной прогон
    через реальный git ведёт `tasks/T056/acceptance_tests/
    test_ac1_worktree_root_refuses.py`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): см. KillKeepsMainIntactTest — /var симлинк на macOS.
        self.sandbox = Path(tmp.name).resolve()
        self.main_copy = self.sandbox / "main"
        self.worktree = self.sandbox / "worktree"
        self.worktree.mkdir(parents=True)
        (self.worktree / ".git").write_text(
            f"gitdir: {self.main_copy}/.git/worktrees/T001\n",
            encoding="utf-8")

    def test_worktree_root_refuses_before_touching_the_db(self):
        with mock.patch.object(config, "ROOT", self.worktree), \
             mock.patch.object(sys, "argv", ["artel.py", "status"]):
            with self.assertRaises(SystemExit) as ctx:
                artel.main()

        message = str(ctx.exception)
        self.assertIn(str(self.worktree), message)
        self.assertIn(str(self.main_copy), message)
        self.assertIn("перезапуст", message.lower())
        self.assertFalse((self.worktree / ".artel").exists(),
                         "guard не должен создавать .artel/ в worktree")

    def test_main_copy_directory_is_not_refused(self):
        """Контроль: обычный каталог (`.git` — каталог, не файл) —
        поведение не меняется (требование 6 SPEC), guard не срабатывает."""
        (self.main_copy / ".git").mkdir(parents=True)

        with mock.patch.object(config, "ROOT", self.main_copy):
            try:
                artel._refuse_if_worktree()
            except SystemExit:
                self.fail("guard отказал в главной копии")

    def test_sandbox_without_dot_git_is_not_refused(self):
        """Контроль: временный каталог без `.git` вовсе (обычная тестовая
        песочница, требование 5 SPEC) — guard не срабатывает."""
        bare = self.sandbox / "bare"
        bare.mkdir()

        with mock.patch.object(config, "ROOT", bare):
            try:
                artel._refuse_if_worktree()
            except SystemExit:
                self.fail("guard отказал вне worktree и вне главной копии")


if __name__ == "__main__":
    unittest.main()
