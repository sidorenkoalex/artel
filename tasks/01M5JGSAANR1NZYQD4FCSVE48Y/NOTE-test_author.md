# Записка test_author

## Выяснено
- Долгоживущий `tests/test_01m5jgsaanr1nzyqd4fcsve48y_task_component.py` (AC-1–6, AC-28) написан; красен (нет `task_components`/`decide_task`), со стабом в project_profile.py зелёный (13 методов), мутации ловятся (depends_on, каталог строкой, расширение зон, все имена).
- Почти все места таблицы сегодня зовут `decide(target)`; `for_task` уже у checkpoint :455/:593/:1662, fsm_merge_gate :1393, amend :213, mandate :191.
- Песочница гейта исходов с поддельными раннерами: `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py::OutcomeGateSandbox` (vitest/junit проекты, `in_dev_task`, `developer_advance`); `commit_code` пишет zones = изменённые файлы.
- Лёгкий шаблон прямого вызова мест с моками gitcmd: `tests/test_project_profile_gates.py::_ExternalTaskTest` (TaskIdSchemaConnTmpRootTest + declare_target).
- Строгий режим: `outcome_integrity._strict_findings(profile, _Files(profile,set(),set()), [("M", path, None)])`.

## План файлов
- acceptance_tests/_training.py — лёгкая песочница с учебной записью backend/frontend.
- test_places_*.py (разовые) — AC-22/24/9 по местам прямыми вызовами; AC-7, 8, 11, 12.
- долгоживущие: outcome_components (AC-16–18, 23), plank_foreign (AC-19, 25, 27), mandate (AC-13, 14).
- test_pin_etalon.py — AC-26, AC-10, AC-15 (эталон пина через DIFF_BASE).

## Не сработало
- `ls`, `sed -i`, запись в /tmp, heredoc с `{'` — отказ песочницы; мутационный прогон — `.mut_check.py` в worktree (удалить!).

## Где остановился
- Готово: _training.py, test_places_transitions.py (AC-22/24/9 выхода; красен на пине, зелён на стабе).
- Стаб: `.stub_apply.py` в worktree (decide-обёртка по последней задаче проекта + места); откат — `git checkout -- orchestrator/` и удалить `.stub_apply.py`, `.mut_check.py`, `.mut1.json`.
- Готово: test_places_gates.py (AC-7, 8, 11, 12, 22/24/9 мержа/пакета/автогейта/прогонов) — 31 зелёных на стабе.
- Готово: test_layers_and_prior_test.py (AC-21, AC-10); долгоживущие tests/test_01m5jgsaanr1nzyqd4fcsve48y_mandate_components.py (AC-13/14), _outcome_components.py (AC-13/14 рубеж, 16, 17, 18, 22 гейт исходов/tests_writing/мерж, 23) — зелёные на стабе (.stub_*.py в worktree).
- Готово: долгоживущие _foreign_plank.py (AC-19, 25, 27), _role_outputs.py (AC-20, AC-22/24 бриф, задание, сводки Vitest, plank-run).
- Неоднозначность: plank-run при отказе for_task — на пине `_task_own_profile` падает ComponentsPending (итоговой строки нет); тест принимает «итог pytest» либо текст отказа, требует только отсутствия «итог vitest».
- Осталось: test_places_roles.py (чекпоинт :455/:593/:1662, runner :1325, amend, preflight, pull, матрица, knowledge), test_pin_etalon.py (AC-15, AC-26), снятие стабов + проверка красноты, preflight.
- Было в списке: AC-21, AC-10, AC-13/14/15 (мандат), AC-16/17/18/23 (гейт исходов e2e), AC-19/25/27 (планка чужого компонента), места ролей (чекпоинт, runner, бриф, role_prompt, plank-run, amend, preflight, pull, матрица) AC-22/24 + AC-20, AC-26 (эталон пина).
- Бриф: песочница `tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py` (prepare/build, BUILDERS).

- Шаг 3 (23.10): test_places_roles.py на диске (AC-22/24/9 ролей) — есть; стабов в worktree нет (чисто). Пишу test_pin_etalon.py (AC-15, AC-26).
- Готово: test_pin_etalon.py + _etalon.py — сценарий мест гонится отдельным процессом из `git archive DIFF_BASE` (без tasks/) и из ветки, выводы сравниваются; зелён, мутация for_task у записи из одного компонента ловится (2 failed), мутация откачена. Осталось: preflight, полный прогон планки.
- preflight отказал «номер задачи» у _foreign_plank.py: импорт `tests.test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components` несёт id своей задачи. Классы AC-19/25/27 перенесены в конец _outcome_components.py, _foreign_plank.py удалён. Импорт из файлов чужих задач guard пропускает.
- Итог шага: preflight — все проверки «пройдена»; plank-run всей планки — 119 failed / 36 passed, ошибок сбора нет; worktree: только D _foreign_plank.py, M _outcome_components.py. Карту codebase-map не регенерировал (правка вне tests/ откатывается пультом).

## Где остановился (итог)
- Планка сдана: AC-1…AC-28 покрыты; стабов в worktree нет.

## Чего не хватило
- —
