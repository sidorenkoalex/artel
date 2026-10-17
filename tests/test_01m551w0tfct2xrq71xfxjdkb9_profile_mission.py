"""Задание test_author и developer называет каталог и префикс долгоживущих файлов по профилю проекта задачи.

Группа: долгоживущий
Красен до реализации: `role_prompt.mission_brief_package` берёт префикс `guard.long_lived_path_prefix(task_id)` и текст «tests/» по умолчаниям артели — у учебного проекта с `backend/tests` задание называет `tests/test_<id>_`, а при отказе профиля и у проекта без профиля абзац о долгоживущих файлах остаётся; AC-1 (артель) держит сегодняшний текст и зелён с рождения.

Задание собирается публичным `role_prompt.mission_brief_package` по строке
задачи из БД песочницы (`tests.sandbox.TmpRootTest`: `config.TARGETS`,
`config.DB` — во временном каталоге), профиль проекта — запись
`targets.yaml` песочницы. Брифы ролей (`brief.*`) подменены пустыми: они не
предмет теста, а задание (`mission`) собирается независимо от них.

Учебный внешний проект — профиль с `long_lived_dir: backend/tests` (вне
корня) и, вторым входом, со случайным вложенным каталогом. Отказ профиля
(`project_profile.Decision.refusal`) — артель без поля `test_profile`;
пропуск (`Decision.skip`) — внешний проект без него. Идентификаторы задач и
имена — из `random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
каталог и префикс — из `project_profile.for_task`, без профиля абзацы о
долгоживущих файлах опущены; все методы зелёные.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import brief, config, project_profile, review, role_prompt, store
from tests.sandbox import TmpRootTest

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
LLD = "backend/tests"
ROLES = ("test_author", "developer")
# `tests/`, не входящий в более длинный путь (`backend/tests/`).
BARE_TESTS = re.compile(r"(?<![\w/])tests/")
LONG_LIVED_WORD = re.compile(r"[Дд]олгоживущ")

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


class ProfileMissionSandbox(TmpRootTest):
    """Артель и учебный внешний проект в `targets.yaml` песочницы."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
        self.ext = f"sled{self.word()}"
        for patcher in (
                mock.patch.object(brief, "test_author_answer_component",
                                  return_value=None),
                mock.patch.object(brief, "developer_brief", return_value=""),
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

    def declare(self, artel_profile: bool = True,
                ext_lld: str | None = LLD) -> None:
        config.TARGETS.write_text(
            "targets:\n" + entry(ARTEL, "tests" if artel_profile else None)
            + entry(self.ext, ext_lld), encoding="utf-8")

    def new_task(self, target: str, state: str) -> str:
        task_id = "01" + "".join(self.rng.choice(CROCKFORD) for _ in range(24))
        store.insert_task(self.conn, task_id, "Учебная задача", state,
                          f"task/{task_id.lower()}-{self.word()}", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def mission(self, target: str, role: str) -> tuple:
        """(задание роли, id задачи) для свежей задачи проекта `target`."""
        state = "tests_writing" if role == "test_author" else "in_dev"
        task_id = self.new_task(target, state)
        t = store.get_task(self.conn, task_id)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, task_id, t, role, f"/tmp/cwd-{self.word()}")
        return mission, task_id


class Ac1ArtelMissionsUnchangedTest(ProfileMissionSandbox):

    def test_ac1_artel_missions_keep_long_lived_paragraphs(self):
        """Артель с профилем артели: абзацы о долгоживущих файлах в заданиях test_author и developer — прежний текст.

        На нескольких случайных задачах задание test_author содержит
        дословно прежние пункт 2а (каталог `tests/`, имя
        `tests/test_<id>_<имя>.py`) и фразу пункта 5 о прогоне
        долгоживущих файлов `tests/`; задание developer — прежнюю фразу
        пункта 3 с `tests/ (tests/test_<id>_*.py)`.

        Ловит мутацию: подстановка профиля изменила текст артели —
        каталог склеен с префиксом иначе (`tests//test_…`, без `/`),
        пример имени вместо префикса, переформулированный абзац — одна из
        дословных фраз пропадёт.
        """
        self.declare()
        for _ in range(2):
            mission, task_id = self.mission(ARTEL, "test_author")
            prefix = f"tests/test_{task_id.lower()}_"
            for fragment in (
                    "2а) Долгоживущий файл (`Группа: долгоживущий`, "
                    "skills/test-authoring.md) пиши не в каталог приёмочных "
                    "тестов, а в каталог tests/ кодовой ветки, с именем "
                    f"{prefix}<имя>.py (<имя> — строчные латинские буквы, "
                    "цифры, подчёркивание). Существующие файлы tests/ не "
                    "трогай — их правку, переименование и удаление, как и "
                    "любую другую правку вне ",
                    "пульт откатит; свои новые файлы с этим префиксом он сам "
                    "закоммитит в ветку на чекпоинте шага.\n3) ",
                    "; долгоживущие файлы tests/ — тем же pytest с теми же "
                    "флагами по их путям из рабочего каталога. "):
                with self.subTest(role="test_author", fragment=fragment[:40]):
                    self.assertIn(fragment, mission, self.note(mission))
            mission, task_id = self.mission(ARTEL, "developer")
            fragment = (
                f"Долгоживущие файлы задачи в tests/ "
                f"(tests/test_{task_id.lower()}_*.py) зафиксированы так же, как "
                f"приёмочные тесты, — перечнем сумм под тем же локом: их не "
                f"правь, расхождение с ними эскалируй.\n4) ")
            with self.subTest(role="developer"):
                self.assertIn(fragment, mission, self.note(mission))


class Ac2ExternalMissionsByProfileTest(ProfileMissionSandbox):

    def test_ac2_external_missions_name_profile_dir_and_prefix(self):
        """Учебный проект: задания называют `<каталог профиля>/test_<id>_`, без префикса и каталога артели.

        Входы — `backend/tests` и случайный вложенный каталог. Задание
        test_author содержит префикс `<каталог>/test_<id>_`, называет
        каталог `<каталог>/` и не содержит голого `tests/` (каталога
        артели); задание developer содержит тот же префикс. В обоих каждое
        вхождение `tests/test_<id>_` — часть префикса профиля.

        Ловит мутацию: задание берёт `guard.long_lived_path_prefix(task_id)`
        без профиля — в нём будет `tests/test_<id>_`; либо префикс
        подставлен по профилю, а каталог в пунктах 2а/5 остался буквальным
        «tests/» — голый `tests/` в задании test_author.
        """
        for lld in (LLD, f"{self.word()}/{self.word()}"):
            self.declare(ext_lld=lld)
            for role in ROLES:
                mission, task_id = self.mission(self.ext, role)
                prefix = f"{lld}/test_{task_id.lower()}_"
                artel_prefix = f"tests/test_{task_id.lower()}_"
                with self.subTest(lld=lld, role=role):
                    self.assertIn(prefix, mission, self.note(mission))
                    self.assertNotIn(artel_prefix, mission.replace(prefix, ""),
                                     self.note(f"префикс артели: {mission}"))
                    if role == "test_author":
                        self.assertIsNone(BARE_TESTS.search(mission),
                                          self.note(f"голый tests/: {mission}"))


class Ac6RefusalMissionTest(ProfileMissionSandbox):

    def test_ac6_refusal_missions_name_no_long_lived_dir(self):
        """Отказ профиля (артель без `test_profile`): задания не называют каталог долгоживущих тестов.

        Задание test_author не содержит ни префикса `tests/test_<id>_`, ни
        голого `tests/`; задание developer — ни префикса, ни фразы
        «Долгоживущие файлы задачи в tests/». Несколько случайных задач.

        Ловит мутацию: при `Decision.refusal` задание откатывается к
        умолчаниям артели — абзацы с `tests/` и префиксом остаются.
        """
        self.declare(artel_profile=False)
        self.assertTrue(project_profile.decide(ARTEL).refusal,
                        self.note("сценарий не дал отказа"))
        for _ in range(2):
            for role in ROLES:
                mission, task_id = self.mission(ARTEL, role)
                with self.subTest(role=role):
                    self.assertNotIn(f"tests/test_{task_id.lower()}_", mission,
                                     self.note(mission))
                    if role == "test_author":
                        self.assertIsNone(BARE_TESTS.search(mission),
                                          self.note(mission))
                    else:
                        self.assertNotIn("Долгоживущие файлы задачи в tests/",
                                         mission, self.note(mission))


class Ac7SkipMissionTest(ProfileMissionSandbox):

    def test_ac7_skip_missions_have_no_long_lived_paragraph(self):
        """Учебный проект без `test_profile`: в заданиях нет абзаца о долгоживущих файлах.

        Задания test_author и developer не упоминают долгоживущие файлы и
        не содержат префикса `tests/test_<id>_`; задание test_author не
        содержит и голого `tests/`. Несколько случайных задач.

        Ловит мутацию: при `Decision.skip` задание подставляет умолчания
        артели — пункт 2а test_author и фраза пункта 3 developer о
        `tests/test_<id>_*.py` остаются.
        """
        self.declare(ext_lld=None)
        for _ in range(2):
            for role in ROLES:
                mission, task_id = self.mission(self.ext, role)
                with self.subTest(role=role):
                    self.assertNotIn(f"tests/test_{task_id.lower()}_", mission,
                                     self.note(mission))
                    self.assertIsNone(LONG_LIVED_WORD.search(mission),
                                      self.note(mission))
                    if role == "test_author":
                        self.assertIsNone(BARE_TESTS.search(mission),
                                          self.note(mission))


if __name__ == "__main__":
    unittest.main()
