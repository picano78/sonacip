"""
PDF Generation Utilities for SONACIP
Provides functions to generate PDF documents for various modules
"""
from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def create_pdf_header(c, title, subtitle=None):
    """Create a standard PDF header"""
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2*cm, 27*cm, title)
    if subtitle:
        c.setFont("Helvetica", 10)
        c.drawString(2*cm, 26.5*cm, subtitle)
    c.setFont("Helvetica", 8)
    c.drawRightString(19*cm, 27*cm, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.line(2*cm, 26.2*cm, 19*cm, 26.2*cm)


def generate_calendar_pdf(events, start_date, end_date, view_type='week'):
    """Generate PDF for calendar events"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=3*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1877f2'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Calendario Eventi", title_style))
    story.append(Paragraph(f"Periodo: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Events table
    if events:
        data = [['Data/Ora', 'Evento', 'Tipo', 'Luogo']]
        for event in events:
            start_str = event.start_datetime.strftime('%d/%m/%Y %H:%M') if hasattr(event, 'start_datetime') and event.start_datetime else 'N/D'
            title = getattr(event, 'title', 'N/D')
            event_type = getattr(event, 'event_type', 'N/D')
            
            # Get location
            if hasattr(event, 'facility') and event.facility:
                location = event.facility.name
            elif hasattr(event, 'location_text') and event.location_text:
                location = event.location_text
            else:
                location = 'N/D'
            
            data.append([start_str, title, event_type, location])
        
        table = Table(data, colWidths=[4*cm, 6*cm, 3*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Nessun evento nel periodo selezionato.", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_planner_pdf(tasks, events):
    """Generate PDF for planner (tasks and events)"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=3*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1877f2'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Planner - Attività ed Eventi", title_style))
    story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Tasks section
    story.append(Paragraph("Attività Assegnate", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))
    
    if tasks:
        data = [['Titolo', 'Scadenza', 'Stato']]
        for task in tasks:
            title = getattr(task, 'title', 'N/D')
            due_date = task.due_date.strftime('%d/%m/%Y') if hasattr(task, 'due_date') and task.due_date else 'N/D'
            status = getattr(task, 'status', 'N/D').replace('_', ' ').title()
            data.append([title, due_date, status])
        
        table = Table(data, colWidths=[8*cm, 4*cm, 5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Nessun task assegnato.", styles['Normal']))
    
    story.append(Spacer(1, 1*cm))
    
    # Events section
    story.append(Paragraph("Eventi", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))
    
    if events:
        data = [['Data', 'Titolo', 'Tipo']]
        for event in events:
            start_str = event.start_date.strftime('%d/%m/%Y') if hasattr(event, 'start_date') and event.start_date else 'N/D'
            title = getattr(event, 'title', 'N/D')
            event_type = getattr(event, 'event_type', 'N/D').title()
            data.append([start_str, title, event_type])
        
        table = Table(data, colWidths=[4*cm, 9*cm, 4*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Nessun evento imminente.", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_contacts_pdf(contacts, status_filter=None):
    """Generate PDF for CRM contacts"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=3*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1877f2'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    title = "Rubrica Contatti CRM"
    if status_filter:
        title += f" - Filtro: {status_filter.title()}"
    
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Contacts table
    if contacts:
        data = [['Nome', 'Email', 'Telefono', 'Azienda', 'Tipo', 'Stato', 'Data Creazione']]
        for contact in contacts:
            full_name = contact.get_full_name() if hasattr(contact, 'get_full_name') else f"{getattr(contact, 'first_name', '')} {getattr(contact, 'last_name', '')}".strip()
            email = getattr(contact, 'email', 'N/D')
            phone = getattr(contact, 'phone', '-')
            company = getattr(contact, 'company', '-')
            contact_type = getattr(contact, 'contact_type', 'N/D')
            status = getattr(contact, 'status', 'N/D')
            created_at = contact.created_at.strftime('%d/%m/%Y') if hasattr(contact, 'created_at') and contact.created_at else 'N/D'
            
            data.append([full_name, email, phone, company, contact_type, status, created_at])
        
        table = Table(data, colWidths=[4*cm, 5*cm, 3*cm, 4*cm, 3*cm, 2.5*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Nessun contatto trovato.", styles['Normal']))
    
    # Footer
    story.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph(f"Totale contatti: {len(contacts) if contacts else 0}", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_crm_data_pdf(contacts_count, activities_count, opportunities_count=0, additional_data=None):
    """Generate PDF for CRM analytics/data summary"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=3*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1877f2'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Report CRM - Dati Analitici", title_style))
    story.append(Paragraph(f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    story.append(Spacer(1, 1*cm))
    
    # Summary table
    data = [
        ['Metrica', 'Valore'],
        ['Totale Contatti', str(contacts_count)],
        ['Totale Attività', str(activities_count)],
        ['Totale Opportunità', str(opportunities_count)]
    ]
    
    if additional_data:
        for key, value in additional_data.items():
            data.append([key, str(value)])
    
    table = Table(data, colWidths=[10*cm, 7*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1877f2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer
