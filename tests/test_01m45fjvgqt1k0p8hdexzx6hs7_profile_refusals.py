"""Проверки тестов без профиля или без контекста проекта — отказ, а не
отключение (ADR-0021 пп. 8-9, ADR-0002 fail-closed).

Группа: долгоживущий

Песочница — `tests.sandbox.LightTransitionSandbox`: задача артели, её
документы на диске (SPEC с одним критерием, планка из одного разового
файла, PLAN `ready`), `targets.yaml` пишет сам сценарий. Рабочую копию
задачи отдаёт подменённый `workspace.ensure`; `subprocess.run` подменён
поверх шпиона песочницы: pytest не исполняется (успех, вызов и его `cwd`
запоминаются), `gh`/`claude` отвечают отказом, остальное — шпиону. Паузы
пульта (`tests.sandbox.patch_pult_sleep`) поднимают исключение-метку:
`approve`, дошедший до ожидания CI, считается прошедшим проверки.

Наблюдаемое — исход команды: состояние задачи, новые записи журнала,
печать и текст `SystemExit` вместе. Вариант порчи профиля, название
задачи и внешнего проекта выбираются случайно; зерно печатается и входит
в текст провала.

Красен до реализации: профиль тестов нигде не читается — задача артели
без `test_profile` проходит `tests_writing -> in_dev` и `in_dev ->
verifying`, `approve` гейта мержа доходит до ожидания CI, пакет ревью
собирается; задача с неразрешённым контекстом проходит переходы, а отказ
`approve` не называет «контекст проекта … не разрешён»; без рабочей копии
задачи артели сухой сбор и прогон приёмки идут с `cwd` = `config.ROOT`.

Зелены уже сегодня два метода неразрешённого контекста, где отказ
приходит раньше гейтов таблицы — на чтении документов из ссылки, чей
репозиторий без контекста не находится: `test_ac9_in_dev_exit_*` и
`test_ac9_acceptance_autogate_*`. Они держат, что этот путь и после
перевода не пропускает переход и не прогоняет планку.

Планка провалидирована временным стабом реализации (удалён, не
закоммичен): разбор `test_profile` в `targets.check`, ответ профиля в
`repo_context`, гейты неослабления/заявки мутации/групп/долгоживущих
файлов/лока и перечня/прогона/`amend-tests` по профилю, отказ артели без
профиля и неразрешённого контекста, прогон только в рабочей копии задачи.
Под ним зелены все методы файла.
"""
import contextlib
import io
import random
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config, fsm, gates, review, store, workspace
from tests.sandbox import LightTransitionSandbox, patch_pult_sleep

SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: профиль тестов проекта (сценарий)

## Критерии приёмки

AC-1. Единственный критерий сценария.
"""

PLANK = '''"""Зелёный с рождения: фикстура сценария профиля тестов.

Группа: разовый
"""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_only(self):
        """Фикстурный критерий.

        Ловит мутацию: фикстура, исполнением не проверяется.
        """
        self.assertTrue(True)
'''

ARTEL_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
{profile}"""

# Профиль, который не разбирается: по одному дефекту на вариант.
BROKEN_PROFILES = (
    ARTEL_PROFILE.replace("      report: junit-xml\n", "      report: tap\n"),
    ARTEL_PROFILE.replace("      command: [python3, -m, pytest]\n", ""),
    ARTEL_PROFILE.replace("test_<id>_<name>.py", "test_<name>.py"),
    ARTEL_PROFILE + "      runner: tox\n",
)

UNREADABLE_FILES = ("targets: [artel\n", "targets:\n", "", None)


class ProfileGateFinished(Exception):
    """Пауза пульта: `approve` прошёл проверки и ждёт CI."""


def stop_at_pause(*_args) -> None:
    raise ProfileGateFinished()


class RefusalSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.wt_path.mkdir(parents=True, exist_ok=True)
        self.ensure_result = (self.wt_path, None)
        ensure_patcher = mock.patch.object(
            workspace, "ensure", lambda *a, **k: self.ensure_result)
        ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)
        self.pytest_calls: list = []
        run_patcher = mock.patch.object(subprocess, "run", self.fake_run)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(SPEC.format(task=self.TASK),
                                           encoding="utf-8")
        plank_dir = self.tdir / "acceptance_tests"
        plank_dir.mkdir(parents=True, exist_ok=True)
        (plank_dir / "test_ac.py").write_text(PLANK, encoding="utf-8")
        self.write_plan_ready()

    def fake_run(self, cmd, *args, **kwargs):
        words = [str(part) for part in cmd]
        if any("pytest" in word for word in words):
            self.pytest_calls.append((words, kwargs.get("cwd")))
            return subprocess.CompletedProcess(
                words, 0, "1 test collected\n1 passed\n", "")
        if words and Path(words[0]).name in ("gh", "claude"):
            return subprocess.CompletedProcess(words, 1, "", "нет в песочнице")
        return self.git_spy(cmd, *args, **kwargs)

    # ----------------------------------------------------------- targets

    def write_targets(self, entries: dict) -> None:
        """entries: имя проекта -> текст блока `test_profile` ("" — поля нет)."""
        text = "targets:\n" + "".join(
            ENTRY.format(name=name, base=config.MAIN_BRANCH, profile=profile)
            for name, profile in entries.items())
        config.TARGETS.write_text(text, encoding="utf-8")

    def write_raw_targets(self, text) -> None:
        if text is None:
            config.TARGETS.unlink(missing_ok=True)
        else:
            config.TARGETS.write_text(text, encoding="utf-8")

    def artel_without_profile_variants(self) -> list:
        """(название варианта, действие над targets.yaml) — нет поля,
        профиль не разбирается, файл не читается; порча и файл —
        случайные из перечней."""
        broken = self.rng.choice(BROKEN_PROFILES)
        unreadable = self.rng.choice(UNREADABLE_FILES)
        return [
            ("нет поля", lambda: self.write_targets(
                {config.DEFAULT_TARGET: ""})),
            ("профиль не разбирается", lambda: self.write_targets(
                {config.DEFAULT_TARGET: broken})),
            ("targets.yaml не читается",
             lambda: self.write_raw_targets(unreadable)),
        ]

    # ----------------------------------------------------------- task row

    def set_row(self, **fields) -> None:
        conn = store.db()
        for key, value in fields.items():
            conn.execute(f"UPDATE tasks SET {key}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    # ----------------------------------------------------------- commands

    def outcome(self, fn, *args) -> tuple:
        """(текст исхода, дошла ли команда до паузы пульта): печать, текст
        `SystemExit` и новые записи журнала одной строкой."""
        before = len(store.task_steps(store.db(), self.TASK))
        buf = io.StringIO()
        exit_text = ""
        finished = False
        with contextlib.redirect_stdout(buf), patch_pult_sleep(stop_at_pause):
            try:
                fn(*args)
            except SystemExit as exc:
                exit_text = str(exc.code or "")
            except ProfileGateFinished:
                finished = True
        rows = store.task_steps(store.db(), self.TASK)[before:]
        journal = "\n".join(f"{r['action']}: {r['detail'] or ''}" for r in rows)
        return f"{buf.getvalue()}\n{exit_text}\n{journal}", finished

    def advance_from(self, state: str) -> str:
        self.set_state(state)
        text, _finished = self.outcome(fsm.cmd_advance, self.TASK)
        return text

    def approve_merge(self) -> tuple:
        self.set_state("merge_gate")
        return self.outcome(fsm.cmd_approve, self.TASK)

    def assert_names_targets_and_field(self, text: str, variant: str) -> None:
        self.assertIn("targets.yaml", text,
                      f"зерно {self.seed}, вариант «{variant}»: {text}")
        self.assertIn("test_profile", text,
                      f"зерно {self.seed}, вариант «{variant}»: {text}")

    def assert_context_unresolved(self, text: str) -> None:
        self.assertRegex(text, r"контекст проекта[^\n]*не разрешён",
                         f"зерно {self.seed}: {text}")


class ArtelWithoutProfileTest(RefusalSandbox):

    def test_ac4_tests_writing_exit_refused_naming_targets_and_field(self):
        """Задача артели без профиля (нет поля, профиль не разбирается,
        `targets.yaml` не читается) на выходе из `tests_writing` — отказ с
        причиной, называющей `targets.yaml` и поле; задача остаётся в
        `tests_writing`, сухой сбор не исполнялся.

        Ловит мутацию: без профиля артели проверки строк группы и
        долгоживущих файлов молча отключаются, как у внешнего проекта, —
        задача уходит в `in_dev`.
        """
        for variant, prepare in self.artel_without_profile_variants():
            with self.subTest(seed=self.seed, variant=variant):
                prepare()
                self.pytest_calls.clear()
                text = self.advance_from("tests_writing")
                self.assertEqual(self.state(), "tests_writing",
                                 f"зерно {self.seed}, «{variant}»: {text}")
                self.assert_names_targets_and_field(text, variant)

    def test_ac4_in_dev_exit_refused_naming_targets_and_field(self):
        """Задача артели без профиля на переходе `in_dev -> verifying` —
        отказ с причиной про `targets.yaml` и поле; задача остаётся в
        `in_dev`.

        Ловит мутацию: гейт неослабления или заявки мутации без профиля
        возвращает «нет отказа» (fail-open) — задача уходит в `verifying`.
        """
        for variant, prepare in self.artel_without_profile_variants():
            with self.subTest(seed=self.seed, variant=variant):
                prepare()
                text = self.advance_from("in_dev")
                self.assertEqual(self.state(), "in_dev",
                                 f"зерно {self.seed}, «{variant}»: {text}")
                self.assert_names_targets_and_field(text, variant)

    def test_ac4_merge_approve_refused_before_ci_wait(self):
        """Задача артели без профиля на `approve` гейта мержа — отказ с
        причиной про `targets.yaml` и поле до ожидания CI; задача не
        уходит в `done`.

        Ловит мутацию: шаг неослабления или сверка лока и перечня на гейте
        мержа без профиля пропускается — `approve` доходит до ожидания CI
        ветки.
        """
        for variant, prepare in self.artel_without_profile_variants():
            with self.subTest(seed=self.seed, variant=variant):
                prepare()
                text, finished = self.approve_merge()
                self.assertFalse(finished,
                                 f"зерно {self.seed}, «{variant}»: approve "
                                 f"дошёл до ожидания CI: {text}")
                self.assertNotEqual(self.state(), "done")
                self.assert_names_targets_and_field(text, variant)

    def test_ac4_review_package_not_built(self):
        """Пакет ревью задачи артели без профиля не собирается: сборка
        отказывает с причиной про `targets.yaml` и поле (исключение или
        `SystemExit`) либо ничего не возвращает.

        Ловит мутацию: раздел изменённых утверждений без профиля молча
        выпадает, а пакет собирается как обычно — ревьювер получает пакет
        без наблюдения неослабления.
        """
        for variant, prepare in self.artel_without_profile_variants():
            with self.subTest(seed=self.seed, variant=variant):
                prepare()
                package = None
                reason = ""
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        package = review.review_package(
                            store.db(), self.TASK, self.TASK_TITLE,
                            self.branch)
                except SystemExit as exc:
                    reason = str(exc.code or "")
                except Exception as exc:  # noqa: BLE001 — отказ сборки
                    reason = str(exc)
                self.assertFalse(package, f"зерно {self.seed}, «{variant}»: "
                                          f"пакет собран")
                if reason:
                    self.assert_names_targets_and_field(reason, variant)


class UnresolvedContextTest(RefusalSandbox):

    def setUp(self):
        super().setUp()
        self.write_targets({config.DEFAULT_TARGET: ARTEL_PROFILE})
        self.ghost = self.rng.choice(["ghost", "nevedomy", "pustota"])
        self.set_row(target=self.ghost)

    def test_ac9_tests_writing_exit_refused_context_unresolved(self):
        """Задача проекта, которого нет в `targets.yaml`, на выходе из
        `tests_writing` — отказ «контекст проекта … не разрешён», задача
        остаётся в `tests_writing`.

        Ловит мутацию: неразрешённый контекст читается как «нет профиля»
        — проверки пропускаются с записью в журнал, задача уходит в
        `in_dev`.
        """
        text = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "tests_writing",
                         f"зерно {self.seed}: {text}")
        self.assert_context_unresolved(text)

    def test_ac9_in_dev_exit_refused_context_unresolved(self):
        """Та же задача на переходе `in_dev -> verifying` — отказ, задача
        остаётся в `in_dev`.

        PLAN этого перехода читается из ссылки документов, а её
        репозиторий у проекта с неразрешённым контекстом не находится
        (`artifact_branch.repo_for_target`): отказ может прийти уже на
        чтении PLAN, раньше гейтов таблицы, — тогда он называет
        непрочитанную ветку, а не контекст. Метод держит, что ни одним
        путём переход не проходит молча.

        Ловит мутацию: `repo_context.resolve` вернул `None`, а чтение PLAN
        откатывается на диск и гейты неослабления и заявки мутации
        возвращают «нет отказа» — задача уходит в `verifying`.
        """
        text = self.advance_from("in_dev")
        self.assertEqual(self.state(), "in_dev", f"зерно {self.seed}: {text}")
        self.assertRegex(
            text, r"контекст проекта[^\n]*не разрешён|переход отклонён[^\n]*"
                  r"не прочитан", f"зерно {self.seed}: {text}")

    def test_ac9_merge_approve_refused_context_unresolved(self):
        """Та же задача на `approve` гейта мержа — отказ «контекст проекта
        … не разрешён» без ожидания CI, задача не в `done`.

        Ловит мутацию: отказ `approve` остаётся прежним текстом «контекст
        target'а не читается» — причина не называет неразрешённый контекст
        проекта.
        """
        text, finished = self.approve_merge()
        self.assertFalse(finished, f"зерно {self.seed}: {text}")
        self.assertNotEqual(self.state(), "done")
        self.assert_context_unresolved(text)

    def test_ac9_acceptance_autogate_not_run_context_unresolved(self):
        """Та же задача с вердиктом ревью `approved` и автоматической
        политикой гейта приёмки — автогейт не проводится (планка не
        прогоняется), в журнале есть запись об отказе.

        Ссылка документов проекта с неразрешённым контекстом не читается
        (`artifact_branch.repo_for_target`), поэтому отказ приходит уже на
        чтении вердикта — раньше автогейта; метод держит, что ни на одном
        шаге этой цепочки планка не прогоняется.

        Ловит мутацию: чтение вердикта или автогейт при неразрешённом
        контексте откатывается на главную копию / команду пульта — планка
        прогоняется (в шпионе появляется вызов pytest), записи отказа нет.
        """
        (self.tdir / "REVIEW.md").write_text(
            f"---\ntask: {self.TASK}\ntype: review\nauthor_role: reviewer\n"
            f"status: approved\niteration: 1\nschema_version: 2\n---\n\n"
            f"# REVIEW\n", encoding="utf-8")
        with mock.patch.object(fsm, "guard_refuses", return_value=False), \
                mock.patch.object(gates, "policy", return_value=gates.AUTO):
            text = self.advance_from("review")
        self.assertEqual(self.pytest_calls, [], f"зерно {self.seed}: {text}")
        self.assertNotIn(self.state(), ("merge_gate", "done"))
        self.assertRegex(text, r"переход отклонён|контекст проекта[^\n]*не разрешён",
                         f"зерно {self.seed}: {text}")


