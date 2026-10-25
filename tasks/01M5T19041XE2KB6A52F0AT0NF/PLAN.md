---
task: 01M5T19041XE2KB6A52F0AT0NF
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: ИИ-настройки внешнего проекта — полем записи, вне рабочей копии роли и вне правок задач

## Подход
Одна точка правды для обвязки — `targets.wrapper_paths(agent_wrapper)`:
`config.AGENT_WRAPPER_MARKERS`, затем элементы поля `agent_wrapper` записи без
повторов строк. Через неё:
- `repo_context.protected_paths(ctx)` внешнего проекта = `no_paths` как есть +
  пути обвязки, которых в кортеже ещё нет (`RepoContext.agent_wrapper` несёт
  сырое поле; `repo_context.wrapper_paths(ctx)` — действующий список, у артели
  пуст). Все места сверки получают обвязку без правки (ANSWER-1, ответ 1).
- Формула `config.is_protected_path` понимает `**/<каталог>/`: компонент
  `<каталог>`, за которым в пути идёт `/` (`parts[:-1]`). Прочие записи —
  без изменений (AC-4).
- Зоны: `config.is_protected_zone` = формула путей ИЛИ (только для записей
  `**/<каталог>/`) зона с `/` на конце; `guard.protected_zones` зовёт её —
  этим путём идут «Зоны:» ТЗ (`catalog._tz_path_check`) и `zones:` SPEC
  (`fsm._spec_protected_zones_refusal`). У артели нет записей-масок каталога —
  результат прежний (AC-5: зона `skills` без `/` не защищена).
- `targets.check`: поле `agent_wrapper` — «список строк»; у внешнего проекта
  с `components:` элемент `knowledge`, нормализованный `posixpath.normpath`,
  отказывает, если покрыт путём обвязки (формулой для файла и как каталог —
  `rel + "/"`), кроме корневых `CLAUDE.md`/`AGENTS.md` и `.`. Локальный слой:
  поле в `LOCAL_FIELDS["policy"]`, `_flatten` переносит; `projects._split_entry`
  кладёт плоское поле в `policy`.
- `workspace.ensure` (новая и зарегистрированная копия) зовёт
  `_exclude_wrapper`: у артели — ничего; у внешнего — `git sparse-checkout set
  --no-cone /* !<шаблон>…` только если `sparse-checkout list` отличается от
  нужного (идемпотентность, следование текущему списку); шаблон маски `**/…` —
  как есть, прочий путь — `/<путь>` с экранированием. `git sparse-checkout`
  сам включает `extensions.worktreeConfig` и пишет `core.sparseCheckout` в
  `config.worktree` копии (клон и чужие копии не задеты, AC-17). Затем свой
  файл игнора в git-каталоге копии (`core.excludesFile` через `config
  --worktree`): пути обвязки + текст прежде действовавшего глобального
  игнора (иначе `.DS_Store` попадал бы в `git add -A`). Игнор снимает отказ
  `git add -A` чекпоинта на неотслеживаемом файле вне sparse (AC-20) без
  правки `checkpoint.py`. Затем `git clean -f -d -x` по pathspec обвязки
  (`:(glob)**/.claude/**`, `:(literal)harness/`) — неотслеживаемые и
  игнорируемые под обвязкой (AC-19). Любой сбой — именованная причина `ensure`,
  `runner.role_cwd` поднимает `OSError`, роль не стартует (AC-21).
- Возврат из verifying (CI 40230886175, `test_merge_outcome_module::test_ac14…`):
  запись проекта не разрешена (нет в `targets.yaml`) — `ensure` НЕ отказывает,
  как и до задачи: копия приводится по стандартным маркерам
  (`targets.wrapper_paths()` без `agent_wrapper`), пометка — запись журнала
  задачи `wrapper_markers_only` (одна на одинаковый текст: `ensure` зовут
  каждый шаг и гейт), без строки задачи в БД — stderr
  (`workspace._note_unresolved_wrapper`). Существующий тест не тронут.
- `doctor`: новая `check_target_wrapper_worktrees` рядом с `target-wrapper`
  (`cli.all_checks`), обходит `worktrees/*` проекта (`workspace.wrapper_file_on_disk`,
  покрытие — `workspace.wrapper_covers`, согласовано с шаблонами sparse).
  `TARGET_WRAPPER_MARKERS` выводится из единой константы.
