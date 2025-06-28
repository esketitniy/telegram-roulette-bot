const mongoose = require('mongoose');

const gameSchema = new mongoose.Schema({
  gameId: {
    type: String,
    required: true,
    unique: true
  },
  result: {
    type: String,
    required: true,
    enum: ['red', 'black', 'green']
  },
  winningNumber: {
    type: Number,
    required: true,
    min: 0,
    max: 14
  },
  totalBets: {
    type: Number,
    default: 0
  },
  redBets: {
    type: Number,
    default: 0
  },
  blackBets: {
    type: Number,
    default: 0
  },
  greenBets: {
    type: Number,
    default: 0
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
});

module.exports = mongoose.model('Game', gameSchema);
