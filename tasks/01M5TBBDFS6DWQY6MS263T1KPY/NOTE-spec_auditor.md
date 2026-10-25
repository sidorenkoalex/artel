# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 3, spec_sha a084efdc…)

## Выяснено
- Находки визита 2 закрыты решениями гейта 26.10 №1–2 и ANSWER-1.
- Остаток (вердикт concerns):
  - add_column: проверка+ALTER не атомарны (schema.py:173-180, test_store_schema_migration_parity.py:4-8) → «одна запись при параллельном догоне» не следует из признака колонки; AC-34 без перемежения.
  - AC-29: эталон «на шаге developer» против фиксации планки (tests_locked_sha, ADR-0012 amend-tests).
  - lease.py:226 `_own_session_live_holder_refusal` зовёт get_task → для id эпика «Задача не найдена».
  - --as-epic: мягкие отказы _approve_spec_gate (fsm.py:1201-1287) — порядок заведения эпика не задан; _read_branch_text_or_refuse пишет журнал.
  - AC-30 без epic show; pin — источник не назван (watch.py:354).

## Не сработало
- `cd …; grep` и составные команды требуют подтверждения — только абсолютные пути, одна команда.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Карточки «добавление колонки в migrate гоняется между процессами» — нашёл по тесту parity.
