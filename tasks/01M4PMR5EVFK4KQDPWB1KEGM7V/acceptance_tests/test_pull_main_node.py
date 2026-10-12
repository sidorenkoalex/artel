"""Команда `pull-main` и узел подтяжки: свойства, требующие закрытых имён `fsm`.

Свойства команды, наблюдаемые через публичный интерфейс, держит
долгоживущий файл задачи `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py`;
его песочница (`PullMainSandbox`) импортируется отсюда, не копируется. Здесь —
то, что по правилам `tests/` туда не ложится:

- узел `fsm._pull_main_or_escalate`, названный критериями SPEC: аргумент
  `run_plank` на пути команды (AC-4) и исходы прежних вызывателей узла
  (AC-5, AC-6, AC-13) — закрытое имя `fsm`, его вызов и подмена в `tests/`
  запрещены;
- неполученная вершина origin main (AC-6) — подмена закрытого
  `fsm._origin_main_sha`;
- «вершина main — предок новой головы ветки» (AC-4) — на настоящем git
  (`tests.sandbox.RealGitSandbox`, bare origin, артефактная ветка с планкой);
- наличие в `tests/` тестов на семь мутаций AC-15 — разбор файлов кодовой
  ветки (`_pult.CODE_ROOT`).

Группа: разовый
Красен до реализации: модуля orchestrator/pull_main.py и команды pull-main ещё нет — импорт модуля падает, у узла подтяжки нет пути команды, отличающего недоступный origin и отказ после слияния; AC-15 и прежние исходы узла (AC-5, AC-6, AC-13) зелены с рождения — они держат долгоживущий файл задачи и поведение прежних вызывателей.
"""
import ast
import contextlib
import inspect
import io
import os
import random
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402

