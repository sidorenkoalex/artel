"""Обязательный артефакт шага роли: долгоживущий файл засчитывается test_author.

Группа: долгоживущий
Красен до реализации: AC-1 и AC-4 — проверка обязательного артефакта шага test_author смотрит только в каталог приёмочных тестов задачи, поэтому шаг с одним долгоживущим файлом получает отказ «без артефакта», а текст отказа не называет долгоживущую форму; AC-2/AC-3/AC-5 держат уже существующее поведение и зелены.

Шаг гоняется целиком через публичный `runner.run_agent_once` в песочнице
с настоящим git (`tests.sandbox.RealGitSandbox` + синхронный origin):
рабочий каталог роли — настоящий worktree задачи, который заводит сам
пульт (`workspace.ensure`), и признак «файл новый относительно базы
ветки» вычисляется по живому git, а не по заглушке. Подставной агент
(`runner.spawn_agent`) пишет файлы сценария в тот `cwd`, который пульт ему
передал, — ровно как роль пишет инструментом Write, — и завершается rc=0.
Идентификаторы задач и имена файлов порождаются `random` при каждом
запуске; зерно печатается и входит в текст каждого провала.
"""
import random
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artifact_branch, config, keychain, runner, stack, store
from scripts import guard
from tests.sandbox import FakeProc, RealGitSandbox

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
MISSING = "шаг завершён без артефакта"
RESULT_LINE = '{"type": "result", "total_cost_usd": 0.001}\n'


def random_task_id(rng: random.Random) -> str:
    """Идентификатор формы ULID (26 знаков алфавита Крокфорда)."""
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def random_name(rng: random.Random) -> str:
    """Имя `<имя>` долгоживущего файла из `[a-z0-9_]`, начинается с буквы."""
    tail = "".join(rng.choice(NAME_ALPHABET + "_")
                   for _ in range(rng.randint(0, 10)))
    return rng.choice("abcdefghijklmnopqrstuvwxyz") + tail


