"""Задание test_author по правилу планки проекта: прежний текст у артели, `test_profile`, pytest-компонента и неопределённого профиля; текст Vitest-планки у компонента с меткой `AC-<n>: `.

Группа: долгоживущий
Красен до реализации: задание test_author у любого компонента требует unittest с методом `test_ac<n>_...` и пометки `# AC-n: …` — пункта 2 о каталоге `acceptance_tests/` без подкаталогов, масках, метке `AC-<n>: ` и `plank_layout`, строки запретов и пометок `//` у компонента `pult-vitest` и `junit-xml` с командой не pytest нет; тексты артели, `test_profile`, pytest-компонента и неопределённого профиля держат поведение пина и зелены с рождения.

Задание собирается публичным `role_prompt.mission_brief_package` по строке
задачи из БД песочницы (`tests.sandbox.TmpRootTest`); брифы ролей
(`brief.*`) подменены пустыми — предмет только задание. Учебные проекты
пишутся в `config.TARGETS` песочницы; идентификаторы задач, имена
компонентов, маски и `plank_layout` — из `random`, зерно печатается и
входит в текст каждого провала.

Эталон прежнего текста (AC-1) снят с кода пина
(`orchestrator/role_prompt.py`, ветка `role == "test_author"`) до
изменения: часть задания от «Роль: автор приёмочных тестов.» до «SPEC.md НЕ
трогай.» — ровно то, что меняет задача; хвост задания (строка knowledge,
рабочий каталог) — чужие абзацы, их тест не утверждает.

Провалидировано временным стабом реализации (удалён, не закоммичен):
ветка test_author при компоненте из `plank_rule(target).labelled_components()`
собирает пункт 2, строку запретов и пункты 3–4 с `//` по требованию 1 —
все методы файла зелёные.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import (brief, config, project_profile, review, role_prompt,
                          stack, store)
from tests.sandbox import TmpRootTest, artel_target_entry, make_project_repo

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
TASKS_DIR = "tasks"

ENTRY_HEAD = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

SLED_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: backend/tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [backend/tests/**/*.py]
      mutation_claim_scope: [backend/tests/test_*.py]
      report: junit-xml
      install: []
"""

BANS = ("В тексте планки запрещены `.fails`, `.skipIf`, `.runIf`, `.only`, "
        "`vi.setConfig`, ключи `retry`/`timeout` и числовой литерал в "
        "аргументах `it`/`test`/`describe`/`suite`.")


def ulid(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(CROCKFORD) for _ in range(24))


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


def component_entry(name: str, comp: str, fields: dict) -> str:
    text = ENTRY_HEAD.format(name=name, base=config.MAIN_BRANCH)
    text += f"    components:\n      {comp}:\n"
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            value = flow(value)
        text += f"        {key}: {value}\n"
    return text


