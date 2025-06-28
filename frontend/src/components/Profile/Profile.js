import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { User, Coins, TrendingUp, TrendingDown, History, Plus } from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import './Profile.css';

const Profile = () => {
  const { user, updateBalance, fetchProfile } = useAuth();
  const [betHistory, setBetHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addBalanceAmount, setAddBalanceAmount] = useState('');
  const [showAddBalance, setShowAddBalance] = useState(false);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

  useEffect(() => {
    fetchBetHistory();
  }, []);

  const fetchBetHistory = async () => {
    try {
      const response = await axios.get(`${API_URL}/user/bets`);
      setBetHistory(response.data.bets);
    } catch (error) {
      console.error('Failed to fetch bet history:', error);
      toast.error('Failed to load bet history');
    } finally {
      setLoading(false);
    }
  };

  const handleAddBalance = async () => {
    const amount = parseInt(addBalanceAmount);
    if (!amount || amount <= 0 || amount > 10000) {
      toast.error('Please enter a valid amount (1-10000)');
      return;
    }

    try {
      const response = await axios.post(`${API_URL}/user/add-balance`, { amount });
      updateBalance(response.data.balance);
      setAddBalanceAmount('');
      setShowAddBalance(false);
      toast.success(`Added ${amount} coins to your balance!`);
    } catch (error) {
      console.error('Failed to add balance:', error);
      toast.error('Failed to add balance');
    }
  };

  const getStats = () => {
    const totalBets = betHistory.length;
    const totalWins = betHistory.filter(bet => bet.result === 'win').length;
    const totalLosses = betHistory.filter(bet => bet.result === 'lose').length;
    const totalWagered = betHistory.reduce((sum, bet) => sum + bet.amount, 0);
    const totalWon = betHistory.reduce((sum, bet) => sum + bet.winAmount, 0);
    const winRate = totalBets > 0 ? Math.round((totalWins / totalBets) * 100) : 0;
    const profit = totalWon - totalWagered;

    return {
      totalBets,
      totalWins,
      totalLosses,
      totalWagered,
      totalWon,
      winRate,
      profit
    };
  };

  const formatDate = (date) => {
    return new Date(date).toLocaleDateString() + ' ' + new Date(date).toLocaleTimeString();
  };

  const getBetTypeColor = (betType) => {
    switch (betType) {
      case 'red': return '#e74c3c';
      case 'black': return '#2c3e50';
      case 'green': return '#27ae60';
      default: return '#95a5a6';
    }
  };

  const stats = getStats();

  if (loading) {
    return (
      <div className="profile-loading">
        <div className="spinner"></div>
        <p>Loading profile...</p>
      </div>
    );
  }

  return (
    <div className="profile-container">
      <div className="profile-header">
        <div className="profile-info">
          <div className="profile-avatar">
            <User size={40} />
          </div>
          <div className="profile-details">
            <h1>{user?.username}</h1>
            <p>{user?.email}</p>
            <div className="member-since">
              Member since {new Date(user?.createdAt).toLocaleDateString()}
            </div>
          </div>
        </div>
        <div className="profile-balance">
          <div className="balance-card">
            <Coins size={24} />
            <div className="balance-info">
              <div className="balance-amount">{user?.balance || 0}</div>
              <div className="balance-label">Current Balance</div>
            </div>
          </div>
          <button 
            className="btn btn-primary add-balance-btn"
            onClick={() => setShowAddBalance(true)}
          >
            <Plus size={16} />
            Add Balance
          </button>
        </div>
      </div>

      {/* Add Balance Modal */}
      {showAddBalance && (
        <div className="modal-overlay" onClick={() => setShowAddBalance(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Add Balance</h3>
            <p>Add coins to your account (Demo purposes only)</p>
            <div className="form-group">
              <label>Amount (1-10000 coins)</label>
              <input
                type="number"
                value={addBalanceAmount}
                onChange={(e) => setAddBalanceAmount(e.target.value)}
                className="form-control"
                placeholder="Enter amount"
                min="1"
                max="10000"
              />
            </div>
            <div className="modal-actions">
              <button 
                className="btn btn-secondary"
                onClick={() => setShowAddBalance(false)}
              >
                Cancel
              </button>
              <button 
                className="btn btn-primary"
                onClick={handleAddBalance}
              >
                Add Balance
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Statistics */}
      <div className="profile-stats">
        <h2>Statistics</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">
              <History size={24} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.totalBets}</div>
              <div className="stat-label">Total Bets</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon win">
              <TrendingUp size={24} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.totalWins}</div>
              <div className="stat-label">Wins</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon loss">
              <TrendingDown size={24} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.totalLosses}</div>
              <div className="stat-label">Losses</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">
              <div className="win-rate">{stats.winRate}%</div>
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.winRate}%</div>
              <div className="stat-label">Win Rate</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">
              <Coins size={24} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.totalWagered}</div>
              <div className="stat-label">Total Wagered</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className="stat-icon">
              <Coins size={24} />
            </div>
            <div className="stat-info">
              <div className="stat-value">{stats.totalWon}</div>
              <div className="stat-label">Total Won</div>
            </div>
          </div>
          
          <div className="stat-card">
            <div className={`stat-icon ${stats.profit >= 0 ? 'profit' : 'loss'}`}>
              {stats.profit >= 0 ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
            </div>
            <div className="stat-info">
              <div className={`stat-value ${stats.profit >= 0 ? 'positive' : 'negative'}`}>
                {stats.profit >= 0 ? '+' : ''}{stats.profit}
              </div>
              <div className="stat-label">Profit/Loss</div>
            </div>
          </div>
        </div>
      </div>

      {/* Bet History */}
      <div className="bet-history">
        <h2>Bet History</h2>
        {betHistory.length === 0 ? (
          <div className="no-history">
            <p>No bets placed yet</p>
            <span>Start playing to see your bet history here!</span>
          </div>
        ) : (
          <div className="history-table">
            <div className="table-header">
              <div className="table-cell">Date</div>
              <div className="table-cell">Game ID</div>
              <div className="table-cell">Bet Type</div>
              <div className="table-cell">Amount</div>
              <div className="table-cell">Multiplier</div>
              <div className="table-cell">Result</div>
              <div className="table-cell">Win Amount</div>
            </div>
            <div className="table-body">
              {betHistory.map((bet, index) => (
                <div key={bet._id || index} className="table-row">
                  <div className="table-cell">
                    {formatDate(bet.createdAt)}
                  </div>
                  <div className="table-cell">
                    <code>{bet.gameId.slice(-8)}</code>
                  </div>
                  <div className="table-cell">
                    <div className="bet-type-display">
                      <div 
                        className="bet-color-dot"
                        style={{ backgroundColor: getBetTypeColor(bet.betType) }}
                      />
                      {bet.betType.toUpperCase()}
                    </div>
                  </div>
                  <div className="table-cell">
                    <span className="amount">{bet.amount}</span>
                  </div>
                  <div className="table-cell">
                    ×{bet.multiplier}
                  </div>
                  <div className="table-cell">
                    <span className={`result ${bet.result}`}>
                      {bet.result.toUpperCase()}
                    </span>
                  </div>
                  <div className="table-cell">
                    <span className={`win-amount ${bet.result === 'win' ? 'positive' : ''}`}>
                      {bet.winAmount || 0}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Profile;
