from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, send_file
from flask_login import login_required, current_user
from app import db, csrf
from app.models import FeePayment, SocietyFee, User
from app.utils import admin_required, log_action
from datetime import datetime, timezone
import os
import json
import stripe

bp = Blueprint('payments', __name__, url_prefix='/payments')

ALLOWED_STATUSES = {'pending', 'completed', 'failed'}


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('payments_online'):
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


def _init_stripe():
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')


def _base_url():
    domain = os.environ.get('APP_DOMAIN', '').strip().rstrip('/')
    if not domain:
        domain = os.environ.get('REPLIT_DOMAINS', '').split(',')[0].strip().rstrip('/')
    if domain:
        if not domain.startswith('http'):
            return f'https://{domain}'
        return domain
    return request.host_url.rstrip('/')


@bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '').strip()
    q = FeePayment.query.filter_by(user_id=current_user.id)
    if status_filter in ALLOWED_STATUSES:
        q = q.filter_by(status=status_filter)
    payments = q.order_by(FeePayment.created_at.desc()).all()
    return render_template('payments/index.html', payments=payments, status_filter=status_filter)


@bp.route('/fee/<int:fee_id>/pay')
@login_required
def pay(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.index'))
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.index'))
    amount_eur = round(float(fee.amount_cents or 0) / 100.0, 2)
    return render_template('payments/pay.html', fee=fee, amount_eur=amount_eur)


@bp.route('/fee/<int:fee_id>/checkout', methods=['POST'])
@login_required
def checkout(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.user_id != current_user.id:
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.index'))
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.index'))

    _init_stripe()
    if not stripe.api_key:
        flash('Stripe non è configurato. Contatta l\'amministratore.', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))

    amount_cents = int(fee.amount_cents or 0)
    if amount_cents <= 0:
        flash('Importo non valido.', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))

    base = _base_url()
    currency = (fee.currency or 'EUR').lower()

    fp = FeePayment.query.filter_by(fee_id=fee.id, user_id=current_user.id, status='pending').first()
    if not fp:
        fp = FeePayment(
            fee_id=fee.id,
            user_id=current_user.id,
            amount=round(amount_cents / 100.0, 2),
            payment_method='stripe',
            status='pending',
        )
        db.session.add(fp)
        db.session.commit()

    try:
        sess = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': currency,
                    'unit_amount': amount_cents,
                    'product_data': {
                        'name': fee.description or f'Quota società #{fee.id}',
                    },
                },
                'quantity': 1,
            }],
            success_url=f'{base}{url_for("payments.success")}?session_id={{CHECKOUT_SESSION_ID}}&fp_id={fp.id}',
            cancel_url=f'{base}{url_for("payments.cancel")}?fee_id={fee.id}',
            metadata={
                'fee_id': str(fee.id),
                'fee_payment_id': str(fp.id),
                'user_id': str(current_user.id),
            },
        )
        return redirect(sess.url, code=303)
    except Exception as exc:
        flash(f'Errore Stripe: {exc}', 'danger')
        return redirect(url_for('payments.pay', fee_id=fee_id))


@bp.route('/success')
@login_required
def success():
    fp_id = request.args.get('fp_id', type=int)
    session_id = request.args.get('session_id', '')
    fp = None
    invoice = None
    
    if fp_id:
        fp = FeePayment.query.get(fp_id)
        if fp and fp.user_id == current_user.id and fp.status == 'pending':
            fp.status = 'completed'
            fp.paid_at = datetime.now(timezone.utc)
            fp.stripe_payment_id = session_id
            db.session.add(fp)
            if fp.fee:
                fp.fee.status = 'paid'
                fp.fee.paid_at = datetime.now(timezone.utc)
                db.session.add(fp.fee)
            db.session.commit()
            
            # Automatically generate invoice
            from app.payments.invoice_utils import generate_invoice_for_payment
            invoice = generate_invoice_for_payment(fp.id)
            
    return render_template('payments/success.html', payment=fp, invoice=invoice)


@bp.route('/cancel')
@login_required
def cancel():
    fee_id = request.args.get('fee_id', type=int)
    return render_template('payments/cancel.html', fee_id=fee_id)


@bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    wh_secret = os.environ.get('STRIPE_WEBHOOK_SECRET') or current_app.config.get('STRIPE_WEBHOOK_SECRET')

    if wh_secret and sig_header:
        try:
            event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=wh_secret)
        except Exception:
            return ('bad signature', 400)
    else:
        try:
            event = json.loads(payload.decode('utf-8'))
        except Exception:
            return ('bad payload', 400)

    if event.get('type') == 'checkout.session.completed':
        session_obj = event['data']['object']
        meta = session_obj.get('metadata', {})
        fp_id = meta.get('fee_payment_id')
        fee_id = meta.get('fee_id')
        if fp_id:
            fp = FeePayment.query.get(int(fp_id))
            if fp and fp.status == 'pending':
                fp.status = 'completed'
                fp.paid_at = datetime.now(timezone.utc)
                fp.stripe_payment_id = session_obj.get('payment_intent') or session_obj.get('id')
                db.session.add(fp)
                if fp.fee and fp.fee.status != 'paid':
                    fp.fee.status = 'paid'
                    fp.fee.paid_at = datetime.now(timezone.utc)
                    db.session.add(fp.fee)
                db.session.commit()
                
                # Automatically generate invoice
                from app.payments.invoice_utils import generate_invoice_for_payment
                generate_invoice_for_payment(fp.id)

    return ('ok', 200)


@bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    """View payment receipt with authorization check."""
    # Fetch only if user has access (super admin mantiene accesso)
    fp = FeePayment.query.filter_by(id=payment_id).filter(
        db.or_(
            FeePayment.user_id == current_user.id,
            current_user.is_admin() == True
        )
    ).first_or_404()
    
    fee = fp.fee
    amount_eur = fp.amount
    return render_template('payments/receipt.html', payment=fp, fee=fee, amount_eur=amount_eur)


