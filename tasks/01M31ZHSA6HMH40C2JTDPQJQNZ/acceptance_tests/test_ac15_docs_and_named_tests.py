"""AC-15 — 01M31ZHSA6HMH40C2JTDPQJQNZ: `docs/stack.md` несёт абзац «Вывод
и стоимость у провайдера», а названные критерием наборы `tests/`
остаются зелёными.

Источник — SPEC.md, «Критерии приёмки»:

AC-15. `docs/stack.md` несёт абзац «Вывод и стоимость у провайдера» — что
провайдер обязан отдавать и как считается стоимость при
`cost_from_cli: false`; полный прогон `tests/` зелёный, включая
`tests/test_step_cost.py`, `tests/test_token_rate_divergence.py`,
`tests/test_model_tariffs.py`, `tests/test_providers.py`,
`tests/test_agent_log.py`, `tests/test_failure_classification.py`.

Планка гоняет ШЕСТЬ файлов, названных критерием поимённо (3.4 с на все
шесть, замер 21.09), а не весь набор `tests/`: полный прогон — предмет
CI (`.github/workflows/ci.yml`) и автогейта приёмки, и повторять его
внутри одного теста планки значило бы гонять его дважды под чужим
таймаутом (skills/test-authoring.md, решение Оператора 05.09).

Красен до реализации: абзаца «Вывод и стоимость у провайдера» в
`docs/stack.md` сегодня нет. Прогон шести файлов сегодня зелёный —
красным он станет, если переезд разбора к провайдеру разойдётся с тем,
как эти файлы подменяют коллаборантов.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, stack  # noqa: E402

TITLE = "Вывод и стоимость у провайдера"

NAMED_FILES = (
    "tests/test_step_cost.py",
    "tests/test_token_rate_divergence.py",
    "tests/test_model_tariffs.py",
    "tests/test_providers.py",
    "tests/test_agent_log.py",
    "tests/test_failure_classification.py",
)

#: Запас под таймаутом ОДНОГО теста планки (`stack.PER_TEST_TIMEOUT_SEC`,
#: тем же числом её гоняет гейт приёмки): прогон обязан упасть своим
#: отказом с хвостом вывода, а не быть срезанным таймаутом снаружи.
TIMEOUT_SEC = max(30, stack.PER_TEST_TIMEOUT_SEC - 30)


def heading_level(line: str) -> int:
    stripped = line.lstrip()
    return len(stripped) - len(stripped.lstrip("#"))


def section_body(text: str, title: str):
    """Тело раздела с заголовком `title` — до следующего заголовка того
    же или более высокого уровня; `None` — раздела нет. Абзац, не
    оформленный заголовком, ищется отдельно самим тестом."""
    lines = text.splitlines()
    start, level = None, 0
    for index, line in enumerate(lines):
        if heading_level(line) and title in line:
            start, level = index, heading_level(line)
            break
    if start is None:
        return None
    body = []
    for line in lines[start + 1:]:
        current = heading_level(line)
        if current and current <= level:
            break
        body.append(line)
    return "\n".join(body)


class DocsAndNamedTestsTest(unittest.TestCase):

    def setUp(self):
        self.text = (config.ROOT / "docs" / "stack.md").read_text(
            encoding="utf-8")

    def test_ac15_stack_doc_describes_output_and_cost_of_a_provider(self):
        """Абзац «Вывод и стоимость у провайдера» есть и говорит обе
        вещи: что провайдер обязан отдавать и как считается стоимость
        при `cost_from_cli: false`.

        Ловит мутацию: абзац добавлен одной фразой «разбор вывода теперь
        у провайдера» — автор следующего провайдера не найдёт в
        документе ни состава события общего вида, ни ответа на вопрос,
        откуда возьмутся деньги, если его CLI цену не сообщает, и
        соберёт то и другое чтением кода.
        """
        body = section_body(self.text, TITLE)
        if body is None:
            self.assertIn(TITLE, self.text,
                          f"в docs/stack.md нет абзаца «{TITLE}»")
            body = self.text

        self.assertIn("cost_from_cli", body)
        self.assertIn("тариф", body.lower())

    def test_ac15_named_test_files_stay_green(self):
        """Шесть файлов `tests/`, названных критерием, проходят все до
        одного — тем же интерпретатором, которым идёт сама планка.

        Ловит мутацию: переезд разбора к провайдеру расходится с тем,
        как эти файлы подменяют коллаборантов (например `OutputPump`
        начинает требовать провайдера аргументом, а тесты пульта
        конструируют её по-старому) — прогон возвращает ненулевой код,
        тест печатает хвост вывода pytest.
        """
        command = [sys.executable, "-m", "pytest", *NAMED_FILES,
                   "-p", "no:cacheprovider", "-q"]

        result = subprocess.run(command, cwd=config.ROOT, capture_output=True,
                                text=True, timeout=TIMEOUT_SEC)

        tail = (result.stdout + result.stderr)[-2000:]
        self.assertEqual(result.returncode, 0,
                         f"прогон {' '.join(NAMED_FILES)} не зелёный:\n{tail}")


if __name__ == "__main__":
    unittest.main()
