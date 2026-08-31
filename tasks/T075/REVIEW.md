---
task: T075
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 2
---

# REVIEW: ANSWER-артефакт: канал ответа Оператора на эскалацию

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (шаблон ANSWER, guard) | OK | `templates/ANSWER.md` несёт требуемый frontmatter; `guard.py::RULES["answer"]` (sections=["Ответы"], statuses={"ready"}) заведён и подтверждён прогоном `guard.py --all` (252 файла, ок) и `test_ac1_*`. |
| 2 (команда `answer`) | реализовано не так | Команда есть, диспетчеризована, коммитит, журналирует (AC-2 зелёный на реальном git) — но `git add -A tasks/<id>` не ограничен новым файлом ответа и рискует незаметно закоммитить посторонние незакоммиченные изменения того же worktree под коммитом «ANSWER создан» (замечание major ниже). |
| 3 (гейт возврата) | OK | Три места эскалации класса «вопрос роли» простановляют `answer_baseline`-снимок в момент эскалации; `approve` из `escalated` отказывает без роста count (`_cmd_approve`, ветка `escalated`) — подтверждено AC-3 и `tests/test_answer_gate.py` (второй раунд). |
| 4 (видимость в брифе) | OK | `developer_brief`/`analyst_map_component`/`test_author_answer_component` добавляют ANSWER (и QUESTIONS для analyst) — подтверждено AC-6 и `tests/test_brief.py`. Ветко-корректное чтение (`foreign=True`) для НОВЫХ функций `_answer_file_count`/`_branch_or_disk_text`/`_latest_answer_rel` не покрыто ни одним тестом диффа (замечание major ниже) — я проверил вручную (мок `on_foreign_branch=True` + `ls_tree_files`/`show`), код корректен, но регресс на этом пути тестами не пойман. |
| 5 (право пересмотра тестов не меняется) | OK | Диффом не тронуто — `orchestrator/acceptance.py` и механика лока приёмочных тестов вне diff'а. |

AC-1..AC-6 — зелёные (17 приёмочных тестов T075, `unittest discover -s tasks/T075/acceptance_tests`). AC-7 — зелёный (`unittest discover -s tests`, 981 тест). Оба замечания ниже — не про красноту тестов, а про то, что часть рисков T075 сама создаёт (незаметный commit постороннего, непокрытый branch-aware путь) тестами не поймана.

## Замечания

- major — `orchestrator/answer.py:80` (`gitcmd.in_repo(wt_path, "add", "-A", rel)`, `rel = f"tasks/{task_id}"`) — стейджинг не ограничен новым `ANSWER-n.md`, а захватывает ЛЮБЫЕ незакоммиченные изменения во всём `tasks/<id>` того же (переиспользуемого на протяжении жизни задачи) worktree. `workspace.ensure` (orchestrator/workspace.py:42-65) не чистит рабочее дерево — если предыдущий шаг (например, developer/test_author, чей прогон упал внутри `AGENT_ATTEMPTS` не закоммитив свою правку, или Оператор, вручную поправивший что-то в worktree) оставил там незакоммиченный файл, `answer` молча включит его в коммит с сообщением `"{task_id}: ANSWER-{n} — ответ Оператора"` — история задачи станет недостоверной, а Оператор фактически закоммитит чужую правку, не видя и не одобряя её явно (это прямо противоречит формулировке AC-2 «Оператор не правит worktree руками» — тут наоборот, worktree правит кто-то другой руками, а Оператор об этом не узнаёт). `catalog.cmd_new` использует тот же приём (`add -A tasks/<id>`, orchestrator/catalog.py:160), но там это безопасно — каталог задачи только что создан этим же вызовом и физически не может нести посторонний мусор; `answer` же работает на каталоге с уже долгой историей задачи (SPEC.md, PLAN.md, acceptance_tests/, возможно REVIEW.md), так что это не то же самое, доказанное ранее допущение. Предложение: ограничить `git add` только новым файлом (`gitcmd.in_repo(wt_path, "add", "--", str(answer_path.relative_to(wt_path)))`), либо явно отказывать, если `git status --porcelain` worktree показывает изменения вне только что созданного `ANSWER-n.md`.

