---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/ci.py, orchestrator/ci_rerun.py, orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/github_adapter.py, tests/
budget_usd: 35
---

# SPEC: CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Контекст
Первая задача на sled (01M55SKHZ293CCAK0N7T4H7ZMR) стоит в `verifying`:
ветка и коммит 9495860f есть в `origin` sled (PR sledproject/sled#17, CI
sled идёт), а пульт трижды пишет «голова ветки не в origin — GitHub не
нашёл коммит 9495860f (HTTP 422)». Причина — `orchestrator/ci.py`
спрашивает GitHub о коммите проекта у репозитория артели:
`gh api repos/{owner}/{repo}/…` разрешает `{owner}/{repo}` по `cwd` пульта
(`config.ROOT`, `ci.py:73`), а функции на пути `verifying`/`ci-rerun`/гейта
мержа не передают репозиторий проекта до `gh`. Вдобавок `ci.gh(repo=…)`
(`ci.py:39-80`) дописывает `--repo <url>`, которого `gh api` не принимает
(«unknown flag: --repo», проверено Оператором 18.10); для `gh api`
репозиторий задаётся переменной окружения `GH_REPO`. Пробел назван аудитом
D2 (Т-5); D2-2 (01M545EDTHS47HSB59AKC1EZ9C) закрыл токен, но не репозиторий.

## Требования

1. Каждый вызов `gh` из `orchestrator/ci.py` по задаче внешнего проекта
   адресован репозиторию проекта (`url` его записи `targets.yaml`) и несёт
   токен его слота `token_slot` (переменной `GH_TOKEN`, как сейчас у
   `ci.gh(repo=…)`):
   - для `gh api` — через переменную окружения `GH_REPO=<владелец>/<имя>`,
     без `--repo` в argv;
   - для `gh run`/`gh pr` — флагом `--repo <url>`, как сейчас.

   Владелец и имя берутся из `url` проекта (решение Оператора 18.10, К-3)
   для двух видов адреса:
   - https: `https://<хост>/<владелец>/<имя>` с необязательными
     завершающими `.git` и `/`;
   - scp: `git@<хост>:<владелец>/<имя>` с необязательным завершающим
     `.git`.

   `<владелец>` и `<имя>` — непустые сегменты без `/`; завершающие `/` и
   `.git` в `GH_REPO` не входят. Адрес иного вида (другая схема, например
   `ssh://…`, меньше или больше двух сегментов пути, пустой сегмент) —
   именованный отказ вызова: `gh` не запускается, вызов возвращает
   ненулевой код с текстом, называющим адрес проекта и причину «вид адреса
   не разобран» (тот же канал, что отказ токена `gitcmd.hosting_token` в
   `ci.gh`, `ci.py:66-69`).

   `GH_REPO` ставится у задачи внешнего проекта и тогда, когда у его
   записи `targets.yaml` нет `token_slot` (токена нет, `gitcmd.py:133-135`):
   окружение такого вызова `gh api` всё равно несёт `GH_REPO` проекта,
   `GH_TOKEN` в нём не появляется.

   Внешний проект узнаётся разрешением контекста клона через
   `repo_context` (решение Оператора 18.10, К-4): переданный путь клона
   сопоставляется с записью `targets.yaml`, клоном которой он является
   (`repo_context.clone_path(<имя>)`), контекст этой записи —
   `repo_context.resolve(<имя>)`; `url` и `base` берутся из него.
   Признак артели — только `repo_context.is_artel` (`repo_context.py:154`);
   нового параллельного признака артели или внешнего проекта (сравнения с
   `config.ROOT`, своего списка имён и т. п.) не вводится. Репозиторий, не
   являющийся клоном ни одной записи внешнего проекта, — вызов артели, в
   том числе главная копия пульта `config.ROOT` и клон артели.
   `orchestrator/repo_context.py` — только чтение: сопоставление живёт в
   зонах задачи и пользуется его функциями.
