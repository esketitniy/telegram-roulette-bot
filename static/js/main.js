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
        updateGameState(data);
    });
    
    socket.on('betting_time', function(data) {
        updateTimer(data.time_left);
    });
    
    socket.on('game_result', function(data) {
        showGameResult(data);
    });
    
    socket.on('history_update', function(data) {
        updateHistory(data.history);
    });
    
    socket.on('bet_placed', function(data) {
        updateUserBets(data);
    });
    
    socket.on('bet_error', function(data) {
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
    
    // Обработчики ставок
    const betOptions = document.querySelectorAll('.bet-option');
    betOptions.forEach(option => {
        option.addEventListener('click', function() {
            if (gameState !== 'betting' || this.classList.contains('disabled')) {
                return;
            }
            
            const betType = this.dataset.bet;
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
    
    socket.emit('place_bet', {
        type: type,
        amount: amount
    });
    
    // Добавляем визуальную обратную связь
    const betOption = document.querySelector(`[data-bet="${type}"]`);
    if (betOption) {
        betOption.style.transform = 'scale(0.95)';
        setTimeout(() => {
            betOption.style.transform = '';
        }, 150);
    }
}

// Обновление состояния игры
function updateGameState(data) {
    gameState = data.state;
    
    const statusElement = document.getElementById('game-status');
    const betOptions = document.querySelectorAll('.bet-option');
    
    switch (data.state) {
        case 'betting':
            if (statusElement) {
                statusElement.querySelector('.status-text').textContent = 'Делайте ваши ставки!';
            }
            betOptions.forEach(option => {
                option.classList.remove('disabled');
            });
            resetBets();
            break;
            
        case 'spinning':
            if (statusElement) {
                statusElement.querySelector('.status-text').textContent = 'Вращение рулетки...';
            }
            betOptions.forEach(option => {
                option.classList.add('disabled');
            });
            spinWheel(data.winning_number);
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
        timerCircle.style.background = `conic-gradient(#ff6b6b ${percentage}deg, transparent ${percentage}deg)`;
        
        // Изменяем цвет в зависимости от оставшегося времени
        if (timeLeft <= 5) {
            timerCircle.style.background = `conic-gradient(#e74c3c ${percentage}deg, transparent ${percentage}deg)`;
        } else if (timeLeft <= 10) {
            timerCircle.style.background = `conic-gradient(#f39c12 ${percentage}deg, transparent ${percentage}deg)`;
        }
    }
}

// Вращение рулетки
function spinWheel(winningNumber) {
    const wheel = document.querySelector('.wheel-inner');
    if (!wheel) return;
    
    // Вычисляем угол для выигрышного числа
    const segmentAngle = 360 / 37;
    const targetAngle = segmentAngle * winningNumber;
    
    // Добавляем несколько полных оборотов для эффекта
    const fullRotations = 5;
    const finalAngle = fullRotations * 360 + (360 - targetAngle);
    
    // Применяем анимацию
    wheel.style.transform = `rotate(${finalAngle}deg)`;
    
    // Звуковой эффект (если добавите аудио)
    playSpinSound();
}

// Показ результата игры
function showGameResult(data) {
    const { winning_number, winning_color } = data;
    
    // Обновляем статус
    const statusElement = document.getElementById('game-status');
    if (statusElement) {
        statusElement.querySelector('.status-text').innerHTML = 
            `Выпало: <span class="winning-number ${winning_color}">${winning_number}</span>`;
    }
    
    // Проверяем выигрыши пользователя
    checkUserWins(winning_color);
    
    // Добавляем число в историю
    addToHistory(winning_number, winning_color);
    
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
            
            // Анимация выигрышной ставки
            const betOption = document.querySelector(`[data-bet="${betType}"]`);
            if (betOption) {
                betOption.classList.add('winning');
                setTimeout(() => {
                    betOption.classList.remove('winning');
                }, 3000);
            }
        }
    });
    
    if (hasWin) {
        showWinAnimation(totalWin);
        updateBalance(totalWin);
    } else {
        showLoseAnimation();
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
        
        // Запуск конфетти
        startConfetti();
        
        // Звук выигрыша
        playWinSound();
        
        setTimeout(() => {
            winOverlay.classList.remove('show');
            stopConfetti();
        }, 3000);
    }
}

// Анимация проигрыша
function showLoseAnimation() {
    // Можно добавить анимацию проигрыша
    const betOptions = document.querySelectorAll('.bet-option');
    betOptions.forEach(option => {
        if (userBets[option.dataset.bet] > 0) {
            option.classList.add('losing');
            setTimeout(() => {
                option.classList.remove('losing');
            }, 1000);
        }
    });
    
    playLoseSound();
}

// Запуск эффекта конфетти
function startConfetti() {
    const confetti = document.getElementById('confetti');
    if (!confetti) return;
    
    const colors = ['#ffd700', '#ff6b6b', '#2ecc71', '#3498db', '#9b59b6'];
    const confettiCount = 50;
    
    for (let i = 0; i < confettiCount; i++) {
        setTimeout(() => {
            const piece = document.createElement('div');
            piece.className = 'confetti-piece';
            piece.style.left = Math.random() * 100 + '%';
            piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            piece.style.animationDelay = Math.random() * 2 + 's';
            confetti.appendChild(piece);
            
            setTimeout(() => {
                if (piece.parentNode) {
                    piece.parentNode.removeChild(piece);
                }
            }, 3000);
        }, i * 50);
    }
}

// Остановка конфетти
function stopConfetti() {
    const confetti = document.getElementById('confetti');
    if (confetti) {
        confetti.innerHTML = '';
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
    
    history.forEach((result, index) => {
        const numberElement = document.createElement('div');
        numberElement.className = `history-number ${result.color}`;
        numberElement.textContent = result.number;
        numberElement.style.animationDelay = `${index * 0.1}s`;
        historyContainer.appendChild(numberElement);
    });
}

// Добавление в историю
function addToHistory(number, color) {
    const historyContainer = document.getElementById('history-numbers');
    if (!historyContainer) return;
    
    // Создаем новый элемент
    const numberElement = document.createElement('div');
    numberElement.className = `history-number ${color}`;
    numberElement.textContent = number;
    
    // Добавляем в начало
    historyContainer.insertBefore(numberElement, historyContainer.firstChild);
    
    // Удаляем лишние элементы (оставляем только 10)
    while (historyContainer.children.length > 10) {
        historyContainer.removeChild(historyContainer.lastChild);
    }
}

// Обновление баланса
function updateBalance(amount) {
    const balanceElement = document.getElementById('user-balance');
    if (balanceElement) {
        const currentBalance = parseFloat(balanceElement.textContent);
        const newBalance = currentBalance + amount;
        balanceElement.textContent = newBalance.toFixed(2);
        
        // Анимация изменения баланса
        balanceElement.style.color = '#2ecc71';
        setTimeout(() => {
            balanceElement.style.color = '';
        }, 1000);
    }
}

// Показ ошибки
function showError(message) {
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
        errorElement.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (errorElement.parentNode) {
                errorElement.parentNode.removeChild(errorElement);
            }
        }, 300);
    }, 3000);
}

