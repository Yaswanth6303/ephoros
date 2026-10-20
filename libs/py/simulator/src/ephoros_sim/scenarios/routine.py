"""Benign day-to-day lifecycle: logins, deployment rollouts, instance replacement."""

import random
from datetime import datetime
from typing import Any

from ephoros_sim import records as r
from ephoros_sim.scenarios import Clock, Instance
from ephoros_sim.world import (
    ACCOUNTS,
    APP_NAMESPACES,
    ATTACKER_COUNTRIES,
    DEPLOY_CONTROLLER,
    DEPLOYER_SA,
    RS_CONTROLLER,
    SCRIPT_AGENTS,
    Person,
    World,
    ci_ip,
    cluster_ip,
    role_arn,
    short_id,
    vpn_ip,
)


def instance(world: World, rng: random.Random, t0: datetime, k: int) -> Instance:
    out = Instance("routine_lifecycle", False, "none")
    add, clock = out.records.append, Clock(t0)
    first, second = rng.sample(world.people, 2)
    if k % 3 == 0:  # travelling / on a commercial VPN: an external IP and country, still benign
        second = Person(second.email, rng.choice(ATTACKER_COUNTRIES), vpn_ip(rng, k // 3))
    script_agent = SCRIPT_AGENTS[k % len(SCRIPT_AGENTS)]
    session = f"sess-{short_id(rng, 8)}"
    for event in ("login", "mfa", "token_issued"):
        add(
            (
                ts := clock.after(rng, 1, 20),
                "identity",
                r.identity(ts, event, first.email, session, first.ip, first.country),
            )
        )

    ns, app = rng.choice(APP_NAMESPACES), rng.choice(["api", "web", "worker", "cache"])
    dep_uid, rs_uid = r.k8s_uid(rng), r.k8s_uid(rng)
    rs = f"{app}-{short_id(rng)}"
    ts = clock.after(rng, 5, 60)
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts, "update", "deployments", ns, app, DEPLOYER_SA, ci_ip(rng), uid=dep_uid, code=200
            ),
        )
    )
    ts = clock.after(rng, 1, 3)
    owner = {"kind": "Deployment", "name": app, "uid": dep_uid}
    body = {"metadata": {"labels": {"app": app}, "ownerReferences": [owner]}}
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts,
                "create",
                "replicasets",
                ns,
                rs,
                DEPLOY_CONTROLLER,
                cluster_ip(rng),
                uid=rs_uid,
                body=body,
            ),
        )
    )
    pods = rng.randint(2, 3)
    image = f"ghcr.io/corp/{app}:1.{rng.randint(0, 40)}"
    for _ in range(pods):
        ts = clock.after(rng, 1, 10)
        pod = r.pod_body(
            image,
            ["./run"],
            labels={"app": app},
            owner={"kind": "ReplicaSet", "name": rs, "uid": rs_uid},
        )
        add(
            (
                ts,
                "k8s",
                r.k8s(
                    ts,
                    "create",
                    "pods",
                    ns,
                    f"{rs}-{short_id(rng)}",
                    RS_CONTROLLER,
                    cluster_ip(rng),
                    uid=r.k8s_uid(rng),
                    body=pod,
                ),
            )
        )
    for _ in range(pods):
        ts = clock.after(rng, 5, 30)
        add(
            (
                ts,
                "k8s",
                r.k8s(
                    ts,
                    "delete",
                    "pods",
                    ns,
                    f"{app}-old-{short_id(rng)}",
                    RS_CONTROLLER,
                    cluster_ip(rng),
                    uid=r.k8s_uid(rng),
                    code=200,
                ),
            )
        )

    account, region = rng.choice(sorted(ACCOUNTS.items()))
    common: dict[str, Any] = {"ip": first.ip, "account": account, "region": region}
    user_arn = f"arn:aws:iam::{account}:user/{first.email.split('@')[0]}"
    ts = clock.after(rng, 10, 120)
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "AssumeRole",
                arn=user_arn,
                identity_type="IAMUser",
                **common,
                request={"roleArn": f"arn:aws:iam::{account}:role/ci-deployer"},
            ),
        )
    )
    deploy_arn = role_arn(account, "ci-deployer", f"deploy-{short_id(rng)}")
    old, new = f"i-{short_id(rng, 12)}", f"i-{short_id(rng, 12)}"
    tags = [{"key": "role", "value": app}]
    ts = clock.after(rng, 5, 60)
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "RunInstances",
                arn=deploy_arn,
                identity_type="AssumedRole",
                **common,
                request={"instanceType": "m6i.large", "marketType": "on-demand", "tags": tags},
                response={"instanceId": new},
            ),
        )
    )
    ts = clock.after(rng, 60, 300)
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "TerminateInstances",
                arn=deploy_arn,
                identity_type="AssumedRole",
                **common,
                request={"instanceIds": [old]},
            ),
        )
    )
    ts = clock.after(rng, 5, 60)
    rule = [{"cidr": "10.0.0.0/8", "fromPort": 443, "toPort": 443}]
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "AuthorizeSecurityGroupIngress",
                arn=deploy_arn,
                identity_type="AssumedRole",
                **common,
                request={"groupId": f"sg-{short_id(rng, 8)}", "ipPermissions": rule},
            ),
        )
    )
    reader = role_arn(account, "read-only", second.email.split("@")[0])
    for _ in range(rng.randint(3, 6)):
        ts = clock.after(rng, 20, 150)
        add(
            (
                ts,
                "cloud_audit",
                r.cloud(
                    ts,
                    "AssumeRole",
                    arn=reader,
                    identity_type="AssumedRole",
                    ip=second.ip,
                    user_agent=script_agent,
                    account=account,
                    region=region,
                    request={"roleArn": f"arn:aws:iam::{account}:role/read-only"},
                ),
            )
        )

    other = f"sess-{short_id(rng, 8)}"
    for event in ("login", "logout"):
        add(
            (
                ts := clock.after(rng, 30, 400),
                "identity",
                r.identity(ts, event, second.email, other, second.ip, second.country),
            )
        )
    add(
        (
            ts := clock.after(rng, 30, 300),
            "identity",
            r.identity(ts, "logout", first.email, session, first.ip, first.country),
        )
    )
    return out
