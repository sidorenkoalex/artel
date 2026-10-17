---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py, tests/test_ci_rerun_command.py, tests/test_ci_status.py, tests/test_ci_stuck_check_run.py, tests/test_invariants.py, tests/test_main_ci_fetched_repo.py, tests/test_main_ci_line.py, tests/test_merge_gate_ci_wait.py; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/fsm_advance.py, orchestrator/fsm_autogate.py, orchestrator/fsm_merge_gate.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: 3b934ecac5e3318eb4bd4852d90de94f0d1931ae
schema_version: 5
---

# SPEC-AUDIT: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## ТЗ и SPEC
ТЗ → SPEC: требования ТЗ 1–4 и три критерия ТЗ перенесены (SPEC требования
1–3, 6, 8; AC-1, AC-2/AC-3, AC-4). Зоны и «Только чтение» ТЗ перенесены
дословно (SPEC frontmatter `zones`, «Не входит»). «Не входит» ТЗ перенесено.

Решения Оператора на гейте SPEC:
- №1 (1)–(5): требование 2 (прежняя форма, `_repo_kwargs`, перечень подмен),
  AC-1 (`accepted_full_suite`), требование 1 / AC-8 (GH_REPO без
  `token_slot`), требование 1 / AC-2 (снятие `/` и `.git`), AC-2/AC-3
  (сценарии) — перенесены.
- №2 (1)–(6): требование 2 и AC-1 на все функции и вызывающих; признак
  проекта по записи `targets.yaml`, `main_line_status(repo=config.ROOT)` —
  артель (требование 2, AC-1); сценарий `main_line_status` в AC-2;
  `ci_rerun.py:272` → требование 5 / AC-10; `_inherited_from_main` →
  требование 4 / AC-9; `flake-rate` → требование 7 / AC-11 — перенесены.
- №3 К-1..К-4: AC-11 со сценарием «не запущен + зелёный»; сигнатуры
  `repo=<путь клона>` (требование 3); https и scp, иной вид — именованный
  отказ (требование 1, AC-12); признак через `repo_context`, `is_artel` —
  единственный признак артели (требование 1) — перенесены. Критерия на К-4
  нет — см. «Проверяемость», Н-1.

SPEC → ТЗ: требований вне ТЗ и решений Оператора нет (требование 7 —
решение №2 (6), требования 4–5 — №2 (4)–(5)).

## Факты против кода
Подтвердилось (рабочий каталог = main):
- `ci.gh` `ci.py:39-80`, `--repo` в конец argv `:63`, `cwd=config.ROOT`
  `:73`, отказ токена `:66-69`; `_repo_kwargs` `:83-95`; `head_sha` `:98`;
  `check_runs_page` `:118` (repo как `--repo`, `:127-129`); `check_runs`
  `:143` без repo; `run_list` `:198`; `_commit_workflow_runs` `:371`, gh api
  `:383`; `_inherited_from_main` `:474-488` (`head_sha("main", …)` `:478`,
  `failed_check_names(main_sha)` `:481`); `verifying_status` `:600`,
  `_no_checks_by_branch` `:674`/`run_list(branch)` `:678`;
  `failed_check_names` `:732`; `branch_status` `:767`; `accepted_full_suite`
  `:823`, отказ внешнему до gh `:829`; `_main_line_runs` `:974`;
  `main_line_status` `:1029`; `find_run_id` `:1136`, gh `:1162`,
  `check_runs` `:1180-1181`; `check_run_workflow_run` `:1211`/`:1221`;
  `trigger_rerun` `:1235`, `head_sha(branch)` без клона `:1256`, тексты «не
  запущен» `:1258`, `:1261`, `:1265`; `rerun_started` `:1274-1289`.
- Вызывающие: `ci_rerun.py:123, :158, :224, :232, :244, :267, :272, :279,
  :298`; `fsm_merge_gate.py:290, :293, :341, :571, :579, :614, :618`,
  `_ci_confirm_red_or_flake` `:281-309`; `acceptance.py:2069, :2087,
  :2184`; `github_adapter.py:168, :193, :306`; `fsm_advance.py:453`;
  `fsm_autogate.py:287`; `pin.py:86`; `doctor/main_ci.py:33`. `git grep`
  по `orchestrator/` и `scripts/` других вызовов функций перечня не
  нашёл — перечень требования 3 полон.
- `fsm._origin_main_sha(target_name, *, repo=None)` `fsm.py:166`; образец
  `fsm.py:264`. `repo_context.is_artel` `repo_context.py:154`,
  `clone_path` `:75`, `resolve` `:82`. `gitcmd.url_key` `gitcmd.py:44-46`,
  `project_by_url` `:71-81`, нет `token_slot` → `(None, None)` `:133-135`.
  `targets.yaml:70` — sled `https://github.com/sledproject/sled`.
