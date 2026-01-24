"""
CRM Routes
Contact and opportunity management
"""
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.crm import bp
from app.crm.forms import ContactForm, OpportunityForm, ActivityForm
from app.models import Contact, Opportunity, CRMActivity, User, AuditLog
from datetime import datetime


@bp.route('/')
@login_required
def index():
    """CRM Dashboard"""
    # Only società and staff can access CRM
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get statistics
    if current_user.role == 'societa':
        contacts = Contact.query.filter_by(society_id=current_user.id).all()
        opportunities = Opportunity.query.filter_by(society_id=current_user.id).all()
    elif current_user.role == 'staff' and current_user.society_id:
        contacts = Contact.query.filter_by(society_id=current_user.society_id).all()
        opportunities = Opportunity.query.filter_by(society_id=current_user.society_id).all()
    else:
        contacts = Contact.query.all()
        opportunities = Opportunity.query.all()
    
    # Calculate stats
    total_contacts = len(contacts)
    new_contacts = len([c for c in contacts if c.status == 'new'])
    converted_contacts = len([c for c in contacts if c.status == 'converted'])
    
    total_opportunities = len(opportunities)
    open_opportunities = len([o for o in opportunities if o.stage not in ['closed_won', 'closed_lost']])
    won_opportunities = len([o for o in opportunities if o.stage == 'closed_won'])
    
    try:
        total_value = sum([float(o.value or 0) for o in opportunities if o.value and o.stage not in ['closed_lost']])
    except (ValueError, TypeError):
        total_value = 0
    
    return render_template('crm/index.html',
                         total_contacts=total_contacts,
                         new_contacts=new_contacts,
                         converted_contacts=converted_contacts,
                         total_opportunities=total_opportunities,
                         open_opportunities=open_opportunities,
                         won_opportunities=won_opportunities,
                         total_value=total_value,
                         recent_contacts=contacts[:5],
                         recent_opportunities=opportunities[:5])


@bp.route('/contacts')
@login_required
def contacts():
    """List all contacts"""
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    # Filter by society
    if current_user.role == 'societa':
        contacts = Contact.query.filter_by(society_id=current_user.id).order_by(Contact.created_at.desc()).all()
    elif current_user.role == 'staff' and current_user.society_id:
        contacts = Contact.query.filter_by(society_id=current_user.society_id).order_by(Contact.created_at.desc()).all()
    else:
        contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    
    # Filter by status if requested
    status_filter = request.args.get('status')
    if status_filter:
        contacts = [c for c in contacts if c.status == status_filter]
    
    return render_template('crm/contacts.html', contacts=contacts, status_filter=status_filter)


@bp.route('/contacts/new', methods=['GET', 'POST'])
@login_required
def new_contact():
    """Create new contact"""
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    form = ContactForm()
    
    if form.validate_on_submit():
        # Determine society_id
        if current_user.role == 'societa':
            society_id = current_user.id
        elif current_user.role == 'staff' and current_user.society_id:
            society_id = current_user.society_id
        else:
            society_id = None
        
        contact = Contact(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            company=form.company.data,
            position=form.position.data,
            contact_type=form.contact_type.data,
            status=form.status.data,
            source=form.source.data,
            notes=form.notes.data,
            address=form.address.data,
            city=form.city.data,
            postal_code=form.postal_code.data,
            society_id=society_id,
            created_by=current_user.id
        )
        
        db.session.add(contact)
        db.session.commit()
        
        flash('Contatto creato con successo!', 'success')
        return redirect(url_for('crm.contacts'))
    
    return render_template('crm/contact_form.html', form=form, title='Nuovo Contatto')


