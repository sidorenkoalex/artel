# ТЗ: две малые правки — пустой реестр REVIEW.md и проверка шаблонов пула канарейки

Порядок: после группы 3.

Источник: копилка, приоритет 1 (06.09 — реестр REVIEW.md ломает guard;
13.09 — канарейка красная из-за защищённого пути в шаблоне пула).
Решение Оператора 05.10: сделать после группы 3.

Факты (пин f7a46d84, сверка кода 05.10):
- Экранирование `\|` в реестре исправлено (fac32a19, `scripts/guard.py::
  registry_table_rows` ~2638); перезапуск роли при отказе guard — 01M446WEVJ
  (`orchestrator/auto.py` ~798-843). Осталось: роль пишет строку-заглушку
  («— | — | …», «(пусто)») при approved без замечаний; `templates/REVIEW.md`
  (~25-36) и `skills/review-checklist.md` («Реестр замечаний», ~114-146)
  не говорят, что пустой реестр — только шапка.
- `new` отказывает на защищённый путь в «Зоны:» (`catalog.py::
  _tz_path_refusal` ~216, a5c079a1); печать пула (`pool_seal.py::
  cmd_pool_seal` ~316) и `doctor/canary_pool.py::check_canary_pool_drift`
  (~97) шаблоны этой проверкой не прогоняют.

Требуется:
1. `scripts/guard.py::registry_record_errors` (~2682): строка реестра из
   одних прочерков или «(пусто)» — понятный отказ «пустой реестр — только
   шапка таблицы» вместо ошибки формата id.
2. Строка в `templates/REVIEW.md` и `skills/review-checklist.md`: нет
   замечаний — только шапка; черта в ячейке — `\|`. templates/ и skills/ —
   защищённые пути: правка приложением PLAN (применяет Оператор на гейте
   мержа).
3. Печать пула канарейки прогоняет каждый шаблон той же проверкой зон, что
   `new` (`catalog._tz_path_check`): отказ печати с именем шаблона; doctor —
   та же проверка строкой отчёта.
4. Тесты в `tests/` с заявками «Ловит мутацию» на пп. 1 и 3.

Зоны: scripts/guard.py, orchestrator/pool_seal.py, orchestrator/doctor/,
tests/, docs/codebase-map.md; templates/REVIEW.md и
skills/review-checklist.md — только приложением PLAN.

Только чтение: conftest.py, tests/test_invariants.py, docs/invariants.md,
docs/adr/, docs/roadmap.md, docs/backlog.md, docs/operator-session.md,
CLAUDE.md, *.yaml, .github/workflows/ci.yml.

Рамка: $25.
