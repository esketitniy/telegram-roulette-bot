import React from 'react';
import { Clock } from 'lucide-react';
import './GameTimer.css';

const GameTimer = ({ gameState }) => {
  const getPhaseText = () => {
    switch (gameState.phase) {
      case 'betting':
        return 'Place Your Bets';
      case 'spinning':
        return 'Spinning...';
      case 'result':
        return 'Round Complete';
      default:
        return 'Loading...';
    }
  };

  const getPhaseColor = () => {
    switch (gameState.phase) {
      case 'betting':
        return '#27ae60';
      case 'spinning':
        return '#f39c12';
      case 'result':
        return '#e74c3c';
      default:
        return '#95a5a6';
    }
  };

  const getProgressPercentage = () => {
    const maxTime = gameState.phase === 'betting' ? 25 : 5;
    return ((maxTime - gameState.timeLeft) / maxTime) * 100;
  };

  return (
    <div className="game-timer">
      <div className="timer-content">
        <div className="timer-icon">
          <Clock size={24} color={getPhaseColor()} />
        </div>
        
        <div className="timer-info">
          <div className="phase-text" style={{ color: getPhaseColor() }}>
            {getPhaseText()}
          </div>
          <div className="time-left">
            {gameState.timeLeft}s
          </div>
        </div>
      </div>
      
      <div className="timer-progress">
        <div 
          className="progress-bar"
          style={{ 
            width: `${getProgressPercentage()}%`,
            backgroundColor: getPhaseColor()
          }}
        />
      </div>
    </div>
  );
};

export default GameTimer;
