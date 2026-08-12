from core.api_client import BackendAPIError, request

def get_recruitment_notice_process():
    return request("GET", "/admin/saved-jobs", role="ADMIN")