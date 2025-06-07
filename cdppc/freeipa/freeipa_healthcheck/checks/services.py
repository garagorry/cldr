from utils.shell import run_command
from utils.colors import GREEN, RED, YELLOW, NC

def freeipa_services_running():
    services = ["ipa", "httpd", "dirsrv", "krb5kdc", "named"]
    for svc in services:
        ret = run_command(["systemctl", "is-active", svc], capture_output=True)
        if ret == "active":
            print(f"{GREEN}Service {svc} is RUNNING{NC}")
        else:
            print(f"{RED}Service {svc} is NOT RUNNING{NC}")
