"""
Accounting Routes
Invoice generation, expense tracking, budget management, financial reports
"""
from flask import render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from app.accounting import bp
from app.models import Invoice, InvoiceLineItem, Expense, Budget, Payment, FeePayment, User, Society
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch


@bp.route('/')
@login_required
def index():
    """Accounting dashboard"""
    # Get user's society if they have one
    society = current_user.society if hasattr(current_user, 'society') and current_user.society else None
    
    # Get recent invoices
    if society and current_user.role in ['society_admin', 'staff']:
        invoices = Invoice.query.filter_by(society_id=society.id).order_by(Invoice.created_at.desc()).limit(10).all()
        expenses = Expense.query.filter_by(society_id=society.id).order_by(Expense.created_at.desc()).limit(10).all()
        budgets = Budget.query.filter_by(society_id=society.id, status='active').all()
    else:
        invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.created_at.desc()).limit(10).all()
        expenses = []
        budgets = []
    
    # Calculate summary statistics
    total_revenue = db.session.query(func.sum(Invoice.total_amount)).filter(
        Invoice.status == 'paid',
        Invoice.user_id == current_user.id
    ).scalar() or 0.0
    
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        Expense.status == 'approved'
    ).scalar() or 0.0
    
    pending_invoices = Invoice.query.filter_by(user_id=current_user.id, status='sent').count()
    
    return render_template('accounting/index.html',
                         invoices=invoices,
                         expenses=expenses,
                         budgets=budgets,
                         total_revenue=total_revenue,
                         total_expenses=total_expenses,
                         pending_invoices=pending_invoices)


@bp.route('/invoices')
@login_required
def invoices():
    """List all invoices"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    
    query = Invoice.query.filter_by(user_id=current_user.id)
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('accounting/invoices.html', pagination=pagination, status=status)


@bp.route('/invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    """View invoice details"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check permissions
    if invoice.user_id != current_user.id and current_user.role != 'super_admin':
        flash('You do not have permission to view this invoice.', 'danger')
        return redirect(url_for('accounting.invoices'))
    
    return render_template('accounting/invoice_detail.html', invoice=invoice)


