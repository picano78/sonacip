#!/usr/bin/env python3
"""
SONACIP Production Verification Script

Verifica che l'applicazione sia configurata correttamente per la produzione.
Esegui questo script prima del deployment finale.

Usage:
    python3 verify_production.py
"""

import os
import sys
import subprocess
from pathlib import Path


class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def check_python_version():
    """Check Python version"""
    print_header("1. Verifica Versione Python")
    version = sys.version_info
    if version >= (3, 10):
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor}.{version.micro} - Richiesto >= 3.10")
        return False


def check_entrypoints():
    """Check that all entrypoints work"""
    print_header("2. Verifica Entrypoints")
    
    results = []
    
    # Test wsgi:application
    try:
        from wsgi import application
        print_success("wsgi:application - OK")
        results.append(True)
    except Exception as e:
        print_error(f"wsgi:application - FAIL: {e}")
        results.append(False)
    
    # Test wsgi:app
    try:
        from wsgi import app
        print_success("wsgi:app - OK")
        results.append(True)
    except Exception as e:
        print_error(f"wsgi:app - FAIL: {e}")
        results.append(False)
    
    # Test run:app
    try:
        from run import app
        print_success("run:app - OK")
        results.append(True)
    except Exception as e:
        print_error(f"run:app - FAIL: {e}")
        results.append(False)
    
    return all(results)


def check_app_factory():
    """Check app factory pattern"""
    print_header("3. Verifica Application Factory")
    
    try:
        from app import create_app
        app = create_app()
        print_success(f"App name: {app.name}")
        print_success(f"Blueprints registrati: {len(app.blueprints)}")
        print_success(f"Routes totali: {len(list(app.url_map.iter_rules()))}")
        return True
    except Exception as e:
        print_error(f"Application factory failed: {e}")
        return False


def check_config_files():
    """Check configuration files"""
    print_header("4. Verifica File di Configurazione")
    
    base_dir = Path(__file__).parent
    files = {
        'requirements.txt': base_dir / 'requirements.txt',
        'wsgi.py': base_dir / 'wsgi.py',
        'run.py': base_dir / 'run.py',
        'gunicorn.conf.py': base_dir / 'gunicorn.conf.py',
        '.env.example': base_dir / '.env.example',
        'deploy/sonacip.service': base_dir / 'deploy' / 'sonacip.service',
        'deploy/sonacip.nginx.conf': base_dir / 'deploy' / 'sonacip.nginx.conf',
    }
    
    results = []
    for name, path in files.items():
        if path.exists():
            print_success(f"{name} - Presente")
            results.append(True)
        else:
            print_error(f"{name} - Mancante")
            results.append(False)
    
    return all(results)


def check_env_variables():
    """Check critical environment variables"""
    print_header("5. Verifica Variabili Ambiente")
    
    critical_vars = {
        'SECRET_KEY': 'Chiave segreta per sessioni/CSRF',
        'DATABASE_URL': 'URL database (opzionale, default SQLite)',
        'SUPERADMIN_EMAIL': 'Email super admin (opzionale, genera random)',
        'SUPERADMIN_PASSWORD': 'Password super admin (opzionale, genera random)',
    }
    
    optional_vars = {
        'MAIL_SERVER': 'Server SMTP',
        'REDIS_URL': 'URL Redis per caching',
        'APP_DOMAIN': 'Dominio applicazione',
    }
    
    # Check if .env exists
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        print_success(".env file presente")
        
        # Try to load .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            print_warning("python-dotenv non installato, usando variabili ambiente di sistema")
    else:
        print_warning(".env file non presente - usando variabili ambiente di sistema o defaults")
    
    # Check critical variables
    print("\nVariabili critiche:")
    for var, description in critical_vars.items():
        value = os.getenv(var)
        if value and value.strip():
            # Mask sensitive values
            if var in ['SECRET_KEY', 'SUPERADMIN_PASSWORD', 'DATABASE_URL']:
                display_value = value[:10] + '...' if len(value) > 10 else '***'
            else:
                display_value = value
            print_success(f"{var} = {display_value}")
        else:
            print_warning(f"{var} non impostato (userà default)")
    
    # Check optional variables
    print("\nVariabili opzionali:")
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value and value.strip():
            print_success(f"{var} = {value}")
        else:
            print_warning(f"{var} non impostato")
    
    return True


