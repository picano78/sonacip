"""Tournament routes implementing multi-format tournaments with scheduling, scoring, standings."""
from datetime import datetime, timedelta, timezone
import math
import random
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy import false
from sqlalchemy.orm import joinedload
from app import db, limiter
from app.tournaments.forms import TournamentForm, TournamentTeamForm, TournamentMatchForm, MatchScoreForm
from app.models import Tournament, TournamentTeam, TournamentMatch, TournamentStanding, SocietyCalendarEvent, Post, CRMActivity, SocialSetting
from app.automation.utils import execute_rules
from app.utils import permission_required, check_permission, log_action, get_active_society_id

bp = Blueprint('tournaments', __name__, url_prefix='/tournaments')


def _can_view_tournament(tournament: Tournament) -> bool:
    if check_permission(current_user, 'admin', 'access'):
        return True
    if tournament.created_by == current_user.id:
        return True
    if tournament.society_id:
        return check_permission(current_user, 'tournaments', 'view', tournament.society_id)
    return False


def _can_manage_tournament(tournament: Tournament) -> bool:
    if check_permission(current_user, 'admin', 'access'):
        return True
    if tournament.created_by == current_user.id:
        return True
    if tournament.society_id:
        return check_permission(current_user, 'tournaments', 'manage', tournament.society_id)
    return False


def _require_view(tournament: Tournament) -> None:
    if not _can_view_tournament(tournament):
        abort(403)


def _require_manage(tournament: Tournament) -> None:
    if not _can_manage_tournament(tournament):
        abort(403)


def _get_society_id():
    # Admin: optional explicit sid from querystring, otherwise follow active scope.
    if check_permission(current_user, 'admin', 'access'):
        return request.args.get('society_id', type=int) or get_active_society_id(current_user)
    # Non-admin: follow active society scope.
    return get_active_society_id(current_user)


def _trigger(event_type, payload):
    execute_rules(event_type, payload)


def _post_kwargs_for_tournament(tournament: Tournament, audience_override: str | None = None) -> dict:
    """
    Return Post scoping kwargs depending on tournament ownership.
    - Society tournaments: scoped to society feed (audience='society').
    - Personal tournaments: public feed (audience='public').
    """
    if tournament.society_id:
        if audience_override == "public":
            return {"audience": "public", "society_id": None, "is_public": True}
        return {"audience": "society", "society_id": tournament.society_id, "is_public": False}
    return {"audience": "public", "society_id": None, "is_public": True}


def _recent_duplicate_post(user_id: int, post_type: str, content: str, minutes: int = 10) -> bool:
    """Best-effort dedupe to avoid double-posting the same message."""
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        exists = (
            Post.query.filter_by(user_id=user_id, post_type=post_type)
            .filter(Post.content == content, Post.created_at >= since)
            .first()
        )
        return exists is not None
    except Exception:
        return False


def _winner_of(match: TournamentMatch) -> TournamentTeam | None:
    if match and match.winner_team_id:
        return db.session.get(TournamentTeam, match.winner_team_id)
    return None


def _propagate_knockout_winner(match: TournamentMatch) -> None:
    """Place winner into next round match slot based on bracket position."""
    if not getattr(match, "is_bracket", False):
        return
    if not match.winner_team_id or not match.round_number:
        return
    next_round = int(match.round_number) + 1
    next_pos = int(match.position or 0) // 2
    slot_home = (int(match.position or 0) % 2) == 0
    nxt = TournamentMatch.query.filter_by(
        tournament_id=match.tournament_id,
        round_number=next_round,
        position=next_pos,
    ).first()
    if not nxt:
        return
    if slot_home:
        nxt.home_team_id = match.winner_team_id
    else:
        nxt.away_team_id = match.winner_team_id
    db.session.add(nxt)


def _round_label(rounds_total: int, round_number: int) -> str:
    remaining = 2 ** (rounds_total - round_number + 1)
    if remaining == 2:
        return "Finale"
    if remaining == 4:
        return "Semifinale"
    if remaining == 8:
        return "Quarti"
    if remaining == 16:
        return "Ottavi"
    return f"Round {round_number}"


