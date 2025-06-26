const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcrypt');

class Database {
    constructor() {
        this.db = null;
        this.initialized = false;
    }

    async init() {
        return new Promise((resolve, reject) => {
            // Для продакшена используйте файл базы данных
            this.db = new sqlite3.Database('./database.db', (err) => {
                if (err) {
                    console.error('Ошибка подключения к базе данных:', err);
                    reject(err);
                    return;
                }
                console.log('База данных подключена успешно');
                this.createTables().then(resolve).catch(reject);
            });
        });
    }

    async createTables() {
        return new Promise((resolve, reject) => {
            this.db.serialize(() => {
                let tablesCreated = 0;
                const totalTables = 3;

                const checkComplete = () => {
                    tablesCreated++;
                    if (tablesCreated === totalTables) {
                        this.initialized = true;
                        console.log('Все таблицы созданы успешно');
                        resolve();
                    }
                };

                // Таблица пользователей
                this.db.run(`
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        balance INTEGER DEFAULT 1000,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                `, (err) => {
                    if (err) {
                        console.error('Ошибка создания таблицы users:', err);
                        reject(err);
                    } else {
                        console.log('Таблица users создана');
                        checkComplete();
                    }
                });

                // Таблица игр
                this.db.run(`
                    CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        result TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                `, (err) => {
                    if (err) {
                        console.error('Ошибка создания таблицы games:', err);
                        reject(err);
                    } else {
                        console.log('Таблица games создана');
                        checkComplete();
                    }
                });

                // Таблица ставок
                this.db.run(`
                    CREATE TABLE IF NOT EXISTS bets (
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
                `, (err) => {
                    if (err) {
                        console.error('Ошибка создания таблицы bets:', err);
                        reject(err);
                    } else {
                        console.log('Таблица bets создана');
                        checkComplete();
                    }
                });
            });
        });
    }

    isReady() {
        return this.initialized && this.db;
    }

    async createUser(username, password) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            const hashedPassword = bcrypt.hashSync(password, 10);
            this.db.run(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                [username, hashedPassword],
                function(err) {
                    if (err) {
                        console.error('Ошибка создания пользователя:', err);
                        reject(err);
                    } else {
                        console.log('Пользователь создан с ID:', this.lastID);
                        resolve({ id: this.lastID, username });
                    }
                }
            );
        });
    }

    async getUser(username) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.get(
                'SELECT * FROM users WHERE username = ?',
                [username],
                (err, row) => {
                    if (err) {
                        console.error('Ошибка получения пользователя:', err);
                        reject(err);
                    } else {
                        resolve(row);
                    }
                }
            );
        });
    }

    async getUserById(id) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.get(
                'SELECT id, username, balance FROM users WHERE id = ?',
                [id],
                (err, row) => {
                    if (err) {
                        console.error('Ошибка получения пользователя по ID:', err);
                        reject(err);
                    } else {
                        resolve(row);
                    }
                }
            );
        });
    }

    async updateBalance(userId, newBalance) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.run(
                'UPDATE users SET balance = ? WHERE id = ?',
                [newBalance, userId],
                (err) => {
                    if (err) {
                        console.error('Ошибка обновления баланса:', err);
                        reject(err);
                    } else {
                        resolve();
                    }
                }
            );
        });
    }

    async createGame(result) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.run(
                'INSERT INTO games (result) VALUES (?)',
                [result],
                function(err) {
                    if (err) {
                        console.error('Ошибка создания игры:', err);
                        reject(err);
                    } else {
                        console.log('Игра создана с ID:', this.lastID);
                        resolve(this.lastID);
                    }
                }
            );
        });
    }

    async getLastGames(limit = 10) {
        if (!this.isReady()) {
            return [];
        }

        return new Promise((resolve, reject) => {
            this.db.all(
                'SELECT * FROM games ORDER BY timestamp DESC LIMIT ?',
                [limit],
                (err, rows) => {
                    if (err) {
                        console.error('Ошибка получения истории игр:', err);
                        resolve([]);
                    } else {
                        resolve(rows || []);
                    }
                }
            );
        });
    }

    async createBet(userId, gameId, color, amount) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.run(
                'INSERT INTO bets (user_id, game_id, color, amount) VALUES (?, ?, ?, ?)',
                [userId, gameId, color, amount],
                function(err) {
                    if (err) {
                        console.error('Ошибка создания ставки:', err);
                        reject(err);
                    } else {
                        console.log('Ставка создана с ID:', this.lastID);
                        resolve(this.lastID);
                    }
                }
            );
        });
    }

    async updateBetResult(betId, won, winnings) {
        if (!this.isReady()) {
            throw new Error('База данных не инициализирована');
        }

        return new Promise((resolve, reject) => {
            this.db.run(
                'UPDATE bets SET won = ?, winnings = ? WHERE id = ?',
                [won, winnings, betId],
                (err) => {
                    if (err) {
                        console.error('Ошибка обновления результата ставки:', err);
                        reject(err);
                    } else {
                        resolve();
                    }
                }
            );
        });
    }

    async getUserBets(userId, limit = 20) {
        if (!this.isReady()) {
            return [];
        }

        return new Promise((resolve, reject) => {
            this.db.all(`
                SELECT b.*, g.result, g.timestamp as game_time 
                FROM bets b 
                JOIN games g ON b.game_id = g.id 
                WHERE b.user_id = ? 
                ORDER BY b.timestamp DESC 
                LIMIT ?
            `, [userId, limit], (err, rows) => {
                if (err) {
                    console.error('Ошибка получения ставок пользователя:', err);
                    resolve([]);
                } else {
                    resolve(rows || []);
                }
            });
        });
    }

    async getCurrentGameBets(gameId) {
        if (!this.isReady()) {
            return [];
        }

        return new Promise((resolve, reject) => {
            this.db.all(`
                SELECT b.color, b.amount, u.username 
                FROM bets b 
                JOIN users u ON b.user_id = u.id 
                WHERE b.game_id = ?
            `, [gameId], (err, rows) => {
                if (err) {
                    console.error('Ошибка получения ставок текущей игры:', err);
                    resolve([]);
                } else {
                    resolve(rows || []);
                }
            });
        });
    }
}

module.exports = Database;
