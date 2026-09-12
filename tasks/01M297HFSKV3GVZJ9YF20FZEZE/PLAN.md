---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: база ветки задачи — origin/main, а не локальный пин; doctor и new видят непушенные коммиты главной копии

## Подход

Вариант A (ANSWER-2): только self/артель. `workspace.ensure` перед
заведением НОВОЙ ветки задачи делает `git fetch origin
<config.MAIN_BRANCH>` (`gitcmd.fetch_head_sha`, уже существующий примитив
— fetch + `rev-parse --verify --quiet FETCH_HEAD`) и создаёт
`git worktree add -b <branch> <wt_path> <origin_sha>` вместо базы
`config.MAIN_BRANCH`. Fetch не удался — именованный отказ («база ветки
недоступна: fetch origin не удался: <причина>»), без отката на локальный
main (AC-3). Путь существующей в git ветки не тронут.

Сверка «HEAD ушёл вперёд origin» вынесена общей парой функций в
`orchestrator/doctor/root_pin.py` (`fetch_origin_main_sha`,
`unpushed_commits`) — новая проверка doctor `check_pin_unpushed`
(fail/ok/warn, требование 2) и предупреждение `catalog.cmd_new`
(требование 3) читают ОДИН и тот же критерий через эти функции, не две
независимые реализации. `catalog.py` импортирует `doctor` ЛЕНИВО, внутри
функции — `doctor/__init__.py` импортирует `canary`, а `canary.py`
импортирует `catalog` на уровне модуля; импорт `doctor` в `catalog.py`
на уровне модуля дал бы цикл `catalog -> doctor -> canary -> catalog`
(тот же приём, что уже несёт `cmd_init` для `canary`).

Побочный эффект (обнаружен прогоном существующих тестов, не входил в
исходную оценку SPEC): требование фактического `git fetch origin`
внутри `ensure()` ломает десятки существующих тестов, которые заводят
worktree задачи под ПОЛНОСТЬЮ фейковым git (`tests/sandbox.py::fake_git`,
`SpyRun`) или под настоящим git без единого origin
(`RealGitSandbox`/`RealPultGitTest` и бесхозные bespoke-песочницы) — не
потому что новая база неверна, а потому что общие тестовые заглушки не
умели симулировать успешный fetch. Почищено без ослабления самих тестов:
`fake_git`/`SpyRun` теперь отвечают успехом с фейковым sha на
`rev-parse --verify --quiet FETCH_HEAD` (тот же приём, что уже несёт
фейковый sha для плотницких примитивов); опционально вызываемый метод
`RealGitSandbox.add_synced_origin()` заведён для песочниц, которым нужен
настоящий синхронный origin; точечно поправлены сценарии, заводящие
worktree на настоящем git без общего фикстурного слоя (`test_amend.py`,
`test_kill_cleanup.py`, `test_timeout_checkpoint.py`,
`test_task_id_prefix_regression.py`, `test_step_refixation.py`,
`test_workspace.py`).

Итерация 2 (REVIEW.md итерации 1, R1-F1, blocker): требование
обязательного `git fetch origin` в `workspace.ensure` несовместимо с
намеренно нерабочим `origin` `canary._ephemeral_clone`
(`ORIGIN_STUB_URL`, схема без транспорта) — канареечный прогон
(`artel.py canary --k N`) заводит ЛЮБУЮ задачу как НОВУЮ, значит для
неё ВСЕГДА исполняется ветка с fetch, которая гарантированно валилась.
Почищено в `orchestrator/canary.py::_ephemeral_clone`: вместо
недостижимой схемы origin эфемерного клона — ОТДЕЛЬНЫЙ одноразовый
bare-клон `origin_dir` рядом с `dest` (`git clone --bare --shared dest
origin_dir`, снят сразу после `dest`, несёт `config.MAIN_BRANCH` на
момент старта прогона), убираемый вместе с `dest` в `finally`. `--
shared` обязателен: первая попытка (полный `--bare` без `--shared`)
формально чинила R1-F1 (`test_ac2_ac4_ephemeral_clone_lifecycle.py`
зелёный), но вторая полная копия объектов пульта на каждую
канареечную задачу подрывала временной запас ДРУГИХ тестов той же
задачи 01M1NEEWH5K1XPFRDGRMPYSBXJ (`test_ac8_escalation_marker_
discrepancy.py`, `test_ac9_per_task_baseline.py`,
`test_ac11_verifying_gate_bypassed.py` — все несут жёсткий потолок
«прогон уложился в 30с»); `--shared` (объекты — alternate-ссылка на
`dest`, не копия) убирает эту стоимость. Fetch/push из `dest` теперь
идёт на `origin_dir`, не на несуществующий адрес и не на `outer_root`
— push по-прежнему не покидает пару временных каталогов, требование 3
(«ноль следов в главном пульте») не нарушено. `ORIGIN_STUB_URL`
убрана как константа; комментарии `orchestrator/fsm_advance.py`
(`_origin_push_gate`, `in_dev`), ссылавшиеся на неё как на «источник
гарантированного отказа push», поправлены — реальная защита там не
это, а явная проверка `if not t["is_canary"]`, гейт вовсе не
вызывается для канареечных задач.

## Шаги

1. `orchestrator/workspace.py::ensure` — fetch origin перед заведением
   новой ветки, именованный отказ без отката (требование 1, AC-1..AC-3).
