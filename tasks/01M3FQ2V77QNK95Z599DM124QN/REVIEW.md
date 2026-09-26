---
task: 01M3FQ2V77QNK95Z599DM124QN
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Гейт неослабления тестов: удалённые, переименованные и ослабленные тесты отказывают на in_dev -> verifying и на гейте мержа

## Фаза A: гейт плана

1. **Покрытие SPEC полно и не съехало за итерацию.** Таблица «Покрытие
   требований» несёт все 11 требований; состав шага 1 совпал с
   фактическим диффом итерации 2 файл-в-файл
   (`docs/operator-gates.md`, `orchestrator/advance_gates/
   test_integrity.py`, `tests/test_test_integrity_gate.py` +
   регенерированная `docs/codebase-map.md`) — лишнего нет, защищённых
   путей в кодовом коммите нет.
2. **Размер шага.** Монолит обоснован (один текст мандата на два гейта;
   одна строка инварианта про оба рубежа) — возражений нет, как и в
   итерации 1.
3. **Решения 6 и 7 итерации 2** — на месте и честны: подключение рубежа
   переехало из планки в постоянный набор (`GateWiringTest`), мандат на
   переименование расширен ДОБАВЛЕНИЕМ второго пути, не подменой первого.
   Оба заявления проверены мутацией (см. «Проверено исполнением»), а не
   прочтением.
4. **Раздел «Влияние на систему» соответствует диффу.** Абзац «Цена
   рубежа в подпроцессах git» теперь называет `+1 git diff -M` и до `+2
   gitcmd.show` на каждый файл `tests/` в диффе, плюс `git log -1`/`git
   show` на `ANSWER-n.md` при находке, и порядок 81 подпроцесса на ветке
   с 40 файлами `tests/` — арифметика сходится с кодом
   (`test_integrity.py:191-211`, отбор `_in_scope` стоит до всякого
   чтения, строка 193). Откат описан и достоверен.
5. Возражений по плану, требующих правки, нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (один узел, ast в guard) | OK | Итерация 2 узел не расщепила: `findings` по-прежнему единственная сборка, ast остался в `guard.qualified_test_methods`/`test_skip_markers` |
| 2 (`tests/**/*.py` любой глубины) | OK | `_in_scope` (test_integrity.py:84-95) не тронут |
| 3 (`git diff -M --name-status`) | OK | `gitcmd.diff_name_status` не тронут; сравнение пары идёт старый-в-base против нового-в-head (`_pair` → `_file_findings`) |
| 4 (мандат Оператора) | OK | `Finding.alias` + `mandate_elements` (test_integrity.py:66-81): у пары переименования засчитываются ОБА пути и оба квалифицированных имени, `::`-элемент по-прежнему покрывает только свой метод. `_answer_mandate` и отказ засчитывать автокоммит роли не тронуты |
| 5 (файл с нулём тестов — не находка) | OK | Условие `if base_methods:` не тронуто; у удалённого файла `alias` остаётся пустым (test_integrity.py:146) — второй путь появляется только у распознанной пары |
| 6 (гейт перехода, место, отказ, пропуски, fail-closed) | OK | `fsm_advance.py:533` — между `_mutation_claim_gate` (525) и `_review_rework_gate_refuses` (535); место теперь держится тестом, а не только планкой |
| 7 (тот же узел на мерже, fail-open) | OK | `fsm_merge_gate.py:920`, между `_protected_path_diff_gate` (918) и `_ensure_branch_head_published`/`_perform_carpentry_merge` (930); подключение держится тестом |
| 8 (гейт заявки мутации не меняется) | OK | `orchestrator/advance_gates/review.py` в диффе ветки против main отсутствует; `tests/test_mutation_claim_gate.py` зелёный (в том числе `test_file_deleted_in_head_is_skipped`) |
| 9 (приложение к PLAN) | OK | Оба блока перегенерированы и прогнаны мной заново: `git apply --check` на ЧИСТОМ дереве merge-base 3b56de30 — rc=0 у каждого; хедер второго блока (`@@ -2235,3 +2236,120 @@`) реальному диапазону файла соответствует |
| 10 (документация Оператора) | OK | `docs/operator-gates.md` п.6 получил фразу про ЛЮБОЙ из двух путей переименования (строки 176-178) — совпадает с фактическим поведением `mandate_elements`; `docs/operator-session.md` не тронут итерацией 2 и пункт о снятии ручной сверки несёт |
| 11 (тесты) | OK | Пробел итерации 1 закрыт: `GateWiringTest` (два сценария, порядок в обоих маршрутах) + `RenameMandateTest` (три сценария) — 40 passed; докстринги трёх тестов, заявлявших недоказуемую мутацию, переписаны на реально ловимую |

## Замечания

