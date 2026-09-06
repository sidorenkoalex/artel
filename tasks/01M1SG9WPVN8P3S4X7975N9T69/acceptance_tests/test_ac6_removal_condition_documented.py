"""Приёмочный тест AC-6 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-6. Докстринг `bash_guard.py` и раздел `docs/reference/role-home.md`
несут одинаковое по смыслу условие: хук — временная мера до появления
таймаута на тест (P1, `pytest-timeout`); после мержа задачи P1 хук
снимается ЕЮ, не ручной правкой Оператора.

Проверка текстовая (grep по ключевым маркерам), не парсинг естественного
языка: дословное совпадение формулировок не требуется, но ОБА документа
обязаны называть конкретный технический маркер условия снятия
(`pytest-timeout`) и явно отрицать ручное снятие Оператором — это и есть
проверяемая часть «одинакового смысла», отличающая содержательное условие
от общей фразы «хук временный».

Красен до реализации: `docs/reference/role-home/claude/hooks/bash_guard.py`
отсутствует на диске (снят коммитом dea8016b) — `setUp` пропускает через
`skipTest`, а не падает, потому что до восстановления файла проверять
условие снятия не на чем (сам файл — предмет AC-1); `docs/reference/
role-home.md` уже существует, но текущая редакция не содержит условия
снятия хука вовсе (текст был убран вместе со сдиранием хука, dea8016b) —
`test_ac6_role_home_md_states_removal_condition` красный по этой причине
уже сейчас, без ожидания восстановления `bash_guard.py`.
"""
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

HOOK = (_REPO_ROOT / "docs" / "reference" / "role-home" / "claude" / "hooks"
        / "bash_guard.py")
ROLE_HOME_MD = _REPO_ROOT / "docs" / "reference" / "role-home.md"

_MANUAL_REMOVAL_NEGATION = re.compile(
    r"не\s+(?:руками|вручную|ручной)", re.IGNORECASE)


def _states_removal_condition(text: str) -> tuple[bool, bool]:
    """(несёт маркер pytest-timeout, явно отрицает ручное снятие)."""
    has_marker = "pytest-timeout" in text.lower() or "pytest_timeout" in text.lower()
    has_negation = bool(_MANUAL_REMOVAL_NEGATION.search(text))
    return has_marker, has_negation


class HookDocstringStatesRemovalConditionTest(unittest.TestCase):

    def setUp(self):
        if not HOOK.is_file():
            self.skipTest(f"хук ещё не восстановлен: {HOOK}")
        self.text = HOOK.read_text(encoding="utf-8")

    def test_ac6_hook_docstring_states_removal_condition(self):
        """Докстринг хука называет `pytest-timeout` как условие снятия и
        явно отрицает ручное снятие Оператором.

        Ловит мутацию: докстринг говорит «хук временный» без указания
        КАКОЙ задачей и КАК он будет снят — тогда следующий разработчик
        мог бы посчитать снятие своей инициативой (ровно повтор истории
        этой самой задачи — предыдущее снятие уже стоило регресса), а
        текстовые маркеры ниже этого не поймают.
        """
        has_marker, has_negation = _states_removal_condition(self.text)
        self.assertTrue(has_marker,
                        "докстринг не называет pytest-timeout как условие снятия")
        self.assertTrue(has_negation,
                        "докстринг не отрицает явно ручное снятие Оператором")


class RoleHomeDocStatesRemovalConditionTest(unittest.TestCase):

    def setUp(self):
        self.text = ROLE_HOME_MD.read_text(encoding="utf-8")

    def test_ac6_role_home_md_states_removal_condition(self):
        """`docs/reference/role-home.md` несёт то же условие снятия, что
        и докстринг хука (`pytest-timeout`, отрицание ручного снятия).

        Ловит мутацию: условие снятия дописано только в докстринг хука, а
        `role-home.md` (читаемый Оператором отдельно от кода хука) о нём
        молчит — расхождение источников истины, которое AC-6 требует
        избежать явно («несут ОДИНАКОВОЕ по смыслу условие»).
        """
        has_marker, has_negation = _states_removal_condition(self.text)
        self.assertTrue(has_marker,
                        "role-home.md не называет pytest-timeout как условие снятия")
        self.assertTrue(has_negation,
                        "role-home.md не отрицает явно ручное снятие Оператором")


if __name__ == "__main__":
    unittest.main()
