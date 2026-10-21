# Записка test_author — 01M5FA4NR91PCF47SZT6V0Q9HS

## Выяснено
- Старт шага: acceptance_tests/ пуст, прошлой записки нет. 21 AC.
- Раскладка планки (план): долгоживущие tests/test_01m5fa4nr91pcf47szt6v0q9hs_{mark,live_cmd,doctor_live,window}.py
  (AC-2/3/4/6; AC-7..15; AC-16..18; AC-1/5/21), разовый acceptance_tests/test_isolation_list.py (AC-19, AC-20).
- Каталог реестра в долгоживущих — `config.ROOT/.artel/config.CANARY_LIVE_DIRNAME` (канон `_live_dir` закрыт).
- Живой pid — дочерний `python -c sleep(600)`, мёртвый — дождавшийся `python -c pass`.
- TmpRootTest подменяет subprocess.run на SpyRun(passthrough) — `ps` идёт настоящий; doctor.process_start_time публичен.
- Отказ под ролью: «artel.py canary live: команда недоступна процессу роли» (artel.py:2043) — уже сегодня.
- Тест окна мержа требует полной песочницы как tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py (отказ стоит перед push).
- Формы cmd_doctor(fix=True) в tests/: прямой kw, позиционный (False, True), `run_cmd(doctor.cmd_doctor, fix=True)`, через self.doctor_fix().

- Готовы: tests/…_mark.py (AC-2,3,4,6), …_live_cmd.py (AC-7..15), …_doctor_live.py (AC-16..18),
  acceptance_tests/test_isolation_list.py (AC-19, AC-20). Красны по верной причине; AC-19 до задачи
  называет ровно CmdCanaryTemplateSelectionTest и DoctorFixOrderTest, остальные 117 проходят.
- doctor.all_checks в песочнице запускает НАСТОЯЩИЙ claude (live-smoke) и gh — в …_doctor_live.py
  стоит сторож subprocess.run/Popen (только ps, python, git без сети).

## Не сработало
- grep/ls в Bash с `cd …&&` иногда требует подтверждения — абсолютные пути работают.

## Где остановился
- Осталось: …_window.py (AC-1, AC-5, AC-21) на песочнице по образцу canary_window; затем стаб-валидация, preflight.

## Чего не хватило
