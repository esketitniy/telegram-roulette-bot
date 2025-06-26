// Глобальные переменные
let socket = null;
let gameState = {
    status: 'waiting',
    timeLeft: 0,
    roundNumber: 1
};
let selectedBet = null;
let isSpinning = false;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    initializeRouletteWheel();
    initializeBettingPanel();
    initializeQuickAmounts();
});

// Инициализация WebSocket соединения
function initializeSocket() {
    if (typeof io === 'undefined') return;
    
    socket = io();
    
    socket.on('connect', function() {
        console.log('Подключен к серверу');
    });
    
    socket.on('disconnect', function() {
        console.log('Отключен от сервера');
    });
    
    socket.on('game_state', function(data) {
        updateGameState(data);
    });
    
    socket.on('new_round', function(data) {
        startNewRound(data);
    });
    
    socket.on('timer_update', function(data) {
        updateTimer(data.time_left, data.status);
    });
    
    socket.on('spin_start', function(data) {
        startWheelSpin(data.winning_number, data.time);
    });
    
    socket.on('round_finished', function(data) {
        finishRound(data);
    });
    
    socket.on('bet_placed', function(data) {
        addBetToList(data);
    });
}

// Инициализация колеса рулетки
function initializeRouletteWheel() {
    const wheelNumbers = document.querySelector('.wheel-numbers');
    if (!wheelNumbers) return;
    
    // Числа европейской рулетки в правильном порядке
    const numbers = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
        24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
    ];
    
    const colors = {
        0: 'green',
        1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black',
        7: 'red', 8: 'black', 9: 'red', 10: 'black', 11: 'black', 12: 'red',
        13: 'black', 14: 'red', 15: 'black', 16: 'red', 17: 'black', 18: 'red',
        19: 'red', 20: 'black', 21: 'red', 22: 'black', 23: 'red', 24: 'black',
        25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red',
        31: 'black', 32: 'red', 33: 'black', 34: 'red', 35: 'black', 36: 'red'
    };
    
    numbers.forEach((number, index) => {
        const numberElement = document.createElement('div');
        numberElement.className = `wheel-number ${colors[number]}`;
        numberElement.textContent = number;
        
        // Позиционирование числа по кругу
        const angle = (360 / numbers.length) * index;
        const radius = 160;
        const x = Math.cos((angle - 90) * Math.PI / 180) * radius;
        const y = Math.sin((angle - 90) * Math.PI / 180) * radius;
        
        numberElement.style.left = `calc(50% + ${x}px - 15px)`;
        numberElement.style.top = `calc(50% + ${y}px - 15px)`;
        numberElement.style.backgroundColor = colors[number] === 'red' ? '#e74c3c' : 
                                           colors[number] === 'black' ? '#2c3e50' : '#27ae60';
        
        wheelNumbers.appendChild(numberElement);
    });
}

// Инициализация панели ставок
function initializeBettingPanel() {
    const betOptions = document.querySelectorAll('.bet-option');
    const placeBetBtn = document.getElementById('place-bet-btn');
    const betAmountInput = document.getElementById('bet-amount');
    
    betOptions.forEach(option => {
        option.addEventListener('click', function() {
            betOptions.forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');
            selectedBet = this.dataset.bet;
            updatePlaceBetButton();
        });
    });
    
    if (betAmountInput) {
        betAmountInput.addEventListener('input', updatePlaceBetButton);
    }
    
    if (placeBetBtn) {
        placeBetBtn.addEventListener('click', placeBet);
    }
}

// Инициализация быстрых сумм
function initializeQuickAmounts() {
    const quickBets = document.querySelectorAll('.quick-bet');
    const betAmountInput = document.getElementById('bet-amount');
    
    quickBets.forEach(btn => {
        btn.addEventListener('click', function() {
            const amount = this.dataset.amount;
            if (betAmountInput) {
                betAmountInput.value = amount;
                updatePlaceBetButton();
            }
        });
    });
}

// Обновление состояния игры
function updateGameState(state) {
    gameState = state;
    updateTimer(state.time_left, state.status);
    
    const roundNumber = document.getElementById('round-number');
    if (roundNumber) {
        roundNumber.textContent = state.round_number;
    }
}

