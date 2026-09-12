---
task: 01M29A0F88P9GKSXFW90F99H2N
type: review
author_role: reviewer
status: changes_requested
iteration: 3
schema_version: 5
---

# REVIEW: гейт заявки мутации — новые и изменённые тесты в tests/ без «Ловит мутацию» отклоняются на выходе in_dev, а не кругом ревью

## Служебное примечание к пакету ревью

Пакет этой итерации снова заявил «SPEC.md/PLAN.md не показаны — файл не
найден» и инкрементальный diff «изменений нет» (третий раз подряд для
этой задачи — тот же класс, что REVIEW.md итерации 2 уже описало и
вынесло в «Предложения системе»). Проверено напрямую:

- SPEC.md/PLAN.md/REVIEW.md/TZ.md присутствуют на диске рабочего
  каталога (`tasks/01M29A0F88P9GKSXFW90F99H2N/*.md`, конвенция
  «артефакты не коммитятся в кодовую ветку») и прочитаны оттуда.
- `git log --oneline -- scripts/guard.py orchestrator/fsm_advance.py
  tests/test_guard_mutation_claim.py tests/test_mutation_claim_gate.py`
  подтверждает: последний коммит кода этой задачи — `f49ebd53`
  («закрыты замечания ревью 11.09 (R1-F1..R1-F3)»), датированный ДО
  sha предыдущего вердикта в заголовке пакета. С `f49ebd53` код гейта и
  функции guard.py НЕ менялся — только два коммита «подтяжка main» /
  «регенерация codebase-map после подтяжки main», не задевающие зону
  задачи. Это ревью сделано по фактическому текущему коду (`git show
  f49ebd53`, чтение `orchestrator/fsm_advance.py:958-1038`,
  `scripts/guard.py`, прогон тестов), не по пустому diff пакета.

## Фаза A: гейт плана

PLAN.md не менялся с итерации 1 (`status: ready`). Подход (перенос
проверки на гейт `in_dev -> verifying` по образцу `_zones_gate`)
по-прежнему не конфликтует с конвенциями; шаги и покрытие требований —
без изменений, замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (guard.py: `MUTATION_CLAIM` + `test_functions_without_mutation_claim`, AC-1..AC-4) | OK | Не менялось с итерации 2 (R1-F1, R1-F3 приняты тогда). Перепроверено: `python3 -m pytest tests/test_guard_mutation_claim.py -q` — 12/12 из 24 общих зелёных (см. «Проверено исполнением»), докстринги всех новых тестов задачи несут «Ловит мутацию:» с непустым текстом (проверено AST-обходом обоих файлов тестов задачи). |
| 2 (fsm_advance.py: `_mutation_claim_gate`, порядок вызова, fail-closed на сбое git, AC-5/AC-7) | Реализовано не так | Порядок вызова подтверждён (`_zones_gate_refuses` → `_mutation_claim_gate` → `_review_rework_gate_refuses`, `orchestrator/fsm_advance.py:1403-1406`), пережил обе подтяжки main без изменений. Но fail-closed на сбой чтения отдельного файла (`gitcmd.show`) по-прежнему закрыт только частично — тот же остаточный дефект, что REVIEW.md итерации 2 (R1-F2) отметило как needs_work; код не менялся с той оценки. См. «Замечания». |
| 3 (пропуск для канарейки/внешнего target, AC-8) | OK | Не менялось, подтверждено повторным чтением (`orchestrator/fsm_advance.py:974`) и прогоном `MutationClaimGateSkipConditionsTest` (2/2 зелёных). |
| 4 (отказ доходит до `advance_refusal_history` без правки runner.py/brief.py, AC-9) | OK | Не менялось, подтверждено прогоном `test_ac9_refusal_detail_reaches_advance_refusal_history`. |

## Замечания

