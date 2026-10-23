"""Миссии ролей задачи внешнего проекта называют команды пульта `guard`, `plank-run`, `suite-run` в форме белого списка роли.

Группа: долгоживущий
Красен до реализации: `role_prompt.mission_brief_package` у задачи внешнего проекта велит «Прогони scripts/guard.py» (analyst, developer, spec_auditor), пункт 5 test_author велит `python3 -m pytest` и не называет `plank-run <id> <префикс>`, миссия ревьювера пишет «Права не сужены» и не называет команд пульта.

Миссия собирается публичным `role_prompt.mission_brief_package` по строке
задачи из БД песочницы (`tests.sandbox.TmpRootTest`: `config.ROOT`,
`config.TARGETS`, `config.DB` — во временном каталоге), профиль проекта —
запись `targets.yaml` песочницы. Брифы и ревью-пакет (`brief.*`,
`review.*`) подменены пустыми: они не предмет теста, миссия собирается
независимо от них; признак проекта задачи (`brief.is_artel_task`) — не
подменён. Корень пульта в ожидаемых строках — `config.ROOT` в момент
сборки. Учебный проект — профиль с `long_lived_dir: backend/tests` и,
вторым входом, со случайным вложенным каталогом. Идентификаторы задач и
имена — из `random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
развилка миссий по `brief.is_artel_task`; все методы зелёные.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import brief, config, project_profile, review, role_prompt, store
from tests.sandbox import TmpRootTest, artel_target_entry

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
LLD = "backend/tests"
GUARD_ROLES = ("analyst", "developer", "spec_auditor")
STATE_OF = {"analyst": "spec_writing", "spec_auditor": "spec_audit",
            "test_author": "tests_writing", "developer": "in_dev",
            "reviewer": "review"}

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [uv, run, --frozen, pytest]
      long_lived_dir: {lld}
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [{lld}/**/*.py]
      mutation_claim_scope: [{lld}/test_*.py]
      report: junit-xml
      install: []
      runner: pytest-own
      workdir: {workdir}
"""


