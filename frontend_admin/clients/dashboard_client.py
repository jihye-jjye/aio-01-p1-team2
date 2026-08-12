from core.api_client import request


def get_dashboard_process(days: int) -> dict:
    return request("GET", "/admin/dashboard", params={"days": days}, role="ADMIN")
