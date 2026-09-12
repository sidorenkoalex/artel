"""AC-2 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — корневой `conftest.py`, при
ARTEL_ROLE в окружении, отказывает сбору pytest для нецелевого запуска
(голый `pytest`, `pytest tests`, `pytest .`) и не мешает целевому — путь
ниже `tests/` или `tasks/<id>/acceptance_tests/` присутствует среди
аргументов.

Красен до реализации: тесты класса `UntargetedFormsBlockedUnderRoleTest`
— `conftest.py` в корне репозитория ещё не существует, ни один из
дочерних прогонов не отказывает под ARTEL_ROLE, «блокирующие» сценарии
зелены неправильно (никто их не блокирует).

Зелёный с рождения: тесты класса `TargetedFormsCollectUnderRoleTest` —
без `conftest.py` целевые пути и сегодня ничем не блокируются (мешать
нечему); после появления guard'а эти тесты становятся регрессионным
барьером на «условие ARTEL_ROLE плюс наличие целевого пути» — их задача
поймать перепутанное условие, которое отказывало бы ДАЖЕ адресному
прогону.

Дочерний pytest — subprocess (`_helpers.run_pytest`), не вызов хука
напрямую: конфтест смотрит на окружение ЦЕЛОГО процесса и на реальные
argv вызова pytest, которые изнутри того же процесса не подделать
надёжно. «Целевой» пример под `tests/` — `tests/test_slugify.py`
(11 тривиальных тестов, доли секунды, без сети/ФС побочных эффектов) —
не тяжёлый модуль планки, специально выбран быстрым. Пример под
`tasks/<id>/acceptance_tests/` — сам каталог этой планки, ровно та
форма (`tasks/<id>/acceptance_tests`, без имени файла), которой
`skills/test-authoring.md` предписывает гонять планку из-под роли —
критично, что именно эта форма не окажется заблокированной новым
conftest.py, иначе будущий test_author/developer не смог бы прогнать
собственную планку ни разу.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _helpers import (ACCEPTANCE_TESTS_DIR, REPO_ROOT, TASK_ID,  # noqa: E402
                      combined_output, run_pytest)

ROLE = "developer"
REASON_MARKER = "Сторож роли"


class UntargetedFormsBlockedUnderRoleTest(unittest.TestCase):
    """Три нецелевые формы запуска, дословно названные требованием 2."""

    def test_ac2_bare_pytest_is_blocked_under_role(self):
        """Голый `pytest` без единого аргумента-пути отказывает сбору под
        ARTEL_ROLE.

        Ловит мутацию: guard в `conftest.py` смотрит только на явный
        аргумент `tests`/`.`, пропуская случай ПОЛНОГО отсутствия
        аргументов — тогда этот вызов вернулся бы кодом 0 вместо отказа.
        """
        result = run_pytest([], role=ROLE)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REASON_MARKER, combined_output(result))

    def test_ac2_pytest_tests_is_blocked_under_role(self):
        """`pytest tests` (весь каталог целиком, не конкретный файл в нём)
        отказывает сбору под ARTEL_ROLE.

        Ловит мутацию: guard принимает буквальный токен `tests` как
        «целевой путь» наравне с `tests/test_x.py` — тогда голый каталог
        целиком проходил бы, хотя требование 2 называет его нецелевым
        явно.
        """
        result = run_pytest(["tests"], role=ROLE)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REASON_MARKER, combined_output(result))

    def test_ac2_pytest_dot_is_blocked_under_role(self):
        """`pytest .` (весь репозиторий от корня) отказывает сбору под
        ARTEL_ROLE.

        Ловит мутацию: guard считает любой непустой позиционный аргумент
        «целевым путём» без проверки на `.`/`./` — тогда обход всего
        дерева репозитория прошёл бы как целевой запуск.
        """
        result = run_pytest(["."], role=ROLE)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(REASON_MARKER, combined_output(result))

    def test_ac2_reason_text_reuses_hook_wording_without_unittest_phrasing(self):
        """Текст отказа воспроизводит прежний REASON хука `bash_guard.py`
        (узнаваемая фраза «Сторож роли», упоминание CI), но с заменой
        формулировки «python3 -m unittest» на pytest-формулировки —
        требование 2 называет это явно.

        Ловит мутацию: REASON скопирован из хука дословно, включая старый
        пример `python3 -m unittest tests.test_x` — тест поймает
        оставшуюся строку «unittest» в тексте причины.
        """
        result = run_pytest([], role=ROLE)
        text = combined_output(result)

        self.assertIn("CI", text)
        self.assertIn("pytest", text)
        self.assertNotIn("python3 -m unittest", text)


class TargetedFormsCollectUnderRoleTest(unittest.TestCase):
    """Путь к конкретному файлу/каталогу ниже `tests/` или
    `tasks/<id>/acceptance_tests/` среди аргументов — сбор идёт."""

    def test_ac2_targeted_file_under_tests_dir_runs_under_role(self):
        """Путь к конкретному файлу под `tests/` — сбор и прогон идут как
        обычно под ARTEL_ROLE, отказа нет.

        Ловит мутацию: guard требует ОТСУТСТВИЯ ARTEL_ROLE для любого
        запуска целиком (перепутанное условие «если ARTEL_ROLE» вместо
        «если ARTEL_ROLE и нет целевого пути») — тогда даже адресный
        прогон отказывал бы.
        """
        result = run_pytest(["tests/test_slugify.py", "-q"], role=ROLE,
                            timeout=60)

        self.assertEqual(result.returncode, 0, combined_output(result))
        self.assertNotIn(REASON_MARKER, combined_output(result))

    def test_ac2_targeted_acceptance_tests_dir_of_this_task_runs_under_role(self):
        """Каталог `tasks/<id>/acceptance_tests` целиком (без имени
        файла) — форма, которой сама эта планка запускается из-под роли
        (`skills/test-authoring.md`) — не блокируется под ARTEL_ROLE.

        Ловит мутацию: guard распознаёт только путь НИЖЕ `tests/`,
        игнорируя вторую половину требования 2 про
        `tasks/<id>/acceptance_tests/` — тогда собственный прогон планки
        роли отказывал бы под ARTEL_ROLE.
        """
        rel = str(ACCEPTANCE_TESTS_DIR.relative_to(REPO_ROOT))
        result = run_pytest([rel, "--collect-only", "-q"], role=ROLE,
                            timeout=60)

        self.assertEqual(result.returncode, 0, combined_output(result))
        self.assertNotIn(REASON_MARKER, combined_output(result))
        self.assertIn(TASK_ID, rel)


if __name__ == "__main__":
    unittest.main()
