class RouletteGame {
    constructor() {
        console.log('Инициализация игры...');
        
        // Улучшенная инициализация Socket.IO
        this.socket = io({
            transports: ['polling', 'websocket'],
            upgrade: true,
            timeout: 20000,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });
        
        this.userBalance = parseInt(document.getElementById('balance')?.textContent) || 1000;
        this.currentBet = null;
        this.spinAngle = 0;
        this.isConnected = false;
        
        this.initializeEventListeners();
        this.initializeSocketListeners();
        
        console.log('Игра инициализирована');
    }

    initializeEventListeners() {
        console.log('Инициализация событий...');
        
        // Кнопки управления ставками
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = e.target.dataset.type;
                this.setBetAmount(type);
            });
        });

        // Кнопки цветных ставок
        document.querySelectorAll('.color-bet').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const color = e.target.dataset.color;
                console.log('Попытка поставить на:', color);
                this.placeBet(color);
            });
        });

        // Закрытие модальных окон
        document.querySelectorAll('.modal .close').forEach(closeBtn => {
            closeBtn.addEventListener('click', () => {
                closeBtn.closest('.modal').style.display = 'none';
            });
        });

        // Закрытие модальных окон по клику вне окна
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                e.target.style.display = 'none';
            }
        });
    }

    initializeSocketListeners() {
        console.log('Инициализация Socket.IO...');
        
        this.socket.on('connect', () => {
            console.log('✅ Подключено к серверу');
            this.isConnected = true;
            this.showNotification('Подключение установлено', 'success');
        });

        this.socket.on('disconnect', (reason) => {
            console.log('❌ Отключено от сервера:', reason);
            this.isConnected = false;
            this.showNotification('Соединение потеряно', 'error');
        });

        this.socket.on('connect_error', (error) => {
            console.error('❌ Ошибка подключения:', error);
            this.showNotification('Ошибка подключения к серверу', 'error');
        });

        this.socket.on('game_state', (data) => {
            console.log('📊 Получено состояние игры:', data);
            this.handleGameState(data);
        });

        this.socket.on('phase_change', (data) => {
            console.log('🔄 Смена фазы:', data);
            this.handlePhaseChange(data);
        });

        this.socket.on('time_update', (data) => {
            console.log('⏰ Обновление времени:', data.time_left);
            this.updateTimer(data);
        });

        this.socket.on('bet_placed', (data) => {
            console.log('💰 Размещена ставка:', data);
            this.handleBetPlaced(data);
        });

        this.socket.on('game_result', (data) => {
            console.log('🎯 Результат игры:', data);
            this.handleGameResult(data);
        });
    }

    handleGameState(data) {
        console.log('Обработка состояния игры:', data);
        this.updateHistory(data.history);
        if (data.current_bets) {
            this.displayCurrentBets(data.current_bets);
        }
    }

    handlePhaseChange(data) {
        console.log('Смена фазы на:', data.phase);
        
        const phaseElement = document.getElementById('game-phase');
        const timerElement = document.getElementById('timer');
        const bettingPanel = document.querySelector('.betting-panel');
        
        if (phaseElement) {
            if (data.phase === 'betting') {
                phaseElement.textContent = 'ВРЕМЯ СТАВОК';
                phaseElement.className = 'game-phase betting';
                if (bettingPanel) {
                    bettingPanel.style.pointerEvents = 'auto';
                    bettingPanel.style.opacity = '1';
                }
                // Сбрасываем ставку для нового раунда
                this.currentBet = null;
                this.clearBetHighlight();
                console.log('🟢 Ставки открыты');
            } else if (data.phase === 'spinning') {
                phaseElement.textContent = 'ВРАЩЕНИЕ РУЛЕТКИ';
                phaseElement.className = 'game-phase spinning';
                if (bettingPanel) {
                    bettingPanel.style.pointerEvents = 'none';
                    bettingPanel.style.opacity = '0.5';
                }
                // Запускаем анимацию рулетки
                if (data.result) {
                    console.log('🎰 Запуск рулетки с результатом:', data.result);
                    this.spinRoulette(data.result);
                }
                console.log('🔴 Ставки закрыты');
            }
        }
        
        if (timerElement) {
            timerElement.textContent = data.time_left;
        }
    }

    updateTimer(data) {
        const timerElement = document.getElementById('timer');
        if (timerElement) {
            timerElement.textContent = data.time_left;
            
            // Добавляем визуальные эффекты для последних секунд
            if (data.time_left <= 5) {
                timerElement.style.color = '#ff4757';
                timerElement.style.animation = 'pulse 1s infinite';
            } else {
                timerElement.style.color = '#ffd700';
                timerElement.style.animation = 'none';
            }
        }
    }

    handleBetPlaced(data) {
        console.log('Ставка размещена:', data);
        this.showNotification(`${data.username} поставил ${data.amount} на ${this.getColorName(data.bet_type)}`, 'info');
    }

    handleGameResult(data) {
        console.log('Результат игры:', data);
        
        // Показываем результат только после окончания анимации (10 секунд)
        setTimeout(() => {
            this.updateHistory(data.history);
            
            if (this.currentBet) {
                const isWin = this.currentBet.type === data.result;
                if (isWin) {
                    const multiplier = data.result === 'green' ? 14 : 2;
                    const winAmount = this.currentBet.amount * multiplier;
                    this.userBalance += winAmount;
                    this.updateBalance();
                    this.showWinModal(winAmount, data.winning_number);
                    this.createConfetti();
                    console.log('🎉 Выиграл:', winAmount);
                } else {
                    this.showLoseModal(data.winning_number);
                    console.log('😞 Проиграл');
                }
            }

            // Показываем результат
            this.showGameResult(data.result, data.winning_number);
            this.showWinningNumber(data.winning_number, data.result);

            // Сбрасываем текущую ставку
            this.currentBet = null;
            this.clearBetHighlight();

        }, 10000); // 10 секунд - время анимации вращения
    }

    placeBet(color) {
        console.log('Попытка поставить ставку на:', color);
        
        // Проверяем подключение
        if (!this.isConnected) {
            this.showNotification('Нет соединения с сервером', 'error');
            return;
        }

        const amountElement = document.getElementById('bet-amount');
        if (!amountElement) {
            console.error('Элемент bet-amount не найден');
            return;
        }

        const amount = parseInt(amountElement.textContent);
        console.log('Сумма ставки:', amount);
        
        if (amount > this.userBalance) {
            this.showNotification('Недостаточно средств!', 'error');
            return;
        }

        if (this.currentBet) {
            this.showNotification('Вы уже сделали ставку в этом раунде!', 'error');
            return;
        }

        console.log('Отправка ставки на сервер...');
        
        fetch('/api/place_bet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                bet_type: color,
                amount: amount
            })
        })
        .then(response => {
            console.log('Ответ сервера:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Данные от сервера:', data);
            if (data.success) {
                this.currentBet = { type: color, amount: amount };
                this.userBalance -= amount;
                this.updateBalance();
                this.highlightBet(color, amount);
                this.showNotification(data.message || 'Ставка принята!', 'success');
            } else {
                this.showNotification(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка при размещении ставки:', error);
            this.showNotification('Ошибка при размещении ставки', 'error');
        });
    }

    setBetAmount(type) {
        const betAmountElement = document.getElementById('bet-amount');
        if (!betAmountElement) return;
        
        const currentAmount = parseInt(betAmountElement.textContent);
        let newAmount = currentAmount;

        switch(type) {
            case 'min':
                newAmount = 10;
                break;
            case 'half':
                newAmount = Math.floor(currentAmount / 2);
                if (newAmount < 10) newAmount = 10;
                break;
            case 'double':
                newAmount = currentAmount * 2;
                break;
            case 'max':
                newAmount = this.userBalance;
                break;
        }

        betAmountElement.textContent = newAmount;
        console.log('Новая сумма ставки:', newAmount);
    }

    spinRoulette(resultData) {
        console.log('Вращение рулетки:', resultData);
        
        const wheel = document.getElementById('roulette-wheel');
        if (!wheel) {
            console.error('Элемент roulette-wheel не найден');
            return;
        }

        // Убираем предыдущие классы анимации
        wheel.classList.remove('spinning');

        // Получаем угол выпавшего сектора
        const targetAngle = resultData.angle || this.getAngleForNumber(resultData.number);
        const spins = 5; // Количество полных оборотов
        
        // Рассчитываем финальный угол
        const finalAngle = (360 * spins) + (360 - targetAngle);

        console.log('Угол вращения:', finalAngle);

        // Устанавливаем CSS переменную для анимации
        wheel.style.setProperty('--spin-degrees', `${finalAngle}deg`);

        // Запускаем анимацию
        setTimeout(() => {
            wheel.classList.add('spinning');
        }, 100);

        this.spinAngle = finalAngle % 360;
    }

    getAngleForNumber(number) {
        const angles = {
            1: 0, 2: 24, 3: 48, 4: 72, 0: 96,
            5: 120, 6: 144, 7: 168, 8: 192, 9: 216,
            10: 240, 11: 264, 12: 288, 13: 312, 14: 336
        };
        return angles[number] || 0;
    }

    showNotification(message, type = 'info') {
        console.log(`Уведомление [${type}]:`, message);
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 1rem 2rem;
            border-radius: 8px;
            font-weight: bold;
            z-index: 10000;
            animation: slideDown 0.3s ease;
        `;

        if (type === 'success') {
            notification.style.background = '#00ff88';
            notification.style.color = '#000';
        } else if (type === 'error') {
            notification.style.background = '#ff4757';
            notification.style.color = '#fff';
        } else {
            notification.style.background = '#ffd700';
            notification.style.color = '#000';
        }

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    highlightBet(color, amount) {
        console.log('Выделение ставки:', color, amount);
        
        // Убираем предыдущие выделения
        this.clearBetHighlight();
        
        // Выделяем выбранную ставку
        const colorBet = document.querySelector(`.color-bet[data-color="${color}"]`);
        if (colorBet) {
            colorBet.classList.add('selected');
            
            // Добавляем индикатор ставки
            const betIndicator = document.createElement('div');
            betIndicator.className = 'bet-indicator';
            betIndicator.textContent = amount;
            colorBet.appendChild(betIndicator);
        }
    }

    clearBetHighlight() {
        document.querySelectorAll('.color-bet').forEach(bet => {
            bet.classList.remove('selected');
            const indicator = bet.querySelector('.bet-indicator');
            if (indicator) {
                indicator.remove();
            }
        });
    }

    updateBalance() {
        const balanceElement = document.getElementById('balance');
        if (balanceElement) {
            balanceElement.textContent = this.userBalance;
        }
    }

    updateHistory(history) {
        const historyContainer = document.getElementById('history-list');
        if (!historyContainer || !history) return;

        historyContainer.innerHTML = '';
        
        history.slice(-10).forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = `history-item ${item.result}`;
            historyItem.innerHTML = `
                <span class="history-number">${item.number}</span>
            `;
            historyContainer.appendChild(historyItem);
        });
    }

    showGameResult(result, number) {
        const resultElement = document.createElement('div');
        resultElement.className = `game-result-popup ${result}`;
        resultElement.innerHTML = `
            <div class="result-content">
                <h3>Выпало: ${number}</h3>
                <div class="result-color-indicator ${result}"></div>
                <p>${this.getColorName(result).toUpperCase()}</p>
            </div>
        `;

        document.body.appendChild(resultElement);

        setTimeout(() => {
            resultElement.remove();
        }, 4000);
    }

    showWinningNumber(number, color) {
        const display = document.getElementById('winning-number');
        if (display) {
            const valueElement = display.querySelector('.winning-value');
            if (valueElement) {
                valueElement.textContent = number;
                valueElement.className = `winning-value ${color}`;
                display.style.display = 'block';
                
                setTimeout(() => {
                    display.style.display = 'none';
                }, 5000);
            }
        }
    }

    showWinModal(amount, number) {
        const modal = document.getElementById('win-modal');
        const winText = document.getElementById('win-text');
        if (modal && winText) {
            winText.textContent = `Поздравляем! Выпало ${number}! Вы выиграли ${amount} монет!`;
            modal.style.display = 'block';
        }
    }

    showLoseModal(number) {
        const modal = document.getElementById('lose-modal');
        const loseText = document.getElementById('lose-text');
        if (modal && loseText) {
            loseText.textContent = `Выпало ${number}. В этот раз не повезло, попробуйте снова!`;
            modal.style.display = 'block';
        }
    }

    createConfetti() {
        // Создаем конфетти для победы
        for (let i = 0; i < 50; i++) {
            const confetti = document.createElement('div');
            confetti.className = 'confetti';
            confetti.style.cssText = `
                position: fixed;
                width: 10px;
                height: 10px;
                background: ${['#ff4757', '#ffd700', '#00ff88'][Math.floor(Math.random() * 3)]};
                left: ${Math.random() * 100}vw;
                top: -10px;
                z-index: 10000;
                animation: confetti-fall ${2 + Math.random() * 3}s linear forwards;
            `;
            
            document.body.appendChild(confetti);
            
            setTimeout(() => {
                confetti.remove();
            }, 5000);
        }
    }

    getColorName(color) {
        const colorNames = {
            'red': 'красное',
            'black': 'черное',
            'green': 'зеленое'
        };
        return colorNames[color] || color;
    }

    displayCurrentBets(bets) {
        console.log('Отображение текущих ставок:', bets);
        // Можно добавить отображение текущих ставок если нужно
    }
}

// Инициализация игры при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Загрузка страницы завершена');
    
    // Добавляем CSS анимации
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from { transform: translate(-50%, -100%); opacity: 0; }
            to { transform: translate(-50%, 0); opacity: 1; }
        }
        
        @keyframes confetti-fall {
            0% { transform: translateY(0) rotate(0deg); opacity: 1; }
            100% { transform: translateY(100vh) rotate(360deg); opacity: 0; }
        }
        
        .bet-indicator {
            position: absolute;
            top: -10px;
            right: -10px;
            background: #ffd700;
            color: #000;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: bold;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .color-bet.selected {
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
            transform: scale(1.05);
        }
        
        .game-result-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.95);
            padding: 2rem;
            border-radius: 20px;
            text-align: center;
            z-index: 10000;
            animation: popIn 0.5s ease;
            border: 3px solid;
        }
        
        .game-result-popup.red { border-color: #ff4757; }
        .game-result-popup.black { border-color: #2f3542; }
        .game-result-popup.green { border-color: #00ff88; }
        
        .result-content h3 {
            margin: 0 0 1rem 0;
            font-size: 2rem;
            color: #fff;
        }
        
        .result-color-indicator {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            margin: 0 auto 1rem auto;
            border: 3px solid #fff;
        }
        
        .result-color-indicator.red { background: #ff4757; }
        .result-color-indicator.black { background: #2f3542; }
        .result-color-indicator.green { background: #00ff88; }
        
        .result-content p {
            margin: 0;
            font-size: 1.5rem;
            font-weight: bold;
            color: #ffd700;
        }
        
        @keyframes popIn {
            0% { transform: translate(-50%, -50%) scale(0.5); opacity: 0; }
            100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
    `;
    document.head.appendChild(style);

    // Проверяем наличие всех необходимых элементов
    const requiredElements = [
        'balance', 'bet-amount', 'game-phase', 'timer', 'roulette-wheel'
    ];
    
    const missingElements = requiredElements.filter(id => !document.getElementById(id));
    
    if (missingElements.length > 0) {
        console.error('❌ Отсутствуют элементы:', missingElements);
        alert('Ошибка: отсутствуют необходимые элементы на странице. Проверьте HTML.');
        return;
    }

    // Проверяем кнопки ставок
    const colorBets = document.querySelectorAll('.color-bet');
    if (colorBets.length === 0) {
        console.error('❌ Кнопки ставок не найдены');
        alert('Ошибка: кнопки ставок не найдены. Проверьте HTML.');
        return;
    }

    console.log('✅ Все элементы найдены, инициализируем игру...');

    // Инициализируем игру
    const game = new RouletteGame();
    
    // Делаем игру доступной глобально для отладки
    window.rouletteGame = game;
    
    console.log('✅ Рулетка инициализирована и готова к работе');
    
    // Проверяем подключение каждые 5 секунд
    setInterval(() => {
        if (game.socket.connected) {
            console.log('📡 Соединение активно');
        } else {
            console.log('❌ Соединение потеряно');
        }
    }, 5000);
});
