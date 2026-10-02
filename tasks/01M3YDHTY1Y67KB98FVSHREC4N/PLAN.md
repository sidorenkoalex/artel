---
task: 01M3YDHTY1Y67KB98FVSHREC4N
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Черновик запроса на слияние сверяет ветку с удалённой базой; массовое подтверждение инцидентов одного вида

## Подход
Две независимые механики одной задачи (монолит принят Оператором 02.10).

**(а) Сверка с удалённой базой.** `github_adapter._commits_over_base` больше
не спрашивает локальную ветку `<base>`: сначала свежий
`gitcmd.fetch_ref_sha("origin", <base>, repo=<клон>)` (приватная ссылка, без
`FETCH_HEAD`), затем `gitcmd.commits_behind(<sha головы>, <ветка>, repo=<клон>)`.
Новых примитивов в `gitcmd` нет — оба существующих принимают sha и `repo`
без обобщения. Пустой sha (fetch отказал / git не ответил / `OSError`) или
нечисловой ответ `rev-list` — `None`, и `ensure_draft_mr` идёт прежним путём
(push → `gh pr create` → инцидент при отказе). Запись пропуска
`DRAFT_MR_SKIPPED_ACTION` называет базу сверки: `origin/<base> (свежий fetch)`.
`repo` — тот же `repo_context.path_or_none(ctx)`, что уже идёт в push:
self-target → `config.ROOT`, внешний → его клон.

**(б) Массовое подтверждение.**
- `alerts.bulk_ack_selection(conn, source, needle)` — открытые алерты из
  `store.open_alerts` (store только читается), фильтр `row["source"] ==
  source and needle in message` в Python — буквально по построению, без
  LIKE/regex; делит на `incident` и пропущенные (все прочие виды).
- `doctor/cli.cmd_alert_ack_bulk(source, needle, resolution, confirmed)` —
  отказ на отсутствующий/пустой/пробельный любой из трёх до чтения БД;
  печать: число, диапазон дат, номера, по строке на алерт (номер, ts,
  первая строка текста), строка «пропущено не-incident: N (вид: n…)»;
  без `--yes` — «предпросмотр: ничего не изменено»; с `--yes` — каждому
  `alerts.ack(conn, id, "operator", resolution)` (тот же путь, что у
  одиночной формы), отказ одного не останавливает остальных, но даёт
  ненулевой код с перечнем.
- `artel._cmd_alert_ack(rest)` — диспетчер: без `--source`/`--grep` —
  прежний вызов `doctor.cmd_alert_ack(rest[0], rest[1] if … else "")`
  байт-в-байт; иначе разбор флагов (`--source`, `--grep` с обязательным
  значением, `--yes`, ровно один позиционный — решение). Вызов идёт через
  `doctor.cli.cmd_alert_ack_bulk`: фасад `orchestrator/doctor/__init__.py`
  в «только чтение» SPEC, новое имя в него не добавляется.
- Отказ из-под роли: `_refuse_if_role_restricted` стоит до диспетчера, а
  `alert-ack` в белом списке роли не значится — массовая форма отказывает
  тем же текстом `artel.py alert-ack: команда недоступна процессу роли …`
  без правки кода (AC-9 проверен прогоном).

**Правка фикстуры существующего теста.** `tests/test_draft_mr_commits.py`
жил в песочнице без `origin`; под требованием 3 такая база «не читается», и
два метода (`test_empty_branch_skips_github_without_an_incident`,
`test_publishing_the_head_opens_the_draft_mr`) уходили в push. В `setUp`
класса `_DraftMrSandbox` добавлен локальный bare-`origin` с `main`
(заведён до подмены `subprocess.run`). Имена методов и все утверждения не
тронуты — изменена только фикстура под новую механику
(skills/coding-standards.md, «Переписываешь тест под новую механику —
сохраняй имя метода»).