2. У артели argv, окружение и `cwd` вызовов `gh` всех функций перечня
   требования 3 — в том числе `failed_check_names` и
   `check_run_workflow_run` — и всех их вызывающих из
   `orchestrator/ci_rerun.py` и `orchestrator/fsm_merge_gate.py` не
   меняются ни на байт относительно main. Сверх того у артели вызовы
   функций перечня идут прежней формой — без новых именованных
   аргументов (приём `ci._repo_kwargs`, `ci.py:83-95`: для клона артели и
   `None` — вызов без `repo`). Вызовы `ci.main_line_status(…,
   repo=config.ROOT)` из `orchestrator/pin.py:86` и
   `orchestrator/doctor/main_ci.py:33` остаются вызовами артели: `gh` в них
   не меняется (ни `GH_REPO`, ни `--repo`, ни `GH_TOKEN` не появляются).
   Существующие подмены функций перечня в `tests/`, написанные под
   прежнюю форму, работают без правки; среди них:
   `tests/test_invariants.py:326-328` (защищённый; `ci.gh` как
   `lambda *a:`, `ci.head_sha` как `lambda branch:`),
   `tests/test_ci_status.py:160` (`fake_gh(*args)`), `:367` (`check_runs`
   как `lambda sha:`), `:372` (`run_list` как `lambda branch:`), `:798`
   (`find_run_id` как `lambda sha:`), `tests/test_main_ci_line.py:62`
   (`gh(self, *args, timeout=None)`), `tests/test_merge_gate_ci_wait.py:82`
   (`trigger_rerun` как `lambda branch:`),
   `tests/test_ci_rerun_command.py:238` (`trigger_rerun` как
   `trigger(branch)`), `:242` (`failed_check_names` как
   `failed_names(sha)`), `tests/test_ci_stuck_check_run.py:220`
   (`check_run_workflow_run` как `lambda cid:`),
   `tests/test_main_ci_fetched_repo.py:64` (`check_runs` как `lambda sha:`
   под `main_line_status(repo=config.ROOT)`),
   `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203`
   (`head_sha` как `lambda branch, **_k:`, вершина main — `head_sha("main")`).
