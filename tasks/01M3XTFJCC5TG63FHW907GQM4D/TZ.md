---
task: 01M3XTFJCC5TG63FHW907GQM4D
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Подсказки пульта называют полный порядок запуска цикла после наблюдения фоновых задач

# ТЗ: Подсказки пульта называют полный порядок запуска цикла после наблюдения фоновых задач

Источник: ревизия 02.10.2026 работы пульта на Codex, находка по задаче
01M3SX69E8P64D77J1XTHMHE40 (наблюдение фоновых задач, мерж 890c96e6):
после мержа отсоединённый запуск цикла требует наблюдения и аргументов
клиента и чата, а подсказки пульта по-прежнему печатают голые
`artel.py run <id>` / `artel.py auto <id>`. Оператор выполняет
подсказку дословно и получает отказ.

Факты (origin/main 83a9c96e):
- `run`/`auto` без `--attach` отсоединяются от сессии и требуют
  `--client codex|claude --chat <id>`: справка `orchestrator/artel.py:90-98`
  и `:125-126`; разбор аргументов отказывает без них —
  `orchestrator/artel.py:651-656` (`_cycle_args`, текст «для
  отсоединённого запуска нужны --client codex|claude и --chat <непустой ID>»).
- Кроме аргументов, запуск требует активного наблюдения той же сессии,
  проекта, клиента и чата, в котором задача включена, и свежей связи с
  `watch`: `orchestrator/artel.py:677-689` (`_launch_detached`: отказы «нет
  активного наблюдения…», «наблюдение зарегистрировано, но связи с watch
  ещё нет», «связь наблюдения протухла»); порог свежести —
  `orchestrator/config.py:70-71` (`OBSERVATION_STALE_SECONDS` = 90 с).
- Наблюдение заводится командой `observe register --client … --chat …
  --tasks <id>` (`orchestrator/artel.py:128`), которая печатает
  `{"id": "<ID наблюдения>"}` (`orchestrator/artel.py:784`); задача
  добавляется в существующее наблюдение командой `observe add <ID
  наблюдения> --tasks <id>` (`orchestrator/artel.py:129`,
  `orchestrator/store.py:70` `add_observation_tasks`).
- Связь наблюдения поддерживает только `watch --observation <ID>`: каждый
  цикл опроса обновляет `last_seen_at` (`orchestrator/watch.py:323`,
  `orchestrator/store.py:91` `touch_observation`); наблюдение чужой сессии
  `watch` отвергает (`orchestrator/watch.py:290`).
- `stop <id>` выключает задачу во всех наблюдениях
  (`orchestrator/artel.py:1025`, `orchestrator/store.py:85`
  `disable_task_observation`): после `stop` повторный запуск без
  `observe add` откажет «нет активного наблюдения».
- Процессу роли отсоединённые `run`/`auto` и `observe register|add` вообще
  запрещены (`orchestrator/artel.py:1277-1284`), то есть все подсказки
  ниже адресованы только Оператору.
- Голые подсказки запуска цикла (тринадцать мест):
  `orchestrator/fsm.py:851` (`run`, запуск разработчика),
  `orchestrator/fsm.py:856` (`run`, запуск test_author),
  `orchestrator/fsm.py:1005` (`run`, после снятия эскалации),
  `orchestrator/fsm.py:1105` (`auto`, возврат SPEC аналитику),
  `orchestrator/auto.py:123` (`auto`, остановка по `stop`),
  `orchestrator/auto.py:193` (`auto`, потолок ожидания зоны),
  `orchestrator/auto.py:200` (`auto`, потеря lease в ожидании зоны),
  `orchestrator/auto.py:732` (`auto`, лимит шагов за вызов),
  `orchestrator/answer.py:276` (`auto`, после `answer`),
  `orchestrator/catalog.py:489` (`run`, после `new --tz`),
  `orchestrator/budget.py:495` (`run`, после поднятия потолка),
  `orchestrator/ci_rerun.py:246` (`auto`, после зелёного повтора CI),
  `orchestrator/advance_gates/tests_writing.py:28` (`run`, прогон
  ревьювера; в исходном перечне находки его не было). Других строк вида
  `artel.py run|auto {task_id}` в `orchestrator/` нет (проверено поиском
  по origin/main). Каждое место собирает строку само, общей функции нет.
- Подсказки остановки `auto` печатаются строкой `  дальше: {hint}`
  (`orchestrator/auto.py:599`, `auto_stop`).
- Существующие тесты проверяют подсказки только вхождением подстроки:
  `tests/test_answer.py:393` («дальше: artel.py auto <id>»),
  `tests/test_auto_cycle.py:982` («artel.py auto <id>»),
  `tests/test_step_cost.py:1053` («дальше: artel.py run <id>»). Если
  строка запуска начинается так же, как сегодня, они остаются зелёными
  без правки.
- Пример полной строки запуска уже есть в
  `docs/operator-session.md:241` (`artel.py auto T123 --client codex
  --chat chat-123`), но порядок «наблюдение → watch → запуск» там не
  назван одной последовательностью.

Требуется:
1. Новый модуль `orchestrator/cycle_hint.py` — единственное место, где
   формируется подсказка запуска цикла. Публичная функция (имя выбирает
   SPEC), принимает соединение с БД, id задачи и команду (`run` или
   `auto`) и возвращает готовые строки подсказки. Все тринадцать мест из
   «Фактов» печатают (или кладут в `Stop.hint`) результат этой функции и
   собственной строки с `artel.py run {…}` / `artel.py auto {…}` больше не
   собирают. Пояснение в скобках, которое место печатает сегодня
   («запуск разработчика», «продолжит отсюда» и т. п.), сохраняется —
   функция принимает его параметром.
