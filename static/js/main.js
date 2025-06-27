// Глобальные переменные
let socket;
let currentBetAmount = 10;
let gameState = 'betting';
let userBets = { red: 0, black: 0, green: 0 };
let spinTimeout;
let timerInterval;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (typeof userId !== 'undefined') {
        initializeSocket();
        initializeBetting();
        setupEventListeners();
    }
});

// Инициализация WebSocket
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Подключено к серверу');
    });
    
    socket.on('disconnect', function() {
        console.log('Отключено от сервера');
    });
    
    socket.on('game_state', function(data) {
        console.log('Game state received:', data);
        updateGameState(data);
    });
    
    socket.on('betting_time', function(data) {
        console.log('Betting time:', data.time_left);
        updateTimer(data.time_left);
    });
    
    socket.on('game_result', function(data) {
        console.log('Game result:', data);
        showGameResult(data);
    });
    
    socket.on('history_update', function(data) {
        updateHistory(data.history);
    });
    
    socket.on('bet_placed', function(data) {
        console.log('Bet placed:', data);
        updateUserBets(data);
    });
    
    socket.on('bet_error', function(data) {
        console.log('Bet error:', data);
        showError(data.message);
    });
}

// Инициализация ставок
function initializeBetting() {
    // Выбор суммы ставки
    const amountButtons = document.querySelectorAll('.amount-btn');
    amountButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            amountButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentBetAmount = parseInt(this.dataset.amount);
            
            // Очищаем кастомное поле
            const customInput = document.getElementById('custom-amount');
            if (customInput) customInput.value = '';
        });
    });
    
    // Активация первой кнопки по умолчанию
    if (amountButtons.length > 0) {
        amountButtons[0].classList.add('active');
    }
    
    // Кастомная сумма
    const customAmountInput = document.getElementById('custom-amount');
    if (customAmountInput) {
        customAmountInput.addEventListener('input', function() {
            const value = parseInt(this.value);
            if (value && value > 0) {
                currentBetAmount = value;
                // Убираем активность с кнопок
                amountButtons.forEach(b => b.classList.remove('active'));
            }
        });
    }
    
    // Обработчики ставок через кнопки BET
    const betButtons = document.querySelectorAll('.bet-btn');
    betButtons.forEach(button => {
        button.addEventListener('click', function() {
            const betType = this.dataset.bet;
            if (gameState !== 'betting' || this.disabled) {
                return;
            }
            placeBet(betType, currentBetAmount);
        });
    });
}

// Размещение ставки
function placeBet(type, amount) {
    if (!socket || gameState !== 'betting') {
        showError('Ставки не принимаются');
        return;
    }
    
    console.log('Placing bet:', type, amount);
    
    socket.emit('place_bet', {
        type: type,
        amount: amount
    });
    
    // Добавляем визуальную обратную связь
    const betButton = document.querySelector(`[data-bet="${type}"].bet-btn`);
    if (betButton) {
        betButton.style.transform = 'scale(0.95)';
        setTimeout(() => {
            betButton.style.transform = '';
        }, 150);
    }
}

// Обновление состояния игры
function updateGameState(data) {
    gameState = data.state;
    console.log('Game state updated to:', gameState);
    
    const statusElement = document.getElementById('game-status');
    const betButtons = document.querySelectorAll('.bet-btn');
    
    switch (data.state) {
        case 'betting':
            if (statusElement) {
                statusElement.querySelector('.status-text').textContent = 'Делайте ваши ставки!';
            }
            betButtons.forEach(button => {
                button.disabled = false;
                button.textContent = 'BET';
            });
            resetBets();
            break;
            
        case 'spinning':
            if (statusElement) {
                statusElement.querySelector('.status-text').textContent = 'Вращение рулетки...';
            }
            betButtons.forEach(button => {
                button.disabled = true;
                button.textContent = 'WAIT';
            });
            if (data.winning_number !== undefined) {
                spinWheel(data.winning_number);
            }
            break;
    }
}

// Обновление таймера
function updateTimer(timeLeft) {
    const timerValue = document.getElementById('timer-value');
    const timerCircle = document.querySelector('.timer-circle');
    
    if (timerValue) {
        timerValue.textContent = timeLeft;
    }
    
    if (timerCircle) {
        const percentage = (timeLeft / 25) * 360;
        
        // Изменяем цвет в зависимости от оставшегося времени
        let color = '#2ecc71'; // зеленый
        if (timeLeft <= 5) {
            color = '#e74c3c'; // красный
        } else if (timeLeft <= 10) {
            color = '#f39c12'; // оранжевый
        }
        
        timerCircle.style.background = `conic-gradient(${color} ${percentage}deg, transparent ${percentage}deg)`;
    }
}