// Начало нового раунда
function startNewRound(data) {
    const roundNumber = document.getElementById('round-number');
    const currentBetsList = document.getElementById('current-bets-list');
    const winningDisplay = document.getElementById('winning-display');
    
    if (roundNumber) {
        roundNumber.textContent = data.round_number;
    }
    
    if (currentBetsList) {
        currentBetsList.innerHTML = '';
    }
    
    if (winningDisplay) {
        winningDisplay.style.display = 'none';
    }
    
    // Сброс выбранной ставки
    document.querySelectorAll('.bet-option').forEach(opt => {
        opt.classList.remove('selected');
    });
    selectedBet = null;
    updatePlaceBetButton();
    
    isSpinning = false;
}

// Обновление таймера
function updateTimer(timeLeft, status) {
    const timerText = document.getElementById('timer-text');
    const timerStatus = document.getElementById('timer-status');
    const placeBetBtn = document.getElementById('place-bet-btn');
    
    if (timerText) {
        timerText.textContent = timeLeft;
    }
    
    if (timerStatus) {
        if (status === 'betting') {
            timerStatus.textContent = 'Делайте ставки';
            timerStatus.style.color = '#ffd700';
        } else if (status === 'spinning') {
            timerStatus.textContent = 'Рулетка крутится';
            timerStatus.style.color = '#ff6b35';
        }
    }
    
    // Управление кнопкой ставки
    if (placeBetBtn) {
        if (status === 'betting' && timeLeft > 0) {
            placeBetBtn.disabled = false;
        } else {
            placeBetBtn.disabled = true;
        }
    }
    
    gameState.status = status;
    gameState.timeLeft = timeLeft;
}

// Запуск вращения колеса
function startWheelSpin(winningNumber, duration) {
    const wheel = document.getElementById('roulette-wheel');
    if (!wheel || isSpinning) return;
    
    isSpinning = true;
    
    // Убираем предыдущие классы анимации
    wheel.classList.remove('roulette-spinning');
    
    // Вычисляем угол для остановки на выигрышном числе
    const numbers = [
        0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
        24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
    ];
    
    const numberIndex = numbers.indexOf(winningNumber);
    const segmentAngle = 360 / numbers.length;
    const targetAngle = numberIndex * segmentAngle;
    
    // Добавляем несколько полных оборотов + точный угол
    const totalRotation = 1800 + (360 - targetAngle);
    
    // Применяем анимацию
    wheel.style.transform = `rotate(${totalRotation}deg)`;
    wheel.style.transition = `transform ${duration}s cubic-bezier(0.23, 1, 0.32, 1)`;
    
    // Добавляем класс для дополнительных эффектов
    wheel.classList.add('roulette-spinning');
}

// Завершение раунда
function finishRound(data) {
    const winningDisplay = document.getElementById('winning-display');
    const winningNumber = document.getElementById('winning-number');
    const winningColor = document.getElementById('winning-color');
    const numbersHistory = document.getElementById('numbers-history');
    
    // Показываем выигрышное число
    if (winningDisplay && winningNumber && winningColor) {
        winningNumber.textContent = data.winning_number;
        winningNumber.parentElement.className = `winning-circle ${data.winning_color}`;
        
        const colorNames = {
            'red': 'Красное',
            'black': 'Чёрное',
            'green': 'Зелёное'
        };
        winningColor.textContent = colorNames[data.winning_color];
        
        winningDisplay.style.display = 'block';
    }
    
    // Добавляем число в историю
    if (numbersHistory) {
        const historyNumber = document.createElement('div');
        historyNumber.className = `history-number ${data.winning_color}`;
        historyNumber.textContent = data.winning_number;
        
        numbersHistory.insertBefore(historyNumber, numbersHistory.firstChild);
        
        // Оставляем только последние 10 чисел
        while (numbersHistory.children.length > 10) {
            numbersHistory.removeChild(numbersHistory.lastChild);
        }
    }
    
    // Обновляем баланс пользователя
    updateUserBalance();
    
    isSpinning = false;
}

// Размещение ставки
function placeBet() {
    if (!selectedBet || gameState.status !== 'betting') {
        return;
    }
    
    const betAmount = document.getElementById('bet-amount').value;
    if (!betAmount || betAmount <= 0) {
        alert('Введите корректную сумму ставки');
        return;
    }
    
    // Отправляем ставку на сервер
    fetch('/api/place_bet', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            bet_type: selectedBet,
            amount: parseFloat(betAmount)
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Обновляем баланс
            updateBalance(data.new_balance);
            
            // Показываем успешное размещение ставки
            showNotification('Ставка размещена!', 'success');
            
            // Сбрасываем выбор
            document.querySelectorAll('.bet-option').forEach(opt => {
                opt.classList.remove('selected');
            });
            selectedBet = null;
            updatePlaceBetButton();
        } else {
            showNotification(data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Ошибка при размещении ставки:', error);
        showNotification('Ошибка при размещении ставки', 'error');
    });
}

