"""Проект задачи: флаг `new --target`, однозначный выбор проекта и клон в `target-init`.

Группа: долгоживущий
Красен до реализации: `new` не знает флага `--target` (нераспознанный аргумент), не отказывает без флага при двух записях `targets.yaml`, читает ТЗ и строку «Проект:» не сверяет, при нечитаемом `targets.yaml` молчит о пропущенной сверке, а `target-init` клон проекта не заводит; отказ `target-init` неизвестному имени, вызов `catalog.cmd_new` без проекта при двух записях и отказ неизвестному проекту без ТЗ держат сегодняшнее поведение и зелёные с рождения.

Песочница — `tests.sandbox.InitializedTmpRootTest`: пути `config` во
временном каталоге, git — настоящий за подменой `subprocess.run`
(`SpyRun`), плотницкая запись ссылки документов подделана, её вызовы
(`update-ref refs/artifacts/…`) видны в журнале подмены. Внешний проект —
случайное имя; его bare-`origin` с первым коммитом заведён
`tests.sandbox.make_project_repo` и вынесен из каталога проекта, так что до
вызова клона проекта на диске нет. `targets.yaml` песочницы пишется
сценарием: одна запись артели, либо артель и внешний проект. Команда
строки — `artel.main` с подменённым `sys.argv`.

Провалидировано временным стабом реализации (удалён, не закоммичен) — все
методы зелёные.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import shutil
import sys
import unittest
from unittest import mock

from orchestrator import artel, catalog, config, projects, store, workspace
from tests.sandbox import (InitializedTmpRootTest, artel_target_entry,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
LETTERS = "abcdefghijklmnopqrstuvwxyz"

PROJECT_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

TZ_BODY = "Учебное ТЗ задачи {word}: поправить поведение команды.\n"


class ProjectSandbox(InitializedTmpRootTest):
    """Артель и внешний проект без клона; команды пульта и наблюдения."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()
        self.ext = "p" + self.word(7)
        make_project_repo(self.ext)
        remotes = self.root / "remotes"
        remotes.mkdir()
        shutil.move(str(projects.project_dir(self.ext)),
                    str(remotes / self.ext))
        self.origin = remotes / self.ext / "origin.git"
        self.title_no = 0
        self.write_targets(two=True)

    # ------------------------------------------------------------ фикстуры

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def write_targets(self, two: bool, url: str = None) -> None:
        """`targets.yaml` песочницы: запись артели и, если `two`, запись
        внешнего проекта с адресом `url` (по умолчанию — его `origin`)."""
        text = "targets:\n" + artel_target_entry()
        if two:
            text += PROJECT_ENTRY.format(
                name=self.ext, url=url or str(self.origin),
                base=config.MAIN_BRANCH)
        config.TARGETS.write_text(text, encoding="utf-8")

    def declared(self) -> list:
        return [ARTEL, self.ext]

    def title(self) -> str:
        self.title_no += 1
        return f"Задача {self.title_no}-{self.rng.randrange(10 ** 6)}"

    def tz(self, lines: list) -> str:
        """Путь файла ТЗ с телом и строками `lines` в начале строки."""
        path = self.root / ".artel" / f"tz-{self.word()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = [TZ_BODY.format(word=self.word())]
        for line in lines:
            body.insert(self.rng.randrange(len(body) + 1), line + "\n")
        path.write_text("# ТЗ\n\n" + "".join(body), encoding="utf-8")
        return str(path)

    # ------------------------------------------------------------- команды

    @staticmethod
    def run_fn(fn, *args, **kwargs) -> tuple:
        """(успех, вывод с текстом отказа, возврат) вызова `fn`."""
        buf = io.StringIO()
        ok, result = True, None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                result = fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    ok = False
                    buf.write(f"\n{exc.code}")
        return ok, buf.getvalue(), result

    def cli(self, *argv: str) -> tuple:
        """(успех, вывод с текстом отказа) команды `artel.py <argv>`."""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            ok, out, _ = self.run_fn(artel.main)
        return ok, out

    # ---------------------------------------------------------- наблюдения

    def task_ids(self) -> set:
        return {row["id"] for row in store.all_tasks(self.conn)}

    def task_by_title(self, title: str):
        rows = [row for row in store.all_tasks(self.conn)
                if row["title"] == title]
        return rows[0] if rows else None

    def docs_ref_writes(self) -> int:
        """Число записей ссылок документов задач (`update-ref
        refs/artifacts/…`) в журнале подмены git."""
        return sum(1 for call in self.git_spy.calls
                   if "update-ref" in call
                   and any(str(a).startswith("refs/artifacts/") for a in call))

    def clone_calls(self) -> int:
        return sum(1 for call in self.git_spy.calls
                   if call[:1] == ["git"] and "clone" in call)

    def clone_exists(self, name: str) -> bool:
        return workspace.repo(name).exists()

    def assert_nothing_created(self, before: set, refs: int, note: str,
                               project: str) -> None:
        """Ни строки задачи, ни ссылки документов, ни клона `project`."""
        self.assertEqual(self.task_ids(), before, self.note(
            f"появилась строка задачи: {note}"))
        self.assertEqual(self.docs_ref_writes(), refs, self.note(
            f"заведена ссылка документов: {note}"))
        self.assertFalse(self.clone_exists(project), self.note(
            f"появился клон {project}: {note}"))


