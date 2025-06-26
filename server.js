const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');
const cors = require('cors');
const Database = require('./database');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Инициализируем базу данных
const db = new Database();
let dbInitialized = false;

const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-in-production';
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Игровые переменные
let gameState = {
    phase: 'betting',
    timeLeft: 30,
    currentGameId: null,
    bets: []
};

const colors = ['red', 'black', 'green'];
const colorMultipliers = { red: 2, black: 2, green: 14 };

// Middleware для проверки JWT
const authenticateToken = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
        return res.sendStatus(401);
    }

    jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
};

// API маршруты
app.post('/api/register', async (req, res) => {
    try {
        if (!dbInitialized) {
            return res.status(503).json({ error: 'Сервер еще не готов, попробуйте через несколько секунд' });
        }

        const { username, password } = req.body;
        
        console.log('Попытка регистрации:', username);
        
        if (!username || !password) {
            return res.status(400).json({ error: 'Логин и пароль обязательны' });
        }

        if (password.length < 6) {
            return res.status(400).json({ error: 'Пароль должен содержать минимум 6 символов' });
        }

        const user = await db.createUser(username, password);
        const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET);
        
        console.log('Пользователь успешно зарегистрирован:', user.id);
        res.json({ token, user: { id: user.id, username: user.username, balance: 1000 } });
    } catch (error) {
        console.error('Ошибка регистрации:', error);
        if (error.code === 'SQLITE_CONSTRAINT') {
            res.status(400).json({ error: 'Пользователь с таким логином уже существует' });
        } else {
            res.status(500).json({ error: 'Ошибка сервера: ' + error.message });
        }
    }
});

app.post('/api/login', async (req, res) => {
    try {
        if (!dbInitialized) {
            return res.status(503).json({ error: 'Сервер еще не готов, попробуйте через несколько секунд' });
        }

        const { username, password } = req.body;
        
        console.log('Попытка входа:', username);
        
        const user = await db.getUser(username);

        if (!user || !bcrypt.compareSync(password, user.password)) {
            return res.status(401).json({ error: 'Неверный логин или пароль' });
        }

        const token = jwt.sign({ id: user.id, username: user.username }, JWT_SECRET);
        
        console.log('Пользователь успешно вошел:', user.id);
        res.json({ 
            token, 
            user: { 
                id: user.id, 
                username: user.username, 
                balance: user.balance 
            } 
        });
    } catch (error) {
        console.error('Ошибка входа:', error);
        res.status(500).json({ error: 'Ошибка сервера: ' + error.message });
    }
});

app.get('/api/profile', authenticateToken, async (req, res) => {
    try {
        if (!dbInitialized) {
            return res.status(503).json({ error: 'Сервер еще не готов' });
        }

        const user = await db.getUserById(req.user.id);
        const bets = await db.getUserBets(req.user.id);
        res.json({ user, bets });
    } catch (error) {
        console.error('Ошибка получения профиля:', error);
        res.status(500).json({ error: 'Ошибка сервера: ' + error.message });
    }
});

app.get('/api/history', async (req, res) => {
    try {
        const games = await db.getLastGames();
        res.json(games);
    } catch (error) {console.error('Ошибка получения истории:', error);
        res.status(500).json({ error: 'Ошибка сервера: ' + error.message });
    }
});

// WebSocket обработка
io.on('connection', (socket) => {
    console.log('Пользователь подключился:', socket.id);

    // Отправка текущего состояния игры
    socket.emit('gameState', gameState);

    // Обработка ставок
    socket.on('placeBet', async (data) => {
        try {
            if (!dbInitialized) {
                socket.emit('error', 'Сервер еще не готов');
                return;
            }

            const { token, color, amount } = data;
            const decoded = jwt.verify(token, JWT_SECRET);
            const user = await db.getUserById(decoded.id);

            if (!user) {
                socket.emit('error', 'Пользователь не найден');
                return;
            }

            if (gameState.phase !== 'betting') {
                socket.emit('error', 'Ставки сейчас не принимаются');
                return;
            }

            if (amount <= 0 || amount > user.balance) {
                socket.emit('error', 'Недостаточно средств');
                return;
            }

            if (!colors.includes(color)) {
                socket.emit('error', 'Неверный цвет');
                return;
            }

            // Создание ставки (временная, будет сохранена в БД позже)
            const bet = {
                id: Date.now() + Math.random(), // Временный ID
                username: user.username,
                color,
                amount,
                userId: decoded.id
            };

            gameState.bets.push(bet);

            // Обновление баланса
            await db.updateBalance(decoded.id, user.balance - amount);

            // Уведомление всех о новой ставке
            io.emit('newBet', bet);
            
            // Обновление баланса пользователя
            socket.emit('balanceUpdate', user.balance - amount);

        } catch (error) {
            console.error('Ошибка при размещении ставки:', error);
            socket.emit('error', 'Ошибка при размещении ставки');
        }
    });

    socket.on('disconnect', () => {
        console.log('Пользователь отключился:', socket.id);
    });
});

