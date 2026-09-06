"""AC-8 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): в той же песочнице,
но без ref `origin/main` (репозиторий без remote) — поведение всех трёх
потребителей (гейт зон, гейт ёмкости, полный diff ревью-пакета) прежнее:
сравнение с локальным `config.MAIN_BRANCH`.

`MergeBaseFixture` (`_sandbox.py`, `CREATE_ORIGIN_REF = False`) строит
ТУ ЖЕ git-историю, что и `test_ac7_origin_ahead_sandbox.py` (ветка
задачи мержит тот же коммит с `docs/roadmap.md`), но не заводит
`refs/remotes/origin/main` вовсе — merge-base с локальным `config.
MAIN_BRANCH` (commit0) остаётся старой точкой расхождения, и файл,
принесённый мержем, обязан выглядеть частью диффа задачи — ровно
поведение ДО этой задачи (требование не «исправить» этот случай, а не
регрессировать его: без ref фикс объективно неприменим, фолбэк —
единственный корректный выбор SPEC).

Зелёный с рождения: сегодняшний код без всякого `gitcmd.diff_base`
сравнивает ветку с `config.MAIN_BRANCH` безусловно — ровно то поведение,
которое эта планка фиксирует как «прежнее» для случая без ref. После
реализации AC-1..AC-3 тест обязан остаться зелёным ровно потому, что
фолбэк-ветка `diff_base` (ref отсутствует) возвращает тот же
`config.MAIN_BRANCH`, что и раньше.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import fsm_advance, review  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MergeBaseFixture  # noqa: E402


class ZonesGateStillRefusesWithoutOriginRefTest(MergeBaseFixture):

    CREATE_ORIGIN_REF = False

    def test_ac8_zones_gate_still_refuses_on_the_merged_in_file(self):
        """Ловит мутацию: фолбэк на `config.MAIN_BRANCH` при отсутствии
        `refs/remotes/origin/main` убран/сломан (например, функция
        возвращает `None` вместо merge-base с локальным main) — гейт
        либо перестал бы видеть файл вовсе, либо отказал бы «git не
        ответил» вместо содержательного «вне зон», ловится по тексту
        причины ниже."""
        refused = fsm_advance._zones_gate_refuses(
            self.conn, self.TASK_ID, self.t, self.BRANCH, "PLAN\n")

        self.assertTrue(
            refused, "без ref origin/main фикс неприменим — прежнее "
            "поведение обязано сохраниться (файл вне зон отказывает)")
        details = "\n".join(self.journal_details())
        self.assertIn(self.OUT_OF_ZONE_REL, details)


class CapacityGateStillCountsTheFileWithoutOriginRefTest(MergeBaseFixture):

    CREATE_ORIGIN_REF = False

    def test_ac8_capacity_gate_still_counts_the_merged_in_file_bytes(self):
        """Ловит мутацию: та же поломка фолбэка — гейт ёмкости перестал
        бы видеть 300 000 байт файла и пропустил бы переход, хотя без
        ref origin/main это заведомо не должно измениться относительно
        поведения до задачи."""
        refused = fsm_advance._capacity_gate_refuses(
            self.conn, self.TASK_ID, self.t, "in_dev")

        self.assertTrue(
            refused, "без ref origin/main фикс неприменим — прежнее "
            "поведение обязано сохраниться (300 000 байт выше потолка)")


class ReviewPackageFullDiffStillContainsTheFileWithoutOriginRefTest(
        MergeBaseFixture):

    CREATE_ORIGIN_REF = False

    def test_ac8_full_review_diff_still_contains_the_merged_in_file(self):
        """Ловит мутацию: та же поломка фолбэка — полный diff пакета
        перестал бы показывать ревьюверу файл, реально попавший в ветку
        задачи, хотя без ref origin/main прежнее поведение (файл виден)
        обязано сохраниться."""
        package = review.review_package(
            self.conn, self.TASK_ID, "Тест merge-base", self.BRANCH)

        self.assertIn(self.OUT_OF_ZONE_REL, package["text"])


if __name__ == "__main__":
    unittest.main()
