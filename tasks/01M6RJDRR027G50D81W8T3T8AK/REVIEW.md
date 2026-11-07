---
task: 01M6RJDRR027G50D81W8T3T8AK
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

## Фаза A: план
- Таблица покрытия полна: требования 1–6 → шаги 1–2 (требование 6 закрыто
  тем, что `target-set` берёт имена из `LOCAL_FIELDS` и проверяет запись
  загрузкой, без правки `projects.py`, — верно, AC-7/AC-8 зелёные).
- Шаги размера MR, подход повторяет `branch_template`/`commit_template` и
  `pull.commit_title` — с архитектурой не конфликтует.
- «Влияние на систему» совпадает с diff: изменены только
  `orchestrator/targets.py`, `orchestrator/github_adapter.py`, новый
  `tests/test_mr_title_template_units.py` (+ карта). `gitlab_adapter`,
  `forge`, `projects`, `store`, `pull` не тронуты. Откат — revert.
- ANSWER-1 (сдвиг номеров строк `projects.py`) учтён в шаге 4 плана; на код
  не влияет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py`: поле в `LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS`; в `_check_delivery` проверки непустоты, перечня `MR_TITLE_PLACEHOLDERS` и `{ref}` только при `ref_required` — тот же приём, что у `branch_template` (`targets.py:676-688`), отказ через `refuse` → `поле 'policy.mr_title_template'`. |
| 2 | OK | `DEFAULT_MR_TITLE_TEMPLATE = "{id}: {title}"`; `{title}` → `t["title"] or task_id` — побайтно прежняя формула (AC-2 на обоих путях зелёный). |
| 3 | OK | `_mr_title` (`github_adapter.py:32-54`) — построчно то же правило ключа, что `pull.commit_title` (`pull.py:926-940`, сверено чтением); ссылки читаются только при `{ref}`; порядок `{id}` → `{ref}` → `{title}`. |
| 4 | OK | Вызов `_mr_title` в `ensure_draft_mr` (`gh pr create`) и `open_forge_mr` (`forge.open_mr`); `gitlab_adapter` не менялся. |
| 5 | OK | Нет ссылки → журнал `шаблон заголовка MR не применён` / `нет ссылки системы <ref_required>`, шаблон по умолчанию, задача не останавливается; на обоих путях (AC-6 а/б). |
| 6 | OK | `target-set` пишет/отклоняет поле без правки `projects.py` (AC-7/AC-8). |

## Замечания
Замечаний уровня blocker/major/minor нет.

Наблюдение (не замечание, правки не требует): запись журнала из
`_mr_title` пишется до вызова хостинга, поэтому при отказе `gh pr create` /
`forge.open_mr` и повторной попытке на следующем переходе она повторится. SPEC
не ограничивает число таких записей; поведение безвредно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6rjdrr027g50d81w8t3t8ak_entry.py tests/test_01m6rjdrr027g50d81w8t3t8ak_mr_title.py tests/test_mr_title_template_units.py` — 28 passed.
- `artel.py plank-run 01M6RJDRR027G50D81W8T3T8AK` — «планки нет: … нет файлов test_*.py; pytest не запускался»: все критерии задачи закрыты долгоживущими файлами `tests/test_01m6rjdrr027g50d81w8t3t8ak_*.py`, их прогон выше.
- Временная мутация 1 (`if "{ref}" in template:` → `if True:` в `_mr_title`): `tests/test_mr_title_template_units.py` — 2 failed (заявка «ссылки читаются безусловно» подтверждена). Код возвращён.
- Временная мутация 2 (`{title}` подставляется первым): `test_template_without_ref_does_not_read_refs` и `test_ac9_gh_pr_create_first_ref_and_literal_ref_in_title` красные (2 failed, 12 passed). Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` — расхождений в карте нет, отличается только `built_at_sha` (затем откат `git checkout -- docs/codebase-map.md`).
- Новый тест разработчика не повторяет долгоживущие: «шаблон без `{ref}` не читает ссылки» долгоживущие файлы не проверяют.

## Предложения системе
- `plank-run` при пустой планке (все критерии в долгоживущих `tests/`) отказывает со словом «отказ»; ревьюверу полезно было бы, чтобы команда сама называла долгоживущие файлы задачи для прогона.