// Игровой цикл
async function gameLoop() {
    if (!dbInitialized) {
        console.log('База данных не готова, пропускаем игровой цикл');
        setTimeout(gameLoop, 5000);
        return;
    }

    try {
        // Фаза ставок (30 секунд)
        gameState.phase = 'betting';
        gameState.timeLeft = 30;
        gameState.currentGameId = Date.now(); // Временный ID
        gameState.bets = [];

        console.log('Начало новой игры, фаза ставок');
        io.emit('gameState', gameState);

        const bettingInterval = setInterval(() => {
            gameState.timeLeft--;
            io.emit('timeUpdate', gameState.timeLeft);

            if (gameState.timeLeft <= 0) {
                clearInterval(bettingInterval);
                spinRoulette();
            }
        }, 1000);
    } catch (error) {
        console.error('Ошибка в игровом цикле:', error);
        setTimeout(gameLoop, 5000);
    }
}

async function spinRoulette() {
    try {
        // Фаза вращения (10 секунд)
        gameState.phase = 'spinning';
        gameState.timeLeft = 10;

        console.log('Начало вращения рулетки');
        io.emit('gameState', gameState);
        io.emit('spinStart');

        setTimeout(async () => {
            try {
                // Генерация результата
                const random = Math.random();
                let result;
                
                if (random < 0.02) { // 2% для зеленого
                    result = 'green';
                } else if (random < 0.51) { // 49% для красного
                    result = 'red';
                } else { // 49% для черного
                    result = 'black';
                }

                console.log('Результат рулетки:', result);

                // Сохранение игры в БД
                const gameId = await db.createGame(result);

                // Сохранение ставок в БД и обработка результатов
                await processBets(result, gameId);

                gameState.phase = 'result';
                io.emit('spinResult', result);
                io.emit('gameState', gameState);

                // Пауза перед новой игрой
                setTimeout(() => {
                    gameLoop();
                }, 5000);

            } catch (error) {
                console.error('Ошибка при обработке результата:', error);
                // Перезапуск игрового цикла в случае ошибки
                setTimeout(gameLoop, 5000);
            }
        }, 10000);
    } catch (error) {
        console.error('Ошибка при запуске рулетки:', error);
        setTimeout(gameLoop, 5000);
    }
}

async function processBets(result, gameId) {
    try {
        const processedBets = [];

        for (const bet of gameState.bets) {
            try {
                // Сохраняем ставку в БД
                const betId = await db.createBet(bet.userId, gameId, bet.color, bet.amount);
                
                const won = bet.color === result;
                const winnings = won ? bet.amount * colorMultipliers[bet.color] : 0;

                // Обновление результата ставки в БД
                await db.updateBetResult(betId, won, winnings);

                if (won) {
                    // Обновление баланса пользователя
                    const user = await db.getUserById(bet.userId);
                    if (user) {
                        await db.updateBalance(bet.userId, user.balance + winnings);
                    }
                }

                processedBets.push({
                    ...bet,
                    won,
                    winnings
                });
            } catch (error) {
                console.error('Ошибка обработки ставки:', error);
            }
        }

        // Отправка результатов всем пользователям
        io.emit('betsResult', { result, bets: processedBets });
    } catch (error) {
        console.error('Ошибка при обработке ставок:', error);
    }
}

// Инициализация базы данных и запуск сервера
async function initializeApp() {
    try {
        console.log('Инициализация базы данных...');
        await db.init();
        dbInitialized = true;
        console.log('База данных инициализирована успешно');
        
        // Запуск игрового цикла после инициализации БД
        console.log('Запуск игрового цикла...');
        gameLoop();
        
    } catch (error) {
        console.error('Ошибка инициализации приложения:', error);
        process.exit(1);
    }
}

// Запуск сервера
server.listen(PORT, () => {
    console.log(`Сервер запущен на порту ${PORT}`);
    initializeApp();
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('Получен сигнал SIGINT, завершение работы...');
    if (db.db) {
        db.db.close((err) => {
            if (err) {
                console.error('Ошибка закрытия базы данных:', err);
            } else {
                console.log('База данных закрыта');
            }
            process.exit(0);
        });
    } else {
        process.exit(0);
    }
});

process.on('SIGTERM', () => {
    console.log('Получен сигнал SIGTERM, завершение работы...');
    if (db.db) {
        db.db.close((err) => {
            if (err) {
                console.error('Ошибка закрытия базы данных:', err);
            } else {
                console.log('База данных закрыта');
            }
            process.exit(0);
        });
    } else {
        process.exit(0);
    }
});
