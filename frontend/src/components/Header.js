8import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Header.css';

const Header = ({ user, onLogout }) => {
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <h1>🎰 Roulette</h1>
        </div>
        <nav className="nav">
          <Link to="/game" className="nav-link">Game</Link>
          <Link to="/profile" className="nav-link">Profile</Link>
        </nav>
        <div className="user-info">
          <span className="balance">💰 ${user.balance}</span>
          <span className="username">{user.username}</span>
          <button onClick={handleLogout} className="logout-btn">Logout</button>
        </div>
      </div>
    </header>
  );
};

export default Header;
