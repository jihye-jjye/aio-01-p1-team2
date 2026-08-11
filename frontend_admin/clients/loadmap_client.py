from core.api_client import request

def loadmap_from_user(login_id : str):
    return request("GET", f"admin/users/by-login-id/{login_id}/roadmaps", role="ADMIN")