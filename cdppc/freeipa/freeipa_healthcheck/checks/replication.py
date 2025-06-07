from utils.shell import run_command
from utils.colors import GREEN, RED, NC

def freeipa_cipa_state():
    ret = run_command(["ipa-replica-manage", "list"], capture_output=True)
    if "Replica ID" in ret:
        print(f"{GREEN}CIPA Replication State:\n{ret}{NC}")
    else:
        print(f"{RED}Could not retrieve CIPA replication state.{NC}")

def freeipa_create_ldap_conflict_file():
    # Este es un placeholder, normalmente genera un archivo con conflictos LDAP
    print("Creating LDAP conflict file (stub).")

def freeipa_ldap_conflicts_check():
    # Placeholder para check conflictos LDAP
    print("Checking LDAP conflicts (stub).")

def freeipa_replication_agreements():
    ret = run_command(["ipa-replica-manage", "list-agreements"], capture_output=True)
    if ret:
        print(f"{GREEN}Replication Agreements:\n{ret}{NC}")
    else:
        print(f"{RED}No replication agreements found or error.{NC}")
