"""Tournament routes implementing multi-format tournaments with scheduling, scoring, standings."""
from datetime import datetime
import math
import random
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import false
from app import db
from app.tournaments.forms import TournamentForm, TournamentTeamForm, TournamentMatchForm, MatchScoreForm
from app.models import Tournament, TournamentTeam, TournamentMatch, TournamentStanding, SocietyCalendarEvent, Post, CRMActivity
from app.automation.utils import execute_rules
from app.utils import permission_required, check_permission

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
    if check_permission(current_user, 'admin', 'access'):
        return request.args.get('society_id', type=int)
    society = current_user.get_primary_society()
    return society.id if society else None


def _trigger(event_type, payload):
    execute_rules(event_type, payload)


def _winner_of(match: TournamentMatch) -> TournamentTeam | None:
    if match and match.winner_team_id:
        return TournamentTeam.query.get(match.winner_team_id)
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
    matches = tournament.matches.order_by(TournamentMatch.match_date.asc()).all()
    standings = tournament.standings.order_by(TournamentStanding.points.desc(), TournamentStanding.goals_for.desc()).all()
    bracket_matches = tournament.matches.filter_by(is_bracket=True).order_by(TournamentMatch.round_number.asc(), TournamentMatch.position.asc()).all()
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
        # Social post for tournament result
        try:
            home_team = match.home_team.name if match.home_team else 'Casa'
            away_team = match.away_team.name if match.away_team else 'Ospiti'
            content = f'Risultato torneo "{tournament.name}": {home_team} {match.home_score} - {match.away_score} {away_team}'
            post = Post(user_id=current_user.id, content=content, is_public=True)
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
