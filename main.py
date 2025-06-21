import asyncio
import json
import random
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, render_template, request, jsonify, send_from_directory
import threading

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEB_APP_URL = os.getenv('REPL_URL', 'https://telegram-casino.your-username.repl.co')

# Flask приложение
app = Flask(__name__)

# Рулетка - европейская версия
ROULETTE_NUMBERS = {
    0: "green",
    1: "red", 2: "black", 3: "red", 4: "black", 5: "red", 6: "black",
    7: "red", 8: "black", 9: "red", 10: "black", 11: "red", 12: "black",
    13: "red", 14: "black", 15: "red", 16: "black", 17: "red", 18: "black",
    19: "red", 20: "black", 21: "red", 22: "black", 23: "red", 24: "black",
    25: "red", 26: "black", 27: "red", 28: "black", 29: "red", 30: "black",
    31: "red", 32: "black", 33: "red", 34: "black", 35: "red", 36: "black"
}

# Инициализация базы данных
def init_db():
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

# Функции для работы с БД
def get_user(user_id):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def save_game(user_id, bet_type, bet_amount, result_number, result_color, won, winnings):
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO games (user_id, bet_type, bet_amount, result_number, result_color, won, winnings)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, bet_type, bet_amount, result_number, result_color, won, winnings))
    
    if won:
        cursor.execute('UPDATE users SET total_games = total_games + 1, total_won = total_won + ? WHERE user_id = ?', (winnings, user_id))
    else:
        cursor.execute('UPDATE users SET total_games = total_games + 1, total_lost = total_lost + ? WHERE user_id = ?', (bet_amount, user_id))
    
    conn.commit()
    conn.close()

# Flask routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Casino Landing</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; background: linear-gradient(45deg, #1e3c72, #2a5298); color: white; }
            h1 { font-size: 3em; margin-bottom: 20px; }
            .emoji { font-size: 4em; }
        </style>
    </head>
    <body>
        <div class="emoji">🎰</div>
        <h1>Casino Bot</h1>
        <p>Telegram Casino Bot is running!</p>
        <p>Go to your Telegram bot to start playing!</p>
    </body>
    </html>
    '''

@app.route('/game')
def game():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🎰 European Roulette</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
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
                border: 5px solid gold;
                animation: spin 3s ease-in-out;
            }
            .wheel-center { 
                position: absolute; top: 50%; left: 50%; 
                transform: translate(-50%, -50%);
                width: 40px; height: 40px; background: gold;
                border-radius: 50%; display: flex; align-items: center;
                justify-content: center; font-weight: bold; color: black;
            }
            .bet-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 20px 0; }
            .bet-btn { 
                padding: 15px; border: none; border-radius: 10px;
                font-size: 16px; font-weight: bold; cursor: pointer;
                transition: transform 0.2s;
            }
            .bet-btn:hover { transform: scale(1.05); }
            .bet-red { background: #ff4444; color: white; }
            .bet-black { background: #333; color: white; }
            .bet-green { background: #00aa00; color: white; }
            .balance { 
                background: rgba(255,255,255,0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0;
            }
            .result { 
                background: rgba(255,255,255,0.1); padding: 15px;
                border-radius: 10px; margin: 20px 0; min-height: 60px;
            }
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(1800deg); } }
            .spinning { animation: spin 3s ease-in-out; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎰 European Roulette</h1>
            
            <div class="balance">
                <h3>💰 Balance: <span id="balance">1000</span> ⭐</h3>
            </div>
            
            <div class="roulette-wheel" id="wheel">
                <div class="wheel-center" id="result-number">0</div>
            </div>
            
            <div class="bet-buttons">
                <button class="bet-btn bet-red" onclick="placeBet('red', 50)">🔴 RED ×2<br>50⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 50)">⚫ BLACK ×2<br>50⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 50)">🟢 GREEN ×36<br>50⭐</button>
                <button class="bet-btn bet-red" onclick="placeBet('red', 100)">🔴 RED<br>100⭐</button>
                <button class="bet-btn bet-black" onclick="placeBet('black', 100)">⚫ BLACK<br>100⭐</button>
                <button class="bet-btn bet-green" onclick="placeBet('green', 100)">🟢 GREEN<br>100⭐</button>
            </div>
            
            <div class="result" id="game-result">
                <p>🎯 Place your bet to start!</p>
            </div>
        </div>

        <script>
            let userBalance = 1000;
            let isSpinning = false;
            
            // Telegram WebApp initialization
            let tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            
            function updateBalance(newBalance) {
                userBalance = newBalance;
                document.getElementById('balance').textContent = newBalance;
            }
            
            function placeBet(color, amount) {
                if (isSpinning) return;
                if (userBalance < amount) {
                    document.getElementById('game-result').innerHTML = '<p>❌ Insufficient balance!</p>';
                    return;
                }
                
                isSpinning = true;
                document.getElementById('game-result').innerHTML = '<p>🎰 Spinning...</p>';
                
                // Simulate API call
                spinRoulette(color, amount);
            }
            
            function spinRoulette(betColor, betAmount) {
                // Start wheel animation
                const wheel = document.getElementById('wheel');
                wheel.classList.add('spinning');
                
                setTimeout(() => {
                    // Generate result
                    const resultNumber = Math.floor(Math.random() * 37); // 0-36
                    const resultColor = getNumberColor(resultNumber);
                    
                    // Update wheel center
                    document.getElementById('result-number').textContent = resultNumber;
                    
                    // Calculate winnings
                    const won = betColor === resultColor;
                    let winnings = 0;
                    
                    if (won) {
                        if (resultColor === 'green') {
                            winnings = betAmount * 36;
                        } else {
                            winnings = betAmount * 2;
                        }
                        updateBalance(userBalance + winnings - betAmount);
                    } else {
                        updateBalance(userBalance - betAmount);
                    }
                    
                    // Show result
                    const colorEmoji = resultColor === 'red' ? '🔴' : resultColor === 'black' ? '⚫' : '🟢';
                    const resultText = won 
                        ? `🎉 YOU WON! ${colorEmoji} ${resultNumber}<br>Winnings: ${winnings}⭐` 
                        : `😔 You lost! ${colorEmoji} ${resultNumber}<br>Loss: ${betAmount}⭐`;
                    
                    document.getElementById('game-result').
