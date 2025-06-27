from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, User, GameRound, Bet
import random
import time
import threading
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Настройка базы данных
if 'DATABASE_URL' in os.environ:
    database_url = os.environ['DATABASE_URL']
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

# Настройка SocketIO для максимальной совместимости
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

# Глобальные переменные игры
current_round = None
game_state = {
    'status': 'waiting',
    'time_left': 0,
    'round_number': 1
}

# Числа европейской рулетки и их цвета
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
    try:
        return User.query.get(int(user_id))
    except:
        return None

# Главная страница
@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return render_template('index.html', user=current_user)

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Валидация
        if len(username) < 3:
            flash('Логин должен содержать минимум 3 символа')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов')
            return render_template('register.html')
        
        # Проверка существования пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует')
            return render_template('register.html')
        
        try:
            # Создание нового пользователя
            user = User(username=username)
            user.set_password(password)
            user.balance = 1000.0
            
            db.session.add(user)
            db.session.commit()
            
            flash('Регистрация успешна! Теперь вы можете войти в систему.')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка регистрации: {e}")
            flash('Ошибка при регистрации. Попробуйте еще раз.')
    
    return render_template('register.html')

# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль')
    
    return render_template('login.html')

# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы')
    return redirect(url_for('login'))

# Профиль пользователя
@app.route('/profile')
@login_required
def profile():
    try:
        # Получаем последние 20 ставок пользователя
        user_bets = Bet.query.filter_by(user_id=current_user.id)\
                            .order_by(Bet.created_at.desc()).limit(20).all()
        return render_template('profile.html', user=current_user, bets=user_bets)
    except Exception as e:
        print(f"Ошибка загрузки профиля: {e}")
        flash('Ошибка загрузки профиля')
        return redirect(url_for('index'))

# API для размещения ставки
@app.route('/api/place_bet', methods=['POST'])
@login_required
def place_bet():
    try:
        # Получение и валидация данных
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Неверный формат данных'})
        
        bet_type = data.get('bet_type')
        amount = data.get('amount')
        
        if not bet_type or not amount:
            return jsonify({'success': False, 'message': 'Недостаточно данных'})
        
        # Проверка суммы ставки
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Неверная сумма ставки'})
        
        # Проверка статуса игры
        if game_state['status'] != 'betting':
            return jsonify({'success': False, 'message': 'Ставки не принимаются в данный момент'})
        
        # Проверка баланса
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Сумма ставки должна быть больше 0'})
        
        if amount > current_user.balance:
            return jsonify({'success': False, 'message': 'Недостаточно средств на балансе'})
        
        # Проверка типа ставки
        if bet_type not in ['red', 'black', 'green']:
            return jsonify({'success': False, 'message': 'Неверный тип ставки'})
        
        # Проверка существования текущего раунда
        if not current_round:
            return jsonify({'success': False, 'message': 'Раунд не найден'})
        
        # Определяем коэффициенты выплат
        multipliers = {'red': 2, 'black': 2, 'green': 36}
        potential_win = amount * multipliers[bet_type]
        
        # Создание ставки
        bet = Bet(
            user_id=current_user.id,
            round_id=current_round.id,
            bet_type=bet_type,
            amount=amount,
            potential_win=potential_win
        )
        
        # Списание средств с баланса
        current_user.balance -= amount
        
        # Сохранение в базе данных
        db.session.add(bet)
        db.session.commit()
        
        # Уведомление всех игроков о новой ставке
        socketio.emit('bet_placed', {
            'username': current_user.username,
            'bet_type': bet_type,
            'amount': amount
        }, room='game')
        
        return jsonify({
            'success': True, 
            'new_balance': round(current_user.balance, 2),
            'message': 'Ставка успешно размещена!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Ошибка размещения ставки: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'})

# API для получения баланса пользователя
@app.route('/api/user_balance')
@login_required
def get_user_balance():
    try:
        return jsonify({'balance': round(current_user.balance, 2)})
    except Exception as e:
        print(f"Ошибка получения баланса: {e}")
        return jsonify({'balance': 0})

# API для получения последних результатов
@app.route('/api/recent_results')
def get_recent_results():
    try:
        recent_rounds = GameRound.query.filter(
            GameRound.winning_number.isnot(None)
        ).order_by(GameRound.end_time.desc()).limit(10).all()
        
        results = []
        for round in recent_rounds:
            results.append({
                'number': round.winning_number,
                'color': round.winning_color,
                'round': round.round_number
            })
        
        return jsonify({'results': results})
    except Exception as e:
        print(f"Ошибка получения результатов: {e}")
        return jsonify({'results': []})

