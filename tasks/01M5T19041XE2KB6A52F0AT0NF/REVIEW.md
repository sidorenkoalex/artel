---
task: 01M5T19041XE2KB6A52F0AT0NF
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: ИИ-настройки внешнего проекта — полем записи, вне рабочей копии роли и вне правок задач

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–13 → шаги 1–4); шаги — размер MR, не микрооперации.
- Подход («одна точка» `targets.wrapper_paths` → `repo_context.protected_paths`) совпадает с ANSWER-1 ответ 1; места вызова `protected_paths` не правились (в диффе нет fsm.py/catalog.py/fsm_merge_gate.py/advance_gates/*), `checkpoint.py` и `brief.py` не тронуты — как требует «Не входит».
- Расширение зон на `orchestrator/store.py` покрыто ANSWER-3; правка — одна функция чтения `journal_action_exists`.
- «Влияние на систему» соответствует диффу: `config.PROTECTED_PATHS` не изменён (`config.py:776-782` — те же 19 записей), `docs/invariants.md`/`tests/test_invariants.py` в диффе нет; путь отката описан (`sparse-checkout disable`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.AGENT_WRAPPER_MARKERS` — ровно 4 маркера в порядке SPEC; в `PROTECTED_PATHS` не добавлены |
| 2 | OK | `preflight.py` `TARGET_WRAPPER_MARKERS` вычисляется `removeprefix("**/").rstrip("/")`; значение прежнее (AC-2 в планке зелёный) |
| 3 | OK | `is_protected_path`: `**/<каталог>/` → `rest[:-1] in parts[:-1]`; `**/<имя>` — по-прежнему `parts[-1]`; префиксная ветка не тронута. Записей-масок каталога у артели нет — AC-4/AC-5 сохраняются |
| 4 | OK | Проверка `agent_wrapper` — та же форма, что у `no_paths` (`targets.py:580-597`); `LOCAL_FIELDS["policy"]`, `_flatten`, `_split_entry` переносят поле |
| 5 | OK | `targets.wrapper_paths` — `dict.fromkeys` над маркерами и `agent_wrapper`: порядок сохранён, повторы убраны |
| 6 | OK | `protected_paths` внешнего: `no_paths` как есть + обвязка, отсутствующая той же строкой; у артели — `tuple(config.PROTECTED_PATHS)` |
| 7 | OK | `config.is_protected_zone` (зона-каталог маски с `/` и без), `guard.protected_zones` зовёт её — через неё идут `catalog._tz_path_check` (`catalog.py:218`), `fsm._spec_protected_zones_refusal` (`fsm.py:1188`), `spec_audit.py:131`. Гейты диффа остаются на `is_protected_path` |
| 8 | OK | `_check_knowledge_outside_wrapper`: `normpath`, исключение `.` и корневых `CLAUDE.md`/`AGENTS.md`, сверка файлом и как каталог (`rel + "/"`), текст называет компонент, элемент и путь обвязки; каталоги-предки (`docs/`, `./`) не отказывают |
| 9 | OK | `_exclude_wrapper` на обоих путях `ensure` (новая и зарегистрированная копия): no-cone sparse-checkout `/*` + `!шаблоны`, сравнение с `sparse-checkout list` для идемпотентности и следования текущему списку, `config --worktree core.excludesFile`, `git clean -f -d -x` по pathspec обвязки; сбой — именованная причина. У артели git не зовётся |
| 10 | OK | `check_target_wrapper_worktrees` зарегистрирована в `cli.all_checks` рядом с `target-wrapper`; `check_target_wrapper` не изменён |
| 11 | OK | Текст источника называет `no_paths` и обвязку, без « (»; у артели прежний |
| 12 | OK | `REQUIRED_TOOLS["git"]` = `(2, 35, 0)` |
| 13 | OK | Долгоживущий `…_wrapper_flow.py` (plank-run, suite-run, гейт зон, дифф ревью) зелёный |

Тесты:
- Изменения существующих тестов — строго в объёме мандата ANSWER-1: `test_project_protected_paths.py:87` (`assertEqual` прежний, ожидание = требование 6), выборки `artel_only_path` в `in_dev_gates`/`merge_gate`/`draft_mr` и два перебора в `draft_mr` (`:167`, `:179` по базе) — исключение вычислено `config.is_protected_path(e, config.AGENT_WRAPPER_MARKERS)`, не литералом. Сужение выборки исключает ровно `CLAUDE.md`, `AGENTS.md` (проверил по `PROTECTED_PATHS`: иных записей под маркерами нет). Утверждения не удалены и не ослаблены; `TargetWrapperCheckTest`, `test_protected_test_settings.py`, `spec_zones`, `no_paths_mirror`, `knowledge_brief` в диффе отсутствуют.
- Новый `tests/test_workspace_wrapper_excludes.py`: оба метода несут сценарий и «Ловит мутацию» с наблюдаемым расхождением; свойства (перенос глобального игнора, неразрешённая запись без отказа и с одной пометкой) не повторяют долгоживущие файлы задачи. Заявку первого метода проверил временной мутацией (см. ниже) — красный.
- Долгоживущие файлы задачи и планка — по формам `Группа:` корректны (свойства кода — `долгоживущий`, планка base-values — разовая).

## Замечания

Замечаний уровня blocker/major/minor нет. Наблюдения к сведению (без последствий, достаточных для замечания, в реестр не заносятся):
- `orchestrator/workspace.py` `wrapper_file_on_disk` — докстринг говорит «вложенные репозитории не обходятся», а код пропускает только каталоги/файлы `.git`, содержимое вложенного репозитория обходится; на поведение строки `doctor` не влияет (информационный `warn`), только на точность описания и время обхода больших копий.
- `agent_wrapper: [""]` проходит проверку «список строк» (как и `no_paths: [""]` на main) — перечень тогда защищает любой путь (fail-closed), а sparse-шаблон вырождается в `!/`. Поведение унаследовано от формы `no_paths`, SPEC требует ту же проверку — не дефект задачи.
- Проверил сценарий «`.gitignore` проекта разыгнорирует путь под обвязкой» (`.claude/*` + `!.claude/commands/`): на git 2.50 `git add -A` в sparse-копии с новым файлом под `.claude/commands/` выходит кодом 0 и не стейджит его — чекпоинт не падает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5T19041XE2KB6A52F0AT0NF` — 5 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5t19041xe2kb6a52f0at0nf_wrapper_*.py tests/test_workspace_wrapper_excludes.py tests/test_project_protected_paths.py tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py tests/test_protected_test_settings.py tests/test_multitarget.py` — 137 passed, 159 subtests passed (git 2.50.1).
- Временная мутация: в `workspace._exclude_wrapper` `own = _inherited_excludes(...)` → `own = ""` — `tests/test_workspace_wrapper_excludes.py::test_global_ignore_survives_own_excludes_file` красный (1 failed, 1 passed); код возвращён `git checkout`, `git status` чист.
- Проба git на временном репозитории (скрипт Python вне рабочей копии): no-cone sparse `/*`, `!**/.claude/`, `!**/CLAUDE.md` + `config --worktree core.excludesFile`; `.gitignore` с `!.claude/commands/`; новый файл под `.claude/commands/` — `git add -A` код 0, в индексе только `src/m.py`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта свежа); файл возвращён.
- `grep` вызовов `is_protected_path`/`protected_zones` по `orchestrator/` и `scripts/` — все сверки зон идут через `guard.protected_zones`.

## Предложения системе
- Окружение шага ревью: `bash` скрипта из каталога документов требует подтверждения, а в `PATH` процесса Python нет `mkdir`/`ls`/`rm` — проба git удалась только чистым Python; стоит назвать это в скиле review-checklist (приём «временная проба на одноразовом репозитории»).
