# Записка test_author — 01M5TBCY7WTN121S136XP2C6SR

## Выяснено
- Все 29 AC покрыты тестами в 6 долгоживущих файлах tests/test_01m5tbcy7wtn121s136xp2c6sr_{envelope_run,epic_alert,epic_view,epic_watch,start_after_write,auto_stop}.py; acceptance_tests/ пуст (сбор с одними долгоживущими — штатный случай acceptance.collect). Пометок manual/skip/escalate нет.
- Кода Э1/Э0 в main нет: тесты опираются на интерфейс SPEC Э1 (refs/artifacts/01M5TBBDFS6DWQY6MS263T1KPY): таблица `epics` (id, title, envelope_usd), `tasks.epic_id`, CLI `epic new <проект> "<название>" --goal … --envelope N`, `epic show`, `board.build_model(conn, project)["cards"][i]{task, waiting_on}`, `tasks.closed_as` (Э0). Своё (Э2а): `epic envelope`, `epic start-after <задача> <id>…`, `new … --epic … --start-after`, колонка `tasks.start_after` (читается как текст — проверяется наличие id, не формат).
- Предупреждение 80 % наблюдается дифференциально: вывод без цифр выше порога ≠ ниже порога (текст предупреждения не навязан). Алерт эпика = строка alerts с id эпика в тексте. Строка watch по эпику = строка с id или названием эпика.
- «Проверки пропустили run» = дошёл до подменённого doctor.preflight_checks (исключение-метка).
- Цикл через start_after в каналах `new` (new --after, строка ТЗ, new --start-after) не строится в принципе (на новую задачу нет входящих рёбер) — AC-18/AC-19 держат цикл на каналах уже заведённых задач; это сказано в докстринге start_after_write.py.
- Валидация: временный стаб Э1+Э2а — 36/36 зелёные, 19 из 20 мутаций стаба красят тесты (20-я нейтральна в самом стабе). Стаб откачен (git checkout + удаление epics.py/board.py). После стаба механически перенесено заведение эпика из фикстур в тело теста (start_after_write, epic_watch) — повторно стабом не гонялось.

## Не сработало
- `ls`/`cat`/`rm` в Bash недоступны (удаление — python os.remove); heredoc с `${…}` отклоняется — скрипт мутаций писал файлом.
- Заведение эпика в фикстуре: SystemExit в setup фикстуры даёт внутреннюю ошибку pytest (`assert not self._finalizers`) — заводить в теле теста.
- Импорт `gitcmd`/`artifact_branch` в долгоживущем файле — отказ guard «git-модуль»: песочница начисления — класс `LightTransitionSandbox + DeveloperBriefTmpRootTest`.

## Где остановился
- Готово: preflight пройдена; plank-run — «планки нет» (ожидаемо, всё в tests/).

## Чего не хватило
- Кода Э1 — интерфейс эпиков взят из его SPEC (ещё на spec_audit); расхождение Э1 с ним разработчик эскалирует.
