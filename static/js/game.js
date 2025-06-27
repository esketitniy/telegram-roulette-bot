class RouletteGame {
    constructor() {
        this.socket = io();
        this.userBalance = parseInt(document.getElementById('balance')?.textContent) || 1000;
        this.currentBet = null;
        this.spinAngle = 0;
        
        this.initializeEventListeners();
        this.initializeSocketListeners();
    }

    initializeEventListeners() {
        // Кнопки управления ставками
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = e.target.dataset.type;
                setBetAmount(type);
            });
        });

        // Кнопки цветных ставок
        document.querySelectorAll('.color-bet').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const color = e.target.dataset.color;
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
        this.socket.on('connect', () => {
            console.log('Подключено к серверу');
        });

        this.socket.on('disconnect', () => {
            console.log('Отключено от сервера');
        });

        this.socket.on('game_state', (data) => {
            this.handleGameState(data);
        });

        this.socket.on('phase_change', (data) => {
            this.handlePhaseChange(data);
        });

        this.socket.on('time_update', (data) => {
            this.updateTimer(data);
        });

        this.socket.on('bet_placed', (data) => {
            this.handleBetPlaced(data);
        });

        this.socket.on('game_result', (data) => {
            this.handleGameResult(data);
        });
    }

    handleGameState(data) {
        this.updateHistory(data.history);
        if (data.current_bets) {
            this.displayCurrentBets(data.current_bets);
        }
    }

    handlePhaseChange(data) {
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
            } else if (data.phase === 'spinning') {
                phaseElement.textContent = 'ВРАЩЕНИЕ РУЛЕТКИ';
                phaseElement.className = 'game-phase spinning';
                if (bettingPanel) {
                    bettingPanel.style.pointerEvents = 'none';
                    bettingPanel.style.opacity = '0.5';
                }
                // Запускаем анимацию рулетки
                if (data.result) {
                    this.spinRoulette(data.result);
                }
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
        this.showNotification(`${data.username} поставил ${data.amount} на ${this.getColorName(data.bet_type)}`);
        this.displayCurrentBets([data]);
    }

    handleGameResult(data) {
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
                } else {
                    this.showLoseModal(data.winning_number);
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

    spinRoulette(resultData) {
        const wheel = document.getElementById('roulette-wheel');
        if (!wheel) return;

        // Убираем предыдущие классы анимации
        wheel.classList.remove('spinning');

        // Получаем угол выпавшего сектора
        const targetAngle = resultData.angle || this.getAngleForNumber(resultData.number);
        const spins = 5; // Количество полных оборотов
        
        // Рассчитываем финальный угол (указатель находится сверху, поэтому компенсируем)
        const finalAngle = (360 * spins) + (360 - targetAngle) + Math.random() * 5 - 2.5;

        // Устанавливаем CSS переменную для анимации
        wheel.style.setProperty('--spin-degrees', `${finalAngle}deg`);

        // Запускаем анимацию
        setTimeout(() => {
            wheel.classList.add('spinning');
        }, 100);

        this.spinAngle = finalAngle % 360;
    }

    getAngleForNumber(number) {
        // Углы для каждого номера (соответствуют порядку в HTML)
        const angles = {
            1: 0, 2: 24, 3: 48, 4: 72, 0: 96,
            5: 120, 6: 144, 7: 168, 8: 192, 9: 216,
            10: 240, 11: 264, 12: 288, 13: 312, 14: 336
        };
        return angles[number] || 0;
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
        const valueElement = display ? display.querySelector('.winning-value') : null;
        
        if (display && valueElement) {
            valueElement.textContent = number;
            valueElement.className = `winning-value ${color}`;
            display.style.display = 'block';
            
            setTimeout(() => {
                display.style.display = 'none';
            }, 5000);
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

    placeBet(color) {
        const amount = parseInt(document.getElementById('bet-amount').textContent);
        
        if (amount > this.userBalance) {
            this.showNotification('Недостаточно средств!', 'error');
            return;
        }

        if (this.currentBet) {
            this.showNotification('Вы уже сделали ставку в этом раунде!', 'error');
            return;
        }

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
        .then(response => response.json())
        .then(data => {
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

    highlightBet(color, amount) {
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
                <span class="history-number">${item.number || item.result}</span>
            `;
            historyContainer.appendChild(historyItem);
        });
    }

    displayCurrentBets(bets) {
        const betsContainer = document.getElementById('current-bets');
        if (!betsContainer || !bets) return;

        // Очищаем предыдущие ставки
        betsContainer.innerHTML = '<h3>Текущие ставки:</h3>';
        
        bets.forEach(bet => {
            const betElement = document.createElement('div');
            betElement.className = 'current-bet-item';
            betElement.innerHTML = `
                <span class="bet-player">${bet.username}</span>
                <span class="bet-details">${bet.amount} на ${this.getColorName(bet.bet_type)}</span>
            `;
            betsContainer.appendChild(betElement);
        });
    }

    getColorName(color) {
        const colorNames = {
            'red': 'красное',
            'black': 'черное',
            'green': 'зеленое'
        };
        return colorNames[color] || color;
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        // Добавляем стили для уведомлений
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
}

// Функции управления ставками
function setBetAmount(type) {
    const betAmountElement = document.getElementById('bet-amount');
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
            const balance = parseInt(document.getElementById('balance').textContent);
            newAmount = balance;
            break;
    }

    betAmountElement.textContent = newAmount;
}

// Инициализация игры при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // CSS анимации для конфетти и уведомлений
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
        
        .current-bet-item {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem;
            margin: 0.5rem 0;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
        }
        
        .bet-player {
            font-weight: bold;
            color: #ffd700;
        }
        
        .bet-details {
            color: #ccc;
        }
        
        .history-item {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin: 0.25rem;
            font-weight: bold;
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }
        
        .history-item.red { background: #ff4757; }
        .history-item.black { background: #2f3542; }
        .history-item.green { background: #00ff88; color: #000; }
        
        .history-number {
            font-size: 0.9rem;
        }
        
        @media (max-width: 768px) {
            .game-result-popup {
                width: 90%;
                padding: 1.5rem;
            }
            
            .result-content h3 {
                font-size: 1.5rem;
            }
            
            .result-color-indicator {
                width: 50px;
                height: 50px;
            }
            
            .result-content p {
                font-size: 1.2rem;
            }
            
            .bet-indicator {
                width: 25px;
                height: 25px;
                font-size: 0.7rem;
            }
            
            .history-item {
                width: 35px;
                height: 35px;
                font-size: 0.8rem;
            }
        }
    `;
    document.head.appendChild(style);

    // Инициализируем игру
    const game = new RouletteGame();
    
    // Делаем игру доступной глобально для отладки
    window.rouletteGame = game;
    
    console.log('Рулетка инициализирована');
});

// Дополнительные утилиты
function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(num);
}

function getRandomColor() {
    const colors = ['#ff4757', '#ffd700', '#00ff88', '#3742fa', '#f1c40f'];
    return colors[Math.floor(Math.random() * colors.length)];
}

// Обработка ошибок WebSocket
window.addEventListener('error', function(event) {
    console.error('Ошибка приложения:', event.error);
});

// Обработка потери соединения
window.addEventListener('offline', function() {
    const game = window.rouletteGame;
    if (game) {
        game.showNotification('Соединение потеряно. Попробуйте обновить страницу.', 'error');
    }
});

window.addEventListener('online', function() {
    const game = window.rouletteGame;
    if (game) {
        game.showNotification('Соединение восстановлено', 'success');
    }
});

// Предотвращение двойных кликов
let lastClickTime = 0;
document.addEventListener('click', function(event) {
    const now = Date.now();
    if (now - lastClickTime < 300) { // 300мс защита от двойного клика
        if (event.target.classList.contains('color-bet') || 
            event.target.classList.contains('bet-btn')) {
            event.preventDefault();
            return false;
        }
    }
    lastClickTime = now;
});

// Автоматическое переподключение при потере соединения
function attemptReconnect() {
    const game = window.rouletteGame;
    if (game && game.socket.disconnected) {
        console.log('Попытка переподключения...');
        game.socket.connect();
        setTimeout(() => {
            if (game.socket.disconnected) {
                attemptReconnect();
            }
        }, 5000);
    }
}

// Проверка соединения каждые 30 секунд
setInterval(() => {
    const game = window.rouletteGame;
    if (game && game.socket.disconnected) {
        attemptReconnect();
    }
}, 30000);

// Функция для безопасного выполнения кода
function safeExecute(fn, context = null) {
    try {
        return fn.call(context);
    } catch (error) {
        console.error('Ошибка выполнения:', error);
        const game = window.rouletteGame;
        if (game) {
            game.showNotification('Произошла ошибка. Попробуйте еще раз.', 'error');
        }
        return null;
    }
}

// Экспорт для использования в других скриптах
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RouletteGame;
}
