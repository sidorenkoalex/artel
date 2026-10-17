---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/test_ci_status.py, tests/test_invariants.py, tests/test_main_ci_line.py, tests/test_merge_gate_ci_wait.py; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: 05cad0f2d7e02ffce76c8aa6d90daf565e53d413
schema_version: 5
---

# SPEC-AUDIT: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## ТЗ и SPEC
Сверка ТЗ → SPEC:
- ТЗ «Требуется» 1 → SPEC требование 1 (SPEC.md:28-42): адресация `gh api` через `GH_REPO`, `gh run`/`gh pr` через `--repo`, токен слота. Отражено.
- ТЗ «Требуется» 1, последняя фраза («у артели … ни на байт») → SPEC требование 2 (SPEC.md:43-56). Отражено.
- ТЗ «Требуется» 2 (полный перечень функций и вызывающих) → SPEC требование 3 (SPEC.md:57-110). Отражено, перечень сверен ниже.
- ТЗ «Требуется» 3 (фиксация до правки) → требование 4 (SPEC.md:111-112). ТЗ «Требуется» 4 (подставной `gh`, учебный проект) → требование 5 и AC-4..AC-6. Отражено.
- Критерии ТЗ → AC-1, AC-2/AC-3, AC-4. Зоны, «Только чтение» и «Не входит» перенесены дословно (SPEC.md:6, :196-209).

Решение Оператора на гейте SPEC №1 (пять пунктов):
- (1) прежняя форма вызовов у артели и перечень подмен — SPEC.md:44-56, :215-220. Перенесено, но перечень неполон: см. «Факты против кода», пункт Ф-1.
- (2) `accepted_full_suite` в AC-1 — SPEC.md:122. Есть.
- (3) `GH_REPO` без `token_slot` — SPEC.md:39-42 и AC-8 (SPEC.md:170-173). Есть.
- (4) правило `gitcmd.url_key`, `url` учебного проекта на `.git` или `/` — SPEC.md:33-36, AC-2 (SPEC.md:129-131). Есть.
- (5) сценарии в AC-2/AC-3 — SPEC.md:133-148. Есть.

Требований сверх ТЗ и решения Оператора в SPEC нет.

## Факты против кода
Подтвердилось (в рабочем каталоге, main):
- `ci.gh` — `ci.py:39`; `--repo` дописывается к любому argv (`ci.py:64`), `env` с `GH_TOKEN` ставится только при непустом токене (`ci.py:65-71`), `cwd=config.ROOT` — `ci.py:72` (в SPEC сказано `:73`, а ТЗ называет `:72`; на смысл не влияет).
- `_repo_kwargs` — `ci.py:83-95`; `check_runs_page` — `:118`, передаёт `repo` как kwarg `gh` (`:127-129`); `check_runs` — `:143`, без `repo`, зовёт `check_runs_page(sha, page)` (`:169`); `run_list` — `:198`; `_commit_workflow_runs` — `:371`, `gh api` на `:383`, без запроса при отсутствии связки `:380-382`; `_inherited_from_main` — `:474`, `failed_check_names(main_sha)` без репозитория на `:481`; `verifying_status` — `:600`, вызов `_inherited_from_main` на `:660`; `_no_checks_by_branch` — `:674`, `run_list(branch)` на `:678`; `failed_check_names` — `:732`; `branch_status` — `:767`, `:814`; `accepted_full_suite` — `:823`, ранний отказ для внешнего клона на `:829-830`; `_main_line_runs` — `:974`; `main_line_status` — `:1029`; `find_run_id` — `:1136`, `gh api` на `:1162`, `check_runs` при `len(failed) > 1` на `:1180-1181`; `check_run_workflow_run` — `:1211`, `gh api` на `:1221`; `trigger_rerun` — `:1235`, `head_sha(branch)` без клона на `:1256`, `gh run rerun`/`watch` на `:1254`, `:1262`, `:1267`.
- Вызывающие: `ci_rerun.py:123`, `:158`, `:224`, `:232`, `:244`, `:267`, `:279`, `:298`; `fsm_merge_gate.py:290`, `:293`, `:341`, `:579`, `:618`, ранний выход `is_artel` на `:571`, `:614`; `acceptance.py:2069`, `:2087`, `:2184`; `github_adapter.py:168`, `:193`, `:306`; `fsm_advance.py:453`, `fsm_autogate.py:287`. Других вызовов перечисленных функций `ci` в `orchestrator/` и `scripts/` нет, кроме названных в «Не входит» (`pin.py:86`, `doctor/main_ci.py:33`). `advance_gates/` функций `ci` не зовёт. Совпадает.
- Утверждение «тестов, утверждающих `--repo` у `gh api`, нет» (SPEC.md:223-224) верно: `--repo` упоминается только в `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:166-198`, и там речь о `gh pr ready` (`undraft_mr`), который требование 1 не меняет.