@bp.route('/invoice/<int:invoice_id>/pdf')
@login_required
def download_invoice_pdf(invoice_id):
    """Generate and download invoice PDF"""
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check permissions
    if invoice.user_id != current_user.id and current_user.role != 'super_admin':
        flash('You do not have permission to download this invoice.', 'danger')
        return redirect(url_for('accounting.invoices'))
    
    # Generate PDF
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Title
    elements.append(Paragraph(f"<b>INVOICE {invoice.invoice_number}</b>", styles['Title']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Invoice details
    details_data = [
        ['Invoice Date:', invoice.invoice_date.strftime('%Y-%m-%d')],
        ['Due Date:', invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else 'N/A'],
        ['Status:', invoice.status.upper()],
    ]
    
    if invoice.billing_name:
        details_data.insert(0, ['Bill To:', invoice.billing_name])
    
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Line items
    if invoice.line_items.count() > 0:
        line_items_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
        for item in invoice.line_items:
            line_items_data.append([
                item.description,
                str(item.quantity),
                f"{item.unit_price:.2f}",
                f"{item.amount:.2f}"
            ])
        
        line_items_table = Table(line_items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
        line_items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(line_items_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Totals
    totals_data = [
        ['Subtotal:', f"{invoice.amount:.2f} {invoice.currency}"],
        ['Tax:', f"{invoice.tax_amount:.2f} {invoice.currency}"],
        ['Total:', f"{invoice.total_amount:.2f} {invoice.currency}"],
    ]
    
    totals_table = Table(totals_data, colWidths=[5*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('LINEABOVE', (0, 2), (-1, 2), 2, colors.black),
    ]))
    elements.append(totals_table)
    
    if invoice.notes:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(f"<b>Notes:</b> {invoice.notes}", styles['Normal']))
    
    pdf.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'invoice_{invoice.invoice_number}.pdf',
        mimetype='application/pdf'
    )


@bp.route('/invoice/generate/<string:payment_type>/<int:payment_id>', methods=['POST'])
@login_required
def generate_invoice(payment_type, payment_id):
    """Generate invoice from payment or fee_payment"""
    try:
        # Check if invoice already exists
        if payment_type == 'payment':
            existing = Invoice.query.filter_by(payment_id=payment_id).first()
            payment = Payment.query.get_or_404(payment_id)
            amount = payment.amount
            user_id = payment.user_id
            society_id = payment.society_id
            description = payment.description or "Payment"
        elif payment_type == 'fee_payment':
            existing = Invoice.query.filter_by(fee_payment_id=payment_id).first()
            payment = FeePayment.query.get_or_404(payment_id)
            amount = payment.amount
            user_id = payment.user_id
            society_id = payment.fee.society_id if payment.fee else None
            description = f"Fee Payment - {payment.fee.title if payment.fee else 'Fee'}"
        else:
            flash('Invalid payment type.', 'danger')
            return redirect(url_for('accounting.index'))
        
        if existing:
            flash('Invoice already exists for this payment.', 'warning')
            return redirect(url_for('accounting.view_invoice', invoice_id=existing.id))
        
        # Create new invoice
        invoice = Invoice(
            user_id=user_id,
            society_id=society_id,
            amount=amount,
            tax_amount=0.0,  # Can be calculated based on tax rules
            total_amount=amount,
            status='paid' if payment.status == 'completed' else 'draft',
            description=description,
            invoice_date=datetime.utcnow(),
            paid_date=payment.paid_at if hasattr(payment, 'paid_at') and payment.paid_at else None
        )
        
        if payment_type == 'payment':
            invoice.payment_id = payment_id
        else:
            invoice.fee_payment_id = payment_id
        
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Generate invoice number
        invoice.invoice_number = invoice.generate_invoice_number()
        
        db.session.commit()
        
        flash('Invoice generated successfully!', 'success')
        return redirect(url_for('accounting.view_invoice', invoice_id=invoice.id))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error generating invoice: {str(e)}', 'danger')
        return redirect(url_for('accounting.index'))


@bp.route('/expenses')
@login_required
def expenses():
    """List expenses"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    
    query = Expense.query.filter_by(user_id=current_user.id)
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Expense.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('accounting/expenses.html', pagination=pagination, status=status)


@bp.route('/expense/create', methods=['GET', 'POST'])
@login_required
def create_expense():
    """Create new expense"""
    if request.method == 'POST':
        try:
            society_id = request.form.get('society_id', type=int)
            amount = request.form.get('amount', type=float)
            category = request.form.get('category')
            description = request.form.get('description')
            vendor_name = request.form.get('vendor_name')
            expense_date = datetime.strptime(request.form.get('expense_date'), '%Y-%m-%d')
            
            expense = Expense(
                society_id=society_id,
                user_id=current_user.id,
                amount=amount,
                category=category,
                description=description,
                vendor_name=vendor_name,
                expense_date=expense_date,
                status='pending'
            )
            
            db.session.add(expense)
            db.session.commit()
            
            flash('Expense created successfully!', 'success')
            return redirect(url_for('accounting.expenses'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating expense: {str(e)}', 'danger')
    
    societies = Society.query.all() if current_user.role == 'super_admin' else []
    return render_template('accounting/expense_form.html', societies=societies)


@bp.route('/budgets')
@login_required
def budgets():
    """List budgets"""
    society = current_user.society if hasattr(current_user, 'society') and current_user.society else None
    
    if not society and current_user.role not in ['super_admin', 'society_admin']:
        flash('You do not have access to budgets.', 'danger')
        return redirect(url_for('accounting.index'))
    
    budgets_list = Budget.query.filter_by(society_id=society.id).order_by(Budget.created_at.desc()).all() if society else []
    
    return render_template('accounting/budgets.html', budgets=budgets_list)


@bp.route('/reports/financial')
@login_required
def financial_reports():
    """Financial reports dashboard"""
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # Get financial data
    if hasattr(current_user, 'society') and current_user.society:
        society_id = current_user.society.id
        
        # Revenue by month
        revenue_query = db.session.query(
            extract('month', Invoice.invoice_date).label('month'),
            func.sum(Invoice.total_amount).label('total')
        ).filter(
            Invoice.society_id == society_id,
            Invoice.status == 'paid',
            extract('year', Invoice.invoice_date) == year
        ).group_by(extract('month', Invoice.invoice_date)).all()
        
        # Expenses by month
        expense_query = db.session.query(
            extract('month', Expense.expense_date).label('month'),
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.society_id == society_id,
            Expense.status == 'approved',
            extract('year', Expense.expense_date) == year
        ).group_by(extract('month', Expense.expense_date)).all()
        
        # Expenses by category
        category_query = db.session.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.society_id == society_id,
            Expense.status == 'approved',
            extract('year', Expense.expense_date) == year
        ).group_by(Expense.category).all()
        
        revenue_by_month = {int(m): float(t) for m, t in revenue_query}
        expenses_by_month = {int(m): float(t) for m, t in expense_query}
        expenses_by_category = {c: float(t) for c, t in category_query}
    else:
        revenue_by_month = {}
        expenses_by_month = {}
        expenses_by_category = {}
    
    return render_template('accounting/financial_reports.html',
                         year=year,
                         month=month,
                         revenue_by_month=revenue_by_month,
                         expenses_by_month=expenses_by_month,
                         expenses_by_category=expenses_by_category)
