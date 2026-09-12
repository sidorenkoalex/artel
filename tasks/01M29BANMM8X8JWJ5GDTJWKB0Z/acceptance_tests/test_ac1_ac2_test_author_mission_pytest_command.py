"""AC-1, AC-2 (SPEC 01M29BANMM8X8JWJ5GDTJWKB0Z) — пункт 5 миссии
test_author в `orchestrator/role_prompt.py` даёт команду pytest той же
формы, что `acceptance._pytest_command`, со значением таймаута из
`stack.PER_TEST_TIMEOUT_SEC` (не литералом), а остальной текст пункта 5
(автокоммит, неприкосновенность кода и SPEC.md) не меняется.

`brief.test_author_answer_component` заглушён `return_value=None` —
эта функция читает задачу из БД (`_artifact_source_branch` ->
`artifact_source.resolve`), а свойство, которое проверяют эти тесты,
целиком лежит в тексте `mission`, не в `brief_text`: заводить настоящую
БД-фикстуру только ради незадействованного возврата — лишняя зависимость
без дополнительного сигнала.

Красен до реализации: пункт 5 миссии test_author сегодня несёт
`python3 -m unittest discover -s <task_ref>/acceptance_tests` буквально
(`orchestrator/role_prompt.py:63`) — три из четырёх тестов красные:
оба `test_ac1_...` (нет ни литеральной pytest-команды, ни подстановки
999 вместо неё) и `test_ac2_old_unittest_discover_command_is_gone`
(старая команда сегодня как раз на месте). Четвёртый,
`test_ac2_rest_of_step5_wording_...`, зелёный уже сегодня — фраза про
автокоммит и неприкосновенность кода/SPEC.md в текущем тексте уже
такая, какой требование 1 её и оставляет («остальной текст пункта —
без изменений»); тест фиксирует это свойство и как планку до, и как
регресс-проверку после правки.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import brief, role_prompt, stack  # noqa: E402


class TestAuthorMissionPytestCommandTest(unittest.TestCase):

    TASK_ID = "01M29BANMM8X8JWJ5GDTJWKB0Z-FIXTURE"

    def _mission(self):
        with mock.patch.object(brief, "test_author_answer_component",
                               return_value=None):
            mission, _, _ = role_prompt.mission_brief_package(
                None, self.TASK_ID, {"branch": "task/fixture-branch"},
                "test_author", "/tmp/fixture-cwd")
        return mission

    def test_ac1_step5_gives_the_pytest_command_form_with_constant_timeout(self):
        """Пункт 5 миссии test_author несёт буквально команду
        `python3 -m pytest <task_ref>/acceptance_tests -p no:cacheprovider
        -p timeout -o timeout=<stack.PER_TEST_TIMEOUT_SEC>` — та же форма,
        что `acceptance._pytest_command`, со значением таймаута,
        подставленным из СЕГОДНЯШНЕГО значения константы.

        Ловит мутацию: любой из флагов `-p no:cacheprovider`/`-p timeout`
        потерян, переставлен местами с `-o timeout=...`, либо каталог
        `<task_ref>/acceptance_tests` подставлен без префикса `tasks/` —
        точный `assertIn` не находит совпадения.
        """
        mission = self._mission()
        expected = (
            f"python3 -m pytest tasks/{self.TASK_ID}/acceptance_tests "
            f"-p no:cacheprovider -p timeout -o "
            f"timeout={stack.PER_TEST_TIMEOUT_SEC}")
        self.assertIn(expected, mission)

    def test_ac1_timeout_value_tracks_the_constant_not_a_hardcoded_120(self):
        """При подмене `stack.PER_TEST_TIMEOUT_SEC` на заведомо другое
        значение (999, не равное сегодняшнему 120) собранная миссия несёт
        именно 999 — значение подставлено чтением константы в момент
        сборки миссии, а не записано литералом `120` во время правки кода.

        Ловит мутацию: пункт 5 несёт `-o timeout=120` литералом вместо
        `-o timeout={stack.PER_TEST_TIMEOUT_SEC}` — при подмене константы
        текст миссии не меняется, `assertIn("timeout=999", ...)` падает.
        """
        with mock.patch.object(stack, "PER_TEST_TIMEOUT_SEC", 999):
            mission = self._mission()
        self.assertIn("timeout=999", mission)
        self.assertNotIn("timeout=120", mission)

    def test_ac2_rest_of_step5_wording_about_commit_and_untouchables_unchanged(self):
        """Фразы пункта 5 про то, что каталог задачи коммитить не нужно
        (автокоммит оркестратора переносит артефакты в артефактную ветку)
        и что код репозитория и SPEC.md трогать нельзя, остаются в
        мисии test_author буквально теми же — меняется только сама
        команда прогона.

        Ловит мутацию: правка команды заодно переписывает или укорачивает
        соседний текст про автокоммит/неприкосновенность (например,
        роняет упоминание SPEC.md) — `assertIn` на точные фразы ниже
        перестаёт находить совпадение.
        """
        mission = self._mission()
        self.assertIn(
            "tasks/<id>/ коммитить не нужно — автокоммит оркестратора "
            "сам перенесёт написанное в артефактную ветку.", mission)
        self.assertIn("Код репозитория и SPEC.md НЕ трогай.", mission)

    def test_ac2_old_unittest_discover_command_is_gone(self):
        """Прежняя команда `unittest discover` не остаётся в миссии рядом
        с новой pytest-командой (SPEC требование 1 — команда ЗАМЕНЕНА,
        не продублирована).

        Ловит мутацию: pytest-команда добавлена ВТОРОЙ строкой, а старая
        `python3 -m unittest discover -s ...` осталась в тексте пункта —
        `assertNotIn` находит совпадение и падает.
        """
        mission = self._mission()
        self.assertNotIn("unittest discover", mission)


if __name__ == "__main__":
    unittest.main()
