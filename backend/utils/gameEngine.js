const Game = require('../models/Game');
const Bet = require('../models/Bet');
const User = require('../models/User');

class GameEngine {
  constructor(io) {
    this.io = io;
    this.gameState = {
      phase: 'betting', // 'betting', 'spinning', 'result'
      timeLeft: 25,
      currentGameId: null,
      bets: [],
      history: [],
      totalBets: { red: 0, black: 0, green: 0 }
    };
    
    this.sectors = [
      { number: 0, color: 'green' },
      { number: 1, color: 'red' },
      { number: 2, color: 'black' },
      { number: 3, color: 'red' },
      { number: 4, color: 'black' },
      { number: 5, color: 'red' },
      { number: 6, color: 'black' },
      { number: 7, color: 'red' },
      { number: 8, color: 'black' },
      { number: 9, color: 'red' },
      { number: 10, color: 'black' },
      { number: 11, color: 'red' },
      { number: 12, color: 'black' },
      { number: 13, color: 'red' },
      { number: 14, color: 'black' }
    ];

    this.minBet = 1;
    this.maxBet = 1000;
    this.multipliers = { red: 2, black: 2, green: 14 };
    
    this.startGameLoop();
    this.loadGameHistory();
  }

  async startGameLoop() {
    setInterval(() => {
      this.gameState.timeLeft--;
      
      if (this.gameState.timeLeft <= 0) {
        if (this.gameState.phase === 'betting') {
          this.startSpinning();
        } else if (this.gameState.phase === 'spinning') {
          this.showResult();
        } else if (this.gameState.phase === 'result') {
          this.startNewRound();
        }
      }
      
      this.io.to('game-room').emit('game-state', this.gameState);
    }, 1000);
  }

  async startSpinning() {
    this.gameState.phase = 'spinning';
    this.gameState.timeLeft = 5;
    this.gameState.currentGameId = this.generateGameId();
    
    // Close betting
    this.io.to('game-room').emit('betting-closed');
  }

  async showResult() {
    const winningNumber = Math.floor(Math.random() * 15);
    const winningColor = this.sectors[winningNumber].color;
    
    this.gameState.phase = 'result';
    this.gameState.timeLeft = 5;
    this.gameState.result = { number: winningNumber, color: winningColor };
    
    // Save game result
    await this.saveGameResult(winningNumber, winningColor);
    
    // Process bets
    await this.processBets(winningColor);
    
    // Update history
    this.gameState.history.unshift({
      gameId: this.gameState.currentGameId,
      result: winningColor,
      number: winningNumber,
      timestamp: new Date()
    });
    
    if (this.gameState.history.length > 20) {
      this.gameState.history.pop();
    }
    
    this.io.to('game-room').emit('game-result', {
      number: winningNumber,
      color: winningColor,
      gameId: this.gameState.currentGameId
    });
  }

  async startNewRound() {
    this.gameState.phase = 'betting';
    this.gameState.timeLeft = 25;
    this.gameState.bets = [];
    this.gameState.totalBets = { red: 0, black: 0, green: 0 };
    this.gameState.result = null;
    
    this.io.to('game-room').emit('new-round');
  }

  async placeBet(userId, betData) {
    if (this.gameState.phase !== 'betting') {
      return { success: false, message: 'Betting is closed' };
    }

    const { betType, amount } = betData;
    
    if (amount < this.minBet || amount > this.maxBet) {
      return { success: false, message: `Bet must be between ${this.minBet} and ${this.maxBet}` };
    }

    if (!['red', 'black', 'green'].includes(betType)) {
      return { success: false, message: 'Invalid bet type' };
    }

    try {
      const user = await User.findById(userId);
      if (!user) {
        return { success: false, message: 'User not found' };
      }

      if (user.balance < amount) {
        return { success: false, message: 'Insufficient balance' };
      }

      // Check if user already has 2 bets in current round
      const userBetsInRound = this.gameState.bets.filter(bet => bet.userId.toString() === userId);
      if (userBetsInRound.length >= 2) {
        return { success: false, message: 'Maximum 2 bets per round' };
      }

      // Deduct from balance
      user.balance -= amount;
      await user.save();

      // Create bet
      const bet = new Bet({
        userId,
        gameId: this.gameState.currentGameId || this.generateGameId(),
        betType,
        amount,
        multiplier: this.multipliers[betType]
      });

      await bet.save();

      // Add to current game state
      this.gameState.bets.push({
        userId,
        username: user.username,
        betType,
        amount,
        multiplier: this.multipliers[betType]
      });

      this.gameState.totalBets[betType] += amount;

      return {
        success: true,
        betInfo: {
          userId,
          username: user.username,
          betType,
          amount,
          balance: user.balance
        }
      };
    } catch (error) {
      console.error('Error placing bet:', error);
      return { success: false, message: 'Failed to place bet' };
    }
  }

  async processBets(winningColor) {
    const bets = await Bet.find({ 
      gameId: this.gameState.currentGameId,
      result: 'pending'
    }).populate('userId');

    for (const bet of bets) {
      if (bet.betType === winningColor) {
        // Winning bet
        bet.result = 'win';
        bet.winAmount = bet.amount * bet.multiplier;
        
        // Add winnings to user balance
        const user = await User.findById(bet.userId);
        user.balance += bet.winAmount;
        user.totalWins += 1;
        await user.save();
        
        this.io.to('game-room').emit('bet-won', {
          userId: bet.userId._id,
          amount: bet.winAmount,
          betType: bet.betType
        });
      } else {
        // Losing bet
        bet.result = 'lose';
        bet.winAmount = 0;
        
        const user = await User.findById(bet.userId);
        user.totalLosses += 1;
        await user.save();
      }
      
      await bet.save();
    }
  }

  async saveGameResult(winningNumber, winningColor) {
    const game = new Game({
      gameId: this.gameState.currentGameId,
      result: winningColor,
      winningNumber,
      totalBets: this.gameState.totalBets.red + this.gameState.totalBets.black + this.gameState.totalBets.green,
      redBets: this.gameState.totalBets.red,
      blackBets: this.gameState.totalBets.black,
      greenBets: this.gameState.totalBets.green
    });
    
    await game.save();
  }

  async loadGameHistory() {
    const games = await Game.find().sort({ createdAt: -1 }).limit(20);
    this.gameState.history = games.map(game => ({
      gameId: game.gameId,
      result: game.result,
      number: game.winningNumber,
      timestamp: game.createdAt
    }));
  }

  generateGameId() {
    return Date.now().toString() + Math.random().toString(36).substr(2, 9);
  }

  getGameState() {
    return this.gameState;
  }
}

module.exports = GameEngine;
