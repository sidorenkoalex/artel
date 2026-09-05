"""Общие фикстуры приёмочных тестов 01M1RGQV4DG2FX1B90W4EEETTR.

Не test_*.py — unittest discover его не подхватит, это общий модуль,
импортируемый остальными файлами каталога.

Часть 1 (01M1RFVWV6WWTXRC5F40K61632, `_regenerate_and_commit_map`/
`doctor.check_map_growth`) на момент написания этих тестов ещё НЕ
смержена в main (только SPEC/TZ/acceptance_tests на её собственной
артефактной ветке) — это не блокер здесь: единственное, что от неё
нужно этой задаче, — ФОРМАТ данных (запись журнала `action="карта:
размер"`, `detail` = однострочный JSON с ключами `bytes_total`/
`sections_total`/`bytes_by_dir`/`top_sections`/(`bytes_projection`
опционально)/`sha`, что подтверждено буквальным текстом её SPEC.md и
`tasks/01M1RFVWV6WWTXRC5F40K61632/acceptance_tests/_fixtures.py`/
`test_fsm_map_size_journal.py` на её артефактной ветке), а не
поведенческий код `doctor.py`/`fsm_postmerge.py`. Эти тесты пишут
записи журнала НАПРЯМУЮ через уже существующий (в main СЕГОДНЯ)
`store.journal`, минуя `fsm_postmerge._regenerate_and_commit_map`
целиком (см. память test_author про бутстрап данных ещё не смерженной
зависимости).

`config.MAP_GROWTH_CALIBRATION_MERGES` (часть 1) тоже ещё не объявлена
в `orchestrator/config.py` — тесты подставляют её `mock.patch.object(
config, "MAP_GROWTH_CALIBRATION_MERGES", N, create=True)`, `create=True`
не мешает патчить атрибут, который уже существует после мержа части 1.

Новая константа-ориентир числа вызовов (эта задача, AC-3) SPEC не
называет по имени — конкретизация теста (тот же приём, что выбор схемы
`bytes_by_dir`/`top_sections` тестами части 1): `orchestrator/config.py::
MAP_GROWTH_CALLS_ESTIMATE`. Разработчик заводит константу с этим именем;
тесты читают её через `config.MAP_GROWTH_CALLS_ESTIMATE`, не литералом
(skills/test-authoring.md), но патчат сами (`create=True`) значением,
контролируемым тестом — тест не зависит от того, какое именно число
разработчик впишет по умолчанию.

Имена функций `orchestrator/report.py`, которые тесты зовут напрямую
(`map_size_entries`/`map_size_table_rows`/`map_growth_calibration_median`/
`map_growth_open_alerts`/`map_growth_cost_estimate`) SPEC тоже не
называет — та же конкретизация, что уже есть в этом модуле для
`token_rate_divergence` (tasks/01M1PP0VYRT55WN8GGVG66X89Y — имя
изобретено тестами той задачи, не SPEC).
"""
import json

from orchestrator import alerts, store

MAP_SIZE_ACTION = "карта: размер"
MAP_GROWTH_SOURCE = "map.growth"


def map_size_detail(bytes_total: int, *, sections_total: int = 3,
                    bytes_projection: int | None = None,
                    bytes_by_dir: dict | None = None,
                    sha: str = "a" * 40) -> str:
    """JSON `detail` записи «карта: размер» — та же схема полей, что уже
    зафиксирована тестами части 1 (`_fixtures.py::expected_stats`)."""
    detail = {
        "bytes_total": bytes_total,
        "sections_total": sections_total,
        "bytes_by_dir": bytes_by_dir or {"orchestrator": bytes_total,
                                        "scripts": 0, "tests": 0},
        "top_sections": [],
        "sha": sha,
    }
    if bytes_projection is not None:
        detail["bytes_projection"] = bytes_projection
    return json.dumps(detail, ensure_ascii=False)


def seed_map_size(conn, task_id: str, ts: str, **detail_kwargs) -> None:
    """Пишет одну запись «карта: размер» задачи `task_id` (её target уже
    должен быть заведён `store.insert_task`) и принудительно
    выставляет ей `ts` (иначе все записи одного быстрого прогона теста
    несли бы одинаковую до секунды метку — `now()`), чтобы хронология
    записей одного target была детерминирована, а не зависела от гонки
    системных часов между быстрыми вызовами `store.journal`."""
    store.journal(conn, task_id, "orchestrator", MAP_SIZE_ACTION,
                 map_size_detail(**detail_kwargs))
    conn.execute("UPDATE steps SET ts=? WHERE id=(SELECT MAX(id) FROM steps)",
                (ts,))
    conn.commit()


def seed_ackd_map_growth_alert(conn, target: str, ack_ts: str,
                              message: str = "решение теста") -> None:
    """Заводит и сразу подтверждает (`ack_ts`) алерт `map.growth` этого
    target — точка отсчёта окна калибровки (AC-7 части 1/этой задачи).
    `ack_ts` — принудительно выставленная метка (та же причина, что и
    `seed_map_size`: детерминированный порядок относительно записей
    ряда, без гонки системных часов)."""
    alerts.raise_alert(conn, target, "trigger", MAP_GROWTH_SOURCE,
                       f"{target}: {message}")
    row = conn.execute(
        "SELECT id FROM alerts WHERE target=? AND source=? "
        "ORDER BY id DESC LIMIT 1", (target, MAP_GROWTH_SOURCE)).fetchone()
    conn.execute(
        "UPDATE alerts SET ack_ts=?, ack_by=?, ack_resolution=? WHERE id=?",
        (ack_ts, "operator", message, row["id"]))
    conn.commit()


def tool_use_log_line(call_id: str, name: str = "Bash",
                      key: str = "echo") -> str:
    """Одна строка потока `--output-format stream-json` с ОДНИМ вызовом
    инструмента — тот же формат, что реальные логи шагов
    (`orchestrator/agent_log.py::_tool_use_calls`), не изобретённый."""
    event = {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": call_id, "name": name,
         "input": {"command": key}}]}}
    return json.dumps(event, ensure_ascii=False) + "\n"


def developer_log_text(n_calls: int) -> str:
    """Текст лога шага `developer` с ровно `n_calls` вызовами
    инструментов подряд."""
    return "".join(tool_use_log_line(f"call{i}") for i in range(n_calls))