class RequiredArtifactStepSandbox(RealGitSandbox):
    """Задача самой артели в нужном состоянии, worktree заводит пульт."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        # Карта ролей и слой моделей — фикстурой песочницы, не файлы
        # репозитория; согласованность стека (venv, CLI) — не предмет теста.
        self.use_role_map()
        stack_ok = [stack.StackCheck(name, "ok", "песочница")
                    for name in ("python", "git", "gh", "claude", "venv")]
        for patcher in (
                mock.patch.object(stack, "check_stack", lambda: list(stack_ok)),
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda role, target: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()

    def new_task(self, state: str) -> str:
        task_id = random_task_id(self.rng)
        store.insert_task(self.conn, task_id, "Задача", state,
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def run_step(self, task_id: str, role: str, files: list) -> tuple:
        """Шаг роли: подставной агент пишет `files` (пути от своего `cwd`;
        документы `tasks/<id>/…` — от корня выкладки документов, куда их
        пишет роль с ADR-0021, этап 1) и выходит rc=0; возврат — `(исход,
        пояснение)` `run_agent_once`."""
        seen_cwd = []
        docs_root = artifact_branch.docs_root(config.DEFAULT_TARGET)

        def fake_agent(cmd, **kwargs):
            cwd = Path(kwargs["cwd"])
            seen_cwd.append(cwd)
            for rel in files:
                base = docs_root if Path(rel).parts[0] == "tasks" else cwd
                dest = base / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text("import unittest\n", encoding="utf-8")
            return FakeProc([RESULT_LINE], 0)

        with mock.patch.object(runner, "spawn_agent", side_effect=fake_agent):
            outcome, reason, _cls = runner.run_agent_once(
                self.conn, task_id, role, "промпт шага", 1)
        self.assertEqual(len(seen_cwd), 1,
                         f"зерно {self.seed}: агент не запущен ровно раз "
                         f"({outcome}: {reason})")
        return outcome, reason

    def assert_accepted(self, outcome: str, reason: str, context: str) -> None:
        self.assertEqual(outcome, "ok",
                         f"зерно {self.seed}: {context} — шаг не сдан: {reason}")
        self.assertNotIn(MISSING, reason, f"зерно {self.seed}: {context}")

    def assert_refused(self, outcome: str, reason: str, context: str) -> None:
        self.assertEqual(outcome, "failed",
                         f"зерно {self.seed}: {context} — шаг сдан: {reason}")
        self.assertIn(MISSING, reason, f"зерно {self.seed}: {context}")


class Ac1LongLivedOnlyStepAcceptedTest(RequiredArtifactStepSandbox):

    def test_ac1_long_lived_file_alone_satisfies_test_author(self):
        """test_author оставил только новый долгоживущий файл своей задачи.

        Подставной агент пишет `tests/test_<префикс задачи>_<случайное
        имя>.py` (новый относительно базы ветки — в базе его нет), каталога
        приёмочных тестов задачи не создаёт; на нескольких случайных
        задачах шаг обязан завершиться исходом "ok" без отказа «без
        артефакта».

        Ловит мутацию: ветка test_author проверки обязательного артефакта
        по-прежнему смотрит только в `acceptance_tests/` (или ищет файл
        долгоживущей формы не в рабочем каталоге роли, а в корне пульта) —
        `run_agent_once` вернёт "failed" с «шаг завершён без артефакта
        acceptance_tests/» вместо "ok".
        """
        for _ in range(3):
            task_id = self.new_task("tests_writing")
            rel = f"tests/test_{task_id.lower()}_{random_name(self.rng)}.py"
            self.assertTrue(guard.is_long_lived_test_path(task_id, rel), rel)
            with self.subTest(file=rel):
                outcome, reason = self.run_step(task_id, "test_author", [rel])
                self.assert_accepted(outcome, reason, f"только {rel}")


class Ac2ForeignTestFileNotCountedTest(RequiredArtifactStepSandbox):

    def test_ac2_foreign_or_unprefixed_test_file_is_refused(self):
        """test_author оставил только файл tests/, не являющийся своим долгоживущим.

        Два вида чужого файла: `tests/test_<префикс другой случайной
        задачи>_x.py` и `tests/test_other.py`; каталога приёмочных тестов
        задачи нет. Каждый шаг обязан получить исход "failed" с отказом
        «шаг завершён без артефакта …».

        Ловит мутацию: новое условие засчитывает любой `tests/test_*.py`
        (или файл с префиксом любой задачи — проверка по маске
        `tests/test_*_*.py` вместо `guard.is_long_lived_test_path` с id
        ЭТОЙ задачи) — шаг с чужим файлом вернёт "ok".
        """
        for _ in range(2):
            task_id = self.new_task("tests_writing")
            other = random_task_id(self.rng)
            for rel in (f"tests/test_{other.lower()}_x.py", "tests/test_other.py"):
                self.assertFalse(guard.is_long_lived_test_path(task_id, rel), rel)
                with self.subTest(file=rel):
                    outcome, reason = self.run_step(task_id, "test_author", [rel])
                    self.assert_refused(outcome, reason, f"только {rel}")


class Ac3AcceptanceTestsFileStillAcceptedTest(RequiredArtifactStepSandbox):

    def test_ac3_acceptance_tests_file_alone_satisfies_test_author(self):
        """test_author оставил только файл в каталоге приёмочных тестов задачи.

        Подставной агент пишет один `test_<случайное имя>.py` в каталог
        `acceptance_tests/` задачи, долгоживущих файлов нет; шаг обязан
        завершиться исходом "ok", как до задачи.

        Ловит мутацию: правка условия заменила прежнюю проверку каталога
        приёмочных тестов новой (только долгоживущий файл) вместо
        дизъюнкции «либо — либо» — шаг с одной планкой вернёт "failed".
        """
        for _ in range(2):
            task_id = self.new_task("tests_writing")
            rel = (Path("tasks") / task_id / "acceptance_tests"
                   / f"test_{random_name(self.rng)}.py")
            with self.subTest(file=str(rel)):
                outcome, reason = self.run_step(task_id, "test_author", [rel])
                self.assert_accepted(outcome, reason, f"только {rel}")


class Ac4NothingWrittenRefusalNamesBothFormsTest(RequiredArtifactStepSandbox):

    def test_ac4_refusal_names_acceptance_tests_and_long_lived_form(self):
        """test_author не оставил ни планки, ни своего долгоживущего файла.

        Подставной агент ничего не пишет. Шаг обязан получить "failed" с
        отказом «шаг завершён без артефакта …», и пояснение называет обе
        ожидаемые формы: `acceptance_tests/` и долгоживущий файл
        `tests/test_<префикс задачи>_<имя>.py` — буквальным шаблоном
        `tests/test_<…` либо фактическим префиксом этой задачи
        (`guard.long_lived_path_prefix`).

        Ловит мутацию: условие расширено, а имя артефакта в отказе
        оставлено прежним «acceptance_tests/» — пояснение не содержит
        ни `tests/test_<`, ни префикса задачи, и тест краснеет.
        """
        for _ in range(2):
            task_id = self.new_task("tests_writing")
            outcome, reason = self.run_step(task_id, "test_author", [])
            self.assert_refused(outcome, reason, "ничего не написано")
            self.assertIn("acceptance_tests/", reason,
                          f"зерно {self.seed}: отказ не называет планку")
            prefix = guard.long_lived_path_prefix(task_id)
            self.assertTrue(
                prefix in reason or "tests/test_<" in reason,
                f"зерно {self.seed}: отказ не называет долгоживущую форму "
                f"tests/test_<префикс задачи>_<имя>.py: {reason}")


# Свой артефакт и прежнее имя в отказе ролей вне test_author (AC-5).
OTHER_ROLES = (
    ("analyst", "spec_writing", ("SPEC.md", "QUESTIONS.md"), "SPEC.md/QUESTIONS.md"),
    ("developer", "in_dev", ("PLAN.md",), "PLAN.md"),
    ("reviewer", "review", ("REVIEW.md",), "REVIEW.md"),
)


class Ac5OtherRolesUnchangedTest(RequiredArtifactStepSandbox):

    def test_ac5_other_roles_keep_their_required_artifact_check(self):
        """analyst/developer/reviewer: свой артефакт — шаг сдан, нет — прежний отказ.

        Для каждой роли два шага на свежих случайных задачах: агент пишет
        свой артефакт (у analyst — случайно SPEC.md или QUESTIONS.md) в
        каталог задачи — исход "ok"; агент пишет только долгоживущий файл
        `tests/test_<префикс задачи>_<имя>.py` — исход "failed" с «шаг
        завершён без артефакта <прежнее имя>».

        Ловит мутацию: признак долгоживущего файла добавлен общим условием
        до ветвления по ролям (или в ветки developer/reviewer/analyst) —
        шаг роли без своего артефакта, но с долгоживущим файлом вернёт "ok";
        либо имя артефакта в отказе этих ролей сменилось вместе с текстом
        test_author — пропадёт «без артефакта PLAN.md» и т.п.
        """
        for role, state, artifacts, missing_name in OTHER_ROLES:
            with self.subTest(role=role):
                task_id = self.new_task(state)
                own = Path("tasks") / task_id / self.rng.choice(artifacts)
                outcome, reason = self.run_step(task_id, role, [own])
                self.assert_accepted(outcome, reason, f"{role}: {own}")

                task_id = self.new_task(state)
                rel = f"tests/test_{task_id.lower()}_{random_name(self.rng)}.py"
                outcome, reason = self.run_step(task_id, role, [rel])
                self.assert_refused(outcome, reason, f"{role}: только {rel}")
                self.assertIn(f"{MISSING} {missing_name}", reason,
                              f"зерно {self.seed}: {role} — прежнее имя "
                              f"артефакта пропало из отказа")


if __name__ == "__main__":
    unittest.main()
