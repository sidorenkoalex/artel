"""Приёмочный тест AC-6 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md):
`python3 orchestrator/artel.py status` на копии БД пульта в песочнице
даёт тот же вывод до и после рефакторинга `store.py`/`schema.py`.

Прямой смоук по буквальному тексту AC («копия живой БД пульта») не
переносим в детерминированный юнит-тест: настоящая `.artel/state.db`
несёт реальные текущие задачи, их состав и тексты меняются на каждом
шаге пульта, так что «тот же вывод» с НЕЙ можно сравнить только вручную
в моменте самого рефакторинга, не заранее зафиксировать здесь. Вместо
буквальной копии — детерминированная ФИКСТУРА БД (три задачи в разных
состояниях + один триггер-алерт), которая исполняет ровно тот же код
`catalog.cmd_status`/`store.all_tasks`/`alerts.open_alerts`, что и
реальная БД — байт-в-байт золотой снимок вывода на этой фикстуре и есть
предмет проверки «тот же вывод до и после».

`store.now` заморожен на фиксированную дату — `created_at`/`updated_at`
самих задач в вывод `status` не попадают, но фиксация всё равно снимает
любую теоретическую зависимость от момента прогона. `config.
LIMIT_REVIEW_ITERS` — крутилка Оператора (`orchestrator/config.py`),
подставляется в ожидаемый текст ДИНАМИЧЕСКИ, не литералом «3»: тест не
обязан ломаться, если Оператор передвинет потолок ревью (урок T062).

Зелёный с рождения: снимок снят с сегодняшнего (дорефакторингового)
`catalog.cmd_status` — тест обязан пройти уже сейчас и остаться зелёным
после переноса схемы/миграций в `schema.py` (AC-1) и группировки
запросов (AC-3), поскольку ни то ни другое не должно менять поведение
(SPEC, требование 6).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class StatusOutputByteParityTest(TmpRootTest):

    def test_ac6_status_output_matches_golden_snapshot(self):
        """`catalog.cmd_status()` на фикстуре из трёх задач (обычная,
        канареечная, эскалированная) и одного триггер-алерта печатает
        ровно тот же текст, что печатал сегодняшний (дорефакторинговый)
        код на той же фикстуре.

        Ловит мутацию: перенос схемы/миграций в `schema.py` (AC-1) или
        группировка запросов заголовками (AC-3), которые по пути
        сломали любую из функций, участвующих в сборке строки статуса
        (`store.all_tasks`, `alerts.open_alerts`, форматирование
        `f"{r['id']}  {r['state']:<13} ..."`) — например, забытый
        импорт после переноса, случайно переставленные поля строки или
        потерянная ветка `[canary]`/`ЖДЁТ ОПЕРАТОРА` — дают другой
        текст, и сравнение с золотым снимком краснеет.
        """
        with mock.patch.object(store, "now", lambda: "2020-01-01 00:00:00Z"):
            conn = store.db()
            store.create_schema(conn)

            store.insert_task(
                conn, "T001", "Обычная задача", "review", "task/t001",
                config.DEFAULT_TARGET, 10.0, is_canary=False)
            store.update_task(conn, "T001", spent_usd=2.5, review_iters=1)

            store.insert_task(
                conn, "T002", "Канареечная задача", "verifying", "task/t002",
                config.DEFAULT_TARGET, 5.0, is_canary=True)
            store.update_task(conn, "T002", spent_usd=0.0)

            store.insert_task(
                conn, "T003", "Эскалированная задача", "escalated",
                "task/t003", config.DEFAULT_TARGET, 8.0, is_canary=False)
            store.update_task(conn, "T003", spent_usd=1.25)

            store.insert_alert(
                conn, None, "trigger", "docs/triggers.md", "тестовый триггер")

            output = capture(catalog.cmd_status)

        lim = config.LIMIT_REVIEW_ITERS
        expected = (
            f"T001  review        ревью 1/{lim}  $2.50/10.00  Обычная задача\n"
            f"T002  verifying     ревью 0/{lim}  $0.00/5.00  Канареечная "
            "задача  [canary]\n"
            f"T003  escalated     ревью 0/{lim}  $1.25/8.00  Эскалированная "
            "задача <- ЖДЁТ ОПЕРАТОРА\n"
            "\n"
            "Триггеры (docs/triggers.md) — ack обязан нести решение:\n"
            "  #1 [-] docs/triggers.md: тестовый триггер\n"
        )
        self.assertEqual(output, expected)


if __name__ == "__main__":
    unittest.main()
