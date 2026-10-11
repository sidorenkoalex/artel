---
task: T042
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Авто-коммит регенерированной карты кодовой базы оркестратором на merge_gate

## Подход
Встраиваю шаг регенерации/коммита карты в `orchestrator/fsm.py`,
`cmd_approve`, ветку `state == "merge_gate"` — между успешным
`git merge --no-ff` и `git push`, как требует SPEC (требования 1, 4).

Новая функция `_regenerate_and_commit_map(conn, task_id)`:
1. Читает текущий `docs/codebase-map.md` (закоммиченная версия — рабочее
   дерево на `merge_gate` чистое).
2. Гоняет `scripts/codebase_map.py` напрямую через `subprocess.run`
   (не `gitcmd.git` — это не git-вызов, требование 6 и AC-4 запрещают
   только обход `gitcmd.git` для git-команд; образец — `brief._regenerate_map`).
3. Сравнивает регенерированный текст с прежним, игнорируя строки
   `built_at_sha:` — та же сверка содержимым, что и CI-джоб
   `codebase-map` (`.github/workflows/ci.yml`, ред. Оператора 26.08),
   и что `brief._built_at_sha`/`_stale_paths`, но напрямую по содержимому,
   как явно требует SPEC требование 2.
4. Есть содержательная разница — `git add` + `git commit` через
   `gitcmd.git` (требование 2, 6).
5. Разницы нет — `git checkout -- docs/codebase-map.md` через `gitcmd.git`
   (требование 3, образец — `brief._regenerate_map`).
6. Любой шаг (чтение файла, регенерация, коммит, откат) падает — функция
   не бросает исключение и не делает `sys.exit`: журналирует провал и
   заводит `alerts.raise_alert(..., kind="incident", source="fsm.map_regen", ...)`,
   затем возвращает управление вызывающему коду (требование 5). Merge и
   переход в `done` эту функцию не видят как условие — она вызывается
   только ради побочного эффекта до `push`, который выполняется всегда,
   независимо от исхода.

`git push` в `cmd_approve` выношу из общего цикла merge-команд в отдельный
шаг после `_regenerate_and_commit_map`: раньше push был последним элементом
цикла `for cmd in (...)`, теперь между merge и push встаёт шаг карты, а
push остаётся условием `sys.exit` при провале — как и раньше, только его
провал (не провал шага карты) всё ещё отменяет переход в `done`.

Альтернатива — регенерировать карту тем же приёмом, что `brief.py`
(отдельный модуль), рассматривал и отклонил: SPEC явно указывает точку
встраивания `orchestrator/fsm.py` (материалы, требование 1), а логика
слишком мала (около 40 строк) и завязана на merge-последовательность,
чтобы обосновать отдельный модуль ради переиспользования с `brief.py` —
там другой контракт отказа (стухшая карта с пометкой в тексте брифа,
не коммит).

## Шаги

1. `orchestrator/fsm.py`: функции `_map_content_without_sha`,
   `_map_regen_incident`, `_regenerate_and_commit_map`; встраивание в
   `cmd_approve` (`merge_gate`); импорт `alerts` и `subprocess`.
   Юнит-тесты на новые функции (`tests/test_fsm_map_regen.py`) —
   содержательное сравнение (только `built_at_sha` отличается / текст
   отличается), провал чтения/регенерации/add/commit/checkout заводит
   incident-алерт и не бросает исключение. Прогон приёмочных тестов
   `tasks/T042/acceptance_tests/` (AC-1..AC-6). Регенерация
   `docs/codebase-map.md` тем же коммитом (правка `orchestrator/fsm.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |

## Влияние на систему
Затронут единственный горячий путь — `cmd_approve` в `merge_gate`,
единственная точка, где оркестратор пишет в `main` (инвариант
`MergeOnlyFromMergeGateTest`, `tests/test_invariants.py`, не ослабляется:
новый код не добавляет альтернативного пути к `git merge`/`git push`, он
только вставляет шаг МЕЖДУ уже существующими git-вызовами того же
перехода). Существующее условие «зелёный CI» и `sys.exit` при провале
`push` не трогаются. Новый инцидент `fsm.map_regen` — читаемый
`alerts.open_alerts(conn, "incident")`, тем же способом, что и остальные
incident-алерты (`brief.codebase_map`, `brief.codebase_map_restore`) —
Оператор увидит его через `doctor`/`alert-ack`, ничего нового заводить не
нужно. `.github/workflows/ci.yml` (джоб `codebase-map`) не трогается —
остаётся детектором ручной правки `.py` мимо конвейера (SPEC, «Не
входит»). Откат — `git revert` коммита этой задачи, поведение `merge_gate`
возвращается к прежнему (без шага карты).

## Риски
- Прямой `subprocess.run(["python3", ...])` в обход `gitcmd.git` — не
  дефект: требование 6 и AC-4 запрещают обход `gitcmd.git` только для
  git-вызовов, регенерация — не git-команда (тот же приём, что
  `brief._regenerate_map`, явно указан в материалах SPEC как образец).
- Если `docs/codebase-map.md` в момент `merge_gate` физически отсутствует
  на диске (не должно случаться — файл в репозитории с T027) —
  `_regenerate_and_commit_map` ловит `OSError` на чтении и заводит
  incident, не падает.