class NewTargetFlagTest(ProjectSandbox):

    def test_ac1_target_flag_reaches_cmd_new_and_task_row(self):
        """`new <название> --target <проект>` заводит задачу этого проекта.

        Сценарий: `targets.yaml` — артель и внешний проект. Команда строки
        `new` с флагом `--target <внешний>` (флаг до или после `--tz`, с ТЗ
        и без — случайно): `catalog.cmd_new` получает `target=<внешний>`,
        строка заведённой задачи несёт `tasks.target = <внешний>`.

        Ловит мутацию: `_cmd_new` снимает флаг, но не передаёт его в
        `catalog.cmd_new` — вызов без `target`, задача заводится в artel (или
        при двух записях отказ «укажи проект»); значение флага передано
        позиционно на место `tz_path`, `target` остаётся `None`.
        """
        for case in range(2):
            title = self.title()
            pairs = [["--target", self.ext]]
            if self.rng.random() < 0.5:
                pairs.append(["--tz", self.tz([])])
            self.rng.shuffle(pairs)
            argv = ["new", title] + [a for pair in pairs for a in pair]
            with self.subTest(argv=argv), mock.patch.object(
                    catalog, "cmd_new", wraps=catalog.cmd_new) as spy:
                ok, out = self.cli(*argv)
                note = self.note(f"{argv}: {out}")
                self.assertTrue(ok, note)
                self.assertEqual(spy.call_count, 1, note)
                self.assertEqual(spy.call_args.kwargs.get("target"), self.ext,
                                 note)
                row = self.task_by_title(title)
                self.assertIsNotNone(row, note)
                self.assertEqual(row["target"], self.ext, note)

    def test_ac1_usage_and_cli_help_name_target_flag(self):
        """Справка `new` и общая справка CLI называют флаг `--target <имя>`.

        Сценарий: `new --help` печатает справку команды, `artel.py --help`
        — общую справку; в обеих есть подстрока `--target <имя>`.

        Ловит мутацию: флаг добавлен в разбор, но `_NEW_USAGE` или строка
        `new` общей справки его не называет — Оператор не узнаёт о флаге.
        """
        for argv in (["new", "--help"], ["--help"]):
            with self.subTest(argv=argv):
                ok, out = self.cli(*argv)
                self.assertTrue(ok, self.note(out))
                self.assertIn("--target <имя>", out, self.note(f"{argv}: {out}"))

    def test_ac1_target_flag_without_value_refused(self):
        """`new <название> --target` без значения — отказ, задача не заведена.

        Сценарий: флаг последним аргументом (с `--tz` перед ним и без) —
        выход с ненулевым кодом, новой строки задачи нет.

        Ловит мутацию: флаг без значения молча снимается и задача уходит в
        проект по умолчанию; значением берётся следующий флаг или индекс за
        концом argv роняет `IndexError` вместо отказа.
        """
        for with_tz in (False, True):
            title = self.title()
            argv = ["new", title] + (["--tz", self.tz([])] if with_tz else []) \
                + ["--target"]
            with self.subTest(argv=argv):
                before = self.task_ids()
                ok, out = self.cli(*argv)
                note = self.note(f"{argv}: {out}")
                self.assertFalse(ok, note)
                self.assertEqual(self.task_ids(), before, note)
                self.assertIsNone(self.task_by_title(title), note)


