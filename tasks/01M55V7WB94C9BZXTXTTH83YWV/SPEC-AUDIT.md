---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py, tests/test_ci_rerun_command.py, tests/test_ci_status.py, tests/test_ci_stuck_check_run.py, tests/test_invariants.py, tests/test_main_ci_fetched_repo.py, tests/test_main_ci_line.py, tests/test_merge_gate_ci_wait.py; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: 924d3943c06bcac9dabe1b87d05f0a1325b82761
schema_version: 5
---

# SPEC-AUDIT: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## ТЗ и SPEC
ТЗ → SPEC:
- ТЗ «Требуется» 1 (gh api через `GH_REPO` без `--repo`, gh run/pr — `--repo`,
  токен слота, артель без изменений) → требования 1-2 SPEC. Есть.
- ТЗ 2 (репозиторий доходит до всех функций пути verifying/ci-rerun/автогейт/
  гейт мержа, перечень по коду) → требование 3, перечень функций и вызывающих.
  Есть; перечень сверен ниже («Факты против кода») — полон.
- ТЗ 3 (фиксация артели тестами до правки) → требование 6, AC-1. Есть.
- ТЗ 4 (подставной `gh`, учебный проект, `verifying_status`/`branch_status`
  зелёные, `trigger_rerun`) → требование 8, AC-4, AC-5, AC-6. Есть.
- Три критерия ТЗ → AC-1, AC-2/AC-3, AC-4. Есть.
- Зоны и «только чтение» ТЗ → frontmatter `zones` и «Не входит» SPEC
  дословно. «Не входит» ТЗ перенесено.

Решения Оператора на гейте SPEC:
- №1 (1) прежняя форма вызовов артели + подмены → требование 2 (перечень
  подмен расширен); (2) `accepted_full_suite` в AC-1 → есть; (3) `GH_REPO` без
  `token_slot` → требование 1, AC-8; (4) правило `gitcmd.url_key`, url на
  `.git`/`/` → требование 1, AC-2; (5) сценарии AC-2/AC-3 → перечислены. Все
  перенесены.
- №2 (1) требование 2 на все функции перечня и вызывающих, «ни одна подмена
  не правится» → требование 2, AC-1; (2) признак по записи `targets.yaml`,
  `main_line_status(repo=config.ROOT)` — артель → требование 1 (абзац 3),
  требование 2, AC-1; (3) `main_line_status` с клоном проекта в AC-2 → есть;
  (4) `ci_rerun.py:272` `repo=` → требование 5, AC-10; (5)
  `_inherited_from_main` по `origin/<base>` → требование 4, AC-9; (6)
  flake-rate «повтор не запущен» → требование 7, AC-11. Все перенесены.

SPEC → ТЗ: требования 4, 5, 7 вне текста ТЗ, но каждое — прямое решение
Оператора №2 (5), (4), (6). Лишних требований нет. Расхождений нет.

## Факты против кода
Сверено по рабочему каталогу (ветка задачи = main на момент аудита):
- `ci.gh` `ci.py:39-80`, `cwd=config.ROOT` — `ci.py:73`; `--repo` дописывается
  к любому argv (`:63`), токен — `gitcmd.project_by_url` + `hosting_token`
  (`:65-71`). Подтверждено.
- `_repo_kwargs` `ci.py:83-95`: `None` и `is_artel(repo)` → `{}`; `config.ROOT`
  не клон артели (`repo_context.py:170-171`) → `{"repo": ROOT}`. Подтверждено;
  отсюда верна оговорка требования 2 про `pin.py:86`/`doctor/main_ci.py:33`.
- `check_runs_page :118` (repo как `--repo`), `check_runs :143` (repo нет),
  `run_list :198`, `_commit_workflow_runs :371` (gh api `:383`), `_inherited_from_main
  :474-488` (`head_sha("main")` `:478`, `failed_check_names(main_sha)` `:481`),
  `verifying_status :600`, `_no_checks_by_branch :674` (`run_list(branch)` `:678`),
  `failed_check_names :732`, `branch_status :767`, `accepted_full_suite :823`
  (отказ внешнему `:829`), `_main_line_runs :974`, `main_line_status :1029`,
  `find_run_id :1136` (gh `:1162`, `check_runs` `:1180-1181`),
  `check_run_workflow_run :1211` (gh `:1221`), `trigger_rerun :1235`
  (`head_sha(branch)` `:1256`), `rerun_started :1274-1289`, тексты «не запущен»
  `:1258`, `:1261`, `:1265`. Все подтверждены.
- Вызывающие: `ci_rerun.py:123, :158, :224, :232, :244, :267, :272, :279, :298`;
  `fsm_merge_gate.py:290, :293, :341, :571, :579, :614, :618`, узел
  `_ci_confirm_red_or_flake :280-309`; `acceptance.py:2069, :2087, :2184`;
  `github_adapter.py:168, :193, :306`; `fsm_advance.py:453`;
  `fsm_autogate.py:287`; `pin.py:86`; `doctor/main_ci.py:33`. Полный поиск
  `ci.<функция gh>(` по `orchestrator/` и `scripts/` других вызывающих не дал;
  `advance_gates/` функций `ci` не зовёт. Подтверждено.
