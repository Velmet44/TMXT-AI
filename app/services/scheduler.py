from __future__ import annotations

from .models import NodeState


def worker_supports_model(node: NodeState, requested_model: str) -> bool:
    return requested_model in node.models or "*" in node.models


def is_node_eligible(node: NodeState, requested_model: str) -> bool:
    return node.status == "online" and not node.busy and worker_supports_model(node, requested_model)


def score_node(node: NodeState) -> float:
    return (0.6 * node.tokens_per_sec) - (0.02 * node.ping_ms) - (10 * node.fail_rate)
