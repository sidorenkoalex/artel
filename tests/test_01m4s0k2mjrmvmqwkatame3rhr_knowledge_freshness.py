"""Пометка «возможно устарела» команды `knowledge`: где сверяется символ
элемента `where` формы `p::s`, какие формы символа считаются найденными и
какие файлы проверка свежести не читает.

Связка «команда — git — диск»: песочница — настоящий git-репозиторий пульта
(`RealGitSandbox`), системные карточки — `knowledge/system.yaml` в голове
`main`, проектные — файл на диске области внешнего проекта, рабочие копии
задач — каталоги `workspace.path` с файлами сценария. Команда зовётся через
диспетчер `artel.main()`. Каждый запрос сценария совпадает с одной-двумя
карточками, поэтому пометка в выводе относится к ним. Имена символов и
метки карточек порождаются от зерна (печатается).

Группа: долгоживущий
Красен до реализации: модуля orchestrator.knowledge_cards и команды knowledge в диспетчере artel.py ещё нет — импорт модуля теста падает ImportError.
"""
import ast
import contextlib
import io
import os
import random
import sys
import unittest
import warnings
from unittest import mock

from orchestrator import artel, config, knowledge_cards, store, workspace
from tests.sandbox import RealGitSandbox, artel_target_entry

EXT = "extproj"
SYSTEM_REL = "knowledge/system.yaml"
STALE = "возможно устарела"
UNCHECKED = "свежесть не проверена"
NO_WORKTREE = "свежесть не проверена: рабочей копии задачи нет"

_EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    knowledge: .artel/projects/{name}/knowledge/cards.yaml
"""

FORMS_PY = """import os

def plain_fn():
    pass

async def async_fn():
    pass

class Klass:
    def method_one(self):
        pass

ASSIGNED = 1
annotated: int = 2
aug_only += 1

if os.environ.get("NEVER_SET"):
    def in_if_fn():
        pass

try:
    class InTry:
        pass
except ImportError:
    pass
