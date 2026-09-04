---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: plan
author_role: developer
status: draft
schema_version: 3
---

# PLAN: Сверка свежести ветки против main артели на origin

## Подход

Два независимых узла, оба живут в существующих модулях, без новых файлов.

**1. Сверка/подтяжка (`orchestrator/fsm.py::_pull_main_or_escalate`, AC-1..AC-4,
AC-8).** Сегодня узел сравнивает и мержит против ЛОКАЛЬНОГО
`config.MAIN_BRANCH` (пина). Нужно сравнивать и мержить против main
артели на `origin`. Ключевая техническая деталь: сам узел вызывает
`gitcmd.commits_behind` (это `gitcmd.git`, контекст `config.ROOT`) — там
символическая ссылка `FETCH_HEAD` разрешается штатно сразу после fetch в
том же репозитории. А вот сам merge идёт через `gitcmd.in_repo(wt_path,
...)` — это ДРУГОЙ git-worktree (worktree задачи), и с git 2.5+
`FETCH_HEAD` — файл, приватный для каждого worktree (аналогично HEAD/
index), поэтому строкового имени `"FETCH_HEAD"` в аргументах merge
worktree'а задачи недостаточно — там его никто не писал. Решение: сразу
после `fetch` резолвить `FETCH_HEAD` в конкретный sha (`git rev-parse
FETCH_HEAD`, тоже в `config.ROOT`) и передавать этот sha и в
`commits_behind(branch, base=<sha>)`, и в `merge --no-ff <sha>` внутри
worktree — один и тот же приём, что уже несёт `orchestrator/
fsm_merge_gate.py::_origin_main_sha` для плотницкого merge на самом
`merge_gate` (Stage0). Новая приватная функция `fsm._origin_main_sha()`
— СВОЯ копия того узла (не импорт): `fsm_merge_gate` импортирует `fsm`,
обратный импорт завёл бы цикл; дублирование по модулю — уже действующий
в файле приём (см. комментарий у `MAP_REL` в начале `fsm.py`).
Деградация при неответившем git/fetch — тот же `None`/фолбэк-строка
`"FETCH_HEAD"` (не критично: в этом случае `commits_behind` тоже не
разберёт результат и вернёт `None` → `"fresh"`, штатный вырожденный
случай, документированный в самой функции уже сегодня).

**2. Ожидание CI на пути «fresh» (`orchestrator/fsm_merge_gate.py::
_cmd_approve_merge_gate`, AC-5..AC-7).** Сегодня ветка `pull_outcome ==
"fresh"` (когда `confirmed_ci_note is None`) опрашивает `ci.branch_status`
РОВНО один раз и `sys.exit`'ит на любом не-зелёном ответе, включая «нет
проверок ещё» (типичный ответ сразу после первой публикации головы).
Путь `"pulled"` уже ждёт циклом (`("wait", branch)` →
`_wait_for_branch_ci_green` во внешнем цикле). Правка: путь `"fresh"` с
`confirmed_ci_note is None` тоже возвращает `("wait", branch)` — БЕЗ
дополнительного push (голова уже в origin: либо `ensure_head_in_origin`
чуть выше в этой же функции её туда впервые опубликовал, либо она была
там уже). Внешний цикл (`_cmd_approve_merge_gate_cycle`) сам вычисляет
`deadline` от `config.MERGE_GATE_CI_WAIT_CEILING_SEC` на ПЕРВОМ исходе
`("wait", ...)` независимо от того, каким путём («fresh» или «pulled»)
он получен — потолок один и тот же, отдельного не заводится (AC-6).
Однократный локальный опрос `ci.branch_status`/ре-ран-логика внутри тела
`"fresh"`-ветки становится недостижимой при `confirmed_ci_note is None`
(вся эта работа переезжает в `_wait_for_branch_ci_green`) — убирается,
не дублируется.

## Шаги

1. `orchestrator/fsm.py`: добавить `_origin_main_sha()` (fetch origin
   `MAIN_BRANCH` + resolve `FETCH_HEAD` → sha, `None` при неответе);
   переписать `_pull_main_or_escalate` на сверку/merge против
   резолвленного origin-sha вместо `config.MAIN_BRANCH`; обновить
   докстринг узла.
2. `orchestrator/fsm_merge_gate.py`: в `_cmd_approve_merge_gate`, ветка
   `pull_outcome == "fresh"` — при `confirmed_ci_note is None` вернуть
   `("wait", branch)` вместо однократной проверки CI с немедленным
   отказом; убрать код, ставший недостижимым; обновить комментарии.
3. `tests/test_branch_freshness_gate.py`: точечно поправить ОДНУ
   существующую проверку (`test_advance_pulls_main_and_advances_when_
   acceptance_green`, строка про `assertIn(config.MAIN_BRANCH, args)`) —
   она буквально проверяла старое (дефектное) поведение «merge мержит
   `config.MAIN_BRANCH`», которое AC-2 прямо запрещает; заменяется
   эквивалентной по строгости проверкой нового источника (не
   `config.MAIN_BRANCH`, а резолвленный origin-sha/`FETCH_HEAD`-фолбэк).
   Остальные существующие тесты файла не трогаются. Плюс новый тест —
   эквивалент AC-4 в стиле этого файла (мок `gitcmd.commits_behind`
   зовётся с `base`, отличным от `config.MAIN_BRANCH`, при этом ветка
   форкнута от пина).
