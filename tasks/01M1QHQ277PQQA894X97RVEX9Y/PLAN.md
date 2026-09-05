---
task: 01M1QHQ277PQQA894X97RVEX9Y
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Тесты не выходят в сеть: перехват сетевых git-команд в песочнице, локальные фикстуры, инвариант

## Подход

Реальный репро (подтверждено чтением кода): `tests/test_git_fixation.py::
ExternalTargetAdvanceIgnoresDirtyCheckTest` заводит `targets.yaml` с
`url: https://example.invalid/sled` и гоняет `fsm.cmd_advance` через
`_GitFixationTmpRootTest` — песочницу, которая ЦЕЛИКОМ подменяет
`gitcmd.subprocess.run` на сырой `_REAL_SUBPROCESS_RUN` (не через `SpyRun`).
`in_dev -> review` зовёт `fsm._pull_main_or_escalate` ->
`_origin_main_sha`, которая для внешнего target фетчит буквально `entry
["url"]` (`orchestrator/fsm.py:199`) — настоящий `git fetch -q https://
example.invalid/sled main` уходит в реальный DNS-резолвер и висит на
таймауте при отсутствии/обрыве сети. Это и есть инцидент из «Контекста»
SPEC.

Два независимых рубежа защиты (оба нужны — обоснование монолита SPEC):

1. **Единая точка перехвата** — `tests/sandbox.py::SpyRun` (её `TmpRootTest.
   setUp` заводит с `passthrough_unknown=True`) перед тем, как отдать
   неопознанную команду настоящему `subprocess.run`, проверяет: это
   `git fetch/push/ls-remote/clone` (сквозь ведущие `-C <path>`, как уже
   делает `git_subcommands`) с адресом (первый позиционный аргумент после
   подкоманды, не начинающийся с `-`), который НЕ является локальным
   (`file://` или абсолютный путь, `/...`; для `http(s)://` — хост ровно
   `localhost`/`127.0.0.1`, точное сравнение, не префикс — тот же
   инвариант АК-6 требует ниже)? Да — мгновенный `CompletedProcess(rc=1,
   stderr="сеть в тестах запрещена: <команда> <адрес>")`, решение по
   ФОРМЕ адреса (текстовый префикс), без обращения к резолверу (AC-9).
   Нет (в т.ч. голое имя remote'а вроде `origin` — не URL вовсе, T048/
   T053 адресуют локальные bare-репо им же) — передаёт дальше настоящему
   `subprocess.run`, поведение не меняется (AC-2).

   Логика вынесена в модульные функции `_is_local_git_address`/
   `_network_git_command_denial`/`network_guarded_real_run` (не только
   метод `SpyRun.__call__`), потому что `tests/test_git_fixation.py::
   _GitFixationTmpRootTest` перекрывает `gitcmd.subprocess.run` СВОИМ
   патчем (`_REAL_SUBPROCESS_RUN`, в обход `SpyRun` целиком) — без
   единой функции этот файл остался бы вторым, никем не защищённым путём
   к реальному `subprocess.run` с тем же классом риска, что и вызвал
   инцидент. Патч этого файла меняется на `sandbox.
   network_guarded_real_run` — тот же настоящий git для всего
   остального (init/add/commit/config/hash-object/...), но с перехватом
   сети.

