// Telegram Casino JavaScript
console.log('🎰 Casino JS загружен');

// Игровые переменные
let userBalance = 1000;
let isSpinning = false;
let userId = null;

// Telegram WebApp инициализация
let tg = null;
if (window.Telegram && window.Telegram.WebApp) {
    tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    
    // Получаем данные пользователя
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        userId = tg.initDataUnsafe.user.id;
        console.log('👤 Пользователь ID:', userId);
        loadUserBalance();
    }
    
    // Настройка главной кнопки
    tg.MainButton.setText('🎰 Крутить рулетку');
    tg.MainButton.hide();
}

// Числа рулетки и их цвета
const ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "black", 12: "red",
    13: "black", 14: "red", 15: "black", 16: "red", 17: "black", 18: "red",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "black", 30: "red",
    31: "black", 32: "red", 33: "black", 34: "red", 35: "black", 36: "red"
};

// Загрузка баланса пользователя
async function loadUserBalance() {
    if (!userId) return;
    
    try {
        const response = await fetch(`/api/user/${userId}`);
        if (response.ok) {
            const userData = await response.json();
            updateBalance(userData.balance);
        }
    } catch (error) {
        console.error('Ошибка загрузки баланса:', error);
    }
}

// Обновление баланса на экране
function updateBalance(newBalance) {
    userBalance = newBalance;
    const balanceElement = document.getElementById('balance');
    if (balanceElement) {
        balanceElement.textContent = newBalance;
        
        // Анимация изменения баланса
        balanceElement.style.transform = 'scale(1.2)';
        balanceElement.style.color = '#FFD700';
        setTimeout(() => {
            balanceElement.style.transform = 'scale(1)';
            balanceElement.style.color = 'inherit';
        }, 300);
    }
}

// Размещение ставки
function placeBet(color, amount) {
    console.log(`🎯 Ставка: ${color} - ${amount}⭐`);
    
    // Проверки
    if (isSpinning) {
        showResult("⏳ Рулетка уже крутится!");
        return;
    }
    
    if (userBalance < amount) {
        showResult("❌ Недостаточно средств!");
        vibratePhone();
        return;
    }
    
    // Блокируем кнопки
    isSpinning = true;
    disableAllButtons();
    
    // Показываем процесс
    showResult("🎰 Крутим рулетку...");
    
    // Запускаем рулетку
    spinRoulette(color, amount);
}

// Анимация рулетки
function spinRoulette(betColor, betAmount) {
    const wheel = document.getElementById('wheel');
    if (!wheel) return;
    
    // Добавляем класс анимации
    wheel.classList.add('spinning');
    
    // Звук (если возможно)
    playSpinSound();
    
    // Делаем API запрос
    fetch('/api/spin', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: userId,
            bet_type: betColor,
            bet_amount: betAmount
        })
    })
    .then(response => response.json())
    .then(data => {
        // Через 3 секунды показываем результат
        setTimeout(() => {
            processSpinResult(data, betColor, betAmount);
        }, 3000);
    })
    .catch(error => {
        console.error('Ошибка API:', error);
        setTimeout(() => {
            // Локальная генерация результата при ошибке
            const localResult = generateLocalResult(betColor, betAmount);
            processSpinResult(localResult, betColor, betAmount);
        }, 3000);
    });
}

// Обработка результата
function processSpinResult(data, betColor, betAmount) {
    const wheel = document.getElementById('wheel');
    const resultNumber = document.getElementById('result-number');
    
    if (wheel) wheel.classList.remove('spinning');
    if (resultNumber) resultNumber.textContent = data.result_number;
    
    // Определяем результат
    const won = data.won;
    const winnings = data.winnings || 0;
    
    // Обновляем баланс
    if (won) {
        updateBalance(userBalance + winnings - betAmount);
        showWinResult(data.result_number, data.result_color, winnings);
        celebrateWin();
    } else {
        updateBalance(userBalance - betAmount);
        showLoseResult(data.result_number, data.result_color, betAmount);
        vibratePhone();
    }
    
    // Разблокируем кнопки
    setTimeout(() => {
        isSpinning = false;
        enableAllButtons();
    }, 2000);
}

// Показ результата выигрыша
function showWinResult(number, color, winnings) {
    const colorEmoji = getColorEmoji(color);
    const message = `🎉 ВЫИГРЫШ! ${colorEmoji} ${number}\n💰 +${winnings}⭐`;
    
    showResult(message, 'win');
    
    // Telegram haptic feedback
    if (tg && tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('heavy');
    }
}

// Показ результата проигрыша
function showLoseResult(number, color, lostAmount) {
    const colorEmoji = getColorEmoji(color);
    const message = `😔 Проигрыш ${colorEmoji} ${number}\n📉 -${lostAmount}⭐`;
    
    showResult(message, 'lose');
}

// Получение эмодзи цвета
function getColorEmoji(color) {
    switch(color) {
        case 'red': return '🔴';
        case 'black': return '⚫';
        case 'green': return '🟢';
        default: return '⚪';
    }
}

// Показ результата в интерфейсе
function showResult(message, type = '') {
    const resultElement = document.getElementById('game-result');
