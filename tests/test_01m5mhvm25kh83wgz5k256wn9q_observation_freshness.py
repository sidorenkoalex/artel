"""Свежесть связи наблюдения — одна функция модуля `watch` вместо трёх копий.

Группа: долгоживущий
Красен до реализации: в `watch` нет `observation_age`/`observation_link_fresh` (AttributeError), запуск и `observe show` считают возраст на собственном `datetime.now` модуля `artel` и падают на пустом `last_seen_at`, а разбор `last_seen_at` через `fromisoformat` стоит в трёх местах `orchestrator/`.

Текущее время фиксируется только подменой
`mock.patch.object(watch, "datetime", <подкласс datetime>)`: подкласс
отдаёт заданное «сейчас» и считает вызовы `now`. Чистые функции `watch`
проверяются без песочницы; выбор наблюдения при запуске и флаг `fresh`
наблюдения — через публичный CLI (`artel.main` с `sys.argv`: `run <id>`,
`observe show <id> --json`) в песочнице БД с подменённым
`subprocess.Popen` (настоящий цикл не идёт). Эта связка «команда CLI —
таблица `observations` — блок свежести» и есть предмет критериев AC-4/AC-5.

Свойства проверяются на случайных моментах и долях секунды; зерно
печатается и входит в текст провала.
"""
import ast
import json
import os
import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import orchestrator
from orchestrator import artel, config, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture


def frozen_datetime(moment: datetime):
    """Подкласс `datetime` с `now`, возвращающим `moment`, и список вызовов `now`."""
    calls = []

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return moment if tz is None else moment.astimezone(tz)

    return Frozen, calls


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def random_moment(rnd: random.Random) -> datetime:
    """Случайный момент UTC — с долями секунды или без (обе формы `isoformat`)."""
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    moment = base + timedelta(seconds=rnd.randrange(0, 10 * 365 * 86400))
    if rnd.random() < 0.5:
        moment = moment.replace(microsecond=rnd.randrange(1, 1_000_000))
    return moment


def fromisoformat_on_last_seen(tree: ast.AST) -> list[str]:
    """Имена функций, внутри которых стоит `<имя>.fromisoformat(...)` с
    константой `"last_seen_at"` в поддереве аргумента (`"<модуль>"` — вне функций)."""
    found = []

    def visit(node, owner):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = node.name
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "fromisoformat"):
            args = list(node.args) + [kw.value for kw in node.keywords]
            if any(isinstance(sub, ast.Constant) and sub.value == "last_seen_at"
                   for arg in args for sub in ast.walk(arg)):
                found.append(owner)
        for child in ast.iter_child_nodes(node):
            visit(child, owner)

    visit(tree, "<модуль>")
    return found


