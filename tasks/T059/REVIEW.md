---
task: T059
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Автокоммит артефактов роли и worktree-чекпоинт

## Фаза A — проверка плана

Покрытие требований в PLAN полное (таблица «Покрытие требований»
закрывает все 6 требований SPEC, требование 4 корректно помечено «код
уже worktree-осведомлён с T048 — без изменений», что подтвердилось
прогоном). Шаги — два: продуктовый код + юнит-тесты одним шагом,
правка адреса тестов T041 — вторым; оба проверяемые единицы размера
MR, не микрооперации. Подход (вынос общей git-обвязки в
`_commit_worktree_change`, тот же держатель авторства
`fixation.FIXATION_AUTHOR_*`, ограничение догфудом) не конфликтует с
существующей архитектурой `commit_timeout_checkpoint` (T041/T048) —
почти буквальный повтор уже принятого паттерна. Раздел «Влияние на
систему» соответствует фактическому diff (см. «Системная
целостность» ниже).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `commit_step_artifacts` вызывается в `run_agent_once` (orchestrator/runner.py:723) после веток `timed_out`/`rc != 0`, то есть только на `rc == 0`, до журнала «agent run finished» и до возврата `"ok"` (advance — отдельная команда, запускаемая позже). Сообщение коммита и текст action журнала (`actor="orchestrator"`) точно совпадают с формулировкой SPEC. Подтверждено AC-1 (`tasks/T059/acceptance_tests`, зелёный). |
| 2 | OK | `_commit_worktree_change` возвращает `committed=False` при `diff --cached --quiet` == 0 (нечего коммитить) — коммит и `store.journal`/`store.record_fixation` не вызываются. Подтверждено `test_ac2_role_committed_changes_itself_no_empty_autocommit` и юнит-тестом `test_clean_tree_commits_nothing_and_journals_nothing`. |
| 3 | OK | `git add` идёт через `gitcmd.in_repo(wt, "add", "-A")` — `-A` без путей действует в пределах репозитория `wt` (worktree задачи через `-C`), не ROOT пульта. AC-3 явно проверяет: посторонний файл в `self.root` не коммитится и не получает `add` (`git status --porcelain` на ROOT после шага). |
| 4 | OK | Продуктовый код `commit_timeout_checkpoint` не тронут по существу (только рефакторинг в общий хелпер `_commit_worktree_change`, поведение идентично); `tests/test_timeout_checkpoint.py` не менялся и зелёный без правок, как и заявлено в PLAN. |
| 5 | OK | Правки `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py` — только адрес дерева (`config.TASKS` → `workspace.path(self.TASK)`) и вызовы (`gitcmd.is_clean(repo=...)`, `self.git_in_worktree(...)`); сценарии, порядок вызовов и тексты ассертов не менялись. Тест был красным на текущем `main` (дефект SPEC «Контекст») и зелёный после правки — проверено прогоном. |
| 6 | OK | `_commit_worktree_change` отказывает молчанием (`return False, ""`) на любом из трёх шагов git — то же поведение, что у `commit_timeout_checkpoint`; покрыто тремя юнит-тестами (`test_git_add_failure_*`, `test_git_diff_failure_*`, `test_git_commit_failure_*`). |

Критерии приёмки — все 5 (AC-1..AC-5) выполнены; AC-1..AC-4 прогнаны
как `tasks/T059/acceptance_tests/test_autocommit_and_checkpoint.py`
(4/4 зелёных), AC-5 — полный прогон `tests/` (802 теста, зелёные),
`tests/test_timeout_checkpoint.py` и
`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`
(4/4 зелёных, включая ранее красный по SPEC «Контекст»),
`scripts/guard.py --all` («ок»), `scripts/codebase_map.py --check`
(карта свежая, без диффа).

## Корректность

