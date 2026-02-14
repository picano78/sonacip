# Code Quality Guidelines

## Exception Handling Best Practices

### ❌ What NOT to Do

```python
# DON'T use bare except
try:
    process_payment()
except:  # Catches everything, even KeyboardInterrupt!
    pass

# DON'T use overly broad Exception catch
try:
    user = User.query.get(user_id)
    send_email(user.email)
except Exception:  # Too broad - hides real errors
    pass

# DON'T silently ignore errors
try:
    critical_operation()
except Exception:
    pass  # Error is lost forever
```

### ✅ What TO Do

```python
# DO catch specific exceptions
try:
    user = User.query.get_or_404(user_id)
    send_email(user.email)
except SQLAlchemyError as e:
    current_app.logger.error(f"Database error: {e}", exc_info=True)
    db.session.rollback()
    return jsonify({'error': 'Database error'}), 500
except SMTPException as e:
    current_app.logger.error(f"Email error: {e}", exc_info=True)
    return jsonify({'error': 'Email sending failed'}), 500

# DO log errors properly
try:
    process_payment(amount)
except PaymentError as e:
    current_app.logger.error(
        f"Payment failed for amount {amount}: {e}",
        exc_info=True,  # Include stack trace
        extra={'user_id': current_user.id, 'amount': amount}
    )
    flash('Payment processing failed. Please try again.', 'error')
    return redirect(url_for('billing.retry'))

# DO use finally for cleanup
try:
    f = open('file.txt', 'r')
    data = f.read()
except IOError as e:
    current_app.logger.error(f"File read error: {e}")
    raise
finally:
    f.close()  # Always runs

# DO use context managers when possible
with open('file.txt', 'r') as f:  # ✅ Better - auto-closes
    data = f.read()
```

## Input Validation

### ✅ Always Validate User Input

```python
from app.utils import safe_int, safe_json_get

@bp.route('/api/update', methods=['POST'])
def update_item():
    # Validate request has JSON
    if not request.json:
        return jsonify({'error': 'JSON data required'}), 400
    
    # Use safe helpers
    item_id = safe_int(request.args.get('id'), default=None)
    if not item_id:
        return jsonify({'error': 'Valid item ID required'}), 400
    
    # Validate expected types
    title = safe_json_get(request.json, 'title', expected_type=str)
    priority = safe_json_get(request.json, 'priority', default=1, expected_type=int)
    
    # Validate required fields
    if not title or len(title) < 3:
        return jsonify({'error': 'Title must be at least 3 characters'}), 400
    
    # Sanitize and validate further
    title = title.strip()[:200]  # Limit length
    
    # Now safe to use
    item = Item.query.get_or_404(item_id)
    item.title = title
    item.priority = priority
    db.session.commit()
    
    return jsonify({'success': True})
```

## Database Operations

### ✅ Always Handle Database Errors

```python
@bp.route('/create-post', methods=['POST'])
def create_post():
    try:
        post = Post(
            title=request.form['title'],
            content=request.form['content'],
            author_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully', 'success')
        return redirect(url_for('social.view_post', id=post.id))
    
    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Database integrity error: {e}", exc_info=True)
        flash('A post with this title already exists', 'error')
        return redirect(url_for('social.new_post'))
    
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error creating post: {e}", exc_info=True)
        flash('Error creating post. Please try again.', 'error')
        return redirect(url_for('social.new_post'))
```

### ✅ Use Transactions for Multi-Step Operations

```python
from sqlalchemy.exc import SQLAlchemyError

def transfer_points(from_user_id, to_user_id, amount):
    try:
        # Start transaction (implicitly with Flask-SQLAlchemy)
        from_user = User.query.with_for_update().get(from_user_id)
        to_user = User.query.with_for_update().get(to_user_id)
        
        if from_user.points < amount:
            raise ValueError("Insufficient points")
        
        # Atomic operations
        from_user.points -= amount
        to_user.points += amount
        
        # Create audit log
        log = PointsTransfer(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount
        )
        db.session.add(log)
        
        # Commit all or none
        db.session.commit()
        return True
    
    except ValueError as e:
        db.session.rollback()
        current_app.logger.warning(f"Business logic error: {e}")
        raise
    
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error in transfer: {e}", exc_info=True)
        raise
```

## Type Hints

### ✅ Add Type Hints for Better Code Quality

```python
from typing import Optional, List, Dict, Any
from flask import Response, jsonify

def get_user_by_email(email: str) -> Optional[User]:
    """
    Find user by email address.
    
    Args:
        email: User's email address
        
    Returns:
        User object if found, None otherwise
    """
    return User.query.filter_by(email=email).first()

def format_user_data(user: User) -> Dict[str, Any]:
    """
    Format user data for API response.
    
    Args:
        user: User object to format
        
    Returns:
        Dictionary with user data
    """
    return {
        'id': user.id,
        'email': user.email,
        'name': user.full_name,
        'created_at': user.created_at.isoformat()
    }

@bp.route('/api/users/<int:user_id>')
def get_user(user_id: int) -> Response:
    """API endpoint to get user data."""
    user = User.query.get_or_404(user_id)
    return jsonify(format_user_data(user))
```

## Logging Best Practices

### ✅ Use Structured Logging

