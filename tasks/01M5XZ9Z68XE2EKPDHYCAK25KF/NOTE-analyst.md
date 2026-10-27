# Записка аналитика — 01M5XZ9Z68XE2EKPDHYCAK25KF

## Выяснено
- ТЗ = подраздел «Деление» SPEC родителя 01M5XXA2HY73D3WTXDR19Z5SWW (refs/artifacts/01M5XXA2HY73D3WTXDR19Z5SWW); требования/AC взяты из требований 4–7, 10 и AC родителя.
- «Порядок: после части 1» = 01M5XZ9Z68V75VXF5Z66C708T4 (в БД уже заявлено) → merge_after.
- Сдвиг строк на main a6af742bf: код 409 в `gitlab_adapter.py:211` (не 209); мьютекс захватывается в `fsm_merge_gate.py:1650` внутри `_cmd_approve_merge_gate_cycle` (:1581); `_refuse_during_canary` стоит на :1541 ПОСЛЕ слияния в scratch — для target-human его надо вызывать до open_mr.
- `awaiting_human` в orchestrator/ на main ещё нет — придёт с частью 1.
- SPEC написан, status: ready, guard ок; 19 AC, budget 45 (рамка ТЗ), монолит-обоснование + вариант разреза для Оператора.

## Не сработало
- `cd … ; sed` в Bash требует подтверждения — использовать абсолютные пути.

## Где остановился
- Готово.

## Чего не хватило
- Номера строк ТЗ уже частично устарели; сверял grep по символам.