3. Репозиторий проекта доходит до всех функций CI на пути `verifying`,
   `ci-rerun`, автогейта приёмки и гейта мержа (проверка CI ветки и CI
   main после мержа) для задачи внешнего проекта. Перечень, сверенный по
   коду main (поиск вызовов `ci.<функция>(` по пакету пульта и скриптам):

   Функции `orchestrator/ci.py`, зовущие `gh` прямо или через другую
   функцию перечня:
   - `gh` (`:39`) — исполнитель; сейчас `--repo` дописывается и к `gh api`;
   - `check_runs_page` (`:118`) — `gh api …/commits/<sha>/check-runs`;
     `repo` принимает, но передаёт его как `--repo`;
   - `check_runs` (`:143`) — репозитория не принимает;
   - `run_list` (`:198`) — `gh run list`; `repo` принимает;
   - `_commit_workflow_runs` (`:371`) — `gh api …/actions/runs?head_sha=`;
     репозитория не принимает;
   - `_no_checks_by_branch` (`:674`) — зовёт `run_list(branch)` без
     репозитория;
   - `_inherited_from_main` (`:474`) — вершину главной ветки читает как
     `head_sha("main")` (литерал `main`, локальная `refs/heads/main`),
     `failed_check_names(main_sha)` зовёт без репозитория;
   - `failed_check_names` (`:732`) — репозитория не принимает;
   - `verifying_status` (`:600`), `branch_status` (`:767`) — клон проекта
     передают только в `head_sha`;
   - `accepted_full_suite` (`:823`) — для внешнего проекта возвращает
     отказ до обращения к `gh` (`:829`); поведение остаётся;
   - `main_line_status` (`:1029`) и `_main_line_runs` (`:974`) —
     `check_runs`/`_commit_workflow_runs` без репозитория;
   - `find_run_id` (`:1136`) — `gh api …/actions/runs` и `check_runs` без
     репозитория;
   - `check_run_workflow_run` (`:1211`) — `gh api …/actions/jobs/<id>` без
     репозитория;
   - `trigger_rerun` (`:1235`) — `gh run rerun`/`gh run watch` без
     репозитория; голову ветки читает `head_sha(branch)` без клона
     проекта (клон артели).

   Вызывающие вне `ci.py`:
   - `orchestrator/ci_rerun.py`: `:224` `check_run_workflow_run(check_id)`,
     `:232` `trigger_rerun(branch, run_id=…)`, `:267` и `:279`
     `failed_check_names(…)`, `:298` `trigger_rerun(branch)` — без
     репозитория проекта; `:272` `fsm._origin_main_sha(target)` — без
     `repo=` (см. требование 5); `:123`, `:158` `verifying_status(…,
     repo=…)` и `:244` `head_sha(…, repo=…)` — клон проекта уже передают;
   - `orchestrator/fsm_merge_gate.py`: `:290` `trigger_rerun(branch)` — без
     репозитория проекта; `:293`, `:341` `branch_status(…, repo=…)` и
     `:579`, `:618` `main_line_status(…, repo=ctx.path)` — клон передают
     (сверка CI main при этом идёт только для артели — ранний выход
     `repo_context.is_artel(ctx)`, `:571`, `:614`);
   - `orchestrator/acceptance.py`: `:2069` `head_sha`, `:2087`
     `accepted_full_suite`, `:2184` `verifying_status` — клон уже передают;
   - `orchestrator/github_adapter.py`: `:168`, `:193`, `:306` `ci.gh("pr",
     …, repo=<url>)` — `gh pr` с `--repo`, уже по требованию 1;
   - `orchestrator/fsm_advance.py:453` и `orchestrator/fsm_autogate.py:287`
     (вне зон) — `verifying_status(…, repo=workspace.task_repo(…))`, клон
     уже передают, правки не требуют;
   - `orchestrator/advance_gates/` функций `ci` не зовёт.

   Форма передачи (решение Оператора 18.10, К-2): репозиторий проекта
   доходит до функций ниже параметром `repo` — путём клона проекта, как у
   `head_sha(branch, repo=…)` и `verifying_status(branch, repo=…)`
   (`ci.py:98`, `:600`); `url` и `GH_REPO` выводятся внутри `ci.py` из
   записи проекта клона (требование 1), вызывающий их не передаёт:
   - `check_runs(sha: str, repo: Path | None = None)`;
   - `failed_check_names(sha: str, repo: Path | None = None)`;
   - `find_run_id(sha: str, repo: Path | None = None)`;
   - `check_run_workflow_run(check_id: str, repo: Path | None = None)`;
   - `trigger_rerun(branch: str, run_id: str = "", repo: Path | None = None)`.

   `repo=None` — прежний вызов артели. Параметр `repo` у `ci.gh`,
   `check_runs_page` и `run_list` сохраняет нынешний смысл (`url`
   проекта): вызовы `ci.gh("pr", …, repo=<url>)` из
   `orchestrator/github_adapter.py` остаются рабочими без правки.

   В вызывающих модулях — только передача репозитория проекта, без
   изменения логики гейтов (исключение — запись журнала требования 7).
4. `_inherited_from_main` (`ci.py:474-488`) у задачи внешнего проекта
   берёт вершину базовой ветки проекта — `base` его записи `targets.yaml`
   (`ctx.base`), а не литерал `main`, — как вершину `origin/<base>` клона
   проекта, а не локальной `refs/heads/main` (её push мержа не двигает), и
   спрашивает её проверки у репозитория проекта по требованию 1. У артели
   путь не меняется (требование 2: подмена `head_sha("main")` в
   `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203`).
5. `orchestrator/ci_rerun.py:272` у задачи внешнего проекта зовёт
   `fsm._origin_main_sha(target, repo=<клон проекта>)` — `git fetch` по
   адресу проекта идёт в клоне проекта, а не в главной копии пульта без
   токена. Функция параметр `repo` уже принимает (`fsm.py:166`); образец
   передачи — `fsm.py:264`. Правка — только вызова в `ci_rerun.py`. У
   артели вызов прежний.
