"""Kubernetes audit events, audit.k8s.io/v1 (spec §6.2)."""

from typing import Any
from uuid import UUID

from ephoros_detection.events import Event
from ephoros_detection.normalize.common import NormalizationError, timestamp

_VERBS = {
    "create": "create",
    "delete": "delete",
    "update": "update",
    "patch": "update",
    "get": "get",
    "list": "list",
}
_SUBRESOURCES = {"exec": "exec", "portforward": "port_forward", "scale": "scale"}
_KINDS = {
    "pods": "Pod",
    "services": "Service",
    "jobs": "Job",
    "cronjobs": "CronJob",
    "deployments": "Deployment",
    "replicasets": "ReplicaSet",
    "statefulsets": "StatefulSet",
    "secrets": "Secret",
    "rolebindings": "RoleBinding",
    "clusterrolebindings": "ClusterRoleBinding",
}
_RBAC = {"rolebindings", "clusterrolebindings"}


def to_event(event_id: UUID, raw: dict[str, Any]) -> Event:
    ref = raw["objectRef"]
    resource = ref["resource"]
    sub = ref.get("subresource")
    action = _SUBRESOURCES.get(sub) if sub else _VERBS.get(raw["verb"])
    if action is None:
        raise NormalizationError(f"k8s: unsupported verb {raw['verb']!r} subresource {sub!r}")
    body = raw.get("requestObject") or {}
    if not isinstance(body, dict):
        raise NormalizationError("k8s: requestObject is not an object")
    meta, spec = body.get("metadata") or {}, body.get("spec") or {}

    if resource in _RBAC and action == "create":
        category, action = "rbac", "bind_role"
    elif action in {"exec", "port_forward", "get", "list"}:
        category = "api_activity"
    else:
        category = "resource_lifecycle"

    attributes: dict[str, Any] = {}
    if containers := spec.get("containers"):
        attributes = {
            "privileged": any(
                (c.get("securityContext") or {}).get("privileged") for c in containers
            ),
            "host_network": bool(spec.get("hostNetwork")),
            "image": containers[0]["image"],
            "command": " ".join(containers[0].get("command") or []),
        }
    elif resource == "services" and spec:
        attributes = {
            "service_type": spec.get("type", "ClusterIP"),
            "exposed_ports": [p.get("nodePort") or p["port"] for p in spec.get("ports", [])],
        }
    elif "roleRef" in body:
        attributes = {"role_ref": body["roleRef"]["name"]}

    owner = (meta.get("ownerReferences") or [None])[0]
    username = raw["user"]["username"]
    namespace = ref.get("namespace")
    return Event.model_validate(
        {
            "event_id": event_id,
            "source": "k8s",
            "category": category,
            "action": action,
            "outcome": "failure"
            if raw.get("responseStatus", {}).get("code", 200) >= 400
            else "success",
            "observed_at": timestamp(raw["requestReceivedTimestamp"]),
            "actor": {
                "principal_id": username,
                "principal_type": "service_account"
                if username.startswith("system:serviceaccount:")
                else "user",
                "source_ip": (raw.get("sourceIPs") or [None])[0],
                "user_agent": raw.get("userAgent"),
            },
            "resource": {
                # subresource calls and some deletes carry no uid; fall back to a stable name key
                "resource_uid": ref.get("uid") or f"k8s:{resource}:{namespace}:{ref['name']}",
                "kind": _KINDS.get(resource, resource),
                "name": ref["name"],
                "namespace": namespace,
                "labels": meta.get("labels") or {},
                "owner_ref": {k: owner[k] for k in ("kind", "name", "uid")} if owner else None,
            },
            "attributes": attributes,
            "raw": raw,
        }
    )
