"""AC-3 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — без ARTEL_ROLE в окружении
(Оператор, CI, автогейт пульта) `conftest.py` в сбор pytest не
вмешивается — ни для целевого, ни для нецелевого запуска.

Зелёный с рождения: `conftest.py` в корне репозитория ещё не
существует — нечему вмешиваться в сбор, оба теста ниже проходят уже
сегодня вакуумно. Это законный старт, не тавтология: после появления
`conftest.py` (AC-2/AC-4 этой же планки) тест продолжит проходить
ТОЛЬКО если guard действительно проверяет ARTEL_ROLE перед отказом, а
не просто всегда блокирует нецелевой запуск — мутация «guard блокирует
нецелевой запуск независимо от ARTEL_ROLE» покрасит именно этот файл,
не AC-2.

Только ОДИН дорогой (реальный полный обход `tests/`) вызов ниже —
голый `pytest` с `--collect-only` (импорт без исполнения тел тестов):
три нецелевые формы (`pytest`/`pytest tests`/`pytest .`) под ARTEL_ROLE
проверены в AC-2 отдельно и структурно бьют по ОДНОЙ и той же ветке
guard'а (нет пути ниже tests/ или tasks/<id>/acceptance_tests/) — здесь
достаточно ОДНОГО представителя: без него сама гарантия «без ARTEL_ROLE
guard не вмешивается в нецелевой запуск» осталась бы непроверенной, а
дублировать все три формы стоило бы утроенного обхода `tests/` без
дополнительной уверенности.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _helpers import combined_output, run_pytest  # noqa: E402

REASON_MARKER = "Сторож роли"


class NoInterferenceWithoutRoleTest(unittest.TestCase):

    def test_ac3_bare_pytest_collects_normally_without_role(self):
        """Голый `pytest --collect-only` без ARTEL_ROLE в окружении
        собирает набор как обычно — conftest.py не отказывает и не
        добавляет предупреждений о страже роли.

        Ловит мутацию: guard проверяет отсутствие целевого пути БЕЗ
        предварительной проверки на присутствие ARTEL_ROLE (перепутанное
        условие/пропущенный `if` вокруг всей проверки) — тогда даже
        обычный прогон Оператора/CI отказывал бы.
        """
        result = run_pytest(["--collect-only", "-q"], role=None, timeout=100)

        self.assertEqual(result.returncode, 0, combined_output(result))
        self.assertNotIn(REASON_MARKER, combined_output(result))

    def test_ac3_targeted_file_runs_normally_without_role(self):
        """Адресный прогон конкретного файла без ARTEL_ROLE — тоже без
        вмешательства (полноценный прогон, не только сбор).

        Ловит мутацию: guard триггерится по наличию/отсутствию пути
        независимо от ARTEL_ROLE (условие на ARTEL_ROLE выпало из
        проверки целиком) — тогда даже адресный прогон Оператора отказал
        бы тем же REASON.
        """
        result = run_pytest(["tests/test_slugify.py", "-q"], role=None,
                            timeout=60)

        self.assertEqual(result.returncode, 0, combined_output(result))
        self.assertNotIn(REASON_MARKER, combined_output(result))


if __name__ == "__main__":
    unittest.main()
