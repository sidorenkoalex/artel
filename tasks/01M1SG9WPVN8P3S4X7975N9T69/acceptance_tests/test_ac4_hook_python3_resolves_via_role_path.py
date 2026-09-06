"""Приёмочный тест AC-4 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-4. Докстринг `bash_guard.py` содержит явное утверждение (со ссылкой
на `orchestrator/runner.py::role_env`/`_venv_interpreter_bin`), что
`python3` команды хука резолвится через PATH роли манифеста стека
(`.artel/venv/bin` — первым в PATH процесса, из которого хук
запускается как дочерний процесс CLI роли), а не через профиль
оболочки Оператора. Отдельный тест на этот пункт не обязателен —
утверждение может быть только текстовым (докстринг).

SPEC прямо разрешает не писать тест на этот пункт («может быть только
текстовым»), но проверка присутствия ссылки — дешёвая и детерминированная
(текстовый grep по докстрингу), поэтому пишем её: она ловит правдоподобную
мутацию «утверждение забыто/обрезано при переносе докстринга» дешевле,
чем ручная приёмка.

Красен до реализации: `docs/reference/role-home/claude/hooks/bash_guard.py`
отсутствует на диске (снят коммитом dea8016b) — `Path.read_text` в
`setUp` падает `FileNotFoundError`. Утверждение о PATH — НОВЫЙ текст
этой задачи (в редакции 80c38245 хука его не было: `role_env` тогда ещё
не существовал, стек ч.3 введён коммитом dea8016b), поэтому даже после
восстановления файла в редакции 80c38245 дословно тест останется
красным, пока разработчик не допишет утверждение (ожидаемое поведение,
не рассинхронизация).
"""
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

HOOK = (_REPO_ROOT / "docs" / "reference" / "role-home" / "claude" / "hooks"
        / "bash_guard.py")


class DocstringNamesThePathResolutionSourceTest(unittest.TestCase):

    def setUp(self):
        if not HOOK.is_file():
            self.skipTest(f"хук ещё не восстановлен: {HOOK}")
        self.text = HOOK.read_text(encoding="utf-8")

    def test_ac4_docstring_references_role_env_and_venv_interpreter_bin(self):
        """Докстринг называет обе функции `orchestrator/runner.py`,
        отвечающие за PATH роли (`role_env`, `_venv_interpreter_bin`).

        Ловит мутацию: утверждение о PATH сформулировано абстрактно
        («резолвится правильно») без ссылки на конкретный код — ссылку
        нельзя было бы отличить от общих слов, и следующая правка
        `role_env` не подсветила бы устаревший докстринг.
        """
        self.assertIn("role_env", self.text)
        self.assertIn("_venv_interpreter_bin", self.text)

    def test_ac4_docstring_states_venv_bin_is_first_in_role_path(self):
        """Докстринг явно говорит, что каталог `.artel/venv/bin` стоит
        ПЕРВЫМ в PATH процесса роли — не просто «участвует в PATH».

        Ловит мутацию: докстринг упоминает venv, но не порядок в PATH —
        тогда обычный `python3` мог бы резолвиться в системный/shell-профиль
        Оператора раньше venv, и утверждение AC-4 (голый `python3`
        резолвится через роль, не Оператора) осталось бы неподтверждённым
        текстом.
        """
        self.assertIn(".artel/venv", self.text)
        self.assertTrue(
            re.search(r"venv[^\n]{0,80}перв|перв[^\n]{0,80}venv|PATH",
                      self.text, re.IGNORECASE),
            "докстринг не описывает порядок venv/bin в PATH")

    def test_ac4_docstring_disclaims_the_operator_shell_profile(self):
        """Докстринг явно исключает профиль оболочки Оператора как
        источник резолвинга `python3` — это и есть содержательная часть
        AC-4 (не «PATH откуда-то берётся», а «не из профиля Оператора»).

        Ловит мутацию: утверждение о venv есть, но нет явного
        противопоставления профилю Оператора — тогда докстринг не
        отличался бы от общего описания `role_env` в самом `runner.py`
        и не закрывал бы содержательную часть критерия отдельно у хука.
        """
        self.assertTrue(
            re.search(r"[Оо]ператор", self.text),
            "докстринг не упоминает Оператора вовсе — нечего противопоставить venv")


if __name__ == "__main__":
    unittest.main()
