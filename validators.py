from functools import wraps
from flask import jsonify, request
from flask_login import current_user

def validate_bet_request(f):
    """Декоратор для валидации запросов ставок"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Требуется JSON'}), 400
        
        data = request.get_json()
        bet_type = data.get('bet_type')
        amount = data.get('amount')
        
        # Проверяем тип ставки
        if bet_type not in ['red', 'black', 'green']:
            return jsonify({'success': False, 'message': 'Неверный тип ставки'}), 400
        
        # Проверяем сумму
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Неверная сумма ставки'}), 400
        
        if amount < 1 or amount > 10000:
            return jsonify({'success': False, 'message': 'Сумма ставки должна быть от 1 до 10000'}), 400
        
        if amount > current_user.balance:
            return jsonify({'success': False, 'message': 'Недостаточно средств'}), 400
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_decorator(max_requests=10, window=60):
    """Простое ограничение частоты запросов"""
    from collections import defaultdict
    import time
    
    requests = defaultdict(list)
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return f(*args, **kwargs)
            
            user_id = current_user.id
            now = time.time()
            
            # Очищаем старые запросы
            requests[user_id] = [req_time for req_time in requests[user_id] 
                               if now - req_time < window]
            
            if len(requests[user_id]) >= max_requests:
                return jsonify({'success': False, 'message': 'Слишком много запросов'}), 429
            
            requests[user_id].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
