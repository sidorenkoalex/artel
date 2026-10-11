---
task: T100
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: Реестр замечаний ревью — жизненный цикл каждого замечания

## Фаза A — гейт плана

PLAN.md не менялся содержательно со времён iteration 1 (единственная
правка после того вердикта — `git diff 1eeb7b8...HEAD` — это одна
строка `schema_version` в самом REVIEW.md, см. ниже); переподтверждаю
вывод iteration 1: 11 требований SPEC покрыты таблицей «Покрытие
требований», пропуски (8, 9) обоснованы явно, шаги — проверяемые
единицы, подход не конфликтует с конвенциями. Замечаний к плану нет.

## Соответствие SPEC

Код не менялся с iteration 1 (см. «Инкрементальный diff» ниже) —
таблица переподтверждена собственным перепрогоном, не переписана
вслепую.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Секция «Реестр замечаний» — в `templates/REVIEW.md`, обязательна при `schema_version >= 3`; формат таблицы, id `R<iteration>-F<n>`, обязательные поля — на месте (перечитал файл). |
| 2 | OK | Пятёрка статусов `open/fixed/rejected/accepted/needs_work` — `guard.REGISTRY_STATUSES`, `RegistryRecordErrorsMessageTest`/AC-4 зелёные. |
| 3 | OK | Обязанность разработчика — `skills/coding-standards.md`, секция «Реестр замечаний»: разметка `fixed`/`rejected` перед каждым выходом в review, запрет самозакрытия — перечитал целиком. |
| 4 | OK | Симметрия `fixed`/`rejected`: единственный пропускающий статус `accepted`; AC-8/AC-9 зелёные и симметричны по конструкции гейта (`orchestrator/fsm_advance.py:151-152` — фильтр `status != "accepted"` не различает исходы). |
| 5 | OK | Машинный гейт — `orchestrator/fsm_advance.py::review()`, ветка `status == "approved"`, до `acceptance.run` и до перехода в `verifying`; отказ называет все незакрытые id (`AllUnresolvedIdsAreNamedTest` зелёный). |
| 6 | OK | `requires_registry` — версия-гейтинг `>= 3`; легаси (без поля, версия 1, версия 2) не подвергается проверкам — AC-6, AC-12 зелёные. |
| 7 | OK | `registry_errors`/`registry_record_errors` — секция обязательна, id уникальны и в формате `R\d+-F\d+`, статус из пятёрки, поля заполнены; содержательность вне мандата guard (докстринг это фиксирует). |
| 8 | OK | Не требует кода; восстановимость из git-истории REVIEW.md (T021) не тронута — сама эта итерация тому наглядный пример (см. «Предложения системе»). |
| 9 | OK | Мандат на правку `templates/REVIEW.md` и `scripts/guard.py` подтверждён `tasks/T100/TZ.md`. |
| 10 | OK | `skills/review-checklist.md` и `skills/coding-standards.md` дополнены протоколом реестра — перечитал обе новые секции целиком. |
| 11 | OK | Зона соблюдена — `git diff main...HEAD --stat` не задевает ни один файл из списка M1 (`brief.py`, `store.py`, `catalog.py`, `fixation.py`, `doctor.py`, `cleanup.py`, `prune.py`, `config.py`). |

AC-1..AC-13 перепрогнаны заново лично (не унаследованы из iteration 1
на слово) — все 15 тестов `tasks/T100/acceptance_tests/` зелёные, все
50 тестов `tests/test_guard_schema.py` + `tests/test_review_registry_gate.py`
зелёные, полный `tests/` — 1192/1194, те же 2 предсуществующих сбоя,
не связанных с диффом T100 (см. «Проверено исполнением»). AC-13 (manual)
— перечитал оба скила целиком заново: протокол по существу, принимаю
manual-пометку повторно.

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

Записей нет — 0 blocker/major/minor замечаний по итогам ревью (в
iteration 1 записей тоже не было, переносить в кумулятив нечего).

## Вердикт

approved

