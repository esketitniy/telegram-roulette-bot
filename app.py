from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, GameRound, Bet
import random
import time
import threading
from datetime import datetime
import os

# Создание приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Настройка базы данных
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///roulette.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Настройка SocketIO (упрощенная для продакшена)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False
)

# Глобальные переменные
current_round = None
game_state = {
    'status': 'waiting',
    'time_left': 0,
    'round_number': 1
}
game_started = False

# Числа европейской рулетки
ROULETTE_NUMBERS = {
    0: 'green',
    1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black',
    7: 'red', 8: 'black', 9: 'red', 10: 'black', 11: 'black', 12: 'red',
    13: 'black', 14: 'red', 15: 'black', 16: 'red', 17: 'black', 18: 'red',
    19: 'red', 20: 'black', 21: 'red', 22: 'black', 23: 'red', 24: 'black',
    25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red',
    31: 'black', 32: 'red', 33: 'black', 34: 'red', 35: 'black', 36: 'red'
}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Маршруты
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('index.html', user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if len(username) < 3:
            flash('Логин должен содержать минимум 3 символа')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html')
        
        try:
            user = User(username=username)
            user.set_password(password)
            user.balance = 1000.0
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна!')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при регистрации')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    user_bets = Bet.query.filter_by(user_id=current_user.id)\
                        .order_by(Bet.created_at.desc()).limit(20).all()
    return render_template('profile.html', user=current_user, bets=user_bets)

@app.route('/api/place_bet', methods=['POST'])
@login_required
def place_bet():
    try:
        data = request.get_json()
        bet_type = data.get('bet_type')
        amount = float(data.get('amount'))
        
        if game_state['status'] != 'betting':
            return jsonify({'success': False, 'message': 'Ставки не принимаются'})
        
        if amount <= 0 or amount > current_user.balance:
            return jsonify({'success': False, 'message': 'Недостаточно средств'})
        
        if bet_type not in ['red', 'black', 'green']:
            return jsonify({'success': False, 'message': 'Неверный тип ставки'})
        
        if not current_round:
            return jsonify({'success': False, 'message': 'Раунд не найден'})
        
        multipliers = {'red': 2, 'black': 2, 'green': 36}
        potential_win = amount * multipliers[bet_type]
        
        bet = Bet(
            user_id=current_user.id,
            round_id=current_round.id,
            bet_type=bet_type,
            amount=amount,
            potential_win=potential_win
        )
        
        current_user.balance -= amount
        db.session.add(bet)
        db.session.commit()
        
        socketio.emit('bet_placed', {
            'username': current_user.username,
            'bet_type': bet_type,
            'amount': amount
        }, room='game')
        
        return jsonify({'success': True, 'new_balance': current_user.balance})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Ошибка сервера'})

@app.route('/api/user_balance')
@login_required
def get_user_balance():
    return jsonify({'balance': current_user.balance})

# WebSocket события
@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        join_room('game')
        emit('game_state', game_state)

@socketio.on('disconnect')
def on_disconnect():
    if current_user.is_authenticated:
        leave_room('game')

def get_winning_color(number):
    return ROULETTE_NUMBERS.get(number, 'green')

def process_bets(winning_number, winning_color):
    if not current_round:
        return
    
    try:
        round_bets = Bet.query.filter_by(round_id=current_round.id).all()
        
        for bet in round_bets:
            if bet.bet_type == winning_color:
                bet.is_winner = True
                bet.actual_win = bet.potential_win
                user = User.query.get(bet.user_id)
                if user:
                    user.balance += bet.actual_win
            else:
                bet.is_winner = False
                bet.actual_win = 0
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()

def game_loop():
    global current_round, game_state, game_started
    
    if game_started:
        return
    
    game_started = True
    
    with app.app_context():
        while True:
            try:
                # Фаза ставок
                game_state['status'] = 'betting'
                game_state['time_left'] = 30
                
                current_round = GameRound(
                    round_number=game_state['round_number'],
                    status='betting'
                )
                db.session.add(current_round)
                db.session.commit()
                
                socketio.emit('new_round', {
                    'round_number': game_state['round_number'],
                    'status': 'betting',
                    'time_left': 30
                }, room='game')
                
                for i in range(30, 0, -1):
                    game_state['time_left'] = i
                    socketio.emit('timer_update', {
                        'time_left': i, 
                        'status': 'betting'
                    }, room='game')
                    time.sleep(1)
                
                # Фаза вращения
                game_state['status'] = 'spinning'
                game_state['time_left'] = 10
                current_round.status = 'spinning'
                db.session.commit()
                
                winning_number = random.randint(0, 36)
                winning_color = get_winning_color(winning_number)
                
                socketio.emit('spin_start', {
                    'winning_number': winning_number,
                    'time': 10
                }, room='game')
                
                for i in range(10, 0, -1):
                    game_state['time_left'] = i
                    socketio.emit('timer_update', {
                        'time_left': i, 
                        'status': 'spinning'
                    }, room='game')
                    time.sleep(1)
                
                # Завершение
                current_round.winning_number = winning_number
                current_round.winning_color = winning_color
                current_round.status = 'finished'
                current_round.end_time = datetime.utcnow()
                db.session.commit()
                
                process_bets(winning_number, winning_color)
                
                socketio.emit('round_finished', {
                    'winning_number': winning_number,
                    'winning_color': winning_color,
                    'round_number': game_state['round_number']
                }, room='game')
                
                game_state['round_number'] += 1
                time.sleep(3)
                
            except Exception as e:
                print(f'Ошибка в игровом цикле: {e}')
                time.sleep(5)

# Инициализация при запуске
def initialize_app():
    with app.app_context():
        db.create_all()
        
        if User.query.count() == 0:
            demo_user = User(username='demo')
            demo_user.set_password('demo123')
            demo_user.balance = 5000.0
            db.session.add(demo_user)
            db.session.commit()
        
        # Запуск игрового цикла
        game_thread = threading.Thread(target=game_loop, daemon=True)
        game_thread.start()

# Инициализация приложения
initialize_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    socketio.run(
        app, 
        debug=debug_mode, 
        host='0.0.0.0', 
        port=port
            )