6. До правки кода argv, окружение и `cwd` вызовов `gh` артели для функций
   перечня требования 3 зафиксированы тестами.
7. `fsm_merge_gate._ci_confirm_red_or_flake` (`fsm_merge_gate.py:281-309`):
   когда повтор не запущен (`ci.rerun_started(<note trigger_rerun>)` ложь,
   `ci.py:1274`), запись журнала `flake-rate` не говорит «ре-ран тоже
   красный» и «подтверждённый красный», а записывает «повтор не запущен» с
   причиной — `note`, которую вернула `trigger_rerun`. Это верно при любом
   исходе последующего `branch_status`: и при красном, и при зелёном
   (решение Оператора 18.10, К-1) — при незапущенном повторе зелёный
   статус записью «флейк: … ре-ран зелёный» не называется. Когда повтор
   запущен, записи `flake-rate` прежние; прочий исход узла (возврат
   зелёного, отказ мержа `sys.exit` с прежним текстом) не меняется.
8. Тесты детерминированы и без сети: подставной исполняемый `gh`,
   записывающий argv и переменные `GH_REPO`/`GH_TOKEN`; учебный внешний
   проект — запись `targets.yaml` со своим `url`, `base` и слотом токена.

## Критерии приёмки

AC-1. У артели argv, окружение (в том числе отсутствие `GH_REPO`) и `cwd`
вызовов `gh` функций перечня требования 3 — `verifying_status`,
`branch_status`, `accepted_full_suite`, `failed_check_names`,
`main_line_status`, `find_run_id`, `check_run_workflow_run`,
`trigger_rerun` — и их вызовов из `orchestrator/ci_rerun.py` и
`orchestrator/fsm_merge_gate.py` совпадают с main; `main_line_status(…,
repo=config.ROOT)` (вызов `pin.py:86` и `doctor/main_ci.py:33`) зовёт `gh`
без `GH_REPO`, без `--repo` и без `GH_TOKEN`, как на main. Ни одна
существующая подмена в `tests/` не правится.

AC-2. У учебного внешнего проекта, `url` которого — https-адрес,
оканчивающийся на `.git` или `/` (например
`https://github.com/<владелец>/<имя>.git`), либо scp-адрес
`git@<хост>:<владелец>/<имя>.git` (оба вида проверяются), каждый
вызов `gh api` функций перечня требования 3 получает в окружении
`GH_REPO=<владелец>/<имя>` (без `.git` и `/` в конце) и `GH_TOKEN` —
токен его слота, а в argv нет `--repo`. Репозиторий проекта доходит до
функций параметром `repo` — путём клона проекта (сигнатуры требования 3).
«Каждый вызов» проверяется в сценариях, доходящих до всех мест `gh api`:
- красный путь `verifying_status`/`branch_status` со сверкой с главной
  веткой — `_inherited_from_main` → `failed_check_names(<вершина>)`
  (`ci.py:660`, `:814`);
- проверки коммита с `check_suite.id` (или ссылкой на прогон) — запрос
  `_commit_workflow_runs` (`ci.py:379-383`);
- `find_run_id` при двух и более красных прогонах коммита — `gh api
  …/actions/runs` и `check_runs` (`ci.py:1162`, `:1180-1181`);
- `check_run_workflow_run` (`ci.py:1221`);
- `main_line_status(<sha>, repo=<клон проекта>)` — `check_runs` и
  `_commit_workflow_runs` через `_main_line_runs` (`ci.py:974`, `:1029`).

AC-3. У учебного внешнего проекта каждый вызов `gh run` (`run list`,
`run rerun`, `run watch`) и `gh pr` функций перечня требования 3 несёт в
argv `--repo <url>` проекта и `GH_TOKEN` — токен его слота. В том числе
в сценарии без проверок коммита — `_no_checks_by_branch` → `run_list`
(`ci.py:627`, `:638`, `:678`).

AC-4. `verifying_status` ветки задачи учебного внешнего проекта, у
головного коммита которой в репозитории проекта все проверки зелёные,
запрашивает проверки коммита у репозитория проекта и возвращает исход
`ci.VERIFYING_GREEN`; `note` не начинается с «голова ветки не в origin».