Не подтвердилось / неполно:
- **Ф-1. Перечень функций с прежней формой вызова и перечень подмен в требовании 2 неполны.** Требование 2 (SPEC.md:44-56) закрепляет прежнюю форму только для `ci.gh`, `head_sha`, `check_runs`, `run_list`, `find_run_id`, `trigger_rerun`, а AC-1 (SPEC.md:124-127) проверяет только закрытый перечень подмен. При этом на main есть подмены, написанные под прежнюю форму, которых нет в перечне:
  - `tests/test_ci_rerun_command.py:242` — `failed_check_names` как `failed_names(sha)`, `:238` — `trigger_rerun` как `trigger(branch)`. Задача там — артель, путь `_red_rerun` (`ci_rerun.py:267`, `:279`, `:298`);
  - `tests/test_ci_stuck_check_run.py:219-220` — `check_run_workflow_run` как `lambda cid:` (`ci_rerun.py:224`);
  - `tests/test_main_ci_fetched_repo.py:63-64` — `check_runs` как `lambda sha:` под `main_line_status(…, repo=config.ROOT)` из `pin`/`doctor` (см. Ф-2);
  - функции того же вида, что уже в перечне: `tests/test_ci_status.py:35`, `:134`, `:457`, `:489`, `:511`, `:521`, `:533`, `:550`, `:553`, `:658-659`, `:794`, `:830`. Правило «прежней формой» на уровне функции их покрывает, но закрытый список AC-1 — нет.

  `failed_check_names` и `check_run_workflow_run` в правило «прежней формой» не входят. Разработчик, который в `ci_rerun.py` всегда передаёт `repo=` (например, `repo=workspace.task_repo(task_id)` для любой задачи), сломает эти подмены. Требование 2 и AC-1 при этом формально выполнены.
