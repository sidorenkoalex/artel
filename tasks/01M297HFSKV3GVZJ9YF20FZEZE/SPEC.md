---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/workspace.py, orchestrator/doctor/, orchestrator/catalog.py, tests/
budget_usd: 35
---

# SPEC: база ветки задачи — origin/main, а не локальный пин; doctor и new видят непушенные коммиты главной копии

## Контекст

Инцидент 11.09: документный коммит сделан прямо в главной копии, push
отклонён, коммит остался только на локальном пине `config.ROOT`. Семь
веток задач волны заведены `workspace.ensure` от локального `main`
(`config.MAIN_BRANCH`) и унаследовали расхождение; то же содержимое
позже попало в `origin/main` другим коммитом — у веток появились две
точки расхождения, и подтяжка конфликтовала даже там, где ветка
изменённый файл не трогала. Итог: семь эскалаций, семь шагов роли на
разрешение, один reject с повторным CI и ревью. `doctor` расхождение
между HEAD главной копии и `origin/<MAIN_BRANCH>` не видел.

По ответу Оператора (ANSWER-2.md, вариант A): новая способность
касается только self/артель — `workspace.ensure` заводит новую ветку
задачи от `origin/<config.MAIN_BRANCH>`, а не от локального
`config.MAIN_BRANCH`. Внешние target через `workspace.ensure`/worktree
`config.ROOT` не ходят (`runner.role_cwd` берёт для них
`role_cwd_path`, отдельный клон `.artel/projects/<target>/workspace`) —
это не меняется. Сигнатура `workspace.ensure(task_id, branch)` остаётся
прежней.

## Требования

1. `workspace.ensure` перед `git worktree add -b` делает `git fetch
   origin <config.MAIN_BRANCH>` и заводит новую ветку задачи от
   `origin/<config.MAIN_BRANCH>` (после успешного fetch), а не от
   локального `config.MAIN_BRANCH`. Если ветка задачи в git уже
   существует — путь без изменений (тот же `git worktree add branch`
   без базы). Если `git fetch origin <config.MAIN_BRANCH>` отказывает —
   `ensure` возвращает именованную причину отказа «база ветки
   недоступна: fetch origin не удался» (или включает эту формулировку),
   worktree/ветка не заводятся, откат на локальный `config.MAIN_BRANCH`
   не происходит. Исполняемый код пульта (`config.ROOT`) остаётся
   пином (ADR-0013) — меняется только база НОВОЙ ветки задачи, не код,
   которым исполняется сам шаг.
2. Новая проверка `doctor` «pin-unpushed»: после `git fetch origin
   <config.MAIN_BRANCH>` HEAD главной копии (`config.ROOT`) обязан быть
   предком `origin/<config.MAIN_BRANCH>`. Если нет — `Check` со
   статусом `fail`, сообщение перечисляет непушенные коммиты (sha и
   первая строка сообщения каждого) и несёт подсказку: документные
   коммиты — только через `note`; выровнять пин — `pin --to <предок>` +
   `pin-update <sha>`. Если HEAD — предок (или совпадает с)
   `origin/<config.MAIN_BRANCH>` — статус `ok`. Если `git fetch`
   отказывает (нет сети, нет origin, песочница без настоящего git) —
   статус `warn` с сообщением «сверка с origin невозможна» (не `ok`,
   в отличие от деградации существующего `check_root_pin`).
3. На входе команды `new` (`catalog.cmd_new`) — та же сверка (HEAD
   `config.ROOT` — предок `origin/<config.MAIN_BRANCH>` после fetch):
   при расхождении команда всё равно заводит задачу (заведение не
   блокируется), но печатает в вывод предупреждение с перечнем
   непушенных коммитов (sha и первая строка каждого) и пишет в журнал
   задачи (`store.journal`) запись «пин расходится с origin: N
   коммитов». При отсутствии расхождения (или при отказе fetch) —
   команда работает как прежде, без нового вывода.