"""

PRESENT_PY = ("plain_fn", "async_fn", "Klass", "Klass.method_one", "ASSIGNED",
              "annotated", "aug_only", "in_if_fn", "InTry")


def exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    return exc.code if isinstance(exc.code, int) else 1


def card_block(key: str, where: list, token: str) -> str:
    return (f"  {key}:\n"
            f"    where: [{', '.join(where)}]\n"
            f"    rule: правило {token}\n"
            f"    why: причина {token}\n")


def stale_lines(out: str) -> list:
    return [line for line in out.splitlines() if STALE in line]


class FreshnessSandbox(RealGitSandbox):
    """Пульт песочницы: запись артели и внешнего проекта EXT с полем
    `knowledge`; задачи EXT и артели заводятся сценарием."""

    def setUp(self):
        super().setUp()
        self.use_role_map()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.home = self.root / ".artel" / "operator-home"
        self.home.mkdir(parents=True, exist_ok=True)
        text = "targets:\n" + artel_target_entry() + _EXTERNAL_ENTRY.format(
            name=EXT, base=config.MAIN_BRANCH)
        config.TARGETS.parent.mkdir(parents=True, exist_ok=True)
        config.TARGETS.write_text(text, encoding="utf-8")
        self.cards: list = []

    def word(self, n: int = 6) -> str:
        return "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(n))

    def commit_main(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "сценарий")

    def project_cards(self, cards: list) -> None:
        path = config.PROJECTS / EXT / "knowledge" / "cards.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("cards:\n" + "".join(card_block(*c) for c in cards),
                        encoding="utf-8")

    def system_cards(self, cards: list, extra: dict | None = None) -> None:
        files = {SYSTEM_REL: "cards:\n" + "".join(card_block(*c)
                                                  for c in cards)}
        files.update(extra or {})
        self.commit_main(files)

    def add_task(self, task_id: str, target: str,
                 worktree: dict | None = None):
        store.insert_task(store.db(), task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha", target, 25.0)
        if worktree is None:
            return None
        wt = workspace.path(task_id, target)
        wt.mkdir(parents=True, exist_ok=True)
        for rel, text in worktree.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return wt

    def run_knowledge(self, task_id: str, query: str) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            os.environ.pop(config.ARTEL_TASK_ENV, None)
            with mock.patch.object(sys, "argv", ["artel.py", "knowledge",
                                                 task_id, query]), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                try:
                    artel.main()
                    code = 0
                except SystemExit as exc:
                    code = exit_code(exc)
        return code, out.getvalue(), err.getvalue()


class SymbolFormsTest(FreshnessSandbox):
    """AC-13: какие формы символа найдены и что пометка называет."""

    def test_ac13_present_symbol_forms_not_marked(self):
        """Файл рабочей копии задачи EXT несёт `def`, `async def`, `class`,
        метод класса, `Assign`, `AnnAssign`, `AugAssign`, `def` внутри
        верхнеуровневого `if` и `class` внутри `try`; текстовый файл несёт
        последний сегмент символа отдельным словом. По проектной карточке на
        каждую форму, запрос `путь::символ`.

        Наблюдение: ни у одного запроса нет «возможно устарела» и «свежесть
        не проверена», карточка выведена.

        Ловит мутацию: учитываются только узлы верхнего уровня модуля, без
        тел верхнеуровневых `if`/`try` — `in_if_fn` и `InTry` получают
        ложную пометку «возможно устарела».
        """
        cards = []
        for i, sym in enumerate(PRESENT_PY):
            cards.append((f"py-{i}", [f"src/forms.py::{sym}"], self.word()))
        cards.append(("txt-0", ["docs/guide.txt::Alpha.beta_word"],
                      self.word()))
        self.project_cards(cards)
        self.system_cards([])
        self.add_task("T201", EXT, worktree={
            "src/forms.py": FORMS_PY,
            "docs/guide.txt": "see the beta_word marker here\n"})
        for key, where, token in cards:
            query = where[0]
            with self.subTest(query):
                code, out, err = self.run_knowledge("T201", query)
                self.assertIn(f"правило {token}", out, f"зерно: {self.seed}")
                self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")
                self.assertNotIn(UNCHECKED, out, f"зерно: {self.seed}\n{out}")

    def test_ac13_removed_symbol_marked_card_still_shown(self):
        """Карточки на символы, которых в файле нет: функция с случайным
        именем, метод, которого нет у существующего класса, слово текстового
        файла, встречающееся только как часть другого слова; карточка на
        файл, которого нет.

        Наблюдение: у каждой — строка «возможно устарела», называющая
        ненайденное (имя символа или путь файла); текст карточки выведен.

        Ловит мутацию: поиск в текстовом файле — подстрокой, а не отдельным
        словом — `gamma_word` находится внутри `gamma_words`, пометки нет.
        """
        gone = f"gone_{self.word()}"
        missing_file = f"src/{self.word()}.py"
        cases = [
            (f"src/forms.py::{gone}", gone),
            ("src/forms.py::Klass.missing_method", "missing_method"),
            ("docs/guide.txt::gamma_word", "gamma_word"),
            (f"{missing_file}::anything", missing_file),
        ]
        cards = [(f"gone-{i}", [where], self.word())
                 for i, (where, _name) in enumerate(cases)]
        self.project_cards(cards)
        self.system_cards([])
        self.add_task("T201", EXT, worktree={
            "src/forms.py": FORMS_PY,
            "docs/guide.txt": "only gamma_words here\n"})
        for (key, where, token), (_w, name) in zip(cards, cases):
            with self.subTest(where[0]):
                _code, out, _err = self.run_knowledge("T201", where[0])
                self.assertIn(f"правило {token}", out, f"зерно: {self.seed}")
                lines = stale_lines(out)
                self.assertTrue(any(name in line for line in lines),
                                f"зерно: {self.seed}: нет пометки о {name}\n"
                                f"{out}")


class WhereCheckedTest(FreshnessSandbox):
    """AC-13: системные карточки — по проекту задачи; нет рабочей копии."""

    def test_ac13_system_card_of_external_task_checked_against_main(self):
        """Голова `main` пульта: `pkg/core.py` с `anchor_main`; рабочая
        копия задачи EXT: `pkg/core.py` только с `anchor_wt`. Системные
        карточки на оба символа.

        Наблюдение: `anchor_main` без пометки, `anchor_wt` — «возможно
        устарела»: сверка с `main` пульта, а не с рабочей копией задачи.

        Ловит мутацию: системная карточка задачи внешнего проекта сверяется
        с рабочей копией задачи — `anchor_main` получает ложную пометку.
        """
        a_main, a_wt = f"anchor_main_{self.word()}", f"anchor_wt_{self.word()}"
        tm, tw = self.word(), self.word()
        self.system_cards([("sys-main", [f"pkg/core.py::{a_main}"], tm),
                           ("sys-wt", [f"pkg/core.py::{a_wt}"], tw)],
                          extra={"pkg/core.py": f"def {a_main}():\n    pass\n"})
        self.project_cards([])
        self.add_task("T201", EXT, worktree={
            "pkg/core.py": f"def {a_wt}():\n    pass\n"})
        _code, out, _err = self.run_knowledge("T201", f"pkg/core.py::{a_main}")
        self.assertIn(f"правило {tm}", out, f"зерно: {self.seed}")
        self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")
        _code, out, _err = self.run_knowledge("T201", f"pkg/core.py::{a_wt}")
        self.assertIn(f"правило {tw}", out, f"зерно: {self.seed}")
        self.assertTrue(any(a_wt in line for line in stale_lines(out)),
                        f"зерно: {self.seed}\n{out}")

    def test_ac13_system_card_of_artel_task_checked_against_worktree(self):
        """Тот же расклад для задачи проекта `config.DEFAULT_TARGET`.

        Наблюдение: `anchor_wt` (есть только в рабочей копии задачи) без
        пометки, `anchor_main` (есть только в `main`) — «возможно устарела».

        Ловит мутацию: системная карточка сверяется с `main` при любом
        проекте задачи — `anchor_wt` задачи артели получает ложную пометку.
        """
        a_main, a_wt = f"anchor_main_{self.word()}", f"anchor_wt_{self.word()}"
        tm, tw = self.word(), self.word()
        self.system_cards([("sys-main", [f"pkg/core.py::{a_main}"], tm),
                           ("sys-wt", [f"pkg/core.py::{a_wt}"], tw)],
                          extra={"pkg/core.py": f"def {a_main}():\n    pass\n"})
        self.add_task("T202", config.DEFAULT_TARGET, worktree={
            "pkg/core.py": f"def {a_wt}():\n    pass\n"})
        _code, out, _err = self.run_knowledge("T202", f"pkg/core.py::{a_wt}")
        self.assertIn(f"правило {tw}", out, f"зерно: {self.seed}")
        self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")
        _code, out, _err = self.run_knowledge("T202", f"pkg/core.py::{a_main}")
        self.assertIn(f"правило {tm}", out, f"зерно: {self.seed}")
        self.assertTrue(any(a_main in line for line in stale_lines(out)),
                        f"зерно: {self.seed}\n{out}")

    def test_ac13_missing_worktree_is_unchecked_not_stale(self):
        """Рабочей копии задачи нет: проектная карточка задачи EXT и
        системная карточка задачи артели на символ, которого нет нигде.

        Наблюдение: «свежесть не проверена: рабочей копии задачи нет», а не
        «возможно устарела»; карточка выведена.

        Ловит мутацию: отсутствие каталога рабочей копии трактуется как
        «файла нет» — печатается «возможно устарела».
        """
        sym = f"nowhere_{self.word()}"
        tp, ts = self.word(), self.word()
        self.project_cards([("prj", [f"lib/a.py::{sym}"], tp)])
        self.system_cards([("sys", [f"lib/b.py::{sym}"], ts)])
        self.add_task("T201", EXT)
        self.add_task("T202", config.DEFAULT_TARGET)
        for task_id, query, token in (("T201", f"lib/a.py::{sym}", tp),
                                      ("T202", f"lib/b.py::{sym}", ts)):
            with self.subTest(task_id):
                _code, out, _err = self.run_knowledge(task_id, query)
                self.assertIn(f"правило {token}", out, f"зерно: {self.seed}")
                self.assertIn(NO_WORKTREE, out, f"зерно: {self.seed}\n{out}")
                self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")


class SafeReadTest(FreshnessSandbox):
    """AC-14: что проверка свежести не читает и как разбирает `.py`."""

    def assert_not_trusted(self, out: str, label: str) -> None:
        self.assertTrue(STALE in out or UNCHECKED in out,
                        f"зерно: {self.seed}; {label}: файл прочитан\n{out}")

    def test_ac14_links_special_and_oversized_files_not_read(self):
        """Рабочая копия задачи EXT: файл с символом за ссылкой на каталог
        внутри пути, ссылка на файл с символом, FIFO, файл с символом в
        начале и размером больше `KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES`;
        контроль — обычный файл с символом.

        Наблюдение: у контроля пометки нет; у каждого из четырёх — пометка
        («возможно устарела» или «свежесть не проверена»): символ, который
        нашёлся бы при чтении, не засчитан.

        Ловит мутацию: путь сверяется `is_file()` без `resolve()` и проверки
        ссылок по пути — файл за ссылкой на каталог прочитан, символ
        найден, пометки нет.
        """
        sym = f"risky_{self.word()}"
        body = f"def {sym}():\n    pass\n"
        big = body + "# заполнение\n" * (
            config.KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES // 10)
        wt = self.add_task("T201", EXT, worktree={
            "ok/plain.py": body, "real_dir/m.py": body,
            "real_file.py": body, "big/huge.py": big})
        (wt / "link_dir").symlink_to("real_dir", target_is_directory=True)
        (wt / "linked.py").symlink_to("real_file.py")
        os.mkfifo(wt / "fifo.py")
        cases = {"контроль": "ok/plain.py", "ссылка на каталог": "link_dir/m.py",
                 "ссылка на файл": "linked.py", "FIFO": "fifo.py",
                 "сверх предела": "big/huge.py"}
        cards = [(f"c-{i}", [f"{path}::{sym}"], self.word())
                 for i, path in enumerate(cases.values())]
        self.project_cards(cards)
        self.system_cards([])
        for (label, path), (_k, _w, token) in zip(cases.items(), cards):
            with self.subTest(label):
                code, out, _err = self.run_knowledge("T201", f"{path}::{sym}")
                self.assertIn(f"правило {token}", out, f"зерно: {self.seed}")
                if label == "контроль":
                    self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")
                    self.assertNotIn(UNCHECKED, out, f"зерно: {self.seed}")
                else:
                    self.assert_not_trusted(out, label)

    def test_ac14_main_blob_oversized_or_link_not_read(self):
        """Голова `main` пульта: блоб больше
        `KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES` с символом в начале,
        символьная ссылка (режим 120000), чья цель — слово символа, и
        контроль — малый файл с символом; системные карточки на них,
        задача внешнего проекта.

        Наблюдение: у контроля пометки нет; у большого блоба и ссылки —
        пометка («возможно устарела» или «свежесть не проверена»).

        Ловит мутацию: размер блоба не сверяется до чтения `gitcmd.show` —
        большой блоб прочитан, символ найден, пометки нет.
        """
        sym = f"huge_{self.word()}"
        word = f"linked_{self.word()}"
        big = f"def {sym}():\n    pass\n" + "# заполнение\n" * (
            config.KNOWLEDGE_CARD_STALE_FILE_MAX_BYTES // 10)
        cards = [("ctl", [f"ok/small.py::{sym}"], self.word()),
                 ("big", [f"big/blob.py::{sym}"], self.word()),
                 ("lnk", [f"lnk/word.txt::{word}"], self.word())]
        link = self.root / "lnk" / "word.txt"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(word)
        self.system_cards(cards, extra={
            "ok/small.py": f"def {sym}():\n    pass\n", "big/blob.py": big})
        self.project_cards([])
        self.add_task("T201", EXT, worktree={})
        for key, where, token in cards:
            with self.subTest(key):
                _code, out, _err = self.run_knowledge("T201", where[0])
                self.assertIn(f"правило {token}", out, f"зерно: {self.seed}")
                if key == "ctl":
                    self.assertNotIn(STALE, out, f"зерно: {self.seed}\n{out}")
                    self.assertNotIn(UNCHECKED, out, f"зерно: {self.seed}")
                else:
                    self.assert_not_trusted(out, key)

    def test_ac14_syntax_warning_suppressed_and_syntax_error_reported(self):
        """`.py` с недопустимой escape-последовательностью (`SyntaxWarning`
        при разборе) и символом; `.py` с ошибкой синтаксиса. Предупреждения
        теста — в режиме «always».

        Наблюдение: у первого — ни записи `SyntaxWarning` в пойманных
        предупреждениях, ни слова `SyntaxWarning` в выводе, пометки нет; у
        второго — «свежесть не проверена» с классом `SyntaxError`, не
        «возможно устарела».

        Ловит мутацию: `ast.parse` без `warnings.catch_warnings()` —
        `SyntaxWarning` уходит в предупреждения процесса и в stderr.
        """
        self.project_cards([("warn", ["src/warn.py::warn_fn"], "tw"),
                            ("broken", ["src/broken.py::broken_fn"], "tb")])
        self.system_cards([])
        self.add_task("T201", EXT, worktree={
            "src/warn.py": 'PATTERN = "\\d+"\n\ndef warn_fn():\n    pass\n',
            "src/broken.py": "def broken_fn(:\n    pass\n"})
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _code, out, err = self.run_knowledge("T201", "src/warn.py::warn_fn")
        self.assertFalse([w for w in caught
                          if issubclass(w.category, SyntaxWarning)],
                         f"зерно: {self.seed}")
        self.assertNotIn("SyntaxWarning", out + err)
        self.assertNotIn(STALE, out, out)
        _code, out, _err = self.run_knowledge("T201", "src/broken.py::broken_fn")
        self.assertIn(UNCHECKED, out, out)
        self.assertIn("SyntaxError", out, out)
        self.assertNotIn(STALE, out, out)

    def test_ac14_parse_does_not_execute_project_code(self):
        """`.py` рабочей копии создаёт файл-метку при исполнении верхнего
        уровня и несёт символ.

        Наблюдение: после вызова файла-метки нет, символ найден (пометки
        нет).

        Ловит мутацию: свежесть проверяется импортом модуля
        (`importlib`/`runpy`) вместо `ast` — исполнение верхнего уровня
        создаёт файл-метку.
        """
        marker = self.root / ".artel" / f"executed-{self.word()}"
        source = (f"open({str(marker)!r}, 'w').write('x')\n\n"
                  f"def side_fn():\n    pass\n")
        self.project_cards([("side", ["src/side_mod.py::side_fn"], "ts")])
        self.system_cards([])
        self.add_task("T201", EXT, worktree={"src/side_mod.py": source})
        _code, out, _err = self.run_knowledge("T201",
                                              "src/side_mod.py::side_fn")
        self.assertFalse(marker.exists(), f"зерно: {self.seed}")
        self.assertNotIn(STALE, out, out)

    def test_ac14_same_file_parsed_once_per_call(self):
        """Две проектные карточки на два символа одного `.py`; запрос по
        пути выдаёт обе.

        Наблюдение: `ast.parse` вызван для текста этого файла ровно один
        раз, обе карточки без пометки.

        Ловит мутацию: файл разбирается заново для каждой карточки —
        `ast.parse` с его текстом вызван дважды.
        """
        token = f"UNIQ{self.word()}"
        source = f"# {token}\n\ndef a_fn():\n    pass\n\ndef b_fn():\n    pass\n"
        self.project_cards([("pa", ["src/shared.py::a_fn"], "ta"),
                            ("pb", ["src/shared.py::b_fn"], "tb")])
        self.system_cards([])
        self.add_task("T201", EXT, worktree={"src/shared.py": source})
        with mock.patch.object(ast, "parse", wraps=ast.parse) as parse:
            _code, out, _err = self.run_knowledge("T201", "src/shared.py")
        calls = []
        for call in parse.call_args_list:
            src = call.args[0] if call.args else call.kwargs.get("source", "")
            if isinstance(src, bytes):
                src = src.decode("utf-8", "replace")
            if token in str(src):
                calls.append(call)
        self.assertEqual(len(calls), 1, f"зерно: {self.seed}")
        self.assertIn("правило ta", out)
        self.assertIn("правило tb", out)
        self.assertNotIn(STALE, out, out)


if __name__ == "__main__":
    unittest.main()
