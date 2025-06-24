import os
import sqlite3
import threading
from flask import Flask, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
BOT_TOKEN = os.getenv('BOT_TOKEN')
PORT = int(os.getenv('PORT', 5000))

def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            balance INTEGER DEFAULT 1000
        )
    ''')
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('INSERT INTO users (telegram_id, balance) VALUES (?, ?)', (telegram_id, 1000))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
    conn.close()
    return user

@app.route('/')
def index():
    return '''
    <h1>🎰 Casino Bot</h1>
    <p>Bot is running!</p>
    <a href="/game">Play Game</a>
    '''
    
@app.route('/game')
def game():
    html_template = """<!DOCTYPE html>
    <html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>European Roulette</title>
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
        .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .bet-red { background: linear-gradient(45deg, #ff4444, #cc0000); color: white; }
        .bet-black { background: linear-gradient(45deg, #333333, #000000); color: white; }
        .bet-green { background: linear-gradient(45deg, #00aa00, #006600); color: white; }
        .balance, .result, .timer { 
            background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 12px; 
            margin: 15px 0; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .balance h3 { margin: 0; color: #FFD700; font-size: 1.4em; }
        .result { min-height: 60px; display: flex; align-items: center; justify-content: center; }
        .timer { background: linear-gradient(45deg, rgba(255, 215, 0, 0.2), rgba(255, 165, 0, 0.2)); }
        .timer h4 { margin: 0; color: #FFD700; }
        .countdown { font-size: 2em; font-weight: bold; color: #fff; margin: 10px 0; }
        .current-bets { background: rgba(255, 215, 0, 0.1); padding: 10px; border-radius: 10px; margin: 10px 0; }
        .bet-indicator { display: inline-block; padding: 5px 10px; margin: 2px; background: rgba(255, 255, 255, 0.2); border-radius: 15px; font-size: 12px; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(var(--spin-degrees, 1800deg)); } }
        .spinning { animation: spin 4s cubic-bezier(0.25, 0.1, 0.25, 1); }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        .win-animation { animation: pulse 0.6s ease-in-out 3; }
        .countdown-warning { animation: pulse 1s infinite; color: #ff4444; }
    </style>
</head>
<body>
    <div class="container">
        <h1>EUROPEAN ROULETTE</h1>
        
        <div class="balance">
            <h3>Balance: <span id="balance">1000</span> stars</h3>
        </div>
        
        <div class="timer">
            <h4>Next spin: <span class="countdown" id="countdown">25</span>s</h4>
        </div>
        
        <div class="roulette-container">
            <div class="roulette-arrow"></div>
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
        </div>
        
        <div class="bet-system">
            <h3>Place Bet</h3>
            <input type="number" id="bet-amount" class="bet-input" placeholder="Amount" min="1" max="1000" value="10">
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red')">RED x2</button>
                <button class="bet-btn bet-black" onclick="placeBet('black')">BLACK x2</button>
                <button class="bet-btn bet-green" onclick="placeBet('green')">GREEN x36</button>
            </div>
        </div>
        
        <div class="current-bets" id="current-bets" style="display: none;">
            <h4>Current Bets:</h4>
            <div id="bet-list"></div>
        </div>
        
        <div class="result" id="game-result">
            <p>Place your bet!</p>
        </div>
    </div>

    <script>
        let userBalance = 1000, currentBets = [], countdownTimer = 25, isSpinning = false;

        function startTimer() {
            setInterval(() => {
                countdownTimer--;
                const el = document.getElementById('countdown');
                el.textContent = countdownTimer;
                el.className = countdownTimer <= 5 ? 'countdown countdown-warning' : 'countdown';
                if (countdownTimer <= 0) { autoSpin(); countdownTimer = 25; }
            }, 1000);
        }

        function autoSpin() {
            if (isSpinning) return;
            isSpinning = true;
            const result = Math.floor(Math.random() * 37);
            const reds = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36];
            const color = result === 0 ? 'green' : (reds.includes(result) ? 'red' : 'black');
            
            const wheel = document.getElementById('wheel');
            wheel.style.setProperty('--spin-degrees', (5 * 360 + result * 10) + 'deg');
            wheel.classList.add('spinning');
            
            setTimeout(() => {
                document.getElementById('result-number').textContent = result;
                wheel.classList.remove('spinning');
                
                let winnings = 0, losses = 0;
                currentBets.forEach(bet => {
                    if (bet.type === color) {
                        const win = bet.type === 'green' ? bet.amount * 36 : bet.amount * 2;
                        winnings += win; userBalance += win;
                    } else {
                        losses += bet.amount; userBalance -= bet.amount;
                    }
                });
                
                const emoji = color === 'red' ? 'RED' : (color === 'black' ? 'BLACK' : 'GREEN');
                const msg = currentBets.length > 0 ? 
                    (winnings > 0 ? `WIN! ${emoji} ${result} (+${winnings} stars)` : `LOSE ${emoji} ${result} (-${losses} stars)`) :
                    `Result: ${emoji} ${result}`;
                
                document.getElementById('game-result').innerHTML = `<p>${msg}</p>`;
                document.getElementById('balance').textContent = userBalance;
                currentBets = []; updateDisplay();
                isSpinning = false;
            }, 4000);
        }

        function placeBet(color) {
            const amount = parseInt(document.getElementById('bet-amount').value) || 0;
            if (amount <= 0 || amount > userBalance || amount > 1000) {
                document.getElementById('game-result').innerHTML = '<p>Invalid bet amount!</p>';
                return;
            }
            
            const existing = currentBets.find(b => b.type === color);
            if (existing) existing.amount += amount;
            else currentBets.push({type: color, amount});
            
            document.getElementById('game-result').innerHTML = `<p>Bet placed: ${color.toUpperCase()} ${amount} stars</p>`;
            updateDisplay();
        }

        function updateDisplay() {
            const div = document.getElementById('current-bets');
            const list = document.getElementById('bet-list');
            if (currentBets.length > 0) {
                div.style.display = 'block';
                list.innerHTML = currentBets.map(bet => {
                    const colorName = bet.type === 'red' ? 'RED' : (bet.type === 'black' ? 'BLACK' : 'GREEN');
                    return `<span class="bet-indicator">${colorName} ${bet.amount} stars</span>`;
                }).join('');
            } else div.style.display = 'none';
        }

    startTimer();
    </script>
</body>
</html>"""
    return html_template
    
    function updateBetDisplay() {
            const currentBetsDiv = document.getElementById('current-bets');
            const betListDiv = document.getElementById('bet-list');
            
            if (currentBets.length > 0) {
                currentBetsDiv.style.display = 'block';
                betListDiv.innerHTML = '';
                
                currentBets.forEach(function(bet) {
                    const colorName = bet.type === 'red' ? 'RED' : (bet.type === 'black' ? 'BLACK' : 'GREEN');
                    const betIndicator = document.createElement('span');
                    betIndicator.className = 'bet-indicator';
                    betIndicator.innerHTML = colorName + ' ' + bet.amount + ' stars';
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
            const availableBalance = userBalance - totalBetAmount;
            
            const buttons = document.querySelectorAll('.bet-btn');
            const betAmountInput = document.getElementById('bet-amount');
            const currentBetAmount = parseInt(betAmountInput.value) || 0;
            
            buttons.forEach(function(button) {
                button.disabled = currentBetAmount > availableBalance || currentBetAmount <= 0 || isSpinning;
            });
            
            betAmountInput.placeholder = 'Available: ' + availableBalance + ' stars';
        }

        function showMessage(message) {
            const resultEl = document.getElementById('game-result');
            resultEl.innerHTML = '<p>' + message + '</p>';
            
            setTimeout(function() {
                if (resultEl.innerHTML.includes(message)) {
                    if (currentBets.length > 0) {
                        resultEl.innerHTML = '<p>Bets placed! Waiting for spin...</p>';
                    } else {
                        resultEl.innerHTML = '<p>Enter bet amount and choose color!</p>';
                    }
                }
            }, 3000);
        }

        document.getElementById('bet-amount').addEventListener('input', function() {
            updateBetButtons();
        });

        function initGame() {
            updateBetButtons();
            startGameTimer();
            showMessage('Game started! Auto spin every 25 seconds');
        }

        window.addEventListener('load', function() {
            setTimeout(initGame, 1000);
        });

        window.addEventListener('beforeunload', function() {
            if (countdownInterval) clearInterval(countdownInterval);
        });
    </script>
</body>
</html>"""
    return html_template

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 Play Roulette", web_app={"url": "https://your-app-name.onrender.com/game"})],
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎰 Welcome to Casino Bot!\n\n"
        f"Your balance: {user[3]} stars\n\n"
        f"Choose an option:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'balance':
        user = get_user(query.from_user.id)
        await query.edit_message_text(
            f"💰 Your current balance: {user[3]} stars\n\n"
            f"Play roulette to win more stars!"
        )
    
    elif query.data == 'help':
        await query.edit_message_text(
            "🎰 How to play:\n\n"
            "1. Click 'Play Roulette' to open the game\n"
            "2. Choose your bet amount (1-1000 stars)\n"
            "3. Select RED (x2), BLACK (x2), or GREEN (x36)\n"
            "4. Wait for the automatic spin every 25 seconds\n"
            "5. Win or lose based on the result!\n\n"
            "Good luck! 🍀"
        )

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling()

if __name__ == '__main__':
    init_db()
    
    if BOT_TOKEN:
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
