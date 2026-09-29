"""AC-14..AC-17 — сверка перечня долгоживущих файлов с головой кодовой
ветки на рубежах Р4: `in_dev -> verifying`, `verifying -> review`,
`review -> acceptance`, `acceptance -> merge_gate` командой `approve` и
гейт мержа после `_sync_main_or_wait`. Изменённый или удалённый после
лока файл, как и сбой git при сверке, дают отказ; отказ называет путь и
несёт подсказку «код чинится под тест; правка теста — `amend-tests` по
решению Оператора».

Перечень и лок пишет сама реализация (настоящий выход из
`tests_writing`); после лока сценарий правит кодовую ветку коммитом, как
это сделал бы разработчик. Гейты рубежей, не относящиеся к предмету,
подменены проходом (см. `_sandbox.py`); контрольный сценарий без
расхождения проходит все пять рубежей подряд.

Группа: разовый
Красен до реализации: сверки перечня нет ни на одном рубеже (и перечня нет) — изменённый, удалённый долгоживущий файл и недоступная голова кодовой ветки проходят каждый переход.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class ManifestCheckTest(_sandbox.LongLivedSandbox):

    def setUp(self):
        super().setUp()
        self.rel = self.ll_path("alpha")
        # Строка с CRLF: байты файла на голове отличаются от текста,
        # прочитанного с перекодировкой концов строк.
        self.lock_with({self.rel: _sandbox.long_lived_source()
                        + "# строка с CRLF\r\n"})

    def change_after_lock(self) -> None:
        self.wt_commit({self.rel: _sandbox.long_lived_source(
            tag="правка разработчика после лока")},
            message="разработчик правит долгоживущий файл")

    def assert_named_with_hint(self, text: str, why: str) -> None:
        self.assertIn(self.rel, text, f"{why}: отказ не называет путь: {text}")
        self.assertRegex(text, _sandbox.HINT_CODE,
                         f"{why}: нет подсказки «код чинится под тест»: {text}")
        self.assertIn(_sandbox.HINT_AMEND, text,
                      f"{why}: нет подсказки про amend-tests: {text}")

    def boundaries(self):
        """(имя рубежа, вызов, состояние до, признак отказа по итогу)."""
        return (
            ("in_dev -> verifying", self.advance_in_dev, "in_dev"),
            ("verifying -> review", self.advance_verifying, "verifying"),
            ("review -> acceptance", self.advance_review, "review"),
            ("acceptance -> merge_gate (approve)", self.approve_acceptance,
             "acceptance"),
        )

    def test_ac14_changed_file_refused_at_in_dev_with_hint(self):
        """Долгоживущий файл изменён в кодовой ветке после лока:
        `in_dev -> verifying` отклонён, отказ называет путь и несёт
        подсказку «код чинится под тест; правка теста — amend-tests».

        Ловит мутацию: сверка сравнивает только НАЛИЧИЕ путей перечня в
        дереве головы, не суммы — изменённый файл проходит.
        """
        self.change_after_lock()
        out, entries = self.advance_in_dev()
        self.assertEqual(self.state(), "in_dev",
                         f"изменённый файл прошёл in_dev -> verifying: {entries!r}")
        self.assert_named_with_hint("\n".join(entries + [out]), "in_dev")

    def test_ac14_changed_file_refused_at_merge_gate_with_hint(self):
        """Тот же изменённый файл на гейте мержа: тело гейта после
        `_sync_main_or_wait` останавливается (`("stopped",)`) раньше
        ожидания CI, отказ называет путь и несёт подсказку.

        Ловит мутацию: сверка стоит только на переходах `cmd_advance`, а
        тело гейта мержа её не зовёт — тело доходит до ожидания CI
        (`("wait", …)`).
        """
        self.change_after_lock()
        outcome, out, entries = self.merge_gate_body()
        self.assertEqual(outcome, ("stopped",),
                         f"гейт мержа не отказал: {outcome!r} {entries!r}")
        self.assert_named_with_hint("\n".join(entries + [out]), "merge_gate")

    def test_ac15_deleted_file_refused_naming_path(self):
        """Долгоживущий файл перечня удалён из кодовой ветки после лока:
        `in_dev -> verifying` отклонён, отказ называет путь.

        Ловит мутацию: сверка перебирает файлы `tests/` головы с префиксом
        задачи и сверяет их с перечнем (а не пути перечня с головой) —
        исчезнувший файл никто не ищет, переход проходит.
        """
        self.wt_commit(remove=[self.rel], message="разработчик удалил файл")
        out, entries = self.advance_in_dev()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "in_dev",
                         f"удалённый файл прошёл in_dev -> verifying: {text}")
        self.assertIn(self.rel, text, "отказ не называет удалённый путь")

    def test_ac16_mismatch_refused_at_every_boundary(self):
        """Расхождение (файл изменён после лока) предъявлено каждому из
        пяти рубежей Р4: четыре перехода оставляют задачу в исходном
        состоянии, тело гейта мержа — `("stopped",)`; каждый отказ
        называет путь.

        Ловит мутацию: узел сверки подключён к `in_dev -> verifying` и
        гейту мержа, но не к `verifying -> review`/`review -> acceptance`/
        `approve` из `acceptance` — задача с правленым тестом доходит до
        приёмки Оператора.
        """
        self.change_after_lock()
        for name, call, before in self.boundaries():
            with self.subTest(boundary=name):
                out, entries = call()
                text = "\n".join(entries + [out])
                self.assertEqual(self.state(), before,
                                 f"{name}: расхождение не отклонило переход: {text}")
                self.assertIn(self.rel, text, f"{name}: отказ не называет путь")
        with self.subTest(boundary="гейт мержа после _sync_main_or_wait"):
            outcome, out, entries = self.merge_gate_body()
            self.assertEqual(outcome, ("stopped",), f"{outcome!r} {entries!r}")
            self.assertIn(self.rel, "\n".join(entries + [out]))

    def test_ac16_matching_manifest_passes_every_boundary(self):
        """Контроль: без расхождения те же пять рубежей проходят подряд —
        `in_dev` → `verifying` → `review` → `acceptance` → `merge_gate`,
        тело гейта мержа доходит до ожидания CI (`("wait", …)`).

        Ловит мутацию: сверка считает SHA-256 от текста, прочитанного
        `git show` с `text=True` (универсальные концы строк), а перечень —
        от байтов: строка с CRLF в файле даёт разные суммы, и совпадающий
        файл отклоняется на первом рубеже.
        """
        for name, call, before in self.boundaries():
            with self.subTest(boundary=name):
                out, entries = call()
                self.assertNotEqual(self.state(), before,
                                    f"{name}: переход без расхождения отклонён: "
                                    f"{entries!r}\n{out}")
        outcome, out, entries = self.merge_gate_body()
        self.assertEqual(outcome[0] if outcome else None, "wait",
                         f"гейт мержа без расхождения остановлен: {entries!r}\n{out}")

    def test_ac17_git_failure_refuses_instead_of_skipping(self):
        """Голова кодовой ветки не читается (ref ветки задачи удалён —
        `git rev-parse`/`git show` по ветке отвечают ошибкой): и
        `in_dev -> verifying`, и тело гейта мержа отказывают, а не
        пропускают сверку.

        Ловит мутацию: сбой чтения головы трактуется как «перечень
        сверять не с чем» (`return None`) — переход проходит в
        `verifying`, гейт мержа доходит до ожидания CI.
        """
        self.git("update-ref", "-d", f"refs/heads/{self.branch}")
        with self.subTest(boundary="in_dev -> verifying"):
            out, entries = self.advance_in_dev()
            self.assertEqual(self.state(), "in_dev",
                             f"сбой git пропущен: {entries!r}\n{out}")
        with self.subTest(boundary="гейт мержа"):
            outcome, out, entries = self.merge_gate_body()
            self.assertEqual(outcome, ("stopped",),
                             f"сбой git пропущен гейтом мержа: {outcome!r} "
                             f"{entries!r}\n{out}")


if __name__ == "__main__":
    unittest.main()
