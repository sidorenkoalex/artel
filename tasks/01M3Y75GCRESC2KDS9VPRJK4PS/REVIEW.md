---
task: 01M3Y75GCRESC2KDS9VPRJK4PS
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: pin-update называет живые циклы auto/run, запущенные на старом коде

## Фаза A — план
- Таблица покрытия полна: требования 1–5 сопоставлены шагам 1–3; шаги 4–8 —
  карта, подтяжка main, исполнение ANSWER-1..3.
- Шаги размером в MR: один модуль отбора, правка `pin.py`, тесты.
- Подход не спорит с архитектурой. Отбор вынесен в `doctor/stale_cycles.py`
  из-за инварианта 33: в `pin.py` нельзя звать `subprocess` напрямую. Вызов
  идёт через фасад `doctor.subprocess`/`doctor.shutil`, как требует правило
  фасада. `tests/test_invariants.py` зелёный.
- Расширение зоны `orchestrator/cycle_hint.py` разрешено ANSWER-2/3/4, а
  раздел «Расширение зон» в PLAN оформлен по ANSWER-3.
- «Влияние на систему» совпадает с diff: 5 файлов кода и тестов плюс карта.
  Существующие тесты в `tests/` не изменены, добавлен только новый файл
  `tests/test_pin_update_stale_cycles.py`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `pin.py:115-121`: момент берётся сразу после `merge --ff-only`. `_report_stale_cycles` печатает перечень и пишет отдельную запись «pin: циклы на коде старше пина» рядом с «pin обновлён». Строка цикла несёт id, pid, старт, состояние, `artel.py stop <id>`, затем `auto <id>`. Аргументы наблюдения берутся из `observed_runs` по task_id И pid через JOIN `observations` (`stale_cycles.py:55-67`). Отбор: тот же host и `_pid_alive` |
| 2 | OK | Сигналов нет: только `_pid_alive` (kill 0). AC-6 долгоживущего файла зелёный |
| 3 | OK | `check_stale_cycles` берёт `ts` последней записи «pin обновлён» (`ORDER BY id DESC`), формат совпадает с `store.now()`. Перечень строит тот же `stale_cycle_lines`. Без записи пина или без циклов статус `ok`. Проверка зарегистрирована в `cli.all_checks` рядом с `check_main_ci` |
| 4 | OK | `ps -o lstart= -p <pid>` под `LC_ALL=C`, местное время переводится в UTC. При OSError/SubprocessError, rc≠0, пустом или мусорном ответе возвращается `None`, цикл остаётся в перечне с «не удалось определить», а `pin-update` не падает |
| 5 | OK | Новый файл `tests/test_pin_update_stale_cycles.py`: у каждого метода есть «Ловит мутацию» с наблюдаемым расхождением |

Сверка AC-1..AC-7 с долгоживущим файлом `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`:
его сумма `8cedcc42…` совпадает с `acceptance_tests/long_lived.sha256.txt`.
Последнюю правку файла внёс Оператор через `amend-tests` (ANSWER-1), это
легально по ADR-0012. Чувствительность не ослаблена: добавлена только
подмена `ci.main_line_status` зелёным статусом, предмет тестов прежний.
Все 8 тестов файла зелёные.

Код решает задачу в общем виде. Веток под литералы фикстур нет: отбор
идёт по hostname, `_pid_alive` и сравнению с моментом пина.

## Замечания
Блокеров и major нет.

Наблюдение без замечания: возможно расхождение в пределах одной секунды
между моментом пина в `pin-update` (`datetime.now` с микросекундами) и в
`doctor` (`ts` журнала с точностью до секунды). PLAN честно называет его в
«Рисках». В обе стороны ошибка консервативна или пренебрежима, на AC не
влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в первой итерации замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider -p timeout -o timeout=120 tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py tests/test_pin_update_stale_cycles.py tests/test_pin.py tests/test_cycle_hint.py tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py`: 32 passed, 24 subtests passed.
- `python3 -m pytest -q -p no:cacheprovider -p timeout -o timeout=120 tests/test_invariants.py tests/test_doctor.py`: 202 passed, 218 subtests passed. Это подтверждает инвариант 33 и правило фасада doctor.
- Две временные мутации в `orchestrator/doctor/stale_cycles.py`, после них код возвращён (`git checkout`):
  1. Снят фильтр `lease["hostname"] != host`. Красный `test_lease_of_another_host_is_not_named`.
  2. `astimezone(timezone.utc)` заменён на `replace(tzinfo=timezone.utc)`. Красный `test_lstart_is_local_time_converted_to_utc`.
  Обе заявки «Ловит мутацию» подтверждены: 2 failed / 2 passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha`: расхождений нет, карта свежая. Файл после проверки возвращён.
- Сумма долгоживущего файла (из описи пакета) сверена с `acceptance_tests/long_lived.sha256.txt`: совпадает.
- В планке и долгоживущем файле пометок `# AC-n: manual|skip` нет (grep).
- CI коммита 02643a12 по пакету зелёный (14 проверок).

## Предложения системе
- Проверка ревьювера «временная мутация» упирается в права шага: `sed -i` и
  составные команды требуют подтверждения, и мутацию приходится вносить
  через Edit. Стоит описать в review-checklist допустимый способ (Edit +
  `git checkout -- <файл>`), чтобы ревьювер не тратил попытки.