class MissionSandbox(TmpRootTest):

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
        self.entries = {}
        self.write_targets()

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def write_targets(self) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry() + "".join(self.entries.values()),
            encoding="utf-8")

    def project(self, entry: str, name: str, clone: bool = True) -> str:
        self.entries[name] = entry
        self.write_targets()
        if clone:
            make_project_repo(name, origin=False)
        return name

    # ------------------------------------------------------------ проекты

    def sled(self) -> str:
        name = f"s{self.word()}"
        return self.project(ENTRY_HEAD.format(name=name, base=config.MAIN_BRANCH)
                            + SLED_PROFILE, name)

    def no_profile(self, clone: bool = True) -> str:
        """Запись без профиля тестов: `decide(target).profile is None`
        (с клоном — пропуск, без клона — отказ неразрешённого контекста)."""
        name = f"n{self.word()}"
        return self.project(ENTRY_HEAD.format(name=name, base=config.MAIN_BRANCH),
                            name, clone)

    def pytest_component(self) -> str:
        name = f"j{self.word()}"
        fields = {"command": ["python3", "-m", "pytest"],
                  "report": project_profile.REPORT_JUNIT,
                  "long_lived_dir": "backend/tests",
                  "long_lived_name": "test_<id>_<name>.py",
                  "weakening_scope": ["backend/tests/**"],
                  "mutation_claim_scope": ["backend/tests/**"],
                  "tests": ["backend/tests/test_*.py"]}
        return self.project(component_entry(name, f"c{self.word()}", fields), name)

    def masks(self, root: str) -> tuple:
        """Две-три маски `tests` со случайными последними сегментами."""
        exts = self.rng.sample(["js", "jsx", "ts", "tsx", "mjs"], 3)
        kinds = self.rng.sample(["test", "spec", "check"], 3)
        count = self.rng.choice((2, 3))
        dirs = [f"{root}/src/**", f"{root}/lib", f"{root}/**"]
        return tuple(f"{dirs[i]}/*.{kinds[i]}.{exts[i]}" for i in range(count))

    def labelled(self, kind: str, layout: bool) -> dict:
        """Проект с одним компонентом с меткой `AC-<n>: `: `pult-vitest`
        либо `junit-xml` с командой не pytest; `layout` — с
        `plank_layout`."""
        name = f"{kind[0]}{self.word()}"
        root = f"w{self.word(4)}"
        masks = self.masks(root)
        fields = {"command": (list(project_profile.VITEST_BASE_ARGV)
                              if kind == "vitest"
                              else [f"bin/run{self.word(4)}"]),
                  "report": (project_profile.REPORT_VITEST if kind == "vitest"
                             else project_profile.REPORT_JUNIT),
                  "long_lived_dir": f"{root}/src",
                  "long_lived_name": "<id>_<name>.test.js",
                  "weakening_scope": [f"{root}/**"],
                  "mutation_claim_scope": [f"{root}/**"],
                  "tests": list(masks)}
        if layout:
            fields["plank_layout"] = f"{root}/src/.p{self.word(5)}/<id>"
        self.project(component_entry(name, f"c{self.word()}", fields), name)
        return {"name": name, "masks": masks, "root": root,
                "layout": fields.get("plank_layout", "")}

    # ------------------------------------------------------------ задание

    def mission(self, target: str) -> tuple:
        """(задание test_author, id задачи, ветка) свежей задачи проекта."""
        task_id = ulid(self.rng)
        branch = f"task/{task_id.lower()}-{self.word()}"
        store.insert_task(self.conn, task_id, "Учебная задача", "tests_writing",
                          branch, target, config.DEFAULT_BUDGET_USD)
        t = store.get_task(self.conn, task_id)
        mission, _brief, _package = role_prompt.mission_brief_package(
            self.conn, task_id, t, "test_author", f"/tmp/cwd-{self.word()}")
        return mission, task_id, branch

    @staticmethod
    def pult() -> str:
        return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'}"

    def point_2a(self, task_id: str, directory: str, prefix: str) -> str:
        return (
            "2а) Долгоживущий файл (`Группа: долгоживущий`, "
            "skills/test-authoring.md) пиши не в каталог приёмочных "
            f"тестов, а в каталог {directory}/ кодовой ветки, с именем "
            f"{prefix}<имя>.py (<имя> — строчные латинские буквы, "
            f"цифры, подчёркивание). Существующие файлы {directory}/ не "
            "трогай — их правку, переименование и удаление, как и любую "
            f"другую правку вне {TASKS_DIR}/{task_id}/, пульт откатит; "
            "свои новые файлы с этим префиксом он сам закоммитит в ветку "
            "на чекпоинте шага.\n")

    def point_5(self, task_id: str, artel: bool, long_lived) -> str:
        """Пункт 5 эталона без завершающей точки; `long_lived` — (каталог,
        префикс) либо `None`."""
        ref = f"{TASKS_DIR}/{task_id}"
        if artel:
            return (f"5) Прогони планку командой пульта `plank-run` (абзац о "
                    f"каталоге документов ниже): она сама выложит черновик и "
                    f"выполнит `python3 -m pytest {ref}/acceptance_tests -p "
                    f"no:cacheprovider -p timeout -o "
                    f"timeout={stack.PER_TEST_TIMEOUT_SEC}`; долгоживущие "
                    f"файлы {long_lived[0]}/ — тем же pytest с теми же "
                    f"флагами по их путям из рабочего каталога")
        point = (f"5) Прогони планку командой пульта `{self.pult()} plank-run "
                 f"{task_id}` (абзац о каталоге документов ниже): она сама "
                 f"выложит черновик и прогонит его раннером проекта")
        if long_lived is not None:
            point += (f"; долгоживущие файлы {long_lived[0]}/ — той же "
                      f"командой по пути каждого файла: `{self.pult()} "
                      f"plank-run {task_id} {long_lived[1]}<имя>.py`")
        return point

    def old_mission(self, task_id: str, branch: str, artel: bool,
                    long_lived) -> str:
        """Эталон части задания test_author, снятый с кода пина."""
        ref = f"{TASKS_DIR}/{task_id}"
        note = ("" if long_lived is None
                else self.point_2a(task_id, long_lived[0], long_lived[1]))
        return (
            f"Роль: автор приёмочных тестов. Задача {task_id}, ветка "
            f"{branch} — уже выписана в этом рабочем каталоге "
            f"(собственный worktree задачи). Разработчик увидит задачу "
            f"только после тебя —\n"
            f"1) {ref}/SPEC.md на диске — актуальная версия "
            f"(материализована из артефактной ветки на старте шага). "
            f"Изучи раздел «Критерии приёмки» (AC-1, AC-2, …).\n"
            f"2) Для каждого AC-n напиши unittest в "
            f"{ref}/acceptance_tests/test_*.py, метод test_ac<n>_... — "
            f"ТОЛЬКО из формулировки критерия.\n"
            f"{note}"
            f"3) Критерий нельзя проверить тестом напрямую — пометь "
            f"`# AC-n: manual — <причина>` (Оператор проверит на приёмке) "
            f"или `# AC-n: skip — <причина>`.\n"
            f"4) Критерий в принципе неисполним тестом — не изобретай "
            f"компромисс: `# AC-n: escalate — <вопрос Оператору>`.\n"
            f"{self.point_5(task_id, artel, long_lived)}"
            f". tasks/<id>/ коммитить "
            f"не нужно — автокоммит оркестратора сам перенесёт написанное в "
            f"артефактную ветку. Остальной код репозитория и SPEC.md НЕ трогай."
        )

    def assert_old(self, target: str, artel: bool, long_lived_of) -> None:
        for _ in range(2):
            mission, task_id, branch = self.mission(target)
            low = task_id.lower()
            long_lived = (None if long_lived_of is None
                          else long_lived_of(low))
            expected = self.old_mission(task_id, branch, artel, long_lived)
            with self.subTest(target=target, task=task_id, seed=self.seed):
                self.assertTrue(
                    mission.startswith(expected + "\n\n"),
                    self.note(f"ожидалось начало:\n{expected}\n\n"
                              f"задание:\n{mission}"))


