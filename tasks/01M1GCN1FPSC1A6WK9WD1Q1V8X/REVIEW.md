---
task: 01M1GCN1FPSC1A6WK9WD1Q1V8X
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: Лимиты пакетов контекста и гейт ёмкости диффа ревью

## Фаза A: гейт плана

PLAN.md не менялся с итерации 1 (в инкрементальном diff этой итерации
файла нет; подтверждено `git show --stat` коммита `7fe05c5`, где
PLAN.md отсутствует в списке изменённых). План уже был принят в
итерации 1 — расхождения тогда были найдены на уровне реализации, не
подхода. Повторно проходить Фазу A нечего: подход не изменился.

## Фаза B: ревью MR

Итерация 2 — точечные правки по R1-F1..R1-F4 (коммит `7fe05c5`) плюс
техническая подтяжка main (коммит `803af0a`, только
`CLAUDE.md`/`docs/operator-gates.md`/`docs/operator-session.md` —
операторский нормативный документ, не код этой задачи; `*.py` подтяжка
не затронула, поэтому отдельной регенерации карты после неё не
требовалось). `docs/codebase-map.md` в коммите `7fe05c5` регенерирован
тем же коммитом, что и правки `*.py` (конвенция `conventions-core`) —
`built_at_sha` в нём указывает на родителя (`12022a3`), что ожидаемо
(карта не может знать sha коммита, в который сама войдёт) и не
противоречит правилу «сверяй карту по содержимому» (`review-checklist`,
built_at_sha).

