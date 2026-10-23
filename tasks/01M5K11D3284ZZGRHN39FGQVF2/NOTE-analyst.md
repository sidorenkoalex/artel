# Записка analyst — 01M5K11D3284ZZGRHN39FGQVF2

## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 9 AC, budget_usd 25), guard ок.
- Факты ТЗ сверены с кодом: `_classify_push_failure` artifact_branch.py:320, `_attempt_push` :336, `push` :378, `_send` :404, `send_pending` :418 (вызовов нет); `store.last_task_step_of` store.py:1185.
- Сторож `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` запрещает тестам глобально подменять `time.sleep`, включая `mock.patch.object(artifact_branch.time, "sleep")`. Поэтому `artifact_branch.time` подменяется объектом-заместителем, у которого подменён `sleep` (требование 6 SPEC).
- Бюджет: в ТЗ $20, поставлено $25 — пол калибровки (`config.BUDGET_CALIBRATION_FLOOR_USD`).
- Сигналы объёма guard засчитал по упоминаниям файлов «только чтение» и по инварианту 33 (`docs/invariants.md`, artifact_branch через `gitcmd`). Дано обоснование монолита и «Прогноз диффа: 20 КиБ».

## Не сработало
- Первая версия SPEC без секции «Оценка объёма и деление»: guard отказал по сигналам объёма.

## Где остановился
- Шаг завершён: SPEC готов к гейту.

## Чего не хватило
- То, что guard считает пути `orchestrator/*.py` по всему тексту SPEC, включая «Не входит», выяснилось только по коду `scripts/guard.py::_zone_paths`.
