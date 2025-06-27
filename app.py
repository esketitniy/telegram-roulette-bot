from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import random
import threading
import time
import os
import signal
import atexit

# Создание приложения
app = Flask(__name__)

# Конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# База данных
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///roulette.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# SocketIO с настройками для продакшена
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False
)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.String(50), nullable=False)
    bet_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    result = db.Column(db.String(20))
    payout = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GameHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(50), unique=True, nullable=False)
    winning_number = db.Column(db.Integer, nullable=False)
    winning_color = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Конфигурация рулетки
ROULETTE_NUMBERS = {
    0: 'green',
    1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black', 7: 'red', 8: 'black', 9: 'red', 10: 'black',
    11: 'black', 12: 'red', 13: 'black', 14: 'red', 15: 'black', 16: 'red', 17: 'black', 18: 'red', 19: 'red', 20: 'black',
    21: 'red', 22: 'black', 23: 'red', 24: 'black', 25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red',
    31: 'black', 32: 'red', 33: 'black', 34: 'red', 35: 'black', 36: 'red'
}

PAYOUT_MULTIPLIERS = {'red': 2.0, 'black': 2.0, 'green': 35.0}

# Глобальные переменные для игры
current_game = {
    'state': 'betting',
    'game_id': None,
    'bets': {},
    'time_left': 25,
    'winning_number': None,
    'winning_color': None
}

game_active = True

def generate_game_id():
    return f"game_{int(time.time())}_{random.randint(1000, 9999)}"

def get_last_results(limit=10):
    try:
        results = GameHistory.query.order_by(GameHistory.created_at.desc()).limit(limit).all()
        return [{'number': r.winning_number, 'color': r.winning_color} for r in results]
    except Exception as e:
        print(f"Ошибка получения истории: {e}")
        return []

def spin_roulette():
    winning_number = random.randint(0, 36)
    winning_color = ROULETTE_NUMBERS[winning_number]
    return winning_number, winning_color

def process_bets(game_id, winning_color):
    try:
        if game_id not in current_game['bets']:
            return
        
        for user_id, user_bets in current_game['bets'][game_id].items():
            user = User.query.get(user_id)
            if not user:
                continue
                
            for bet_info in user_bets:
                bet_type = bet_info['type']
                amount = bet_info['amount']
                
                if bet_type == winning_color:
                    result = 'win'
                    payout = amount * PAYOUT_MULTIPLIERS[bet_type]
                    user.balance += payout
                else:
                    result = 'lose'
                    payout = 0
                
                bet = Bet(
                    user_id=user_id,
                    game_id=game_id,
                    bet_type=bet_type,
                    amount=amount,
                    result=result,
                    payout=payout
                )
                db.session.add(bet)
        
        db.session.commit()
    except Exception as e:
        print(f"Ошибка обработки ставок: {e}")
        db.session.rollback()

def game_loop():
    global game_active
    print("🎮 Игровой цикл запущен")
    
    while game_active:
        try:
            # Создаем контекст приложения для каждой итерации
            with app.app_context():
                # Фаза ставок (25 секунд)
                current_game['state'] = 'betting'
                current_game['game_id'] = generate_game_id()
                current_game['bets'][current_game['game_id']] = {}
                current_game['time_left'] = 25
                
                print(f"🎯 Новая игра запущена: {current_game['game_id']}")
                
                socketio.emit('game_state', {
                    'state': 'betting',
                    'time_left': 25,
                    'game_id': current_game['game_id']
                }, broadcast=True)
                
                # Обратный отсчет ставок
                for i in range(25, 0, -1):
                    if not game_active:
                        break
                    current_game['time_left'] = i
                    print(f"⏰ Время ставок: {i}")
                    socketio.emit('betting_time', {'time_left': i}, broadcast=True)
                    socketio.sleep(1)
                
                if not game_active:
                    break
                
                # Фаза вращения (10 секунд)
                current_game['state'] = 'spinning'
                winning_number, winning_color = spin_roulette()
                current_game['winning_number'] = winning_number
                current_game['winning_color'] = winning_color
                
                print(f"🎲 Выпало: {winning_number} ({winning_color})")
                
                socketio.emit('game_state', {
                    'state': 'spinning',
                    'winning_number': winning_number,
                    'winning_color': winning_color
                }, broadcast=True)
                
                # Анимация вращения
                socketio.sleep(10)
                
                if not game_active:
                    break
                
                # Обработка результатов
                process_bets(current_game['game_id'], winning_color)
                
                # Сохранение результата в историю
                try:
                    game_result = GameHistory(
                        game_id=current_game['game_id'],
                        winning_number=winning_number,
                        winning_color=winning_color
                    )
                    db.session.add(game_result)
                    db.session.commit()
                except Exception as e:
                    print(f"Ошибка сохранения истории: {e}")
                    db.session.rollback()
                
                # Отправка результатов
                socketio.emit('game_result', {
                    'winning_number': winning_number,
                    'winning_color': winning_color,
                    'game_id': current_game['game_id']
                }, broadcast=True)
                
                # Отправка обновленной истории
                socketio.emit('history_update', {'history': get_last_results()}, broadcast=True)
                
                # Пауза перед следующей игрой
                socketio.sleep(3)
                
        except Exception as e:
            print(f"❌ Ошибка в игровом цикле: {str(e)}")
            socketio.sleep(5)

