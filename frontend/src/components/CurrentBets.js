import React from 'react';
import './CurrentBets.css';

const CurrentBets = ({ bets }) => {
  const groupedBets = bets.reduce((acc, bet) => {
    if (!acc[bet.color]) {
      acc[bet.color] = { total: 0, count: 0, bets: [] };
    }
    acc[bet.color].total += bet.amount;
    acc[bet.color].count += 1;
    acc[bet.color].bets.push(bet);
    return acc;
  }, {});

  return (
    <div className="current-bets">
      <h3>Current Round Bets</h3>
      
      <div className="bet-summary">
        {Object.entries(groupedBets).map(([color, data]) => (
          <div key={color} className={`bet-group ${color.toLowerCase()}`}>
            <div className="bet-header">
              <span className="color-name">{color}</span>
              <span className="bet-total">${data.total} ({data.count} bets)</span>
            </div>
          </div>
        ))}
      </div>

      <div className="all-bets">
        {bets.slice(-10).map((bet, index) => (
          <div key={index} className="bet-item">
            <span className="username">{bet.username}</span>
            <span className={`bet-color ${bet.color.toLowerCase()}`}>
              {bet.color}
            </span>
            <span className="bet-amount">${bet.amount}</span>
          </div>
        ))}
      </div>
      
      {bets.length === 0 && (
        <div className="no-bets">No bets placed yet</div>
      )}
    </div>
  );
};

export default CurrentBets;
