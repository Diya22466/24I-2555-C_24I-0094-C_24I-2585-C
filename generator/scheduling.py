"""Rescue windows (module C data) and alarms (module D data)."""

# Per case study: window duration range (minutes) and how start times are spread.
WINDOW_PROFILE = {
    1: ((30, 240), "spread"),   # Delta: boats run all day
    2: ((20, 180), "bursts"),   # Earthquake: work comes after each aftershock
    3: ((5, 60), "surge"),      # Cyclone: short, overlapping windows around each surge
    4: ((10, 120), "spread"),   # Urban: many short jobs across the day
    5: ((60, 480), "spread"),   # Landslide: long clearing jobs
    6: ((30, 300), "spread"),   # Outbreak: shifts in the camp
}

# Weights of priorities 1..10 per case study.
PRIORITY_WEIGHTS = {
    1: [5, 5, 6, 6, 5, 5, 4, 3, 2, 2],
    2: [1, 1, 1, 2, 3, 5, 7, 8, 7, 6],   # Earthquake: urgent calls (mean about 7.2)
    3: [4, 4, 5, 5, 5, 5, 4, 4, 3, 3],
    4: [6, 6, 6, 5, 5, 4, 3, 3, 2, 2],
    5: [4, 4, 4, 5, 5, 5, 4, 3, 3, 3],
    6: [3, 3, 4, 5, 5, 5, 5, 4, 3, 3],
}


def overlap_average_ok(windows):
    """Cyclone rule: on average every window overlaps at least 2 others."""
    total = 0
    for a in windows:
        for b in windows:
            if a is not b and a["start"] < b["finish"] and b["start"] < a["finish"]:
                total += 1
    return total >= 2 * len(windows)


def random_window(rng, duration_range, mode, peaks):
    duration = rng.randint(*duration_range)
    if mode == "spread":
        start = rng.randint(0, 1440 - duration)
    else:
        spread = 40 if mode == "surge" else 120
        start = rng.choice(peaks) + rng.randint(-spread, spread)
        start = max(0, min(1440 - duration, start))
    return start, start + duration


def make_windows(rng, n, scenario):
    duration_range, mode = WINDOW_PROFILE[scenario]
    while True:
        peaks = [rng.randint(100, 1300) for i in range(max(1, n // 40))]
        windows = []
        for window_id in range(1, n + 1):
            start, finish = random_window(rng, duration_range, mode, peaks)
            windows.append({"window_id": window_id, "start": start, "finish": finish,
                            "value": rng.randint(1, 100)})

        # Plant touching pairs: window j starts exactly when window i finishes.
        n_pairs = max(2, n // 100)
        chosen = rng.sample(range(n), 2 * n_pairs)
        for p in range(n_pairs):
            first = windows[chosen[2 * p]]
            second = windows[chosen[2 * p + 1]]
            if first["finish"] > 1435:  # keep room for a 5-minute window after it
                first["start"] -= 10
                first["finish"] -= 10
            duration = second["finish"] - second["start"]
            second["start"] = first["finish"]
            second["finish"] = min(1440, second["start"] + duration)
            if second["finish"] - second["start"] < 5:
                second["finish"] = second["start"] + 5

        if scenario != 3 or overlap_average_ok(windows):
            return windows


def make_incidents(rng, n, tier, scenario):
    # Alarms per tick = n / (last tick + 1).
    if tier == "S":
        rate = rng.uniform(0.8, 2.0)
    elif scenario == 4:
        rate = rng.uniform(1.55, 1.75)  # Urban: calls arrive faster (>= 1.5 per tick)
    else:
        rate = rng.uniform(1.25, 1.75)
    n_ticks = max(1, round(n / rate))
    if tier != "S":
        # Integer form of: low <= n / n_ticks <= 1.8 (low = 1.5 Urban, else 1.2).
        low_times_10 = 15 if scenario == 4 else 12
        while 10 * n > 18 * n_ticks:
            n_ticks += 1
        while 10 * n < low_times_10 * n_ticks:
            n_ticks -= 1
    last_tick = n_ticks - 1

    while True:
        ticks = []
        if scenario == 2:
            # Earthquake: bursts of calls after each aftershock.
            shocks = [rng.randint(0, last_tick) for i in range(max(2, n // 60))]
            for i in range(n):
                if rng.random() < 0.6:
                    ticks.append(min(last_tick, rng.choice(shocks) + rng.randint(0, 3)))
                else:
                    ticks.append(rng.randint(0, last_tick))
        else:
            for i in range(n):
                ticks.append(rng.randint(0, last_tick))
        ticks.sort()
        ticks[0] = 0
        ticks[-1] = last_tick

        priorities = rng.choices(range(1, 11), weights=PRIORITY_WEIGHTS[scenario], k=n)
        if tier != "S":
            # At least 6 distinct priorities, including 1.
            for p in [1, 2, 3, 4, 5, 6]:
                if p not in priorities:
                    priorities[rng.randint(0, n - 1)] = p
            if 1 not in priorities or len(set(priorities)) < 6:
                continue
        if scenario == 2 and sum(priorities) < 6 * n:
            continue
        break

    incidents = []
    for i in range(n):
        incidents.append({"alarm_id": i + 1, "tick": ticks[i], "priority": priorities[i]})
    return incidents
