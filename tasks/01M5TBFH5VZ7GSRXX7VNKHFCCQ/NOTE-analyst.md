# Записка аналитика 01M5TBFH5VZ7GSRXX7VNKHFCCQ (Э4), шаг 2 — возврат со spec_gate 26.10

## Выяснено
- Причина возврата — решения Оператора (1)–(9); все переносятся в SPEC без вопросов.
- Факты по origin/main (ветка задачи Э1 не содержит): `report.py:48` STATE_ORDER = fsm.STATES, `_tile_html` `:565`, `_board_html` `:596`, `cmd_report` `:1428` (всё на `store.all_tasks`, доска одна на все проекты). `board.py:39` `_card` — нет `review_iters`, `escalated_from`, проекта; `build_model(conn, project)` `:123`.
- Внутренности доски в tests/ зовёт только `tests/test_report.py:213,220,230` (_tile_html), `:246,255,261` (_board_html); `spec_audit_units.py:357` — `report.STATE_ORDER`. Прочие ~10 файлов report-тестов идут через cmd_report/_render-вывод.
- Части деления: `catalog.spawn_subtask` `:786`, зов `fsm.py:1070`.
- `targets.py:289-294` LOCAL_SECTIONS/LOCAL_FIELDS — сюда `ref_required`, `ref_systems`.

## Где остановился
- SPEC переписан (status: ready, 13 AC, матрица неослабления по 6 методам test_report.py + строки «без правки», budget 60, монолит/деление — на выбор Оператора), guard: ок.
- Пп. возврата → SPEC: (1)(4) треб. 2/AC-5,6; (2) AC-7; (3) треб. 3/AC-8; (5) AC-5; (6) матрица; (7) треб. 9/AC-13; (8) треб. 5/AC-12; (9) Контекст/Материалы, треб. 6-7/AC-9,10.

## Чего не хватило
- Ветка задачи отстаёт от origin/main (нет Э1) — сверка только `git show origin/main:`.
