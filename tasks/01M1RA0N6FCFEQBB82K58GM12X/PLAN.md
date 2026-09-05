---
task: 01M1RA0N6FCFEQBB82K58GM12X
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: Гейт ёмкости diff не считает артефакты задачи в кодовой ветке

## Подход

Один pathspec-приём в двух местах:

1. `orchestrator/review.py::git_diff_part` получает необязательный
   параметр `pathspec: tuple[str, ...] = ()` — непустой добавляет
   `"--", *pathspec` в конец команды `git diff [flags] base...branch`.
   Пустой (по умолчанию) — поведение byte-for-byte прежнее, вызывающий
   код `orchestrator/fsm.py::_snapshot_split_assessment` (не в зоне
   этой задачи) не меняется.

2. `review.review_package` зовёт `git_diff_part` для `--stat` и для
   самого diff с `pathspec=(".", f":!tasks/{task_id}/")` вместо без
   pathspec — тот же вызов, что и раньше, плюс исключение (AC-2, AC-6).

3. `fsm_advance._capacity_gate_refuses` меряет ДВА diff'а вместо
   одного: «код» — `pathspec=(".", f":!tasks/{task_id}/")` (та же мера,
   что use в review_package) и, только когда код сам по себе выше
   потолка (иначе вторая цифра просто не нужна и не считается),
   «артефакты» — `pathspec=(f"tasks/{task_id}/",)`. Порог сравнивается
   с размером «кода» (AC-1, AC-4, AC-5); отказ печатает и журналирует
   обе цифры (AC-3).

Способ исключения (`-- . ':!tasks/<id>/'`) — буквально пример из SPEC,
`_sandbox.GitFeatureBranchSandbox`/тесты AC-1..AC-6 совпадают с ним по
конструкции, а не навязывают его — но раз пример уже нужен для
согласованности с независимым оракулом теста AC-3, используется он же,
без изобретения второго способа.

Fail-closed по-прежнему: git не ответил на diff «кода» — отказ (как и
до задачи, R1-F2). git не ответил на diff «артефактов» (второй вызов,
только на пути уже подтверждённого отказа) — отказ всё равно
происходит (первая цифра уже превышает потолок), а вторая цифра в
сообщении заменяется явной пометкой «неизвестен: git не ответил», а не
роняет гейт и не выдаёт вымышленное число.

## Шаги

1. `orchestrator/review.py`: параметр `pathspec` в `git_diff_part`;
   `review_package` передаёт исключающий pathspec в оба вызова
   (`--stat` и diff). Обновить `tests/test_review_package.py` —
   существующие assert'ы на точный список `self.git.calls` для diff/
   stat (`test_stat_and_diff_are_taken_against_main`,
   `test_diff_and_stat_are_taken_against_the_previous_verdict_sha`,
   `test_missing_prev_sha_falls_back_to_the_full_diff`) обязаны
   отражать новый (требуемый SPEC) вызов с pathspec — это не ослабление
   теста, а обновление под изменившееся, требуемое SPEC поведение;
   намерение теста (diff/stat считаются от правильной базы) не
   меняется. Новые тесты: AC-2/AC-6 — планка задачи
   (`acceptance_tests/test_ac2_ac6_review_package_excludes_tasks_dir.py`),
   плюс юнит-тест на сам `git_diff_part(pathspec=...)` в
   `tests/test_review_package.py` (аргументы команды с pathspec).

2. `orchestrator/fsm_advance.py`: `_capacity_gate_refuses` считает
   «код» и, при превышении, «артефакты» отдельными вызовами
   `git_diff_part`; сообщение отказа (журнал и печать) называет обе
   цифры. Юнит-тесты в `tests/test_capacity_gate.py` (mock-based)
   остаются зелёными без изменений — mock не смотрит на аргументы
   diff-вызова; добавить юнит-тест на формат сообщения с двумя
   цифрами (mock двух разных diff-ответов по разным pathspec).
   Планка задачи (`acceptance_tests/
   test_ac1_ac3_ac4_ac5_capacity_gate.py`) закрывает AC-1/AC-3/AC-4/
   AC-5 на настоящем git.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1 |
| 3 | 2 |

## Влияние на систему

- `orchestrator/fsm.py::_snapshot_split_assessment` тоже зовёт
  `review.git_diff_part(config.MAIN_BRANCH, t["branch"])` (материал для
  `artel report`, не условие перехода) — вне зоны этой задачи
  (`fsm.py` не в `zones:`), новый параметр `pathspec` необязательный с
  дефолтом «нет исключения», так что этот вызов не меняется ни по
  аргументам, ни по посчитанному размеру: `diff_bytes` в `report`
  по-прежнему считает ПОЛНЫЙ diff, включая `tasks/<id>/` — сознательно,
  не предмет этой задачи (SPEC «не входит» ничего не говорит про
  report, требование её не касается).
- Потолок `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES` не меняется (SPEC
  «не входит») — сравнение в гейте просто смотрит на другое число.
- Существующие тесты гейта ёмкости (`tests/test_capacity_gate.py`,
  mock-based) и ревью-пакета (`tests/test_review_package.py`) остаются
  зелёными; три места с точным списком `self.git.calls` обновлены под
  новый (обязательный по SPEC) вызов с pathspec — не ослабление, тест
  по-прежнему проверяет ту же базу сравнения (main/prev_sha), только
  вызов теперь несёт pathspec, без которого AC-2/AC-6 недостижимы.
  Устаревшая (уже неисполняемая CI, `tests/` не видит `tasks/`) планка
  `tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/acceptance_tests/` не трогается —
  вне зоны, вне CI-обнаружения.
- Откат: обе правки — чистое добавление необязательного параметра со
  значением по умолчанию, сохраняющим старое поведение; откат —
  вернуть вызовы `git_diff_part` без `pathspec` и старую однострочную
  формулировку отказа гейта.

## Риски

- Хрупкость к точному списку `self.git.calls` в тестах — обновление
  этих строк было предусмотрено в SPEC (регресс-риск AC-7 закрыт
  прогоном `tests/test_review_package.py` и
  `tests/test_capacity_gate.py` целиком).

## Предложения системе

(нет)
