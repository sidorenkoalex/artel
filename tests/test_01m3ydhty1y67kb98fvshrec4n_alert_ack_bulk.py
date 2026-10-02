"""Массовая форма `alert-ack --source <источник> --grep <подстрока> "<решение>" [--yes]`.

Команда пульта отбирает открытые алерты с полем `source`, равным
источнику, и подстрокой в тексте (буквально: без шаблонов LIKE и без
регулярных выражений). Без `--yes` — только перечень отобранных `incident`
(число, номера, диапазон дат, первые строки), БД не меняется; с `--yes` —
каждый отобранный `incident` подтверждается от `operator` тем же текстом
решения, что дал бы одиночный `alert-ack`; `trigger`/`threshold` массово не
подтверждаются, и вывод называет их число как пропущенные. Пустые или
отсутствующие источник, подстрока, решение — отказ без изменений; одиночная
форма работает как прежде; из-под роли массовая форма отказывает так же,
как одиночная.

Команда вызывается через диспетчер `artel.main` с подменённым `sys.argv`
в окружении Оператора (`HOME` чужой, без `ARTEL_ROLE`) — тест не зависит от
того, из какого окружения его запустили. Номера, даты, источник, подстрока
и состав алертов — случайные; зерно печатается и входит в текст провала.

Группа: долгоживущий
Красен до реализации: диспетчер передаёт `alert-ack --source …` одиночной форме, она отказывает «не номер алерта» — предпросмотра, массового подтверждения и счёта пропущенных нет (AC-5, AC-6, AC-7 падают).
"""
import contextlib
import io
import os
import random
import re
import sys
import unittest
from unittest import mock

from orchestrator import artel, config, store
from tests.sandbox import SchemaConnTmpRootTest

SOURCES = ("github_adapter", "doctor", "runner")
NEEDLES = ("No commits between", "push не удался", "таймаут gh pr view")
WORDS = ("сбой", "форджа", "ветка", "черновик", "отказ", "запрос", "слияние",
         "повтор", "журнал", "пульт")


def new_seed() -> int:
    seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {seed}")
    return seed


def has_token(text: str, number: int) -> bool:
    return re.search(rf"(?<!\d){number}(?!\d)", text) is not None


class AlertAckBulkSandbox(SchemaConnTmpRootTest):
    """БД пульта во временном каталоге и случайный набор алертов."""

    def setUp(self):
        super().setUp()
        self.seed = new_seed()
        self.rng = random.Random(self.seed)
        self.used_ids: set = set()

    # ------------------------------------------------------------ окружение

    def operator_env(self) -> dict:
        return {"HOME": f"/tmp/operator_{self.rng.randrange(1 << 30):x}",
                "PATH": os.environ.get("PATH", "")}

    def dispatch(self, argv, env=None) -> tuple:
        """(код выхода или None, вывод stdout+stderr) вызова `artel.py`."""
        out, err = io.StringIO(), io.StringIO()
        code = None
        with mock.patch.dict(os.environ, env or self.operator_env(), clear=True), \
                mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def assert_refused(self, code, output, what: str) -> None:
        self.assertNotIn(code, (None, 0),
                         f"зерно: {self.seed}; {what}: нет отказа; вывод: {output}")

    def assert_succeeded(self, code, output, what: str) -> None:
        self.assertIn(code, (None, 0),
                      f"зерно: {self.seed}; {what}: отказ {code!r}; вывод: {output}")

    # ------------------------------------------------------------ фикстуры

    def new_id(self) -> int:
        while True:
            alert_id = self.rng.randrange(3000, 9999)
            if alert_id not in self.used_ids:
                self.used_ids.add(alert_id)
                return alert_id

    def words(self, k: int = 2) -> str:
        return " ".join(self.rng.choice(WORDS) for _ in range(k))

    def add_alert(self, kind: str, source: str, first_line: str,
                  day: int | None = None, acked: bool = False) -> int:
        alert_id = self.new_id()
        day = day if day is not None else self.rng.randint(1, 27)
        ts = f"2026-09-{day:02d} 10:00:00Z"
        message = f"{first_line}\nподробности: {self.words(3)}"
        self.conn.execute(
            "INSERT INTO alerts (id, target, kind, source, message, ts) "
            "VALUES (?,?,?,?,?,?)",
            (alert_id, config.DEFAULT_TARGET, kind, source, message, ts))
        self.conn.commit()
        if acked:
            store.ack_alert(self.conn, alert_id, "doctor", "прежнее решение")
        return alert_id

    def scenario(self, *, other_kinds: int = 0) -> dict:
        """Отобранные `incident` и помехи: другой источник с той же
        подстрокой, тот же источник без подстроки, уже подтверждённый
        алерт с подстрокой; `other_kinds` — сколько открытых `trigger`/
        `threshold` с тем же источником и подстрокой."""
        source = self.rng.choice(SOURCES)
        needle = self.rng.choice(NEEDLES)
        other_source = self.rng.choice([s for s in SOURCES if s != source])
        foreign_needle = self.rng.choice([n for n in NEEDLES if n != needle])
        days = self.rng.sample(range(1, 28), self.rng.randint(2, 6))
        selected = {}
        for day in days:
            line = f"{self.words()} {needle} {self.words()}"
            selected[self.add_alert("incident", source, line, day)] = line
        noise = [
            self.add_alert("incident", other_source,
                           f"{self.words()} {needle} {self.words()}"),
            self.add_alert("incident", source,
                           f"{self.words()} {foreign_needle} {self.words()}"),
            self.add_alert("incident", source,
                           f"{self.words()} {needle} {self.words()}", acked=True),
        ]
        skipped = [self.add_alert(self.rng.choice(("trigger", "threshold")),
                                  source, f"{self.words()} {needle}")
                   for _ in range(other_kinds)]
        return {"source": source, "needle": needle, "selected": selected,
                "days": sorted(days), "noise": noise, "skipped": skipped}

    def resolution(self) -> str:
        return f"закрыто: {self.words(3)}"

    # ---------------------------------------------------------- наблюдения

    def snapshot(self) -> dict:
        return {r["id"]: (r["ack_ts"], r["ack_by"], r["ack_resolution"])
                for r in self.conn.execute("SELECT * FROM alerts").fetchall()}

    def row(self, alert_id: int):
        return store.get_alert(self.conn, alert_id)

    def bulk_argv(self, sc: dict, resolution: str, yes: bool) -> list:
        argv = ["alert-ack", "--source", sc["source"], "--grep", sc["needle"],
                resolution]
        return argv + (["--yes"] if yes else [])