- major — `orchestrator/fsm.py:499-517` (`_answer_file_count`, ветка `on_foreign_branch`) и `orchestrator/brief.py` (`_branch_or_disk_text`, `_latest_answer_rel`, обе — ветка `foreign`) — ветко-корректное чтение ANSWER/QUESTIONS, которое сам PLAN называет «обычным случаем в проде после T048», не покрыто НИ ОДНИМ тестом этого диффа: все новые тесты (`tests/test_answer_gate.py`, `tests/test_brief.py::AnswerComponentTest`, `tasks/T075/acceptance_tests/_sandbox.py`) используют заглушку `gitcmd.git = fake_git`, при которой `on_foreign_branch()` всегда `False` — упражняется только дисковая ветка кода. Я проверил вручную (мок `gitcmd.on_foreign_branch → True` + `ls_tree_files`/`show`): код сейчас корректен (верно выбирает `ANSWER-10.md` как последний по числовому, не строковому сравнению, верно считает 3 файла). Но ни один тест не упадёт, если этот путь сломается при будущей правке — тот же класс риска, который докстринг `_answer_file_count` и PLAN («Влияние на систему») сами формулируют как повод для branch-aware чтения («без него гейт был бы сломан в проде при видимом зелёном прогоне тестов») — только не для самого чтения, а для его тестового покрытия: репозиторий уже несёт готовый инструмент именно для этого (`tests/test_fsm_branch_correct_status_reads.py::RealGitBranchTest` — worktree на реальном git, тот же приём, что и для `_developer_spec_text`/QUESTIONS.md T031/T047), но он не переиспользован для ANSWER. PLAN («Подход», п.3) сознательно объявляет эту ось «ортогональной критериям T075» и не покрывает её приёмочными тестами — это решение обосновано для критериев (AC не формулирует требование к branch-aware чтению явно), но не отменяет п.3 review-checklist («падают ли тесты, если сломать реализацию») именно для кода, который сам PLAN называет обычным продовым путём. Предложение: как минимум один юнит-тест с мок `on_foreign_branch=True`+`ls_tree_files`/`show` на `_answer_file_count`/`_answer_component`/`_questions_component`; в идеале — тест на базе `RealGitBranchTest` по образцу `QuestionsOnForeignBranchTest`.

- minor — `orchestrator/fsm.py` (4 места: ~646, ~666, ~774, ~793 — все вызовы `answer_baseline=_answer_file_count(t, tdir) or 0`) — `None` от `_answer_file_count` (git не ответил на чужой ветке) молча превращается в снимок `0`, а не в отказ, хотя весь остальной модуль на git-сбоях того же класса отказывает громко (`_read_branch_text_or_refuse`, отказ по `q_paths is None` несколькими строками выше). Сегодня риск низкий: в каждой из 4 точек `_answer_file_count` вызывается сразу после того, как та же функция (`gitcmd.ls_tree_files`/`gitcmd.show`) на той же ветке уже успешно отработала мгновение назад в этом же вызове — но стиль расходится с остальным модулем и маскирует именно тот класс сбоя («git не ответил»), от которого рядом стоящий код специально защищается. Предложение: как и везде рядом, при `None` — не глотать в `0`, а явно отказать переходу (тот же приём, что и у `q_paths is None`).

## Вердикт

changes_requested — до мержа поправить оба major-замечания: (1) `orchestrator/answer.py` — ограничить `git add` только новым `ANSWER-n.md` (не всем `tasks/<id>`), чтобы `answer` не мог незаметно закоммитить чужие незакоммиченные изменения; (2) добавить хотя бы юнит-тест на `foreign=True` ветку `_answer_file_count`/`_answer_component`/`_questions_component` (ANSWER/QUESTIONS на чужой ветке) — единственный сегодня непокрытый производственный путь этой задачи. Minor-замечание (тихий `or 0` на git-сбое) — по усмотрению разработчика, не блокирует.

## Проверено исполнением

- `python3 -m unittest discover -s tests` — 981 тест, все зелёные (OK).
- `python3 -m unittest discover -s tasks/T075/acceptance_tests -v` — 17 тестов (AC-1..AC-6), все зелёные (OK), включая `RealPultGitTest`-сценарий AC-2 на настоящем git.
- `python3 scripts/guard.py --all` — «ок (252 файлов)».
- `python3 scripts/codebase_map.py` в рабочей копии и сверка `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha`, содержимое карты свежее (изменение откатил, чтобы не трогать код).
- Ручная проверка `orchestrator/fsm.py::_answer_file_count` и `orchestrator/brief.py::_latest_answer_rel/_branch_or_disk_text` веткой `on_foreign_branch=True` (мок `gitcmd.on_foreign_branch`/`ls_tree_files`/`show`, вне тестового диффа, только для ревью) — код корректен (верно выбирает `ANSWER-10.md` численным сравнением, верно считает 3 файла), но это именно тот путь, который замечание major #2 просит покрыть тестом на постоянной основе.
- Прочитано вручную: `orchestrator/answer.py` целиком, `orchestrator/fsm.py` (диффовые участки + окружающий контекст `_cmd_advance`/`_cmd_approve`), `orchestrator/brief.py` (диффовые функции), `orchestrator/store.py` (SCHEMA/migrate/update_task), `orchestrator/workspace.py::ensure` (для замечания major #1 — подтверждено отсутствие очистки worktree), `orchestrator/catalog.py::cmd_new` (для сравнения паттерна `add -A`), `orchestrator/runner.py:190-260` (доставка `brief_text` для `test_author`), `scripts/guard.py` (RULES + `--all` сканирование `tasks/**/*.md` по `rglob`), `tests/test_fsm_branch_correct_status_reads.py::RealGitBranchTest` (существующий инструмент для замечания major #2).

## Предложения системе

- (см. также PLAN.md «Предложения системе» — сканер AC-маркеров по всем `*.py`, не только `test_*.py`, уже отмечен разработчиком, повторно не поднимаю.)