def _generate_knockout_bracket(tournament: Tournament, teams: list[TournamentTeam], seeding: str) -> int:
    """
    Generate single-elimination bracket matches.
    Returns number of matches created.
    """
    if len(teams) < 2:
        return 0
    if tournament.matches.count() > 0:
        return 0

    # Decide initial ordering
    ordered = list(teams)
    if seeding == "random":
        random.shuffle(ordered)
    else:
        ordered.sort(key=lambda t: (t.seed is None, t.seed if t.seed is not None else 10**9, t.name.lower()))

    n = len(ordered)
    bracket_size = 1 << (n - 1).bit_length()  # next power of 2
    rounds_total = int(math.log2(bracket_size))

    # Pad with None (byes / TBD)
    slots: list[TournamentTeam | None] = ordered + [None] * (bracket_size - n)

    created = 0
    # Round 1
    for pos in range(bracket_size // 2):
        a = slots[pos * 2]
        b = slots[pos * 2 + 1]
        m = TournamentMatch(
            tournament_id=tournament.id,
            home_team_id=a.id if a else None,
            away_team_id=b.id if b else None,
            round_number=1,
            position=pos,
            round_label=_round_label(rounds_total, 1),
            is_bracket=True,
            status="scheduled",
        )
        # Auto-advance BYE if only one team present
        if (a and not b) or (b and not a):
            winner = a if a else b
            m.status = "played"
            m.home_score = 1
            m.away_score = 0
            m.winner_team_id = winner.id if winner else None
        db.session.add(m)
        created += 1
    db.session.flush()

    # Create remaining rounds as placeholders
    for r in range(2, rounds_total + 1):
        matches_in_round = bracket_size // (2 ** r)
        for pos in range(matches_in_round):
            db.session.add(
                TournamentMatch(
                    tournament_id=tournament.id,
                    home_team_id=None,
                    away_team_id=None,
                    round_number=r,
                    position=pos,
                    round_label=_round_label(rounds_total, r),
                    is_bracket=True,
                    status="scheduled",
                )
            )
            created += 1
        db.session.flush()

    # Propagate any BYE winners from round 1 forward
    bye_matches = TournamentMatch.query.filter_by(tournament_id=tournament.id, round_number=1).all()
    for m in bye_matches:
        _propagate_knockout_winner(m)

    db.session.commit()
    return created


@bp.route('/')
@login_required
def list_tournaments():
    sid = _get_society_id()
    query = Tournament.query
    if check_permission(current_user, 'admin', 'access'):
        if sid:
            query = query.filter_by(society_id=sid)
        tournaments = query.order_by(Tournament.created_at.desc()).all()
    else:
        # Show society tournaments (if any) + personal tournaments created by user.
        if sid:
            query = query.filter((Tournament.society_id == sid) | (Tournament.created_by == current_user.id))
        else:
            query = query.filter(Tournament.created_by == current_user.id)
        tournaments = query.order_by(Tournament.created_at.desc()).all()
    return render_template('tournaments/index.html', tournaments=tournaments)


@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_tournament():
    sid = _get_society_id()
    form = TournamentForm()
    if form.validate_on_submit():
        tournament = Tournament(
            society_id=sid,
            created_by=current_user.id,
            name=form.name.data,
            description=form.description.data,
            format=form.format.data,
            season=form.season.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status='scheduled',
            auto_select_criteria=form.auto_criteria.data if form.auto_select.data else None
        )
        db.session.add(tournament)
        db.session.commit()
        # CRM activity log for key action
        try:
            activity = CRMActivity(
                activity_type='note',
                subject='Torneo creato',
                description=f'Torneo "{tournament.name}" creato da {current_user.get_full_name()}',
                created_by=current_user.id
            )
            db.session.add(activity)
            db.session.commit()
        except Exception:
            db.session.rollback()
        _trigger('tournament.created', {'tournament_id': tournament.id})
        flash('Torneo creato.', 'success')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
    return render_template('tournaments/create.html', form=form)


@bp.route('/<int:tournament_id>')
@login_required
def view_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_view(tournament)
    teams = tournament.teams.order_by(TournamentTeam.name.asc()).all()
    matches = (
        tournament.matches.options(
            joinedload(TournamentMatch.home_team),
            joinedload(TournamentMatch.away_team),
            joinedload(TournamentMatch.winner_team),
        )
        .order_by(TournamentMatch.match_date.asc())
        .all()
    )
    standings = tournament.standings.order_by(TournamentStanding.points.desc(), TournamentStanding.goals_for.desc()).all()
    bracket_matches = (
        tournament.matches.options(
            joinedload(TournamentMatch.home_team),
            joinedload(TournamentMatch.away_team),
            joinedload(TournamentMatch.winner_team),
        )
        .filter_by(is_bracket=True)
        .order_by(TournamentMatch.round_number.asc(), TournamentMatch.position.asc())
        .all()
    )
    bracket_rounds = {}
    for m in bracket_matches:
        bracket_rounds.setdefault(m.round_number, []).append(m)
    return render_template(
        'tournaments/detail.html',
        tournament=tournament,
        teams=teams,
        matches=matches,
        standings=standings,
        bracket_rounds=bracket_rounds,
        can_manage=_can_manage_tournament(tournament),
    )


@bp.route('/<int:tournament_id>/publish', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def publish_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)

    try:
        settings = SocialSetting.query.first()
        if settings and not settings.feed_enabled and not check_permission(current_user, 'admin', 'access'):
            flash("Pubblicazione sul feed social disabilitata dall'amministratore.", 'warning')
            return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
    except Exception:
        pass

    teams_count = 0
    try:
        teams_count = tournament.teams.count()
    except Exception:
        teams_count = 0

    fmt = tournament.format or "tournament"
    when = ""
    try:
        if tournament.start_date:
            when = f" (inizio {tournament.start_date.strftime('%d/%m/%Y')})"
    except Exception:
        when = ""

    content = f'Nuovo torneo: "{tournament.name}" — formato {fmt} — {teams_count} squadre{when}.'
    audience = request.form.get('audience') if tournament.society_id else None
    if _recent_duplicate_post(current_user.id, "tournament_announcement", content):
        flash('Torneo già pubblicato di recente.', 'info')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

        post = Post(
        user_id=current_user.id,
        content=content,
        post_type="tournament_announcement",
            **_post_kwargs_for_tournament(tournament, audience_override=audience),
    )
    try:
        db.session.add(post)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if current_app:
            current_app.logger.exception("Tournament publish failed")
        flash('Errore durante la pubblicazione sul social.', 'danger')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    try:
        log_action(
            "tournament_publish",
            "Tournament",
            tournament.id,
            f'Published tournament "{tournament.name}"',
            society_id=tournament.society_id,
        )
    except Exception:
        pass

    flash('Torneo pubblicato sul social.', 'success')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:tournament_id>/matches/<int:match_id>/publish', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def publish_match_result(tournament_id, match_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)
    match = TournamentMatch.query.get_or_404(match_id)
    if match.tournament_id != tournament.id:
        abort(404)
    if match.status != 'played':
        flash('Puoi pubblicare solo risultati di partite già giocate.', 'warning')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    home_team = match.home_team.name if match.home_team else 'Casa'
    away_team = match.away_team.name if match.away_team else 'Ospiti'
    phase = f" — {match.round_label}" if match.round_label else ""
    content = f'Risultato torneo "{tournament.name}"{phase}: {home_team} {match.home_score} - {match.away_score} {away_team}'

    if _recent_duplicate_post(current_user.id, "tournament_result", content):
        flash('Risultato già pubblicato di recente.', 'info')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    audience = request.form.get('audience') if tournament.society_id else None
    post = Post(
        user_id=current_user.id,
        content=content,
        post_type="tournament_result",
        **_post_kwargs_for_tournament(tournament, audience_override=audience),
    )
    try:
        db.session.add(post)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if current_app:
            current_app.logger.exception("Tournament match publish failed")
        flash('Errore durante la pubblicazione del risultato.', 'danger')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    try:
        log_action(
            "tournament_result_publish",
            "TournamentMatch",
            match.id,
            f"Published result {match.home_score}-{match.away_score}",
            society_id=tournament.society_id,
        )
    except Exception:
        pass

    flash('Risultato pubblicato sul social.', 'success')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:tournament_id>/teams/add', methods=['POST'])
@login_required
def add_team(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)
    form = TournamentTeamForm()
    if form.validate_on_submit():
        team = TournamentTeam(
            tournament_id=tournament.id,
            name=form.name.data,
            category=form.category.data,
            external_ref=form.external_ref.data,
            seed=(int(request.form.get('seed')) if request.form.get('seed') else None),
        )
        db.session.add(team)
        db.session.flush()
        standing = TournamentStanding(tournament_id=tournament.id, team_id=team.id)
        db.session.add(standing)
        db.session.commit()
        flash('Squadra aggiunta.', 'success')
    else:
        flash('Errore nella squadra.', 'danger')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:tournament_id>/matches/add', methods=['POST'])
@login_required
def add_match(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)
    form = TournamentMatchForm()
    if form.validate_on_submit():
        # Ensure teams are valid for this tournament
        home_id = form.home_team_id.data
        away_id = form.away_team_id.data
        if home_id == away_id:
            flash('Casa e trasferta non possono essere uguali.', 'danger')
            return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
        valid_ids = {t.id for t in tournament.teams.all()}
        if home_id not in valid_ids or away_id not in valid_ids:
            flash('Squadre non valide per questo torneo.', 'danger')
            return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
        match = TournamentMatch(
            tournament_id=tournament.id,
            home_team_id=home_id,
            away_team_id=away_id,
            round_label=form.round_label.data,
            match_date=datetime.combine(form.match_date.data, datetime.min.time()) if form.match_date.data else None,
            location=form.location.data,
            is_bracket=False,
        )
        db.session.add(match)
        db.session.commit()
        _trigger('tournament.match_created', {'match_id': match.id})
        flash('Partita pianificata.', 'success')
    else:
        flash('Errore nella creazione della partita.', 'danger')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:match_id>/score', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def set_score(match_id):
    match = TournamentMatch.query.get_or_404(match_id)
    tournament = match.tournament
    _require_manage(tournament)
    form = MatchScoreForm()
    if form.validate_on_submit():
        # Prevent draws in knockout tournaments (no tiebreak implemented here).
        if tournament.format == 'knockout' and form.home_score.data == form.away_score.data:
            flash('Pareggio non consentito in eliminazione diretta. Inserisci un vincitore.', 'danger')
            return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
        match.set_score(form.home_score.data, form.away_score.data)
        if tournament.format == 'knockout':
            _propagate_knockout_winner(match)
        # Update standings
        for standing in tournament.standings:
            if standing.team_id in (match.home_team_id, match.away_team_id):
                standing.update_from_match(match)
        # Optional: publish result to social (explicit user action)
        publish = (request.form.get("publish_to_social") or "").strip() == "1"
        if publish:
            try:
                home_team = match.home_team.name if match.home_team else 'Casa'
                away_team = match.away_team.name if match.away_team else 'Ospiti'
                phase = f" — {match.round_label}" if match.round_label else ""
                content = f'Risultato torneo "{tournament.name}"{phase}: {home_team} {match.home_score} - {match.away_score} {away_team}'
                if not _recent_duplicate_post(current_user.id, "tournament_result", content):
                    post = Post(
                        user_id=current_user.id,
                        content=content,
                        post_type="tournament_result",
                        **_post_kwargs_for_tournament(tournament),
                    )
                    db.session.add(post)
            except Exception:
                pass
        # CRM activity log
        try:
            activity = CRMActivity(
                activity_type='note',
                subject='Risultato torneo aggiornato',
                description=f'Punteggio aggiornato per {tournament.name}: {match.home_score}-{match.away_score}',
                created_by=current_user.id
            )
            db.session.add(activity)
        except Exception:
            pass
        db.session.commit()
        _trigger('tournament.match_scored', {'match_id': match.id})
        flash('Risultato salvato e classifica aggiornata.', 'success')
    else:
        flash('Errore nel punteggio.', 'danger')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:tournament_id>/bracket/generate', methods=['POST'])
@login_required
def generate_bracket(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)
    if tournament.format != 'knockout':
        flash('Generazione tabellone disponibile solo per eliminazione diretta.', 'warning')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    seeding = (request.form.get('seeding') or 'random').strip()
    if seeding not in ('random', 'manual'):
        seeding = 'random'

    teams = tournament.teams.order_by(TournamentTeam.name.asc()).all()
    created = _generate_knockout_bracket(tournament, teams, seeding=seeding)
    flash('Tabellone generato.' if created else 'Tabellone non generato (verifica squadre/partite).', 'success' if created else 'warning')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/<int:tournament_id>/teams/seeding', methods=['POST'])
@login_required
def update_seeding(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)

    updated = 0
    teams = tournament.teams.all()
    for t in teams:
        raw = request.form.get(f"seed_{t.id}")
        if raw is None:
            continue
        raw = raw.strip()
        if raw == "":
            if t.seed is not None:
                t.seed = None
                updated += 1
            continue
        try:
            val = int(raw)
        except Exception:
            continue
        if t.seed != val:
            t.seed = val
            updated += 1
    db.session.commit()
    flash('Seeding aggiornato.' if updated else 'Nessuna modifica.', 'success' if updated else 'info')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


def _round_robin_pairs(team_ids: list[int]) -> list[list[tuple[int | None, int | None]]]:
    """
    Circle method.
    Returns rounds, each round is list of (home_id, away_id); ids can be None for BYE.
    """
    ids = list(team_ids)
    if len(ids) < 2:
        return []
    # Add BYE if odd
    if len(ids) % 2 == 1:
        ids.append(None)
    n = len(ids)
    rounds = n - 1
    half = n // 2
    arr = ids[:]
    out: list[list[tuple[int | None, int | None]]] = []
    for r in range(rounds):
        pairs = []
        for i in range(half):
            a = arr[i]
            b = arr[n - 1 - i]
            pairs.append((a, b))
        out.append(pairs)
        # rotate all but first
        fixed = arr[0]
        rest = arr[1:]
        rest = [rest[-1]] + rest[:-1]
        arr = [fixed] + rest
    return out


def _create_calendar_event_for_match(tournament: Tournament, match: TournamentMatch) -> None:
    """If society tournament, create SocietyCalendarEvent and link it."""
    if not tournament.society_id or not match.match_date:
        return
    if match.calendar_event_id:
        return

    title = f"{match.home_team.name if match.home_team else 'TBD'} vs {match.away_team.name if match.away_team else 'TBD'}"
    ev = SocietyCalendarEvent(
        society_id=tournament.society_id,
        created_by=tournament.created_by,
        title=f"Torneo: {title}",
        event_type="match",
        start_datetime=match.match_date,
        end_datetime=match.match_date,
        location_text=match.location or None,
        notes=f"Torneo: {tournament.name} ({match.round_label or 'Round'})",
        share_to_social=True,
        color="#198754",
    )
    db.session.add(ev)
    db.session.flush()
    match.calendar_event_id = ev.id
    db.session.add(match)


@bp.route('/<int:tournament_id>/schedule/generate', methods=['POST'])
@login_required
def generate_schedule(tournament_id):
    """Generate matches automatically (round-robin only)."""
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_manage(tournament)

    if tournament.format != 'round_robin':
        flash('Generazione calendario disponibile solo per girone all’italiana.', 'warning')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    if tournament.matches.count() > 0:
        flash('Calendario già presente: elimina le partite per rigenerare.', 'warning')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    mode = (request.form.get('seeding') or 'random').strip()
    if mode not in ('random', 'manual'):
        mode = 'random'

    # Base date and interval days
    start_date_str = (request.form.get('start_date') or '').strip()
    interval_days = int(request.form.get('interval_days') or 7)
    try:
        base_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
    except Exception:
        base_date = None
    if not base_date:
        base_date = datetime.now(timezone.utc).replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        base_date = base_date.replace(hour=18, minute=0, second=0, microsecond=0)
    if interval_days <= 0:
        interval_days = 7

    teams = tournament.teams.order_by(TournamentTeam.name.asc()).all()
    if len(teams) < 2:
        flash('Servono almeno 2 squadre.', 'warning')
        return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))

    # Choose ordering for pairing generation
    ordered = list(teams)
    if mode == 'random':
        random.shuffle(ordered)
    else:
        ordered.sort(key=lambda t: (t.seed is None, t.seed if t.seed is not None else 10**9, t.name.lower()))

    rounds = _round_robin_pairs([t.id for t in ordered])
    created = 0
    from datetime import timedelta as _td
    for r_idx, pairs in enumerate(rounds, start=1):
        round_date = base_date + _td(days=(r_idx - 1) * interval_days)
        for a, b in pairs:
            if a is None or b is None:
                continue
            match = TournamentMatch(
                tournament_id=tournament.id,
                home_team_id=a,
                away_team_id=b,
                round_label=f"Giornata {r_idx}",
                match_date=round_date,
                location=None,
                status='scheduled',
                is_bracket=False,
            )
            db.session.add(match)
            db.session.flush()
            created += 1
            try:
                # Link calendar event (society tournaments)
                match.home_team = db.session.get(TournamentTeam, a)
                match.away_team = db.session.get(TournamentTeam, b)
                _create_calendar_event_for_match(tournament, match)
            except Exception:
                pass

    db.session.commit()
    flash(f'Calendario generato: {created} partite.', 'success')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))
