const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');
const http = require('http');
const socketIo = require('socket.io');
const rateLimit = require('express-rate-limit');
const helmet = require('helmet');
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: process.env.FRONTEND_URL || "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

// Middleware
app.use(helmet());
app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:3000"
}));
app.use(express.json());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

// Database connection
const pool = new Pool({
  connectionString: 'postgresql://admin:aLqNou9NGyaVk0g8roYnBsmPXDSiLz9R@dpg-d1ftqqali9vc739vuieg-a.oregon-postgres.render.com/roulette_jnfa',
  ssl: {
    rejectUnauthorized: false
  }
});

// JWT Secret
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-this';

// Roulette configuration
const ROULETTE_CONFIG = {
  RED_COUNT: 7,
  BLACK_COUNT: 7,
  GREEN_COUNT: 1,
  TOTAL_SECTORS: 15,
  ROUND_DURATION: 25000, // 25 seconds
  BETTING_DURATION: 20000, // 20 seconds for betting
  SPIN_DURATION: 5000, // 5 seconds for spinning
  PAYOUTS: {
    RED: 2,
    BLACK: 2,
    GREEN: 14
  }
};

// Game state
let gameState = {
  phase: 'BETTING', // BETTING, SPINNING, RESULT
  timeLeft: ROULETTE_CONFIG.BETTING_DURATION,
  currentBets: [],
  roundId: 1,
  result: null,
  history: []
};

// Initialize database tables
async function initDatabase() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        balance DECIMAL(10,2) DEFAULT 1000.00,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS bets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        round_id INTEGER NOT NULL,
        color VARCHAR(10) NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        result VARCHAR(10),
        payout DECIMAL(10,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS rounds (
        id SERIAL PRIMARY KEY,
        result_color VARCHAR(10) NOT NULL,
        result_sector INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    console.log('Database initialized successfully');
  } catch (error) {
    console.error('Database initialization error:', error);
  }
}

// Authentication middleware
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ error: 'Invalid token' });
    }
    req.user = user;
    next();
  });
};

// Routes
app.post('/api/register', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password required' });
    }

    if (password.length < 6) {
      return res.status(400).json({ error: 'Password must be at least 6 characters' });
    }

    const existingUser = await pool.query('SELECT id FROM users WHERE username = $1', [username]);
    if (existingUser.rows.length > 0) {
      return res.status(400).json({ error: 'Username already exists' });
    }

    const hashedPassword = await bcrypt.hash(password, 12);
    const result = await pool.query(
      'INSERT INTO users (username, password) VALUES ($1, $2) RETURNING id, username, balance',
      [username, hashedPassword]
    );

    const token = jwt.sign({ userId: result.rows[0].id, username }, JWT_SECRET);
    
    res.json({
      token,
      user: {
        id: result.rows[0].id,
        username: result.rows[0].username,
        balance: result.rows[0].balance
      }
    });
  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ error: 'Server error' });
  }
});

app.post('/api/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    const result = await pool.query('SELECT * FROM users WHERE username = $1', [username]);
    if (result.rows.length === 0) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }

    const user = result.rows[0];
    const isValidPassword = await bcrypt.compare(password, user.password);
    if (!isValidPassword) {
      return res.status(400).json({ error: 'Invalid credentials' });
    }

    const token = jwt.sign({ userId: user.id, username: user.username }, JWT_SECRET);
    
    res.json({
      token,
      user: {
        id: user.id,
        username: user.username,
        balance: user.balance
      }
    });
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Server error' });
  }
});

app.get('/api/profile', authenticateToken, async (req, res) => {
  try {
    const userResult = await pool.query('SELECT id, username, balance FROM users WHERE id = $1', [req.user.userId]);
    const user = userResult.rows[0];

    const betsResult = await pool.query(
      'SELECT * FROM bets WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50',
      [req.user.userId]
    );

    const stats = await pool.query(`
      SELECT 
        COUNT(*) as total_bets,
        SUM(amount) as total_wagered,
        SUM(payout) as total_won,
        SUM(payout - amount) as net_profit
      FROM bets WHERE user_id = $1
    `, [req.user.userId]);

    res.json({
      user,
      bets: betsResult.rows,
      stats: stats.rows[0]
    });
  } catch (error) {
    console.error('Profile error:', error);
    res.status(500).json({ error: 'Server error' });
  }
});

app.get('/api/game-state', (req, res) => {
  res.json(gameState);
});

app.get('/api/history', async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT * FROM rounds ORDER BY created_at DESC LIMIT 20'
    );
    res.json(result.rows);
  } catch (error) {
    console.error('History error:', error);
    res.status(500).json({ error: 'Server error' });
  }
});

