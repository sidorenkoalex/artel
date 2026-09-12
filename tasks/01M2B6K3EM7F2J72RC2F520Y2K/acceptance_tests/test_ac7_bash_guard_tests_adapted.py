"""AC-7 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — тесты хука `bash_guard`
(`tests/test_role_bash_guard.py`, планка T058), проверяющие наличие
файла хука или его подключения в settings.json, адаптированы к его
снятию без ослабления гарантии изоляции роли — гарантия проверяется
через conftest.py (AC-2–AC-4) и диспетчер (AC-5) этой же планки.

Зелёный с рождения: на момент написания планки `tests/
test_role_bash_guard.py` ещё ссылается на хук (он ещё не удалён) — тест
ниже проходит уже сейчас (файл существует, грузит хук по существующему
пути) и покраснеет, если после удаления хука (AC-6) разработчик не
тронет этот файл вовсе — он попытается загрузить по
`importlib.util.spec_from_file_location` уже несуществующий файл и
упадёт `FileNotFoundError`/ошибкой импорта внутри subprocess pytest.

«Адаптация» согласно требованию 5/AC-7 не обязана означать «файл
остался»: полное удаление файла (гарантия целиком переехала в
conftest.py/диспетчер) — тоже валидный исход, тест ниже это учитывает
явно (`skipTest`, не провал), а не требует существования любой ценой.
Поведенческая проверка (реальный прогон файла), не сверка текста на
отсутствие строки-пути: правка хука тем, КАК построен путь в файле
(конкатенация против `Path` — сегментами), сделала бы любую сверку по
одной строке текста ненадёжной в обе стороны.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_TEST = REPO_ROOT / "tests" / "test_role_bash_guard.py"


class LegacyBashGuardTestAdaptedTest(unittest.TestCase):

    def test_ac7_legacy_file_is_green_if_still_present(self):
        """Если `tests/test_role_bash_guard.py` остался — его собственные
        тесты проходят (subprocess pytest, targeted-путь — не заблокирован
        AC-2 ни при ARTEL_ROLE, ни без него).

        Ловит мутацию: файл адаптирован частично — часть тестов всё ещё
        целится в удалённый хук/файл настроек старой формы, прогон падает
        импортной ошибкой или ассертом.
        """
        if not LEGACY_TEST.is_file():
            self.skipTest("файл адаптирован удалением целиком — валидный исход")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
             str(LEGACY_TEST.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
