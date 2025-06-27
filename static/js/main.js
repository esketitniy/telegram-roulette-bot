class RouletteGame {
    constructor() {
        this.socket = io();
        this.gameState = { status: 'waiting', time_left: 0 };
        this.userBalance = 0;
        this.currentBets = {};
        this.recentResults = [];
        this.isSpinning = false;
        
        this.init();
        this.loadRecentResults();
        this.loadPlayerStats();
        this.updateBalance();
    }

    init() {
        this.bindEvents();
        this.setupSocketEvents();
        this.createRouletteWheel();
    }

    // Создание колеса рулетки с правильными углами
    createRouletteWheel() {
        const wheel = document.querySelector('.roulette-wheel');
        if (!wheel) return;

        // Числа в правильном порядке европейской рулетки
        const numbers = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];

        // Цвета для чисел
        const colors = {
            0: 'green',
            1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black',
            7: 'red', 8: 'black', 9: 'red', 10: 'black', 11: 'black', 12: 'red',
            13: 'black', 14: 'red', 15: 'black', 16: 'red', 17: 'black', 18: 'red',
            19: 'red', 20: 'black', 21: 'red', 22: 'black', 23: 'red', 24: 'black',
            25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red',
            31: 'black', 32: 'red', 33: 'black', 34: 'red', 35: 'black', 36: 'red'
        };

        // Очищаем колесо
        wheel.innerHTML = '';

        // Угол для каждого сектора
        const sectorAngle = 360 / numbers.length;

        numbers.forEach((number, index) => {
            const sector = document.createElement('div');
            sector.className = `sector sector-${colors[number]}`;
            sector.setAttribute('data-number', number);
            
            const rotation = index * sectorAngle;
            sector.style.transform = `rotate(${rotation}deg)`;
            
            const numberSpan = document.createElement('span');
            numberSpan.textContent = number;
            numberSpan.style.transform = `rotate(${-rotation}deg)`;
            
            sector.appendChild(numberSpan);
            wheel.appendChild(sector);
        });
    }

    // Вычисление угла поворота для определенного числа
    calculateAngleForNumber(targetNumber) {
        const numbers = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];
        
        const index = numbers.indexOf(targetNumber);
        if (index === -1) return 0;
        
        const sectorAngle = 360 / numbers.length;
        // Добавляем случайный поворот в пределах сектора для реалистичности
        const randomOffset = (Math.random() - 0.5) * (sectorAngle * 0.8);
        // Инвертируем угол для правильного направления
        const targetAngle = -(index * sectorAngle) + randomOffset;
        
        // Добавляем несколько полных оборотов для эффектности
        const fullRotations = 5 + Math.random() * 3; // 5-8 оборотов
        return targetAngle + (fullRotations * 360);
    }

    bindEvents() {
        // Кнопки ставок
        document.querySelectorAll('.bet-button').forEach(button => {
            button.addEventListener('click', (e) => {
                const betType = e.target.getAttribute('data-bet');
                this.showBetModal(betType);
            });
        });

        // Модальное окно ставки
        const modal = document.getElementById('betModal');
        const closeBtn = modal?.querySelector('.close');
        const confirmBtn = document.getElementById('confirmBet');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeBetModal());
        }

        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.placeBet());
        }

        // Закрытие модального окна по клику вне его
        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeBetModal();
            }
        });

        // Закрытие модального окна по Enter
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && modal && modal.style.display === 'block') {
                this.placeBet();
            }
            if (e.key === 'Escape' && modal && modal.style.display === 'block') {
                this.closeBetModal();
            }
        });
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Подключено к серверу');
        });

        this.socket.on('game_state', (data) => {
            this.updateGameState(data);
        });

        this.socket.on('new_round', (data) => {
            console.log('Новый раунд:', data);
            this.gameState = data;
            this.updateUI();
            this.resetWheel();
        });

        this.socket.on('timer_update', (data) => {
            this.gameState.time_left = data.time_left;
            this.gameState.status = data.status;
            this.updateTimer();
        });

        this.socket.on('spin_start', (data) => {
            console.log('Начало вращения:', data);
            this.spinWheel(data.winning_number);
        });

        this.socket.on('round_finished', (data) => {
            console.log('Раунд завершен:', data);
            this.handleRoundFinished(data);
        });

        this.socket.on('bet_placed', (data) => {
            this.showBetNotification(data);
        });

        this.socket.on('disconnect', () => {
            console.log('Отключено от сервера');
            this.showMessage('Соединение с сервером потеряно', 'error');
        });

        this.socket.on('reconnect', () => {
            console.log('Переподключение к серверу');
            this.showMessage('Соединение восстановлено', 'success');
        });
    }

    // Сброс колеса к начальной позиции
    resetWheel() {
        const wheel = document.querySelector('.roulette-wheel');
        if (wheel) {
            wheel.style.transition = 'none';
            wheel.style.transform = 'rotate(0deg)';
            wheel.classList.remove('spinning');
            this.isSpinning = false;
            
            // Принудительно применяем стили
            wheel.offsetHeight;
        }
    }

    // Анимация вращения колеса
    spinWheel(winningNumber) {
        if (this.isSpinning) return;
        
        this.isSpinning = true;
        const wheel = document.querySelector('.roulette-wheel');
        if (!wheel) return;

        const targetAngle = this.calculateAngleForNumber(winningNumber);
        
        // Добавляем класс для дополнительных эффектов
        wheel.classList.add('spinning');
        
        // Применяем анимацию
        wheel.style.transition = 'transform 4s cubic-bezier(0.23, 1, 0.32, 1)';
        wheel.style.transform = `rotate(${targetAngle}deg)`;

        console.log(`Вращение к числу ${winningNumber}, угол: ${targetAngle}°`);

        // Убираем класс spinning после завершения анимации
        setTimeout(() => {
            wheel.classList.remove('spinning');
        }, 4000);
    }

    updateGameState(state) {
        this.gameState = state;
        this.updateUI();
    }

    updateUI() {
        this.updateTimer();
        this.updateRoundNumber();
        this.updateBettingStatus();
    }

    updateTimer() {
        const timerElement = document.getElementById('timer');
        const statusElement = document.getElementById('gameStatus');
        
        if (timerElement) {
            timerElement.textContent = this.gameState.time_left || 0;
        }
        
        if (statusElement) {
            const statusText = this.gameState.status === 'betting' 
                ? 'Принимаются ставки' 
                : this.gameState.status === 'spinning'
                ? 'Рулетка вращается'
                : 'Ожидание';
            statusElement.textContent = statusText;
            
            // Добавляем визуальные индикаторы
            statusElement.className = `status-${this.gameState.status}`;
        }
    }

    updateRoundNumber() {
        const roundElement = document.getElementById('roundNumber');
        if (roundElement) {
            roundElement.textContent = this.gameState.round_number || 1;
        }
    }

    updateBettingStatus() {
        const buttons = document.querySelectorAll('.bet-button');
        const isBetting = this.gameState.status === 'betting';
        
        buttons.forEach(button => {
            button.disabled = !isBetting;
            if (isBetting) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    showBetModal(betType) {
        if (this.gameState.status !== 'betting') {
            this.showMessage('Ставки не принимаются!', 'error');
            return;
        }

        const modal = document.getElementById('betModal');
        const betTypeElement = document.getElementById('betType');
        const betAmountInput = document.getElementById('betAmount');

        if (modal && betTypeElement) {
            betTypeElement.textContent = this.getBetTypeName(betType);
            betTypeElement.setAttribute('data-bet', betType);
            modal.style.display = 'block';
            
            if (betAmountInput) {
                betAmountInput.focus();
                betAmountInput.value = '';
            }
        }
    }

    closeBetModal() {
        const modal = document.getElementById('betModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    getBetTypeName(betType) {
        const names = {
            'red': 'Красное (x2)',
            'black': 'Черное (x2)',
            'green': 'Зеро (x36)'
        };
        return names[betType] || betType;
    }

    async placeBet() {
        const betTypeElement = document.getElementById('betType');
        const betAmountInput = document.getElementById('betAmount');
        
        if (!betTypeElement || !betAmountInput) return;

        const betType = betTypeElement.getAttribute('data-bet');
        const amount = parseFloat(betAmountInput.value);

        // Валидация
        if (!amount || amount <= 0) {
            this.showMessage('Введите корректную сумму ставки!', 'error');
            betAmountInput.focus();
            return;
        }

        if (amount > this.userBalance) {
            this.showMessage('Недостаточно средств!', 'error');
            betAmountInput.focus();
            return;
        }

        // Минимальная ставка
        if (amount < 1) {
            this.showMessage('Минимальная ставка: 1₽', 'error');
            betAmountInput.focus();
            return;
        }

        try {
            const response = await fetch('/api/place_bet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    bet_type: betType,
                    amount: amount
                })
            });

            const data = await response.json();

            if (data.success) {
                this.userBalance = data.new_balance;
                this.updateBalanceDisplay();
                this.showMessage(`Ставка ${amount}₽ на ${this.getBetTypeName(betType)} размещена!`, 'success');
                this.closeBetModal();
                
                // Обновляем статистику
                setTimeout(() => this.loadPlayerStats(), 500);
            } else {
                this.showMessage(data.message || 'Ошибка размещения ставки', 'error');
            }
        } catch (error) {
            console.error('Ошибка:', error);
            this.showMessage('Ошибка соединения с сервером', 'error');
        }
    }

    async updateBalance() {
        try {
            const response = await fetch('/api/user_balance');
            const data = await response.json();
            this.userBalance = data.balance || 0;
            this.updateBalanceDisplay();
        } catch (error) {
            console.error('Ошибка получения баланса:', error);
        }
    }

    updateBalanceDisplay() {
        const balanceElement = document.getElementById('userBalance');
        if (balanceElement) {
            balanceElement.textContent = `${this.userBalance.toFixed(2)}₽`;
            
            // Анимация при изменении баланса
            balanceElement.classList.add('balance-updated');
            setTimeout(() => {
                balanceElement.classList.remove('balance-updated');
            }, 1000);
        }
    }

    async loadRecentResults() {
        try {
            const response = await fetch('/api/recent_results');
            const data = await response.json();
            this.recentResults = data.results || [];
            this.updateRecentResults();
        } catch (error) {
            console.error('Ошибка загрузки результатов:', error);
        }
    }

    updateRecentResults() {
        const container = document.getElementById('recentResults');
        if (!container) return;

        container.innerHTML = '';

        if (this.recentResults.length === 0) {
            container.innerHTML = '<div class="no-results">Нет результатов</div>';
            return;
        }

        this.recentResults.forEach(result => {
            const resultElement = document.createElement('div');
            resultElement.className = `result-item result-${result.color}`;
            resultElement.textContent = result.number;
            resultElement.title = `Раунд #${result.round}`;
            
            // Добавляем анимацию для новых результатов
            resultElement.style.animation = 'slideIn 0.5s ease';
            
            container.appendChild(resultElement);
        });
    }

    async loadPlayerStats() {
        try {
            const response = await fetch('/api/player_stats');
            const data = await response.json();
            this.updatePlayerStats(data);
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
    }

    updatePlayerStats(stats) {
        const elements = {
            totalBets: document.getElementById('totalBets'),
            winRate: document.getElementById('winRate'),
            totalWinnings: document.getElementById('totalWinnings'),
            netProfit: document.getElementById('netProfit')
        };

        if (elements.totalBets) elements.totalBets.textContent = stats.total_bets;
        if (elements.winRate) elements.winRate.textContent = `${stats.win_rate}%`;
        if (elements.totalWinnings) elements.totalWinnings.textContent = `${stats.total_winnings}₽`;
        
        if (elements.netProfit) {
            elements.netProfit.textContent = `${stats.net_profit}₽`;
            elements.netProfit.style.color = stats.net_profit >= 0 ? 'var(--green-color)' : 'var(--red-color)';
            
            // Добавляем иконку для прибыли/убытка
            const icon = stats.net_profit >= 0 ? '📈' : '📉';
            elements.netProfit.innerHTML = `${icon} ${stats.net_profit}₽`;
        }
    }

    handleRoundFinished(data) {
        // Добавляем результат в начало массива
        this.recentResults.unshift({
            number: data.winning_number,
            color: data.winning_color,
            round: data.round_number
        });

        // Ограничиваем до 10 последних результатов
        if (this.recentResults.length > 10) {
            this.recentResults = this.recentResults.slice(0, 10);
        }

        this.updateRecentResults();
        this.updateBalance();
        this.loadPlayerStats(); // Обновляем статистику после каждого раунда

        // Показываем результат с задержкой
        setTimeout(() => {
            this.showMessage(
                `🎯 Выпало: ${data.winning_number} (${this.getColorName(data.winning_color)})`,
                this.getMessageTypeByColor(data.winning_color)
            );
        }, 4000);

        // Добавляем звуковой эффект (если браузер поддерживает)
        this.playResultSound(data.winning_color);
    }

    getColorName(color) {
        const names = {
            'red': 'Красное',
            'black': 'Черное',
            'green': 'Зеро'
        };
        return names[color] || color;
    }

    getMessageTypeByColor(color) {
        return color === 'green' ? 'success' : 'info';
    }

    showBetNotification(data) {
        this.showMessage(
            `💰 ${data.username} поставил ${data.amount}₽ на ${this.getBetTypeName(data.bet_type)}`,
            'info'
        );
    }

    playResultSound(color) {
        // Простой звуковой эффект через Web Audio API
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // Разные частоты для разных цветов
            const frequencies = {
                'red': 440,    // A4
                'black': 330,  // E4
                'green': 660   // E5
            };
            
            oscillator.frequency.setValueAtTime(frequencies[color] || 440, audioContext.currentTime);
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0, audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(0.1, audioContext.currentTime + 0.1);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
        } catch (error) {
            // Игнорируем ошибки звука
        }
    }

    showMessage(message, type = 'info') {
        // Создаем элемент уведомления
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = message;

        // Добавляем кнопку закрытия
        const closeBtn = document.createElement('span');
        closeBtn.className = 'notification-close';
        closeBtn.innerHTML = '×';
        closeBtn.onclick = () => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        };
        notification.appendChild(closeBtn);

        // Добавляем в контейнер уведомлений
        let container = document.getElementById('notifications');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notifications';
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }

        container.appendChild(notification);

        // Автоматически удаляем уведомление через 5 секунд
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.add('fade-out');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        }, 5000);

        // Удаляем при клике на уведомление
        notification.addEventListener('click', (e) => {
            if (e.target !== closeBtn) {
                notification.classList.add('fade-out');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.remove();
                    }
                }, 300);
            }
        });

        // Ограничиваем количество уведомлений
        const notifications = container.querySelectorAll('.notification');
        if (notifications.length > 5) {
            notifications[0].remove();
        }
    }

    // Метод для отладки
    debugInfo() {
        console.log('=== DEBUG INFO ===');
        console.log('Game State:', this.gameState);
        console.log('User Balance:', this.userBalance);
        console.log('Recent Results:', this.recentResults);
        console.log('Is Spinning:', this.isSpinning);
        console.log('Socket Connected:', this.socket.connected);
    }

    // Метод для обработки ошибок
    handleError(error, context = 'Unknown') {
        console.error(`[${context}] Error:`, error);
        this.showMessage(`Ошибка: ${context}`, 'error');
    }

    // Проверка подключения к серверу
    checkConnection() {
        if (!this.socket.connected) {
            this.showMessage('Проблемы с подключением к серверу', 'error');
            return false;
        }
        return true;
    }

    // Метод для форматирования времени
    formatTime(seconds) {
        if (seconds <= 0) return '00:00';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    // Метод для анимации баланса
    animateBalance(oldBalance, newBalance) {
        const balanceElement = document.getElementById('userBalance');
        if (!balanceElement) return;

        const difference = newBalance - oldBalance;
        if (difference === 0) return;

        // Создаем элемент для показа изменения
        const changeElement = document.createElement('div');
        changeElement.className = `balance-change ${difference > 0 ? 'positive' : 'negative'}`;
        changeElement.textContent = `${difference > 0 ? '+' : ''}${difference.toFixed(2)}₽`;
        
        balanceElement.parentNode.appendChild(changeElement);

        // Анимируем и удаляем
        setTimeout(() => {
            changeElement.style.opacity = '0';
            changeElement.style.transform = 'translateY(-20px)';
            setTimeout(() => changeElement.remove(), 500);
        }, 100);
    }

    // Сохранение настроек в localStorage
    saveSettings() {
        const settings = {
            soundEnabled: this.soundEnabled || true,
            notificationsEnabled: this.notificationsEnabled || true
        };
        localStorage.setItem('rouletteSettings', JSON.stringify(settings));
    }

    // Загрузка настроек из localStorage
    loadSettings() {
        try {
            const settings = JSON.parse(localStorage.getItem('rouletteSettings') || '{}');
            this.soundEnabled = settings.soundEnabled !== false;
            this.notificationsEnabled = settings.notificationsEnabled !== false;
        } catch (error) {
            console.error('Ошибка загрузки настроек:', error);
        }
    }
}

