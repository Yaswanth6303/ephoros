"""CloudTrail-like records (spec §6)."""

from typing import Any
from uuid import UUID

from ephoros_detection.events import Event
from ephoros_detection.normalize.common import NormalizationError, timestamp

# eventName → (action, category, resource kind)
_EVENTS = {
    "RunInstances": ("run_instances", "resource_lifecycle", "Instance"),
    "TerminateInstances": ("terminate_instances", "resource_lifecycle", "Instance"),
    "AuthorizeSecurityGroupIngress": ("modify_sg", "api_activity", "SecurityGroup"),
    "AssumeRole": ("assume_role", "session", "Role"),
    "CreateAccessKey": ("create_access_key", "api_activity", "AccessKey"),
}
_PRINCIPAL_TYPES = {
    "IAMUser": "user",
    "Root": "user",
    "AssumedRole": "role",
    "FederatedUser": "federated",
}


def to_event(event_id: UUID, raw: dict[str, Any]) -> Event:
    name = raw["eventName"]
    if name not in _EVENTS:
        raise NormalizationError(f"cloud_audit: unsupported eventName {name!r}")
    action, category, kind = _EVENTS[name]
    who, req, resp = (
        raw["userIdentity"],
        raw.get("requestParameters") or {},
        raw.get("responseElements") or {},
    )
    uid = {
        "Instance": resp.get("instanceId") or (req.get("instanceIds") or [None])[0],
        "SecurityGroup": req.get("groupId"),
        "Role": req.get("roleArn"),
        "AccessKey": resp.get("accessKeyId") or req.get("userName"),
    }[kind]
    if not uid and raw.get("errorCode"):
        uid = f"failed:{action}:{event_id}"  # refused calls create nothing, but the attempt matters
    if not uid:
        raise NormalizationError(f"cloud_audit: {name} has no resource id")
    attributes: dict[str, Any] = {}
    if "instanceType" in req:
        attributes |= {
            "instance_type": req["instanceType"],
            "spot": req.get("marketType") == "spot",
        }
    if "publicIpAddress" in resp:
        attributes["public_ip"] = resp["publicIpAddress"]
    if "ipPermissions" in req:
        attributes["sg_rules"] = [
            {"cidr": p["cidr"], "from_port": p["fromPort"], "to_port": p["toPort"]}
            for p in req["ipPermissions"]
        ]
    return Event.model_validate(
        {
            "event_id": event_id,
            "source": "cloud_audit",
            "category": category,
            "action": action,
            "outcome": "failure" if raw.get("errorCode") else "success",
            "observed_at": timestamp(raw["eventTime"]),
            "actor": {
                "principal_id": who["arn"],
                "principal_type": _PRINCIPAL_TYPES.get(who["type"], "role"),
                "session_id": who.get("accessKeyId"),
                "source_ip": raw.get("sourceIPAddress"),
                "user_agent": raw.get("userAgent"),
            },
            "resource": {
                "resource_uid": uid,
                "kind": kind,
                "account": raw.get("recipientAccountId"),
                "region": raw.get("awsRegion"),
                "labels": {t["key"]: t["value"] for t in req.get("tags", [])},
            },
            "attributes": attributes,
            "raw": raw,
        }
    )