AC-5. `branch_status` ветки задачи учебного внешнего проекта с зелёными
проверками головного коммита в репозитории проекта запрашивает проверки у
репозитория проекта и возвращает зелёный исход (`True`).

AC-6. `trigger_rerun` ветки задачи учебного внешнего проекта — и с
заданным `run_id`, и с поиском прогона по головному коммиту — адресует
каждый вызов `gh` репозиторию проекта (поиск прогона — `gh api` с
`GH_REPO` проекта; `gh run rerun`/`gh run watch` — с `--repo <url>`
проекта), головной коммит читает в клоне проекта.

AC-7. Вызовы `check_run_workflow_run` и `failed_check_names` из
`ci-rerun` (`orchestrator/ci_rerun.py`) и `trigger_rerun` из
`ci-rerun` и гейта мержа (`orchestrator/fsm_merge_gate.py`) для задачи
учебного внешнего проекта адресуют `gh` репозиторию проекта.

AC-8. У учебного внешнего проекта без `token_slot` в записи
`targets.yaml` вызов `gh api` функций перечня требования 3 (например
`check_runs` из `verifying_status`) получает в окружении `GH_REPO` проекта,
`GH_TOKEN` в нём не выставлен пультом, в argv нет `--repo`.

AC-9. У учебного внешнего проекта с `base`, отличной от `main`, клон
которого несёт `origin/<base>` на коммите A и локальную ветку `main`
(или `<base>`) на другом коммите B, красный путь `verifying_status`/
`branch_status` со сверкой с главной веткой спрашивает упавшие проверки
коммита A (`gh api …/commits/<A>/check-runs` с `GH_REPO` проекта), а не B,
и фраза «красный унаследован от …» называет sha A.

AC-10. `ci-rerun` задачи учебного внешнего проекта зовёт
`fsm._origin_main_sha` с `repo=` — клоном проекта задачи; у задачи
артели вызов прежний (без `repo=`).

AC-11. Гейт мержа (`_ci_confirm_red_or_flake`) при красном статусе ветки и
`trigger_rerun`, вернувшей `note` отказа запуска («ре-ран CI не запущен: …»
или «ре-ран прогона <id> не запущен: …»), пишет запись журнала
`flake-rate` с текстом «повтор не запущен» и этой причиной; ни одна
запись `flake-rate` этого прохода не содержит «ре-ран тоже красный» и
«подтверждённый красный». То же при незапущенном повторе и зелёном
последующем `branch_status`: запись `flake-rate` содержит «повтор не
запущен» и причину, ни одна запись `flake-rate` этого прохода не
содержит «флейк». При запущенном повторе и красном статусе запись
`flake-rate` по-прежнему содержит «подтверждённый красный».

AC-12. У учебного внешнего проекта, `url` которого не https- и не
scp-вида требования 1 (например `ssh://git@github.com/<владелец>/<имя>.git`
или `https://github.com/<имя>` с одним сегментом пути), вызов `gh api`
функции перечня требования 3 (например `check_runs(sha, repo=<клон>)`)
не запускает `gh` (подставной `gh` не вызван) и возвращает отказ
(«статуса нет»), текст которого называет адрес проекта.

## Оценка объёма и деление
Сработавшие сигналы: число файлов зоны ≥ 5 (шесть элементов зоны из ТЗ);
число критериев приёмки ≥ 10 (12); `budget_usd` ≥ $30 (рамка ТЗ $35);
зона задевает механизм инварианта 19 `docs/invariants.md` (неизвестный
статус CI не зелёный — `ci.py`).

