import React, { createContext, useContext, useEffect, useState } from 'react';
import io from 'socket.io-client';
import { useAuth } from './AuthContext';
import toast from 'react-hot-toast';

const SocketContext = createContext();

export const useSocket = () => {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocket must be used within a SocketProvider');
  }
  return context;
};

export const SocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [connected, setConnected] = useState(false);
  const { user, updateBalance } = useAuth();

  const SOCKET_URL = process.env.REACT_APP_SOCKET_URL || 'http://localhost:5000';

  useEffect(() => {
    if (user) {
      const newSocket = io(SOCKET_URL, {
        auth: {
          userId: user.id
        }
      });

      setSocket(newSocket);

      newSocket.on('connect', () => {
        setConnected(true);
        newSocket.emit('join-game', user.id);
      });

      newSocket.on('disconnect', () => {
        setConnected(false);
      });

      newSocket.on('game-state', (state) => {
        setGameState(state);
      });

      newSocket.on('bet-placed', (result) => {
        updateBalance(result.betInfo.balance);
        toast.success('Bet placed successfully!');
      });

      newSocket.on('bet-error', (error) => {
        toast.error(error);
      });

      newSocket.on('bet-won', (data) => {
        if (data.userId === user.id) {
          toast.success(`You won ${data.amount} coins on ${data.betType}!`);
        }
      });

      newSocket.on('game-result', (result) => {
        // Game result is handled in the roulette component
      });

      newSocket.on('betting-closed', () => {
        toast.info('Betting is now closed');
      });

      newSocket.on('new-round', () => {
        toast.info('New round starting!');
      });

      return () => {
        newSocket.close();
      };
    }
  }, [user, SOCKET_URL, updateBalance]);

  const placeBet = (betType, amount) => {
    if (socket && connected) {
      socket.emit('place-bet', { betType, amount });
    } else {
      toast.error('Not connected to game server');
    }
  };

  const value = {
    socket,
    gameState,
    connected,
    placeBet
  };

  return (
    <SocketContext.Provider value={value}>
      {children}
    </SocketContext.Provider>
  );
};
