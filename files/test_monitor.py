#!/usr/bin/env python
"""Test for new monitoring system with trend simulation"""
from sol_monitor import SolMonitor
import time

print("=== SolMonitor Trend Test ===")
m = SolMonitor()

# Simulate rising CPU
print("\nSimulating rising CPU trend...")
for i in range(10):
    val = 50 + i * 5  # 50, 55, 60, ... 95
    m.cpu_history.append(val)
    trend = m._calculate_trend(m.cpu_history)
    alert = "YES!" if m.should_escalate("cpu", {"cpu_percent": val, "cpu_critical": val > 85}) else "no"
    print("CPU=%d%%, trend=%s, escalate=%s" % (val, trend, alert))

# Simulate stable
print("\nSimulating stable CPU...")
m.cpu_history.clear()
for i in range(10):
    m.cpu_history.append(60)
    trend = m._calculate_trend(m.cpu_history)
    print("Iteration %d: trend=%s" % (i+1, trend))

# Test full metrics
print("\n=== Full Metrics Test ===")
metrics = m.get_all_metrics()
print("All metrics keys: %s" % list(metrics.keys())[:10])

print("\n=== Test Complete ===")
