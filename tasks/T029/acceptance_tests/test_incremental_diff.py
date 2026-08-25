"""Приёмочные тесты T029 — инкрементальный diff ревью поздних итераций.

Источник — только tasks/T029/SPEC.md, раздел «Критерии приёмки» (AC-1..AC-9).

Реального CLI здесь нет, но реальный git — есть: предмет проверки (что
именно попадает в ревью-пакет при iteration > 1) — это содержимое git diff
между конкретными коммитами, а подделать его заглушкой `gitcmd.git`
означало бы утверждать формат вызова, который SPEC не называет (только
результат — «diff от sha предыдущего вердикта до HEAD»). Песочница —
тот же приём, что у `RealPultGitTest` (tests/test_git_fixation.py, T021)
и `BriefSandboxTest` (tasks/T028/acceptance_tests/test_brief.py): временный
каталог сам является git-репозиторием пульта (config.ROOT), `subprocess.Popen`
подменён так, что настоящий git идёт как есть, а команда `claude` —
заглушкой (агент не пишет артефакты сам — REVIEW.md для следующей итерации
тест дописывает от его имени, как это делает реальный ревьювер).

FSM двигается ПО-НАСТОЯЩЕМУ (`fsm.cmd_advance`/`cmd_approve`), а не прыжком
состояния в обход перехода: sha «предыдущего вердикта» в T029 — это именно
sha, который `_record_fixation` (T021) зафиксировал НА переходе
`review -> in_dev` по вердикту `changes_requested`, и только реальный проход
через этот переход даёт настоящее, а не придуманное значение sha для
сверки diff'а.

Различить «взяли из журнала fixation» (AC-3) и «взяли из живого fixed_sha»
можно только если эти два значения к моменту второго прогона ревьювера уже
разные: переход `in_dev -> review` для итерации 2 фиксирует НОВЫЙ sha
(текущий HEAD, после правки разработчика), поэтому `tasks.fixed_sha`
к моменту сборки пакета указывает уже на итерацию 2, а не на sha, на
котором был вынесен вердикт итерации 1. Тесты AC-2/AC-3 держат оба
значения и проверяют, что diff собран именно от исторического значения
из журнала, а не от текущего fixed_sha (иначе diff инкрементальной
итерации был бы пуст — sha совпал бы с HEAD).
"""
import contextlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, fsm, runner, store  # noqa: E402

SPEC_READY = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: инкрементальный diff

## Контекст

Маркер-SPEC-T029-приёмка.

## Требования

## Критерии приёмки

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: инкрементальный diff

## Подход

Маркер-PLAN-T029-приёмка.

## Шаги

## Покрытие требований

## Влияние на систему
"""

REVIEW_ITER1_CHANGES_REQUESTED = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 1
---

# REVIEW: инкрементальный diff

## Соответствие SPEC

## Замечания

Маркер-REVIEW-T029-итерация-1.

## Вердикт

changes_requested — доработать.
"""

# Форма вердикта (templates/REVIEW.md) — маркер её присутствия в пакете.
FORM_MARKER = "severity (blocker/major/minor)"


