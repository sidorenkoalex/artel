---
task: T045
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 2
---

# REVIEW: Worktree-норма: рабочая поверхность на задачу

## Фаза A — гейт плана

Без изменений с итерации 1: PLAN.md не менялся в этой итерации,
замечаний к плану как таковому нет.

## Соответствие SPEC

HEAD ветки задачи — коммит `1ed61c18639f570f04b35a03cfbaa257dff4b303`
(«T045: закрыты замечания ревью итерации 1-2 — workspace <id> под
lease»), непустой диф относительно коммита вердикта итерации 2
(`26e8b3620...`): `orchestrator/workspace.py`, `orchestrator/cleanup.py`,
`tests/test_workspace.py`, `docs/codebase-map.md`. Проверил построчно
все три замечания итераций 1-2 — все устранены фактическим кодом (не
только текстом), с тестами и зелёным прогоном.

1. **major (lease у `cmd_workspace`)** — устранено.
   `orchestrator/workspace.py:119-139`: `cmd_workspace` теперь берёт
   lease тем же приёмом, что `runner.cmd_run`/`cleanup.cmd_kill`
   (`lease.resolve_session_id` → `lease.acquire` → `sys.exit(refusal)`
   при отказе → работа в `_cmd_workspace` → `lease.release` в `finally`,
   только если lease взят с нуля). Сверил построчно с
   `orchestrator/runner.py:56-72` и `orchestrator/cleanup.py:115-127` —
   тот же паттерн, тот же порядок операций. Покрыто новым
   `CmdWorkspaceLeaseTest` (`tests/test_workspace.py:303-330`): чужой
   свежий lease отказывает без создания worktree (сверено
   `assertNotIn(str(self.wt_path()), self.worktree_list())`), свой lease
   с нуля освобождается после вызова. Прогнал `python3 -m unittest
   tests.test_workspace -v` — 23/23 зелёных, включая оба новых теста.
2. **minor (пустая причина отказа `remove()`)** — устранено.
   `orchestrator/workspace.py:112-115`: тот же фоллбэк по returncode,
   что уже был у `ensure()` (`res.stderr.strip()[:200] if ... and
   res.stderr else f"... вернул {res.returncode ...}"`). Покрыто
   `test_failure_with_empty_stderr_still_reports_a_reason`
   (`tests/test_workspace.py:250-266`) — зелёный.
3. **minor (устаревший комментарий `cleanup.py`)** — устранено.
   `orchestrator/cleanup.py:96-101`: комментарий переписан под
   worktree-норму («Оператор мог руками зачекаутить ветку задачи в
   ROOT»); логика ветки не тронута (диф — только комментарий).

Дополнительно проверил регенерацию карты (`docs/codebase-map.md`
`built_at_sha` == HEAD ветки `1ed61c1...`, запись `workspace.py`
получила `lease.py` в списке импортов) — соответствует правилу
`conventions-core`.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`workspace <id>` создаёт/выдаёт worktree) | OK | |
| 2 (агентные шаги в worktree) | OK | |
| 3 (мутирующие команды сверяют поверхность) | OK | `cmd_workspace` теперь под lease, как остальные мутирующие команды задачи (замечание итерации 1/2 устранено) |
| 4 (главная копия — территория оркестратора) | OK | |
| 5 (kill/done убирают worktree) | OK | |
| 6 (doctor не путает легитимный worktree с сиротой) | OK | |

## Проверка целостности и объёма правки

- Файлы этой итерации (`git diff --stat 26e8b36...HEAD`):
  `docs/codebase-map.md`, `orchestrator/cleanup.py`,
  `orchestrator/workspace.py`, `tests/test_workspace.py` — ровно то,
  что требовали замечания 1-3, без расширения зоны. `ci/`, `.github/`,
  `gates.yaml`, `roles.yaml`, `templates/`, `skills/` не тронуты.
- Ни один тест/гейт/лимит/guard не ослаблен и не удалён — правки только
  добавляют защиту (lease) и точность (фоллбэк причины отказа,
  актуальный комментарий).
- `python3 scripts/guard.py --all` — «GUARD: ок (137 файлов)».
- Полный набор тестов (`python3 -m unittest discover -s tests -p
  'test_*.py'`) — 697 тестов, 3 упавших: все три в
  `tests.test_multitarget.RoleEnvTest`
  (`test_env_carries_the_git_identity`,
  `test_identity_already_in_the_environment_is_not_overridden`,
  `test_absent_identity_is_journalled_before_the_step`). Перепроверил
  отдельно на чистом `main` через временный `git worktree` (без
  правок этой задачи) — те же три теста падают идентично: причина —
  `GIT_AUTHOR_NAME`/`GIT_COMMITTER_EMAIL` уже заданы в окружении самой
  сессии, `role_env()`'s `setdefault` корректно предпочитает их
  тестовой заглушке (as designed), а сам тест собирался без
  пред-заданного окружения. Не регрессия этой задачи и не относится к
  файлам её диффа (`test_multitarget.py` в этой итерации не менялся).
  AC-10 по существу выполнен: единственные красные тесты —
  environment-зависимые и воспроизводятся байт-в-байт на `main`.

## Замечания

Замечаний нет.

## Вердикт

approved — все три замечания итераций 1-2 устранены фактическим кодом
(проверено построчно и тестами `tests/test_workspace.py`, 23/23
зелёных), полный набор тестов зелёный за вычетом трёх
environment-зависимых тестов `RoleEnvTest`, воспроизводящихся
идентично на чистом `main` (не регрессия), `guard.py --all` зелёный,
диф не выходит за рамки замечаний прошлой итерации.

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.