Граничные случаи покрыты: чистое дерево (молчание), грязное дерево
(коммит), отказ git на каждом из трёх шагов add/diff/commit,
не-догфуд target (тихий no-op до первого git-вызова —
`test_non_dogfood_target_skips_autocommit` проверяет
`git_mock.assert_not_called()`), провал шага по rc (нет чекпоинта,
инвариант 30 не тронут), таймаут с посторонним файлом в ROOT (AC-3).
Порядок вызова в `run_agent_once` (после ранних `return` для
`timed_out`/`rc != 0`, до финального журнала) проверен чтением файла
напрямую (orchestrator/runner.py:600-731) — совпадает с заявленным в
PLAN «сразу по получении `rc == 0`».

## Тесты

`tests/test_step_autocommit.py` и
`tasks/T059/acceptance_tests/test_autocommit_and_checkpoint.py`
покрывают требования, а не структуру: мысленный мутационный тест —
удаление вызова `commit_step_artifacts` из `run_agent_once` завалит
AC-1 (advance наткнётся на грязное дерево) и юнит-тест на грязном
дереве; инверсия условия `staged.returncode != 1` завалит AC-2 и
`test_clean_tree_commits_nothing_and_journals_nothing`; замена `wt` на
`config.ROOT` в `_commit_worktree_change` завалит AC-3 (посторонний
файл ROOT попал бы в коммит). Тесты реальные (`RealPultGitTest`,
настоящий git в песочнице), не заглушка вызовов — тот же приём, что
уже был принят для `commit_timeout_checkpoint` в T041.

## Простота

`_commit_worktree_change` устраняет дублирование 15 строк
git-обвязки между двумя функциями без лишней абстракции — параметров
ровно два (`wt`, `message`), никакой преждевременной параметризации
под гипотетическое будущее расхождение (риск честно назван в PLAN).
Изменение минимальное и локализовано в `orchestrator/runner.py`.

## Безопасность

Изменённые файлы — `orchestrator/runner.py`, тесты, артефакты
`tasks/T059/*` и `tasks/T041/acceptance_tests/*`,
`docs/codebase-map.md`; ни одного защищённого пути (`gates.yaml`,
`roles.yaml`, `.github/`, `templates/`, `skills/`) diff не задевает.
Секретов, инъекций и недоверенного ввода в diff нет.

## Системная целостность (ADR-0002)

Ни один существующий тест/гейт/лимит/guard не ослаблен: полный прогон
`tests/` (802) зелёный без исключений и `xfail`; правки
`tests/test_review_package.py` только расширяют список ожидаемых
git-вызовов (два новых вызова `add -A`/`diff --cached --quiet` в
worktree — реальное следствие нового кода) и патчат `config.WORKTREES`,
чтобы `workspace.path` в этом сценарии не утекал на реальный путь
пульта — это укрепление изоляции песочницы, а не ослабление ассерта.
Правки тестов T041 — только адрес дерева, без изменения сценариев
(требование 5, проверено построчно по diff). Инвариант 30 не тронут:
условие автокоммита (`rc == 0`) и условие чекпоинта (таймаут) взаимно
исключающие по построению (`run_agent_once` возвращается на каждой из
веток `timed_out`/`rc != 0` раньше, чем доходит до автокоммита).
«Влияние на систему» в PLAN соответствует фактическому diff — затронут
только `orchestrator/runner.py` (успешная ветка `run_agent_once`),
`fsm.py`/`guard.py`/advance-логика не изменены. Откат описан (ревёрт
коммита правки `runner.py`).

## Замечания

(нет)

## Вердикт

approved

## Предложения системе

- Согласен с наблюдением PLAN («Предложения системе»): `docs/invariants.md`
  стоит дополнить соседним с инвариантом 30 пунктом «автокоммит на
  `rc == 0` не создаёт пустой коммит» — тот же реестр закрыл бы
  проверку для следующей задачи класса «незакоммиченный артефакт» без
  чтения SPEC T059 напрямую.
