"""AC-5 (SPEC 01M3H3K73XBMJMD0EPXZX6HYY9): запись журнала об окружении
либо явно помечена как описание окружения ПУЛЬТА, либо несёт PATH роли — и
существующие читатели записи от этого не ломаются.

Красен до реализации: `agent_log.environment_fingerprint()` отдаёт
`python=<версия> (<путь>), git=…, claude=…` — ни слова о том, чьё это
окружение, и без PATH роли; ни одна из двух ветвей критерия сегодня не
выполнена.

Предмет — значение `agent_log.environment_fingerprint()`: это
единственный источник записи об окружении на весь пульт (её печатают
`runner.py` двумя журнальными событиями шага и `advance_gates/
acceptance.py` — обе ветви критерия, и «помечена», и «несёт PATH роли»,
реализуемы только внутри неё: у префикса журнального события PATH роли
взять негде).

Читатели, чей контракт тест сверяет, — залоченная планка
`tasks/01M1SHK3MD4ZF9NYXSCT67J8AP/acceptance_tests/
test_python_bootstrap.py::test_ac6_role_step_python_field_format_is_unchanged`
(первое поле записи — ровно `python=<версия> (<путь>)`) и
`tests/test_agent_log.py::EnvironmentFingerprintTest` (запись несёт версию
интерпретатора и путь `sys.executable`). Оба читают запись как есть,
поэтому маркер или PATH обязаны прийти НЕ ценой первого поля.
"""
import platform
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import agent_log  # noqa: E402

from _step_env import ProviderStepEnvSandbox  # noqa: E402

#: Слова, которыми запись называет предмет своего описания — окружение
#: САМОГО пульта (оркестратора), а не шага роли. Перечень, а не единственная
#: формулировка: критерий требует явной пометки, а не конкретных слов.
CONSOLE_MARKERS = ("пульт", "оркестратор", "orchestrator")

#: Первое поле записи в том виде, в котором его читает залоченная планка
#: 01M1SHK3MD4ZF9NYXSCT67J8AP (см. докстринг модуля).
PYTHON_FIELD_RE = r"^python=[^\s(]+ \([^)]+\)$"


class EnvironmentJournalRecordTest(ProviderStepEnvSandbox):
    """Песочница шага здесь нужна не ради шага: ветка «запись несёт PATH
    роли» реализуется обращением к `runner.role_env`, а он без временного
    venv и подменённой сверки стека отказал бы `OSError` в рабочей копии
    задачи (своего `.artel/` worktree не несёт) — тест краснел бы на
    состоянии каталога, а не на записи."""

    def fingerprint(self):
        """Запись об окружении, снятая заново: модульный кэш сбрасывается
        до и после — иначе значение, собранное другим тестом процесса,
        подменило бы предмет проверки."""
        agent_log._environment_fingerprint_cache = None
        self.addCleanup(setattr, agent_log,
                        "_environment_fingerprint_cache", None)
        return agent_log.environment_fingerprint()

    def test_ac5_record_is_marked_as_the_console_environment_or_carries_the_role_path(self):
        """Запись об окружении либо называет словами, что описывает
        окружение пульта, либо несёт PATH — одно из двух обязательно.

        Ловит мутацию: интерпретатор шага починен, а запись оставлена как
        была — Оператор по-прежнему читает `python=3.13.12 (…)` как «вот
        что видит шаг» (ровно то заблуждение, из которого выросла задача:
        строка 27.09 описывала пульт, а шаг видел 3.9), и ни маркера, ни
        PATH в записи не находится.
        """
        text = self.fingerprint()

        marked = any(word in text.lower() for word in CONSOLE_MARKERS)
        carries_path = re.search(r"PATH=\S", text) is not None

        self.assertTrue(
            marked or carries_path,
            f"запись не помечена как окружение пульта и не несёт PATH: "
            f"{text!r}")

    def test_ac5_existing_readers_of_the_record_keep_working(self):
        """Существующие читатели записи не ломаются: первое поле остаётся
        ровно `python=<версия> (<путь>)`, а сама запись по-прежнему несёт
        версию интерпретатора и путь `sys.executable`.

        Ловит мутацию: маркер или PATH дописаны В НАЧАЛО записи (или внутрь
        python-поля) — залоченная планка 01M1SHK3MD4ZF9NYXSCT67J8AP,
        читающая первое поле шаблоном ровно из двух частей, краснеет, и
        правку записи пришлось бы оплачивать правкой залоченной планки.
        """
        text = self.fingerprint()

        self.assertRegex(text.split(", ")[0], PYTHON_FIELD_RE)
        self.assertIn(platform.python_version(), text)
        self.assertIn(sys.executable, text)


if __name__ == "__main__":
    unittest.main()