// Глобальные утилиты
window.RouletteUtils = {
    // Форматирование валюты
    formatCurrency: (amount) => {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 2
        }).format(amount);
    },

    // Форматирование времени
    formatTime: (date) => {
        return new Intl.DateTimeFormat('ru-RU', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }).format(date);
    },

    // Получение случайного числа
    getRandomNumber: (min, max) => {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    },

    // Копирование в буфер обмена
    copyToClipboard: async (text) => {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (error) {
            console.error('Ошибка копирования:', error);
            return false;
        }
    }
};

// Инициализация игры при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем поддержку необходимых API
    if (!window.io) {
        console.error('Socket.IO не загружен!');
        alert('Ошибка загрузки игры. Обновите страницу.');
        return;
    }

    // Создаем экземпляр игры
    window.rouletteGame = new RouletteGame();

    // Добавляем глобальные обработчики
    window.addEventListener('beforeunload', () => {
        if (window.rouletteGame) {
            window.rouletteGame.saveSettings();
        }
    });

    // Обработчик ошибок
    window.addEventListener('error', (event) => {
        console.error('Глобальная ошибка:', event.error);
        if (window.rouletteGame) {
            window.rouletteGame.handleError(event.error, 'Global');
        }
    });

    // Обработчик потери соединения
    window.addEventListener('offline', () => {
        if (window.rouletteGame) {
            window.rouletteGame.showMessage('Соединение с интернетом потеряно', 'error');
        }
    });

    window.addEventListener('online', () => {
        if (window.rouletteGame) {
            window.rouletteGame.showMessage('Соединение с интернетом восстановлено', 'success');
        }
    });

    console.log('🎰 Рулетка загружена успешно!');
});

// Экспорт для использования в других скриптах
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RouletteGame;
}
