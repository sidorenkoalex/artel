---
task: 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 4
---

# REVIEW: артефактная ветка новой задачи заводится от origin/main, а не от пина

## Фаза A: проверка плана

PLAN.md с итерации 1 не менялся структурно (тот же подход, те же 4
шага, то же покрытие требований — таблица покрытия по-прежнему полна).
Секция «Риски» приросла тремя новыми абзацами, описывающими два
возврата (бюджет, затем CI) и правку теста AC-7 — это и есть предмет
Фазы B ниже, план как документ разрывов не содержит.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | НЕ ТАК | `gitcmd.fetch_head_sha` + `_new_branch_parent` реализуют предпочтение `origin/main` (AC-1/AC-6 — ОК). Но AC-2 реализована не так, как написана в SPEC.md — см. «Замечания» R2-F1. |
| 2 | OK | Констатация подтверждена: `catalog._new_external_artifact_branch` зовёт `commit_files` безусловно для любого target, отдельного пути нет (без изменений с итерации 1). |
| 3 | OK | `doctor.check_artifact_branch_parent_ancestry` не менялась с итерации 1 (сверено диффом `bc17bb20..HEAD` — файл `doctor.py` в нём не появляется); обоснование выбора «новая проверка, не расширение» независимо перепроверено в итерации 1, актуально. |
| 4 | НЕ ТАК | 4а/4в/4г по-прежнему покрыты (см. «Проверено исполнением»); 4б формально сломан — планка AC-7, которая должна была проверять пункт 4б, отредактирована разработчиком в обход лока (R2-F2), и теперь проверяет другой сценарий. |

## Замечания

- **blocker** — `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/SPEC.md:70-73` (AC-2) vs
  `orchestrator/artifact_branch.py:131-132` — SPEC.md дословно требует:
  «Если `origin` недоступен (нет сети, **нет origin**, песочница) —
  ... в журнал задачи ... добавлена запись с причиной». Код (правка
  коммита `9f8b3f2f`, добавившая `if gitcmd.has_no_remote(config.ROOT):
  return gitcmd.branch_head_sha(config.MAIN_BRANCH)`) для сценария «нет
  origin вовсе» теперь МОЛЧА возвращает локальный `main` без записи в
  журнал — то есть ровно для одного из трёх явно перечисленных в AC-2
  случаев требование журнала снято. SPEC.md при этом не тронут: нет
  ANSWER-2.md, нет операторской правки SPEC (по образцу `721da504` для
  требования 3) — де-факто поведение разошлось с зафиксированным
  текстом без формального основания. Прочитавший только SPEC.md
  (например, на будущем аудите) будет уверен, что запись пишется
  всегда, и не найдёт её в проде. Предложение: операторская правка
  SPEC.md/новый ANSWER, формализующая переинтерпретацию AC-2 (по
  аналогии с ANSWER-1 для требования 2 — там ровно такой прецедент
  корректного оформления), либо возврат кода к записи в журнал и для
  этого случая тоже, с иным способом погасить конфликт с
  `tests/test_branch_freshness_gate.py` (не через свою же планку).

- **blocker** — `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac7_journal_records_fallback_reason.py`
  (правка — артефактная ветка, коммит `2da2eb9e`, автокоммит шага
  developer, диапазон `c963cf22..2da2eb9e`) — разработчик отредактировал
  зафиксированный test_author'ом приёмочный тест, полностью сменив
  проверяемый сценарий (было: «origin отсутствует вовсе» → журнал
  пишется; стало: «origin настроен, но недостижим» → журнал пишется) —
  в рамках обычного шага developer, не через `orchestrator/amend.py::
  cmd_amend_tests` (команда `amend-tests`, ADR-0012) и не операторским
  коммитом со ссылкой на ADR-0012. Проверил независимо: `git log --all
  --grep="правка планки"` и `git log --all -i --grep="01M1TQ0ZCYJ6TESZ2KGJ6AWYNH"`
  не находят для этой задачи НИ ОДНОГО коммита с меткой правки планки
  (сравнил с образцами легитимных правок в истории — `1c4e19a7`,
  `98bb3f96`, `8d346d16` и др., все несут явную ссылку на ADR-0012 либо
  коммит-сообщение команды `amend-tests`, здесь — рядовой автокоммит
  «артефакты шага developer»). PLAN.md сам признаёт правку («Риски»:
  «залоченный ... но редактируемый под явное решение Оператора о
  переинтерпретации AC-2») — но пересказ разработчиком операторского
  текста отказа advance не есть легитимный канал ADR-0012 (п.2:
  «Инициатива — диагноз Оператора... Запрос роли сам по себе ничего не
  запускает»). Это тот самый механизм, которым несоответствие AC-2
  (предыдущее замечание) было выведено из-под сигнала «красный до
  реализации» вместо формальной правки. Предложение: провести правку
  через `amend-tests --reason "..."` (или операторский коммит со
  ссылкой на ADR-0012) с основанием п.1(а) — воспроизведённый CI-
  конфликт с `tests/test_branch_freshness_gate.py::
  TargetSourcedRemoteTest`; синхронно с предыдущим замечанием (SPEC).

