import React from 'react';
import { Users, Coins } from 'lucide-react';
import './CurrentBets.css';

const CurrentBets = ({ bets, totalBets }) => {
  const getBetsByColor = (color) => {
    return bets.filter(bet => bet.betType === color);
  };

  const getTotalByColor = (color) => {
    return totalBets[color] || 0;
  };

  const colors = [
    { type: 'red', label: 'Red', color: '#e74c3c' },
    { type: 'black', label: 'Black', color: '#2c3e50' },
    { type: 'green', label: 'Green', color: '#27ae60' }
  ];

  const grandTotal = Object.values(totalBets).reduce((sum, amount) => sum + amount, 0);

  return (
    <div className="current-bets">
      <div className="bets-header">
        <div className="header-title">
          <Users size={20} />
          <h3>Current Bets</h3>
        </div>
        <div className="total-bets">
          <Coins size={16} />
          {grandTotal}
        </div>
      </div>

      <div className="bets-summary">
        {colors.map(({ type, label, color }) => (
          <div key={type} className="bet-summary-item">
            <div className="bet-summary-header">
              <div className="bet-summary-color">
                <div 
                  className="color-indicator" 
                  style={{ backgroundColor: color }}
                />
                <span>{label}</span>
              </div>
              <div className="bet-summary-total">
                {getTotalByColor(type)} coins
              </div>
            </div>
            <div className="bet-summary-count">
              {getBetsByColor(type).length} bets
            </div>
          </div>
        ))}
      </div>

      <div className="bets-list">
        <div className="bets-list-header">
          <h4>Recent Bets</h4>
        </div>
        
        {bets.length === 0 ? (
          <div className="no-bets">
            <p>No bets placed yet</p>
            <span>Be the first to place a bet!</span>
          </div>
        ) : (
          <div className="bets-items">
            {bets.slice(-10).reverse().map((bet, index) => (
              <div key={index} className={`bet-item bet-${bet.betType}`}>
                <div className="bet-player">
                  <div className="player-avatar">
                    {bet.username.charAt(0).toUpperCase()}
                  </div>
                  <div className="player-info">
                    <div className="player-name">{bet.username}</div>
                    <div className="bet-details">
                      {bet.amount} on {bet.betType.toUpperCase()}
                    </div>
                  </div>
                </div>
                <div className="bet-amount">
                  <Coins size={14} />
                  {bet.amount}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CurrentBets;