@bp.route('/admin')
@login_required
@admin_required
def admin():
    status_filter = request.args.get('status', '').strip()
    user_filter = request.args.get('user', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    q = FeePayment.query
    if status_filter in ALLOWED_STATUSES:
        q = q.filter_by(status=status_filter)
    if user_filter:
        from app.utils import escape_like
        user_filter_safe = escape_like(user_filter)
        q = q.join(User, FeePayment.user_id == User.id).filter(
            db.or_(
                User.username.ilike(f'%{user_filter_safe}%', escape='\\'),
                User.first_name.ilike(f'%{user_filter_safe}%', escape='\\'),
                User.last_name.ilike(f'%{user_filter_safe}%', escape='\\')
            )
        )
    if date_from:
        try:
            q = q.filter(FeePayment.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(FeePayment.created_at <= datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except ValueError:
            pass

    payments = q.order_by(FeePayment.created_at.desc()).all()

    from sqlalchemy import func
    total_received = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter_by(status='completed').scalar()
    total_pending = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter_by(status='pending').scalar()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = db.session.query(func.coalesce(func.sum(FeePayment.amount), 0)).filter(
        FeePayment.status == 'completed', FeePayment.paid_at >= month_start
    ).scalar()

    pending_fees = SocietyFee.query.filter_by(status='pending').order_by(SocietyFee.due_on.desc()).limit(50).all()

    return render_template('payments/admin.html',
                           payments=payments,
                           total_received=total_received,
                           total_pending=total_pending,
                           this_month=this_month,
                           status_filter=status_filter,
                           user_filter=user_filter,
                           date_from=date_from,
                           date_to=date_to,
                           pending_fees=pending_fees)


@bp.route('/manual/<int:fee_id>', methods=['POST'])
@login_required
@admin_required
def manual_payment(fee_id):
    fee = SocietyFee.query.get_or_404(fee_id)
    if fee.status == 'paid':
        flash('Questa quota è già stata pagata.', 'info')
        return redirect(url_for('payments.admin'))

    method = request.form.get('payment_method', 'contanti')
    notes = request.form.get('notes', '')

    fp = FeePayment(
        fee_id=fee.id,
        user_id=fee.user_id,
        amount=round(float(fee.amount_cents or 0) / 100.0, 2),
        payment_method=method,
        status='completed',
        paid_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.session.add(fp)

    fee.status = 'paid'
    fee.paid_at = datetime.now(timezone.utc)
    db.session.add(fee)
    db.session.commit()

    log_action('manual_payment', 'FeePayment', fp.id, f'Pagamento manuale registrato per quota #{fee.id}')
    flash('Pagamento manuale registrato con successo.', 'success')
    return redirect(url_for('payments.admin'))


@bp.route('/quick-approve/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
def quick_approve(payment_id):
    """Quick approve payment - modern social network style (super admin only)"""
    payment = FeePayment.query.get_or_404(payment_id)
    
    if payment.status == 'completed':
        return jsonify({'success': False, 'message': 'Pagamento già completato'}), 400
    
    # Get current time once for consistency
    now = datetime.now(timezone.utc)
    
    # Approve payment
    payment.status = 'completed'
    payment.paid_at = now
    payment.notes = (payment.notes or '') + f'\n[ADMIN] Approvato da {current_user.username} il {now.strftime("%d/%m/%Y %H:%M")}'
    db.session.add(payment)
    
    # Update fee status
    if payment.fee and payment.fee.status != 'paid':
        payment.fee.status = 'paid'
        payment.fee.paid_at = now
        db.session.add(payment.fee)
    
    db.session.commit()
    
    # Send notification to user
    from app.notifications.utils import create_notification
    create_notification(
        user_id=payment.user_id,
        notification_type='payment_approved',
        title='✅ Pagamento Approvato',
        message=f'Il tuo pagamento di €{payment.amount:.2f} è stato approvato!',
        link=f'/payments/receipt/{payment.id}'
    )
    
    log_action('quick_approve_payment', 'FeePayment', payment.id, f'Pagamento approvato rapidamente')
    
    return jsonify({
        'success': True,
        'message': 'Pagamento approvato con successo',
        'payment_id': payment.id
    })


@bp.route('/quick-reject/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
def quick_reject(payment_id):
    """Quick reject payment - modern social network style (super admin only)"""
    payment = FeePayment.query.get_or_404(payment_id)
    
    if payment.status == 'completed':
        return jsonify({'success': False, 'message': 'Pagamento già completato, impossibile rifiutare'}), 400
    
    reason = request.json.get('reason', 'Nessun motivo specificato') if request.is_json else request.form.get('reason', 'Nessun motivo specificato')
    
    # Reject payment
    payment.status = 'failed'
    payment.notes = (payment.notes or '') + f'\n[ADMIN] Rifiutato da {current_user.username}: {reason}'
    db.session.add(payment)
    db.session.commit()
    
    # Send notification to user
    from app.notifications.utils import create_notification
    create_notification(
        user_id=payment.user_id,
        notification_type='payment_rejected',
        title='❌ Pagamento Rifiutato',
        message=f'Il tuo pagamento di €{payment.amount:.2f} è stato rifiutato. Motivo: {reason}',
        link='/payments'
    )
    
    log_action('quick_reject_payment', 'FeePayment', payment.id, f'Pagamento rifiutato: {reason}')
    
    return jsonify({
        'success': True,
        'message': 'Pagamento rifiutato',
        'payment_id': payment.id
    })


@bp.route('/bulk-approve', methods=['POST'])
@login_required
@admin_required
def bulk_approve():
    """Bulk approve multiple payments - modern automation feature (super admin only)"""
    payment_ids = request.json.get('payment_ids', []) if request.is_json else request.form.getlist('payment_ids[]')
    
    if not payment_ids:
        return jsonify({'success': False, 'message': 'Nessun pagamento selezionato'}), 400
    
    approved_count = 0
    failed_count = 0
    
    for payment_id in payment_ids:
        try:
            payment = FeePayment.query.get(int(payment_id))
            if payment and payment.status == 'pending':
                payment.status = 'completed'
                payment.paid_at = datetime.now(timezone.utc)
                payment.notes = (payment.notes or '') + f'\n[ADMIN] Approvazione bulk da {current_user.username}'
                db.session.add(payment)
                
                if payment.fee and payment.fee.status != 'paid':
                    payment.fee.status = 'paid'
                    payment.fee.paid_at = datetime.now(timezone.utc)
                    db.session.add(payment.fee)
                
                # Send notification
                from app.notifications.utils import create_notification
                create_notification(
                    user_id=payment.user_id,
                    notification_type='payment_approved',
                    title='✅ Pagamento Approvato',
                    message=f'Il tuo pagamento di €{payment.amount:.2f} è stato approvato!',
                    link=f'/payments/receipt/{payment.id}'
                )
                
                approved_count += 1
        except Exception as e:
            failed_count += 1
            current_app.logger.error(f'Error approving payment {payment_id}: {e}')
    
    db.session.commit()
    log_action('bulk_approve_payments', 'FeePayment', 0, f'Approvati {approved_count} pagamenti in blocco')
    
    return jsonify({
        'success': True,
        'message': f'{approved_count} pagamenti approvati con successo',
        'approved_count': approved_count,
        'failed_count': failed_count
    })


@bp.route('/automation-settings', methods=['GET', 'POST'])
@login_required
@admin_required
def automation_settings():
    """Configure payment automation settings (super admin only)"""
    from app.payments.automation import AUTO_APPROVE_THRESHOLD
    import os
    
    if request.method == 'POST':
        # Update settings (in production, store in database or config file)
        threshold = request.form.get('auto_approve_threshold', type=float, default=50.0)
        
        # For now, we'll just show a success message
        # In production, you'd save this to database or config
        flash(f'Impostazioni di automazione aggiornate. Soglia auto-approvazione: €{threshold:.2f}', 'success')
        return redirect(url_for('payments.automation_settings'))
    
    return render_template('payments/automation_settings.html',
                         auto_approve_threshold=AUTO_APPROVE_THRESHOLD)


@bp.route('/invoices')
@login_required
def invoices():
    """List user's invoices"""
    from app.models import Invoice
    
    # Get user's invoices
    user_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).all()
    
    return render_template('payments/invoices.html', invoices=user_invoices)


@bp.route('/invoice/<int:invoice_id>')
@login_required
def invoice_detail(invoice_id):
    """View invoice details"""
    from app.models import Invoice
    
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check permissions - user must own the invoice or be admin
    if invoice.user_id != current_user.id and not current_user.is_admin():
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.invoices'))
    
    return render_template('payments/invoice_detail.html', invoice=invoice)


@bp.route('/invoice/<int:invoice_id>/download')
@login_required
def download_invoice(invoice_id):
    """Download invoice PDF"""
    from app.models import Invoice
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    import io
    from flask import send_file
    
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check permissions
    if invoice.user_id != current_user.id and not current_user.is_admin():
        flash('Accesso negato.', 'danger')
        return redirect(url_for('payments.invoices'))
    
    # Get invoice settings for company info
    from app.models import InvoiceSettings
    settings = InvoiceSettings.query.first()
    
    # Generate PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333')
    )
    
    # Add company logo if available
    if settings and settings.logo_path:
        try:
            # Sanitize logo path to prevent directory traversal
            logo_filename = os.path.basename(settings.logo_path)
            logo_full_path = os.path.join(current_app.root_path, 'static', 'uploads', 'invoice_logos', logo_filename)
            
            # Verify the path is within the expected directory
            uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'invoice_logos')
            if os.path.commonpath([logo_full_path, uploads_dir]) == uploads_dir and os.path.exists(logo_full_path):
                img = Image(logo_full_path, width=2*inch, height=1*inch)
                elements.append(img)
                elements.append(Spacer(1, 0.3*inch))
        except Exception:
            pass
    
    # Title
    elements.append(Paragraph(f"<b>FATTURA {invoice.invoice_number}</b>", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Company and invoice info table
    company_info = []
    if settings:
        company_info.append([Paragraph('<b>Da:</b>', header_style), ''])
        if settings.company_name:
            company_info.append(['', Paragraph(f'<b>{settings.company_name}</b>', header_style)])
        if settings.company_address:
            company_info.append(['', settings.company_address])
        if settings.company_city and settings.company_postal_code:
            company_info.append(['', f'{settings.company_postal_code} {settings.company_city}, {settings.company_country or "Italia"}'])
        if settings.company_vat:
            company_info.append(['', f'P.IVA: {settings.company_vat}'])
        if settings.company_tax_code:
            company_info.append(['', f'C.F.: {settings.company_tax_code}'])
    
    if company_info:
        company_table = Table(company_info, colWidths=[0.8*inch, 5*inch])
        company_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(company_table)
        elements.append(Spacer(1, 0.2*inch))
    
    # Client info
    client_info = [
        [Paragraph('<b>A:</b>', header_style), ''],
        ['', Paragraph(f'<b>{invoice.billing_name or invoice.user.username}</b>', header_style)],
    ]
    if invoice.billing_address:
        client_info.append(['', invoice.billing_address])
    if invoice.billing_city:
        client_info.append(['', f'{invoice.billing_postal_code or ""} {invoice.billing_city}'])
    if invoice.tax_id:
        client_info.append(['', f'P.IVA/C.F.: {invoice.tax_id}'])
    
    client_table = Table(client_info, colWidths=[0.8*inch, 5*inch])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Invoice details
    details_data = [
        ['Data Fattura:', invoice.invoice_date.strftime('%d/%m/%Y')],
        ['Numero Fattura:', invoice.invoice_number],
        ['Stato:', invoice.status.upper()],
    ]
    
    if invoice.paid_date:
        details_data.append(['Data Pagamento:', invoice.paid_date.strftime('%d/%m/%Y')])
    
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Line items
    items_data = [['Descrizione', 'Importo']]
    items_data.append([invoice.description or 'Servizio', f'€ {invoice.amount:.2f}'])
    
    items_table = Table(items_data, colWidths=[4*inch, 2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Totals
    totals_data = [
        ['Imponibile:', f'€ {invoice.amount:.2f}'],
        ['IVA:', f'€ {invoice.tax_amount:.2f}'],
        ['<b>TOTALE:</b>', f'<b>€ {invoice.total_amount:.2f}</b>'],
    ]
    
    totals_table = Table(totals_data, colWidths=[4.5*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, 1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, 1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('LINEABOVE', (0, 2), (-1, 2), 2, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(totals_table)
    
    # Notes
    if invoice.notes or (settings and settings.invoice_footer):
        elements.append(Spacer(1, 0.4*inch))
        if invoice.notes:
            elements.append(Paragraph(f"<b>Note:</b> {invoice.notes}", styles['Normal']))
        if settings and settings.invoice_footer:
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph(settings.invoice_footer, styles['Normal']))
    
    # Build PDF
    pdf.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'fattura_{invoice.invoice_number}.pdf',
        mimetype='application/pdf'
    )


