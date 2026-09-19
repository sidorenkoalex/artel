---
task: 01M2XMCC837R5CX9M58VARK85G
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/git-hooks/, orchestrator/gitcmd.py, orchestrator/repo_context.py, orchestrator/doctor/, docs/operator-session.md, tests/
budget_usd: 35
---

# SPEC: Защита main главной копии: git-хуки от ручных коммитов и push в main, маркер команд пульта, включение через doctor --fix

## Контекст
В главной копии пульта нет ни одного git-хука (`.git/hooks` пуст,
`core.hooksPath` не задан), а единственный сторож — проверка `doctor`
«pin-unpushed» (`orchestrator/doctor/root_pin.py::check_pin_unpushed`) —
видит незапушенные коммиты уже постфактум. Правило «HEAD главной копии
без локальных коммитов» держится только памятью сессии: 19.09
ассистентская сессия трижды закоммитила `docs/backlog.md` прямо в main
главной копии в обход команды `note`, после мержа задачи HEAD отстал от
origin на четыре коммита и прямой push стал невозможен без запрещённого
pull. При этом ни одна команда пульта не создаёт коммитов на ветке main
главной копии, а все её обращения к git идут через `orchestrator/gitcmd.py`
(`git`, `in_repo`, `carpentry`) и `orchestrator/repo_context.py::git` —
значит правило можно сделать программным: хуки отказывают всем, а команды
пульта помечают себя переменной окружения.

## Требования

1. Хуки в репозитории: `scripts/git-hooks/pre-commit` и
   `scripts/git-hooks/pre-push` на POSIX sh, использующие только git и
   стандартные утилиты (PATH роли ограничен манифестом стека).
   `pre-commit` отказывает коммиту, если текущая ветка — main и в
   окружении нет маркера пульта (требование 3). `pre-push` читает пары
   refs со stdin и отказывает, если среди целевых refs есть
   `refs/heads/main` и маркера нет.
2. Текст отказа обоих хуков именованный: «коммит/push в main главной
   копии — только командой пульта (note, doc-commit, pin-update, approve
   на merge_gate); обход по решению Оператора: ARTEL_PULT_GIT=1».
3. Коммиты и push веток `task/*`, `artifact/*` и refs `refs/artifacts/*`
   хуки не трогают.
4. Включение: `doctor --fix` ставит `git config core.hooksPath
   scripts/git-hooks` в главной копии и делает файлы хуков исполняемыми.
5. `doctor` без `--fix` несёт проверку «git-hooks»: `ok` при
   `core.hooksPath = scripts/git-hooks` и исполняемых файлах хуков, `fail`
   с подсказкой `doctor --fix` иначе.
6. Маркер пульта: `gitcmd.git`, `gitcmd.in_repo`, `gitcmd.carpentry` и
   `repo_context.git` добавляют в окружение своих процессов git
   переменную `ARTEL_PULT_GIT=1` — так команды пульта (push мержа,
   pin-update, note, doc-commit) проходят хуки, а ручной `git commit` /
   `git push` из оболочки сессии или Оператора — нет.
7. Прочие переменные окружения не меняются; для `carpentry` маркер
   добавляется поверх переданного ей явного env.
8. Процесс роли (`runner.role_env`) маркер НЕ получает: роль не вправе
   писать в main (сегодня и не пишет — только ветка задачи), хук здесь —
   вторая линия к `permissions.deny` курируемого слоя.
9. Тестовые песочницы (`tests/sandbox.py`, временные репозитории)
   конфигурацию главной копии не наследуют: существующие тесты не должны
   начинать упираться в хуки.
10. Документация: `docs/operator-session.md` получает абзац «Правки main
    только командами» с перечнем команд и маркером обхода (обычный
    документ, не защищённый путь).

## Критерии приёмки

AC-1. В репозитории существуют файлы `scripts/git-hooks/pre-commit` и
`scripts/git-hooks/pre-push`; оба — POSIX sh и обходятся только git и
стандартными утилитами (никаких python/bash-измов вне POSIX sh).

AC-2. Во временном репозитории с включёнными хуками (`core.hooksPath =
scripts/git-hooks`) `git commit` на ветке main без `ARTEL_PULT_GIT` в
окружении отказывает ненулевым кодом возврата, коммит не создаётся, а в
выводе присутствует именованный текст отказа требования 2.

AC-3. Тот же коммит на main с `ARTEL_PULT_GIT=1` в окружении проходит.

AC-4. Коммит на ветке `task/x` без маркера проходит.

AC-5. Push вида `<sha>:refs/heads/main` без маркера отказывает ненулевым
кодом с тем же именованным текстом отказа; с `ARTEL_PULT_GIT=1` тот же
push проходит.

