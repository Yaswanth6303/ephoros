import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from ephoros_detection.normalize import normalize
from ephoros_sim.generate import generate
from ephoros_sim.model import SimRecord

START = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
MALICIOUS = {"crypto_mining", "public_exposure", "identity_anomaly"}
# update deliberately when the generator changes: it pins the evaluation dataset
GOLDEN_SEED_7 = "fd0597974dbcad9d74deccc7a7654c5b22dbe6a6cadaf9be8b3c401f1e1996aa"


def dump(records: list[SimRecord]) -> str:
    return json.dumps(
        [
            asdict(r) | {"event_id": str(r.event_id), "observed_at": r.observed_at.isoformat()}
            for r in records
        ],
        sort_keys=True,
    )


def test_same_seed_is_byte_identical() -> None:
    assert dump(generate(7, START)) == dump(generate(7, START))
    assert dump(generate(7, START)) != dump(generate(8, START))


def test_golden_digest_seed_7() -> None:
    assert hashlib.sha256(dump(generate(7, START)).encode()).hexdigest() == GOLDEN_SEED_7


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 7])
def test_counts_per_source_are_in_range(seed: int) -> None:
    counts = Counter(r.source for r in generate(seed, START))
    assert 500 <= counts["cloud_audit"] <= 1000
    assert 500 <= counts["k8s"] <= 1000
    assert 200 <= counts["identity"] <= 500


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 7])
def test_scenario_mix_is_in_range(seed: int) -> None:
    instances = {r.label.scenario_instance_id: r.label.scenario for r in generate(seed, START)}
    share = {name: n / len(instances) for name, n in Counter(instances.values()).items()}
    assert 0.05 <= share["crypto_mining"] <= 0.08
    assert 0.03 <= share["public_exposure"] <= 0.05
    assert 0.05 <= share["identity_anomaly"] <= 0.08
    assert 0.40 <= share["legit_burst"] <= 0.50
    assert 0.30 <= share["routine_lifecycle"] <= 0.40


def test_records_are_time_ordered_inside_the_window() -> None:
    records = generate(7, START, hours=6)
    times = [r.observed_at for r in records]
    assert times == sorted(times)
    assert START <= times[0] and times[-1] <= START + timedelta(hours=6)


def test_every_record_normalizes() -> None:
    for r in generate(7, START):
        event = normalize(r.event_id, r.source, r.raw)
        assert event.observed_at == r.observed_at


def test_malicious_scenarios_are_labelled() -> None:
    for r in generate(7, START):
        if r.label.scenario in {"legit_burst", "routine_lifecycle"}:
            assert not r.label.is_malicious and r.label.severity == "none"
        elif r.label.is_malicious:
            assert r.label.scenario in MALICIOUS and r.label.severity in {
                "medium",
                "high",
                "critical",
            }
        else:  # the approved-exposure twin
            assert r.label.scenario == "public_exposure" and r.label.severity == "low"


def test_ambiguity_twins_exist() -> None:
    records = generate(7, START)
    events = [normalize(r.event_id, r.source, r.raw) for r in records]
    pods = [e for e in events if e.resource.kind == "Pod" and e.action == "create"]
    assert any(
        e.resource.owner_ref and e.resource.owner_ref["kind"] == "Job" for e in pods
    )  # CI pod
    assert any(
        e.resource.owner_ref is None and e.attributes.get("privileged") for e in pods
    )  # miner-like
    deployer_ips = {
        e.actor.source_ip for e in events if e.actor.principal_id.endswith(":ci:deployer")
    }
    assert len(deployer_ips) >= 2  # shared SA: CI automation and a stolen token
    assert any(r.label.scenario == "public_exposure" and not r.label.is_malicious for r in records)
