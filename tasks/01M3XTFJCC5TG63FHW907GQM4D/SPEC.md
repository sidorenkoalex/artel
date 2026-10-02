---
task: 01M3XTFJCC5TG63FHW907GQM4D
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/cycle_hint.py, orchestrator/store.py, orchestrator/fsm.py, orchestrator/auto.py, orchestrator/answer.py, orchestrator/catalog.py, orchestrator/budget.py, orchestrator/ci_rerun.py, orchestrator/advance_gates/tests_writing.py, tests/test_cycle_hint.py
budget_usd: 30
---

# SPEC: Подсказки пульта называют полный порядок запуска цикла после наблюдения фоновых задач

## Контекст
После мержа наблюдения фоновых задач (01M3SX69E8P64D77J1XTHMHE40, 890c96e6)
отсоединённые `run`/`auto` требуют `--client codex|claude --chat <id>`
(`orchestrator/artel.py` `_cycle_args`) и активного наблюдения той же
сессии, проекта, клиента и чата со свежей связью с `watch`
(`_launch_detached`, `store.matching_observation`). Подсказки пульта в
тринадцати местах по-прежнему печатают голые `artel.py run <id>` /
`artel.py auto <id>`; Оператор выполняет их дословно и получает отказ.
Каждое место собирает строку само, общей функции нет.

Тринадцать мест (origin/main 83a9c96e): `orchestrator/fsm.py:851`, `:856`,
`:1005`, `:1105`; `orchestrator/auto.py:123`, `:193`, `:200`, `:732`;
`orchestrator/answer.py:276`; `orchestrator/catalog.py:489`;
`orchestrator/budget.py:495`; `orchestrator/ci_rerun.py:246`;
`orchestrator/advance_gates/tests_writing.py:28`.

## Требования
1. Новый модуль `orchestrator/cycle_hint.py` — единственное место, где
   формируется подсказка запуска цикла. Публичная функция
   `launch_hint(conn, task_id, cmd, note="") -> list[str]`: `cmd` —
   `"run"` или `"auto"`, `note` — пояснение места вызова (сегодняшнее
   «(запуск разработчика)», «— продолжит отсюда» и т. п.); возвращает
   готовые строки подсказки.
2. Все тринадцать мест печатают (или кладут в `Stop.hint`) результат
   `launch_hint` и собственной строки с `artel.py run {…}` /
   `artel.py auto {…}` больше не собирают. Префикс места вызова
   («дальше:», «затем:», текст до «затем …» в `auto.py:193`/`:732`) и
   пояснение (через `note`) сохраняются.
3. Форма результата: первый элемент — строка запуска, начинается как
   сегодня `artel.py <cmd> <id>`, продолжается `--client <клиент> --chat
   <чат>` и завершается пояснением `note` (если задано). Второй элемент —
   строка, начинающаяся с `сначала:`; за ней — по одному элементу на
   каждый недостающий шаг, в порядке исполнения.
4. Случай определяется по БД для текущей сессии
   (`session.resolve_session_id(None)`) и проекта задачи (`target`):
   - **а)** есть активное наблюдение этой сессии и проекта, в котором
     задача включена, — в строку запуска подставлены его `client` и
     `chat`; шаги: `artel.py watch --observation <его ID>` фоновой задачей
     сессии с оговоркой «если ещё не идёт»;
   - **б)** есть активное наблюдение этой сессии и проекта, но задача в
     нём не включена (например, после `stop`), — шаги по порядку:
     `artel.py observe add <его ID> --tasks <id>`, затем `artel.py watch
     --observation <его ID>` (если ещё не идёт); строка запуска — с его
     `client`/`chat`;
   - **в)** активного наблюдения нет — шаги по порядку: `artel.py observe
     register --client codex|claude --chat <ID чата> --tasks <id>` (ID
     наблюдения — из её вывода), затем `artel.py watch --observation <ID
     наблюдения>` фоновой задачей сессии; строка запуска — `artel.py <cmd>
     <id> --client codex|claude --chat <ID чата>`.
5. Наблюдения другой сессии, другого проекта и не в `state='active'` не
   учитываются (для них — случай «в»). Из нескольких подходящих
   наблюдений берётся то, что выбрал бы `store.matching_observation`, —
   с самой свежей связью (порядок `last_seen_at DESC, rowid DESC`); случай
   «а» имеет приоритет над «б».
6. Чтение наблюдений сессии и проекта — новой функцией чтения в
   `orchestrator/store.py` рядом с прочими функциями наблюдений; SQL в
   `orchestrator/cycle_hint.py` не пишется. Подсказка ничего не
   регистрирует и не меняет в БД.
7. Строка запуска случаев «а» и «б» принимается разбором
   `orchestrator/artel.py` (`_cycle_args`) без отказа; поведение команд
   `run`/`auto`/`observe`/`watch` не меняется.
8. Тесты — в `tests/test_cycle_hint.py`, на временной БД, как соседние
   тесты наблюдения.

## Критерии приёмки

AC-1. `launch_hint(conn, id, cmd, note)` возвращает список строк: первая
начинается с `artel.py <cmd> <id> --client ` и содержит `--chat ` и
переданный `note`; вторая начинается с `сначала:`; для `cmd` из
`run`/`auto` подставляется переданная команда.

AC-2. Случай «в» (наблюдений нет): в подсказке есть `observe register`,
`--tasks <id>`, `watch --observation`, `<cmd> <id> --client`, и они идут
в этом порядке. Ловит мутацию: шаг наблюдения или `watch` выпал из
подсказки либо порядок шагов перепутан.