# WebSocket: Подключение пользователя
@socketio.on('connect')
def on_connect():
    try:
        if current_user.is_authenticated:
            join_room('game')
            emit('game_state', game_state)
            print(f"Игрок подключился: {current_user.username}")
        else:
            print("Анонимный пользователь подключился")
    except Exception as e:
        print(f"Ошибка подключения: {e}")

# WebSocket: Отключение пользователя
@socketio.on('disconnect')
def on_disconnect():
    try:
        if current_user.is_authenticated:
            leave_room('game')
            print(f"Игрок отключился: {current_user.username}")
    except Exception as e:
        print(f"Ошибка отключения: {e}")

# Функция определения цвета числа
def get_winning_color(number):
    return ROULETTE_NUMBERS.get(number, 'green')

# Обработка ставок после завершения раунда
def process_bets(winning_number, winning_color):
    """Обрабатывает все ставки для текущего раунда"""
    if not current_round:
        return
    
    try:
        # Получаем все ставки текущего раунда
        round_bets = Bet.query.filter_by(round_id=current_round.id).all()
        
        winners_count = 0
        total_payout = 0
        
        for bet in round_bets:
            if bet.bet_type == winning_color:
                # Выигрышная ставка
                bet.is_winner = True
                bet.actual_win = bet.potential_win
                
                # Начисляем выигрыш пользователю
                user = User.query.get(bet.user_id)
                if user:
                    user.balance += bet.actual_win
                    total_payout += bet.actual_win
                    winners_count += 1
                    
            else:
                # Проигрышная ставка
                bet.is_winner = False
                bet.actual_win = 0
        
        # Сохраняем изменения
        db.session.commit()
        
        print(f"Обработано ставок: {len(round_bets)}, Выигравших: {winners_count}, Выплачено: {total_payout}")
        
    except Exception as e:
        db.session.rollback()
        print(f'Ошибка обработки ставок: {e}')

# Основной игровой цикл
def game_loop():
    """Основной игровой цикл рулетки"""
    global current_round, game_state
    
    print("🎰 Игровой цикл запущен!")
    
    with app.app_context():
        while True:
            try:
                print(f"\n🎲 Начинается раунд #{game_state['round_number']}")
                
                # === ФАЗА ПРИЕМА СТАВОК (30 секунд) ===
                game_state['status'] = 'betting'
                game_state['time_left'] = 30
                
                # Создание нового раунда в БД
                current_round = GameRound(
                    round_number=game_state['round_number'],
                    status='betting'
                )
                db.session.add(current_round)
                db.session.commit()
                
                # Уведомление всех игроков о начале раунда
                socketio.emit('new_round', {
                    'round_number': game_state['round_number'],
                    'status': 'betting',
                    'time_left': 30
                }, room='game')
                
                # Обратный отсчет для приема ставок
                for i in range(30, 0, -1):
                    game_state['time_left'] = i
                    socketio.emit('timer_update', {
                        'time_left': i, 
                        'status': 'betting'
                    }, room='game')
                    time.sleep(1)
                
                print("⏰ Прием ставок завершен")
                
                # === ФАЗА ВРАЩЕНИЯ РУЛЕТКИ (10 секунд) ===
                game_state['status'] = 'spinning'
                game_state['time_left'] = 10
                
                # Обновляем статус раунда
                current_round.status = 'spinning'
                db.session.commit()
                
                # Генерация случайного выигрышного числа
                winning_number = random.randint(0, 36)
                winning_color = get_winning_color(winning_number)
                
                print(f"🎯 Выпало число: {winning_number} ({winning_color})")
                
                # Уведомление о начале вращения
                socketio.emit('spin_start', {
                    'winning_number': winning_number,
                    'time': 10
                }, room='game')
                
                # Обратный отсчет для вращения
                for i in range(10, 0, -1):
                    game_state['time_left'] = i
                    socketio.emit('timer_update', {
                        'time_left': i, 
                        'status': 'spinning'
                    }, room='game')
                    time.sleep(1)
                
                # === ЗАВЕРШЕНИЕ РАУНДА ===
                
                # Обновляем информацию о раунде
                current_round.winning_number = winning_number
                current_round.winning_color = winning_color
                current_round.status = 'finished'
                current_round.end_time = datetime.utcnow()
                db.session.commit()
                
                print("🎊 Обработка результатов...")
                
                # Обрабатываем все ставки
                process_bets(winning_number, winning_color)
                
                # Уведомляем всех игроков о результате
                socketio.emit('round_finished', {
                    'winning_number': winning_number,
                    'winning_color': winning_color,
                    'round_number': game_state['round_number']
                }, room='game')
                
                print(f"✅ Раунд #{game_state['round_number']} завершен")
                
                # Переходим к следующему раунду
                game_state['round_number'] += 1
                
                # Пауза между раундами
                print("⏸️  Пауза между раундами (3 сек)")
                time.sleep(3)
                
            except Exception as e:
                print(f'❌ Ошибка в игровом цикле: {e}')
                time.sleep(5)  # Пауза при ошибке

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return jsonify({'error': 'Доступ запрещен'}), 403

