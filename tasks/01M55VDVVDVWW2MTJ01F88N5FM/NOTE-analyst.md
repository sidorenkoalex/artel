# NOTE analyst 01M55VDVVDVWW2MTJ01F88N5FM

## Выяснено
- `mandate.refusals` из продакшена зовёт только `answer.py:113` (с conn/task_id); прочие вызовы — тесты (conn=None).
- `test_integrity._in_scope` (:227-244) — только запасная область `_compare` при `scope=None`; все продакшен-вызовы (`test_integrity.py:1518`, `fsm_merge_gate.py:146`, `review.py:644`) передают `decision.profile.in_weakening_scope`. Вне пути внешнего проекта, правка не нужна.
- `mandate._covered` (`mandate.py:346-350`) через `_TEST_REF_RE` (:264, lookbehind `(?<![\w/])`) не видит `backend/tests/x.py` — у внешнего проекта строка матрицы с таким покрытием требует «ок при условии». В зоне (mandate.py) → требование 4 SPEC.
- У артели профиль `weakening_scope: [tests/**/*.py]` (targets.yaml:49): `mask_matches` даёт то же решение, что текущая формула, на путях, прошедших `_looks_like_path`.
- Текст «вне области tests/**/*.py» держит `tests/test_answer_mandate.py:211`.

## Не сработало
- —

## Где остановился
- Шаг 2 (возврат spec_gate 18.10): внесены три решения Оператора — AC-5 в обоих каналах (answer, zones-extend --matrix); у проекта с профилем ссылкой на тест в матрице считается только путь из weakening_scope (tests/… у внешнего не засчитывается); оговорка в требовании 3 + AC-6: у артели в деградированном состоянии профиля мандат при записи отказывается. 6 AC, budget 25, guard: ок.
- SPEC написан (5 AC, status: ready, budget 25), guard: ок.
- Выбор по требованию 1 ТЗ: без conn/task_id — область артели; Decision.refusal/skip — именованный отказ (гейт на них мандат не засчитывает).
- Риск для разработчика: тесты artel-задач через `answer` в песочнице должны разрешать профиль артели (иначе новый именованный отказ сломает прежние исходы) — сверить на старте.

## Чего не хватило
- Нет сводки «кто зовёт `_compare` без scope» — найдено grep'ом по `scope=` в orchestrator/.
