---
task: 01M55V7WB94C9BZXTXTTH83YWV
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: CI ветки внешнего проекта: запросы gh к репозиторию проекта

# CI ветки внешнего проекта: запросы gh к репозиторию проекта

## Факты

Первая задача на sled (01M55SKHZ293CCAK0N7T4H7ZMR) стоит в `verifying`: ветка и коммит 9495860f есть в `origin` sled, PR sledproject/sled#17, CI sled идёт, а пульт трижды пишет «голова ветки не в origin — GitHub не нашёл коммит 9495860f (HTTP 422)». Задача остановлена командой `stop`, состояние сохранено.

Причина в `orchestrator/ci.py`:
- `check_runs(sha)` (`:143`) не принимает репозиторий проекта; `gh api repos/{owner}/{repo}/…` разрешает `{owner}/{repo}` по `cwd` пульта (`config.ROOT`, `:72`) — это репозиторий артели. Так же без репозитория проекта: `_commit_workflow_runs` (`:383`), `failed_check_names` (`:732`), `find_run_id` (`:1162`), `check_run_workflow_run` (`:1221`), `trigger_rerun` (`gh run rerun`/`gh run watch`, `:1235-1270`);
- `gh(..., repo=…)` (`:39-80`) дописывает `--repo <url>` в конец argv, но `gh api` флаг `--repo` не принимает («unknown flag: --repo»; проверено 18.10). Для `gh api` репозиторий задаётся переменной окружения `GH_REPO` (`GH_REPO=sledproject/sled gh api 'repos/{owner}/{repo}'` → `sledproject/sled`); `gh run`/`gh pr` принимают `--repo`;
- `verifying_status(branch, repo)` (`:600`) получает клон проекта, но дальше передаёт его только в `head_sha`; то же у `branch_status` (`:767`), `accepted_full_suite` (`:823`), `main_line_status` (`:1029`) — проверить по коду.
Пробел назван аудитом D2 (Т-5: «каждый вызов gh по задаче внешнего проекта несёт токен проекта… AC на verifying_status/trigger_rerun внешней задачи»); D2-2 (01M545EDTHS47HSB59AKC1EZ9C) закрыл токен, но не репозиторий.

## Требуется

1. Каждый вызов `gh` из `orchestrator/ci.py` по задаче внешнего проекта адресован репозиторию проекта (`url` записи `targets.yaml`) и несёт токен его слота (как сейчас `ci.gh(repo=…)`): для `gh api` — через `GH_REPO` (владелец/имя из `url`), без `--repo`; для `gh run`/`gh pr` — `--repo`, как сейчас. У артели argv, окружение и `cwd` вызовов не меняются ни на байт.
2. Репозиторий проекта доходит до всех функций CI на пути `verifying`, `ci-rerun`, автогейта приёмки и гейта мержа (проверка CI ветки и CI main после мержа) для задачи внешнего проекта; аналитик сверяет по коду полный перечень функций и вызывающих (`ci.py`, `ci_rerun.py`, `acceptance.py`, `fsm_merge_gate.py`, `advance_gates/`) и перечисляет его в SPEC.
3. До правки зафиксировать тестами argv, окружение и `cwd` вызовов `gh` артели для перечисленных функций.
4. Тесты детерминированы, без сети: подставной исполняемый `gh`, записывающий argv и `GH_REPO`/`GH_TOKEN`; учебный внешний проект — `verifying_status` и `branch_status` внешней задачи запрашивают проверки коммита у репозитория проекта и дают зелёный исход на зелёных проверках; `trigger_rerun` внешней задачи — у репозитория проекта.

Критерии приёмки:
- у артели вызовы `gh` перечисленных функций не изменились;
- у учебного внешнего проекта каждый `gh api` получает `GH_REPO=<владелец>/<имя>` проекта и токен слота, без `--repo`; `gh run`/`gh pr` — `--repo <url>` проекта;
- `verifying_status` внешней задачи с зелёными проверками коммита в репозитории проекта — зелёный исход, не «голова ветки не в origin».

Зоны: `orchestrator/ci.py`, `orchestrator/ci_rerun.py`, `orchestrator/acceptance.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/github_adapter.py`, `tests/`. В вызывающих модулях — только передача репозитория проекта, без изменения логики гейтов.

Только чтение: `orchestrator/advance_gates/`, `orchestrator/gitcmd.py`, `orchestrator/repo_context.py`, `orchestrator/targets.py`, `targets.yaml`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: мерж через `gh pr merge` для внешних проектов; защита ветки sled; задача sled 01M55SKHZ293CCAK0N7T4H7ZMR (продолжится после мержа).

Рамка: $35. Набор моделей — по умолчанию.
