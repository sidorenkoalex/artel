"""Факты задачи 01M4RZB9287PXZ4Y7ZJG7HDR6Y в ветке: правка комментариев о формате строки лога (AC-11), новый файл тестов `tests/` без правки существующих (AC-13), свежесть `docs/codebase-map.md` (AC-14).

Группа: разовый

Красен до реализации: комментарии `claude.py`/`codex.py`/`base.py` ещё прежние (не называют задачу и `base.short_log_path`), в закоммиченном диффе ветки нет нового `tests/test_*.py`, а карта ветки не пересобрана после появления нового файла тестов задачи.

Критерии AC-1..AC-10 и AC-12 — свойства кода; их держит долгоживущий
файл `tests/test_01m4rzb9287pxz4y7zjg7hdr6y_short_log_path.py` кодовой
ветки (методы `test_ac1_…`..`test_ac10_…`, `test_ac12_…`).

Источник фактов — рабочая копия кода (`CODE_ROOT` помощника пульта) и её
закоммиченный дифф от базы задачи (`branch_diff()`): артефакты задачи
здесь не читаются.

Валидация стабом: с временным стабом реализации (общая функция в
`base.py`, правка комментариев о формате строки в трёх модулях,
пересобранная карта) `test_ac11_…` и `test_ac14_…` зелёные; разбор
диффа `test_ac13_…` проверен на диффе с новым файлом тестов и на диффе с
правкой существующего — первый зелёный, второй красный. Стаб удалён.
"""
import ast
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, branch_diff  # noqa: E402

TASK_ID = "01M4RZB9287PXZ4Y7ZJG7HDR6Y"
MUTATION_CLAIM = "Ловит мутацию:"


def code_root() -> Path:
    return Path(CODE_ROOT)


def source(rel: str) -> list:
    return (code_root() / rel).read_text(encoding="utf-8").splitlines()


def normalized(lines: list) -> str:
    """Текст строк комментария без `#` одной строкой по пробелам."""
    return " ".join(" ".join(line.strip().lstrip("#").strip()
                             for line in lines).split())


def comment_blocks(lines: list) -> list:
    """Непрерывные блоки строк-комментариев модуля: [(первая строка, текст)]."""
    blocks, current, start = [], [], 0
    for number, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            if not current:
                start = number
            current.append(line)
        elif current:
            blocks.append((start, normalized(current)))
            current = []
    if current:
        blocks.append((start, normalized(current)))
    return blocks


def comment_above(lines: list, pattern: str) -> str:
    """Ближайший блок комментария над строкой, совпавшей с `pattern`:
    вверх через строки кода и пустые до первой строки-комментария, затем
    весь непрерывный блок комментария."""
    regex = re.compile(pattern)
    index = next(i for i, line in enumerate(lines) if regex.match(line))
    index -= 1
    while index >= 0 and not lines[index].strip().startswith("#"):
        index -= 1
    end = index
    while index >= 0 and lines[index].strip().startswith("#"):
        index -= 1
    return normalized(lines[index + 1:end + 1])


OLD_BASE_SENTENCE = normalized([
    "Формат строки знает провайдер: и отметка вызова инструмента, и сквозной "
    "проброс строки, не разобравшейся в событие (stderr, трейсбек CLI), — его "
    "знание, а не общее"])
OLD_CODEX_SENTENCE = normalized([
    "Символ и число повторяют `claude.py`, а не импортируются из него: формат "
    "строки лога — провайдерское знание (докстринг `base.py`)"])


class CommentsTest(unittest.TestCase):

    def test_ac11_format_comments_name_task_and_shared_function(self):
        """Комментарии о формате строки лога в трёх модулях правлены под задачу.

        Сценарий: в `orchestrator/providers/claude.py` блок комментария над
        `TOOL_ARGUMENT_LIMIT` (заморозка формата по SPEC
        01M31ZHSA6HMH40C2JTDPQJQNZ) называет задачу 01M4RZB9287PXZ4Y7ZJG7HDR6Y
        и путь файла; в `codex.py` такой же блок над пределом называет
        задачу и `short_log_path` и больше не несёт дословно довода
        «формат строки лога — провайдерское знание»; в `base.py` блок
        комментария о `log_text` называет `short_log_path` и не несёт
        дословно «— его знание, а не общее».

        Ловит мутацию: комментарий о заморозке формата в `claude.py` или
        `codex.py` не обновлён (нет ссылки на задачу); комментарий
        `base.py:60-64` или обоснование `codex.py:305-309` оставлены
        прежними и опровергаются общей функцией `base.short_log_path`.
        """
        claude_block = comment_above(source("orchestrator/providers/claude.py"),
                                     r"TOOL_ARGUMENT_LIMIT\s*=")
        self.assertIn(TASK_ID, claude_block, claude_block)
        self.assertRegex(claude_block, r"(?i)пут[ьи]", claude_block)

        codex_block = comment_above(source("orchestrator/providers/codex.py"),
                                    r"TOOL_ARGUMENT_LIMIT\s*=")
        self.assertIn(TASK_ID, codex_block, codex_block)
        self.assertIn("short_log_path", codex_block, codex_block)
        self.assertNotIn(OLD_CODEX_SENTENCE, codex_block, codex_block)

        base_blocks = [text for _start, text in
                       comment_blocks(source("orchestrator/providers/base.py"))
                       if "`log_text`" in text]
        self.assertTrue(base_blocks, "в base.py нет комментария о `log_text`")
        for text in base_blocks:
            self.assertIn("short_log_path", text, text)
            self.assertNotIn(OLD_BASE_SENTENCE, text, text)