// Звуковые эффекты (заглушки - можно добавить реальные аудио файлы)
function playSpinSound() {
    // Здесь можно добавить воспроизведение звука вращения
    console.log('Playing spin sound');
}

function playWinSound() {
    // Здесь можно добавить воспроизведение звука выигрыша
    console.log('Playing win sound');
}

function playLoseSound() {
    // Здесь можно добавить воспроизведение звука проигрыша
    console.log('Playing lose sound');
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

@keyframes slideOutRight {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

.bet-option.winning {
    animation: winningPulse 0.5s ease-in-out 3;
    border-color: #ffd700 !important;
    box-shadow: 0 0 30px #ffd700 !important;
}

.bet-option.losing {
    animation: losingShake 0.5s ease-in-out;
    filter: grayscale(0.5);
}

@keyframes winningPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.1); }
}

@keyframes losingShake {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
    20%, 40%, 60%, 80% { transform: translateX(5px); }
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

// Обработка видимости страницы (для паузы при неактивной вкладке)
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Страница скрыта
        console.log('Page hidden');
    } else {
        // Страница активна
        console.log('Page visible');
        if (socket && !socket.connected) {
            socket.connect();
        }
    }
});

// Обработка потери соединения
function handleConnectionLoss() {
    showError('Соединение потеряно. Переподключение...');
    
    // Пытаемся переподключиться
    setTimeout(() => {
        if (socket) {
            socket.connect();
        }
    }, 2000);
}

