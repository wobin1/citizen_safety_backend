from datetime import datetime, datetime, timedelta

def dispatch_alert(alert: dict):
    """Mock alert dispatch"""
    print(f"Mock: Dispatching alert {alert['id']} to citizens within {alert['radius_km']}km")

def notify_emergency_services_alert(alert: dict):
    """Mock emergency service notification"""
    print(f"Mock: Notifying services of alert {alert['id']}: {alert['type']}")