class UnknownProjectTest(ProjectSandbox):

    def test_ac2_unknown_target_refused_before_tz_and_clone(self):
        """`catalog.cmd_new` с необъявленным проектом отказывает до ТЗ и клона.

        Сценарий: случайное имя вне `targets.yaml`, вызов без ТЗ и с
        нечитаемым путём `--tz`: отказ, текст которого называет все
        объявленные проекты; `workspace.ensure_clone` не вызван, новой строки
        задачи, записи ссылки документов, git clone и каталога клона нет.

        Ловит мутацию: сверка проекта стоит после чтения ТЗ — при нечитаемом
        `--tz` отказ «ТЗ не прочитано» без перечня проектов; сверки нет
        вовсе и отказ приходит из `ensure_clone` (он вызван); перечень в
        отказе неполон.
        """
        for tz in (None, str(self.root / f"net-{self.word()}" / "tz.md")):
            unknown = "u" + self.word(7)
            with self.subTest(tz=tz, project=unknown), mock.patch.object(
                    workspace, "ensure_clone",
                    wraps=workspace.ensure_clone) as ensure:
                before, refs, clones = (self.task_ids(),
                                        self.docs_ref_writes(),
                                        self.clone_calls())
                ok, out, _ = self.run_fn(catalog.cmd_new, self.title(), tz,
                                         target=unknown)
                note = f"{unknown}, tz {tz}: {out}"
                self.assertFalse(ok, self.note(note))
                for name in self.declared():
                    self.assertIn(name, out, self.note(
                        f"отказ не называет {name}: {note}"))
                ensure.assert_not_called()
                self.assertEqual(self.clone_calls(), clones, self.note(note))
                self.assert_nothing_created(before, refs, note, unknown)


