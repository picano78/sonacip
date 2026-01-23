"""
Main routes
"""
from flask import render_template, redirect, url_for
from flask_login import current_user, login_required
from app.main import bp


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


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard - redirect to appropriate view"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_society():
        return redirect(url_for('social.society_dashboard'))
    else:
        return redirect(url_for('social.feed'))
