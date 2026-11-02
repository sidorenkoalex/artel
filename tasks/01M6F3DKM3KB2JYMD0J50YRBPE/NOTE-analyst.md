# NOTE analyst

## Выяснено
- Факты ТЗ сверены по коду: `fsm_advance.verifying` — `orchestrator/fsm_advance.py:442` (гейт по исходам `verifying_gate` уже на `verifying`, строка 474); `board.waiting_on` — `orchestrator/board.py:27`, `CI_STATES = ("verifying",)` строка 20.
- Предел возвратов ревью — `config.LIMIT_REVIEW_ITERS = 3` (`config.py:330`), механизм — `fsm_advance._review_changes_requested` (`fsm_advance.py:350`): возврат, доводящий счётчик до предела, эскалирует вместо возврата.
- Возврат `verifying -> in_dev` уже считается возвратом в брифе (`brief._RETURN_TRIGGER_STATES`, `brief.py:86`) — причина попадает в раздел «Причина возврата».
- `tests/test_invariants.py` — защищённый путь (`config.py:788`); обход команд — `FsmTest.commands()` (`tests/test_invariants.py:400`).
- Сигналы объёма: 10 зон, бюджет ≥ $30, критериев ≥ 10 → в SPEC обоснование монолита (выбор за Оператором).

## Не сработало
- `cd … ; grep` и составные команды Bash требуют подтверждения — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC написан (13 AC, status: ready, merge_after 01M6BMG29KZV1RX21HFAXZG3CM, budget 40 = рамка ТЗ), `scripts/guard.py` — ок.
- Толкование: счётчик `verify-fail` — свой, с пределом `LIMIT_REVIEW_ITERS` (ТЗ: «тем же механизмом и значением»); если Оператор имел в виду общий `review_iters` — правка на гейте SPEC.

## Чего не хватило
- Константы «общего правила долгого ожидания Оператора» в `config.py` не нашёл — в SPEC новое алерт-правило вынесено в «Не входит».
