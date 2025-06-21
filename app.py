from flask import Flask, render_template, request, jsonify
import sqlite3
import random
import json

app = Flask(__name__)

# Рулетка - европейская версия
ROULETTE_NUMBERS = {
    0: "green",
    **{i: "red" for i in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]},
    **{i: "black" for i in [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]}
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game')
def game():
    return render_template('game.html')

@app.route('/api/spin', methods=['POST'])
def spin_roulette():
    data = request.json
    user_id = data.get('user_id')
    bet_type = data.get('bet_type')  # 'red', 'black', 'green'
    bet_amount = data.get('bet_amount')
    
    # Проверяем баланс пользователя
    conn = sqlite3.connect('casino.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if not result or result[0] < bet_amount:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    # Генерируем результат
