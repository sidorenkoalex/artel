---
task: 01M1RNZ6V7TTTTYAHBMF8JBQQS
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 4
---

# REVIEW: регрессия №14 — приёмка гоняет планку на коде кодовой ветки, а не на коде пульта

Примечание к пакету ревью: инкрементальный diff пакета взят от sha
`cde22926` («предыдущий вердикт»), но это НЕ коммит, на котором писался
REVIEW.md итерации 1 — это более поздний коммит разработчика (уже
после ответа R1-F1/R1-F2 и после ANSWER-2/мержа hotfix). Реальный
коммит вердикта итерации 1 — `02c7efb3` (сообщение коммита прямо
называет закрываемые находки), сам он лежит НИЖЕ по истории, чем
`e509da24` (подтяжка main, на которой реально писался REVIEW.md
итерации 1 — судя по репро R1-F1 в «Проверено исполнением» той
итерации, баг там ещё был живым). Тот же класс проблемы, что уже
отмечен в «Предложениях системе» итерации 1 и в скиле
(«Инкрементальный diff пакета — пустой не значит "без изменений"»).
Пересобрал реальный diff вручную: `git diff e509da24..HEAD` — там же
лежит и R1-F1/R1-F2 фикс, и весь мерж hotfix/ANSWER-2, а не только
`docs/backlog.md`, который показал пакет. Ревью ниже — по этому
реальному diff.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (материализация планки в рабочий каталог кода, не tempdir, оверлей поверх устаревшей копии) | OK | `acceptance.materialize_from_branch` — на месте, R1-F1 закрыт (см. ниже) |
| 2 (`cwd`/`code_root` прогона = рабочий каталог кода) | OK | `acceptance.run(tdir, code_root=...)` на всех 3 точках (fsm.py:374, fsm_advance.py:240, fsm_advance.py:327); имя параметра приведено к `code_root` по ANSWER-2 (контракт hotfix 88b38022/ADR-0013) на всех вызывающих узлах и в обоих тестах |
| 3/5 (общий вход материализации/прогона, без дублей) | OK | не изменилось с итерации 1 |
| 4 (отказ называет каталог и cwd одной строкой) | OK | не изменилось с итерации 1 |
| R1-F1 (None vs [] у `ls_tree_files`) | Исправлено, подтверждено | `orchestrator/acceptance.py:89-91`: `if paths is None: return tdir` ДО построения `wanted`, тем же приёмом, что `artifact_branch.materialize_task_dir` — диск не трогается при сбое git. Прогон `tests/test_branch_freshness_gate.py`, `tests/test_fsm_map_conflict_autoresolve.py`, `tests/test_acceptance.py`, `tests/test_fsm_autogate.py`, `tests/test_artifact_materialization.py` — 32/32 зелёные |
| R1-F2 (докстринг «Ловит мутацию») | Исправлено, подтверждено | оба теста (`test_branch_freshness_gate.py:294-298`, `test_fsm_map_conflict_autoresolve.py:241-246`) несут абзац с корректным описанием сценария/свойства, по образцу соседнего теста |

ANSWER-2 (влить main, привести к SPEC поверх hotfix) выполнен:
конфликт в двух файлах (`acceptance.py`, `fsm.py`, коммит `5eea18f3`),
переименование `cwd`→`code_root` докатано отдельным коммитом
(`cde22926`) по всем вызывающим узлам и обоим тестам — грепом по
репозиторию посторонних `acc_run.call_args.kwargs.get("cwd")`/
`acceptance.run(..., cwd=` не осталось (кроме несвязанного
`regen.call_args.kwargs.get("cwd")` в `test_fsm_map_conflict_autoresolve.py:264`
— другая функция, не `acceptance.run`). `orchestrator/amend.py:254`
вне зоны — вызывает `acceptance.run(tdir)` без kwarg, `code_root=None`
обратной совместимостью, не задет.

## Замечания

- minor — `orchestrator/fsm_advance.py:8` (`import shutil`) — мёртвый
  импорт: до этой задачи `shutil.rmtree(cleanup_acc, ...)` вызывался в
  двух местах (было на строках ~255 и ~332 версии до `d03a90a6`), эта
  задача убрала оба вызова (материализация теперь на месте, временный
  каталог не чистится), но сам `import shutil` не убран — в файле
  `shutil` больше нигде не используется (`grep -c shutil
  orchestrator/fsm_advance.py` → 1, это и есть строка импорта). Не
  ломает поведение, но это мусор, оставшийся именно от диффа этой
  задачи. Предложение: убрать строку 8.

- minor — тест-покрытие: фикс R1-F1 (`orchestrator/acceptance.py:89-91`,
  `paths is None` → диск не трогать) подтверждён только ручным репро в
  тексте REVIEW.md итерации 1 (не персистентным тестом) — тот же вывод,
  что сама итерация 1 честно отметила в «Соответствие SPEC»
  («AC-1 всё же не покрывает конкретно сценарий R1-F1... ни
  какой-либо другой AC не воспроизводит именно эту комбинацию»), но не
  завела как отдельную находку. Ни один из committed тестов
  (`tests/test_branch_freshness_gate.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_acceptance.py`) не мокает `gitcmd.ls_tree_files` в
  `materialize_from_branch` на `None` — все используют
  `disk_backed_ls_tree_files`/явные списки файлов, которые всегда
  что-то возвращают. Если это поведение когда-нибудь регрессирует
  обратно к `or []` (например, слиянием, конфликтом мержа — ровно тот
  класс риска, которым и была вызвана эта задача), ни один тест этого
  не заметит. Предложение: unit-тест по образцу уже существующего
  `tests/test_artifact_materialization.py::MaterializeTaskDirTest::
  test_no_branch_returns_empty_sha_and_leaves_disk_untouched` — то же
  свойство («ls_tree_files -> None не трогает диск»), но для
  `acceptance.materialize_from_branch`, а не `artifact_branch.
  materialize_task_dir`. Не blocker (фикс поведенчески верен и
  подтверждён вручную), но дешёвый и целевой для класса дефекта,
  из-за которого заведена вся эта задача.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:89 | `ls_tree_files(...) or []` терял различие None/[] | транзиентный сбой git стирал реальную планку | `if paths is None: return tdir` добавлен, репро из итерации 1 и полный прогон 32/32 зелёные — фикс подтверждён |