class ExternalMissionSandbox(TmpRootTest):
    """Артель и учебный внешний проект с профилем `pytest-own`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
        self.ext = f"sled{self.word()}"
        for patcher in (
                mock.patch.object(brief, "analyst_map_component",
                                  return_value=""),
                mock.patch.object(brief, "test_author_answer_component",
                                  return_value=None),
                mock.patch.object(brief, "developer_brief", return_value=""),
                mock.patch.object(brief, "spec_auditor_brief", return_value=""),
                mock.patch.object(brief, "step_notes_block", return_value=""),
                mock.patch.object(review, "review_package", return_value=""),
                mock.patch.object(review, "previous_verdict_sha",
                                  return_value="")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def declare(self, lld: str = LLD) -> None:
        workdir = lld.split("/")[0]
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + ENTRY.format(
                name=self.ext, base=config.MAIN_BRANCH, lld=lld,
                workdir=workdir), encoding="utf-8")

    def new_task(self, target: str, state: str) -> str:
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, task_id, "Учебная задача", state,
                          f"task/{task_id.lower()}-{self.word()}", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def mission(self, role: str) -> tuple:
        """(миссия роли, id задачи) для свежей задачи учебного проекта."""
        task_id = self.new_task(self.ext, STATE_OF[role])
        t = store.get_task(self.conn, task_id)
        docs = config.PROJECTS / self.ext / "tasks" / task_id
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, task_id, t, role, f"/tmp/cwd-{self.word()}", docs)
        return mission, task_id

    def pult(self) -> str:
        return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'}"


class Ac4GuardInMissionsTest(ExternalMissionSandbox):

    def test_ac4_external_missions_name_pult_guard_command(self):
        """Миссии analyst, developer и spec_auditor задачи учебного проекта называют `python3 <корень пульта>/orchestrator/artel.py guard <id>` и не называют `scripts/guard.py`.

        Несколько случайных задач учебного проекта; для каждой роли миссия
        содержит строку `python3 <config.ROOT>/orchestrator/artel.py guard
        <id>` и не содержит `scripts/guard.py`.

        Ловит мутацию: развилка миссии по проекту задачи не тронула одну из
        трёх ролей — у неё остаётся «Прогони scripts/guard.py»; команда
        названа без полного пути пульта (`artel.py guard`) либо без
        идентификатора задачи — ожидаемой строки нет.
        """
        self.declare()
        for _ in range(2):
            for role in GUARD_ROLES:
                mission, task_id = self.mission(role)
                with self.subTest(role=role, seed=self.seed):
                    self.assertNotIn("scripts/guard.py", mission,
                                     self.note(mission))
                    self.assertIn(f"{self.pult()} guard {task_id}", mission,
                                  self.note(mission))


class Ac7TestAuthorRunNoteTest(ExternalMissionSandbox):

    def point5(self, mission: str) -> str:
        start = mission.find("\n5) ")
        self.assertNotEqual(start, -1, self.note(f"пункта 5 нет: {mission}"))
        end = mission.find("\n\n", start)
        return mission[start:] if end == -1 else mission[start:end]

    def test_ac7_external_test_author_runs_long_lived_by_plank_run_prefix(self):
        """Пункт 5 миссии test_author учебного проекта велит `plank-run <id> <long_lived_prefix(id)>` командой пульта, без `python3 -m pytest`.

        Входы — профиль с `long_lived_dir: backend/tests` и со случайным
        вложенным каталогом, по две случайные задачи. Пункт 5 содержит
        `python3 <config.ROOT>/orchestrator/artel.py plank-run <id>
        <префикс профиля>` и не содержит `python3 -m pytest`; у профиля
        `backend/tests` пункт содержит `plank-run <id>
        backend/tests/test_<id>_` и не содержит `backend/tests/backend/tests`.

        Ловит мутацию: к префиксу профиля повторно приписан каталог
        (`{long_lived_dir}/{long_lived_prefix}`) — в пункте
        `backend/tests/backend/tests`; хвост пункта 5 остался «тем же
        pytest с теми же флагами» или прогон планки назван командой
        `python3 -m pytest` — эта строка в пункте; префикс взят по
        умолчаниям артели — `tests/test_<id>_` вместо префикса профиля.
        """
        for lld in (LLD, f"{self.word()}/{self.word()}"):
            self.declare(lld)
            profile = project_profile.decide(self.ext).profile
            for _ in range(2):
                mission, task_id = self.mission("test_author")
                point = self.point5(mission)
                with self.subTest(lld=lld, seed=self.seed):
                    prefix = profile.long_lived_prefix(task_id)
                    self.assertIn(f"{self.pult()} plank-run {task_id} {prefix}",
                                  point, self.note(point))
                    self.assertNotIn("python3 -m pytest", point, self.note(point))
                    if lld == LLD:
                        self.assertIn(f"plank-run {task_id} backend/tests/"
                                      f"test_{task_id.lower()}_", point,
                                      self.note(point))
                        self.assertNotIn("backend/tests/backend/tests", point,
                                         self.note(point))


class Ac8ReviewerChecksTest(ExternalMissionSandbox):

    def test_ac8_external_reviewer_lists_pult_check_commands(self):
        """Миссия ревьювера задачи учебного проекта перечисляет `guard`, `plank-run` командами пульта, не называет `suite-run <id>` и не пишет «Права не сужены».

        Несколько случайных задач учебного проекта в `review`; миссия
        содержит `python3 <config.ROOT>/orchestrator/artel.py guard` и `…
        plank-run`, не содержит «Права не сужены» и не содержит
        `suite-run <id>` без ` --failed`/` --wait` (решение Оператора 23.10,
        CR-2026-10-22-2, вариант А: полный набор ревьюверу запрещён).

        Ловит мутацию: строка ревьювера о правах не развилась по проекту
        задачи — «Права не сужены» остаётся; перечень команд пульта неполон
        (нет `plank-run` или `guard`) либо назван без полного пути пульта —
        одной из строк нет; перечень снова называет `suite-run <id>` —
        полный прогон без флагов.
        """
        self.declare()
        for _ in range(2):
            mission, task_id = self.mission("reviewer")
            with self.subTest(seed=self.seed):
                self.assertNotIn("Права не сужены", mission, self.note(mission))
                for command in ("guard", "plank-run"):
                    self.assertIn(f"{self.pult()} {command}", mission,
                                  self.note(mission))
                for name in (re.escape(task_id), re.escape("<id>")):
                    self.assertIsNone(
                        re.search(rf"suite-run {name}(?! --failed)(?! --wait)",
                                  mission), self.note(mission))


if __name__ == "__main__":
    unittest.main()
