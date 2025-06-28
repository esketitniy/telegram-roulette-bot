import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import './Auth.css';

const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    let result;
    if (isLogin) {
      result = await login(formData.username, formData.password);
    } else {
      result = await register(formData.username, formData.email, formData.password);
    }

    setLoading(false);
    
    if (result.success) {
      setFormData({ username: '', email: '', password: '' });
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>🎰 Online Roulette</h1>
          <p>Welcome to the ultimate roulette experience</p>
        </div>

        <div className="auth-tabs">
          <button 
            className={`tab ${isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(true)}
          >
            Login
          </button>
          <button 
            className={`tab ${!isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(false)}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              className="form-control"
              placeholder="Enter your username"
              required
            />
          </div>

          {!isLogin && (
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="form-control"
                placeholder="Enter your email"
                required
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="form-control"
              placeholder="Enter your password"
              required
            />
          </div>

          <button 
            type="submit" 
            className="btn btn-primary auth-btn"
            disabled={loading}
          >
            {loading ? 'Please wait...' : (isLogin ? 'Login' : 'Register')}
          </button>
        </form>

        <div className="auth-footer">
          <p>
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <button 
              className="link-btn"
              onClick={() => setIsLogin(!isLogin)}
            >
              {isLogin ? 'Register here' : 'Login here'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Auth;
