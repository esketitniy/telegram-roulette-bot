import React from 'react';
import { History, TrendingUp } from 'lucide-react';
import './GameHistory.css';

const GameHistory = ({ history }) => {
  const getColorClass = (color) => {
    return `history-item-${color}`;
  };

  const getColorStats = () => {
    const stats = { red: 0, black: 0, green: 0 };
    history.forEach(game => {
      stats[game.result]++;
    });
    return stats;
  };

  const stats = getColorStats();
  const total = history.length;

  return (
    <div className="game-history">
      <div className="history-header">
        <div className="header-title">
          <History size={20} />
          <h3>Game History</h3>
        </div>
        <div className="history-count">
          {history.length} games
        </div>
      </div>

      {/* Statistics */}
      {total > 0 && (
        <div className="history-stats">
          <div className="stats-title">
            <TrendingUp size={16} />
            Statistics
          </div>
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-color red"></div>
              <div className="stat-info">
                <div className="stat-label">Red</div>
                <div className="stat-value">
                  {stats.red} ({Math.round((stats.red / total) * 100)}%)
                </div>
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-color black"></div>
              <div className="stat-info">
                <div className="stat-label">Black</div>
                <div className="stat-value">
                  {stats.black} ({Math.round((stats.black / total) * 100)}%)
                </div>
              </div>
            </div>
            <div className="stat-item">
              <div className="stat-color green"></div>
              <div className="stat-info">
                <div className="stat-label">Green</div>
                <div className="stat-value">
                  {stats.green} ({Math.round((stats.green / total) * 100)}%)
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* History List */}
      <div className="history-list">
        {history.length === 0 ? (
          <div className="no-history">
            <p>No games played yet</p>
          </div>
        ) : (
          <div className="history-items">
            {history.map((game, index) => (
              <div key={game.gameId || index} className={`history-item ${getColorClass(game.result)}`}>
                <div className="history-number">
                  {game.number}
                </div>
                <div className="history-info">
                  <div className="history-color">
                    {game.result.toUpperCase()}
                  </div>
                  <div className="history-time">
                    {new Date(game.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default GameHistory;