# Контекстный процессор для шаблонов
@app.context_processor
def utility_processor():
    def format_currency(amount):
        return f"{amount:.2f}₽"
    return dict(format_currency=format_currency)

# Фильтры для шаблонов
@app.template_filter('currency')
def currency_filter(amount):
    return f"{amount:.2f}₽"

@app.template_filter('datetime')
def datetime_filter(dt):
    return dt.strftime('%d.%m.%Y %H:%M')

# API для статистики (дополнительно)
@app.route('/api/stats')
def get_stats():
    try:
        total_rounds = GameRound.query.filter(GameRound.winning_number.isnot(None)).count()
        total_bets = Bet.query.count()
        total_users = User.query.count()
        
        # Статистика по цветам
        red_wins = GameRound.query.filter_by(winning_color='red').count()
        black_wins = GameRound.query.filter_by(winning_color='black').count()
        green_wins = GameRound.query.filter_by(winning_color='green').count()
        
        return jsonify({
            'total_rounds': total_rounds,
            'total_bets': total_bets,
            'total_users': total_users,
            'color_stats': {
                'red': red_wins,
                'black': black_wins,
                'green': green_wins
            }
        })
    except Exception as e:
        print(f"Ошибка получения статистики: {e}")
        return jsonify({'error': 'Ошибка сервера'}), 500

# Проверка здоровья приложения
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'game_status': game_state['status'],
        'round': game_state['round_number']
    })

# Главная точка входа
if __name__ == '__main__':
    with app.app_context():
        try:
            # Создание таблиц базы данных
            print("🗃️  Инициализация базы данных...")
            db.create_all()
            
            # Создание тестового пользователя для демонстрации
            if User.query.count() == 0:
                print("👤 Создание тестового пользователя...")
                
                # Основной тестовый пользователь
                demo_user = User(username='demo')
                demo_user.set_password('demo123')
                demo_user.balance = 5000.0
                db.session.add(demo_user)
                
                # Дополнительные тестовые пользователи
                test_users = [
                    ('player1', 'pass123', 2000.0),
                    ('player2', 'pass123', 3000.0),
                    ('vip', 'vip123', 10000.0)
                ]
                
                for username, password, balance in test_users:
                    user = User(username=username)
                    user.set_password(password)
                    user.balance = balance
                    db.session.add(user)
                
                db.session.commit()
                
                print("✅ Тестовые пользователи созданы:")
                print("   demo/demo123 (баланс: 5000₽)")
                print("   player1/pass123 (баланс: 2000₽)")
                print("   player2/pass123 (баланс: 3000₽)")
                print("   vip/vip123 (баланс: 10000₽)")
            else:
                print("✅ База данных уже содержит пользователей")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации базы данных: {e}")
        
        # Запуск игрового цикла в отдельном потоке
        print("🚀 Запуск игрового потока...")
        game_thread = threading.Thread(target=game_loop, daemon=True)
        game_thread.start()
        
        # Определение параметров запуска
        port = int(os.environ.get('PORT', 5000))
        debug_mode = os.environ.get('FLASK_ENV') != 'production'
        
        print(f"🌐 Приложение запускается на порту {port}")
        print(f"🔧 Режим отладки: {'включен' if debug_mode else 'выключен'}")
        print("=" * 50)
        print("🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА ОНЛАЙН")
        print("=" * 50)
        print(f"📱 Локальный адрес: http://localhost:{port}")
        print("🎮 Готов к игре!")
        
        try:
            # Запуск приложения с SocketIO
            socketio.run(
                app, 
                debug=debug_mode, 
                host='0.0.0.0', 
                port=port,
                allow_unsafe_werkzeug=True,
                use_reloader=False  # Отключаем reloader чтобы избежать двойного запуска
            )
        except KeyboardInterrupt:
            print("\n👋 Приложение остановлено пользователем")
        except Exception as e:
            print(f"❌ Ошибка запуска приложения: {e}")