- `workspace.task_repo(id)` = `repo_context.clone_path(target)`
  (`workspace.py`, `task_repo`/`repo`) — сопоставление «путь клона → запись»
  требования 1 работает для всех вызывающих, передающих `task_repo`.
- Подмены в `tests/`, перечисленные в требовании 2, все на указанных
  строках и указанной формы.
- «Тестов, утверждающих `--repo` у `gh api`, нет» — верно: единственное
  утверждение `--repo` — `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:191-198`
  о `gh pr ready` (`github_adapter.undraft_mr`), его поведение не
  меняется. «Подтверждённый красный» держит
  `tests/test_merge_gate_ci_wait.py:163` при запущенном повторе («ре-ран
  (тест)», `:82`) — сохраняется AC-11.

Замечание (не отклонение): `_repo_kwargs(config.ROOT)` возвращает
`{"repo": ROOT}` — `is_artel(путь)` истинен только для клона артели
(`repo_context.py:170-171`). Требование 2 (SPEC.md:75) приводит его как
образец «прежней формы», но для `check_runs` под
`main_line_status(repo=config.ROOT)` прямое переиспользование дало бы
`check_runs(sha, repo=ROOT)` и сломало подмену
`tests/test_main_ci_fetched_repo.py:64` — это ловит AC-1, поэтому не
отклонение.

Замечание (не отклонение): `refs/remotes/origin/<base>` клона (требование 4)
двигают только подтяжка, вход в `verifying` и `git push`
(`github_adapter.py:33-39`); выбор источника вершины — решение Оператора №2 (5).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `GH_REPO`/`--repo`/`GH_TOKEN` у вызова артели; новый kwarg `repo=` у артели (ломает подмены `lambda sha:` и т. п.); `config.ROOT` признан внешним |
| AC-2 | да | `gh api` без `GH_REPO` или с `--repo`; `.git`/`/` в `GH_REPO`; scp не разобран; пропуск repo в `_inherited_from_main`→`failed_check_names`, `_commit_workflow_runs`, `find_run_id`, `check_run_workflow_run`, `_main_line_runs`. Не ловит порчу голого https-адреса — Н-2 |
| AC-3 | да | `gh run list/rerun/watch` без `--repo`; `_no_checks_by_branch` зовёт `run_list(branch)` без адреса |
| AC-4 | да | `check_runs` без репозитория проекта (исход «голова ветки не в origin» на 422) |
| AC-5 | да | то же для `branch_status` |
| AC-6 | да | `trigger_rerun` читает голову в клоне артели; `find_run_id`/`gh run` без адресации |
| AC-7 | да | `ci_rerun.py:224/:232/:267/:279/:298`, `fsm_merge_gate.py:290` не передают клон |
| AC-8 | да | `GH_REPO` ставится только при наличии токена; пульт выставляет `GH_TOKEN` пустым |
| AC-9 | да | вершина из `refs/heads/main`/`<base>` или литерал `main` вместо `origin/<base>` |
| AC-10 | да | `_origin_main_sha` без `repo=` у внешней задачи; `repo=` у артели |
| AC-11 | да | «подтверждённый красный»/«флейк» при незапущенном повторе; потеря «подтверждённый красный» при запущенном |
| AC-12 | частично | `gh` запускается на `ssh://`/односегментном адресе — ловит; текст отказа без причины «вид адреса не разобран» (SPEC.md:48-49) — не ловит, Н-3 |
| К-4 (требование 1, SPEC.md:56-67) | нет критерия | параллельный признак «найдена запись с именем ≠ `config.DEFAULT_TARGET`» вместо `repo_context.is_artel` — Н-1 |

