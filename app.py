from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import sqlite3
import hashlib
import secrets
import threading
import time
import random
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['DEBUG'] = True

# Инициализация SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Конфигурация рулетки
ROULETTE_CONFIG = {
    'betting_time': 25,     # 25 секунд на ставки
    'spinning_time': 10,    # 10 секунд анимация вращения
    'min_bet': 10,
    'multipliers': {'red': 2, 'black': 2, 'green': 14}
}

# Состояние игры
game_state = {
    'phase': 'betting',  # betting, spinning
    'time_left': ROULETTE_CONFIG['betting_time'],
    'current_bets': {},
    'history': [],
    'result': None,
    'winning_number': None,
    'hash': None,
    'is_running': False
}

def get_db_connection():
    conn = sqlite3.connect('roulette.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 1000
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bet_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bet_type TEXT,
            amount INTEGER,
            result TEXT,
            win_amount INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            game_hash TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

def safe_emit(event, data, room=None, namespace=None):
    """Безопасная отправка сообщений через Socket.IO"""
    try:
        if room:
            socketio.emit(event, data, room=room, namespace=namespace)
        else:
            socketio.emit(event, data, namespace=namespace)
        print(f"Отправлено событие {event}: {data}")
    except Exception as e:
        print(f"Ошибка отправки {event}: {e}")

def spin_roulette():
    """Определение результата рулетки (15 секторов)"""
    roulette_sectors = [
        {'number': 1, 'color': 'red', 'angle': 0},
        {'number': 2, 'color': 'black', 'angle': 24},
        {'number': 3, 'color': 'red', 'angle': 48},
        {'number': 4, 'color': 'black', 'angle': 72},
        {'number': 0, 'color': 'green', 'angle': 96},
        {'number': 5, 'color': 'red', 'angle': 120},
        {'number': 6, 'color': 'black', 'angle': 144},
        {'number': 7, 'color': 'red', 'angle': 168},
        {'number': 8, 'color': 'black', 'angle': 192},
        {'number': 9, 'color': 'red', 'angle': 216},
        {'number': 10, 'color': 'black', 'angle': 240},
        {'number': 11, 'color': 'red', 'angle': 264},
        {'number': 12, 'color': 'black', 'angle': 288},
        {'number': 13, 'color': 'red', 'angle': 312},
        {'number': 14, 'color': 'black', 'angle': 336}
    ]
    
    result = random.choice(roulette_sectors)
    game_state['winning_number'] = result['number']
    game_state['winning_angle'] = result['angle']
    return result

def process_results(result_data):
    """Обработка результатов игры"""
    winners = []
    result = result_data['color']
    
    for bet_key, bet_data in game_state['current_bets'].items():
        if bet_data['bet_type'] == result:
            # Победитель
            multiplier = ROULETTE_CONFIG['multipliers'][result]
            win_amount = bet_data['amount'] * multiplier
            
            # Обновляем баланс в базе данных
            conn = get_db_connection()
            conn.execute('UPDATE users SET balance = balance + ? WHERE id = ?',
                        (win_amount, bet_data['user_id']))
            
            # Записываем в историю
            conn.execute('''INSERT INTO bet_history 
                           (user_id, bet_type, amount, result, win_amount, game_hash) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (bet_data['user_id'], bet_data['bet_type'], bet_data['amount'], 
                         result, win_amount, game_state['hash']))
            conn.commit()
            conn.close()
            
            winners.append({
                'username': bet_data['username'],
                'amount': win_amount
            })
        else:
            # Проигравший
            conn = get_db_connection()
            conn.execute('''INSERT INTO bet_history 
                           (user_id, bet_type, amount, result, win_amount, game_hash) 
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (bet_data['user_id'], bet_data['bet_type'], bet_data['amount'], 
                         result, 0, game_state['hash']))
            conn.commit()
            conn.close()
    
    # Добавляем в историю игр
    game_state['history'].append({
        'result': result,
        'number': game_state['winning_number'],
        'timestamp': int(time.time())
    })
    
    # Отправляем результат
    safe_emit('game_result', {
        'result': result,
        'winning_number': game_state['winning_number'],
        'winners': winners,
        'history': game_state['history'][-10:]
    })

def game_loop():
    """Основной цикл игры"""
    print("Запуск игрового цикла...")
    
    while game_state['is_running']:
        try:
            print("Начинаем новый раунд...")
            
            # Фаза ставок (25 секунд)
            game_state['phase'] = 'betting'
            game_state['time_left'] = ROULETTE_CONFIG['betting_time']
            game_state['current_bets'] = {}
            game_state['hash'] = secrets.token_hex(8)
            
            print(f"Фаза ставок: {game_state['time_left']} секунд")
            
            safe_emit('phase_change', {
                'phase': 'betting',
                'time_left': game_state['time_left'],
                'hash': game_state['hash']
            })
            
            # Отсчет времени для ставок
            for i in range(ROULETTE_CONFIG['betting_time']):
                if not game_state['is_running']:
                    break
                time.sleep(1)
                game_state['time_left'] = ROULETTE_CONFIG['betting_time'] - i - 1
                safe_emit('time_update', {'time_left': game_state['time_left']})
                print(f"Осталось времени на ставки: {game_state['time_left']}")
            
            if not game_state['is_running']:
                break
                
            print("Ставки закрыты, начинаем вращение...")
            
            # Фаза вращения (10 секунд)
            game_state['phase'] = 'spinning'
            game_state['time_left'] = ROULETTE_CONFIG['spinning_time']
            result_data = spin_roulette()
            game_state['result'] = result_data['color']
            game_state['winning_number'] = result_data['number']
            
            print(f"Результат: {result_data['number']} ({result_data['color']})")
            
            safe_emit('phase_change', {
                'phase': 'spinning',
                'time_left': game_state['time_left'],
                'result': result_data
            })
            
            # Отсчет времени вращения
            for i in range(ROULETTE_CONFIG['spinning_time']):
                if not game_state['is_running']:
                    break
                time.sleep(1)
                game_state['time_left'] = ROULETTE_CONFIG['spinning_time'] - i - 1
                safe_emit('time_update', {'time_left': game_state['time_left']})
            
            if not game_state['is_running']:
                break
                
            # Обработка результатов и выплаты
            process_results(result_data)
            
            print("Раунд завершен, пауза 2 секунды...")
            # Небольшая пауза перед следующим раундом
            time.sleep(2)
            
        except Exception as e:
            print(f"Ошибка в игровом цикле: {e}")
            time.sleep(5)

def start_game_loop():
    """Запуск игрового цикла в отдельном потоке"""
    if not game_state['is_running']:
        game_state['is_running'] = True
        game_thread = threading.Thread(target=game_loop, daemon=True)
        game_thread.start()
        print("Игровой поток запущен")

@socketio.on('connect')
def handle_connect():
    """Обработка подключения клиента"""
    try:
        print(f'Клиент подключился: {request.sid}')
        
        # Запускаем игровой цикл если он не запущен
        start_game_loop()
        
        # Отправляем текущее состояние игры новому клиенту
        emit('game_state', {
            'phase': game_state['phase'],
            'time_left': game_state['time_left'],
            'history': game_state['history'][-10:],
            'current_bets': list(game_state['current_bets'].values())
        })
        
    except Exception as e:
        print(f"Ошибка при подключении: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Обработка отключения клиента"""
    try:
        print(f'Клиент отключился: {request.sid}')
    except Exception as e:
        print(f"Ошибка при отключении: {e}")

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    return render_template('index.html', user=user, history=game_state['history'][-10:])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and user['password'] == hashlib.sha256(password.encode()).hexdigest():
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing_user:
            conn.close()
            return render_template('register.html', error='Пользователь уже существует')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                    (username, hashed_password))
        conn.commit()
        conn.close()
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/place_bet', methods=['POST'])
def place_bet():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    # Проверяем фазу игры
    if game_state['phase'] != 'betting':
        return jsonify({'error': 'Ставки закрыты. Дождитесь следующего раунда.'}), 400
    
    data = request.json
    bet_type = data.get('bet_type')
    amount = int(data.get('amount', 0))
    
    if bet_type not in ['red', 'black', 'green']:
        return jsonify({'error': 'Неверный тип ставки'}), 400
    
    if amount < ROULETTE_CONFIG['min_bet']:
        return jsonify({'error': f'Минимальная ставка {ROULETTE_CONFIG["min_bet"]}'}), 400
    
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
    
    print(f"Ставка размещена: {session['username']} - {amount} на {bet_type}")
    
    # Отправляем обновление всем игрокам
    safe_emit('bet_placed', {
        'username': session['username'],
        'bet_type': bet_type,
        'amount': amount
    })
    
    return jsonify({'success': True, 'message': 'Ставка принята!'})

@app.route('/api/user_balance')
def get_user_balance():
    if 'user_id' not in session:
        return jsonify({'error': 'Не авторизован'}), 401
    
    conn = get_db_connection()
    user = conn.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return jsonify({'balance': user['balance'] if user else 0})

@app.route('/api/game_state')
def get_game_state():
    return jsonify({
        'phase': game_state['phase'],
        'time_left': game_state['time_left'],
        'history': game_state['history'][-10:],
        'current_bets': list(game_state['current_bets'].values())
    })

if __name__ == '__main__':
    init_db()
    print("База данных инициализирована")
    print("Запуск сервера...")
    
    # Запускаем игровой цикл
    start_game_loop()
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
