# Записка analyst

## Выяснено
- ТЗ — часть 1 деления родителя 01M6P22XBCQS49HE92YGAB25N9; его SPEC читается `git show refs/artifacts/01M6P22XBCQS49HE92YGAB25N9:tasks/01M6P22XBCQS49HE92YGAB25N9/SPEC.md`.
- Шаг 2 (второй круг гейта, решения 1–6) внесён с пометкой «решение второго круга N».
- Шаг 3 (третий круг гейта, решения 1–4) внесён с пометкой «решение третьего круга N»: константы COMPOSE_CONFIG/UP/TEARDOWN_TIMEOUT_SEC (треб. 4, 8, 9, 13; AC-5, AC-8); down после провала up (треб. 8, AC-8); правило тома driver_opts у local + volumes_from (треб. 5, AC-5); AC-10 гейт исходов только на компоненте, AC-17 pull_policy — требование к файлу, порядок DOCKER_HOST → ls-files → копирование (треб. 4, AC-13).
- `in_outcome_bounds` сверен: advance_gates/acceptance.py:213-218 — только компоненты с report.
- guard требует классифицировать каждый упомянутый путь: advance_gates/acceptance.py добавлен в «Не входит» (только чтение).

- Шаг 4 (четвёртый круг, решения 1–2) внесён с пометкой «решение четвёртого круга N»: аргумент `task_id` у `_report_run`/`report_run` (обязателен для compose; вызовы — run_repeat :1731, outcome_integrity :445/:736, two_sided :359), запись журнала — `store.journal` задачи (треб. 3, 8; AC-8, AC-9); зоны + outcome_integrity.py (только передача task_id); соотношение пределов config/context inspect/up/run (треб. 9, AC-8).

- Шаг 5 (пятый круг, решения 1–2) внесён с пометкой «решение пятого круга N»: канал task_id до run_repeat (advance_gates/acceptance.py:174), run_full_suite (suite_run.py:607/:680; у run_full_suite acceptance.py:2338 нужен необязательный task_id), run_plank долгоживущего файла (plank_run.py:267-269; у run_plank task_id уже есть), outcome_integrity._rerun (:430, вызовы :757/:972). Зоны +3 файла (12), AC-9 расширен. Прочие вызывающие run_full_suite — mutation_run.py:516 (вне объёма), notes.py:1102 (полный набор артели, не compose).

- Шаг 6 (шестой круг, решение 1) внесён с пометкой «решение шестого круга 1»: у `run_plank` (acceptance.py:2042) новый необязательный параметр id для имени проекта Compose (напр. `compose_task_id`), без раскладки; `task_id` прежний (цели в `tasks/<id>/acceptance_tests`, раскладка). plank_run.py:267-269 передаёт только новый параметр. Треб. 3, AC-9, «Не входит», шапка.

- Шаг 7 (седьмой круг, решения 1–2) внесён с пометкой «решение седьмого круга N»: имя проекта у `run_plank` — `compose_task_id or task_id` (треб. 3, AC-9: оба вызова plank-run; plank_run.py:283-286 не правится, сверено); треб. 7 заменено отказом compose в процессе роли до любого `docker` (текст отказа — дословно из решения), AC-12 переписан. Решение называет проверку «AC-11» — у нас она в AC-12 (AC-11 — окружение вне роли), это отмечено в AC-12. Якорь in_role_environment в коде :1364-1381 (решение пишет :1366-1383).

## Не сработало
- awk и цепочки команд в Bash требуют подтверждения — одиночный grep работает.
- `artel.py docs` из роли недоступна.

## Где остановился
- SPEC.md обновлён (седьмой круг), status: ready, guard ок. AC — 17, зон-файлов 12, бюджет $60 (рамка родителя).
- `cd … && …` в Bash отказывает («simple_expansion») — звать guard абсолютным путём.

## Чего не хватило
- Ничего существенного.