| R1-F2 | accepted | tests/test_branch_freshness_gate.py:284, tests/test_fsm_map_conflict_autoresolve.py:240 | новые assert'ы без докстринга «Ловит мутацию» | конвенция test-authoring не соблюдена | докстринги дописаны в обоих файлах по образцу соседнего теста — проверено чтением |
| R2-F1 | open | orchestrator/fsm_advance.py:8 | мёртвый `import shutil`, оставшийся после удаления `shutil.rmtree` этой же задачей | не ломает поведение, засоряет код | убрать строку импорта |
| R2-F2 | open | orchestrator/acceptance.py:89-91 (фикс R1-F1) | фикс не покрыт персистентным unit-тестом, только ручным репро в тексте прошлого REVIEW.md | будущий рефакторинг/мерж-конфликт может незаметно вернуть `or []` без единого красного теста | добавить unit-тест по образцу `MaterializeTaskDirTest::test_no_branch_returns_empty_sha_and_leaves_disk_untouched`, но для `acceptance.materialize_from_branch` |

## Вердикт

changes_requested — оба новых замечания minor и мелкие по объёму
(одна строка удалить, один тест добавить по готовому образцу), но
реестр не может закрыться в `accepted` сам по себе: R2-F1/R2-F2 нужно
закрыть тем же коммитом, следующая итерация должна быть короткой.
R1-F1/R1-F2 подтверждены закрытыми — код и тесты корректны, дальше не
трогать.

## Проверено исполнением

- Восстановлен реальный diff с момента иcходного REVIEW.md итерации 1
  (`git diff e509da24..task/01m1rnz6v7ttttyahbmf8jbqqs-regressiya-14-priyomka-gonyaet`
  — commit `e509da24` соответствует состоянию, на котором репро R1-F1
  в прошлом REVIEW.md ещё воспроизводилось), не только инкремент от
  `cde22926`, который показал пакет.
- `python3 -m unittest tests.test_branch_freshness_gate
  tests.test_fsm_map_conflict_autoresolve tests.test_acceptance
  tests.test_fsm_autogate tests.test_artifact_materialization -v` —
  32 теста, все зелёные (включает оба теста с докстрингом R1-F2 и
  проверку `code_root` вместо `cwd` во всех вызовах).
- `python3 -m unittest tests.test_amend tests.test_dry_run
  tests.test_multitarget tests.test_multitarget_invariants
  tests.test_canary` — все зелёные (модули, где `acceptance.run`/
  `materialize_from_branch` тоже задействованы, включая внешний
  target и `amend.py`, вызывающий `acceptance.run(tdir)` без kwarg).
- `python3 -m unittest discover -s
  tasks/01M1RNZ6V7TTTTYAHBMF8JBQQS/acceptance_tests -v` — 11 тестов,
  `Ran 11 tests ... OK` (AC-1..AC-9, включая намеренно-красные
  AC-6/AC-7, красные по замыслу фикстуры, не по сбою).
- Чтением: `orchestrator/acceptance.py` (полностью, R1-F1 фикс —
  `paths is None: return tdir` до построения `wanted`, до прунинга),
  `orchestrator/fsm.py:330-380`, `orchestrator/fsm_advance.py:210-335`
  — все три точки вызова используют один и тот же `materialize_from_branch`/
  `run(code_root=...)`, дублей нет.
- `grep -n "tempfile\|shutil" orchestrator/acceptance.py
  orchestrator/fsm.py orchestrator/fsm_advance.py` — `tempfile` не
  осталось нигде (кроме упоминания в докстринге как исторический
  контекст regресcии №14); `shutil` — мёртвый импорт в
  `fsm_advance.py:8` (R2-F1), в `fsm.py` не осталось совсем.
- `git show 5eea18f3 --stat` / `git log --merges -1 5eea18f3
  --format=%P` — подтяжка main действительно мерж-коммит с двумя
  родителями, конфликт ровно в `acceptance.py`/`fsm.py`, как и
  описывало ANSWER-2.
- `git diff ...docs/codebase-map.md` — меняется только `built_at_sha`
  (перегенерация после правки `*.py`), не признак дефекта.

## Предложения системе

- Инкрементальный diff ревью-пакета снова (второй раз подряд для этой
  же задачи, ср. с наблюдением из итерации 1 про отсутствующие
  SPEC.md/PLAN.md) указывал не на тот коммит: sha «предыдущего
  вердикта» (`cde22926`) — коммит разработчика ПОСЛЕ фактического
  вердикта (`02c7efb3`), из-за чего пакет показал только
  `docs/backlog.md` вместо всего diff с R1-F1/R1-F2 фиксом и мержем
  hotfix. Причина, видимо, та же, что уже описана в скиле
  («Инкрементальный diff пакета» — Т082/Т087): узел сборки пакета
  берёт sha не из коммита, где REVIEW.md реально получил свой статус,
  а из какого-то соседнего. Стоит проверить конкретно эту задачу как
  третий воспроизводимый случай.
