import os
import sqlite3
import threading
import time
import asyncio
from datetime import datetime
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import random
import json

# Настройки
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
PORT = int(os.getenv('PORT', 5000))
APP_URL = os.getenv('APP_URL', 'https://your-app.onrender.com')

app = Flask(__name__)

# Глобальные переменные для игры
current_bets = {}
game_state = {
    'countdown': 25,
    'is_spinning': False,
    'last_result': {'number': 0, 'color': 'green'},
    'spin_history': []
}

# База данных
def init_db():
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            balance INTEGER DEFAULT 1000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            bet_type TEXT,
            amount INTEGER,
            round_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
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
        cursor.execute('INSERT INTO users (telegram_id, username) VALUES (?, ?)', 
                      (telegram_id, f'user_{telegram_id}'))
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def update_balance(telegram_id, new_balance):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE telegram_id = ?', (new_balance, telegram_id))
    conn.commit()
    conn.close()

def get_current_bets():
    return current_bets

def add_bet(user_id, username, bet_type, amount):
    if user_id not in current_bets:
        current_bets[user_id] = []
    
    # Проверяем есть ли уже ставка на этот цвет
    existing_bet = None
    for bet in current_bets[user_id]:
        if bet['type'] == bet_type:
            existing_bet = bet
            break
    
    if existing_bet:
        existing_bet['amount'] += amount
    else:
        current_bets[user_id].append({
            'username': username,
            'type': bet_type,
            'amount': amount
        })

def clear_bets():
    global current_bets
    current_bets = {}

# Flask маршруты
@app.route('/')
def index():
    return '''
    <h1>🎰 Casino Bot</h1>
    <p>Telegram Casino Bot is running!</p>
    <a href="/game">Open Game</a>
    '''

