"""AC-5 — тесты AC-1…AC-4 лежат в `tests/test_amend_remove.py`, каждый с
«Ловит мутацию: …»; `tests/test_amend.py` и
`tests/test_amend_long_lived.py` не изменены.

Группа: разовый
Красен до реализации: файла tests/test_amend_remove.py в кодовой ветке задачи ещё нет.

Источник — код под проверкой (корень, откуда импортирован пульт), база —
точка расхождения ветки с `origin/<основная ветка>` (`gitcmd.diff_base`).
Что именно каждый метод проверяет и что он соответствует своему
критерию — предмет ревью по диффу; здесь — механически проверяемое:
файл есть, тестовые методы в нём есть, у каждого заявка мутации, заявки,
названные в AC-1…AC-3, присутствуют, два соседних файла не тронуты.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402

#: Корень кода, который сейчас проверяется (откуда импортирован пульт).
REPO = Path(config.__file__).resolve().parent.parent
NEW_FILE = "tests/test_amend_remove.py"
UNTOUCHED = ("tests/test_amend.py", "tests/test_amend_long_lived.py")
CLAIM = "Ловит мутацию:"
# Заявки, которые AC-1…AC-3 называют дословно (сверка по устойчивому ядру
# фразы — без обрамляющих кавычек и разметки).
NAMED_CLAIMS = (
    "не передан",                            # AC-1, режим без перечня
    "только в одном из двух режимов",        # AC-1, режим с перечнем
    "проверка пустого коммита убрана",       # AC-2
    "удалённые файлы исключены из проверок",  # AC-3
)


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True)


def _test_methods(source: str) -> list[tuple[str, str]]:
    """(имя, докстринг) тестовых методов классов и функций модуля."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test")):
            found.append((node.name, ast.get_docstring(node) or ""))
    return found


class TestsFileTest(unittest.TestCase):

    def test_ac5_new_file_has_claimed_test_methods(self):
        """В коде под проверкой есть `tests/test_amend_remove.py`, в нём
        есть тестовые методы, у каждого в докстринге «Ловит мутацию:», а
        среди заявок — четыре, названные в AC-1…AC-3.

        Ловит мутацию: тесты удаления дописаны в `tests/test_amend.py`
        вместо нового файла, либо у метода нет заявки мутации, либо
        заявка из критерия (например «проверка пустого коммита убрана»)
        не заведена — имя файла, метода или недостающей заявки в тексте
        провала.
        """
        path = REPO / NEW_FILE
        self.assertTrue(path.is_file(), f"{NEW_FILE} нет в коде под проверкой")
        source = path.read_text(encoding="utf-8")
        methods = _test_methods(source)
        self.assertTrue(methods, f"в {NEW_FILE} нет тестовых методов")
        unclaimed = [name for name, doc in methods if CLAIM not in doc]
        self.assertEqual(unclaimed, [], f"методы {NEW_FILE} без «{CLAIM}»")
        claims = " ".join(" ".join(doc.split()) for _name, doc in methods)
        missing = [c for c in NAMED_CLAIMS if c not in claims]
        self.assertEqual(missing, [], f"заявки из AC-1…AC-3 не найдены в "
                                      f"{NEW_FILE}")

    def test_ac5_neighbour_test_files_untouched(self):
        """`tests/test_amend.py` и `tests/test_amend_long_lived.py` в коде
        под проверкой побайтно равны своим версиям в базе ветки задачи.

        Ловит мутацию: тест удаления вписан в существующий файл или
        существующий тест поправлен под новое поведение — имя изменённого
        файла в тексте провала.
        """
        base = gitcmd.diff_base("HEAD", repo=REPO)
        self.assertTrue(base, "база ветки задачи не вычислена")
        changed = []
        for rel in UNTOUCHED:
            res = _git("show", f"{base}:{rel}")
            self.assertEqual(res.returncode, 0,
                             f"{rel} нет в базе {base}: {res.stderr.strip()}")
            path = REPO / rel
            now = path.read_text(encoding="utf-8") if path.is_file() else None
            if now != res.stdout:
                changed.append(rel)
        self.assertEqual(changed, [], "изменены файлы, которые AC-5 требует "
                                      "оставить как есть")


if __name__ == "__main__":
    unittest.main()
