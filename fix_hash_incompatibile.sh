#!/bin/bash
# FIX HASH INCOMPATIBILE - SOLUZIONE DEFINITIVA

ssh root@87.106.1.221 "cd /root/sonacip && source venv/bin/activate && cat > .env << 'EOF'
SUPERADMIN_EMAIL=picano78@gmail.com
SUPERADMIN_PASSWORD=Simone78
DATABASE_URL=sqlite:////root/sonacip/uploads/sonacip.db
SQLALCHEMY_DATABASE_URI=sqlite:////root/sonacip/uploads/sonacip.db
SECRET_KEY=4f8a2b9c1d3e5f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2
FLASK_ENV=production
PORT=8000
EOF

python3 << 'PY'
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash

app = create_app()
with app.app_context():
    # Trova utente
    user = User.query.filter_by(id=2).first()
    if not user:
        user = User.query.filter_by(email='picano78@gmail.com').first()
    
    if not user:
        print('ERRORE: Utente non trovato!')
        exit(1)
    
    print(f'Utente: {user.email} (ID: {user.id})')
    print(f'Hash vecchio: {user.password_hash[:40]}...')
    
    # Test hash vecchio
    old_check = user.check_password('Simone78')
    print(f'Verifica hash vecchio: {old_check}')
    
    # Genera NUOVO hash compatibile
    new_hash = generate_password_hash('Simone78')
    print(f'Hash nuovo:    {new_hash[:40]}...')
    
    # Sostituisci hash
    user.password_hash = new_hash
    db.session.commit()
    
    # Verifica nuovo hash
    new_check = user.check_password('Simone78')
    print(f'Verifica hash nuovo: {new_check}')
    
    if new_check:
        print('✅ HASH INCOMPATIBILE RISOLTO!')
        print('✅ Login superadmin ora funzionante!')
    else:
        print('❌ ERRORE: ancora non funziona!')
        exit(1)
PY

systemctl restart sonacip
sleep 3

echo "Test finale..."
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -d "identifier=picano78@gmail.com&password=Simone78" \
  -w "HTTP %{http_code}" -L | tail -1

echo ""
echo "=========================================="
echo "HASH INCOMPATIBILE - FIX COMPLETATO"
echo "=========================================="
echo "Credenziali:"
echo "  Email: picano78@gmail.com"
echo "  Password: Simone78"
echo "=========================================="