def diff_files(diff: str) -> list:
    """[(путь, вид)] файлов унифицированного диффа git; вид — `new`,
    `deleted`, `renamed` или `modified`."""
    files = []
    for chunk in re.split(r"(?m)^diff --git ", diff)[1:]:
        header = chunk.split("\n", 1)[0]
        match = re.match(r"a/(.+?) b/(.+)$", header)
        if not match:
            continue
        old, new = match.group(1), match.group(2)
        head = chunk.split("\n@@", 1)[0]
        if re.search(r"(?m)^new file mode", head):
            files.append((new, "new"))
        elif re.search(r"(?m)^deleted file mode", head):
            files.append((old, "deleted"))
        elif re.search(r"(?m)^rename from", head) or old != new:
            files.append((old, "renamed"))
        else:
            files.append((new, "modified"))
    return files


def methods_without_claim(text: str) -> list:
    """Имена тестовых методов файла без строки «Ловит мутацию:» в докстринге."""
    missing = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name.startswith("test"):
            if MUTATION_CLAIM not in (ast.get_docstring(node) or ""):
                missing.append(node.name)
    return missing


class BranchTest(unittest.TestCase):

    def test_ac13_new_tests_file_with_claims_existing_untouched(self):
        """В закоммиченном диффе ветки есть новый `tests/test_*.py`, каждый тест которого несёт «Ловит мутацию:»; существующие файлы `tests/` не изменены.

        Сценарий: дифф от базы задачи до HEAD разбирается по файлам; среди
        новых файлов есть `tests/test_*.py` с хотя бы одним тестом, и у
        каждого его тестового метода в докстринге есть «Ловит мутацию:».
        Ни один файл `tests/`, существовавший на базе, не изменён, не
        удалён и не переименован.

        Покрытие мутаций требования 6 по существу держат методы
        долгоживущего файла задачи (заявки «Ловит мутацию:» каждого
        метода названы по списку требования 6).

        Ловит мутацию: новый файл тестов не добавлен или у его метода нет
        заявки «Ловит мутацию:»; существующий тест `tests/` поправлен или
        удалён (например, ожидание `tests/test_providers.py` переписано
        под короткую форму пути).
        """
        files = diff_files(branch_diff())
        touched = [(path, kind) for path, kind in files
                   if path.startswith("tests/") and kind != "new"]
        self.assertEqual(touched, [], f"изменены существующие файлы tests/: "
                                      f"{touched}")
        new_tests = [path for path, kind in files if kind == "new"
                     and re.fullmatch(r"tests/test_[^/]+\.py", path)]
        self.assertTrue(new_tests, f"в диффе ветки нет нового tests/test_*.py; "
                                   f"файлы диффа: {files}")
        good = []
        for path in new_tests:
            text = (code_root() / path).read_text(encoding="utf-8")
            has_tests = re.search(r"(?m)^\s*def test", text) is not None
            if has_tests and not methods_without_claim(text):
                good.append(path)
        self.assertTrue(good, "ни в одном новом файле tests/ не все тесты несут "
                              f"«{MUTATION_CLAIM}»: " + "; ".join(
                                  f"{p}: {methods_without_claim((code_root() / p).read_text(encoding='utf-8'))}"
                                  for p in new_tests))

    def test_ac14_codebase_map_matches_generator(self):
        """`docs/codebase-map.md` в HEAD ветки совпадает с выводом `scripts/codebase_map.py` по дереву ветки, кроме строки `built_at_sha`.

        Сценарий: генератор ветки загружается из её `scripts/codebase_map.py`
        и строит карту функциями `build_modules`/`render` в памяти (файл
        карты не перезаписывается); закоммиченная карта читается
        `git show HEAD:docs/codebase-map.md`; строки `built_at_sha:`
        сравнением не учитываются — тем же правилом сверяет CI.

        Ловит мутацию: карта не пересобрана после правки `*.py` задачи
        (`base.short_log_path` не появилась в публичных функциях
        `providers/base.py`, новый файл `tests/` не в перечне) или
        поправлена руками.
        """
        root = code_root()
        spec = importlib.util.spec_from_file_location(
            "branch_codebase_map", root / "scripts" / "codebase_map.py")
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        modules, resolved, imported_by = generator.build_modules(root)
        built = generator.render(modules, resolved, imported_by, "-")
        committed = subprocess.run(
            ["git", "show", "HEAD:docs/codebase-map.md"], cwd=root,
            capture_output=True, text=True, check=True).stdout

        def strip(text: str) -> list:
            return [line for line in text.splitlines()
                    if not line.startswith("built_at_sha:")]

        built_lines, committed_lines = strip(built), strip(committed)
        if built_lines != committed_lines:
            import difflib
            delta = "\n".join(list(difflib.unified_diff(
                committed_lines, built_lines, "HEAD", "генератор",
                lineterm=""))[:40])
            self.fail(f"карта ветки разошлась с генератором:\n{delta}")


if __name__ == "__main__":
    unittest.main()
