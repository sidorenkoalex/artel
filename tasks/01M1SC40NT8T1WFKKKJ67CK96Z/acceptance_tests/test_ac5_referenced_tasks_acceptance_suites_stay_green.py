"""Приёмочный тест 01M1SC40NT8T1WFKKKJ67CK96Z — AC-5: приёмочные тесты
задач 01M1R8B3ZKXQT0Z0G6QQQDV906 и 01M1RHFRQ2C0P4A57XJJ1WZV8N зелёные без
правки утверждений.

Область теста ниже — ТОЛЬКО 01M1RHFRQ2C0P4A57XJJ1WZV8N: его
`acceptance_tests/` присутствуют в дереве этой ветки (`git ls-tree -r
HEAD -- tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests/`, проверено
при написании — 5 файлов) и прогоняются `unittest discover` прямо
отсюда так же, как в его собственной приёмке.

01M1R8B3ZKXQT0Z0G6QQQDV906 сюда сознательно НЕ включена: её
`acceptance_tests/` в дереве ЭТОЙ ветки нет вовсе — `git log --all
--oneline -- tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests` называет
только три коммита («артефакты шага test_author», «снапшот закрытия
(killed)»), ни один из которых не входит в историю `main`/этой ветки
(`git merge-base --is-ancestor <тот коммит> HEAD` — «NOT ANCESTOR»,
проверено); каталог живёт только на артефактной ветке пульта
`origin/artifact/01m1r8b3zkxqt0z0g6qqqdv906`, которую CI job `python`
(`.github/workflows/ci.yml`) не тянет (`actions/checkout@v4` без
`fetch-depth: 0` — только текущий коммит, без сторонних веток), и
которую по конвенции репозитория (`skills/conventions-core.md`, «Никогда:
… `git remote add`/сетевые операции с посторонними ветками из шага роли»)
доставать здесь сетевым `git fetch` тоже неверно — тесты этого пакета
нигде не заводят живой git/сеть (`tests/sandbox.py::fake_git`,
инвариант 35 `tests/test_invariants.py`), а привязка к конкретному
удалённому ref, которого может не быть в чекауте разработчика/CI,
сделала бы этот тест хрупким по причине, не связанной с самим
рефакторингом. Это внешняя интеграция без тестового контура в этой
песочнице (см. `# AC-5: manual` ниже) — Оператор проверяет зелёность
01M1R8B3ZKXQT0Z0G6QQQDV906 вручную (checkout
`artifact/01m1r8b3zkxqt0z0g6qqqdv906`, `unittest discover` там) на
приёмке; вопрос интерпретации критерия здесь не стоит — только
отсутствие стенда в этой песочнице, поэтому пометка `manual`, не
`escalate` (не блокирует переход задачи дальше `tests_writing`).

Зелёный с рождения: `tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests/`
зелёные уже сегодня (прогон при написании этого файла — 10 тестов, OK) —
тест ниже замыкает наблюдаемое следствие требования 5 SPEC, не новую
функциональность.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class ReferencedTaskAcceptanceSuiteStaysGreenTest(unittest.TestCase):

    def test_ac5_01m1rhfrq2c0p4a57xjj1wzv8n_acceptance_suite_is_fully_green(self):
        """`python3 -m unittest discover -s tasks/
        01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests` завершается нулевым
        кодом и без FAILED/ERROR в выводе.

        Ловит мутацию: рефакторинг `_cmd_auto` меняет поведение рубежа
        регрессии №13 (не только его структуру) — любой из 10
        существующих тестов этого пакета, сверяющих буквальный текст
        отказа/журнала того же рубежа, покраснеет.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s",
             "tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests", "-v"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)

        self.assertEqual(
            0, result.returncode,
            f"AC-5: tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests "
            f"обязаны остаться зелёными без правки утверждений.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        self.assertNotIn("FAILED", result.stderr)
        self.assertNotIn("FAILED", result.stdout)


# AC-5: manual — половина критерия про 01M1R8B3ZKXQT0Z0G6QQQDV906 не
# имеет стенда в дереве этой ветки (см. докстринг модуля): её
# acceptance_tests/ существуют только на origin/artifact/
# 01m1r8b3zkxqt0z0g6qqqdv906, который CI job "python" не тянет
# (actions/checkout без fetch-depth: 0) и который сетевым git fetch
# доставать из теста неверно по конвенции («не заводить живой git/сеть
# в tests/», инвариант 35) — внешняя интеграция без тестового контура в
# этой песочнице. Формулировка критерия не двусмысленна (не требует
# решения Оператора об интерпретации), поэтому это `manual`, не
# `escalate`: Оператор на приёмке проверяет зелёность
# 01M1R8B3ZKXQT0Z0G6QQQDV906 вручную (checkout
# `artifact/01m1r8b3zkxqt0z0g6qqqdv906`, `python3 -m unittest discover
# -s tasks/01M1R8B3ZKXQT0Z0G6QQQDV906/acceptance_tests` там), автомат
# выше тем временем закрывает вторую, стендом обеспеченную половину.


if __name__ == "__main__":
    unittest.main()
