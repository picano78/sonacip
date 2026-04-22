# Performance Best Practices

## Database Query Optimization

### 1. Avoid N+1 Queries

**Problem**: Loading a list of objects and then accessing related objects in a loop.

```python
# ❌ BAD: N+1 queries
users = User.query.all()
for user in users:
    print(user.society.name)  # Triggers 1 query per user
```

**Solution**: Use eager loading with `joinedload()` or `selectinload()`.

```python
# ✅ GOOD: Single query with join
from sqlalchemy.orm import joinedload

users = User.query.options(joinedload(User.society)).all()
for user in users:
    print(user.society.name)  # No additional queries
```

### 2. Use Pagination for Large Result Sets

**Problem**: Loading all records at once can cause memory issues and slow page loads.

```python
# ❌ BAD: Loading everything
all_posts = Post.query.all()  # Could be thousands of records
```

**Solution**: Use pagination with `.paginate()`.

```python
# ✅ GOOD: Paginated results
page = request.args.get('page', 1, type=int)
posts = Post.query.order_by(Post.created_at.desc()).paginate(
    page=page,
    per_page=20,
    error_out=False
)
```

### 3. Select Only Required Columns

**Problem**: Loading entire objects when you only need a few fields.

```python
# ❌ BAD: Loading all columns
users = User.query.all()
user_ids = [u.id for u in users]
```

**Solution**: Use `with_entities()` to select specific columns.

```python
# ✅ GOOD: Only load needed columns
from sqlalchemy import select

user_ids = db.session.execute(
    select(User.id).where(User.is_active == True)
).scalars().all()
```

### 4. Use Database Indexes

Ensure frequently queried columns have indexes:

```python
# In models.py
class User(db.Model):
    email = db.Column(db.String(120), unique=True, index=True)  # ✅ Indexed
    created_at = db.Column(db.DateTime, index=True)  # ✅ Indexed for sorting
```

### 5. Avoid Lazy Loading in Loops

```python
# ❌ BAD: Lazy loading in loop
posts = Post.query.all()
for post in posts:
    author_name = post.author.username  # N+1 queries

# ✅ GOOD: Eager load relationships
from sqlalchemy.orm import joinedload

posts = Post.query.options(joinedload(Post.author)).all()
for post in posts:
    author_name = post.author.username  # No extra queries
```

## Caching Strategies

### 1. Cache Expensive Queries

```python
from app.cache import get_cache

cache = get_cache()

def get_popular_posts():
    cached = cache.get('popular_posts')
    if cached:
        return cached
    
    # Expensive query
    posts = Post.query.join(Like).group_by(Post.id)\
        .order_by(db.func.count(Like.id).desc())\
        .limit(10).all()
    
    cache.set('popular_posts', posts, ttl=300)  # Cache 5 minutes
    return posts
```

### 2. Cache User Sessions

Already implemented via Flask-Session with Redis backend.

### 3. Cache Static Content

Use Flask-Compress for response compression (already configured).

## Request Handling

### 1. Validate Input Early

```python
from app.utils import safe_int, safe_json_get

@bp.route('/api/items', methods=['POST'])
def create_item():
    # ✅ Validate at entry point
    if not request.json:
        return jsonify({'error': 'JSON required'}), 400
    
    name = safe_json_get(request.json, 'name', expected_type=str)
    priority = safe_int(request.json.get('priority'), default=1)
    
    if not name:
        return jsonify({'error': 'Name required'}), 400
    
    # Continue with validated data...
```

### 2. Use Async Tasks for Heavy Operations

```python
from app.tasks import send_email_task

@bp.route('/send-newsletter', methods=['POST'])
def send_newsletter():
    # ❌ BAD: Blocking operation
    # send_emails_to_all_users()  # Takes 30 seconds
    
    # ✅ GOOD: Async with Celery
    send_email_task.delay(recipient_list)
    return jsonify({'status': 'queued'}), 202
```

## Frontend Optimization

### 1. Minimize Template Rendering

```jinja2
{# ✅ GOOD: Filter in Python, not template #}
{% for post in recent_posts %}
    {{ post.title }}
{% endfor %}

{# ❌ BAD: Filtering in template #}
{% for post in all_posts %}
    {% if post.created_at > cutoff_date %}
        {{ post.title }}
    {% endif %}
{% endfor %}
```

### 2. Use AJAX for Dynamic Content

Load heavy content dynamically instead of on page load:

```javascript
// ✅ GOOD: Load on demand
$('#load-comments').click(function() {
    $.get('/api/post/123/comments', function(data) {
        $('#comments').html(data);
    });
});
```

## File Handling

### 1. Stream Large Files

```python
# ✅ GOOD: Stream instead of loading into memory
from flask import send_file

@bp.route('/download/<filename>')
def download_file(filename):
    return send_file(
        f'/path/to/{filename}',
        as_attachment=True,
        download_name=filename
    )
```

### 2. Limit Upload Sizes

Already configured in config.py:
```python
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB limit
```

## Monitoring and Profiling

### 1. Use Query Logging (Development)

In development, enable SQLAlchemy query logging:

```python
# config.py
SQLALCHEMY_ECHO = True  # Only in development
```

### 2. Monitor Slow Queries

Check PostgreSQL slow query log:

```bash
# In postgresql.conf
log_min_duration_statement = 1000  # Log queries > 1 second
```

### 3. Profile Endpoints

Use Flask-DebugToolbar (development only):

```python
# Development only
from flask_debugtoolbar import DebugToolbarExtension
toolbar = DebugToolbarExtension(app)
```

## Database Connection Pooling

Already optimized in `app/core/config.py`:

```python
# PostgreSQL production settings
DB_POOL_SIZE = 10
DB_MAX_OVERFLOW = 20
DB_POOL_RECYCLE = 300  # Recycle connections every 5 min
DB_POOL_TIMEOUT = 30
```

## Common Performance Issues to Avoid

1. **Avoid SELECT * queries** - Select only needed columns
2. **Don't use `.all()` without limit** - Use pagination
3. **Avoid string concatenation in queries** - Use parameterized queries
4. **Don't perform calculations in templates** - Do it in Python
5. **Avoid synchronous operations in request handlers** - Use Celery
6. **Don't load large files into memory** - Stream them
7. **Avoid circular imports** - Use lazy loading where needed

## Testing Performance

```python
import time

def test_query_performance():
    start = time.time()
    users = User.query.options(joinedload(User.society)).limit(100).all()
    duration = time.time() - start
    
    assert duration < 0.5, f"Query took {duration}s, expected < 0.5s"
```

## Resources

- [SQLAlchemy Performance Tips](https://docs.sqlalchemy.org/en/20/faq/performance.html)
- [Flask Best Practices](https://flask.palletsprojects.com/en/3.0.x/patterns/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
