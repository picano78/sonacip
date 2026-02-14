"""
Tasks and Project Management Routes
Advanced planning with Kanban, Gantt, Calendar views
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Task, Project, User, Team
from app.utils import permission_required, check_permission
from app.models import Event
from app.automation.utils import execute_automations, execute_rules
from datetime import datetime, timedelta, timezone
import json

bp = Blueprint('tasks', __name__, url_prefix='/tasks')


def _task_scope_id(*args, **kwargs):
    """Resolve society scope for task/project operations."""
    task_id = kwargs.get('task_id')
    project_id = kwargs.get('project_id')

    if task_id:
        task = Task.query.get(task_id)
        if task:
            if task.society_id:
                return task.society_id
            if task.project and task.project.society_id:
                return task.project.society_id

    if project_id:
        project = Project.query.get(project_id)
        if project:
            return project.society_id

    try:
        from app.utils import get_active_society_id
        return get_active_society_id(current_user)
    except (ImportError, AttributeError) as e:
        # Fallback to primary society if utils not available or user has no active society
        current_app.logger.debug(f"Could not get active society ID: {e}, using primary society")
        society = current_user.get_primary_society()
        return society.id if society else None


@bp.route('/')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def index():
    """Task management dashboard"""
    scope_id = _task_scope_id()

    # Get user's tasks within scope
    my_tasks_query = Task.query.filter_by(assigned_to=current_user.id)
    created_tasks_query = Task.query.filter_by(created_by=current_user.id)
    if scope_id:
        my_tasks_query = my_tasks_query.filter(Task.society_id == scope_id)
        created_tasks_query = created_tasks_query.filter(Task.society_id == scope_id)

    my_tasks = my_tasks_query.order_by(Task.due_date).all()
    created_tasks = created_tasks_query.all()
    
    # Get projects within scope
    if check_permission(current_user, 'admin', 'access'):
        projects = Project.query.all()
    elif scope_id:
        projects = Project.query.filter_by(society_id=scope_id).all()
    else:
        projects = []
    
    # Stats
    stats = {
        'total_tasks': len(my_tasks),
        'todo': len([t for t in my_tasks if t.status == 'todo']),
        'in_progress': len([t for t in my_tasks if t.status == 'in_progress']),
        'done': len([t for t in my_tasks if t.status == 'done']),
        'overdue': len([t for t in my_tasks if t.due_date and t.due_date < datetime.now().date() and t.status != 'done']),
    }
    
    return render_template('tasks/index.html',
                         my_tasks=my_tasks,
                         created_tasks=created_tasks,
                         projects=projects,
                         stats=stats)


@bp.route('/planner')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def planner():
    """Unified planner for tasks and events"""
    # Upcoming events: admin sees all, society sees own, others see convocated
    scope_id = _task_scope_id()

    if check_permission(current_user, 'admin', 'access'):
        events_query = Event.query
    elif scope_id:
        events_query = Event.query.filter_by(creator_id=current_user.id)
    else:
        events_query = current_user.events

    events = events_query.order_by(Event.start_date.asc()).limit(20).all()

    # Tasks assigned to me
    tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date).limit(20).all()

    return render_template('tasks/planner.html', events=events, tasks=tasks)


@bp.route('/kanban')
@bp.route('/kanban/<int:project_id>')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def kanban(project_id=None):
    """Kanban board view (Trello/Monday.com style)"""
    if project_id:
        project = Project.query.get_or_404(project_id)
        tasks = Task.query.filter_by(project_id=project_id).order_by(Task.position).all()
    else:
        project = None
        # All my tasks
        tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.position).all()
    
    # Organize by status columns
    columns = {
        'todo': [t for t in tasks if t.status == 'todo'],
        'in_progress': [t for t in tasks if t.status == 'in_progress'],
        'review': [t for t in tasks if t.status == 'review'],
        'blocked': [t for t in tasks if t.status == 'blocked'],
        'done': [t for t in tasks if t.status == 'done'],
    }
    
    return render_template('tasks/kanban.html',
                         project=project,
                         columns=columns,
                         tasks=tasks)


@bp.route('/timeline')
@bp.route('/timeline/<int:project_id>')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def timeline(project_id=None):
    """Gantt chart / Timeline view"""
    if project_id:
        project = Project.query.get_or_404(project_id)
        tasks = Task.query.filter_by(project_id=project_id).filter(
            Task.start_date.isnot(None),
            Task.due_date.isnot(None)
        ).order_by(Task.start_date).all()
    else:
        project = None
        tasks = Task.query.filter_by(assigned_to=current_user.id).filter(
            Task.start_date.isnot(None),
            Task.due_date.isnot(None)
        ).order_by(Task.start_date).all()
    
    # Prepare timeline data
    timeline_data = []
    for task in tasks:
        timeline_data.append({
            'id': task.id,
            'title': task.title,
            'start': task.start_date.isoformat() if task.start_date else None,
            'end': task.due_date.isoformat() if task.due_date else None,
            'progress': task.progress_percentage,
            'assignee': task.assignee.get_full_name() if task.assignee else 'Unassigned',
            'status': task.status,
            'priority': task.priority
        })
    
    return render_template('tasks/timeline.html',
                         project=project,
                         tasks=tasks,
                         timeline_data=json.dumps(timeline_data))


@bp.route('/calendar')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def calendar():
    """Calendar view for tasks"""
    # Get all tasks with due dates
    tasks = Task.query.filter_by(assigned_to=current_user.id).filter(
        Task.due_date.isnot(None)
    ).all()
    
    # Prepare calendar events
    events = []
    for task in tasks:
        events.append({
            'id': task.id,
            'title': task.title,
            'start': task.due_date.isoformat(),
            'backgroundColor': get_priority_color(task.priority),
            'borderColor': get_status_color(task.status),
            'url': f'/tasks/task/{task.id}'
        })
    
    return render_template('tasks/calendar.html', events=json.dumps(events))


@bp.route('/task/create', methods=['GET', 'POST'])
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def create_task():
    """Create new task"""
    if request.method == 'POST':
        scope_id = _task_scope_id()
        task = Task(
            title=request.form.get('title'),
            description=request.form.get('description'),
            created_by=current_user.id,
            assigned_to=request.form.get('assigned_to') or None,
            status=request.form.get('status', 'todo'),
            priority=request.form.get('priority', 'medium'),
            project_id=request.form.get('project_id') or None,
            society_id=scope_id,
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d') if request.form.get('due_date') else None,
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d') if request.form.get('start_date') else None,
            estimated_hours=request.form.get('estimated_hours') or None,
        )
        
        # Handle tags
        tags = request.form.get('tags', '').split(',')
        task.tags = json.dumps([t.strip() for t in tags if t.strip()])
        
        db.session.add(task)
        db.session.commit()

        # Fire automations for task creation
        execute_automations('task_created', society_id=task.society_id or current_user.society_id, payload={'task_id': task.id})
        execute_rules('task_created', payload={'task_id': task.id, 'assigned_to': task.assigned_to, 'status': task.status})
        
        flash('Task created successfully!', 'success')
        return redirect(url_for('tasks.index'))
    
    # Get available projects and users for assignment
    scope_id = _task_scope_id()
    projects = Project.query.filter_by(society_id=scope_id).all() if scope_id else []
    users = User.query.filter_by(society_id=scope_id, is_active=True).all() if scope_id else []
    
    return render_template('tasks/create_task.html', projects=projects, users=users)


@bp.route('/task/<int:task_id>')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def view_task(task_id):
    """View task details"""
    task = Task.query.get_or_404(task_id)
    
    # Check permissions
    if not can_view_task(current_user, task):
        flash('Access denied.', 'danger')
        return redirect(url_for('tasks.index'))
    
    # Get subtasks
    subtasks = Task.query.filter_by(parent_task_id=task_id).all()
    
    # Get watchers
    watchers = []
    if task.watchers:
        watcher_ids = json.loads(task.watchers)
        watchers = User.query.filter(User.id.in_(watcher_ids)).all()
    
    return render_template('tasks/view_task.html',
                         task=task,
                         subtasks=subtasks,
                         watchers=watchers)


@bp.route('/task/<int:task_id>/update', methods=['POST'])
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def update_task(task_id):
    """Update task (AJAX)"""
    from app.utils import safe_json_get, safe_int
    
    task = Task.query.get_or_404(task_id)
    
    if not can_edit_task(current_user, task):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    if not request.json:
        return jsonify({'success': False, 'message': 'Invalid request: JSON data required'}), 400
    
    try:
        # Update fields with safe JSON access and validation
        status = safe_json_get(request.json, 'status', expected_type=str)
        if status:
            task.status = status
            if status == 'done' and not task.completed_at:
                task.completed_at = datetime.now(timezone.utc)
        
        priority = safe_json_get(request.json, 'priority', expected_type=str)
        if priority:
            task.priority = priority
        
        progress = safe_json_get(request.json, 'progress')
        if progress is not None:
            task.progress_percentage = safe_int(progress, default=0, field_name='progress')
        
        assigned_to = safe_json_get(request.json, 'assigned_to')
        if assigned_to is not None:
            task.assigned_to = safe_int(assigned_to, default=None, field_name='assigned_to')
        
        position = safe_json_get(request.json, 'position')
        if position is not None:
            task.position = safe_int(position, default=0, field_name='position')
        
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Fire automations for task updates
        execute_automations('task_updated', society_id=task.society_id or current_user.society_id, 
                          payload={'task_id': task.id, 'status': task.status})
        execute_rules('task_updated', payload={'task_id': task.id, 'status': task.status, 
                                              'assigned_to': task.assigned_to})
        
        return jsonify({'success': True, 'message': 'Task updated'})
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating task {task_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error updating task'}), 500


@bp.route('/project/create', methods=['GET', 'POST'])
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def create_project():
    """Create new project"""
    if request.method == 'POST':
        scope_id = _task_scope_id()
        project = Project(
            name=request.form.get('name'),
            description=request.form.get('description'),
            society_id=scope_id,
            owner_id=current_user.id,
            status='active',
            project_type=request.form.get('project_type'),
            color=request.form.get('color', '#3498db'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None,
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None,
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('tasks.view_project', project_id=project.id))
    
    return render_template('tasks/create_project.html')


@bp.route('/project/<int:project_id>')
@login_required
@permission_required('tasks', 'manage', society_id_func=_task_scope_id)
def view_project(project_id):
    """View project details"""
    project = Project.query.get_or_404(project_id)
    
    # Get project tasks
    tasks = Task.query.filter_by(project_id=project_id).all()
    
    # Calculate stats
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == 'done'])
    progress = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
    
    project.progress_percentage = progress
    db.session.commit()
    
    # Task breakdown by status
    task_stats = {
        'todo': len([t for t in tasks if t.status == 'todo']),
        'in_progress': len([t for t in tasks if t.status == 'in_progress']),
        'review': len([t for t in tasks if t.status == 'review']),
        'done': completed_tasks
    }
    
    return render_template('tasks/view_project.html',
                         project=project,
                         tasks=tasks,
                         task_stats=task_stats,
                         progress=progress)


# Helper functions
def can_view_task(user, task):
    """Check if user can view task"""
    scope_id = _task_scope_id(task_id=task.id)
    if check_permission(user, 'admin', 'access'):
        return True
    if not check_permission(user, 'tasks', 'manage', scope_id):
        return False
    if task.created_by == user.id or task.assigned_to == user.id:
        return True
    if task.watchers and str(user.id) in task.watchers:
        return True
    return False


def can_edit_task(user, task):
    """Check if user can edit task"""
    scope_id = _task_scope_id(task_id=task.id)
    if check_permission(user, 'admin', 'access'):
        return True
    if not check_permission(user, 'tasks', 'manage', scope_id):
        return False
    if task.created_by == user.id or task.assigned_to == user.id:
        return True
    return False


def is_team_member(user_id, team_members_json):
    """Check if user is in team"""
    if not team_members_json:
        return False
    try:
        members = json.loads(team_members_json)
        return user_id in members
    except:
        return False


def get_priority_color(priority):
    """Get color for priority"""
    colors = {
        'low': '#95a5a6',
        'medium': '#3498db',
        'high': '#f39c12',
        'urgent': '#e74c3c'
    }
    return colors.get(priority, '#3498db')


def get_status_color(status):
    """Get color for status"""
    colors = {
        'todo': '#95a5a6',
        'in_progress': '#3498db',
        'review': '#f39c12',
        'blocked': '#e74c3c',
        'done': '#27ae60'
    }
    return colors.get(status, '#95a5a6')