## Шаги
1. `orchestrator/github_adapter.py` — `_commits_over_base` через
   `fetch_ref_sha` + `commits_behind(sha, branch)`, текст записи пропуска с
   `origin/<base>`; фикстура `tests/test_draft_mr_commits.py` (bare-origin);
   свой тест `tests/test_draft_mr_remote_base_args.py` (база — `base`
   target'а, не `MAIN_BRANCH`; подсчёт над sha, не над именем).
2. `orchestrator/alerts.py::bulk_ack_selection`,
   `orchestrator/doctor/cli.py::cmd_alert_ack_bulk`,
   `orchestrator/artel.py::_cmd_alert_ack` + строка usage; свой тест
   `tests/test_alert_ack_bulk_parsing.py` (флаг без значения, лишний
   позиционный, частичный отказ `ack`).
3. `python3 scripts/codebase_map.py` — карта регенерирована.

Прогоны (передний план, `-p no:cacheprovider -p timeout -o timeout=120`):
- обе долгоживущие планки задачи + `test_alert_ack_bulk_parsing`,
  `test_draft_mr_remote_base_args`, `test_draft_mr_commits`,
  `test_github_adapter`, `test_fsm_draft_mr_reentry`,
  `test_gitcmd_fetch_ref_sha`, `test_doctor_wave_breaker`,
  `test_01m3xtf5506gf43hd51ece230t_role_refusal`,
  `test_artel_role_restricted_commands`, `test_alerts_wave_breaker`,
  `test_codebase_map`, `test_kill_live_cycle_refusal` — 129 passed, 146 subtests;
- `test_doctor`, `test_invariants`, `test_multitarget` — 253 passed, 232 subtests.

Мутационная проверка своих сторожей (временная правка кода, прогон,
возврат): fetch за `config.MAIN_BRANCH` вместо `base` → красный;
`commits_behind(base, …)` вместо sha → красный; игнор ошибки `ack` в цикле →
красный; разбор без проверки «следующий токен — флаг» → красный; лишний
позиционный не отсекается → красный.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 2 (без правки кода — отказ диспетчера до разбора; проверено AC-9) |
| 10 | раздел «Команда закрытия накопленных инцидентов» ниже |

## Команда закрытия накопленных инцидентов (требование 10)
Исполняет Оператор после мержа и сдвига пина (`pin-update`), не задача.

Предпросмотр (ничего не меняет):

    python3 orchestrator/artel.py alert-ack --source github_adapter --grep "No commits between" "Ложные инциденты Draft MR: пустая ветка сверялась с отставшей локальной main; устранено задачей 01M3YDHTY1Y67KB98FVSHREC4N (сверка с origin/<base> свежим fetch)"

Подтверждение — та же команда с `--yes`:

    python3 orchestrator/artel.py alert-ack --source github_adapter --grep "No commits between" "Ложные инциденты Draft MR: пустая ветка сверялась с отставшей локальной main; устранено задачей 01M3YDHTY1Y67KB98FVSHREC4N (сверка с origin/<base> свежим fetch)" --yes

Сверить перед `--yes`: число в первой строке предпросмотра ≈ 148, строка
«пропущено не-incident» отсутствует или ожидаема.

## Влияние на систему
- `ensure_draft_mr` теперь делает один сетевой `git fetch` на вход в
  `in_dev`/рубеж публикации (только пока `draft_mr_created = 0`, т.е. до
  первого успешного черновика). Отказ сети — прежняя попытка push/gh, не
  отказ перехода FSM: адаптер по-прежнему побочный эффект.
- `_ensure_draft_mr_after_publish` (дешёвая предпроверка `head == локальная
  base`) не тронута: она решает лишь «будить ли адаптер», а не пропуск
  черновика; совпадение головы с отставшим пином означает ноль своих
  коммитов и над удалённой базой.
- Одиночная форма `alert-ack` — тот же вызов с теми же аргументами;
  `alerts.ack`/`store.ack_alert` не менялись. Белый список команд роли не
  менялся.
- Гейты, лимиты, инварианты, guard — не затронуты. Существующие тесты: ни
  одно утверждение и ни одно имя метода не изменены; правка только
  фикстуры `_DraftMrSandbox.setUp` (обоснование — в «Подходе»).
- Откат — revert merge-коммита задачи; схема БД не менялась.

## Риски
- Fetch может быть медленным на большом `origin`: приватная ссылка тянет
  только одну ветку базы; таймаута у `gitcmd.git` нет и раньше не было
  (push того же шага в том же положении).
- Объекты фетча остаются в объектной базе после удаления приватной ссылки —
  штатно для `fetch_ref_sha`, их подберёт `git gc`.

## Предложения системе
- Фасад `orchestrator/doctor/__init__.py` перечисляет экспорты `cli` поимённо
  и при этом в «только чтение» у SPEC — новая команда doctor вынуждена ходить
  в `doctor.cli.<имя>` мимо фасада. Либо фасад в зону задач, добавляющих
  команды, либо диспетчер `artel.py` зовёт `doctor.cli` напрямую как норму.
- Скилл coding-standards различает «утверждение» и «имя метода», но не
  называет явно случай «новая механика требует правки ФИКСТУРЫ
  существующего теста» (здесь — bare-origin в `setUp`): стоит одной строкой
  сказать, допустимо ли это без эскалации при неизменных утверждениях.