from orchestrator import (acceptance, artel, artifact_branch, config, fsm,  # noqa: E402
                          github_adapter, gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox  # noqa: E402
from tests.test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main import (  # noqa: E402
    OLD_STAMP, PullMainSandbox, pull_main_module)

#: Состояния прежних точек подтяжки: переходы `in_dev`, `acceptance`,
#: `merge_gate`.
TRANSITION_STATES = ("in_dev", "acceptance", "merge_gate")

#: Мутации AC-15 — дословно из критерия.
AC15_MUTATIONS = (
    "команда меняет состояние задачи при успехе",
    "подтяжка пропущена по документному диффу",
    "потолок не сброшен после подтяжки",
    "команда работает вне `verifying`",
    "команда работает при занятом lease",
    "голова не отправлена в origin после подтяжки",
    "`verifying` вне набора `PULL_CONFLICT_MARKED_STATES`",
)

SPEC_WITH_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка (фикстура test_pull_main_node.py)

## Критерии приёмки

AC-1. Фикстура.
"""

PLANK_STUB = ("import unittest\n\n\nclass StubTest(unittest.TestCase):\n\n"
              "    def test_stub(self):\n        pass\n")


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("`", "")).strip().lower()


class NodeSandbox(PullMainSandbox):
    """Песочница долгоживущего файла + вызов узла прежним путём."""

    def legacy_pull(self, state: str) -> str:
        """Узел подтяжки так, как его зовут переходы автомата и `runner`:
        без признака команды `pull-main`."""
        self.set_task_state(state)
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        return fsm._pull_main_or_escalate(conn, self.TASK, t, state)

    def assert_no_pull_effects(self, text: str) -> None:
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(self.merges(), [], tag)
        self.push.assert_not_called()
        self.assertEqual(self.git_pushes(), [], tag)
        self.assertEqual(self.ceiling_resets(), [], tag)
        self.assertEqual(self.task()["updated_at"], OLD_STAMP, tag)
        self.assertNotIn(pull_main_module().PULL_MAIN_ACTION, self.actions(), tag)
        self.assertEqual(self.task()["state"], "verifying", tag)


class RunPlankTest(NodeSandbox):

    def test_ac4_command_calls_node_with_run_plank(self):
        """Команда зовёт узел подтяжки с `run_plank=True`, планка гоняется после слияния.

        Сценарий: задача в `verifying`, main ушёл вперёд без конфликта. Вызов
        `fsm._pull_main_or_escalate` подсмотрен обёрткой (исполняется
        настоящий узел): он состоялся, аргумент `run_plank` (явный или по
        умолчанию) — `True`, после `git merge` прогнана планка.

        Ловит мутацию: команда зовёт узел с `run_plank=False` (как подтяжка
        перед шагом разработчика) — планка после слияния не гоняется, и
        непроверенная голова уходит в origin.
        """
        original = fsm._pull_main_or_escalate
        spy = mock.Mock(wraps=original)
        with mock.patch.object(fsm, "_pull_main_or_escalate", spy):
            text = self.run_pull_main()
        tag = f"зерно: {self.seed}; вывод: {text!r}"
        self.assertEqual(spy.call_count, 1, tag)
        bound = inspect.signature(original).bind(*spy.call_args.args,
                                                 **spy.call_args.kwargs)
        bound.apply_defaults()
        self.assertIs(bound.arguments["run_plank"], True, tag)
        self.assertEqual(len(self.merges()), 1, tag)
        self.plank_run.assert_called()


class DocOnlyTransitionTest(NodeSandbox):

    def test_ac5_transition_pull_still_skips_doc_only_main(self):
        """Подтяжка на переходах по-прежнему пропускает документный дифф main.

        Сценарий: тот же документный дифф main, что в долгоживущем тесте
        AC-5; узел зовётся прежним путём из случайного состояния перехода —
        исход `"fresh"`, `git merge` нет, состояние прежнее.

        Ловит мутацию: пропуск по документному диффу отключён для всех
        вызывателей узла, а не только для команды — переход сливает main
        ради копилки и бэклога, исход `"pulled"`.
        """
        self.doc_only_main = True
        state = self.rng.choice(TRANSITION_STATES)
        outcome = self.legacy_pull(state)
        tag = f"зерно: {self.seed}; состояние {state}"
        self.assertEqual(outcome, "fresh", tag)
        self.assertEqual(self.merges(), [], tag)
        self.assertEqual(self.task()["state"], state, tag)


class UnavailableOriginTest(NodeSandbox):

    def test_ac6_unavailable_origin_or_behind_is_named_refusal(self):
        """Недоступная вершина origin main и `commits_behind` → `None` — отказ, не «свежо».

        Сценарий, в случайном порядке: (а) вершина origin main не получена
        (`fsm._origin_main_sha` и `gitcmd.fetch_ref_sha` не дают sha); (б)
        `rev-list --count` не отвечает — `commits_behind` даёт `None`. В
        обоих случаях вывод команды непуст и не содержит
        `PULL_MAIN_ALREADY_FRESH`; слияния, отправки, записи подтяжки и
        сброса потолка нет; задача в `verifying`.

        Ловит мутацию: команда не отличает сбой origin от свежей ветки —
        исход `Fresh()` переводится в «main уже в ветке», и Оператор
        считает ветку подтянутой, когда git не ответил.
        """
        cases = ["origin", "behind"]
        self.rng.shuffle(cases)
        fresh = pull_main_module().PULL_MAIN_ALREADY_FRESH
        for case in cases:
            with self.subTest(case=case):
                self.reset_observations()
                self.behind = None if case == "behind" else self.rng.randint(1, 9)
                with contextlib.ExitStack() as stack:
                    if case == "origin":
                        stack.enter_context(mock.patch.object(
                            fsm, "_origin_main_sha", return_value=None))
                        stack.enter_context(mock.patch.object(
                            gitcmd, "fetch_ref_sha",
                            return_value=(None, "fetch не ответил")))
                    text = self.run_pull_main()
                tag = f"зерно: {self.seed}; {case}; вывод: {text!r}"
                self.assertTrue(text.strip(), tag)
                self.assertNotIn(fresh, text, tag)
                self.assert_no_pull_effects(text)

    def test_ac6_transition_callers_still_get_fresh(self):
        """Прежние вызыватели узла получают `"fresh"`, как до задачи.

        Сценарий: узел зовётся прежним путём (без признака команды) из
        случайного состояния перехода при (а) неполученной вершине origin
        main и (б) `commits_behind` → `None` — исход `"fresh"`, задача не
        эскалирована и в прежнем состоянии.

        Ловит мутацию: прежний переход при `commits_behind` → `None`
        получает новый исход или `"escalated"` — различение включено для
        всех вызывателей, и переход `in_dev -> verifying` эскалирует задачу
        на первом же сбое git.
        """
        for case in ("origin", "behind"):
            with self.subTest(case=case):
                state = self.rng.choice(TRANSITION_STATES)
                self.behind = None if case == "behind" else self.rng.randint(1, 9)
                with contextlib.ExitStack() as stack:
                    if case == "origin":
                        stack.enter_context(mock.patch.object(
                            fsm, "_origin_main_sha", return_value=None))
                    outcome = self.legacy_pull(state)
                tag = f"зерно: {self.seed}; {case}; состояние {state}"
                self.assertEqual(outcome, "fresh", tag)
                self.assertEqual(self.task()["state"], state, tag)


class RefusedAfterMergeTransitionTest(NodeSandbox):

    def test_ac13_transition_callers_keep_refused_after_merge(self):
        """Отказ после слияния у прежних вызывателей — по-прежнему `"refused"`.

        Сценарий: SPEC требует AC-разметку, планки в источнике нет; узел
        зовётся прежним путём из случайного состояния перехода — исход
        `"refused"`, задача не эскалирована и в прежнем состоянии.

        Ловит мутацию: переход получил новый исход — эскалация «голова после
        подтяжки не проверена планкой» включена для всех вызывателей узла, и
        `in_dev -> verifying` уводит задачу в `escalated` вместо отказа.
        """
        shutil.rmtree(self.tdir / "acceptance_tests")
        state = self.rng.choice(TRANSITION_STATES)
        outcome = self.legacy_pull(state)
        tag = f"зерно: {self.seed}; состояние {state}"
        self.assertEqual(outcome, "refused", tag)
        self.assertEqual(self.task()["state"], state, tag)


class RealGitAncestorTest(RealGitSandbox):
    """Настоящий git: bare origin, ветка задачи, артефактная ветка с планкой."""

    TASK = "01M4PMR5EVFK4KQDPWB1KEGMRG"
    BRANCH = f"task/{TASK.lower()}-pull-main"

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        store.insert_task(store.db(), self.TASK, "pull-main на настоящем git",
                          "verifying", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.checkout(self.BRANCH, create=True)
        self.commit_file("orchestrator/branch_side.py", "# ветка задачи\n")
        self.add_synced_origin()

        self.checkout(config.MAIN_BRANCH)
        for i in range(rng.randint(1, 4)):
            self.commit_file(f"orchestrator/main_side_{i}.py", f"# main {i}\n")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.main_sha = self.git("rev-parse", config.MAIN_BRANCH).strip()

        self.checkout(artifact_branch.branch_name(self.TASK), create=True)
        tdir = self.root / "tasks" / self.TASK
        (tdir / "acceptance_tests").mkdir(parents=True)
        (tdir / "SPEC.md").write_text(SPEC_WITH_AC.format(task=self.TASK),
                                      encoding="utf-8")
        (tdir / "acceptance_tests" / "test_stub.py").write_text(
            PLANK_STUB, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "артефактная ветка")
        self.checkout(self.BRANCH)

        self.push = mock.Mock(return_value=(True, ""))
        for module, name, value in (
                (workspace, "ensure", lambda task_id, branch: (self.root, None)),
                (acceptance, "run", mock.Mock(return_value=(True, "1 passed"))),
                (github_adapter, "ensure_head_in_origin", self.push)):
            patcher = mock.patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def commit_file(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", rel)

    def test_ac4_main_tip_becomes_ancestor_of_branch_head(self):
        """После команды вершина main — предок новой головы ветки задачи.

        Сценарий: main ушёл вперёд на случайное число коммитов кода, без
        конфликта с веткой; планка зелёная. После `pull-main` настоящий
        `git merge-base --is-ancestor <вершина main> <ветка>` отвечает «да»,
        задача в `verifying`.

        Ловит мутацию: команда сливает в ветку не вершину origin main, а
        локальный `main` пульта или прежнюю базу ветки (либо не сливает
        вовсе, ответив «main уже в ветке») — вершина main не входит в
        историю ветки.
        """
        env = {"HOME": str(self.root / ".artel" / "operator-home"),
               "PATH": os.environ.get("PATH", ""),
               "ARTEL_SESSION_ID": f"operator-{self.seed:x}"}
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", "pull-main", self.TASK]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                out.write(f"\n{exc.code}")
        tag = f"зерно: {self.seed}; вывод: {out.getvalue()!r}"
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", self.main_sha, self.BRANCH],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, tag)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "verifying", tag)


class MutationTestsPresentTest(unittest.TestCase):

    def test_ac15_tests_dir_names_each_of_seven_mutations(self):
        """В `tests/` на каждую из семи мутаций AC-15 есть тест с заявкой о ней.

        Сценарий: разбираются все `tests/test_*.py` кодовой ветки; у каждого
        тестового метода берётся текст докстринга после «Ловит мутацию»
        (обратные кавычки и переносы строк не различаются). Каждая из семи
        мутаций критерия находится в заявке хотя бы одного метода.

        Ловит мутацию: долгоживущий тест на одну из мутаций удалён из
        `tests/` или его заявка перестала называть свою мутацию — фраза
        мутации не находится ни в одной заявке.
        """
        claims = []
        for path in sorted((Path(CODE_ROOT) / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name.startswith("test")):
                    doc = normalized(ast.get_docstring(node) or "")
                    marker = "ловит мутацию"
                    if marker in doc:
                        claims.append(doc[doc.index(marker):])
        for mutation in AC15_MUTATIONS:
            with self.subTest(mutation=mutation):
                self.assertTrue(any(normalized(mutation) in c for c in claims),
                                f"нет заявки «Ловит мутацию» о мутации {mutation!r}")


if __name__ == "__main__":
    unittest.main()
