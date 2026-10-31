# Записка developer — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- Б2.1а уже в ветке: `targets.delivery_policy`, `store.set_mr_link`/`mr_link`, `fsm.AWAITING_HUMAN`, отказ отправки в awaiting_human в gitcmd.
- Код: ветвь `_approve_for_project_people` (fsm_merge_gate.py) из `_cmd_approve_merge_gate`; `github_adapter.open_forge_mr`/`ensure_forge_draft_mr`/`mr_assignee`/`mr_description`; `gitcmd._in_flight_refusal` в `_push_plan`; `tests_writing._forge_draft_mr_gate` после `_publish_head_gate` в `_origin_push_gate`; `catalog._delivery_suffix`.
- Подтверждённая голова кода внешнего проекта — `код=` последней записи «sha зафиксирован» с sha=fixed_sha.
- Долгоживущий файл 36/36, планка ac3 зелёная, свои юниты tests/test_mr_delivery_units.py 10/10 (мутации красные), test_invariants.py с приложением 87/87, приложение проходит `git apply --check`. Карта регенерирована.

## Не сработало
- `pytest -n 8` в шаге: сторож роли отказывает каждому воркеру — гонять без `-n`.
- Первый вариант выключения `gh` для target-human добавлял второй вызов `targets.target` и ронял test_github_adapter (side_effect-список) — проверка перенесена на уже прочитанную запись.

## Где остановился
- PLAN.md status: escalate — один вопрос: ANSWER-2 п.2 (отказ max_in_flight в начале amend-tests) требует правки orchestrator/amend.py вне зон. Дефолт (б): оставить отказ в точке gitcmd (как сейчас). При ответе (а) + zones-extend: добавить `gitcmd.in_flight_refusal(task_id)` и вызов первым действием `amend._cmd_amend_tests`, юнит-тест; снять escalate.

## Чего не хватило
- Как найти подтверждённую голову кода внешнего проекта (sha approve — ссылка документов): нашлось в store.record_fixation (`код=`).