Обоснование монолита (решение — за Оператором на гейте SPEC): правка
одна по смыслу — адресация `gh` репозиторием проекта внутри `ci.py` и
передача этого репозитория из двух вызывающих (`ci_rerun.py`,
`fsm_merge_gate.py`, по одному–шести местам вызова). Часть «только
`ci.py`» без передачи из вызывающих оставляет `ci-rerun` и ре-ран гейта
мержа бьющими в репозиторий артели — дефект ТЗ не закрыт; часть «только
вызывающие» без `ci.py` не имеет куда передать репозиторий. Тесты
фиксации поведения артели (требование 6) — сторож требования 2 этой же
правки: отдельной задачей они мержились бы без изменения, которое
сторожат. Требования 4, 5, 7 — решения Оператора 18.10 по тем же местам
вызова (`_inherited_from_main`, `ci_rerun.py:272`, ре-ран гейта мержа);
вынесенные отдельно, они правили бы те же строки параллельно. Логика
гейтов не меняется (кроме текста записи `flake-rate` требования 7),
правки в `acceptance.py` и `github_adapter.py` по перечню требования 3
могут не понадобиться вовсе.

## Не входит
- Мерж через `gh pr merge` для внешних проектов.
- Защита ветки sled.
- Задача sled 01M55SKHZ293CCAK0N7T4H7ZMR — продолжится после мержа этой.
- Изменение логики гейтов в вызывающих модулях, в том числе включение
  сверки CI main после мержа (`fsm_merge_gate._check_main_ci`/
  `_await_main_ci`) для внешнего проекта: она остаётся только для артели;
  здесь — лишь передача репозитория проекта (и текст записи требования 7).
- Смена источника вершины главной ветки `_inherited_from_main` у артели
  (`head_sha("main")`): её держит подмена долгоживущего теста
  `tests/test_01m4pmqsypr2kd6n1jcvg9zabv_branch_verdict.py:203`, а AC-1
  запрещает правку подмен; требование 4 — только для внешнего проекта.
- Правка `orchestrator/advance_gates/`, `orchestrator/gitcmd.py`,
  `orchestrator/repo_context.py`, `orchestrator/targets.py`,
  `targets.yaml`, `docs/backlog.md` — только чтение; потребность в правке
  вне зон — эскалация.
- Правка `orchestrator/fsm.py`, `orchestrator/fsm_advance.py` и
  `orchestrator/fsm_autogate.py` (вне зон): клон проекта в
  `verifying_status` последние две уже передают, `fsm._origin_main_sha`
  параметр `repo` уже принимает.
- Правка вызовов `ci.main_line_status` в `orchestrator/pin.py:86` и
  `orchestrator/doctor/main_ci.py:33` (артель, вне зон) — их поведение
  держит требование 2.

## Материалы
- ТЗ: `tasks/01M55V7WB94C9BZXTXTTH83YWV/TZ.md`; решения Оператора по
  аудитам SPEC 18.10 (причины возврата из spec_gate: пункты 1-6; затем
  К-1..К-4 третьего аудита — AC-11, сигнатуры `repo=<клон>`, https/scp
  и отказ иного вида адреса, признак проекта через `repo_context`).
- Ручная проверка Оператора 18.10: `GH_REPO=sledproject/sled gh api
  'repos/{owner}/{repo}'` → `sledproject/sled`; `gh api … --repo …` →
  «unknown flag: --repo».
- `url` учебного проекта в `targets.yaml` — вида
  `https://github.com/<владелец>/<имя>` (так записан sled, `targets.yaml:70`).
- Сопоставление `url` с записью проекта в `ci.gh` — `gitcmd.project_by_url`
  через `gitcmd.url_key` (`gitcmd.py:44-46`, `:71-81`, только чтение):
  снимает завершающие `/` и `.git`; правило владельца и имени для
  `GH_REPO` — требование 1.
- Признак «повтор запущен» — `ci.rerun_started` (`ci.py:1274-1289`):
  подстрока «не запущен» в `note` `trigger_rerun` (`ci.py:1258`, `:1261`,
  `:1265`).
- Тестов, утверждающих `--repo` у `gh api` или «подтверждённый красный»
  при незапущенном повторе, в `tests/` main нет (подмена
  `tests/test_merge_gate_ci_wait.py:82` возвращает «ре-ран (тест)» —
  повтор запущен): раздел «Меняемое поведение» не нужен.
