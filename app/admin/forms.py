"""
Admin forms
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, BooleanField, TextAreaField, PasswordField, IntegerField, DateTimeField
from wtforms.validators import DataRequired, Email, Optional, Length
from wtforms.validators import URL
from app.models import Role


def _load_role_choices(include_empty=False):
    """Load active roles from DB with safe fallback."""
    try:
        roles = Role.query.filter_by(is_active=True).order_by(Role.level.desc()).all()
        choices = [(r.name, r.display_name or r.name) for r in roles]
    except Exception:
        choices = [
            ('super_admin', 'Super Admin'),
            ('society_admin', 'Admin Società'),
            ('societa', 'Società Sportiva'),
            ('coach', 'Coach'),
            ('staff', 'Staff'),
            ('athlete', 'Athlete'),
            ('atleta', 'Atleta'),
            ('appassionato', 'Appassionato')
        ]
    if include_empty:
        return [('', 'Tutti')] + choices
    return choices


class UserEditForm(FlaskForm):
    """Form for editing users"""
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    first_name = StringField('Nome', validators=[Optional()])
    last_name = StringField('Cognome', validators=[Optional()])
    phone = StringField('Telefono', validators=[Optional()])
    role = SelectField('Ruolo', choices=[], validators=[DataRequired()])
    is_active = BooleanField('Account Attivo')
    is_verified = BooleanField('Account Verificato')
    is_banned = BooleanField('Account Bannato')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role.choices = _load_role_choices()


class UserSearchForm(FlaskForm):
    """Form for searching users"""
    query = StringField('Cerca', validators=[Optional()])
    role = SelectField('Ruolo', choices=[], validators=[Optional()])
    status = SelectField('Stato', choices=[
        ('', 'Tutti'),
        ('active', 'Attivi'),
        ('inactive', 'Disattivati'),
        ('verified', 'Verificati'),
        ('unverified', 'Non Verificati')
    ], validators=[Optional()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role.choices = _load_role_choices(include_empty=True)


class PrivacySettingsForm(FlaskForm):
    """Form per gestire banner privacy/cookie"""
    banner_enabled = BooleanField('Mostra banner privacy')
    consent_message = TextAreaField('Messaggio banner', validators=[DataRequired(), Length(max=2000)])
    privacy_url = StringField('Link privacy policy', validators=[Optional(), Length(max=255)])
    cookie_url = StringField('Link cookie policy', validators=[Optional(), Length(max=255)])


class AdsSettingsForm(FlaskForm):
    """Form per tariffe inserzioni/promo post"""
    price_per_day = StringField('Prezzo per giorno (€)', validators=[DataRequired()])
    price_per_thousand_views = StringField('Prezzo per 1000 visualizzazioni (€)', validators=[DataRequired()])
    default_duration_days = StringField('Durata predefinita (giorni)', validators=[DataRequired()])
    default_views = StringField('Impression predefinite', validators=[DataRequired()])


class AdCampaignForm(FlaskForm):
    name = StringField('Nome campagna', validators=[DataRequired(), Length(max=200)])
    objective = SelectField('Obiettivo', choices=[
        ('traffic', 'Traffico'),
        ('awareness', 'Awareness'),
    ], validators=[Optional()])
    society_id = StringField('Society ID (opzionale)', validators=[Optional(), Length(max=20)])
    autopilot = BooleanField('Autopilot (ottimizza CTR)', default=True)
    is_active = BooleanField('Attiva', default=True)
    starts_at = DateTimeField('Inizio (UTC) YYYY-mm-dd HH:MM', format='%Y-%m-%d %H:%M', validators=[Optional()])
    ends_at = DateTimeField('Fine (UTC) YYYY-mm-dd HH:MM', format='%Y-%m-%d %H:%M', validators=[Optional()])
    max_impressions = IntegerField('Max impression (opzionale)', validators=[Optional()])
    max_clicks = IntegerField('Max click (opzionale)', validators=[Optional()])


class AdCreativeForm(FlaskForm):
    campaign_id = IntegerField('Campaign ID', validators=[DataRequired()])
    placement = SelectField('Placement', choices=[
        ('feed_inline', 'Feed (inline)'),
        ('sidebar_card', 'Sidebar (card)'),
    ], validators=[DataRequired()])
    headline = StringField('Headline', validators=[Optional(), Length(max=120)])
    body = TextAreaField('Body', validators=[Optional(), Length(max=500)])
    image_url = StringField('Image URL', validators=[Optional(), Length(max=500)])
    link_url = StringField('Link URL', validators=[DataRequired(), Length(max=800)])
    cta_label = StringField('CTA', validators=[Optional(), Length(max=50)])
    weight = IntegerField('Weight (solo se autopilot off)', validators=[Optional()])
    is_active = BooleanField('Attiva', default=True)


class SocialSettingsAdminForm(FlaskForm):
    feed_enabled = BooleanField('Abilita feed social')
    allow_likes = BooleanField('Abilita like')
    allow_comments = BooleanField('Abilita commenti')
    allow_shares = BooleanField('Abilita condivisioni')
    allow_photos = BooleanField('Consenti pubblicazione foto')
    allow_videos = BooleanField('Consenti pubblicazione video')
    boost_official = BooleanField('Dai priorità a contenuti ufficiali')
    mute_user_posts = BooleanField('Silenzia post utenti generici')
    max_posts_per_day = StringField('Max post per giorno (per ruolo)', validators=[Optional()])
    boosted_types = TextAreaField('Tipi contenuto da potenziare (JSON array)', validators=[Optional()])
    muted_types = TextAreaField('Tipi contenuto da silenziare (JSON array)', validators=[Optional()])


class AppearanceSettingsForm(FlaskForm):
    primary_color = StringField('Colore primario', validators=[Optional(), Length(max=7)])
    secondary_color = StringField('Colore secondario', validators=[Optional(), Length(max=7)])
    accent_color = StringField('Colore accent', validators=[Optional(), Length(max=7)])
    font_family = StringField('Font', validators=[Optional(), Length(max=100)])
    logo_upload = FileField('Carica logo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Solo immagini!')])
    logo_url = StringField('Logo URL', validators=[Optional(), URL()])
    favicon_url = StringField('Favicon URL', validators=[Optional(), URL()])
    app_icon_upload = FileField('Carica icona app', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Solo immagini!')])
    app_icon_url = StringField('Icona app URL', validators=[Optional(), URL()])
    layout_style = StringField('Layout', validators=[Optional(), Length(max=50)])


class ModerationRuleForm(FlaskForm):
    """Form for moderation rules"""
    name = StringField('Nome regola', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrizione', validators=[Optional(), Length(max=1000)])
    rule_type = SelectField('Tipo regola', choices=[
        ('keyword_filter', 'Filtro parole chiave'),
        ('spam_detection', 'Rilevamento spam'),
        ('content_filter', 'Filtro contenuto')
    ], validators=[DataRequired()])
    keywords = TextAreaField('Parole chiave (separate da virgola)', validators=[Optional()])
    action = SelectField('Azione', choices=[
        ('flag', 'Segnala'),
        ('hide', 'Nascondi'),
        ('delete', 'Elimina')
    ], default='flag', validators=[DataRequired()])
    severity = SelectField('Severità', choices=[
        ('low', 'Bassa'),
        ('medium', 'Media'),
        ('high', 'Alta')
    ], default='medium', validators=[DataRequired()])


class StorageSettingsForm(FlaskForm):
    storage_backend = SelectField('Backend', choices=[('local', 'Locale')], validators=[DataRequired()])
    base_path = StringField('Percorso base salvataggi', validators=[DataRequired(), Length(max=255)])
    preferred_image_format = SelectField('Formato immagini', choices=[('webp', 'WEBP'), ('jpeg', 'JPEG'), ('jpg', 'JPG')], validators=[Optional()])
    image_quality = StringField('Qualità immagini (1-100)', validators=[Optional(), Length(max=3)])
    preferred_video_format = StringField('Formato video', validators=[Optional(), Length(max=10)])
    video_bitrate = StringField('Bitrate video (bps)', validators=[Optional(), Length(max=10)])
    video_max_width = StringField('Larghezza max video (px)', validators=[Optional(), Length(max=5)])
    max_image_mb = StringField('Limite immagini (MB)', validators=[Optional(), Length(max=4)])
    max_video_mb = StringField('Limite video (MB)', validators=[Optional(), Length(max=4)])


class SiteCustomizationForm(FlaskForm):
    navbar_brand_text = StringField('Testo brand navbar', validators=[Optional(), Length(max=100)])
    navbar_brand_icon = StringField('Icona navbar (Bootstrap Icons)', validators=[Optional(), Length(max=50)])
    footer_html = TextAreaField('Footer HTML', validators=[Optional(), Length(max=20000)])
    custom_css = TextAreaField('CSS personalizzato', validators=[Optional(), Length(max=50000)])


class PageCustomizationForm(FlaskForm):
    slug = StringField('Slug pagina (es: main.index)', validators=[DataRequired(), Length(max=120)])
    title = StringField('Titolo pagina (tab)', validators=[Optional(), Length(max=200)])
    hero_title = StringField('Titolo hero', validators=[Optional(), Length(max=200)])
    hero_subtitle = StringField('Sottotitolo hero', validators=[Optional(), Length(max=500)])
    body_html = TextAreaField('Contenuto HTML', validators=[Optional(), Length(max=50000)])


class DashboardTemplateForm(FlaskForm):
    role_name = SelectField('Ruolo', choices=[], validators=[Optional()])
    name = StringField('Nome template', validators=[DataRequired(), Length(max=200)])
    layout = SelectField('Layout', choices=[('grid', 'Grid')], validators=[DataRequired()])
    widgets = TextAreaField('Widgets (JSON array)', validators=[DataRequired(), Length(max=50000)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # '' means global default
        self.role_name.choices = [('', 'Default (tutti)')] + _load_role_choices(include_empty=False)


class NavigationConfigForm(FlaskForm):
    links_json = TextAreaField('Link navbar (JSON array)', validators=[DataRequired(), Length(max=50000)])


class SmtpSettingsForm(FlaskForm):
    enabled = BooleanField('Abilita invio email (SMTP)')
    host = StringField('Host SMTP', validators=[Optional(), Length(max=255)])
    port = StringField('Porta', validators=[Optional(), Length(max=6)])
    use_tls = BooleanField('Usa STARTTLS')
    username = StringField('Username', validators=[Optional(), Length(max=255)])
    password = PasswordField('Password', validators=[Optional(), Length(max=255)])
    default_sender = StringField('Mittente predefinito', validators=[Optional(), Length(max=255)])
    test_recipient = StringField('Invia test a (email)', validators=[Optional(), Email(), Length(max=255)])


