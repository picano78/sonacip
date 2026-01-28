"""
Main routes
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.utils import check_permission

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Homepage - redirect based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for('social.feed'))
    return render_template('main/index.html')


@bp.route('/about')
def about():
    """About page"""
    return render_template('main/about.html')


@bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('main/contact.html')


@bp.route('/healthz')
def healthz():
    """Lightweight health check for uptime monitoring"""
    return {'status': 'ok'}, 200


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard - redirect to appropriate view"""
    if check_permission(current_user, 'admin', 'access'):
        return redirect(url_for('admin.dashboard'))
    if check_permission(current_user, 'society', 'manage'):
        return redirect(url_for('social.society_dashboard'))
    return redirect(url_for('social.feed'))
