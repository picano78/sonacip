#!/usr/bin/env python3
"""
OTTIMIZZAZIONE COMPLETA SOFTWARE - ANALISI ERRORI 404
Scan completo delle route, template e link per identificare errori 404
"""

import os
import sys
import re
import traceback
from pathlib import Path
from urllib.parse import urljoin

BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

print("="*80)
print("OTTIMIZZAZIONE COMPLETA SOFTWARE - ANALISI ERRORI 404")
print("="*80)

# Setup environment
if not (BASE_DIR / '.env').exists():
    with open(BASE_DIR / '.env', 'w') as f:
        f.write("FLASK_ENV=development\n")
        f.write("DATABASE_URL=sqlite:///uploads/sonacip.db\n")
        f.write("SECRET_KEY=test_debug\n")

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env', override=True)

try:
    from app import create_app, db
    from flask import url_for
    
    os.environ['FLASK_ENV'] = 'development'
    app = create_app()
    
    with app.app_context():
        print("\n[1] ANALISI COMPLETE ROUTES")
        print("-"*60)
        
        # Raccoglie tutte le route definite
        all_routes = []
        for rule in app.url_map.iter_rules():
            all_routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'rule': str(rule),
                'defaults': rule.defaults
            })
        
        print(f"Totale route definite: {len(all_routes)}")
        
        # Route per metodo GET
        get_routes = [r for r in all_routes if 'GET' in r['methods']]
        print(f"Route GET: {len(get_routes)}")
        
        # Route POST
        post_routes = [r for r in all_routes if 'POST' in r['methods']]
        print(f"Route POST: {len(post_routes)}")
        
        print("\n[2] ANALISI TEMPLATE E LINK INTERNI")
        print("-"*60)
        
        # Scansiona tutti i template per trovare link interni
        template_dir = BASE_DIR / 'app' / 'templates'
        broken_links = []
        all_links = []
        
        def extract_links_from_file(file_path):
            """Estrae tutti i link interni da un file template"""
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Pattern per trovare link Flask
                flask_links = re.findall(r"url_for\(['\"]([^'\"]+)['\"]\)", content)
                
                # Pattern per trovare href relativi
                href_links = re.findall(r"href=['\"]([^'\"]+)['\"]", content)
                
                # Pattern per trovare action nei form
                action_links = re.findall(r"action=['\"]([^'\"]+)['\"]", content)
                
                # Pattern per trovare redirect
                redirect_links = re.findall(r"redirect\(url_for\(['\"]([^'\"]+)['\"]\)\)", content)
                
                return {
                    'flask_links': flask_links,
                    'href_links': href_links,
                    'action_links': action_links,
                    'redirect_links': redirect_links
                }
            except Exception as e:
                print(f"Errore lettura {file_path}: {e}")
                return {'flask_links': [], 'href_links': [], 'action_links': [], 'redirect_links': []}
        
        # Scansiona ricorsivamente i template
        for template_file in template_dir.rglob('*.html'):
            rel_path = template_file.relative_to(template_dir)
            links = extract_links_from_file(template_file)
            
            for link_type, link_list in links.items():
                for link in link_list:
                    all_links.append({
                        'template': str(rel_path),
                        'type': link_type,
                        'link': link
                    })
        
        print(f"Link interni trovati: {len(all_links)}")
        
        print("\n[3] VERIFICA ROUTE VS LINK")
        print("-"*60)
        
        # Mappa di tutti gli endpoint disponibili
        available_endpoints = {r['endpoint'] for r in all_routes}
        
        # Verifica ogni link
        broken_endpoints = []
        valid_endpoints = []
        
        for link_info in all_links:
            link = link_info['link']
            
            # Salta link esterni e statici
            if (link.startswith(('http://', 'https://', '#', 'mailto:', 'tel:', '/static/')) or 
                link.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico'))):
                continue
            
            # Per url_for, verifica l'endpoint
            if link_info['type'] in ['flask_links', 'redirect_links']:
                if link not in available_endpoints:
                    broken_endpoints.append({
                        'template': link_info['template'],
                        'type': link_info['type'],
                        'endpoint': link
                    })
                else:
                    valid_endpoints.append(link)
            
            # Per href relativi, verifica se corrisponde a una route
            elif link_info['type'] in ['href_links', 'action_links']:
                if link.startswith('/'):
                    # Route assoluta
                    route_found = False
                    for rule in all_routes:
                        if 'GET' in rule['methods']:
                            # Semplice verifica di pattern
                            rule_pattern = rule['rule'].replace('<', '<').replace('>', '>')
                            if link == rule_pattern:
                                route_found = True
                                break
                    
                    if not route_found:
                        broken_endpoints.append({
                            'template': link_info['template'],
                            'type': link_info['type'],
                            'endpoint': link
                        })
                    else:
                        valid_endpoints.append(link)
        
        print(f"Link validi: {len(valid_endpoints)}")
        print(f"Link rotti: {len(broken_endpoints)}")
        
        if broken_endpoints:
            print("\n❌ LINK ROTTI TROVATI:")
            for broken in broken_endpoints[:20]:  # Limita output
                print(f"   • {broken['template']}: {broken['type']} -> {broken['endpoint']}")
            
            if len(broken_endpoints) > 20:
                print(f"   ... e altri {len(broken_endpoints) - 20} link")
        
        print("\n[4] ANALISI STATIC FILES")
        print("-"*60)
        
        # Verifica file statici referenziati
        static_dir = BASE_DIR / 'app' / 'static'
        missing_static = []
        
        for link_info in all_links:
            link = link_info['link']
            
            if link.startswith('/static/'):
                static_path = static_dir / link[8:]  # Rimuove '/static/'
                if not static_path.exists():
                    missing_static.append({
                        'template': link_info['template'],
                        'missing_file': str(static_path)
                    })
        
        if missing_static:
            print(f"❌ File statici mancanti: {len(missing_static)}")
            for missing in missing_static[:10]:
                print(f"   • {missing['template']}: {missing['missing_file']}")
        else:
            print("✅ Tutti i file statici referenziati esistono")
        
        print("\n[5] TEST HTTP COMPLETO")
        print("-"*60)
        
        # Test HTTP completo delle route
        test_routes = [
            ('/', 'Homepage'),
            ('/auth/login', 'Login'),
            ('/auth/register', 'Register'),
            ('/dashboard', 'Dashboard'),
            ('/admin', 'Admin'),
            ('/field_planner/', 'Field Planner'),
            ('/calendar/', 'Calendar'),
            ('/tasks', 'Tasks'),
            ('/social/feed', 'Social Feed'),
            ('/marketplace', 'Marketplace'),
            ('/notifications', 'Notifications'),
            ('/profile', 'Profile'),
            ('/settings', 'Settings'),
            ('/subscription/plans', 'Subscription Plans'),
            ('/tournaments', 'Tournaments'),
            ('/messages', 'Messages')
        ]
        
        http_errors = []
        
        with app.test_client() as client:
            # Login per testare pagine protette
            try:
                client.post('/auth/login', data={'identifier': 'picano78@gmail.com', 'password': 'Simone78'})
            except:
                pass  # Se il login fallisce, testiamo comunque
            
            for route, name in test_routes:
                try:
                    response = client.get(route, follow_redirects=False)
                    
                    if response.status_code == 404:
                        http_errors.append((route, name, 404))
                        print(f"❌ {name:20s} {route:25s} HTTP 404")
                    elif response.status_code == 500:
                        http_errors.append((route, name, 500))
                        print(f"❌ {name:20s} {route:25s} HTTP 500")
                    elif response.status_code in (200, 302, 401, 403):
                        print(f"✅ {name:20s} {route:25s} HTTP {response.status_code}")
                    else:
                        print(f"⚠️  {name:20s} {route:25s} HTTP {response.status_code}")
                        
                except Exception as e:
                    http_errors.append((route, name, f'ERR: {str(e)[:30]}'))
                    print(f"💥 {name:20s} {route:25s} ERRORE: {str(e)[:30]}")
        
        print(f"\nErrori HTTP trovati: {len(http_errors)}")
        
        print("\n[6] OTTIMIZZAZIONI CONSIGLIATE")
        print("-"*60)
        
        optimizations = []
        
        # Controlla route duplicate
        endpoint_counts = {}
        for route in all_routes:
            endpoint = route['endpoint']
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1
        
        duplicates = {k: v for k, v in endpoint_counts.items() if v > 1}
        if duplicates:
            print("⚠️  Endpoint duplicati trovati:")
            for endpoint, count in duplicates.items():
                print(f"   • {endpoint}: {count} volte")
            optimizations.append("Rimuovi endpoint duplicati")
        
        # Controlla route senza metodi specificati
        no_methods = [r for r in all_routes if not r['methods'] or r['methods'] == ['HEAD', 'OPTIONS']]
        if no_methods:
            print(f"⚠️  Route senza metodi HTTP: {len(no_methods)}")
            optimizations.append("Specifica metodi HTTP per tutte le route")
        
        # Controlla template mancanti
        missing_templates = []
        for rule in all_routes:
            if 'GET' in rule['methods']:
                try:
                    # Prova a generare URL per vedere se template esiste
                    with app.test_request_context():
                        try:
                            url = url_for(rule['endpoint'])
                            # Non possiamo facilmente verificare il template qui
                        except:
                            missing_templates.append(rule['endpoint'])
                except:
                    pass
        
        if missing_templates:
            print(f"⚠️  Route con problemi URL generation: {len(missing_templates)}")
            optimizations.append("Correggi route con URL generation problems")
        
        if not optimizations:
            print("✅ Nessuna ottimizzazione critica necessaria")
        
        print("\n[7] RIEPILOGO FINALE")
        print("-"*60)
        
        total_issues = len(broken_endpoints) + len(missing_static) + len(http_errors)
        
        if total_issues == 0:
            print("🎉 NESSUN ERRORE 404 TROVATO!")
            print("✅ Tutte le route funzionano correttamente")
            print("✅ Tutti i link interni sono validi")
            print("✅ Tutti i file statici esistono")
        else:
            print(f"❌ TROVATI {total_issues} PROBLEMI:")
            print(f"   • Link rotti: {len(broken_endpoints)}")
            print(f"   • File statici mancanti: {len(missing_static)}")
            print(f"   • Errori HTTP: {len(http_errors)}")
            
            print("\n🔧 AZIONI CONSIGLIATE:")
            if broken_endpoints:
                print("   1. Correggi endpoint mancanti nei template")
            if missing_static:
                print("   2. Aggiungi file statici mancanti")
            if http_errors:
                print("   3. Correggi route che danno errore HTTP")
        
        print("\n" + "="*80)
        print("ANALISI ERRORI 404 COMPLETATA")
        print("="*80)

except Exception as e:
    print(f"ERRORE GENERALE: {e}")
    traceback.print_exc()