- `fsm._origin_main_sha(target, *, repo=None)` `fsm.py:166`, образец `:264-269`;
  при `repo=None` фетч по адресу проекта в `config.ROOT` (`:207-208`).
  Подтверждено.
- `gitcmd.url_key` `gitcmd.py:44-46`; `token_slot` нет → `(None, None)`
  `gitcmd.py:133-135`; sled `url` — `targets.yaml:70`. Подтверждено.
- Подмены требования 2: `test_invariants.py:326-328`, `test_ci_status.py:160,
  :367, :372, :798`, `test_main_ci_line.py:62`, `test_merge_gate_ci_wait.py:82`,
  `test_ci_rerun_command.py:238, :242`, `test_ci_stuck_check_run.py:220`,
  `test_main_ci_fetched_repo.py:64`, `test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203`.
  Подтверждены (форма как названа). Перечень помечен «среди них» — не
  исчерпывающий: ещё `test_ci_status.py:793` и `:846` (`head_sha` как
  `lambda branch:` под `trigger_rerun`), `test_merge_gate_ci_wait.py:78`
  (`branch_status` как `lambda branch, repo=None:`), `test_ci_rerun_command.py:254`
  (`_origin_main_sha` как `lambda *a, **kw:`) — все держит общее правило AC-1.
- «Тестов, утверждающих `--repo` у gh api, нет»: литерала `--repo` в `tests/`
  нет; `test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:191` проверяет
  `repo` у `gh pr ready` — форма `gh pr` остаётся. «Подтверждённый красный» —
  только `test_merge_gate_ci_wait.py:163` с запущенным повтором. Подтверждено.

Несовпадений нет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | артель получает `GH_REPO`/`--repo`/`GH_TOKEN`; признак внешнего — «не клон артели» (ловит `main_line_status(repo=config.ROOT)`); новый именованный аргумент в вызове артели (ломает подмены `lambda sha:`/`lambda branch:`) |
| AC-2 | да | `gh api` внешнего с `--repo` либо без `GH_REPO`; `GH_REPO` с `.git`/`/`; пропуск репозитория в одном из мест (`_inherited_from_main`, `_commit_workflow_runs`, `find_run_id`→`check_runs`, `check_run_workflow_run`, `_main_line_runs`) |
| AC-3 | да | `_no_checks_by_branch` зовёт `run_list(branch)` без репозитория; `gh run` внешнего через `GH_REPO` вместо `--repo` |
| AC-4 | да | `verifying_status` не передаёт репозиторий в `check_runs` — исход 422 «голова ветки не в origin» |
| AC-5 | да | то же для `branch_status` |
| AC-6 | да, с оговоркой К-2 | `trigger_rerun` читает голову в клоне артели; `gh run rerun/watch` без `--repo`; поиск прогона без `GH_REPO` |
| AC-7 | да | вызывающий в `ci_rerun.py`/`fsm_merge_gate.py` не передаёт репозиторий |
| AC-8 | да | `GH_REPO` ставится только вместе с токеном |
| AC-9 | да | вершина — локальная `refs/heads/main`/`<base>` вместо `origin/<base>`; литерал `main` вместо `base` |
| AC-10 | да | `_origin_main_sha` без `repo=` у внешнего; `repo=` появился у артели |
| AC-11 | частично (К-1) | при незапущенном повторе и красном — прежние «ре-ран тоже красный»/«подтверждённый красный»; при запущенном — пропала «подтверждённый красный». НЕ ловит: незапущенный повтор + зелёный повторный статус → прежняя запись «флейк: … ре-ран зелёный» |

## Зоны
- Требования меняют `orchestrator/ci.py` (адресация, параметр репозитория,
  `_inherited_from_main`), `orchestrator/ci_rerun.py` (передача репозитория,
  `:272`), `orchestrator/fsm_merge_gate.py` (передача в `trigger_rerun :290`,
  текст flake-rate `:298-306`), `tests/` — все в зонах. `acceptance.py`,
  `github_adapter.py` в зонах с запасом (правки могут не понадобиться — SPEC
  это говорит).
- `docs/codebase-map.md` регенерируется при правке `*.py` — входит в
  `config.COMMON_ZONES` (`config.py:803`).
- Помощник «клон → запись `targets.yaml`» строится из `repo_context.clone_path`
  и `targets.load` без правки `repo_context.py`/`targets.py`/`gitcmd.py` (только
  чтение) — вне зон менять ничего не требуется.
- `fsm.py`, `fsm_advance.py`, `fsm_autogate.py` вне зон: правки не нужны
  (сверено — клон передают, `_origin_main_sha` принимает `repo`).
- Защищённые пути: `tests/test_invariants.py` — только чтение, подмена
  `:326-328` должна работать без правки (требование 2). Правок `skills/`,
  `templates/`, `gates.yaml`, `roles.yaml`, `.github/` нет. Песочница ролей не
  расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `ci.gh`: `gh api` внешнего без `--repo`, с `GH_REPO` | токен слота у `gh` внешнего (D2-2) — `tests/test_01m545edths47hsb59akc1ez9c_project_token.py:517-544` (gh pr) | да | тот же тест + AC-2, AC-8 | остаётся |
