---
task: 01M290PP4KBTG1KYS1PWKQJH6T
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: дозор watch — классы stops/ci, identity сессии не через ppid, отказ пустой --mine, выход по событию --exit-on

## Фаза A: проверка плана

PLAN.md итерации 2 не переоткрывает подход — секция «Итерация 2» точечно
описывает исправление двух замечаний R1-F1/R1-F2 из REVIEW.md итерации 1
(`orchestrator/session.py:53-68`, докстринги тестов), без расширения зоны
за пределы `orchestrator/session.py`/`orchestrator/watch.py`/`tests/`.
Инкрементальный diff пакета от sha предыдущего вердикта показал пусто —
это артефакт того, что sha предыдущего вердикта (c909a628, коммит
«подтяжка main») совпадает с текущим HEAD ветки, а не признак отсутствия
изменений (см. заметку скила «Инкрементальный diff — пустой не значит
без изменений»); проверил вручную: коммит вердикта итерации 1
(66e5f048, артефактная ветка) предшествует фикс-коммиту `c70e73af`
(«замечания ревью — эксклюзивное создание session-id (R1-F1), заявки
Ловит-мутацию (R1-F2)») и merge-коммиту `c909a628` («подтяжка main») —
именно эти два коммита и есть содержимое итерации 2.

## Соответствие SPEC

Все 6 требований и AC-1..AC-9 уже разобраны построчно в REVIEW.md
итерации 1 с вердиктом OK (кроме двух замечаний ниже) — повторно не
пересказываю, изменений в этой части кода со времени итерации 1 не было
(единственные правки — по замечаниям R1-F1/R1-F2, см. «Реестр
замечаний»). Прогнал все 9 приёмочных модулей `tasks/…/acceptance_tests/
test_ac{1..9}*.py` заново — зелёные (AC-9 — легальная пометка `ci`, весь
`tests/` гоняет CI на каждый пуш).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (классы stops/ci) | OK | без изменений с итерации 1; AC-1/2/3 зелёные |
| 2 (identity из файла `.artel/`) | OK | R1-F1 закрыто — эксклюзивное создание файла; AC-4/5 зелёные |
| 3 (отказ пустой выборки) | OK | без изменений с итерации 1; AC-6 зелёный |
| 4 (`--exit-on`/`--once`) | OK | без изменений с итерации 1; AC-7 зелёный |
| 5 (фильтр pre-advance из `refusals`) | OK | без изменений с итерации 1; AC-8 зелёный |
| 6 (диф `docs/operator-session.md`) | OK | приложение к PLAN.md — перепроверил `git apply --check` на текущем HEAD, применяется чисто |

## Замечания

Оба замечания итерации 1 закрыты по существу — новых не завёл.

- (закрыто) `orchestrator/session.py:53-68` — R1-F1, см. реестр.
- (закрыто) `tests/test_watch.py`/`tests/test_session.py` — R1-F2, см. реестр.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/session.py:53-68 | создание `.artel/session-id` не атомарно (гонка записи между конкурентными первыми обращениями) | процесс, проигравший гонку, действовал бы под identity, расходящейся с персистентным файлом — регресс исходного бага задачи | эксклюзивное создание (`O_CREAT\|O_EXCL`) — реализовано `c70e73af`: `os.open(path, os.O_CREAT\|os.O_EXCL\|os.O_WRONLY)`, при `FileExistsError` перечитывает уже записанное победителем значение (`session.py:77-82`). Новый тест `SessionIdentityFileRaceTest::test_concurrent_first_access_returns_winners_identity_not_own_fresh_value` мокает `os.open` так, что первый вызов пишет «чужую» identity и поднимает `FileExistsError` — проверил: тест реально ловит регресс отката к голому `write_text` (вручную откатил фикс — тест падает: `ppid-222 != ppid-111`). Заодно найден и исправлен побочный дубликат `tests/test_lease.py::ResolveSessionIdTest` (падал на реальном `config.ROOT`, не наследовал `TmpRootTest`) — предметно, не расширение зоны. Прогнал `tests.test_session`, `tests.test_watch`, `tests.test_lease` — 52 теста, все зелёные. |
| R1-F2 | accepted | tests/test_watch.py (137,178,197,220,235,265,279,290,304,312,327); tests/test_session.py (35,39,43,49,55,69,80,95) | ни один новый/изменённый тестовый метод не нёс заявку `Ловит мутацию: …` в докстринге | нарушение обязательной практики test-authoring/review-checklist | дописан абзац `Ловит мутацию: …` в докстринг каждого из 19 перечисленных методов — сверил каждую заявку с телом теста: формулировки называют конкретную мутацию (например «`_matches_class` перестанет звать `ci.verifying_is_red`», «`os.open(... O_EXCL ...)` заменят на `write_text`») и её наблюдаемый эффект, соответствующий фактическому ассерту метода — тавтологий и пересказа имени метода не нашёл. |

