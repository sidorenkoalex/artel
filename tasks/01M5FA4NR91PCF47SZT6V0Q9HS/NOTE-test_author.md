# Записка test_author — 01M5FA4NR91PCF47SZT6V0Q9HS

## Выяснено
- Раскладка планки: долгоживущие tests/test_01m5fa4nr91pcf47szt6v0q9hs_{mark,live_cmd,doctor_live,window}.py
  (AC-2/3/4/6; AC-7..15; AC-16..18; AC-1/5/21), разовый acceptance_tests/test_isolation_list.py (AC-19, AC-20).
  Все 21 AC — тесты, пометок manual/skip/escalate нет.
- Каталог реестра в долгоживущих — `config.ROOT/.artel/config.CANARY_LIVE_DIRNAME` (`_live_dir` закрыт).
- Живой pid — дочерний `python -c sleep(600)`, мёртвый — дождавшийся `python -c pass`.
- Отказ под ролью «canary live: команда недоступна процессу роли» есть уже сегодня (artel.py:2043); AC-15 красен из-за справки.
- doctor.all_checks в песочнице зовёт настоящий claude/gh — в …_doctor_live.py сторож subprocess.run/Popen.
- Краснота до кода (проверено): mark — AC-2/3/4; live_cmd — всё, кроме частей с прежним поведением; doctor_live — всё;
  window — AC-1 (approve мержит) и AC-5(i) (note уходит в origin); AC-5(ii), AC-21 зелёные с рождения (прежнее поведение);
  планка — AC-19 и AC-20 называют ровно CmdCanaryTemplateSelectionTest и DoctorFixOrderTest.
- Стаб-валидация (шаг 2): временный стаб в canary.py (метки без записи в live_run_note, `canary live`/`--drop`, проверка
  doctor), artel.py (ветка `canary live`, строка справки), doctor/cli.py (строка canary-live, уборка под --fix) и подмена
  `canary._live_dir` в setUp двух классов — все 4 файла tests/ и планка зелёные (17+3+3 passed). Стаб откачен, дерево чистое.
- preflight: все проверки «пройдена».

## Не сработало
- grep/ls в Bash с `cd …&&`, `$var`, циклы for — песочница требует подтверждения; абсолютные пути и один pytest на несколько файлов работают.
- Отказ advance прошлого шага (нет трассируемости всех AC) — шаг 1 оборвался rc=1 до сдачи; сейчас трассируемость пройдена.

## Где остановился
- Готово к сдаче шага.

## Чего не хватило
- Ничего существенного; дольше всего — сборка песочницы окна мержа (образец tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py).
