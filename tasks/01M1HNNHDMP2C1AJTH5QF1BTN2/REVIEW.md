---
task: 01M1HNNHDMP2C1AJTH5QF1BTN2
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 3
---

# REVIEW: Штатная команда правки зафиксированной планки приёмки

Инкрементальный diff пакета (`00e32aaf...`) снова не собрался (`Invalid
symmetric difference expression`) — тот же несуществующий sha, что и в
iteration 3 (`git cat-file -t 00e32aaf2c15059ffb72260275b29b9d2b53e8fe`
— ошибка). Ревью проведено вручную по фактическому дифу с предыдущего
вердикта: на кодовой ветке — `git diff 4aee54a 77c823a --stat`
(единственный коммит этой итерации), на артефактной — `git diff d25f4fe
artifact/01m1hnnhdmp2c1ajth5qf1btn2 --stat -- tasks/
01M1HNNHDMP2C1AJTH5QF1BTN2/` (`d25f4fe` — коммит вердикта iteration 3,
найден по `git log --oneline --all -- tasks/.../REVIEW.md`). Единственный
коммит `77c823a` трогает ровно 4 файла: `orchestrator/amend.py`,
`tests/test_amend.py`, `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/PLAN.md`,
`docs/codebase-map.md` — ничего за пределами зоны задачи и конвенции
(нет правок `ci/`, `.github/`, `gates.yaml`, `roles.yaml`, `skills/`,
`templates/`).

**Главный вывод фазы B: оба открытых замечания предыдущей итерации
(R2-F1 blocker, R2-F2 major) исправлены по существу и проверены
мутационно — не просто заявлены `fixed`.**

## Фаза A: гейт плана

1. Покрытие требований — таблица PLAN.md полна; с исправлением R2-F1
   фактическое покрытие требования 1/AC-1/AC-2 теперь соответствует
   таблице (было расхождение в iteration 2/3). OK.
2. Шаги — без изменений с iteration 2, размер MR разумен. OK.
3. Подход — раздел «Правка R2-F1/R2-F2» явно документирует найденный в
   iteration 2 факт (трекнутые `tasks/<id>/acceptance_tests/` в main,
   включая эту задачу) и способ устранения — расхождение из iteration 3
   (раздел «Подход» не упоминал риск) закрыто. OK.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (коммит на артефактную ветку, лок, журнал sha+reason) | OK | `_tests_snapshot` теперь видит трекнутые файлы (`--cached`) — R2-F1 исправлен и проверен мутационно. |
| 2 (три именованных отказа + лок не стоял) | OK | AC-2 строится на исправленном снимке. |
| 3 (журнал — признаваемое основание) | OK | без изменений. |
| 4 (метка «правка планки», отчётность, порог/алерт) | OK | без изменений. |
| 5 (не оценивает существо, не запускает агентов) | OK | без изменений. |
| 6 (обязательный прогон, маркер красноты, итог в журнале) | OK | без изменений. |

| AC | Вердикт |
|---|---|
| AC-1 | OK (R2-F1 исправлен) |
| AC-2 | OK (R2-F1 исправлен) |
| AC-3..AC-12 | OK, без изменений с iteration 2 |
| AC-13 | OK — планка 14/14, полный набор `tests/` 1332 passed (был 1332 на входе итерации, прирост на 1 регресс-тест R2-F1 уже засчитан прошлой итерацией — этой итерацией регресса нет) |

## Замечания

Новых замечаний нет.

- Оба замечания предыдущей итерации проверены не только чтением диффа,
  но и живой мутацией: откат `--cached` в
  `orchestrator/amend.py::_tests_snapshot` (строка с
  `"ls-files", "--cached", "--others", "--exclude-standard"`, `amend.py:146`)
  красит именно заявленный регресс-тест
  (`TestsSnapshotAndMaterializeTest::
  test_tests_snapshot_includes_modified_tracked_file`,
  `tests/test_amend.py:224`) — `AssertionError: None != b'...'`, ровно
  тот сценарий, что описан в докстринге теста. Файл восстановлен
  (`git checkout -- orchestrator/amend.py`) сразу после проверки.
- Все 23 реальных тестовых метода `tests/test_amend.py` (проверено
  `pytest --collect-only`, не построчным grep по исходнику — строковой
  литерал фикстуры `AC_TEST_AMENDED` внутри файла содержит два `def
  test_...`, не являющихся реальными тестами модуля, и грубый grep их
  бы посчитал) несут докстринг с «Ловит мутацию: …»
  (`grep -c "Ловит мутацию" tests/test_amend.py` — `23`, совпадает с
  числом реальных тестов). Выборочно прочитаны докстринги
  `TestsSnapshotAndMaterializeTest`, `LockedWindowTest`,
  `AmendEventsInWindowTest` — каждый описывает конкретный правдоподобный
  дефект и наблюдаемое следствие, не пересказывает имя метода.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | orchestrator/amend.py:119-160 (`_tests_snapshot`) | видел только untracked-файлы, терял правки уже трекнутых | лок двигался бы без реального коммита правки | `--cached` добавлен к `git ls-files`; проверено мутационно этой итерацией (откат красит регресс-тест) — закрыто |
