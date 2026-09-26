"""Юнит-тесты `doctor.check_role_log_pool_leak`/`check_token_repo_scope`
(SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13б/13в) — вызовы функций
напрямую, без полного `cmd_doctor` (тот прогон, включая AC-15 с реальным
`config.LOGS`, покрыт приёмочными тестами `tasks/
01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`).

Отбор файлов каталога логов (SPEC 01M3F7BYE82S9AQCBSP1RTQQTR, требование
7): логи шагов ролей ОБОИХ провайдеров читаются независимо от формата
содержимого (в том числе JSONL `codex exec --json`), записи сессий
Оператора (`*.session.log`) не читаются вовсе — «не читает» проверяется
слежкой за `Path.read_text`, а не отсутствием срабатывания.

`CanaryPoolDriftCheckTest` — `doctor.check_canary_pool_drift` (SPEC
01M1NSR5M5THYRC0RFWPMVE2DW, требование 3/AC-8) вызовом функции напрямую;
полный сценарий через `doctor` CLI и обе команды восстановления уже
покрыт приёмочными тестами `tasks/01M1NSR5M5THYRC0RFWPMVE2DW/
acceptance_tests/`.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, doctor, store  # noqa: E402


class RoleLogPoolLeakCheckTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("LOGS", self.root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()

    def test_no_logs_directory_is_ok_and_raises_nothing(self):
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(self.conn, "incident"), [])

    def test_clean_log_is_ok(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            "Обычный шаг роли: правка кода, коммит, готово.\n",
            encoding="utf-8")
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(self.conn, "incident"), [])

    def test_leaking_log_fails_and_raises_one_incident_alert(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            f"Agent: гружу шаблон из ~/{config.CANARY_POOL_DIRNAME}/x.md\n",
            encoding="utf-8")
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "fail")
        incidents = alerts.open_alerts(self.conn, "incident")
        self.assertEqual(len(incidents), 1)
        self.assertIn(config.CANARY_POOL_DIRNAME, incidents[0]["message"])

    def test_two_runs_over_the_same_leaking_log_do_not_duplicate_the_alert(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            f"~/{config.CANARY_POOL_DIRNAME}/x.md\n", encoding="utf-8")
        doctor.check_role_log_pool_leak(self.conn)
        doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(len(alerts.open_alerts(self.conn, "incident")), 1)

    # --- логи обоих провайдеров и записи сессий Оператора (SPEC
    #     01M3F7BYE82S9AQCBSP1RTQQTR, требование 7) ----------------------

    #: Лог шага роли на Codex: `codex exec --json`, то есть JSONL, а не
    #: строки текста, — формат содержимого, которого проверка до этой
    #: задачи не видела.
    CODEX_LOG = "01M32NH6P053978AER66P0X4GN-developer-1.log"
    #: Запись сессии Оператора — имя из живого разбора 21.09
    #: (docs/backlog.md, строка 3 копилки): именно они давали ложные
    #: срабатывания.
    SESSION_LOG = "canary-20260911T230820Z.session.log"

    def codex_jsonl(self) -> str:
        marker = config.CANARY_POOL_DIRNAME
        return "\n".join(json.dumps(event, ensure_ascii=False) for event in (
            {"type": "thread.started", "thread_id": "th-1"},
            {"type": "item.completed",
             "item": {"type": "command_execution",
                      "command": f"ls ~/{marker}/templates",
                      "aggregated_output": "ok"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10}},
        )) + "\n"

    def read_names(self) -> tuple:
        """(список имён прочитанных файлов, контекст слежки за чтением):
        «не читает» проверяется буквально, а не отсутствием
        срабатывания."""
        seen = []
        real_read_text = Path.read_text

        def spy(self_path, *args, **kwargs):
            seen.append(self_path.name)
            return real_read_text(self_path, *args, **kwargs)

        return seen, mock.patch.object(Path, "read_text", spy)

    def test_codex_step_log_in_jsonl_is_read_and_caught(self):
        """Лог шага роли в формате JSONL (`codex exec --json`), несущий имя
        каталога пула внутри команды шага, поднимает срабатывание: ищется
        подстрока, формат содержимого значения не имеет.

        Ловит мутацию: отбор файлов сужает заодно и содержимое (лог
        разбирается как строки лога Claude, а JSON-строка пропускается как
        «не текст лога») — утечка в шаге на Codex перестаёт быть видимой
        ровно у того провайдера, ради которого проверку и правят.
        """
        config.LOGS.mkdir(parents=True)
        (config.LOGS / self.CODEX_LOG).write_text(self.codex_jsonl(),
                                                  encoding="utf-8")

        check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(self.CODEX_LOG, check.detail)
        incidents = alerts.open_alerts(self.conn, "incident")
        self.assertEqual(len(incidents), 1, incidents)
        self.assertIn(config.CANARY_POOL_DIRNAME, incidents[0]["message"])

    def test_operator_session_log_is_not_read_at_all(self):
        """Запись сессии Оператора `*.session.log` с именем каталога пула
        внутри оставляет проверку зелёной — и не читается вовсе.

        Ловит мутацию: файлы сессий отсеиваются ПОСЛЕ чтения (прочитали,
        нашли совпадение, отбросили по имени) — содержимое сессии
        Оператора всё равно проходит через проверку, и следующая правка
        условия снова вернёт ложные срабатывания 21.09.
        """
        config.LOGS.mkdir(parents=True)
        (config.LOGS / self.SESSION_LOG).write_text(
            f"artel.py canary --k 1\nклон пула "
            f"~/{config.CANARY_POOL_DIRNAME}/pool\n", encoding="utf-8")

        seen, spy = self.read_names()
        with spy:
            check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual(check.status, "ok", check.detail)
        self.assertEqual(alerts.open_alerts(self.conn, "incident"), [])
        self.assertNotIn(self.SESSION_LOG, seen, seen)

    def test_role_log_beside_a_session_log_is_still_read(self):
        """Обычный текстовый лог шага роли рядом с записью сессии
        по-прежнему читается и ловится: сужение по имени не отменяет саму
        проверку.

        Ловит мутацию: отбор написан слишком узко (маска `*-developer-*`,
        «имя начинается с ULID») — логи ролей, не попавшие в маску,
        перестают проверяться вовсе, и проверка зеленеет молча.
        """
        config.LOGS.mkdir(parents=True)
        (config.LOGS / self.SESSION_LOG).write_text(
            f"~/{config.CANARY_POOL_DIRNAME}/pool\n", encoding="utf-8")
        role_log = "01M1NSR5M5THYRC0RFWPMVE2DW-test_author-2.log"
        (config.LOGS / role_log).write_text(
            f"Agent: гружу шаблон из ~/{config.CANARY_POOL_DIRNAME}/x.md\n",
            encoding="utf-8")

        seen, spy = self.read_names()
        with spy:
            check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(role_log, check.detail)
        self.assertNotIn(self.SESSION_LOG, check.detail)
        self.assertIn(role_log, seen)


class TokenRepoScopeCheckTest(unittest.TestCase):

    def test_gh_missing_is_a_skip_without_any_subprocess_call(self):
        with mock.patch.object(doctor.shutil, "which", return_value=None), \
             mock.patch.object(doctor.subprocess, "run") as run_mock:
            checks = doctor.check_token_repo_scope()
        run_mock.assert_not_called()
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "skip")

    def test_no_role_token_found_is_a_skip(self):
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token", return_value=None):
            checks = doctor.check_token_repo_scope()
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "skip")

    def test_token_visible_in_one_repo_is_ok(self):
        result = subprocess.CompletedProcess(
            [], 0, "artel-org/artel\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run", return_value=result):
            checks = doctor.check_token_repo_scope()
        statuses = {c.status for c in checks}
        self.assertEqual(statuses, {"ok"})

    def test_token_visible_in_more_than_one_repo_warns(self):
        result = subprocess.CompletedProcess(
            [], 0, "artel-org/artel\nartel-org/other-repo\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run", return_value=result):
            checks = doctor.check_token_repo_scope()
        statuses = {c.status for c in checks}
        self.assertIn("warn", statuses)

    def test_same_token_across_roles_is_queried_only_once(self):
        result = subprocess.CompletedProcess([], 0, "artel-org/artel\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run",
                               return_value=result) as run_mock:
            doctor.check_token_repo_scope()
        self.assertEqual(run_mock.call_count, 1)


class CanaryPoolDriftCheckTest(unittest.TestCase):
    """`doctor.check_canary_pool_drift` (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW,
    требование 3/AC-8) — предупреждение о незапечатанных правках через
    прямой вызов функции, без полного `doctor` CLI."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root_patcher = mock.patch.object(config, "ROOT", Path(tmp.name))
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.fake_home = Path(home_tmp.name)
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.fake_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)

        self.pool_dir = self.fake_home / config.CANARY_POOL_DIRNAME
        self.pool_dir.mkdir()
        (self.pool_dir / "a.md").write_text("тело А\n", encoding="utf-8")

        kc_patcher = mock.patch.object(
            doctor.pool_seal.keychain, "token",
            return_value="unit-test-drift-key")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)

    def test_no_sealed_file_is_ok(self):
        """Ловит мутацию: `check_canary_pool_drift` не проверяет
        существование `canary/pool.sealed` до сравнения и падает/
        предупреждает раньше времени, когда сравнивать ещё нечего."""
        self.assertEqual(doctor.check_canary_pool_drift().status, "ok")

    def test_matching_pool_is_ok(self):
        """Ловит мутацию: сравнение множеств файлов пула сломано
        (например, сверка по количеству файлов, а не по имени+
        содержимому) — совпадающий пул ложно дал бы `warn`."""
        doctor.pool_seal.cmd_pool_seal()
        self.assertEqual(doctor.check_canary_pool_drift().status, "ok")

    def test_diverging_pool_warns(self):
        """Ловит мутацию: расхождение открытого пула с запечатанным не
        замечено (сравнение всегда `ok` либо сравнивает не то поле) —
        `warn` не наступил бы даже при реальной незапечатанной правке."""
        doctor.pool_seal.cmd_pool_seal()
        (self.pool_dir / "a.md").write_text(
            "тело А, незапечатанная правка\n", encoding="utf-8")
        check = doctor.check_canary_pool_drift()
        self.assertEqual(check.status, "warn")
        self.assertIn("пул", check.detail.lower())

    def test_foreign_non_md_file_in_pool_dir_is_not_a_false_drift(self):
        """REVIEW.md итерации 1, R1-F2: `cmd_pool_seal` берёт в payload
        только `*.md`, значит сравнение обязано применять тот же
        фильтр — иначе любой посторонний файл в `~/.artel-canary`
        (например, `.DS_Store`, который macOS Finder кладёт в любой
        просмотренный каталог) даёт ложное "незапечатанные правки" даже
        когда набор `*.md`-шаблонов не менялся ни на байт.

        Ловит мутацию: `check_canary_pool_drift`/`pool_drift_warning`
        сравнивает ВСЕ файлы каталога без фильтра по `.md` — добавление
        `.DS_Store` после seal ложно покраснило бы этот тест в `warn`.
        """
        doctor.pool_seal.cmd_pool_seal()
        (self.pool_dir / ".DS_Store").write_bytes(b"\x00\x01macos-junk")

        check = doctor.check_canary_pool_drift()

        self.assertEqual(check.status, "ok")


if __name__ == "__main__":
    unittest.main()
