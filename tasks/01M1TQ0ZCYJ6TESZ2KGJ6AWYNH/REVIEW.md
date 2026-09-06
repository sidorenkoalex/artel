---
task: 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: артефактная ветка новой задачи заводится от origin/main, а не от пина

## Замечание к пакету ревью (диагностика перед вердиктом)

Инкрементальный diff пакета (от sha предыдущего вердикта
`fbc398e00281938f9bbc07e663780be132edbc71` до HEAD) на 99% состоит из
содержимого ЧУЖИХ задач (стоп-кран волны 01M1THKPNZ…, ADR-0014 часть 1
01M1THKTJ7…, R3-рефакторинг `fsm.py`/`pull.py` 01M1TKP08P…) — это
файлы одного-единственного коммита `ab4f138a` («подтяжка main»,
merge fbc398e0+9f1e468c), а не работа этой задачи. Причина: sha,
который пакет взял за «предыдущий вердикт» (`fbc398e0`), — это
собственный коммит РАЗРАБОТЧИКА («R2-F3 — тест…»), а не коммит
ревьювера: REVIEW.md не коммитится в кодовую ветку (артефакты — только
через автокоммит в артефактную ветку), поэтому у diff пакета попросту
нет надёжной точки отсчёта на этой ветке — тот же класс, что уже
описан в review-checklist («Инкрементальный diff пакета»), но новый
подслучай: sha указывает не на устаревший автокоммит роли, а на
последний код-коммит РАЗРАБОТЧИКА перед подтяжкой main.

Восстановил фактический материал вручную:
- `git log --oneline task/01m1tq0zcyj6tesz2kgj6awynh-artefaktnaya-vetka-novoy-zadac`
  и `git log --oneline --all artifact/01m1tq0zcyj6tesz2kgj6awynh` —
  восстановлена хронология обеих веток (код и артефакты) с точными
  таймстампами (`git log -1 --format="%cI"`).
- `git show <sha> --stat`/`git show <sha>` по каждому коммиту задачи
  после предыдущего вердикта (`9f8b3f2f`, `300d1bd8`, `fbc398e0` — код;
  `c3c8584c`, `cce12274`, `97dc8d32` — артефакты) — построчно сверил
  содержимое с реестром замечаний итерации 2 и ANSWER-2.
- `git diff de6f5f20 97dc8d32 -- tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/`
  — пусто: залоченная планка (test_author) не тронута повторно с
  итерации 2.
- `git diff de6f5f20 97dc8d32 -- .../REVIEW.md` — реестр R2-F1/F2/F3
  размечен разработчиком `fixed` со ссылками на пункты ANSWER-2.

## Фаза A: проверка плана

PLAN.md не менялся структурно с итерации 2 (тот же подход, те же 4
шага, покрытие требований 1↔1,2; 2↔2; 3↔3; 4↔4 — таблица полна).
Секция «Риски» приросла записями о закрытии эскалации по ANSWER-2 и о
повторных прогонах; появилась секция «## Эскалация (закрыта ANSWER-2 —
история)» с явной пометкой «status артефакта — `ready`, не `escalate`»
— текст вопросов сохранён как история батча, не как действующий
блокер. Замечаний к плану нет.