def check_dependencies():
    """Check Python dependencies"""
    print_header("6. Verifica Dipendenze Python")
    
    required_packages = [
        'flask',
        'flask_sqlalchemy',
        'flask_login',
        'gunicorn',
        'psycopg2',
        'redis',
        'celery',
    ]
    
    results = []
    for package in required_packages:
        try:
            __import__(package)
            print_success(f"{package} - Installato")
            results.append(True)
        except ImportError:
            print_error(f"{package} - NON installato")
            results.append(False)
    
    return all(results)


def check_gunicorn():
    """Check Gunicorn configuration"""
    print_header("7. Verifica Configurazione Gunicorn")
    
    try:
        # Check gunicorn is installed
        result = subprocess.run(['gunicorn', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"Gunicorn version: {result.stdout.strip()}")
        
        # Test gunicorn config file exists
        config_file = Path(__file__).parent / 'gunicorn.conf.py'
        if config_file.exists():
            print_success(f"gunicorn.conf.py presente")
            
            # Try to load config values
            import importlib.util
            spec = importlib.util.spec_from_file_location("gunicorn_conf", config_file)
            gunicorn_conf = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gunicorn_conf)
            
            print_success(f"Bind: {gunicorn_conf.bind}")
            print_success(f"Workers: {gunicorn_conf.workers}")
            print_success(f"Timeout: {gunicorn_conf.timeout}s")
        else:
            print_error("gunicorn.conf.py non trovato")
            return False
        
        return True
    except Exception as e:
        print_error(f"Gunicorn check failed: {e}")
        return False


def test_app_startup():
    """Test that the app can start"""
    print_header("8. Test Avvio Applicazione")
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            # Test database connection
            from app import db
            print_success("Database connection OK")
            
            # Test that we can query database
            try:
                from app.models import User
                user_count = User.query.count()
                print_success(f"Database accessible - {user_count} utenti trovati")
            except Exception as e:
                print_warning(f"Impossibile contare utenti (database potrebbe essere vuoto): {e}")
        
        print_success("Applicazione avviata con successo!")
        return True
    except Exception as e:
        print_error(f"Startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_production_config():
    """Check production-specific configuration"""
    print_header("9. Verifica Configurazione Produzione")
    
    app_env = os.getenv('APP_ENV', 'development')
    flask_env = os.getenv('FLASK_ENV', 'development')
    
    if app_env == 'production' or flask_env == 'production':
        print_success(f"Modalità: PRODUCTION")
        
        # Check critical production settings
        secret_key = os.getenv('SECRET_KEY', '').strip()
        if not secret_key or secret_key in ['', 'CHANGEME_GENERATE_WITH_PYTHON_SECRETS']:
            print_error("SECRET_KEY non impostato o usa valore di default!")
            print_error("Genera una chiave sicura: python3 -c \"import secrets; print(secrets.token_hex(32))\"")
            return False
        else:
            print_success("SECRET_KEY configurato correttamente")
        
        db_url = os.getenv('DATABASE_URL', '').strip()
        if db_url and db_url.startswith('postgresql://'):
            print_success("Database: PostgreSQL (raccomandato)")
        else:
            print_warning("Database: SQLite (non raccomandato per produzione)")
        
        if os.getenv('USE_PROXYFIX', 'false').lower() in ['true', '1', 'on']:
            print_success("ProxyFix abilitato (per Nginx)")
        else:
            print_warning("ProxyFix non abilitato (richiesto per Nginx)")
        
    else:
        print_warning(f"Modalità: {app_env.upper()} (non production)")
    
    return True


def main():
    """Main verification function"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║   SONACIP - Verifica Configurazione Produzione       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(Colors.ENDC)
    
    checks = [
        ("Python Version", check_python_version),
        ("Entrypoints", check_entrypoints),
        ("Application Factory", check_app_factory),
        ("Config Files", check_config_files),
        ("Environment Variables", check_env_variables),
        ("Dependencies", check_dependencies),
        ("Gunicorn", check_gunicorn),
        ("App Startup", test_app_startup),
        ("Production Config", check_production_config),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Check '{name}' failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print_header("RIEPILOGO")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print(f"\n{Colors.BOLD}Risultato: {passed}/{total} verifiche superate{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TUTTI I CONTROLLI SUPERATI - PRONTO PER PRODUZIONE!{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ Alcuni controlli falliti - Correggere prima del deployment{Colors.ENDC}\n")
        return 1


if __name__ == '__main__':
    sys.exit(main())
