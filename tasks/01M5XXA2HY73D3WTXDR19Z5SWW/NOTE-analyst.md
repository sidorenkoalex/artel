# Записка analyst — 01M5XXA2HY73D3WTXDR19Z5SWW

## Выяснено
- Возврат с гейта SPEC №2 (8 пунктов) внесён точечно: AC 29 → 32 (новые AC-30 перечни APPROVE_NEEDS_SHA/SET_MODELS_STATES/STATE_ROLE без awaiting_human; AC-31 max_in_flight на amend-tests; AC-32 на входе в in_dev через черновой MR GitHub).
- mr_assignee: загрузка как в Б1.1 (record_fields.py:169 держит "alice"); нечисловое — MR без исполнителя + журнал «исполнитель не числовой id — не назначен».
- 409: forge.MergeRequest (forge.py:67-74) без кода; текст адаптера gitlab_adapter.py:209 «GitLab ответил кодом {status} на …» — разбор в fsm_merge_gate.py (AC-11, плюс отрицательный случай 403).
- Шаги гейта: :1513 публикация, :1541 канарейка, :1581-1601 мьютекс — исполняются; :1545 коммит закрытия — нет (AC-3/AC-4).
- max_in_flight перенесён в gitcmd._push_plan (`gitcmd.py:730`) перед первой отправкой; gitcmd.py добавлен в зоны части 2.
- Ссылка на MR — пара (iid, web_url), undraft/assign по iid.

## Не сработало
- —

## Где остановился
- SPEC.md обновлён, status: ready, guard ок. Бюджет 70, деление 2×$45 без изменений.

## Чего не хватило
- —