class FakeStream:
    """Пайп процесса-агента: отдаёт заготовленные строки."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        pass


class FakeProc:
    """Процесс-агент: отдаёт заготовленные строки, wait() — сразу rc."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class IncrementalReviewPackageTest(unittest.TestCase):
    """Песочница: ROOT пульта — настоящий git-репозиторий, ветка задачи
    создаётся и коммитится по-настоящему, FSM двигается через
    `fsm.cmd_advance`/`cmd_approve`."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude")):
            self.patches.enter_context(mock.patch.object(config, attr, value))
        self.patches.enter_context(mock.patch.object(
            runner.keychain, "token", lambda slot: "tok-test"))
        self.patches.enter_context(mock.patch(
            "orchestrator.doctor.preflight_checks", lambda role, target: []))

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Инкрементальный diff")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        self.git("checkout", "-q", "-b", self.branch)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, *paths: str, message: str = "wip") -> None:
        self.git("add", *paths)
        self.git("commit", "-q", "-m", message)

    def task_steps(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def package_notes(self) -> list:
        """Detail всех записей журнала «ревью-пакет собран», по порядку."""
        return [s["detail"] for s in self.task_steps()
               if s["action"] == "ревью-пакет собран"]

    def last_fixed_sha(self) -> str:
        """Sha из последней записи журнала «sha зафиксирован» (T021)."""
        entries = [s["detail"] for s in self.task_steps()
                  if s["action"] == "sha зафиксирован"]
        self.assertTrue(entries, "нет ни одной записи «sha зафиксирован»")
        match = re.search(r"sha=([0-9a-f]{4,40})", entries[-1])
        self.assertIsNotNone(match, entries[-1])
        return match.group(1)

    def run_reviewer(self) -> str:
        """Прогон шага ревьювера: настоящий git, заглушка только для `claude`."""
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return FakeProc(["готово\n"])
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner.subprocess, "Popen",
                               side_effect=side_effect) as popen:
            self.capture(runner.cmd_run, self.TASK)

        calls = [c for c in popen.call_args_list
                if c.args and c.args[0] and c.args[0][0] == "claude"]
        self.assertEqual(len(calls), 1, "ожидался ровно один запуск ревьювера")
        return Path(calls[-1].kwargs["stdin"].name).read_text(encoding="utf-8")

    # ------------------------------------------------------- сценарий FSM

    def enter_spec_gate(self) -> str:
        self.write(f"tasks/{self.TASK}/SPEC.md", SPEC_READY.format(task=self.TASK))
        self.commit(f"tasks/{self.TASK}", message="SPEC ready")
        self.capture(fsm.cmd_advance, self.TASK)
        return self.head()

    def enter_in_dev(self) -> None:
        sha = self.enter_spec_gate()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(self.state(), "in_dev")

    def enter_review_iteration1(self, original_content: str | None = None) -> None:
        """in_dev -> review: первый проход разработчика, первый вход ревьювера."""
        self.enter_in_dev()
        if original_content is None:
            original_content = "ORIGINAL_MARKER_0 = True\n"
        self.write("feature/original.py", original_content)
        self.write(f"tasks/{self.TASK}/PLAN.md", PLAN_READY.format(task=self.TASK))
        self.commit("feature", f"tasks/{self.TASK}", message="дев итерация 1")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "review")

    def enter_review_iteration2(self, fix_content: str | None = None
                                ) -> tuple[str, str]:
        """review(1) -> вердикт changes_requested -> in_dev -> review(2).

        Возвращает (prompt итерации 1, sha предыдущего вердикта из журнала).
        """
        self.enter_review_iteration1()
        prompt1 = self.run_reviewer()

        self.write(f"tasks/{self.TASK}/REVIEW.md",
                  REVIEW_ITER1_CHANGES_REQUESTED.format(task=self.TASK))
        self.commit(f"tasks/{self.TASK}", message="ревью итерация 1: доработать")
        self.capture(fsm.cmd_advance, self.TASK)  # review -> in_dev
        self.assertEqual(self.state(), "in_dev")

        prev_sha = self.last_fixed_sha()
        self.assertEqual(
            prev_sha, self.head(),
            "sha-фикстура теста: журнал должен зафиксировать HEAD ровно на "
            "коммите с вердиктом итерации 1")

        if fix_content is None:
            fix_content = "FIX_MARKER_0 = True\n"
        self.write("feature/fix.py", fix_content)
        self.commit("feature", message="дев итерация 2: правка по замечанию")
        self.capture(fsm.cmd_advance, self.TASK)  # in_dev -> review
        self.assertEqual(self.state(), "review")

        return prompt1, prev_sha


# --------------------------------------------------------------------------
# AC-1: iteration == 1 — полный diff, без изменений в составе/потолках.

class Ac1FullDiffAtFirstIterationTest(IncrementalReviewPackageTest):

    def test_ac1_iteration_one_uses_the_full_branch_diff_unchanged(self):
        self.enter_review_iteration1()

        prompt = self.run_reviewer()

        full_diff = self.git(
            "diff", f"{config.MAIN_BRANCH}...{self.branch}").strip()
        self.assertIn(full_diff, prompt,
                      "при iteration == 1 в пакете должен быть diff main...branch")
        self.assertIn("+ORIGINAL_MARKER_0 = True", prompt)

        note = self.package_notes()[-1]
        self.assertIn("полный", note,
                      "запись журнала не называет тип diff «полный» (требование 7)")
        self.assertRegex(
            note, r"итерац\w*\D{0,4}1\b",
            "запись журнала не называет номер итерации 1 (требование 8)")


# --------------------------------------------------------------------------
# AC-2..AC-9: iteration > 1.

class IncrementalDiffTest(IncrementalReviewPackageTest):

    def test_ac2_iteration_gt1_diffs_from_previous_verdict_sha_to_head(self):
        prompt1, prev_sha = self.enter_review_iteration2()

        prompt2 = self.run_reviewer()

        expected = self.git("diff", f"{prev_sha}...{self.branch}").strip()
        self.assertIn(
            expected, prompt2,
            "diff пакета не совпадает с git diff от sha предыдущего "
            "вердикта до HEAD ветки задачи")
        self.assertNotIn(
            "+ORIGINAL_MARKER_0 = True", prompt2,
            "в пакете инкрементальной итерации показан diff от main, а не "
            "от sha предыдущего вердикта — изменение, известное ревьюверу "
            "по прошлой итерации, показано заново")
        self.assertIn("+FIX_MARKER_0 = True", prompt2)

    def test_ac3_previous_verdict_sha_is_taken_from_the_fixation_journal(self):
        prompt1, prev_sha = self.enter_review_iteration2()
        live_fixed_sha = store.get_task(store.db(), self.TASK)["fixed_sha"]
        self.assertNotEqual(
            live_fixed_sha, prev_sha,
            "sha-фикстура теста не различает текущий fixed_sha и sha "
            "прошлого вердикта — переход in_dev -> review должен был "
            "зафиксировать новый (более поздний) sha")
        self.assertEqual(
            live_fixed_sha, self.head(),
            "sha-фикстура теста: текущий fixed_sha должен совпадать с HEAD "
            "на момент повторного входа в review")

        prompt2 = self.run_reviewer()

        expected = self.git("diff", f"{prev_sha}...{self.branch}").strip()
        self.assertIn(
            expected, prompt2,
            "diff пакета не соответствует sha, зафиксированному журналом "
            "hash-фиксации (T021) на переходе вердикта прошлой итерации — "
            "похоже, sha взят не из журнала (например, из текущего "
            "tasks.fixed_sha, который к этому моменту уже указывает на "
            "текущую итерацию, а не на прошлый вердикт)")
        # Различающая часть проверки: diff от main...branch (или от текущего
        # fixed_sha, который к этому моменту равен HEAD) содержал бы
        # ORIGINAL_MARKER_0 как добавленную строку — без него `assertIn`
        # выше проходит и на диффе main...branch (та же самая полная
        # правка среди прочего включает и файл fix.py), поэтому сам по
        # себе не доказывает, что источником взят именно журнал.
        self.assertNotIn(
            "+ORIGINAL_MARKER_0 = True", prompt2,
            "diff пакета шире, чем от sha предыдущего вердикта: похоже, "
            "sha для сравнения взят не из журнала hash-фиксации")

    def test_ac4_spec_plan_previous_review_and_verdict_form_are_present(self):
        prompt1, prev_sha = self.enter_review_iteration2()

        prompt2 = self.run_reviewer()

        self.assertIn(f"tasks/{self.TASK}/SPEC.md", prompt2)
        self.assertIn("Маркер-SPEC-T029-приёмка.", prompt2, "тело SPEC.md")
        self.assertIn(f"tasks/{self.TASK}/PLAN.md", prompt2)
        self.assertIn("Маркер-PLAN-T029-приёмка.", prompt2, "тело PLAN.md")
        self.assertIn(f"tasks/{self.TASK}/REVIEW.md", prompt2)
        self.assertIn("Маркер-REVIEW-T029-итерация-1.", prompt2,
                      "тело прошлого REVIEW.md (итерация 1)")
        self.assertIn("templates/REVIEW.md", prompt2)
        self.assertIn(FORM_MARKER, prompt2, "тело формы вердикта")

    def test_ac5_package_names_the_git_command_for_the_full_diff(self):
        prompt1, prev_sha = self.enter_review_iteration2()

        prompt2 = self.run_reviewer()

        self.assertIn(
            f"git diff {config.MAIN_BRANCH}...{self.branch}", prompt2,
            "пакет не называет ревьюверу git-команду для просмотра полного "
            "diff ветки (требование 5)")

    def test_ac6_diff_line_cap_applies_to_the_incremental_diff(self):
        many_lines = "\n".join(
            f"FIX_MARKER_{i} = True" for i in range(
                config.REVIEW_DIFF_MAX_LINES + 500)) + "\n"
        prompt1, prev_sha = self.enter_review_iteration2(fix_content=many_lines)

        prompt2 = self.run_reviewer()

        self.assertIn(
            "[diff усечён", prompt2,
            "потолок REVIEW_DIFF_MAX_LINES не применён к инкрементальному diff")
        note = self.package_notes()[-1]
        self.assertIn("diff усечён", note)

    def test_ac7_package_byte_cap_applies_to_the_incremental_package(self):
        # Мало строк (потолок строк не сработает), но каждая — очень длинная,
        # так что байтовый потолок пакета срабатывает первым (тот же приём,
        # что tests/test_review_package.py,
        # test_long_lines_are_cut_even_though_the_line_cap_passes).
        long_lines = "\n".join(
            "FIX" + "z" * 50_000 + str(i) for i in range(10)) + "\n"
        prompt1, prev_sha = self.enter_review_iteration2(fix_content=long_lines)

        prompt2 = self.run_reviewer()

        self.assertIn(
            "[пакет усечён", prompt2,
            "потолок REVIEW_PACKAGE_MAX_BYTES не применён к пакету с "
            "инкрементальным diff")
        note = self.package_notes()[-1]
        self.assertIn("пакет усечён", note)

    def test_ac8_journal_step_names_the_diff_type(self):
        prompt1, prev_sha = self.enter_review_iteration2()
        note_iteration1 = self.package_notes()[0]

        self.run_reviewer()
        note_iteration2 = self.package_notes()[-1]

        self.assertIn(
            "полный", note_iteration1,
            "запись журнала итерации 1 не называет тип diff «полный»")
        self.assertIn(
            "инкрементальный", note_iteration2,
            "запись журнала итерации 2 не называет тип diff «инкрементальный»")

    def test_ac9_journal_step_names_the_review_iteration(self):
        prompt1, prev_sha = self.enter_review_iteration2()
        note_iteration1 = self.package_notes()[0]

        self.run_reviewer()
        note_iteration2 = self.package_notes()[-1]

        self.assertRegex(
            note_iteration1, r"итерац\w*\D{0,4}1\b",
            "запись журнала итерации 1 не называет номер итерации")
        self.assertRegex(
            note_iteration2, r"итерац\w*\D{0,4}2\b",
            "запись журнала итерации 2 не называет номер итерации")


if __name__ == "__main__":
    unittest.main()
