---
task: 01M69W4J5DSBFYS8A0FG71N93K
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Предпосылка теста fetch базы рабочей копии не зависит от версии git

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–6 → шаг 1. Один шаг — адекватно
  объёму (правка одного вспомогательного метода).
- Подход (commit-tree/update-ref в bare-репозитории с `-c user.*`) прямо
  следует требованиям 1 и 6 SPEC и не противоречит архитектуре: код пульта
  не тронут, `tests/sandbox.py` не тронут.
- «Влияние на систему» = фактический diff: тестовый файл + строка
  `built_at_sha` в `docs/codebase-map.md` (`git diff a6af742bf --stat`).
  Откат — revert коммита.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `advance_origin` (`tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py:57-80`): `git --git-dir <origin> commit-tree` в цикле `self.rng.randint(1, 3)`, затем `update-ref refs/heads/<MAIN_BRANCH> <new> <old>`; `git push` удалён. `self.git` идёт с `cwd` пульта, но `--git-dir` перенаправляет все команды в bare-репозиторий. |
| 2 | OK | Обе `assertEqual`-предпосылки (`origin_head() == sha`, `rev(tracking) == tracking_before`) на месте, изменён только текст сообщения (без слова «пуш»); `return sha` сохранён. |
| 3 | OK | Тела тестов AC-3/AC-4/AC-5 в diff не входят; `self.assert*` 13 → 13, `def test_` 3 → 3 (подсчёт `git show <rev>:… \| grep -c` на a6af742bf и HEAD). |
| 4 | OK | Docstring модуля и метода описывают commit-tree/update-ref в bare-репозитории; «пуш по пути» как способа сдвига в них нет (в модуле осталось «заведена пушем» про начальную ссылку отслеживания — это про `add_synced_origin`, вне сдвига, корректно). |
| 5 | OK | `orchestrator/` в diff отсутствует. |
| 6 | OK | `origin_git` несёт `-c user.name=artel tests -c user.email=artel@example.invalid` — те же значения, что `tests/sandbox.py:1276-1277`; применяется ко всем вызовам `--git-dir`, включая `commit-tree`. |

AC-1…AC-5 подтверждены исполнением (ниже). Мелочь вкуса, не замечание:
строка docstring модуля `:14` длиннее соседних (перенос не выровнен) —
на поведение и проверки не влияет.

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved — правка ровно в зоне мандата, предпосылки и проверки тестов
сохранены, чувствительность к мутации AC-4 подтверждена, CI ветки (git
2.56) зелёный.

## Проверено исполнением
- `python3 -m pytest tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py -p no:cacheprovider -q` (git 2.50 локально) — 3 passed.
- Тот же прогон в окружении AC-1 через `python3 -c` + `subprocess` с env: `EMAIL` удалена, `HOME=/var/empty`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` — 3 passed, код 0.
- Временная мутация AC-4: `orchestrator/workspace.py::_fetched_base` `tracking_refs=False` → `True` — FAILED `test_ac3_ensure_succeeds_with_locked_tracking_ref`, FAILED `test_ac4_ensure_fetch_does_not_move_tracking_ref`, 1 passed (AC-5); мутация откачена `git checkout -- orchestrator/workspace.py`, `git status --short` пуст.
- Подсчёт неослабления: `git show a6af742bf:<файл> | grep -c "self.assert"` = 13, на HEAD = 13; `def test_` 3 / 3.
- `git diff a6af742bf -- docs/codebase-map.md` — изменена только строка `built_at_sha`.
- Поведение на git 2.56 локально не воспроизводимо; по пакету CI коммита c9aa7103 (HEAD ветки) зелёный, 16 проверок.

## Предложения системе
- Песочнице пригодился бы помощник «git над bare-origin с идентичностью песочницы» (`tests/sandbox.py`) — согласен с предложением PLAN: иначе каждый тест, двигающий голову `origin`, повторяет `-c user.*` вручную.