// Обновление кнопки размещения ставки
function updatePlaceBetButton() {
    const placeBetBtn = document.getElementById('place-bet-btn');
    const betAmount = document.getElementById('bet-amount');
    
    if (placeBetBtn && betAmount) {
        const isValid = selectedBet && 
                       betAmount.value && 
                       parseFloat(betAmount.value) > 0 && 
                       gameState.status === 'betting';
        
        placeBetBtn.disabled = !isValid;
        
        if (selectedBet && betAmount.value) {
            const multipliers = {'red': 2, 'black': 2, 'green': 36};
            const potentialWin = parseFloat(betAmount.value) * multipliers[selectedBet];
            placeBetBtn.textContent = `Поставить ${betAmount.value}₽ (выигрыш: ${potentialWin}₽)`;
        } else {
            placeBetBtn.textContent = 'Сделать ставку';
        }
    }
}

// Добавление ставки в список
function addBetToList(betData) {
    const currentBetsList = document.getElementById('current-bets-list');
    if (!currentBetsList) return;
    
    const betItem = document.createElement('div');
    betItem.className = 'bet-item';
    
    const colorNames = {
        'red': 'Красное',
        'black': 'Чёрное',
        'green': 'Зелёное'
    };
    
    betItem.innerHTML = `
        <div>
            <strong>${betData.username}</strong>
        </div>
        <div>
            <span class="bet-type ${betData.bet_type}">${colorNames[betData.bet_type]}</span>
        </div>
        <div>
            <strong>${betData.amount}₽</strong>
        </div>
    `;
    
    currentBetsList.insertBefore(betItem, currentBetsList.firstChild);
    
    // Анимация появления
    betItem.style.opacity = '0';
    betItem.style.transform = 'translateX(-20px)';
    
    setTimeout(() => {
        betItem.style.transition = 'all 0.3s ease';
        betItem.style.opacity = '1';
        betItem.style.transform = 'translateX(0)';
    }, 10);
}

// Обновление баланса пользователя
function updateBalance(newBalance) {
    const balanceElement = document.getElementById('user-balance');
    if (balanceElement) {
        // Анимация изменения баланса
        balanceElement.style.transform = 'scale(1.2)';
        balanceElement.style.color = '#ffd700';
        
        setTimeout(() => {
            balanceElement.textContent = newBalance.toFixed(2);
            balanceElement.style.transform = 'scale(1)';
            balanceElement.style.color = '';
        }, 200);
    }
}

// Обновление баланса с сервера
function updateUserBalance() {
    fetch('/api/user_balance')
        .then(response => response.json())
        .then(data => {
            if (data.balance !== undefined) {
                updateBalance(data.balance);
            }
        })
        .catch(error => {
            console.error('Ошибка получения баланса:', error);
        });
}

// Показ уведомлений
function showNotification(message, type = 'info') {
    // Создаём элемент уведомления
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    // Стили для уведомления
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        padding: 1rem 2rem;
        border-radius: 8px;
        color: white;
        font-weight: bold;
        z-index: 10000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    `;
    
    // Цвета в зависимости от типа
    if (type === 'success') {
        notification.style.background = '#28a745';
    } else if (type === 'error') {
        notification.style.background = '#dc3545';
    } else {
        notification.style.background = '#ff6b35';
    }
    
    document.body.appendChild(notification);
    
    // Анимация появления
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 10);
    
    // Удаление через 3 секунды
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Дополнительные утилиты
function formatCurrency(amount) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2
    }).format(amount);
}

// Обработка звуков (если нужно)
function playSound(soundType) {
    // Можно добавить звуковые эффекты
    // const audio = new Audio(`/static/sounds/${soundType}.mp3`);
    // audio.play().catch(e => console.log('Не удалось воспроизвести звук'));
}

// Обработка видимости страницы
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible' && socket) {
        // Переподключение при возвращении на страницу
        if (!socket.connected) {
            socket.connect();
        }
    }
});

// Обработка потери соединения
if (socket) {
    socket.on('reconnect', function() {
        showNotification('Соединение восстановлено', 'success');
        // Обновляем состояние игры
        updateUserBalance();
    });
    
    socket.on('disconnect', function() {
        showNotification('Соединение потеряно', 'error');
    });
}
