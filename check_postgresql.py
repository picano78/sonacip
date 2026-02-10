#!/usr/bin/env python3
"""
Script per verificare l'installazione e configurazione di PostgreSQL per SONACIP.
Controlla che PostgreSQL sia installato, il database sia creato e accessibile.
"""
from __future__ import annotations

import os
import sys
import subprocess
from typing import Tuple

# Colori per output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(title: str) -> None:
    """Stampa un header formattato."""
    print(f'\n{BLUE}{"=" * 70}')
    print(f'  {title}')
    print(f'{"=" * 70}{RESET}')


def check_success(message: str) -> None:
    """Stampa un messaggio di successo."""
    print(f'{GREEN}✓{RESET} {message}')


def check_failure(message: str) -> None:
    """Stampa un messaggio di errore."""
    print(f'{RED}✗{RESET} {message}')


def check_warning(message: str) -> None:
    """Stampa un messaggio di warning."""
    print(f'{YELLOW}⚠{RESET} {message}')


def check_postgresql_installed() -> Tuple[bool, str]:
    """Verifica se PostgreSQL è installato nel sistema."""
    print_header('VERIFICA INSTALLAZIONE POSTGRESQL')
    
    # Controlla se psql è disponibile
    try:
        result = subprocess.run(
            ['which', 'psql'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            psql_path = result.stdout.strip()
            check_success(f'PostgreSQL client trovato: {psql_path}')
            
            # Ottieni versione
            version_result = subprocess.run(
                ['psql', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if version_result.returncode == 0:
                version = version_result.stdout.strip()
                check_success(f'Versione: {version}')
            
            return True, psql_path
        else:
            check_failure('PostgreSQL client (psql) non trovato')
            check_warning('Installa PostgreSQL con: sudo apt install postgresql postgresql-contrib')
            return False, ''
    except Exception as e:
        check_failure(f'Errore nella verifica di PostgreSQL: {e}')
        return False, ''


def check_postgresql_service() -> bool:
    """Verifica se il servizio PostgreSQL è attivo."""
    print_header('VERIFICA SERVIZIO POSTGRESQL')
    
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'postgresql'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip() == 'active':
            check_success('Servizio PostgreSQL è attivo')
            return True
        else:
            check_failure('Servizio PostgreSQL non è attivo')
            check_warning('Avvia PostgreSQL con: sudo systemctl start postgresql')
            return False
    except FileNotFoundError:
        check_warning('systemctl non disponibile (non systemd?)')
        # Prova con pg_isready
        try:
            result = subprocess.run(
                ['pg_isready'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                check_success('PostgreSQL server risponde (verificato con pg_isready)')
                return True
            else:
                check_failure('PostgreSQL server non risponde')
                return False
        except Exception:
            check_warning('Impossibile verificare stato servizio')
            return False
    except Exception as e:
        check_failure(f'Errore nella verifica del servizio: {e}')
        return False


def check_database_url_configured() -> Tuple[bool, str]:
    """Verifica se DATABASE_URL è configurato."""
    print_header('VERIFICA CONFIGURAZIONE DATABASE_URL')
    
    # Prova a caricare da .env
    env_file = '.env'
    database_url = os.environ.get('DATABASE_URL', '')
    
    if os.path.exists(env_file):
        check_success(f'File .env trovato: {env_file}')
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DATABASE_URL=') and not line.startswith('#'):
                        database_url = line.split('=', 1)[1].strip()
                        break
        except Exception as e:
            check_warning(f'Errore nella lettura del file .env: {e}')
    else:
        check_warning(f'File .env non trovato (path: {os.path.abspath(env_file)})')
    
    if database_url:
        # Oscura password nell'output
        display_url = database_url
        if '@' in database_url and ':' in database_url:
            parts = database_url.split('@')
            if len(parts) == 2:
                credentials = parts[0].split('//')[-1]
                if ':' in credentials:
                    user = credentials.split(':')[0]
                    display_url = database_url.replace(credentials, f'{user}:****')
        
        check_success(f'DATABASE_URL configurato: {display_url}')
        
        if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
            check_success('DATABASE_URL utilizza PostgreSQL')
            return True, database_url
        else:
            check_warning(f'DATABASE_URL non utilizza PostgreSQL (utilizza: {database_url.split(":")[0]})')
            return False, database_url
    else:
        check_warning('DATABASE_URL non configurato (verrà usato SQLite di default)')
        check_warning('Per usare PostgreSQL, configura DATABASE_URL in .env')
        return False, ''


def parse_database_url(url: str) -> dict:
    """Parse PostgreSQL URL per estrarre componenti."""
    # Formato: postgresql://user:password@host:port/database
    try:
        # Rimuovi schema
        url = url.replace('postgresql://', '').replace('postgres://', '')
        
        # Separa credenziali e host
        if '@' in url:
            credentials, rest = url.split('@', 1)
            if ':' in credentials:
                user, password = credentials.split(':', 1)
            else:
                user = credentials
                password = ''
        else:
            user = 'postgres'
            password = ''
            rest = url
        
        # Separa host e database
        if '/' in rest:
            host_port, database = rest.split('/', 1)
        else:
            host_port = rest
            database = ''
        
        # Separa host e porta
        if ':' in host_port:
            host, port = host_port.split(':', 1)
        else:
            host = host_port
            port = '5432'
        
        return {
            'user': user,
            'password': password,
            'host': host,
            'port': port,
            'database': database
        }
    except Exception as e:
        print(f'Errore nel parsing di DATABASE_URL: {e}')
        return {}


def check_database_connection(database_url: str) -> bool:
    """Verifica la connessione al database PostgreSQL."""
    print_header('VERIFICA CONNESSIONE DATABASE')
    
    if not database_url:
        check_warning('DATABASE_URL non fornito, skip verifica connessione')
        return False
    
    db_params = parse_database_url(database_url)
    if not db_params:
        check_failure('Impossibile parsare DATABASE_URL')
        return False
    
    user = db_params.get('user', 'postgres')
    host = db_params.get('host', 'localhost')
    port = db_params.get('port', '5432')
    database = db_params.get('database', '')
    password = db_params.get('password', '')
    
    check_success(f'Database: {database}')
    check_success(f'Host: {host}:{port}')
    check_success(f'User: {user}')
    
    # Tenta connessione con psycopg2
    try:
        import psycopg2
        check_success('Modulo psycopg2 disponibile')
        
        # Prova connessione
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                connect_timeout=5
            )
            check_success(f'Connessione al database "{database}" riuscita!')
            
            # Verifica alcune informazioni
            cursor = conn.cursor()
            cursor.execute('SELECT version();')
            version = cursor.fetchone()[0]
            check_success(f'PostgreSQL server: {version[:50]}...')
            
            # Controlla permessi
            cursor.execute("""
                SELECT has_database_privilege(%s, %s, 'CREATE')
            """, (user, database))
            has_create = cursor.fetchone()[0]
            if has_create:
                check_success(f'Utente {user} ha permessi CREATE sul database')
            else:
                check_warning(f'Utente {user} NON ha permessi CREATE sul database')
            
            cursor.close()
            conn.close()
            return True
            
        except psycopg2.OperationalError as e:
            check_failure(f'Impossibile connettersi al database: {e}')
            check_warning('Verifica che:')
            print(f'  - Il database "{database}" esista')
            print(f'  - L\'utente "{user}" abbia accesso')
            print(f'  - La password sia corretta')
            print(f'  - PostgreSQL accetti connessioni su {host}:{port}')
            return False
        except Exception as e:
            check_failure(f'Errore durante la connessione: {e}')
            return False
            
    except ImportError:
        check_failure('Modulo psycopg2 non disponibile')
        check_warning('Installa con: pip install psycopg2-binary')
        return False


def check_database_tables(database_url: str) -> bool:
    """Verifica se le tabelle del database sono create."""
    print_header('VERIFICA TABELLE DATABASE')
    
    if not database_url or not (database_url.startswith('postgresql://') or database_url.startswith('postgres://')):
        check_warning('Skip verifica tabelle (non PostgreSQL)')
        return False
    
    try:
        import psycopg2
        
        db_params = parse_database_url(database_url)
        conn = psycopg2.connect(
            host=db_params.get('host', 'localhost'),
            port=db_params.get('port', '5432'),
            user=db_params.get('user', 'postgres'),
            password=db_params.get('password', ''),
            database=db_params.get('database', ''),
            connect_timeout=5
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            check_success(f'Trovate {len(tables)} tabelle nel database')
            print(f'\n  Tabelle presenti:')
            for table in tables[:10]:  # Mostra prime 10
                print(f'    - {table[0]}')
            if len(tables) > 10:
                print(f'    ... e altre {len(tables) - 10} tabelle')
        else:
            check_warning('Nessuna tabella trovata nel database')
            check_warning('Esegui inizializzazione con: python init_db.py')
        
        cursor.close()
        conn.close()
        return len(tables) > 0
        
    except Exception as e:
        check_failure(f'Errore nella verifica delle tabelle: {e}')
        return False


def print_setup_instructions():
    """Stampa le istruzioni per configurare PostgreSQL."""
    print_header('ISTRUZIONI SETUP POSTGRESQL')
    
    print(f"""
{YELLOW}Per configurare PostgreSQL per SONACIP:{RESET}

1. Installa PostgreSQL:
   sudo apt update
   sudo apt install postgresql postgresql-contrib libpq-dev

2. Crea database e utente:
   sudo -u postgres psql
   CREATE USER sonacip WITH PASSWORD 'tua_password_sicura';
   CREATE DATABASE sonacip OWNER sonacip;
   GRANT ALL PRIVILEGES ON DATABASE sonacip TO sonacip;
   \\q

3. Configura DATABASE_URL nel file .env:
   DATABASE_URL=postgresql://sonacip:tua_password_sicura@localhost:5432/sonacip

4. Inizializza il database:
   python init_db.py

5. Verifica l'installazione:
   python check_postgresql.py

{BLUE}Per maggiori dettagli, consulta: deploy/GUIDA_VPS.md{RESET}
""")


def main() -> int:
    """Funzione principale."""
    print(f'\n{BLUE}╔{"═" * 68}╗')
    print(f'║{" " * 16}VERIFICA POSTGRESQL PER SONACIP{" " * 21}║')
    print(f'╚{"═" * 68}╝{RESET}')
    
    checks_passed = 0
    checks_failed = 0
    checks_warning = 0
    
    # 1. Verifica installazione PostgreSQL
    pg_installed, psql_path = check_postgresql_installed()
    if pg_installed:
        checks_passed += 1
    else:
        checks_failed += 1
    
    # 2. Verifica servizio PostgreSQL
    if pg_installed:
        service_active = check_postgresql_service()
        if service_active:
            checks_passed += 1
        else:
            checks_failed += 1
    else:
        check_warning('Skip verifica servizio (PostgreSQL non installato)')
        checks_warning += 1
    
    # 3. Verifica configurazione DATABASE_URL
    db_configured, database_url = check_database_url_configured()
    if db_configured:
        checks_passed += 1
    else:
        checks_warning += 1
    
    # 4. Verifica connessione database
    if db_configured and pg_installed:
        conn_ok = check_database_connection(database_url)
        if conn_ok:
            checks_passed += 1
        else:
            checks_failed += 1
    else:
        check_warning('Skip verifica connessione database')
        checks_warning += 1
    
    # 5. Verifica tabelle database
    if db_configured and pg_installed:
        tables_ok = check_database_tables(database_url)
        if tables_ok:
            checks_passed += 1
        else:
            checks_warning += 1
    
    # Riepilogo
    print_header('RIEPILOGO VERIFICHE')
    print(f'{GREEN}✓ Verifiche superate: {checks_passed}{RESET}')
    if checks_failed > 0:
        print(f'{RED}✗ Verifiche fallite: {checks_failed}{RESET}')
    if checks_warning > 0:
        print(f'{YELLOW}⚠ Warning: {checks_warning}{RESET}')
    
    # Determina esito
    if checks_failed == 0 and checks_passed >= 3:
        print(f'\n{GREEN}{"=" * 70}')
        print(f'  ✓ PostgreSQL è installato e configurato correttamente!')
        print(f'{"=" * 70}{RESET}\n')
        return 0
    elif checks_failed > 0:
        print(f'\n{RED}{"=" * 70}')
        print(f'  ✗ Ci sono problemi con la configurazione PostgreSQL')
        print(f'{"=" * 70}{RESET}')
        print_setup_instructions()
        return 1
    else:
        print(f'\n{YELLOW}{"=" * 70}')
        print(f'  ⚠ PostgreSQL non è configurato (verrà usato SQLite)')
        print(f'{"=" * 70}{RESET}')
        print_setup_instructions()
        return 2


if __name__ == '__main__':
    sys.exit(main())
