"""Malicious: a stolen service-account token runs a privileged, controller-less miner-like pod
(a harmless busybox loop in the demo), sometimes with a GPU spot burst; all gone within minutes."""

import random
from datetime import datetime
from typing import Any

from ephoros_sim import records as r
from ephoros_sim.scenarios import Clock, Instance
from ephoros_sim.world import (
    ACCOUNTS,
    APP_NAMESPACES,
    ATTACKER_COUNTRIES,
    DEPLOYER_SA,
    World,
    attacker_ip,
    short_id,
)


def instance(world: World, rng: random.Random, t0: datetime, k: int) -> Instance:
    gpu = k % 2 == 1 or rng.random() < 0.3
    out = Instance("crypto_mining", True, "critical" if gpu else "high")
    add, clock = out.records.append, Clock(t0)
    agent = rng.choice(["python-requests/2.32", "kubectl/v1.31.0"])
    ip, ns = attacker_ip(rng), rng.choice([*APP_NAMESPACES, "ci"])
    ts = clock.after(rng, 0, 5)
    add(
        (
            ts,
            "identity",
            r.identity(
                ts,
                "token_issued",
                DEPLOYER_SA,
                f"tok-{short_id(rng, 8)}",
                ip,
                rng.choice(ATTACKER_COUNTRIES),
                principal_type="service_account",
                user_agent=agent,
            ),
        )
    )
    name = f"{rng.choice(['xmrig', 'kworker', 'sysupdate', 'kdevtmpfsi'])}-{short_id(rng)}"
    if name.startswith("xmrig"):
        image, command = "docker.io/xmrig/xmrig:6.21", ["xmrig", "-o", "pool.supportxmr.com:443"]
    else:
        image, command = (
            "docker.io/library/busybox:1.36",
            ["sh", "-c", "while true; do sha256sum /dev/zero; done"],
        )
    uid = r.k8s_uid(rng)
    body = r.pod_body(image, command, privileged=True, host_network=rng.random() < 0.5)
    ts = clock.after(rng, 2, 30)
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts,
                "create",
                "pods",
                ns,
                name,
                DEPLOYER_SA,
                ip,
                uid=uid,
                body=body,
                user_agent=agent,
            ),
        )
    )
    if rng.random() < 0.6:
        ts = clock.after(rng, 10, 60)
        add(
            (
                ts,
                "k8s",
                r.k8s(
                    ts,
                    "create",
                    "pods",
                    ns,
                    name,
                    DEPLOYER_SA,
                    ip,
                    subresource="exec",
                    code=101,
                    user_agent=agent,
                ),
            )
        )
    ts = clock.after(rng, 120, 480)  # deleted before anyone triages it
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts,
                "delete",
                "pods",
                ns,
                name,
                DEPLOYER_SA,
                ip,
                uid=uid,
                code=200,
                user_agent=agent,
            ),
        )
    )
    if gpu:
        account, region = rng.choice(sorted(ACCOUNTS.items()))
        common: dict[str, Any] = {
            "arn": f"arn:aws:iam::{account}:user/ci-bot",
            "identity_type": "IAMUser",
            "ip": ip,
            "account": account,
            "region": region,
            "access_key": f"AKIA{short_id(rng, 16).upper()}",
        }
        launched = []
        for _ in range(rng.randint(2, 4)):
            instance_id = f"i-{short_id(rng, 12)}"
            ts = clock.after(rng, 1, 20)
            add(
                (
                    ts,
                    "cloud_audit",
                    r.cloud(
                        ts,
                        "RunInstances",
                        **common,
                        request={"instanceType": "g4dn.xlarge", "marketType": "spot"},
                        response={"instanceId": instance_id, "publicIpAddress": attacker_ip(rng)},
                    ),
                )
            )
            launched.append(instance_id)
        clock.after(rng, 600, 1200)
        for instance_id in launched:
            ts = clock.after(rng, 1, 20)
            add(
                (
                    ts,
                    "cloud_audit",
                    r.cloud(
                        ts, "TerminateInstances", **common, request={"instanceIds": [instance_id]}
                    ),
                )
            )
    return out
