"""AC-11: `status` для задачи с активным lease показывает держателя
(идентификатор сессии) и его живость (жив/мёртв); существующие колонки
вывода `status` присутствуют и не переставлены.

Формат добавки — решение разработчика (SPEC, требование 6) — тест не
предполагает, ГДЕ именно в строке появится держатель, только что он там
есть для задач с lease и что существующий префикс строки (id, state,
"ревью X/Y", бюджет, title) остаётся на месте для ЛЮБОЙ задачи, с lease
или без.

Красен до реализации: тесты на держателя (`test_ac11_shows_dead_holder`/
`test_ac11_shows_alive_holder`) — сегодня `catalog.cmd_status` не читает
таблицу `leases` вовсе (`orchestrator/catalog.py::cmd_status`) —
держатель нигде не появляется.

Зелёный с рождения: тест `test_ac11_existing_columns_are_preserved_for_
every_line` — существующий префикс строки status (id, state, "ревью X/Y",
бюджет, title) уже сегодня соответствует `EXISTING_COLUMNS_RE` для всех
трёх задач вне зависимости от lease — тест фиксирует это как регрессионный
барьер: добавка держателя обязана остаться ДОБАВКОЙ, не заменой или
перестановкой существующих колонок.
"""
import os
import re
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TmpRootTest, capture, dead_pid  # noqa: E402

EXISTING_COLUMNS_RE = re.compile(
    r"^T\d{3}\s+in_dev\s+ревью 0/\d+\s+\$0\.00/\d+\.\d{2}\s+Задача")

DEAD_SESSION = "sess-dead-holder-ac11"
ALIVE_SESSION = "sess-alive-holder-ac11"


class StatusHolderDisplayTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for task_id, title in (("T001", "Задача без lease"),
                               ("T002", "Задача с мёртвым lease"),
                               ("T003", "Задача с живым lease")):
            store.insert_task(store.db(), task_id, title, "in_dev",
                              f"task/{task_id.lower()}-x",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T002", DEAD_SESSION, dead_pid(), socket.gethostname(),
             store.now()))
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T003", ALIVE_SESSION, os.getpid(), socket.gethostname(),
             store.now()))
        conn.commit()

    def _lines(self) -> dict:
        output = capture(catalog.cmd_status)
        return {ln.split()[0]: ln for ln in output.splitlines()
               if ln.startswith("T0")}

    def test_ac11_existing_columns_are_preserved_for_every_line(self):
        """Три задачи — без lease, с мёртвым и с живым держателем: во
        всех трёх строках `status` существующий префикс (id, state,
        "ревью X/Y", бюджет, title) остаётся на месте и в исходном
        порядке, независимо от того, добавлена ли информация о lease.

        Зелёный с рождения (см. докстринг модуля).

        Ловит мутацию: разработчик добавляет держателя ПЕРЕД
        существующими колонками (например, первым полем строки) или
        вставляет его между `state` и "ревью X/Y" вместо того, чтобы
        дописать его в конец строки — `EXISTING_COLUMNS_RE` жёстко
        фиксирует текущий порядок и перестанет совпадать.
        """
        lines = self._lines()
        for task_id in ("T001", "T002", "T003"):
            self.assertRegex(
                lines[task_id], EXISTING_COLUMNS_RE,
                f"строка {task_id} потеряла или переставила существующие "
                f"колонки status (id, state, ревью, бюджет, title): "
                f"{lines[task_id]!r}")

    def test_ac11_shows_dead_holder(self):
        """Задача T002 несёт lease с гарантированно мёртвым pid
        (`_sandbox.dead_pid`): строка `status` обязана назвать
        держателя (`session_id`) и явно сообщить, что он мёртв.

        Ловит мутацию: разработчик показывает identity держателя, но
        решение «жив/мёртв» берёт не из проверки pid, а из самого факта
        наличия строки `leases` (lease есть -> «жив» всегда) — эта
        задача с заведомо мёртвым pid тогда ошибочно покажется живой.
        """
        line = self._lines()["T002"]

        self.assertIn(DEAD_SESSION, line,
                     f"строка T002 не называет держателя lease: {line!r}")
        self.assertTrue(
            "мёртв" in line or "мертв" in line,
            f"строка T002 не сообщает, что держатель lease мёртв: {line!r}")

    def test_ac11_shows_alive_holder(self):
        """Задача T003 несёт lease с pid текущего тестового процесса
        (заведомо живой): строка `status` обязана назвать держателя и
        явно сообщить, что он жив.

        Ловит мутацию: разработчик хардкодит вывод «мёртв» для ЛЮБОГО
        держателя (например, копирует ветку T002 и забывает завести
        симметричную ветку для живого случая) — эта задача с заведомо
        живым pid тогда ошибочно покажется мёртвой.
        """
        line = self._lines()["T003"]

        self.assertIn(ALIVE_SESSION, line,
                     f"строка T003 не называет держателя lease: {line!r}")
        self.assertIn(
            "жив", line,
            f"строка T003 не сообщает, что держатель lease жив: {line!r}")


if __name__ == "__main__":
    unittest.main()