// Обработка восстановления соединения
function handleReconnection() {
    const successElement = document.createElement('div');
    successElement.className = 'success-message';
    successElement.innerHTML = `<i class="fas fa-check-circle"></i> Соединение восстановлено`;
    
    successElement.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #2ecc71;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(46, 204, 113, 0.3);
        z-index: 10000;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(successElement);
    
    setTimeout(() => {
        successElement.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (successElement.parentNode) {
                successElement.parentNode.removeChild(successElement);
            }
        }, 300);
    }, 2000);
}

// Дополнительные обработчики событий WebSocket
function setupSocketListeners() {
    if (!socket) return;
    
    socket.on('connect_error', handleConnectionLoss);
    socket.on('disconnect', handleConnectionLoss);
    socket.on('reconnect', handleReconnection);
}

// Установка обработчиков событий
function setupEventListeners() {
    // Обработка кликов вне модальных окон
    document.addEventListener('click', function(e) {
        const winOverlay = document.getElementById('win-overlay');
        if (winOverlay && e.target === winOverlay) {
            winOverlay.classList.remove('show');
            stopConfetti();
        }
    });
    
    // Обработка клавиш
    document.addEventListener('keydown', function(e) {
        // ESC для закрытия модальных окон
        if (e.key === 'Escape') {
            const winOverlay = document.getElementById('win-overlay');
            if (winOverlay && winOverlay.classList.contains('show')) {
                winOverlay.classList.remove('show');
                stopConfetti();
            }
        }
        
        // Горячие клавиши для ставок (только в режиме ставок)
        if (gameState === 'betting') {
            switch(e.key) {
                case '1':
                    placeBet('red', currentBetAmount);
                    break;
                case '2':
                    placeBet('black', currentBetAmount);
                    break;
                case '3':
                    placeBet('green', currentBetAmount);
                    break;
            }
        }
    });
    
    // Обработка свайпов для мобильных устройств
    let touchStartX = 0;
    let touchStartY = 0;
    
    document.addEventListener('touchstart', function(e) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    });
    
    document.addEventListener('touchend', function(e) {
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        
        const deltaX = touchEndX - touchStartX;
        const deltaY = touchEndY - touchStartY;
        
        // Проверяем, что это горизонтальный свайп
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
            // Свайп влево/вправо по истории
            const historyContainer = document.getElementById('history-numbers');
            if (historyContainer && historyContainer.contains(e.target)) {
                if (deltaX > 0) {
                    // Свайп вправо - можно добавить функционал
                    console.log('Swipe right on history');
                } else {
                    // Свайп влево - можно добавить функционал
                    console.log('Swipe left on history');
                }
            }
        }
    });
}

// Функция для обновления UI при изменении размера экрана
function handleResize() {
    const isMobile = window.innerWidth <= 768;
    
    // Адаптация рулетки под размер экрана
    const rouletteWheel = document.querySelector('.roulette-wheel');
    if (rouletteWheel) {
        if (isMobile) {
            rouletteWheel.style.width = '200px';
            rouletteWheel.style.height = '200px';
        } else {
            rouletteWheel.style.width = '300px';
            rouletteWheel.style.height = '300px';
        }
    }
    
    // Адаптация таймера
    const timerCircle = document.querySelector('.timer-circle');
    if (timerCircle) {
        if (isMobile) {
            timerCircle.style.width = '60px';
            timerCircle.style.height = '60px';
        } else {
            timerCircle.style.width = '80px';
            timerCircle.style.height = '80px';
        }
    }
}

// Добавляем обработчик изменения размера окна
window.addEventListener('resize', handleResize);

// Функция для сохранения состояния в localStorage
function saveGameState() {
    const gameData = {
        currentBetAmount: currentBetAmount,
        userBets: userBets,
        timestamp: Date.now()
    };
    
    localStorage.setItem('rouletteGameState', JSON.stringify(gameData));
}

