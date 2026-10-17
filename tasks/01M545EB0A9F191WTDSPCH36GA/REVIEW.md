---
task: 01M545EB0A9F191WTDSPCH36GA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: D2-1 — проектные скилы и меры для роли внешнего проекта

## Фаза A: план
- Таблица покрытия полна (требования 1–9 → шаги 1–5). Шаги — единицы размера MR.
- Подход согласуется с ANSWER-1: п.1 — `brief.project_skills_refusal(target, entry)`;
  п.2 — артель без чтения `targets.yaml` (`runner._step_project`, ветка `is_artel`);
  п.3 — пустая колонка `target` даёт отказ, откат на `DEFAULT_TARGET` убран.
- «Влияние на систему» сходится с diff: тронуты только `brief.py`, `runner.py`,
  `providers/{base,claude,codex}.py` и новый `tests/test_step_project.py`.
  `targets.py`, `store.py`, `skills/`, `roles.yaml`, гейты и существующие тесты
  не тронуты. Откат — revert merge-коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `runner.py` `_refuse_before_start`: `project_skills_text` дописывается после `skills` роли, в порядке поля (`_project_skills_read` идёт по списку по порядку). |
| 2 | OK | Имя: пустое, с `/` или `\`, `.`/`..` → отказ по имени. Остальное → `gitcmd.show(config.MAIN_BRANCH, "skills/<имя>.md", repo=config.ROOT)` — тот же источник, что у `skills_text`. Текст отказа одной функцией для брифа и для проверки: `проект <p>: поле project_skills — скил '<n>' не годен: …`. `targets.py` не менялся. Элементы списка — строки: это уже гарантирует `targets.check` (`targets.py:162-165`), так что `name.strip()` не упадёт. |
| 3 | OK | При `project_entry is None` (артель) ветка проектных скилов не исполняется. Планка `test_main_parity.py` зелёная. |
| 4 | OK | `role_env(project=…)`: `GIT_CONFIG_NOSYSTEM=1` ставится после `provider.environment`, значит у любого провайдера. AC-6 (Codex) зелёный. |
| 5 | OK | `claude.external_allowed_tools()` = `Bash(git:*),Bash(python3 {config.ROOT/"orchestrator"/"artel.py"}:*)`; `Bash(python3:*)` не остаётся. |
| 6 | OK | `project is None or is_artel(project)` → прежний `ALLOWED_TOOLS`; у `role_env` без проекта / для артели окружение не меняется. |
| 7 | OK | В `base.py`/`codex.py` меняются только сигнатура и докстринг; тело `CodexProvider.command` не тронуто. |
| 8 | OK | Тесты на песочнице, сети нет. |
| 9 | OK | `_step_project` вызывается в `_refuse_before_start` до провайдера и предполёта. `store.task_target` на пути шага заменён проектом, который пробрасывается в `_run_attempts` → `run_agent_once` → `_prepare_step` (`role_env`, `role_cwd`) и `_spawn_and_wait` (`_step_docs_dir`, `provider.command`). При прямом вызове `run_agent_once` без проекта он определяется той же функцией с отказом (`skipped`). `store.task_target` остаётся только в `_step_docs_dir(project=None)` — это вне пути шага. |

## Замечания
Блокеров и major нет.

Сверка, без замечания: `_step_docs_dir(conn, task_id, target)` в `_build_prompt` для артели даёт тот же адрес, что прежний `store.task_target` (колонка `artel`). `_escalate_after_attempts` получает тот же `target`, что раньше давал `t["target"] or DEFAULT_TARGET`, если колонка непуста.

Тесты: `tests/test_step_project.py` не повторяет долгоживущий файл. Там пустая колонка, артель без `targets.yaml`, вырожденные имена и прямой `run_agent_once` — у долгоживущего файла этих сценариев нет. Заявки «Ловит мутацию» проверены временными мутациями, подменой в памяти, файлы не правились (см. ниже); все три покраснели. Удалённых или ослабленных утверждений в `tests/` в diff нет: файл только добавлен.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_step_project.py tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py tests/test_brief.py tests/test_multitarget.py tests/test_provider_scoped_step_env.py` — 94 passed, 29 subtests passed.
- `python3 -m pytest -q tests/test_providers*.py tests/test_runner*.py tests/test_docs_dir_layout.py tests/test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir.py` — 145 passed, 105 subtests passed.
- `artel.py plank-run 01M545EB0A9F191WTDSPCH36GA` — 5 passed, код выхода pytest 0 (в том числе `test_main_head_skills.py`, `test_main_parity.py`).
- Временные мутации через `mock.patch.object` в процессе `python3 -c`, файлы не правились, `git status` чистый:
  - `brief._project_skill_name_error` → «только разделитель»: `ProjectSkillNameTest` красный (4 провала subTest);
  - `runner._step_project` с откатом пустого `target` на артель: `test_empty_target_refuses_without_artel_fallback` красный (2 провала);
  - `run_agent_once` без проекта → `store.task_target`: `RunAgentOnceProjectTest` красный.
- CI коммита 06d7416b зелёный (16 проверок, из пакета).
- Свежесть `docs/codebase-map.md` не проверял: генератор запускать не стал, чтобы не менять рабочую копию.

## Предложения системе
- Песочница Bash шага ревью отклоняет `cmd > file`, heredoc и `cd …; grep` (статический анализ). Временную мутацию пришлось делать через `python3 -c` с `mock.patch.object`. Этот приём стоит упомянуть в `skills/review-checklist.md` («Сторож — проверен временной мутацией») как способ, который не трогает рабочую копию.
