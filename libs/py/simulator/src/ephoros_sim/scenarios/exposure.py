"""Public exposure: a debug pod behind a NodePort/LoadBalancer, or a security group opened to the
world. The benign twin is an approved sandbox exposure."""

import random
from datetime import datetime

from ephoros_sim import records as r
from ephoros_sim.scenarios import Clock, Instance
from ephoros_sim.world import ACCOUNTS, APP_NAMESPACES, World, short_id


def instance(world: World, rng: random.Random, t0: datetime, k: int) -> Instance:
    person = rng.choice(world.people)
    clock = Clock(t0)
    # k=0: the approved sandbox twin, k=1: a security group, then random
    if k == 1 or (k > 1 and rng.random() < 0.4):
        out = Instance("public_exposure", True, "high")
        account, region = rng.choice(sorted(ACCOUNTS.items()))
        port = rng.choice([22, 3389, 5432])
        ts = clock.after(rng, 0, 60)
        out.records.append(
            (
                ts,
                "cloud_audit",
                r.cloud(
                    ts,
                    "AuthorizeSecurityGroupIngress",
                    arn=f"arn:aws:iam::{account}:user/{person.email.split('@')[0]}",
                    identity_type="IAMUser",
                    ip=person.ip,
                    account=account,
                    region=region,
                    request={
                        "groupId": f"sg-{short_id(rng, 8)}",
                        "ipPermissions": [{"cidr": "0.0.0.0/0", "fromPort": port, "toPort": port}],
                    },
                ),
            )
        )
        return out

    approved = k == 0 or rng.random() < 0.3
    out = Instance(
        "public_exposure", not approved, "low" if approved else rng.choice(["medium", "high"])
    )
    add = out.records.append
    ns = "sandbox" if approved else rng.choice(APP_NAMESPACES)
    name, uid, svc_uid = f"debug-{short_id(rng)}", r.k8s_uid(rng), r.k8s_uid(rng)
    labels = {"exposure": "approved"} if approved else {"app": "debug"}
    ts = clock.after(rng, 0, 60)
    body = r.pod_body("docker.io/nicolaka/netshoot:v0.13", ["sleep", "infinity"], labels=labels)
    add(
        (
            ts,
            "k8s",
            r.k8s(ts, "create", "pods", ns, name, person.email, person.ip, uid=uid, body=body),
        )
    )
    service_type = rng.choice(["NodePort", "LoadBalancer"])
    ports = [{"port": 80, "nodePort": rng.randint(30000, 32767)}]
    ts = clock.after(rng, 5, 120)
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts,
                "create",
                "services",
                ns,
                name,
                person.email,
                person.ip,
                uid=svc_uid,
                body={
                    "metadata": {"labels": labels},
                    "spec": {"type": service_type, "ports": ports},
                },
            ),
        )
    )
    ts = clock.after(rng, 300, 1500)
    add(
        (
            ts,
            "k8s",
            r.k8s(
                ts, "delete", "services", ns, name, person.email, person.ip, uid=svc_uid, code=200
            ),
        )
    )
    ts = clock.after(rng, 1, 30)
    add(
        (
            ts,
            "k8s",
            r.k8s(ts, "delete", "pods", ns, name, person.email, person.ip, uid=uid, code=200),
        )
    )
    return out
