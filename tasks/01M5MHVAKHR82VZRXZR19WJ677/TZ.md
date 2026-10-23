---
task: 01M5MHVAKHR82VZRXZR19WJ677
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Удалить тринадцать определений пульта, которые никто не вызывает

# Удалить тринадцать определений пульта, которые никто не вызывает

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-12 (`docs/audits/code-revision-2026-10-22.md`, раздел «Находки»). Сверено с `origin/main` edbbc059 (пин 870aa7e9; код `orchestrator/`, `scripts/`, `tests/` совпадает) поиском `grep -rnw <имя>` по `orchestrator/`, `scripts/`, `tests/`, `skills/`, `templates/`, `.github/`, включая обращения через модуль и строки `mock.patch`.

Ни одно из тринадцати определений не вызывается ни кодом пульта, ни тестами, ни скилами:

| № | Определение | Где |
|---|---|---|
| 1 | функция `answer_names` | `orchestrator/advance_gates/spec_audit.py:107` |
| 2 | функция `assertion_observation` | `orchestrator/advance_gates/test_integrity.py:1047` |
| 3 | функция `external_code_sha` | `orchestrator/fixation.py:69` (упомянута только в докстринге того же файла, `:95`) |
| 4 | функция `is_clean` | `orchestrator/gitcmd.py:401` (упомянута в комментариях `gitcmd.py:242`, `:511` и в докстринге `tests/test_repo_context.py:91`) |
| 5 | функция `has_mandate_line` | `orchestrator/merge_after.py:395` (`_has_mandate_lines` — другая функция, используется) |
| 6 | функция `guids_path` | `orchestrator/pool_seal.py:75` |
| 7 | функция `retro_path` | `orchestrator/retro.py:258`; докстринг называет единственного вызывающего в `orchestrator/fsm_merge_gate.py`, вызова там нет с 318d3b1f; одноимённые локальные переменные `retro_path` в пяти тестах — не обращения к функции |
| 8 | функция `read_cache` | `orchestrator/retro_corpus.py:106` (`_read_cache` в тесте — другое имя) |
| 9 | функция `task_rounds` | `orchestrator/rounds.py:72` |
| 10 | константа `VERDICT_APPROVED` | `orchestrator/models.py:1582` |
| 11 | константа `SETTING_KEYS` | `scripts/core_reference.py:53` |
| 12 | константа `SHA_HEX` | `scripts/core_reference.py:66` |
| 13 | функция `retro_rel_path` | `orchestrator/retro.py:254` — вызывается только из `retro_path` (`:264`); константа `RETRO_DIR_REL` остаётся, её читает `budget.py:397` |

Определение находки `artifact_branch.send_pending` уже удалено задачей CR-5 (01M5K11D32, коммит 21dfce1d).

Имена функций 1–9 и `retro_rel_path` перечислены в `docs/codebase-map.md`, констант в карте нет (карта генерируется `scripts/codebase_map.py`, CI сверяет её свежесть содержимым).

## Требования

1. Тринадцать определений таблицы удаляются из своих модулей целиком (вместе с докстрингами). Импорты, которые после удаления становятся неиспользуемыми в этом модуле, удаляются; прочий код модулей не меняется.
2. Комментарии и докстринги в зонах задачи, которые называют удалённые имена как существующие (`gitcmd.py:242`, `:511` про `is_clean`; `fixation.py:95` про `external_code_sha`), переписываются без ссылки на удалённое имя, смысл комментария сохраняется. Комментарий `models.py:1580` («Вердикты ревью в `pair_verdicts`.») уточняется: в `pair_verdicts` пишутся вердикты `return` и `approved`, константа есть только для `return` — её читает сверка пары.
3. Тест (новый файл в `tests/`): для каждой из тринадцати пар «модуль — имя» модуль импортируется, и `hasattr(модуль, имя)` ложно; сообщение отказа называет модуль и имя. Для `scripts/core_reference.py` — `from scripts import core_reference`, как в `tests/test_core_reference.py`. На текущем коде — красный по всем тринадцати. Строка «Ловит мутацию»: возврат любого из удалённых определений.
4. Тест (тот же файл): разбор AST всех `*.py` в `orchestrator/` и `scripts/` не находит ни одного обращения к тринадцати именам: `ast.Name` с контекстом `ast.Load`, `ast.Attribute.attr`, `ast.alias.name`; цели присваиваний, определения функций и строковые константы не учитываются. На текущем коде — красный только по `retro_rel_path` (обращение из `retro_path`, `retro.py:264`); после удаления держит отсутствие висячих ссылок. Строка «Ловит мутацию»: обращение к удалённому имени в `orchestrator/` или `scripts/`.
5. Карта кодовой базы `docs/codebase-map.md` перегенерируется `scripts/codebase_map.py` по правилу соглашений.
6. Поведение пульта не меняется. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/advance_gates/spec_audit.py, orchestrator/advance_gates/test_integrity.py, orchestrator/fixation.py, orchestrator/gitcmd.py, orchestrator/merge_after.py, orchestrator/pool_seal.py, orchestrator/retro.py, orchestrator/retro_corpus.py, orchestrator/rounds.py, orchestrator/models.py, scripts/core_reference.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в перечисленных модулях — только удаление определений таблицы, ставших лишними импортов и правка упоминаний по требованию 2.

Только чтение: orchestrator/ и scripts/ (каталоги обхода AST в тесте; меняются только файлы Зон), .github/, skills/, templates/ (места поиска обращений), orchestrator/fsm_merge_gate.py, scripts/codebase_map.py (генератор карты — не меняется).

Не входит: колонка `pair_suspensions.resume_decision` (пишется в `store.resume_pair_suspension`, не читается; решение дублируется в журнал) — удаление меняет схему БД, отдельное решение; устаревшие упоминания `send_pending` в докстрингах трёх тестов (`tests/test_artifact_ref_sync.py:145`, `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py:578`, `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py:191`) и `is_clean` в `tests/test_repo_context.py:91` — существующие тесты не правятся; список CR-2026-09-30-13 (определения, которые держат только тесты).

Бюджет: $25.
