"""Monitoring and observability module.

This module provides:
- Metrics collection (request counts, latency, error rates)
- Structured logging with JSON format
- Health check dependency status
- Cloud Monitoring integration
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from collections import defaultdict
from threading import Lock

# Try to import Cloud Monitoring (optional)
try:
    from google.cloud import monitoring_v3
    from google.api import metric_pb2
    CLOUD_MONITORING_AVAILABLE = True
except ImportError:
    CLOUD_MONITORING_AVAILABLE = False


@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    timestamp: str


class MetricsCollector:
    """Collects and aggregates application metrics."""
    
    def __init__(self):
        self._request_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._latencies = defaultdict(list)
        self._lock = Lock()
        self._total_requests = 0
        self._total_errors = 0
        
    def record_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        latency_ms: float = 0.0
    ):
        """Record a request metric.
        
        Args:
            endpoint: The endpoint path (e.g., "/ask", "/health")
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code
            latency_ms: Request latency in milliseconds
        """
        with self._lock:
            self._total_requests += 1
            key = f"{method} {endpoint}"
            self._request_counts[key] += 1
            
            if status_code >= 400:
                self._error_counts[key] += 1
                self._total_errors += 1
            
            self._latencies[key].append(latency_ms)
            # Keep only last 1000 latencies per endpoint
            if len(self._latencies[key]) > 1000:
                self._latencies[key] = self._latencies[key][-1000:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics.
        
        Returns:
            Dictionary with request counts, error rates, and latency stats
        """
        with self._lock:
            stats = {
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": (
                    self._total_errors / self._total_requests
                    if self._total_requests > 0
                    else 0.0
                ),
                "endpoints": {}
            }
            
            for key in self._request_counts:
                latencies = self._latencies.get(key, [])
                stats["endpoints"][key] = {
                    "count": self._request_counts[key],
                    "errors": self._error_counts.get(key, 0),
                    "error_rate": (
                        self._error_counts.get(key, 0) / self._request_counts[key]
                        if self._request_counts[key] > 0
                        else 0.0
                    ),
                    "avg_latency_ms": (
                        sum(latencies) / len(latencies)
                        if latencies
                        else 0.0
                    ),
                    "p50_latency_ms": (
                        sorted(latencies)[len(latencies) // 2]
                        if latencies
                        else 0.0
                    ),
                    "p95_latency_ms": (
                        sorted(latencies)[int(len(latencies) * 0.95)]
                        if latencies
                        else 0.0
                    ),
                    "p99_latency_ms": (
                        sorted(latencies)[int(len(latencies) * 0.99)]
                        if latencies
                        else 0.0
                    ),
                }
            
            return stats
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._request_counts.clear()
            self._error_counts.clear()
            self._latencies.clear()
            self._total_requests = 0
            self._total_errors = 0


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


class StructuredLogger:
    """Structured JSON logger for better observability."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with structured data."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": logging.getLevelName(level),
            "logger": self.name,
            "message": message,
            **kwargs
        }
        
        # Use JSON format if structured logging is enabled
        if os.environ.get("STRUCTURED_LOGGING", "false").lower() == "true":
            self.logger.log(level, json.dumps(log_data))
        else:
            # Human-readable format
            extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.log(level, f"{message} {extra_info}".strip())
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self._log(logging.ERROR, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with structured data."""
        self._log(logging.ERROR, message, exc_info=True, **kwargs)


class HealthChecker:
    """Health check with dependency status."""
    
    def __init__(self):
        self.dependencies: Dict[str, callable] = {}
    
    def register_dependency(self, name: str, check_func: callable):
        """Register a dependency health check.
        
        Args:
            name: Dependency name (e.g., "rag_backend", "gemini_api")
            check_func: Async function that returns (healthy: bool, message: str)
        """
        self.dependencies[name] = check_func
    
    async def check_all(self) -> Dict[str, Any]:
        """Check all registered dependencies.
        
        Returns:
            Dictionary with overall status and individual dependency statuses
        """
        results = {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "dependencies": {}
        }
        
        all_healthy = True
        for name, check_func in self.dependencies.items():
            try:
                healthy, message = await check_func()
                results["dependencies"][name] = {
                    "status": "healthy" if healthy else "unhealthy",
                    "message": message
                }
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results["dependencies"][name] = {
                    "status": "error",
                    "message": str(e)
                }
                all_healthy = False
        
        if not all_healthy:
            results["status"] = "degraded"
        
        return results


class CloudMonitoringExporter:
    """Exports metrics to Google Cloud Monitoring."""
    
    def __init__(self, project_id: Optional[str] = None):
        if not CLOUD_MONITORING_AVAILABLE:
            raise ImportError(
                "google-cloud-monitoring is not installed. "
                "Install with: pip install google-cloud-monitoring"
            )
        
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self.project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Cloud Monitoring")
        
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{self.project_id}"
    
    def write_metric(
        self,
        metric_type: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Write a metric to Cloud Monitoring.
        
        Args:
            metric_type: Metric type (e.g., "custom.googleapis.com/api/request_count")
            value: Metric value
            labels: Optional labels for the metric
        """
        series = monitoring_v3.TimeSeries()
        series.metric.type = metric_type
        series.resource.type = "global"
        
        if labels:
            for key, value in labels.items():
                series.metric.labels[key] = value
        
        point = monitoring_v3.Point()
        point.value.double_value = value
        point.interval.end_time.seconds = int(time.time())
        point.interval.end_time.nanos = int((time.time() % 1) * 1e9)
        
        series.points = [point]
        
        try:
            self.client.create_time_series(
                name=self.project_name,
                time_series=[series]
            )
        except Exception as e:
            # Log but don't fail on monitoring errors
            logging.warning(f"Failed to write metric to Cloud Monitoring: {e}")


def create_structured_logger(name: str) -> StructuredLogger:
    """Create a structured logger instance."""
    return StructuredLogger(name)