AC-6. Push ветки `task/x` без маркера проходит; ветки `artifact/*` и refs
`refs/artifacts/*` хуками также не блокируются.

AC-7. `gitcmd.git`, `gitcmd.in_repo`, `gitcmd.carpentry` и
`repo_context.git` запускают дочерний процесс git с `ARTEL_PULT_GIT=1` в
его окружении.

AC-8. Прочие переменные окружения дочернего процесса не меняются; для
`carpentry` маркер добавлен поверх переданного ей env (переданные
`GIT_INDEX_FILE`, `GIT_AUTHOR_*`, `GIT_COMMITTER_*` сохраняются).

AC-9. Окружение, которое возвращает `runner.role_env`, маркера
`ARTEL_PULT_GIT` не содержит — в том числе когда переменная выставлена в
окружении процесса пульта.

AC-10. `doctor` без `--fix` даёт проверку с именем «git-hooks» со
статусом `ok`, когда `core.hooksPath = scripts/git-hooks` и файлы хуков
исполняемы, и `fail` с подсказкой `doctor --fix` в остальных случаях.

AC-11. `doctor --fix` выставляет `git config core.hooksPath
scripts/git-hooks` и делает файлы хуков исполняемыми; проверка «git-hooks»
после него — `ok`.

AC-12. `docs/operator-session.md` несёт абзац «Правки main только
командами» с перечнем команд (note, doc-commit, pin-update, approve на
merge_gate) и маркером обхода `ARTEL_PULT_GIT=1`.

AC-13. Полная сюита `tests/` зелёная, включая `tests/test_gitcmd_*.py`,
`tests/test_doctor.py`, `tests/test_runner_role_model.py`; песочницы и
временные репозитории тестов конфигурацию хуков главной копии не
наследуют.

## Оценка объёма и деление

Сработавшие сигналы:
- **число затрагиваемых модулей/файлов зоны** — 6 путей в `zones:`
  (порог `SPLIT_SIGNAL_ZONE_FILES` = 5);
- **число критериев приёмки** — 13 (порог `SPLIT_SIGNAL_AC_COUNT` = 10);
- **затронут инвариантный механизм** — зона `tests/` встречается в
  `docs/invariants.md` (реестр ссылается на тесты-свидетели).

Прогноз диффа: 15 КиБ (два коротких sh-скрипта, точечные правки
`gitcmd.py`/`repo_context.py`, одна проверка doctor, абзац документации,
один тестовый файл) — ниже порога сигнала (128 КиБ).

**Решение: монолит.** Разрезать по границам зон здесь нечего:
- хуки и проверка doctor без маркера (требования 1–5 отдельно от 6–7)
  дают заведомо неработоспособное промежуточное состояние — как только
  `core.hooksPath` включён, `pre-push` отказывает собственному push мержа
  пульта (`fsm_merge_gate::_push_merged_main` через `repo_context.git`),
  то есть мерж задач ломается на первом же `approve` на `merge_gate`;
- маркер без хуков (требования 6–7 отдельно) — переменная окружения без
  единого потребителя: мержится «зелено», но не даёт ни защиты, ни
  проверяемого поведения, и её единственный критерий приёмки — факт
  присутствия строки в env.

Смена механики атомарна: защита обязана включаться ровно тем коммитом, в
котором команды пульта уже помечены. Объём (15 КиБ диффа, рамка $35)
деления также не требует — обе части были бы по 2–3 файла.

## Не входит

- Включение хуков командой `init` (`orchestrator/catalog.py` — зона идущей
  задачи 01M2XJKQNF; отдельной строкой копилки после мержа).
- Хуки на стороне GitHub — защита ветки в настройках репозитория
  (действие Оператора).
- Хуки Claude Code на команды Bash.
- Команда `doc-commit` — парное ТЗ той же даты.
- Изменение `orchestrator/pin.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/notes.py`, `orchestrator/github_adapter.py`,
  `orchestrator/snapshot.py`: пути записи в origin только сверяются на
  прохождение хуков с маркером.
- Изменение `orchestrator/runner.py`: `role_env` остаётся как есть —
  сверяется, что маркер не протекает в роль через `os.environ` (белый
  список `stack.ROLE_ENV_ALLOWLIST`).

## Материалы

- Инцидент 19.09: три коммита `docs/backlog.md` в main главной копии в
  обход `note`; HEAD отстал от origin на четыре коммита.
- `orchestrator/doctor/root_pin.py::check_pin_unpushed` — постфактумный
  сторож, который эта задача дополняет превентивным.
- `orchestrator/stack.py::ROLE_ENV_ALLOWLIST` — белый список окружения
  роли (`runner.role_env`, строки 593–595 `orchestrator/runner.py`).