// Socket.IO for real-time communication
io.on('connection', (socket) => {
  console.log('User connected:', socket.id);

  // Send current game state
  socket.emit('gameState', gameState);

  socket.on('placeBet', async (data) => {
    try {
      const { token, color, amount } = data;
      
      if (gameState.phase !== 'BETTING') {
        socket.emit('betError', 'Betting is closed');
        return;
      }

      const decoded = jwt.verify(token, JWT_SECRET);
      const userId = decoded.userId;

      // Validate bet
      if (!['RED', 'BLACK', 'GREEN'].includes(color)) {
        socket.emit('betError', 'Invalid color');
        return;
      }

      if (amount < 1 || amount > 1000) {
        socket.emit('betError', 'Bet amount must be between 1 and 1000');
        return;
      }

      // Check user balance
      const userResult = await pool.query('SELECT balance FROM users WHERE id = $1', [userId]);
      if (userResult.rows.length === 0 || userResult.rows[0].balance < amount) {
        socket.emit('betError', 'Insufficient balance');
        return;
      }

      // Check if user already has 2 bets in current round
      const existingBets = gameState.currentBets.filter(bet => bet.userId === userId);
      if (existingBets.length >= 2) {
        socket.emit('betError', 'Maximum 2 bets per round');
        return;
      }

      // Deduct balance
      await pool.query('UPDATE users SET balance = balance - $1 WHERE id = $2', [amount, userId]);

      // Add bet to current round
      const bet = {
        userId,
        username: decoded.username,
        color,
        amount,
        roundId: gameState.roundId
      };

      gameState.currentBets.push(bet);

      // Broadcast updated bets
      io.emit('betsUpdate', gameState.currentBets);
      socket.emit('betSuccess', bet);

    } catch (error) {
      console.error('Bet error:', error);
      socket.emit('betError', 'Invalid token or server error');
    }
  });

  socket.on('disconnect', () => {
    console.log('User disconnected:', socket.id);
  });
});

// Game loop
function generateRouletteResult() {
  const sectors = [];
  
  // Add red sectors (1-7)
  for (let i = 1; i <= ROULETTE_CONFIG.RED_COUNT; i++) {
    sectors.push({ number: i, color: 'RED' });
  }
  
  // Add black sectors (8-14)
  for (let i = 8; i <= 14; i++) {
    sectors.push({ number: i, color: 'BLACK' });
  }
  
  // Add green sector (0)
  sectors.push({ number: 0, color: 'GREEN' });

  const randomIndex = Math.floor(Math.random() * sectors.length);
  return sectors[randomIndex];
}

async function processRound() {
  try {
    // Generate result
    const result = generateRouletteResult();
    gameState.result = result;

    // Save round to database
    await pool.query(
      'INSERT INTO rounds (result_color, result_sector) VALUES ($1, $2)',
      [result.color, result.number]
    );

    // Process bets
    for (const bet of gameState.currentBets) {
      let payout = 0;
      let betResult = 'LOSE';

      if (bet.color === result.color) {
        betResult = 'WIN';
        payout = bet.amount * ROULETTE_CONFIG.PAYOUTS[result.color];
        
        // Add winnings to user balance
        await pool.query('UPDATE users SET balance = balance + $1 WHERE id = $2', [payout, bet.userId]);
      }

      // Save bet to database
      await pool.query(
        'INSERT INTO bets (user_id, round_id, color, amount, result, payout) VALUES ($1, $2, $3, $4, $5, $6)',
        [bet.userId, gameState.roundId, bet.color, bet.amount, betResult, payout]
      );
    }

    // Add to history
    gameState.history.unshift({
      roundId: gameState.roundId,
      result: result,
      timestamp: new Date()
    });

    if (gameState.history.length > 20) {
      gameState.history = gameState.history.slice(0, 20);
    }

    // Broadcast result
    io.emit('roundResult', {
      result,
      roundId: gameState.roundId,
      bets: gameState.currentBets
    });

    // Reset for next round
    setTimeout(() => {
      gameState.currentBets = [];
      gameState.roundId++;
      gameState.phase = 'BETTING';
      gameState.timeLeft = ROULETTE_CONFIG.BETTING_DURATION;
      gameState.result = null;

      io.emit('gameState', gameState);
      startGameTimer();
    }, 3000);

  } catch (error) {
    console.error('Process round error:', error);
  }
}

function startGameTimer() {
  const timer = setInterval(() => {
    gameState.timeLeft -= 1000;

    if (gameState.timeLeft <= 0) {
      clearInterval(timer);
      
      if (gameState.phase === 'BETTING') {
        gameState.phase = 'SPINNING';
        gameState.timeLeft = ROULETTE_CONFIG.SPIN_DURATION;
        
        io.emit('gameState', gameState);
        
        setTimeout(() => {
          processRound();
        }, ROULETTE_CONFIG.SPIN_DURATION);
      }
    } else {
      io.emit('gameState', gameState);
    }
  }, 1000);
}

// Start the game
initDatabase().then(() => {
  startGameTimer();
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
