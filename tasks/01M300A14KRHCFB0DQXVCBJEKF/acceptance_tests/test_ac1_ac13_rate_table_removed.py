"""AC-1 и AC-13 — 01M300A14KRHCFB0DQXVCBJEKF: таблица курса по роли
`config.TOKEN_RATES` удалена, и на её имя не ссылается ни код пульта, ни
набор `tests/`.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. В `orchestrator/config.py` нет `TOKEN_RATES`, и ни один модуль кода
пульта на это имя не ссылается.

AC-13. Ни один файл `tests/` не ссылается на удалённую таблицу курса
(`TOKEN_RATES`), и полный прогон `tests/` зелёный — включая
`tests/test_token_rate_divergence.py`, `tests/test_step_cost.py`,
`tests/test_report.py`, `tests/test_store_schema_migration_parity.py`.

«Ссылается» разбирается по дереву разбора (`ast`), а не поиском
подстроки: историческое упоминание имени в комментарии или докстринге
(«курс роли жил в `config.TOKEN_RATES` до 21.09») ссылкой не является и
красить планку не должно, а чтение атрибута или присваивание — является.

Вторую половину AC-13 («полный прогон `tests/` зелёный») планка не
дублирует копией всего набора: её проверяет джоб unit-тестов CI и
автогейт acceptance на той же ветке (skills/test-authoring.md, «Планка
для задачи класса рефакторинг»). Планка фиксирует то, чего полный прогон
не ловит: оставшуюся ССЫЛКУ на удалённое имя в файле, который сам по
себе зелёный (например, скан-тест или модуль, где имя лежит в мёртвой
ветке).

Красен до реализации: `orchestrator/config.py:547` всё ещё объявляет
`TOKEN_RATES`, а `orchestrator/spend.py`/`orchestrator/report.py` и
`tests/test_token_rate_divergence.py`/`tests/test_step_cost.py` читают
её — оба теста называют эти файлы поимённо и падают на них.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402
from orchestrator import config  # noqa: E402

REMOVED_NAME = "TOKEN_RATES"

#: Код пульта (AC-1) и набор тестов (AC-13) — разные критерии, разные
#: деревья каталогов, один и тот же способ поиска ссылки.
PULT_CODE_DIRS = ("orchestrator", "scripts")
TESTS_DIR = "tests"


def _references(path: Path, name: str) -> list:
    """Номера строк, где `path` ССЫЛАЕТСЯ на имя `name`: чтение/запись
    атрибута (`config.TOKEN_RATES`) либо голого имени (`TOKEN_RATES = …`,
    `TOKEN_RATES.get(...)`). Строковые литералы и комментарии — не
    ссылки. Файл, который не разбирается, пропускается: его синтаксис —
    предмет CI, а не этого критерия."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == name:
            hits.append(node.lineno)
        elif isinstance(node, ast.Name) and node.id == name:
            hits.append(node.lineno)
    return sorted(set(hits))


def _referencing_files(dirs) -> list:
    found = []
    for rel in dirs:
        root = _tariff.REPO_ROOT / rel
        for path in sorted(root.rglob("*.py")):
            lines = _references(path, REMOVED_NAME)
            if lines:
                found.append(f"{path.relative_to(_tariff.REPO_ROOT)}:"
                             f"{','.join(str(n) for n in lines)}")
    return found


class RateTableIsGoneFromPultCodeTest(unittest.TestCase):

    def test_ac1_no_pult_module_references_the_role_rate_table(self):
        """`config` не несёт атрибута `TOKEN_RATES`, и ни один `*.py` в
        `orchestrator/`/`scripts/` на это имя не ссылается.

        Ловит мутацию: таблица вычищена из `orchestrator/config.py`, но
        один из читателей оставлен как был (например,
        `report.map_growth_cost_estimate`, который берёт
        `config.TOKEN_RATES["developer"]` — `orchestrator/report.py:252`)
        — пульт падал бы `AttributeError` на живом пути отчёта, а не на
        прогоне тестов, где этот путь не задет.
        """
        self.assertFalse(
            hasattr(config, REMOVED_NAME),
            f"orchestrator/config.py всё ещё объявляет {REMOVED_NAME} "
            f"(AC-1: таблица курса по роли удаляется)")

        referencing = _referencing_files(PULT_CODE_DIRS)

        self.assertEqual(
            [], referencing,
            f"модули кода пульта ссылаются на удалённое имя "
            f"{REMOVED_NAME}: {'; '.join(referencing)}")


class RateTableIsGoneFromTestsTest(unittest.TestCase):

    def test_ac13_no_test_file_references_the_removed_rate_table(self):
        """Ни один `tests/**/*.py` не ссылается на `TOKEN_RATES`.

        Ловит мутацию: ожидания по удалённой таблице переписаны в
        `tests/test_token_rate_divergence.py`, но забыты в
        `tests/test_step_cost.py` (обе сегодня патчат
        `config.TOKEN_RATES`) — набор остаётся зелёным, пока патч
        `mock.patch.object` создаёт отсутствующий атрибут сам
        (`create=True` или подмена словаря), и мёртвая ссылка на
        удалённую таблицу переживает задачу.
        """
        referencing = _referencing_files((TESTS_DIR,))

        self.assertEqual(
            [], referencing,
            f"файлы tests/ ссылаются на удалённое имя {REMOVED_NAME}: "
            f"{'; '.join(referencing)}")


if __name__ == "__main__":
    unittest.main()
