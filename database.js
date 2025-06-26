const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcrypt');

class Database {
    constructor() {
        this.db = new sqlite3.Database('./database.db'); // Для продакшена используйте файл
    }

    init() {
        // Создание таблиц
        this.db.serialize(() => {
            // Таблица пользователей
            this.db.run(`
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    balance INTEGER DEFAULT 1000,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            `);

            // Таблица игр
            this.db.run(`
                CREATE TABLE games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            `);

            // Таблица ставок
            this.db.run(`
                CREATE TABLE bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_id INTEGER,
                    color TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    won BOOLEAN DEFAULT FALSE,
                    winnings INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (game_id) REFERENCES games (id)
                )
            `);
        });
    }

    async createUser(username, password) {
        return new Promise((resolve, reject) => {
            const hashedPassword = bcrypt.hashSync(password, 10);
            this.db.run(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                [username, hashedPassword],
                function(err) {
                    if (err) reject(err);
                    else resolve({ id: this.lastID, username });
                }
            );
        });
    }

    async getUser(username) {
        return new Promise((resolve, reject) => {
            this.db.get(
                'SELECT * FROM users WHERE username = ?',
                [username],
                (err, row) => {
                    if (err) reject(err);
                    else resolve(row);
                }
            );
        });
    }

    async getUserById(id) {
        return new Promise((resolve, reject) => {
            this.db.get(
                'SELECT id, username, balance FROM users WHERE id = ?',
                [id],
                (err, row) => {
                    if (err) reject(err);
                    else resolve(row);
                }
            );
        });
    }

    async updateBalance(userId, newBalance) {
        return new Promise((resolve, reject) => {
            this.db.run(
                'UPDATE users SET balance = ? WHERE id = ?',
                [newBalance, userId],
                (err) => {
                    if (err) reject(err);
                    else resolve();
                }
            );
        });
    }

    async createGame(result) {
        return new Promise((resolve, reject) => {
            this.db.run(
                'INSERT INTO games (result) VALUES (?)',
                [result],
                function(err) {
                    if (err) reject(err);
                    else resolve(this.lastID);
                }
            );
        });
    }

    async getLastGames(limit = 10) {
        return new Promise((resolve, reject) => {
            this.db.all(
                'SELECT * FROM games ORDER BY timestamp DESC LIMIT ?',
                [limit],
                (err, rows) => {
                    if (err) reject(err);
                    else resolve(rows);
                }
            );
        });
    }

    async createBet(userId, gameId, color, amount) {
        return new Promise((resolve, reject) => {
            this.db.run(
                'INSERT INTO bets (user_id, game_id, color, amount) VALUES (?, ?, ?, ?)',
                [userId, gameId, color, amount],
                function(err) {
                    if (err) reject(err);
                    else resolve(this.lastID);
                }
            );
        });
    }

    async updateBetResult(betId, won, winnings) {
        return new Promise((resolve, reject) => {
            this.db.run(
                'UPDATE bets SET won = ?, winnings = ? WHERE id = ?',
                [won, winnings, betId],
                (err) => {
                    if (err) reject(err);
                    else resolve();
                }
            );
        });
    }

    async getUserBets(userId, limit = 20) {
        return new Promise((resolve, reject) => {
            this.db.all(`
                SELECT b.*, g.result, g.timestamp as game_time 
                FROM bets b 
                JOIN games g ON b.game_id = g.id 
                WHERE b.user_id = ? 
                ORDER BY b.timestamp DESC 
                LIMIT ?
            `, [userId, limit], (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });
    }

    async getCurrentGameBets(gameId) {
        return new Promise((resolve, reject) => {
            this.db.all(`
                SELECT b.color, b.amount, u.username 
                FROM bets b 
                JOIN users u ON b.user_id = u.id 
                WHERE b.game_id = ?
            `, [gameId], (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });
    }
}

module.exports = Database;
