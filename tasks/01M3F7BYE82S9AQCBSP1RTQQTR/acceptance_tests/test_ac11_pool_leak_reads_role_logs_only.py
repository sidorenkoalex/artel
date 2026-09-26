"""AC-11 — 01M3F7BYE82S9AQCBSP1RTQQTR: проверка утечки пула читает логи
шагов ролей любого формата и не читает записи сессий Оператора.

Источник — SPEC.md, «Критерии приёмки»:

AC-11. `check_role_log_pool_leak` читает файлы вида
`<task_id>-<role>-<n>.log` независимо от формата их содержимого (в том
числе JSONL шагов Codex) и не читает файлы `*.session.log`.

«Не читает» проверяется буквально — слежкой за `Path.read_text`: строка
`doctor`, которая молча прочитала запись сессии Оператора и не нашла в
ней совпадения, критерию не отвечает (сегодняшние ложные срабатывания
21.09 — ровно из такого чтения, docs/backlog.md, запись 3).

Логи синтетические, каталог логов — во временном корне песочницы
`tests/sandbox.py`; настоящий `.artel/logs` пульта прогон планки не
трогает.

Красен до реализации: проверка сегодня читает ВСЕ файлы `*.log` каталога
логов — запись сессии Оператора с именем каталога пула внутри красит её,
и `assertEqual("ok", …)` падает на `fail`.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import alerts, config, doctor  # noqa: E402
from tests.sandbox import SchemaConnTmpRootTest  # noqa: E402

#: Имена из живого разбора 21.09 (docs/backlog.md, запись 3): лог шага
#: роли и запись сессии Оператора.
ROLE_LOG = "01M1NSR5M5THYRC0RFWPMVE2DW-test_author-2.log"
CODEX_ROLE_LOG = "01M32NH6P053978AER66P0X4GN-developer-1.log"
SESSION_LOG = "canary-20260911T230820Z.session.log"


class PoolLeakReadsRoleLogsOnlyTest(SchemaConnTmpRootTest):

    def setUp(self):
        super().setUp()
        config.LOGS.mkdir(parents=True, exist_ok=True)
        self.marker = config.CANARY_POOL_DIRNAME

    def write_log(self, name: str, text: str) -> None:
        (config.LOGS / name).write_text(text, encoding="utf-8")

    def codex_jsonl(self) -> str:
        """Строки лога шага роли на Codex: `codex exec --json`, то есть
        JSONL, а не текст строками, — формат содержимого, которого
        сегодняшняя проверка не видела."""
        return "\n".join(json.dumps(event, ensure_ascii=False) for event in (
            {"type": "thread.started", "thread_id": "th-1"},
            {"type": "item.completed",
             "item": {"type": "command_execution",
                      "command": f"ls ~/{self.marker}/templates",
                      "aggregated_output": "ok"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10}},
        )) + "\n"

    def read_paths(self):
        """Контекст слежки: (список прочитанных путей, менеджер)."""
        seen = []
        real_read_text = Path.read_text

        def spy(self_path, *args, **kwargs):
            seen.append(self_path.name)
            return real_read_text(self_path, *args, **kwargs)

        return seen, mock.patch.object(Path, "read_text", spy)

    def test_ac11_a_codex_step_log_with_the_pool_name_is_caught(self):
        """Лог шага роли в формате JSONL (`codex exec --json`), несущий
        имя каталога пула внутри команды шага, поднимает срабатывание
        проверки — формат содержимого значения не имеет, ищется
        подстрока.

        Ловит мутацию: отбор файлов по имени написан так, что заодно
        сужает и содержимое (лог разбирается как строки лога Claude, а
        JSON-строка пропускается как «не текст лога») — утечка в шаге на
        Codex перестаёт быть видимой ровно у того провайдера, ради
        которого проверку и правят.
        """
        self.write_log(CODEX_ROLE_LOG, self.codex_jsonl())

        check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual("fail", check.status, check.detail)
        self.assertIn(CODEX_ROLE_LOG, check.detail)
        incidents = alerts.open_alerts(self.conn, "incident")
        self.assertEqual(1, len(incidents), incidents)
        self.assertIn(self.marker, incidents[0]["message"])

    def test_ac11_an_operator_session_log_is_not_read_at_all(self):
        """Запись сессии Оператора `*.session.log` с именем каталога пула
        внутри оставляет проверку зелёной — и не читается вовсе: её имени
        нет среди файлов, к которым проверка обратилась.

        Ловит мутацию: файлы сессий отсеиваются ПОСЛЕ чтения (прочитали,
        нашли совпадение, отбросили по имени) — предмет требования 7
        («не читает») не выполнен: содержимое сессии Оператора всё равно
        проходит через проверку, и следующая правка условия снова
        вернёт ложные срабатывания 21.09.
        """
        self.write_log(SESSION_LOG, f"artel.py canary --k 1\n"
                                    f"клон пула ~/{self.marker}/pool\n")

        seen, spy = self.read_paths()
        with spy:
            check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual("ok", check.status, check.detail)
        self.assertEqual([], alerts.open_alerts(self.conn, "incident"))
        self.assertNotIn(
            SESSION_LOG, seen,
            f"запись сессии Оператора прочитана проверкой (прочитанные "
            f"файлы: {seen}) — AC-11 требует её не читать")

    def test_ac11_a_plain_role_log_is_still_read_beside_a_session_log(self):
        """Обычный текстовый лог шага роли рядом с записью сессии
        по-прежнему читается и по-прежнему ловится: сужение по имени не
        отменяет саму проверку.

        Ловит мутацию: отбор написан слишком узко (например, по маске
        `*-developer-*.log` или по «имя начинается с ULID сегодняшних
        задач») — логи ролей, не попавшие в маску, перестают
        проверяться вовсе, и проверка зеленеет молча.
        """
        self.write_log(SESSION_LOG, f"~/{self.marker}/pool\n")
        self.write_log(ROLE_LOG, f"Agent: гружу шаблон из ~/{self.marker}/x.md\n")

        seen, spy = self.read_paths()
        with spy:
            check = doctor.check_role_log_pool_leak(self.conn)

        self.assertEqual("fail", check.status, check.detail)
        self.assertIn(ROLE_LOG, check.detail)
        self.assertNotIn(SESSION_LOG, check.detail)
        self.assertIn(ROLE_LOG, seen)


if __name__ == "__main__":
    unittest.main()
