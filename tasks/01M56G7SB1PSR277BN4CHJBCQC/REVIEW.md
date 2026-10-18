---
task: 01M56G7SB1PSR277BN4CHJBCQC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Ревью-пакет задачи внешнего проекта: конвенции проекта, без карты пульта

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–6 → шаг 1 / тест ba3c8a3d / долгоживущий файл.
- Один шаг размера MR (одна развилка в `review_package` + помощник) — соразмерно SPEC (прогноз 14 КиБ, фактически +40/−12 строк).
- Подход совпадает с конвенцией брифа (`brief.is_artel_task`, `brief._project_conventions_parts` с колбэком `render`); место конвенций (требование 3) названо: после формы вердикта, до ANSWER-n.md.
- «Влияние на систему» соответствует diff: тронуты только `orchestrator/review.py` и `docs/codebase-map.md`; `snapshot_exclude` и гейт ёмкости не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `review.py:917-918` зовёт `brief._project_conventions_parts(conn, task_id, "reviewer", run_id, _conventions_component)`; своего чтения в `review.py` нет; пометки ABSENT/UNREAD и журнал — из `brief.py:586-621`. |
| 2 | OK | `_conventions_component` (`review.py:205-210`) → `artifact_part(label, text, "", run_id)`: заголовок `### CLAUDE.md (корень ветки … проекта …) — N байт, sha256=…`, тело в `wrap_boundary` с общим `run_id`. Мутация «компонент без artifact_part» красит AC-2 (проверено). |
| 3 | OK | После формы вердикта, до ANSWER-n.md; докстринг `review_package` обновлён. |
| 4 | OK | `review.py:995-1003`: у внешней задачи фраза об исключении `tasks/<id>/` из стат-списка и diff + упоминание исключения `docs/codebase-map.md` из diff с `excluded_note`; джоба и команды нет. Признак — `brief.is_artel_task`. |
| 5 | OK | Порядок по истории ветки: `ba3c8a3d` (только `tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py`) → `f64be831` (подтяжка main, `review.py` не трогает) → `35d45077` (`review.py`, карта). Эталон — литерал `ARTEL_ETALON`; ветка артели в коде — прежние строки побайтно. Мутация «конвенции без развилки» красит AC-7 (проверено). |
| 6 | OK | Песочничный `RealGitSandbox` + `make_project_repo(origin=False)`; AC-8 подменяет `subprocess.run`/сокеты. |

## Замечания
Нет blocker/major/minor по коду задачи.

Наблюдение вне зоны (не замечание): запись журнала при нечитаемых конвенциях пишется действием `brief.PROJECT_CONVENTIONS_UNREAD_ACTION = "бриф: конвенции проекта не прочитаны"` (`brief.py:47`) от роли `reviewer` — префикс «бриф:» для пакета ревьювера неточен, но `brief.py` вне зон задачи по SPEC («Не входит»), и SPEC требует тех же пометок; см. «Предложения системе».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено, прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `git log --oneline --name-only 260efd26..HEAD` — тест задачи (`ba3c8a3d`) раньше первого коммита с `orchestrator/review.py` (`35d45077`); подтяжка `f64be831` `review.py` не меняет (`git show f64be831 --stat`). Требование 5 выполнено.
- `python3 -m pytest -q tests/test_01m56g7sb1psr277bn4chjbcqc_review_conventions.py tests/test_review_package_map.py tests/test_review_long_lived_exclude.py tests/test_review_freshness.py tests/test_review_package.py` — 178 passed, 4 subtests passed.
- Временные мутации (Edit, затем `git checkout -- orchestrator/review.py`, дерево чистое): (а) `if not is_artel:` → `if True:` — AC-7 красный; (б) `_conventions_component` возвращает `### {label}\n\n{text}\n` без `artifact_part` — AC-2 красный. После возврата кода файл задачи — 8 passed.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (не дефект); файл возвращён `git checkout`.
- `artel.py plank-run 01M56G7SB1PSR277BN4CHJBCQC` — «планки нет», pytest не запускался (у задачи только долгоживущий файл в `tests/`).
- CI коммита 35d45077 зелёный (16 проверок, из пакета).

## Предложения системе
- `orchestrator/brief.py:47` — `PROJECT_CONVENTIONS_UNREAD_ACTION` начинается с «бриф:», а теперь его пишет и сборка ревью-пакета (роль reviewer); при следующей правке brief стоит сделать действие нейтральным к потребителю или параметризовать его.
- `brief._project_conventions_parts` закрыт по имени, но теперь у него второй потребитель (`review.py`) — кандидат в публичное имя.
