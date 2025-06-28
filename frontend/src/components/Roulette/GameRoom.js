import React, { useState, useEffect } from 'react';
import { useSocket } from '../../contexts/SocketContext';
import { useAuth } from '../../contexts/AuthContext';
import RouletteWheel from './RouletteWheel';
import BettingPanel from './BettingPanel';
import GameHistory from './GameHistory';
import CurrentBets from './CurrentBets';
import GameTimer from './GameTimer';
import './GameRoom.css';

const GameRoom = () => {
  const { gameState, connected } = useSocket();
  const { user } = useAuth();
  const [selectedBet, setSelectedBet] = useState({ type: 'red', amount: 10 });

  if (!connected || !gameState) {
    return (
      <div className="game-room loading">
        <div className="loading-content">
          <div className="spinner"></div>
          <p>Connecting to game...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="game-room">
      <div className="game-header">
        <h1>🎰 Live Roulette</h1>
        <div className="game-info">
          <div className="info-item">
            <span className="label">Min Bet:</span>
            <span className="value">1 coin</span>
          </div>
          <div className="info-item">
            <span className="label">Max Bet:</span>
            <span className="value">1000 coins</span>
          </div>
          <div className="info-item">
            <span className="label">Players Online:</span>
            <span className="value">{gameState.bets?.length || 0}</span>
          </div>
        </div>
      </div>

      <div className="game-content">
        <div className="game-left">
          <div className="roulette-section">
            <GameTimer gameState={gameState} />
            <RouletteWheel gameState={gameState} />
          </div>
          
          <BettingPanel 
            gameState={gameState}
            selectedBet={selectedBet}
            setSelectedBet={setSelectedBet}
          />
        </div>

        <div className="game-right">
          <GameHistory history={gameState.history || []} />
          <CurrentBets 
            bets={gameState.bets || []} 
            totalBets={gameState.totalBets || {}}
          />
        </div>
      </div>
    </div>
  );
};

export default GameRoom;
