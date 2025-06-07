from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_check_nginx():
    ret = run_command(["cat", "/etc/nginx/nginx.conf"], capture_output=True)
    if "error_log" in ret:
        print(f"{GREEN}Nginx configuration found and readable.{NC}")
    else:
        print(f"{RED}Nginx configuration missing or unreadable.{NC}")