@app.route('/game')
def game():
    return render_template_string('''<!DOCTYPE html>
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; min-height: 100vh; padding: 10px; overflow-x: hidden;
        }
        .container { max-width: 420px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 20px; }
        .header h1 { 
            font-size: 24px; margin-bottom: 10px; 
            background: linear-gradient(45deg, #FFD700, #FFA500);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .stats-row { 
            display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px;
        }
        .stat-box { 
            background: rgba(255, 255, 255, 0.15); padding: 15px; border-radius: 15px; 
            text-align: center; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .stat-box h3 { font-size: 14px; margin-bottom: 5px; opacity: 0.8; }
        .stat-value { font-size: 18px; font-weight: bold; color: #FFD700; }
        .countdown-box { 
            background: linear-gradient(45deg, rgba(255, 69, 0, 0.3), rgba(255, 140, 0, 0.3));
            border: 2px solid rgba(255, 69, 0, 0.5);
        }
        .countdown-timer { font-size: 28px; font-weight: bold; color: #ff4500; }
        .countdown-warning { animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1); } }
        
        .roulette-container { 
            position: relative; width: 280px; height: 280px; margin: 20px auto;
            display: flex; align-items: center; justify-content: center;
        }
        .roulette-wheel { 
            width: 260px; height: 260px; border-radius: 50%; position: relative;
            background: conic-gradient(
                #00ff00 0deg 9.73deg,    /* 0 */
                #ff0000 9.73deg 19.46deg, /* 32 */
                #000000 19.46deg 29.19deg, /* 15 */
                #ff0000 29.19deg 38.92deg, /* 19 */
                #000000 38.92deg 48.65deg, /* 4 */
                #ff0000 48.65deg 58.38deg, /* 21 */
                #000000 58.38deg 68.11deg, /* 2 */
                #ff0000 68.11deg 77.84deg, /* 25 */
                #000000 77.84deg 87.57deg, /* 17 */
                #ff0000 87.57deg 97.30deg, /* 34 */
                #000000 97.30deg 107.03deg, /* 6 */
                #ff0000 107.03deg 116.76deg, /* 27 */
                #000000 116.76deg 126.49deg, /* 13 */
                #ff0000 126.49deg 136.22deg, /* 36 */
                #000000 136.22deg 145.95deg, /* 11 */
                #ff0000 145.95deg 155.68deg, /* 30 */
                #000000 155.68deg 165.41deg, /* 8 */
                #ff0000 165.41deg 175.14deg, /* 23 */
                #000000 175.14deg 184.87deg, /* 10 */
                #ff0000 184.87deg 194.60deg, /* 5 */
                #000000 194.60deg 204.33deg, /* 24 */
                #ff0000 204.33deg 214.06deg, /* 16 */
                #000000 214.06deg 223.79deg, /* 33 */
                #ff0000 223.79deg 233.52deg, /* 1 */
                #000000 233.52deg 243.25deg, /* 20 */
                #ff0000 243.25deg 252.98deg, /* 14 */
                #000000 252.98deg 262.71deg, /* 31 */
                #ff0000 262.71deg 272.44deg, /* 9 */
                #000000 272.44deg 282.17deg, /* 22 */
                #ff0000 282.17deg 291.90deg, /* 18 */
                #000000 291.90deg 301.63deg, /* 29 */
                #ff0000 301.63deg 311.36deg, /* 7 */
                #000000 311.36deg 321.09deg, /* 28 */
                #ff0000 321.09deg 330.82deg, /* 12 */
                #000000 330.82deg 340.55deg, /* 35 */
                #ff0000 340.55deg 350.28deg, /* 3 */
                #000000 350.28deg 360deg /* 26 */
            );
            border: 6px solid #FFD700; 
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.6), inset 0 0 20px rgba(0,0,0,0.3);
            transition: transform 8s cubic-bezier(0.25, 0.1, 0.25, 1);
        }
        .roulette-arrow { 
            position: absolute; top: -15px; left: 50%; transform: translateX(-50%);
            width: 0; height: 0; border-left: 20px solid transparent; 
            border-right: 20px solid transparent; border-top: 40px solid #FFD700; 
            z-index: 10; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.5));
        }
        .wheel-center { 
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: 80px; height: 80px; 
            background: radial-gradient(circle, #FFD700 30%, #FFA500 70%, #FF8C00 100%); 
            border-radius: 50%; display: flex; align-items: center; justify-content: center; 
            font-weight: bold; color: #000; font-size: 24px; 
            border: 4px solid #fff; z-index: 5;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.9), inset 0 0 15px rgba(0,0,0,0.2);
        }
        .spinning { animation: spin 8s cubic-bezier(0.25, 0.1, 0.25, 1); }
        @keyframes spin { 
            from { transform: rotate(0deg); } 
            to { transform: rotate(var(--spin-degrees, 2880deg)); } 
        }
        
        .bet-section { 
            background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 20px; 
            margin: 20px 0; backdrop-filter: blur(15px); 
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .bet-input-container { text-align: center; margin-bottom: 20px; }
        .bet-input { 
            padding: 15px 20px; border: 2px solid rgba(255, 215, 0, 0.5);
            border-radius: 30px; background: rgba(255, 255, 255, 0.1);
            color: white; font-size: 18px; text-align: center; width: 200px;
            backdrop-filter: blur(10px); font-weight: bold;
        }
        .bet-input:focus { 
            outline: none; border-color: #FFD700; 
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5); 
        }
        .bet-input::placeholder { color: rgba(255, 255, 255, 0.7); }
        .bet-buttons { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; }
        .bet-btn { 
            padding: 18px 15px; border: none; border-radius: 15px; font-size: 14px; 
            font-weight: bold; cursor: pointer; transition: all 0.3s; text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        .bet-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.4); }
        .bet-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .bet-red { 
            background: linear-gradient(45deg, #ff4444, #cc0000); 
            color: white; border: 2px solid #ff6666;
        }
        .bet-black { 
            background: linear-gradient(45deg, #333333, #000000); 
            color: white; border: 2px solid #555555;
        }
        .bet-green { 
            background: linear-gradient(45deg, #00aa00, #006600); 
            color: white; border: 2px solid #00cc00;
        }
        
        .players-bets { 
            background: rgba(255, 215, 0, 0.1); padding: 15px; border-radius: 15px; 
            margin: 15px 0; border: 2px solid rgba(255, 215, 0, 0.3);
        }
        .players-bets h4 { margin-bottom: 15px; color: #FFD700; text-align: center; }
        .bet-list { max-height: 150px; overflow-y: auto; }
        .player-bet { 
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 12px; margin: 5px 0; 
            background: rgba(255, 255, 255, 0.1); border-radius: 10px;
            font-size: 13px;
        }
        .player-name { font-weight: bold; }
        .bet-details { display: flex; gap: 10px; align-items: center; }
        .bet-color-red { color: #ff4444; }
        .bet-color-black { color: #cccccc; }
        .bet-color-green { color: #00ff00; }
        
        .result-section { 
            background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 15px; 
            margin: 20px 0; text-text-align: center; backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2); min-height: 80px;
            display: flex; align-items: center; justify-content: center;
        }
        .result-win { 
            background: linear-gradient(45deg, rgba(0, 255, 0, 0.2), rgba(0, 200, 0, 0.2));
            border-color: #00ff00; color: #00ff00;
        }
        .result-lose { 
            background: linear-gradient(45deg, rgba(255, 0, 0, 0.2), rgba(200, 0, 0, 0.2));
            border-color: #ff4444; color: #ff4444;
        }
        .result-text { font-size: 16px; font-weight: bold; }
        
        .history-section { 
            background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 15px; 
            margin: 15px 0; backdrop-filter: blur(10px);
        }
        .history-title { text-align: center; margin-bottom: 15px; color: #FFD700; }
        .history-numbers { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
        .history-number { 
            width: 35px; height: 35px; border-radius: 50%; 
            display: flex; align-items: center; justify-content: center;
            font-size: 12px; font-weight: bold; border: 2px solid rgba(255,255,255,0.3);
        }
        .history-red { background: #ff4444; color: white; }
        .history-black { background: #333333; color: white; }
        .history-green { background: #00aa00; color: white; }
        
        .footer { text-align: center; margin-top: 30px; opacity: 0.7; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎰 EUROPEAN ROULETTE</h1>
        </div>
        
        <div class="stats-row">
            <div class="stat-box">
                <h3>💰 Balance</h3>
                <div class="stat-value" id="balance">1000 ⭐</div>
            </div>
            <div class="stat-box countdown-box" id="countdown-container">
                <h3>⏰ Next Spin</h3>
                <div class="countdown-timer" id="countdown">25</div>
            </div>
        </div>
        
        <div class="roulette-container">
            <div class="roulette-arrow"></div>
            <div class="roulette-wheel" id="roulette-wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
        </div>
        
        <div class="bet-section">
            <div class="bet-input-container">
                <input type="number" id="bet-amount" class="bet-input" 
                       placeholder="Enter bet (10-20000)" min="10" max="20000" value="10">
            </div>
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red')" id="red-btn">
                    🔴 RED<br><small>x2</small>
                </button>
                <button class="bet-btn bet-black" onclick="placeBet('black')" id="black-btn">
                    ⚫ BLACK<br><small>x2</small>
                </button>
                <button class="bet-btn bet-green" onclick="placeBet('green')" id="green-btn">
                    🟢 GREEN<br><small>x36</small>
                </button>
            </div>
        </div>
        
        <div class="players-bets" id="players-bets" style="display: none;">
            <h4>👥 Current Bets</h4>
            <div class="bet-list" id="bet-list"></div>
        </div>
        
        <div class="result-section" id="result-section">
            <div class="result-text">Place your bet and wait for spin!</div>
        </div>
        
        <div class="history-section">
            <h4 class="history-title">📊 Last Results</h4>
            <div class="history-numbers" id="history-numbers"></div>
        </div>
        
        <div class="footer">
            <p>🎰 Automatic spin every 25 seconds</p>
        </div>
    </div>

    <script>
        let tg = window.Telegram.WebApp;
        let userId = tg.initDataUnsafe?.user?.id || 123456;
        let username = tg.initDataUnsafe?.user?.username || 'Player';
        
        let userBalance = 1000;
        let gameState = {
            countdown: 25,
            isSpinning: false,
            lastResult: { number: 0, color: 'green' },
            history: []
        };
        let playerBets = {};
        let hasUserBet = false;
        
        const rouletteNumbers = [
            0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
            24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
        ];
        
        const redNumbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36];
        
        function getNumberColor(number) {
            if (number === 0) return 'green';
            return redNumbers.includes(number) ? 'red' : 'black';
        }
        
        function updateUI() {
            document.getElementById('balance').textContent = userBalance + ' ⭐';
            document.getElementById('countdown').textContent = gameState.countdown;
            
            // Предупреждение при последних секундах
            const countdownContainer = document.getElementById('countdown-container');
            if (gameState.countdown <= 5 && !gameState.isSpinning) {
                countdownContainer.classList.add('countdown-warning');
            } else {
                countdownContainer.classList.remove('countdown-warning');
            }
            
            updateBetButtons();
            updatePlayersBets();
            updateHistory();
        }
        
        function updateBetButtons() {
            const betAmount = parseInt(document.getElementById('bet-amount').value) || 0;
            const buttons = ['red-btn', 'black-btn', 'green-btn'];
            
            buttons.forEach(btnId => {
                const btn = document.getElementById(btnId);
                btn.disabled = gameState.isSpinning || betAmount < 10 || betAmount > 20000 || betAmount > userBalance;
            });
        }
        
        function updatePlayersBets() {
            const betsContainer = document.getElementById('players-bets');
            const betsList = document.getElementById('bet-list');
            
            const allBets = [];
            Object.keys(playerBets).forEach(playerId => {
                playerBets[playerId].forEach(bet => {
                    allBets.push({
                        username: bet.username,
                        type: bet.type,
                        amount: bet.amount
                    });
                });
            });
            
            if (allBets.length > 0) {
                betsContainer.style.display = 'block';
                betsList.innerHTML = '';
                
                allBets.forEach(bet => {
                    const betDiv = document.createElement('div');
                    betDiv.className = 'player-bet';
                    betDiv.innerHTML = `
                        <span class="player-name">${bet.username}</span>
                        <div class="bet-details">
                            <span class="bet-color-${bet.type}">${bet.type.toUpperCase()}</span>
                            <span>${bet.amount} ⭐</span>
                        </div>
                    `;
                    betsList.appendChild(betDiv);
                });
            } else {
                betsContainer.style.display = 'none';
            }
        }
        
        function updateHistory() {
            const historyContainer = document.getElementById('history-numbers');
            historyContainer.innerHTML = '';
            
            gameState.history.slice(-10).forEach(result => {
                const numberDiv = document.createElement('div');
                numberDiv.className = `history-number history-${result.color}`;
                numberDiv.textContent = result.number;
                historyContainer.appendChild(numberDiv);
            });
        }
        
        function placeBet(color) {
            if (gameState.isSpinning) return;
            
            const betAmount = parseInt(document.getElementById('bet-amount').value);
            
            if (betAmount < 10 || betAmount > 20000) {
                showResult('❌ Bet must be between 10 and 20,000 stars!', 'result-lose');
                return;
            }
            
            if (betAmount > userBalance) {
                showResult('❌ Insufficient balance!', 'result-lose');
                return;
            }
            
            // Добавляем ставку пользователя
            if (!playerBets[userId]) {
                playerBets[userId] = [];
            }
            
            // Проверяем есть ли уже ставка на этот цвет
            const existingBet = playerBets[userId].find(bet => bet.type === color);
            if (existingBet) {
                existingBet.amount += betAmount;
            } else {
                playerBets[userId].push({
                    username: username,
                    type: color,
                    amount: betAmount
                });
            }
            
            userBalance -= betAmount;
            hasUserBet = true;
            
            showResult(`✅ Bet placed: ${color.toUpperCase()} ${betAmount} ⭐`, '');
            updateUI();
            
            // Имитируем ставки других игроков
            simulateOtherPlayersBets();
        }
        
        function simulateOtherPlayersBets() {
            if (Math.random() < 0.7) { // 70% шанс что кто-то еще поставит
                const fakePlayers = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank'];
                const randomPlayer = fakePlayers[Math.floor(Math.random() * fakePlayers.length)];
                const randomPlayerId = 'bot_' + randomPlayer;
                const randomColor = ['red', 'black', 'green'][Math.floor(Math.random() * 3)];
                const randomAmount = [10, 25, 50, 100, 250, 500][Math.floor(Math.random() * 6)];
                
                if (!playerBets[randomPlayerId]) {
                    playerBets[randomPlayerId] = [];
                }
                
                const existingBet = playerBets[randomPlayerId].find(bet => bet.type === randomColor);
                if (existingBet) {
                    existingBet.amount += randomAmount;
                } else {
                    playerBets[randomPlayerId].push({
                        username: randomPlayer,
                        type: randomColor,
                        amount: randomAmount
                    });
                }
                
                updateUI();
            }
        }
        
        function spin() {
            if (gameState.isSpinning) return;
            
            gameState.isSpinning = true;
            showResult('🎰 Spinning...', '');
            
            const wheel = document.getElementById('roulette-wheel');
            const resultNumber = rouletteNumbers[Math.floor(Math.random() * rouletteNumbers.length)];
            const resultColor = getNumberColor(resultNumber);
            
            // Случайное количество оборотов + точная позиция
            const spins = 8 + Math.random() * 4; // 8-12 оборотов
            const numberIndex = rouletteNumbers.indexOf(resultNumber);
            const degreesPerNumber = 360 / 37;
            const finalDegree = 360 - (numberIndex * degreesPerNumber) + (degreesPerNumber / 2);
            const totalDegrees = (spins * 360) + finalDegree;
            
            wheel.style.setProperty('--spin-degrees', totalDegrees + 'deg');
            wheel.classList.add('spinning');
            
            setTimeout(() => {
                wheel.classList.remove('spinning');
                document.getElementById('result-number').textContent = resultNumber;
                
                gameState.lastResult = { number: resultNumber, color: resultColor };
                gameState.history.push({ number: resultNumber, color: resultColor });
                if (gameState.history.length > 20) gameState.history.shift();
                
                processResults(resultNumber, resultColor);
                updateUI();
                
                gameState.isSpinning = false;
                gameState.countdown = 25;
                startCountdown();
            }, 8000);
        }
        
        function processResults(number, color) {
            let userWon = false;
            let userWinAmount = 0;
            let userLossAmount = 0;
            
            if (playerBets[userId]) {
                playerBets[userId].forEach(bet => {
                    if (bet.type === color) {
                        userWon = true;
                        const multiplier = color === 'green' ? 36 : 2;
                        userWinAmount += bet.amount * multiplier;
                    } else {
                        userLossAmount += bet.amount;
                    }
                });
                
                if (userWon) {
                    userBalance += userWinAmount;
                    showResult(`🎉 WIN! ${color.toUpperCase()} ${number} - You won ${userWinAmount} ⭐!`, 'result-win');
                } else if (hasUserBet) {
                    showResult(`💔 LOSE! ${color.toUpperCase()} ${number} - You lost ${userLossAmount} ⭐`, 'result-lose');
                } else {
                    showResult(`🎰 Result: ${color.toUpperCase()} ${number}`, '');
                }
            } else {
                showResult(`🎰 Result: ${color.toUpperCase()} ${number}`, '');
            }
            
            // Очищаем все ставки
            playerBets = {};
            hasUserBet = false;
        }
        
        function showResult(message, className) {
            const resultSection = document.getElementById('result-section');
            resultSection.className = 'result-section ' + className;
            resultSection.innerHTML = `<div class="result-text">${message}</div>`;
        }
        
        function startCountdown() {
            const countdownInterval = setInterval(() => {
                gameState.countdown--;
                updateUI();
                
                if (gameState.countdown <= 0) {
                    clearInterval(countdownInterval);
                    spin();
                }
            }, 1000);
        }
        
        // Обработчики событий
        document.getElementById('bet-amount').addEventListener('input', updateBetButtons);
        
        // Инициализация игры
        function initGame() {
            updateUI();
            startCountdown();
            showResult('🎰 Game started! Place your bets!', '');
            // Периодически добавляем ставки ботов
            setInterval(() => {
                if (!gameState.isSpinning && gameState.countdown > 5) {
                    simulateOtherPlayersBets();
                }
            }, 3000);
        }
        
        // Telegram WebApp настройки
        if (tg) {
            tg.ready();
            tg.expand();
            tg.MainButton.hide();
        }
        
        // Запуск игры
        initGame();
        
        // Предотвращение закрытия во время игры
        window.addEventListener('beforeunload', function(e) {
            if (hasUserBet && !gameState.isSpinning) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    </script>
</body>
</html>''')

