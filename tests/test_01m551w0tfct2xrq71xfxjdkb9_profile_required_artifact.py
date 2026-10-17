"""Проверка обязательного артефакта шага test_author видит долгоживущий файл по профилю проекта задачи.

Группа: долгоживущий
Красен до реализации: проверка обязательного артефакта ищет долгоживущий файл только под `tests/` по умолчаниям артели — шаг учебного проекта с одним `backend/tests/test_<id>_<имя>.py` получает отказ «без артефакта», текст отказа называет `tests/test_<id>_`; при отказе профиля и у проекта без профиля файл `tests/test_<id>_<имя>.py` засчитывается; артель (AC-5, вторая часть) держит сегодняшнее поведение и зелена с рождения.

Шаг гоняется целиком через публичный `runner.run_agent_once` в песочнице с
настоящим git (`tests.sandbox.RealGitSandbox`): рабочий каталог роли —
рабочая копия задачи, которую заводит сам пульт (`workspace.ensure`), в
клоне проекта с bare `origin` (`tests.sandbox.make_project_repo`).
Подставной агент (`runner.spawn_agent`) пишет файлы сценария в `cwd`,
который ему передал пульт, — как роль инструментом Write, — и выходит
rc=0; каталога приёмочных тестов он не создаёт. Связка «шаг роли — профиль
проекта (`targets.yaml`) — git рабочей копии».

Учебный внешний проект — профиль с `long_lived_dir: backend/tests`. Отказ
профиля (`project_profile.Decision.refusal`) — артель без поля
`test_profile`; пропуск (`Decision.skip`) — внешний проект без него.
Идентификаторы задач, имена проектов и файлов — из `random`; зерно
печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
каталог, признак и префикс отказа — из профиля задачи, при отказе
профиля — запись журнала с причиной; все методы зелёные.
"""
import random
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (catalog, config, keychain, project_profile, runner,
                          stack, store, workspace)
from tests.sandbox import FakeProc, RealGitSandbox, capture, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
LLD = "backend/tests"
MISSING = "шаг завершён без артефакта"
RESULT_LINE = '{"type": "result", "total_cost_usd": 0.001}\n'

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
      report: junit-xml
      install: []
