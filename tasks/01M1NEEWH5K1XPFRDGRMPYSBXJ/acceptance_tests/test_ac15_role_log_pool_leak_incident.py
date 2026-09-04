"""AC-15 (SPEC.md): после прогона канарейки и при `doctor` логи шагов
ролей проверяются на упоминание каталога пула, имени его репозитория и
GUID любого шаблона; тест: лог с таким упоминанием поднимает алерт
`kind=incident`, лог без него — не поднимает.

Наблюдаемый вход — файл в `config.LOGS` (`<task>-<role>-N.log`, именно
так их создаёт `orchestrator/agent_log.py::new_agent_log`, единственное
существующее место записи персистентного лога роли); наблюдаемый выход
— строка в таблице `alerts` с `kind="incident"` (`orchestrator/
alerts.py`, единственный существующий носитель инцидентов, которым уже
пользуются соседние проверки `doctor` — `recovery_check`/`check_orphans`
и т.п.). Между входом и выходом — «на каждом doctor» (буквально из
требования 13б) — самый прямой и при этом НЕ гадающий о будущем имени
внутренней функции публичный путь: команда `artel.py doctor`.

Контраст, не точный текст алерта: критерий проверяется СРАВНЕНИЕМ двух
независимых прогонов `doctor` — с «утёкшим» логом и с чистым, при
одинаковом иначе окружении — а не разбором формулировки сообщения
алерта (её SPEC не фиксирует, поэтому проверка текста рисковала бы
покраснеть от несовпадения слов, а не от отсутствия механики). Из трёх
перечисленных в требовании 13б сигналов утечки («каталог пула, имя его
репозитория, GUID шаблона») тест использует ПУТЬ КАТАЛОГА ПУЛА — он же
единственный из трёх, буквально и однозначно зафиксированный кодом
самого SPEC (`~/.artel-canary`, требование 1, `self.pool_dir` этой же
песочницы); «имя репозитория пула» — внешняя настройка Оператора
(«Не входит» SPEC: «Инициализация каталога пула ... и его приватного
git-remote ... разовая ручная настройка Оператором»), а точный формат
«canary-GUID» шаблона эта SPEC не определяет (см. `markers.py`, AC-7) —
опираться на них здесь означало бы гадать о ещё не существующем имени
конфигурационного значения, тот же риск «красный не по той причине»,
которого избегает остальная планка этой задачи.

Живой `claude` CLI внутри `doctor` (`live_smoke`/`check_cli_version`)
подменён тем же приёмом, что и в `tests/test_doctor.py::
DoctorCommandTest.healthy_mocks` (`claude_only_run`/`claude_only_popen`
из `tests/sandbox.py` — отвечают только на `cmd[0] == "claude"`,
остальные подпроцессы, включая настоящий `git` этой песочницы, уходят
в настоящий `subprocess`) — без него `doctor` в каждом прогоне теста
дорого и недетерминированно дёргал бы настоящий CLI.

Красен до реализации: сегодня `doctor.all_checks` не содержит вообще никакой проверки логов ролей на утечку пула — `alerts.open_alerts(..., "incident")` остаётся пустым списком и после прогона `doctor` над «утёкшим» логом, положительная половина контраста падает `AssertionError` (алертов не появилось). Отрицательная половина («чистый лог не поднимает алерт») тем самым уже сегодня зелёная — несуществующая проверка не может поднять ложный алерт; она остаётся регрессионным стражем и после реализации задачи, если проверка не получится избыточно жадной.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import CanarySandbox  # noqa: E402

from orchestrator import alerts, config, doctor, store  # noqa: E402
from tests.sandbox import claude_only_popen, claude_only_run  # noqa: E402


def _result_event(usd: float = 0.01) -> str:
    return f'{{"type":"result","total_cost_usd":{usd},"usage":{{}}}}\n'


class _FakeLiveSmokeProc:
    """Замена `subprocess.Popen` живого смоука doctor — тот же приём и
    тот же класс, что `tests/test_doctor.py::FakeLiveSmokeProc`."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