class BulkPreviewTest(AlertAckBulkSandbox):

    def test_ac5_preview_lists_selection_and_changes_nothing(self):
        """Без `--yes` — перечень отобранных `incident`, БД не меняется.

        Сценарий: 2–6 открытых `incident` случайного источника с подстрокой
        в первой строке, на разные дни сентября, плюс помехи. Команда без
        `--yes` завершается успешно, вывод несёт их число, номер каждого,
        первую и последнюю дату диапазона и первую строку текста каждого;
        ни один алерт БД не изменился.

        Ловит мутацию: флаг `--yes` не проверяется (или проверяется
        инвертированно) — предпросмотр подтверждает отобранные алерты, у
        них появляется `ack_ts`.
        """
        sc = self.scenario()
        before = self.snapshot()

        code, output = self.dispatch(self.bulk_argv(sc, self.resolution(), False))

        self.assert_succeeded(code, output, "предпросмотр")
        msg = f"зерно: {self.seed}; вывод: {output}"
        self.assertEqual(self.snapshot(), before, msg)
        self.assertTrue(has_token(output, len(sc["selected"])),
                        f"{msg}; нет числа {len(sc['selected'])}")
        for alert_id, line in sc["selected"].items():
            self.assertTrue(has_token(output, alert_id), f"{msg}; нет #{alert_id}")
            self.assertIn(line, output, f"{msg}; нет первой строки #{alert_id}")
        self.assertIn(f"2026-09-{sc['days'][0]:02d}", output, f"{msg}; нет начала")
        self.assertIn(f"2026-09-{sc['days'][-1]:02d}", output, f"{msg}; нет конца")