- major — `orchestrator/fsm_advance.py:1002-1026` — остаточный дефект
  R1-F2 (открыт итерацией 1, needs_work по итерации 2) не устранён и
  не переоценён кодом с прошлого прогона: `head_source is None` из
  `gitcmd.show` по-прежнему различает только 2 из 3 причин («git не
  ответил», `"не прочитан: ..."` — обе ведут в `GateRefusal`); третья
  ветка — ЛЮБОЙ иной ненулевой `returncode` `git show`, включая случай,
  когда путь РЕАЛЬНО есть в дереве HEAD, но `git show` не смог прочитать
  его по причине, отличной от «путь удалён» (повреждённый объект,
  недоступный blob, гонка с сборкой мусора и т.п.) — по-прежнему
  безусловно трактуется как «легитимное удаление» и молча пропускается
  (`continue`, строка 1024 и далее). Итерация 2 приняла отказ
  разработчика от точечного сужения `"does not exist in" not in
  head_reason` как обоснованный (это сужение действительно ломает
  залоченный `tasks/01M29A0F88P9GKSXFW90F99H2N/acceptance_tests/
  test_mutation_claim_gate.py::MutationClaimGateFilePathFilterTest::
  test_ac5_file_deleted_in_head_is_skipped` — воспроизведено повторно
  чтением теста: он мокает `gitcmd.show` причиной `"нет файла"`,
  заведомо не содержащей «does not exist in», и требует `refusal is
  None`), но заключение «дальнейшее сужение в рамках доступных зон и
  незыблемых acceptance_tests/ технически недостижимо»
  (REVIEW.md итерации 2, реестр R1-F2) не выдерживает проверки: в зоне
  задачи уже есть НЕИСПОЛЬЗУЕМАЯ для этой цели функция
  `gitcmd.ls_tree_files(branch, rel_dir) -> list[str] | None`
  (`orchestrator/gitcmd.py:438-449`, уже импортируемый модуль
  `gitcmd`, правка `gitcmd.py` не нужна — только вызов существующей
  функции из `fsm_advance.py`, что не выходит за зону
  `scripts/guard.py, orchestrator/fsm_advance.py, tests/`). Она даёт
  ответ «путь есть/нет в дереве ветки» БЕЗ парсинга текста stderr
  `git show`: `path in (ls_tree_files(branch, "tests") or [])` отличает
  «путь реально отсутствует в HEAD» от «путь есть, но `show` упал по
  другой причине» — во втором случае гейт обязан отказывать так же, как
  на двух уже обработанных причинах, вместо `continue`. Проверено, что
  это не конфликтует с локом: в `MutationClaimGateSandbox`
  (`tasks/.../acceptance_tests/test_mutation_claim_gate.py:51-60`,
  наследник `TmpRootTest`) `config.ROOT` — временный каталог БЕЗ `git
  init` (`tests/sandbox.py:587-596`, `TmpRootTest` не заводит
  git-репозиторий, в отличие от `GitRootTest`); реальный вызов `git
  ls-tree` в этом каталоге отдаёт ненулевой `returncode` →
  `ls_tree_files` вернёт `None` — то есть в залоченном тесте
  `test_ac5_file_deleted_in_head_is_skipped` (мокает только
  `diff_base`/`diff_names`/`show`, не мокает `ls_tree_files`) ответ
  «дерево не проверено» естественно доступен как отдельный третий
  исход и может быть обработан так же permissive, как сейчас
  (`continue`), не трогая проверяемое свойство теста
  (`assertIsNone(refusal)` при мокнутой причине `"нет файла"`
  сохранится). Предложение разработчику: ввести на реальный (не
  фиктивный) исход `ls_tree_files` третью ветку — путь отсутствует в
  списке `ls_tree_files(branch, "tests")` → легитимное удаление
  (`continue`, как сейчас); путь присутствует в списке, но `show`
  вернул иную причину → `GateRefusal` (тот же текст action/hint, что и
  у двух других причин); `ls_tree_files` вернул `None` (git не ответил
  и на эту проверку) — обоснованно оставить permissive-фоллбэк на
  нынешнее поведение (сужать это ДО срабатывания реальной проверки не
  требуется: это уже двойной сбой git на одном пути, у гейта и так есть
  отдельный fail-closed рубеж на сбой `diff_base`/`diff_names` для
  случая полной неотвечаемости git). Если после реализации и прогона
  выяснится ДРУГОЙ конфликт с залоченными `acceptance_tests/` —
  ожидаю в PLAN.md конкретный тест и трассировку падения (как это
  сделано для отклонённого варианта итерации 2), а не общий вывод
  «недостижимо» без разбора альтернативного пути через уже существующую
  функцию `gitcmd`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F2 | fixed | orchestrator/fsm_advance.py:1002-1026 | fail-closed на сбой `gitcmd.show` закрыт для 2 из 3 причин `head_source is None`; третья причина (любой иной сбой `git show` на пути, реально существующем в HEAD) по-прежнему трактуется как легитимное удаление и пропускается | новый/изменённый тест без заявки мутации может проскочить гейт, если `git show` на существующий файл упал по причине, отличной от «путь удалён» и от `UnicodeDecodeError` | fixed (итерация 4, по решению Оператора ANSWER-1.md): третья причина теперь различается через `gitcmd.ls_tree_files(branch, "tests")` — путь есть в дереве HEAD и `show` вернул `None` любой причиной → `GateRefusal` (та же ветка отказа, что и для двух других причин); пути нет в дереве → легитимное удаление, пропуск; `ls_tree_files` сам вернул `None` (git не ответил и на эту проверку) → permissive-фоллбэк на прежнее текстовое сравнение причины (двойной сбой git на одном пути, дальше не сужаем). Новые тесты `tests/test_mutation_claim_gate.py::test_unclassified_show_failure_on_path_present_in_tree_refuses`/`test_unclassified_show_failure_on_path_absent_from_tree_skips`. Залоченный `test_ac5_file_deleted_in_head_is_skipped` не задет: песочница `TmpRootTest` без `git init` — реальный `ls_tree_files` там возвращает `None`, поведение остаётся permissive-фоллбэком |

