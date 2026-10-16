# Записка spec_auditor (визит 2, spec_sha 58e64fef…)

## Выяснено
- Все 10 решений Оператора 16.10 внесены в SPEC (зоны, req 1/7/8/9, AC-2..AC-12, матрица, факты :186, :587, :1343-1350).
- Новые находки: `suite-run --failed` — id упавших из вывода pytest (`acceptance.failed_entries`, :1452) отсчитаны от rootdir pytest, не от корня репозитория; req 4 велит переводить их от корня -> поломка при workdir.
- `run_full_suite` проверяет `root/"tests"` (`acceptance.py:1172-1174`) — SPEC не говорит, что проверка идёт по long_lived_dir.
- `amend.py:715-718` зовёт collect/run без cwd -> `config.ROOT`; AC-9 требует cwd=workdir при «только передаче профиля».
- `run_plank` (:923) и `two_sided._run_side` (:222) параметра command не имеют — фиксация AC-1 по пути command=[python3,-m,pytest] на текущем коде для них не определена.
- preflight.py/dry_run.py pytest не запускают — подтверждено.

## Не сработало
- Bash с `W=…;` требует подтверждения — только `cd … && grep`.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, spec_sha 58e64fef…, guard ок. Работа завершена.

## Чего не хватило
- Карта не даёт вызывающих по функциям — grep по `acceptance\.<fn>(`.