# Маршруты
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    history = get_last_results()
    return render_template('index.html', user=user, history=history)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not username or not email or not password:
            flash('Все поля обязательны для заполнения')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует')
            return render_template('register.html')
        
        try:
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            
            session['user_id'] = user.id
            session['username'] = user.username
            session.permanent = True
            
            flash('Регистрация успешна!')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при регистрации. Попробуйте снова.')
            print(f"Registration error: {e}")
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = 'remember' in request.form
        
        if not username or not password:
            flash('Введите имя пользователя и пароль')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    bets = Bet.query.filter_by(user_id=user.id).order_by(Bet.created_at.desc()).limit(50).all()
    return render_template('profile.html', user=user, bets=bets)

# WebSocket события
@socketio.on('connect')
def handle_connect():
    print(f"👤 Клиент подключился: {request.sid}")
    if 'user_id' in session:
        join_room('game_room')
        # Отправляем текущее состояние игры
        emit('game_state', {
            'state': current_game['state'],
            'time_left': current_game['time_left'],
            'game_id': current_game['game_id']
        })
        emit('history_update', {'history': get_last_results()})
        print(f"🎮 Пользователь {session.get('username')} подключился к игре")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"👤 Клиент отключился: {request.sid}")
    if 'user_id' in session:
        leave_room('game_room')

@socketio.on('place_bet')
def handle_bet(data):
    if 'user_id' not in session:
        emit('bet_error', {'message': 'Необходимо войти в систему'})
        return
    
    if current_game['state'] != 'betting':
        emit('bet_error', {'message': 'Ставки не принимаются'})
        return
    
    try:
        user_id = session['user_id']
        user = User.query.get(user_id)
        
        if not user:
            emit('bet_error', {'message': 'Пользователь не найден'})
            return
        
        bet_type = data.get('type')
        amount = float(data.get('amount', 0))
        
        if amount <= 0 or amount > user.balance:
            emit('bet_error', {'message': 'Недостаточно средств'})
            return
        
        if bet_type not in ['red', 'black', 'green']:
            emit('bet_error', {'message': 'Неверный тип ставки'})
            return
        
        # Списание суммы ставки
        user.balance -= amount
        db.session.commit()
        
        # Сохранение ставки
        game_id = current_game['game_id']
        if game_id not in current_game['bets']:
            current_game['bets'][game_id] = {}
        
        if user_id not in current_game['bets'][game_id]:
            current_game['bets'][game_id][user_id] = []
        
        current_game['bets'][game_id][user_id].append({
            'type': bet_type,
            'amount': amount
        })
        
        emit('bet_placed', {
            'type': bet_type,
            'amount': amount,
            'balance': user.balance
        })
        
        print(f"💰 Ставка размещена: {user.username} - {bet_type} - {amount}")
        
    except Exception as e:
        db.session.rollback()
        emit('bet_error', {'message': 'Ошибка при размещении ставки'})
        print(f"❌ Bet error: {e}")

# Функция запуска игрового цикла
def start_game_loop():
    """Запуск игрового цикла в отдельном потоке"""
    print("🚀 Запуск игрового цикла...")
    socketio.start_background_task(game_loop)

# Обработчик завершения работы
def cleanup():
    global game_active
    game_active = False
    print("🛑 Игровой цикл остановлен")

# Регистрация обработчиков сигналов
signal.signal(signal.SIGINT, lambda s, f: cleanup())
signal.signal(signal.SIGTERM, lambda s, f: cleanup())
atexit.register(cleanup)

# Инициализация базы данных
def init_db():
    try:
        with app.app_context():
            db.create_all()
            print("📊 База данных инициализирована")
            
            # Проверяем, есть ли записи в истории
            history_count = GameHistory.query.count()
            print(f"📈 Записей в истории: {history_count}")
            
            # Создаем тестовые записи если их нет
            if history_count == 0:
                test_results = [
                    {'number': 7, 'color': 'red'},
                    {'number': 0, 'color': 'green'},
                    {'number': 22, 'color': 'black'},
                    {'number': 14, 'color': 'red'},
                    {'number': 31, 'color': 'black'}
                ]
                
                for i, result in enumerate(test_results):
                    game_history = GameHistory(
                        game_id=f"test_game_{i}",
                        winning_number=result['number'],
                        winning_color=result['color']
                    )
                    db.session.add(game_history)
                
                db.session.commit()
                print("🎲 Добавлены тестовые результаты")
                
    except Exception as e:
        print(f"❌ Ошибка инициализации базы данных: {e}")

# Проверка состояния приложения
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'ok',
        'game_active': game_active,
        'current_state': current_game['state'],
        'time_left': current_game['time_left']
    })

# API для получения статистики
@app.route('/api/stats')
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        total_games = GameHistory.query.count()
        user_bets = Bet.query.filter_by(user_id=session['user_id']).count()
        
        # Статистика по цветам
        red_count = GameHistory.query.filter_by(winning_color='red').count()
        black_count = GameHistory.query.filter_by(winning_color='black').count()
        green_count = GameHistory.query.filter_by(winning_color='green').count()
        
        return jsonify({
            'total_games': total_games,
            'user_bets': user_bets,
            'color_stats': {
                'red': red_count,
                'black': black_count,
                'green': green_count
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Инициализация базы данных
    init_db()
    
    # Запуск игрового цикла после инициализации
    start_game_loop()
    
    # Настройка для продакшена
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"🌐 Запуск сервера на порту {port}")
    print(f"🔧 Debug режим: {debug}")
    
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=port, 
        debug=debug,
        allow_unsafe_werkzeug=True
    )
