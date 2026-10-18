---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Подход
Адресация `gh` решается внутри `orchestrator/ci.py` одним узлом, вызывающие
лишь передают клон проекта параметром `repo` (К-2).

- `ci.gh(repo=<url>)`: для `gh api` — `GH_REPO=<владелец>/<имя>` в
  окружении вызова, без `--repo`; для `gh run`/`gh pr` — `--repo <url>`, как
  было. Окружение собирается, если есть хоть одна переменная (`GH_REPO` и/или
  `GH_TOKEN`) — поэтому запись без `token_slot` тоже получает `GH_REPO`.
  Разбор `_owner_and_name`: https `https://<хост>/<o>/<n>[.git][/]` и scp
  `git@<хост>:<o>/<n>[.git]`; иной вид — отказ вызова `gh api` (ненулевой
  код, текст называет адрес и «вид адреса не разобран»), `gh` не запускается
  (Н-3: отказ только для `gh api`).
- `_project_context(repo)` — (контекст проекта, отказ) по пути клона:
  `None` или путь, который `repo_context.is_artel` зовёт артелью, — артель;
  путь в области `repo_context.projects_root()/<имя>/…`, имя которого не
  артель, — `repo_context.resolve(<имя>)`; не разрешён — отказ (Н-4); прочие
  пути (главная копия `config.ROOT`) — артель. Нового признака артели нет:
  оба решения «артель ли» — `repo_context.is_artel`.
- `_project_kwargs(repo)` — `{"repo": repo}` только для пути внешнего
  проекта, иначе `{}`: внутренние вызовы у артели идут прежней формой (без
  `repo`), подмены `lambda sha:` в `tests/` работают без правки. В отличие
  от `_repo_kwargs`, `config.ROOT` здесь — артель (`main_line_status(…,
  repo=config.ROOT)` из `pin.py`/`doctor/main_ci.py`).
- `_gh_at(repo, *args)` — `gh` с `repo=ctx.remote` у проекта, прежний
  `gh(*args)` у артели, отказ — ненулевой код без запуска.
- Сигнатуры требования 3: `check_runs`, `failed_check_names`, `find_run_id`,
  `check_run_workflow_run`, `trigger_rerun` получили `repo: Path | None =
  None`; закрытые `_commit_workflow_runs`, `_no_checks_by_branch`,
  `_main_line_runs` — тоже.
- `_inherited_from_main` у проекта: вершина `refs/remotes/origin/<base>`
  клона, проверки — у репозитория проекта, фраза «красный унаследован от
  <base> <sha>»; у артели — прежние `head_sha("main")` и литерал `main`.
- `ci_rerun.py`: `ci._repo_kwargs(workspace.task_repo(task_id))` передаётся
  в `check_run_workflow_run`, `trigger_rerun`, `failed_check_names` и
  `fsm._origin_main_sha` (требование 5); у артели — `{}`, вызов прежний.
- `fsm_merge_gate._ci_confirm_red_or_flake`: `trigger_rerun(branch,
  **ci._repo_kwargs(repo))`; при `not ci.rerun_started(note)` запись
  `flake-rate` — «повтор не запущен: <note>; …» вместо «флейк»/«подтверждённый
  красный»; возврат зелёного и `sys.exit` с прежним текстом — без изменений.
- `acceptance.py`, `github_adapter.py` правки не потребовали.

## Шаги
1. `ci.py`: разбор адреса и `GH_REPO` в `gh`; `_project_context`/
   `_project_kwargs`/`_gh_at`; `repo` у функций перечня; `_inherited_from_main`
   по `origin/<base>`.
2. `ci_rerun.py`, `fsm_merge_gate.py`: передача клона проекта; запись
   `flake-rate` при незапущенном повторе.
3. Юнит-тесты `tests/test_ci_project_gh_address.py` (Н-1..Н-4 ANSWER-1),
   прогон долгоживущего файла задачи, планки, тестов затронутых модулей;
   карта `docs/codebase-map.md`.
4. Фикстуры тестов по ANSWER-2 (вариант а; код задачи не меняется):
   адрес внешнего проекта песочниц — https-вида на localhost
   (`tests/sandbox.py`: `PROJECT_URL = "https://localhost/artel-tests/{name}"`
   в записи `make_project_repo`; инвариант 35 — только localhost), git
   песочницы ходит в bare прежним механизмом: `origin` клона
   `make_project_repo` — путь bare, как было; для клона по `url` — помощник
   `route_url_to_bare` (`url.<bare>.insteadOf <url>` через
   `GIT_CONFIG_COUNT/KEY/VALUE` окружения теста, без сети). Места:
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::add_external_project`
   (`url` — `PROJECT_URL` + `route_url_to_bare`),
   `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py::FetchAllClonesTest`
   (подменял буквальную заглушку `file:///nonexistent/<имя>` записи
   `make_project_repo` на путь bare — теперь подменяет `PROJECT_URL`).
   `ExternalMergeTest` 01M4M67… правки не потребовал — его чинит
   `make_project_repo`. Утверждения и докстринги тестов не тронуты.