"""


def entry(name: str, lld: str | None) -> str:
    text = ENTRY.format(name=name, base=config.MAIN_BRANCH)
    return text + (PROFILE.format(lld=lld) if lld is not None else "")


class ProfileArtifactStepSandbox(RealGitSandbox):
    """Артель и учебный внешний проект; профили — по сценарию."""

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        stack_ok = [stack.StackCheck(name, "ok", "песочница")
                    for name in ("python", "git", "gh", "claude", "venv")]
        for patcher in (
                mock.patch.object(stack, "check_stack", lambda: list(stack_ok)),
                mock.patch.object(keychain, "token", lambda slot: "tok-test"),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.ext = f"sled{self.word()}"

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def declare(self, artel_profile: bool = True,
                ext_lld: str | None = LLD) -> None:
        config.TARGETS.write_text(
            "targets:\n" + entry(ARTEL, "tests" if artel_profile else None)
            + entry(self.ext, ext_lld), encoding="utf-8")
        make_project_repo(self.ext)
        capture(catalog.cmd_init)

    def new_task(self, target: str) -> str:
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id

    def own(self, task_id: str, directory: str) -> str:
        return f"{directory}/test_{task_id.lower()}_{self.word()}.py"

    def run_step(self, task_id: str, files: list) -> tuple:
        """Шаг test_author: агент пишет `files` от своего `cwd` и выходит
        rc=0; возврат — (исход, пояснение, id последней записи журнала до
        шага)."""
        before = max((r["id"] for r in store.task_steps(self.conn, task_id)),
                     default=0)
        seen = []

        def fake_agent(cmd, **kwargs):
            cwd = Path(kwargs["cwd"])
            seen.append(cwd)
            for rel in files:
                dest = cwd / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text("import unittest\n", encoding="utf-8")
            return FakeProc([RESULT_LINE], 0)

        with mock.patch.object(runner, "spawn_agent", side_effect=fake_agent):
            outcome, reason, _cls = runner.run_agent_once(
                self.conn, task_id, "test_author", "промпт шага", 1)
        self.assertEqual(len(seen), 1, self.note(
            f"агент не запущен ровно раз ({outcome}: {reason})"))
        return outcome, reason or "", before

    def assert_accepted(self, outcome: str, reason: str, context: str) -> None:
        self.assertEqual(outcome, "ok", self.note(f"{context} — шаг не сдан: {reason}"))
        self.assertNotIn(MISSING, reason, self.note(context))

    def assert_refused(self, outcome: str, reason: str, context: str) -> None:
        self.assertEqual(outcome, "failed", self.note(f"{context} — шаг сдан: {reason}"))
        self.assertIn(MISSING, reason, self.note(context))


class Ac5ExternalLongLivedArtifactTest(ProfileArtifactStepSandbox):

    def test_ac5_external_long_lived_file_alone_accepted(self):
        """Учебный проект с `backend/tests`: шаг с одним своим `backend/tests/test_<id>_<имя>.py` сдан.

        Агент пишет только свой долгоживущий файл в каталоге профиля,
        каталога приёмочных тестов нет. На нескольких случайных задачах
        исход "ok" без отказа «шаг завершён без артефакта».

        Ловит мутацию: `git diff`/`ls-files` проверки артефакта
        ограничены `-- tests`, либо признак своего файла — с каталогом
        артели по умолчанию — файл `backend/tests/…` не виден, и шаг
        вернёт "failed" с «без артефакта».
        """
        self.declare()
        for _ in range(2):
            task_id = self.new_task(self.ext)
            rel = self.own(task_id, LLD)
            with self.subTest(file=rel):
                outcome, reason, _ = self.run_step(task_id, [rel])
                self.assert_accepted(outcome, reason, f"только {rel}")

    def test_ac5_external_refusal_text_names_profile_prefix(self):
        """Учебный проект: отказ шага без планки называет `backend/tests/test_<id>_`, не `tests/test_<id>_`.

        Агент ничего не пишет; шаг получает "failed" с «шаг завершён без
        артефакта …», пояснение содержит `backend/tests/test_<id>_`, и
        каждое вхождение `tests/test_<id>_` в нём — часть
        `backend/tests/test_<id>_`.

        Ловит мутацию: текст отказа собран
        `guard.long_lived_path_prefix(task_id)` без каталога профиля — в
        пояснении будет `tests/test_<id>_` артели.
        """
        self.declare()
        task_id = self.new_task(self.ext)
        outcome, reason, _ = self.run_step(task_id, [])
        self.assert_refused(outcome, reason, "ничего не написано")
        prefix = f"tests/test_{task_id.lower()}_"
        self.assertIn(f"{LLD}/test_{task_id.lower()}_", reason, self.note(reason))
        self.assertEqual(reason.count(prefix), reason.count(f"backend/{prefix}"),
                         self.note(f"отказ называет префикс артели: {reason}"))

    def test_ac5_artel_behavior_and_refusal_text_unchanged(self):
        """Артель с профилем артели: свой `tests/test_<id>_<имя>.py` засчитан, отказ без планки — прежний текст.

        Первый шаг пишет только свой долгоживущий файл — "ok". Второй
        ничего не пишет — "failed", и пояснение несёт прежний текст отказа
        целиком: «шаг завершён без артефакта acceptance_tests/ (файл в
        <каталог задачи>/acceptance_tests/ либо долгоживущий файл
        tests/test_<id>_<имя>.py)».

        Ловит мутацию: подстановка профиля сменила текст отказа артели
        (другая формулировка, пример имени вместо префикса, иной каталог)
        или каталог профиля артели склеен с префиксом иначе — своё
        засчитывание сломается либо текст разойдётся с прежним.
        """
        self.declare()
        task_id = self.new_task(ARTEL)
        outcome, reason, _ = self.run_step(task_id, [self.own(task_id, "tests")])
        self.assert_accepted(outcome, reason, "только свой файл артели")
        task_id = self.new_task(ARTEL)
        outcome, reason, _ = self.run_step(task_id, [])
        acc = Path("tasks", task_id, "acceptance_tests").as_posix()
        expected = (f"{MISSING} acceptance_tests/ (файл в {acc}/ либо "
                    f"долгоживущий файл tests/test_{task_id.lower()}_<имя>.py)")
        self.assert_refused(outcome, reason, "ничего не написано")
        self.assertIn(expected, reason, self.note("текст отказа артели изменился"))


class Ac6RefusalArtifactTest(ProfileArtifactStepSandbox):

    def test_ac6_refusal_long_lived_not_counted_and_journaled(self):
        """Отказ профиля (артель без `test_profile`): долгоживущий файл не засчитан, журнал называет причину.

        Агент пишет только `tests/test_<id>_<имя>.py` — по умолчаниям
        артели свой. Шаг обязан получить "failed" с «шаг завершён без
        артефакта», а среди новых записей журнала задачи — запись с
        причиной отказа (`project_profile.decide(артель).refusal`).

        Ловит мутацию: при `Decision.refusal` проверка подставляет
        умолчания артели — шаг вернёт "ok"; либо отказ обработан молча —
        записи с причиной нет.
        """
        self.declare(artel_profile=False)
        decision = project_profile.decide(ARTEL)
        self.assertTrue(decision.refusal, self.note("сценарий не дал отказа"))
        task_id = self.new_task(ARTEL)
        outcome, reason, before = self.run_step(task_id, [self.own(task_id, "tests")])
        self.assert_refused(outcome, reason, "отказ профиля")
        texts = [f"{r['action']} {r['detail'] or ''}"
                 for r in store.task_steps(self.conn, task_id) if r["id"] > before]
        self.assertTrue(any(decision.refusal in t for t in texts),
                        self.note(f"нет записи с причиной отказа: {texts}"))


class Ac7SkipArtifactTest(ProfileArtifactStepSandbox):

    def test_ac7_skip_default_long_lived_not_counted(self):
        """Учебный проект без `test_profile`: шаг с одним `tests/test_<id>_<имя>.py` получает отказ «без артефакта».

        Несколько случайных задач; каталога приёмочных тестов нет.

        Ловит мутацию: при `Decision.skip` проверка подставляет умолчания
        артели — файл засчитается, и шаг вернёт "ok".
        """
        self.declare(ext_lld=None)
        for _ in range(2):
            task_id = self.new_task(self.ext)
            rel = self.own(task_id, "tests")
            with self.subTest(file=rel):
                outcome, reason, _ = self.run_step(task_id, [rel])
                self.assert_refused(outcome, reason, f"только {rel}")


if __name__ == "__main__":
    unittest.main()
