#!/usr/bin/env python3

import sys
import time
from utils.colors import GREEN, RED, YELLOW, BLUE, NC
from checks import (
    services, status, ports, health_agent, cdp_nsm,
    dns, nginx, backup, replication, control_plane
)
from utils.shell import run_command
from utils.kinit import kinit_authenticate

FREEIPA_DOMAIN = None  # se inicializa más abajo

def clear_screen():
    print("\033c", end="")

def menu_ppal():
    global FREEIPA_DOMAIN
    FREEIPA_DOMAIN = run_command(["salt-call", "pillar.get", "freeipa:domain", "--out=json"], capture_output=True)
    # parsear JSON para extraer dominio
    import json
    try:
        FREEIPA_DOMAIN = json.loads(FREEIPA_DOMAIN).get('local')
    except Exception:
        FREEIPA_DOMAIN = "unknown.domain"

    while True:
        clear_screen()
        print(f"\n#== FREEIPA Health Check for {FREEIPA_DOMAIN} ==#\n")
        print("1) FreeIPA Node Health Check")
        print("2) FreeIPA Support Report")
        print("3) Exit")
        choice = input("Please select an option [1-3]: ").strip()

        if choice == "1":
            main_health_check()
            input("\nPress Enter to return to menu...")
        elif choice == "2":
            print("\n... Preparing the Support Health Check Report ...\n")
            # Aquí invocar la función que crea el reporte usando salt
            # TODO: implementar con asyncio para spinner?
            # Por ahora simplificado
            # Puedes mover lógica desde el bash al módulo python
            # salt '*' cmd.run 'bash /tmp/freeipa_functions_create_report.sh'
            # Guardar salida en archivo y avisar al usuario
            print("Support report creation is not yet implemented.")
            input("\nPress Enter to return to menu...")
        elif choice == "3":
            print(f"\n===> {BLUE}Restoring Default Configuration{NC} <===")
            # TODO: recover_default_salt_master_conf() si aplica
            sys.exit(0)
        else:
            print("\nInvalid option, please try again.")

def main_health_check():
    print(f"\n===> {BLUE}FreeIPA Health Checks{NC} <===\n")

    print(f"{YELLOW}01|01 FreeIPA Required Services{NC}")
    services.freeipa_services_running()

    print(f"\n{YELLOW}01|02 FreeIPA Status{NC}")
    status.freeipa_status()

    print(f"\n{YELLOW}01|03 CDP Node Status Monitor for VMs{NC}")
    cdp_nsm.freeipa_cdp_nsm()

    print(f"\n{YELLOW}02 Required Ports Listening{NC}")
    ports.freeipa_checkports()

    print(f"\n{YELLOW}03 FreeIPA Health Agent Service{NC}")
    health_agent.freeipa_health_agent()

    print(f"\n{YELLOW}04|04 Forward DNS Test{NC}")
    dns.freeipa_forward_dns()

    print(f"\n{YELLOW}04|05 Reverse DNS Test{NC}")
    dns.freeipa_reverse_dns()

    print(f"\n{YELLOW}04|06 Reviewing /etc/nginx/nginx.conf{NC}")
    nginx.freeipa_check_nginx()

    print(f"\n{YELLOW}05 FreeIPA Backups{NC}")
    backup.freeipa_test_backup()

    print(f"\n{YELLOW}06|01 CIPA output{NC}")
    replication.freeipa_cipa_state()

    print(f"\n{YELLOW}06|02 LDAP Conflicts{NC}")
    replication.freeipa_create_ldap_conflict_file()
    replication.freeipa_ldap_conflicts_check()

    print(f"\n{YELLOW}06|03 Replication Agreements{NC}")
    replication.freeipa_replication_agreements()

    print(f"\n{YELLOW}07|01 saltuser password rotation{NC}")
    control_plane.freeipa_check_saltuser_password_rotation()

    print(f"\n{YELLOW}07|02 Control Plane Access{NC}")
    control_plane.freeipa_ccm_network_status()

    print(f"\n{YELLOW}07|03 CCM Available{NC}")
    control_plane.freeipa_ccm()

def prepare_environment():
    # Validar ejecución como root
    import os
    if os.geteuid() != 0:
        print(f"You are not the -->> {RED}root{NC} <<-- user. Please execute: >> {GREEN}sudo -i{NC} << then run this script again.")
        sys.exit(1)
    # Ejecutar kinit
    if not kinit_authenticate():
        print(f"{RED}Kerberos authentication failed. Aborting.{NC}")
        sys.exit(1)
    # Copiar scripts, preparar salt keys, etc
    # TODO: implementar funciones si aplica

def main():
    prepare_environment()
    menu_ppal()

if __name__ == "__main__":
    main()
