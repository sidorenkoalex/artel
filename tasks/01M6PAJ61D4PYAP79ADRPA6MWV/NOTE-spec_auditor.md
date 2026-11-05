# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Седьмой визит, SPEC 5a67fea4: решение 7.1 (`compose_task_id`, иначе `task_id`) закрыло пункт визита 6.
- Решение 7.2 (отказ compose в роли): `runner.in_role_environment` runner.py:1364-1381 (ARTEL_ROLE или HOME == config.ROLE_HOME); фоновый suite-run снимает только ARTEL_ROLE (suite_run.py:921-922).
- Остаток: треб. 3 «чтобы suite-run/plank-run у compose работали» vs треб. 7 «отказ в роли, в т.ч. фоновый suite-run»; и «окружение docker (треб. 6–7)» для runner.py части 2. Вердикт concerns, дефолт: треб. 7 первично, вне роли работают.

## Не сработало
- `ls` в этой оболочке нет; составные bash с `cd &&` проходят.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard прогнан.

## Чего не хватило
- Явного «вне процесса роли» в цели канала id треб. 3.