class ProjectChoiceTest(ProjectSandbox):

    def test_ac3_two_targets_new_without_flag_refused(self):
        """При двух записях `targets.yaml` `new` без `--target` отказывает.

        Сценарий: артель и внешний проект; `new <название>` (с ТЗ и без) —
        отказ с «--target» и именами обоих проектов, ни строки задачи, ни
        записи ссылки документов.

        Ловит мутацию: при нескольких записях `new` без флага молча
        заводит задачу в artel; отказ не перечисляет объявленные проекты;
        отказ наступает после заведения ссылки документов.
        """
        for with_tz in (False, True):
            title = self.title()
            argv = ["new", title] + (["--tz", self.tz([])] if with_tz else [])
            with self.subTest(argv=argv):
                before, refs = self.task_ids(), self.docs_ref_writes()
                ok, out = self.cli(*argv)
                note = self.note(f"{argv}: {out}")
                self.assertFalse(ok, note)
                self.assertIn("--target", out, note)
                for name in self.declared():
                    self.assertIn(name, out, note)
                self.assertEqual(self.task_ids(), before, note)
                self.assertEqual(self.docs_ref_writes(), refs, note)

    def test_ac3_single_target_new_without_flag_goes_to_artel(self):
        """При одной записи артели `new` без флага заводит задачу в artel.

        Сценарий: `targets.yaml` с одной записью `artel`; `new <название>`
        без `--target` — успех, `tasks.target = artel`.

        Ловит мутацию: правило обязательности проекта отказывает при любом
        числе записей (`>= 1` вместо `> 1`) — `new` без флага ломается на
        сегодняшнем пульте с одной артелью.
        """
        self.write_targets(two=False)
        title = self.title()
        ok, out = self.cli("new", title)
        note = self.note(out)
        self.assertTrue(ok, note)
        row = self.task_by_title(title)
        self.assertIsNotNone(row, note)
        self.assertEqual(row["target"], ARTEL, note)

    def test_ac4_cmd_new_without_target_stays_artel_with_two_targets(self):
        """Прямой `catalog.cmd_new` без проекта при двух записях — задача артели.

        Сценарий: артель и внешний проект в `targets.yaml`; вызовы
        `catalog.cmd_new(<название>)` и `catalog.cmd_new(<название>,
        canary=True)` (как из ведения канарейки) — успех, `tasks.target =
        artel`.

        Ловит мутацию: правило «укажи проект» перенесено в `catalog.cmd_new`
        — вызов без `target` (канарейка, прежние вызыватели) отказывает при
        двух записях.
        """
        for canary in (False, True):
            title = self.title()
            with self.subTest(canary=canary):
                ok, out, task_id = self.run_fn(catalog.cmd_new, title,
                                               canary=canary)
                note = self.note(f"canary={canary}: {out}")
                self.assertTrue(ok, note)
                row = store.get_task(self.conn, task_id)
                self.assertIsNotNone(row, note)
                self.assertEqual(row["target"], ARTEL, note)


class ProjectLineTest(ProjectSandbox):

    def test_ac5_project_line_mismatch_or_duplicate_refused_before_clone(self):
        """Строка ТЗ «Проект:» чужая или повторена — отказ до клона проекта.

        Сценарий: внешний проект без клона, `catalog.cmd_new(…, target=
        <внешний>)` с ТЗ: одна строка `Проект: <другой>`; две и более строк
        `Проект:` (совпадающие и разные). Каждый раз — отказ, после него ни
        строки задачи, ни записи ссылки документов, ни git clone, ни
        каталога клона проекта.

        Ловит мутацию: строка «Проект:» не сверяется — задача заводится;
        сверка стоит после `workspace.ensure_clone` — отказ есть, но клон
        проекта уже на диске; повтор строки не отказывает, берётся первая
        или последняя.
        """
        other = self.rng.choice([ARTEL, "o" + self.word(7)])
        cases = [
            ("чужая", [f"Проект: {other}"]),
            ("две совпадающие", [f"Проект: {self.ext}"] * 2),
            ("совпадающая и чужая", [f"Проект: {self.ext}", f"Проект: {other}"]),
            ("три", [f"Проект: {self.ext}"] * 3),
        ]
        self.rng.shuffle(cases)
        for name, lines in cases:
            with self.subTest(case=name, lines=lines):
                before, refs, clones = (self.task_ids(),
                                        self.docs_ref_writes(),
                                        self.clone_calls())
                ok, out, _ = self.run_fn(catalog.cmd_new, self.title(),
                                         self.tz(lines), target=self.ext)
                note = f"{name} {lines}: {out}"
                self.assertFalse(ok, self.note(note))
                self.assertEqual(self.clone_calls(), clones, self.note(note))
                self.assert_nothing_created(before, refs, note, self.ext)

    def test_ac5_matching_or_absent_project_line_and_canary_create_task(self):
        """Совпадающая строка «Проект:», её отсутствие и канарейка заводят задачу.

        Сценарий: внешний проект без клона; ТЗ с одной строкой `Проект:
        <внешний>`, ТЗ без строки и, с `canary=True`, ТЗ со строкой чужого
        проекта — `catalog.cmd_new(…, target=<внешний>)` заводит задачу с
        `tasks.target = <внешний>`.

        Ловит мутацию: отказ на любой строке «Проект:» (сверка с artel
        вместо проекта задачи); отсутствие строки считается ошибкой;
        канарейка разбирает строку «Проект:» и отказывает.
        """
        other = self.rng.choice([ARTEL, "o" + self.word(7)])
        cases = [("совпадающая", [f"Проект: {self.ext}"], False),
                 ("без строки", [], False),
                 ("канарейка, чужая", [f"Проект: {other}"], True)]
        self.rng.shuffle(cases)
        for name, lines, canary in cases:
            with self.subTest(case=name):
                ok, out, task_id = self.run_fn(
                    catalog.cmd_new, self.title(), self.tz(lines),
                    canary=canary, target=self.ext)
                note = self.note(f"{name} {lines}: {out}")
                self.assertTrue(ok, note)
                row = store.get_task(self.conn, task_id)
                self.assertIsNotNone(row, note)
                self.assertEqual(row["target"], self.ext, note)


