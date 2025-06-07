from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_health_agent():
    ret = run_command(["systemctl", "is-active", "freeipa-healthcheck"], capture_output=True)
    if ret == "active":
        print(f"{GREEN}FreeIPA Health Agent service is running.{NC}")
    else:
        print(f"{RED}FreeIPA Health Agent service is NOT running.{NC}")
