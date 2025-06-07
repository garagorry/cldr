from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_forward_dns():
    domain = "example.com"  # Ajustar con dominio real
    ret = run_command(["dig", "+short", domain], capture_output=True)
    if ret:
        print(f"{GREEN}Forward DNS lookup for {domain}: {ret}{NC}")
    else:
        print(f"{RED}Forward DNS lookup failed for {domain}.{NC}")

def freeipa_reverse_dns():
    ip = "127.0.0.1"  # Ajustar con IP real
    ret = run_command(["dig", "-x", ip, "+short"], capture_output=True)
    if ret:
        print(f"{GREEN}Reverse DNS lookup for {ip}: {ret}{NC}")
    else:
        print(f"{RED}Reverse DNS lookup failed for {ip}.{NC}")