class ObservationAgeTest(unittest.TestCase):
    """Чистые функции `watch` — без песочницы."""

    def setUp(self):
        self.seed = new_seed()
        self.rnd = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def test_ac1_observation_age_none_for_empty_and_about_30_for_30s_ago(self):
        """Пустой `last_seen_at` — `None`; «сейчас минус 30 с» — около 30.

        Строки с `last_seen_at`, равным `None` и `""`, дают `None`, а
        `(datetime.now(timezone.utc) - 30 с).isoformat()` — число в
        пределах 30 ± 2 по настоящему времени машины.

        Ловит мутацию: `observation_age` проверяет только `is None` — на
        `""` падает `ValueError` из `fromisoformat`; либо возраст считается
        в обратную сторону (`last_seen - now`) — получается около −30.
        """
        for empty in (None, ""):
            with self.subTest(last_seen_at=empty, seed=self.seed):
                self.assertIsNone(watch.observation_age({"last_seen_at": empty}),
                                  self.msg(f"возраст при {empty!r} не None"))
        for _ in range(3):
            seen = datetime.now(timezone.utc) - timedelta(seconds=30)
            if self.rnd.random() < 0.5:
                seen = seen.replace(microsecond=0)
            age = watch.observation_age({"last_seen_at": seen.isoformat()})
            self.assertIsNotNone(age, self.msg("возраст None для непустой связи"))
            self.assertLessEqual(abs(age - 30), 2,
                                 self.msg(f"возраст {age} вне 30 ± 2 для {seen.isoformat()}"))

    def test_ac2_link_fresh_at_threshold_and_stale_one_second_later(self):
        """Свежесть при зафиксированном «сейчас»: ровно порог — да, порог + 1 с — нет.

        Для случайного момента `last_seen_at` подменённый `watch.datetime`
        отдаёт «сейчас» = `last_seen_at + OBSERVATION_STALE_SECONDS` (истина)
        и `+ OBSERVATION_STALE_SECONDS + 1` с (ложь); пустой `last_seen_at`
        (`None` и `""`) — ложь.

        Ловит мутацию: сравнение `<` вместо `<=` — на возрасте ровно порог
        возвращается `False`; либо `observation_age` берёт настоящее время
        мимо `watch.datetime` — при давнем `last_seen_at` ровно порог даёт
        `False`; либо пустая строка роняет `ValueError` вместо `False`.
        """
        threshold = config.OBSERVATION_STALE_SECONDS
        for _ in range(3):
            seen = random_moment(self.rnd)
            row = {"last_seen_at": seen.isoformat()}
            for offset, expected in ((threshold, True), (threshold + 1, False)):
                with self.subTest(seen=row["last_seen_at"], offset=offset, seed=self.seed):
                    frozen, _ = frozen_datetime(seen + timedelta(seconds=offset))
                    with mock.patch.object(watch, "datetime", frozen):
                        self.assertIs(watch.observation_link_fresh(row), expected,
                                      self.msg(f"свежесть при возрасте {offset} с"))
        frozen, _ = frozen_datetime(random_moment(self.rnd))
        with mock.patch.object(watch, "datetime", frozen):
            for empty in (None, ""):
                with self.subTest(last_seen_at=empty, seed=self.seed):
                    self.assertIs(watch.observation_link_fresh({"last_seen_at": empty}),
                                  False, self.msg(f"свежая при {empty!r}"))

    def test_ac3_single_last_seen_at_parse_inside_observation_age(self):
        """Линтер: разбор `last_seen_at` через `fromisoformat` в `orchestrator/` — один.

        Обходит AST всех модулей `orchestrator/` и собирает вызовы
        `<имя>.fromisoformat(...)` со строковой константой `"last_seen_at"`
        в поддереве аргумента: такой вызов ровно один и лежит внутри
        функции `observation_age` модуля `orchestrator/watch.py`. Сам
        детектор сверяется на синтетическом тексте с копией разбора в
        случайно названной функции — он обязан её найти.

        Ловит мутацию: в `artel.py` или `watch.py` возвращена своя копия разбора `last_seen_at`.
        """
        name = "copy_" + "".join(self.rnd.choice("abcdefgh") for _ in range(6))
        sample = (f"def {name}(row):\n"
                  "    return datetime.fromisoformat(row['last_seen_at'] or '')\n")
        self.assertEqual(fromisoformat_on_last_seen(ast.parse(sample)), [name],
                         self.msg("детектор не нашёл копию разбора в образце"))
        package = Path(orchestrator.__file__).resolve().parent
        hits = []
        for path in sorted(package.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rel = path.relative_to(package.parent).as_posix()
            hits.extend((rel, owner) for owner in fromisoformat_on_last_seen(tree))
        self.assertEqual(hits, [("orchestrator/watch.py", "observation_age")],
                         self.msg(f"разбор last_seen_at найден в: {hits}"))

    def test_ac6_process_state_without_pid_by_link_freshness(self):
        """Наблюдение без pid: `unstarted` при пустой связи, `fresh`/`stale` по порогу.

        `observation_process_state` со строкой `pid=None` при подменённом
        `watch.datetime` даёт `"unstarted"` для `last_seen_at` `None` и `""`,
        `"fresh"` при возрасте ровно `OBSERVATION_STALE_SECONDS` и `"stale"`
        при возрасте порог + 1 с.

        Ловит мутацию: ветка `pid is None` сравнивает возраст строго (`<`) —
        ровно порог даёт `"stale"`; либо считает возраст на настоящем
        времени — давний `last_seen_at` на пороге даёт `"stale"`; либо
        пустая строка уходит в разбор и падает `ValueError`.
        """
        threshold = config.OBSERVATION_STALE_SECONDS
        host = self.rnd.choice(["host-a", "host-b", None])
        for empty in (None, ""):
            frozen, _ = frozen_datetime(random_moment(self.rnd))
            with self.subTest(last_seen_at=empty, seed=self.seed):
                with mock.patch.object(watch, "datetime", frozen):
                    state = watch.observation_process_state(
                        {"pid": None, "hostname": host, "last_seen_at": empty})
                self.assertEqual(state, "unstarted", self.msg(f"при {empty!r}"))
        for _ in range(3):
            seen = random_moment(self.rnd)
            row = {"pid": None, "hostname": host, "last_seen_at": seen.isoformat()}
            for offset, expected in ((threshold, "fresh"), (threshold + 1, "stale")):
                with self.subTest(seen=row["last_seen_at"], offset=offset, seed=self.seed):
                    frozen, _ = frozen_datetime(seen + timedelta(seconds=offset))
                    with mock.patch.object(watch, "datetime", frozen):
                        state = watch.observation_process_state(row)
                    self.assertEqual(state, expected,
                                     self.msg(f"состояние при возрасте {offset} с"))


class ObservationFreshnessCliTest(TaskSeededTmpRootTest):
    """Связка «команда CLI — таблица `observations` — блок свежести»."""

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.seed = new_seed()
        self.rnd = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def cli(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]):
            return capture(artel.main)

    def register(self) -> str:
        out = self.cli("observe", "register", "--tasks", self.TASK)
        return json.loads(out)["id"]

    def set_seen(self, observation_id: str, value) -> None:
        conn = store.db()
        with conn:
            conn.execute("UPDATE observations SET last_seen_at=? WHERE id=?",
                         (value, observation_id))

    def seen_now(self, observation_id: str) -> datetime:
        """`last_seen_at` = настоящее время машины (с долями секунды или без)."""
        seen = datetime.now(timezone.utc)
        if self.rnd.random() < 0.5:
            seen = seen.replace(microsecond=0)
        self.set_seen(observation_id, seen.isoformat())
        return seen

    def launch(self, observation_id: str, now: datetime):
        """`run <id> --observation <ID>` при «сейчас» `now` подменённого
        `watch.datetime`: (текст отказа или None, вызовы `now`, вызван ли Popen)."""
        frozen, calls = frozen_datetime(now)
        pid = self.rnd.randrange(10_000, 4_000_000)
        with mock.patch.object(artel.subprocess, "Popen",
                               return_value=mock.Mock(pid=pid)) as popen, \
                mock.patch.object(watch, "datetime", frozen):
            try:
                self.cli("run", self.TASK, "--observation", observation_id)
                code = None
            except SystemExit as exc:
                code = str(exc.code)
        return code, calls, popen.called

    def test_ac4_launch_freshness_gate_uses_watch_age_once(self):
        """Запуск: пустая связь — «связи ещё нет», порог + 1 с — «устарела на N с», порог — проходит.

        Наблюдение заведено `observe register`, запуск — `run <id>
        --observation <ID>`. При `last_seen_at` `None` и `""` отказ
        содержит «связи с watch ещё нет» (без `ValueError`). При
        `last_seen_at`, равном настоящему времени машины, подменённый
        `watch.datetime` отдаёт «сейчас» = `last_seen_at` + порог + 1 с —
        отказ «связь устарела на {порог+1} с (порог {порог} с)»; «сейчас» =
        `last_seen_at` + порог — отказа «устарела» нет, Popen вызван. За
        каждый запуск, дошедший до блока свежести, `watch.datetime.now`
        вызван ровно один раз.

        Ловит мутацию: блок свежести `artel.py` оставлен копией разбора на
        собственном `datetime.now` модуля `artel` — при подменённом
        `watch.datetime` порог + 1 с проходит без отказа, а счётчик `now`
        равен нулю; либо после `watch.observation_age` блок свежести второй
        раз берёт текущее время — счётчик `now` равен двум; либо проверка
        оставлена `is None` — пустая строка роняет `ValueError`.
        """
        threshold = config.OBSERVATION_STALE_SECONDS
        observation_id = self.register()
        for empty in (None, ""):
            with self.subTest(last_seen_at=empty, seed=self.seed):
                self.set_seen(observation_id, empty)
                code, _, spawned = self.launch(
                    observation_id, random_moment(self.rnd))
                self.assertIsNotNone(code, self.msg(f"запуск при {empty!r} не отказал"))
                self.assertIn("связи с watch ещё нет", code,
                              self.msg(f"отказ при {empty!r}: {code}"))
                self.assertFalse(spawned, self.msg("Popen вызван при пустой связи"))
        with self.subTest(case="порог + 1 с", seed=self.seed):
            seen = self.seen_now(observation_id)
            code, calls, spawned = self.launch(
                observation_id, seen + timedelta(seconds=threshold + 1))
            self.assertIsNotNone(code, self.msg("связь старше порога не отказала"))
            self.assertIn("связь устарела", code, self.msg(f"отказ: {code}"))
            self.assertIn(f"устарела на {threshold + 1} с", code, self.msg(f"отказ: {code}"))
            self.assertIn(f"(порог {threshold} с)", code, self.msg(f"отказ: {code}"))
            self.assertFalse(spawned, self.msg("Popen вызван при устаревшей связи"))
            self.assertEqual(len(calls), 1, self.msg(f"вызовов now: {len(calls)}"))
        with self.subTest(case="ровно порог", seed=self.seed):
            seen = self.seen_now(observation_id)
            code, calls, spawned = self.launch(
                observation_id, seen + timedelta(seconds=threshold))
            self.assertFalse(code is not None and "устарела" in code,
                             self.msg(f"отказ по свежести на пороге: {code}"))
            self.assertIsNone(code, self.msg(f"запуск на пороге отказал: {code}"))
            self.assertTrue(spawned, self.msg("Popen не вызван на пороге"))
            self.assertEqual(len(calls), 1, self.msg(f"вызовов now: {len(calls)}"))

    def test_ac5_show_fresh_flag_follows_watch_link_freshness(self):
        """`observe show --json`: поле `fresh` — `False` у пустой связи и неактивного, иначе по порогу `watch`.

        У активного наблюдения с `last_seen_at` `None` и `""` поле `fresh`
        ложно (без `ValueError`). При `last_seen_at`, равном настоящему
        времени машины, подменённый `watch.datetime` с «сейчас» =
        `last_seen_at` + порог + 1 с даёт `False`, с «сейчас» =
        `last_seen_at` + порог — `True`. После `observe stop` (состояние не
        `active`) при «сейчас» = `last_seen_at` поле ложно.

        Ловит мутацию: `_observation_fresh` оставлена копией разбора на
        собственном `datetime.now` модуля `artel` — при подменённом
        `watch.datetime` порог + 1 с даёт `True`; либо пустая строка уходит
        в разбор и `observe show` падает `ValueError`; либо снята проверка
        `state != "active"` — остановленное наблюдение со свежей связью
        показано свежим.
        """
        threshold = config.OBSERVATION_STALE_SECONDS
        observation_id = self.register()

        def shown_fresh(now: datetime):
            frozen, _ = frozen_datetime(now)
            with mock.patch.object(watch, "datetime", frozen):
                return json.loads(self.cli("observe", "show", observation_id,
                                           "--json"))["fresh"]

        for empty in (None, ""):
            with self.subTest(last_seen_at=empty, seed=self.seed):
                self.set_seen(observation_id, empty)
                self.assertIs(shown_fresh(random_moment(self.rnd)), False,
                              self.msg(f"свежая при {empty!r}"))
        for offset, expected in ((threshold + 1, False), (threshold, True)):
            with self.subTest(offset=offset, seed=self.seed):
                seen = self.seen_now(observation_id)
                self.assertIs(shown_fresh(seen + timedelta(seconds=offset)), expected,
                              self.msg(f"fresh при возрасте {offset} с"))
        self.cli("observe", "stop", observation_id)
        with self.subTest(state="stopped", seed=self.seed):
            seen = self.seen_now(observation_id)
            self.assertIs(shown_fresh(seen), False,
                          self.msg("остановленное наблюдение показано свежим"))


if __name__ == "__main__":
    unittest.main()
