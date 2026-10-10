---
task: 01M4G8KPP8DVNBCPGCAPSVMAKZ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Роль не пишет в главную копию пульта — корень генератора карты и сторож после шага роли

## Подход
Две независимые части одного инцидента 05.10.

**Причина — корень генератора.** `scripts/codebase_map.py::main` берёт
корень как `repo_root(Path(__file__).resolve().parent)` вместо
`repo_root(Path.cwd())`: дерево самого сценария, а не текущего каталога.
`repo_root` не меняется (её ожидания держит `tests/test_codebase_map.py::RepoRootTest`).
Все вызовы пульта (`brief.py`, `pull.py`, `fsm_postmerge.py`,
`fsm_merge_gate.py`) запускают `python3 scripts/codebase_map.py` с
`cwd=<дерево>` — сценарий того же дерева, результат прежний.

**Слепота — сторож главной копии** (`orchestrator/checkpoint.py`):
- `main_copy_watch_start(conn, task_id)` — снимок `git status --porcelain`
  главной копии (своя точка вызова `subprocess.run(["git", "-C",
  config.ROOT, "status", "--porcelain"], env=gitcmd.pult_env())`, не
  `gitcmd.git` — см. «Возврат из verifying») и id/время записи
  «agent run started» этого шага; зовётся в `runner.run_agent_once` сразу
  после `_prepare_step`, до запуска агента. git не ответил — `None`, сверки
  не будет (шаг не страдает).
- `watch_main_copy(conn, task_id, role, watch)` — зовётся в каждом
  `_finish_*` (`_finish_timeout`, `_finish_failed`,
  `_finish_missing_artifact`, `_finish_ok`) сразу после чекпоинта шага.
  Появившиеся строки = строки статуса после минус строки до (требование 4:
  бывшее до шага не попадает и алерт само не поднимает). Пусто — ничего.
  Иначе — алерт `kind=warning`, `source=main-copy-watch`, target `None`
  (главная копия — уровень пульта). Сбой git на второй сверке при удачной
  первой — запись журнала «сверка главной копии не выполнена» (молчаливый
  сбой недопустим).