- **Ф-2. Приём `_repo_kwargs`, на который SPEC ссылается как на механизм различения «артель или нет», не отличает главную копию пульта от клона внешнего проекта.** `_repo_kwargs(config.ROOT)` возвращает `{"repo": config.ROOT}`: `is_artel` для пути сравнивает его с `clone_path(DEFAULT_TARGET)` (`repo_context.py:170-171`), а `pin.py:86` и `doctor/main_ci.py:33` зовут `main_line_status(sha, repo=config.ROOT)`. Если разработчик отправит `gh` в репозиторий проекта по признаку «`_repo_kwargs` не пуст», то вызовы `check_runs`/`_commit_workflow_runs` из `main_line_status` у артели (pin-update, `doctor main-ci`) пойдут в новой форме: `check_runs(commit, repo=…)`, возможно с `GH_REPO`. Это ломает `tests/test_main_ci_fetched_repo.py:64` и меняет argv/окружение вызовов артели. SPEC выводит вызывающих `pin.py`/`doctor` из зоны (SPEC.md:206-207), но не говорит, что `main_line_status(repo=config.ROOT)` — случай артели, у которого `gh` не меняется. AC-1 этот случай не называет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, но закрытым перечнем | В `gh` артели появился `GH_REPO` или `env=`; `cwd` ≠ `config.ROOT`; внутренний вызов артели получил kwarg `repo=None` (ломает подмену `lambda sha:`). **Не ловит** (Ф-1, Ф-2): `ci_rerun` всегда передаёт `repo=` в `failed_check_names`/`check_run_workflow_run`; `main_line_status(repo=config.ROOT)` уходит в новую форму — этих подмен нет в перечне AC-1 |
| AC-2 | да | `check_runs_page` оставил `--repo` у `gh api`; `_inherited_from_main` не передал репозиторий в `failed_check_names(main_sha)`; `_commit_workflow_runs`/`find_run_id`/`check_run_workflow_run` без `GH_REPO`; `GH_REPO` взят из `url` без снятия `.git`/`/`. Слабее для `main_line_status`/`_main_line_runs`: их сценария в списке AC-2 (SPEC.md:133-143) нет, а оба вызывающих в проде рано выходят для внешнего проекта (`fsm_merge_gate.py:571`, `:614`) |
| AC-3 | да | `run_list` из `_no_checks_by_branch` без `--repo`; `gh run rerun`/`watch` без `--repo`; без `GH_TOKEN` |
| AC-4 | да | `verifying_status` не передал репозиторий в `check_runs` — подставной `gh` без `GH_REPO` отвечает 422, исход «голова ветки не в origin» |
| AC-5 | да | `branch_status` не передал репозиторий в `check_runs` |
| AC-6 | да | `trigger_rerun` читает голову в клоне артели (`ci.py:1256`); `find_run_id` без `GH_REPO`; `rerun`/`watch` без `--repo` |
| AC-7 | да | `ci_rerun.py:224`/`:267`/`:279`/`:232`/`:298` или `fsm_merge_gate.py:290` не передают репозиторий проекта |
| AC-8 | да | `GH_REPO` ставится только вместе с токеном (как сейчас `env` на `ci.py:69-71`); при отсутствии токена `GH_TOKEN` всё же выставлен пультом |

## Зоны
Зоны SPEC (`ci.py`, `ci_rerun.py`, `acceptance.py`, `fsm_merge_gate.py`, `github_adapter.py`, `tests/`) покрывают все места правки по перечню требования 3. `fsm_advance.py:453`, `fsm_autogate.py:287` и `acceptance.py` уже передают клон. Отображение «клон → `url`/слот» читает `targets.py`/`gitcmd.py`/`repo_context.py`, импорт без правки допустим. Защищённый `tests/test_invariants.py` меняться не должен, его подмены (`:326-328`) закреплены требованием 2. Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) требования не касаются. Песочница ролей не расширяется. Отклонений нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `ci.gh` для `gh api` внешнего проекта: `--repo` → `GH_REPO` | Токен слота внешнего проекта в `GH_TOKEN` (`ci.py:65-71`; `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`) | да | AC-2, AC-8; существующий тест токена | ок |
| Внутренние вызовы `ci` у артели | Прежняя форма вызова — подмены `tests/test_invariants.py:326-328` (инвариант 19), `test_ci_status.py`, `test_main_ci_line.py:62`, `test_merge_gate_ci_wait.py:82` | да | AC-1 + требование 4 | ок |
| То же, подмены вне перечня | `tests/test_ci_rerun_command.py:238`, `:242`; `tests/test_ci_stuck_check_run.py:220`; `tests/test_main_ci_fetched_repo.py:64` | да, если разработчик не поменяет форму вызова | не покрыто закрытым перечнем AC-1 (Ф-1, Ф-2); ловит только полный прогон, а «починка» подмены правкой теста выглядит как не-ослабление | concerns |
| `main_line_status` у `pin`/`doctor` (`repo=config.ROOT`) | Красный main под документной головой виден (`tests/test_main_ci_fetched_repo.py:68-86`) | да при верной реализации | не названо в SPEC (Ф-2) | concerns |
| `gh pr` из `github_adapter` | `--repo` у внешнего проекта, нет `--repo` у артели (`tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:165-198`) | да | не меняется | ок |
| Инвариант 19 (неизвестное не зелёное) в `check_runs`/`failed_check_names`/`main_line_status` | `tests/test_invariants.py:326-328`, `tests/test_ci_status.py` | да, логика не меняется | существующие тесты | ок |

