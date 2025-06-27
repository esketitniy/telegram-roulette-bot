class RouletteGame {
    constructor() {
        this.socket = io();
        this.userBalance = parseInt(document.getElementById('balance')?.textContent) || 0;
        this.currentBet = null;
        this.gamePhase = 'betting';
        this.spinAngle = 0;
        this.initializeEventListeners();
        this.connectSocket();
    }

    initializeEventListeners() {
        // Socket события
        this.socket.on('connect', () => {
            console.log('Подключен к серверу');
        });

        this.socket.on('game_state', (data) => {
            this.updateGameState(data);
        });

        this.socket.on('phase_change', (data) => {
            this.handlePhaseChange(data);
        });

        this.socket.on('time_update', (data) => {
            this.updateTimer(data.time_left);
        });

        this.socket.on('bet_placed', (data) => {
            this.addPlayerBet(data);
        });

        this.socket.on('game_result', (data) => {
            this.handleGameResult(data);
        });

        // Кнопки ставок
        const colorButtons = document.querySelectorAll('.color-bet');
        colorButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const color = e.currentTarget.classList.contains('red') ? 'red' :
                             e.currentTarget.classList.contains('black') ? 'black' : 'green';
                this.placeBet(color);
            });
        });
    }

    connectSocket() {
        this.socket.connect();
    }

    updateGameState(data) {
        this.gamePhase = data.phase;
        this.updateTimer(data.time_left);
        this.updatePlayerBets(data.current_bets);
        this.updateHistory(data.history);
    }

    handlePhaseChange(data) {
        this.gamePhase = data.phase;
        const phaseText = document.getElementById('phase-text');
        const timerCircle = document.querySelector('.timer-circle');

        if (data.phase === 'betting') {
            phaseText.textContent = 'Делайте ставки!';
            timerCircle.style.background = 'linear-gradient(45deg, #ffd700, #ffed4a)';
            this.enableBetting();
        } else if (data.phase === 'spinning') {
            phaseText.textContent = 'Рулетка крутится!';
            timerCircle.style.background = 'linear-gradient(45deg, #ff4757, #ff6b7d)';
            this.disableBetting();
            this.spinRoulette(data.result);
        }
    }

    updateTimer(timeLeft) {
        const timerText = document.getElementById('timer-text');
        if (timerText) {
            timerText.textContent = timeLeft;
        }
    }

    enableBetting() {
        const colorButtons = document.querySelectorAll('.color-bet');
        colorButtons.forEach(button => {
            button.disabled = false;
            button.classList.remove('loading');
        });
    }

    disableBetting() {
        const colorButtons = document.querySelectorAll('.color-bet');
        colorButtons.forEach(button => {
            button.disabled = true;
            button.classList.add('loading');
        });
    }

    placeBet(betType) {
        if (this.gamePhase !== 'betting') {
            this.showNotification('Ставки не принимаются!', 'error');
            return;
        }

        const betAmount = parseInt(document.getElementById('bet-amount')?.value) || 0;
        
        if (betAmount < 10) {
            this.showNotification('Минимальная ставка 10 монет!', 'error');
            return;
        }

        if (betAmount > this.userBalance) {
            this.showNotification('Недостаточно средств!', 'error');
            return;
        }

        // Отправляем ставку на сервер
        fetch('/api/place_bet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                bet_type: betType,
                amount: betAmount
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.userBalance -= betAmount;
                this.updateBalance();
                this.currentBet = { type: betType, amount: betAmount };
                this.showNotification(`Ставка ${betAmount} на ${this.getColorName(betType)} принята!`, 'success');
                this.highlightBetButton(betType);
            } else {
                this.showNotification(data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Ошибка при размещении ставки:', error);
            this.showNotification('Ошибка при размещении ставки', 'error');
        });
    }

    getColorName(color) {
        const names = {
            'red': 'красное',
            'black': 'чёрное',
            'green': 'зелёное'
        };
        return names[color] || color;
    }

    highlightBetButton(betType) {
        // Убираем подсветку со всех кнопок
        document.querySelectorAll('.color-bet').forEach(btn => {
            btn.classList.remove('active-bet');
        });

        // Добавляем подсветку на выбранную кнопку
        const button = document.querySelector(`.color-bet.${betType}`);
        if (button) {
            button.classList.add('active-bet');
            button.style.boxShadow = '0 0 20px rgba(255, 215, 0, 0.8)';
        }
    }

    updateBalance() {
        const balanceElement = document.getElementById('balance');
        if (balanceElement) {
            balanceElement.textContent = this.userBalance;
            balanceElement.classList.add('pulse-animation');
            setTimeout(() => {
                balanceElement.classList.remove('pulse-animation');
            }, 1000);
        }
    }

    addPlayerBet(data) {
        const betsContainer = document.getElementById('bets-container');
        if (!betsContainer) return;

        const betElement = document.createElement('div');
        betElement.className = 'player-bet';
        betElement.innerHTML = `
            <div class="bet-info">
                <div class="bet-color ${data.bet_type}"></div>
                <span class="player-name">${data.username}</span>
            </div>
            <span class="bet-amount">${data.amount}</span>
        `;

        betsContainer.insertBefore(betElement, betsContainer.firstChild);

        // Удаляем старые ставки, если их больше 10
        while (betsContainer.children.length > 10) {
            betsContainer.removeChild(betsContainer.lastChild);
        }
    }

    updatePlayerBets(bets) {
        const betsContainer = document.getElementById('bets-container');
        if (!betsContainer) return;

        betsContainer.innerHTML = '';
        bets.forEach(bet => {
            this.addPlayerBet(bet);
        });
    }

    spinRoulette(result) {
        const wheel = document.getElementById('roulette-wheel');
        if (!wheel) return;

        // Убираем предыдущие классы анимации
        wheel.classList.remove('spinning');

        // Рассчитываем угол поворота
        const colorAngles = this.getColorAngles();
        const targetAngle = colorAngles[result];
        const spins = 5; // Количество полных оборотов
        const totalAngle = (360 * spins) + targetAngle + Math.random() * 20 - 10; // Добавляем небольшую случайность

        // Устанавливаем CSS переменную для анимации
        wheel.style.setProperty('--spin-degrees', `${totalAngle}deg`);

        // Запускаем анимацию
        setTimeout(() => {
            wheel.classList.add('spinning');
        }, 100);

        this.spinAngle = totalAngle % 360;
    }

    getColorAngles() {
    // Углы для 15 секторов (24 градуса на сектор)
    const sectorAngle = 24;
    const angles = {
        'red': [0, 48, 120, 168, 240, 288, 336],      // красные сектора
        'black': [24, 72, 144, 192, 216, 264, 312],   // черные сектора
        'green': [96]                                  // зеленый сектор
    };
    
    // Выбираем случайный угол из доступных для выпавшего цвета
    return angles;
}

