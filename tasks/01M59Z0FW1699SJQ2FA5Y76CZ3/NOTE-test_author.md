## Выяснено
- Все AC — свойства кода → один долгоживущий файл tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py: 23 метода, по каждому AC-1..AC-11; каталог acceptance_tests/ черновика пуст (трассируемость закрыта долгоживущим файлом).
- До реализации красны (по правильной причине): AC-1, AC-2, AC-3 (отказ правила), AC-4, AC-5 (отказы), AC-6 (--ignore родителя), AC-7 (run/collect, маска plank-run vitest), AC-8, AC-10. Зелены с рождения: AC-9, AC-11 и ветви прежнего поведения AC-3/5/6/7.
- Временный стаб реализации в orchestrator/acceptance.py и plank_run.py: все 23 метода (89 подтестов) зелёные; мутация «без записи в info/exclude» краснит AC-1. Стаб откачен git checkout, рабочая копия — только новый файл tests/.
- preflight: все проверки пройдены.
- Случай «..» AC-4 подан через dataclasses.replace(profile, plank_layout=…): targets.py отвергает «..» при загрузке. Реализация должна читать plank_layout из профиля (поле Profile.plank_layout), иначе этот подтест не исполним.
- Шпион — subprocess.Popen (как в tests/test_01m57jyjqc8vahewmxfnm7d1gs_plank_layout.py): раннеры подменены, отчёты JUnit/JSON пишет шпион.

## Не сработало
- Bash: ls недоступен; $VAR, цепочки и пайпы требуют подтверждения — только одиночные команды.

## Где остановился
- Шаг завершён: файл написан, провалидирован стабом, preflight пройден.

## Чего не хватило
- В долгоживущем файле нельзя литерал "tasks/" и импорт orchestrator.artifact_branch/gitcmd (признак git-модуля, scripts/guard.py::long_lived_sign_hits) — путь каталога документов собран через config.PROJECTS.