2. **Локальные фикстуры** (требование 2) — адреса `https://
   example.invalid/...` в целевых YAML-фикстурах заменены на
   `file:///nonexistent/<name>` (три названных файла + два подобных,
   `test_doctor.py`/`test_multitarget.py`) — независимая защита: даже
   там, где перехват физически не участвует (`gitcmd.git` подменён
   отдельно, как в `test_branch_freshness_gate.py`), быстрый локальный
   адрес не даёт сканеру требования 3 покраснеть и не даёт НИКАКОМУ
   будущему коду случайно уйти в сеть тем же фикстурным значением.
   `test_branch_freshness_gate.py::TargetSourcedRemoteTest` — адрес
   `http://127.0.0.1:9/acme-target.git` (не `file://`, чтобы остаться
   похожим на URL-запись target'а, как того просит AC-4: `"127.0.0.1" in
   class_src`); её assert на литерал адреса переписан на новое значение,
   остальные три assert'а того же метода (origin/trunk/MAIN_BRANCH) не
   тронуты.

   Дополнительно найдены (grep по `tests/**/*.py`, не названы SPEC)
   `test_ci_status.py:499`/`test_github_adapter.py:50` — `https://
   api.github.com/...`/`https://github.com/...` внутри УЖЕ ЗАМОКАННОГО
   ответа `gh` (`ci.gh`/`github_adapter.ci.gh` подменены лямбдой/моком в
   самих этих тестах, реального обращения нет). Правка их текста снизила
   бы реалистичность фикстуры без всякой пользы (адрес никогда не
   резолвится) — закрываю именованной константой исключений требования
   3, а не правкой (SPEC, требование 2, допускает оба пути; тот же выбор
   применён здесь ко второй паре файлов, которую нашла я, а не аналитик).

3. **Структурный тест + инвариант** (требование 3, AC-6/AC-7) —
   `docs/invariants.md`/`tests/test_invariants.py` защищены (ADR-0002):
   правка поставляется unified-diff-приложением к этому PLAN.md, не
   коммитом в ветку (AC-8, тот же порядок, что ANSWER-1
   01M1KVGD18P9H5WR7VM8TGPV1T). Сканер диффа и приёмочный `_util.
   find_dns_addresses` реализуют ОДНО и то же правило (регэксп
   `https?://[^\s'"]+`, хост — точное сравнение с `localhost`/
   `127.0.0.1`) двумя независимыми копиями кода (тот же приём, что уже
   разводит защищённый и приёмочный код в 01M1KVGD18P9H5WR7VM8TGPV1T) —
   не импортом друг друга, потому что защищённый файл на диске ветки
   задачи не появится вовсе до применения диффа Оператором.

## Шаги

1. `tests/sandbox.py`: `_is_local_git_address`, `_network_git_command_
   denial`, `network_guarded_real_run` — единая точка перехвата;
   `SpyRun.__call__` зовёт её вместо прямого `_REAL_RUN` в ветке
   `passthrough_unknown`. Новый `tests/test_sandbox.py` — постоянное
   юнит-покрытие (AC-1/AC-2/AC-9 в миниатюре, не дублирует приёмку
   буквально: как модульные функции, так и `SpyRun`/`TmpRootTest` целиком).
2. `tests/test_git_fixation.py`: `_GitFixationTmpRootTest.setUp` патчит
   `gitcmd.subprocess.run` на `sandbox.network_guarded_real_run` (было —
   сырой `_REAL_SUBPROCESS_RUN`); адреса `TARGETS_YAML`/
   `ARTEL_TARGETS_YAML`/строка 188 — `file:///nonexistent/...`.
3. `tests/test_coldstart.py`, `tests/test_doctor.py`, `tests/
   test_multitarget.py`: адреса фикстур — `file:///nonexistent/...`.
4. `tests/test_branch_freshness_gate.py`: адрес `TargetSourcedRemoteTest.
   TARGETS_YAML` — `http://127.0.0.1:9/acme-target.git`; assert строки
   592 — под новый адрес, остальные три assert'а метода не трогаю.
5. Регенерация `docs/codebase-map.md` (`python3 scripts/codebase_map.py`)
   тем же коммитом, что правка `tests/sandbox.py` (conventions-core).
6. Unified-diff-приложение (не коммит в ветку) к этому PLAN.md:
   `docs/invariants.md` (новая строка 34) + `tests/test_invariants.py`
   (`NoNetworkAddressesInTestsTest`, включает именованную константу
   исключений для `test_ci_status.py`/`test_github_adapter.py`).
   Проверено `git apply --check` на чистом дереве перед сдачей.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (единая точка перехвата) | 1, 2 |
| 2 (локальные фикстуры трёх файлов + doctor/multitarget) | 2, 3, 4 |
| 3 (инвариант + структурный тест) | 6 |
| 4 (тесты перехвата/структурного теста) | 1 (юниты), 6 (диф несёт свой структурный тест), приёмка задачи (AC-1/2/3/4/5/6/9/10, уже залочена) |

## Влияние на систему

Затронуто: `tests/sandbox.py` (единая точка подмены `gitcmd` для ВСЕХ
наследников `TmpRootTest`, инвариант 33) и пять существующих тестовых
файлов — только текст фикстур/один патч `setUp`, ни один существующий
ассерт логики продукта не ослаблен и не удалён (AC-4 явно требует
сохранить все четыре ассерта переписываемого метода — сохранены).
`RealGitSandbox` (tests/sandbox.py, ~10 файлов-наследников) намеренно НЕ
тронут этой задачей: ни один его текущий потребитель не несёт DNS-адрес
в фикстуре (проверено grep) — нулевой риск сейчас; см. «Предложения
системе» ниже про будущий риск того же класса.

Продуктовый код (`orchestrator/`) не меняется ни строкой — вся правка
внутри тестовой инфраструктуры и защищённых документов (последние —
диффом, не кодом этой ветки). Откат: `git revert` коммита(ов) этой
ветки восстанавливает прежние (медленные при обрыве сети, но
корректные) фикстуры и снимает перехват — без остаточного состояния,
поскольку продуктовый код не менялся.

Инварианты/гейты/лимиты рядом не ослабляются: новый структурный тест
(защищённый диф) — строго добавление нового инварианта 34, ни один из
33 существующих не тронут; `TmpRootTest`/`SpyRun` — расширение
существующей точки подмены (инвариант 33) новым правилом отказа, не
снятие существующего покрытия.

## Риски

- `_is_local_git_address` распознаёт голое имя remote'а (`origin`,
  `acme`, ...) как «локальное» без проверки его реальной git-конфигурации
  (нет схемы `://` и не начинается с `/` → передаётся дальше без
  перехвата). Это НАМЕРЕННО (T048/T053 адресуют локальные bare-репо
  именно так, AC-2/приёмочный тест `test_ac2_local_bare_repo_not_
  blocked.py` это фиксирует) — но если когда-нибудь появится тест,
  настраивающий `origin` на реальный сетевой URL и адресующий фетч по
  ИМЕНИ remote'а, а не URL'ом напрямую, перехват его не увидит. Сегодня
  такого нет нигде в `tests/` (проверено — все внешние адреса либо URL
  напрямую, либо локальные bare по абсолютному пути).
