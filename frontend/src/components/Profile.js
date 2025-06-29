import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Profile.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const Profile = ({ user }) => {
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchProfileData();
  }, []);

  const fetchProfileData = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_URL}/api/profile`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProfileData(response.data);
    } catch (error) {
      setError('Failed to load profile data');
      console.error('Profile error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading profile...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!profileData) return <div className="error">No profile data available</div>;

  const { user: userData, bets, stats } = profileData;

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const winRate = stats.total_bets > 0 
    ? ((bets.filter(bet => bet.result === 'WIN').length / stats.total_bets) * 100).toFixed(1)
    : 0;

  return (
    <div className="profile-container">
      <div className="profile-header">
        <h2>👤 Player Profile</h2>
        <div className="user-info-grid">
          <div className="info-card">
            <div className="info-icon">👤</div>
            <div className="info-content">
              <label>Username</label>
              <span>{userData.username}</span>
            </div>
          </div>
          <div className="info-card">
            <div className="info-icon">💰</div>
            <div className="info-content">
              <label>Current Balance</label>
              <span className="balance">${parseFloat(userData.balance).toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="profile-stats">
        <h3>📊 Statistics</h3>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">🎯</div>
            <div className="stat-content">
              <span className="stat-value">{stats.total_bets || 0}</span>
              <span className="stat-label">Total Bets</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">💸</div>
            <div className="stat-content">
              <span className="stat-value">${parseFloat(stats.total_wagered || 0).toFixed(2)}</span>
              <span className="stat-label">Total Wagered</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🏆</div>
            <div className="stat-content">
              <span className="stat-value">${parseFloat(stats.total_won || 0).toFixed(2)}</span>
              <span className="stat-label">Total Won</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-content">
              <span className={`stat-value ${parseFloat(stats.net_profit || 0) >= 0 ? 'positive' : 'negative'}`}>
                ${parseFloat(stats.net_profit || 0).toFixed(2)}
              </span>
              <span className="stat-label">Net Profit</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🎲</div>
            <div className="stat-content">
              <span className="stat-value">{winRate}%</span>
              <span className="stat-label">Win Rate</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">💵</div>
            <div className="stat-content">
              <span className="stat-value">
                ${stats.total_bets > 0 ? (parseFloat(stats.total_wagered) / stats.total_bets).toFixed(2) : '0.00'}
              </span>
              <span className="stat-label">Avg Bet</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bet-history">
        <h3>📝 Bet History</h3>
        <div className="bets-container">
          {bets.length > 0 ? (
            <>
              <div className="bets-table">
                <div className="table-header">
                  <span>Round</span>
                  <span>Color</span>
                  <span>Amount</span>
                  <span>Result</span>
                  <span>Payout</span>
                  <span>Profit</span>
                  <span>Date</span>
                </div>
                {bets.map((bet) => {
                  const profit = parseFloat(bet.payout) - parseFloat(bet.amount);
                  return (
                    <div key={bet.id} className="table-row">
                      <span className="round-id">#{bet.round_id}</span>
                      <span className={`color-indicator ${bet.color.toLowerCase()}`}>
                        <div className="color-dot"></div>
                        {bet.color}
                      </span>
                      <span className="amount">${parseFloat(bet.amount).toFixed(2)}</span>
                      <span className={`result ${bet.result === 'WIN' ? 'win' : 'lose'}`}>
                        {bet.result === 'WIN' ? '✅ WIN' : '❌ LOSE'}
                      </span>
                      <span className={`payout ${bet.payout > 0 ? 'win' : ''}`}>
                        ${parseFloat(bet.payout).toFixed(2)}
                      </span>
                      <span className={`profit ${profit >= 0 ? 'positive' : 'negative'}`}>
                        {profit >= 0 ? '+' : ''}${profit.toFixed(2)}
                      </span>
                      <span className="date">{formatDate(bet.created_at)}</span>
                    </div>
                  );
                })}
              </div>
              
              {bets.length >= 50 && (
                <div className="pagination-info">
                  Showing latest 50 bets
                </div>
              )}
            </>
          ) : (
            <div className="no-bets">
              <div className="no-bets-icon">🎰</div>
              <h4>No betting history available</h4>
              <p>Start playing to see your bet history here!</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;