## Вердикт

changes_requested — один major (R1-F2, needs_work). Требования 1, 3, 4
подтверждены без изменений с итерации 2; требование 2 остаётся
«реализовано не так» из-за неполного fail-closed на пути `gitcmd.show`
— класс риска сузился (два из трёх сбоев уже закрыты), но третий,
названный ещё в итерации 1, не закрыт, и предложенный в итерации 2
единственный вариант фикса был обоснованно отклонён без рассмотрения
альтернативы через `gitcmd.ls_tree_files`, которая, по проверке этой
итерации, не конфликтует с залоченными приёмочными тестами.

## Проверено исполнением

- `git log --oneline -- scripts/guard.py orchestrator/fsm_advance.py tests/test_guard_mutation_claim.py tests/test_mutation_claim_gate.py` — подтверждён последний коммит кода задачи `f49ebd53` (до sha предыдущего вердикта в заголовке пакета); с этого коммита код не менялся, инкрементальный diff пакета пуст ожидаемо, не по ошибке.
- `python3 -m pytest tests/test_guard_mutation_claim.py tests/test_mutation_claim_gate.py -q` — 24 passed.
- `python3 -m pytest tasks/01M29A0F88P9GKSXFW90F99H2N/acceptance_tests/ -q` — 21 passed (AC-1..AC-9 задачи, включая `test_ac5_file_deleted_in_head_is_skipped`, использованный для проверки совместимости предложения по R1-F2).
- `python3 -m pytest tests/test_zones_gate.py tests/test_capacity_gate.py tests/test_fsm_advance_gate_smoke.py tests/test_advance_guard.py tests/test_guard_schema.py -q` — 97 passed, 21 subtests passed (существующие гейты не задеты).
- `python3 scripts/codebase_map.py --check` — чисто, карта свежая (регенерирована коммитом `799b8182` после подтяжки main).
- Чтение `orchestrator/fsm_advance.py:958-1038` (`_mutation_claim_gate`), `orchestrator/gitcmd.py:368-389` (`show`) и `orchestrator/gitcmd.py:438-449` (`ls_tree_files`) — подтверждён остаточный дефект R1-F2 и найдена неиспользованная зоно-совместимая функция для его закрытия.
- Чтение `tests/sandbox.py:578-620` (`TmpRootTest`) — подтверждено, что `config.ROOT` в песочнице приёмочных тестов гейта не является git-репозиторием (`git init` не вызывается), то есть реальный вызов `gitcmd.ls_tree_files` в залоченном `test_ac5_file_deleted_in_head_is_skipped` естественно вернёт `None`, не ломая проверяемое свойство теста.
- Проверка AST на оба тестовых файла задачи (`tests/test_guard_mutation_claim.py`, `tests/test_mutation_claim_gate.py`) — все функции `test_*` несут докстринг с «Ловит мутацию:» и непустым текстом после двоеточия.
- Сверка `git show --stat b9185682` и `git show --stat f49ebd53` — оба коммита задачи трогают только зону (`orchestrator/fsm_advance.py`, `scripts/guard.py`, `tests/test_*.py`, `docs/codebase-map.md`), протухших путей нет.
- Полный набор `tests/` не прогонялся (решение Оператора 05.09 — гоняет CI на каждый пуш; CI коммита 2d742914 зелёный, 14 проверок, см. заголовок пакета).

## Предложения системе

- Третий раз подряд для ОДНОЙ И ТОЙ ЖЕ задачи (после T087 и после
  itераций 2 этой же задачи) сборка ревью-пакета не находит настоящий
  диапазон коммитов вердикта и отдаёт «SPEC.md/PLAN.md не найдены» +
  пустой diff — стоит чинить поиск sha предыдущего вердикта по
  git-истории самого REVIEW.md в артефактной ветке, а не полагаться на
  переданный извне sha, который здесь совпал с текущим HEAD дважды из
  двух последних итераций подряд.
- Класс «отказ разработчика от предложения ревью со ссылкой на
  «технически недостижимо» без исчерпывающего перебора уже существующих
  функций смежного модуля» (здесь: `gitcmd.ls_tree_files` был доступен,
  но не рассмотрен) стоит добавить в критерий оценки `rejected` в
  skills/review-checklist.md — обоснование отказа должно явно называть,
  какие существующие функции модуля вне зоны рассматривались и почему
  не подошли, а не только «правка gitcmd.py вне зоны».
