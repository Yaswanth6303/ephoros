"""Unexpected identity activity: stolen human credentials (impossible travel), automation
credentials used from a new network, and a federated identity escalating."""

import random
from datetime import datetime
from typing import Any

from ephoros_sim import records as r
from ephoros_sim.scenarios import Clock, Instance
from ephoros_sim.world import (
    ACCOUNTS,
    ATTACKER_COUNTRIES,
    DEPLOYER_SA,
    IDPS,
    SCRIPT_AGENTS,
    World,
    attacker_ip,
    role_arn,
    short_id,
)

_AGENTS = [*SCRIPT_AGENTS, "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)"]


def instance(world: World, rng: random.Random, t0: datetime, k: int) -> Instance:
    variant = k % 3
    person = rng.choice(world.people)
    account, region = rng.choice(sorted(ACCOUNTS.items()))
    ip, country = attacker_ip(rng), rng.choice(ATTACKER_COUNTRIES)
    admin = f"arn:aws:iam::{account}:role/admin"
    clock = Clock(t0)
    agent = rng.choice(_AGENTS)

    if (
        variant == 0
    ):  # stolen human credentials: home login, then the same user from abroad minutes later
        out = Instance("identity_anomaly", True, "high")
        add = out.records.append
        home = f"sess-{short_id(rng, 8)}"
        add(
            (
                ts := clock.after(rng, 0, 30),
                "identity",
                r.identity(ts, "login", person.email, home, person.ip, person.country),
            )
        )
        stolen = f"sess-{short_id(rng, 8)}"
        add(
            (
                ts := clock.after(rng, 300, 900),
                "identity",
                r.identity(ts, "login", person.email, stolen, ip, country, user_agent=agent),
            )
        )
        add(
            (
                ts := clock.after(rng, 1, 10),
                "identity",
                r.identity(
                    ts,
                    "mfa",
                    person.email,
                    stolen,
                    ip,
                    country,
                    outcome="failure",
                    user_agent=agent,
                ),
            )
        )
        add(
            (
                ts := clock.after(rng, 5, 60),
                "identity",
                r.identity(ts, "token_issued", person.email, stolen, ip, country, user_agent=agent),
            )
        )
        arn = f"arn:aws:iam::{account}:user/{person.email.split('@')[0]}"
        identity_type = "IAMUser"
    elif variant == 1:  # automation credentials from a network CI never uses
        out = Instance("identity_anomaly", True, "medium")
        add = out.records.append
        add(
            (
                ts := clock.after(rng, 0, 30),
                "identity",
                r.identity(
                    ts,
                    "token_issued",
                    DEPLOYER_SA,
                    f"tok-{short_id(rng, 8)}",
                    ip,
                    country,
                    principal_type="service_account",
                    user_agent=agent,
                ),
            )
        )
        arn, identity_type = (
            role_arn(account, "ci-deployer", f"deploy-{short_id(rng)}"),
            "AssumedRole",
        )
    else:  # federated identity from an unusual place, straight to admin
        out = Instance("identity_anomaly", True, "medium")
        add = out.records.append
        idp, session = rng.choice(IDPS), f"sess-{short_id(rng, 8)}"
        add(
            (
                ts := clock.after(rng, 0, 30),
                "identity",
                r.identity(
                    ts,
                    "login",
                    person.email,
                    session,
                    ip,
                    country,
                    principal_type="federated",
                    federated_from=idp,
                    user_agent=agent,
                ),
            )
        )
        arn, identity_type = (
            f"arn:aws:sts::{account}:federated-user/{person.email.split('@')[0]}",
            "FederatedUser",
        )

    common: dict[str, Any] = {
        "arn": arn,
        "identity_type": identity_type,
        "ip": ip,
        "account": account,
        "region": region,
        "user_agent": agent,
    }
    ts = clock.after(rng, 10, 120)
    add((ts, "cloud_audit", r.cloud(ts, "AssumeRole", **common, request={"roleArn": admin})))
    ts = clock.after(rng, 10, 120)
    add(
        (
            ts,
            "cloud_audit",
            r.cloud(
                ts,
                "CreateAccessKey",
                **common,
                request={"userName": "backup-admin"},
                response={"accessKeyId": f"AKIA{short_id(rng, 16).upper()}"},
            ),
        )
    )
    return out
