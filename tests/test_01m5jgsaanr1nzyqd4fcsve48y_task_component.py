"""Компонент задачи по зонам: `task_components`, `decide_task`, `for_task`, прежний отказ `decide` и зона-каталог.

Группа: долгоживущий
Красен до реализации: у `project_profile` нет `task_components` и `decide_task` — вызовы падают `AttributeError`; `for_task` зон не читает и у записи из нескольких компонентов отдаёт отказ `decide`; текст `targets.MULTI_COMPONENT_PENDING` — прежний «… исполняется после G1б».

Стенд — `tests.sandbox.RealGitSandbox`: пути `config` во временном
каталоге, `targets.yaml` песочницы несёт запись артели (`seed_artel_targets`)
и учебные записи сценария; клон внешнего проекта —
`tests.sandbox.make_project_repo` с bare `origin` (настоящий git: зона-каталог
сопоставляется по файлам репозитория на базе, AC-28). `for_task` получает
соединение sqlite в памяти с таблицей задач только из тех колонок, которые
сценарий заявляет (AC-5: у записи не из нескольких компонентов колонок зон
нет вовсе).

Учебная запись из нескольких компонентов строится из `random`: число
компонентов, их имена, каталоги `paths`, маски `test_support` и зависимости
`depends_on` вида `files` (потребитель зависит от каталога `seed/`
поставщика). Зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`task_components` по `paths`/`test_support` без `depends_on` с перечнем
`git ls-files` клона для зоны-каталога, `decide_task` поверх `decide` с
тремя отказами и профилем компонента через `with_tools`-поля, `for_task`,
читающий колонки зон только у записи из нескольких компонентов, — все методы
файла зелёные.
"""
import dataclasses
import random
import re
import shutil
import sqlite3
import string
from unittest import mock

from orchestrator import config, project_profile, repo_context, targets, zone_lock
from tests.sandbox import RealGitSandbox, make_project_repo