spinRoulette(result) {
    const wheel = document.getElementById('roulette-wheel');
    if (!wheel) return;

    // Убираем предыдущие классы анимации
    wheel.classList.remove('spinning');

    // Рассчитываем угол поворота
    const colorAngles = this.getColorAngles();
    const availableAngles = colorAngles[result];
    const targetAngle = availableAngles[Math.floor(Math.random() * availableAngles.length)];
    const spins = 5; // Количество полных оборотов
    const totalAngle = (360 * spins) + targetAngle + Math.random() * 10 - 5; // Добавляем небольшую случайность

    // Устанавливаем CSS переменную для анимации
    wheel.style.setProperty('--spin-degrees', `${totalAngle}deg`);

    // Запускаем анимацию
    setTimeout(() => {
        wheel.classList.add('spinning');
    }, 100);

    this.spinAngle = totalAngle % 360;
}
    
    handleGameResult(data) {
        setTimeout(() => {
            this.updateHistory(data.history);
            
            if (this.currentBet) {
                const isWin = this.currentBet.type === data.result;
                if (isWin) {
                    const multiplier = data.result === 'green' ? 14 : 2;
                    const winAmount = this.currentBet.amount * multiplier;
                    this.userBalance += winAmount;
                    this.updateBalance();
                    this.showWinModal(winAmount);
                    this.createConfetti();
                } else {
                    this.showLoseModal();
                }
            }

            // Показываем результат
            this.showGameResult(data.result);

            // Сбрасываем текущую ставку
            this.currentBet = null;
            this.clearBetHighlight();

        }, 10000); // Показываем результат после окончания анимации
    }

    showGameResult(result) {
        const resultElement = document.createElement('div');
        resultElement.className = `game-result-popup ${result}`;
        resultElement.innerHTML = `
            <div class="result-content">
                <h3>Выпало: ${this.getColorName(result).toUpperCase()}</h3>
                <div class="result-color-indicator ${result}"></div>
            </div>
        `;

        document.body.appendChild(resultElement);

        setTimeout(() => {
            resultElement.remove();
        }, 3000);
    }

    clearBetHighlight() {
        document.querySelectorAll('.color-bet').forEach(btn => {
            btn.classList.remove('active-bet');
            btn.style.boxShadow = '';
        });
    }

    updateHistory(history) {
        const historyContainer = document.getElementById('history-items');
        if (!historyContainer) return;

        historyContainer.innerHTML = '';
        history.slice(-10).forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = `history-item ${item.result}`;
            historyItem.innerHTML = '<span class="history-color"></span>';
            historyContainer.appendChild(historyItem);
        });
    }

    showWinModal(amount) {
        const modal = document.getElementById('win-modal');
        const winText = document.getElementById('win-text');
        if (modal && winText) {
            winText.textContent = `Поздравляем! Вы выиграли ${amount} монет!`;
            modal.style.display = 'block';
        }
    }

    showLoseModal() {
        const modal = document.getElementById('lose-modal');
        const loseText = document.getElementById('lose-text');
        if (modal && loseText) {
            loseText.textContent = 'В этот раз не повезло, попробуйте снова!';
            modal.style.display = 'block';
        }
    }

    showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        Object.assign(notification.style, {
            position: 'fixed',
            top: '100px',
            right: '20px',
            padding: '1rem 2rem',
            borderRadius: '10px',
            color: 'white',
            fontWeight: 'bold',
            zIndex: '2000',
            animation: 'slideInRight 0.5s ease',
            background: type === 'success' ? '#00ff88' : '#ff4757'
        });
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.5s ease';
            setTimeout(() => {
                notification.remove();
            }, 500);
        }, 3000);
    }

    createConfetti() {
        for (let i = 0; i < 50; i++) {
            setTimeout(() => {
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + 'vw';
                confetti.style.backgroundColor = ['#ffd700', '#ff4757', '#00ff88'][Math.floor(Math.random() * 3)];
                confetti.style.animationDelay = Math.random() * 2 + 's';
                document.body.appendChild(confetti);

                setTimeout(() => {
                    confetti.remove();
                }, 3000);
            }, i * 50);
        }
    }
}