class BulkConfirmTest(AlertAckBulkSandbox):

    def test_ac6_yes_acks_selected_incidents_like_single_form(self):
        """С `--yes` — все отобранные `incident` подтверждены как одиночной формой.

        Сценарий: контрольный алерт постороннего источника подтверждается
        одиночной `alert-ack <id> "<решение>"`; затем массовая форма с тем
        же решением и `--yes`. Каждый отобранный `incident` получает
        `ack_ts`, `ack_by = operator` и тот же `ack_resolution`, что
        контрольный; помехи (другой источник, текст без подстроки, уже
        подтверждённый) не изменились.

        Ловит мутацию: отбор не сверяет `source` (или игнорирует
        подстроку, или не исключает подтверждённые) — помеха получает
        новый `ack_ts`/`ack_by`, либо уже подтверждённому переписывают
        решение.
        """
        sc = self.scenario()
        resolution = self.resolution()
        control = self.add_alert("incident", "control_source", self.words())
        code, output = self.dispatch(["alert-ack", str(control), resolution])
        self.assert_succeeded(code, output, "одиночная форма")
        single = self.row(control)
        before = self.snapshot()

        code, output = self.dispatch(self.bulk_argv(sc, resolution, True))

        self.assert_succeeded(code, output, "массовая форма --yes")
        msg = f"зерно: {self.seed}; вывод: {output}"
        for alert_id in sc["selected"]:
            row = self.row(alert_id)
            self.assertIsNotNone(row["ack_ts"], f"{msg}; #{alert_id} не подтверждён")
            self.assertEqual(row["ack_by"], "operator", msg)
            self.assertEqual(row["ack_by"], single["ack_by"], msg)
            self.assertEqual(row["ack_resolution"], single["ack_resolution"], msg)
        after = self.snapshot()
        for alert_id in sc["noise"] + [control]:
            self.assertEqual(after[alert_id], before[alert_id],
                             f"{msg}; помеха #{alert_id} изменена")

    def test_ac6_grep_is_literal_not_like_or_regex(self):
        """Подстрока ищется буквально: `%`, `_`, `.`, `.*` — обычные символы.

        Сценарий: для каждой подстроки со спецсимволом (`No%commits`,
        `No_commits`, `No.commits`, `No.*commits`) — открытый `incident`, где
        она стоит буквально, и открытый `incident` с текстом «No commits
        between» того же источника. Массовая форма с `--yes` подтверждает
        первый и не трогает второй.

        Ловит мутацию: отбор собран как `message LIKE '%' || ? || '%'` без
        экранирования (или через `re.search`) — `%`/`_`/`.` совпадают с
        пробелом, и инцидент «No commits between» подтверждается вместе с
        буквальным.
        """
        source = self.rng.choice(SOURCES)
        for needle in ("No%commits", "No_commits", "No.commits", "No.*commits"):
            with self.subTest(grep=needle):
                literal = self.add_alert(
                    "incident", source, f"{self.words()} {needle} between")
                plain = self.add_alert(
                    "incident", source, f"{self.words()} No commits between")
                before = self.snapshot()

                code, output = self.dispatch(
                    ["alert-ack", "--source", source, "--grep", needle,
                     self.resolution(), "--yes"])

                self.assert_succeeded(code, output, f"--grep {needle}")
                msg = f"зерно: {self.seed}; --grep {needle}; вывод: {output}"
                self.assertIsNotNone(self.row(literal)["ack_ts"], msg)
                self.assertEqual(self.row(literal)["ack_by"], "operator", msg)
                self.assertEqual(self.snapshot()[plain], before[plain],
                                 f"{msg}; «No commits between» подтверждён")
                store.ack_alert(self.conn, plain, "doctor", "уборка сценария")

    def test_ac7_trigger_and_threshold_are_skipped_and_counted(self):
        """`trigger`/`threshold` массово не подтверждаются, вывод называет их число.

        Сценарий: к отобранным `incident` добавлены открытые `trigger` и
        `threshold` (2–5 штук, число не совпадает с числом `incident`) того
        же источника с той же подстрокой. После массовой формы с `--yes`
        `incident` подтверждены, а `trigger`/`threshold` остались открытыми;
        в выводе есть строка о пропущенных с их числом.

        Ловит мутацию: отбор не фильтрует по `kind = incident` — открытые
        триггеры и пороги подтверждаются массово без решения по существу, и
        строки о пропущенных в выводе нет.
        """
        n_incidents = None
        while True:
            m = self.rng.randint(2, 5)
            sc = self.scenario(other_kinds=m)
            n_incidents = len(sc["selected"])
            if n_incidents != m:
                break
            self.conn.execute("DELETE FROM alerts")
            self.conn.commit()
            self.used_ids.clear()

        code, output = self.dispatch(self.bulk_argv(sc, self.resolution(), True))

        self.assert_succeeded(code, output, "массовая форма --yes")
        msg = f"зерно: {self.seed}; вывод: {output}"
        for alert_id in sc["selected"]:
            self.assertIsNotNone(self.row(alert_id)["ack_ts"], msg)
        for alert_id in sc["skipped"]:
            self.assertIsNone(self.row(alert_id)["ack_ts"],
                              f"{msg}; {self.row(alert_id)['kind']} #{alert_id} "
                              f"подтверждён массово")
        lines = [line for line in output.splitlines()
                 if "пропущ" in line.lower() and has_token(line, m)]
        self.assertTrue(lines, f"{msg}; нет строки о {m} пропущенных")


