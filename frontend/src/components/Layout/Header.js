import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { User, LogOut, Home, Coins } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import './Header.css';

const Header = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

  return (
    <header className="header">
      <div className="header-container">
        <Link to="/" className="logo">
          <div className="logo-icon">🎰</div>
          <span>Roulette</span>
        </Link>

        <nav className="nav">
          <Link 
            to="/" 
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            <Home size={20} />
            <span>Game</span>
          </Link>
          <Link 
            to="/profile" 
            className={`nav-link ${location.pathname === '/profile' ? 'active' : ''}`}
          >
            <User size={20} />
            <span>Profile</span>
          </Link>
        </nav>

        <div className="user-info">
          <div className="balance">
            <Coins size={20} />
            <span>{user?.balance || 0}</span>
          </div>
          <div className="user-menu">
            <span className="username">{user?.username}</span>
            <button className="logout-btn" onClick={logout}>
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
