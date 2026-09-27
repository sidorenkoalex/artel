---
task: 01M3GKJBXEBHB6ZA48J7VG8Z8W
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: answer — проверка строки мандата при записи и подсказка approve после ответа

## Фаза A: гейт плана

1. **Покрытие SPEC.** Таблицы PLAN дополнены шагами 6-8 (замечания
   итерации 1) и по-прежнему покрывают все 5 требований и все 9 AC-n:
   требование 1 → шаги 1,2,3,8; требование 2 → 1,3,7; требование 5 → 5,6.
   Каждая строка ведёт на существующий шаг, пробелов нет.
2. **Размер шагов.** Три новых шага — единицы того же MR (перечень
   недостающих тестов, перенос формулы области, разбор строки `Пути:`),
   не микрооперации.
3. **Конвенции и архитектура.** Шаг 7 расширяет отказ СВЕРХ буквы
   требования 2в (`tests/**/*.py` вместо префикса `tests/`) — это
   расхождение с SPEC записано в PLAN явным абзацем «Итерация 2: область
   мандата ослабления строже буквы 2в» и это ровно один из двух исходов,
   которые замечание R1-F2 предлагало. Расхождение в сторону ужесточения
   отказа Оператору на форме, которую гейт и раньше не засчитывал; ни один
   существующий рубеж при этом не ослаблен, поведение гейта на входах не
   меняется (формула перенесена, не изменена) — оснований для `escalate`
   («код прав, спека нет») нет, решение зафиксировано в артефакте.
   Артефакты в кодовую ветку не закоммичены (`git show --stat` обоих
   собственных коммитов — только зоны SPEC + `docs/codebase-map.md` из
   `COMMON_ZONES`), карта регенерирована тем же коммитом.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Разбор один — `mandate.elements` (`mandate.py:64`); после шага 8 собственного отсечения префикса маркера нет ни в одном модуле пакета: `git grep 'len(_ZONES_MANDATE_MARKER)\|len(TEST_WEAKENING_MANDATE_MARKER)\|len(marker)\|len("Пути:")' -- orchestrator scripts` оставляет единственное вхождение `mandate.py:82` (остальные два — `artel.py:673`, `codebase_map.py:214` — про свои маркеры, не про мандат). `zones._plan_zones_extension_paths` (`zones.py:72`) теперь тоже зовёт узел; семантика прежняя: `elements` стрипает строку и режет префикс на той же стрипнутой строке, что делал и снятый код, `[]` на голом `Пути:` отдаётся как и раньше. |
| 2 | OK | Правила 2а-2г на месте (`mandate.py:143,149,163,194`); новое правило 2в — `in_weakening_scope` (`mandate.py:102`), та же формула, что область гейта (`test_integrity._in_scope:101` зовёт её), текст отказа назван («путь вне области tests/**/*.py»). Ложного отказа на элементе, который гейт засчитывает, нет: `Finding.mandate_elements` (`test_integrity.py:66-81`) всегда несёт путь, прошедший `_in_scope`, и именно он стоит в тексте отказа гейта (`refusal_detail:286` печатает `f.line` со стороной base) — элемент, который Оператор списывает с отказа, проверку при записи проходит. |
| 3 | OK | `answer.py:191-195` (журнал) и `answer.py:201-202` (подсказка). Обе строки теперь держит `tests/` — проверено мутацией, см. «Проверено исполнением». |
| 4 | OK | `docs/operator-gates.md:192-202`: формулировка правила мандата ослабления приведена в соответствие с реализацией (`tests/**/*.py` с примерами `tests/`, `tests/fixtures/data.json`), формат строки, проверка при записи и шаг `approve` на месте; AC-8 планки зелен. |
| 5 | OK | Три недостающих теста заведены — см. реестр R1-F1. Существующие тесты не правились: `git diff main...HEAD -- tests/test_answer.py tests/test_answer_gate.py tests/test_answer_branch_reads.py tests/test_zones_gate.py tests/test_test_integrity_gate.py \| grep '^-[^-]'` — ни одной удалённой строки; единственный правленый `assert` итерации 2 (`tests/test_answer_mandate.py:206`) — в файле, заведённом этой же задачей, и он не ослаблен: подстрока причины стала точнее («вне области tests/**/*.py» вместо «не под tests/»). |

