# Записка test_author — 01M52EEHSRD93WMPHWB5VJYRKD

## Выяснено
- Планка — один долгоживущий файл tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py (26 методов test_ac1..test_ac12, AC-10 — два метода); acceptance_tests/ задачи пуст — трассируемость закрывают методы долгоживущего файла (preflight пройдена).
- Песочница ProfileCallersSandbox: RealGitSandbox + внешний проект (make_project_repo) с bare origin; профиль внешнего проекта в targets.yaml — `pytest-own` (workdir под `tests/`, env) или `pult-pytest` с командой `python3 -m pytest -rN` (флаг отличает команду профиля от команды пульта).
- Наблюдение — подмена `acceptance.subprocess` и `two_sided.subprocess` (PytestSpy): pytest записывается (argv, cwd, env), git идёт настоящим.
- Публичные входы мест: автогейт — `fsm.cmd_advance` из review (REVIEW approved, `gates.policy`→auto); approve/merge — `fsm.cmd_approve`; suite-run — `cmd_suite_run` (Popen подменён) + `suite_run.background`; plank-run — `cmd_plank_run` (черновик кладётся в каталог документов после автокоммита: автокоммит убирает файлы оттуда); amend — `amend.cmd_amend_tests`; pull — `pull_main.cmd_pull_main` из verifying после сдвига main; двусторонний — `cmd_advance` из in_dev; сухой сбор — `cmd_advance` из tests_writing; in_dev — `cmd_advance` с долгоживущим файлом с `import random`.
- На main: AC-1, AC-2, AC-10, AC-11 зелёные; AC-3..9, AC-12 красны (голова argv — интерпретатор пульта, не `python3` профиля).
- Стаб реализации (9 файлов зоны, откачен `git checkout -- orchestrator/`): все 26 зелёные; мутации «amend :715 без cwd», «ключ базы suite-run по списку», «профиль в pull безусловно» ловятся AC-6/AC-4/AC-10.
- AC-10: «как на main» — у внешнего pult-pytest гейт мержа, suite-run, сухой сбор, in_dev сегодня идут командой профиля, остальные — командой пульта (таблица `places()`).

## Не сработало
- approve гейта SPEC пишет «объявлена смена поведения тестов» только задаче артели (fsm._behavior_change_declaration) — сценарий гейта двустороннего прогона кладёт запись через store.journal сам.
- Раздел «Меняемое поведение» принимает только пути `tests/…` → workdir профиля под `tests/`.
- Пайпы/heredoc/`env X=` в Bash требуют подтверждения; длинный heredoc падает парсером — правки через Edit.

## Где остановился
- Шаг завершён: файл написан, preflight пройдена, прогон 26 тестов ~90 с (самый долгий метод ~26 с).

## Чего не хватило
- Карты «место запуска → публичный вход и минимальная песочница» — искал дольше всего (4 агента разведки).
- Карту кодовой базы (scripts/codebase_map.py) не регенерировал: test_author правит только tests/; это сделает разработчик/пульт.