@bp.route('/contacts/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    """View contact details"""
    contact = Contact.query.get_or_404(contact_id)
    
    # Check access
    if current_user.role == 'societa' and contact.society_id != current_user.id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.contacts'))
    elif current_user.role == 'staff' and contact.society_id != current_user.society_id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.contacts'))
    
    # Get related opportunities and activities
    opportunities = Opportunity.query.filter_by(contact_id=contact_id).all()
    activities = CRMActivity.query.filter_by(contact_id=contact_id).order_by(CRMActivity.created_at.desc()).all()
    
    return render_template('crm/contact_detail.html', 
                         contact=contact, 
                         opportunities=opportunities,
                         activities=activities)


@bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(contact_id):
    """Edit contact"""
    contact = Contact.query.get_or_404(contact_id)
    
    # Check access
    if current_user.role == 'societa' and contact.society_id != current_user.id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.contacts'))
    elif current_user.role == 'staff' and contact.society_id != current_user.society_id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.contacts'))
    
    form = ContactForm(obj=contact)
    
    if form.validate_on_submit():
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.email = form.email.data
        contact.phone = form.phone.data
        contact.company = form.company.data
        contact.position = form.position.data
        contact.contact_type = form.contact_type.data
        contact.status = form.status.data
        contact.source = form.source.data
        contact.notes = form.notes.data
        contact.address = form.address.data
        contact.city = form.city.data
        contact.postal_code = form.postal_code.data
        contact.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash('Contatto aggiornato!', 'success')
        return redirect(url_for('crm.contact_detail', contact_id=contact_id))
    
    return render_template('crm/contact_form.html', form=form, title='Modifica Contatto', contact=contact)


@bp.route('/opportunities')
@login_required
def opportunities():
    """List all opportunities"""
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    # Filter by society
    if current_user.role == 'societa':
        opportunities = Opportunity.query.filter_by(society_id=current_user.id).order_by(Opportunity.created_at.desc()).all()
    elif current_user.role == 'staff' and current_user.society_id:
        opportunities = Opportunity.query.filter_by(society_id=current_user.society_id).order_by(Opportunity.created_at.desc()).all()
    else:
        opportunities = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    
    return render_template('crm/opportunities.html', opportunities=opportunities)


@bp.route('/opportunities/new', methods=['GET', 'POST'])
@login_required
def new_opportunity():
    """Create new opportunity"""
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    form = OpportunityForm()
    
    # Populate contact choices
    if current_user.role == 'societa':
        contacts = Contact.query.filter_by(society_id=current_user.id).all()
    elif current_user.role == 'staff' and current_user.society_id:
        contacts = Contact.query.filter_by(society_id=current_user.society_id).all()
    else:
        contacts = Contact.query.all()
    
    form.contact_id.choices = [(0, 'Nessuno')] + [(c.id, f'{c.first_name} {c.last_name}') for c in contacts]
    
    if form.validate_on_submit():
        # Determine society_id
        if current_user.role == 'societa':
            society_id = current_user.id
        elif current_user.role == 'staff' and current_user.society_id:
            society_id = current_user.society_id
        else:
            society_id = None
        
        opportunity = Opportunity(
            title=form.title.data,
            description=form.description.data,
            opportunity_type=form.opportunity_type.data,
            stage=form.stage.data,
            value=form.value.data,
            probability=form.probability.data,
            expected_close_date=form.expected_close_date.data,
            contact_id=form.contact_id.data if form.contact_id.data != 0 else None,
            society_id=society_id,
            created_by=current_user.id
        )
        
        db.session.add(opportunity)
        db.session.commit()
        
        flash('Opportunità creata con successo!', 'success')
        return redirect(url_for('crm.opportunities'))
    
    return render_template('crm/opportunity_form.html', form=form, title='Nuova Opportunità')


@bp.route('/opportunities/<int:opp_id>')
@login_required
def opportunity_detail(opp_id):
    """View opportunity details"""
    opportunity = Opportunity.query.get_or_404(opp_id)
    
    # Check access
    if current_user.role == 'societa' and opportunity.society_id != current_user.id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.opportunities'))
    elif current_user.role == 'staff' and opportunity.society_id != current_user.society_id:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('crm.opportunities'))
    
    # Get related activities
    activities = CRMActivity.query.filter_by(opportunity_id=opp_id).order_by(CRMActivity.created_at.desc()).all()
    
    return render_template('crm/opportunity_detail.html', 
                         opportunity=opportunity,
                         activities=activities)


@bp.route('/activities/new', methods=['GET', 'POST'])
@login_required
def new_activity():
    """Log new activity"""
    if current_user.role not in ['super_admin', 'societa', 'staff']:
        flash('Accesso non autorizzato.', 'danger')
        return redirect(url_for('main.index'))
    
    form = ActivityForm()
    
    # Populate choices
    if current_user.role == 'societa':
        contacts = Contact.query.filter_by(society_id=current_user.id).all()
        opportunities = Opportunity.query.filter_by(society_id=current_user.id).all()
    elif current_user.role == 'staff' and current_user.society_id:
        contacts = Contact.query.filter_by(society_id=current_user.society_id).all()
        opportunities = Opportunity.query.filter_by(society_id=current_user.society_id).all()
    else:
        contacts = Contact.query.all()
        opportunities = Opportunity.query.all()
    
    form.contact_id.choices = [(0, 'Nessuno')] + [(c.id, f'{c.first_name} {c.last_name}') for c in contacts]
    form.opportunity_id.choices = [(0, 'Nessuna')] + [(o.id, o.title) for o in opportunities]
    
    if form.validate_on_submit():
        activity = CRMActivity(
            activity_type=form.activity_type.data,
            subject=form.subject.data,
            description=form.description.data,
            activity_date=form.activity_date.data or datetime.utcnow(),
            completed=form.completed.data,
            contact_id=form.contact_id.data if form.contact_id.data != 0 else None,
            opportunity_id=form.opportunity_id.data if form.opportunity_id.data != 0 else None,
            created_by=current_user.id
        )
        
        db.session.add(activity)
        db.session.commit()
        
        flash('Attività registrata!', 'success')
        
        # Redirect based on context
        if activity.opportunity_id:
            return redirect(url_for('crm.opportunity_detail', opp_id=activity.opportunity_id))
        elif activity.contact_id:
            return redirect(url_for('crm.contact_detail', contact_id=activity.contact_id))
        else:
            return redirect(url_for('crm.index'))
    
    # Pre-fill from query params
    contact_id = request.args.get('contact_id', type=int)
    opportunity_id = request.args.get('opportunity_id', type=int)
    
    if contact_id:
        form.contact_id.data = contact_id
    if opportunity_id:
        form.opportunity_id.data = opportunity_id
    
    return render_template('crm/activity_form.html', form=form, title='Nuova Attività')