2. Первая строка подсказки начинается как сегодня — `artel.py <cmd> <id>`
   (с тем же префиксом «дальше:»/«затем:» в месте вызова) — и продолжается
   аргументами `--client … --chat …`. Под ней — строка «сначала:» (или
   аналог, выбирает SPEC) с недостающими шагами по порядку. Три случая
   определяются по БД для текущей сессии (`orchestrator/session.py`,
   `resolve_session_id`) и проекта задачи:
   а) есть активное наблюдение, в котором задача включена, — в строку
      запуска подставлены его настоящие `--client` и `--chat`; строка
      «сначала:» называет `artel.py watch --observation <его ID>` как
      фоновую задачу сессии с оговоркой «если ещё не идёт»;
   б) есть активное наблюдение этой сессии и проекта, но задача в нём не
      включена (например, после `stop`), — шаги: `artel.py observe add
      <его ID> --tasks <id>`, затем `watch --observation <его ID>` (если не
      идёт), затем запуск с его `--client`/`--chat`;
   в) активного наблюдения нет — шаги: `artel.py observe register --client
      codex|claude --chat <ID чата> --tasks <id>` (ID наблюдения — из её
      вывода), затем `artel.py watch --observation <ID наблюдения>` фоновой
      задачей сессии, затем `artel.py <cmd> <id> --client codex|claude
      --chat <ID чата>`.
   Наблюдения другой сессии, другого проекта и прекращённые
   (`state` не `active`) не учитываются: для них подсказка — случай «в».
   Если активных наблюдений несколько, берётся то же, что выбрал бы
   `matching_observation`, — с самой свежей связью.
3. Чтение наблюдений сессии и проекта — новой функцией чтения в
   `orchestrator/store.py` рядом с прочими функциями наблюдений; запросы
   SQL в `orchestrator/cycle_hint.py` не пишутся. Функция только читает:
   подсказка ничего не регистрирует и не меняет в БД.
4. Строка запуска в случаях «а» и «б» должна приниматься разбором
   `orchestrator/artel.py` (`_cycle_args`) без отказа; поведение самих
   команд `run`/`auto`/`observe`/`watch` не меняется.
5. Тесты в `tests/test_cycle_hint.py` (на временной БД, как соседние
   тесты наблюдения):
   - случай «в»: подсказка содержит `observe register`, `--tasks <id>`,
     `watch --observation`, `<cmd> <id> --client`, и они идут в этом
     порядке. Ловит мутацию: шаг наблюдения или `watch` выпал из
     подсказки либо порядок шагов перепутан;
   - случай «а»: подставлены `--client`/`--chat` и ID наблюдения из БД,
     `observe register` и `observe add` не предлагаются. Ловит мутацию:
     подсказка игнорирует существующее наблюдение и печатает заполнители;
   - случай «б» (наблюдение есть, задача выключена тем же путём, что
     `stop`, — `store.disable_task_observation`): предлагается `observe
     add <ID> --tasks <id>`, а не `observe register`. Ловит мутацию:
     после `stop` подсказка ведёт к отказу «нет активного наблюдения»;
   - наблюдение другой сессии и прекращённое наблюдение дают случай «в».
     Ловит мутацию: подставлены клиент и чат чужого или остановленного
     наблюдения;
   - строка запуска случая «а» проходит `artel._cycle_args` и возвращает
     те же клиент и чат. Ловит мутацию: формат флагов подсказки разошёлся
     с разбором команды;
   - проверка текста модулей `orchestrator/` (кроме
     `orchestrator/cycle_hint.py`): нет строковых литералов, собирающих
     `artel.py run {` или `artel.py auto {`. Ловит мутацию: в одном из
     тринадцати мест осталась или появилась голая подсказка;
   - минимум два сквозных теста через команды пульта: `new --tz`
     (`orchestrator/catalog.py`) и остановка `auto` командой `stop`
     (`orchestrator/auto.py`, случай «б») печатают подсказку с шагами
     наблюдения. Ловит мутацию: место вызова печатает старую строку
     мимо функции.
6. Существующие тесты из «Фактов» не правятся и остаются зелёными.

Зоны: orchestrator/cycle_hint.py, orchestrator/store.py,
orchestrator/fsm.py, orchestrator/auto.py, orchestrator/answer.py,
orchestrator/catalog.py, orchestrator/budget.py, orchestrator/ci_rerun.py,
orchestrator/advance_gates/tests_writing.py, tests/test_cycle_hint.py.

Приложением: нет.

Только чтение (не менять): orchestrator/ (кроме файлов из «Зон»), orchestrator/artel.py, orchestrator/watch.py,
orchestrator/config.py, orchestrator/session.py, orchestrator/schema.py,
tests/test_answer.py, tests/test_auto_cycle.py, tests/test_step_cost.py,
tests/test_observation_edges.py,
tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py,
docs/operator-session.md, tasks/.

Не входит: изменение поведения `run`/`auto`/`observe`/`watch` и порогов
свежести; автоматическая регистрация наблюдения пультом вместо
подсказки; подсказки прочих команд (`advance`, `approve`, `budget`,
`reject`, `zone-release`); вариант `--attach` в подсказке; правка
`docs/operator-session.md`; ручная регенерация `docs/codebase-map.md`
(её делает пульт после мержа).

Рамка: $30.
