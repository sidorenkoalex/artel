---
task: 01M6RN8EY72K25GZ60NSJVVEGG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Шаблон сообщения коммитов пульта в ветке задачи без сжатия: policy.commit_message_template

## Подход
- `orchestrator/targets.py`: поле `commit_message_template` в
  `LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS` (переносится в
  плоскую запись `_flatten`); проверка в `_check_delivery` формой
  `refuse("commit_message_template", …)`: непустая строка, подстановки
  только `{id}`, `{ref}`, `{title}`, `{text}`, `{ref}` — только при
  `policy.ref_required`. Константы `DEFAULT_COMMIT_MESSAGE_TEMPLATE =
  "{id}: {text}"`, `COMMIT_MESSAGE_PLACEHOLDERS` и чистая функция
  `render_template(template, values)` — однократная подстановка одним
  `re.sub` по шаблону (значения повторно не разбираются; цепочку
  `str.replace` из `pull.commit_title` не копирую — решение гейта SPEC).
  `target-set` берёт перечень из `LOCAL_FIELDS` — требование 5 без правки
  `projects.py`.
- `orchestrator/checkpoint.py`: `pult_subject(conn, task_id, text, *,
  journal=True)` — первая строка коммита пульта кодовой ветки: запись
  проекта задачи (`targets.target`, деградация на `{}` как
  `gitcmd._project_entry`), `{ref}` — первая ссылка системы
  `ref_required` (правило `commit_title`), `{title}` — название или id.
  Нет ссылки при `{ref}` — умолчание и (при `journal`) запись журнала
  `шаблон сообщения не применён` / `нет ссылки системы <система>`.
  Применяется в общей обвязке `_commit_worktree_change` — через неё идут
  все шесть чекпоинтов (`:369`, `:776`, `:821`, `:925-934`, `:1572`):
  сообщение `<id>: <текст>` разбирается на текст и собирается шаблоном.
  Подпись `gitcmd.pult_message` не трогаю. Строка задачи читается только
  функциями `store` (`task_exists`, `task_target`, `get_task`) — SQL вне
  `store.py` запрещён сторожем `tests/test_multitarget.py::SqlOnlyInStoreTest`
  (возврат из verifying: прямой `conn.execute` в `task_project_entry` и
  `pult_subject` заменён на эти функции, `store.py` не тронут).
- `orchestrator/pull.py` (`_auto_resolve_conflict`, `_run_merge`) и
  `orchestrator/amend.py` (`_commit_long_lived`) зовут
  `checkpoint.pult_subject` для своего служебного текста; `_run_merge`
  получает `conn` параметром.
- `orchestrator/advance_gates/review.py`:
  `_latest_developer_commit_iso_date(branch, task_id, conn=None)` отсеивает
  тему с прежним префиксом `<id>: подтяжка ` и тему, равную
  `pult_subject(conn, task_id, "подтяжка <base>", journal=False)`, где
  `<base>` — `base` записи проекта задачи. Нет строки задачи, записи или
  поля — только прежний префикс. Сравнение темы — на полное равенство,
  поэтому шаблон с текстом после `{text}` опознаётся, а коммит кода по
  шаблону — нет.
- Ревью, итерация 1, R1-F1: git при `commit -m` срезает пробелы в конце
  строк, а `%s` склеивает строки первого абзаца — побайтное сравнение с
  сырым `pult_subject` пропускало подтяжку по шаблону с пробелом в конце
  (или с переводом строки в названии задачи). Закрыто двумя слоями:
  (а) `_check_delivery` отказывает шаблону с `\n`/`\r` (шаблон описывает
  первую строку; `target-set` такое значение и так не пишет, а
  локальный слой не раскрывает `\n` — проверка держит свойство для любого
  источника); (б) ожидаемая тема нормализуется `_git_subject`
  (`advance_gates/review.py`) тем же правилом, что git, тема из `git log`
  сравнивается после `rstrip()`. Сторож —
  `tests/test_commit_message_template_subject.py` (сверка `_git_subject`
  с настоящим `git log --format=%s`, рубеж на пробеле в конце и
  многострочном названии, отказ многострочного шаблона).

## Шаги
1. Поле, проверка и `render_template` в `targets.py`.
2. `pult_subject` и применение в `_commit_worktree_change` (`checkpoint.py`).
3. Применение в `pull.py` (два места подтяжки) и `amend.py`.
4. Опознание подтяжки рубежом ревью (`advance_gates/review.py`).
5. Карта `docs/codebase-map.md` (`python3 scripts/codebase_map.py`),
   прогон долгоживущих файлов задачи и тестов затронутых модулей.
   Свойства требований 1-6 покрыты
   `tests/test_01m6rn8ey72k25gz60nsjvvegg_*.py`; свойство, не покрытое
   ими (нормализация темы git, R1-F1), — новым
   `tests/test_commit_message_template_subject.py`.
6. Закрытие R1-F1: отказ многострочному шаблону (`targets.py`),
   `_git_subject` в опознании подтяжки (`advance_gates/review.py`), тест.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 2, 3 |
| 4 | 2 |
| 5 | 1 |
| 6 | 4, 6 |

## Влияние на систему
- Без поля умолчание `{id}: {text}` даёт прежнее сообщение побайтно:
  `_commit_worktree_change` пересобирает `<id>: <текст>` в то же самое;
  сообщения журнала (detail чекпоинтов) не меняются — шаблон касается
  только текста коммита.
- Коммиты артефактной ветки (`artifact_branch`, `_commit_step_artifacts_to_branch`)
  и сжатый коммит (`pull.commit_title`) не трогаются.
- Рубеж «замечания ревью не отработаны» не ослабляется: прежний префикс
  отсеивается как раньше, добавлено только опознание темы подтяжки по
  шаблону (без него требование 3 открыло бы обход рубежа). Существующий
  тест без строки задачи в БД (`tests/test_fsm_review_rework_gate.py`)
  идёт по ветке деградации.
- Откат — revert merge-коммита задачи; поле в записи проекта после
  отката отвергается загрузкой как «неизвестное поле» — его надо снять
  `target-set`/правкой локального слоя.

## Риски
- Шаблон без `{text}` (например `"{ref}: {title}"`): тема подтяжки
  совпадает с темой чекпоинта кода — рубеж отсеет и чекпоинт кода
  пульта (наблюдение аналитика в SPEC, решением не разобрано, AC-8 не
  проверяет).
- Смена шаблона `target-set` посреди `in_dev` с `changes_requested` —
  риск принят Оператором (SPEC «Не входит»).

## Предложения системе
