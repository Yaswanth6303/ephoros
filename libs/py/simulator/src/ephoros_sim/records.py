"""Raw record builders in exactly the formats ephoros_detection.normalize accepts."""

import random
import uuid
from datetime import datetime
from typing import Any


def iso(ts: datetime) -> str:
    return ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def k8s_uid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def k8s(
    ts: datetime,
    verb: str,
    resource: str,
    namespace: str,
    name: str,
    user: str,
    ip: str,
    *,
    uid: str | None = None,
    body: dict[str, Any] | None = None,
    subresource: str | None = None,
    code: int = 201,
    user_agent: str = "kubectl/v1.31.0",
) -> dict[str, Any]:
    ref: dict[str, Any] = {"resource": resource, "namespace": namespace, "name": name}
    if uid:
        ref["uid"] = uid
    if subresource:
        ref["subresource"] = subresource
    return {
        "apiVersion": "audit.k8s.io/v1",
        "kind": "Event",
        "requestReceivedTimestamp": iso(ts),
        "verb": verb,
        "user": {"username": user, "groups": ["system:authenticated"]},
        "sourceIPs": [ip],
        "userAgent": user_agent,
        "objectRef": ref,
        "responseStatus": {"code": code},
        "requestObject": body,
    }


def pod_body(
    image: str,
    command: list[str],
    *,
    privileged: bool = False,
    labels: dict[str, str] | None = None,
    owner: dict[str, str] | None = None,
    host_network: bool = False,
) -> dict[str, Any]:
    meta: dict[str, Any] = {"labels": labels or {}}
    if owner:
        meta["ownerReferences"] = [owner]
    return {
        "metadata": meta,
        "spec": {
            "hostNetwork": host_network,
            "containers": [
                {"image": image, "command": command, "securityContext": {"privileged": privileged}}
            ],
        },
    }


def cloud(
    ts: datetime,
    event_name: str,
    *,
    arn: str,
    identity_type: str,
    ip: str,
    account: str,
    region: str,
    request: dict[str, Any],
    response: dict[str, Any] | None = None,
    access_key: str | None = None,
    user_agent: str = "aws-sdk-go-v2/1.30",
    error: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "eventTime": iso(ts),
        "eventName": event_name,
        "userIdentity": {"type": identity_type, "principalId": arn.rsplit("/", 1)[-1], "arn": arn},
        "sourceIPAddress": ip,
        "userAgent": user_agent,
        "awsRegion": region,
        "recipientAccountId": account,
        "requestParameters": request,
        "responseElements": response or {},
    }
    if access_key:
        record["userIdentity"]["accessKeyId"] = access_key
    if error:
        record["errorCode"] = error
    return record


def identity(
    ts: datetime,
    event_type: str,
    principal: str,
    session_id: str,
    ip: str,
    country: str,
    *,
    principal_type: str = "user",
    federated_from: str | None = None,
    outcome: str = "success",
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5)",
) -> dict[str, Any]:
    return {
        "timestamp": iso(ts),
        "event_type": event_type,
        "principal": principal,
        "principal_type": principal_type,
        "session_id": session_id,
        "ip": ip,
        "geo": {"country": country},
        "user_agent": user_agent,
        "federated_from": federated_from,
        "outcome": outcome,
    }
