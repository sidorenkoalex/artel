"""Механическая проверка ТЗ в `new`: ссылки `файл:строка` и вызывающие вне зон.

Группа: долгоживущий
Красен до реализации: `new` не проверяет ссылки `файл:строка` и вызывающих по дереву проекта, не печатает строку «проверка ТЗ: N отказов, M предупреждений» и не знает флага `--strict-tz` (нераспознанный аргумент); методы о прежнем выводе без ссылок и имён, о канарейке и `spawn_subtask`, о не-ссылках `host/api:8080` и о путях в кавычках держат сегодняшнее поведение и зелёные с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): корень —
главная копия артели (он же её клон) с bare `origin`; внешний проект —
клон с bare `origin` (`tests.sandbox.make_project_repo`), его база в
`targets.yaml` песочницы — ветка со случайным именем, не `main`. Учебные
файлы (модули-определители в зоне ТЗ, модули-вызывающие вне её, текстовые
файлы со строками) коммитятся в HEAD главной копии или в `origin/<base>`
клона. ТЗ — файл под игнорируемым `.artel/` песочницы. Команда —
`artel.main` с подменённым `sys.argv` (`new <название> --tz <файл>
--target <проект> [--strict-tz]`); канарейка и деление — `catalog.cmd_new(
canary=True)` и `catalog.spawn_subtask`. Недоступное дерево артели —
вторая песочница `tests.sandbox.InitializedTmpRootTest`, где корень — не
git-репозиторий.

Наблюдается: вывод команды (строка «проверка ТЗ: …», sha в ней, находки),
строки задач в БД, ссылки документов `refs/artifacts/…` в git главной
копии и клона (в лёгкой песочнице — записи `update-ref` в журнале подмены
git) и записи журнала задачи с действием «проверка ТЗ».

Провалидировано временным стабом реализации (удалён, не закоммичен) — все
методы зелёные.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, catalog, config, store
from scripts import guard
from tests.sandbox import (InitializedTmpRootTest, RealGitSandbox,
                           artel_target_entry, capture, make_project_repo)

ARTEL = config.DEFAULT_TARGET
LETTERS = "abcdefghijklmnopqrstuvwxyz"
HEADER_RE = re.compile(
    r"^проверка ТЗ: (\d+) отказ\w*, (\d+) предупрежден\w*")
SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
CHECK_ACTION = "проверка ТЗ"
CALLERS_WARNING = "в зонах нет вызывающих"
AMBIGUOUS = "имя файла неоднозначно — не проверено"
COMMON_MARK = "общее имя — не проверено"
TREE_UNAVAILABLE = "дерево недоступно — проверка ТЗ не выполнена:"
STRICT = "--strict-tz"
COMMON_NAMES = ("run", "main", "load", "get", "set", "check", "parse", "cmd",
                "new")
# Расширения, по которым содержимое кавычек — путь (требование 4.4), —
# короткое случайное имя не должно совпасть ни с одним из них.
PATH_EXTENSIONS = ("py", "md", "yaml", "yml", "json", "toml", "txt", "sh",
                   "js", "jsx", "ts", "tsx", "cfg", "ini", "lock", "gitignore")
NEW_CHECK_TEXTS = (CHECK_ACTION, CALLERS_WARNING, AMBIGUOUS, COMMON_MARK,
                   "дерево недоступно")

PROJECT_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class TzCheckHelpers:
    """Фикстуры и наблюдения, общие для обеих песочниц файла."""

    def start_rng(self) -> None:
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used_words = set()
        self.title_no = 0
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

    def word(self, size: int = 7) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used_words:
                self.used_words.add(text)
                return text

    def ident(self, prefix: str = "f") -> str:
        """Случайное имя функции: длиннее 4 знаков, не общее."""
        return prefix + self.word(8)

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def title(self) -> str:
        self.title_no += 1
        return f"Задача {self.title_no}-{self.rng.randrange(10 ** 6)}"

    def write_tz(self, body: list, zones: list, extra: list = ()) -> str:
        """Путь файла ТЗ: строки `body` до «Зоны:», затем «Зоны:» и
        разделы `extra` (каждый — отдельный абзац)."""
        text = f"# ТЗ учебной задачи {self.word()}\n\n" + "\n".join(body)
        text += "\n\nЗоны: " + ", ".join(zones) + "\n"
        for section in extra:
            text += "\n" + section + "\n"
        path = self.root / ".artel" / f"tz-{self.word()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

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
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            ok, out, _ = self.run_fn(artel.main)
        return ok, out

    def new(self, title: str, tz: str, target: str,
            strict: bool = False) -> tuple:
        """(успех, вывод) `new <title> --tz <tz> --target <target>`; флаг
        `--strict-tz` — в случайном месте argv."""
        argv = ["new", title, "--tz", tz, "--target", target]
        if strict:
            argv.insert(self.rng.choice((2, 4, 6)), STRICT)
        return self.cli(*argv)

    @staticmethod
    def header(out: str):
        """(N, M, строка) строки «проверка ТЗ: …» вывода либо None."""
        for line in out.splitlines():
            match = HEADER_RE.match(line.strip())
            if match:
                return int(match.group(1)), int(match.group(2)), line
        return None

    @staticmethod
    def first_line(out: str) -> str:
        lines = [line for line in out.splitlines() if line.strip()]
        return lines[0].strip() if lines else ""

    @staticmethod
    def place_in(text: str, path: str, line: int) -> bool:
        """`path:line` стоит в `text` отдельным местом (не `:12` у `:1`)."""
        return re.search(r"(?<![\w./-])" + re.escape(f"{path}:{line}")
                         + r"(?!\d)", text) is not None

    def task_ids(self) -> set:
        return {row["id"] for row in store.all_tasks(store.db())}

    def task_by_title(self, title: str):
        rows = [row for row in store.all_tasks(store.db())
                if row["title"] == title]
        return rows[0] if rows else None

    def check_journal(self, title: str) -> list:
        """detail записей журнала задачи `title` с действием «проверка ТЗ»."""
        row = self.task_by_title(title)
        if row is None:
            return []
        return [step["detail"] or "" for step in store.task_steps(
            store.db(), row["id"]) if step["action"] == CHECK_ACTION]


class TzCheckSandbox(TzCheckHelpers, RealGitSandbox):
    """Главная копия артели и клон внешнего проекта с базой не `main`."""

    def setUp(self):
        super().setUp()
        self.start_rng()
        self.add_synced_origin()
        self.ext = "p" + self.word(7)
        self.clone = make_project_repo(self.ext)
        self.origin_bare = config.PROJECTS / self.ext / "origin.git"
        self.base = "rel" + self.word(5)
        self.pgit("branch", self.base, config.MAIN_BRANCH)
        self.pgit("push", "-q", "origin", self.base)
        self.write_targets(self.base)
        capture(catalog.cmd_init)
        self.zone = "z" + self.word(6)

    def write_targets(self, base: str, extra: str = "") -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + PROJECT_ENTRY.format(name=self.ext, url=str(self.origin_bare),
                                   base=base) + extra, encoding="utf-8")

    def pgit(self, *args: str) -> str:
        return self.git("-C", str(self.clone), *args)

    def root_commit(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "--", *files)
        self.git("commit", "-q", "-m", "учебные файлы")

    def project_commit(self, branch: str, files: dict) -> None:
        self.pgit("checkout", "-q", branch)
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.pgit("add", "--", *files)
        self.pgit("commit", "-q", "-m", "учебные файлы")
        self.pgit("push", "-q", "origin", branch)
        self.pgit("checkout", "-q", config.MAIN_BRANCH)

    def head_sha(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def project_base_sha(self) -> str:
        return self.pgit("rev-parse", f"origin/{self.base}").strip()

    def docs_refs(self) -> set:
        refs = set()
        for repo in (self.root, self.clone):
            out = self.git("-C", str(repo), "for-each-ref",
                           "--format=%(refname)", "refs/artifacts/")
            refs |= {f"{repo}:{ref}" for ref in out.split()}
        return refs

    def lines_file(self, size: int, marks: dict = None) -> str:
        """Текст из `size` строк-заполнителей; `marks` — {номер строки:
        слово}, слово стоит в этой строке."""
        marks = marks or {}
        return "".join(
            f"строка {i} {marks[i]}\n" if i in marks else f"строка {i}\n"
            for i in range(1, size + 1))

    def py_lines_file(self, size: int, marks: dict = None) -> str:
        marks = marks or {}
        return "".join(
            f"# строка {i} {marks[i]}\n" if i in marks else f"# строка {i}\n"
            for i in range(1, size + 1))

    def assert_refused_without_traces(self, title: str, out: str, ok: bool,
                                      before: set, refs: set,
                                      note: str) -> None:
        self.assertFalse(ok, note)
        self.assertIsNone(self.task_by_title(title), note)
        self.assertEqual(self.task_ids(), before, note)
        self.assertEqual(self.docs_refs(), refs, note)


class RefsTest(TzCheckSandbox):

    def test_ac1_missing_file_ref_refuses_with_header_and_no_traces(self):
        """Ссылка на файл, которого нет в дереве, — отказ без следов в БД и git.

        Сценарий: ТЗ артели или внешнего проекта (случайно) со ссылкой
        `каталог/файл.<расш>:N` на несуществующий файл — `*.py` и не-`*.py`,
        в обратных кавычках и без. `new` отказывает; первая непустая строка
        вывода — «проверка ТЗ: N отказов, M предупреждений» с N ≥ 1 и sha
        проверенного коммита (HEAD главной копии либо `origin/<base>`
        клона); ссылка названа в выводе; строки задачи и ссылки документов
        нет.

        Ловит мутацию: проверяются только `*.py` — ссылка на `.md` проходит;
        ссылка вне кавычек не распознаётся; отказ стоит после
        `_new_task_row` — строка задачи и ссылка документов появляются;
        строка «проверка ТЗ» печатается после текста отказа или без sha.
        """
        cases = [("py", True), ("md", False), (self.rng.choice(
            ("yaml", "txt", "json")), self.rng.random() < 0.5)]
        for ext, quoted in cases:
            target = self.rng.choice((ARTEL, self.ext))
            path = f"{self.zone}/{self.word()}/{self.word()}.{ext}"
            ref = f"{path}:{self.rng.randint(1, 60)}"
            shown = f"`{ref}`" if quoted else ref
            with self.subTest(ext=ext, quoted=quoted, target=target):
                tz = self.write_tz([f"Поправить поведение, см. {shown} и "
                                    f"соседей."], [f"{self.zone}/"])
                before, refs, title = self.task_ids(), self.docs_refs(), \
                    self.title()
                ok, out = self.new(title, tz, target)
                note = self.note(f"{target} {shown}: {out}")
                self.assert_refused_without_traces(title, out, ok, before,
                                                   refs, note)
                first = self.first_line(out)
                match = HEADER_RE.match(first)
                self.assertIsNotNone(match, note)
                self.assertGreaterEqual(int(match.group(1)), 1, note)
                sha = (self.head_sha() if target == ARTEL
                       else self.project_base_sha())
                self.assertIn(sha, first, note)
                self.assertIn(ref, out, note)

    def test_ac1_host_and_branch_texts_are_not_refs(self):
        """Тексты без расширения в последней части пути — не ссылки.

        Сценарий: ТЗ артели с `host/api:8080`, `origin/main:12` и
        случайными `слово/слово:N` — в обратных кавычках и без. `new`
        заводит задачу, строки «проверка ТЗ» нет, тексты в выводе не
        названы.

        Ловит мутацию: грамматика ссылки не требует расширения — `host/api`
        ищется в дереве и даёт отказ «файла нет».
        """
        texts = ["host/api:8080", "origin/main:12",
                 f"{self.word()}/{self.word()}:{self.rng.randint(1, 99)}"]
        body = []
        for text in texts:
            body.append(f"Адрес `{text}` и {text} в прозе.")
        tz = self.write_tz(body, [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, self.rng.choice((ARTEL, self.ext)))
        note = self.note(out)
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        self.assertNotIn(CHECK_ACTION, out, note)
        for text in texts:
            self.assertNotIn(text, out, note)

    def test_ac2_refs_past_end_refused_all_at_once(self):
        """Строка или верхняя граница диапазона за концом файла — отказ, все ссылки разом.

        Сценарий: три закоммиченных файла разных видов (`.py`, `.md`,
        `.yaml`) длиной L₁…L₃. ТЗ несёт ссылки `f1:L₁+k`, `f2:a-(L₂+k)` с
        `a ≤ L₂` и верные `f3:L₃`, `f1:1-L₁`. `new` отказывает без строки
        задачи и ссылки документов; обе неверные ссылки названы, верные —
        нет. Второе ТЗ — только верные граничные ссылки — заводит задачу.

        Ловит мутацию: у диапазона сверяется только граница `a`; отказ
        называет первую неверную ссылку и прекращается; длина считается с
        ошибкой на единицу — `:L` последней строки даёт отказ.
        """
        exts = ["py", "md", "yaml"]
        self.rng.shuffle(exts)
        files, sizes = {}, []
        for ext in exts:
            size = self.rng.randint(5, 30)
            path = f"{self.zone}/{self.word()}.{ext}"
            files[path] = (self.py_lines_file(size) if ext == "py"
                           else self.lines_file(size))
            sizes.append((path, size))
        self.root_commit(files)
        (f1, l1), (f2, l2), (f3, l3) = sizes
        bad = [f"{f1}:{l1 + self.rng.randint(1, 5)}",
               f"{f2}:{self.rng.randint(1, l2)}-{l2 + self.rng.randint(1, 5)}"]
        good = [f"{f3}:{l3}", f"{f1}:1-{l1}"]
        refs_text = bad + good
        self.rng.shuffle(refs_text)
        tz = self.write_tz([f"Ссылка {ref} в тексте." for ref in refs_text],
                           [f"{self.zone}/"])
        before, refs, title = self.task_ids(), self.docs_refs(), self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assert_refused_without_traces(title, out, ok, before, refs, note)
        for ref in bad:
            self.assertIn(ref, out, note)
        for ref in good:
            self.assertNotIn(ref, out, note)

        tz = self.write_tz([f"Ссылка {ref} в тексте." for ref in good],
                           [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        self.assertTrue(ok, self.note(f"верные границы: {out}"))
        self.assertIsNotNone(self.task_by_title(title), self.note(out))

    def test_ac3_bare_file_name_refs(self):
        """Ссылка без каталога: однозначное имя проверяется, двойное — предупреждение, отсутствующее — не ссылка.

        Сценарий: в дереве файл `uniq.md` в одном каталоге (L строк) и
        `amb.txt` в двух каталогах. ТЗ с `uniq.md:L` заводит задачу; ТЗ с
        `uniq.md:L+k` отказывает и называет ссылку; ТЗ с `amb.txt:N` при N
        за концом обоих файлов заводит задачу с предупреждением «имя
        файла неоднозначно — не проверено»; ТЗ с `нет.md:3` — задача без
        строки «проверка ТЗ».

        Ловит мутацию: неоднозначное имя проверяется по первому найденному
        файлу (отказ за концом); имя без каталога вовсе не распознаётся
        (нет отказа по `uniq.md:L+k`); отсутствующее имя даёт отказ «файла
        нет».
        """
        uniq, amb, absent = (f"{self.word()}.md", f"{self.word()}.txt",
                             f"{self.word()}.md")
        size = self.rng.randint(5, 20)
        self.root_commit({
            f"{self.zone}/{self.word()}/{uniq}": self.lines_file(size),
            f"{self.zone}/{self.word()}/{amb}": self.lines_file(4),
            f"{self.zone}/{self.word()}/{amb}": self.lines_file(6),
        })

        def run(ref: str) -> tuple:
            shown = f"`{ref}`" if self.rng.random() < 0.5 else ref
            tz = self.write_tz([f"Поправить, см. {shown} рядом."],
                               [f"{self.zone}/"])
            title = self.title()
            ok, out = self.new(title, tz, ARTEL)
            return ok, out, title

        ok, out, title = run(f"{uniq}:{size}")
        self.assertTrue(ok, self.note(f"верная однозначная: {out}"))

        bad = f"{uniq}:{size + self.rng.randint(1, 5)}"
        before, refs = self.task_ids(), self.docs_refs()
        ok, out, title = run(bad)
        note = self.note(f"неверная однозначная: {out}")
        self.assert_refused_without_traces(title, out, ok, before, refs, note)
        self.assertIn(bad, out, note)

        ok, out, title = run(f"{amb}:{self.rng.randint(7, 40)}")
        note = self.note(f"неоднозначная: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        self.assertIn(AMBIGUOUS, out, note)

        ok, out, title = run(f"{absent}:3")
        note = self.note(f"отсутствующая: {out}")
        self.assertTrue(ok, note)
        self.assertNotIn(CHECK_ACTION, out, note)

    def test_ac4_name_near_ref_checked_in_window(self):
        """Имя рядом со ссылкой сверяется с окном ±3 своей ссылки, в том числе в не-`*.py` файле.

        Сценарий: текстовый файл (`.md`/`.txt`/`.yaml` — случайно) и `.py`
        файл по 40 строк, слова-имена расставлены по строкам. Первое ТЗ —
        только «найденные»: имя в строке `N+3` и `N-3` для `:N`, в `b+3`
        для `:a-b`, имя после второй ссылки строки — в окне второй, имя
        `модуль.имя` — последняя часть в окне; `new` заводит задачу без
        строки «проверка ТЗ». Второе ТЗ — только «ненайденные»: имя в
        `N+4`, `N-4`, `b+4`, имя второй ссылки — лишь в окне первой, имя в
        `N+4` у `.py` файла; каждое имя названо в выводе, предупреждений
        не меньше числа таких имён, задача заводится.

        Ловит мутацию: окно ±2 или ±4; окно диапазона считается от `a`, а
        не до `b+3`; имя второй ссылки сверяется с окном первой; сверка
        окна только у `*.py` либо только у не-`*.py`.
        """
        text_ext = self.rng.choice(("md", "txt", "yaml"))
        doc = f"{self.zone}/{self.word()}.{text_ext}"
        pydoc = f"{self.zone}/{self.word()}.py"
        n = self.rng.randint(10, 15)
        a, b = n + 5, n + self.rng.randint(7, 9)
        n2 = b + 8
        names = {key: self.ident("n") for key in (
            "up3", "down3", "range3", "second", "dotted", "up4", "down4",
            "range4", "second_wrong", "py4", "first")}
        marks = {n + 3: names["up3"], n - 3: names["down3"],
                 b + 3: names["range3"], n2 + 2: names["second"],
                 n2 - 1: names["dotted"], n + 4: names["up4"],
                 n - 4: names["down4"], b + 4: names["range4"],
                 n + 1: names["second_wrong"] + " " + names["first"]}
        self.root_commit({doc: self.lines_file(40, marks),
                          pydoc: self.py_lines_file(40, {n + 4: names["py4"]})})
        found = [
            f"См. {doc}:{n} `{names['up3']}` и дальше.",
            f"См. `{doc}:{n}` про `{names['down3']}`.",
            f"См. {doc}:{a}-{b} `{names['range3']}`.",
            f"См. {doc}:{n} `{names['first']}`, затем {doc}:{n2} "
            f"`{names['second']}`.",
            f"См. {doc}:{n2} `{self.word()}.{names['dotted']}`.",
        ]
        missing = [
            (names["up4"], f"См. {doc}:{n} `{names['up4']}`."),
            (names["down4"], f"См. {doc}:{n} `{names['down4']}`."),
            (names["range4"], f"См. {doc}:{a}-{b} `{names['range4']}`."),
            (names["second_wrong"],
             f"См. {doc}:{n} `{names['first']}`, затем {doc}:{n2} "
             f"`{names['second_wrong']}`."),
            (names["py4"], f"См. {pydoc}:{n} `{names['py4']}`."),
        ]
        tz = self.write_tz(found, [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(f"найденные: {out}")
        self.assertTrue(ok, note)
        self.assertNotIn(CHECK_ACTION, out, note)

        tz = self.write_tz([line for _name, line in missing], [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(f"ненайденные: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        head = self.header(out)
        self.assertIsNotNone(head, note)
        self.assertGreaterEqual(head[1], len(missing), note)
        for name, _line in missing:
            self.assertIn(name, out, note)


class CallersTest(TzCheckSandbox):

    def callers_line(self, out: str, name: str) -> str:
        lines = [line for line in out.splitlines()
                 if CALLERS_WARNING in line and name in line]
        return "\n".join(lines)

    def test_ac5_named_function_called_outside_zones_warns(self):
        """Функция `модуль.функция` или `Класс.метод` до «Зоны:» с вызывающим вне зон — предупреждение с местом вызова.

        Сценарий: модуль-определитель вне зон с `def f(…)` и классом с
        методом; вызывающие вне зон: `mod.f(1)`, обратный вызов `h =
        mod.f` (форма `.имя` без скобок), `K().m()`; строка с `x_f(2)` (имя
        не целым словом). ТЗ называет `` `mod.f` `` и `` `K.m` `` до «Зоны:».
        `new` заводит задачу; предупреждение «в зонах нет вызывающих …»
        называет места `mod.f(1)`, `h = mod.f` и `K().m()`; места `x_f(2)` и
        строки `def f(`/`def m(` определителя в выводе нет.

        Ловит мутацию: поиск подстрокой — `x_f(` засчитан вызывающим;
        форма `.имя` выпала — обратный вызов без скобок пропущен; строка
        `def f(` определителя попала в вызывающие; кандидаты `Класс.метод`
        не берутся.
        """
        lib, callers = "l" + self.word(6), "c" + self.word(6)
        mod, fn = self.ident("m"), self.ident("f")
        klass, meth = "K" + self.word(7), self.ident("m")
        definer = f"{lib}/{mod}.py"
        definer_text = (f'"""Определитель."""\n\n\ndef {fn}(value):\n'
                        f"    return value\n\n\nclass {klass}:\n"
                        f"    def {meth}(self):\n        return 1\n")
        def_lines = [i + 1 for i, line in enumerate(definer_text.splitlines())
                     if line.lstrip().startswith("def ")]
        call_file = f"{callers}/{self.word()}.py"
        call_text = (f"def use(obj, {mod}):\n"
                     f"    return {mod}.{fn}(1)\n"
                     f"\n"
                     f"handler = {mod}.{fn}\n"
                     f"value = {klass}().{meth}()\n")
        noise_file = f"{callers}/{self.word()}.py"
        noise_text = (f"def x_{fn}(value):\n    return value\n\n\n"
                      f"result = x_{fn}(2)\n")
        self.root_commit({definer: definer_text, call_file: call_text,
                          noise_file: noise_text})
        tz = self.write_tz([f"Поправить `{mod}.{fn}` и `{klass}.{meth}` в "
                            f"поведении."], [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        head = self.header(out)
        self.assertIsNotNone(head, note)
        self.assertGreaterEqual(head[1], 1, note)
        fn_line = self.callers_line(out, fn)
        for line in (2, 4):
            self.assertTrue(self.place_in(fn_line, call_file, line), note)
        self.assertTrue(self.place_in(self.callers_line(out, meth),
                                      call_file, 5), note)
        self.assertNotIn(noise_file, out, note)
        for line in def_lines:
            self.assertFalse(self.place_in(out, definer, line), note)

    def test_ac6_ref_lines_give_enclosing_definitions(self):
        """Ссылка `файл.py:N` даёт кандидатом объемлющее определение по отступу; диапазон — все начатые в нём плюс объемлющее `a`; строка модуля — ничего.

        Сценарий: модуль в зоне: функция `alpha` (ссылка — на строку её
        тела), класс `K` с методом `m1` и строкой тела класса с отступом 4
        после `m1` (ссылка — на неё), функция `delta` и следующие за ней
        `beta`, `gamma` (диапазон — от строки тела `delta` до строки тела
        `gamma`), функция `eps` и константа модуля ниже неё (ссылка — на
        константу). У каждого определения — вызывающий вне зон отдельной
        строкой. `new` заводит задачу; в выводе есть места вызова
        `alpha`, `K`, `delta`, `beta`, `gamma` и нет мест вызова `m1` и
        `eps`.

        Ловит мутацию: кандидат — ближайшее `def` выше строки без сверки
        отступа (`m1` вместо `K`; `eps` у константы модуля); у диапазона
        нет объемлющего определения строки `a` (`delta` пропал); диапазон
        даёт только одно определение; кандидат берётся лишь из строки
        `def` ровно на `N` (тело функции кандидата не даёт).
        """
        mod = self.ident("m")
        names = {key: self.ident(key[0]) for key in (
            "alpha", "m1", "delta", "beta", "gamma", "eps")}
        names["klass"] = "K" + self.word(7)
        marker, const = "v" + self.word(7), "C" + self.word(7).upper()
        lines = ['"""Учебный модуль."""', "", ""]

        def add(text: str) -> int:
            lines.append(text)
            return len(lines)

        add(f"def {names['alpha']}(value):")
        ref_body = add("    total = value + 1")
        add("    return total")
        add(""), add("")
        add(f"class {names['klass']}:")
        add(f"    def {names['m1']}(self):")
        add("        return 1")
        add("")
        ref_class = add(f"    {marker} = 2")
        add(""), add("")
        add(f"def {names['delta']}(value):")
        range_a = add("    inner = value * 2")
        add("    return inner")
        add(""), add("")
        add(f"def {names['beta']}():")
        add("    return 3")
        add(""), add("")
        add(f"def {names['gamma']}():")
        range_b = add("    return 4")
        add(""), add("")
        add(f"def {names['eps']}():")
        add("    return 5")
        add(""), add("")
        ref_const = add(f"{const} = 7")
        definer = f"{self.zone}/{mod}.py"

        order = ["alpha", "klass", "m1", "delta", "beta", "gamma", "eps"]
        self.rng.shuffle(order)
        call_lines, call_text = {}, ["def use(obj, mod):"]
        for key in order:
            call = (f"    obj.{names[key]}()" if key == "m1"
                    else f"    mod.{names[key]}()")
            call_text.append(call)
            call_lines[key] = len(call_text)
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({definer: "\n".join(lines) + "\n",
                          call_file: "\n".join(call_text) + "\n"})
        refs = [f"{definer}:{ref_body}", f"{definer}:{ref_class}",
                f"{definer}:{range_a}-{range_b}", f"{definer}:{ref_const}"]
        self.rng.shuffle(refs)
        tz = self.write_tz([f"Поправить поведение, см. {ref}." for ref in refs],
                           [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        for key in ("alpha", "klass", "delta", "beta", "gamma"):
            self.assertTrue(self.place_in(out, call_file, call_lines[key]),
                            self.note(f"нет вызывающего {key}: {out}"))
        for key in ("m1", "eps"):
            self.assertFalse(self.place_in(out, call_file, call_lines[key]),
                             self.note(f"лишний вызывающий {key}: {out}"))

    def test_ac7_names_at_or_below_labels_are_not_candidates(self):
        """Имя на строке метки «Зоны:»/«Не входит»/«Только чтение…»/«Приложением» или ниже неё — не кандидат.

        Сценарий: для каждой из четырёх меток — ТЗ, у которого первая
        строка-метка — эта метка с `` `mod.f1` `` на ней же, а `` `mod.f2` ``
        стоит абзацем ниже; до метки имён нет. У `f1` и `f2` есть
        вызывающие вне зон. `new` заводит задачу; строки «проверка ТЗ» и
        мест вызова в выводе нет.

        Ловит мутацию: кандидаты собираются из всего текста ТЗ; граница —
        только «Зоны:», а «Не входит»/«Только чтение (…)»/«Приложением»
        её не ставят; строка самой метки ещё считается текстом до неё.
        """
        mod = self.ident("m")
        labels = ["Не входит:", "Только чтение (не менять):", "Приложением:"]
        cases = []
        call_text = ["def use(mod):"]
        for label in ["Зоны:"] + labels:
            f1, f2 = self.ident("f"), self.ident("g")
            call_text += [f"    mod.{f1}(1)", f"    mod.{f2}(2)"]
            cases.append((label, f1, f2))
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({call_file: "\n".join(call_text) + "\n"})
        for label, f1, f2 in cases:
            with self.subTest(label=label):
                body = "Поправить поведение команды без имён."
                if label == "Зоны:":
                    text = (f"# ТЗ {self.word()}\n\n{body}\n\n"
                            f"Зоны: {self.zone}/ (`{mod}.{f1}`)\n\n"
                            f"Ещё про `{mod}.{f2}` ниже.\n")
                else:
                    text = (f"# ТЗ {self.word()}\n\n{body}\n\n"
                            f"{label} `{mod}.{f1}` правка.\n\n"
                            f"Ещё про `{mod}.{f2}` ниже.\n\n"
                            f"Зоны: {self.zone}/\n")
                path = self.root / ".artel" / f"tz-{self.word()}.md"
                path.write_text(text, encoding="utf-8")
                title = self.title()
                ok, out = self.new(title, str(path), ARTEL)
                note = self.note(f"{label}: {out}")
                self.assertTrue(ok, note)
                self.assertNotIn(CHECK_ACTION, out, note)
                self.assertNotIn(call_file, out, note)

    def test_ac7_paths_in_backticks_are_neither_candidates_nor_near_names(self):
        """Путь в обратных кавычках — не кандидат и не «имя рядом».

        Сценарий: до «Зоны:» строки вида «см. `doc.md:N` и `<путь>`» с
        путями `` `targets.yaml` ``, `` `QUESTIONS.md` ``,
        `` `orchestrator/<имя>.py` `` и `` `<имя>.<имя2>` `` — последний
        существует в дереве файлом. В строках файла по ссылке этих путей
        нет; в дереве есть вызывающие `.yaml`, `.md`, `.<имя2>(` вне зон.
        `new` заводит задачу; строки «проверка ТЗ», пометок «общее имя» и
        предупреждений нет.

        Ловит мутацию: содержимое кавычек с расширением из списка
        считается именем — `targets.yaml` даёт кандидата `yaml` (его
        вызывающий — предупреждение) или «имя рядом» не в окне; `QUESTIONS.md`
        даёт пометку «общее имя» по `md`; имя, существующее в дереве
        файлом, не распознано как путь.
        """
        doc = f"{self.zone}/{self.word()}.md"
        stem, tail = self.word(), self.word(8)
        file_name = f"{stem}.{tail}"
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({
            doc: self.lines_file(12),
            file_name: "учебный файл\n",
            call_file: (f"def use(cfg):\n    data = cfg.yaml\n"
                        f"    text = cfg.md\n    return cfg.{tail}(1)\n"),
        })
        paths = ["targets.yaml", "QUESTIONS.md",
                 f"orchestrator/{self.word()}.py", file_name]
        self.rng.shuffle(paths)
        body = [f"См. `{doc}:{i + 2}` и `{path}` рядом."
                for i, path in enumerate(paths)]
        tz = self.write_tz(body, [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        self.assertNotIn(CHECK_ACTION, out, note)
        self.assertNotIn(COMMON_MARK, out, note)
        self.assertNotIn(call_file, out, note)

    def test_ac8_covered_or_declared_callers_do_not_warn(self):
        """Вызывающий в «Зонах» (вложенно), в `config.COMMON_ZONES` или названный в объявляющих разделах — без предупреждения.

        Сценарий: функция `mod.f` названа до «Зоны:»; вызывающие —
        в подкаталоге зоны-каталога, в файле под общей зоной (из
        `config.COMMON_ZONES`, кроме `tests/`), в файлах, названных в
        «Только чтение (не менять):», «Не входит:» и «Приложением:», и
        контрольный — нигде не названный. `new` заводит задачу;
        предупреждение называет только контрольного вызывающего.

        Ловит мутацию: зона-каталог покрывает только файлы прямо в нём
        (без вложенности); `config.COMMON_ZONES` не учтён; не учтён один
        из разделов «Только чтение»/«Не входит»/«Приложением».
        """
        mod, fn = self.ident("m"), self.ident("f")
        call = f"def use(mod):\n    return mod.{fn}(1)\n"
        zone_dir = "y" + self.word(6)
        covered = {"вложенно": f"{zone_dir}/{self.word()}/{self.word()}.py"}
        common = [z for z in config.COMMON_ZONES
                  if z.endswith(".py") and not z.startswith("tests/")]
        common += [f"{z}{self.word()}.py" for z in config.COMMON_ZONES
                   if z.endswith("/") and z != "tests/"]
        if common:
            covered["общая зона"] = self.rng.choice(common)
        declared = {label: f"d{self.word(6)}/{self.word()}.py"
                    for label in ("Только чтение (не менять):", "Не входит:",
                                  "Приложением:")}
        control = f"u{self.word(6)}/{self.word()}.py"
        files = {path: call for path in
                 list(covered.values()) + list(declared.values()) + [control]}
        self.root_commit(files)
        extra = [f"{label} {path}" for label, path in declared.items()]
        self.rng.shuffle(extra)
        tz = self.write_tz([f"Поправить `{mod}.{fn}`."],
                           [f"{self.zone}/", f"{zone_dir}/"], extra)
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        self.assertTrue(self.place_in(out, control, 2), note)
        for kind, path in list(covered.items()) + list(declared.items()):
            self.assertNotIn(path, out, self.note(f"{kind} {path}: {out}"))

    def test_ac9_tests_callers_ignored_and_list_cut_at_twenty(self):
        """Вызывающие из `tests/` не учитываются; больше 20 мест — 20 в предупреждении и остаток числом.

        Сценарий: общие зоны сужены до записей, не покрывающих `tests/`
        (иначе исключение `tests/` неотличимо от общей зоны). Функция
        `mod.f` названа до «Зоны:»; 20+k (k — случайное 1…9) строк вызова
        вне зон в трёх файлах и два вызова в `tests/`. В предупреждении о
        `f` — ровно 20 мест из вне-зонных, мест из `tests/` нет, число k
        стоит отдельным числом.

        Ловит мутацию: `tests/` не исключён — его места в перечне или в
        остатке (k+2); срез не на 20; остаток не печатается.
        """
        mod, fn = self.ident("m"), self.ident("f")
        extra_count = self.rng.randint(1, 9)
        total = 20 + extra_count
        places, files = [], {}
        per_file = [total // 3, total // 3, total - 2 * (total // 3)]
        for count in per_file:
            path = f"u{self.word(6)}/{self.word()}.py"
            text = ["def use(mod):"]
            for i in range(count):
                text.append(f"    mod.{fn}({i})")
                places.append((path, len(text)))
            files[path] = "\n".join(text) + "\n"
        tests_files = [f"tests/{self.word()}.py",
                       f"tests/{self.word()}/{self.word()}.py"]
        for path in tests_files:
            files[path] = f"def use(mod):\n    return mod.{fn}(1)\n"
        self.root_commit(files)
        narrowed = tuple(z for z in config.COMMON_ZONES
                         if not any(t == z or (z.endswith("/") and t.startswith(z))
                                    for t in tests_files))
        tz = self.write_tz([f"Поправить `{mod}.{fn}`."], [f"{self.zone}/"])
        title = self.title()
        with mock.patch.object(config, "COMMON_ZONES", narrowed):
            ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        line = "\n".join(ln for ln in out.splitlines()
                          if CALLERS_WARNING in ln and fn in ln)
        self.assertTrue(line, note)
        listed = [p for p in places if self.place_in(line, *p)]
        self.assertEqual(len(listed), 20, note)
        for path in tests_files:
            self.assertNotIn(path, out, note)
        rest = line
        for path, number in listed:
            rest = rest.replace(f"{path}:{number}", "")
        self.assertRegex(rest, rf"(?<!\d){extra_count}(?!\d)", note)

    def test_ac10_common_and_short_names_marked_not_searched(self):
        """Общее и короткое имя — отдельная пометка «общее имя — не проверено», без поиска и вне счёта M.

        Сценарий: до «Зоны:» — `` `mod.<общее>` `` (случайное из списка
        требования 5.3) и `` `mod.<короткое>` `` (2–3 буквы); у обоих есть
        вызывающие вне зон. Без `--strict-tz` и с ним `new` заводит
        задачу; строка «проверка ТЗ: 0 отказов, 0 предупреждений»; строк
        пометки — по одной на имя; предупреждения о вызывающих и мест
        вызова нет; в журнале задачи запись «проверка ТЗ» с пометкой.

        Ловит мутацию: общее или короткое имя ищется (предупреждение с
        местом вызова); пометка входит в M; под `--strict-tz` пометка —
        отказ; пометка не пишется в журнал.
        """
        mod = self.ident("m")
        common = self.rng.choice(COMMON_NAMES)
        while True:
            short = self.word(self.rng.randint(2, 3))
            if short not in COMMON_NAMES and short not in PATH_EXTENSIONS:
                break
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({call_file: (f"def use(mod):\n    mod.{common}(1)\n"
                                      f"    mod.{short}(2)\n")})
        for strict in (False, True):
            with self.subTest(strict=strict):
                tz = self.write_tz([f"Поправить `{mod}.{common}` и "
                                    f"`{mod}.{short}`."], [f"{self.zone}/"])
                title = self.title()
                ok, out = self.new(title, tz, ARTEL, strict=strict)
                note = self.note(f"strict={strict}: {out}")
                self.assertTrue(ok, note)
                self.assertIsNotNone(self.task_by_title(title), note)
                head = self.header(out)
                self.assertIsNotNone(head, note)
                self.assertEqual(head[:2], (0, 0), note)
                marks = [ln for ln in out.splitlines() if COMMON_MARK in ln]
                self.assertEqual(len(marks), 2, note)
                self.assertNotIn(CALLERS_WARNING, out, note)
                self.assertNotIn(call_file, out, note)
                journal = self.check_journal(title)
                self.assertTrue([d for d in journal if COMMON_MARK in d],
                                self.note(f"журнал {journal}: {out}"))

    def test_ac11_warnings_pass_without_flag_refuse_with_strict(self):
        """Предупреждение не останавливает `new`, а под `--strict-tz` — отказ без записи в БД.

        Сценарий: ТЗ называет `mod.f`, у которой есть вызывающий вне зон.
        Без флага `new` заводит задачу, предупреждение «в зонах нет
        вызывающих» в выводе и в записи журнала задачи «проверка ТЗ». С
        `--strict-tz` в случайном месте argv то же ТЗ — отказ: ни строки
        задачи, ни ссылки документов. `new --help` называет
        `[--strict-tz]`.

        Ловит мутацию: предупреждение останавливает `new` без флага; флаг
        принят, но не превращает предупреждения в отказ (или отказ после
        `_new_task_row`); предупреждение не записано в журнал; справка
        без флага.
        """
        mod, fn = self.ident("m"), self.ident("f")
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({call_file: f"def use(mod):\n    return mod.{fn}(1)\n"})
        tz = self.write_tz([f"Поправить `{mod}.{fn}`."], [f"{self.zone}/"])

        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(f"без флага: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        self.assertIn(CALLERS_WARNING, out, note)
        journal = self.check_journal(title)
        self.assertTrue([d for d in journal if CALLERS_WARNING in d],
                        self.note(f"журнал {journal}: {out}"))

        before, refs, title = self.task_ids(), self.docs_refs(), self.title()
        ok, out = self.new(title, tz, ARTEL, strict=True)
        note = self.note(f"--strict-tz: {out}")
        self.assert_refused_without_traces(title, out, ok, before, refs, note)
        self.assertIn(CALLERS_WARNING, out, note)

        ok, out = self.cli("new", "--help")
        self.assertTrue(ok, self.note(out))
        self.assertIn(f"[{STRICT}]", out, self.note(out))


class TreeTest(TzCheckSandbox):

    def test_ac12_plain_tz_output_unchanged(self):
        """ТЗ без ссылок и имён в кавычках — прежний вывод без строки «проверка ТЗ», в том числе при недоступном дереве.

        Сценарий: ТЗ с путями в обратных кавычках (существующий файл зоны и
        несуществующий), прозой `слово:12` и без имён — для артели и для
        внешнего проекта, чья база в `targets.yaml` отсутствует в клоне
        (дерево недоступно). Задача заводится; строка заведения
        `[<id>] «<название>» создана …` на месте; ни одного текста
        новых проверок в выводе, записи «проверка ТЗ» в журнале нет. ТЗ с
        неклассифицированным путём даёт прежний отказ дословно — текст
        `guard.unclassified_paths_refusal` и ничего сверх.

        Ловит мутацию: дерево открывается при ТЗ без ссылок и кандидатов —
        у недоступного дерева появляется предупреждение «дерево
        недоступно»; строка «проверка ТЗ» печатается и без находок; путь в
        кавычках считается именем; новая проверка дописывает строки к
        прежнему отказу.
        """
        existing = f"{self.zone}/{self.word()}.md"
        self.root_commit({existing: self.lines_file(5)})
        broken = "b" + self.word(6)
        make_project_repo(broken)
        self.write_targets(self.base, PROJECT_ENTRY.format(
            name=broken, url=str(config.PROJECTS / broken / "origin.git"),
            base="nobase" + self.word(5)))
        body = [f"Поправить `{existing}` и `{self.zone}/{self.word()}.py`.",
                f"Ещё {self.word()}:12 в прозе."]
        self.rng.shuffle(body)
        for target in (ARTEL, broken):
            with self.subTest(target=target):
                tz = self.write_tz(body, [f"{self.zone}/"])
                title = self.title()
                ok, out = self.new(title, tz, target)
                note = self.note(f"{target}: {out}")
                self.assertTrue(ok, note)
                row = self.task_by_title(title)
                self.assertIsNotNone(row, note)
                self.assertTrue([ln for ln in out.splitlines() if ln.startswith(
                    f"[{row['id']}] «{title}» создана")], note)
                for text in NEW_CHECK_TEXTS:
                    self.assertNotIn(text, out, note)
                self.assertEqual(self.check_journal(title), [], note)

        stray = f"o{self.word(6)}/{self.word()}.md"
        self.root_commit({stray: self.lines_file(3)})
        tz = self.write_tz([f"Поправить {stray} в прозе."], [f"{self.zone}/"])
        ok, out = self.new(self.title(), tz, ARTEL)
        note = self.note(f"прежний отказ: {out}")
        self.assertFalse(ok, note)
        self.assertEqual(out.strip(),
                         f"ТЗ {tz}: {guard.unclassified_paths_refusal([stray])}",
                         note)

    def test_ac12_canary_and_subtask_skip_the_check(self):
        """Канарейка и подзадача деления проверку ТЗ не выполняют.

        Сценарий: ТЗ со ссылкой на несуществующий файл и с функцией,
        вызываемой вне зон. `catalog.cmd_new(canary=True)` и
        `catalog.spawn_subtask` с этим текстом заводят задачу; в выводе нет
        строки «проверка ТЗ» и находок, в журнале — записи «проверка ТЗ».

        Ловит мутацию: проверка встроена в общий скелет заведения
        (`_new_task_row`) или выполняется без оглядки на `canary` —
        канарейка и деление получают отказ или предупреждения.
        """
        mod, fn = self.ident("m"), self.ident("f")
        call_file = f"c{self.word(6)}/{self.word()}.py"
        self.root_commit({call_file: f"def use(mod):\n    return mod.{fn}(1)\n"})
        missing = f"{self.zone}/{self.word()}.md:{self.rng.randint(1, 9)}"
        body = [f"Поправить `{mod}.{fn}`, см. {missing}."]
        tz = self.write_tz(body, [f"{self.zone}/"])
        title = self.title()
        ok, out, task_id = self.run_fn(catalog.cmd_new, title, tz, canary=True)
        note = self.note(f"канарейка: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        for text in NEW_CHECK_TEXTS:
            self.assertNotIn(text, out, note)
        self.assertEqual(self.check_journal(title), [], note)

        title = self.title()
        tz_body = "\n".join(body) + f"\n\nЗоны: {self.zone}/\n"
        ok, out, task_id = self.run_fn(
            catalog.spawn_subtask, "01PARENTFIXTURE" + self.word(5).upper(),
            "Родитель", title, tz_body)
        note = self.note(f"деление: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        for text in NEW_CHECK_TEXTS:
            self.assertNotIn(text, out, note)
        self.assertEqual(self.check_journal(title), [], note)

    def test_ac13_tree_is_project_base_or_artel_head(self):
        """Дерево проверки — `origin/<base>` клона у внешнего проекта и HEAD главной копии у артели, без `fetch`.

        Сценарий: файлы, существующие только в одном из мест: в HEAD
        главной копии; в `origin/main` главной копии (HEAD откачен); на
        диске главной копии без коммита; в `origin/<base>` клона (база —
        не `main`); в `origin/main` клона; в коммите bare-`origin`
        проекта, которого клон не получал. Ссылка на каждый файл даёт
        отказ или его отсутствие по таблице: артель видит только HEAD,
        внешний проект — только `origin/<base>` клона. Строка «проверка
        ТЗ» отказа несёт `git rev-parse HEAD` главной копии либо `git
        rev-parse origin/<base>` клона, а не sha объекта `^{tree}`;
        `origin/<base>` клона после отказа не сдвинулся.

        Ловит мутацию: у внешнего проекта берётся `origin/main` вместо
        `origin/<base>`; у артели — клон/`origin/main` или рабочий каталог
        вместо HEAD; перед проверкой делается `fetch`; в строке — sha
        дерева `^{tree}`.
        """
        z = self.zone

        def name(ext: str = "md") -> str:
            return f"{z}/{self.word()}/{self.word()}.{ext}"

        project_base_only, project_main_only = name(), name("yaml")
        self.project_commit(self.base, {project_base_only: self.lines_file(5)})
        self.project_commit(config.MAIN_BRANCH,
                            {project_main_only: self.lines_file(5)})

        remote_only = name()
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.git("clone", "-q", "-b", self.base, str(self.origin_bare),
                 str(scratch / "w"))
        work = str(scratch / "w")
        self.git("-C", work, "config", "user.email", "artel@example.invalid")
        self.git("-C", work, "config", "user.name", "artel tests")
        (scratch / "w" / remote_only).parent.mkdir(parents=True)
        (scratch / "w" / remote_only).write_text(self.lines_file(5),
                                                 encoding="utf-8")
        self.git("-C", work, "add", "--", remote_only)
        self.git("-C", work, "commit", "-q", "-m", "только в origin")
        self.git("-C", work, "push", "-q", "origin", self.base)
        base_before = self.project_base_sha()

        origin_only = name("txt")
        self.root_commit({origin_only: self.lines_file(5)})
        self.git("push", "-q", "origin", config.MAIN_BRANCH)
        self.git("reset", "-q", "--hard", "HEAD~1")
        head_only = name("py")
        self.root_commit({head_only: self.py_lines_file(5)})
        disk_only = name()
        (self.root / disk_only).parent.mkdir(parents=True, exist_ok=True)
        (self.root / disk_only).write_text(self.lines_file(5), encoding="utf-8")

        cases = [(self.ext, remote_only, True),
                 (ARTEL, head_only, False), (self.ext, head_only, True),
                 (self.ext, project_base_only, False),
                 (ARTEL, project_base_only, True),
                 (self.ext, project_main_only, True),
                 (ARTEL, origin_only, True), (ARTEL, disk_only, True)]
        first, rest = cases[0], cases[1:]
        self.rng.shuffle(rest)
        for number, (target, path, refused) in enumerate([first] + rest):
            with self.subTest(target=target, path=path):
                ref = f"{path}:{self.rng.randint(1, 5)}"
                tz = self.write_tz([f"Поправить, см. {ref}."], [f"{z}/"])
                before, refs, title = (self.task_ids(), self.docs_refs(),
                                       self.title())
                ok, out = self.new(title, tz, target)
                note = self.note(f"{target} {ref}: {out}")
                if not refused:
                    self.assertTrue(ok, note)
                    continue
                self.assert_refused_without_traces(title, out, ok, before,
                                                   refs, note)
                self.assertIn(ref, out, note)
                head = self.header(out)
                self.assertIsNotNone(head, note)
                if target == ARTEL:
                    sha = self.head_sha()
                    tree = self.git("rev-parse", "HEAD^{tree}").strip()
                else:
                    sha = self.project_base_sha()
                    tree = self.pgit("rev-parse",
                                     f"origin/{self.base}^{{tree}}").strip()
                    if number == 0:
                        # Первый же `new` — до любых заведений задач
                        # проекта: `origin/<base>` клона не сдвинулся.
                        self.assertEqual(sha, base_before, note)
                self.assertIn(sha, head[2], note)
                self.assertNotIn(tree, head[2], note)

    def test_ac14_unavailable_project_tree_warns_or_refuses_under_strict(self):
        """Клон без `origin/<base>` при ТЗ со ссылкой или кандидатом — предупреждение «дерево недоступно», под `--strict-tz` — отказ.

        Сценарий: внешний проект, чья база в `targets.yaml` — ветка,
        которой нет в клоне. ТЗ со ссылкой `путь:N` или с `` `mod.f` `` до
        «Зоны:» (случайно). Без флага задача заводится, в выводе
        «дерево недоступно — проверка ТЗ не выполнена: <причина>» с
        непустой причиной. С `--strict-tz` — отказ без строки задачи и
        ссылки документов.

        Ловит мутацию: недоступное дерево — отказ без флага, либо молчание
        (ни предупреждения, ни отказа под флагом); недоступность
        проглатывается как «находок нет».
        """
        self.write_targets("nobase" + self.word(5))
        if self.rng.random() < 0.5:
            body = [f"См. {self.zone}/{self.word()}.md:{self.rng.randint(1, 9)}."]
        else:
            body = [f"Поправить `{self.ident('m')}.{self.ident('f')}`."]
        tz = self.write_tz(body, [f"{self.zone}/"])
        title = self.title()
        ok, out = self.new(title, tz, self.ext)
        note = self.note(f"без флага {body}: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        lines = [ln for ln in out.splitlines() if TREE_UNAVAILABLE in ln]
        self.assertTrue(lines, note)
        self.assertTrue(lines[0].split(TREE_UNAVAILABLE, 1)[1].strip(), note)

        before, refs, title = self.task_ids(), self.docs_refs(), self.title()
        ok, out = self.new(title, tz, self.ext, strict=True)
        note = self.note(f"--strict-tz {body}: {out}")
        self.assert_refused_without_traces(title, out, ok, before, refs, note)
        self.assertIn(TREE_UNAVAILABLE, out, note)


class NoGitArtelTest(TzCheckHelpers, InitializedTmpRootTest):
    """Главная копия артели — не git-репозиторий (лёгкая песочница)."""

    def setUp(self):
        super().setUp()
        self.start_rng()

    def docs_ref_writes(self) -> int:
        return sum(1 for call in self.git_spy.calls
                   if "update-ref" in call
                   and any(str(a).startswith("refs/artifacts/") for a in call))

    def test_ac14_artel_main_copy_not_git_warns_or_refuses_under_strict(self):
        """Главная копия артели не git-репозиторий — предупреждение «дерево недоступно», под `--strict-tz` — отказ.

        Сценарий: ТЗ артели со ссылкой `путь:N` или с `` `mod.f` `` до
        «Зоны:» (случайно). Без флага задача заводится, в выводе
        «дерево недоступно — проверка ТЗ не выполнена: <причина>». С
        `--strict-tz` — отказ: ни строки задачи, ни записи ссылки
        документов.

        Ловит мутацию: сбой `git` главной копии — необработанное
        исключение или отказ без флага; дерево берётся из клона артели
        вместо главной копии (клон-заглушка есть — предупреждения нет).
        """
        if self.rng.random() < 0.5:
            body = [f"См. z{self.word()}/{self.word()}.md:{self.rng.randint(1, 9)}."]
        else:
            body = [f"Поправить `{self.ident('m')}.{self.ident('f')}`."]
        tz = self.write_tz(body, ["src/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(f"без флага {body}: {out}")
        self.assertTrue(ok, note)
        self.assertIsNotNone(self.task_by_title(title), note)
        self.assertIn(TREE_UNAVAILABLE, out, note)

        before, writes, title = (self.task_ids(), self.docs_ref_writes(),
                                 self.title())
        ok, out = self.new(title, tz, ARTEL, strict=True)
        note = self.note(f"--strict-tz {body}: {out}")
        self.assertFalse(ok, note)
        self.assertEqual(self.task_ids(), before, note)
        self.assertEqual(self.docs_ref_writes(), writes, note)
        self.assertIn(TREE_UNAVAILABLE, out, note)

    def test_ac12_plain_tz_with_unavailable_artel_tree_is_silent(self):
        """ТЗ без ссылок и имён при главной копии не-git — задача без строк новой проверки.

        Сценарий: ТЗ артели с путём в обратных кавычках и прозой
        `слово:12`, без ссылок и имён. `new` заводит задачу; строка
        заведения `[<id>] «<название>» создана …` на месте; ни «проверка
        ТЗ», ни «дерево недоступно» в выводе.

        Ловит мутацию: дерево открывается без ссылок и кандидатов —
        предупреждение «дерево недоступно» на каждом ТЗ.
        """
        tz = self.write_tz([f"Поправить `src/{self.word()}.py` и "
                            f"{self.word()}:12 в прозе."], ["src/"])
        title = self.title()
        ok, out = self.new(title, tz, ARTEL)
        note = self.note(out)
        self.assertTrue(ok, note)
        row = self.task_by_title(title)
        self.assertIsNotNone(row, note)
        self.assertTrue([ln for ln in out.splitlines() if ln.startswith(
            f"[{row['id']}] «{title}» создана")], note)
        for text in NEW_CHECK_TEXTS:
            self.assertNotIn(text, out, note)


if __name__ == "__main__":
    unittest.main()