AC-3. Случай «а» (активное наблюдение текущей сессии и проекта, задача
включена): строка запуска несёт `--client`/`--chat` этого наблюдения из
БД, шаги называют `watch --observation <его ID>` с оговоркой «если ещё
не идёт», а `observe register` и `observe add` не предлагаются. Ловит
мутацию: подсказка игнорирует существующее наблюдение и печатает
заполнители.

AC-4. Случай «б» (наблюдение есть, задача выключена
`store.disable_task_observation` — тем же путём, что `stop`):
предлагается `observe add <ID наблюдения> --tasks <id>`, а не `observe
register`; шаг `observe add` идёт раньше `watch --observation <ID>`,
строка запуска несёт `--client`/`--chat` этого наблюдения. Ловит
мутацию: после `stop` подсказка ведёт к отказу «нет активного
наблюдения».

AC-5. Наблюдение другой сессии, наблюдение другого проекта и
прекращённое (`store.stop_observation`) наблюдение дают случай «в» — их
клиент, чат и ID в подсказку не попадают; из двух подходящих активных
наблюдений выбирается то, у которого свежее `last_seen_at`. Ловит
мутацию: подставлены клиент и чат чужого, остановленного или
протухшего-в-пользу-свежего наблюдения.

AC-6. Строка запуска случая «а» (первая строка до пояснения `note`),
разбитая на аргументы, проходит `artel._cycle_args` без `SystemExit` и
возвращает те же клиент и чат, что у наблюдения в БД. Ловит мутацию:
формат флагов подсказки разошёлся с разбором команды.

AC-7. В тексте модулей `orchestrator/` (кроме `orchestrator/cycle_hint.py`)
нет строковых литералов, собирающих `artel.py run {` или `artel.py auto {`.
Ловит мутацию: в одном из тринадцати мест осталась или появилась голая
подсказка.

AC-8. `orchestrator/cycle_hint.py` не содержит SQL (`SELECT`/`execute`), а
вызов `launch_hint` во всех трёх случаях не меняет содержимого таблиц
наблюдений в БД (снимок до и после совпадает). Ловит мутацию: подсказка
регистрирует или включает наблюдение сама.

AC-9. Сквозные тесты через команды пульта: `new --tz`
(`orchestrator/catalog.py`) печатает подсказку запуска со строкой
`observe register` (случай «в»); остановка `auto` командой `stop`
(`orchestrator/auto.py`) при наблюдении текущей сессии печатает
подсказку с `observe add <ID> --tasks <id>` (случай «б»). Ловит мутацию:
место вызова печатает старую строку мимо функции.

## Оценка объёма и деление
Сработавший сигнал: число файлов зоны ≥ 5 (девять файлов вне общих зон).

**Обоснование монолита** (материал для решения Оператора на гейте SPEC):
правка в каждом из восьми модулей мест вызова — замена одной f-строки
вызовом `launch_hint`, объём каждой мал; содержательная механика одна —
`cycle_hint.py` + функция чтения в `store.py`. AC-7 (нет голых
подсказок нигде в `orchestrator/`) и AC-9 (сквозные тесты) проверяют
замену во всех тринадцати местах сразу: часть «модуль без мест вызова»
мержится мёртвым кодом и не закрывает находку, а часть «половина мест»
оставляет Оператору две разные формы подсказки и красный AC-7.
Альтернатива, если Оператор предпочтёт нарезку: (1) `cycle_hint.py` +
`store.py` + AC-1…AC-6, AC-8; (2) тринадцать мест вызова + AC-7, AC-9.
Рамка ТЗ — $30 на задачу целиком.

## Не входит
- Изменение поведения `run`/`auto`/`observe`/`watch` и порогов свежести
  (`OBSERVATION_STALE_SECONDS`).
- Автоматическая регистрация наблюдения пультом вместо подсказки.
- Подсказки прочих команд (`advance`, `approve`, `budget`, `reject`,
  `zone-release`) — кроме строки запуска цикла внутри тех же сообщений.
- Вариант `--attach` в подсказке.
- Правка `docs/operator-session.md`.
- Ручная регенерация `docs/codebase-map.md` — её делает пульт после мержа.
- Правка файлов «только чтение» ТЗ: `orchestrator/artel.py`,
  `orchestrator/watch.py`, `orchestrator/config.py`,
  `orchestrator/session.py`, `orchestrator/schema.py`,
  `tests/test_answer.py`, `tests/test_auto_cycle.py`,
  `tests/test_step_cost.py`, `tests/test_observation_edges.py`,
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`, прочие модули
  `orchestrator/` вне зон.
- Зелёность существующих тестов (`tests/test_answer.py:393`,
  `tests/test_auto_cycle.py:982`, `tests/test_step_cost.py:1053` и весь
  `tests/`) — её держит пульт; строка запуска начинается как сегодня,
  поэтому их проверки вхождения подстроки остаются верными.

## Материалы
- ТЗ: `tasks/01M3XTFJCC5TG63FHW907GQM4D/TZ.md` (факты со ссылками на
  строки origin/main 83a9c96e).
- `orchestrator/store.py` — `matching_observation`,
  `disable_task_observation`, `add_observation_tasks`, `stop_observation`.
- `orchestrator/artel.py` — `_cycle_args`, `_launch_detached`, запрет
  ролям отсоединённых `run`/`auto` и `observe register|add`: все подсказки
  адресованы только Оператору.
- `orchestrator/auto.py` `auto_stop` печатает `  дальше: {hint}`.
- Пример полной строки: `docs/operator-session.md:241`.
