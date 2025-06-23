@app.route('/game')
def game():
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎰 European Roulette</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; padding: 20px;
            }
            .container { max-width: 400px; margin: 0 auto; text-align: center; }
            .roulette-wheel { 
                width: 200px; height: 200px; border-radius: 50%; 
                margin: 20px auto; position: relative;
                background: conic-gradient(
                    #ff0000 0deg 9.73deg, #000000 9.73deg 19.46deg,
                    #ff0000 19.46deg 29.19deg, #000000 29.19deg 38.92deg,
                    #ff0000 38.92deg 48.65deg, #000000 48.65deg 58.38deg,
                    #ff0000 58.38deg 68.11deg, #000000 68.11deg 77.84deg,
                    #ff0000 77.84deg 87.57deg, #000000 87.57deg 97.30deg,
                    #00ff00 97.30deg 107.03deg,
                    #000000 107.03deg 116.76deg, #ff0000 116.76deg 126.49deg,
                    #000000 126.49deg 136.22deg, #ff0000 136.22deg 145.95deg,
                    #000000 145.95deg 155.68deg, #ff0000 155.68deg 165.41deg,
                    #000000 165.41deg 175.14deg, #ff0000 175.14deg 184.87deg,
                    #000000 184.87deg 194.60deg, #ff0000 194.60deg 204.33deg,
                    #000000 204.33deg 214.06deg, #ff0000 214.06deg 223.79deg,
                    #000000 223.79deg 233.52deg, #ff0000 233.52deg 243.25deg,
                    #000000 243.25deg 252.98deg, #ff0000 252.98deg 262.71deg,
                    #000000 262.71deg 272.44deg, #ff0000 272.44deg 282.17deg,
                    #000000 282.17deg 291.90deg, #ff0000 291.90deg 301.63deg,
                    #000000 301.63deg 311.36deg, #ff0000 311.36deg 321.09deg,
                    #000000 321.09deg 330.82deg, #ff0000 330.82deg 340.55deg,
                    #000000 340.55deg 350.28deg, #ff0000 350.28deg 360deg
                );
                border: 5px solid gold; transition: transform 0.5s ease;
            }
            .wheel-center { 
                position: absolute; top: 50%; left: 50%; 
                transform: translate(-50%, -50%); width: 40px; height: 40px; 
                background: gold; border-radius: 50%; display: flex; 
                align-items: center; justify-content: center; 
                font-weight: bold; color: black; font-size: 16px;
            }
            .bet-buttons { 
                display: grid; grid-template-columns: 1fr 1fr; gap: 10px; 
                margin: 20px 0; max-width: 300px; margin-left: auto; margin-right: auto;
            }
            .bet-btn { 
                padding: 15px; border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold; cursor: pointer;
                transition: all 0.2s; text-align: center;
            }
            .bet-btn:active { transform: scale(0.95); }
            .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .bet-red { background: linear-gradient(45deg, #ff4444, #cc0000); color: white; }
            .bet-black { background: linear-gradient(45deg, #333333, #000000); color: white; }
            .bet-green { background: linear-gradient(45deg, #00aa00, #006600); color: white; }
            .balance, .result { 
                background: rgba(255, 255, 255, 0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0; backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .balance h3 { margin: 0; color: #FFD700; }
            .result { min-height: 60px; display: flex; align-items: center; justify-content: center; }
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(1800deg); } }
            .spinning { animation: spin 3s cubic-bezier(0.25, 0.46, 0.45, 0.94); }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            .win-animation { animation: pulse 0.5s ease-in-out 3; }
            @media (max-width: 480px) {
                .container { padding: 10px; }
                .roulette-wheel { width: 150px; height: 150px; }
                .wheel-center { width: 30px; height: 30px; font-size: 14px; }
                .bet-btn { padding: 12px; font-size: 12px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА</h1>
            
            <div class="balance">
                <h3>💰 Баланс: <span id="balance">1000</span> ⭐</h3>
            </div>
            
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
            
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red', 50)">
                    🔴 КРАСНОЕ ×2<br>50⭐
                </button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 50)">
                    ⚫ ЧЁРНОЕ ×2<br>50⭐
                </button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 50)">
                    🟢 ЗЕЛЁНОЕ ×36<br>50⭐
                </button>
                <button class="bet-btn bet-red" onclick="placeBet('red', 100)">
                    🔴 КРАСНОЕ<br>100⭐
                </button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 100)">
                    ⚫ ЧЁРНОЕ<br>100⭐
                </button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 100)">
                    🟢 ЗЕЛЁНОЕ<br>100⭐
                </button>
            </div>
            
            <div class="result" id="game-result">
                <p>🎯 Сделайте ставку для начала игры!</p>
            </div>
        </div>

        <script>
            // Игровые переменные
            let userBalance = 1000;
            let isSpinning = false;
            let userId = null;

            // Telegram WebApp
            let tg = null;
            if (window.Telegram && window.Telegram.WebApp) {
                tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                
                if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
                    userId = tg.initDataUnsafe.user.id;
                    loadUserBalance();
                }
            }

            // Загрузка баланса
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

            // Обновление баланса
            function updateBalance(newBalance) {
                userBalance = newBalance;
                const balanceElement = document.getElementById('balance');
                if (balanceElement) {
                    balanceElement.textContent = newBalance;
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
                
                if (isSpinning) {
                    showResult("⏳ Рулетка уже крутится!");
                    return;
                }
                
                if (userBalance < amount) {
                    showResult("❌ Недостаточно средств!");
                    vibratePhone();
                    return;
                }
                
                isSpinning = true;
                disableAllButtons();
                showResult("🎰 Крутим рулетку...");
                
                spinRoulette(color, amount);
            }

            // Анимация рулетки
            function spinRoulette(betColor, betAmount) {
                const wheel = document.getElementById('wheel');
                if (wheel) wheel.classList.add('spinning');
                
                fetch('/api/spin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: userId,
                        bet_type: betColor,
                        bet_amount: betAmount
                    })
                })
                .then(response => response.json())
                .then(data => {
                    setTimeout(() => processSpinResult(data, betColor, betAmount), 3000);
                })
                .catch(error => {
                    console.error('API Error:', error);
                    setTimeout(() => {
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
                
                const won = data.won;
                const winnings = data.winnings || 0;
                
                if (won) {
                    updateBalance(userBalance + winnings - betAmount);
                    showWinResult(data.result_number, data.result_color, winnings);
                    celebrateWin();
                } else {
                    updateBalance(userBalance - betAmount);
                    showLoseResult(data.result_number, data.result_color, betAmount);
                    vibratePhone();
                }
                
                setTimeout(() => {
                    isSpinning = false;
                    enableAllButtons();
                }, 2000);
            }

            // Показ результата выигрыша
            function showWinResult(number, color, winnings) {
                const colorEmoji = getColorEmoji(color);
                const message = `🎉 ВЫИГРЫШ! ${colorEmoji} ${number}<br>💰 +${winnings}⭐`;
                showResult(message, 'win');
                
                if (tg && tg.HapticFeedback) {
                    tg.HapticFeedback.impactOccurred('heavy');
                }
            }

            // Показ результата проигрыша
            function showLoseResult(number, color, lostAmount) {
                const colorEmoji = getColorEmoji(color);
                const message = `😔 Проигрыш ${colorEmoji} ${number}<br>📉 -${lostAmount}⭐`;
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

            // Показ результата
            function showResult(message, type = '') {
                const resultElement = document.getElementById('game-result');
                if (resultElement) {
                    resultElement.innerHTML = `<p>${message}</p>`;
                    resultElement.className = `result ${type}`;
                    
                    resultElement.style.transform = 'scale(0.8)';
                    resultElement.style.opacity = '0.5';
                    setTimeout(() => {
                        resultElement.style.transform = 'scale(1)';
                        resultElement.style.opacity = '1';
                    }, 100);
                }
            }

            // Локальная генерация результата
            function generateLocalResult(betColor, betAmount) {
                const resultNumber = Math.floor(Math.random() * 37);
                const resultColor = getNumberColor(resultNumber);
                const won = betColor === resultColor;
                
                let winnings = 0;
                if (won) {
                    winnings = resultColor === 'green' ? betAmount * 36 : betAmount * 2;
                }
                
                return {
                    success: true,
                    result_number: resultNumber,
                    result_color: resultColor,
                    won: won,
                    winnings: winnings
                };
            }

            // Определение цвета числа
            function getNumberColor(number) {
                if (number === 0) return 'green';
                const redNumbers = [1,3
