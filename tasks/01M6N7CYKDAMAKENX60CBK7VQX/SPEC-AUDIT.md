---
task: 01M6N7CYKDAMAKENX60CBK7VQX
type: spec_audit
author_role: spec_auditor
status: ready
verdict: fail
signals: "б) мандат в ANSWER: Ослабление тестов разрешено: tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py / Ослабление тестов разрешено: tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py / Ослабление тестов разрешено: tests/test_epic_draft_promote_unsupported_project.py; в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py, tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py, tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py, tests/test_awaiting_human_units.py, tests/test_epic_draft_promote_unsupported_project.py, tests/test_gitcmd_push_point.py, tests/test_mr_delivery_units.py, tests/test_push_hook_stand.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; в) защищённые пути: .github/, .github/workflows/; г) budget_usd 85 ≥ 45; д) ТЗ ссылается на ADR: ADR-0029."
spec_sha: eb433765efbb4eea3b9b62fb620e3b6f66425c93
schema_version: 5
---

# SPEC-AUDIT: Ручной мерж для GitHub, часть 2 — открытие пары `github` + `target-human`

## ТЗ и SPEC
Требования ТЗ 1–9 перенесены в SPEC 1–9 почти дословно; мандат ANSWER-1 —
требование 10 и AC-1, AC-2, AC-13; решение «монолит, $85» — раздел деления и
`budget_usd: 85`. Критерии ТЗ перенесены в AC-1…AC-12. Потерь нет.

Расхождения:
1. **AC-13 строже ANSWER-1 и противоречит требованию 10.** ANSWER-1
   (матрица, строка 1) требует «все действия для `gitlab` + `operator` с
   точным текстом причины». SPEC AC-13 добавляет «(равенство, не
   «содержит»)» для КАЖДОГО действия, включая `new`, `run`, `auto`,
   `approve`, `epic draft promote`, строку `project-support`. На main эти
   действия утверждают вхождение полного текста причины в вывод/журнал, а
   не равенство: `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:200`,
   `:231`, `:259`, `:291`, `:314`, `:391`;
   `tests/test_epic_draft_promote_unsupported_project.py:87`;
   `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:131`
   (`check_refusal`). Равенство вывода CLI тексту причины недостижимо, а
   переписать утверждения требование 10 запрещает («иные правки … не
   делаются»). Буквально AC-13 невыполним, и гейт сверки диффа мандата
   (ANSWER-1, вопрос 1) получает условие, которого main не выполняет.
   Нужно: «точный полный текст причины (новая константа) — в выводе/журнале,
   как на main; `unsupported_reason(name) == <текст>` — равенством».
2. **AC-9 шире требования 9.** Требование 9 SPEC: «для записи, у которой
   прежде закрывался бы PR (хостинг без конвейеров), журнал называет «PR не
   тронут»». После отправки PR не закрывался и раньше
   (`orchestrator/cleanup.py:296-302`), а AC-9 требует «PR не тронут» и после
   отправки. ТЗ (критерии) требует того же, что AC-9, так что по сути верно
   AC-9, но требование 9 его не говорит, и не сказано, меняется ли
   прежний текст после отправки для GitLab `target-human` («сервер проекта не
   тронут: …», `cleanup.py:298-299`). Тестов на этот текст на main нет
   (поиск `не тронут`/`оставлены (` по `tests/`), так что ничего не
   ломается, но формулировка двусмысленна.

## Факты против кода
Подтвердилось (HEAD 2b62f8a03):
- `SUPPORTED_PAIRS` — `orchestrator/targets.py:33`, комментарий `:25-30`;
  `unsupported_reason` — `:292-313`, перечень по `sorted(SUPPORTED_PAIRS)`;
  с новой парой даёт «github + operator, github + target-human, gitlab +
  target-human» — AC-2 верен.