Наблюдение по процессу (не блокер, см. «Предложения системе» ниже):
таймстампы показывают, что ANSWER-2 (13:46:13) появилась РАНЬШЕ
коммита разработчика «эскалация — AC-2 vs
test_doctor_fix_ignored_artifacts.py» (13:57:37) — то есть разработчик
самостоятельно продублировал тот же анализ и написал в PLAN текст
эскалации с вопросами, на которые Оператор уже ответил за 11 минут до
этого. Итоговое состояние корректно (см. ниже), но это потраченный
впустую заход.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `gitcmd.fetch_head_sha` + `_new_branch_parent` реализуют предпочтение `origin/main` (AC-1/AC-6, без изменений с итерации 1). AC-2: буквальный текст SPEC.md (строки 70-73, «нет сети, нет origin, песочница» → запись в журнал во всех случаях) разошёлся с кодом ещё с 9f8b3f2f, но R2-F1 закрыт легитимным каналом — ANSWER-2 п.1 переинтерпретирует AC-2 операторским решением (ADR-0005: правка SPEC за гейтом — тем же каналом ANSWER, без физической правки текста SPEC.md), по прецеденту ANSWER-1 для требования 2. Код (`orchestrator/artifact_branch.py:119-146`) реализует ровно то, что описывает ANSWER-2: `has_no_remote` → тихий локальный `main` без записи; remote есть, `fetch` не удался → запись с причиной. |
| 2 | OK | Без изменений с итерации 1 — `catalog._new_external_artifact_branch` зовёт `commit_files` безусловно для любого target. |
| 3 | OK | `doctor.check_artifact_branch_parent_ancestry` не менялась ни разу с итерации 1 (сверено `git diff fbc398e0 HEAD -- orchestrator/doctor.py` — пусто). |
| 4 | OK | 4а/4в/4г без изменений (см. «Проверено исполнением»); 4б (AC-7) — прежнее замечание R2-F2 закрыто: `test_ac7_journal_records_fallback_reason.py` сейчас несёт легализованный ANSWER-2 п.2 сценарий («origin настроен, fetch недостижим»), совпадающий байт-в-байт с коммитом `2da2eb9e` — сверено чтением файла и прогоном (1/1 в составе планки). |

## Замечания

Нет новых замечаний. Три замечания итерации 2 (R2-F1/R2-F2/R2-F3)
закрыты легитимным каналом ANSWER-2 — см. реестр.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/SPEC.md:70-73, orchestrator/artifact_branch.py:119-146 | код для «origin отсутствует вовсе» не пишет в журнал, SPEC AC-2 требует запись во всех случаях недоступности origin, SPEC не амендирован | разошедшийся с реализацией SPEC вводит в заблуждение будущего читателя/аудитора | Проверил: ANSWER-2 п.1 — легитимная операторская реинтерпретация AC-2 каналом ANSWER (ADR-0005), тот же приём, что уже принят для ANSWER-1/требования 2 в итерации 1. Код (`_new_branch_parent`) не менялся с 9f8b3f2f и ровно соответствует описанному в ANSWER-2 поведению — сверено чтением и прогоном `tasks/.../acceptance_tests/` (7/7). Закрыто. |
| R2-F2 | accepted | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac7_journal_records_fallback_reason.py | разработчик отредактировал зафиксированный приёмочный тест напрямую, без amend-tests/ADR-0012-коммита | планка приёмки менялась в обход единственного легитимного канала | Проверил: ANSWER-2 п.2 легализует правку прямым сдвигом `tests_locked_sha` Оператором (`3ffa8655 → 2da2eb9e`, журнал «правка планки» 10:31:12Z) — ровно тот канал, что требует ADR-0012/review-checklist для правки зафиксированной планки. Текущее содержимое файла (сверено чтением) — сценарий «origin настроен, fetch недостижим», совпадает с легализованным `2da2eb9e` (промежуточный откат к оригиналу test_author в шаге `300d1bd8`/`c3c8584c` исправлен тем же финальным шагом). Планка `acceptance_tests/` не тронута С ЭТОГО момента (`git diff de6f5f20 97dc8d32 -- .../acceptance_tests/` — пусто). Закрыто. |
| R2-F3 | accepted | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac2_local_main_fallback_parent.py | нет прямой проверки отсутствия записи в журнал для сценария «origin отсутствует вовсе» | регрессия этого класса ловилась только косвенно, посторонним tests/test_branch_freshness_gate.py | Проверил: ANSWER-2 п.3 прямо запрещает доработку залоченной планки и предписывает добавить проверку в общий набор `tests/` — сделано (`tests/test_artifact_branch_new_parent.py::NoOriginLeavesJournalUntouchedTest`, коммит `fbc398e0`), тест напрямую проверяет `store.task_steps` на отсутствие записи с префиксом «артефактная ветка от локального main:» в сценарии без origin. Прогнан — 1/1 зелёный. Закрыто. |