class RoleLogPoolLeakIncidentTest(CanarySandbox):

    def setUp(self):
        super().setUp()

        def which(name):
            return "/usr/bin/claude" if name == "claude" else None

        which_patcher = mock.patch.object(doctor.shutil, "which", side_effect=which)
        which_patcher.start()
        self.addCleanup(which_patcher.stop)

        run_patcher = mock.patch.object(
            doctor.subprocess, "run",
            side_effect=claude_only_run(f"{config.CLI_VERSION_PIN} (Claude Code)\n"))
        run_patcher.start()
        self.addCleanup(run_patcher.stop)

        popen_patcher = mock.patch.object(
            doctor.subprocess, "Popen",
            side_effect=claude_only_popen(_FakeLiveSmokeProc(_result_event())))
        popen_patcher.start()
        self.addCleanup(popen_patcher.stop)

    def _write_role_log(self, name: str, text: str) -> None:
        config.LOGS.mkdir(parents=True, exist_ok=True)
        (config.LOGS / name).write_text(text, encoding="utf-8")

    def _open_incidents(self) -> list:
        return alerts.open_alerts(store.db(), "incident")

    def test_ac15_role_log_mentioning_pool_directory_raises_incident_alert(self):
        """Персистентный лог шага роли (`config.LOGS/T900-developer-1.log`,
        имя — точно то, что заводит `agent_log.new_agent_log`) упоминает
        путь каталога пула (`self.pool_dir`, вне корня пульта, требование
        1) — прогон `artel.py doctor` обязан поднять алерт `kind=incident`.

        Ловит мутацию: разработчик реализует проверку логов только для
        `canary`-прогона (сразу после `cmd_canary`), не подключая её к
        `doctor.all_checks` — тогда этот прогон `doctor` (без канарейки
        рядом) не найдёт утечку вовсе, `open_alerts(..., "incident")`
        останется пустым.
        """
        self.assertEqual(
            self._open_incidents(), [],
            "в чистой песочнице до записи лога уже есть открытые "
            "incident-алерты — сравнение с положительным сценарием "
            "ничего не докажет")

        self._write_role_log(
            "T900-developer-1.log",
            f"· Bash git status\n"
            f"Agent: гружу шаблон из {self.pool_dir}\n"
            f"· Bash cat {self.pool_dir}/shablon-1.md\n")

        out = self.run_cli("doctor")

        incidents = self._open_incidents()
        self.assertTrue(
            incidents,
            f"`doctor` не поднял incident-алерт на лог роли, "
            f"упоминающий каталог пула {self.pool_dir}:\n{out}")

    def test_ac15_role_log_without_pool_mention_does_not_raise_incident_alert(self):
        """Тот же лог-файл, но без единого упоминания пула/канарейки —
        обычный шаг обычной продуктовой задачи. Прогон `artel.py doctor`
        не имеет права поднять по нему incident-алерт: иначе проверка
        ложно тревожит Оператора на КАЖДОМ обычном логе.

        Ловит мутацию: проверка утечки реализована «наоборот» — поднимает
        алерт на любой лог роли независимо от содержимого (например,
        просто по факту существования файла в `config.LOGS`), не по
        факту упоминания пула — тогда этот, заведомо чистый лог тоже
        поднял бы incident, и `assertEqual([], ...)` поймал бы лишний
        элемент в списке.
        """
        self._write_role_log(
            "T900-developer-1.log",
            "· Bash git status\n"
            "Agent: правлю orchestrator/report.py под требование 3\n"
            "· Edit orchestrator/report.py\n")

        out = self.run_cli("doctor")

        self.assertEqual(
            self._open_incidents(), [],
            f"`doctor` поднял incident-алерт на лог роли без единого "
            f"упоминания пула/канарейки:\n{out}")


if __name__ == "__main__":
    unittest.main()
