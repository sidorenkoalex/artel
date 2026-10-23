---
task: 01M5MHVRS39CDP5V4HBWY4K7WK
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/; в) пути-признаки (песочница ролей): orchestrator/runner.py"
spec_sha: f63844bc278f7c408fa6b556b583d039a71571e9
schema_version: 5
---

# SPEC-AUDIT: Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

## ТЗ и SPEC
Требования 1–2, 4 ТЗ перенесены в SPEC требования 1–2, 4 дословно; ограничение зон по смыслу — SPEC требование 6; «Не входит» и бюджет ($25) совпадают с ТЗ. ANSWER-n и решений Оператора на гейте SPEC нет.

Расхождения:
1. ТЗ требование 2 «Докстринги сохраняют утверждение «префикс разворачивается до взятия lease»; слово «ЗДЕСЬ» заменяется ссылкой» предполагает, что утверждение есть у всех семи. В коде оно есть с «ЗДЕСЬ» только у четырёх: `orchestrator/fsm.py:1681` (cmd_reject), `orchestrator/workspace.py:264`, `orchestrator/ci_rerun.py:55`, `orchestrator/runner.py:160`. У `cmd_pull_main` (`orchestrator/pull_main.py:39`) утверждение есть, но без «ЗДЕСЬ»; у `cmd_zones_extend` (`orchestrator/answer.py:492`) — только «резолв префикса, что у `cmd_answer`»; у `cmd_spec_audit` (`orchestrator/fsm.py:1767-1772`) утверждения нет. SPEC AC-7 (SPEC.md:90) толкует ТЗ как «утверждение и ссылка у каждой из семи», то есть для двух-трёх докстрингов утверждение нужно ДОБАВИТЬ, а не сохранить. Толкование разумное и в рамках зон (докстринги семи функций), но в SPEC это расхождение с фактом не названо — разработчик встретит его сам.
2. ТЗ требование 4 «остаются зелёными» SPEC выносит в «Не входит» («её держит пульт», SPEC.md:102-110). Это не потеря: полный прогон держит гейт `in_dev -> verifying`; отмечено для полноты, не отклонение.

Требований сверх ТЗ в SPEC нет (AC-5/AC-6/AC-9 раскрывают ТЗ требование 2 и ограничение зон).

## Факты против кода
Подтвердилось:
- Семь функций и их обвязка: `orchestrator/fsm.py:1678-1688` (cmd_reject), `orchestrator/fsm.py:1766-1776` (cmd_spec_audit), `orchestrator/pull_main.py:35-46`, `orchestrator/workspace.py:255-270`, `orchestrator/ci_rerun.py:44-64`, `orchestrator/runner.py:153-166` (`return lease.run_locked(...)`), `orchestrator/answer.py:488-502` — все три строки `store.db()` → `store.resolve_task_id` → `lease.run_locked(conn, task_id, session_id, lambda sid: _cmd_X(...))`, без именованных аргументов, `sid` не используется.
- `lease.run_locked` — `orchestrator/lease.py:334`, сигнатура `(conn, task_id, session_id, body, *, on_refusal="exit", same_host_ok=False, force=False)`; `lease` импортирует `store` (`orchestrator/lease.py:24`).
- `auto` передаёт `session_id` в `cmd_run`: `orchestrator/auto.py:928`.
- Докстринги с «ЗДЕСЬ» вне таблицы, перечисленные в «Не входит»: `orchestrator/fsm.py:732` (cmd_advance), `orchestrator/fsm.py:921` (cmd_approve), `orchestrator/answer.py:309` (cmd_answer) — верно.
- Существующие подмены `lease.run_locked` в тестах позиционные `(conn, task, sid, fn)` (`tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py:468`, `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py:53`, `tests/test_01m3rwa2786hcac8pt3xsbkqt4_autogate.py:74`) — совместимы с вызовом `run_locked(conn, task_id, session_id, lambda sid: ...)` из `run_task_command`, если тот обращается к имени модуля `run_locked` в момент вызова.
- Линтер `force=True` (`tests/test_01m4xv9xpjzd29py0ntnz98m02_commands.py:35`) правкой не задевается.