| R2-F2 | accepted | tests/test_amend.py (23 тестовых метода) | ни один тест не нёс докстринг «Ловит мутацию: …» | ревью не могло сверить чувствительность теста с заявкой | докстринги добавлены всем 23 методам, выборочно проверены на содержательность (не пересказ имени) — закрыто |

## Вердикт

approved — оба открытых замечания реестра исправлены по существу и
подтверждены мутационной проверкой, новых blocker/major не найдено,
диф итерации не выходит за пределы зоны задачи, полный набор тестов
зелёный без регрессов.

## Проверено исполнением

- `git checkout -- tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/` — восстановлен
  каталог задачи, пропавший в рабочем дереве на старте сессии (тот же
  повторяющийся класс; не переписывался, память
  `feedback_task_dir_deletion_recovery`).
- `git log --oneline -20` / `git log --oneline --all -- tasks/
  01M1HNNHDMP2C1AJTH5QF1BTN2/REVIEW.md` — нашёл `d25f4fe` (вердикт
  iteration 3) и текущий HEAD артефактной ветки `14fd081`.
- `git diff 4aee54a 77c823a --stat` (кодовая ветка) — 4 файла:
  `docs/codebase-map.md`, `orchestrator/amend.py`, `tasks/.../PLAN.md`,
  `tests/test_amend.py`; ничего за пределами зоны.
- `grep -n '"ls-files", "--cached"' orchestrator/amend.py` —
  подтверждено наличие `--cached` в `_tests_snapshot`.
- `python3 -B -m pytest tests/test_amend.py::TestsSnapshotAndMaterializeTest::test_tests_snapshot_includes_modified_tracked_file -q`
  после ручного отката `--cached` в `orchestrator/amend.py` — `1
  failed`, `AssertionError: None != b'...'` (мутация поймана); файл
  восстановлен `git checkout -- orchestrator/amend.py` сразу после.
- `python3 -B -m pytest tests/test_amend.py -q` — `23 passed`.
- `python3 -B -m pytest tests/test_amend.py --collect-only -q` — `23
  tests collected` (сверка реального числа тестовых методов против
  грубого grep, который включает строковой литерал фикстуры).
- `grep -c "Ловит мутацию" tests/test_amend.py` — `23`, совпадает с
  числом реальных тестов.
- `python3 -B -m unittest discover -s
  tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests -p 'test_*.py'` —
  `Ran 14 tests in 15.177s`, `OK`.
- `python3 -B -m pytest tests/test_acceptance_tests_flow.py -k LockTest -q`
  — `4 passed` (инвариант 27 не ослаблен).
- `python3 -B -m pytest tests/ -q` (полный набор) — `1332 passed, 408
  subtests passed in 137.48s`, exit code 0 — без регрессов.
- `python3 -B scripts/guard.py tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/*.md` —
  `GUARD: ок (4 файлов)` (REVIEW.md материализован отдельно из
  артефактной ветки, тем же приёмом, что и в прошлых итерациях).
- `python3 scripts/codebase_map.py` (пробный прогон) — диф только
  строки `built_at_sha` (`git diff --stat docs/codebase-map.md` — `1
  file changed, 1 insertion(+), 1 deletion(-)`), содержимое карты не
  изменилось; расхождение `built_at_sha: 4aee54a...` при HEAD
  `77c823a` легитимно (карта регенерируется ДО коммита, несущего её
  же правку — неизбежный лаг на один коммит, не признак дефекта). Файл
  восстановлен `git checkout -- docs/codebase-map.md`.
- `find tasks/01M1HNNHDMP2C1AJTH5QF1BTN2 -name '__pycache__' -o -name
  '*.pyc'` — пусто на конец ревью (все прогоны `-B`).

## Предложения системе

Класс «MR пересдаётся на ревью со `status: ready` без обработки
открытых замечаний реестра» (отмечен iteration 3) на этот раз не
повторился: разработчик явно исправил обе записи, зафиксировал в
PLAN.md и разметил реестр `fixed` с описанием правки — сам этот случай
можно считать подтверждением, что формулировка предложения из
iteration 3 сработала при следующей сдаче; отдельного нового пункта не
завожу.
