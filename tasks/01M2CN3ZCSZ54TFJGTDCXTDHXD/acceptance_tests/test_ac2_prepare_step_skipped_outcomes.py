"""AC-2 (SPEC.md): `_prepare_step` воспроизводит все пять исходов
SKIPPED (промпт не записан; окружение роли не создано; рабочий
каталог роли не создан; промпт не прочитан; claude CLI не найден) с
прежними текстами возврата и прежними записями журнала.

Пять тестов ниже проверяют это ЧЁРНЫМ ЯЩИКОМ — через публичный
`run_agent_once` (SPEC 01M2CN3ZCSZ54TFJGTDCXTDHXD/SPEC.md, AC-1:
«значение и тип возврата run_agent_once не меняются»), а не прямым
вызовом `_prepare_step`: SPEC не называет сигнатуру `_prepare_step`
(её аргументы, порядок, что именно она возвращает при успехе), а
AC-3 относит открытие файла промпта и вызов `spawn_agent` уже к
`_spawn_and_wait` — то есть где именно физически расположены две
последние из пяти проверок (промпт не прочитан; CLI не найден),
SPEC не фиксирует однозначно. Пять текстов и пять записей журнала,
которые обязан воспроизвести исход `run_agent_once`, однозначны и
дословно взяты из текущей реализации (tests/test_agent_log.py:606,
tests/test_agent_prompt.py:257, tests/test_multitarget.py:881,
материалы SPEC) — они и проверяются, независимо от того, какой именно
приватный помощник их произвёл внутри модуля.

Красен до реализации: нет — на текущем, ещё не разложенном
`run_agent_once` все пять сценариев уже дают ровно эти тексты и записи
(поведение не меняется, разбор целиком внутри модуля). Зелёный с
рождения: тексты и адреса мест отказа (`Path.write_text`, `role_env`,
`role_cwd`, `open`, `spawn_agent`) сверены с текущим исходником
orchestrator/runner.py и live-прогоном этой же песочницы перед сдачей
планки — красен этот файл станет, только если разбор ПОМЕНЯЕТ один из
пяти текстов/записей журнала, что и есть предмет проверки.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunAgentOnceSandbox  # noqa: E402


class PrepareStepSkippedOutcomesTest(RunAgentOnceSandbox):

    def test_ac2_unwritable_prompt_is_skipped_with_the_same_text(self):
        """Промпт не записался на диск (`Path.write_text` бросает
        `OSError`) — исход "skipped" с текстом «промпт не записан: …» и
        записью журнала «промпт не записан в <путь>: …», `spawn_agent`
        не зовётся вовсе (шаг не успел дойти до запуска процесса).

        Ловит мутацию: разработчик меняет текст на «не удалось записать
        промпт» или переносит первым пункт `role_env` вместо записи
        промпта — оба `assertEqual` ниже откажут (первый на исходе,
        второй косвенно: если `role_env` вызван раньше, тест AC-2 про
        него получил бы другой набор журнала).
        """
        with mock.patch.object(Path, "write_text",
                               side_effect=OSError("диск переполнен")), \
                mock.patch.object(runner, "spawn_agent") as spawn:
            outcome = self.run_once()

        spawn.assert_not_called()
        self.assertEqual(outcome[0], "skipped")
        self.assertTrue(outcome[1].startswith("промпт не записан:"), outcome[1])
        self.assertIsNone(outcome[2])
        details = self.journal_details("agent run SKIPPED")
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].startswith("промпт не записан в "), details[0])
        self.assertIn("диск переполнен", details[0])

    def test_ac2_unavailable_role_env_is_skipped_with_the_same_text(self):
        """Окружение роли не собралось (`role_env` бросает `OSError`) —
        исход "skipped" с текстом «окружение роли не подготовлено: …» и
        записью журнала «каталог окружения роли не создан: …».

        Ловит мутацию: помощник перестаёт останавливать шаг на этой
        ошибке (например, `except` сужен до конкретного подкласса
        `OSError` и общий `OSError("нет места")` проходит мимо) —
        `spawn_agent` был бы вызван, `assert_not_called` откажет.
        """
        with mock.patch.object(runner, "role_env",
                               side_effect=OSError("нет места")), \
                mock.patch.object(runner, "spawn_agent") as spawn:
            outcome = self.run_once()

        spawn.assert_not_called()
        self.assertEqual(
            outcome, ("skipped", "окружение роли не подготовлено: нет места", None))
        self.assertEqual(
            self.journal_details("agent run SKIPPED"),
            ["каталог окружения роли не создан: нет места"])

    def test_ac2_unavailable_role_cwd_is_skipped_with_the_same_text(self):
        """Рабочий каталог роли не собрался (`role_cwd` бросает
        `OSError`) — исход "skipped" с текстом «рабочий каталог роли не
        подготовлен: …» и записью журнала «рабочий каталог роли не
        создан: …».

        Ловит мутацию: проверка `role_cwd` переставлена ПОСЛЕ открытия
        файла промпта/запуска агента (перепутанный порядок фаз при
        разборе) — тогда до `role_cwd` уже случился бы вызов `open`/
        `spawn_agent`, и `assert_not_called` на `spawn_agent` ниже
        откажет первым.
        """
        with mock.patch.object(runner, "role_cwd",
                               side_effect=OSError("диск недоступен")), \
                mock.patch.object(runner, "spawn_agent") as spawn:
            outcome = self.run_once()

        spawn.assert_not_called()
        self.assertEqual(
            outcome,
            ("skipped", "рабочий каталог роли не подготовлен: диск недоступен",
             None))
        self.assertEqual(
            self.journal_details("agent run SKIPPED"),
            ["рабочий каталог роли не создан: диск недоступен"])

    def test_ac2_unreadable_prompt_is_skipped_with_the_same_text(self):
        """Файл промпта пропал между записью и чтением (`open` бросает
        `FileNotFoundError`) — исход "skipped" с текстом «промпт не
        прочитан: …», а НЕ «claude CLI не найден» (обе беды приходят
        одним и тем же классом исключения, различает их только место
        перехвата — см. докстринг соответствующей ветки в runner.py).

        Ловит мутацию: перехват `open()` объединяют с перехватом
        `spawn_agent()` в один `try/except FileNotFoundError` — пропавший
        файл промпта тогда отчитывался бы Оператору как «claude CLI не
        найден», уводя его чинить установку CLI вместо диска;
        `assertNotIn("CLI не найден", ...)` ниже откажет.
        """
        with mock.patch.object(runner, "open",
                               side_effect=FileNotFoundError("нет файла"),
                               create=True), \
                mock.patch.object(runner, "spawn_agent") as spawn:
            outcome = self.run_once()

        spawn.assert_not_called()
        self.assertEqual(
            outcome, ("skipped", "промпт не прочитан: нет файла", None))
        self.assertNotIn("CLI не найден", outcome[1])
        details = self.journal_details("agent run SKIPPED")
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].startswith("промпт не прочитан из "), details[0])

    def test_ac2_missing_cli_is_skipped_with_the_same_text(self):
        """`spawn_agent` не находит бинарь claude (`FileNotFoundError`) —
        исход "skipped" с текстом «claude CLI не найден» и записью
        журнала «claude CLI не найден, промпт: <путь>» — промпт уже
        записан на диск ДО этой попытки, путь называется буквально, для
        ручного прогона роли.

        Ловит мутацию: путь к промпту выпадает из текста записи журнала
        (например, разработчик решает, что путь уже назван записью
        «agent run started» и не дублирует его) — `assertIn(str(path), …)`
        откажет, хотя именно этот путь Оператор копирует для ручного
        запуска роли.
        """
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=FileNotFoundError):
            outcome = self.run_once()

        self.assertEqual(outcome, ("skipped", "claude CLI не найден", None))
        details = self.journal_details("agent run SKIPPED")
        self.assertEqual(len(details), 1)
        self.assertTrue(details[0].startswith("claude CLI не найден, промпт: "),
                        details[0])
        prompt_path = details[0].split("промпт: ", 1)[1]
        self.assertTrue(Path(prompt_path).is_file(),
                        "промпт обязан лежать на диске для ручного прогона")
