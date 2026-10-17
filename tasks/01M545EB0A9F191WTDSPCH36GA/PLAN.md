---
task: 01M545EB0A9F191WTDSPCH36GA
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: D2-1 — проектные скилы и меры для роли внешнего проекта

## Подход
Проект задачи на пути запуска шага определяется одной функцией
`runner._step_project(t) -> (имя, запись | None)`:
- пустая колонка `target` — отказ (ANSWER-1 п.3);
- артель (`repo_context.is_artel`) — без чтения `targets.yaml`, запись `None`
  (ANSWER-1 п.2, как `repo_context.resolve`);
- внешний проект — `targets.target(имя)`; `TargetsError` (файл не читается,
  не разбирается, проект не объявлен) — отказ.
Отказ — исключение `StepProjectError`; `_refuse_before_start` превращает его
в именованный отказ шага `run отклонён: проект задачи не определён` (журнал +
`sys.exit` с id задачи и причиной), агент не запускается. Строка
`t["target"] or config.DEFAULT_TARGET` и `store.task_target` на пути шага
больше не используются: имя проекта передаётся параметром дальше —
`_run_attempts` → `run_agent_once(project=…)` → `role_env`, `role_cwd`,
`_step_docs_dir`, `provider.command`. `run_agent_once`, вызванный без
`project` (тесты зовут его напрямую), определяет проект той же функцией с тем
же отказом (исход `skipped`), не откатываясь на артель.

Проектные скилы — `orchestrator/brief.py`:
- `_project_skills_read(target, entry)` — один проход по `project_skills`:
  проверка имени (непустое, без `/` и `\`, не `.`/`..` — только файл прямо в
  `skills/`) и чтение `skills/<имя>.md` из головы `main` пульта
  (`gitcmd.show(config.MAIN_BRANCH, …, repo=config.ROOT)` — тот же источник,
  что у скилов роли). Первое неверное имя — текст отказа одной строкой:
  `проект <имя>: поле project_skills — скил '<имя скила>' не годен: <причина>`.
- `project_skills_refusal(target, entry) -> str | None` — публичная проверка
  по записи проекта без сборки брифа (ANSWER-1 п.1, для `doctor` части 2).
- `project_skills_text(conn, task_id, role, target, entry)` — тексты для
  брифа + фингерпринт в журнал, как у `skills_text`; отказ — тот же текст.
Бриф и проверка идут через `_project_skills_read`, поэтому источник и текст
отказа у них один. В `runner` тексты добавляются после скилов роли, в порядке
поля; для артели (`entry is None`) промпт байт-в-байт прежний.

Меры для роли внешнего проекта:
- `runner.role_env(..., project=None)`: при проекте, отличном от артели, —
  `GIT_CONFIG_NOSYSTEM=1` поверх окружения провайдера (у любого провайдера).
  Вызовы без `project` (doctor, `role_cmd`, прямой вызов в тестах) — без
  изменений.
- `command(model, docs_dir, project=None)` у `base`/`claude`/`codex`; у Claude
  при проекте не артели `--allowedTools` =
  `Bash(git:*),Bash(python3 <config.ROOT/orchestrator/artel.py>:*)`, у Codex
  параметр не используется (поведение прежнее, О-4).

`targets.py`, `store.py`, `skills/`, `roles.yaml` не меняются.

## Шаги
1. `brief.py`: `_project_skill_name_error`, `_project_skills_read`,
   `project_skills_refusal`, `project_skills_text`.
2. `runner.py`: `StepProjectError`, `_step_project`, отказ в
   `_refuse_before_start`, проектные скилы после скилов роли, проброс проекта
   до `role_env`/`role_cwd`/`_step_docs_dir`/`provider.command`;
   `role_env(project=)` с `GIT_CONFIG_NOSYSTEM=1`.
3. `providers/base.py`, `providers/codex.py` — сигнатура `command`;
   `providers/claude.py` — белый список для проекта не артели.
4. Юнит-тесты `tests/test_step_project.py` на свойства сверх долгоживущего
   файла: пустой `target` — отказ без отката на артель; артель без чтения
   `targets.yaml`; имена `''`/`.`/`..` — отказ по имени; прямой
   `run_agent_once` без проекта — `skipped` для необъявленного проекта.
   Каждый проверен временной мутацией (покраснел, код возвращён).
5. Карта `python3 scripts/codebase_map.py`; долгоживущий файл задачи (7/7),
   планка `plank-run` (5/5), тесты затронутых модулей (`test_providers*`,
   `test_runner*`, `test_brief`, `test_multitarget`, `test_docs_dir_layout`,
   `test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir`,
   `test_provider_scoped_step_env`) — зелёные; полный набор — `suite-run`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1, 2 |
| 4 | 2 |
| 5 | 3 |
| 6 | 2, 3 |
| 7 | 3 |
| 8 | 4, 5 |
| 9 | 2 |

## Влияние на систему
- Путь шага задачи артели: прежние бриф, окружение, argv (AC-1 сверяется
  разовой планкой с деревом базы). Добавлено одно новое условие отказа — пустой
  `target` строки задачи (колонка по умолчанию `artel`, на практике не
  встречается).
- Задача внешнего проекта с необъявленным проектом или нечитаемым
  `targets.yaml` теперь не стартует (раньше шла дальше до предполёта) —
  ужесточение, не ослабление.
- Гейты, лимиты, guard и существующие тесты не трогаются; сигнатуры
  расширены необязательными параметрами — прежние вызовы работают.
- Откат — revert одного merge-коммита.

## Риски
- Тесты, зовущие `run_agent_once` напрямую для задачи внешнего проекта без
  записи в `targets.yaml` песочницы, получат исход `skipped` — проверено
  полным набором: `suite-run` №1 зелёный (5553 прошло, 0 упало, 2 пропущено).

## Предложения системе