Новых замечаний нет. Все три записи реестра итерации 1 закрыты
исправлением и подтверждены мутационной проверкой (не прочтением
диффа) — подробности в «Проверено исполнением».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_test_integrity_gate.py:417-489 (было :396); PLAN.md, приложение → tests/test_invariants.py | Три теста заявляли докстрингом мутацию «рубеж не подключён к маршруту», а зовут функции гейта напрямую; в `tests/` подключение и порядок не проверял никто | Снятие обеих строк обвязки оставляло набор `tests/` зелёным — после мержа отключение рубежа прошло бы молча | **accepted.** Проверил мутацией сам, в отдельном worktree на HEAD: сняты обе строки (`fsm_advance.py:533`, `fsm_merge_gate.py:920`) при целом модуле гейта → `tests/test_test_integrity_gate.py` **2 failed, 38 passed**, краснеют ровно оба сценария `GateWiringTest` с названными сообщениями («рубеж отключён от перехода», «рубеж отключён от маршрута мержа»). Отдельно проверил перестановку: гейт перенесён ПЕРЕД `_mutation_claim_gate` → **1 failed** (`test_in_dev_calls_the_gate_between_mutation_claim_and_review_rework`), то есть заявленное старшинство держится, а не только факт вызова. Сверка по форме `имя(conn` работает: имя в комментарии над строкой 533 в match не попадает. Докстринги трёх тестов переписаны на поведение узла/обёртки с явной отсылкой к `GateWiringTest`; мутация «`merge_gate_escalates` без `store.set_state`» краснит и переписанный сценарий планки приложения, и `MergeGateTest` (**2 failed, 32 passed**) — то есть новые докстринги описывают то, что тесты действительно ловят |
| R1-F2 | accepted | orchestrator/advance_gates/test_integrity.py:48-81, 124-166 | Мандат на пару переименования засчитывался только по старому пути; `docs/operator-gates.md` не называл, какой из двух писать | Оператор пишет имя, которое видит в ветке и в PR, — лишний круг `advance` на безупречном разрешении | **accepted.** Второй путь ДОБАВЛЕН, не подменил первый — проверено двусторонней мутацией: `paths = (self.alias,)` вместо пары → краснеет `test_mandate_on_the_old_path_still_covers_the_rename`; `alias = ""` (поведение итерации 1) → краснеют `test_mandate_on_the_new_path_covers_the_rename_and_its_method` и `test_method_element_of_a_rename_does_not_cover_the_rename_itself`. Точность сохранена: расширение сверки до префикса (`m.startswith(e)`) краснит третий сценарий, то есть `::`-элемент нового пути само переименование по-прежнему не покрывает. `alias` пуст у всех остальных классов находок (удаление — test_integrity.py:146), лишнего элемента мандата у них не появилось. `docs/operator-gates.md` п.6 сказанному соответствует дословно |
| R1-F3 | accepted | tasks/01M3FQ2V77QNK95Z599DM124QN/PLAN.md, «Влияние на систему» | Цена рубежа была названа как «одна git-команда на переход» | Оператор недооценивает латентность перехода, читая PLAN | **accepted.** Абзац переписан теми числами, которые даёт код: `+1 git diff -M --name-status` на переход, до `+2 gitcmd.show` на файл `tests/` в диффе (по одному на сторону), `git log -1` + `git show` на каждый `ANSWER-n.md` при находке, порядок 81 подпроцесса на 40 файлах `tests/`; оговорка про `_in_scope` до всякого чтения верна (test_integrity.py:193 стоит перед `gitcmd.show`) |

## Вердикт

`approved`. Блокеров и major нет, реестр закрыт целиком.

Реализация отвечает SPEC по всем 11 требованиям; единственный
содержательный пробел итерации 1 (подключение рубежа не сторожил никто,
кроме планки, которую `pytest tests` после мержа не собирает) закрыт
именно там, где он был, — в постоянном наборе, и закрытие подтверждено
воспроизведением исходной мутации, а не словом «добавлено».

Системной целостности изменение не нарушает: дифф ветки против main по
`tests/` — два НОВЫХ файла и ни одной удалённой или изменённой строки
(`git diff main...HEAD -- tests/` не содержит ни одной строки со знаком
`-`), удалённых и переименованных файлов тестов нет,
`orchestrator/advance_gates/review.py` не тронут, защищённых путей в
кодовом коммите нет — `docs/invariants.md` и `tests/test_invariants.py`
идут приложением к PLAN. Пометок `# AC-n: manual|skip` в планке нет ни
одной. Ветка проходит собственный рубеж вчистую. Откат — revert одного
merge-коммита, приложение Оператор откатывает обратным патчем тех же двух
файлов.

## Проверено исполнением

Всё ниже — в переднем плане, из рабочего каталога шага; временные
worktree созданы внутри рабочего каталога и сняты
`git worktree remove --force` (проверено: `git status` чист, кроме
`tasks/<id>/`).

- `python3 -m pytest tests/test_test_integrity_gate.py
  tests/test_guard_test_ast.py -q` — **40 passed** (совпало с заявкой
  PLAN: было 35, добавлены 2 `GateWiringTest` + 3 `RenameMandateTest`).
- **Мутация R1-F1, обе строки обвязки сняты** (worktree на HEAD, модуль
  гейта цел): **2 failed, 38 passed** — падают ровно
  `GateWiringTest::test_in_dev_calls_the_gate_between_mutation_claim_
  and_review_rework` и `::test_merge_gate_calls_the_gate_after_the_
  protected_path_gate`. После `git checkout --` — снова 40 passed.