2. `orchestrator/doctor/root_pin.py` — `check_pin_unpushed` +
   вспомогательные `fetch_origin_main_sha`/`unpushed_commits`;
   регистрация в фасаде `orchestrator/doctor/__init__.py` и в
   `orchestrator/doctor/cli.py::all_checks` (требование 2, AC-4..AC-6).
3. `orchestrator/catalog.py::cmd_new` — предупреждение о расхождении
   пина + запись в журнал, переиспользующие функции шага 2 через ленивый
   импорт `doctor` (требование 3, AC-7..AC-8).
4. Тесты: юнит-тесты `tests/test_workspace.py` (AC-1/AC-3 на настоящем
   git), `tests/test_doctor.py::PinUnpushedCheckTest` (AC-4..AC-6 +
   wiring-тест регистрации в `all_checks`), `tests/
   test_catalog_pin_divergence.py` (чистое форматирование предупреждения/
   записи журнала, без git — сверка с origin уже покрыта acceptance_tests
   этой задачи), плюс правки существующих тестов/тестовых заглушек,
   сломанных требованием реального fetch (см. «Подход»).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 4 |

## Влияние на систему

Затронуты только self/артель (сигнатура `workspace.ensure` не менялась,
внешние target через `workspace.ensure` не ходят — ANSWER-2). Новая
проверка doctor `pin-unpushed` может завести `fail` там, где раньше
`doctor` был чист — это осознанное следствие требования 2 (непушенный
документный коммит — инцидент, не деградация); гейты/лимиты/инварианты
не ослаблены, только добавлена НОВАЯ блокирующая проверка. `catalog.
cmd_new` не блокирует заведение задачи при расхождении (AC-7) —
поведение существующих вызывающих мест (`spawn_subtask`, батч `canary`)
не меняется, предупреждение — только для прямого `cmd_new`.

Правки тестовых заглушек (`tests/sandbox.py::fake_git`/`SpyRun`) —
строго ДОБАВЛЕНИЕ нового распознаваемого случая (`rev-parse --verify
--quiet FETCH_HEAD`), существующие случаи (отказ на `refs/heads/*`,
плотницкие примитивы) не тронуты; проверено прогоном широкого среза
существующих файлов `tests/` (workspace, doctor, catalog, invariants,
auto_cycle, multitarget, git_fixation, canary, amend, kill_cleanup,
timeout_checkpoint, step_refixation, step_autocommit, answer, pause_now
и другие — все зелёные). Откат — правка одним диффом (`git revert`),
затронутые модули изолированы (`workspace.py`, `orchestrator/doctor/`,
`catalog.py`, `tests/`).

## Риски

`RealGitSandbox`/`RealPultGitTest` — общие базовые песочницы для
ДЕСЯТКОВ тестовых файлов; не тронуты в base `setUp()` намеренно (часть
подклассов заводит СВОЙ origin другой формы, включая сценарии,
рассчитывающие на ЕГО отсутствие — Draft-MR-флоу) — точечная правка по
факту столкновения безопаснее общего изменения базового класса. Файлы
вне прогнанного среза, которые заводят worktree задачи напрямую на
настоящем git БЕЗ origin (минуя `fake_git`/`SpyRun`/
`RealGitSandbox.add_synced_origin`), теоретически могут обнаружиться в
CI — по построению это тот же узкий класс, что уже почищен (прямой
`workspace.ensure`/`cmd_run`/`cmd_auto` на голом `git init` без origin),
исчерпан прицельным поиском (`grep workspace.ensure`, `grep cmd_run` по
RealGitSandbox/RealPultGitTest-наследникам и bespoke `git("init"...)`
песочницам), но полный прогон `tests/` в шаге запрещён — если CI найдёт
пропуск, чинится тем же приёмом.

## Предложения системе

- `orchestrator/doctor/root_pin.py::check_root_pin` не несёт ни одного
  юнит-теста в `tests/test_doctor.py` (только упоминание в докстринге
  соседнего теста) — прецедент, на который эта задача опиралась при
  решении не дублировать acceptance-покрытие юнит-тестами построчно;
  стоило бы явно закрепить это правило в `coding-standards.md`
  («acceptance_tests закрывают AC — юнит-тест обязателен только для
  чистой логики без git»), а не оставлять implicit.
- При проверке R1-F1 обнаружена ПРЕДСУЩЕСТВУЮЩАЯ (не от этой задачи)
  флакующая планка в `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`:
  `test_ac8_escalation_marker_discrepancy.py`,
  `test_ac9_per_task_baseline.py`,
  `test_ac11_verifying_gate_bypassed.py` несут жёсткий потолок «прогон
  канарейки укладывается в 30с» — на текущем размере пульта прогон
  реально занимает ~41с ДАЖЕ на HEAD ДО начала этой задачи (проверено
  прямым откатом трёх файлов `workspace.py`/`canary.py`/`catalog.py` к
  cd9a477b и повторным прогоном — тот же провал по тому же порогу).
  Похоже на естественный рост пульта со временем (больше коммитов/
  файлов — дольше материализация worktree), не на конкретную мутацию
  кода. Вне зоны этой задачи (`tasks:` не входят в zones SPEC, файл
  чужой уже закрытой задачи) — не чинил; фиксирую, чтобы не потерялось
  и не было ошибочно приписано следующей задаче, которая случайно
  заденет этот путь.