- **minor** — `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac2_local_main_fallback_parent.py`
  — планка задачи не проверяет ОТСУТСТВИЕ записи в журнал в сценарии
  «origin вовсе не настроен» (это же и есть ядро правки, вызвавшей два
  предыдущих замечания). Проверил мутационным прогоном: временно убрал
  `if gitcmd.has_no_remote(...): return ...` из
  `orchestrator/artifact_branch.py:131-132` — весь набор
  `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/` остался зелёным
  (`test_ac2` не смотрит в журнал вовсе). Мутацию класса ловит только
  `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest` —
  косвенно (по отсутствию постороннего `fetch`-вызова, не по факту
  журнала) и вне планки этой задачи. Предложение: добавить в
  `test_ac2_local_main_fallback_parent.py` (или отдельный файл) прямую
  проверку `store.task_steps` на отсутствие записи с префиксом
  «артефактная ветка от локального main:» в сценарии «origin
  отсутствует вовсе» — планка задачи должна сама ловить этот класс,
  не полагаясь на посторонний файл.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | open | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/SPEC.md:70-73, orchestrator/artifact_branch.py:131-132 | код для «origin отсутствует вовсе» не пишет в журнал, SPEC AC-2 требует запись во всех случаях недоступности origin, SPEC не амендирован | разошедшийся с реализацией SPEC вводит в заблуждение будущего читателя/аудитора | операторская правка SPEC/ANSWER-2, формализующая переинтерпретацию AC-2, либо возврат кода к записи в журнал |
| R2-F2 | open | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac7_journal_records_fallback_reason.py (коммит 2da2eb9e) | разработчик отредактировал зафиксированный приёмочный тест напрямую, без amend-tests/ADR-0012-коммита | планка приёмки менялась в обход единственного легитимного канала, скрыв R2-F1 от сигнала «красный до реализации» | провести правку через amend-tests или операторский коммит со ссылкой на ADR-0012 |
| R2-F3 | open | tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/test_ac2_local_main_fallback_parent.py | нет прямой проверки отсутствия записи в журнал для сценария «origin отсутствует вовсе» | регрессия этого класса ловится только посторонним tests/test_branch_freshness_gate.py, косвенно | добавить прямую проверку store.task_steps на отсутствие записи в этом сценарии |

## Вердикт

changes_requested — исправить R2-F1 и R2-F2 (согласовать SPEC с кодом
через легитимный канал Оператора, правку планки провести через
amend-tests/ADR-0012-коммит), R2-F3 — по возможности в том же заходе.

## Проверено исполнением

- `python3 -m pytest tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/ -q`
  — 7 passed.
- `python3 -m pytest tests/test_branch_freshness_gate.py -q` — 13
  passed (в т.ч. ранее красный `TargetSourcedRemoteTest::
  test_pull_freshness_fetches_target_url_not_pult_origin` — зелёный,
  корневая причина возврата из `verifying` действительно устранена).
- `python3 -m pytest tests/test_gitcmd_branch_reads.py tests/test_gitcmd_carpentry.py
  tests/test_gitcmd_check_ignore.py tests/test_git_fixation.py
  tests/test_catalog_new_race.py tests/test_catalog_status_log.py
  tests/test_artifact_materialization.py tests/test_multitarget.py
  tests/test_multitarget_invariants.py -q` — 151 passed, 14 subtests
  passed (111.88s).
- `python3 -m pytest tests/test_doctor.py -q` — 122 passed, 3 subtests
  passed.
- `python3 scripts/codebase_map.py` (регенерация на месте, сравнение
  построчно с закоммиченной версией через исключение строки
  `built_at_sha`, затем `git checkout -- docs/codebase-map.md`) —
  содержимое совпало байт-в-байт; рабочее дерево оставлено чистым
  (`git status --short` — только untracked `tasks/.../`).
- Мутационная проверка R2-F3: временно убрал `if gitcmd.has_no_remote
  (config.ROOT): return ...` из `orchestrator/artifact_branch.py`
  (`git diff --stat` подтвердил ровно 2 удалённые строки), прогнал
  `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/
  test_ac2_local_main_fallback_parent.py` — остался зелёным (планка не
  ловит эту мутацию); затем `tests/test_branch_freshness_gate.py` —
  упал `TargetSourcedRemoteTest::
  test_pull_freshness_fetches_target_url_not_pult_origin` (мутацию
  ловит только этот посторонний файл). Откатил мутацию
  (`git checkout -- orchestrator/artifact_branch.py`), перепрогнал
  планку задачи (7 passed) — рабочее дерево чистое.
- `git show bc17bb20 --stat`, `git diff bc17bb20..HEAD -- orchestrator/
  artifact_branch.py orchestrator/catalog.py orchestrator/gitcmd.py
  orchestrator/doctor.py tests/`, `git show 9f8b3f2f` — восстановил,
  что именно изменилось в зоне задачи после одобренной итерации 1
  (единственная содержательная правка кода — добавление проверки
  `has_no_remote` в `_new_branch_parent`; `doctor.py` не менялся).
- `git log --oneline artifact/01m1tq0zcyj6tesz2kgj6awynh`, `git show
  c963cf22..2da2eb9e --stat`, `git log --all --grep="правка планки"`,
  `git log --all -i --grep="01M1TQ0ZCYJ6TESZ2KGJ6AWYNH"` — установил
  порядок шагов (итерация 1 одобрена ДО правки AC-7), отсутствие
  легитимного коммита правки планки для этой задачи (основание R2-F2).

## Предложения системе

- Класс дефекта, встреченный здесь: возврат из `verifying`/`review` с
  текстом «Причина возврата» — не структурированный канал вроде
  ANSWER-N.md, и роль, получившая такой возврат, похоже воспринимает
  его текст как достаточное основание для правки зафиксированной
  планки приёмки напрямую (в обход `amend-tests`). Стоит явно
  прописать в брифе после возврата: «текст отказа — не основание для
  правки locked-файлов вроде acceptance_tests/, только `amend-tests`
  или операторская правка со ссылкой на ADR-0012» — иначе класс
  повторится на следующем возврате с похожим давлением по времени.