Прочитан код всех четырёх правок (`orchestrator/context_package.py`,
`orchestrator/fsm_advance.py`, `orchestrator/brief.py`,
`orchestrator/review.py`) и оба места, откуда `discipline()` вызывается
(`review.py:195`, `brief.py:364`) — оба обновлены на новую сигнатуру
списка компонентов, других вызывающих в живом коде нет
(`grep -rn "context_package.discipline"`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (опись) | OK | Без изменений с итерации 1 — подтверждено повторно тестами `test_ac1_manifest.py`. |
| 2 (константы) | OK | Без изменений с итерации 1. |
| 3 (дисциплина частей) | OK | R1-F1 закрыт: `_pack_components` (`context_package.py:71-119`) трактует каждый компонент как атомарную единицу упаковки — компонент не разрывается между частями, если его размер (с учётом `sep`) не превышает потолок части; крупнее потолка — по-прежнему делится по строкам (`split_into_parts`), без потери байт. Проверено чтением кода: инвариант «каждая произведённая часть ≤ `CONTEXT_PART_MAX_BYTES`» держится за счёт `flush()` до превышения потолка, не после. `review.py:195` и `brief.py:364` передают списки компонентов, не склеенный текст — подтверждено `grep`. Регресс воспроизведён вручную (см. «Проверено исполнением») — на том же сценарии, что дал R1-F1 в прошлой итерации (заполнитель у границы потолка + маленький «diff»-компонент), diff больше не разорван. |
| 4 (diff той же дисциплиной) | OK | AC-8 закрыт вместе с R1-F1 — diff в `review.review_package` идёт отдельным элементом списка `parts` (`review.py:190`), поэтому упаковывается как атомарная единица наравне с остальными компонентами. AC-9/AC-10 — без изменений с итерации 1. |
| 5 (гейт ёмкости) | OK | R1-F2 закрыт: `_capacity_gate_refuses` (`fsm_advance.py:409-422`) теперь читает третий элемент `git_diff_part` (причину сбоя) и на непустой причине отказывает переходу fail-closed, журналируя отказ через `store.journal` — тот же приём, что уже применён в этом файле для лока `acceptance_tests/` (строки ~484-498). Добавленное по ходу фикса исключение для внешнего (не self) target (`fsm_advance.py:409-410`) подтверждено существующим тестом-прецедентом `tests/test_git_fixation.py::ExternalTargetAdvanceIgnoresDirtyCheckTest` — `tasks/<id>/` внешнего target закономерно не закоммичен в `config.ROOT` до перехода, буквальный fail-closed заблокировал бы такой переход навсегда; SPEC не различает target явно, но и не запрещает эту защиту — приёмочные тесты AC-12..AC-16 используют self target (`GateSandbox` создаёт задачу через `catalog.cmd_new` без указания внешнего target) и не задеты исключением. |
| 6 (инкрементальный diff) | OK | Без изменений с итерации 1. |
| 7 (протокол в скилах) | OK | Без изменений с итерации 1 (скилы не тронуты этой итерацией). |
| 8 (тесты) | OK | Оба сценария R1-F1/R1-F2 теперь покрыты регресс-тестами: `tests/test_review_package.py::DisciplineComponentBoundaryTest` (3 теста) и `tests/test_capacity_gate.py` (5 тестов, включая fail-closed на сбое git и пропуск для внешнего target). Полный набор `tests/` (1233 теста) и все 36 приёмочных тестов задачи — зелёные. |
| 9 (алерт на пропуск карты) | OK | R1-F4 закрыт: `_fresh_map_text_and_note` (`brief.py`) возвращает текст карты и пометку стухлости раздельно; `developer_brief` (`brief.py:343-354`) считает опись (`_manifest_component`) по голому `map_text`, пометку приклеивает снаружи рендера компонента — sha256/размер в описи теперь совпадают с `sha256sum docs/codebase-map.md` даже когда карта стухшая. `_handle_map_size_alert` по-прежнему вызывается с тем же голым `map_text` — алерт AC-21/AC-22 не задет разделением. |

## Замечания

Пусто — обе фазы пройдены без замечаний. Оба major (R1-F1, R1-F2) и оба
minor (R1-F3, R1-F4) из итерации 1 подтверждены исправленными чтением
кода и тестами; новых дефектов в инкрементальном diff (коммиты
`7fe05c5`, `803af0a`) не найдено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/context_package.py:71-119 (используется из orchestrator/review.py:195, orchestrator/brief.py:364) | деление тела пакета на части шло по строкам всего тела, не по границам компонентов/diff | нарушение AC-8 в реалистичном сценарии, не было покрыто тестами | Проверено: `_pack_components` трактует каждый компонент атомарно, оба вызывающих передают списки, регресс-тест `DisciplineComponentBoundaryTest` зелёный, ручная проверка сценария из R1-F1 больше не воспроизводится. |
| R1-F2 | accepted | orchestrator/fsm_advance.py:409-422 (`_capacity_gate_refuses`) | гейт отбрасывал причину сбоя git и мерил байты строки-ошибки вместо реального diff | fail-open вместо fail-closed при сбое git | Проверено: третий элемент `git_diff_part` читается, непустая причина — журналируемый fail-closed отказ; внешний target обоснованно исключён (прецедент `ExternalTargetAdvanceIgnoresDirtyCheckTest`); 5 регресс-тестов в `tests/test_capacity_gate.py` зелёные. |
| R1-F3 | accepted | orchestrator/brief.py, orchestrator/context_package.py:21-22 | `component_hash` и `sha256_of` — две идентичные реализации sha256 | лишнее дублирование логики хэширования | Проверено: `component_hash` делегирует `context_package.sha256_of`, собственной копии `hashlib.sha256(...)` в brief.py больше нет (`grep` не находит `import hashlib` в brief.py). |
| R1-F4 | accepted | orchestrator/brief.py (`_fresh_map_text_and_note`, `developer_brief:343-354`) | sha256/размер карты в описи считались по тексту с примешанной пометкой «КАРТА НЕАКТУАЛЬНА» | sha256 из описи мог разойтись с `sha256sum docs/codebase-map.md` | Проверено: текст и пометка разделены, опись считается по голому тексту карты; регресс-тест `DeveloperBriefStaleMapManifestTest` зелёный. |

Статус — одно из: `open` (заведено ревьювером, ждёт разработчика),
`fixed` (разработчик отметил исправленным), `rejected` (разработчик
отклонил с обоснованием, код не менялся), `needs_work` (ревьювер
вернул на новую попытку), `accepted` (ревьювер подтвердил закрытие —
терминальный статус).

## Вердикт

approved — реестр замечаний закрыт целиком (все четыре записи в
`accepted`), новых blocker/major/minor в инкрементальном diff этой
итерации не найдено, полный набор тестов и приёмочные тесты задачи
зелёные.

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1233 теста, все зелёные (было 1224 в итерации 1; +9 новых тестов этой итерации: 5 в `test_capacity_gate.py`, 3 в `DisciplineComponentBoundaryTest`, 1 в `DeveloperBriefStaleMapManifestTest`).
- `python3 -m unittest discover -s tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests -p "test_ac*.py"` — 36 тестов (AC-1..AC-22), все зелёные.
- `python3 -m unittest tests.test_review_package tests.test_brief tests.test_capacity_gate` — 99 тестов, все зелёные (изолированный прогон затронутых модулей, включая новый `test_capacity_gate.py`).
- `grep -rn "REVIEW_DIFF_MAX_LINES|REVIEW_PACKAGE_MAX_BYTES|truncate_diff|truncate_package" orchestrator/ tests/ scripts/` — только упоминания в комментариях/докстрингах («замена прежнего...»), ни одного живого символа с этими именами.
- `grep -rn "context_package.discipline" orchestrator/ tests/` — оба вызывающих (`review.py:195`, `brief.py:364`) передают список компонентов; сигнатура согласована по всему коду.
- Ручная проверка регресса R1-F1: воспроизведён точный сценарий прошлой итерации (`context_package.discipline([filler, small_component])` с заполнителем у границы `CONTEXT_PART_MAX_BYTES` и маленьким компонентом-диффом из нескольких строк, тот же тест уже присутствует как `DisciplineComponentBoundaryTest.test_a_small_component_after_a_near_cap_filler_is_never_split`) — маленький компонент теперь целиком в одной части, разрыва нет.
- Ручная проверка регресса R1-F2: чтение `fsm_advance.py:409-422` — третий элемент `_review_git_diff_part` (`reason`) читается и используется для fail-closed отказа; `tests/test_capacity_gate.py::CapacityGateGitFailureTest` (4 теста) подтверждает поведение на обычном и Unicode-сбое git, а `CapacityGateExternalTargetTest` — что внешний target гейт не проверяется вовсе (обоснованное расширение сверх буквы SPEC, оправданное существующим прецедентом `ExternalTargetAdvanceIgnoresDirtyCheckTest`).
- `git show --stat 7fe05c5` — собственные изменения задачи (без учёта подтяжки main) ограничены `docs/codebase-map.md`, `orchestrator/{brief,context_package,fsm_advance,review}.py`, `tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/REVIEW.md`, `tests/{test_brief,test_capacity_gate,test_review_package}.py` — совпадает с «Влияние на систему» PLAN.md, вне зоны задачи ничего не тронуто.
- `git show --stat 803af0a` — подтяжка main принесла только `CLAUDE.md`/`docs/operator-gates.md`/`docs/operator-session.md` (нормативные документы Оператора, не относящиеся к этой задаче), `*.py` не задет — регенерация карты после подтяжки не требовалась.

## Предложения системе

- Прежнее предложение (composed-сценарий для приёмочных тестов вида
  «X не превышает потолок») остаётся в силе — в этой итерации его
  закрыл сам разработчик регресс-тестом на уровне `tests/`, а не
  приёмочных тестов, что для локальной задачи достаточно, но для
  будущих задач с похожей дисциплиной «раздели на части» стоит
  закладывать composed-сценарий сразу в `acceptance_tests/`, а не
  только постфактум в `tests/`.
