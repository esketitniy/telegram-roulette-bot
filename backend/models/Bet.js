const mongoose = require('mongoose');

const betSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  gameId: {
    type: String,
    required: true
  },
  betType: {
    type: String,
    required: true,
    enum: ['red', 'black', 'green']
  },
  amount: {
    type: Number,
    required: true,
    min: 1
  },
  multiplier: {
    type: Number,
    required: true
  },
  result: {
    type: String,
    enum: ['win', 'lose', 'pending'],
    default: 'pending'
  },
  winAmount: {
    type: Number,
    default: 0
  },
  createdAt: {
    type: Date,
    default: Date.now
  }
});

module.exports = mongoose.model('Bet', betSchema);
