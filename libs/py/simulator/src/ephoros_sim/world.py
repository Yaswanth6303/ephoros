"""The fixed cast every run shares: accounts, namespaces, people, service accounts, networks."""

import random
from dataclasses import dataclass

ACCOUNTS = {
    "111111111111": "eu-west-1",
    "222222222222": "us-east-1",
    "333333333333": "eu-central-1",
}
NAMESPACES = ["ci", "payments", "web", "data", "platform", "sandbox"]
APP_NAMESPACES = ["payments", "web", "data", "platform"]
HOME_COUNTRIES = ["IN", "FR", "PT", "DE"]
ATTACKER_COUNTRIES = ["RU", "BR", "NG", "VN", "KP"]
IDPS = ["okta", "azure-ad"]
CI_SA = "system:serviceaccount:ci:runner"
DEPLOYER_SA = "system:serviceaccount:ci:deployer"  # shared by CI automation and humans
JOB_CONTROLLER = "system:serviceaccount:kube-system:job-controller"
RS_CONTROLLER = "system:serviceaccount:kube-system:replicaset-controller"
DEPLOY_CONTROLLER = "system:serviceaccount:kube-system:deployment-controller"


@dataclass(frozen=True)
class Person:
    email: str
    country: str
    ip: str


@dataclass(frozen=True)
class World:
    people: list[Person]

    @staticmethod
    def build(rng: random.Random) -> "World":
        names = [
            "ana",
            "bob",
            "chen",
            "dara",
            "eli",
            "farah",
            "gus",
            "hana",
            "ivan",
            "jo",
            "kai",
            "lena",
            "milo",
            "nia",
            "omar",
            "pia",
            "quinn",
            "ravi",
            "sara",
            "tomas",
        ]
        return World(
            people=[
                Person(f"{n}@corp.example", rng.choice(HOME_COUNTRIES), f"198.51.100.{i + 10}")
                for i, n in enumerate(names)
            ]
        )


def ci_ip(rng: random.Random) -> str:
    return f"10.0.2.{rng.randint(2, 250)}"


def cluster_ip(rng: random.Random) -> str:
    return f"10.0.1.{rng.randint(2, 250)}"


def attacker_ip(rng: random.Random) -> str:
    return rng.choice(["185.220.101", "45.155.205", "103.75.190"]) + f".{rng.randint(2, 250)}"


def role_arn(account: str, role: str, session: str) -> str:
    return f"arn:aws:sts::{account}:assumed-role/{role}/{session}"


def short_id(rng: random.Random, n: int = 5) -> str:
    return f"{rng.getrandbits(4 * n):0{n}x}"
