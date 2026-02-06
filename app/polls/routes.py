from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Poll, PollOption, PollVote
from datetime import datetime

bp = Blueprint('polls', __name__, url_prefix='/polls')


@bp.before_request
def _check_feature():
    from app.utils import check_feature_enabled
    if not check_feature_enabled('polls'):
        from flask import flash
        flash('Questa funzionalità non è attualmente disponibile.', 'warning')
        return redirect(url_for('main.dashboard'))


def _poll_is_active(poll):
    if not poll.is_active:
        return False
    if poll.closes_at and datetime.utcnow() > poll.closes_at:
        return False
    return True


def _has_voted(poll, user):
    return PollVote.query.filter_by(poll_id=poll.id, user_id=user.id).first() is not None


def _total_votes(poll):
    return sum(o.votes_count or 0 for o in poll.options.all())


@bp.route('/')
@login_required
def index():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    active_polls = [p for p in polls if _poll_is_active(p)]
    closed_polls = [p for p in polls if not _poll_is_active(p)]
    return render_template('polls/index.html',
                           active_polls=active_polls,
                           closed_polls=closed_polls,
                           total_votes=_total_votes)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        multiple_choice = request.form.get('multiple_choice') == 'on'
        is_anonymous = request.form.get('is_anonymous') == 'on'
        closes_at_str = request.form.get('closes_at', '').strip()

        options_texts = request.form.getlist('options')
        options_texts = [o.strip() for o in options_texts if o.strip()]

        if not title:
            flash('Il titolo è obbligatorio.', 'warning')
            return render_template('polls/create.html')

        if len(options_texts) < 2:
            flash('Inserisci almeno 2 opzioni.', 'warning')
            return render_template('polls/create.html')

        closes_at = None
        if closes_at_str:
            try:
                closes_at = datetime.strptime(closes_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Formato data di chiusura non valido.', 'warning')
                return render_template('polls/create.html')

        poll = Poll(
            title=title,
            description=description,
            creator_id=current_user.id,
            multiple_choice=multiple_choice,
            is_anonymous=is_anonymous,
            closes_at=closes_at,
            is_active=True,
        )
        db.session.add(poll)
        db.session.flush()

        for i, text in enumerate(options_texts):
            option = PollOption(poll_id=poll.id, text=text, display_order=i)
            db.session.add(option)

        db.session.commit()
        flash('Sondaggio creato!', 'success')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    return render_template('polls/create.html')


@bp.route('/<int:poll_id>')
@login_required
def detail(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    has_voted = _has_voted(poll, current_user)
    options = poll.options.order_by(PollOption.display_order).all()
    is_active = _poll_is_active(poll)

    results = []
    total = _total_votes(poll)
    for opt in options:
        count = opt.votes_count or 0
        pct = round((count / total * 100), 1) if total > 0 else 0
        results.append({
            'id': opt.id,
            'text': opt.text,
            'count': count,
            'percentage': pct,
        })

    return render_template('polls/detail.html',
                           poll=poll,
                           has_voted=has_voted,
                           options=options,
                           results=results,
                           total_votes=total,
                           is_active=is_active)


@bp.route('/<int:poll_id>/vote', methods=['POST'])
@login_required
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)

    if not _poll_is_active(poll):
        flash('Questo sondaggio è chiuso.', 'warning')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    if _has_voted(poll, current_user):
        flash('Hai già votato in questo sondaggio.', 'info')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    if poll.multiple_choice:
        option_ids = request.form.getlist('option_id', type=int)
    else:
        opt_id = request.form.get('option_id', type=int)
        option_ids = [opt_id] if opt_id else []

    if not option_ids:
        flash('Seleziona almeno un\'opzione.', 'warning')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    valid_options = {o.id: o for o in poll.options.all()}
    for oid in option_ids:
        if oid not in valid_options:
            flash('Opzione non valida.', 'danger')
            return redirect(url_for('polls.detail', poll_id=poll.id))
        pv = PollVote(poll_id=poll.id, option_id=oid, user_id=current_user.id)
        db.session.add(pv)
        valid_options[oid].votes_count = (valid_options[oid].votes_count or 0) + 1

    db.session.commit()
    flash('Voto registrato!', 'success')
    return redirect(url_for('polls.detail', poll_id=poll.id))


@bp.route('/<int:poll_id>/close', methods=['POST'])
@login_required
def close_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    if poll.creator_id != current_user.id and not current_user.is_admin():
        flash('Non hai i permessi per chiudere questo sondaggio.', 'danger')
        return redirect(url_for('polls.detail', poll_id=poll.id))

    poll.is_active = False
    db.session.commit()
    flash('Sondaggio chiuso.', 'success')
    return redirect(url_for('polls.detail', poll_id=poll.id))


@bp.route('/my')
@login_required
def my_polls():
    polls = Poll.query.filter_by(creator_id=current_user.id).order_by(Poll.created_at.desc()).all()
    return render_template('polls/my_polls.html', polls=polls, total_votes=_total_votes, poll_is_active=_poll_is_active)
