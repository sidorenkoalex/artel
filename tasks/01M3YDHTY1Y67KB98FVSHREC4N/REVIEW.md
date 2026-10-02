---
task: 01M3YDHTY1Y67KB98FVSHREC4N
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Черновик запроса на слияние сверяет ветку с удалённой базой; массовое подтверждение инцидентов одного вида

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–10 привязаны к шагам; требование 9
  закрыто без правки кода (отказ `_refuse_if_role_restricted`, `orchestrator/artel.py:1432`,
  стоит до диспетчера) и подтверждено AC-9 планки.
- Шаги — единицы размера MR (адаптер / массовая форма / карта).
- Подход не противоречит архитектуре: используются существующие
  `gitcmd.fetch_ref_sha` (приватная ссылка, без `FETCH_HEAD`) и
  `gitcmd.commits_behind`; `store.py` и фасад `doctor/__init__.py` (только чтение
  по SPEC) не тронуты — вызов идёт через `doctor.cli.cmd_alert_ack_bulk`.
- Требование 10: команды предпросмотра и подтверждения в PLAN есть, с текстом решения.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `github_adapter._commits_over_base`: `fetch_ref_sha("origin", base, repo=repo)` → `commits_behind(base_sha, branch, repo=repo)`; локальная `<base>` и `refs/remotes/origin/<base>` не участвуют. `repo` — тот же, что у push (self → ROOT, внешний → клон; AC-4 зелёный). |
| 2 | OK | Ноль → журнал `DRAFT_MR_SKIPPED_ACTION` с `origin/<base>`, без push/gh/алерта, флаг не выставлен (AC-1). |
| 3 | OK | Пустой sha → `None` → прежний путь; `None` от git и нечисловой счёт — тоже `None` (`commits_behind`). AC-3 покрывает 4 способа × 3 исхода форджа. |
| 4 | OK | `_cmd_alert_ack` + `cmd_alert_ack_bulk`: отсутствующее/пустое/пробельное значение — `sys.exit` до чтения БД (AC-8). |
| 5 | OK | `alerts.bulk_ack_selection`: `store.open_alerts` + фильтр `source ==` и `needle in message` в Python — буквально; не-`incident` → пропущенные, число печатается. |
| 6 | OK | Без `--yes` печать числа, диапазона дат, номеров, первых строк; запись в БД не идёт (AC-5). |
| 7 | OK | `alerts.ack(conn, id, "operator", resolution)` — тот же путь, что у одиночной формы (AC-6). |
| 8 | OK | Без `--source`/`--grep` — прежний вызов `doctor.cmd_alert_ack(rest[0], rest[1] if … else "")` байт-в-байт. |
| 9 | OK | Отказ до диспетчера, белый список не менялся (AC-9). |
| 10 | OK | Раздел «Команда закрытия накопленных инцидентов» PLAN. |

## Фаза B — разбор
- Корректность: отказ fetch/`None`/`OSError` не превращается в «ноль»; гонка
  «подтвердили между отбором и записью» не прерывает цикл, но даёт ненулевой код
  (`doctor/cli.py`, конец `cmd_alert_ack_bulk`). Флаг без значения и лишний
  позиционный — отказ с внятным текстом, не `IndexError`.
- Тесты: в `tests/` ни одна строка не удалена (`git diff b9cac34c...HEAD -- tests/`
  — только добавления). Правка `tests/test_draft_mr_commits.py` — только фикстура
  `setUp` (bare-`origin` с `main`), утверждения и имена методов не тронуты;
  без неё база «не читается» по требованию 3 — правка вынуждена SPEC, сужения
  данных под неизменным утверждением нет (наоборот, проверка стала требовательнее).
- Новые тесты `tests/` несут заявки «Ловит мутацию»; повторов долгоживущих файлов
  задачи нет — `test_draft_mr_remote_base_args` различает `base` target'а ≠
  `MAIN_BRANCH`, чего планка не видит; `test_alert_ack_bulk_parsing` — углы
  разбора и частичный отказ `ack`.
- Обе планки помечены `Группа: долгоживущий` и проверяют свойства кода — корректно.
- Специальных веток под литералы планки нет: отбор по общему правилу.
- Безопасность/целостность: файлы вне зон SPEC не тронуты, гейты/лимиты/guard не
  менялись; откат — revert, схема БД та же.

## Замечания
Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний в итерации 1 не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider -p timeout -o timeout=120` по
  `tests/test_01m3ydhty1y67kb98fvshrec4n_alert_ack_bulk.py`,
  `tests/test_01m3ydhty1y67kb98fvshrec4n_draft_mr_remote_base.py`,
  `tests/test_alert_ack_bulk_parsing.py`, `tests/test_draft_mr_remote_base_args.py`,
  `tests/test_draft_mr_commits.py`, `tests/test_github_adapter.py`,
  `tests/test_fsm_draft_mr_reentry.py`, `tests/test_gitcmd_fetch_ref_sha.py`,
  `tests/test_doctor_wave_breaker.py`,
  `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
  `tests/test_artel_role_restricted_commands.py` — 73 passed, 143 subtests passed.
- Временная мутация (код возвращён `git checkout`, дерево чистое):
  (1) `commits_behind(base, …)` вместо `base_sha` в `github_adapter._commits_over_base`;
  (2) игнор результата `alerts.ack` в цикле `cmd_alert_ack_bulk` —
  `tests/test_draft_mr_remote_base_args.py` и
  `tests/test_alert_ack_bulk_parsing.py::…test_one_failed_ack_does_not_stop_the_rest_but_fails_the_command`
  оба красные (2 failed) — сторожа ловят свои заявки.
- `git diff b9cac34c...HEAD --stat -- tests/` — только добавления (1002 вставки, 0 удалений).
- Свежесть `docs/codebase-map.md` не перепроверял: регенерация в шаге упёрлась
  в запрос подтверждения команды; CI коммита 5e99e5c0 зелёный (14 проверок).

## Предложения системе
- Поддерживаю наблюдение PLAN: фасад `orchestrator/doctor/__init__.py` в «только
  чтение» вынуждает новые команды doctor ходить в `doctor.cli.<имя>` мимо фасада —
  стоит закрепить одну норму.
