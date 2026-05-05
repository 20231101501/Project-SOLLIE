"""
Sol Monitor - Advanced system monitoring with Jarvis-style proactive features
"""

import time
import psutil
from datetime import datetime
from collections import deque


class SolMonitor:
    """Advanced system monitoring with trend detection and multi-level alerts"""

    def __init__(self, config=None):
        self.config = config or {}
        self.monitoring_config = self.config.get("monitoring", {})
        self.metrics_config = self.monitoring_config.get("metrics", {})

        # History for trend detection (store last N readings)
        self.cpu_history = deque(maxlen=60)  # 60 readings ~ 5 min at 5s intervals
        self.memory_history = deque(maxlen=60)
        self.disk_history = deque(maxlen=60)
        self.network_history = deque(maxlen=60)

        # Persistence tracking
        self.alert_start_times = {}  # metric -> timestamp when alert first triggered
        self.last_alert_levels = {}  # metric -> last alert level (warning/critical)

        # Network baseline
        self._last_net_io = None
        self._last_net_time = None

        # Try to import optional libraries
        self.gputil_available = False
        try:
            import GPUtil
            self.GPUtil = GPUtil
            self.gputil_available = True
        except ImportError:
            pass

    def get_all_metrics(self):
        """Collect all system metrics in one call"""
        metrics = {}

        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        metrics["cpu_percent"] = cpu_percent
        metrics["cpu_warning"] = self._check_threshold("cpu", cpu_percent, "warning")
        metrics["cpu_critical"] = self._check_threshold("cpu", cpu_percent, "critical")

        # Memory
        memory = psutil.virtual_memory()
        metrics["memory_percent"] = memory.percent
        metrics["memory_used_gb"] = memory.used / (1024 ** 3)
        metrics["memory_total_gb"] = memory.total / (1024 ** 3)
        metrics["memory_warning"] = self._check_threshold("memory", memory.percent, "warning")
        metrics["memory_critical"] = self._check_threshold("memory", memory.percent, "critical")

        # Disk
        disk = psutil.disk_usage('/')
        metrics["disk_percent"] = disk.percent
        metrics["disk_free_gb"] = disk.free / (1024 ** 3)
        metrics["disk_total_gb"] = disk.total / (1024 ** 3)
        metrics["disk_warning"] = self._check_threshold("disk", disk.percent, "warning")
        metrics["disk_critical"] = self._check_threshold("disk", disk.percent, "critical")

        # Disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics["disk_read_bytes"] = disk_io.read_bytes
                metrics["disk_write_bytes"] = disk_io.write_bytes
        except Exception:
            pass

        # Network
        net_metrics = self._get_network_metrics()
        metrics.update(net_metrics)

        # Battery
        battery_metrics = self._get_battery_metrics()
        metrics.update(battery_metrics)

        # Top processes
        metrics["top_cpu_processes"] = self._get_top_processes("cpu", 5)
        metrics["top_memory_processes"] = self._get_top_processes("memory", 5)

        # GPU (if available)
        gpu_metrics = self._get_gpu_metrics()
        metrics.update(gpu_metrics)

        # Update history
        self._update_history(metrics)

        # Add trend info
        metrics["cpu_trend"] = self._calculate_trend(self.cpu_history)
        metrics["memory_trend"] = self._calculate_trend(self.memory_history)

        return metrics

    def _check_threshold(self, metric, value, level):
        """Check if metric exceeds threshold for given level (warning/critical)"""
        metric_config = self.metrics_config.get(metric, {})
        threshold = metric_config.get(level, self._get_default_threshold(metric, level))
        return value >= threshold

    def _get_default_threshold(self, metric, level):
        """Fallback default thresholds"""
        defaults = {
            "cpu": {"warning": 70, "critical": 85},
            "memory": {"warning": 75, "critical": 85},
            "disk": {"warning": 80, "critical": 90}
        }
        return defaults.get(metric, {}).get(level, 80)

    def _get_network_metrics(self):
        """Get network upload/download speeds"""
        metrics = {}
        try:
            net_io = psutil.net_io_counters()
            now = time.time()

            if self._last_net_io and self._last_net_time:
                duration = now - self._last_net_time
                if duration > 0:
                    upload_speed = (net_io.bytes_sent - self._last_net_io.bytes_sent) / duration
                    download_speed = (net_io.bytes_recv - self._last_net_io.bytes_recv) / duration
                    metrics["network_upload_mbps"] = upload_speed / (1024 ** 2)
                    metrics["network_download_mbps"] = download_speed / (1024 ** 2)

            self._last_net_io = net_io
            self._last_net_time = now
        except Exception:
            pass

        return metrics

    def _get_battery_metrics(self):
        """Get battery status (for laptops)"""
        metrics = {}
        try:
            battery = psutil.sensors_battery()
            if battery:
                metrics["battery_percent"] = battery.percent
                metrics["battery_plugged"] = battery.power_plugged
                metrics["battery_low"] = battery.percent <= 20 and not battery.power_plugged
        except Exception:
            pass
        return metrics

    def _get_top_processes(self, sort_by="cpu", count=5):
        """Get top processes by CPU or memory usage"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    if pinfo['cpu_percent'] is not None or pinfo['memory_percent'] is not None:
                        processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            return []

        if sort_by == "cpu":
            processes.sort(key=lambda x: x.get('cpu_percent') or 0, reverse=True)
        else:
            processes.sort(key=lambda x: x.get('memory_percent') or 0, reverse=True)

        return processes[:count]

    def _get_gpu_metrics(self):
        """Get GPU metrics if GPUtil is available"""
        metrics = {}
        if not self.gputil_available:
            return metrics

        try:
            gpus = self.GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Primary GPU
                metrics["gpu_load"] = gpu.load * 100
                metrics["gpu_temp"] = gpu.temperature
                metrics["gpu_memory_percent"] = gpu.memoryUtil * 100
        except Exception:
            pass

        return metrics

    def _update_history(self, metrics):
        """Update metric history for trend detection"""
        self.cpu_history.append(metrics.get("cpu_percent", 0))
        self.memory_history.append(metrics.get("memory_percent", 0))
        self.disk_history.append(metrics.get("disk_percent", 0))

    def _calculate_trend(self, history):
        """Calculate if metric is trending up, down, or stable"""
        if len(history) < 5:
            return "stable"

        recent = list(history)[-5:]
        # Simple linear trend
        x = list(range(len(recent)))
        y = recent

        # Calculate slope
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)

        if slope > 1.5:
            return "rising"
        elif slope < -1.5:
            return "falling"
        else:
            return "stable"

    def check_persistent_alert(self, metric, metrics):
        """Check if a metric has been in alert state persistently"""
        value = metrics.get(f"{metric}_percent", 0)
        is_critical = metrics.get(f"{metric}_critical", False)
        is_warning = metrics.get(f"{metric}_warning", False)

        current_time = time.time()

        if is_critical or is_warning:
            if metric not in self.alert_start_times:
                self.alert_start_times[metric] = current_time
                return False  # Just started

            duration = current_time - self.alert_start_times[metric]
            return duration > 120  # Persistent if > 2 minutes
        else:
            # Clear the alert state
            if metric in self.alert_start_times:
                del self.alert_start_times[metric]
            return False

    def get_alert_level(self, metric, metrics):
        """Get the appropriate alert level for a metric"""
        if metrics.get(f"{metric}_critical", False):
            return "critical"
        elif metrics.get(f"{metric}_warning", False):
            return "warning"
        return None

    def should_escalate(self, metric, metrics):
        """Check if alert should be escalated (persistent + trending up)"""
        persistent = self.check_persistent_alert(metric, metrics)
        trend = metrics.get(f"{metric}_trend", "stable")
        return persistent and trend == "rising"
