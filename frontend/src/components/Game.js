import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import Roulette from './Roulette';
import BettingPanel from './BettingPanel';
import CurrentBets from './CurrentBets';
import History from './History';
import './Game.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const Game = ({ user }) => {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState({
    phase: 'BETTING',
    timeLeft: 20000,
    currentBets: [],
    roundId: 1,
    result: null
  });
  const [userBets, setUserBets] = useState([]);
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const newSocket = io(API_URL);
    setSocket(newSocket);

    newSocket.on('gameState', (state) => {
      setGameState(state);
    });

    newSocket.on('betsUpdate', (bets) => {
      setGameState(prev => ({ ...prev, currentBets: bets }));
    });

    newSocket.on('roundResult', (data) => {
      setGameState(prev => ({ 
        ...prev, 
        result: data.result,
        phase: 'RESULT'
      }));
      
      // Update history
      setHistory(prev => [data, ...prev.slice(0, 19)]);
      
      // Clear user bets for next round
      setTimeout(() => {
        setUserBets([]);
        setMessage('');
      }, 3000);
    });

    newSocket.on('betSuccess', (bet) => {
      setUserBets(prev => [...prev, bet]);
      setMessage('Bet placed successfully!');
      setTimeout(() => setMessage(''), 3000);
    });

    newSocket.on('betError', (error) => {
      setMessage(error);
      setTimeout(() => setMessage(''), 3000);
    });

    // Load initial history
    fetch(`${API_URL}/api/history`)
      .then(res => res.json())
      .then(data => setHistory(data))
      .catch(console.error);

    return () => {
      newSocket.disconnect();
    };
  }, []);

  const placeBet = (color, amount) => {
    if (!socket) return;

    const token = localStorage.getItem('token');
    socket.emit('placeBet', { token, color, amount });
  };

  const formatTime = (ms) => {
    const seconds = Math.ceil(ms / 1000);
    return `${seconds}s`;
  };

  return (
    <div className="game-container">
      <div className="game-header">
        <div className="round-info">
          <h2>Round #{gameState.roundId}</h2>
          <div className={`timer ${gameState.phase.toLowerCase()}`}>
            {gameState.phase === 'BETTING' && `Betting: ${formatTime(gameState.timeLeft)}`}
            {gameState.phase === 'SPINNING' && `Spinning: ${formatTime(gameState.timeLeft)}`}
            {gameState.phase === 'RESULT' && 'Round Finished'}
          </div>
        </div>
        {message && <div className="message">{message}</div>}
      </div>

      <div className="game-content">
        <div className="roulette-section">
          <Roulette 
            isSpinning={gameState.phase === 'SPINNING'} 
            result={gameState.result}
          />
        </div>

        <div className="betting-section">
          <BettingPanel 
            onPlaceBet={placeBet}
            disabled={gameState.phase !== 'BETTING'}
            userBets={userBets}
            balance={user.balance}
          />
        </div>
      </div>

      <div className="game-info">
        <CurrentBets bets={gameState.currentBets} />
        <History history={history} />
      </div>
    </div>
  );
};

export default Game;
