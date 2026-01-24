"""Tournament routes implementing multi-format tournaments with scheduling, scoring, standings."""
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.tournaments import bp
from app.tournaments.forms import TournamentForm, TournamentTeamForm, TournamentMatchForm, MatchScoreForm
from app.models import Tournament, TournamentTeam, TournamentMatch, TournamentStanding, SocietyCalendarEvent, Post, CRMActivity
from app.automation.utils import execute_rules
from app.utils import permission_required


def _require_society_scope(tournament: Tournament = None):
    if current_user.is_admin():
        return
    society = current_user.get_primary_society()
    if not society:
        abort(403)
    if tournament and tournament.society_id != society.id:
        abort(403)


def _get_society_id():
    if current_user.is_admin():
        sid = request.args.get('society_id', type=int)
        return sid
    society = current_user.get_primary_society()
    return society.id if society else None


def _trigger(event_type, payload):
    execute_rules(event_type, payload)


@bp.route('/tournaments')
@login_required
@permission_required('tournaments', 'view')
def list_tournaments():
    sid = _get_society_id()
    query = Tournament.query
    if not current_user.is_admin():
        query = query.filter_by(society_id=sid)
    tournaments = query.order_by(Tournament.created_at.desc()).all()
    return render_template('tournaments/index.html', tournaments=tournaments)


@bp.route('/tournaments/new', methods=['GET', 'POST'])
@login_required
@permission_required('tournaments', 'manage')
def create_tournament():
    sid = _get_society_id()
    if not sid:
        abort(403)
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


@bp.route('/tournaments/<int:tournament_id>')
@login_required
@permission_required('tournaments', 'view')
def view_tournament(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_society_scope(tournament)
    teams = tournament.teams.order_by(TournamentTeam.name.asc()).all()
    matches = tournament.matches.order_by(TournamentMatch.match_date.asc()).all()
    standings = tournament.standings.order_by(TournamentStanding.points.desc(), TournamentStanding.goals_for.desc()).all()
    return render_template('tournaments/detail.html', tournament=tournament, teams=teams, matches=matches, standings=standings)


@bp.route('/tournaments/<int:tournament_id>/teams/add', methods=['POST'])
@login_required
@permission_required('tournaments', 'manage')
def add_team(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_society_scope(tournament)
    form = TournamentTeamForm()
    if form.validate_on_submit():
        team = TournamentTeam(
            tournament_id=tournament.id,
            name=form.name.data,
            category=form.category.data,
            external_ref=form.external_ref.data
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


@bp.route('/tournaments/<int:tournament_id>/matches/add', methods=['POST'])
@login_required
@permission_required('tournaments', 'manage')
def add_match(tournament_id):
    tournament = Tournament.query.get_or_404(tournament_id)
    _require_society_scope(tournament)
    form = TournamentMatchForm()
    if form.validate_on_submit():
        match = TournamentMatch(
            tournament_id=tournament.id,
            home_team_id=form.home_team_id.data,
            away_team_id=form.away_team_id.data,
            round_label=form.round_label.data,
            match_date=datetime.combine(form.match_date.data, datetime.min.time()) if form.match_date.data else None,
            location=form.location.data
        )
        db.session.add(match)
        db.session.commit()
        _trigger('tournament.match_created', {'match_id': match.id})
        flash('Partita pianificata.', 'success')
    else:
        flash('Errore nella creazione della partita.', 'danger')
    return redirect(url_for('tournaments.view_tournament', tournament_id=tournament.id))


@bp.route('/tournaments/<int:match_id>/score', methods=['POST'])
@login_required
@permission_required('tournaments', 'manage')
def set_score(match_id):
    match = TournamentMatch.query.get_or_404(match_id)
    tournament = match.tournament
    _require_society_scope(tournament)
    form = MatchScoreForm()
    if form.validate_on_submit():
        match.set_score(form.home_score.data, form.away_score.data)
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