Раздела «Меняемое поведение» в SPEC нет, обоснование (SPEC.md:223-224) верно: утверждений о `--repo` у `gh api` в `tests/` нет.

## Пути обхода гейтов
- **О-1 (из Ф-1).** Разработчик всегда передаёт `repo=` из `ci_rerun.py` в `failed_check_names`/`check_run_workflow_run`/`trigger_rerun` и «чинит» сломанные подмены `tests/test_ci_rerun_command.py:238,242` и `tests/test_ci_stuck_check_run.py:220`, дописав в лямбды `repo=None`/`**kw`. Утверждения тестов при этом не меняются, и гейт неослабления такую правку может не увидеть. AC-1 выполнен, потому что этих подмен в перечне нет. Итог: форма вызова у артели меняется, хотя требование 2 по смыслу это запрещает.
- **О-2 (из Ф-2).** Различение «внешний или артель» по `_repo_kwargs` (как называет SPEC) переводит `main_line_status(repo=config.ROOT)` у `pin`/`doctor` в новую форму. AC-1 проверяет `main_line_status` только для клона артели или `None`, так что регресс артели в pin-update/`doctor main-ci` проходит AC-1. Его поймает лишь `tests/test_main_ci_fetched_repo.py:64` — а это опять «починка» подмены.
- **О-3.** Сценарии AC-2 не доходят до `main_line_status`/`_main_line_runs` с внешним клоном. Невыполненное требование 3 для них («репозиторий доходит до всех функций») AC не ловит. В проде путь закрыт ранним выходом (`fsm_merge_gate.py:571`, `:614`), поэтому это мелочь.

## Вердикт
**concerns.** SPEC выполняет ТЗ и все пять пунктов решения Оператора №1. Факты о коде подтверждены, расхождение в номере строки одно (`ci.py:73` вместо `:72`) и на смысл не влияет. Возврат аналитику не нужен: все отклонения Оператор может снять на гейте одной фразой.

1. **Ф-1 / О-1.** Правило «прежней формой» (SPEC.md:44-48) не называет `failed_check_names` и `check_run_workflow_run`. В закрытом перечне подмен (SPEC.md:48-56, :124-127, :215-220) нет `tests/test_ci_rerun_command.py:238`, `:242`, `tests/test_ci_stuck_check_run.py:219-220`, `tests/test_main_ci_fetched_repo.py:63-64`. Предложение: распространить требование 2 на все функции перечня требования 3 и на всех вызывающих из `ci_rerun.py`/`fsm_merge_gate.py`, а AC-1 записать как «ни одна существующая подмена в `tests/` не правится».
2. **Ф-2 / О-2.** Не определено, по какому признаку `ci.py` отличает внешний проект от артели. Названный приём `ci._repo_kwargs` (SPEC.md:47, `ci.py:83-95`) считает главную копию `config.ROOT` не артелью (`repo_context.py:170-171`), а её передают `pin.py:86` и `doctor/main_ci.py:33`. Предложение: в требовании 2 и AC-1 явно — `main_line_status(…, repo=config.ROOT)` (pin-update, `doctor main-ci`) остаётся вызовом артели без изменения `gh`, а внешний проект узнаётся по записи `targets.yaml` клона, не по «не клон артели».
3. **О-3 (мелочь).** В AC-2 (SPEC.md:133-143) нет сценария `main_line_status` с клоном внешнего проекта, хотя требование 3 (SPEC.md:80-81) требует довести до неё репозиторий.