@app.route('/api/game-state')
def get_game_state():
    return {
        'countdown': game_state['countdown'],
        'is_spinning': game_state['is_spinning'],
        'last_result': game_state['last_result'],
        'current_bets': get_current_bets()
    }

# Telegram Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    keyboard = [[InlineKeyboardButton("🎰 Play Casino", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"""
🎰 <b>Welcome to European Roulette!</b>

💰 Your balance: <b>{user[3]} ⭐</b>

🎲 <b>How to play:</b>
• Place bets from 10 to 20,000 stars
• Choose RED, BLACK, or GREEN
• Automatic spin every 25 seconds
• RED/BLACK: x2 payout
• GREEN (0): x36 payout

🚀 <b>Features:</b>
• Live betting with other players
• Real-time animations
• Betting history
• Automatic gameplay

Click the button below to start playing!
    """
    
    await update.message.reply_text(
        welcome_msg, 
        parse_mode='HTML', 
        reply_markup=reply_markup
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 Your current balance: <b>{user[3]} ⭐</b>", parse_mode='HTML')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    history = game_state['spin_history'][-10:] if game_state['spin_history'] else []
    
    history_text = ""
    if history:
        for result in history:
            color_emoji = "🟢" if result['color'] == 'green' else ("🔴" if result['color'] == 'red' else "⚫")
            history_text += f"{color_emoji} {result['number']} "
    else:
        history_text = "No games played yet"
    
    stats_msg = f"""
