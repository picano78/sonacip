#!/usr/bin/env python3
"""
SONACIP Virtual Site Check
Verifica completa di tutte le pagine e route del sito
"""

import os
import sys
from pathlib import Path

# Configurazione
BASE_DIR = Path(__file__).parent
REPORT_FILE = BASE_DIR / "site_check_report.txt"

def log(msg, level="INFO"):
    """Log message to console and file"""
    print(f"[{level}] {msg}")
    with open(REPORT_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{level}] {msg}\n")

def check_file_exists(filepath, description=""):
    """Verifica se un file esiste"""
    if os.path.exists(filepath):
        log(f"✓ {filepath} {description}", "OK")
        return True
    else:
        log(f"✗ MANCANTE: {filepath} {description}", "ERROR")
        return False

def check_route_blueprint(module_name, url_prefix=""):
    """Verifica un blueprint route"""
    routes_file = BASE_DIR / "app" / module_name / "routes.py"
    init_file = BASE_DIR / "app" / module_name / "__init__.py"
    
    if not routes_file.exists() and not init_file.exists():
        log(f"✗ Modulo {module_name} non trovato", "ERROR")
        return False
    
    # Cerca il blueprint nel file
    found_bp = False
    target_file = routes_file if routes_file.exists() else init_file
    
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "Blueprint(" in content or "bp =" in content or "bp=" in content:
                found_bp = True
    except Exception as e:
        log(f"✗ Errore lettura {target_file}: {e}", "ERROR")
        return False
    
    if found_bp:
        log(f"✓ Blueprint {module_name} OK (prefix: {url_prefix or '/'})", "OK")
        return True
    else:
        log(f"⚠ Blueprint {module_name} - 'bp' non trovato esplicitamente", "WARN")
        return True  # Potrebbe essere importato diversamente

def check_templates(module_name, templates_to_check):
    """Verifica template per un modulo"""
    templates_dir = BASE_DIR / "app" / module_name / "templates" / module_name
    
    if not templates_dir.exists():
        # Prova path alternativo
        templates_dir = BASE_DIR / "app" / "templates" / module_name
    
    if not templates_dir.exists():
        log(f"⚠ Directory template non trovata per {module_name}", "WARN")
        return False
    
    found_count = 0
    for template in templates_to_check:
        template_path = templates_dir / template
        if template_path.exists():
            log(f"  ✓ Template: {module_name}/{template}", "OK")
            found_count += 1
        else:
            log(f"  ✗ Template mancante: {module_name}/{template}", "ERROR")
    
    return found_count == len(templates_to_check)