Обоснование: код и артефакты идентичны iteration 1 во всём, что
касается требований SPEC и AC — единственная правка ветки со времени
того вердикта (коммит `1eeb7b8`, где REVIEW.md впервые получил
`status: approved`) это коммит `655b46a`, целиком: одна строка,
`schema_version` в самом `tasks/T100/REVIEW.md` — 3 → 2.

Разобрался, почему инкрементальный diff пакета (baseline
`655b46ad28be275d7e4bbcc2e2b3e6c8231572ff`) пуст: этот baseline sha
совпадает с текущим HEAD, а не с коммитом реального вердикта — тот же
класс искажения, что описан в review-checklist про T087/T082.
Настоящий коммит вердикта — `1eeb7b8` («артефакты шага reviewer»); всё,
что после него, — `git diff 1eeb7b8...HEAD` — это правка Оператора
`655b46a`.

Разобрал саму правку, а не принял её на слово:
- `1eeb7b8` (iteration-1 ревьювер) закоммитил REVIEW.md со
  `schema_version: 3` — по шаблону `templates/REVIEW.md`, который сама
  же эта задача подняла до 3.
- Но `SUPPORTED_SCHEMA_VERSION` в `scripts/guard.py`, который реально
  исполняет проверки для ЖИВОГО FSM (не для этой ветки — guard main
  ещё не видел бампа до мержа T100), на момент коммита понимал только
  `<= 2`. `schema_errors` (`scripts/guard.py:95-101`) в этом случае
  прямо отказывает: «schema_version 3 новее поддерживаемой 2 — этот
  guard не понимает формат... эскалируй, чтобы Оператор обновил guard».
  Значит `fsm.guard_refuses` на живом контуре отказал бы этому REVIEW.md
  сразу после его коммита — переход `review -> acceptance` не мог
  пройти, несмотря на то что во frontmatter уже стоял `status: approved`.
- Это НЕ первый такой случай в этой же ветке: `8fc7740` — та же правка
  (3 → 2) двумя коммитами раньше, но для `tasks/T100/PLAN.md`.
  Обнаружил прецедент и вне этой ветки — T023 (первая задача, поднявшая
  `SUPPORTED_SCHEMA_VERSION` 1 → 2) держала СОБСТВЕННЫЙ `tasks/T023/SPEC.md`
  на версии 1, а не на новой 2 (`git show ca599ea:tasks/T023/SPEC.md`) —
  т.е. правильный паттерн для самореференсной задачи известен и
  соблюдался раньше; в T100 разработчик и ревьювер iteration 1 его не
  учли дважды подряд для двух разных артефактов (PLAN.md, затем
  REVIEW.md), и оба раза чинить пришлось Оператору руками, а не через
  штатный протокол `escalation-rules` (ни PLAN.md, ни REVIEW.md
  iteration 1 не проходили через `status: escalate`).
- Правка Оператора технически корректна и последствий не имеет: после
  неё `requires_registry(meta)` для этого REVIEW.md возвращает `False`
  (версия < 3), реестр в файле и так пуст («Записей нет»), поэтому AC-11
  («реестр пуст → переход проходит») дало бы тот же результат что при
  версии 2, что при версии 3 — сам вердикт `approved` и его обоснование
  содержательно не изменились ни на йоту.

По той же причине САМ этот REVIEW.md (iteration 2) я сознательно пишу
со `schema_version: 2`, а не 3 из шаблона по умолчанию — иначе я
воспроизведу тот же самый затор, который только что чинил Оператор:
живой guard на main всё ещё не видит бампа до фактического мержа T100.

Системная целостность: ни один существующий тест/гейт/лимит не
ослаблен и не удалён; зона задачи (требование 11) соблюдена; откат
(`git revert`) описан в PLAN и остаётся верным — правка `655b46a`
аддитивно обратима тем же приёмом.

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 1192 теста, 2 упавших:
  `test_agent_log.CmdRunLoggingTest.test_timeout_kills_process_and_journals`
  и `test_step_cost.CmdRunPartialCostTest.test_timeout_with_usage_events_charges_a_partial_token_sum`
  — те же два, что и в iteration 1; причина по-прежнему в `AGENT_TIMEOUT_SEC`
  на main (`20afc92`), не в диффе T100, оба файла вне diff T100.