HEAD = """  {name}:
    forge: github
    url: https://localhost/artel-tests/{name}
    base: main
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

ALPHABET = string.ascii_lowercase
NOT_SET = ("зоны задачи не заданы — компонент задачи на записи из нескольких "
           "компонентов не выбран")
NOT_TOUCHED = "зоны задачи не задевают ни одного компонента записи"
SEVERAL = re.compile(r"задача затрагивает несколько компонентов \((.*?)\) — "
                     r"дели задачу по компонентам \(решение Оператора 20\.10\)")
NEW_PENDING = ("запись проекта с несколькими компонентами: профиль выбирается "
               "по зонам задачи")


def flow(items) -> str:
    return "[" + ", ".join(items) + "]"


class TaskComponentSandbox(RealGitSandbox):
    """Учебные записи `targets.yaml` и клон проекта; зерно случайных
    входов."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def word(self, size: int = 6) -> str:
        while True:
            value = "".join(self.rng.choice(ALPHABET) for _ in range(size))
            if value not in self.used:
                self.used.add(value)
                return value

    def append_entry(self, text: str) -> None:
        old = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(old.rstrip("\n") + "\n" + text,
                                  encoding="utf-8")

    @staticmethod
    def component_lines(comp: dict) -> list:
        lines = [f"      {comp['name']}:\n",
                 "        command: [python3, -m, pytest]\n",
                 "        report: junit-xml\n",
                 f"        weakening_scope: [{comp['dir']}/tests/**]\n",
                 f"        mutation_claim_scope: [{comp['dir']}/tests/test_*.py]\n",
                 f"        paths: [^{comp['dir']}/]\n",
                 f"        test_support: [{comp['support']}/**]\n"]
        if comp.get("pair", True):
            lines += [f"        long_lived_dir: {comp['dir']}/tests\n",
                      "        long_lived_name: test_<id>_<name>.py\n"]
        if comp.get("limit"):
            lines.append(f"        full_suite_timeout_sec: {comp['limit']}\n")
        if comp.get("depends"):
            lines.append("        depends_on:\n")
            for provider in comp["depends"]:
                lines += [f"          {provider['name']}:\n",
                          "            via: files\n",
                          f"            paths: [^{provider['dir']}/seed/]\n"]
        return lines

    def multi_record(self, count: int | None = None, *, pair: bool = True,
                     clone: bool = True):
        """Запись проекта из `count` (по умолчанию 2–4) компонентов;
        (имя проекта, список компонентов {name, dir, support, depends})."""
        count = count or self.rng.randint(2, 4)
        comps = []
        for i in range(count):
            comp = {"name": self.word(), "dir": self.word(5),
                    "support": self.word(5), "pair": pair,
                    "limit": self.rng.randint(30, 900)}
            if i and self.rng.random() < 0.7:
                comp["depends"] = [self.rng.choice(comps)]
            comps.append(comp)
        name = f"m{self.word()}"
        lines = [HEAD.format(name=name), "    components:\n"]
        for comp in comps:
            lines += self.component_lines(comp)
        self.append_entry("".join(lines))
        if clone:
            self.clone = make_project_repo(name)
        return name, comps

    def single_record(self, comp: dict) -> str:
        """Запись проекта из одного компонента `comp` (те же поля)."""
        name = f"s{self.word()}"
        lines = [HEAD.format(name=name), "    components:\n"]
        lines += self.component_lines(dict(comp, depends=None))
        self.append_entry("".join(lines))
        make_project_repo(name)
        return name

    def own_profile_record(self) -> str:
        name = f"t{self.word()}"
        self.append_entry(
            HEAD.format(name=name) + "    test_profile:\n"
            "      command: [python3, -m, pytest]\n"
            "      long_lived_dir: tests\n"
            "      long_lived_name: test_<id>_<name>.py\n"
            "      weakening_scope: [tests/**]\n"
            "      mutation_claim_scope: [tests/test_*.py]\n")
        make_project_repo(name)
        return name

    def file_in(self, comp: dict, support: bool = False) -> str:
        base = comp["support"] if support else comp["dir"]
        return f"{base}/{self.word(4)}/{self.word(5)}.py"

    def outside(self) -> str:
        return f"z{self.word(5)}/{self.word(4)}.py"

    def commit_clone(self, files: list) -> None:
        for rel in files:
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {rel}\n", encoding="utf-8")
        self.git("-C", str(self.clone), "add", "-A")
        self.git("-C", str(self.clone), "commit", "-q", "-m", "файлы проекта")
        self.git("-C", str(self.clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def same(self, got, expected, text: str) -> None:
        """Решения совпадают побайтно: и равенство, и полный `repr`
        (поля профиля вне сравнения тоже)."""
        self.assertEqual(got, expected, self.note(text))
        self.assertEqual(repr(got), repr(expected), self.note(text))


def task_conn(task_id: str, target: str, zones=None, extension=None, *,
              zone_columns: bool = True) -> sqlite3.Connection:
    """Соединение с одной строкой задачи; `zone_columns=False` — таблица
    без колонок `zones`/`zones_extension`."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    if zone_columns:
        conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, target TEXT, "
                     "zones TEXT, zones_extension TEXT)")
        conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?)",
                     (task_id, target, zones, extension))
    else:
        conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, target TEXT)")
        conn.execute("INSERT INTO tasks VALUES (?, ?)", (task_id, target))
    return conn


# ------------------------------------------------------------------ AC-1

class Ac1TaskComponentsTest(TaskComponentSandbox):

    def test_ac1_components_by_paths_and_support_in_record_order(self):
        """Компоненты, чьи `paths` или маски `test_support` задевают зону, — в порядке записи, без потребителей и без расширения путём вне компонентов.

        Сценарий: случайная запись из 2–4 компонентов, часть — потребители
        по `depends_on` вида `files` на каталог `seed/` поставщика.
        Несколько раундов: случайное подмножество компонентов задевается
        зоной-файлом под `paths` либо под маской `test_support`, в зоны
        подмешаны путь под `seed/` поставщика (задевает только поставщика:
        потребитель не добавляется) и иногда путь вне всех компонентов.
        Ожидание — ровно задетые компоненты в порядке записи.

        Ловит мутацию: выбор через `select_components`/`_touches` — путь
        под `seed/` добавляет потребителя, путь вне компонентов даёт все
        компоненты; маски `test_support` не читаются — компонент,
        задетый только ими, выпадает; порядок по зонам, а не по записи.
        """
        target, comps = self.multi_record(4)
        for round_ in range(12):
            chosen = [c for c in comps if self.rng.random() < 0.5] or \
                [self.rng.choice(comps)]
            zones = set()
            for comp in chosen:
                zones.add(self.file_in(comp, support=self.rng.random() < 0.5))
            providers = {d["name"] for c in comps for d in c.get("depends") or ()}
            seed_hits = [c for c in chosen if c["name"] in providers]
            for comp in seed_hits:
                zones.add(f"{comp['dir']}/seed/{self.word(4)}.py")
            if self.rng.random() < 0.5:
                zones.add(self.outside())
            expected = tuple(c["name"] for c in comps if c in chosen)
            got = project_profile.task_components(target, zones)
            self.assertEqual(tuple(got), expected, self.note(
                f"раунд {round_}: зоны {sorted(zones)}"))

    def test_ac1_seed_path_selects_provider_only(self):
        """Зона под `seed/` поставщика выбирает только поставщика: потребитель по `depends_on` в кортеж не входит.

        Сценарий: запись из двух компонентов, второй зависит от первого по
        `files` на `<каталог первого>/seed/`. Зона — один файл под `seed/`.

        Ловит мутацию: выбор с зависимостями `depends_on` (как у
        `select_components`) — в кортеже и потребитель.
        """
        for _ in range(3):
            target, comps = self.multi_record(2, clone=False)
            comps[1]["depends"] = [comps[0]]
            # Запись выше могла собраться без зависимости — перепишем её.
            lines = [HEAD.format(name=target), "    components:\n"]
            for comp in comps:
                lines += self.component_lines(comp)
            text = config.TARGETS.read_text(encoding="utf-8")
            start = text.index(f"  {target}:\n")
            config.TARGETS.write_text(text[:start] + "".join(lines),
                                      encoding="utf-8")
            make_project_repo(target)
            zone = f"{comps[0]['dir']}/seed/{self.word(4)}.py"
            self.assertEqual(
                tuple(project_profile.task_components(target, {zone})),
                (comps[0]["name"],), self.note(f"зона {zone}"))


# ------------------------------------------------------------------ AC-2

class Ac2DecideTaskEqualsDecideTest(TaskComponentSandbox):

    def random_zones(self) -> set:
        zones = {self.outside() for _ in range(self.rng.randint(0, 3))}
        zones |= {f"tests/{self.word(4)}.py" for _ in range(self.rng.randint(0, 2))}
        return zones

    def test_ac2_non_multi_records_return_decide_as_is(self):
        """У артели, `test_profile`, записи из одного компонента и неразрешённого проекта `decide_task` побайтно равен `decide` при любых зонах.

        Сценарий: четыре проекта, по каждому несколько случайных наборов
        зон (пустой, вне компонентов, совпадающий с путями компонента);
        решение `decide_task` сверяется с `decide` равенством и `repr`.

        Ловит мутацию: зоны читаются и у записи из одного компонента —
        зоны вне компонента дают отказ «не задевают»; у неразрешённого
        проекта отказ заменён текстом выбора компонента.
        """
        _multi, comps = self.multi_record(2, clone=False)
        single = self.single_record(comps[0])
        own = self.own_profile_record()
        missing = f"x{self.word()}"
        for target in (config.DEFAULT_TARGET, own, single, missing):
            for zones in (set(), self.random_zones(),
                          {self.file_in(comps[0])}, {self.file_in(comps[1])}):
                with self.subTest(target=target, zones=sorted(zones)):
                    self.same(project_profile.decide_task(target, zones),
                              project_profile.decide(target),
                              f"проект {target}, зоны {sorted(zones)}")

    def test_ac2_targets_error_and_patched_decide_pass_through(self):
        """Непригодный `targets.yaml` и подменённый в тесте `decide` проходят через `decide_task` как есть.

        Сценарий 1: `targets.yaml` испорчен — исход `decide_task` (решение
        либо исключение `TargetsError` с текстом) тот же, что у `decide`.
        Сценарий 2: `decide` подменён и отдаёт решение-маркер для проекта
        без записи — `decide_task` возвращает тот же объект при любых
        зонах.

        Ловит мутацию: `decide_task` сам перечитывает запись до `decide` —
        исключение `TargetsError` вместо решения `decide`; подменённый
        `decide` обходится собственным разбором записи — маркер теряется.
        """
        broken = f"y{self.word()}"
        config.TARGETS.write_text("targets: [не, запись\n", encoding="utf-8")
        zones = self.random_zones()
        try:
            expected = project_profile.decide(broken)
        except targets.TargetsError as exc:
            with self.assertRaises(targets.TargetsError, msg=self.note()) as got:
                project_profile.decide_task(broken, zones)
            self.assertEqual(str(got.exception), str(exc), self.note())
        else:
            self.same(project_profile.decide_task(broken, zones), expected,
                      "испорченный targets.yaml")
        marker = project_profile.Decision(f"p{self.word()}",
                                          refusal=f"маркер {self.word()}")
        with mock.patch.object(project_profile, "decide", return_value=marker):
            for zones in (set(), self.random_zones()):
                got = project_profile.decide_task(marker.target, zones)
                self.assertIs(got, marker, self.note(f"зоны {sorted(zones)}"))


# ------------------------------------------------------------------ AC-3

class Ac3RefusalTextsTest(TaskComponentSandbox):

    def test_ac3_three_refusals_carry_decide_reason(self):
        """Три отказа записи из нескольких компонентов: зоны не заданы, не задевают ни одного, задевают несколько — каждый с причиной `decide` дословно.

        Сценарий: случайная запись из 3–4 компонентов. (1) пустые зоны;
        (2) зоны только вне компонентов; (3) зоны в 2+ случайных
        компонентах — имена в скобках ровно задетые. Профиля нет, отказ
        содержит причину `decide(target)`.

        Ловит мутацию: пустые зоны дают отказ «не задевают» (или все
        компоненты); путь вне компонентов расширяет выбор; в скобках
        перечислены все компоненты записи, а не задетые; причина `decide`
        не дописана к тексту отказа.
        """
        target, comps = self.multi_record(self.rng.randint(3, 4))
        reason = project_profile.decide(target).refusal
        self.assertTrue(reason, self.note("decide записи без отказа"))
        cases = [(set(), NOT_SET),
                 ({self.outside() for _ in range(self.rng.randint(1, 3))},
                  NOT_TOUCHED)]
        for case in cases:
            zones, text = case
            got = project_profile.decide_task(target, zones)
            self.assertIsNone(got.profile, self.note(f"зоны {sorted(zones)}"))
            self.assertIn(text, got.refusal, self.note(f"зоны {sorted(zones)}"))
            self.assertIn(reason, got.refusal, self.note(f"зоны {sorted(zones)}"))
        for _ in range(4):
            touched = self.rng.sample(comps, self.rng.randint(2, len(comps) - 1))
            zones = {self.file_in(c, support=self.rng.random() < 0.5)
                     for c in touched}
            got = project_profile.decide_task(target, zones)
            self.assertIsNone(got.profile, self.note(f"зоны {sorted(zones)}"))
            match = SEVERAL.search(got.refusal)
            self.assertIsNotNone(match, self.note(got.refusal))
            named = match.group(1)
            for comp in comps:
                if comp in touched:
                    self.assertIn(comp["name"], named, self.note(got.refusal))
                else:
                    self.assertNotIn(comp["name"], named, self.note(got.refusal))
            self.assertIn(reason, got.refusal, self.note(got.refusal))


# ------------------------------------------------------------------ AC-4

class Ac4SingleComponentProfileTest(TaskComponentSandbox):

    def test_ac4_profile_matches_single_component_record(self):
        """Зоны в одном компоненте — профиль этого компонента с полями, как у записи из одного этого компонента.

        Сценарий: случайная запись из 2–4 компонентов и для выбранного
        компонента — отдельная запись из него одного с теми же полями.
        Каждое поле профиля `decide_task` (кроме имени проекта) равно полю
        профиля `decide` записи из одного компонента; имя компонента —
        выбранное.

        Ловит мутацию: профиль собран `component_profiles` без проверки
        подполей или не тем компонентом (первым по записи); пропущены поля
        компонента (`test_support`, `paths`, предел набора) — поле
        расходится с профилем записи из одного компонента.
        """
        target, comps = self.multi_record()
        for comp in self.rng.sample(comps, min(2, len(comps))):
            single = self.single_record(comp)
            expected = project_profile.decide(single).profile
            self.assertIsNotNone(expected, self.note(
                project_profile.decide(single).refusal))
            zones = {self.file_in(comp), self.file_in(comp, support=True)}
            got = project_profile.decide_task(target, zones)
            self.assertIsNotNone(got.profile, self.note(got.refusal))
            self.assertFalse(got.refusal, self.note(got.refusal))
            self.assertEqual(got.profile.component, comp["name"], self.note())
            for field in dataclasses.fields(project_profile.Profile):
                if field.name == "project":
                    continue
                self.assertEqual(getattr(got.profile, field.name),
                                 getattr(expected, field.name),
                                 self.note(f"поле {field.name}"))

    def test_ac4_missing_required_subfield_names_component(self):
        """Задетый компонент без обязательного подполя профиля (пары `long_lived_dir`/`long_lived_name`) — отказ, называющий компонент.

        Сценарий: запись из нескольких компонентов без пары долгоживущих
        у всех компонентов (запись из нескольких компонентов это
        допускает); зоны в одном случайном компоненте.

        Ловит мутацию: обязательные подполя не проверяются — профиль с
        пустыми `long_lived_dir`/`long_lived_name` вместо отказа; отказ без
        имени компонента.
        """
        target, comps = self.multi_record(pair=False)
        comp = self.rng.choice(comps)
        got = project_profile.decide_task(target, {self.file_in(comp)})
        self.assertIsNone(got.profile, self.note())
        self.assertTrue(got.refusal, self.note())
        self.assertIn(comp["name"], got.refusal, self.note(got.refusal))


# ------------------------------------------------------------------ AC-5

class Ac5ForTaskTest(TaskComponentSandbox):

    def test_ac5_for_task_reads_zones_of_multi_record(self):
        """`for_task` равен `decide_task(<проект>, task_zone_paths(<строка>))`: зоны и расширение зон строки задачи выбирают компонент.

        Сценарий: запись из нескольких компонентов, строки задачи с зонами
        в одном компоненте — в `zones`, только в `zones_extension`, в двух
        компонентах (одна зона в каждой колонке), без зон.

        Ловит мутацию: `for_task` остаётся `decide(target)` — отказ
        записи вместо профиля компонента; расширение зон не читается —
        задача с зоной только в `zones_extension` получает отказ «не
        заданы».
        """
        target, comps = self.multi_record()
        a, b = self.rng.sample(comps, 2)
        rows = [(self.file_in(a), None), (None, self.file_in(b)),
                (self.file_in(a), self.file_in(b)), (None, None)]
        for zones, extension in rows:
            task_id = f"T{self.word(8).upper()}"
            conn = task_conn(task_id, target, zones, extension)
            row = conn.execute("SELECT * FROM tasks").fetchone()
            expected = project_profile.decide_task(
                target, zone_lock.task_zone_paths(row))
            self.same(project_profile.for_task(conn, task_id), expected,
                      f"zones={zones}, extension={extension}")
        conn = task_conn("TONE", target, self.file_in(a))
        got = project_profile.for_task(conn, "TONE")
        self.assertIsNotNone(got.profile, self.note(got.refusal))
        self.assertEqual(got.profile.component, a["name"], self.note())

    def test_ac5_other_records_need_no_zone_columns(self):
        """У артели, `test_profile` и записи из одного компонента `for_task` работает с таблицей задач без колонок зон и равен `decide`.

        Сценарий: таблица задач из колонок `id`, `target`; для каждого
        проекта `for_task` сверяется с `decide` побайтно.

        Ловит мутацию: колонки зон читаются для любой записи — `for_task`
        падает `IndexError`/`OperationalError` на таблице без `zones`.
        """
        _multi, comps = self.multi_record(2, clone=False)
        for target in (config.DEFAULT_TARGET, self.own_profile_record(),
                       self.single_record(comps[0]), f"x{self.word()}"):
            task_id = f"T{self.word(8).upper()}"
            conn = task_conn(task_id, target, zone_columns=False)
            self.same(project_profile.for_task(conn, task_id),
                      project_profile.decide(target), f"проект {target}")


# ------------------------------------------------------------------ AC-6

class Ac6DecideKeepsRefusalTest(TaskComponentSandbox):

    def test_ac6_decide_and_profile_of_refuse_with_new_text(self):
        """`decide` и `profile_of` записи из нескольких компонентов без задачи — прежний отказ с новым текстом `MULTI_COMPONENT_PENDING`.

        Сценарий: случайные записи из 2–4 компонентов. `profile_of` — не
        прочитан, признак `multi`, причина — константа; `decide` — отказ
        прежней формы «профиль тестов проекта «…» не прочитан (поле
        components …): <константа>», профиля нет.

        Ловит мутацию: `decide` у записи из нескольких компонентов
        выбирает компонент сам (первый) — профиль вместо отказа; текст
        константы оставлен прежним «… исполняется после G1б».
        """
        self.assertEqual(targets.MULTI_COMPONENT_PENDING, NEW_PENDING)
        for _ in range(3):
            target, _comps = self.multi_record(clone=False)
            answer = repo_context.profile_of(target)
            self.assertEqual(answer.outcome, repo_context.PROFILE_UNREAD,
                             self.note())
            self.assertTrue(answer.multi, self.note())
            self.assertEqual(answer.reason, NEW_PENDING, self.note())
            got = project_profile.decide(target)
            self.assertIsNone(got.profile, self.note())
            self.assertEqual(got.refusal, (
                f"профиль тестов проекта «{target}» не прочитан (поле "
                f"{targets.COMPONENTS_FIELD} записи в targets.yaml): "
                f"{NEW_PENDING}"), self.note())


# ------------------------------------------------------------------ AC-28

class Ac28DirectoryZoneTest(TaskComponentSandbox):

    def test_ac28_directory_zone_matches_by_repository_files(self):
        """Зона-каталог задевает компонент по файлам репозитория на базе под ним, сама строка каталога не сопоставляется.

        Сценарий: запись из нескольких компонентов, `paths` — `^<каталог>/`;
        в клоне на базе закоммичены файлы под `<каталог компонента>/<x>/`.
        Зона-каталог верхнего уровня `<x>/` с файлом
        `<x>/<каталог компонента>/…` (его путь `paths` `^…` не
        сопоставляется) компонент не задевает; зона-каталог
        `<каталог компонента>/<x>/` с файлами задевает (строка каталога сама
        тоже совпала бы — поэтому есть и третий случай); зона-каталог
        `<каталог>/<пусто>/` без файлов — не задевает; зона-файл
        несуществующего файла сопоставляется сама.

        Ловит мутацию: зона-каталог сопоставляется строкой как есть —
        каталог без файлов задевает компонент; перечень файлов не читается —
        каталог верхнего уровня с файлами под чужим префиксом даёт
        компонент.
        """
        target, comps = self.multi_record(3)
        comp = self.rng.choice(comps)
        inner = f"{comp['dir']}/{self.word(4)}"
        stray_top = self.word(5)
        files = [f"{inner}/{self.word(5)}.py",
                 f"{stray_top}/{comp['dir']}/{self.word(5)}.py"]
        self.commit_clone(files)
        self.assertEqual(
            tuple(project_profile.task_components(target, {f"{inner}/"})),
            (comp["name"],), self.note(f"каталог {inner}/"))
        self.assertEqual(
            tuple(project_profile.task_components(target, {f"{stray_top}/"})),
            (), self.note(f"каталог {stray_top}/"))
        empty = f"{comp['dir']}/{self.word(4)}/"
        self.assertEqual(
            tuple(project_profile.task_components(target, {empty})),
            (), self.note(f"каталог без файлов {empty}"))
        new_file = f"{comp['dir']}/{self.word(4)}/{self.word(5)}.py"
        self.assertEqual(
            tuple(project_profile.task_components(target, {new_file})),
            (comp["name"],), self.note(f"зона-файл {new_file}"))

    def test_ac28_directory_selected_by_file_matching_paths_only(self):
        """Каталог, строка которого не соответствует `paths`, задевает компонент по файлу под ним, сопоставленному только с `paths`.

        Сценарий: у компонента `paths` — `\\.jsx$` (по расширению файла)
        и маска `test_support` в другом каталоге; в клоне — файл
        `<каталог>/<x>.jsx`. Зона `<каталог>/` даёт ровно этот компонент;
        `decide_task` на этих зонах — профиль компонента.

        Ловит мутацию: зона-каталог сопоставляется своей строкой — `\\.jsx$`
        к `<каталог>/` не подходит, выбор пуст и отказ «не задевают».
        """
        name = f"m{self.word()}"
        front, back = self.word(), self.word()
        top = self.word(5)
        self.append_entry(
            HEAD.format(name=name) + "    components:\n"
            f"      {back}:\n"
            "        command: [python3, -m, pytest]\n"
            f"        weakening_scope: [{back}/tests/**]\n"
            f"        mutation_claim_scope: [{back}/tests/test_*.py]\n"
            f"        paths: [^{back}/]\n"
            f"        long_lived_dir: {back}/tests\n"
            "        long_lived_name: test_<id>_<name>.py\n"
            f"      {front}:\n"
            "        command: [python3, -m, pytest]\n"
            f"        weakening_scope: [{top}/**]\n"
            f"        mutation_claim_scope: [{top}/**]\n"
            "        paths: [\\.jsx$]\n"
            f"        test_support: [s{self.word(4)}/**]\n"
            f"        long_lived_dir: {top}/tests\n"
            "        long_lived_name: test_<id>_<name>.py\n")
        self.clone = make_project_repo(name)
        self.commit_clone([f"{top}/{self.word(5)}.jsx"])
        self.assertEqual(
            tuple(project_profile.task_components(name, {f"{top}/"})),
            (front,), self.note(f"каталог {top}/"))
        got = project_profile.decide_task(name, {f"{top}/"})
        self.assertIsNotNone(got.profile, self.note(got.refusal))
        self.assertEqual(got.profile.component, front, self.note())

    def test_ac28_listing_failure_refuses_decide_task(self):
        """Сбой получения перечня файлов для зоны-каталога — отказ `decide_task`, не пустой выбор и не выбор компонента.

        Сценарий: клон проекта удалён (git перечня не отвечает); зоны —
        каталог компонента и файл того же компонента. Решение — отказ без
        профиля, не текст «не задевают ни одного компонента».

        Ловит мутацию: сбой `git ls-files` читается как пустой перечень —
        каталог отбрасывается, зона-файл выбирает компонент (профиль
        вместо отказа) либо выбор пуст (отказ «не задевают»).
        """
        target, comps = self.multi_record()
        comp = self.rng.choice(comps)
        directory = f"{comp['dir']}/{self.word(4)}"
        self.commit_clone([f"{directory}/{self.word(5)}.py"])
        shutil.rmtree(repo_context.clone_path(target))
        for zones in ({f"{directory}/"},
                      {f"{directory}/", self.file_in(comp)}):
            got = project_profile.decide_task(target, zones)
            self.assertIsNone(got.profile, self.note(f"зоны {sorted(zones)}"))
            self.assertTrue(got.refusal, self.note(f"зоны {sorted(zones)}"))
            self.assertNotIn(NOT_TOUCHED, got.refusal, self.note(got.refusal))