# ---------------------------------------------------------------- AC-1

class Ac1OldMissionTest(MissionSandbox):

    def test_ac1_artel_test_profile_and_pytest_component_unchanged(self):
        """Задание test_author у артели, записи `test_profile` и компонента `junit-xml` с командой pytest — побайтно эталон пина.

        Сценарий: на нескольких случайных задачах каждого из трёх видов
        проекта задание начинается ровно с эталона пина — пункт 2 «напиши
        unittest … метод test_ac<n>_...», пункт 2а с прежним каталогом и
        префиксом, пункты 3–4 с пометками `# AC-n: …`, пункт 5 ветки артели
        либо внешнего проекта, завершающая фраза — и дальше идёт пустая
        строка следующего абзаца.

        Ловит мутацию: признак взят не из `labelled_components()`, а из
        «у компонента есть маски `tests`» либо «запись `components:`» —
        pytest-компонент с масками получает Vitest-текст пункта 2; новая
        строка запретов добавлена безусловно — она есть и у артели;
        пометки `# AC-n` заменены на `//` для всех.
        """
        sled = self.sled()
        pytest_comp = self.pytest_component()
        with self.subTest(kind="artel"):
            self.assert_old(ARTEL, True,
                            lambda low: ("tests", f"tests/test_{low}_"))
        with self.subTest(kind="test_profile"):
            self.assert_old(sled, False, lambda low: (
                "backend/tests", f"backend/tests/test_{low}_"))
        with self.subTest(kind="junit-xml pytest"):
            self.assert_old(pytest_comp, False, lambda low: (
                "backend/tests", f"backend/tests/test_{low}_"))


# ---------------------------------------------------------------- AC-5

class Ac5UndefinedProfileMissionTest(MissionSandbox):

    def test_ac5_mission_unchanged_without_profile(self):
        """Задание test_author у задачи с неопределённым профилем — побайтно эталон пина, без исключения.

        Сценарий: запись проекта без профиля тестов с клоном (пропуск
        проверок) и такая же запись без клона (отказ неразрешённого
        контекста) — `decide(target).profile is None`; задание собирается
        без исключения и начинается ровно с эталона пина внешнего проекта
        без пункта 2а и без хвоста пункта 5 о долгоживущих файлах.

        Ловит мутацию: признак читается как `decide(target).profile.report`
        без проверки на `None` — сборка задания падает AttributeError;
        неопределённый профиль трактуется как «не pytest» — задание
        получает Vitest-текст.
        """
        for clone in (True, False):
            target = self.no_profile(clone)
            decision = project_profile.decide(target)
            with self.subTest(clone=clone, seed=self.seed):
                self.assertIsNone(decision.profile, self.note(
                    f"фикстура: у {target} есть профиль"))
                self.assert_old(target, False, None)


# ---------------------------------------------------------------- AC-2

