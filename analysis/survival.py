"""Kaplan-Meier and a small Cox model for rule-file survival."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import math
import random

from analysis.corpuslib import BOOTSTRAP_DRAWS, SEED


def incidence_at(times: list[float], events: list[int], horizon: float) -> float | None:
    """Cumulative incidence 1-S(horizon). None when the risk set is empty before the horizon."""
    if not times:
        return None
    order = sorted(range(len(times)), key=lambda index: times[index])
    survival = 1.0
    at_risk = len(times)
    index = 0
    size = len(times)
    while index < size and times[order[index]] <= horizon:
        moment = times[order[index]]
        count = 0
        event_count = 0
        while index < size and times[order[index]] == moment:
            count += 1
            event_count += int(events[order[index]])
            index += 1
        if at_risk <= 0:
            return None
        if event_count:
            survival *= 1 - event_count / at_risk
        at_risk -= count
    if index < size or (order and times[order[-1]] >= horizon):
        return 1 - survival
    return None


def bootstrap_incidence(times: list[float], events: list[int], horizon: float) -> tuple[float, float, float] | None:
    point = incidence_at(times, events, horizon)
    if point is None:
        return None
    rng = random.Random(SEED)
    size = len(times)
    stats = []
    for _ in range(BOOTSTRAP_DRAWS):
        sample_times = []
        sample_events = []
        for _ in range(size):
            index = rng.randrange(size)
            sample_times.append(times[index])
            sample_events.append(events[index])
        estimate = incidence_at(sample_times, sample_events, horizon)
        if estimate is not None:
            stats.append(estimate)
    if not stats:
        return point, point, point
    stats.sort()
    return point, stats[int(0.025 * (len(stats) - 1))], stats[int(0.975 * (len(stats) - 1))]


def cox_ph(times: list[float], events: list[int], covariates: list[list[float]]) -> dict:
    """Breslow Cox model. covariates is a list of columns."""
    rows = [
        (time, int(event), [column[index] for column in covariates])
        for index, (time, event) in enumerate(zip(times, events))
    ]
    rows = [row for row in rows if row[0] >= 0]
    if sum(row[1] for row in rows) < 20 or not covariates:
        return {"converged": False, "reason": "fewer than 20 events or no covariates"}
    width = len(covariates)
    means = []
    scales = []
    for column in range(width):
        values = [row[2][column] for row in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        scale = math.sqrt(variance) or 1.0
        means.append(mean)
        scales.append(scale)
    scaled = []
    for time, event, values in rows:
        scaled.append((time, event, [(value - means[index]) / scales[index] for index, value in enumerate(values)]))
    scaled.sort(key=lambda row: row[0])
    beta = [0.0] * width
    converged = False
    for _ in range(25):
        score, information, ok = _partial(scaled, beta)
        if not ok:
            return {"converged": False, "reason": "partial likelihood failed"}
        step = _solve(information, score)
        if step is None:
            return {"converged": False, "reason": "singular information"}
        beta = [value + delta for value, delta in zip(beta, step)]
        if max(abs(delta) for delta in step) < 1e-6:
            converged = True
            break
    names = ["log_commits", "log_authors"]
    estimates = []
    information = _partial(scaled, beta)[1]
    inverse = _invert(information)
    for index, name in enumerate(names[:width]):
        variance = inverse[index][index] if inverse else None
        coef = beta[index] / scales[index]
        record = {"name": name, "coef": coef, "hr": math.exp(coef)}
        if variance is not None and variance >= 0:
            se = math.sqrt(variance) / scales[index]
            record["ci_low"] = math.exp(coef - 1.96 * se)
            record["ci_high"] = math.exp(coef + 1.96 * se)
        estimates.append(record)
    return {"converged": converged, "estimates": estimates}


def _partial(rows: list[tuple], beta: list[float]) -> tuple[list[float], list[list[float]], bool]:
    width = len(beta)
    score = [0.0] * width
    info = [[0.0] * width for _ in range(width)]
    # Walk from the latest time so the risk set grows by earlier subjects.
    exp_terms = []
    for _, _, values in rows:
        linear = sum(weight * value for weight, value in zip(beta, values))
        linear = max(-20, min(20, linear))
        weight = math.exp(linear)
        exp_terms.append((weight, [weight * value for value in values], values))
    risk_w = 0.0
    risk_wx = [0.0] * width
    risk_wxx = [[0.0] * width for _ in range(width)]
    index = len(rows) - 1
    while index >= 0:
        time = rows[index][0]
        start = index
        while start >= 0 and rows[start][0] == time:
            weight, wx, values = exp_terms[start]
            risk_w += weight
            for col in range(width):
                risk_wx[col] += wx[col]
                for other in range(width):
                    risk_wxx[col][other] += weight * values[col] * values[other]
            start -= 1
        if risk_w <= 0:
            return score, info, False
        event_index = index
        while event_index > start:
            if rows[event_index][1]:
                values = rows[event_index][2]
                for col in range(width):
                    score[col] += values[col] - risk_wx[col] / risk_w
                for col in range(width):
                    for other in range(width):
                        info[col][other] += (
                            risk_wxx[col][other] / risk_w
                            - (risk_wx[col] / risk_w) * (risk_wx[other] / risk_w)
                        )
            event_index -= 1
        index = start
    return score, info, True


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    size = len(vector)
    aug = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(aug[row][col]))
        if abs(aug[pivot][col]) < 1e-10:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        for other in range(col, size + 1):
            aug[col][other] /= scale
        for row in range(size):
            if row == col:
                continue
            factor = aug[row][col]
            for other in range(col, size + 1):
                aug[row][other] -= factor * aug[col][other]
    return [aug[index][size] for index in range(size)]


def _invert(matrix: list[list[float]]) -> list[list[float]] | None:
    size = len(matrix)
    columns = []
    for index in range(size):
        basis = [0.0] * size
        basis[index] = 1.0
        solved = _solve(matrix, basis)
        if solved is None:
            return None
        columns.append(solved)
    return [[columns[col][row] for col in range(size)] for row in range(size)]


def _self_check() -> None:
    times = [1, 1, 2, 5, 30]
    events = [1, 0, 1, 1, 0]
    estimate = incidence_at(times, events, 24)
    assert estimate is not None and 0 < estimate < 1, estimate
    quick = bootstrap_incidence([1.0, 2.0, 40.0], [1, 0, 0], 24)
    assert quick is not None
    fitted = cox_ph(
        [1, 2, 3, 4, 5, 6, 7, 8] * 5,
        [1, 0, 1, 0, 1, 1, 0, 1] * 5,
        [[0, 1, 0, 1, 2, 3, 0, 2] * 5, [1, 1, 2, 0, 1, 2, 0, 1] * 5],
    )
    assert "converged" in fitted
    print("survival self-check ok", round(estimate, 3), fitted["converged"])


if __name__ == "__main__":
    _self_check()
