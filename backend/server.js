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
app.use(helmet({
  contentSecurityPolicy: false
}));

app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:3000",
  credentials: true
}));

app.use(express.json({ limit: '10mb' }));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});
app.use('/api', limiter);

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://admin:aLqNou9NGyaVk0g8roYnBsmPXDSiLz9R@dpg-d1ftqqali9vc739vuieg-a.oregon-postgres.render.com/roulette_jnfa',
  ssl: process.env.NODE_ENV === 'production' ? {
    rejectUnauthorized: false
  } : false
});

// JWT Secret
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-change-this';

// Roulette configuration
const ROULETTE_CONFIG = {
  RED_COUNT: 7,
  BLACK_COUNT: 7,
  GREEN_COUNT: 1,
  TOTAL_SECTORS: 15,
  ROUND_DURATION: parseInt(process.env.ROUND_DURATION) || 25000, // 25 seconds
  BETTING_DURATION: parseInt(process.env.BETTING_DURATION) || 20000, // 20 seconds for betting
  SPIN_DURATION: parseInt(process.env.SPIN_DURATION) || 5000, // 5 seconds for spinning
  PAYOUTS: {
    RED: 2,
    BLACK: 2,
    GREEN: 14
  },
  MIN_BET: 1,
  MAX_BET: 1000,
  MAX_BETS_PER_ROUND: 2
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
    // Users table
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        balance DECIMAL(10,2) DEFAULT 1000.00,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Bets table
    await pool.query(`
      CREATE TABLE IF NOT EXISTS bets (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        round_id INTEGER NOT NULL,
        color VARCHAR(10) NOT NULL CHECK (color IN ('RED', 'BLACK', 'GREEN')),
        amount DECIMAL(10,2) NOT NULL CHECK (amount > 0),
        result VARCHAR(10) DEFAULT 'PENDING' CHECK (result IN ('WIN', 'LOSE', 'PENDING')),
        payout DECIMAL(10,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Rounds table
    await pool.query(`
      CREATE TABLE IF NOT EXISTS rounds (
        id SERIAL PRIMARY KEY,
        result_color VARCHAR(10) NOT NULL CHECK (result_color IN ('RED', 'BLACK', 'GREEN')),
        result_sector INTEGER NOT NULL CHECK (result_sector >= 0 AND result_sector <= 14),
        total_bets INTEGER DEFAULT 0,
        total_amount DECIMAL(10,2) DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Create indexes for better performance
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_bets_user_id ON bets(user_id)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_bets_round_id ON bets(round_id)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_rounds_created_at ON rounds(created_at DESC)`);

    console.log('✅ Database initialized successfully');
  } catch (error) {
    console.error('❌ Database initialization error:', error);
    process.exit(1);
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
      return res.status(403).json({ error: 'Invalid or expired token' });
    }
    req.user = user;
    next();
  });
};

// Validation middleware
const validateRegistration = (req, res, next) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password are required' });
  }

  if (username.length < 3 || username.length > 20) {
    return res.status(400).json({ error: 'Username must be between 3 and 20 characters' });
  }

  if (password.length < 6) {
    return res.status(400).json({ error: 'Password must be at least 6 characters long' });
  }

  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    return res.status(400).json({ error: 'Username can only contain letters, numbers, and underscores' });
  }

  next();
};

// Routes
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'OK', 
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    gameState: {
      phase: gameState.phase,
      roundId: gameState.roundId,
      activeBets: gameState.currentBets.length
    }
  });
});

app.post('/api/register', validateRegistration, async (req, res) => {
  const client = await pool.connect();
  
  try {
    await client.query('BEGIN');
    
    const { username, password } = req.body;

    // Check if username already exists
    const existingUser = await client.query(
      'SELECT id FROM users WHERE LOWER(username) = LOWER($1)', 
      [username]
    );
    
    if (existingUser.rows.length > 0) {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: 'Username already exists' });
    }

    // Hash password
    const saltRounds = 12;
    const hashedPassword = await bcrypt.hash(password, saltRounds);
    
    // Create user
    const result = await client.query(
      'INSERT INTO users (username, password, balance) VALUES ($1, $2, $3) RETURNING id, username, balance, created_at',
      [username, hashedPassword, 1000.00]
    );

    await client.query('COMMIT');

    const user = result.rows[0];
    const token = jwt.sign(
      { userId: user.id, username: user.username }, 
      JWT_SECRET,
      { expiresIn: '7d' }
    );
    
    res.status(201).json({
      message: 'User registered successfully',
      token,
      user: {
        id: user.id,
        username: user.username,
        balance: parseFloat(user.balance),
        createdAt: user.created_at
      }
    });

  } catch (error) {
    await client.query('ROLLBACK');
    console.error('Registration error:', error);
    res.status(500).json({ error: 'Internal server error during registration' });
  } finally {
    client.release();
  }
});

app.post('/api/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const result = await pool.query(
      'SELECT * FROM users WHERE LOWER(username) = LOWER($1)', 
      [username]
    );
    
    if (result.rows.length === 0) {
      return res.status(400).json({ error: 'Invalid username or password' });
    }

    const user = result.rows[0];
    const isValidPassword = await bcrypt.compare(password, user.password);
    
    if (!isValidPassword) {
      return res.status(400).json({ error: 'Invalid username or password' });
    }

    const token = jwt.sign(
      { userId: user.id, username: user.username }, 
      JWT_SECRET,
      { expiresIn: '7d' }
    );
    
    res.json({
      message: 'Login successful',
      token,
      user: {
        id: user.id,
        username: user.username,
        balance: parseFloat(user.balance)
      }
    });

  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Internal server error during login' });
  }
});

app.get('/api/profile', authenticateToken, async (req, res) => {
  try {
    // Get user data
    const userResult = await pool.query(
      'SELECT id, username, balance, created_at FROM users WHERE id = $1', 
      [req.user.userId]
    );
    
    if (userResult.rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    const user = userResult.rows[0];

    // Get user's betting history
    const betsResult = await pool.query(`
      SELECT 
        b.*,
        r.result_color as round_result_color,
        r.result_sector as round_result_sector
      FROM bets b
      LEFT JOIN rounds r ON b.round_id = r.id
      WHERE b.user_id = $1 
      ORDER BY b.created_at DESC 
      LIMIT 50
    `, [req.user.userId]);

    // Get user statistics
    const statsResult = await pool.query(`
      SELECT 
        COUNT(*) as total_bets,
        COALESCE(SUM(amount), 0) as total_wagered,
        COALESCE(SUM(payout), 0) as total_won,
        COALESCE(SUM(payout - amount), 0) as net_profit,
        COUNT(CASE WHEN result = 'WIN' THEN 1 END) as wins,
        COUNT(CASE WHEN result = 'LOSE' THEN 1 END) as losses
      FROM bets 
      WHERE user_id = $1
    `, [req.user.userId]);

    const stats = statsResult.rows[0];
    const winRate = stats.total_bets > 0 ? (stats.wins / stats.total_bets * 100).toFixed(2) : 0;

    res.json({
      user: {
        ...user,
        balance: parseFloat(user.balance)
      },
      bets: betsResult.rows.map(bet => ({
        ...bet,
        amount: parseFloat(bet.amount),
        payout: parseFloat(bet.payout)
      })),
      stats: {
          ...stats,
          total_wagered: parseFloat(stats.total_wagered),
          total_won: parseFloat(stats.total_won),
          net_profit: parseFloat(stats.net_profit),
          win_rate: parseFloat(winRate),
          total_bets: parseInt(stats.total_bets),
          wins: parseInt(stats.wins),
          losses: parseInt(stats.losses)
        }
      });

  } catch (error) {
    console.error('Profile error:', error);
    res.status(500).json({ error: 'Internal server error while fetching profile' });
  }
});

app.get('/api/game-state', (req, res) => {
  res.json({
    ...gameState,
    config: {
      minBet: ROULETTE_CONFIG.MIN_BET,
      maxBet: ROULETTE_CONFIG.MAX_BET,
      maxBetsPerRound: ROULETTE_CONFIG.MAX_BETS_PER_ROUND,
      payouts: ROULETTE_CONFIG.PAYOUTS
    }
  });
});

app.get('/api/history', async (req, res) => {
  try {
    const limit = Math.min(parseInt(req.query.limit) || 20, 100);
    const result = await pool.query(
      'SELECT * FROM rounds ORDER BY created_at DESC LIMIT $1',
      [limit]
    );
    
    res.json(result.rows.map(round => ({
      ...round,
      total_amount: parseFloat(round.total_amount)
    })));
  } catch (error) {
    console.error('History error:', error);
    res.status(500).json({ error: 'Failed to fetch game history' });
  }
});

// Socket.IO for real-time communication
const connectedUsers = new Map();

io.on('connection', (socket) => {
  console.log(`🔗 User connected: ${socket.id}`);

  // Send current game state immediately
  socket.emit('gameState', gameState);
  socket.emit('betsUpdate', gameState.currentBets);

  socket.on('placeBet', async (data) => {
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');

      const { token, color, amount } = data;
      
      // Validate game phase
      if (gameState.phase !== 'BETTING') {
        socket.emit('betError', 'Betting is currently closed');
        await client.query('ROLLBACK');
        return;
      }

      // Validate token
      let decoded;
      try {
        decoded = jwt.verify(token, JWT_SECRET);
      } catch (error) {
        socket.emit('betError', 'Invalid or expired token');
        await client.query('ROLLBACK');
        return;
      }

      const userId = decoded.userId;

      // Validate bet parameters
      if (!['RED', 'BLACK', 'GREEN'].includes(color)) {
        socket.emit('betError', 'Invalid color selection');
        await client.query('ROLLBACK');
        return;
      }

      const betAmount = parseFloat(amount);
      if (isNaN(betAmount) || betAmount < ROULETTE_CONFIG.MIN_BET || betAmount > ROULETTE_CONFIG.MAX_BET) {
        socket.emit('betError', `Bet amount must be between $${ROULETTE_CONFIG.MIN_BET} and $${ROULETTE_CONFIG.MAX_BET}`);
        await client.query('ROLLBACK');
        return;
      }

      // Check user balance
      const userResult = await client.query('SELECT balance FROM users WHERE id = $1', [userId]);
      if (userResult.rows.length === 0) {
        socket.emit('betError', 'User not found');
        await client.query('ROLLBACK');
        return;
      }

      const userBalance = parseFloat(userResult.rows[0].balance);
      if (userBalance < betAmount) {
        socket.emit('betError', 'Insufficient balance');
        await client.query('ROLLBACK');
        return;
      }

      // Check if user already has maximum bets in current round
      const existingBets = gameState.currentBets.filter(bet => bet.userId === userId);
      if (existingBets.length >= ROULETTE_CONFIG.MAX_BETS_PER_ROUND) {
        socket.emit('betError', `Maximum ${ROULETTE_CONFIG.MAX_BETS_PER_ROUND} bets per round allowed`);
        await client.query('ROLLBACK');
        return;
      }

      // Deduct balance
      await client.query(
        'UPDATE users SET balance = balance - $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2', 
        [betAmount, userId]
      );

      // Add bet to current round
      const bet = {
        userId,
        username: decoded.username,
        color,
        amount: betAmount,
        roundId: gameState.roundId,
        timestamp: new Date()
      };

      gameState.currentBets.push(bet);

      await client.query('COMMIT');

      // Broadcast updated bets to all clients
      io.emit('betsUpdate', gameState.currentBets);
      
      // Send success confirmation to the betting user
      socket.emit('betSuccess', {
        message: 'Bet placed successfully!',
        bet: bet,
        newBalance: userBalance - betAmount
      });

      console.log(`💰 Bet placed: ${decoded.username} - ${color} - $${betAmount}`);

    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Bet placement error:', error);
      socket.emit('betError', 'Failed to place bet. Please try again.');
    } finally {
      client.release();
    }
  });

  socket.on('getUserBalance', async (token) => {
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      const result = await pool.query('SELECT balance FROM users WHERE id = $1', [decoded.userId]);
      
      if (result.rows.length > 0) {
        socket.emit('balanceUpdate', parseFloat(result.rows[0].balance));
      }
    } catch (error) {
      console.error('Balance fetch error:', error);
    }
  });

  socket.on('disconnect', () => {
    console.log(`🔌 User disconnected: ${socket.id}`);
    connectedUsers.delete(socket.id);
  });
});

// Game logic functions
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
  const client = await pool.connect();
  
  try {
    await client.query('BEGIN');

    // Generate result
    const result = generateRouletteResult();
    gameState.result = result;

    console.log(`🎰 Round ${gameState.roundId} result: ${result.color} ${result.number}`);

    // Save round to database
    const roundResult = await client.query(
      'INSERT INTO rounds (id, result_color, result_sector, total_bets, total_amount) VALUES ($1, $2, $3, $4, $5) RETURNING *',
      [
        gameState.roundId,
        result.color, 
        result.number,
        gameState.currentBets.length,
        gameState.currentBets.reduce((sum, bet) => sum + bet.amount, 0)
      ]
    );

    // Process each bet
    const winningBets = [];
    const losingBets = [];
    
    for (const bet of gameState.currentBets) {
      let payout = 0;
      let betResult = 'LOSE';

      if (bet.color === result.color) {
        betResult = 'WIN';
        payout = bet.amount * ROULETTE_CONFIG.PAYOUTS[result.color];
        winningBets.push({ ...bet, payout });
        
        // Add winnings to user balance
        await client.query(
          'UPDATE users SET balance = balance + $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2', 
          [payout, bet.userId]
        );
      } else {
        losingBets.push(bet);
      }

      // Save bet to database
      await client.query(
        'INSERT INTO bets (user_id, round_id, color, amount, result, payout) VALUES ($1, $2, $3, $4, $5, $6)',
        [bet.userId, gameState.roundId, bet.color, bet.amount, betResult, payout]
      );
    }

    await client.query('COMMIT');

    // Add to history
    gameState.history.unshift({
      roundId: gameState.roundId,
      result: result,
      timestamp: new Date(),
      totalBets: gameState.currentBets.length,
      totalAmount: gameState.currentBets.reduce((sum, bet) => sum + bet.amount, 0)
    });

    // Keep only last 50 rounds in memory
    if (gameState.history.length > 50) {
      gameState.history = gameState.history.slice(0, 50);
    }

    // Broadcast result to all clients
    io.emit('roundResult', {
      result,
      roundId: gameState.roundId,
      winningBets,
      losingBets,
      totalBets: gameState.currentBets.length,
      totalAmount: gameState.currentBets.reduce((sum, bet) => sum + bet.amount, 0)
    });

    console.log(`✅ Round ${gameState.roundId} processed: ${winningBets.length} winners, ${losingBets.length} losers`);

    // Reset for next round after delay
    setTimeout(() => {
      gameState.currentBets = [];
      gameState.roundId++;
      gameState.phase = 'BETTING';
      gameState.timeLeft = ROULETTE_CONFIG.BETTING_DURATION;
      gameState.result = null;

      io.emit('gameState', gameState);
      io.emit('betsUpdate', []);
      
      console.log(`🎮 New round started: #${gameState.roundId}`);
      startGameTimer();
    }, 3000);

  } catch (error) {
    await client.query('ROLLBACK');
    console.error('❌ Process round error:', error);
    
    // Reset game state on error
    gameState.phase = 'BETTING';
    gameState.timeLeft = ROULETTE_CONFIG.BETTING_DURATION;
    gameState.result = null;
    io.emit('gameState', gameState);
    
    setTimeout(() => startGameTimer(), 5000);
  } finally {
    client.release();
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
        
        console.log(`🎲 Round ${gameState.roundId} - Spinning phase started`);
        io.emit('gameState', gameState);
        
        setTimeout(() => {
          processRound();
        }, ROULETTE_CONFIG.SPIN_DURATION);
      }
    } else {
      // Broadcast time updates every second
      io.emit('gameState', gameState);
    }
  }, 1000);
}

// Error handling
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// 404 handler
app.use('*', (req, res) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('🛑 SIGTERM received, shutting down gracefully...');
  server.close(() => {
    console.log('✅ HTTP server closed');
    pool.end(() => {
      console.log('✅ Database connection pool closed');
      process.exit(0);
    });
  });
});

process.on('SIGINT', async () => {
  console.log('🛑 SIGINT received, shutting down gracefully...');
  server.close(() => {
    console.log('✅ HTTP server closed');
    pool.end(() => {
      console.log('✅ Database connection pool closed');
      process.exit(0);
    });
  });
});

// Initialize and start server
async function startServer() {
  try {
    await initDatabase();
    
    const PORT = process.env.PORT || 5000;
    server.listen(PORT, () => {
      console.log(`🚀 Server running on port ${PORT}`);
      console.log(`🎰 Roulette game initialized`);
      console.log(`📊 Game config:`, ROULETTE_CONFIG);
      
      // Start the first game timer
      startGameTimer();
    });
  } catch (error) {
    console.error('❌ Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