- Текст алерта: «главная копия пульта: за время шага роли <роль> (задача
  <id>) появились изменения: <пути>. Кто их внёс, не установлено — шаги
  ролей других задач в пересекающийся промежуток: <роль> (задача <id>), …
  | нет; в главной копии работает и сессия Оператора. Ничего не откачено.»
  Авторство не утверждается (требование 3); за именем роли всегда идёт
  «(», чтобы ни один глагол не стоял в одном предложении с ролью.
- Пересекающиеся шаги — по журналу `steps` (порядок `id`, не секунды
  `ts`): шаг другой задачи = запись «agent run started»; его конец —
  первая позже неё запись той же задачи из «agent run finished/FAILED/
  TIMEOUT/SKIPPED» или следующий «started». Пересекается, если конца нет
  либо конец позже старта проверяемого шага. Окно выборки — старты не
  раньше `2 × AGENT_TIMEOUT_SEC` до старта шага (дольше шаг не живёт:
  таймаут его снимает), чтобы осиротевший «started» упавшего процесса не
  висел в каждом алерте вечно. Выборка — `store.steps_of_action`
  (store.py — путь «только чтение» ТЗ, новых запросов в нём не заводим).
- Сторож ничего не откатывает и не меняет состояние задачи (требование
  5): только `git status` и `raise_alert`.

**Возврат из verifying (ANSWER-1, CI 772f0613 красный).** Сверка главной
копии шла через `gitcmd.git("status", "--porcelain")` в
`checkpoint._main_copy_status`:
1. `test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py::...::test_ac8_every_call_without_repo_is_in_the_allow_list`
   — вызов примитива без явного репозитория вне перечня;
2. `test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`
   — лишний `['status', '--porcelain']` в точном списке git-вызовов шага
   (тест подменяет `gitcmd.git`).
Исправление — одно место, закрывает оба класса: `_main_copy_status` зовёт
git своей точкой вызова (`subprocess.run` с `-C <config.ROOT>` —
репозиторий назван явно, окружение пульта `gitcmd.pult_env()`; сбой
запуска/декодирования — `None`, как прежде). Сторож — наблюдение пульта
за собой, а не git-вызов шага, поэтому в последовательность, которую
сверяют тесты `gitcmd.git`, не попадает. Долгоживущие тесты не правились.
Свой `tests/test_main_copy_watch.py`: подмена сбоя git перенесена с
`gitcmd.git` на `checkpoint.subprocess.run` (имя метода и утверждения те
же). Других вызовов `gitcmd.*` без репозитория в diff задачи нет
(`git diff main -- orchestrator/` проверен).

## Шаги
1. `scripts/codebase_map.py`: корень от `__file__`, докстринг модуля;
   регенерация `docs/codebase-map.md`.
2. `orchestrator/checkpoint.py`: `main_copy_watch_start`,
   `watch_main_copy`, выбор пересекающихся шагов, текст алерта.
3. `orchestrator/runner.py`: снимок до запуска агента, сверка во всех
   четырёх `_finish_*` после чекпоинта.
4. Тесты: долгоживущие `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_*.py`
   (зафиксированы, не правятся) покрывают AC-1..AC-8; свой юнит-тест
   `tests/test_main_copy_watch.py` — на свойства вне них: сбой git на
   снимке/сверке не роняет шаг и пишет запись журнала; осиротевший старт
   старше окна в алерт не попадает.
5. Регенерация карты, guard, прогон затронутых модулей и полного набора
   командой пульта.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2, 3 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |

## Влияние на систему
- `runner.run_agent_once`: +2 вызова `git status` главной копии на
  попытку и одна выборка журнала по действиям при срабатывании. Исходы и
  возвраты `_finish_*` не меняются; сторож не бросает исключений (git
  не ответил — сверки нет).
- Алерт `warning` не входит в выборки `incident` (бриф, авто-ack doctor,
  стоп-кран волны) — на FSM и `auto` не влияет; виден в `doctor`/`status`.
- Гейты, лимиты, тесты, инварианты не ослабляются. Существующие тесты не
  правятся.
- Откат — revert коммита ветки.

## Риски
- Файл, грязный уже до шага и изменённый ещё раз за шаг, не ловится:
  строка `git status` у него та же. Требование 4 прямо исключает бывшие
  до шага изменения; сверка содержимого — отдельная задача при нужде.
- Рабочие копии задач и каталоги документов лежат под `.artel/`
  (игнорируется git главной копии) — в сверку не попадают.

## Проверка
- Долгоживущие `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_*.py`: 9 passed
  (16 subtests) после реализации.
- Свой `tests/test_main_copy_watch.py`: 2 passed; временная мутация (снято
  окно выборки + убрана запись журнала сбоя git) — оба красные, код
  возвращён.
- Затронутые модули (`test_checkpoint_*`, `test_codebase_map`,
  `test_runner_*`, `test_timeout_checkpoint`, `test_main_copy_watch`):
  146 passed.
- `plank-run`: планки нет (в ссылке документов только перечень сумм
  долгоживущих файлов) — pytest не запускался.
- Карта регенерирована `python3 scripts/codebase_map.py`.
- Итерация 1 (до возврата): полный набор `suite-run` не прогнан — три
  попытки получили отказ замка полных прогонов
  (задача 01M4G8N9KBTVNNT7YGZ59Q5WBF).
- Итерация 2 (возврат из verifying, ANSWER-1):
  - оба упавших в CI теста —
    `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py`,
    `tests/test_review_package.py` — плюс
    `tests/test_01m4g8kpp8dvnbcpgcapsvmakz_*.py` и
    `tests/test_main_copy_watch.py`: 158 passed, 24 subtests;
  - затронутые модули (`test_checkpoint_*` ×4, `test_runner_*` ×5,
    `test_timeout_checkpoint`, `test_codebase_map`): 144 passed;
  - `suite-run` №1 (полный набор): 4776 passed, 2 skipped, 1 failed —
    `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`,
    отчёт пульта: «падают и на базе» (база eccf5709), новых падений на
    ветке 0; тест вне зоны задачи (`liveness.py` не тронут);
  - карта регенерирована (`docs/codebase-map.md`, 3 строки).

## Предложения системе
- `suite-run --wait` в сводке красного прогона печатает «прошло: 1,
  упало: 0» при логе «1 failed, 4776 passed» — сводка пульта расходится
  с итогом pytest (orchestrator/suite_run.py, `render`/`parse`).
- Шаг роли (bash-песочница) отказывает в `ls`/`cat` — роль не может
  посмотреть содержимое каталога документов иначе как через
  `python3 -c os.walk`; миссия шага этого не упоминает.
