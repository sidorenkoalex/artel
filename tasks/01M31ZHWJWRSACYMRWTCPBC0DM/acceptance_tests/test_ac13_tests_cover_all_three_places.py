"""AC-13 — 01M31ZHWJWRSACYMRWTCPBC0DM: `tests/` несут тесты показа токенов
по видам и показа прочерка без данных для каждого из трёх мест показа, и
эти тесты зелёные.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. `tests/` несут тесты показа токенов по видам и показа прочерка без
данных для каждого из трёх мест показа; полный прогон `tests/` зелёный.

Полный прогон `tests/` планка не запускает: это условие автогейта приёмки
(ADR-0007, `acceptance.run_full_suite`) и штатного CI-джоба `python`, и
повторять его внутри одного теста планки значило бы гонять весь набор
дважды, второй раз — под чужим таймаутом (skills/test-authoring.md,
решение Оператора 05.09; тот же приём у планки
01M31ZHSA6HMH40C2JTDPQJQNZ, AC-15). Вместо этого планка находит ИМЕННО
те файлы, о которых говорит критерий, и гоняет найденное: имён файлов не
называет ни SPEC, ни планка — их выбирает разработчик.

Единица поиска — ОБЛАСТЬ теста: класс (или тестовая функция верхнего
уровня) вместе с шапкой модуля, где живут его константы. Не метод: набор
видов и ожидаемые числа идиоматично выносят в константу рядом с классом,
и разбор по одному методу объявил бы такой тест несуществующим. Не файл
целиком: в больших файлах `tests/` соседние классы говорят о своём, и
файловая склейка выдала бы за покрытие случайное соседство.

Красен до реализации: ни одна область `tests/`, зовущая `catalog.
cmd_status`, `retro.*` или `report.*`, не называет все четыре вида
токенов и не проверяет прочерк значением (проверено разбором `tests/*.py`
на 21.09 — пусто по всем трём местам, обе половины).
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import stack  # noqa: E402

#: Три места показа и признак «область теста трогает это место»: обращение
#: к модулю, который его печатает. Имя места — то, которым его называет
#: SPEC. `retro\.` не ловит `retro_corpus.` — после `retro` требуется точка.
PLACES = (
    ("status", re.compile(r"\bcmd_status\b")),
    ("RETRO", re.compile(r"\bretro\.[A-Za-z_]+")),
    ("report", re.compile(r"\breport\.[A-Za-z_]+")),
)

#: Прочерк, проверяемый ЗНАЧЕНИЕМ, а не встреченный в русской прозе
#: докстринга: строковый литерал из одного тире, константа `report._DASH`
#: или слово «прочерк» в самом тесте.
DASH_AS_VALUE = re.compile(r"""["']\s*[—–]\s*["']|_DASH|прочерк""")

#: Запас под таймаутом ОДНОГО теста планки (`stack.PER_TEST_TIMEOUT_SEC` —
#: тем же числом её гоняет гейт приёмки).
TIMEOUT_SEC = max(30, stack.PER_TEST_TIMEOUT_SEC - 30)

#: Разбор `tests/` делается один раз на прогон: инвентаризация идёт по
#: неизменному дереву, а повторный обход сотни файлов на каждый вопрос
#: съел бы таймаут теста впустую.
_SCOPES_CACHE: list = []


def _definitions(node) -> list:
    return [n for n in ast.walk(node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def scopes() -> list:
    """(файл относительно корня, имя области, исходник области) по всем
    `tests/*.py` репозитория — статическим разбором, без импорта: разные
    файлы `tests/` тянут разные песочницы, и импортировать их ради
    инвентаризации незачем.

    Исходник области — шапка модуля (всё до первого определения верхнего
    уровня: импорты и константы) плюс сам класс/функция. Области без
    единого метода `test_*` в результат не попадают.
    """
    if _SCOPES_CACHE:
        return _SCOPES_CACHE
    found = _SCOPES_CACHE
    for path in sorted((_tokens.REPO_ROOT / "tests").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover — синтаксис tests/ стережёт CI
            continue
        tops = [n for n in tree.body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef))]
        lines = source.splitlines()
        first = min((n.lineno for n in tops), default=len(lines) + 1)
        header = "\n".join(lines[:first - 1])
        for node in tops:
            if not any(fn.name.startswith("test_")
                       for fn in _definitions(node)):
                continue
            segment = ast.get_source_segment(source, node) or ""
            found.append((f"tests/{path.name}", node.name,
                          f"{header}\n{segment}"))
    return found


def covering(touches, predicate) -> list:
    """`tests/<файл>::<область>` областей, которые трогают место показа и
    удовлетворяют предикату."""
    return [f"{rel}::{name}" for rel, name, source in scopes()
            if touches.search(source) and predicate(source)]


def shows_every_kind(source: str) -> bool:
    return all(kind in source for kind in _tokens.KINDS)


def shows_dash_as_value(source: str) -> bool:
    return bool(DASH_AS_VALUE.search(source))


class TestsCoverEveryDisplayPlaceTest(unittest.TestCase):

    def test_ac13_every_place_has_a_by_kind_and_a_dash_test(self):
        """Для каждого из трёх мест показа в `tests/` есть область,
        трогающая это место и называющая ВСЕ четыре вида токенов, и
        область, трогающая то же место и проверяющая прочерк значением.

        Ловит мутацию: разработчик покрывает новыми тестами только одно
        место из трёх (например `report`, где правка крупнее всего), а
        `status` и RETRO оставляет на приёмочной планке — `gaps` назовёт
        непокрытое место и недостающую половину поимённо.
        """
        gaps = []
        for place, touches in PLACES:
            if not covering(touches, shows_every_kind):
                gaps.append(f"{place}: в tests/ нет теста, который трогает "
                            f"это место показа и называет все четыре вида "
                            f"{_tokens.KINDS}")
            if not covering(touches, shows_dash_as_value):
                gaps.append(f"{place}: в tests/ нет теста, который трогает "
                            f"это место показа и проверяет прочерк "
                            f"значением")

        self.assertEqual([], gaps, "\n".join(gaps))

    def test_ac13_those_tests_are_green(self):
        """Найденные файлы `tests/` проходят тем же интерпретатором,
        которым идёт сама планка.

        Ловит мутацию: новые тесты показа написаны, но расходятся с
        реализацией (ждут `cache_write=17`, а печатается
        `cache_creation=17`) — прогон вернёт ненулевой код, тест напечатает
        хвост вывода pytest. Гоняются именно НАЙДЕННЫЕ файлы, а не заранее
        названные: какие файлы заведёт разработчик, SPEC не диктует.
        """
        files = set()
        for _place, touches in PLACES:
            for predicate in (shows_every_kind, shows_dash_as_value):
                files.update(hit.split("::", 1)[0]
                             for hit in covering(touches, predicate))
        self.assertTrue(
            files,
            "ни одного теста показа токенов в tests/ не нашлось — гонять "
            "нечего (см. test_ac13_every_place_has_a_by_kind_and_a_dash_test)")

        command = [sys.executable, "-m", "pytest", *sorted(files),
                   "-p", "no:cacheprovider", "-q"]

        result = subprocess.run(command, cwd=_tokens.REPO_ROOT,
                                capture_output=True, text=True,
                                timeout=TIMEOUT_SEC)

        tail = (result.stdout + result.stderr)[-2000:]
        self.assertEqual(0, result.returncode,
                         f"прогон {' '.join(sorted(files))} не зелёный:\n"
                         f"{tail}")


if __name__ == "__main__":
    unittest.main()
