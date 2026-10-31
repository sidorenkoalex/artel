---
task: 01M69W4J5DSBFYS8A0FG71N93K
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Предпосылка теста fetch базы рабочей копии не зависит от версии git

## Подход
Правка одного вспомогательного метода долгоживущего файла
`tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py` (мандат Оператора
31.10.2026). `WorkspaceFetchSandbox.advance_origin` больше не пушит из git
пульта: коммиты создаются `git --git-dir <origin> commit-tree` прямо в
bare-репозитории (дерево `MAIN_BRANCH` там есть — `origin` синхронен после
`add_synced_origin`), голова ставится `git --git-dir <origin> update-ref
refs/heads/<MAIN_BRANCH> <new> <old>`. Git пульта ничего не отправляет —
поведение git 2.56 (обновление ссылки отслеживания при пуше по пути,
совпадающему с адресом `origin`) сценарий больше не задевает. Все вызовы
`--git-dir` идут с `-c user.name='artel tests' -c user.email=artel@example.invalid`
(значения `tests/sandbox.py:1276-1277`/`:1532-1533`): у bare-репозитория
своей идентичности нет. Число коммитов — `self.rng.randint(1, 3)`, как было;
обе проверки-предпосылки и возврат новой головы сохранены. Бюджет SPEC не
пересматривается.

## Шаги
1. `advance_origin`: commit-tree/update-ref в bare-репозитории с явной
   идентичностью; текст сообщения предпосылки про ссылку отслеживания —
   без слова «пуш»; строки документации модуля и метода — по новому
   способу. Карта `docs/codebase-map.md` перегенерирована (изменилась только
   `built_at_sha`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 (тесты AC-3/4/5 не тронуты; `self.assert*` 13 → 13, тестов 3 → 3) |
| 4 | 1 |
| 5 | 1 (код пульта не меняется: `git status` — только файл теста и карта) |
| 6 | 1 |

Проверки (локально, git 2.50):
- `python3 -m pytest tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 3 passed.
- То же в окружении AC-1 (`HOME` — пустой временный каталог,
  `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `EMAIL` удалена) —
  3 passed.
- Мутация AC-4: `workspace._fetched_base` с `tracking_refs=True` — AC-3 и
  AC-4 красные, AC-5 зелёный (2 failed, 1 passed); мутация откачена,
  `orchestrator/workspace.py` без изменений.
- Поведение на git 2.56 локально не проверить (нет такой версии) —
  подтверждает CI ветки задачи.

## Влияние на систему
Затронут только вспомогательный метод долгоживущего файла и его
строки документации; утверждения тестов AC-3/AC-4/AC-5 не менялись, их
число не уменьшилось, матрица неослабления SPEC выполняется (обе
предпосылки — те же `assertEqual`). Код пульта не меняется. Откат —
revert коммита ветки.

## Риски
- `update-ref` с ожидаемым старым значением отказывает, если голова
  `origin` не совпадает с прочитанной — в песочнице одного теста это
  невозможно, а если случится — отказ громкий (assert в `self.git`).

## Предложения системе
- Песочница не даёт помощника «git над bare-origin с идентичностью
  песочницы» — тесты, двигающие голову `origin`, повторяют `-c user.*`
  вручную (tests/sandbox.py, `RealGitSandbox`).