class ArtelWithoutWorkCopyTest(RefusalSandbox):

    def setUp(self):
        super().setUp()
        self.write_targets({config.DEFAULT_TARGET: ARTEL_PROFILE})
        reason = self.rng.choice(["fetch не удался", "каталог занят",
                                  "клон не заведён"])
        self.ensure_result = (None, f"рабочая копия не заведена: {reason}")

    def assert_not_run_in_root(self, text: str) -> None:
        in_root = [words for words, cwd in self.pytest_calls
                   if cwd is not None and Path(cwd) == config.ROOT]
        self.assertEqual(in_root, [], f"зерно {self.seed}: pytest с cwd = "
                                      f"config.ROOT; исход: {text}")

    def test_ac11_tests_writing_exit_refused_without_work_copy(self):
        """Задача артели с профилем, рабочую копию которой завести не
        вышло, на выходе из `tests_writing` — отказ, задача остаётся в
        `tests_writing`, сухой сбор с `cwd` = `config.ROOT` не исполнялся.

        Ловит мутацию: прежняя ветка «не на ветке задачи — каталог
        документов и главная копия» оставлена для артели — сухой сбор идёт
        в `config.ROOT`, задача уходит в `in_dev`.
        """
        text = self.advance_from("tests_writing")
        self.assertEqual(self.state(), "tests_writing",
                         f"зерно {self.seed}: {text}")
        self.assertIn("переход отклонён", text)
        self.assert_not_run_in_root(text)

    def test_ac11_acceptance_run_refused_without_work_copy(self):
        """Та же задача на `in_dev -> verifying` — прогон приёмки отклоняет
        переход, задача остаётся в `in_dev`, pytest с `cwd` =
        `config.ROOT` не исполнялся.

        Ловит мутацию: прогон приёмки артели без рабочей копии на ветке
        идёт в главной копии пульта (`run_cwd = config.ROOT`) — задача
        уходит в `verifying`.
        """
        text = self.advance_from("in_dev")
        self.assertEqual(self.state(), "in_dev", f"зерно {self.seed}: {text}")
        self.assertIn("переход отклонён", text)
        self.assert_not_run_in_root(text)


if __name__ == "__main__":
    unittest.main()
