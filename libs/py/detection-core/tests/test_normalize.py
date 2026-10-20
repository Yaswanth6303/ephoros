from typing import Any

import pytest
from records import cloud, identity, k8s

from ephoros_detection.events import Event
from ephoros_detection.ids import uuid7
from ephoros_detection.normalize import NormalizationError, normalize


def run(source: str, raw: dict[str, Any]) -> Event:
    return normalize(uuid7(), source, raw)


def test_cloud_run_instances() -> None:
    e = run("cloud_audit", cloud())
    assert (e.category, e.action, e.outcome) == ("resource_lifecycle", "run_instances", "success")
    assert e.actor.principal_type == "role"
    assert e.actor.principal_id == "arn:aws:sts::111111111111:assumed-role/autoscaler/session-1"
    assert (e.resource.kind, e.resource.resource_uid) == ("Instance", "i-0abc")
    assert (e.resource.account, e.resource.region) == ("111111111111", "eu-west-1")
    assert e.resource.labels == {"role": "autoscaler"}
    assert e.attributes == {"instance_type": "c5.large", "spot": True, "public_ip": "52.1.2.3"}
    assert e.observed_at.isoformat() == "2026-01-05T08:00:00+00:00"


def test_cloud_security_group_open_to_world() -> None:
    raw = cloud(
        "AuthorizeSecurityGroupIngress",
        requestParameters={
            "groupId": "sg-1",
            "ipPermissions": [{"cidr": "0.0.0.0/0", "fromPort": 22, "toPort": 22}],
        },
        responseElements={},
    )
    e = run("cloud_audit", raw)
    assert (e.category, e.action, e.resource.kind, e.resource.resource_uid) == (
        "api_activity",
        "modify_sg",
        "SecurityGroup",
        "sg-1",
    )
    assert e.attributes["sg_rules"] == [{"cidr": "0.0.0.0/0", "from_port": 22, "to_port": 22}]


def test_cloud_error_is_failure() -> None:
    assert run("cloud_audit", cloud(errorCode="UnauthorizedOperation")).outcome == "failure"


def test_k8s_privileged_pod_create() -> None:
    e = run("k8s", k8s())
    assert (e.source, e.category, e.action) == ("k8s", "resource_lifecycle", "create")
    assert (e.resource.kind, e.resource.name, e.resource.namespace) == ("Pod", "build-1", "ci")
    assert e.resource.resource_uid == "uid-1"
    assert e.attributes == {
        "privileged": True,
        "host_network": False,
        "image": "ghcr.io/corp/builder:1.2",
        "command": "make test",
    }
    assert e.actor == e.actor.model_copy(update={"principal_type": "user", "source_ip": "10.0.1.5"})


def test_k8s_exec_subresource() -> None:
    raw = k8s(
        "create",
        objectRef={"resource": "pods", "subresource": "exec", "namespace": "ci", "name": "build-1"},
    )
    e = run("k8s", raw | {"requestObject": None})
    assert (e.category, e.action) == ("api_activity", "exec")
    assert e.resource.resource_uid == "k8s:pods:ci:build-1"  # no uid on subresource calls


def test_k8s_service_account_actor() -> None:
    raw = k8s(user={"username": "system:serviceaccount:ci:runner", "groups": []})
    assert run("k8s", raw).actor.principal_type == "service_account"


def test_k8s_exposed_service() -> None:
    raw = k8s(
        resource="services",
        requestObject={
            "metadata": {},
            "spec": {"type": "NodePort", "ports": [{"port": 80, "nodePort": 30080}]},
        },
    )
    e = run("k8s", raw)
    assert e.resource.kind == "Service"
    assert e.attributes == {"service_type": "NodePort", "exposed_ports": [30080]}


def test_k8s_rolebinding_is_rbac() -> None:
    raw = k8s(
        resource="clusterrolebindings",
        requestObject={"metadata": {}, "roleRef": {"kind": "ClusterRole", "name": "cluster-admin"}},
    )
    e = run("k8s", raw)
    assert (e.category, e.action, e.attributes["role_ref"]) == (
        "rbac",
        "bind_role",
        "cluster-admin",
    )


def test_k8s_owner_reference() -> None:
    e = run("k8s", k8s())
    assert e.resource.owner_ref == {"kind": "Job", "name": "build-42", "uid": "job-uid"}
    assert e.resource.labels == {"app": "build"}


def test_k8s_error_is_failure() -> None:
    assert run("k8s", k8s(responseStatus={"code": 403})).outcome == "failure"


def test_identity_federated_login() -> None:
    e = run("identity", identity())
    assert (e.category, e.action, e.actor.principal_type) == ("session", "login", "federated")
    assert (e.actor.session_id, e.actor.source_ip) == ("sess-1", "203.0.113.9")
    assert (e.resource.kind, e.resource.resource_uid) == ("Session", "sess-1")
    assert e.attributes == {"geo": {"country": "PT", "city": "Lisbon"}, "federated_from": "okta"}


@pytest.mark.parametrize(
    ("source", "raw"),
    [
        pytest.param("mainframe", identity(), id="unknown-source"),
        pytest.param(
            "cloud_audit",
            {k: v for k, v in cloud().items() if k != "eventTime"},
            id="missing-timestamp",
        ),
        pytest.param("cloud_audit", cloud("DescribeInstances"), id="unknown-event-name"),
        pytest.param("k8s", k8s("watch"), id="unknown-verb"),
        pytest.param("k8s", k8s(requestObject="not-a-dict"), id="non-dict-request-object"),
        pytest.param("identity", identity(timestamp="2026-01-05T08:00:00"), id="naive-timestamp"),
        pytest.param("identity", identity(event_type="teleport"), id="unknown-identity-event"),
        pytest.param("k8s", [], id="not-a-dict"),
    ],
)
def test_invalid_records_raise_normalization_error(source: str, raw: Any) -> None:
    with pytest.raises(NormalizationError):
        normalize(uuid7(), source, raw)