- `_check_delivery` — `targets.py:622-726`, `forge` не участвует; вызов —
  `:475`; `_check_full_suite_source` — `:1137-1160`, по
  `getattr(_hosting_registry().get(hosting), "job_test_report", None)`.
- `gitlab_adapter._required` — `orchestrator/gitlab_adapter.py:417-418`;
  `ci.GREEN` с `skipped` — `orchestrator/ci.py:27`.
- `trigger_rerun` — `ci.py:1793-1837`; отказ GitLab по `_pipeline_project`
  — `:1814-1816`; `_ci_confirm_red_or_flake` — `fsm_merge_gate.py:297-338`,
  путь «повтор не запущен» — `:318-322`, выход — `:336-338`; путь
  `target-human` доходит до него через `_approve_for_project_people` →
  `_ci_ready_or_wait` и `_wait_for_branch_ci_green` (`fsm_merge_gate.py:1595-1645`,
  `:372-384`).
- `cleanup_project_remote` — `cleanup.py:279-316`; после отправки —
  `_server_left_to_project_people` (`:319-333`); до отправки — `gh pr close`
  при `_forge_of(target) == "github"` (`:311-312`, `_close_project_pr` `:245`).
  Литерал в `cleanup.py` — в исключениях сторожа
  (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:430-435`).
- `project_entry_checks` — `orchestrator/doctor/project_checks.py:37-76`,
  условие строки `:70-73`; `check_ci_file_no_paths` — `:740-750`
  (`CI_FILE` `:668`, маска через `project_profile.mask_matches`);
  `project-ci-reruns` — `:450-452`.
- `_github_form_allowed` — `orchestrator/forge.py:165-194`, `return rest == []`
  — `:181`: AC-11 верен.

Не подтвердилось / неполно:
3. **«`gh` не вызван» на пути `approve` (AC-7, требование 7).** На гейте
   мержа GitHub статус CI читается через `gh api …/check-runs`:
   `ci.branch_status` → `check_runs` → `check_runs_page` (`ci.py:1206-1225`,
   `:257-282`, вызов `gh("api", …)` на `:267`). `branch_status` зовётся до
   `_ci_confirm_red_or_flake` (`fsm_merge_gate.py:372`) и в нём самом после
   `trigger_rerun` (`:316`). Шпион `ci.gh` в тесте AC-7 обязан увидеть
   `api`-вызовы — иначе красного статуса нет вовсе. Утверждение верно только
   для самого `trigger_rerun` (нет `run rerun`/`run watch`).
4. **`ci-rerun` «без вызова `gh`» (требование 7).** SPEC называет одно место,
   где `gh` зовётся до `trigger_rerun`, — путь зависшей проверки
   (`ci_rerun.py:220-231`). На деле на КАЖДОМ пути первым идёт
   `ci.verifying_status` (`orchestrator/ci_rerun.py:156`, для GitHub — тот же
   `gh api`), а на красном пути ещё `ci.failed_check_names` (`:274`, `:289`).
   Отказ «без `gh`» возможен только до `:156`, то есть раньше проверки
   состояния `verifying` (`:158-162`): для задачи проекта людей текст отказа
   вне `verifying` сменится. SPEC этого не называет; зона
   `ci_rerun.py` («только отказ для проекта людей») это допускает, но
   разработчик, поверивший SPEC и правящий только `_stuck_rerun`, получит
   красный AC-7.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | пара не добавлена в `SUPPORTED_PAIRS`; проверка поддержки по `SUPPORTED_FORGES`. Красная фаза: отказ причиной — безопасно. |
| AC-2 | да | `SUPPORTED_PAIRS` открыт целиком (`gitlab` + `operator` поддержан); текст причины переписан |
| AC-3 | да (закрепление) | исключение для GitHub в `_check_delivery`; отказ `ci_required_jobs` требования 8 поставлен ДО `_check_delivery` (строка `ci_required_jobs` с не-списком даст иной текст) |
| AC-4 | частично | строка не строится без `full_suite`; путь по литералу; маска `*` принята. **Не ловит** пробу одним именем файла (см. отклонение 5) |
| AC-5 | да (закрепление) | `project-ci-reruns`/`token-expiry` появились у GitHub |
| AC-6 | да | `gh pr merge`/`pr close`/`run rerun` на пути; отправка в `base`. Красная фаза: пара закрыта — `approve` отказывает, `gh` подделан |
| AC-7 | **нет в данной форме** | «`gh` не вызван» невыполнимо буквально (отклонение 3); при сужении до «нет `run rerun`/`run watch`» ловит пропуск проверки `merged_by_project_people` в `trigger_rerun`. Красная фаза: подделка `ci.gh` — `gh run watch` с `CI_RERUN_WAIT_SEC` не ждёт по-настоящему, если подделка отвечает сразу; SPEC этого не оговаривает, но безопасность обеспечена подделкой |
| AC-8 | да | отказ по `merged_by_project_people` без признака реализации (GitLab тоже отказывает); проверка только `operator`. **Не ловит** литерал `forge == "github"` в `targets.py` (сторож этот модуль не смотрит) — требование «не литерал» без теста |
| AC-9 | да | `gh pr close` до отправки остался; ветка origin не удалена. Красная фаза: `gh` подделан, `origin` локальный |
| AC-10 | да | новая запись «PR не тронут» попала и в GitLab |
| AC-11 | да | `return rest == []` → `return True` |
| AC-12 | да | литерал `forge`/`merge_gate` в `ci.py`/`cleanup.py`/`project_checks.py` |
| AC-13 | **нет** | «равенство» для действий невыполнимо (отклонение 1) |

5. **Требование 3 / AC-4: «`<любой файл>`» не задаёт формулу.** Опыт
   (`config.is_protected_path` на этой ветке): записи `**/ci.yml` и
   `.github/workflows/c` покрывают `.github/workflows/ci.yml`, но не
   `.github/workflows/release.yml`; `.github/wo` и `.github` (без `/`)
   покрывают всё. Реализация с пробой одного имени (например
   `.github/workflows/ci.yml`) пройдёт все случаи AC-4 и даст `ok` при
   незащищённом каталоге. Нужно задать пробу (имя, которого не бывает в
   `no_paths`, либо требование истинности для двух разных имён) и добавить в
   AC-4 случай `**/<имя файла>` → `fail`.

## Зоны
Зоны SPEC покрывают все правки: `targets.py` (требования 1, 8), `forge.py`/
`gitlab_adapter.py` (признак), `doctor/project_checks.py` (3), `ci.py` (7),
`ci_rerun.py` (7 — с учётом отклонения 4 правка нужна и до `:156`),
`cleanup.py` (9), `docs/codebase-map.md`, `tests/`. Защищённые пути
(`.github/`) не меняются — `.github/workflows/` лишь значение `no_paths` в
песочнице. Песочница ролей не расширяется. Отклонений нет.

## Матрица неослабления
Матрица ANSWER-1 покрывает три мандатных файла. Поиск по `tests/` вызовов
меняемых функций:
- `trigger_rerun` — `tests/test_ci_rerun_command.py`, `test_ci_stuck_check_run.py`,
  `test_ci_callers_project_repo.py`, `test_merge_gate_ci_wait.py`,
  `test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`, `test_ci_project_gh_address.py`
  и др.: ни в одном нет `target-human` — новый отказ их не задевает.
- `project_entry_checks`/`check_ci_file_no_paths` —
  `tests/test_doctor_gitlab_ci_file.py:150-173` (подменяет `ci_by_pipeline`
  → `True`, путь GitLab — прежний),
  `tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py` (GitLab и
  `github` + `operator`) — не ломаются.
- `cleanup_project_remote` —
  `tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py` — только
  `merge_gate: operator` (`:74`) — не ломается.
- `ci_required_jobs` при загрузке —
  `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:61-65` (`github` +
  `operator`), `test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` (GitLab) —
  не ломаются.
- Тесты части 1, подменяющие `SUPPORTED_PAIRS`
  (`test_01m6m1799ycy5hxmhhd71shjet_github_mr_gate.py:367`,
  `_github_mr_units.py:151`): `set(SUPPORTED_PAIRS) | …` устойчив к новому
  составу; повтора CI, `kill`, `ci_required_jobs` в них нет.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `SUPPORTED_PAIRS` + три файла мандата | отказ неподдержанной пары во всех действиях (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:149-391`, `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:188-313`, `tests/test_epic_draft_promote_unsupported_project.py:58-87`) | да, на `gitlab` + `operator` | те же файлы + AC-2, AC-13 | ок, но AC-13 переформулировать (отклонение 1) |
