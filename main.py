import os
import random
import sqlite3
import threading
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('WEB_APP_URL', 'https://telegram-casino.onrender.com')
PORT = int(os.getenv('PORT', 5000))

print(f"✅ Bot Token: {'НАЙДЕН' if BOT_TOKEN else 'НЕ НАЙДЕН'}")
print(f"✅ Web App URL: {WEB_APP_URL}")
print(f"✅ Port: {PORT}")

# Flask приложение
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'telegram-casino-secret')

# Рулетка - европейская версия
ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "black", 12: "red",
    13: "black", 14: "red", 15: "black", 16: "red", 17: "black", 18: "red",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "black", 30: "red",
    31: "black", 32: "red", 33: "black", 34: "red", 35: "black", 36: "red"
}

# База данных
def init_db():
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 1000,
                total_games INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0,
                total_lost INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bet_type TEXT,
                bet_amount INTEGER,
                result_number INTEGER,
                result_color TEXT,
                won BOOLEAN,
                winnings INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")

def get_user(user_id):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def create_user(user_id, username, first_name):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка создания пользователя: {e}")

def save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings):
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO games (user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, bet_type, bet_amount, result_number, result_color, won, winnings))
        
        if won:
            cursor.execute('UPDATE users SET total_games = total_games + 1, total_won = total_won + ?, balance = balance + ? WHERE user_id = ?', (winnings, winnings - bet_amount, user_id))
        else:
            cursor.execute('UPDATE users SET total_games = total_games + 1, total_lost = total_lost + ?, balance = balance - ? WHERE user_id = ?', (bet_amount, bet_amount, user_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка сохранения игры: {e}")

# Flask routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🎰 Telegram Casino</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                color: white; min-height: 100vh; display: flex;
                align-items: center; justify-content: center; padding: 20px;
            }
            .container { 
                text-align: center; max-width: 400px; padding: 40px 20px;
                background: rgba(255, 255, 255, 0.1); border-radius: 20px;
                backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
            }
            .logo { font-size: 4em; margin-bottom: 20px; animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            h1 { font-size: 2.5em; margin-bottom: 20px; 
                 background: linear-gradient(45deg, #FFD700, #FFA500);
                 -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
                 background-clip: text; }
            .subtitle { font-size: 1.2em; margin-bottom: 30px; opacity: 0.9; }
            .features { list-style: none; margin-bottom: 30px; }
            .features li { padding: 10px 0; font-size: 1.1em; }
            .cta-button { 
                background: linear-gradient(45deg, #FF6B6B, #4ECDC4); color: white;
                padding: 15px 30px; border: none; border-radius: 50px;
                font-size: 1.2em; font-weight: bold; cursor: pointer;
                transition: transform 0.3s; text-decoration: none; display: inline-block;
                margin: 10px;
            }
            .cta-button:hover { transform: translateY(-2px); }
            .status { margin-top: 20px; padding: 10px; 
                     background: rgba(0, 255, 0, 0.2); border-radius: 10px;
                     border: 1px solid rgba(0, 255, 0, 0.3); }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🎰</div>
            <h1>PREMIUM CASINO</h1>
            <p class="subtitle">Премиум казино в Telegram</p>
            
            <ul class="features">
                <li>🔥 Европейская рулетка</li>
                <li>💎 Виртуальные звезды</li>
                <li>⚡ Мгновенные результаты</li>
                <li>🎯 Честная игра</li>
            </ul>
            
            <a href="/game" class="cta-button">🎮 ИГРАТЬ СЕЙЧАС</a>
            <a href="/health" class="cta-button" style="background: linear-gradient(45deg, #28a745, #20c997);">📊 СТАТУС</a>
            
            <div class="status">✅ Сервер работает</div>
        </div>

        <script>
            if (window.Telegram && window.Telegram.WebApp) {
                const tg = window.Telegram.WebApp;
                tg.ready();
                tg.expand();
                
                if (tg.themeParams.bg_color) {
                    document.body.style.background = 'linear-gradient(135deg, ' + tg.themeParams.bg_color + ' 0%, #2a5298 100%)';
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/game')
def game():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎰 European Roulette</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white; min-height: 100vh; padding: 20px;
        }
        .container { max-width: 400px; margin: 0 auto; text-align: center; }
        .roulette-container { 
            position: relative; width: 220px; height: 220px; 
            margin: 20px auto; display: flex; align-items: center; justify-content: center;
        }
        .roulette-wheel { 
            width: 200px; height: 200px; border-radius: 50%; position: relative;
            background: conic-gradient(
                #00ff00 0deg 10deg, #ff0000 10deg 20deg, #000000 20deg 30deg,
                #ff0000 30deg 40deg, #000000 40deg 50deg, #ff0000 50deg 60deg,
                #000000 60deg 70deg, #ff0000 70deg 80deg, #000000 80deg 90deg,
                #ff0000 90deg 100deg, #000000 100deg 110deg, #ff0000 110deg 120deg,
                #000000 120deg 130deg, #ff0000 130deg 140deg, #000000 140deg 150deg,
                #ff0000 150deg 160deg, #000000 160deg 170deg, #ff0000 170deg 180deg,
                #000000 180deg 190deg, #ff0000 190deg 200deg, #000000 200deg 210deg,
                #ff0000 210deg 220deg, #000000 220deg 230deg, #ff0000 230deg 240deg,
                #000000 240deg 250deg, #ff0000 250deg 260deg, #000000 260deg 270deg,
                #ff0000 270deg 280deg, #000000 280deg 290deg, #ff0000 290deg 300deg,
                #000000 300deg 310deg, #ff0000 310deg 320deg, #000000 320deg 330deg,
                #ff0000 330deg 340deg, #000000 340deg 350deg, #ff0000 350deg 360deg
            );
            border: 5px solid gold; transition: transform 4s cubic-bezier(0.25, 0.1, 0.25, 1);
        }
        .roulette-arrow { 
            position: absolute; top: -10px; left: 50%; transform: translateX(-50%);
            width: 0; height: 0; border-left: 15px solid transparent; 
            border-right: 15px solid transparent; border-top: 30px solid #FFD700; 
            z-index: 10; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
        }
        .wheel-center { 
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 50px; height: 50px; background: radial-gradient(circle, #FFD700, #FFA500); 
            border-radius: 50%; display: flex; align-items: center; justify-content: center; 
            font-weight: bold; color: black; font-size: 18px; border: 3px solid #fff; z-index: 5;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
        }
        .bet-system { 
            background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 15px; 
            margin: 20px 0; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .bet-input { 
            padding: 12px 15px; border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 25px; background: rgba(255, 255, 255, 0.1);
            color: white; font-size: 16px; text-align: center; width: 120px;
            backdrop-filter: blur(10px); margin-bottom: 15px;
        }
        .bet-input:focus { outline: none; border-color: #FFD700; box-shadow: 0 0 15px rgba(255, 215, 0, 0.5); }
        .bet-input::placeholder { color: rgba(255, 255, 255, 0.6); }
        .bet-buttons { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 15px; }
        .bet-btn { 
            padding: 15px 10px; border: none; border-radius: 12px; font-size: 13px; 
            font-weight: bold; cursor: pointer; transition: all 0.3s; text-align: center;
        }
        .bet-btn:hover { transform: translateY(-2px); }
        .bet-btn:active { transform: scale(0.95);}
        .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .bet-red { 
            background: linear-gradient(45deg, #ff4444, #cc0000); color: white; 
            box-shadow: 0 4px 15px rgba(255, 68, 68, 0.4);
        }
        .bet-black { 
            background: linear-gradient(45deg, #333333, #000000); color: white; 
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
        }
        .bet-green { 
            background: linear-gradient(45deg, #00aa00, #006600); color: white; 
            box-shadow: 0 4px 15px rgba(0, 170, 0, 0.4);
        }
        .balance, .result, .timer { 
            background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 12px; 
            margin: 15px 0; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .balance h3 { margin: 0; color: #FFD700; font-size: 1.4em; }
        .result { min-height: 60px; display: flex; align-items: center; justify-content: center; }
        .timer { 
            background: linear-gradient(45deg, rgba(255, 215, 0, 0.2), rgba(255, 165, 0, 0.2));
            border: 2px solid rgba(255, 215, 0, 0.5);
        }
        .timer h4 { margin: 0; color: #FFD700; }
        .countdown { font-size: 2em; font-weight: bold; color: #fff; margin: 10px 0; }
        .current-bets {
            background: rgba(255, 215, 0, 0.1); padding: 10px; border-radius: 10px; 
            margin: 10px 0; border: 1px solid rgba(255, 215, 0, 0.3);
        }
        .bet-indicator {
            display: inline-block; padding: 5px 10px; margin: 2px;
            background: rgba(255, 255, 255, 0.2); border-radius: 15px;
            font-size: 12px; font-weight: bold;
        }
        @keyframes spin { 
            from { transform: rotate(0deg); } 
            to { transform: rotate(var(--spin-degrees, 1800deg)); } 
        }
        .spinning { animation: spin 4s cubic-bezier(0.25, 0.1, 0.25, 1); }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        .win-animation { animation: pulse 0.6s ease-in-out 3; }
        @keyframes countdown-pulse { 
            0%, 100% { transform: scale(1); color: #fff; } 
            50% { transform: scale(1.1); color: #ff4444; } 
        }
        .countdown-warning { animation: countdown-pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎰 ЕВРОПЕЙСКАЯ РУЛЕТКА</h1>
        
        <div class="balance">
            <h3>💰 Баланс: <span id="balance">1000</span> ⭐</h3>
        </div>
        
        <div class="timer">
            <h4>⏰ До следующего спина:</h4>
            <div class="countdown" id="countdown">25</div>
        </div>
        
        <div class="roulette-container">
            <div class="roulette-arrow"></div>
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
        </div>
        
        <div class="bet-system">
            <h3>💸 Сделать ставку</h3>
            <input type="number" id="bet-amount" class="bet-input" placeholder="Сумма ⭐" min="1" max="1000" value="10">
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red')">🔴 КРАСНОЕ<br>×2</button>
                <button class="bet-btn bet-black" onclick="placeBet('black')">⚫ ЧЁРНОЕ<br>×2</button>
                <button class="bet-btn bet-green" onclick="placeBet('green')">🟢 ЗЕЛЁНОЕ<br>×36</button>
            </div>
        </div>
        
        <div class="current-bets" id="current-bets" style="display: none;">
            <h4>🎲 Текущие ставки:</h4>
            <div id="bet-list"></div>
        </div>
        
        <div class="result" id="game-result">
            <p>🎯 Введите сумму ставки и выберите цвет!</p>
        </div>
    </div>

    <script>
        let userBalance = 1000;
        let isSpinning = false;
        let userId = null;
        let currentBets = [];
        let countdownTimer = 25;
        let countdownInterval;

        if (window.Telegram && window.Telegram.WebApp) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
                userId = tg.initDataUnsafe.user.id;
            }
        }

        function startGameTimer() {
            countdownInterval = setInterval(function() {
                countdownTimer--;
                const countdownEl = document.getElementById('countdown');
                countdownEl.textContent = countdownTimer;
                
                if (countdownTimer <= 5) {
                    countdownEl.classList.add('countdown-warning');
                } else {
                    countdownEl.classList.remove('countdown-warning');
                }
                
                if (countdownTimer <= 0) {
                    autoSpin();
                    countdownTimer = 25;
                }
            }, 1000);
        }

        function autoSpin() {
            if (isSpinning) return;
            
            isSpinning = true;
            document.getElementById('game-result').innerHTML = '<p>🎰 Автоматический спин...</p>';
            
            const result = Math.floor(Math.random() * 37);
            const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
            const resultColor = result === 0 ? 'green' : (redNumbers.includes(result) ? 'red' : 'black');
            
            const segmentAngle = 360 / 37;
            const targetAngle = result * segmentAngle;
            const spinRotations = 5;
            const finalAngle = (spinRotations * 360) + (360 - targetAngle);
            
            const wheel = document.getElementById('wheel');
            wheel.style.setProperty('--spin-degrees', finalAngle + 'deg');
            wheel.classList.add('spinning');
            
            setTimeout(function() {
                processSpinResult(result, resultColor);
                wheel.classList.remove('spinning');
                isSpinning = false;
            }, 4000);
        }

        function processSpinResult(result, resultColor) {
            document.getElementById('result-number').textContent = result;
            
            let totalWinnings = 0;
            let totalLosses = 0;
            
            currentBets.forEach(function(bet) {
                const won = bet.type === resultColor;
                if (won) {
                    const winAmount = bet.type === 'green' ? bet.amount * 36 : bet.amount * 2;
                    totalWinnings += winAmount;
                    userBalance += winAmount;
                } else {
                    totalLosses += bet.amount;
                    userBalance -= bet.amount;
                }
            });
            
            const colorEmoji = resultColor === 'red' ? '🔴' : (resultColor === 'black' ? '⚫' : '🟢');
            let resultMessage = '';
            
            if (currentBets.length > 0) {
                if (totalWinnings > 0) {
                    resultMessage = '🎉 ВЫИГРЫШ! ' + colorEmoji + ' ' + result + '<br>💰 +' + totalWinnings + '⭐';
                    document.getElementById('game-result').classList.add('win-animation');
                    setTimeout(function() {
                        document.getElementById('game-result').classList.remove('win-animation');
                    }, 2000);
                } else {
                    resultMessage = '😔 Проигрыш ' + colorEmoji + ' ' + result + '<br>📉 -' + totalLosses + '⭐';
                }
            } else {
                resultMessage = '🎯 Выпало: ' + colorEmoji + ' ' + result + '<br>💡 Делайте ставки!';
            }
            
            document.getElementById('game-result').innerHTML = '<p>' + resultMessage + '</p>';
            document.getElementById('balance').textContent = userBalance;
            
            currentBets = [];
            updateBetDisplay();
            updateBetButtons();
        }

        function placeBet(color) {
            const betAmountInput = document.getElementById('bet-amount');
            const betAmount = parseInt(betAmountInput.value) || 0;
            
            if (betAmount <= 0) {
                showMessage('❌ Введите корректную сумму ставки!');
                return;
            }
            
            if (betAmount > userBalance) {
                showMessage('❌ Недостаточно средств!');
                return;
            }
            
            if (betAmount > 1000) {
                showMessage('❌ Максимальная ставка: 1000⭐');
                return;
            }
            
            const totalCurrentBets = currentBets.reduce(function(sum, bet) {
                return sum + bet.amount;
            }, 0);
            
            if (totalCurrentBets + betAmount > userBalance) {
                showMessage('❌ Недостаточно средств для всех ставок!');
                return;
            }
            
            const existingBetIndex = currentBets.findIndex(function(bet) {
                return bet.type === color;
            });
            
            if (existingBetIndex !== -1) {
                currentBets[existingBetIndex].amount += betAmount;
                showMessage('✅ Ставка увеличена: ' + color.toUpperCase() + ' ' + currentBets[existingBetIndex].amount + '⭐');
            } else {
                currentBets.push({ type: color, amount: betAmount });
                showMessage('✅ Ставка размещена: ' + color.toUpperCase() + ' ' + betAmount + '⭐');
            }
            
            updateBetDisplay();
            updateBetButtons();
            betAmountInput.value = '10';
        }

        function updateBetDisplay() {
            const currentBetsDiv = document.getElementById('current-bets');
            const betListDiv = document.getElementById('bet-list');
            
            if (currentBets.length > 0) {
                currentBetsDiv.style.display = 'block';
                betListDiv.innerHTML = '';
                
                currentBets.forEach(function(bet) {
                    const colorEmoji = bet.type === 'red' ? '🔴' : (bet.type === 'black' ? '⚫' : '🟢');
                    const betIndicator = document.createElement('span');
                    betIndicator.className = 'bet-indicator';
                    betIndicator.innerHTML = colorEmoji + ' ' + bet.amount + '⭐';
                    betListDiv.appendChild(betIndicator);
                });
            } else {
                currentBetsDiv.style.display = 'none';
            }
        }

        function updateBetButtons() {
            const totalBetAmount = currentBets.reduce(function(sum, bet) {
                return sum + bet.amount;
            }, 0);
            const availableBalance
            await update.message.reply_text(
        f"🎰 Добро пожаловать в казино, {user.first_name}!\n\n💰 Ваш баланс: 1000 ⭐",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance":
        user_data = get_user(query.from_user.id)
        balance = user_data[3] if user_data else 1000
        await query.edit_message_text(f"💰 Ваш баланс: {balance} ⭐")

def run_bot():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback))
        print("🤖 Бот запущен!")
        application.run_polling()
    except Exception as e:
        print(f"❌ Ошибка бота: {e}")

# Инициализация и запуск
init_db()

if BOT_TOKEN:
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