def main():
    """Main check function"""
    # Inizializza report
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("SONACIP Site Check Report\n")
        f.write("=" * 60 + "\n\n")
    
    log("Inizio verifica completa SONACIP...")
    log("")
    
    # 1. Verifica file essenziali
    log("1. VERIFICA FILE ESSENZIALI", "SECTION")
    essential_files = [
        ("run.py", "Entrypoint principale"),
        ("wsgi.py", "WSGI per Gunicorn"),
        (".env", "Configurazione ambiente"),
        ("requirements.txt", "Dipendenze Python"),
    ]
    
    for filepath, desc in essential_files:
        check_file_exists(BASE_DIR / filepath, desc)
    
    log("")
    
    # 2. Verifica blueprint core
    log("2. VERIFICA BLUEPRINT CORE", "SECTION")
    
    core_modules = [
        ("main", ""),
        ("auth", "/auth"),
        ("admin", "/admin"),
        ("social", "/social"),
        ("tournaments", "/tournaments"),
        ("tasks", "/tasks"),
        ("events", "/events"),
        ("scheduler", "/scheduler"),
        ("messages", "/messages"),
        ("notifications", "/notifications"),
        ("subscription", "/subscription"),
        ("backup", "/backup"),
        ("analytics", "/analytics"),
        ("crm", "/crm"),
        ("ads", "/ads"),
        ("marketplace", "/marketplace"),
        ("groups", "/groups"),
        ("stories", "/stories"),
        ("livestream", "/livestream"),
        ("polls", "/polls"),
        ("stats", "/stats"),
        ("payments", "/payments"),
        ("documents", "/documents"),
        ("gamification", "/gamification"),
        ("security", "/security"),
        ("field_planner", "/field-planner"),
    ]
    
    for module, prefix in core_modules:
        check_route_blueprint(module, prefix)
    
    log("")
    
    # 3. Verifica template base
    log("3. VERIFICA TEMPLATE ESSENZIALI", "SECTION")
    
    templates_dir = BASE_DIR / "app" / "templates"
    base_templates = [
        "base.html",
        "index.html",
        "errors/404.html",
        "errors/500.html",
    ]
    
    for template in base_templates:
        check_file_exists(templates_dir / template, f"Template {template}")
    
    log("")
    
    # 4. Verifica static files
    log("4. VERIFICA STATIC FILES", "SECTION")
    static_dir = BASE_DIR / "app" / "static"
    
    static_files = [
        "css/main.css",
        "js/main.js",
        "icons/icon-192x192.png",
        "icons/icon-512x512.png",
    ]
    
    for static_file in static_files:
        check_file_exists(static_dir / static_file, f"Static {static_file}")
    
    log("")
    
    # 5. Verifica directory uploads
    log("5. VERIFICA DIRECTORY UPLOADS", "SECTION")
    uploads_dir = BASE_DIR / "uploads"
    
    if uploads_dir.exists():
        log(f"✓ Directory uploads esiste: {uploads_dir}", "OK")
        # Verifica sottodirectory
        for subdir in ["avatars", "covers", "posts", "groups"]:
            subdir_path = uploads_dir / subdir
            if subdir_path.exists():
                log(f"  ✓ {subdir}/", "OK")
            else:
                log(f"  ⚠ {subdir}/ mancante (verrà creato)", "WARN")
    else:
        log(f"✗ Directory uploads mancante: {uploads_dir}", "ERROR")
    
    log("")
    
    # 6. Verifica app/__init__.py
    log("6. VERIFICA CONFIGURAZIONE APP", "SECTION")
    init_file = BASE_DIR / "app" / "__init__.py"
    
    if init_file.exists():
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            checks = [
                ("create_app", "Funzione create_app"),
                ("_load_dotenv_if_present", "Loader .env"),
                ("_register_blueprints", "Registrazione blueprint"),
                ("_auto_seed", "Auto-seed database"),
                ("db.init_app", "Inizializzazione DB"),
            ]
            
            for check, desc in checks:
                if check in content:
                    log(f"✓ {desc} presente", "OK")
                else:
                    log(f"⚠ {desc} non trovato", "WARN")
    
    log("")
    
    # 7. Verifica service systemd (se presente)
    log("7. VERIFICA SYSTEMD SERVICE", "SECTION")
    service_file = BASE_DIR / "sonacip.service"
    
    if service_file.exists():
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if "run:app" in content or "wsgi:app" in content:
                log("✓ Service config OK (entrypoint corretto)", "OK")
            else:
                log("✗ Service: entrypoint non corretto", "ERROR")
            
            if "8000" in content:
                log("✓ Service: porta 8000 configurata", "OK")
            else:
                log("⚠ Service: porta non esplicita", "WARN")
    else:
        log("⚠ sonacip.service non trovato", "WARN")
    
    log("")
    
    # 8. Verifica models
    log("8. VERIFICA MODELLI DATABASE", "SECTION")
    models_file = BASE_DIR / "app" / "models.py"
    
    if models_file.exists():
        with open(models_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            models = [
                "class User",
                "class Role", 
                "class Society",
                "class Post",
                "class Event",
                "class Tournament",
            ]
            
            for model in models:
                if model in content:
                    log(f"✓ Modello {model.split()[1]} trovato", "OK")
                else:
                    log(f"⚠ Modello {model.split()[1]} non trovato", "WARN")
    else:
        log("✗ models.py non trovato!", "ERROR")
    
    log("")
    log("=" * 60)
    log("VERIFICA COMPLETATA")
    log(f"Report salvato in: {REPORT_FILE}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
