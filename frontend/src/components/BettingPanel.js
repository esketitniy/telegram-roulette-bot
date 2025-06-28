import React, { useState } from 'react';
import './BettingPanel.css';

const BettingPanel = ({ onPlaceBet, disabled, userBets, balance }) => {
  const [betAmount, setBetAmount] = useState(10);
  const [selectedColor, setSelectedColor] = useState('');

  const colors = [
    { id: 'RED', name: 'Red', payout: '2x', color: '#ff4444' },
    { id: 'BLACK', name: 'Black', payout: '2x', color: '#333333' },
    { id: 'GREEN', name: 'Green', payout: '14x', color: '#22aa22' }
  ];

  const betAmounts = [1, 5, 10, 25, 50, 100];

  const handlePlaceBet = () => {
    if (!selectedColor || betAmount <= 0 || userBets.length >= 2) return;
    
    onPlaceBet(selectedColor, betAmount);
    setSelectedColor('');
  };

  const canPlaceBet = () => {
    return !disabled && 
           selectedColor && 
           betAmount > 0 && 
           betAmount <= balance && 
           userBets.length < 2 &&
           betAmount >= 1 &&
           betAmount <= 1000;
  };

  return (
    <div className="betting-panel">
      <div className="betting-header">
        <h3>Place Your Bets</h3>
        <div className="bet-limits">
          Min: $1 | Max: $1000 | Your bets: {userBets.length}/2
        </div>
      </div>

      <div className="bet-amount-section">
        <label>Bet Amount:</label>
        <div className="amount-buttons">
          {betAmounts.map(amount => (
            <button
              key={amount}
              className={`amount-btn ${betAmount === amount ? 'active' : ''}`}
              onClick={() => setBetAmount(amount)}
              disabled={amount > balance}
            >
              ${amount}
            </button>
          ))}
        </div>
        <input
          type="number"
          value={betAmount}
          onChange={(e) => setBetAmount(Math.max(1, Math.min(1000, parseInt(e.target.value) || 1)))}
          min="1"
          max="1000"
          className="custom-amount"
        />
      </div>

      <div className="color-selection">
        <label>Select Color:</label>
        <div className="color-buttons">
          {colors.map(color => (
            <button
              key={color.id}
              className={`color-btn ${selectedColor === color.id ? 'selected' : ''}`}
              style={{ backgroundColor: color.color }}
              onClick={() => setSelectedColor(color.id)}
              disabled={disabled}
            >
              <span>{color.name}</span>
              <small>{color.payout}</small>
            </button>
          ))}
        </div>
      </div>

      <button
        className="place-bet-btn"
        onClick={handlePlaceBet}
        disabled={!canPlaceBet()}
      >
        {disabled ? 'Betting Closed' : 'Place Bet'}
      </button>

      {userBets.length > 0 && (
        <div className="user-bets">
          <h4>Your Bets This Round:</h4>
          {userBets.map((bet, index) => (
            <div key={index} className="user-bet">
              <span className={`bet-color ${bet.color.toLowerCase()}`}>
                {bet.color}
              </span>
              <span className="bet-amount">${bet.amount}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BettingPanel;
