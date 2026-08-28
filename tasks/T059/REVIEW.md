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
закрывает все 6 требований SPEC; требование 4 корректно помечено «код
уже worktree-осведомлён с T048 — без изменений», проверено прогоном
`tests/test_timeout_checkpoint.py` без правок — 14/14 зелёных). Шаги —
два: продуктовый код + юнит-тесты одним шагом, правка адреса тестов
T041 — вторым; оба проверяемые единицы размера MR, не микрооперации.
Подход (вынос общей git-обвязки в `_commit_worktree_change`, тот же
держатель авторства `fixation.FIXATION_AUTHOR_*`, ограничение
догфудом) не конфликтует с существующей архитектурой
`commit_timeout_checkpoint` (T041/T048) — почти буквальный повтор уже
принятого паттерна. Раздел «Влияние на систему» соответствует
фактическому diff (см. «Системная целостность» ниже).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `commit_step_artifacts` вызывается в `run_agent_once` (orchestrator/runner.py:726) после ранних `return` для веток `timed_out`/`rc != 0`, то есть только на `rc == 0`, до журнала «agent run finished» (runner.py:727) и до возврата `"ok"`; `advance` — отдельная команда, запускается позже. Сообщение коммита (`f"{task_id}: артефакты шага {role} (автокоммит оркестратора)"`, runner.py:516) и `actor="orchestrator"` в `store.journal` (runner.py:521) точно совпадают с формулировкой SPEC. Подтверждено прогоном `test_ac1_successful_step_with_uncommitted_changes_autocommits` (зелёный), в т.ч. дошедшим до реального `fsm.cmd_advance` без инцидента целостности. |
| 2 | OK | `_commit_worktree_change` (runner.py:527) возвращает `(False, "")` при `diff --cached --quiet` == 0 (returncode 0 — нечего коммитить, строка 541), тогда `commit_step_artifacts` возвращает `""` до `store.journal`/`store.record_fixation`. Подтверждено `test_ac2_role_committed_changes_itself_no_empty_autocommit` (HEAD не сдвигается поверх коммита роли) и юнит-тестом `test_clean_tree_commits_nothing_and_journals_nothing`. |
| 3 | OK | `git add` идёт через `gitcmd.in_repo(wt, "add", "-A")`, где `in_repo` — обёртка `git("-C", str(repo), *args)` (gitcmd.py:84-95): `-C wt` ограничивает всю git-команду репозиторием `wt = workspace.path(task_id) = config.WORKTREES / task_id` (workspace.py:21-23) — отдельным от `config.ROOT`. `test_ac3_timeout_checkpoint_stays_in_task_worktree` прямой проверкой подтверждает, что посторонний файл в `self.root` не коммитится и не получает `add` (то же ограничение общее у чекпоинта и автокоммита — они делят один хелпер). |
| 4 | OK | Продуктовый код `commit_timeout_checkpoint` не тронут по существу (только рефакторинг в общий хелпер `_commit_worktree_change`, поведение идентично — сверено построчно со старой версией по diff); `tests/test_timeout_checkpoint.py` не менялся и зелёный без правок (14/14, прогнано). |
| 5 | OK | Правки `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py` — только адрес дерева (`config.TASKS / self.TASK` → `workspace.path(self.TASK) / "tasks" / self.TASK`, добавлен импорт `workspace`) и вызовы (`gitcmd.is_clean(repo=...)`, `self.git_in_worktree(...)`); сценарии AC-1/AC-3/AC-4, порядок вызовов и тексты ассертов не менялись — сверено построчно по diff. Тест был красным на `main` (дефект SPEC «Контекст») и зелёный после правки (4/4, прогнано). |
| 6 | OK | `_commit_worktree_change` отказывает молчанием (`return False, ""`) на любом из трёх git-шагов; `gitcmd.git` ловит `OSError` и возвращает `CompletedProcess` с ненулевым кодом вместо исключения (gitcmd.py:15-19) — исключение из `commit_step_artifacts` не улетит наверх и не уронит шаг. Покрыто тремя юнит-тестами (`test_git_add_failure_*`, `test_git_diff_failure_*`, `test_git_commit_failure_*`). |

Критерии приёмки — все 5 (AC-1..AC-5) проверены самостоятельным
прогоном, а не приняты со слов PLAN: `tasks/T059/acceptance_tests/test_autocommit_and_checkpoint.py`
(4/4 зелёных), `tests/test_step_autocommit.py` (8/8),
`tests/test_timeout_checkpoint.py` (14/14 в сумме с предыдущим),
`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py` (4/4,
включая ранее красный по SPEC «Контекст» тест), полный прогон
`python3 -m unittest discover -s tests` — 802 теста, все зелёные,
`scripts/guard.py --all` → «ок (193 файлов)»,
`scripts/codebase_map.py --check` — карта свежая (единственный
локальный дифф после прогона — обновление `built_at_sha` самим
`--check` до текущего HEAD, не содержательное расхождение; отменён
после проверки, чтобы не примешиваться к артефакту ревью).