## Вердикт

approved — оба замечания итерации 1 закрыты по существу (не только
формально), новых дефектов не нашёл. Приложение-диф к защищённому пути
проверено `git apply --check` заново на текущем HEAD.

## Проверено исполнением

- `python3 -m unittest tests.test_session tests.test_watch tests.test_lease -v` — 52 теста, все `ok`.
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac1_stops_ci_event_classes.py` — 3 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac2_stops_class.py` — 2 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac3_ci_class.py` — 2 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac4_session_identity_file.py` — 3 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac5_detached_lease_matches_watch_mine.py` — 1 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac6_empty_selection_refuses.py` — 2 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac7_exit_on_and_once.py` — 4 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac8_pre_advance_refusals_excluded.py` — 1 ok
- `python3 -m unittest tasks/01M290PP4KBTG1KYS1PWKQJH6T/acceptance_tests/test_ac9_existing_suites_stay_green.py` — 0 тестов (легальная пометка `ci`, критерий про существующий `tests/`, покрывается CI-джобом ветки)
- Вручную откатил фикс R1-F1 (заменил `os.open(O_EXCL)` обратно на `path.write_text`) — `SessionIdentityFileRaceTest` упал (`ppid-222 != ppid-111`), затем восстановил фикс через `git checkout -- orchestrator/session.py` — подтверждает, что тест реально ловит заявленную мутацию, не тавтологичен.
- `python3 scripts/guard.py --all` — «GUARD: ок (773 файлов)», предупреждения только по чужим задачам (`01M1RA0R9AH9RBAHD4A2Z5SEWQ`, `T067`), не по этой ветке.
- `python3 scripts/codebase_map.py` — диф с закоммиченным `docs/codebase-map.md` только по `built_at_sha` (восстановил рабочее дерево `git checkout -- docs/codebase-map.md` после проверки, в вердикт не входит).
- `git apply --check` (диф-приложение `docs/operator-session.md` из PLAN.md, требование 6) на текущем HEAD ветки — применяется чисто.
- `git show c70e73af --stat` / `git show c909a628 --stat` — единственные файлы фикс-коммита: `orchestrator/session.py`, `tests/test_session.py`, `tests/test_lease.py`, `tests/test_watch.py`, `docs/codebase-map.md` (только `built_at_sha`); единственный файл merge-коммита подтяжки main — `docs/backlog.md`, взят из main целиком, как предписывал ANSWER-1 — вне зоны задачи ничего не тронуто.
- CI ветки (коммит c909a628) — зелёный, 7 проверок (по данным пакета ревью).
- Статус: CI-джоб полного `tests/` гоняется на каждый пуш отдельно — сам полный набор в шаге ревью не прогонял (решение Оператора 05.09).

## Предложения системе

- Инкрементальный diff пакета ревью (sha предыдущего вердикта → HEAD)
  снова оказался пустым при реально непустой итерации (тот же класс,
  что T082/T087) — на этот раз потому, что sha предыдущего вердикта
  оркестратор взял равным merge-коммиту «подтяжка main», который
  оказался текущим HEAD ветки. Стоит донастроить построение пакета брать
  sha именно коммита, где REVIEW.md получил свой предыдущий `status`
  (артефактная ветка), а не последний известный код-коммит ветки — иначе
  каждый ревьювер вынужден вручную идти в `git log -- tasks/<id>/
  REVIEW.md`, как предписывает уже существующая заметка скила.