5. Ревью, итерация 1 (R1-F1): сторожа вызывающих в `tests/` —
   `tests/test_ci_callers_project_repo.py` (новый файл разработчика):
   `FlakeRateNotStartedTest` — запись `flake-rate` при незапущенном повторе
   (красный и зелёный исход, обе формы отказа) и прежние записи при
   запущенном; `MergeGateRerunRepoTest` — `_ci_confirm_red_or_flake` зовёт
   `trigger_rerun(branch, repo=<клон>)` у проекта и без `repo` у артели;
   `CiRerunRepoTest` — `_red_rerun` (`failed_check_names` ×2,
   `fsm._origin_main_sha`, `trigger_rerun`) и `_stuck_rerun`
   (`check_run_workflow_run` каждой проверки, `trigger_rerun(…, run_id=…)`)
   передают `repo=<клон>` у проекта и не передают `repo` у артели.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 3 (Н-2, Н-3, Н-4; AC-2, AC-8, AC-12 — долгоживущий файл) |
| 2 | 1, 2 (AC-1: долгоживущий файл и планка; Н-1) |
| 3 | 1, 2, 5 (сторож передачи клона из вызывающих, AC-7) |
| 4 | 1 (AC-9) |
| 5 | 2, 5 (AC-10; сторож — `CiRerunRepoTest`) |
| 6 | долгоживущий файл задачи `tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py` (AC-1, написан test_author до правки) |
| 7 | 2, 5 (AC-11; сторож — `FlakeRateNotStartedTest`) |
| 8 | 3 |
| ANSWER-2 (фикстуры) | 4 |

## Влияние на систему
- Инвариант 19 (неизвестный статус CI не зелёный): отказ разбора адреса и
  неразрешённый проект возвращаются как «gh не ответил»/«статуса нет» —
  не зелёный исход; новых путей к зелёному нет.
- Поведение артели: argv, `cwd` и окружение `gh` не меняются — окружение
  передаётся только при `GH_REPO`/`GH_TOKEN`, а они у артели не ставятся;
  внутренние вызовы у артели — прежняя форма. Подтверждено AC-1
  долгоживущего файла и планки, существующие тесты модулей
  (`test_ci_status`, `test_invariants`, `test_main_ci_line`,
  `test_merge_gate_ci_wait`, `test_ci_rerun_command`,
  `test_ci_stuck_check_run`, `test_main_ci_fetched_repo`,
  `test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict`,
  `test_01m484rnv3qbdy3b0m16j916zp_artel_predicate`) зелёные без правки.
- Логика гейтов не меняется; меняется только текст записи `flake-rate` при
  незапущенном повторе (требование 7).
- Тесты: добавлен один файл; по мандату ANSWER-2 правлены только данные
  фикстур (адрес проекта песочниц) в `tests/sandbox.py` и двух файлах —
  ни одно утверждение не удалено и не ослаблено.
- Прогоны: тесты затронутых модулей (10 файлов, 164 теста) и планка (4)
  зелёные. `suite-run` №1 оборван пределом 1500 с при load average ~80:
  3000 прошло, 67 «упавших» — без сообщения pytest, по одному в 67
  несвязанных файлах (недобежавшие при обрыве); на базе прогон тот же.
  Связанные с правкой файлы из этого списка прогнаны по именам отдельно:
  три красных одного класса (адрес `file://`/локальный путь в записи
  проекта песочницы) — эскалация, ответ ANSWER-2 (вариант а).
- После правки фикстур: `suite-run` №2 — 5718 прошло, 1 новый красный
  (`test_01m484rnv3qbdy3b0m16j916zp_artel_docs_ref.py::FetchAllClonesTest`,
  тот же класс — подмена буквальной заглушки), исправлен; `suite-run` №3
  (повтор упавших) — зелёный. Планка 4/4, файлы 01M42…/01M4M67…/файлы
  задачи — 59 зелёных; `test_invariants` сеть (инвариант 35) — зелёный.
- Итерация 2 (R1-F1): код не менялся, добавлен один файл тестов
  `tests/test_ci_callers_project_repo.py` (5 тестов, 12 подтестов).
  Временной мутацией проверено: каждая из восьми мутаций — `if not
  ci.rerun_started(...)` → `if False`, снятие клона у `trigger_rerun`
  гейта мержа, у `fsm._origin_main_sha`, у обоих `failed_check_names`, у
  `trigger_rerun` красного пути, у `check_run_workflow_run` и у
  `trigger_rerun(…, run_id=…)` в `ci_rerun.py` — красит файл; код
  восстановлен. Файлы затронутых модулей (7 файлов) — 141 зелёный; карта
  регенерирована.
- Откат — revert коммита задачи.

## Риски
- Путь в области проекта, но не сам клон (рабочая копия
  `.artel/projects/<имя>/worktrees/<id>`) тоже считается проектом `<имя>` —
  вызывающие сейчас передают клон (`workspace.task_repo`), так что на путях
  задачи это не проявляется; иное толкование было бы вызовом артели к
  чужому репозиторию.
- Тексты отказов обрезаются вызывающими до 200 знаков (`check_runs_page`):
  адрес/имя проекта стоят в начале текста, путь — в конце.

## Предложения системе
- `rm`/`ls` недоступны в Bash шага (command not found) — уборку временного
  файла пришлось делать `python3 -c "os.remove(...)"`; стоит назвать это в
  скиле или вернуть утилиты.
- `suite-run`: оборванный пределом прогон помечает недобежавшие тесты
  «новыми упавшими» (признак неизвестен) — стоит выделить их отдельной
  строкой «не добежали», чтобы не путать с регрессией ветки.
