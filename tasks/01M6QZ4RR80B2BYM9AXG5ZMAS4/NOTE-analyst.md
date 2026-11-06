# Записка analyst

## Выяснено
- ТЗ достаточно; SPEC.md написан, status: ready, guard ок. 9 AC (8 из критериев ТЗ + AC-9 про справку, требование 8 ТЗ).
- Ссылки ТЗ на код сверены с worktree: `orchestrator/projects.py` (`TARGET_SET_USAGE` :370, `KEY_FIELDS` :380, `NO_COMPONENT` :382, `cmd_target_set` :395, `_comment_line` :610, `_field_keys` :633, `_target_set_mismatches` :761, `_merge_mismatches` :813, `_backup_copy` :839), `orchestrator/targets.py` (`COMPOSE_REQUIRED` :110, `COMPOSE_FORBIDDEN` :115, `merge_local` :486, `_check_compose` :1239), справка в `orchestrator/artel.py` :197-200.
- budget_usd: 30 — рамка Оператора из ТЗ (таблица дала бы ~40).

## Не сработало
- Первый прогон guard: сигнал «число модулей ≥ 5» считается по ВСЕМ путям `orchestrator/*.py`/`scripts/*.py`, упомянутым в тексте SPEC (`guard._zone_paths`), включая файлы только чтения; плюс неклассифицированные пути. Закрыл секцией «Оценка объёма» (монолит, прогноз диффа 20 КиБ) и строкой «Не входит» с путями только чтения.

## Где остановился
- Шаг закончен; монолит ждёт утверждения Оператора на гейте SPEC.

## Чего не хватило
- Что сигнал объёма считает упомянутые, а не правимые модули, — нашёл только в `scripts/guard.py::_zone_paths`.
