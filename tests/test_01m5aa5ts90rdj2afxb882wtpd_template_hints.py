"""Подсказки о долгоживущих файлах по шаблону с `<dir>`: задание test_author и developer, отказ обязательного артефакта шага.

Группа: долгоживущий
Красен до реализации: запись с компонентом `pult-vitest` и полем `long_lived` отказывает «long_lived исполняется после G2б» — профиля нет, задания не называют каталог долгоживущих файлов, а отказ шага не называет долгоживущий файл; тексты прежде склеивались из префикса и хвоста «<имя>.py»/«*.py» — у шаблона `.test.jsx` они были бы иными. Тексты артели, записи `test_profile` и явной пары (AC-13) держат поведение базы ветки и зелены с рождения.

Задания собираются публичным `role_prompt.mission_brief_package` по строке
задачи из БД песочницы (`tests.sandbox.TmpRootTest`); брифы ролей
(`brief.*`, `review.*`) подменены пустыми — предмет только задание. Отказ
обязательного артефакта — штатный шаг `runner.run_agent_once` с
подставным агентом (`runner.spawn_agent`), ничего не пишущим, на настоящем
git (`tests.sandbox.RealGitSandbox`): связка «шаг роли — профиль проекта —
рабочая копия задачи».

Учебные проекты: компонент `pult-vitest` с шаблоном
`frontend/src/<dir>/<name>.<id>.test.jsx`; компонент `pult-vitest` с явной
парой `web/src` / `<id>_<name>.test.js`; запись `test_profile` как у sled
(`backend/tests`, `test_<id>_<name>.py`); артель. Идентификаторы задач и
имена — из `random`; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
пример пути с `<каталог>` и `*` в заданиях test_author/developer и в
отказе обязательного артефакта, пояснение `<каталог>` у шаблона с `<dir>`
— все методы файла зелёные; тексты артели, `test_profile` и явной пары —
зелёные и на базе ветки, и на стабе.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import (brief, catalog, config, keychain, project_profile,
                          review, role_prompt, runner, stack, store, workspace)
from tests.sandbox import (FakeProc, RealGitSandbox, TmpRootTest,
                           artel_target_entry, capture, make_project_repo)

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
TASKS_DIR = "tasks"
MISSING = "шаг завершён без артефакта"
RESULT_LINE = '{"type": "result", "total_cost_usd": 0.001}\n'
TEMPLATE = "frontend/src/<dir>/<name>.<id>.test.jsx"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

VITEST_COMPONENT = """    components:
      {comp}:
        command: [{command}]
        report: pult-vitest
        weakening_scope: [frontend/src/**, web/src/**]
        mutation_claim_scope: [frontend/src/**, web/src/**]
        tests: [{masks}]
{pair}"""

SLED_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
"""


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def task_ref(task_id: str) -> str:
    return f"{TASKS_DIR}/{task_id}"


class HintProjects:
    """Записи учебных проектов: шаблон, явная пара, `test_profile` sled."""

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def vitest_entry(self, name: str, template: bool) -> str:
        pair = (f"        long_lived: {TEMPLATE}\n" if template else
                "        long_lived_dir: web/src\n"
                "        long_lived_name: <id>_<name>.test.js\n")
        masks = "frontend/**/*.test.jsx" if template else "web/src/**/*.test.js"
        return ENTRY_HEAD.format(name=name, base=config.MAIN_BRANCH) + \
            VITEST_COMPONENT.format(
                comp=f"c{self.word()}",
                command=", ".join(project_profile.VITEST_BASE_ARGV),
                masks=masks, pair=pair)

    # Проект с шаблоном заводят только сценарии шаблона: прежние тексты
    # (AC-13) не зависят от того, читается ли запись с шаблоном.
    WITH_TEMPLATE = False

    def declare_projects(self) -> dict:
        """{вид: имя проекта} — явная пара, sled и (`WITH_TEMPLATE`)
        шаблон; запись артели — с профилем артели."""
        names = {"pair": f"p{self.word()}", "sled": f"s{self.word()}"}
        text = ("targets:\n" + artel_target_entry()
                + self.vitest_entry(names["pair"], False)
                + ENTRY_HEAD.format(name=names["sled"], base=config.MAIN_BRANCH)
                + SLED_PROFILE)
        if self.WITH_TEMPLATE:
            names["template"] = f"t{self.word()}"
            text += self.vitest_entry(names["template"], True)
        config.TARGETS.write_text(text, encoding="utf-8")
        return names

    def old_paths(self, kind: str, task_id: str) -> tuple:
        """(каталог, префикс) прежних текстов вида `kind`."""
        low = task_id.lower()
        return {ARTEL: ("tests", f"tests/test_{low}_"),
                "pair": ("web/src", f"web/src/{low}_"),
                "sled": ("backend/tests", f"backend/tests/test_{low}_")}[kind]


class MissionSandbox(HintProjects, TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        store.create_schema(store.db())
        self.conn = store.db()
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
        self.names = self.declare_projects()
        for name in self.names.values():
            make_project_repo(name, origin=False)

    def mission(self, target: str, role: str) -> tuple:
        """(задание роли, id задачи) свежей задачи проекта `target`."""
        state = "tests_writing" if role == "test_author" else "in_dev"
        task_id = ulid(self.rng)
        store.insert_task(self.conn, task_id, "Учебная задача", state,
                          f"task/{task_id.lower()}-{self.word()}", target,
                          config.DEFAULT_BUDGET_USD)
        t = store.get_task(self.conn, task_id)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, task_id, t, role, f"/tmp/cwd-{self.word()}")
        return mission, task_id

    def pult_of(self, mission: str, task_id: str) -> str:
        """Форма команды пульта, которой задание test_author внешнего
        проекта начинает пункт 5."""
        found = re.search(r"5\) Прогони планку командой пульта `(.+?) "
                          r"plank-run " + re.escape(task_id) + "`", mission)
        self.assertIsNotNone(found, self.note(f"нет пункта 5: {mission}"))
        return found.group(1)


# ---------------------------------------------------------------- AC-15

class Ac15TemplateMissionTextsTest(MissionSandbox):
    WITH_TEMPLATE = True

    def test_ac15_test_author_points_for_dir_template(self):
        """Задание test_author проекта с шаблоном `frontend/src/<dir>/<name>.<id>.test.jsx` несёт дословно пункт 2а с пояснением `<каталог>` и хвост пункта 5.

        Сценарий: на нескольких случайных задачах проекта с единственным
        компонентом `pult-vitest` и этим шаблоном задание test_author
        содержит пункт 2а требования 4 целиком (с переводом строки) и хвост
        пункта 5 «; долгоживущие файлы frontend/src/ — той же командой по
        пути каждого файла: `<пульт> plank-run <ID>
        frontend/src/<каталог>/<имя>.<id>.test.jsx`», где `<пульт>` — та же
        форма команды, что в начале пункта 5.

        Ловит мутацию: пункт 2а собран прежней склейкой
        `{prefix}<имя>.py` — в нём `frontend/src/<dir>/` и `.py`; пояснение
        `<каталог>` не добавлено — фразы «ноль или больше подкаталогов»
        нет; хвост пункта 5 склеен из префикса — путь иной.
        """
        name = self.names["template"]
        for _ in range(2):
            mission, task_id = self.mission(name, "test_author")
            low = task_id.lower()
            point = (
                "2а) Долгоживущий файл (`Группа: долгоживущий`, "
                "skills/test-authoring.md) пиши не в каталог приёмочных "
                "тестов, а в каталог frontend/src/ кодовой ветки, с именем "
                f"frontend/src/<каталог>/<имя>.{low}.test.jsx (<имя> — "
                "строчные латинские буквы, цифры, подчёркивание; <каталог> — "
                "каталог модуля: ноль или больше подкаталогов frontend/src/, "
                "ни один не начинается с точки). Существующие файлы "
                "frontend/src/ не трогай — их правку, переименование и "
                "удаление, как и любую другую правку вне "
                f"{task_ref(task_id)}/, пульт откатит; свои новые файлы с "
                "этим префиксом он сам закоммитит в ветку на чекпоинте "
                "шага.\n")
            with self.subTest(point="2а", task=task_id, seed=self.seed):
                self.assertIn(point, mission, self.note(mission))
            pult = self.pult_of(mission, task_id)
            tail = ("; долгоживущие файлы frontend/src/ — той же командой по "
                    f"пути каждого файла: `{pult} plank-run {task_id} "
                    f"frontend/src/<каталог>/<имя>.{low}.test.jsx`")
            with self.subTest(point="5", task=task_id, seed=self.seed):
                self.assertIn(tail, mission, self.note(mission))

    def test_ac15_developer_phrase_for_dir_template(self):
        """Задание developer проекта с шаблоном несёт фразу о долгоживущих файлах с примером `frontend/src/<каталог>/*.<id>.test.jsx`.

        Сценарий: на нескольких случайных задачах задание developer
        содержит дословно « Долгоживущие файлы задачи в frontend/src/
        (frontend/src/<каталог>/*.<id>.test.jsx) зафиксированы так же, как
        приёмочные тесты, — перечнем сумм под тем же локом: их не правь,
        расхождение с ними эскалируй.» — это и пример пути функции
        примера `guard` с подстановкой `*` (AC-4).

        Ловит мутацию: фраза склеена из префикса и «*.py» — в ней
        `frontend/src/<dir>/*.py`; функция примера подставляет `<имя>`
        вместо переданного `*` — в скобках `<имя>`.
        """
        name = self.names["template"]
        for _ in range(2):
            mission, task_id = self.mission(name, "developer")
            phrase = (" Долгоживущие файлы задачи в frontend/src/ "
                      f"(frontend/src/<каталог>/*.{task_id.lower()}.test.jsx) "
                      "зафиксированы так же, как приёмочные тесты, — перечнем "
                      "сумм под тем же локом: их не правь, расхождение с ними "
                      "эскалируй.")
            with self.subTest(task=task_id, seed=self.seed):
                self.assertIn(phrase, mission, self.note(mission))


# ---------------------------------------------------------------- AC-13

class Ac13OldMissionTextsTest(MissionSandbox):

    def test_ac13_missions_unchanged_for_artel_sled_and_pair(self):
        """Пункт 2а, пункт 5 и фраза developer у артели, записи `test_profile` sled и явной пары — побайтно прежние.

        Сценарий: для каждого вида проекта — задание test_author содержит
        прежний пункт 2а (каталог, `<префикс><имя>.py`, без пояснения
        `<каталог>`), пункт 5 — прежний хвост ветки артели («тем же pytest
        с теми же флагами …») либо внешнего проекта («той же командой по
        пути каждого файла: `<пульт> plank-run <ID> <префикс><имя>.py`»);
        задание developer — прежнюю фразу с `<префикс>*.py`. Пояснения
        `<каталог>` нет ни в одном.

        Ловит мутацию: новая функция примера пути применена к явной паре —
        у пары `web/src` / `<id>_<name>.test.js` пример становится
        `web/src/<id>_<имя>.test.js` вместо прежнего `web/src/<id>_<имя>.py`;
        пояснение `<каталог>` добавляется безусловно — оно есть у артели.
        """
        for kind in (ARTEL, "sled", "pair"):
            target = ARTEL if kind == ARTEL else self.names[kind]
            mission, task_id = self.mission(target, "test_author")
            directory, prefix = self.old_paths(kind, task_id)
            point = (
                "2а) Долгоживущий файл (`Группа: долгоживущий`, "
                "skills/test-authoring.md) пиши не в каталог приёмочных "
                f"тестов, а в каталог {directory}/ кодовой ветки, с именем "
                f"{prefix}<имя>.py (<имя> — строчные латинские буквы, "
                f"цифры, подчёркивание). Существующие файлы {directory}/ не "
                "трогай — их правку, переименование и удаление, как и любую "
                f"другую правку вне {task_ref(task_id)}/, пульт откатит; "
                "свои новые файлы с этим префиксом он сам закоммитит в ветку "
                "на чекпоинте шага.\n")
            if kind == ARTEL:
                tail = (f"; долгоживущие файлы {directory}/ — тем же pytest с "
                        "теми же флагами по их путям из рабочего каталога")
            else:
                tail = (f"; долгоживущие файлы {directory}/ — той же командой "
                        f"по пути каждого файла: `{self.pult_of(mission, task_id)} "
                        f"plank-run {task_id} {prefix}<имя>.py`")
            with self.subTest(kind=kind, role="test_author", seed=self.seed):
                self.assertIn(point, mission, self.note(mission))
                self.assertIn(tail, mission, self.note(mission))
                self.assertNotIn("<каталог> — каталог модуля", mission,
                                 self.note(mission))
            mission, task_id = self.mission(target, "developer")
            directory, prefix = self.old_paths(kind, task_id)
            phrase = (f" Долгоживущие файлы задачи в {directory}/ ({prefix}*.py) "
                      "зафиксированы так же, как приёмочные тесты, — перечнем "
                      "сумм под тем же локом: их не правь, расхождение с ними "
                      "эскалируй.")
            with self.subTest(kind=kind, role="developer", seed=self.seed):
                self.assertIn(phrase, mission, self.note(mission))


# ---------------------------------------------------------------- шаг роли

class RequiredArtifactSandbox(HintProjects, RealGitSandbox):

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
        self.names = self.declare_projects()
        for name in self.names.values():
            make_project_repo(name)
        capture(catalog.cmd_init)

    def empty_step_reason(self, target: str) -> tuple:
        """(пояснение отказа, id задачи) шага test_author, агент которого
        ничего не пишет."""
        task_id = ulid(self.rng)
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        _wt, error = workspace.ensure(task_id, branch, target)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        with mock.patch.object(runner, "spawn_agent",
                               return_value=FakeProc([RESULT_LINE], 0)):
            outcome, reason, _cls = runner.run_agent_once(
                self.conn, task_id, "test_author", "промпт шага", 1)
        self.assertEqual(outcome, "failed", self.note(f"шаг сдан: {reason}"))
        self.assertIn(MISSING, reason or "", self.note(str(reason)))
        return reason, task_id


class Ac15RequiredArtifactTextTest(RequiredArtifactSandbox):
    WITH_TEMPLATE = True

    def test_ac15_required_artifact_hint_for_dir_template(self):
        """Отказ шага test_author без артефакта у проекта с шаблоном называет `frontend/src/<каталог>/<имя>.<id>.test.jsx`.

        Сценарий: подставной агент ничего не пишет; пояснение отказа шага
        несёт дословно «acceptance_tests/ (файл в <каталог
        задачи>/acceptance_tests/ либо долгоживущий файл
        frontend/src/<каталог>/<имя>.<id>.test.jsx)».

        Ловит мутацию: подсказка склеена прежним `{prefix}<имя>.py` — в
        ней `frontend/src/<dir>/` и `.py`.
        """
        reason, task_id = self.empty_step_reason(self.names["template"])
        hint = (f"acceptance_tests/ (файл в {task_ref(task_id)}/acceptance_tests/ "
                f"либо долгоживущий файл frontend/src/<каталог>/<имя>."
                f"{task_id.lower()}.test.jsx)")
        self.assertIn(hint, reason, self.note(reason))


class Ac13RequiredArtifactTextTest(RequiredArtifactSandbox):

    def test_ac13_required_artifact_hint_unchanged(self):
        """Отказ шага test_author без артефакта у артели, sled и явной пары — прежний текст с `<префикс><имя>.py`.

        Сценарий: для каждого вида проекта подставной агент ничего не
        пишет; пояснение несёт «acceptance_tests/ (файл в <каталог
        задачи>/acceptance_tests/ либо долгоживущий файл
        <префикс><имя>.py)» с прежним префиксом вида.

        Ловит мутацию: функция примера пути применена к явной паре — у неё
        в подсказке `web/src/<id>_<имя>.test.js` вместо прежнего текста.
        """
        for kind in (ARTEL, "sled", "pair"):
            target = ARTEL if kind == ARTEL else self.names[kind]
            with self.subTest(kind=kind, seed=self.seed):
                reason, task_id = self.empty_step_reason(target)
                _directory, prefix = self.old_paths(kind, task_id)
                hint = (f"acceptance_tests/ (файл в "
                        f"{task_ref(task_id)}/acceptance_tests/ либо "
                        f"долгоживущий файл {prefix}<имя>.py)")
                self.assertIn(hint, reason, self.note(reason))


if __name__ == "__main__":
    unittest.main()
