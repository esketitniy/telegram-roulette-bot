// Отладочная информация
console.log('Script.js загружен');

// Проверка доступности элементов при загрузке
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded');
    
    // Проверяем наличие ключевых элементов
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const authError = document.getElementById('authError');
    
    console.log('LoginForm:', loginForm ? 'найден' : 'НЕ НАЙДЕН');
    console.log('RegisterForm:', registerForm ? 'найден' : 'НЕ НАЙДЕН');
    console.log('AuthError:', authError ? 'найден' : 'НЕ НАЙДЕН');
    
    // Тестируем switchTab функцию
    window.testSwitchTab = function() {
        console.log('Testing switchTab function');
        switchTab('register');
        setTimeout(() => switchTab('login'), 1000);
    };
    
    console.log('Для тестирования переключения вкладок выполните: testSwitchTab()');
});

class RouletteGame {
    constructor() {
        this.socket = io();
        this.token = localStorage.getItem('token');
        this.user = null;
        this.selectedColor = null;
        this.gameState = {};
        this.retryCount = 0;
        this.maxRetries = 3;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuth();
    }

    checkAuth() {
        if (this.token) {
            this.verifyToken();
        } else {
            this.showAuthScreen();
        }
    }

    async verifyToken() {
        try {
            const response = await fetch('/api/profile', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.showGameScreen();
                this.retryCount = 0;
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
                setTimeout(() => this.verifyToken(), 3000);
            } else {
                localStorage.removeItem('token');
                this.showAuthScreen();
            }
        } catch (error) {
            console.error('Ошибка проверки токена:', error);
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                setTimeout(() => this.verifyToken(), 2000);
            } else {
                this.showAuthScreen();
            }
        }
    }

    setupEventListeners() {
        // Auth form handlers
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');

        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleLogin();
            });
        }

        if (registerForm) {
            registerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleRegister();
            });
        }

        // Game handlers
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.selectColor(btn.dataset.color);
            });
        });

        const placeBetBtn = document.getElementById('placeBetBtn');
        if (placeBetBtn) {
            placeBetBtn.addEventListener('click', () => {
                this.placeBet();
            });
        }

        const betAmountInput = document.getElementById('betAmount');
        if (betAmountInput) {
            betAmountInput.addEventListener('input', () => {
                this.updateBetButton();
            });
        }

        const profileBtn = document.getElementById('profileBtn');
        if (profileBtn) {
            profileBtn.addEventListener('click', () => {
                this.showProfile();
            });
        }

        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.logout();
            });
        }

        // Modal handlers
        const closeBtn = document.querySelector('.close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                document.getElementById('profileModal').style.display = 'none';
            });
        }

        window.addEventListener('click', (e) => {
            const modal = document.getElementById('profileModal');
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Socket event listeners
        this.setupSocketListeners();
    }

    setupSocketListeners() {
        this.socket.on('gameState', (state) => {
            this.gameState = state;
            this.updateGameUI();
        });

        this.socket.on('timeUpdate', (timeLeft) => {
            const timeLeftElement = document.getElementById('timeLeft');
            if (timeLeftElement) {
                timeLeftElement.textContent = timeLeft;
                
                if (timeLeft <= 5 && this.gameState.phase === 'betting') {
                    timeLeftElement.style.color = '#ff4444';
                } else {
                    timeLeftElement.style.color = '#ffd700';
                }
            }
        });

        this.socket.on('spinStart', () => {
            this.startRouletteAnimation();
        });

        this.socket.on('spinResult', (result) => {
            this.showResult(result);
            this.loadGameHistory();
        });

        this.socket.on('newBet', (bet) => {
            this.addBetToList(bet);
        });

        this.socket.on('balanceUpdate', (newBalance) => {
            this.user.balance = newBalance;
            this.updateBalance();
        });

        this.socket.on('betsResult', (data) => {
            this.processBetsResult(data);
        });

        this.socket.on('error', (message) => {
            this.showError(message);
        });
    }

    // Auth methods
    switchTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
        
        const tabButton = document.querySelector(`[onclick="switchTab('${tab}')"]`);
        const tabForm = document.getElementById(`${tab}Form`);
        
        if (tabButton) tabButton.classList.add('active');
        if (tabForm) tabForm.classList.add('active');
        
        this.clearAuthError();
    }

    async handleLogin() {
        const usernameInput = document.getElementById('loginUsername');
        const passwordInput = document.getElementById('loginPassword');
        
        if (!usernameInput || !passwordInput) {
            this.showAuthError('Ошибка: поля ввода не найдены');
            return;
        }

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        console.log('Попытка входа для пользователя:', username);

        if (!username || !password) {
            this.showAuthError('Введите логин и пароль');
            return;
        }

        this.showAuthLoading('Вход в систему...');

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            console.log('Ответ сервера:', response.status);
            const data = await response.json();
            console.log('Данные ответа:', data);

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showAuthSuccess('Успешный вход!');
                setTimeout(() => {
                    this.showGameScreen();
                }, 1000);
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
            } else {
                this.showAuthError(data.error || 'Ошибка входа');
            }
        } catch (error) {
            console.error('Ошибка при входе:', error);
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    async handleRegister() {
        const usernameInput = document.getElementById('registerUsername');
        const passwordInput = document.getElementById('registerPassword');
        
        if (!usernameInput || !passwordInput) {
            this.showAuthError('Ошибка: поля ввода не найдены');
            return;
        }

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        console.log('Попытка регистрации для пользователя:', username);

        if (!username || !password) {
            this.showAuthError('Введите логин и пароль');
            return;
        }

        if (username.length < 3) {
            this.showAuthError('Логин должен содержать минимум 3 символа');
            return;
        }

        if (password.length < 6) {
            this.showAuthError('Пароль должен содержать минимум 6 символов');
            return;
        }

        this.showAuthLoading('Регистрация...');

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            console.log('Ответ сервера:', response.status);
            const data = await response.json();
            console.log('Данные ответа:', data);

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showAuthSuccess('Регистрация успешна!');
                setTimeout(() => {
                    this.showGameScreen();
                }, 1000);
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
            } else {
                this.showAuthError(data.error || 'Ошибка регистрации');
            }
        } catch (error) {
            console.error('Ошибка при регистрации:', error);
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    showAuthError(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message error';
            errorElement.style.display = 'block';
        }
        console.error('Auth error:', message);
    }

    showAuthSuccess(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message success';
            errorElement.style.display = 'block';
        }
        console.log('Auth success:', message);
    }

    showAuthLoading(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message loading';
            errorElement.style.display = 'block';
        }
        console.log('Auth loading:', message);
    }

    clearAuthError() {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
    }

    // Screen management
    showAuthScreen() {
        const authScreen = document.getElementById('authScreen');
        const gameScreen = document.getElementById('gameScreen');
        
        if (authScreen) authScreen.classList.remove('hidden');
        if (gameScreen) gameScreen.classList.add('hidden');
    }

    showGameScreen() {
        const authScreen = document.getElementById('authScreen');
        const gameScreen = document.getElementById('gameScreen');
        
        if (authScreen) authScreen.classList.add('hidden');
        if (gameScreen) gameScreen.classList.remove('hidden');
        
        this.updateUserInfo();
        this.loadGameHistory();
    }

    updateUserInfo() {
        const usernameElement = document.getElementById('username');
        if (usernameElement && this.user) {
            usernameElement.textContent = this.user.username;
        }
        this.updateBalance();
    }

    updateBalance() {
        const balanceElement = document.getElementById('balance');
        const profileBalanceElement = document.getElementById('profileBalance');
        
        if (balanceElement && this.user) {
            balanceElement.textContent = this.user.balance;
        }
        if (profileBalanceElement && this.user) {
            profileBalanceElement.textContent = this.user.balance;
        }
    }

    // Game methods
    updateGameUI() {
        const timerText = document.getElementById('timerText');
        const placeBetBtn = document.getElementById('placeBetBtn');

        if (!timerText || !placeBetBtn) return;

        switch (this.gameState.phase) {
            case 'betting':
                timerText.textContent = 'Ставки: ';
                placeBetBtn.disabled = false;
                break;
            case 'spinning':
                timerText.textContent = 'Вращение: ';
                placeBetBtn.disabled = true;
                this.selectedColor = null;
                this.updateColorSelection();
                break;
            case 'result':
                timerText.textContent = 'Результат';
                placeBetBtn.disabled = true;
                break;
        }

        this.updateBetButton();
    }

    selectColor(color) {
        if (this.gameState.phase !== 'betting') return;
        
        this.selectedColor = color;
        this.updateColorSelection();
        this.updateBetButton();
    }

    updateColorSelection() {
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.classList.remove('selected');
        });

        if (this.selectedColor) {
            const selectedBtn = document.querySelector(`[data-color="${this.selectedColor}"]`);
            if (selectedBtn) {
                selectedBtn.classList.add('selected');
            }
        }
    }

    updateBetButton() {
        const betAmountInput = document.getElementById('betAmount');
        const placeBetBtn = document.getElementById('placeBetBtn');
        
        if (!betAmountInput || !placeBetBtn || !this.user) return;

        const betAmount = parseInt(betAmountInput.value);

        const canBet = this.selectedColor && 
                      betAmount > 0 && 
                      betAmount <= this.user.balance && 
                      this.gameState.phase === 'betting';

        placeBetBtn.disabled = !canBet;
    }

    placeBet() {
        const betAmountInput = document.getElementById('betAmount');
        if (!betAmountInput) return;

        const betAmount = parseInt(betAmountInput.value);
        
        if (!this.selectedColor || betAmount <= 0 || betAmount > this.user.balance) {
            this.showError('Неверная ставка');
            return;
        }

        this.socket.emit('placeBet', {
            token: this.token,
            color: this.selectedColor,
            amount: betAmount
        });

        // Очистка формы
        betAmountInput.value = '';
        this.selectedColor = null;
        this.updateColorSelection();
        this.updateBetButton();
    }

    startRouletteAnimation() {
        const wheel = document.getElementById('rouletteWheel');
        if (!wheel) return;

        wheel.classList.add('spinning');
        
        setTimeout(() => {
            wheel.classList.remove('spinning');
            const spins = 5 + Math.random() * 5;
            const finalRotation = spins * 360;
            wheel.style.transform = `rotate(${finalRotation}deg)`;
        }, 100);
    }

    showResult(result) {
        const wheel = document.getElementById('rouletteWheel');
        if (!wheel) return;
        
        const colorAngles = {
            'greenclass RouletteGame {
    constructor() {
        this.socket = io();
        this.token = localStorage.getItem('token');
        this.user = null;
        this.selectedColor = null;
        this.gameState = {};
        this.retryCount = 0;
        this.maxRetries = 3;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuth();
    }

    checkAuth() {
        if (this.token) {
            this.verifyToken();
        } else {
            this.showAuthScreen();
        }
    }

    async verifyToken() {
        try {
            const response = await fetch('/api/profile', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.showGameScreen();
                this.retryCount = 0;
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
                setTimeout(() => this.verifyToken(), 3000);
            } else {
                localStorage.removeItem('token');
                this.showAuthScreen();
            }
        } catch (error) {
            console.error('Ошибка проверки токена:', error);
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                setTimeout(() => this.verifyToken(), 2000);
            } else {
                this.showAuthScreen();
            }
        }
    }

    setupEventListeners() {
        // Auth form handlers
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');

        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleLogin();
            });
        }

        if (registerForm) {
            registerForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleRegister();
            });
        }

        // Game handlers
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.selectColor(btn.dataset.color);
            });
        });

        const placeBetBtn = document.getElementById('placeBetBtn');
        if (placeBetBtn) {
            placeBetBtn.addEventListener('click', () => {
                this.placeBet();
            });
        }

        const betAmountInput = document.getElementById('betAmount');
        if (betAmountInput) {
            betAmountInput.addEventListener('input', () => {
                this.updateBetButton();
            });
        }

        const profileBtn = document.getElementById('profileBtn');
        if (profileBtn) {
            profileBtn.addEventListener('click', () => {
                this.showProfile();
            });
        }

        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                this.logout();
            });
        }

        // Modal handlers
        const closeBtn = document.querySelector('.close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                document.getElementById('profileModal').style.display = 'none';
            });
        }

        window.addEventListener('click', (e) => {
            const modal = document.getElementById('profileModal');
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Socket event listeners
        this.setupSocketListeners();
    }

    setupSocketListeners() {
        this.socket.on('gameState', (state) => {
            this.gameState = state;
            this.updateGameUI();
        });

        this.socket.on('timeUpdate', (timeLeft) => {
            const timeLeftElement = document.getElementById('timeLeft');
            if (timeLeftElement) {
                timeLeftElement.textContent = timeLeft;
                
                if (timeLeft <= 5 && this.gameState.phase === 'betting') {
                    timeLeftElement.style.color = '#ff4444';
                } else {
                    timeLeftElement.style.color = '#ffd700';
                }
            }
        });

        this.socket.on('spinStart', () => {
            this.startRouletteAnimation();
        });

        this.socket.on('spinResult', (result) => {
            this.showResult(result);
            this.loadGameHistory();
        });

        this.socket.on('newBet', (bet) => {
            this.addBetToList(bet);
        });

        this.socket.on('balanceUpdate', (newBalance) => {
            this.user.balance = newBalance;
            this.updateBalance();
        });

        this.socket.on('betsResult', (data) => {
            this.processBetsResult(data);
        });

        this.socket.on('error', (message) => {
            this.showError(message);
        });
    }

    // Auth methods
    switchTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
        
        const tabButton = document.querySelector(`[onclick="switchTab('${tab}')"]`);
        const tabForm = document.getElementById(`${tab}Form`);
        
        if (tabButton) tabButton.classList.add('active');
        if (tabForm) tabForm.classList.add('active');
        
        this.clearAuthError();
    }

    async handleLogin() {
        const usernameInput = document.getElementById('loginUsername');
        const passwordInput = document.getElementById('loginPassword');
        
        if (!usernameInput || !passwordInput) {
            this.showAuthError('Ошибка: поля ввода не найдены');
            return;
        }

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        console.log('Попытка входа для пользователя:', username);

        if (!username || !password) {
            this.showAuthError('Введите логин и пароль');
            return;
        }

        this.showAuthLoading('Вход в систему...');

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            console.log('Ответ сервера:', response.status);
            const data = await response.json();
            console.log('Данные ответа:', data);

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showAuthSuccess('Успешный вход!');
                setTimeout(() => {
                    this.showGameScreen();
                }, 1000);
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
            } else {
                this.showAuthError(data.error || 'Ошибка входа');
            }
        } catch (error) {
            console.error('Ошибка при входе:', error);
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    async handleRegister() {
        const usernameInput = document.getElementById('registerUsername');
        const passwordInput = document.getElementById('registerPassword');
        
        if (!usernameInput || !passwordInput) {
            this.showAuthError('Ошибка: поля ввода не найдены');
            return;
        }

        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        console.log('Попытка регистрации для пользователя:', username);

        if (!username || !password) {
            this.showAuthError('Введите логин и пароль');
            return;
        }

        if (username.length < 3) {
            this.showAuthError('Логин должен содержать минимум 3 символа');
            return;
        }

        if (password.length < 6) {
            this.showAuthError('Пароль должен содержать минимум 6 символов');
            return;
        }

        this.showAuthLoading('Регистрация...');

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            console.log('Ответ сервера:', response.status);
            const data = await response.json();
            console.log('Данные ответа:', data);

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showAuthSuccess('Регистрация успешна!');
                setTimeout(() => {
                    this.showGameScreen();
                }, 1000);
            } else if (response.status === 503) {
                this.showAuthError('Сервер загружается, попробуйте через несколько секунд...');
            } else {
                this.showAuthError(data.error || 'Ошибка регистрации');
            }
        } catch (error) {
            console.error('Ошибка при регистрации:', error);
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    showAuthError(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message error';
            errorElement.style.display = 'block';
        }
        console.error('Auth error:', message);
    }

    showAuthSuccess(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message success';
            errorElement.style.display = 'block';
        }
        console.log('Auth success:', message);
    }

    showAuthLoading(message) {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.className = 'error-message loading';
            errorElement.style.display = 'block';
        }
        console.log('Auth loading:', message);
    }

    clearAuthError() {
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
    }

    // Screen management
    showAuthScreen() {
        const authScreen = document.getElementById('authScreen');
        const gameScreen = document.getElementById('gameScreen');
        
        if (authScreen) authScreen.classList.remove('hidden');
        if (gameScreen) gameScreen.classList.add('hidden');
    }

    showGameScreen() {
        const authScreen = document.getElementById('authScreen');
        const gameScreen = document.getElementById('gameScreen');
        
        if (authScreen) authScreen.classList.add('hidden');
        if (gameScreen) gameScreen.classList.remove('hidden');
        
        this.updateUserInfo();
        this.loadGameHistory();
    }

    updateUserInfo() {
        const usernameElement = document.getElementById('username');
        if (usernameElement && this.user) {
            usernameElement.textContent = this.user.username;
        }
        this.updateBalance();
    }

    updateBalance() {
        const balanceElement = document.getElementById('balance');
        const profileBalanceElement = document.getElementById('profileBalance');
        
        if (balanceElement && this.user) {
            balanceElement.textContent = this.user.balance;
        }
        if (profileBalanceElement && this.user) {
            profileBalanceElement.textContent = this.user.balance;
        }
    }

    // Game methods
    updateGameUI() {
        const timerText = document.getElementById('timerText');
        const placeBetBtn = document.getElementById('placeBetBtn');

        if (!timerText || !placeBetBtn) return;

        switch (this.gameState.phase) {
            case 'betting':
                timerText.textContent = 'Ставки: ';
                placeBetBtn.disabled = false;
                break;
            case 'spinning':
                timerText.textContent = 'Вращение: ';
                placeBetBtn.disabled = true;
                this.selectedColor = null;
                this.updateColorSelection();
                break;
            case 'result':
                timerText.textContent = 'Результат';
                placeBetBtn.disabled = true;
                break;
        }

        this.updateBetButton();
    }

    selectColor(color) {
        if (this.gameState.phase !== 'betting') return;
        
        this.selectedColor = color;
        this.updateColorSelection();
        this.updateBetButton();
    }

    updateColorSelection() {
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.classList.remove('selected');
        });

        if (this.selectedColor) {
            const selectedBtn = document.querySelector(`[data-color="${this.selectedColor}"]`);
            if (selectedBtn) {
                selectedBtn.classList.add('selected');
            }
        }
    }

    updateBetButton() {
        const betAmountInput = document.getElementById('betAmount');
        const placeBetBtn = document.getElementById('placeBetBtn');
        
        if (!betAmountInput || !placeBetBtn || !this.user) return;

        const betAmount = parseInt(betAmountInput.value);

        const canBet = this.selectedColor && 
                      betAmount > 0 && 
                      betAmount <= this.user.balance && 
                      this.gameState.phase === 'betting';

        placeBetBtn.disabled = !canBet;
    }

    placeBet() {
        const betAmountInput = document.getElementById('betAmount');
        if (!betAmountInput) return;

        const betAmount = parseInt(betAmountInput.value);
        
        if (!this.selectedColor || betAmount <= 0 || betAmount > this.user.balance) {
            this.showError('Неверная ставка');
            return;
        }

        this.socket.emit('placeBet', {
            token: this.token,
            color: this.selectedColor,
            amount: betAmount
        });

        // Очистка формы
        betAmountInput.value = '';
        this.selectedColor = null;
        this.updateColorSelection();
        this.updateBetButton();
    }

    startRouletteAnimation() {
        const wheel = document.getElementById('rouletteWheel');
        if (!wheel) return;

        wheel.classList.add('spinning');
        
        setTimeout(() => {
            wheel.classList.remove('spinning');
            const spins = 5 + Math.random() * 5;
            const finalRotation = spins * 360;
            wheel.style.transform = `rotate(${finalRotation}deg)`;
        }, 100);
    }

    showResult(result) {
        const wheel = document.getElementById('rouletteWheel');
        if (!wheel) return;
        
        const colorAngles = {
            'green': 348,
            'red': [12, 36, 60, 84, 108, 132, 156, 180, 204, 228, 252, 276, 300, 324],
            'black': [24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336]
        };

        let targetAngle;
        if (result === 'green') {
            targetAngle = colorAngles.green;
        } else {
            const angles = colorAngles[result];
            targetAngle = angles[Math.floor(Math.random() * angles.length)];
        }

        const extraSpins = 5 * 360;
        const finalAngle = extraSpins + targetAngle;

        wheel.style.transition = 'transform 4s cubic-bezier(0.23, 1, 0.32, 1)';
        wheel.style.transform = `rotate(${finalAngle}deg)`;

        setTimeout(() => {
            this.displayResult(result);
        }, 4000);
    }

    displayResult(result) {
        const resultElement = document.createElement('div');
        resultElement.className = `result-announcement ${result}`;
        resultElement.innerHTML = `
            <div class="result-content">
                <div class="result-color ${result}"></div>
                <h2>Выпало: ${this.getColorName(result)}!</h2>
            </div>
        `;
        
        document.body.appendChild(resultElement);
        
        setTimeout(() => {
            resultElement.remove();
        }, 3000);
    }

    getColorName(color) {
        const names = {
            'red': 'Красное',
            'black': 'Черное',
            'green': 'Зеленое'
        };
        return names[color];
    }

    processBetsResult(data) {
        const { result, bets } = data;
        
        this.loadUserProfile();
        
        bets.forEach(bet => {
            if (bet.userId === this.user.id) {
                const won = bet.color === result;
                const message = won ? 
                    `Вы выиграли ${bet.amount * this.getMultiplier(bet.color)}!` :
                    `Вы проиграли ${bet.amount}`;
                
                this.showNotification(message, won ? 'success' : 'error');
            }
        });
    }

    getMultiplier(color) {
        const multipliers = { red: 2, black: 2, green: 14 };
        return multipliers[color];
    }

    addBetToList(bet) {
        const betsList = document.getElementById('currentBets');
        if (!betsList) return;

        const betElement = document.createElement('div');
        betElement.className = 'bet-item fade-in';
        betElement.innerHTML = `
            <div class="bet-username">${bet.username}</div>
            <div>
                <span class="result-color ${bet.color}"></span>
                ${this.getColorName(bet.color)} - ${bet.amount}
            </div>
        `;
        
        betsList.insertBefore(betElement, betsList.firstChild);
        
        while (betsList.children.length > 10) {
            betsList.removeChild(betsList.lastChild);
        }
    }

    async loadGameHistory() {
        try {
            const response = await fetch('/api/history');
            const games = await response.json();
            
            const historyList = document.getElementById('gameHistory');
            if (!historyList) return;

            historyList.innerHTML = '';
            
            games.forEach(game => {
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item';
                historyItem.innerHTML = `
                    <div>
                        <span class="result-color ${game.result}"></span>
                        ${this.getColorName(game.result)}
                    </div>
                    <div class="game-time">${new Date(game.timestamp).toLocaleTimeString()}</div>
                `;
                historyList.appendChild(historyItem);
            });
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
        }
    }

    async loadUserProfile() {
        try {
            const response = await fetch('/api/profile', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.updateBalance();
                this.displayUserBets(data.bets);
            }
        } catch (error) {
            console.error('Ошибка загрузки профиля:', error);
        }
    }

    displayUserBets(bets) {
        const betsList = document.getElementById('userBets');
        if (!betsList) return;

        betsList.innerHTML = '';
        
        if (bets.length === 0) {
            betsList.innerHTML = '<p>У вас пока нет ставок</p>';
            return;
        }
        
        bets.forEach(bet => {
            const betItem = document.createElement('div');
            betItem.className = 'user-bet-item';
            
            const resultClass = bet.won ? 'won' : 'lost';
            const resultText = bet.won ? `+${bet.winnings}` : `-${bet.amount}`;
            
            betItem.innerHTML = `
                <div class="bet-details">
                    <span class="result-color ${bet.color}"></span>
                    <div>
                        <div>${this.getColorName(bet.color)} - ${bet.amount}</div>
                        <div class="bet-time">${new Date(bet.game_time).toLocaleString()}</div>
                    </div>
                </div>
                <div class="bet-result ${resultClass}">
                    ${resultText}
                </div>
            `;
            
            betsList.appendChild(betItem);
        });
    }

    showProfile() {
        this.loadUserProfile();
        const modal = document.getElementById('profileModal');
        if (modal) {
            modal.style.display = 'block';
        }
    }

    logout() {
        localStorage.removeItem('token');
        this.token = null;
        this.user = null;
        this.socket.disconnect();
        this.socket.connect();
        this.showAuthScreen();
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 2rem;
            border-radius: 10px;
            color: white;
            font-weight: bold;
            z-index: 1001;
            animation: slideIn 0.3s ease-out;
            max-width: 300px;
        `;
        
        switch (type) {
            case 'success':
                notification.style.background = '#4caf50';
                break;
            case 'error':
                notification.style.background = '#f44336';
                break;
            default:
                notification.style.background = '#2196f3';
        }
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }
}

// Глобальная функция для переключения вкладок
window.switchTab = function(tab) {
    if (window.game) {
        window.game.switchTab(tab);
    } else {
        // Fallback если game еще не инициализирован
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
        
        const tabButton = document.querySelector(`[onclick="switchTab('${tab}')"]`);
        const tabForm = document.getElementById(`${tab}Form`);
        
        if (tabButton) tabButton.classList.add('active');
        if (tabForm) tabForm.classList.add('active');
        
        const errorElement = document.getElementById('authError');
        if (errorElement) {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
    }
};

// Инициализация игры
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM загружен, инициализация игры...');
    window.game = new RouletteGame();
});