- `RealGitSandbox` (см. «Влияние на систему») — не защищена этой задачей;
  если будущая задача добавит туда DNS-адрес фикстуры, инвариант 34
  поймает его структурно (AC-6/AC-7), но реальный `subprocess.run` там
  всё ещё без перехвата по форме адреса — регрессия хана возможна,
  просто CI её увидит через инвариант/структурный тест раньше, чем через
  зависший прогон.

## Предложения системе

- `tests/sandbox.py::RealGitSandbox` — единственная широко используемая
  (~10 файлов) песочница с настоящим git, которая НЕ патчит `gitcmd.
  subprocess.run` вовсе (ни `SpyRun`, ни новый `network_guarded_real_
  run`): класс риска этой задачи («песочница с настоящим git без
  перехвата сети») закрыт для `TmpRootTest`/`_GitFixationTmpRootTest`, но
  не для неё. Кандидат на отдельную задачу: патчить и её тем же
  `network_guarded_real_run`, раз он теперь существует.

## docs/invariants.md

Новая строка реестра #34 (требование 3, AC-7). Проверено `git apply
--check` на чистом дереве.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index bd3196fd..383c6685 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -58,6 +58,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 31 | Агентный шаг роли не читает и не исполняет project-/local-слой клиентских настроек репозитория (`.claude/settings.json`, `.claude/settings.local.json`, включая хуки — ни главной копии пульта, ни worktree роли): `run_agent_once` вызывает `claude` с `--setting-sources user` (`config.AGENT_SETTING_SOURCES`), исключающим оба слоя из резолвинга CLI независимо от cwd. Времянка «операторские хуки обязаны безвредно деградировать» (27.08, инцидент T046) остаётся вторым рубежом (defense-in-depth), не единственной защитой | `test_agent_prompt.PromptChannelTest` (argv несёт флаг); `test_doctor.IsolationSmokeTest` (структурный маркер); `tasks/T058/acceptance_tests/test_ac1_ac2_role_hook_isolation.py` (канарейка реально не/срабатывает — role/operator) | ADR-0003 п.14; tasks/T058/SPEC.md, требования 1–2; инцидент T046 27.08.2026 |
 | 32 | Потолок `MAX_PARALLEL_TASKS` блокирует старт агентного шага (`run`/`auto`), пока число других задач с живым lease (heartbeat не старше `LEASE_STALE_AFTER_SEC`, pid адресуем) не опустится ниже потолка; отказ именует занятые задачи и их `session_id`, пишется в журнал, не обходится ни повторным `run`, ни `advance` следующим за отказавшим шагом; собственный lease стартующей задачи и протухшие/мёртвые чужие lease в счёт не идут; `kill`/`status`/`approve`/`reject`/`budget`/`log`/`release`/`doctor` лимитером не затронуты | `test_invariants.ParallelTaskLimitIsNotBypassableTest`; `tasks/T060/acceptance_tests/test_max_parallel_tasks.py`; `tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py::Ac5ReleaseBypassesLeaseAndLimiterTest` | tasks/T060/SPEC.md, требования 1-6; решение Оператора 28.08.2026 (очередь п.2б роадмапа); tasks/T062/SPEC.md, требование 4 |
 | 33 | Тесты не пишут в настоящий репозиторий пульта: полный прогон `tests/` не меняет набор ссылок (`refs/heads/*`, `refs/artifacts/*`) настоящего репозитория; вся плотницкая запись артефактной ветки (`artifact_branch.write_commit`/`commit_files`, `snapshot.py`, `pin.py`) идёт через единую точку подмены `gitcmd` (не `subprocess.run`/`Popen` напрямую), которую `tests/sandbox.py::TmpRootTest` патчит по умолчанию для всех наследников | `test_invariants.CarpentryGitCallsGoThroughGitcmdTest`; CI job `python` (сторож ссылок вокруг `unittest discover`, `.github/workflows/ci.yml`); `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/test_ac1_full_suite_ref_isolation.py`, `test_ac2_previous_verdict_sha_test_migration.py`, `test_ac3_unified_git_choke_point.py` | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md, требования 1-3 (класс-дефект: `tests.test_review_package.PreviousVerdictShaTest` заводил задачу через `cmd_new` без подмены `config.ROOT`, `artifact_branch.py` звал `subprocess.run` в обход `gitcmd` — сотни осиротевших веток `artifact/*` в настоящем репозитории пульта) |
+| 34 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` | tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
 
 ## На ревью — тестом не выражаются
 
```

## tests/test_invariants.py

Новый структурный тест требования 3 (AC-6, AC-10): `NoNetworkAddressesInTestsTest`
— сканирует `tests/**/*.py` на предмет `http(s)://<DNS-имя>` (правило и
исключения буквально соответствуют `_util.find_dns_addresses` приёмочной
планки задачи, две независимые копии одного и того же правила — см.
«Подход»). Проверено `git apply --check` на чистом дереве.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index a3a8b88c..947debaf 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -20,6 +20,7 @@ main (сценарии уборки — test_kill_cleanup.py).
 import contextlib
 import json
 import os