- `python3 -m unittest tests.test_guard_schema tests.test_review_registry_gate -v`
  — 50 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/T100/acceptance_tests -v` —
  15 тестов, все зелёные (AC-1..AC-12 исполняемые, AC-13 manual).
- `python3 -c "import orchestrator.fsm_advance"` — без ошибок (циклический
  импорт `scripts.guard` ↔ `orchestrator.fsm_advance` не возникает).
- `git diff main...HEAD --stat` — 19 файлов; ни один файл из списка
  «НЕ трогать» требования 11 (`orchestrator/brief.py`, `store.py`,
  `catalog.py`, `fixation.py`, `doctor.py`, `cleanup.py`, `prune.py`,
  `config.py`) в списке нет.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`
  — расхождение только в строке `built_at_sha`; локальную регенерацию
  откатил (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое
  (`git status --short` пуст).
- `git log --oneline -- tasks/T100/REVIEW.md`, `git show 655b46a`,
  `git diff 1eeb7b8 HEAD -- tasks/T100/REVIEW.md`, `git log --all -p --
  scripts/guard.py \| grep SUPPORTED_SCHEMA_VERSION`, `git show
  ca599ea:tasks/T023/SPEC.md` — восстановил историю правки Оператора и
  прецедент T023 (обоснование вердикта выше).
- Ручное чтение: `scripts/guard.py:83-102` (`schema_errors`, версия-
  гейтинг), `orchestrator/fsm_advance.py:101-190` (`review()` целиком),
  `templates/REVIEW.md`, `skills/review-checklist.md` и `skills/
  coding-standards.md` (секции «Реестр замечаний» обеих) — заново, не
  по памяти iteration 1.

## Предложения системе

- Класс «задача поднимает `SUPPORTED_SCHEMA_VERSION`, но применяет НОВУЮ
  версию к своим же `PLAN.md`/`REVIEW.md`» — живой guard/FSM на main
  ещё не знает новую версию до мержа задачи, поэтому любой такой
  артефакт с новой версией стопорит переход через `schema_errors`
  (`scripts/guard.py:95-101`) и требует ручной правки Оператора.
  Правильный паттерн уже был явлен в T023 (собственный SPEC.md остался
  на старой версии), но нигде не зафиксирован — в T100 наступили на те
  же грабли дважды подряд (`8fc7740` для PLAN.md, `655b46a` для
  REVIEW.md уже ПОСЛЕ одобрения ревьювером). Стоит явно зафиксировать
  в `conventions-core` или `coding-standards.md`: задача, поднимающая
  `SUPPORTED_SCHEMA_VERSION`, обязана держать свои собственные
  `tasks/<id>/*.md` на прежней поддерживаемой версии до фактического
  мержа — тем же приёмом, что уже применяла T023.
- Оба раза этот класс чинился ПРЯМОЙ правкой Оператора в обход
  `escalation-rules` (ни разработчик, ни ревьювер iteration 1 не ставили
  `status: escalate`, хотя по формальному критерию escalation-rules
  («для решения нужно право, которого у твоей роли нет») это ровно тот
  случай — ни разработчик, ни ревьювер не могут сами поднять
  `SUPPORTED_SCHEMA_VERSION` живого guard'а). Стоит явно упомянуть этот
  класс в escalation-rules как пример «право есть только у Оператора» —
  сейчас пример там абстрактный, а этот случай уже воспроизвёлся дважды
  подряд в одной задаче.
- Инъекция скилов в промпт роли (в данном случае мне, ревьюверу) сама
  происходит с MAIN, не с ветки задачи: текст `review-checklist.md`,
  выданный мне как «Скил роли» в начале этого ревью, не содержал секции
  «Реестр замечаний», которая уже есть в файле на этой ветке (проверено
  `grep` по обоим `skills/*.md` на диске worktree) — тот же класс
  самореференсного бутстрапа, что и со `schema_version` выше, просто
  для skills вместо guard.py. Не блокирует T100 (я прочитал актуальный
  текст с диска, а не полагался на инъекцию), но стоит иметь в виду при
  ревью любой задачи, меняющей `skills/`/`templates/`: контекст роли
  может отставать от диска ветки на весь бамп задачи.