// Вращение рулетки
function spinWheel(winningNumber) {
    const wheel = document.querySelector('.wheel-inner');
    if (!wheel) {
        console.log('Wheel element not found');
        return;
    }
    
    console.log('Spinning wheel to number:', winningNumber);
    
    // Сбрасываем предыдущие повороты
    wheel.style.transition = 'none';
    wheel.style.transform = 'rotate(0deg)';
    
    // Небольшая задержка для применения сброса
    setTimeout(() => {
        // Вычисляем угол для выигрышного числа
        const segmentAngle = 360 / 37;
        const targetAngle = segmentAngle * winningNumber;
        
        // Добавляем несколько полных оборотов для эффекта
        const fullRotations = 5;
        const finalAngle = fullRotations * 360 + (360 - targetAngle);
        
        // Применяем анимацию
        wheel.style.transition = 'transform 5s cubic-bezier(0.25, 0.1, 0.25, 1)';
        wheel.style.transform = `rotate(${finalAngle}deg)`;
        
        console.log('Wheel spinning to angle:', finalAngle);
    }, 100);
}

// Показ результата игры
function showGameResult(data) {
    const { winning_number, winning_color } = data;
    
    console.log('Showing game result:', winning_number, winning_color);
    
    // Обновляем статус
    const statusElement = document.getElementById('game-status');
    if (statusElement) {
        statusElement.querySelector('.status-text').innerHTML = 
            `Выпало: <span class="winning-number ${winning_color}">${winning_number}</span>`;
    }
    
    // Проверяем выигрыши пользователя
    checkUserWins(winning_color);
    
    setTimeout(() => {
        gameState = 'betting';
    }, 3000);
}

// Проверка выигрышей пользователя
function checkUserWins(winningColor) {
    let totalWin = 0;
    let hasWin = false;
    
    Object.keys(userBets).forEach(betType => {
        if (userBets[betType] > 0 && betType === winningColor) {
            const multiplier = getMultiplier(betType);
            const winAmount = userBets[betType] * multiplier;
            totalWin += winAmount;
            hasWin = true;
        }
    });
    
    if (hasWin) {
        showWinAnimation(totalWin);
        updateBalance(totalWin);
    }
}

// Получение множителя для типа ставки
function getMultiplier(betType) {
    const multipliers = {
        'red': 2,
        'black': 2,
        'green': 35
    };
    return multipliers[betType] || 1;
}

// Анимация выигрыша
function showWinAnimation(amount) {
    const winOverlay = document.getElementById('win-overlay');
    const winAmountElement = document.getElementById('win-amount');
    
    if (winOverlay && winAmountElement) {
        winAmountElement.textContent = `+${amount.toFixed(2)}₽`;
        winOverlay.classList.add('show');
        
        setTimeout(() => {
            winOverlay.classList.remove('show');
        }, 3000);
    }
}

// Обновление пользовательских ставок
function updateUserBets(data) {
    userBets[data.type] += data.amount;
    
    // Обновляем отображение ставок
    const totalElement = document.getElementById(`${data.type}-total`);
    if (totalElement) {
        totalElement.textContent = `${userBets[data.type].toFixed(2)}₽`;
    }
    
    // Обновляем баланс
    const balanceElement = document.getElementById('user-balance');
    if (balanceElement) {
        balanceElement.textContent = data.balance.toFixed(2);
    }
}

// Сброс ставок
function resetBets() {
    userBets = { red: 0, black: 0, green: 0 };
    
    // Обновляем отображение
    Object.keys(userBets).forEach(type => {
        const totalElement = document.getElementById(`${type}-total`);
        if (totalElement) {
            totalElement.textContent = '0₽';
        }
    });
}

// Обновление истории
function updateHistory(history) {
    const historyContainer = document.getElementById('history-numbers');
    if (!historyContainer) return;
    
    historyContainer.innerHTML = '';
    
    history.forEach(result => {
        const numberElement = document.createElement('div');
        numberElement.className = `history-number ${result.color}`;
        numberElement.textContent = result.number;
        historyContainer.appendChild(numberElement);
    });
}

// Обновление баланса
function updateBalance(amount) {
    const balanceElement = document.getElementById('user-balance');
    if (balanceElement) {
        const currentBalance = parseFloat(balanceElement.textContent);
        const newBalance = currentBalance + amount;
        balanceElement.textContent = newBalance.toFixed(2);
    }
}

// Показ ошибки
function showError(message) {
    console.error('Error:', message);
    
    // Создаем элемент ошибки
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    
    // Добавляем стили
    errorElement.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #e74c3c;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
        z-index: 10000;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(errorElement);
    
    // Удаляем через 3 секунды
    setTimeout(() => {
        if (errorElement.parentNode) {
            errorElement.parentNode.removeChild(errorElement);
        }
    }, 3000);
}

// Установка обработчиков событий
function setupEventListeners() {
    // Обработка кликов вне модальных окон
    document.addEventListener('click', function(e) {
        const winOverlay = document.getElementById('win-overlay');
        if (winOverlay && e.target === winOverlay) {
            winOverlay.classList.remove('show');
        }
    });
}

// Дополнительные анимации CSS
const additionalStyles = `
@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.winning-number {
    font-weight: bold;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}

.winning-number.red {
    background: #ff6b6b;
    color: white;
}

.winning-number.black {
    background: #2c3e50;
    color: white;
}

.winning-number.green {
    background: #2ecc71;
    color: white;
}

.error-message {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
`;

// Добавляем дополнительные стили
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);