// Функция для восстановления состояния из localStorage
function restoreGameState() {
    const savedData = localStorage.getItem('rouletteGameState');
    if (savedData) {
        try {
            const gameData = JSON.parse(savedData);
            
            // Проверяем, что данные не слишком старые (максимум 1 час)
            if (Date.now() - gameData.timestamp < 3600000) {
                currentBetAmount = gameData.currentBetAmount || 10;
                
                // Обновляем активную кнопку суммы
                const amountButtons = document.querySelectorAll('.amount-btn');
                amountButtons.forEach(btn => {
                    btn.classList.toggle('active', 
                        parseInt(btn.dataset.amount) === currentBetAmount);
                });
            }
        } catch (error) {
            console.error('Error restoring game state:', error);
        }
    }
}

// Сохраняем состояние при изменениях
function setupStateSaving() {
    // Сохраняем при изменении суммы ставки
    const amountButtons = document.querySelectorAll('.amount-btn');
    amountButtons.forEach(btn => {
        btn.addEventListener('click', saveGameState);
    });
    
    const customAmountInput = document.getElementById('custom-amount');
    if (customAmountInput) {
        customAmountInput.addEventListener('input', saveGameState);
    }
    
    // Сохраняем при размещении ставок
    window.addEventListener('beforeunload', saveGameState);
}

// Инициализация дополнительных функций
document.addEventListener('DOMContentLoaded', function() {
    if (typeof userId !== 'undefined') {
        restoreGameState();
        setupStateSaving();
        handleResize();
    }
});

// Функция для показа подсказок для новых пользователей
function showTutorial() {
    const isFirstVisit = !localStorage.getItem('rouletteTutorialShown');
    
    if (isFirstVisit) {
        const tutorialSteps = [
            {
                element: '.bet-amount-selector',
                text: 'Выберите сумму ставки'
            },
            {
                element: '.betting-options',
                text: 'Нажмите на цвет для размещения ставки'
            },
            {
                element: '.timer-circle',
                text: 'Следите за таймером - у вас есть 25 секунд на ставки'
            },
            {
                element: '.history-numbers',
                text: 'Здесь отображаются последние результаты'
            }
        ];
        
        showTutorialStep(tutorialSteps, 0);
        localStorage.setItem('rouletteTutorialShown', 'true');
    }
}

function showTutorialStep(steps, currentStep) {
    if (currentStep >= steps.length) return;
    
    const step = steps[currentStep];
    const element = document.querySelector(step.element);
    
    if (!element) {
        showTutorialStep(steps, currentStep + 1);
        return;
    }
    
    const tooltip = document.createElement('div');
    tooltip.className = 'tutorial-tooltip';
    tooltip.innerHTML = `
        <div class="tooltip-content">
            <p>${step.text}</p>
            <div class="tooltip-controls">
                <button onclick="closeTutorial()">Пропустить</button>
                <button onclick="nextTutorialStep(${currentStep + 1})">
                    ${currentStep < steps.length - 1 ? 'Далее' : 'Понятно'}
                </button>
            </div>
        </div>
        <div class="tooltip-arrow"></div>
    `;
    
    // Позиционируем подсказку
    const rect = element.getBoundingClientRect();
    tooltip.style.cssText = `
        position: fixed;
        top: ${rect.bottom + 10}px;
        left: ${rect.left + rect.width / 2}px;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        z-index: 10001;
        max-width: 300px;
        animation: fadeIn 0.3s ease;
    `;
    
    document.body.appendChild(tooltip);
    
    // Подсвечиваем элемент
    element.style.boxShadow = '0 0 20px #ffd700';
    element.style.position = 'relative';
    element.style.zIndex = '10000';
    
    window.currentTutorialTooltip = tooltip;
    window.currentTutorialElement = element;
    window.tutorialSteps = steps;
}

function nextTutorialStep(step) {
    closeTutorialTooltip();
    showTutorialStep(window.tutorialSteps, step);
}

function closeTutorial() {
    closeTutorialTooltip();
}

function closeTutorialTooltip() {
    if (window.currentTutorialTooltip) {
        window.currentTutorialTooltip.remove();
    }
    if (window.currentTutorialElement) {
        window.currentTutorialElement.style.boxShadow = '';
        window.currentTutorialElement.style.zIndex = '';
    }
}

// Показываем туториал для новых пользователей
setTimeout(showTutorial, 2000);
