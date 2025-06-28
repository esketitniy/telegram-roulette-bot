const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const mongoose = require('mongoose');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
require('dotenv').config();

const authRoutes = require('./routes/auth');
const gameRoutes = require('./routes/game');
const userRoutes = require('./routes/user');
const GameEngine = require('./utils/gameEngine');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: process.env.FRONTEND_URL || "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.FRONTEND_URL || "http://localhost:3000",
  credentials: true
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100 // limit each IP to 100 requests per windowMs
});
app.use(limiter);

app.use(express.json());

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/game', gameRoutes);
app.use('/api/user', userRoutes);

// MongoDB connection
mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/roulette', {
  useNewUrlParser: true,
  useUnifiedTopology: true,
})
.then(() => console.log('MongoDB connected'))
.catch(err => console.error('MongoDB connection error:', err));

// Game engine
const gameEngine = new GameEngine(io);

// Socket.io connection handling
io.on('connection', (socket) => {
  console.log('New client connected');

  socket.on('join-game', (userId) => {
    socket.userId = userId;
    socket.join('game-room');
    
    // Send current game state
    socket.emit('game-state', gameEngine.getGameState());
  });

  socket.on('place-bet', async (betData) => {
    try {
      const result = await gameEngine.placeBet(socket.userId, betData);
      if (result.success) {
        socket.emit('bet-placed', result);
        io.to('game-room').emit('bet-update', result.betInfo);
      } else {
        socket.emit('bet-error', result.message);
      }
    } catch (error) {
      socket.emit('bet-error', 'Failed to place bet');
    }
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`);
});