## Зоны
Зоны SPEC (`orchestrator/ci.py`, `ci_rerun.py`, `acceptance.py`,
`fsm_merge_gate.py`, `github_adapter.py`, `tests/`) = зоны ТЗ и покрывают все
места правки требований 1–8: `ci.py` (адресация, сигнатуры, разбор адреса,
сопоставление путь→запись), `ci_rerun.py` (передача, требование 5),
`fsm_merge_gate.py` (передача в `:290`, текст требования 7). `fsm.py`,
`fsm_advance.py`, `fsm_autogate.py`, `repo_context.py`, `gitcmd.py`,
`targets.py` правки не требуют (проверено: параметры уже есть, клон уже
передаётся). Защищённый `tests/test_invariants.py` — только чтение (подмена
`:326-328` обязана работать без правки, требование 2); защищённых путей
задача не меняет, песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `ci.check_runs`/`branch_status` и др. — новый параметр `repo` | Инвариант 19, merge только на зелёном CI — `tests/test_invariants.py:671` (`MergeNeedsGreenCiTest`, подмены `:326-328`) | да | тот же тест без правки (требование 2, AC-1) | остаётся |
| `ci.gh` — `GH_REPO` вместо `--repo` у `gh api` внешнего проекта | Артель без `--repo` / внешний `gh pr` с `repo=` — `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:165-198` | да (`gh pr` не меняется) | тот же тест; AC-1, AC-3 | остаётся |
| Внутренние вызовы с `repo=` | Прежняя форма для клона артели — `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:200-229`; подмены `tests/test_ci_status.py:160,367,372,798`, `test_main_ci_line.py:62`, `test_main_ci_fetched_repo.py:64`, `test_ci_stuck_check_run.py:220`, `test_ci_rerun_command.py:238,242,254` | да | те же тесты без правки (AC-1) | остаётся |
| `_inherited_from_main` у внешнего проекта | Вершина `head_sha("main")` артели — `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203` | да (у артели путь прежний) | тот же тест; AC-9 | остаётся |
| Записи `flake-rate` в `_ci_confirm_red_or_flake` | «подтверждённый красный» при запущенном повторе — `tests/test_merge_gate_ci_wait.py:163` | да | тот же тест; AC-11 | остаётся |
| Признак внешнего проекта для `gh api` | Единственный признак артели `repo_context.is_artel` — для нового пути не держит ничего | — | не покрыто (Н-1) | на гейт |

Раздел «Меняемое поведение» в SPEC отсутствует; утверждений, меняющих
ожидание на main, не нашлось (см. «Факты») — отсутствие обосновано.

## Пути обхода гейтов
- П-1 (Н-1): исполнитель узнаёт внешний проект как «найдена запись
  `targets.yaml`, клон которой = путь, и имя ≠ `config.DEFAULT_TARGET`» —
  буквально «сопоставление через `repo_context.clone_path`», но признак
  артели фактически дублирован сравнением имени, вопреки К-4. Все AC-1..12
  проходят: ни один не подменяет `repo_context.is_artel`, как это делают
  строки 18/19 `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:165-229`.
- П-2 (Н-4): `targets.yaml` не читается (или запись проекта сломана) —
  по SPEC.md:65-67 путь клона «не является клоном ни одной записи» и вызов
  идёт как вызов артели: `gh api` снова спрашивает репозиторий артели о
  коммите проекта (исходный дефект ТЗ, 422 → «голова ветки не в origin»).
  Инвариант 19 не нарушается (неизвестное не зелёное), но это молчаливый
  откат, против которого прямо предупреждает `repo_context.py:29-31`;
  гейт не ослабляется, поведение — вопрос Оператору.

## Вердикт
concerns. Решения Оператора №1–№3 перенесены полностью, факты о коде
сверены и верны, перечень функций и вызывающих полон. Отклонения
(решаемы на гейте, без возврата аналитику):

- Н-1. Решение К-4 (SPEC.md:56-67, «Признак артели — только
  `repo_context.is_artel`») без критерия: нет AC, где `is_artel` подменён
  и `gh api` клона внешнего проекта идёт как у артели (образец —
  `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py:165-229`).
  Мутация «параллельный признак по имени записи» проходит AC-1..12.
  Предложение: AC — под подменой `repo_context.is_artel`, признающей проект
  артелью, `check_runs(sha, repo=<клон проекта>)` зовёт `gh` без `GH_REPO`,
  `--repo` и `GH_TOKEN`.
- Н-2. AC-2 (SPEC.md:211-215) требует учебный `url` с `.git`/`/` и scp с
  `.git`; голый https-адрес (`https://github.com/<владелец>/<имя>` — так
  записан sled, `targets.yaml:70`, SPEC.md:346) и scp без `.git` явно не
  проверяются. Мутация, ломающая разбор именно голого адреса (например,
  обязательное снятие суффикса), проходит AC-2. Предложение: в AC-2 —
  и голый https-адрес.
- Н-3. AC-12 (SPEC.md:284-289) проверяет только адрес в тексте отказа, не
  причину «вид адреса не разобран» требования 1 (SPEC.md:48-49); кроме того
  требование 1 не уточняет, распространяется ли отказ на `gh run`/`gh pr`
  (`--repo <url>` разбора владельца не требует; `ci.gh("pr", …, repo=url)`
  из `github_adapter.py:168, :193, :306` с `ssh://`-адресом сейчас
  работает). Предложение: отказ — только для `gh api`; AC-12 — и причина.
- Н-4. SPEC.md:65-67: при нечитаемом `targets.yaml` или сломанной записи
  клон внешнего проекта (`.artel/projects/<имя>/repo`) молча считается
  артелью — возврат исходного дефекта без сигнала (`repo_context.py:29-31`
  требует сигнал «конфигурация не читается»). Предложение: для пути под
  областью внешнего проекта без разрешённой записи — именованный отказ
  вызова (тем же каналом, что отказ вида адреса), AC на это.
