from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import time
import random
import threading
import hashlib
from datetime import datetime, timedelta
import os

def safe_emit(event, data, room=None):
    """Безопасная отправка сообщений через Socket.IO"""
    try:
        if room:
            socketio.emit(event, data, room=room)
        else:
            socketio.emit(event, data)
    except Exception as e:
        print(f"Ошибка отправки {event}: {e}")

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", 
                   transport=['websocket'], 
                   ping_timeout=60, 
                   ping_interval=25)

# Глобальные переменные для игры
game_state = {
    'phase': 'betting',  # betting, spinning, waiting
    'time_left': 25,
    'current_bets': {},
    'history': [],
    'active_players': set(),
    'round_id': 1,
    'result': None,
    'hash': None
}

# Конфигурация рулетки
ROULETTE_CONFIG = {
    'red_count': 7,
    'black_count': 7,
    'green_count': 1,
    'red_multiplier': 2,
    'black_multiplier': 2,
    'green_multiplier': 14,
    'min_bet': 10,
    'betting_time': 25,
    'spinning_time': 10
}

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        balance INTEGER DEFAULT 1000,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Таблица истории ставок
    c.execute('''CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        round_id INTEGER,
        bet_type TEXT,
        amount INTEGER,
        result TEXT,
        win_amount INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Таблица истории игр
    c.execute('''CREATE TABLE IF NOT EXISTS game_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER,
        result TEXT,
        hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Получение соединения с базой данных"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def generate_game_hash():
    """Генерация хеша для честной игры"""
    timestamp = str(time.time())
    random_data = str(random.random())
    return hashlib.sha256((timestamp + random_data).encode()).hexdigest()

def spin_roulette():
    """Определение результата рулетки (15 секторов)"""
    # 15 секторов: красный-черный-красный-черный-зеленый...
    roulette_sectors = [
        {'number': 1, 'color': 'red'},      # сектор 1
        {'number': 2, 'color': 'black'},    # сектор 2
        {'number': 3, 'color': 'red'},      # сектор 3
        {'number': 4, 'color': 'black'},    # сектор 4
        {'number': 0, 'color': 'green'},    # сектор 5 (зеленый)
        {'number': 5, 'color': 'red'},      # сектор 6
        {'number': 6, 'color': 'black'},    # сектор 7
        {'number': 7, 'color': 'red'},      # сектор 8
        {'number': 8, 'color': 'black'},    # сектор 9
        {'number': 9, 'color': 'red'},      # сектор 10
        {'number': 10, 'color': 'black'},   # сектор 11
        {'number': 11, 'color': 'red'},     # сектор 12
        {'number': 12, 'color': 'black'},   # сектор 13
        {'number': 13, 'color': 'red'},     # сектор 14
        {'number': 14, 'color': 'black'}    # сектор 15
    ]
    
    result = random.choice(roulette_sectors)
    game_state['winning_number'] = result['number']
    return result['color']
    
def calculate_winnings(bet_type, amount, result):
    """Расчет выигрыша"""
    if bet_type == result:
        if result == 'green':
            return amount * ROULETTE_CONFIG['green_multiplier']
        else:
            return amount * ROULETTE_CONFIG['red_multiplier']
    return 0

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    history = conn.execute('SELECT * FROM game_history ORDER BY id DESC LIMIT 10').fetchall()
    conn.close()
    
    return render_template('index.html', user=user, history=history)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if len(username) < 3:
            flash('Имя пользователя должно содержать минимум 3 символа')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов')
            return render_template('register.html')
        
        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing_user:
            flash('Пользователь с таким именем уже существует')
            conn.close()
            return render_template('register.html')
        
        password_hash = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                    (username, password_hash))
        conn.commit()
        conn.close()
        
        flash('Регистрация успешна! Войдите в систему')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
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
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    # История ставок
    bets = conn.execute('''
        SELECT b.*, gh.result as game_result, gh.created_at as game_time
        FROM bets b
        JOIN game_history gh ON b.round_id = gh.round_id
        WHERE b.user_id = ?
        ORDER BY b.created_at DESC
        LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
    # Статистика
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_bets,
            SUM(amount) as total_wagered,
            SUM(win_amount) as total_won,
            COUNT(CASE WHEN win_amount > 0 THEN 1 END) as wins
        FROM bets WHERE user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    conn.close()
    
    return render_template('profile.html', user=user, bets=bets, stats=stats)

@app.route('/api/place_bet', methods=['POST'])
def place_bet():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    data = request.json
    bet_type = data.get('bet_type')
    amount = int(data.get('amount', 0))
    
    if bet_type not in ['red', 'black', 'green']:
        return jsonify({'error': 'Неверный тип ставки'}), 400
    
    if amount < ROULETTE_CONFIG['min_bet']:
        return jsonify({'error': f'Минимальная ставка {ROULETTE_CONFIG["min_bet"]}'}), 400
    
    if game_state['phase'] != 'betting':
        return jsonify({'error': 'Ставки не принимаются'}), 400
    
    # Проверка на существующую ставку
    user_key = f"user_{session['user_id']}"
    if user_key in game_state['current_bets']:
        return jsonify({'error': 'Вы уже сделали ставку в этом раунде'}), 400
    
    conn = get_db_connection()
    user = conn.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    if user['balance'] < amount:
        conn.close()
        return jsonify({'error': 'Недостаточно средств'}), 400
    
    # Обновляем баланс
    conn.execute('UPDATE users SET balance = balance - ? WHERE id = ?', 
                (amount, session['user_id']))
    conn.commit()
    conn.close()
    
    # Добавляем ставку в текущую игру
    game_state['current_bets'][user_key] = {
        'user_id': session['user_id'],
        'username': session['username'],
        'bet_type': bet_type,
        'amount': amount
    }
    
    # Отправляем обновление всем игрокам
    safe_emit('bet_placed', {
        'username': session['username'],
        'bet_type': bet_type,
        'amount': amount
    })
    
    return jsonify({'success': True})
@socketio.on('connect')
def handle_connect():
    try:
        if 'user_id' in session:
            game_state['active_players'].add(session['username'])
            join_room('game')
            emit('game_state', {
                'phase': game_state['phase'],
                'time_left': game_state['time_left'],
                'current_bets': list(game_state['current_bets'].values()),
                'history': game_state['history'][-10:]
            })
    except Exception as e:
        print(f"Ошибка подключения: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    try:
        if 'username' in session:
            game_state['active_players'].discard(session['username'])
            leave_room('game')
    except Exception as e:
        print(f"Ошибка отключения: {e}")
        
def game_loop():
    """Основной игровой цикл"""
    while True:
        # Фаза ставок
        game_state['phase'] = 'betting'
        game_state['time_left'] = ROULETTE_CONFIG['betting_time']
        game_state['hash'] = generate_game_hash()
        
        safe_emit('phase_change', {
            'phase': 'spinning',
            'time_left': game_state['time_left'],
            'result': game_state['result']
        })
        
        # Отсчет времени для ставок
        for i in range(ROULETTE_CONFIG['betting_time']):
            time.sleep(1)
            game_state['time_left'] -= 1
            safe_emit('time_update', {'time_left': game_state['time_left']})
        
        # Фаза вращения
        game_state['phase'] = 'spinning'
        game_state['time_left'] = ROULETTE_CONFIG['spinning_time']
        game_state['result'] = spin_roulette()
        
        safe_emit('phase_change', {
            'phase': 'betting',
            'time_left': game_state['time_left'],
            'hash': game_state['hash']
        })
        
        # Отсчет времени вращения
        for i in range(ROULETTE_CONFIG['spinning_time']):
            time.sleep(1)
            game_state['time_left'] -= 1
            safe_emit('time_update', {'time_left': game_state['time_left']})
        
        # Обработка результатов
        process_results()
        
        # Пауза между играми
        game_state['phase'] = 'waiting'
        time.sleep(3)
        
        # Подготовка к следующему раунду
        game_state['round_id'] += 1
        game_state['current_bets'] = {}

def process_results():
    """Обработка результатов игры"""
    result = game_state['result']
    round_id = game_state['round_id']
    
    # Сохраняем результат в историю
    conn = get_db_connection()
    conn.execute('INSERT INTO game_history (round_id, result, hash) VALUES (?, ?, ?)',
                (round_id, result, game_state['hash']))
    
    # Обрабатываем ставки
    winners = []
    for user_key, bet_data in game_state['current_bets'].items():
        user_id = bet_data['user_id']
        bet_type = bet_data['bet_type']
        amount = bet_data['amount']
        
        win_amount = calculate_winnings(bet_type, amount, result)
        
        # Сохраняем ставку в базу
        conn.execute('''INSERT INTO bets (user_id, round_id, bet_type, amount, result, win_amount) 
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, round_id, bet_type, amount, result, win_amount))
        
        # Начисляем выигрыш
        if win_amount > 0:
            conn.execute('UPDATE users SET balance = balance + ? WHERE id = ?', 
                        (win_amount, user_id))
            winners.append({
                'username': bet_data['username'],
                'bet_type': bet_type,
                'amount': amount,
                'win_amount': win_amount
            })
    
    conn.commit()
    conn.close()
    
    # Обновляем историю
    game_state['history'].append({
        'round_id': round_id,
        'result': result,
        'timestamp': datetime.now().isoformat()
    })
    
    # Отправляем результаты
    safe_emit('game_result', {
        'result': result,
        'winners': winners,
        'history': game_state['history'][-10:]
    })

if __name__ == '__main__':
    init_db()
    
    # Запускаем игровой цикл в отдельном потоке
    game_thread = threading.Thread(target=game_loop)
    game_thread.daemon = True
    game_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