class NewExternalOutputTest(ProjectSandbox):

    def test_ac6_new_external_prints_project_and_journals_it(self):
        """`new --target <внешний>` без клона заводит задачу и называет проект.

        Сценарий: внешний проект без клона; `new <название> --target
        <внешний>` — успех; вывод команды содержит имя проекта, запись
        журнала задачи с действием `created` — тоже.

        Ловит мутацию: флаг не доходит до `catalog.cmd_new` — задача в
        artel, вывод и запись `created` несут artel; вывод `new` перестал
        печатать проект задачи.
        """
        title = self.title()
        ok, out = self.cli("new", title, "--target", self.ext)
        note = self.note(out)
        self.assertTrue(ok, note)
        self.assertIn(self.ext, out, note)
        row = self.task_by_title(title)
        self.assertIsNotNone(row, note)
        created = [step for step in store.task_steps(self.conn, row["id"])
                   if step["action"] == "created"]
        self.assertTrue(created, note)
        texts = [" ".join(str(v) for v in dict(step).values())
                 for step in created]
        self.assertTrue([t for t in texts if self.ext in t],
                        self.note(f"записи created: {texts}; {out}"))


class TargetInitCloneTest(ProjectSandbox):

    def project_dirs_exist(self) -> bool:
        return all((projects.project_dir(self.ext) / sub).is_dir()
                   for sub in config.PROJECT_DIRS)

    def test_ac7_target_init_creates_dirs_and_clone_idempotently(self):
        """`target-init <внешний>` заводит каталоги и клон; повтор клон не трогает.

        Сценарий: внешний проект без клона; `projects.cmd_target_init` —
        каталоги проекта есть, `workspace.repo(<внешний>)` — git-репозиторий.
        В клон кладётся файл-метка; повторный вызов — без ошибки, git clone
        не вызывается, метка на месте.

        Ловит мутацию: `target-init` не вызывает `workspace.ensure_clone` —
        клона нет; повторный вызов пересоздаёт клон (метка пропала) или
        отказывает на существующем каталоге клона.
        """
        ok, out, _ = self.run_fn(projects.cmd_target_init, self.ext)
        self.assertTrue(ok, self.note(out))
        self.assertTrue(self.project_dirs_exist(), self.note(out))
        clone = workspace.repo(self.ext)
        self.assertTrue((clone / ".git").exists(), self.note(
            f"клон {clone} не заведён: {out}"))
        mark = clone / f"metka-{self.word()}.txt"
        mark.write_text(self.word(), encoding="utf-8")
        clones = self.clone_calls()

        ok, out, _ = self.run_fn(projects.cmd_target_init, self.ext)
        self.assertTrue(ok, self.note(f"повтор: {out}"))
        self.assertEqual(self.clone_calls(), clones, self.note(out))
        self.assertTrue(mark.is_file(), self.note(f"клон тронут: {out}"))

    def test_ac7_target_init_clone_failure_refused_with_reason(self):
        """Неудача клона в `target-init` — отказ с причиной, каталоги остаются.

        Сценарий: адрес внешнего проекта — несуществующий локальный путь со
        случайным именем; `projects.cmd_target_init` — ненулевой выход,
        текст отказа называет этот адрес (причину из `workspace.
        ensure_clone`), каталоги проекта на диске.

        Ловит мутацию: неудача клона проглатывается — `target-init`
        завершается успехом без клона; отказ без причины; при неудаче клона
        созданные каталоги проекта удаляются.
        """
        missing = self.root / f"net-{self.word(8)}" / "origin.git"
        self.write_targets(two=True, url=f"file://{missing}")
        ok, out, _ = self.run_fn(projects.cmd_target_init, self.ext)
        note = self.note(out)
        self.assertFalse(ok, note)
        self.assertIn(missing.parent.name, out, note)
        self.assertTrue(self.project_dirs_exist(), note)

    def test_ac8_target_init_unknown_name_creates_no_dirs(self):
        """`target-init` необъявленного имени — отказ без каталогов проекта.

        Сценарий: случайные имена вне `targets.yaml` — ненулевой выход,
        `projects.project_dir(<имя>)` не существует.

        Ловит мутацию: каталоги проекта создаются до сверки имени с
        `targets.yaml` (перестановка `init_project` выше сверки при
        добавлении клона) — отказ есть, а каталог-сирота остался.
        """
        for _ in range(2):
            unknown = "u" + self.word(7)
            with self.subTest(project=unknown):
                ok, out, _ = self.run_fn(projects.cmd_target_init, unknown)
                note = self.note(f"{unknown}: {out}")
                self.assertFalse(ok, note)
                self.assertFalse(projects.project_dir(unknown).exists(), note)


