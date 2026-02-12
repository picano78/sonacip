#!/usr/bin/env python3
"""
Script per recuperare le credenziali del Super Admin dai log di SONACIP.

Questo script cerca nei log dell'applicazione le credenziali generate
automaticamente al primo avvio.

Uso:
    python recupera_credenziali.py
    python recupera_credenziali.py --log-file /percorso/custom/log.txt
"""

import argparse
import os
import re
import subprocess
import sys


def search_in_file(filepath):
    """Cerca le credenziali in un file di log."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Cerca il blocco di credenziali generate
        pattern = r'Generated Super Admin credentials:.*?Email:\s*(.+?)\s*Password:\s*(.+?)(?:\s*COPY|$)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            return matches
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"⚠️  Errore durante la lettura del file {filepath}: {e}")
        return None


def search_in_journalctl():
    """Cerca le credenziali nei log di systemd (journalctl)."""
    try:
        # Cerca negli ultimi 1000 log del servizio sonacip
        result = subprocess.run(
            ['journalctl', '-u', 'sonacip', '-n', '1000', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None
            
        content = result.stdout
        pattern = r'Generated Super Admin credentials:.*?Email:\s*(.+?)\s*Password:\s*(.+?)(?:\s*COPY|$)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            return matches
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Recupera le credenziali del Super Admin dai log di SONACIP'
    )
    parser.add_argument(
        '--log-file',
        help='Percorso personalizzato del file di log da analizzare'
    )
    parser.add_argument(
        '--all-logs',
        action='store_true',
        help='Cerca in tutti i possibili file di log'
    )
    
    args = parser.parse_args()
    
    print("🔍 Ricerca credenziali Super Admin nei log...")
    print()
    
    credentials_found = False
    
    # Se specificato un file personalizzato
    if args.log_file:
        print(f"📄 Controllo file: {args.log_file}")
        matches = search_in_file(args.log_file)
        if matches:
            credentials_found = True
            print("\n✅ CREDENZIALI TROVATE!\n")
            for i, (email, password) in enumerate(matches, 1):
                print(f"Set #{i}:")
                print(f"  Email:    {email.strip()}")
                print(f"  Password: {password.strip()}")
                print()
    
    # Altrimenti cerca in varie posizioni
    else:
        # Lista di possibili percorsi di log
        log_paths = [
            'logs/sonacip.log',
            '/var/log/sonacip/sonacip.log',
            '/var/log/sonacip/startup.log',
            '/opt/sonacip/logs/sonacip.log',
        ]
        
        # Cerca in tutti i file di log
        for log_path in log_paths:
            if os.path.exists(log_path):
                print(f"📄 Controllo file: {log_path}")
                matches = search_in_file(log_path)
                if matches:
                    credentials_found = True
                    print("\n✅ CREDENZIALI TROVATE!\n")
                    for i, (email, password) in enumerate(matches, 1):
                        if len(matches) > 1:
                            print(f"Set #{i}:")
                        print(f"  Email:    {email.strip()}")
                        print(f"  Password: {password.strip()}")
                        print()
        
        # Prova anche con journalctl se disponibile
        if not credentials_found:
            print("📄 Controllo journalctl (systemd)...")
            matches = search_in_journalctl()
            if matches:
                credentials_found = True
                print("\n✅ CREDENZIALI TROVATE!\n")
                for i, (email, password) in enumerate(matches, 1):
                    if len(matches) > 1:
                        print(f"Set #{i}:")
                    print(f"  Email:    {email.strip()}")
                    print(f"  Password: {password.strip()}")
                    print()
    
    if not credentials_found:
        print("❌ Credenziali non trovate nei log.")
        print()
        print("Possibili cause:")
        print("  1. Le credenziali sono state impostate manualmente tramite SUPERADMIN_EMAIL")
        print("     e SUPERADMIN_PASSWORD (controlla il file .env)")
        print("  2. I log sono stati cancellati o ruotati")
        print("  3. I file di log sono in una posizione diversa")
        print()
        print("Soluzioni:")
        print("  1. Controlla il file .env per vedere se le credenziali sono impostate lì")
        print("  2. Esegui: python manage.py check-admin")
        print("     per verificare gli utenti admin esistenti")
        print("  3. Reimposta le credenziali seguendo la guida in FAQ_CREDENZIALI_ADMIN.md")
        print()
        print("Per specificare un percorso di log personalizzato:")
        print("  python recupera_credenziali.py --log-file /percorso/al/tuo/log.txt")
        return 1
    
    print("⚠️  IMPORTANTE:")
    print("  - Copia queste credenziali in un luogo sicuro")
    print("  - Cambia la password dopo il primo accesso")
    print("  - Considera di impostare SUPERADMIN_PASSWORD in .env per il futuro")
    print()
    print("📖 Per maggiori informazioni: FAQ_CREDENZIALI_ADMIN.md")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