4. `tests/test_merge_gate_ci_wait.py`: новый тест — эквивалент AC-7 в
   стиле этого файла (`_cmd_approve_merge_gate_cycle` с реальным телом
   гейта на пути `"fresh"`, `ci.branch_status` даёт «нет проверок» на
   первом опросе — гейт не отказывает немедленно, доходит до второго
   опроса циклом ожидания).
5. Прогнать полный `tests/` + `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/
   acceptance_tests/` (реальный git — дольше обычного), `scripts/
   guard.py` на артефактах, закоммитить.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (AC-1) | 1 |
| 2 (AC-2) | 1 |
| 3 (AC-3) | 1 (общий узел, обе точки входа не меняются) |
| 4 (AC-5, AC-6) | 2 |
| AC-4 | 1, 3 (юнит-эквивалент) |
| AC-7 | 2, 4 (юнит-эквивалент) |
| AC-8 | 1 (fetch не трогает `refs/heads/<MAIN_BRANCH>`, merge — только в worktree задачи) |
| AC-9 | 3, 4, 5 |

## Влияние на систему

- Единственный существующий тест, чья проверка меняется: `tests/
  test_branch_freshness_gate.py::
  BranchFreshnessGateTest::test_advance_pulls_main_and_advances_when_acceptance_green`,
  одна строка (`assertIn(config.MAIN_BRANCH, args)` →
  `assertNotEqual(config.MAIN_BRANCH, args[2])` + проверка нового
  источника). Это не ослабление: старая строка утверждала ровно то
  поведение, которое локальный (незыблемый) AC-2 приёмочной планки
  запрещает («merge не имеет права называть `config.MAIN_BRANCH`
  буквальным аргументом») — оставить её как есть значило бы либо не
  закрыть AC-2, либо держать в дереве тест, детерминированно красный
  после корректной реализации. Сила проверки не падает: было «источник
  есть 'main'», стало «источник не 'main' и назван явно» — тот же
  класс утверждения, применённый к исправленному, а не старому
  поведению. Остальные тесты файла (конфликт/эскалация/worktree-отказ/
  «не отстала») не зависят от конкретного значения source-аргумента и
  не тронуты.
- `gitcmd.commits_behind`, `gitcmd.in_repo`, `gitcmd.git` — сигнатуры не
  меняются, новых примитивов `gitcmd.py` не заводится (уже есть
  параметр `base`, ровно под эту задачу).
- Три точки вызова `_pull_main_or_escalate` (`in_dev -> review`,
  `acceptance -> merge_gate`, окно `merge_gate`) продолжают звать один
  и тот же узел без изменений на своей стороне (AC-3) — правка целиком
  внутри узла.
- `doctor.check_root_pin` не трогается (SPEC «Не входит», AC-8 вторая
  половина) — независимый узел, свой собственный `ls-remote`, не делит
  код с `_pull_main_or_escalate`/`_origin_main_sha`.
- Ре-ран флейка (`_ci_confirm_red_or_flake`) и запись в flake-rate на
  пути «fresh» теперь идут ровно тем же кодом, что и на пути «pulled»
  (общий `_wait_for_branch_ci_green`) — раньше это был отдельный
  инлайн-вызов внутри `_cmd_approve_merge_gate`; поведение при
  подтверждённо красном CI не меняется (тот же узел
  `_ci_confirm_red_or_flake`, та же семантика), меняется только то, что
  «нет проверок ещё»/«идёт» теперь не отказывают немедленно, а ждут.
- Откат: правка локализована в двух функциях (`fsm._pull_main_or_
  escalate` + новая `fsm._origin_main_sha`, `fsm_merge_gate._cmd_
  approve_merge_gate`); `git revert` двух коммитов возвращает прежнее
  поведение байт-в-байт, тестовая правка отменяется тем же revert.

## Риски

- Fetch добавляет один сетевой вызов на КАЖДЫЙ вход в `_pull_main_or_
  escalate` (было: только внутри уже отставшей ветки не считалось —
  теперь fetch происходит ДО решения «отстала или нет», иначе решение
  и не по чему принимать). Тот же характер стоимости уже несёт
  `fsm_merge_gate._origin_main_sha` на каждом заходе `merge_gate`, так
  что для этой точки это не новый класс стоимости, только для `in_dev
  -> review`/`acceptance -> merge_gate` эта пара вызовов теперь на
  каждом advance/approve, а не только при реальном отставании.
- Путь «fresh» на `merge_gate` теперь всегда проходит через
  `merge_lock.release`/повторный `merge_lock.acquire` даже когда CI
  оказывается зелёным с первого опроса (раньше — один локальный опрос
  без освобождения мьютекса между ним и merge). Мьютекс сам по себе
  сериализует только *merge*-окна разных задач, не блокирует остальную
  работу пульта — лишний цикл акгейр/релиз на пустом месте (CI уже
  зелёный) стоит одну лишнюю итерацию `_wait_for_branch_ci_green`
  (сразу `green=True`, без `sleep`), не заметно на практике.

## Предложения системе

(пусто)