+import re
 import shutil
 import socket
 import subprocess
@@ -1496,5 +1497,89 @@ class CarpentryGitCallsGoThroughGitcmdTest(unittest.TestCase):
             f"прямые вызовы subprocess.run/Popen вне единого модуля gitcmd: {offenders}")
 
 
+class NoNetworkAddressesInTestsTest(unittest.TestCase):
+    """Инвариант 34 (docs/invariants.md): тесты не читают сеть по DNS-имени.
+
+    Ни один файл `tests/**/*.py` не несёт адреса `http(s)://<DNS-имя>`,
+    кроме `localhost`/`127.0.0.1` (SPEC 01M1QHQ277PQQA894X97RVEX9Y,
+    требование 3, AC-6) — тот же класс защиты, что инвариант 33 (единая
+    точка подмены `gitcmd`), только про сетевое ЧТЕНИЕ, не про плотницкую
+    ЗАПИСЬ: реальный `git fetch` по такому адресу резолвит DNS настоящим
+    резолвером и виснет на таймауте при обрыве сети (инцидент 05.09,
+    «Контекст» той же SPEC — фикстурный адрес `sled`-target'а в `tests/
+    test_git_fixation.py` вешал полный прогон `tests/` на минуты).
+
+    Хост сравнивается ТОЧНО, не префиксом (`127.0.0.1.evil.example` —
+    DNS-имя, лишь начинающееся с исключённого `127.0.0.1`, не сам
+    loopback — обязан быть пойман, не пропущен).
+    """
+
+    _URL_RE = re.compile(r"https?://[^\s'\"]+")
+    _EXEMPT_HOSTS = ("localhost", "127.0.0.1")
+
+    # (имя файла, хост) -> обоснование: адрес — decorative/тестовый текст,
+    # никогда не передаётся реальному сетевому вызову, поэтому исключён
+    # из скана (SPEC 01M1QHQ277PQQA894X97RVEX9Y, требование 3).
+    _EXCEPTIONS = {
+        ("test_github_adapter.py", "github.com"):
+            "stdout уже замоканного `gh` (github_adapter.ci.gh подменена "
+            "лямбдой в setUp самого теста) — тест не открывает соединение "
+            "по этому адресу, строка лишь имитирует формат вывода "
+            "`gh pr create`",
+        ("test_ci_status.py", "api.github.com"):
+            "текст внутри сообщения об ошибке уже замоканного `ci.gh` "
+            "(`set_check_runs` подменяет ответ целиком) — адрес не "
+            "аргумент реального вызова, тест не обращается к сети",
+        ("test_sandbox.py", "example.invalid"):
+            "статические строки-фикстуры, проверяющие саму логику "
+            "распознавания DNS-адреса (`_is_local_git_address`/"
+            "`_network_git_command_denial`) — никогда не передаются "
+            "реальному `subprocess.run`, только сравниваются как текст",
+        ("test_sandbox.py", "127.0.0.1.evil.example"):
+            "та же статическая фикстура — хост, лишь НАЧИНАЮЩИЙСЯ с "
+            "loopback-адреса, проверяет точность сравнения хоста в "
+            "`_is_local_git_address`, тоже не передаётся `subprocess.run`",
+    }
+
+    @classmethod
+    def _host_of(cls, url: str) -> str:
+        rest = url.split("://", 1)[1]
+        return rest.split("/", 1)[0].split(":", 1)[0]
+
+    def _dns_addresses(self, text: str) -> list:
+        return [m.group(0) for m in self._URL_RE.finditer(text)
+                if self._host_of(m.group(0)) not in self._EXEMPT_HOSTS]
+
+    def test_no_dns_hostname_addresses_in_tests_tree(self):
+        offenders = {}
+        for path in sorted((config.ROOT / "tests").rglob("*.py")):
+            hits = [url for url in self._dns_addresses(
+                        path.read_text(encoding="utf-8"))
+                    if (path.name, self._host_of(url)) not in self._EXCEPTIONS]
+            if hits:
+                offenders[str(path.relative_to(config.ROOT))] = hits
+        self.assertEqual(
+            {}, offenders,
+            "tests/**/*.py несёт адрес http(s)://<DNS-имя> вне localhost/"
+            f"127.0.0.1 и вне именованных исключений: {offenders}")
+
+    def test_synthetic_dns_hostname_fixture_is_caught(self):
+        """AC-10: мутация — синтетическая фикстура с DNS-именем, которого
+        нет ни в одном реальном файле репозитория, обязана быть поймана
+        (доказательство, что сканер ловит нарушение, а не декорация).
+
+        Схема и хост собраны конкатенацией по частям (не одним смежным
+        литералом), чтобы исходный текст самого этого метода не нёс
+        адрес одной строкой и не попал под собственную проверку
+        требования 3 при сканировании `tests/**/*.py` (сканер читает
+        байты файла, не значение переменной в рантайме).
+        """
+        scheme = "http" + "s://"
+        host = "ci-mirror" + ".invariant-check.example"
+        url = f"{scheme}{host}/repo.git"
+        hits = self._dns_addresses(f'url: "{url}"\n')
+        self.assertEqual([url], hits)
+
+
 if __name__ == "__main__":
     unittest.main()
```

Оба диффа проверены `git apply --check` на чистом дереве по отдельности
и совместно (последовательным `git apply --check` обоих файлов на
незакоммиченное состояние ветки).