class BulkRefusalTest(AlertAckBulkSandbox):

    def test_ac8_missing_or_blank_arguments_are_refused(self):
        """Нет или пусты источник, подстрока или решение — отказ, БД не тронута.

        Сценарий: при наличии подходящих открытых `incident` массовая форма
        с `--yes` вызывается без `--source`, с пустым и пробельным
        источником, так же для `--grep` и для текста решения. Каждый вызов
        завершается ненулевым кодом, ни один алерт не изменился. Затем
        одиночная `alert-ack <id> "<решение>"` подтверждает один из
        отобранных: `ack_by = operator`, решение — данный текст, остальные
        алерты не тронуты.

        Ловит мутацию: пробельные значения не отсекаются (проверка `if not
        value` вместо `if not value.strip()`), либо при пустой подстроке
        отбор идёт по одному источнику — все `incident` источника
        подтверждаются; либо разбор массовой формы перехватывает и
        одиночную — `alert-ack <id> "<решение>"` перестаёт подтверждать.
        """
        sc = self.scenario()
        src, needle, res = sc["source"], sc["needle"], self.resolution()
        variants = []
        for blank in (None, "", "   "):
            source_part = [] if blank is None else ["--source", blank]
            variants.append(("источник", ["alert-ack", *source_part,
                                          "--grep", needle, res, "--yes"]))
            grep_part = [] if blank is None else ["--grep", blank]
            variants.append(("подстрока", ["alert-ack", "--source", src,
                                           *grep_part, res, "--yes"]))
            res_part = [] if blank is None else [blank]
            variants.append(("решение", ["alert-ack", "--source", src,
                                         "--grep", needle, *res_part, "--yes"]))
        self.rng.shuffle(variants)
        before = self.snapshot()
        for what, argv in variants:
            with self.subTest(argv=argv):
                code, output = self.dispatch(argv)
                self.assert_refused(code, output, f"{what}: {argv}")
                self.assertEqual(self.snapshot(), before,
                                 f"зерно: {self.seed}; {argv}: алерты изменены")

        target = self.rng.choice(sorted(sc["selected"]))
        code, output = self.dispatch(["alert-ack", str(target), res])

        self.assert_succeeded(code, output, "одиночная форма")
        row = self.row(target)
        msg = f"зерно: {self.seed}; одиночная форма #{target}"
        self.assertIsNotNone(row["ack_ts"], msg)
        self.assertEqual(row["ack_by"], "operator", msg)
        self.assertEqual(row["ack_resolution"], res, msg)
        after = self.snapshot()
        for alert_id, state in before.items():
            if alert_id != target:
                self.assertEqual(after[alert_id], state, f"{msg}; #{alert_id}")

    def test_ac9_bulk_form_is_refused_under_a_role_like_single_form(self):
        """Из-под роли массовая форма отказывает так же, как одиночная.

        Сценарий: окружение шага роли двумя признаками (маркер
        `ARTEL_ROLE` со случайной ролью при чужом HOME; HOME, равный дому
        роли `config.ROLE_HOME`). В каждом одиночная `alert-ack <id>
        "<решение>"` и массовая форма (с `--yes` и без) завершаются
        ненулевым кодом, текст отказа массовой формы после имени команды
        совпадает с текстом отказа одиночной, ни один алерт не изменился.

        Ловит мутацию: массовую форму разбирают и исполняют до проверки
        признака роли (или вносят её в белый список читающих команд) — шаг
        роли подтверждает инциденты пульта, у отобранных появляется
        `ack_ts`.
        """
        sc = self.scenario()
        res = self.resolution()
        role = f"role_{self.rng.randrange(1 << 30):x}"
        envs = (("маркер", {"HOME": f"/tmp/operator_{self.rng.randrange(1 << 30):x}",
                            config.ARTEL_ROLE_ENV: role,
                            "PATH": os.environ.get("PATH", "")}),
                ("HOME роли", {"HOME": str(config.ROLE_HOME),
                               "PATH": os.environ.get("PATH", "")}))
        before = self.snapshot()
        single_target = self.rng.choice(sorted(sc["selected"]))
        for title, env in envs:
            with self.subTest(role_env=title):
                code, single = self.dispatch(
                    ["alert-ack", str(single_target), res], env)
                self.assert_refused(code, single, f"{title}: одиночная форма")
                single_reason = str(code).split(": ", 1)[-1]
                for yes in (False, True):
                    code, output = self.dispatch(self.bulk_argv(sc, res, yes), env)
                    what = f"{title}: массовая форма, --yes={yes}"
                    self.assert_refused(code, output, what)
                    self.assertEqual(str(code).split(": ", 1)[-1], single_reason,
                                     f"зерно: {self.seed}; {what}: отказ "
                                     f"{code!r} не как у одиночной")
                self.assertEqual(self.snapshot(), before,
                                 f"зерно: {self.seed}; {title}: алерты изменены")


if __name__ == "__main__":
    unittest.main()