4. Тесты:
   - ветка новой задачи, заводимая `workspace.ensure`, стартует от
     `origin/<config.MAIN_BRANCH>`, а не от локального
     `config.MAIN_BRANCH`, когда они расходятся — мутация «база
     `config.MAIN_BRANCH`» (без предшествующего `git fetch origin`)
     красит этот тест;
   - отказ `git fetch origin <config.MAIN_BRANCH>` в `workspace.ensure`
     — именованный отказ шага, ветка/worktree не заведены;
   - новая проверка doctor «pin-unpushed»: `fail` на непушенном HEAD
     (с перечнем sha и первых строк сообщений в тексте), `ok` при
     совпадении/предковости, `warn` при отказе fetch;
   - `catalog.cmd_new` печатает предупреждение и пишет запись в журнал
     при расхождении пина с origin; без расхождения — не печатает и не
     пишет;
   - существующие тесты `orchestrator/workspace.py`,
     `orchestrator/doctor/`, `orchestrator/catalog.py` (в частности
     `tests/test_workspace.py`, `tests/test_doctor.py`,
     `tests/test_catalog_*`) остаются зелёными без ослабления.

## Критерии приёмки

AC-1. `workspace.ensure` при заведении НОВОЙ ветки задачи выполняет
`git fetch origin <config.MAIN_BRANCH>` и создаёт ветку от
`origin/<config.MAIN_BRANCH>`, а не от локального `config.MAIN_BRANCH`.

AC-2. Если ветка задачи в git уже существует, `workspace.ensure`
заводит worktree на существующей ветке без обращения к базе (поведение
не меняется).

AC-3. Если `git fetch origin <config.MAIN_BRANCH>` в `workspace.ensure`
отказывает, функция возвращает именованную причину отказа «база ветки
недоступна: fetch origin не удался» (или содержащую эту формулировку),
worktree и ветка не создаются, отката на локальный `config.MAIN_BRANCH`
не происходит.

AC-4. Новая проверка `doctor` (условно `pin-unpushed`) возвращает
`fail`, если после `git fetch origin <config.MAIN_BRANCH>` HEAD
`config.ROOT` не является предком `origin/<config.MAIN_BRANCH>`;
сообщение перечисляет непушенные коммиты (sha и первая строка каждого)
и содержит подсказку про `note` и `pin --to`/`pin-update`.

AC-5. Та же проверка возвращает `ok`, если HEAD `config.ROOT` совпадает
с `origin/<config.MAIN_BRANCH>` или является его предком.

AC-6. Та же проверка возвращает `warn` с сообщением «сверка с origin
невозможна», если `git fetch origin <config.MAIN_BRANCH>` отказывает
(не `ok`).

AC-7. `catalog.cmd_new` при расхождении HEAD `config.ROOT` с
`origin/<config.MAIN_BRANCH>` (после fetch) печатает в вывод команды
предупреждение с перечнем непушенных коммитов (sha и первая строка
каждого) и пишет в журнал задачи (`store.journal`) запись вида «пин
расходится с origin: N коммитов»; задача при этом заводится (заведение
не блокируется расхождением).

AC-8. `catalog.cmd_new` без расхождения пина (или при отказе fetch) не
печатает предупреждение о расхождении и не пишет соответствующую
запись в журнал.

## Не входит

- `pin-update`/`pin --to` (сама операция выравнивания пина Оператором)
  и гейт свежести канарейки — не меняются.
- Подтяжка main в ветку задачи (`orchestrator/pull.py`) — не меняется.
- Разрешение уже возникших перекрёстных конфликтов волны 11.09.
- Pre-commit hook главной копии (локальная настройка, не код
  репозитория).
- Способность `workspace.ensure`/`runner.role_cwd` заводить ветку
  внешнего target от базы этого target по `targets.yaml` — по ответу
  Оператора (ANSWER-2.md) новая база от origin касается только
  self/артель; внешние target через `workspace.ensure` не ходят и эта
  задача этот путь не трогает.

## Материалы

- Копилка П1 «непушенный коммит на пине множит конфликты подтяжки»,
  решение Оператора 11.09 «заведи».
- `orchestrator/doctor/root_pin.py` — существующий соседний check
  `root-pin` (другая семантика: сверка пина исполняемого кода с main
  артели, не про непушенные коммиты HEAD) — ориентир по форме `Check`,
  не по содержанию.
- `orchestrator/fsm.py:70-153` (`_origin_main_source`/
  `_origin_main_sha`) — образец для остальных мест кодовой базы,
  сверяющихся с origin main; в зону этой задачи не входит (задача не
  трогает `fsm.py`, вариант A).
