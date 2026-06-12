"""工作流运行时状态 Redis 存储单元测试。"""

import json
from unittest.mock import MagicMock

from app.services.workflow.runtime_state_store import WorkflowRuntimeStateStore


def test_runtime_store_save_and_get() -> None:
    """保存后应能读取运行时状态。"""
    fake = MagicMock()
    storage: dict[str, str] = {}

    def _setex(key: str, _ttl: int, value: str) -> None:
        storage[key] = value

    def _get(key: str) -> str | None:
        return storage.get(key)

    def _delete(key: str) -> None:
        storage.pop(key, None)

    fake.setex.side_effect = _setex
    fake.get.side_effect = _get
    fake.delete.side_effect = _delete

    store = WorkflowRuntimeStateStore()
    store._redis = fake

    payload = {
        "thread_id": "execution_1",
        "node_statuses": {"scheduler": "completed"},
        "logs": [{"node_id": "scheduler"}],
    }
    store.save(1, payload)
    loaded = store.get(1)
    assert loaded is not None
    assert loaded["thread_id"] == "execution_1"
    assert loaded["node_statuses"]["scheduler"] == "completed"


def test_runtime_store_delete() -> None:
    """删除后应返回 None。"""
    fake = MagicMock()
    storage: dict[str, str] = {"workflow:runtime:2": "{}"}

    fake.get.side_effect = lambda key: storage.get(key)
    fake.delete.side_effect = lambda key: storage.pop(key, None)
    fake.setex.side_effect = lambda key, _ttl, value: storage.__setitem__(key, value)

    store = WorkflowRuntimeStateStore()
    store._redis = fake
    store.save(2, {"thread_id": "execution_2"})
    store.delete(2)
    assert store.get(2) is None


def test_runtime_store_merge_update() -> None:
    """merge_update 应合并字段。"""
    fake = MagicMock()
    storage: dict[str, str] = {}

    fake.setex.side_effect = lambda key, _ttl, value: storage.__setitem__(key, value)
    fake.get.side_effect = lambda key: storage.get(key)

    store = WorkflowRuntimeStateStore()
    store._redis = fake
    store.save(3, {"thread_id": "execution_3", "logs": []})
    merged = store.merge_update(3, {"task_id": "arq-123"})
    assert merged["task_id"] == "arq-123"
    data = json.loads(storage["workflow:runtime:3"])
    assert data["task_id"] == "arq-123"