Не подтвердилось: утверждение SPEC требования 3 «докстринги семи команд сохраняют утверждение … слово «ЗДЕСЬ» в нём заменяется» — у трёх команд нет «ЗДЕСЬ», у одной нет утверждения (см. «ТЗ и SPEC», п. 1).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, (а) | тело зовётся с префиксом вместо полного id; `run_task_command` не возвращает результат `run_locked` |
| AC-2 | да, (а)+(б) | `resolve_task_id` после `run_locked` (шпион видит префикс); `same_host_ok=True` (в (б) чужой lease своей машины не откажет, тело вызовется); `force=True` (строка lease перепишется); `on_refusal="print"` (нет `SystemExit`). Проверку отсутствия именованных аргументов шпионом (а) требование 4 не называет, но (б) ловит все три |
| AC-3 | да, (б) | обход `acquire`; взятие lease по префиксу (отказ с другим id в тексте). Риск нестабильности: текст отказа содержит `heartbeat {int(age)} сек` (`orchestrator/lease.py:190`) — эталон из второго вызова `acquire` может разойтись на секунду |
| AC-4 | да, (в) | возвращённая копия обвязки; `None`/литерал вместо `session_id`; `session_id=` именованным. НЕ ловит: замыкание по внешнему `task_id` (префиксу) вместо параметра `tid` — `lambda conn, tid: _cmd_ci_rerun(conn, task_id, reason)` |
| AC-5 | частично, существующими тестами | потеря `reason`/`paths_arg`/`matrix_path` ловят `tests/test_01m4r4jdg8rh53znwm0xf90cfj_spec_gate_decisions.py:140`, `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py:466`, `tests/test_answer.py:385-432`; потеря `return` в `cmd_run` — `tests/test_01m446wevjxarr5cded8re9ccr_run_advances.py`. Новый файл AC-5 не проверяет |
| AC-6 | частично, существующими вызовами | `answer.cmd_zones_extend(t.id, path, None, str(matrix))` (`tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py:899`) держит позицию `session_id`/`matrix_path`; позиционный `session_id` у `cmd_workspace` — `tests/test_workspace.py::CmdWorkspaceLeaseTest` |
| AC-7 | нет | ни (а), ни (б), ни (в) докстринги не читают — только ревью |
| AC-8 | да | наличие файла, строки докстринга и красноты до изменения — ревью/гейт планки |
| AC-9 | да | правка существующего теста — гейт неослабления тестов; правка прочих функций `lease.py`/`answer.py` — ревью диффа |

Отклонение (проверяемость AC-4/AC-5): замыкание, использующее внешний `task_id` вместо `tid`, проходит линтер (в) и проверки (а)/(б), а для `cmd_ci_rerun` и `cmd_zones_extend` префикс не проверяет ни один существующий тест (`tests/test_task_id_prefix_regression.py` покрывает reject :214 и workspace :274, `pull_main` — ac1 :208). Мутация «команда с префиксом падает в `_cmd_*` с неразвёрнутым id» остаётся непойманной. Закрыть можно в (в): тело — имя `_cmd_*` либо `lambda` с двумя параметрами, во вызове которой вторым аргументом стоит второй параметр `lambda`.

## Зоны
Зоны SPEC = зоны ТЗ: `orchestrator/lease.py`, шесть модулей команд, `docs/codebase-map.md`, `tests/`. Правки требований 1–4 ими покрыты. Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) задача не трогает. Песочница ролей: в `orchestrator/runner.py` меняется только `cmd_run` (обвязка и докстринг) — `role_env`, `role_cmd`, `role_cwd` и прочее окружение роли не затрагиваются, расширения песочницы нет. Импорт `store` во всех шести модулях остаётся нужен прочему коду — «ставшие лишними импорты», скорее всего, пусты.