| признак артели в `ci` | `_repo_kwargs`/`is_artel` — `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:200-229`, `:165-198` | да (форма `head_sha`, `gh pr` не меняется) | те же тесты + AC-1 | остаётся |
| адресация `check_runs` в `branch_status` | инвариант 19 (неизвестный CI не зелёный) — `tests/test_invariants.py:320-330` | да | тот же тест (без правки, требование 2) | остаётся |
| `_inherited_from_main` у внешнего | вершина main артели — `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203` | да (артель не меняется) | тот же тест + AC-9 | остаётся |
| текст flake-rate `_ci_confirm_red_or_flake` | «подтверждённый красный» при запущенном повторе — `tests/test_merge_gate_ci_wait.py:154-163`; без flake-rate для не-красного — `tests/test_ci_status_kind_gate.py:99-140` | да | те же тесты + AC-11 | остаётся |
| `ci_rerun` вершина главной ветки | сверка флейка с main — `tests/test_ci_rerun_command.py:236-258` | да | тот же тест + AC-10 | остаётся |
| `trigger_rerun` поиск прогона | выбор упавшего прогона — `tests/test_ci_status.py:787-850`, `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py:570-610` | да | те же тесты + AC-6 | остаётся |

Раздел «Меняемое поведение» в SPEC отсутствует и не нужен: утверждений,
литерал «было» которых меняется, на main нет (сверено выше).

## Пути обхода гейтов
- П-1 (= К-1). Требование 7 исполняется буквально для красного повторного
  статуса, а при незапущенном повторе и зелёном статусе (`fsm_merge_gate.py:297-302`)
  остаётся запись «флейк: первый статус красный, ре-ран зелёный» — ложный флейк
  в метрике flake-rate, AC-11 это пропускает.
- Прочие очевидные обходы закрыты критериями: признак «не клон артели» ловит
  AC-1 (`repo=config.ROOT`); сохранение `--repo` рядом с `GH_REPO` ловит «в argv
  нет `--repo`» AC-2/AC-8; передача репозитория только в `verifying_status` без
  `_inherited_from_main`/`find_run_id`/`check_run_workflow_run` ловят сценарии
  AC-2; локальная ветка вместо `origin/<base>` — AC-9.

## Вердикт
concerns — отклонения есть, все решаемы Оператором на гейте; SPEC можно вести
дальше.

- К-1 (проверяемость, обход). AC-11 не ловит незапущенный повтор с зелёным
  повторным статусом: требование 7 велит писать «повтор не запущен», но ветка
  `if rerun_green:` (`orchestrator/fsm_merge_gate.py:297-302`) может остаться
  прежней («флейк: … ре-ран зелёный»), и критерий пройдёт. Предложение:
  дополнить AC-11 сценарием «повтор не запущен + `branch_status` зелёный» —
  запись flake-rate «повтор не запущен» с причиной, без «флейк».
- К-2 (проверяемость/интерфейс). SPEC не задаёт, в каком виде репозиторий
  проекта доходит до `check_runs`, `failed_check_names`, `find_run_id`,
  `check_run_workflow_run`, `trigger_rerun` (имя и тип параметра: путь клона, как
  у `head_sha`/`verifying_status` `ci.py:98`, `:600`, или URL, как у `gh`/
  `check_runs_page`/`run_list` `ci.py:39`, `:118`, `:198` — `repo` в модуле уже
  значит и то и другое). AC-6 описан как прямой вызов `trigger_rerun` внешней
  задачи: автор тестов угадывает сигнатуру → риск эскалации
  `тест-навязывает-устройство` в `in_dev`. Предложение: назвать форму
  (например, `repo=<путь клона>` — как у `verifying_status`) либо проверять
  AC-6 только через `ci-rerun`/гейт мержа.
- К-3 (полнота правила). «`GH_REPO` — два последних сегмента пути адреса»
  (требование 1) не определено для scp-адреса `git@github.com:<владелец>/<имя>.git`:
  разбиение по `/` даёт `git@github.com:<владелец>/<имя>`. Поле `url`
  (`orchestrator/targets.py:27`) — свободный текст; сейчас в `targets.yaml:26,
  :70` только https. Низкая важность; ответ Оператора — либо «только https»,
  либо правило для scp-формы.

Замечания без отклонения: перечень подмен требования 2 не исчерпывающий
(названы ещё `tests/test_ci_status.py:793`, `:846`, `tests/test_merge_gate_ci_wait.py:78`,
`tests/test_ci_rerun_command.py:254`), но правило AC-1 «ни одна подмена не
правится» их покрывает. Признак внешнего по записи `targets.yaml` (решение
Оператора №2 (2)) — второй признак рядом с `repo_context.is_artel`
(`repo_context.py:154-158`, «единственный признак»); как они сочетаются при
подмене `is_artel` (`tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:226`),
SPEC не говорит; текущие тесты это не ломает.
