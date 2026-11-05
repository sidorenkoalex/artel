# Записка spec_auditor

## Выяснено
- Визит 3: SPEC 3d4f1b84…, 13 решений гейта закрывают 14 пунктов визита 2. Якоря верны.
- Опыт Docker (`/usr/local/bin/docker`, временный DOCKER_CONFIG с `{}` и ссылкой на дополнение compose, DOCKER_HOST=unix://~/.docker/run/docker.sock, проект `auditexp-*`, снят): `config --format json` — JSON, `default` с `name: <проект>_default`; метки сервиса доходят до one-off контейнера; после SIGKILL клиента one-off живёт; `compose kill` его убивает; `down -v --remove-orphans` убирает всё; `-p <имя> down` без `-f` работает; `context inspect --format` → unix://.
- Новые находки: DoctorFixOrderTest (tests/test_doctor_closed_ref_fix.py:152, unittest.TestCase без песочницы, store.db→None) исполнит новую починку по-настоящему; `_pult.py` (plank_helper.py:36-39) — git по путям машины, в контейнере не работает; решение 9 не закрывает планку при long_lived_dir вне workdir (acceptance.py:2068) и plank_layout компонента; AC-5 «подменённая проверка» без канала; doctor docker без предела времени/исхода отказа; test_ac6 (test_01m5n8…_plank_layout_names.py:331) запрещает закрытые имена acceptance вне модуля.

## Не сработало
- `cd` + относительный путь, `$VAR`, `{…}` в Bash — отказ; помогает python3 - <<EOF с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, 8 пунктов; guard ок. Временный каталог опыта Docker в $TMPDIR (audit-docker-*) — без контейнеров, проекты сняты.

## Чего не хватило
- Docker без дополнения compose в HOME роли: нужен свой DOCKER_CONFIG с ссылкой на ~/.docker/cli-plugins/docker-compose.
