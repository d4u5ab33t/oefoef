#!/usr/bin/env python3
"""
idex_kernel.py — IDEX Kernel & Micro-Services Container for SYNAPSE AUDIO DYNAMICS
Location: J:\\Oidasheim\\oefoef\\idex_kernel.py
Motto: "Resonanz erzeugen. Werte erschaffen. Unsterblichkeit codieren."
"""
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Callable

class IDEXKernel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IDEXKernel, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.event_bus: List[Dict[str, Any]] = []
        self.kernel_start_time = time.time()
        self.init_core_nodes()

    def init_core_nodes(self):
        from config import SYNAPSE_NODES
        for name, desc in SYNAPSE_NODES.items():
            self.register_node(name, desc, status="ONLINE")

    def register_node(self, name: str, description: str, status: str = "READY", handler: Callable = None):
        self.nodes[name] = {
            "name": name,
            "description": description,
            "status": status,
            "handler": handler,
            "registered_at": time.time(),
            "execution_count": 0
        }

    def trigger_event(self, event_type: str, payload: Dict[str, Any]):
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "payload": payload
        }
        self.event_bus.append(event)

    def execute_node(self, name: str, *args, **kwargs) -> Any:
        if name not in self.nodes:
            raise KeyError(f"IDEX Node '{name}' nicht im Kernel registriert.")
        node = self.nodes[name]
        node["execution_count"] += 1
        node["status"] = "RUNNING"
        start = time.time()
        result = None
        if node["handler"]:
            result = node["handler"](*args, **kwargs)
        node["status"] = "IDLE"
        duration = time.time() - start
        self.trigger_event("NODE_EXECUTED", {"node": name, "duration_sec": duration})
        return result

    def get_status_dashboard(self) -> Dict[str, Any]:
        return {
            "uptime_sec": time.time() - self.kernel_start_time,
            "active_nodes": len(self.nodes),
            "nodes": {k: {"status": v["status"], "executions": v["execution_count"]} for k, v in self.nodes.items()},
            "events_logged": len(self.event_bus)
        }

def get_kernel() -> IDEXKernel:
    return IDEXKernel()

if __name__ == "__main__":
    kernel = get_kernel()
    print("🧠 IDEX Kernel initialized.")
    print(json.dumps(kernel.get_status_dashboard(), indent=2))