📊 <b>Game Statistics</b>

💰 Your balance: <b>{user[3]} ⭐</b>
🎰 Last 10 results: {history_text}

🎯 <b>Current Game:</b>
⏰ Next spin in: <b>{game_state['countdown']} seconds</b>
🎲 Last result: <b>{game_state['last_result']['color'].upper()} {game_state['last_result']['number']}</b>
    """
    
    keyboard = [[InlineKeyboardButton("🎰 Play Now", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_msg, parse_mode='HTML', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🎰 <b>European Roulette Help</b>

<b>📖 Commands:</b>
/start - Start the game
/balance - Check your balance
/stats - View game statistics
/help - Show this help

<b>🎮 How to Play:</b>
1. Click "Play Casino" button
2. Enter bet amount (10-20,000 ⭐)
3. Choose color: RED, BLACK, or GREEN
4. Wait for automatic spin (every 25 seconds)
5. Win and collect your payout!

<b>💰 Payouts:</b>
• RED: x2 (18/37 chance)
• BLACK: x2 (18/37 chance)  
• GREEN (0): x36 (1/37 chance)

<b>✨ Features:</b>
• Real-time multiplayer betting
• Smooth wheel animations
• Live countdown timer
• Betting history tracking
• Mobile-optimized interface

<b>💡 Tips:</b>
• Start with small bets to learn
• Green has highest payout but lowest chance
• Watch other players' bets for insights
• Game runs automatically every 25 seconds

Good luck! 🍀
    """
    
    keyboard = [[InlineKeyboardButton("🎰 Start Playing", web_app={'url': f'{APP_URL}/game'})]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "play_game":
        keyboard = [[InlineKeyboardButton("🎰 Open Casino", web_app={'url': f'{APP_URL}/game'})]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎰 Click the button to open the casino!", reply_markup=reply_markup)

# Игровой движок (работает в фоне)
def game_engine():
    """Автоматический игровой движок"""
    while True:
        try:
            if not game_state['is_spinning']:
                # Обратный отсчет
                for i in range(25, 0, -1):
                    if game_state['is_spinning']:
                        break
                    game_state['countdown'] = i
                    time.sleep(1)
                
                if not game_state['is_spinning']:
                    # Запуск спина
                    game_state['is_spinning'] = True
                    game_state['countdown'] = 0
                    
                    # Генерация результата
                    roulette_numbers = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
                    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
                    
                    result_number = random.choice(roulette_numbers)
                    result_color = 'green' if result_number == 0 else ('red' if result_number in red_numbers else 'black')
                    
                    # Обработка результатов
                    process_spin_result(result_number, result_color)
                    
                    # Пауза на анимацию
                    time.sleep(8)
                    
                    # Сохранение результата
                    game_state['last_result'] = {'number': result_number, 'color': result_color}
                    game_state['spin_history'].append({'number': result_number, 'color': result_color})
                    
                    # Ограничиваем историю
                    if len(game_state['spin_history']) > 50:
                        game_state['spin_history'] = game_state['spin_history'][-50:]
                    
                    # Очистка ставок
                    clear_bets()
                    game_state['is_spinning'] = False
                    
                    print(f"🎰 Spin result: {result_color.upper()} {result_number}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Game engine error: {e}")
            time.sleep(1)

def process_spin_result(number, color):
    """Обработка результатов спина"""
    try:
        conn = sqlite3.connect('casino.db')
        cursor = conn.cursor()
        
        # Получаем всех пользователей с активными ставками
        cursor.execute('''
            SELECT u.telegram_id, u.balance, b.bet_type, b.amount 
            FROM users u 
            JOIN bets b ON u.id = b.user_id 
            WHERE b.round_id = ?
        ''', (int(time.time()) // 30,))  # Используем время как ID раунда
        
        active_bets = cursor.fetchall()
        
        for telegram_id, balance, bet_type, amount in active_bets:
            if bet_type == color:
                # Выигрыш
                multiplier = 36 if color == 'green' else 2
                win_amount = amount * multiplier
                new_balance = balance + win_amount
                update_balance(telegram_id, new_balance)
                print(f"Player {telegram_id} won {win_amount} stars!")
        
        # Очистка старых ставок
        cursor.execute('DELETE FROM bets WHERE round_id < ?', (int(time.time()) // 30,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error processing spin result: {e}")

def run_bot():
    """Запуск Telegram бота"""
    try:
        app_bot = Application.builder().token(BOT_TOKEN).build()
        
        # Команды
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CommandHandler("balance", balance))
        app_bot.add_handler(CommandHandler("stats", stats))
        app_bot.add_handler(CommandHandler("help", help_command))
        app_bot.add_handler(CallbackQueryHandler(button_callback))
        
        # Запуск бота
        app_bot.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == '__main__':
    print("🎰 Starting Casino Bot...")
    
    # Инициализация базы данных
    init_db()
    print("✅ Database initialized")
    
    # Запуск игрового движка
    game_thread = threading.Thread(target=game_engine)
    game_thread.daemon = True
    game_thread.start()
    print("✅ Game engine started")
    
    # Запуск Telegram бота
    if BOT_TOKEN and BOT_TOKEN != 'YOUR_BOT_TOKEN':
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        print("✅ Telegram bot started")
    else:
        print("⚠️  BOT_TOKEN not configured")
    
    # Запуск Flask сервера
    print(f"🚀 Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
