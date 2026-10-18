# Записка developer

## Выяснено
- Код задачи (ci.py, ci_rerun.py, fsm_merge_gate.py) — в 6fe01626, по ANSWER-2 (вариант а) не менялся.
- Шаг 3 (после ANSWER-2): правка только фикстур. `tests/sandbox.py`: константа `PROJECT_URL = "https://localhost/artel-tests/{name}"` (localhost — инвариант 35), `make_project_repo` пишет её в запись проекта; помощник `route_url_to_bare(test, url, bare)` — `url.<bare>.insteadOf` через `GIT_CONFIG_COUNT/KEY/VALUE` в os.environ (mock.patch.dict). `tests/test_01m42…_project_area.py::add_external_project` — url = PROJECT_URL + route_url_to_bare.
- Три красных теста (01M42 test_ac5, 01M4M67 ExternalMergeTest×2) зелёные; оба файла целиком + файлы задачи — 59 зелёных.
- Прочие тесты с `file:///nonexistent/<имя>` в своих записях (много файлов) — не трогал: красных от них в прогоне №1 не было.

## Не сработало
- `pytest -n 4` — воркеры падают; гонять последовательно.
- `ls`/`rm`/цепочки `;` в Bash требуют подтверждения.

## Где остановился
- suite-run №2: 5718 прошло, 1 красный того же класса (`test_01m484…_artel_docs_ref.py::FetchAllClonesTest` подменял буквальную заглушку `file:///nonexistent/<имя>`) — переведён на `PROJECT_URL`; №3 (повтор упавших) зелёный. Планка 4/4. Карта регенерирована. PLAN status: ready. Фикстурная правка не закоммичена — закоммитит пульт.

## Чего не хватило
- Машина перегружена — полный набор долго.
