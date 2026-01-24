"""
Tasks and Project Management Routes
Advanced planning with Kanban, Gantt, Calendar views
"""
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.tasks import bp
from app.models import Task, Project, User, Team
from app.utils import role_required
from app.models import Event
from app.automation.utils import execute_automations
from datetime import datetime, timedelta
import json


@bp.route('/')
@login_required
def index():
    """Task management dashboard"""
    # Get user's tasks
    my_tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.due_date).all()
    
    # Get created tasks
    created_tasks = Task.query.filter_by(created_by=current_user.id).all()
    
    # Get projects
    if current_user.is_admin():
        projects = Project.query.all()
    elif current_user.is_society():
        projects = Project.query.filter_by(society_id=current_user.id).all()
    else:
        # Get projects where user is a team member
        all_projects = Project.query.all()
        projects = [p for p in all_projects if is_team_member(current_user.id, p.team_members)]
    
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
def planner():
    """Unified planner for tasks and events"""
    # Upcoming events: admin sees all, society sees own, others see convocated
    if current_user.is_admin():
        events_query = Event.query
    elif current_user.is_society() or current_user.is_staff():
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
def create_task():
    """Create new task"""
    if request.method == 'POST':
        task = Task(
            title=request.form.get('title'),
            description=request.form.get('description'),
            created_by=current_user.id,
            assigned_to=request.form.get('assigned_to') or None,
            status=request.form.get('status', 'todo'),
            priority=request.form.get('priority', 'medium'),
            project_id=request.form.get('project_id') or None,
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
        
        flash('Task created successfully!', 'success')
        return redirect(url_for('tasks.index'))
    
    # Get available projects and users for assignment
    projects = Project.query.filter_by(society_id=current_user.id).all() if current_user.is_society() else []
    users = User.query.filter_by(society_id=current_user.id, is_active=True).all() if current_user.is_society() else []
    
    return render_template('tasks/create_task.html', projects=projects, users=users)


@bp.route('/task/<int:task_id>')
@login_required
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
def update_task(task_id):
    """Update task (AJAX)"""
    task = Task.query.get_or_404(task_id)
    
    if not can_edit_task(current_user, task):
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    # Update fields
    if 'status' in request.json:
        task.status = request.json['status']
        if request.json['status'] == 'done' and not task.completed_at:
            task.completed_at = datetime.utcnow()
    
    if 'priority' in request.json:
        task.priority = request.json['priority']
    
    if 'progress' in request.json:
        task.progress_percentage = int(request.json['progress'])
    
    if 'assigned_to' in request.json:
        task.assigned_to = request.json['assigned_to']
    
    if 'position' in request.json:
        task.position = request.json['position']
    
    task.updated_at = datetime.utcnow()
    db.session.commit()

    # Fire automations for task updates
    execute_automations('task_updated', society_id=task.society_id or current_user.society_id, payload={'task_id': task.id, 'status': task.status})
    
    return jsonify({'success': True, 'message': 'Task updated'})


@bp.route('/project/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'societa', 'staff')
def create_project():
    """Create new project"""
    if request.method == 'POST':
        project = Project(
            name=request.form.get('name'),
            description=request.form.get('description'),
            society_id=current_user.id if current_user.is_society() else request.form.get('society_id'),
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
    if user.is_admin():
        return True
    if task.created_by == user.id or task.assigned_to == user.id:
        return True
    if task.watchers and str(user.id) in task.watchers:
        return True
    return False


def can_edit_task(user, task):
    """Check if user can edit task"""
    if user.is_admin():
        return True
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
