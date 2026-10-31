# Записка developer — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- Б2.1а уже в ветке: `targets.delivery_policy`, `store.set_mr_link`/`mr_link`, `fsm.AWAITING_HUMAN`, отказ отправки в awaiting_human в gitcmd.
- Код: ветвь `_approve_for_project_people` (fsm_merge_gate.py) из `_cmd_approve_merge_gate`; `github_adapter.open_forge_mr`/`ensure_forge_draft_mr`/`mr_assignee`/`mr_description`; `gitcmd._in_flight_refusal` в `_push_plan`; `tests_writing._forge_draft_mr_gate` после `_publish_head_gate` в `_origin_push_gate`; `catalog._delivery_suffix`.
- ANSWER-3 (зона amend.py): `gitcmd.in_flight_refusal(task_id)` + `amend._refuse_in_flight` первым действием `_cmd_amend_tests` и `_cmd_amend_tests_from_branch` (после отказа awaiting_human; канарейка пропускается). Юнит `AmendInFlightBeforeCommitTest` в tests/test_mr_delivery_units.py — мутация (снять вызов) красная.
- Прогоны после правки: units 11/11, долгоживущий файл, все amend-тесты, gitcmd_push_point, invariants, multitarget — 283 passed; plank-run 2 passed. Карта регенерирована.

## Не сработало
- `pytest -n 8` в шаге: сторож роли отказывает каждому воркеру — гонять без `-n`.
- Edit по строке `_refuse_awaiting_human(...)\n _refuse_in_flight(...)` неуникален (два пути amend) — брать с заголовком функции.

## Где остановился
- 01.11: advance отклонил гейт зон «мандат есть, раздела PLAN нет» — в PLAN.md добавлен раздел «## Расширение зон» со строкой «Пути: orchestrator/amend.py» (формат — zones.py:59, `_plan_zones_extension_paths`). Код не менялся, guard ок.
- PLAN.md status: ready, раздел «Эскалация» снят. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Как найти подтверждённую голову кода внешнего проекта (sha approve — ссылка документов): нашлось в store.record_fixation (`код=`).