- **Мутация «порядок»**: вызов гейта перенесён ПЕРЕД
  `_mutation_claim_gate` в теле `in_dev` → **1 failed** (тот же сценарий
  `GateWiringTest`), то есть тест держит не только факт вызова, но и
  заявленное старшинство.
- **Мутации R1-F2, три штуки** (`tests/test_test_integrity_gate.py`):
  `paths = (self.alias,)` — 1 failed (`test_mandate_on_the_old_path_
  still_covers_the_rename`); `alias = ""` — 2 failed
  (`test_mandate_on_the_new_path_...`,
  `test_method_element_of_a_rename_...`); сверка мандата расширена до
  префикса (`m.startswith(e)`) — 1 failed
  (`test_method_element_of_a_rename_does_not_cover_the_rename_itself`).
  Каждая мутация краснит ровно тот сценарий, чей докстринг её заявляет.
- **Мутация «эскалация без `store.set_state`»** в
  `merge_gate_escalates`: **2 failed, 32 passed** —
  `tests/test_invariants.py::TestWeakeningNeedsTheOperatorTest::
  test_the_merge_gate_escalates_the_same_finding` (приложение) и
  `tests/test_test_integrity_gate.py::MergeGateTest::
  test_finding_without_mandate_escalates_with_the_same_text`;
  переписанные докстринги обоих соответствуют пойманному.
- **Приложение к PLAN.** Оба блока сняты из PLAN.md и прогнаны
  `git apply --check` по отдельности в отдельном worktree на ЧИСТОМ
  merge-base 3b56de30 — rc=0 у каждого. Второй блок, применённый на
  HEAD ветки: `python3 -m pytest tests/test_invariants.py -q` — **66
  passed, 215 subtests passed** (включая три сценария
  `TestWeakeningNeedsTheOperatorTest`); совпало с заявкой PLAN.
- Соседи по гейтам и маршруту мержа: `python3 -m pytest
  tests/test_mutation_claim_gate.py tests/test_fsm_advance_gate_smoke.py
  tests/test_protected_paths_gate.py tests/test_zones_gate.py
  tests/test_fsm_advance_gate_framework.py
  tests/test_guard_mutation_claim.py tests/test_plan_appendix.py
  tests/test_fsm_merge_gate_done_snapshot.py
  tests/test_split_assessment_merge_gate.py -q` — **119 passed**.
- Планка задачи: `python3 -m pytest
  tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests -q` — **30 passed**.
- **Узел против собственной ветки на живом git.**
  `test_integrity.findings(<ветка>)` → `base=3b56de30…`, `found=[]`,
  `detail=''` — ложных находок на реальном диффе нет.
- **Неослабление набора по диффу, а не прогоном** (решение Оператора
  05.09): `git diff main...HEAD -- tests/` не содержит ни одной строки
  со знаком `-`; `git diff --name-status -M main...HEAD -- tests/ tasks/`
  — только два `A` (`tests/test_test_integrity_gate.py`,
  `tests/test_guard_test_ast.py`). Удалённых, переименованных и
  ослабленных тестов нет.
- **Свежесть карты.** `python3 scripts/codebase_map.py` →
  `git diff -- docs/codebase-map.md` даёт одну строку различия, и это
  `built_at_sha`; содержательных расхождений **0**. Файл возвращён
  `git checkout --`.
- Проверка обвязки по факту, а не по тесту: `fsm_advance.py:525/533/535`
  и `fsm_merge_gate.py:918/920/930` — порядок вызовов такой, как
  заявлено в SPEC (требования 6-7).
- `python3 scripts/guard.py tasks/.../PLAN.md` — «ок».
- Полный набор `tests/` не гонял (решение Оператора 05.09) — его держит
  CI ветки: коммит 2ca37b32 зелёный, 14 проверок.

## Предложения системе

- Подтверждаю наблюдение PLAN про планку как единственного сторожа:
  правило «инвариант, чей единственный тест лежит в
  `tasks/<id>/acceptance_tests/`, обязан получить двойник в `tests/`»
  стоит сделать машинным — сверкой колонки «тест» первой таблицы
  `docs/invariants.md` с набором `tests/`. В этой задаче класс стоил
  целой итерации ревью, и поймало его только ручное воспроизведение
  мутации; вторая задача с тем же пробелом заплатит столько же.
- Приём «заявка о ПОДКЛЮЧЕНИИ узла к маршруту проверяется прогоном
  маршрута либо `inspect.getsource`, и больше ничем» после этой итерации
  выражен в коде дважды (`GateWiringTest` здесь, планка AC-13) — пора
  назвать его в `skills/test-authoring.md` как образец, а не только
  запрет: сейчас скил говорит, чего нельзя, но не даёт готовой формы, и
  автор каждый раз изобретает её заново.
- Первая таблица `docs/invariants.md` по-прежнему несёт ДВА инварианта с
  номером 36 (строки 66 и 67): ссылка «инвариант 36» неоднозначна, а
  приложение этой задачи добавляет к той же таблице строку 38 — дубль
  никуда не денется сам. Отдельная строка бэклога Оператору.