// Функции для управления ставками
function setBetAmount(type) {
    const betInput = document.getElementById('bet-amount');
    const currentAmount = parseInt(betInput.value) || 10;
    const balance = parseInt(document.getElementById('balance').textContent) || 0;

    let newAmount;
    switch (type) {
        case 'min':
            newAmount = 10;
            break;
        case 'half':
            newAmount = Math.floor(currentAmount / 2);
            if (newAmount < 10) newAmount = 10;
            break;
        case 'double':
            newAmount = currentAmount * 2;
            if (newAmount > balance) newAmount = balance;
            break;
        case 'max':
            newAmount = balance;
            break;
        default:
            newAmount = 10;
    }

    betInput.value = newAmount;
    
    // Анимация для кнопки
    const button = event.target;
    button.style.transform = 'scale(0.95)';
    setTimeout(() => {
        button.style.transform = '';
    }, 150);
}

function placeBet(color) {
    if (window.rouletteGame) {
        window.rouletteGame.placeBet(color);
    }
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
}

// Инициализация игры при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('roulette-wheel')) {
        window.rouletteGame = new RouletteGame();
    }
});

// Дополнительные анимации CSS
const additionalStyles = `
@keyframes slideOutRight {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
}

.game-result-popup {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.9);
    padding: 2rem;
    border-radius: 20px;
    border: 3px solid;
    z-index: 1500;
    animation: resultPopup 3s ease;
}

.game-result-popup.red {
    border-color: #ff4757;
}

.game-result-popup.black {
    border-color: #2f3542;
}

.game-result-popup.green {
    border-color: #00ff88;
}

@keyframes resultPopup {
    0% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
    20% { opacity: 1; transform: translate(-50%, -50%) scale(1.1); }
    80% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
    100% { opacity: 0; transform: translate(-50%, -50%) scale(0.5); }
}

.result-content h3 {
    font-size: 1.5rem;
    margin-bottom: 1rem;
    text-align: center;
}

.result-color-indicator {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    margin: 0 auto;
    border: 3px solid #fff;
}

.result-color-indicator.red {
    background: #ff4757;
}

.result-color-indicator.black {
    background: #2f3542;
}

.result-color-indicator.green {
    background: #00ff88;
}

.active-bet {
    animation: betPulse 2s infinite;
}

@keyframes betPulse {
    0% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.5); }
    50% { box-shadow: 0 0 25px rgba(255, 215, 0, 1); }
    100% { box-shadow: 0 0 5px rgba(255, 215, 0, 0.5); }
}

.notification {
    max-width: 300px;
    word-wrap: break-word;
}
`;

// Добавляем дополнительные стили
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);
