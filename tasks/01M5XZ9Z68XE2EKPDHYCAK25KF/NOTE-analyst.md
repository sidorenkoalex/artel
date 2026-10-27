# Записка аналитика — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- ТЗ = подраздел «Деление» SPEC родителя 01M5XXA2HY73D3WTXDR19Z5SWW; merge_after = часть 1 01M5XZ9Z68V75VXF5Z66C708T4.
- Шаг 2 (возврат с spec_gate): применены все 9 решений Оператора. Новые требование 2 (сдвиг base → in_dev, без подтяжки на гейте), AC-20 (max_awaiting под мьютексом, два параллельных approve), AC-21 (отказ open_mr(draft) → in_dev), AC-22 (PUSH_SENT_LEGACY_ACTION — не первая отправка). Нумерация требований сдвинута на +1 начиная с 2.
- Переход merge_gate -> in_dev уже есть (fsm_merge_gate.py:283, :1006; fsm.py:1858) — нового состояния FSM нет.
- В forge нет метода правки описания MR (undraft_mr меняет только title, gitlab_adapter.py:527-535), forge.py/gitlab_adapter.py read-only — отмечено в «Материалах» как факт для PLAN.
- Отказ ensure_draft_mr сегодня — инцидент (github_adapter.py:67, :168, :181).

## Не сработало
- `cd … ; sed` в Bash требует подтверждения — абсолютные пути.

## Где остановился
- SPEC переписан, status: ready; guard прогнан.

## Чего не хватило
- Способа обновить описание MR в пределах зон (forge его не даёт).