class Ac2LabelledMissionTest(MissionSandbox):

    def point_2(self, task_id: str, masks, layout: str) -> str:
        segments = ", ".join(f"`{m.rsplit('/', 1)[-1]}`" for m in masks)
        text = (f"2) Для каждого AC-n напиши тест в {TASKS_DIR}/{task_id}/"
                f"acceptance_tests/ (без подкаталогов), имя файла — по маскам "
                f"{segments}; помощники — `_<имя>.<расширение>`. Имя теста "
                f"`it`/`test` начинается с `AC-<n>: `, одна метка на тест, "
                f"`describe` меткой не начинается — ТОЛЬКО из формулировки "
                f"критерия.")
        if layout:
            text += (f" На прогоне файлы лежат в "
                     f"`{layout.replace('<id>', task_id)}`: импорты кода пиши "
                     f"относительно этого каталога.")
        return text + "\n"

    def check_labelled(self, case: dict) -> None:
        mission, task_id, _branch = self.mission(case["name"])
        low = task_id.lower()
        directory = f"{case['root']}/src"
        context = self.note(f"проект {case}\nзадание:\n{mission}")
        rule = project_profile.plank_rule(case["name"])
        self.assertTrue(rule.labelled_components(), self.note(
            f"фикстура: компонент без метки AC-<n>: {case}"))
        self.assertIn(self.point_2(task_id, case["masks"], case["layout"]),
                      mission, context)
        self.assertNotIn("напиши unittest", mission, context)
        self.assertIn(BANS, mission, context)
        points = re.search(r"\n3\) (.*?)\n4\) (.*?)\n5\) ", mission, re.S)
        self.assertIsNotNone(points, context)
        both = points.group(1) + "\n" + points.group(2)
        self.assertIn("// AC-n: manual", both, context)
        self.assertIn("skip", both, context)
        self.assertIn("escalate", both, context)
        self.assertNotIn("# AC-n:", mission, context)
        self.assertIn(self.point_2a(task_id, directory, f"{directory}/{low}_"),
                      mission, context)
        self.assertIn(self.point_5(task_id, False, (directory,
                                                    f"{directory}/{low}_"))
                      + ". tasks/<id>/ коммитить", mission, context)
        if not case["layout"]:
            self.assertNotIn("На прогоне файлы лежат в", mission, context)

    def test_ac2_vitest_and_junit_non_pytest_mission_text(self):
        """Задание test_author у `pult-vitest` и у `junit-xml` с командой не pytest несёт текст требования 1 с подстановками.

        Сценарий: для каждого вида компонента на случайных масках `tests`
        (две-три, в случайном порядке записи) и случайном `plank_layout`
        пункт 2 задания совпадает с эталоном требования 1 дословно:
        последние сегменты масок в порядке записи, каждый в обратных
        кавычках через «, », `plank_layout` с `<id>`, заменённым id задачи
        как есть (верхний регистр); строка запретов — дословно; пункты 3–4
        несут пометки `// AC-n: …` с manual, skip и escalate, пометок
        `# AC-n:` нет; пункт 2а и пункт 5 — прежние тексты внешнего
        проекта.

        Ловит мутацию: маски выведены целиком, а не последним сегментом, или
        отсортированы; `<id>` заменён идентификатором в нижнем регистре;
        признак взят только по `report == pult-vitest` — у `junit-xml` с
        командой не pytest прежний текст unittest; пометки `#` не
        заменены на `//`; пункт 2а пропал при новом пункте 2.
        """
        for kind in ("vitest", "junit"):
            case = self.labelled(kind, layout=True)
            with self.subTest(kind=kind, seed=self.seed):
                self.check_labelled(case)

    def test_ac2_without_plank_layout_phrase_omitted(self):
        """У компонента с масками, командой не pytest и без `plank_layout` фразы о каталоге выкладки и импортах нет, остальной текст тот же.

        Сценарий: для `pult-vitest` и `junit-xml` с командой не pytest без
        поля `plank_layout` пункт 2 задания кончается на «— ТОЛЬКО из
        формулировки критерия.» и переводом строки; фразы «На прогоне
        файлы лежат в» нет нигде; строка запретов, пункты 3–4 с `//`,
        пункты 2а и 5 — как у компонента с `plank_layout`.

        Ловит мутацию: фраза собирается и при пустом `plank_layout` —
        в задании «На прогоне файлы лежат в ``»; без `plank_layout`
        выбирается прежний текст unittest.
        """
        for kind in ("vitest", "junit"):
            case = self.labelled(kind, layout=False)
            with self.subTest(kind=kind, seed=self.seed):
                self.check_labelled(case)


if __name__ == "__main__":
    unittest.main()