## Матрица неослабления
Задача не меняет тестов, гейтов, лимитов и проверок; раздела «Меняемое поведение» в SPEC нет — и не нужно.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Обвязка семи команд → `lease.run_task_command` | Префикс разворачивается до lease: семь копий (`orchestrator/fsm.py:1685`, `:1774`, `orchestrator/pull_main.py:45`, `orchestrator/workspace.py:268`, `orchestrator/ci_rerun.py:62`, `orchestrator/runner.py:164`, `orchestrator/answer.py:499`); тесты `tests/test_task_id_prefix_regression.py:214`, `:274` | да | `tests/test_task_id_prefix_regression.py` + новый файл (а), (в); для ci_rerun/zones_extend на уровне команды — не покрыто (см. «Проверяемость») | концерн Оператору |
| Отказ по чужому живому lease для семи команд | `lease.run_locked` дефолты `on_refusal="exit"`, `same_host_ok=False`, `force=False` (`orchestrator/lease.py:334-336`); `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` (ac3, без `same_host_ok`), `tests/test_workspace.py::CmdWorkspaceLeaseTest` | да | новый файл (б); существующие тесты без правки | — |
| `session_id` команд | `tests/test_workspace.py::CmdWorkspaceLeaseTest` (позиционно), `orchestrator/auto.py:928` | да | новый файл (в) | — |

## Пути обхода гейтов
1. Замыкание по внешнему `task_id` вместо `tid` (см. «Проверяемость критериев») — буквально выполняет AC-4 и требование 2 («добавочные аргументы передаются замыканием»), но для `cmd_ci_rerun`/`cmd_zones_extend` возвращает регрессию префикса, которую ни один тест не ловит.
2. AC-7 не проверяется ни одним тестом: исполнитель может оставить у `cmd_spec_audit` докстринг без утверждения о префиксе — поймает только ревью.
3. Эталон (б) «текст как у `lease.acquire`»: если тест получает эталон, вызвав `acquire` с теми же аргументами, а сравнение нестабильно из-за `int(age)` (`orchestrator/lease.py:190`), у тест-автора есть соблазн сравнивать по подстроке/без возраста — ослабленная проверка AC-3 пройдёт и при отказе с другим id в тексте, если подстрока выбрана без id. SPEC не требует ни фиксации времени, ни id в сравнении.

## Вердикт
concerns — SPEC вести дальше можно, отклонения решаемы Оператором на гейте или уточнением тест-автору:

1. Проверяемость AC-4/AC-5: линтер (в) не ловит замыкание по внешнему префиксу `task_id` вместо параметра тела; для `cmd_ci_rerun` (`orchestrator/ci_rerun.py:62-64`) и `cmd_zones_extend` (`orchestrator/answer.py:499-502`) префикс на уровне команды не держит ни один тест (`tests/test_task_id_prefix_regression.py:214`, `:274` — только reject и workspace). SPEC.md:54-68, :84.
2. Факт SPEC требования 3 (SPEC.md:51-53) «сохраняют утверждение … «ЗДЕСЬ» заменяется» не совпадает с кодом: «ЗДЕСЬ» только у четырёх (`orchestrator/fsm.py:1681`, `orchestrator/workspace.py:264`, `orchestrator/ci_rerun.py:55`, `orchestrator/runner.py:160`), у `cmd_spec_audit` (`orchestrator/fsm.py:1767`) утверждения нет; AC-7 (SPEC.md:90) фактически требует добавить его — это толкование ТЗ, стоит подтвердить Оператору.
3. AC-7 (SPEC.md:90) не проверяется ни одной проверкой требования 4 — только ревью.
4. Риск нестабильности (б)/AC-3 (SPEC.md:82): текст отказа `acquire` несёт `heartbeat {int(age)} сек` (`orchestrator/lease.py:190`); SPEC не оговаривает, как получать эталон без гонки по секунде (фиксировать heartbeat/`liveness._age_seconds` или брать эталон тем же моментом).
