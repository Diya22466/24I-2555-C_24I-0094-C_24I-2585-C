"""Radio log, phrase patterns and report pairs (module E data), including trap 49."""

from config import ALPHABET, PATTERN_LENGTHS

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
COMMON_WORDS = ["SOS", "HQ", "OK", "LOC", "UNIT", "NEED", "ROGER", "OVER", "TEAM"]
STORY_WORDS = {
    1: ["FLOOD", "WATER", "BOAT", "ROOF", "LEVEE", "FOOD", "VILLAGE", "DELTA"],
    2: ["QUAKE", "INJURED", "MEDIC", "RUBBLE", "TOOLS", "AFTERSHOCK", "TRAPPED"],
    3: ["CYCLONE", "SURGE", "PORT", "SHELTER", "WIND", "EVAC", "FISHING"],
    4: ["STREET", "FLASH", "CAR", "METRO", "PUMP", "BLOCK", "HELP"],
    5: ["SLIDE", "HIGHWAY", "GORGE", "CUTOFF", "ROCK", "BRIDGE"],
    6: ["CAMP", "OUTBREAK", "MEDICINE", "WATER", "BEACON", "FEVER", "ISOLATE"],
}


def random_message(rng, scenario):
    words = STORY_WORDS[scenario] + COMMON_WORDS
    parts = []
    for i in range(rng.randint(1, 3)):
        parts.append(rng.choice(words))
    if rng.random() < 0.6:
        parts.append(str(rng.randint(0, 999)))
    return rng.choice("_-").join(parts)


def message_text(rng, scenario, length, beacon=None):
    """Radio-style text of exactly `length` symbols."""
    pieces = []
    total = 0
    while total < length:
        if beacon is not None and rng.random() < 0.4:
            message = beacon * rng.randint(6, 14)  # a beacon repeating itself
        else:
            message = random_message(rng, scenario)
        message += "_"
        pieces.append(message)
        total += len(message)
    return "".join(pieces)[:length]


def make_log(rng, scenario, length):
    beacon = None
    if scenario == 6:
        beacon = rng.choice(LETTERS)
    text = list(message_text(rng, scenario, length, beacon))

    if scenario == 3:
        # Coastal Cyclone: storm noise; the log uses at least 32 of the 38 symbols.
        for i in range(len(text)):
            if rng.random() < 0.12:
                text[i] = rng.choice(ALPHABET)
        while len(set(text)) < 32:
            missing = [s for s in ALPHABET if s not in text]
            text[rng.randint(0, len(text) - 1)] = rng.choice(missing)

    if scenario == 6:
        # Outbreak Camp: the beacon symbol is at least 30% of the log.
        need = (3 * len(text) + 9) // 10 - text.count(beacon)
        if need > 0:
            others = [i for i in range(len(text)) if text[i] != beacon]
            for i in rng.sample(others, need):
                text[i] = beacon
    return "".join(text)


def count_occurrences(text, pattern):
    """Occurrences of pattern in text, overlaps included."""
    count = 0
    pos = text.find(pattern)
    while pos != -1:
        count += 1
        pos = text.find(pattern, pos + 1)
    return count


def random_string(rng, length):
    return "".join(rng.choice(ALPHABET) for i in range(length))


def make_patterns(rng, log):
    """Six patterns of lengths 2, 4, 8, 12, 20, 40.

    Patterns 0 and 1 are cut from the log (they occur), pattern 5 is random and
    checked to be absent, patterns 2-4 are a random mix (cut, near-miss, absent).
    """
    patterns = []
    for pattern_no in range(6):
        length = PATTERN_LENGTHS[pattern_no]
        if pattern_no <= 1:
            kind = "inside"
        elif pattern_no == 5:
            kind = "absent"
        else:
            kind = rng.choice(["inside", "near", "absent"])

        if kind == "absent":
            pattern = random_string(rng, length)
            while count_occurrences(log, pattern) > 0:
                pattern = random_string(rng, length)
        else:
            start = rng.randint(0, len(log) - length)
            pattern = log[start:start + length]
            if kind == "near":
                last = rng.choice([s for s in ALPHABET if s != pattern[-1]])
                pattern = pattern[:-1] + last
        patterns.append({"pattern_no": pattern_no, "pattern": pattern,
                         "count": count_occurrences(log, pattern)})
    return patterns


def split_parts(rng, log, tier):
    """Cut the log into cells of at most 10,000 symbols (part 1, 2, ...)."""
    parts = []
    pos = 0
    while pos < len(log):
        if tier == "S":
            size = rng.randint(100, 300)
        else:
            size = rng.randint(5000, 10000)
        parts.append({"part": len(parts) + 1, "text": log[pos:pos + size]})
        pos += size
    return parts


def make_reports(rng, scenario, length_range):
    """report_b is report_a after a known number of random edits.

    That number is edit_bound: it is never below the true edit distance.
    """
    low, high = length_range
    report_a = message_text(rng, scenario, rng.randint(low, high))
    report_b = list(report_a)
    n_edits = rng.randint(1, max(1, len(report_a) // 4))
    for e in range(n_edits):
        op = rng.choice(["replace", "insert", "delete"])
        if op == "insert" and len(report_b) >= high:
            op = "replace"
        if op == "delete" and len(report_b) <= low:
            op = "replace"
        if op == "replace":
            report_b[rng.randint(0, len(report_b) - 1)] = rng.choice(ALPHABET)
        elif op == "insert":
            report_b.insert(rng.randint(0, len(report_b)), rng.choice(ALPHABET))
        else:
            del report_b[rng.randint(0, len(report_b) - 1)]
    return report_a, "".join(report_b), n_edits


def make_trap49_radio(rng):
    """Trap 49: a 50k-100k log that is over 90% one repeated symbol (block length 1).

    Every pattern is (block repeated length-1 times) + one different final symbol,
    so its first length-1 symbols match at almost every start position, but the
    full pattern almost never matches (a near miss each time).
    """
    N = rng.randint(50000, 100000)
    block = rng.choice(LETTERS)
    others = [s for s in ALPHABET if s != block]
    head_len = rng.randint(200, N // 30)
    tail_len = rng.randint(200, N // 30)
    run_end = rng.choice(others)  # the symbol that ends the long run
    head = "".join(rng.choice(others) for i in range(head_len))
    tail = "".join(rng.choice(others) for i in range(tail_len))
    run_len = N - head_len - tail_len - 1
    log = head + block * run_len + run_end + tail

    patterns = []
    for pattern_no in range(6):
        length = PATTERN_LENGTHS[pattern_no]
        if pattern_no <= 2:
            last = run_end  # occurs exactly once, where the run ends
        else:
            last = rng.choice([s for s in others if s != run_end])  # never occurs
        pattern = block * (length - 1) + last
        patterns.append({"pattern_no": pattern_no, "pattern": pattern,
                         "count": count_occurrences(log, pattern)})
    return log, patterns