## Корректность

Граничные случаи покрыты: чистое дерево (молчание), грязное дерево
(коммит), отказ git на каждом из трёх шагов add/diff/commit,
не-догфуд target (тихий no-op до первого git-вызова —
`test_non_dogfood_target_skips_autocommit` проверяет
`git_mock.assert_not_called()`), провал шага по rc (нет чекпоинта,
инвариант 30 не тронут — `test_ac4_return_code_failure_creates_no_checkpoint`),
таймаут с посторонним файлом в ROOT (AC-3). Порядок вызова в
`run_agent_once` (после ранних `return` для `timed_out`/`rc != 0`, до
финального журнала) проверен чтением файла напрямую
(orchestrator/runner.py:700-731) — совпадает с заявленным в PLAN
«сразу по получении `rc == 0`». Деградация без git (`gitcmd.git`
ловит `OSError`, требование 6) проверена чтением gitcmd.py:9-19 —
исключение не пробивается наверх ни при одном из трёх шагов.

## Тесты

`tests/test_step_autocommit.py` и
`tasks/T059/acceptance_tests/test_autocommit_and_checkpoint.py`
покрывают требования, а не структуру: мысленный мутационный тест —
удаление вызова `commit_step_artifacts` из `run_agent_once` завалит
AC-1 (advance наткнётся на грязное дерево) и юнит-тест на грязном
дереве; инверсия условия `staged.returncode != 1` завалит AC-2 и
`test_clean_tree_commits_nothing_and_journals_nothing`; замена `wt` на
`config.ROOT` в `_commit_worktree_change` завалит AC-3 (посторонний
файл ROOT попал бы в коммит и в `git add`). Тесты реальные
(`RealPultGitTest`, настоящий git в песочнице), не заглушка вызовов —
тот же приём, что уже был принят для `commit_timeout_checkpoint` в
T041. Все перечисленные тесты прогнаны лично в рамках этого ревью, а
не приняты по утверждению PLAN/предыдущего прогона.

## Простота

`_commit_worktree_change` устраняет дублирование git-обвязки между
двумя функциями без лишней абстракции — параметров ровно два (`wt`,
`message`), никакой преждевременной параметризации под гипотетическое
будущее расхождение (риск честно назван в PLAN). Изменение минимальное
и локализовано в `orchestrator/runner.py`.

## Безопасность

Изменённые файлы — `orchestrator/runner.py`, тесты
(`tests/test_step_autocommit.py`, правки `tests/test_review_package.py`),
артефакты `tasks/T059/*` и `tasks/T041/acceptance_tests/*`,
`docs/codebase-map.md`; ни одного защищённого пути (`gates.yaml`,
`roles.yaml`, `.github/`, `templates/`, `skills/`) diff не задевает.
Секретов, инъекций и недоверенного ввода в diff нет.

## Системная целостность (ADR-0002)

Ни один существующий тест/гейт/лимит/guard не ослаблен: полный прогон
`tests/` (802) зелёный без исключений и `xfail`, `scripts/guard.py --all`
проходит. Правки `tests/test_review_package.py` только расширяют
список ожидаемых git-вызовов (два новых вызова `add -A`/
`diff --cached --quiet` в worktree — реальное следствие нового кода)
и патчат `config.WORKTREES`, чтобы `workspace.path` в этом сценарии не
утекал на реальный путь пульта — это укрепление изоляции песочницы, а
не ослабление ассерта (список git-вызовов в тесте остаётся точным
`assertEqual`, не ослаблен до «содержит»). Правки тестов T041 — только
адрес дерева, без изменения сценариев (требование 5, проверено
построчно по diff). Инвариант 30 не тронут: условие автокоммита
(`rc == 0`) и условие чекпоинта (таймаут) взаимно исключающие по
построению — `run_agent_once` возвращается на каждой из веток
`timed_out`/`rc != 0` раньше, чем доходит до строки с автокоммитом
(runner.py:700-726). «Влияние на систему» в PLAN соответствует
фактическому diff — затронут только `orchestrator/runner.py` (успешная
ветка `run_agent_once`), `fsm.py`/`guard.py`/advance-логика не
изменены (проверено по diff — эти файлы в нём не встречаются). Откат
описан и правдоподобен (ревёрт коммита правки `runner.py` возвращает
поведение к прежнему — роль вручную спасается Оператором).

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