class UnreadableTargetsTest(ProjectSandbox):

    BROKEN = {
        "нет файла": None,
        "табуляция": "targets:\n  artel:\n\tforge: github\n",
        "не UTF-8": b"targets:\n  \xff\xfe:\n",
    }

    def break_targets(self, content) -> None:
        if content is None:
            config.TARGETS.unlink()
        elif isinstance(content, bytes):
            config.TARGETS.write_bytes(content)
        else:
            config.TARGETS.write_text(content, encoding="utf-8")

    def test_ac9_unreadable_targets_artel_task_created_with_warning(self):
        """Нечитаемый `targets.yaml` не мешает `new` задачи артели — с предупреждением.

        Сценарий: `targets.yaml` нет, либо он не разбирается; прямой вызов
        `catalog.cmd_new(<название>)` и команда строки `new <название>` без
        `--target` — успех, `tasks.target = artel`, вывод называет
        `targets.yaml` (предупреждение о пропущенной сверке проекта).

        Ловит мутацию: сверка проекта для артели требует читаемого
        `targets.yaml` — `new` задачи артели отказывает; правило «укажи
        проект» в командной строке отказывает при нечитаемом файле;
        пропуск сверки молчит, без предупреждения в выводе.
        """
        cases = [(kind, content, via)
                 for kind, content in self.BROKEN.items()
                 for via in ("cmd_new", "cli")]
        self.rng.shuffle(cases)
        for kind, content, via in cases:
            with self.subTest(targets=kind, via=via):
                self.write_targets(two=True)
                self.break_targets(content)
                title = self.title()
                if via == "cli":
                    ok, out = self.cli("new", title)
                else:
                    ok, out, _ = self.run_fn(catalog.cmd_new, title)
                note = self.note(f"{kind}, {via}: {out}")
                self.assertTrue(ok, note)
                row = self.task_by_title(title)
                self.assertIsNotNone(row, note)
                self.assertEqual(row["target"], ARTEL, note)
                self.assertIn(config.TARGETS.name, out, note)


if __name__ == "__main__":
    unittest.main()
