---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ручной мерж для GitHub, часть 2 — открытие пары `github` + `target-human`, проверки записи и строки `doctor`

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–10 привязаны к шагам 1–6; шаги — единицы размера MR по модулю.
- Подход (признаки реализации `READS_CI_REQUIRED_JOBS`, `forge.ci_by_pipeline`, `targets.merged_by_project_people` вместо литералов хостинга) совпадает с SPEC и записками Оператора; модули «только для чтения» из «Не входит» не тронуты (`git diff --stat`: только `ci.py`, `ci_rerun.py`, `cleanup.py`, `doctor/project_checks.py`, `gitlab_adapter.py`, `targets.py`, три файла мандата, карта).
- «Влияние на систему» соответствует диффу: `gitcmd.py` не тронут (условие ANSWER-2), `fsm_merge_gate.py` не тронут, откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/targets.py` `SUPPORTED_PAIRS` — три пары, комментарий обновлён; `unsupported_reason` не правлен. |
| 2 | OK | Новых исключений для GitHub в `_check_delivery`/`_check_full_suite_source` нет; AC-3 (16 полей × 2 хостинга, `full_suite: ci`) зелёный. |
| 3 | OK | `project_checks.py:74-79` — для `not by_pipeline` строка всегда, иначе прежнее условие. `check_workflows_dir_no_paths` пробует имя длиннее всех записей с первым символом вне «занятых» префиксами — ровно формула записки Оператора. Сверил вручную по `config.is_protected_path`: `.github/workflows/`, `.github`, `.github/workflows`, `**/workflows/`, `**/.github/`, `.github/w`, `.git` → ok; `**/`, `**/aaaa`, `**/github/`, `.github/workflows/a`+`b`, `[]` → fail — всё по формуле гейта. |
| 4 | OK | Закреплено `test_ac5_*`; код строк не менялся. |
| 5 | OK | `test_ac6_full_cycle_github_people_to_done`, `test_ac6_kill_after_send_*` зелёные. |
| 6 | OK | Карта содержит новые символы и тесты задачи (27 вхождений), удалённого `_forge_of` нет. |
| 7 | OK | `ci.people_rerun_refusal` в `trigger_rerun` после отказа GitLab и до любого `_gh_at`; в `ci_rerun.py` — после проверок `--reason`, до `ci.verifying_status`, в любом состоянии. `_people_project` `gh` не зовёт. |
| 8 | OK | `targets._check_ci_required_jobs` по `getattr(_hosting_registry().get(hosting), "READS_CI_REQUIRED_JOBS", False)`; `gitlab_adapter.READS_CI_REQUIRED_JOBS = True`; у `operator` — без изменений. Порядок: для локальной записи `_check_delivery` (форма поля) идёт раньше `check()` — текст отказа формы прежний (AC-3 `ci_required_jobs: 5` равен у двух хостингов). |
| 9 | OK | `cleanup.py`: `pr_hosting = hosting and not ci_by_pipeline`; у проекта людей вместо `_close_project_pr` — `PR_LEFT_TO_PROJECT_PEOPLE` рядом с исходом `_delete_origin_branch` (до отправки) и дописью к прежнему тексту (после); GitLab — без фразы; `github` + `operator` — прежний `gh pr close`. |
| 10 | OK | Три файла мандата: `github` + `target-human` перенесён в поддержанные, `gitlab` + `operator` — все случаи и равенства на месте (`GITLAB_REASON`/`GLOP_REASON` — новый текст целиком, `test_ac4_*` равенством), в `test_epic_draft_promote_unsupported_project.py` — только перенос параметра, вид проверки причины прежний; новых `skip`/`xfail` нет. Планка AC-13 зелёная. Поддержанные `run`/`auto`/`approve` идут с подделкой `ci.gh`. |

## Замечания
Замечаний blocker/major/minor нет.

Наблюдение (не замечание, реестр не заводит): в `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py` метод `test_ac2_github_target_human_actions_refuse` сохранил имя «…_refuse», хотя теперь утверждает поддержку; докстринг сценарий описывает верно. Переименование вне буквы мандата ANSWER-1 (сменило бы идентичность метода для гейта неослабления), поэтому разработчику не предъявляется.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved — все требования SPEC реализованы признаками реализации, без литералов хостинга; правка тестов — в рамке мандата ANSWER-1; условие ANSWER-2 (`gitcmd.py` не меняется) выполнено.

## Проверено исполнением
- `artel.py plank-run 01M6N7CYKDAMAKENX60CBK7VQX` — 10 passed, код выхода pytest 0 (включая `test_mandate_files.py`, AC-13).
- `pytest -n 0` по долгоживущим тестам задачи (`tests/test_01m6n7cykdamakenx60cbk7vqx_{doctor_lines,entry_checks,pair_open,people_flow}.py`) и трём файлам мандата — 104 passed.
- `pytest -n 0` по AC-12: `test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py`, `test_awaiting_human_units.py`, `test_gitcmd_push_point.py`, `test_push_hook_stand.py`, `test_mr_delivery_units.py` — 91 passed.
- `pytest -n 0` по тестам затронутых модулей: `test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py`, `test_kill_cleanup.py`, `test_ci_rerun_command.py`, `test_ci_stuck_check_run.py`, `test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py`, `test_01m6m1799ycy5hxmhhd71shjet_github_mr_{gate,units}.py`, `test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `test_ci_callers_project_repo.py` — 354 passed.
- Прямой вызов `check_workflows_dir_no_paths` на 12 наборах `no_paths` (см. требование 3) — исходы совпали с формулой `config.is_protected_path`.
- Временная мутация `_probe_file_name` → `"ci.yml"` не выполнена: запись в файл кода отклонена разрешениями шага; покрытие этой мутации видно из параметров `test_ac4_github_workflows_dir_covered_by_no_paths` (`**/ci.yml` → fail).

## Предложения системе
- `pytest -n 4` в шаге ревью падает «node down: Not properly terminated» (xdist в песочнице роли) — прогоны шага стоит явно вести с `-n 0`; стоит назвать это в миссии ревьювера (`orchestrator/role_prompt.py`).
