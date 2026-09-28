"""AC-9: в `tests/` есть тест окружения шага Codex в клоне с заявкой
мутации «клон отдаёт свой `CODEX_HOME`: вход не найден» в докстринге, и ни
один тест задачи не запускает настоящий клиент Codex и не обращается к
связке ключей.

Красен до реализации: такого докстринга в `tests/` сегодня нет вовсе —
поиск по всем тестовым функциям набора не находит ни одной заявки с этим
текстом.

Вторая половина критерия проверяется по ДОБАВЛЕННЫМ строкам диффа задачи, а
не по файлам целиком: тест задачи — то, что задача дописала, и чужая строка
в файле, который задача всего лишь тронула, к ней отношения не имеет. База
диффа — точка расхождения ветки с `origin/<основная ветка>`, одной точкой
правды пульта (`gitcmd.diff_base`), не собственным `merge-base`.

Ни клиент Codex, ни связка ключей здесь не при чём: тест читает тексты
файлов и вывод `git diff`.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402

#: Заявка мутации критерия. Разделитель и обратные кавычки вокруг имени
#: переменной — оформление автора, критерий требует самого утверждения:
#: «клон отдаёт свой CODEX_HOME» -> «вход не найден».
CLAIM_RE = re.compile(
    r"клон\s+отда[её]т\s+свой\s+`?CODEX_HOME`?\s*[:—–-]+\s*вход\s+не\s+найден",
    re.I)

#: Запуск процесса из тестового кода.
LAUNCH_RE = re.compile(
    r"\b(?:subprocess\.(?:run|Popen|call|check_call|check_output)"
    r"|os\.(?:system|popen|execvp|spawnv))\s*\(")

#: Цель запуска, делающая его обращением к настоящему клиенту Codex или к
#: связке ключей. Узкий перечень намеренно: запуск настоящего git в тесте
#: критерий не запрещает, и широкий образец краснел бы на нём.
CODEX_TARGET_RE = re.compile(
    r"""(['"]codex['"]|CLI_NAME|login_status_command|['"]security['"])""")

#: То, что обращается к связке ключей и без запуска процесса.
KEYCHAIN_RE = re.compile(r"default-keychain|find-generic-password|keyring\.")


def docstrings_of_test_functions(source: str):
    """(имя, докстринг) каждой функции `test_*` текста `source`; файл, не
    разбирающийся как Python, даёт пустой перечень.

    Имя функции сознательно НЕ начинается с `test`: помощник модуля с таким
    именем pytest собрал бы как тест и потребовал бы фикстуру `source`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test")):
            found.append((node.name, ast.get_docstring(node) or ""))
    return found


class TestsOfTheTaskTest(unittest.TestCase):
    """AC-9: заявка мутации в `tests/` и чистота тестов задачи."""

    def test_ac9_a_test_claims_the_clone_codex_home_mutation(self):
        """Среди тестовых функций `tests/` есть та, чей докстринг заявляет
        мутацию «клон отдаёт свой `CODEX_HOME`: вход не найден».

        Ловит мутацию: юнит-тест окружения шага в клоне написан, но
        заявлена у него другая, поведенчески нейтральная мутация (скажем,
        «константу переименовали») — тест остался бы без названного
        наблюдаемого расхождения, и ревьюверу нечего было бы сверить с
        предметом задачи: именно эта мутация и есть тот отказ прогона
        20260928T135246Z, ради которого задача заводится.
        """
        claimed = []
        for path in sorted((config.ROOT / "tests").rglob("test_*.py")):
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for name, docstring in docstrings_of_test_functions(source):
                if CLAIM_RE.search(docstring):
                    claimed.append(f"{path.name}::{name}")

        self.assertTrue(claimed,
                        "ни один тест tests/ не заявляет мутацию «клон "
                        "отдаёт свой CODEX_HOME: вход не найден»")

    def test_ac9_no_test_of_the_task_launches_codex_or_the_keychain(self):
        """Ни одна строка, добавленная задачей в `tests/`, не запускает
        настоящий клиент Codex и не обращается к связке ключей.

        Ловит мутацию: тест окружения шага написан так, что зовёт
        `codex login status` по-настоящему (или спрашивает связку через
        `security`) — набор зеленел бы только на машине вошедшего Оператора
        и краснел бы на CI и у любой роли, а каждый прогон дёргал бы связку
        ключей, которую пульт не читает и не пишет.
        """
        base = gitcmd.diff_base("HEAD")
        if not base:
            self.skipTest("база диффа задачи не определилась — git не ответил")
        res = gitcmd.git("diff", base, "--", "tests")
        self.assertEqual(0, res.returncode, res.stderr)

        offenders = []
        for line in res.stdout.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            added = line[1:]
            launches_codex = (LAUNCH_RE.search(added)
                              and CODEX_TARGET_RE.search(added))
            if launches_codex or KEYCHAIN_RE.search(added):
                offenders.append(added.strip())

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
