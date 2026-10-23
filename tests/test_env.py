"""Environment rules: no future leaks, schedule can't be gamed, limits enforced, scores repeatable."""

import json
from pathlib import Path

from dosesim.env import DoseEnv

TASKS = Path(__file__).resolve().parent.parent / "tasks" / "vanc"


def load(tid):
    return DoseEnv.from_file(TASKS / f"dose-vanc-{tid}.json")


def test_labs_never_show_future_creatinine():
    env = load("0002")  # creatinine rises each day
    assert env.get_labs(1)["scr_mg_dl_by_day"] == env.task["patient"]["scr_by_day"][:2]


def test_level_hidden_until_after_draw():
    env = load("0006")  # levels drawn at 23.5 h and 47.5 h
    env.submit_dose(0, 1000, 12, "")
    assert env.get_labs(0)["vancomycin_levels"] == []      # drawn later tonight
    env.submit_dose(1, 1000, 12, "")
    assert len(env.get_labs(1)["vancomycin_levels"]) == 1  # 23.5 h level now visible


def test_level_reflects_hidden_patient_not_textbook():
    # 0006 hides a fast clearer: measured trough should be below the textbook prediction
    env = load("0006")
    env.submit_dose(0, 1000, 12, "")
    env.submit_dose(1, 1000, 12, "")
    measured = env.get_labs(1)["vancomycin_levels"][0]["mg_per_l"]
    textbook = DoseEnv(json.loads(json.dumps(env.task)))
    textbook.task["hidden"]["eta"] = {}
    textbook.task["hidden"]["level_draws"][0].update(prop_error=0.0, add_error=0.0)
    textbook.submit_dose(0, 1000, 12, "")
    textbook.submit_dose(1, 1000, 12, "")
    assert measured < textbook.get_labs(1)["vancomycin_levels"][0]["mg_per_l"]


def test_changing_regimen_cannot_add_hidden_doses():
    # Switching q24 -> q24 with a new amount must NOT add a dose at the start of the day
    env = load("0001")
    env.submit_dose(0, 1000, 24, "")
    env.submit_dose(1, 1250, 24, "")
    times = [d.time_h for d in env._doses()]
    assert times[:2] == [0.0, 24.0]  # day 1 dose at 24 h (0 + 24), not an extra one


def test_shorter_interval_waits_for_its_own_gap():
    env = load("0001")
    env.submit_dose(0, 2000, 24, "")   # dose at 0 h
    env.submit_dose(1, 1000, 8, "")    # change on day 1: next dose at max(24, 0 + 8) = 24
    times = [d.time_h for d in env._doses()][:4]
    assert times == [0.0, 24.0, 32.0, 40.0]


def test_loading_dose_cap():
    env = load("0009")  # 45 kg -> cap = 35 x 45 = 1575 mg
    assert "error" in env.submit_dose(0, 750, 24, "", loading_dose_mg=3000)
    assert env.submit_dose(0, 750, 24, "", loading_dose_mg=1500)["ok"]


def test_loading_only_day0_and_days_in_order():
    env = load("0001")
    assert "error" in env.submit_dose(1, 1000, 12, "")            # skipped day 0
    env.submit_dose(0, 1000, 12, "")
    assert "error" in env.submit_dose(1, 1000, 12, "", loading_dose_mg=1000)


def test_invalid_interval_rejected():
    env = load("0001")
    assert "error" in env.submit_dose(0, 1000, 48, "")


def test_grade_is_deterministic_and_bounded():
    def play():
        env = load("0010")
        for d in range(env.n_days):
            env.submit_dose(d, 750, 24, "creatinine rising so I reduce; trough level checked")
        return env.grade()
    a, b = play(), play()
    assert a == b
    assert 0.0 <= a["reward"] <= 1.0


def test_unfinished_episode_scores_zero():
    env = load("0001")
    env.submit_dose(0, 1000, 12, "")
    assert env.grade()["reward"] == 0.0


def test_simulate_tool_uses_population_model_only():
    # The what-if tool must not leak the hidden patient: same answer with or without hidden effects
    env = load("0006")
    a = env.simulate(1000, 12, 3)
    env.task["hidden"]["eta"] = {}
    assert env.simulate(1000, 12, 3) == a
