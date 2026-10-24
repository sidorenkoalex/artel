## Выяснено
- Планка читает новые файлы из HEAD (git show HEAD:…) — код надо КОММИТИТЬ самому, иначе AC-5/7/8… красные.
- Шаг ограничен ~45 мин; прогоны mutation-run «до»/«после» (~15 мин на часть) за один шаг не успеть — пускать в фоне, отчёт забирать `--wait`.
- План: все 53 теста переносятся (дублей не удаляем), одна мутация на заявку/группу заявок.
- Сделано: tests/outcome_gate_sandbox.py (ast.dump 60/60 сверен), три импортёра переключены; 35 патчей mutation-001..035.diff в каталоге документов (генератор — `.mutgen_tmp.py` в корне worktree, временный, удалить до сдачи; `python3 .mutgen_tmp.py <номера>` перегенерирует).
- Сопоставление мутаций тестам — комментарии `# N …` в .mutgen_tmp.py; карта тест→мутация: 1 Ac1 artel/test_profile; 2 Ac1 decide/canary; 3 Ac2 text first; 4 Ac2 before rework; 5 Ac3; 6 Ac4 git (а),(б); 7 Ac4 git выписка базы/головы; 8 Ac4 side (а) и base timeout; 9 Ac4 side head unknown/timeout; 10 Ac5 retried + RecordLevel retried; 11 Ac5 no tests; 12 Ac6 red kinds; 13 RecordLevel red_on_branch_kinds; 14 Ac6 skipped; 15 Ac7 rerun prep (а)(б)(в); 16 Ac7 base skipped/missing; 17 Ac7 branch retried; 18 Ac7 branch skipped/missing; 19 Ac7 red_kinds, error, Ac8 broken(а); 20 Ac8 unstable; 21 Ac8 flaky; 22 Ac8 neighbour; 23 Ac9 vitest/junit + RecordLevel compare x2; 24 Ac9 one finding; 25 Ac10; 26 Ac11 file/class/method; 27 Ac11 other file; 28 Ac11 separator + RecordLevel separator; 29 Ac11 role answer + RoleAutocommitTest; 30 Ac13 counts; 31 ExactIdTest; 32 HintTest; 33 skip_growth; 34 covered_ids; 35 fingerprint.
- Новый файл tests/test_outcome_gate_module.py пишет фоновый субагент (может не успеть в шаге — проверь наличие/сбор).
## Не сработало
- в Bash нет ls/cat; `$(…)` в команде запрещён; heredoc с длинным скриптом — «Parser skipped input» → писать скрипт файлом.
- mutation-run часть 1 «до»: замок занят suite-run задачи 01M5PCB66D936FDGG7H09CVGA1 — повторить.
## Где остановился
- Коммит 071800d4: sandbox, новый файл (53 функции/58 узлов, 2287 строк), импортёры, удаление трёх файлов, карта. plank-run: test_module_form 20/20, test_branch_diff 7/7, test_sandbox_transfer 17/19 (2 красных — PLAN ещё не в ссылке документов).
- PLAN.md (draft): разделы «Мутации и заявки», «Перенос песочниц», «Числа свода» заполнены; НЕ хватает: «Мутации до»/«Мутации после» (вывод mutation-run дословно), строк «mutation-NNN до/после: узел — tests/<файл>.py:<строка>» (файл:строка из логов .artel/logs/suite-run/<id>/), итога CI (адресный прогон «после» сделан: 58 passed, 230 с — в PLAN) трёх импортёров, status: ready.
- Генератор патчей .mutgen_tmp.py удалён (патчи лежат в каталоге документов; правка патча — руками в .diff + `git apply --check`).
- Прогон «до» №1 (патчи 1-15, ref base) ЗАПУЩЕН в конце шага 1 (pid 31102); отчёт: `artel.py mutation-run 01M5PHK9K0YQCTPA6CK94BBZ33 --wait 9`; лог/таблица — .artel/logs/suite-run/01M5PHK9K0YQCTPA6CK94BBZ33/…-mutation-run-1.*. Дальше 16-30, 31-35.
- «До» №1 (1-15) готов и вставлен в PLAN «Мутации до»: 14 убиты, 11 не убита → mutation-011.diff переписан (отказ при пустом списке записей) — нужен перепрогон `--patches 11-11` «до». «До» №2 (16-30) запущен.
- (история) Прогон «до» долго не стартовал: замок suite_lock держал прогон задачи 01M5PCB66D936FDGG7H09CVGA1 (pid 12525) 25+ мин. Следующему шагу: первым делом `mutation-run … --ref base --tests <3 исходных файла через запятую> --patches 1-15` (затем 16-30, 31-35), затем «после» `--ref worktree --tests tests/test_outcome_gate_module.py` теми же частями; перед каждой частью «после» — вывод `git status --porcelain -- orchestrator/` (пустой) в PLAN (ANSWER-1 п.3).
- guard на PLAN.md — без нарушений.
- запуск «до» частями 1-15, 16-30, 31-35 (замок был занят; повтор в фоне).
- PLAN.md (status: draft) уже несёт раздел «Мутации и заявки» (35 строк сопоставления). В строках с mutation-NNN не писать слова «подготовк»/«находк»/«setUp» — планка трактует их как отметки.
## Чего не хватило
-
