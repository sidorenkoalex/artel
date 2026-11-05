## Выяснено
- Реализация — orchestrator/projects.py: `_target_set_key` (ветки `--key`/`--drop-key`), общие помощники `_target_set_load` (отказы артели/записи/чтения/комментария), `_target_set_write` (сверка → копия → запись → журнал), `_rendered`, `_was_text`; `_drop_key_mismatches`; общие куски сверок `_changed_leaves`, `_merge_mismatches` (поведение `_target_set_mismatches` прежнее).
- Константы `KEY_FLAG`, `DROP_KEY_FLAG`, `KEY_FIELDS`; `TARGET_SET_USAGE` и справка artel.py называют обе формы.
- Прогон: долгоживущие + прежние тесты target-set/submodule_tokens/help_registry — 145 passed; plank-run — 10 passed. Карта регенерирована.

## Не сработало
- `sed -i` в Bash отклонён хуком (simple_expansion) — правил PLAN через Edit.

## Где остановился
- Шаг завершён, PLAN.md status: ready.

## Чего не хватило
- Ничего существенного.
