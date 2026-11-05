---
task: 01M6PRDZH17WQ6SYABJFZRDCWW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тест compose с настоящим Docker — каталог дополнений Docker в подставном DOCKER_CONFIG

## Подход
В `tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py` добавляется
помощник `docker_config_sandbox() -> Path` рядом с `docker_skip_reason`:
`tempfile.mkdtemp(prefix="artel-docker-config-")` (тот же префикс, что
прежний `:314`), настоящая конфигурация — `os.environ.get("DOCKER_CONFIG")
or str(Path(os.environ.get("HOME") or Path.home()) / ".docker")` (правило
`orchestrator/acceptance.py:870-872`), вычисляется в момент вызова; при
`<настоящая>/cli-plugins`, являющемся каталогом, — `os.symlink` на него
под именем `cli-plugins`. Ничего больше не копируется и не связывается.
`test_ac17_real_docker_compose_run` берёт каталог вызовом помощника вместо
`tempfile.mkdtemp`; очистка и подмены `DOCKER_CONFIG`/`HOME` — прежние
строки от того же имени. Условие пропуска, утверждения и `finally` не
меняются. Докстринги модуля и теста дополняются строкой о ссылке.
Новые тесты не пишутся: AC-1…AC-5 целиком покрыты долгоживущим файлом
`tests/test_01m6prdzh17wq6syabjfzrdcww_docker_config_sandbox.py`.

## Шаги
1. Помощник `docker_config_sandbox`, правка тела теста и докстрингов; прогон
   `tests/test_01m6prdzh17wq6syabjfzrdcww_docker_config_sandbox.py` и
   прежнего файла при `CI=1` (ожидание: 5 passed, 1 skipped); карта
   `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 (долгоживущий файл test_author) |

## Влияние на систему
Меняется только тестовый файл задачи 01M6PAJ61D4PYAP79ADRPA6MWV, строки
подготовки: утверждения, маркер `skipif`, `finally` не тронуты — гейт
неослабления находок не даст. Код пульта не меняется. Ссылка ведёт в
настоящий каталог дополнений, но `shutil.rmtree` подставного каталога
ссылку не разыменовывает (удаляет саму ссылку) — цель цела. Откат — revert
merge-коммита.

## Риски
- Вне CI и с Docker тест теперь действительно проверяет `compose` — если
  стенд окажется не снят, тест покраснеет (это и есть цель правки).

## Предложения системе
- `compose_projects` (`tests/test_01m6paj61d4pyap79adrpa6mwv_compose_docker.py:246-256`)
  молча возвращает `[]` при неразборчивом выводе/ненулевом коде `docker compose ls` —
  утверждение «стенд снят» становится пустым; строка бэклога (SPEC «Не входит»).
