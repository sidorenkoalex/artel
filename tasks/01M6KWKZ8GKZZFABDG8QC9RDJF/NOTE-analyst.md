# Записка analyst

## Выяснено
- Итерация 2: возврат со spec_gate, 7 решений Оператора; все утверждения о коде сверены на 32ec975d: повтор `--as-epic` под lease fsm.py:1799-1801; skip_tests-путь fsm.py:1491-1499 зовёт `_maybe_ensure_draft_mr` (fsm.py:157 → github_adapter.py:118); answer на spec_gate отказывает зонам/merge_after (answer.py:239-256), берёт только мандат тестов (:261-268); `raw.strip()` answer.py:291; `_read_decision_file` fsm.py:1934-1940; `_as_epic_goal` fsm.py:1006-1027; маркеры mandate.py:32-56.
- Решения противоречий не несут — переношу в SPEC (AC-15 новый, AC-5/6/7/8 уточнены, имена констант/функции по решению 5).
- Строка ТЗ «Порядок: задача … смержена» без «после» — merge_after не ставлю.

## Не сработало
- Bash с `;`/`|` и `head` требует подтверждения — по одной команде.

## Где остановился
- SPEC.md переписан под решения 1-7: AC-15 новый (повтор под lease), AC-5 (только пробелы), AC-6 (4 маркера, подсказка по виду), AC-7 (байты, граница ±1), AC-8/AC-15 + «Безопасность тестов» (пустышка `_maybe_ensure_draft_mr`), имена `fsm.SPEC_GATE_NOTE_ACTION`, `brief.spec_gate_note`, `brief/review.SPEC_GATE_NOTE_PREAMBLE` с точными текстами; треб. 10 — `log` печатает, `watch` не показывает. status: ready, guard ок, budget 45.
- guard требовал классифицировать catalog.py/watch.py — вынесены в «Не входит» вместе с github_adapter.py.

## Чего не хватило
- —
