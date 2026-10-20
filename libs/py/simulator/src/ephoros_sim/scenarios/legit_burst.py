"""Benign bursts that look like attacks: CI job fan-outs and autoscaler spot scale-outs."""

import random
from datetime import datetime
from typing import Any

from ephoros_sim import records as r
from ephoros_sim.scenarios import Clock, Instance
from ephoros_sim.world import (
    ACCOUNTS,
    CI_SA,
    DEPLOYER_SA,
    JOB_CONTROLLER,
    World,
    ci_ip,
    cluster_ip,
    role_arn,
    short_id,
)


def instance(world: World, rng: random.Random, t0: datetime, k: int) -> Instance:
    return (_ci if k % 2 == 0 else _autoscaler)(rng, t0)


def _ci(rng: random.Random, t0: datetime) -> Instance:
    out = Instance("legit_burst", False, "none")
    add, clock = out.records.append, Clock(t0)
    pipeline = f"p{rng.randint(1000, 9999)}"
    job, job_uid = f"build-{pipeline}", r.k8s_uid(rng)
    actor, ip = rng.choice([CI_SA, DEPLOYER_SA]), ci_ip(rng)
    ts = clock.after(rng, 0, 5)
    add(
        (
            ts,
            "identity",
            r.identity(
                ts,
                "token_issued",
                actor,
                f"ci-{pipeline}",
                ip,
                "DE",
                principal_type="service_account",
                user_agent="gitlab-runner/17.4",
            ),
        )
    )
    labels = {"ci.ephoros.io/pipeline": pipeline, "app": "build"}
    ts = clock.after(rng, 1, 5)
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts,
                "create",
                "jobs",
                "ci",
                job,
                actor,
                ip,
                uid=job_uid,
                body={"metadata": {"labels": labels}},
                user_agent="gitlab-runner/17.4",
            ),
        )
    )
    pods = []
    for _ in range(rng.randint(4, 8)):
        dind = rng.random() < 0.3  # docker-in-docker builds run privileged: the twin of a miner pod
        image, command = (
            ("docker:27-dind", ["dockerd-entrypoint.sh"])
            if dind
            else ("ghcr.io/corp/builder:2.3", ["make", "test"])
        )
        name, uid = f"{job}-{short_id(rng)}", r.k8s_uid(rng)
        body = r.pod_body(
            image,
            command,
            privileged=dind,
            labels=labels,
            owner={"kind": "Job", "name": job, "uid": job_uid},
        )
        ts = clock.after(rng, 0.2, 3)
        add(
            (
                ts,
                "k8s",
                r.k8s(
                    ts,
                    "create",
                    "pods",
                    "ci",
                    name,
                    JOB_CONTROLLER,
                    cluster_ip(rng),
                    uid=uid,
                    body=body,
                ),
            )
        )
        pods.append((name, uid))
    for name, uid in pods:
        ts = clock.after(rng, 20, 90)
        add(
            (
                ts,
                "k8s",
                r.k8s(
                    ts,
                    "delete",
                    "pods",
                    "ci",
                    name,
                    JOB_CONTROLLER,
                    cluster_ip(rng),
                    uid=uid,
                    code=200,
                ),
            )
        )
    ts = clock.after(rng, 5, 30)
    add((ts, "k8s", r.k8s(ts, "delete", "jobs", "ci", job, actor, ip, uid=job_uid, code=200)))
    return out


def _autoscaler(rng: random.Random, t0: datetime) -> Instance:
    out = Instance("legit_burst", False, "none")
    add, clock = out.records.append, Clock(t0)
    account, region = rng.choice(sorted(ACCOUNTS.items()))
    arn = role_arn(account, "autoscaler", f"asg-{short_id(rng)}")
    common: dict[str, Any] = {
        "arn": arn,
        "identity_type": "AssumedRole",
        "ip": f"10.0.4.{rng.randint(2, 250)}",
        "account": account,
        "region": region,
    }
    ts = clock.after(rng, 0, 5)
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "AssumeRole",
                **common,
                request={"roleArn": f"arn:aws:iam::{account}:role/autoscaler"},
            ),
        )
    )
    tags = [{"key": "autoscaler", "value": "true"}, {"key": "role", "value": "worker"}]
    instances = []
    for _ in range(rng.randint(5, 10)):
        instance_id = f"i-{short_id(rng, 12)}"
        ts = clock.after(rng, 0.5, 10)
        add(
            (
                ts,
                "cloud_audit",
                r.cloud(
                    ts,
                    "RunInstances",
                    **common,
                    request={"instanceType": "c5.large", "marketType": "spot", "tags": tags},
                    response={"instanceId": instance_id},
                ),
            )
        )
        instances.append(instance_id)
    clock.after(rng, 600, 1800)
    for instance_id in instances:
        ts = clock.after(rng, 1, 30)
        add(
            (
                ts,
                "cloud_audit",
                r.cloud(ts, "TerminateInstances", **common, request={"instanceIds": [instance_id]}),
            )
        )
    return out
