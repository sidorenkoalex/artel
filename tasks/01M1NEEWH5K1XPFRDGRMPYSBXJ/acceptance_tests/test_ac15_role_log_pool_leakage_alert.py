"""AC-15 (SPEC.md): после прогона канарейки и при `doctor` логи шагов
ролей проверяются на упоминание каталога пула, имени его репозитория и
GUID любого шаблона; тест: лог с таким упоминанием поднимает алерт
`kind=incident`, лог без него — не поднимает.

Прогоняется через триггер `doctor` (второй из двух, названных
критерием буквально «и на каждом doctor») — не через триггер «после
прогона канарейки»: тот происходит ВНУТРИ эфемерного клона (AC-2), чья
собственная синхронизация со сканированием логов до его удаления
(AC-4) — деталь механизма, которую SPEC не называет (только то, ЧТО
логи проверяются, не КОГДА именно относительно уборки клона). `doctor`
— самостоятельная, однозначно определённая точка входа: Оператор
вызывает её когда угодно, критерий называет её дословно, без
интерполяции недокументированного порядка событий.

Лог шага роли — `<task>-<role>-<N>.log` под `config.LOGS`, тот же
формат имени, что `orchestrator/agent_log.py::new_agent_log` уже
использует для ЛЮБОГО реального шага (не специфика этой задачи);
файл сюда кладётся напрямую, не через реальный прогон агента —
`runner.cmd_run` в этой песочнице подменён `SmartAgent`, который
никогда не пишет `agent_log` (см. докстринг `_sandbox.py`).

`claude`/`security` (keychain) не мокаются здесь построчно — `doctor.
check_token`/`check_git_identity` реально дергают `security find-
generic-password`/`git config` (офлайн, read-only, безопасно в любом
окружении); только `claude --version`/живой смоук (`subprocess.Popen`)
подменены — иначе `doctor.live_smoke` реально запустил бы установленный
`claude` CLI (`orchestrator/doctor.py::_live_smoke_run`), потенциально
платный сетевой вызов, которому в приёмочном тесте не место (тот же
принцип, что `tests/test_doctor.py::DoctorCommandTest.healthy_mocks`).

Красен до реализации: в текущем `doctor.py` нет проверки логов шагов
ролей на упоминание каталога пула/GUID пула — после планового
упоминания каталога пула в логе шага роли `doctor` не заводит НИКАКОГО
нового `kind=incident` алерта с этим упоминанием; первая содержательная
проверка (наличие такого алерта после прогона `doctor`) падает
`AssertionError`, не по опечатке песочницы (сам файл лога кладётся и
читается напрямую, без посредничества ещё не написанного кода).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import CanarySandbox  # noqa: E402

from orchestrator import config, doctor, store  # noqa: E402

_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen


class _FakeLiveSmokeProc:
    """`subprocess.Popen`-заглушка живого смоука `doctor` (SPEC T101/
    T037): успешный ответ с событием стоимости, без единого реального
    сетевого байта."""

    def __init__(self):
        self.returncode = 0

    def communicate(self, timeout=None):
        return '{"type":"result","total_cost_usd":0.0,"usage":{}}\n', None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return 0


def _claude_only_run(args, **kwargs):
    """`subprocess.run` только для `claude ...` (версия CLI) — остальное
    (`security`, `git`) уходит в настоящий `subprocess.run`, тем же
    приёмом, что `tests/sandbox.py::claude_only_run`."""
    if args and args[0] == "claude":
        return subprocess.CompletedProcess(
            args, 0, f"{config.CLI_VERSION_PIN} (Claude Code)\n", "")
    return _REAL_RUN(args, **kwargs)


def _claude_only_popen(cmd, *args, **kwargs):
    if cmd and cmd[0] == "claude":
        return _FakeLiveSmokeProc()
    return _REAL_POPEN(cmd, *args, **kwargs)


class RoleLogPoolLeakageAlertTest(CanarySandbox):

    def setUp(self):
        super().setUp()
        self._run_patcher = mock.patch.object(
            doctor.subprocess, "run", side_effect=_claude_only_run)
        self._popen_patcher = mock.patch.object(
            doctor.subprocess, "Popen", side_effect=_claude_only_popen)
        self._run_patcher.start()
        self._popen_patcher.start()
        self.addCleanup(self._run_patcher.stop)
        self.addCleanup(self._popen_patcher.stop)

    def _write_role_log(self, name: str, text: str) -> None:
        config.LOGS.mkdir(parents=True, exist_ok=True)
        (config.LOGS / name).write_text(text, encoding="utf-8")

    def _incident_messages(self) -> list[str]:
        return [a["message"] for a in store.open_alerts(store.db(), "incident")]

    def test_ac15_log_mentioning_pool_dir_raises_an_incident_alert(self):
        """Лог шага роли `developer` буквально упоминает путь каталога
        пула (`self.pool_dir`, вне корня пульта, требование 1). После
        такого лога `doctor` обязан завести открытый `kind=incident`
        алерт, называющий это упоминание.

        Ловит мутацию: разработчик реализует AC-14 (запрещающие правила
        CLI роли), но пропускает отдельную AC-15 (сверку УЖЕ
        случившихся логов на упоминание) — тогда `doctor` проходит
        чисто, новых `incident`-алертов про лог/пул не появляется, и
        этот тест отличает такой пропуск от честной реализации.
        """
        self._write_role_log(
            "T900-developer-1.log",
            f"шаг роли: читаю {self.pool_dir}/malaya-pravka.md по ошибке\n")

        out = self.run_cli("doctor")

        self.assertNotIn("Traceback", out, out)
        messages = self._incident_messages()
        leak_alerts = [m for m in messages if str(self.pool_dir) in m]
        self.assertTrue(
            leak_alerts,
            f"после лога с упоминанием каталога пула {self.pool_dir} "
            f"`doctor` не завёл incident-алерт с этим путём; открытые "
            f"incident-алерты: {messages}\nвывод doctor:\n{out}")

    def test_ac15_log_without_a_mention_raises_no_such_alert(self):
        """Контрольная пара: лог шага роли без какого-либо упоминания
        каталога/репозитория/GUID пула — `doctor` не заводит про него
        incident-алерт (различает «есть упоминание» от «лога вообще
        не было», а не просто «doctor всегда молчит»).

        Ловит мутацию: реализация AC-15 срабатывает на КАЖДЫЙ лог
        шага роли безусловно (не ищет реальное упоминание) — тогда
        обычный, чистый лог тоже завёл бы incident-алерт, и тест это
        поймает.
        """
        self._write_role_log(
            "T901-developer-1.log",
            "шаг роли: обычная синтетическая правка, без упоминаний пула\n")

        out = self.run_cli("doctor")

        self.assertNotIn("Traceback", out, out)
        messages = self._incident_messages()
        leak_alerts = [m for m in messages if str(self.pool_dir) in m]
        self.assertFalse(
            leak_alerts,
            f"чистый лог без упоминания каталога пула всё равно завёл "
            f"incident-алерт с путём пула: {leak_alerts}\nвывод doctor:\n{out}")


if __name__ == "__main__":
    unittest.main()
