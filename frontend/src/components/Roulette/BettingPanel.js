import React, { useState } from 'react';
import { useSocket } from '../../contexts/SocketContext';
import { useAuth } from '../../contexts/AuthContext';
import { Coins } from 'lucide-react';
import toast from 'react-hot-toast';
import './BettingPanel.css';

const BettingPanel = ({ gameState, selectedBet, setSelectedBet }) => {
  const { placeBet } = useSocket();
  const { user } = useAuth();
  const [customAmount, setCustomAmount] = useState('');

  const quickAmounts = [10, 25, 50, 100, 250, 500];
  const betTypes = [
    { type: 'red', label: 'Red', multiplier: 2, color: '#e74c3c' },
    { type: 'black', label: 'Black', multiplier: 2, color: '#2c3e50' },
    { type: 'green', label: 'Green', multiplier: 14, color: '#27ae60' }
  ];

  const handleAmountSelect = (amount) => {
    setSelectedBet(prev => ({ ...prev, amount }));
    setCustomAmount('');
  };

  const handleCustomAmountChange = (e) => {
    const value = e.target.value;
    if (value === '' || (Number(value) >= 1 && Number(value) <= 1000)) {
      setCustomAmount(value);
      if (value !== '') {
        setSelectedBet(prev => ({ ...prev, amount: Number(value) }));
      }
    }
  };

  const handlePlaceBet = () => {
    if (gameState.phase !== 'betting') {
      toast.error('Betting is closed');
      return;
    }

    if (selectedBet.amount < 1 || selectedBet.amount > 1000) {
      toast.error('Bet amount must be between 1 and 1000');
      return;
    }

    if (selectedBet.amount > user.balance) {
      toast.error('Insufficient balance');
      return;
    }

    // Check if user already has 2 bets
    const userBets = gameState.bets.filter(bet => bet.userId === user.id);
    if (userBets.length >= 2) {
      toast.error('Maximum 2 bets per round');
      return;
    }

    placeBet(selectedBet.type, selectedBet.amount);
  };

  const getUserBets = () => {
    return gameState.bets.filter(bet => bet.userId === user.id);
  };

  const canPlaceBet = () => {
    return gameState.phase === 'betting' && 
           selectedBet.amount <= user.balance && 
           getUserBets().length < 2;
  };

  return (
    <div className="betting-panel">
      <div className="betting-header">
        <h3>Place Your Bets</h3>
        <div className="betting-status">
          {gameState.phase === 'betting' ? (
            <span className="status-open">Betting Open</span>
          ) : (
            <span className="status-closed">Betting Closed</span>
          )}
        </div>
      </div>

      {/* Bet Type Selection */}
      <div className="bet-types">
        <div className="section-title">Choose Color</div>
        <div className="bet-type-grid">
          {betTypes.map(({ type, label, multiplier, color }) => (
            <button
              key={type}
              className={`bet-type ${selectedBet.type === type ? 'selected' : ''}`}
              onClick={() => setSelectedBet(prev => ({ ...prev, type }))}
              style={{ '--bet-color': color }}
            >
              <div className="bet-type-content">
                <div className="bet-color" style={{ backgroundColor: color }} />
                <div className="bet-label">{label}</div>
                <div className="bet-multiplier">×{multiplier}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Amount Selection */}
      <div className="bet-amount">
        <div className="section-title">Bet Amount</div>
        
        <div className="quick-amounts">
          {quickAmounts.map(amount => (
            <button
              key={amount}
              className={`amount-btn ${selectedBet.amount === amount ? 'selected' : ''}`}
              onClick={() => handleAmountSelect(amount)}
              disabled={amount > user.balance}
            >
              {amount}
            </button>
          ))}
        </div>

        <div className="custom-amount">
          <input
            type="number"
            placeholder="Custom amount"
            value={customAmount}
            onChange={handleCustomAmountChange}
            className="amount-input"
            min="1"
            max="1000"
          />
        </div>
      </div>

      {/* Bet Summary */}
      <div className="bet-summary">
        <div className="summary-row">
          <span>Bet Type:</span>
          <span className="bet-type-display" style={{ 
            color: betTypes.find(bt => bt.type === selectedBet.type)?.color 
          }}>
            {betTypes.find(bt => bt.type === selectedBet.type)?.label}
          </span>
        </div>
        <div className="summary-row">
          <span>Amount:</span>
          <span>{selectedBet.amount} coins</span>
        </div>
        <div className="summary-row">
          <span>Potential Win:</span>
          <span className="potential-win">
            {selectedBet.amount * betTypes.find(bt => bt.type === selectedBet.type)?.multiplier} coins
          </span>
        </div>
      </div>

      {/* Place Bet Button */}
      <button
        className="place-bet-btn"
        onClick={handlePlaceBet}
        disabled={!canPlaceBet()}
      >
        <Coins size={20} />
        Place Bet
      </button>

      {/* User's Current Bets */}
      {getUserBets().length > 0 && (
        <div className="current-user-bets">
          <div className="section-title">Your Bets This Round</div>
          {getUserBets().map((bet, index) => (
            <div key={index} className="user-bet">
              <div className="bet-info">
                <span className={`bet-color-indicator ${bet.betType}`}></span>
                <span>{bet.betType.toUpperCase()}</span>
              </div>
              <div className="bet-amount-display">{bet.amount} coins</div>
            </div>
          ))}
          <div className="bets-remaining">
            {2 - getUserBets().length} bets remaining
          </div>
        </div>
      )}
    </div>
  );
};

export default BettingPanel;