| `trigger_rerun` для проекта людей | повтор GitHub `gh run rerun --failed` (`tests/test_ci_rerun_command.py`, артель) | да для артели/`operator` | AC-7 (случай `github` + `operator`) | ок |
| `cleanup_project_remote` до отправки | `gh pr close` GitHub (`tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:460`) | да для `operator` | тот же тест + AC-9 | ок |
| условие строки `project-ci-file-no-paths` | GitLab без `full_suite` ci/both — строки нет (`tests/test_doctor_gitlab_ci_file.py:150-173`) | да | тот же тест + AC-4 | ок |

SPEC не несёт раздела «Меняемое поведение» — смен ожиданий существующих
тестов вне мандата нет, это согласуется с поиском выше.

## Пути обхода гейтов
6. **Проба одного файла в `project-ci-file-no-paths` GitHub** (отклонение 5):
   буквальное «`.github/workflows/<любой файл>`» с фиксированным именем
   даёт `ok` для `no_paths: [**/ci.yml]` — роль может править
   `.github/workflows/другой.yml`, а `doctor` говорит «покрыт».
7. **Литерал в `targets.py` вместо признака реализации (требование 8).**
   Сторож литералов исключает `targets.py`
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:436`), AC-8
   поведенчески не отличает `forge == "github"` от признака: новый хостинг
   без чтения поля пройдёт молча. Нужен случай AC-8 с подменённой
   реализацией в `forge.IMPLEMENTATIONS` (без признака → отказ).
8. **AC-7 «`gh` не вызван»** — тест-автор, не сумевший выполнить его
   буквально, сузит шпион произвольно; без названного набора форм
   (`run rerun`, `run watch`) сужение может выкинуть и их.

## Вердикт
`fail` — возврат аналитику. Отклонения:
1. AC-13 «равенство, не «содержит»» невыполним и противоречит требованию 10:
   действия на main утверждают вхождение
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:200,231,259,291,314,391`,
   `tests/test_epic_draft_promote_unsupported_project.py:87`,
   `tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py:131`).
2. AC-7: «`gh` не вызван» на `approve` невозможен — статус CI GitHub идёт
   через `gh api` (`orchestrator/ci.py:267`, `orchestrator/fsm_merge_gate.py:316`,
   `:372`); сузить до «нет `run rerun`/`run watch`, `trigger_rerun` не зовёт
   `gh`».
3. Требование 7: `ci-rerun` зовёт `gh` до `trigger_rerun` на всех путях
   (`orchestrator/ci_rerun.py:156`, `:274`, `:289`), не только на пути
   зависшей проверки; назвать место отказа и смену текста вне `verifying`.
4. Требование 3/AC-4: проба «`<любой файл>`» не определена — `**/ci.yml`,
   `.github/workflows/c` проходят на одном имени (опыт `config.is_protected_path`);
   задать пробу и добавить случай `fail`.
5. Требование 8/AC-8: «не литерал» без теста — `targets.py` вне сторожа
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:436`).
6. Требование 9 vs AC-9: «PR не тронут» после отправки и текст GitLab после
   отправки (`orchestrator/cleanup.py:298-299`) не согласованы.
