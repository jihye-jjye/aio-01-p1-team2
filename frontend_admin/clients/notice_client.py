from core.api_client import request

def notice_all_process():
    return request("GET", "/admin/notices", role="ADMIN")