Критерии AC-1…AC-9 проходят: планка задачи целиком — 25 тестов, зелёные;
пометок `# AC-n: manual|skip` нет ни одной (автогейт acceptance включён).
Файлы планки собственными коммитами задачи не тронуты: единственный
коммит, касающийся `tasks/<id>/acceptance_tests`, — автокоммит шага
test_author (`67cc4388` на `artifact/01m3gkjbxebhb6za48j7vg8z8w`), лок
планки не обойдён.

## Замечания

Новых замечаний нет. Все три записи реестра итерации 1 закрыты по
существу (разбор — в реестре ниже).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_answer_mandate.py, tests/test_answer.py | требование 5 SPEC: в `tests/` не было трёх поимённо названных тестов (отказ на пустой список через `refusals`, подсказка+журнал в `escalated`, сверка третьего потребителя) | правка, снявшая подсказку/запись журнала или ветку 2г, проходила весь `tests/` зелёным — планку после мержа не гоняет никто | закрыто: (а) `RefusalsTest.test_bare_marker_refuses_naming_the_empty_element_list` (`tests/test_answer_mandate.py:284`) — три формы голого маркера, сверяется и строка, и текст причины; (б) `AnswerInEscalatedNamesApproveAsTheNextStepTest` (`tests/test_answer.py:265`) — подсказка в stdout + действие журнала, новый класс, ни одно прежнее ожидание не тронуто; ЧУВСТВИТЕЛЬНОСТЬ проверена двумя мутациями кода (возврат действия к «ANSWER создан» и снятие `print` подсказки — тест краснеет в обоих случаях, см. «Проверено исполнением»); (в) `ThreeConsumersOnOneLineTest` (`tests/test_answer_mandate.py:107`) — поведенческая сверка ТРЁХ потребителей на одной строке с отступом и пустым элементом (не тождество объектов), плюс структурный `ThreeConsumersShareOneNodeTest.test_answer_is_the_third_consumer_of_the_same_parse` |
| R1-F2 | accepted | orchestrator/advance_gates/mandate.py:102, orchestrator/advance_gates/test_integrity.py:101 | правило мандата ослабления требовало префикса `tests/` без `.py`, тогда как область гейта — `tests/**/*.py` со сверкой точным вхождением | мандат «tests/» или «tests/fixtures/data.json» записывался без отказа и молча не срабатывал на гейте | закрыто первым из двух предложенных исходов и лучше него: формула не продублирована, а вынесена в `mandate.in_weakening_scope`, которую зовёт и проверка при записи, и сам гейт (`_in_scope`) — разойтись им теперь нечем; поведение гейта на входах не изменилось (`tests.test_test_integrity_gate` зелен без правки ожиданий), расхождение с буквой 2в записано в PLAN «Влияние на систему», отказ назван, тест — `RefusalsTest.test_weakening_element_under_tests_but_not_python_refuses` (`tests/test_answer_mandate.py:304`), сверяющий заодно, что область гейта и правило при записи отвечают одинаково. Остаточный угол, отказа не стоящий: у пары переименования `mandate_elements` несёт и НОВЫЙ путь (`test_integrity.py:77`), поэтому мандат на путь теста, ВЫНЕСЕННОГО из `tests/`, при записи откажет, хотя гейт его засчитал бы; тупика нет — текст отказа гейта называет сторону base (путь под `tests/`), и этот элемент проверку проходит. |
| R1-F3 | accepted | orchestrator/advance_gates/zones.py:60-75 | `_plan_zones_extension_paths` несла собственный разбор «маркер → элементы» для маркера `Пути:` рядом с общим узлом | следующая правка правила разбора разошлась бы между двумя местами — тот же класс, что чистился для мандата | закрыто: `elements(line, _PLAN_PATHS_MARKER)` с проверкой `is not None`, маркер вынесен в именованную константу (`zones.py:57`), собственного отсечения префикса не осталось; семантика сохранена буквально (стрип до среза префикса — как и раньше; `None` только когда строки нет), `tests.test_zones_gate` и `tests.test_answer::ZonesExtendCommandTest` зелены без правки ожиданий |

## Вердикт

