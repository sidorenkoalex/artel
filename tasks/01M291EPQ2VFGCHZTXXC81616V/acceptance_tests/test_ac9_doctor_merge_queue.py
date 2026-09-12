"""AC-9 — `doctor` показывает текущее содержимое очереди `merge_queue` и
отдельно предупреждает о мёртвых записях в ней — рядом с существующей
проверкой `merge_lock` (`orchestrator/doctor/leases.py::check_merge_lock`)
(SPEC 01M291EPQ2VFGCHZTXXC81616V).

Проверяем через `orchestrator.doctor.all_checks(conn)` — стабильную
публичную точку агрегации ВСЕХ проверок doctor (`orchestrator/doctor/
cli.py:13`), а не имя конкретной новой чек-функции (её разработчик
называет сам; `all_checks` не меняет форму вызова от этого выбора).
Песочница и мок subprocess — байт-в-байт приём `tests/test_doctor.py`
(`TmpRootTest`/`claude_only_run`/`claude_only_popen`): `all_checks` зовёт
дорогие проверки (`isolation_smoke`/`live_smoke`/версия CLI), которым
нужен рабочий `docs/codebase-map.md`/`CLAUDE.md`/keychain и перехват
вызовов `claude` — тот же набор, каким уже безопасно гоняют `all_checks`
десятки тестов `tests/test_doctor.py::DoctorCommandTest`.

Красен до реализации: таблицы `merge_queue` нет — прямой `INSERT INTO
merge_queue` упадёт `sqlite3.OperationalError: no such table:
merge_queue` (отсутствие кода задачи); если бы таблица уже была, но
проверки `doctor` не было бы — оба `assertTrue(any(...))` не нашли бы
совпадения ни по одному `Check`.
"""
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, store  # noqa: E402
from tests.sandbox import _dead_pid, _ts_ago, claude_only_popen  # noqa: E402
from tests.sandbox import claude_only_run  # noqa: E402
from tests.test_doctor import (FakeLiveSmokeProc, TmpRootTest,  # noqa: E402
                               result_event)


class DoctorMergeQueueTest(TmpRootTest):
    TASK_LIVE = "T001"
    TASK_DEAD = "T002"

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.insert_task(conn, self.TASK_LIVE, "Живая", "merge_gate",
                          "task/t001-live", config.DEFAULT_TARGET, 25.0)
        store.insert_task(conn, self.TASK_DEAD, "Мёртвая",
                          "merge_gate", "task/t002-dead",
                          config.DEFAULT_TARGET, 25.0)
        conn.execute(
            "INSERT INTO merge_queue (task_id, session_id, pid, hostname, "
            "enqueued_ts, heartbeat_ts) VALUES (?,?,?,?,?,?)",
            (self.TASK_LIVE, "sess-live", os.getpid(), socket.gethostname(),
             store.now(), store.now()))
        conn.execute(
            "INSERT INTO merge_queue (task_id, session_id, pid, hostname, "
            "enqueued_ts, heartbeat_ts) VALUES (?,?,?,?,?,?)",
            (self.TASK_DEAD, "sess-dead", _dead_pid(), socket.gethostname(),
             _ts_ago(1), _ts_ago(1)))
        conn.commit()

    def test_ac9_doctor_lists_queue_content_and_warns_about_the_dead_entry(self):
        """`doctor.all_checks` несёт хотя бы один `Check`, называющий живую
        запись очереди (видимость содержимого), и хотя бы один ОТДЕЛЬНЫЙ
        `Check` со статусом `fail`, называющий именно мёртвую запись
        (предупреждение о мёртвых записях) — не один и тот же `Check` на
        оба случая, иначе Оператор не отличит живую очередь от
        предупреждения.

        Ловит мутацию: проверка мёртвых записей очереди не заведена вовсе
        — второй `assertTrue` (наличие fail-чека по `TASK_DEAD`) не
        найдёт совпадений; проверка есть, но помечает fail'ом весь список
        независимо от живости pid — `assertFalse` по живой записи упадёт.
        """
        with mock.patch.object(
                doctor.subprocess, "run",
                side_effect=claude_only_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")), \
             mock.patch.object(
                doctor.subprocess, "Popen",
                side_effect=claude_only_popen(
                    FakeLiveSmokeProc(result_event(0.01)))):
            checks = doctor.all_checks(store.db())

        content_checks = [c for c in checks if self.TASK_LIVE in c.detail]
        self.assertTrue(
            content_checks,
            "doctor обязан показывать текущее содержимое очереди "
            "merge_queue — ни один Check не назвал живую запись")

        dead_fail_checks = [c for c in checks
                            if c.status == "fail" and self.TASK_DEAD in c.detail]
        self.assertTrue(
            dead_fail_checks,
            "doctor обязан отдельно предупреждать о мёртвых записях "
            "очереди — ни один fail-Check не назвал мёртвую запись")
        self.assertFalse(
            any(c.status == "fail" and self.TASK_LIVE in c.detail
               for c in checks),
            "живая запись не должна попадать в предупреждение о мёртвых "
            "записях")


if __name__ == "__main__":
    unittest.main()