```python
import logging

# Different log levels for different situations
current_app.logger.debug('Detailed debug information')
current_app.logger.info('General information')
current_app.logger.warning('Warning - something unexpected')
current_app.logger.error('Error - operation failed')
current_app.logger.critical('Critical - system unstable')

# Include context in logs
current_app.logger.error(
    'Payment processing failed',
    exc_info=True,  # Include stack trace
    extra={
        'user_id': current_user.id,
        'payment_method': payment_method,
        'amount': amount,
        'currency': currency
    }
)

# Use lazy formatting (better performance)
current_app.logger.debug('Processing user %s with %d items', user_id, item_count)
# Instead of:
# current_app.logger.debug(f'Processing user {user_id} with {item_count} items')
```

## Security Best Practices

### ✅ Validate Permissions

```python
from app.utils import enforce_permission

@bp.route('/society/<int:society_id>/settings')
@login_required
@enforce_permission('society', 'manage')
def society_settings(society_id):
    """Only society managers can access."""
    society = Society.query.get_or_404(society_id)
    
    # Double-check user has access to THIS society
    if society.id != current_user.society_id:
        abort(403)
    
    return render_template('society/settings.html', society=society)
```

### ✅ Sanitize User Input

```python
from markupsafe import escape
from bleach import clean

# For HTML display
@bp.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    # Escape user content
    safe_title = escape(post.title)
    
    # Or allow limited HTML with bleach
    safe_content = clean(
        post.content,
        tags=['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
        strip=True
    )
    
    return render_template('post.html', 
                         title=safe_title, 
                         content=safe_content)
```

### ✅ Use Parameterized Queries

```python
# ✅ GOOD: Parameterized (safe from SQL injection)
users = User.query.filter(User.email == email).all()

# ✅ GOOD: Using SQLAlchemy text with bound parameters
from sqlalchemy import text
result = db.session.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {'email': email}
)

# ❌ BAD: String interpolation (SQL injection risk)
query = f"SELECT * FROM users WHERE email = '{email}'"  # NEVER DO THIS
result = db.session.execute(text(query))
```

## Code Organization

### ✅ Keep Functions Focused (Single Responsibility)

```python
# ❌ BAD: Function does too many things
def process_order(order_id):
    order = Order.query.get(order_id)
    validate_order(order)
    charge_payment(order)
    send_confirmation_email(order)
    update_inventory(order)
    create_shipping_label(order)
    notify_warehouse(order)

# ✅ GOOD: Separate concerns
def process_order(order_id):
    order = Order.query.get(order_id)
    validate_order(order)
    
    payment_result = process_payment(order)
    if not payment_result.success:
        return payment_result
    
    fulfillment_result = fulfill_order(order)
    if not fulfillment_result.success:
        refund_payment(payment_result.transaction_id)
        return fulfillment_result
    
    notify_customer(order)
    return OrderResult(success=True, order=order)

def process_payment(order):
    # Payment logic only
    pass

def fulfill_order(order):
    # Fulfillment logic only
    pass
```

## Testing

### ✅ Write Testable Code

```python
# ❌ BAD: Hard to test (depends on global state)
def get_current_user_posts():
    posts = Post.query.filter_by(author_id=current_user.id).all()
    return posts

# ✅ GOOD: Easy to test (dependency injection)
def get_user_posts(user_id: int) -> List[Post]:
    posts = Post.query.filter_by(author_id=user_id).all()
    return posts

# In route handler
@bp.route('/my-posts')
@login_required
def my_posts():
    posts = get_user_posts(current_user.id)
    return render_template('posts.html', posts=posts)

# In test
def test_get_user_posts():
    user = User(id=1, email='test@example.com')
    posts = get_user_posts(user.id)
    assert len(posts) > 0
```

## Performance

### ✅ Use Lazy Evaluation

```python
# ✅ GOOD: Generator (memory efficient)
def get_all_users():
    return User.query.yield_per(100)  # Fetches in batches

# In route
for user in get_all_users():
    process_user(user)  # Only loads 100 at a time

# ❌ BAD: Loads everything into memory
def get_all_users():
    return User.query.all()  # Could be millions of records
```

## Documentation

### ✅ Document Complex Logic

```python
def calculate_subscription_price(user, plan, coupon=None):
    """
    Calculate final subscription price with discounts.
    
    Price calculation follows this order:
    1. Base plan price
    2. Apply volume discount if user has multiple licenses
    3. Apply coupon discount if provided and valid
    4. Add tax based on user's country
    
    Args:
        user: User object
        plan: SubscriptionPlan object
        coupon: Optional Coupon object
        
    Returns:
        dict: {
            'base_price': Decimal,
            'discounts': List[Dict],
            'tax': Decimal,
            'final_price': Decimal
        }
        
    Raises:
        ValueError: If plan is invalid or expired
        CouponError: If coupon is invalid or expired
    """
    if not plan.is_active:
        raise ValueError(f"Plan {plan.id} is not active")
    
    # Implementation...
```

## Summary

1. **Always catch specific exceptions**, not bare `except` or broad `Exception`
2. **Validate all user input** before using it
3. **Use type hints** for better code clarity
4. **Log errors with context** - include user IDs, timestamps, etc.
5. **Handle database errors** with rollback and proper error messages
6. **Keep functions focused** - one responsibility per function
7. **Write testable code** - avoid global state
8. **Document complex logic** - future you will thank you
9. **Use security best practices** - parameterized queries, permission checks
10. **Think about performance** - pagination, caching, lazy loading
