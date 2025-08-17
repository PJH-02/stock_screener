// File: public/script.js

class StockScreenerApp {
    constructor() {
        this.dataUrl = 'data/screener_results.json';
        this.refreshInterval = 15 * 60 * 1000; // 15 minutes
        this.refreshTimer = null;
        this.isLoading = false;
        
        this.initializeApp();
    }
    
    initializeApp() {
        // Initialize theme
        this.initializeTheme();
        
        // Bind event listeners
        this.bindEventListeners();
        
        // Load initial data
        this.loadData();
        
        // Start auto-refresh
        this.startAutoRefresh();
    }
    
    initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
    }
    
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        const themeIcon = document.querySelector('.theme-icon');
        if (themeIcon) {
            themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    }
    
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }
    
    bindEventListeners() {
        // Theme toggle
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.refreshData();
            }
            if (e.key === 't' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.toggleTheme();
            }
        });
        
        // Handle modal close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideAbout();
            }
        });
    }
    
    async loadData() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading();
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            const response = await fetch(this.dataUrl, {
                signal: controller.signal,
                cache: 'no-cache'
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.renderData(data);
            this.hideLoading();
            this.hideError();
            
        } catch (error) {
            console.error('Error loading data:', error);
            this.showError(this.getErrorMessage(error));
            this.hideLoading();
        } finally {
            this.isLoading = false;
        }
    }
    
    getErrorMessage(error) {
        if (error.name === 'AbortError') {
            return 'Request timed out. Please try again.';
        }
        if (error.message.includes('404')) {
            return 'Data file not found. The screener may be running for the first time.';
        }
        if (error.message.includes('Failed to fetch')) {
            return 'Network error. Please check your connection and try again.';
        }
        return error.message || 'An unexpected error occurred.';
    }
    
    renderData(data) {
        try {
            // Validate data structure
            if (!data || !data.metadata || !Array.isArray(data.filtered_stocks)) {
                throw new Error('Invalid data format received');
            }
            
            // Render statistics
            this.renderStatistics(data.metadata, data);
            
            // Render stock results
            this.renderStocks(data.filtered_stocks);
            
            // Show appropriate sections
            this.showResults();
            
        } catch (error) {
            console.error('Error rendering data:', error);
            this.showError('Error displaying data. Please refresh the page.');
        }
    }
    
    renderStatistics(metadata, data) {
        const elements = {
            totalAnalyzed: document.getElementById('totalAnalyzed'),
            signal1Count: document.getElementById('signal1Count'),
            signal2Count: document.getElementById('signal2Count'),
            successRate: document.getElementById('successRate'),
            lastUpdated: document.getElementById('lastUpdated')
        };
        
        // Update values with animation
        if (elements.totalAnalyzed) {
            this.animateValue(elements.totalAnalyzed, metadata.total_analyzed || 0);
        }
        
        if (elements.signal1Count && data.signal_breakdown) {
            this.animateValue(elements.signal1Count, data.signal_breakdown.signal1_count || 0);
        }
        
        if (elements.signal2Count && data.signal_breakdown) {
            this.animateValue(elements.signal2Count, data.signal_breakdown.signal2_count || 0);
        }
        
        if (elements.successRate) {
            elements.successRate.textContent = `${metadata.success_rate || 0}%`;
        }
        
        if (elements.lastUpdated && metadata.last_updated) {
            const date = new Date(metadata.last_updated);
            elements.lastUpdated.textContent = this.formatDateTime(date);
            elements.lastUpdated.title = date.toLocaleString();
        }
    }
    
    renderStocks(stocks) {
        const stocksList = document.getElementById('stocksList');
        const emptyState = document.getElementById('emptyState');
        
        if (!stocksList) return;
        
        if (!stocks || stocks.length === 0) {
            stocksList.innerHTML = '';
            if (emptyState) {
                emptyState.classList.remove('hidden');
            }
            return;
        }
        
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
        
        // Generate stock cards
        stocksList.innerHTML = stocks.map(stock => this.createStockCard(stock)).join('');
        
        // Add animation to cards
        const cards = stocksList.querySelectorAll('.stock-card');
        cards.forEach((card, index) => {
            card.style.animationDelay = `${index * 0.1}s`;
            card.classList.add('slide-up');
        });
    }
    
    createStockCard(stock) {
        const signals = stock.signals;
        const breakouts = stock.breakout_levels;
        
        // Determine primary signal type and details
        let primarySignal = null;
        let signalBadge = '';
        let signalDetails = '';
        
        if (signals.signal1.entry) {
            primarySignal = signals.signal1.entry;
            signalBadge = '<span class="signal-indicator signal-1">Signal 1</span><span class="signal-indicator signal-entry">Entry</span>';
            signalDetails = `
                <div class="detail-item">
                    <span class="detail-label">Breakout Level</span>
                    <span class="detail-value">${this.formatPrice(primarySignal.breakout_level, stock.market)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Exit Level</span>
                    <span class="detail-value">${this.formatPrice(primarySignal.exit_level, stock.market)}</span>
                </div>
            `;
        } else if (signals.signal1.exit) {
            primarySignal = signals.signal1.exit;
            signalBadge = '<span class="signal-indicator signal-1">Signal 1</span><span class="signal-indicator signal-exit">Exit</span>';
            signalDetails = `
                <div class="detail-item">
                    <span class="detail-label">Breakdown Level</span>
                    <span class="detail-value">${this.formatPrice(primarySignal.breakdown_level, stock.market)}</span>
                </div>
            `;
        } else if (signals.signal2.entry) {
            primarySignal = signals.signal2.entry;
            signalBadge = '<span class="signal-indicator signal-2">Signal 2</span><span class="signal-indicator signal-entry">Entry</span>';
            signalDetails = `
                <div class="detail-item">
                    <span class="detail-label">Breakout Level (55d)</span>
                    <span class="detail-value">${this.formatPrice(primarySignal.breakout_level, stock.market)}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Exit Level</span>
                    <span class="detail-value">${this.formatPrice(primarySignal.exit_level, stock.market)}</span>
                </div>
            `;
        }
        
        const marketBadge = `<span class="market-badge market-${stock.market.toLowerCase()}">${stock.market}</span>`;
        
        return `
            <div class="stock-card">
                <div class="stock-header">
                    <div class="stock-ticker">
                        ${this.escapeHtml(stock.name)}
                        <span class="ticker-code">(${this.escapeHtml(stock.ticker)})</span>
                        ${marketBadge}
                    </div>
                    <div class="stock-price">${this.formatPrice(stock.current_price, stock.market)}</div>
                </div>
                
                <div class="stock-signal">
                    ${signalBadge}
                </div>
                
                <div class="stock-details">
                    <div class="detail-item">
                        <span class="detail-label">20d Avg Volume</span>
                        <span class="detail-value">${this.formatVolume(stock.volume_20_avg)}</span>
                    </div>
                    ${signalDetails}
                    <div class="detail-item">
                        <span class="detail-label">Signal Date</span>
                        <span class="detail-value">${this.formatDate(new Date(primarySignal.date))}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    formatPrice(price, market) {
        if (typeof price !== 'number') return '0.00';
        
        if (market === 'KRX') {
            return `₩${price.toLocaleString('ko-KR')}`;
        } else {
            return `${price.toFixed(2)}`;
        }
    }
    
    // Utility functions
    formatNumber(num) {
        if (typeof num !== 'number') return '0.00';
        return num.toFixed(2);
    }
    
    formatVolume(volume) {
        if (typeof volume !== 'number') return '0';
        
        if (volume >= 1_000_000) {
            return `${(volume / 1_000_000).toFixed(1)}M`;
        }
        if (volume >= 1_000) {
            return `${(volume / 1_000).toFixed(1)}K`;
        }
        return volume.toLocaleString();
    }
    
    formatDate(date) {
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    }
    
    formatDateTime(date) {
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }
    
    getDaysAgo(date) {
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'today';
        if (diffDays === 1) return 'yesterday';
        return `${diffDays} days ago`;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    animateValue(element, targetValue, duration = 1000) {
        if (!element) return;
        
        const startValue = parseInt(element.textContent) || 0;
        const difference = targetValue - startValue;
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out animation
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            const currentValue = Math.round(startValue + (difference * easedProgress));
            
            element.textContent = currentValue;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    // UI State management
    showLoading() {
        const loading = document.getElementById('loading');
        if (loading) {
            loading.classList.remove('hidden');
        }
        
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.classList.add('loading');
            refreshBtn.disabled = true;
        }
    }
    
    hideLoading() {
        const loading = document.getElementById('loading');
        if (loading) {
            loading.classList.add('hidden');
        }
        
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }
    }
    
    showError(message) {
        const error = document.getElementById('error');
        const errorMessage = document.getElementById('errorMessage');
        
        if (error) {
            error.classList.remove('hidden');
        }
        
        if (errorMessage) {
            errorMessage.textContent = message;
        }
        
        // Hide other sections
        this.hideResults();
    }
    
    hideError() {
        const error = document.getElementById('error');
        if (error) {
            error.classList.add('hidden');
        }
    }
    
    showResults() {
        const stats = document.getElementById('stats');
        const results = document.getElementById('results');
        
        if (stats) {
            stats.classList.remove('hidden');
            stats.classList.add('fade-in');
        }
        
        if (results) {
            results.classList.remove('hidden');
            results.classList.add('fade-in');
        }
    }
    
    hideResults() {
        const stats = document.getElementById('stats');
        const results = document.getElementById('results');
        const emptyState = document.getElementById('emptyState');
        
        if (stats) {
            stats.classList.add('hidden');
        }
        
        if (results) {
            results.classList.add('hidden');
        }
        
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
    }
    
    // Refresh functionality
    refreshData() {
        if (this.isLoading) return;
        this.loadData();
    }
    
    startAutoRefresh() {
        // Clear existing timer
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        // Set up new timer
        this.refreshTimer = setInterval(() => {
            this.loadData();
        }, this.refreshInterval);
    }
    
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }
    
    // Modal functionality
    showAbout() {
        const modal = document.getElementById('aboutModal');
        if (modal) {
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }
    }
    
    hideAbout() {
        const modal = document.getElementById('aboutModal');
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        }
    }
}

// Global functions for modal (called from HTML)
function showAbout() {
    if (window.stockScreenerApp) {
        window.stockScreenerApp.showAbout();
    }
}

function hideAbout() {
    if (window.stockScreenerApp) {
        window.stockScreenerApp.hideAbout();
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.stockScreenerApp = new StockScreenerApp();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (window.stockScreenerApp) {
        if (document.hidden) {
            window.stockScreenerApp.stopAutoRefresh();
        } else {
            window.stockScreenerApp.startAutoRefresh();
            // Refresh data when page becomes visible
            setTimeout(() => window.stockScreenerApp.loadData(), 1000);
        }
    }
});

// Handle online/offline status
window.addEventListener('online', () => {
    if (window.stockScreenerApp) {
        window.stockScreenerApp.loadData();
    }
});

window.addEventListener('offline', () => {
    if (window.stockScreenerApp) {
        window.stockScreenerApp.showError('You are currently offline. Data will refresh when connection is restored.');
    }
});