Реестр закрыт целиком.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/ -q` — 7 passed.
- `python3 -m pytest tests/test_artifact_branch_new_parent.py -q` — 1 passed (новый тест R2-F3).
- `python3 -m pytest tests/test_branch_freshness_gate.py tests/test_doctor_fix_ignored_artifacts.py -q` — 18 passed (обе стороны прежнего конфликта из R2-F1 зелёные одновременно).
- `python3 -m pytest tests/test_gitcmd_branch_reads.py tests/test_gitcmd_carpentry.py tests/test_gitcmd_check_ignore.py tests/test_git_fixation.py tests/test_catalog_new_race.py tests/test_catalog_status_log.py tests/test_artifact_materialization.py tests/test_multitarget.py tests/test_multitarget_invariants.py -q` — 151 passed, 14 subtests passed (126.28s).
- `python3 -m pytest tests/test_doctor.py -q` — 122 passed, 3 subtests passed.
- `python3 scripts/guard.py tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/SPEC.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/PLAN.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/REVIEW.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/ANSWER-1.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/ANSWER-2.md` — «GUARD: ок (5 файлов)».
- `python3 scripts/codebase_map.py` (регенерация на месте) + сравнение с закоммиченной картой построчно, исключая `built_at_sha`, — совпадает; `git checkout -- docs/codebase-map.md` вернул рабочее дерево в чистое состояние.
- `git diff fbc398e0 HEAD -- orchestrator/artifact_branch.py orchestrator/catalog.py orchestrator/doctor.py orchestrator/gitcmd.py` — пусто: коммит подтяжки main (`ab4f138a`) не затронул зону задачи; вся правка после предыдущего вердикта — `docs/codebase-map.md` (общая зона) + `tests/test_artifact_branch_new_parent.py` (R2-F3).
- `git diff de6f5f20 97dc8d32 -- tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/` — пусто: залоченная планка test_author не редактировалась повторно.
- `git status --short` — чисто (кроме материализованного untracked `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/`).
- Полный набор `tests/` не гонял (решение Оператора 05.09 — гоняет CI на каждый пуш) — прогнаны планка задачи и все модули, реально пересекающиеся с зоной задачи и с прежним конфликтом R2-F1/R2-F2.

## Предложения системе

- Диагностика выше — третий наблюдаемый подслучай класса «sha
  предыдущего вердикта ненадёжен для инкрементального diff пакета»
  (review-checklist уже описывает два: устаревший автокоммит роли;
  совпадение с текущим HEAD из-за подтяжки main). Здесь третий вариант:
  sha указывает на код-коммит РАЗРАБОТЧИКА, сделанный ПОСЛЕ вердикта,
  но REVIEW.md самого вердикта в кодовую ветку не коммитится вовсе —
  надёжной точки отсчёта на кодовой ветке для diff «с прошлого вердикта»
  не существует по конструкции; нужен трёхточечный diff от коммита в
  АРТЕФАКТНОЙ ветке, где реально лежит прошлый REVIEW.md.
- Наблюдение по процессу (эта задача, шаг `300d1bd8`/`c3c8584c`, 06.09
  13:57): роль developer самостоятельно повторила анализ конфликта
  AC-2 ↔ `test_doctor_fix_ignored_artifacts.py` и написала в PLAN.md
  черновик эскалации с вариантами ответа — хотя Оператор уже закрыл
  ровно этот вопрос ANSWER-2 за 11 минут до того (13:46:13). Похоже на
  то же семейство, что и наблюдение backlog о материализации
  `tasks/<id>/` только в начале шага (копилка 06.09, «не читает правку в
  артефактной ветке») — здесь тот же класс на артефакте ANSWER-N,
  появившемся, пока шаг уже шёл. Кандидат: шаг роли, обнаружившей повод
  для эскалации, перечитывает список `ANSWER-*.md` артефактной ветки
  непосредственно перед записью текста эскалации, а не полагается
  только на снимок начала шага.
