#!/usr/bin/env python3
"""
SONACIP Complete Site Audit & Virtual Check
Scansione completa di tutte le pagine, route e potenziali problemi
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).parent
REPORT_FILE = BASE_DIR / "complete_site_audit.txt"

class Colors:
    OK = "\033[92m"
    WARN = "\033[93m"
    ERROR = "\033[91m"
    INFO = "\033[94m"
    RESET = "\033[0m"

class SiteAuditor:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.ok_items = []
        self.routes_found = defaultdict(list)
        self.templates_found = set()
        self.missing_templates = []
        
    def log(self, msg, level="INFO", console=True):
        """Log to file and optionally console"""
        if console:
            color = getattr(Colors, level, Colors.INFO)
            print(f"{color}[{level}] {msg}{Colors.RESET}")
        
        with open(REPORT_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{level}] {msg}\n")
    
    def scan_routes(self):
        """Scansione di tutte le route nel progetto"""
        self.log("=" * 70, "INFO")
        self.log("SCANNING TUTTE LE ROUTE DEL PROGETTO", "INFO")
        self.log("=" * 70, "INFO")
        
        app_dir = BASE_DIR / "app"
        
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                if file.endswith("routes.py"):
                    filepath = Path(root) / file
                    self._analyze_route_file(filepath)
    
    def _analyze_route_file(self, filepath):
        """Analizza un file routes.py"""
        module_name = filepath.parent.name
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.log(f"Errore lettura {filepath}: {e}", "ERROR")
            return
        
        # Cerca blueprint definition
        bp_match = re.search(r"bp\s*=\s*Blueprint\(['\"](\w+)['\"].*?url_prefix=['\"]([^'\"]*)['\"]", content)
        if not bp_match:
            bp_match = re.search(r"bp\s*=\s*Blueprint\(['\"](\w+)['\"]", content)
        
        if bp_match:
            bp_name = bp_match.group(1)
            url_prefix = bp_match.group(2) if bp_match.lastindex >= 2 else "/"
        else:
            bp_name = module_name
            url_prefix = f"/{module_name}"
        
        # Cerca tutte le route
        route_pattern = r"@bp\.route\(['\"]([^'\"]+)['\"](?:.*?methods=\[([^\]]+)\])?"
        routes = re.findall(route_pattern, content)
        
        if routes:
            self.log(f"\n📁 {module_name}/routes.py ({len(routes)} route)", "INFO")
            
            for route_path, methods in routes:
                full_path = f"{url_prefix}{route_path}" if url_prefix != "/" else route_path
                if full_path == "//":
                    full_path = "/"
                
                http_methods = methods.replace("'", "").replace('"', "").replace(" ", "") if methods else "GET"
                self.routes_found[module_name].append({
                    'path': full_path,
                    'methods': http_methods,
                    'file': str(filepath)
                })
                self.log(f"  → {full_path} [{http_methods}]", "OK")
        
        # Cerca render_template calls
        template_pattern = r'render_template\(["\']([^"\']+)["\']'
        templates = re.findall(template_pattern, content)
        
        for template in templates:
            self._check_template_exists(module_name, template)
    
    def _check_template_exists(self, module_name, template_path):
        """Verifica se un template esiste"""
        # Possibili percorsi del template
        possible_paths = [
            BASE_DIR / "app" / "templates" / template_path,
            BASE_DIR / "app" / module_name / "templates" / module_name / template_path,
            BASE_DIR / "app" / module_name / "templates" / template_path,
        ]
        
        found = False
        for path in possible_paths:
            if path.exists():
                self.templates_found.add(str(path.relative_to(BASE_DIR)))
                found = True
                break
        
        if not found:
            self.missing_templates.append({
                'module': module_name,
                'template': template_path
            })
            self.log(f"  ⚠️ Template mancante: {module_name}/{template_path}", "WARN")
    
    def scan_all_templates(self):
        """Scansione di tutti i template"""
        self.log("\n" + "=" * 70, "INFO")
        self.log("SCANNING TEMPLATE FILES", "INFO")
        self.log("=" * 70, "INFO")
        
        templates_dir = BASE_DIR / "app" / "templates"
        
        if not templates_dir.exists():
            self.log("Directory templates non trovata!", "ERROR")
            return
        
        count = 0
        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if file.endswith('.html'):
                    filepath = Path(root) / file
                    rel_path = filepath.relative_to(BASE_DIR)
                    self.templates_found.add(str(rel_path))
                    count += 1
        
        self.log(f"Trovati {count} file HTML in app/templates/", "OK")
    
    def check_core_files(self):
        """Verifica file essenziali"""
        self.log("\n" + "=" * 70, "INFO")
        self.log("VERIFICA FILE ESSENZIALI", "INFO")
        self.log("=" * 70, "INFO")
        
        essential = [
            ("run.py", "Entrypoint Flask"),
            ("wsgi.py", "Entrypoint Gunicorn"),
            (".env", "Configurazione ambiente"),
            ("requirements.txt", "Dipendenze"),
            ("app/__init__.py", "App factory"),
            ("app/models.py", "Modelli database"),
            ("app/templates/base.html", "Template base"),
            ("app/static/css/main.css", "CSS principale"),
        ]
        
        for filepath, desc in essential:
            full_path = BASE_DIR / filepath
            if full_path.exists():
                self.log(f"✓ {filepath} - {desc}", "OK")
            else:
                self.log(f"✗ {filepath} MANCANTE - {desc}", "ERROR")
                self.issues.append(f"File mancante: {filepath}")
    
    def check_common_issues(self):
        """Controlla problemi comuni"""
        self.log("\n" + "=" * 70, "INFO")
        self.log("CONTROLLO PROBLEMI COMUNI", "INFO")
        self.log("=" * 70, "INFO")
        
        issues_found = []
        
        # 1. Verifica imports circolari potenziali
        init_file = BASE_DIR / "app" / "__init__.py"
        if init_file.exists():
            with open(init_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Verifica che db sia inizializzato prima dei modelli
            if "db = SQLAlchemy()" in content and "db.init_app" in content:
                self.log("✓ Database SQLAlchemy configurato correttamente", "OK")
            else:
                self.log("⚠ Configurazione SQLAlchemy da verificare", "WARN")
        
        # 2. Verifica config.py
        config_file = BASE_DIR / "config.py"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "SECRET_KEY" in content:
                self.log("✓ SECRET_KEY in config.py", "OK")
            else:
                self.log("⚠ SECRET_KEY mancante in config.py", "WARN")
        
        # 3. Verifica gestione errori
        error_templates = [
            BASE_DIR / "app" / "templates" / "errors" / "404.html",
            BASE_DIR / "app" / "templates" / "errors" / "500.html",
        ]
        
        for error_template in error_templates:
            if error_template.exists():
                self.log(f"✓ Template errore: {error_template.name}", "OK")
            else:
                self.log(f"⚠ Template errore mancante: {error_template.name}", "WARN")
        
        # 4. Verifica directory uploads
        uploads_dir = BASE_DIR / "uploads"
        if uploads_dir.exists():
            self.log("✓ Directory uploads esiste", "OK")
            # Verifica permessi (simulato)
            self.log(f"  → Path: {uploads_dir}", "INFO")
        else:
            self.log("⚠ Directory uploads mancante (verrà creata)", "WARN")
    
    def generate_summary(self):
        """Genera riepilogo finale"""
        self.log("\n" + "=" * 70, "INFO")
        self.log("RIEPILOGO AUDIT", "INFO")
        self.log("=" * 70, "INFO")
        
        total_routes = sum(len(routes) for routes in self.routes_found.values())
        total_templates = len(self.templates_found)
        
        self.log(f"\n📊 STATISTICHE:", "INFO")
        self.log(f"  • Blueprint/Moduli: {len(self.routes_found)}", "INFO")
        self.log(f"  • Route totali: {total_routes}", "INFO")
        self.log(f"  • Template trovati: {total_templates}", "INFO")
        self.log(f"  • Template mancanti: {len(self.missing_templates)}", "WARN" if self.missing_templates else "OK")
        
        if self.routes_found:
            self.log(f"\n📋 ROUTE PER MODULO:", "INFO")
            for module, routes in sorted(self.routes_found.items()):
                self.log(f"  {module}: {len(routes)} route", "INFO")
        
        if self.missing_templates:
            self.log(f"\n⚠️  TEMPLATE MANCANTI:", "WARN")
            for item in self.missing_templates:
                self.log(f"  - {item['module']}/{item['template']}", "WARN")
        
        self.log(f"\n✅ Audit completato. Report salvato in: {REPORT_FILE}", "OK")
    
    def run(self):
        """Esegue l'audit completo"""
        # Inizializza report file
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            f.write("SONACIP - Complete Site Audit Report\n")
            f.write("=" * 70 + "\n\n")
        
        self.log("🔍 AVVIO AUDIT COMPLETO SONACIP", "INFO")
        self.log(f"Directory base: {BASE_DIR}", "INFO")
        
        self.check_core_files()
        self.scan_routes()
        self.scan_all_templates()
        self.check_common_issues()
        self.generate_summary()
        
        return 0

if __name__ == "__main__":
    auditor = SiteAuditor()
    sys.exit(auditor.run())