approved. Блокеров и major нет, реестр закрыт целиком: требования 1-5
реализованы и так, как описаны; планка задачи (25) и затронутые наборы
`tests/` (113 + 180) зелёные; ни один существующий тест, гейт, лимит или
guard не ослаблен — единственное изменение рубежа идёт в сторону
ужесточения и зафиксировано в PLAN; «Влияние на систему» PLAN совпадает с
фактическим diff (пять файлов + регенерированная карта, всё внутри `zones`
SPEC и `COMMON_ZONES`); откат — revert одного merge-коммита.

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M3GKJBXEBHB6ZA48J7VG8Z8W/acceptance_tests -t tasks/01M3GKJBXEBHB6ZA48J7VG8Z8W/acceptance_tests` — планка задачи целиком: **25 тестов, OK** (18.1 с); в выводе видна реальная подсказка «дальше: artel.py approve <id> (снятие эскалации)».
- `python3 -m unittest tests.test_answer_mandate tests.test_answer tests.test_answer_gate tests.test_answer_branch_reads tests.test_zones_gate tests.test_test_integrity_gate` — **113 тестов, OK** (8.5 с): пять наборов AC-9 плюс новый (+5 тестов к 108 итерации 1).
- `python3 -m unittest tests.test_invariants tests.test_auto_cycle tests.test_capacity_gate_map tests.test_fsm_advance_tests_writing_artifact_source tests.test_plan_appendix tests.test_review_package_map tests.test_step_refixation` — **180 тестов, OK** (134 с): все остальные наборы, зависящие от `advance_gates` (`git grep -l` по импорту пакета), включая инварианты 34/38.
- **Мутационная проверка нового теста R1-F1(б)** (правка кода внесена временно и снята `git checkout --`, дерево чисто): `action = "ANSWER создан"` вместо «…, ждёт approve» → `AnswerInEscalatedNamesApproveAsTheNextStepTest` FAILED; снятие `print` подсказки → тот же тест FAILED. Оба ассерта реально держат требование 3, а не только повторяют планку.
- `git grep -n 'len(_ZONES_MANDATE_MARKER)\|len(TEST_WEAKENING_MANDATE_MARKER)\|len(marker)\|len("Пути:")' -- orchestrator scripts` — единственное отсечение префикса маркера мандата осталось в `mandate.py:82` (требование 1 по существу, а не по зелёности).
- `git grep -n 'startswith("tests/")' -- orchestrator scripts tests` — формула области одна (`mandate.py:102`); второе вхождение — `tests/test_plan_appendix.py`, чужой фильтр приложения к PLAN, к области гейта отношения не имеет (полнота класса R1-F2).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождений вне строки `built_at_sha` 0 (2 строки diff, обе `built_at_sha`); файл возвращён `git checkout --`.
- `git diff main...HEAD -- tests/test_answer.py tests/test_answer_gate.py tests/test_answer_branch_reads.py tests/test_zones_gate.py tests/test_test_integrity_gate.py | grep '^-[^-]'` — пусто: ни одной удалённой/изменённой строки в наборах AC-9.
- `git log --oneline artifact/01m3gkjbxebhb6za48j7vg8z8w -- tasks/01M3GKJBXEBHB6ZA48J7VG8Z8W/acceptance_tests` — один коммит (автокоммит шага test_author): планка после лока не правилась.
- `git show --stat 012171e4` и `git show --stat 9f9fc5b1`, `git grep -A6 '^COMMON_ZONES' -- orchestrator/config.py` — все тронутые пути внутри зон SPEC плюс `docs/codebase-map.md` из `COMMON_ZONES`; артефакты задачи в кодовой ветке отсутствуют (`git status --short` — только untracked `tasks/<id>/`).
- `git grep -n "AC-[0-9]*: *\(manual\|skip\)" -- tasks/01M3GKJBXEBHB6ZA48J7VG8Z8W` — пусто, автогейт acceptance задачи включён.
- Полный набор `tests/` в шаге не гонял (решение Оператора 05.09): его держит CI — на `9f9fc5b1` 14 проверок зелёные.

## Предложения системе

- `zones-extend` (`orchestrator/answer.py:236`) по-прежнему собирает строку
  мандата из своего аргумента и коммитит её без `mandate.refusals`: путь с
  пробелом, поданный туда, уедет в ANSWER и молча не сработает. SPEC этой
  задачи вынес это в «Не входит» сознательно — наблюдение повторяется
  вторую итерацию подряд, стоит строки бэклога (один вызов узла на
  собранном тексте).
- Класс R1-F1 подтверждён в этой задаче именно как расхождение ориентиров:
  `skills/test-authoring.md` («планка кроет AC, `tests/` — углы») против
  поимённого перечня тестов в требовании SPEC. Разработчик и ревьювер
  прочитали каждый свой ориентир честно, круг ревью стоил один. То же
  наблюдение — в PLAN.md и в REVIEW.md итерации 1: три независимых записи
  об одном пробеле формулировки.
