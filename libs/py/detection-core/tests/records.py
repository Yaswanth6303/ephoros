"""Sample raw records in each source's format (the simulator emits exactly these shapes)."""

from typing import Any

TS = "2026-01-05T08:00:00Z"


def cloud(event_name: str = "RunInstances", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "eventTime": TS,
        "eventName": event_name,
        "userIdentity": {
            "type": "AssumedRole",
            "principalId": "AROAEXAMPLE:autoscaler",
            "arn": "arn:aws:sts::111111111111:assumed-role/autoscaler/session-1",
            "accessKeyId": "ASIAEXAMPLE",
        },
        "sourceIPAddress": "10.0.4.12",
        "userAgent": "aws-sdk-go/1.44",
        "awsRegion": "eu-west-1",
        "recipientAccountId": "111111111111",
        "requestParameters": {
            "instanceType": "c5.large",
            "marketType": "spot",
            "tags": [{"key": "role", "value": "autoscaler"}],
        },
        "responseElements": {"instanceId": "i-0abc", "publicIpAddress": "52.1.2.3"},
    }
    return record | overrides


def k8s(verb: str = "create", resource: str = "pods", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "apiVersion": "audit.k8s.io/v1",
        "kind": "Event",
        "requestReceivedTimestamp": TS,
        "verb": verb,
        "user": {"username": "alice@corp.example", "groups": ["system:authenticated"]},
        "sourceIPs": ["10.0.1.5"],
        "userAgent": "kubectl/v1.31.0",
        "objectRef": {"resource": resource, "namespace": "ci", "name": "build-1", "uid": "uid-1"},
        "responseStatus": {"code": 201},
        "requestObject": {
            "metadata": {
                "labels": {"app": "build"},
                "ownerReferences": [{"kind": "Job", "name": "build-42", "uid": "job-uid"}],
            },
            "spec": {
                "hostNetwork": False,
                "containers": [
                    {
                        "image": "ghcr.io/corp/builder:1.2",
                        "command": ["make", "test"],
                        "securityContext": {"privileged": True},
                    }
                ],
            },
        },
    }
    return record | overrides


def identity(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "timestamp": TS,
        "event_type": "login",
        "principal": "bob@corp.example",
        "principal_type": "federated",
        "session_id": "sess-1",
        "ip": "203.0.113.9",
        "geo": {"country": "PT", "city": "Lisbon"},
        "user_agent": "Mozilla/5.0",
        "federated_from": "okta",
        "outcome": "success",
    }
    return record | overrides
