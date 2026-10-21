---
task: 01M5G6PDQA7AYDYDPA7DD5JD4S
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на QUESTIONS (круг 1): вариант A — мандат ровно на один метод (самый узкий; входит в мандат Оператора 22.10 на четыре файла задачи). В трёх других файлах утверждения не удаляются — гейт неослабления по ним остаётся полным.

Ослабление тестов разрешено: tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted

Условия мандата (SPEC обязан потребовать отдельными критериями AC-n): удаляется только `self.assertLessEqual(elapsed, limit, …)` (строка 602); прочие утверждения метода (state killed, silence.hits ≥ 1, обе заметки SILENT) остаются дословно; добавляются проверки без часов — (а) config.GH_TIMEOUT_SEC подменён на случайное значение 7…300, отличное от исходного и от 2; перехват subprocess.run: пуш удаления несёт `-c http.lowSpeedLimit=1 -c http.lowSpeedTime=<значение>`, `gh pr close` вызван с `timeout=<значение>`; текст заметки «не ответил за N с» несёт это значение; (б) сквозной сценарий (предел 2 с, подставной gh спит 2×предел+15 с, срок молчания хостинга строго меньше времени самоосвобождения без предела): к возврату kill флаг истечения молчания хостинга не поднят и события «gh дожил до конца сна» нет; (в) при молчащих gh и origin — ровно один запуск `gh pr close` и ровно один пуш удаления (счётчики журнала подставных программ). Три мутации строки «Ловит мутацию» пойманы до и после — таблица в PLAN.md. Остальные отклонения аудита (1, 3, 4, 5) аналитик вносит в SPEC.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | kill при молчащем origin не ждёт дольше предела: пуш удаления несёт предел скорости из config.GH_TIMEOUT_SEC (tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:602, мутация «пуш без -c http.lowSpeed*») | остаётся | новая проверка (а) — аргументы пуша с пределом, и (б) — флаг истечения молчания не поднят к возврату kill; AC-n SPEC | ок при условии: (а) и (б) отдельными AC |
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | предел читается из config.GH_TIMEOUT_SEC в момент вызова, не зашит числом (там же, :602, мутация «предел числом») | остаётся | проверка (а) со случайным пределом, отличным от исходного GH_TIMEOUT_SEC | ок при условии: (а) отдельным AC |
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | молчащий gh не задерживает kill дольше предела: gh pr close с timeout (там же, :602) | остаётся | проверка (а) — timeout=<предел> у gh pr close; (б) — нет события конца сна gh к возврату kill | ок при условии: (а) и (б) отдельными AC |
| Нет (утверждение остаётся) | срабатывание предела пишется «не ответил», не «отказ» (там же, :603–604, assertIn SILENT ×2) | остаётся | tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:598–604 (те же утверждения дословно) | ок |
| Нет (утверждение остаётся) | kill доводит задачу до killed и пуш удаления доходит до хостинга (там же, :598–601) | остаётся | tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py:598–604 (те же утверждения дословно) | ок |
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | kill вообще завершается и пределы gh и пуша идут последовательно по одному разу, без повторов попыток (там же, :602) | остаётся | новая проверка (в) — ровно один gh pr close и один пуш удаления; (б) | ок при условии: (в) отдельным AC |
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | предел gh близок к GH_TIMEOUT_SEC, не любой конечный (там же, :602; ловила мутация «gh timeout чужим значением») | остаётся | (а) — timeout=<значение> у gh pr close на подменённом случайном значении; (б) — сон gh 2×предел+15 с, конца сна нет | ок при условии: (а) и (б) отдельными AC |
| Удаление assertLessEqual(elapsed, limit) в tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py::SilentHostingTest::test_ac6_silent_gh_and_origin_bounded_and_noted | текст заметки о срабатывании предела несёт фактический предел (orchestrator/cleanup.py, заметка «не ответил за N с») | остаётся | (а) — текст заметки на случайном значении | ок при условии: (а) отдельным AC |

Независимая проверка: ок при условии — добавлены три строки (общий предел без повторов, предел gh, текст заметки) и уточнены замены (а) подменой конфигурации на случайное значение и перехватом subprocess.run с timeout=, (б) сном gh 2×предел+15 с, (в) счётчиками ровно одного gh pr close и одного пуша; проверяющий без контекста сессии, 22.10.