- Draft MR: источник внешнего проекта называет `no_paths` и обвязку, без « (».
- `stack.REQUIRED_TOOLS["git"]` — `(2, 35, 0)`.

Бюджет SPEC ($75) не пересматривается.

## Шаги
1. `config.py`: `AGENT_WRAPPER_MARKERS`, формула `**/<каталог>/`, `is_protected_zone`;
   `guard.protected_zones` через неё; `doctor/preflight.py` — вывод
   `TARGET_WRAPPER_MARKERS`; `stack.py` — минимум git.
2. `targets.py`/`projects.py`/`repo_context.py`: поле `agent_wrapper` в обоих
   слоях и переносе, `wrapper_paths`, отказ `knowledge`, перечень проекта.
3. `github_adapter.py`: текст источника перечня.
4. `workspace.py`: исключение обвязки в `ensure`; `doctor` — проверка
   `target-wrapper-worktrees`.
5. Тесты мандата ANSWER-1 (`test_project_protected_paths.py:87`, выборки
   `artel_only_path`/перебор записей в трёх файлах `01m45fk56…` — исключение
   вычисляется `config.is_protected_path(e, config.AGENT_WRAPPER_MARKERS)`);
   свой тест `tests/test_workspace_wrapper_excludes.py` (глобальный игнор
   переживает свой файл игнора копии; неразрешённая запись — без отказа,
   стандартные маркеры исключены, одна пометка в журнале; обе мутации
   проверены — красный);
   карта `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 1 |
| 8 | 2 |
| 9 | 4 |
| 10 | 4 |
| 11 | 3 |
| 12 | 1 |
| 13 | 4 (долгоживущий `…_wrapper_flow.py` зелёный) |

Прогоны после фикса возврата: `tests/test_merge_outcome_module.py` — 19 passed
(упавший в CI `test_ac14…` зелёный); 38 файлов затронутых модулей (workspace*,
project_*, *outcome*, two_sided*, worktree*, wrapper_* задачи, doctor) — 551 passed;
планка 5 passed. Полный набор разработчику недоступен (`suite-run` отказывает) —
его гоняют CI и гейт приёмки.
Прежние прогоны: планка `plank-run` — 5 passed, код 0; долгоживущие
`tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_*.py` — 50 passed; затронутые
модули (protected_paths, 01m45fk56 ×5, workspace ×3, project_area, repo_context,
doctor, stack, guard_zones, protected_paths_gate, protected_test_settings,
ci_protected_paths, github_adapter, targets_migrate, doctor_layer,
targets_knowledge, knowledge_brief, project_role_step, step_project,
catalog_tz_zones, zones_gate/approve, project_components, doctor_components,
worktrees_prune, project_kill_cleanup, draft_mr_commits, invariants,
codebase_map) — все зелёные.

## Влияние на систему
- Артель: перечень, формула на её записях, зоны, рабочие копии — без изменений
  (AC-4/5/9/22 зелёные; у артели `_exclude_wrapper` не зовёт git).
- `config.PROTECTED_PATHS` и `docs/invariants.md`/`tests/test_invariants.py` не
  тронуты. Гейты не ослаблены: перечень внешнего проекта только расширен.
- Правки существующих тестов — строго в объёме мандата ANSWER-1; утверждения не
  ослаблены (`assertEqual` прежний, исключение из выборки — вычислено из константы).
- `checkpoint.py` не правился: AC-20 закрыт игнором копии.
- Побочные эффекты на клон: `extensions.worktreeConfig = true` в общем конфиге
  клона внешнего проекта (ANSWER-2, ответ 3). Откат — revert коммитов задачи;
  уже приведённые копии вернуть полными: `git -C <копия> sparse-checkout disable`.
- `ensure` у внешнего проекта теперь делает 3–5 git-вызовов на каждый вход
  (sparse list, rev-parse, config, clean) — ensure зовут шаги и гейты; стоимость
  миллисекунды, `git clean` с glob-pathspec обходит дерево копии.

## Риски
- Свой `core.excludesFile` копии подменяет глобальный: текст глобального
  игнора дописывается в него на каждом `ensure` (тест
  `test_workspace_wrapper_excludes.py`); системный `core.excludesFile`
  (`/etc/gitconfig`) учитывается тем же `config --get-all`.
- Ветка, правящая обвязку «по делу» (Оператор), в копии без обвязки этих
  файлов не видит — по замыслу SPEC; правка идёт `git add --sparse -f`.

## Предложения системе
- Сторож `conftest.py` отказывает `-n` (xdist) даже для явного списка файлов
  затронутых модулей — прогон ~35 файлов в шаге разработчика идёт 3 минуты
  последовательно; узел: `conftest.py` / `suite-run` (нет команды «затронутые
  модули параллельно»).
