const AdminPanel = {
    API_BASE: 'http://127.0.0.1:7070/api/admin',
    token: null,
    username: null,
    isAdmin: false,
    currentQuery: null,
    queryMode: 'basic',
    
    init() {
        console.log('[Admin] Starting initialization...');
        
        // Check authentication
        this.token = localStorage.getItem('adminToken');
        this.username = localStorage.getItem('adminUsername');
        this.isAdmin = localStorage.getItem('isAdmin') === 'true';
        
        console.log('[Admin] Token exists:', !!this.token);
        console.log('[Admin] Username:', this.username);
        console.log('[Admin] Is Admin:', this.isAdmin);
        
        if (!this.token) {
            console.log('[Admin] No token, redirecting to login...');
            window.location.href = '/login';
            return;
        }

        if (!this.isAdmin) {
            console.log('[Admin] Not admin, redirecting to main app...');
            this.showNotification('Admin privileges required. Redirecting to main app...', 'error');
            setTimeout(() => {
                window.location.href = '/main';
            }, 2000);
            return;
        }
        
        // Display username
        const usernameElement = document.getElementById('username');
        if (usernameElement) {
            usernameElement.textContent = this.username || 'Admin';
        }
        
        console.log('[Admin] Setting up event listeners...');
        this.setupEventListeners();
        
        console.log('[Admin] Showing first tab...');
        this.switchTab('queries');
        
        console.log('[Admin] Loading initial data...');
        this.loadQueries();
        this.loadUsers();
        
        console.log('[Admin] Initialization complete!');
    },
    
    setupEventListeners() {
        console.log('[Admin] Setting up event listeners...');
        
        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
            console.log('[Admin] Logout button listener added');
        }
        
        // Tab navigation
        const navTabs = document.querySelectorAll('.nav-tab');
        console.log('[Admin] Found nav tabs:', navTabs.length);
        
        navTabs.forEach((tab, index) => {
            const tabName = tab.dataset.tab;
            console.log(`[Admin] Setting up tab ${index}:`, tabName);
            
            tab.addEventListener('click', (e) => {
                console.log('[Admin] Tab clicked:', tabName);
                this.switchTab(tabName);
            });
        });
        
        // Query editor buttons
        const saveQueryBtn = document.getElementById('saveQueryBtn');
        if (saveQueryBtn) saveQueryBtn.addEventListener('click', () => this.saveQuery());
        
        const cancelEditBtn = document.getElementById('cancelEditBtn');
        if (cancelEditBtn) cancelEditBtn.addEventListener('click', () => this.cancelEdit());
        
        const loadDefaultBtn = document.getElementById('loadDefaultBtn');
        if (loadDefaultBtn) loadDefaultBtn.addEventListener('click', () => this.loadDefaultQuery());
        
        const testQueryBtn = document.getElementById('testQueryBtn');
        if (testQueryBtn) testQueryBtn.addEventListener('click', () => this.testQuery());
        
        // Query mode buttons
        const basicModeBtn = document.getElementById('basicModeBtn');
        if (basicModeBtn) basicModeBtn.addEventListener('click', () => this.switchQueryMode('basic'));
        
        const advancedModeBtn = document.getElementById('advancedModeBtn');
        if (advancedModeBtn) advancedModeBtn.addEventListener('click', () => this.switchQueryMode('advanced'));
        
        // Change password form
        const changePasswordForm = document.getElementById('changePasswordForm');
        if (changePasswordForm) {
            changePasswordForm.addEventListener('submit', (e) => this.changePassword(e));
        }
        
        // Create user form
        const createUserForm = document.getElementById('createUserForm');
        if (createUserForm) {
            createUserForm.addEventListener('submit', (e) => this.createUser(e));
        }
        
        console.log('[Admin] Event listeners setup complete');
    },
    
    switchTab(tabName) {
        console.log('[Admin] ===== SWITCHING TO TAB:', tabName, '=====');
        
        // Get all nav tabs
        const navTabs = document.querySelectorAll('.nav-tab');
        console.log('[Admin] Found nav tabs:', navTabs.length);
        
        // Update nav tabs - remove active from all, add to clicked
        navTabs.forEach(tab => {
            const isActive = tab.dataset.tab === tabName;
            if (isActive) {
                tab.classList.add('active');
                console.log('[Admin] Activated nav tab:', tab.dataset.tab);
            } else {
                tab.classList.remove('active');
            }
        });
        
        // Get all tab contents
        const tabContents = document.querySelectorAll('.tab-content');
        console.log('[Admin] Found tab contents:', tabContents.length);
        
        // Hide all tab contents first
        tabContents.forEach(content => {
            content.classList.remove('active');
            console.log('[Admin] Removed active from:', content.id);
        });
        
        // Show the selected tab content
        const targetTab = document.getElementById(`${tabName}-tab`);
        if (targetTab) {
            targetTab.classList.add('active');
            console.log('[Admin] ✅ Activated tab content:', targetTab.id);
        } else {
            console.error('[Admin] ❌ Tab content not found:', `${tabName}-tab`);
        }

        // Load data if needed
        if (tabName === 'users') {
            console.log('[Admin] Loading users for users tab...');
            this.loadUsers();
        }
        
        console.log('[Admin] ===== TAB SWITCH COMPLETE =====');
    },
    
    switchQueryMode(mode) {
        this.queryMode = mode;
        
        document.getElementById('basicModeBtn').classList.toggle('active', mode === 'basic');
        document.getElementById('advancedModeBtn').classList.toggle('active', mode === 'advanced');
        
        document.getElementById('basicModeForm').style.display = mode === 'basic' ? 'block' : 'none';
        document.getElementById('advancedModeForm').style.display = mode === 'advanced' ? 'block' : 'none';

        if (this.currentQuery) {
            if (mode === 'basic') {
                this.populateBasicMode(this.currentQuery.query_sql);
            } else {
                this.populateAdvancedMode(this.currentQuery.query_sql);
            }
        }
    },
    
    populateBasicMode(querySQL) {
        const queryLower = querySQL.toLowerCase();
        
        // For device_query: Extract device type
        if (this.currentQuery && this.currentQuery.query_name === 'device_query') {
            const deviceTypeMatch = querySQL.match(/dvcDeviceType_FRK\s*=\s*(\d+)/i);
            if (deviceTypeMatch) {
                document.getElementById('deviceType').value = deviceTypeMatch[1];
            }
            
            const deviceTableMatch = querySQL.match(/FROM\s+(\w+)/i);
            if (deviceTableMatch) {
                document.getElementById('deviceTableName').value = deviceTableMatch[1];
            }
        }
        // For building_query: Extract building_prk field and building table
        else if (this.currentQuery && this.currentQuery.query_name === 'building_query') {
            // Extract building_prk column name
            const buildingPrkMatch = querySQL.match(/SELECT\s+([\w_]+)\s*,/i);
            if (buildingPrkMatch) {
                document.getElementById('buildingPrkField').value = buildingPrkMatch[1];
            }
            
            const buildingTableMatch = querySQL.match(/FROM\s+(\w+)/i);
            if (buildingTableMatch) {
                document.getElementById('buildingTableName').value = buildingTableMatch[1];
            }
        }
    },
    
    populateAdvancedMode(querySQL) {
        document.getElementById('querySQL').value = querySQL;
    },
    
    logout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
            localStorage.removeItem('isAdmin');
            window.location.href = '/login';
        }
    },
    
    async apiRequest(endpoint, options = {}) {
        const url = `${this.API_BASE}/${endpoint}`;
        
        const headers = {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        try {
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            if (response.status === 401) {
                this.showNotification('Session expired. Please login again.', 'error');
                setTimeout(() => {
                    localStorage.removeItem('adminToken');
                    localStorage.removeItem('adminUsername');
                    localStorage.removeItem('isAdmin');
                    window.location.href = '/login';
                }, 2000);
                throw new Error('Unauthorized');
            }
            
            if (response.status === 403) {
                this.showNotification('Admin privileges required', 'error');
                throw new Error('Forbidden');
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    },
    
    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        if (!notification) return;
        
        notification.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 4000);
    },
    
    async loadQueries() {
        const queryList = document.getElementById('queryList');
        if (!queryList) return;
        
        queryList.innerHTML = '<div class="loader">Loading queries...</div>';
        
        try {
            const data = await this.apiRequest('queries');
            
            queryList.innerHTML = '';
            
            if (data.queries.length === 0) {
                queryList.innerHTML = '<p class="empty-state">No queries found</p>';
                return;
            }
            
            data.queries.forEach(query => {
                const queryItem = this.createQueryListItem(query);
                queryList.appendChild(queryItem);
            });
            
        } catch (error) {
            queryList.innerHTML = '<p class="error-state">Failed to load queries</p>';
            this.showNotification('Failed to load queries', 'error');
        }
    },
    
    createQueryListItem(query) {
        const div = document.createElement('div');
        div.className = 'query-item';
        div.dataset.queryName = query.query_name;
        
        const isDefault = !query.updated_at;
        
        div.innerHTML = `
            <div class="query-item-header">
                <h4>${query.query_name}${isDefault ? ' <span class="badge">Default</span>' : ''}</h4>
                <span class="query-item-date">
                    ${query.updated_at ? `Updated: ${new Date(query.updated_at).toLocaleDateString()}` : 'Not customized'}
                </span>
            </div>
            <p class="query-item-description">${query.description || 'No description'}</p>
        `;
        
        div.addEventListener('click', () => this.loadQueryForEdit(query.query_name));
        
        return div;
    },
    
    async loadQueryForEdit(queryName) {
        try {
            const data = await this.apiRequest(`queries/${queryName}`);
            
            this.currentQuery = data;
            
            document.getElementById('editorPlaceholder').style.display = 'none';
            document.getElementById('queryEditor').style.display = 'block';
            document.getElementById('loadDefaultBtn').style.display = 'inline-block';
            document.getElementById('testQueryBtn').style.display = 'inline-block';
            
            document.getElementById('editorTitle').textContent = `Editing: ${queryName}`;
            document.getElementById('queryName').value = data.query_name;
            document.getElementById('queryDescription').value = data.description || '';
            
            // Update field labels based on query type
            this.updateFieldLabels(queryName);
            
            this.switchQueryMode('basic');
            this.populateBasicMode(data.query_sql);
            this.populateAdvancedMode(data.query_sql);
            
            document.querySelectorAll('.query-item').forEach(item => {
                item.classList.toggle('active', item.dataset.queryName === queryName);
            });
            
        } catch (error) {
            this.showNotification(`Failed to load query: ${queryName}`, 'error');
        }
    },
    
    updateFieldLabels(queryName) {
        const deviceTypeLabel = document.querySelector('label[for="deviceType"]');
        const tableNameLabel = document.querySelector('label[for="buildingTableName"]');
        const deviceTableNameLabel = document.querySelector('label[for="deviceTableName"]');
        const buildingPrkLabel = document.querySelector('label[for="buildingPrkField"]');
        
        const deviceTypeInput = document.getElementById('deviceType');
        const tableNameInput = document.getElementById('buildingTableName');
        const deviceTableNameInput = document.getElementById('deviceTableName');
        const buildingPrkInput = document.getElementById('buildingPrkField');
        
        if (queryName === 'device_query') {
            // Device query: Device Type + Device Table Name
            if (deviceTypeLabel && deviceTypeLabel.parentElement) {
                deviceTypeLabel.parentElement.style.display = 'block';
            }
            if (deviceTableNameLabel && deviceTableNameLabel.parentElement) {
                deviceTableNameLabel.parentElement.style.display = 'block';
            }
            if (buildingPrkLabel && buildingPrkLabel.parentElement) {
                buildingPrkLabel.parentElement.style.display = 'none';
            }
            if (tableNameLabel && tableNameLabel.parentElement) {
                tableNameLabel.parentElement.style.display = 'none';
            }
        } else if (queryName === 'building_query') {
            // Building query: Building PRK field + Building Table Name
            if (deviceTypeLabel && deviceTypeLabel.parentElement) {
                deviceTypeLabel.parentElement.style.display = 'none';
            }
            if (deviceTableNameLabel && deviceTableNameLabel.parentElement) {
                deviceTableNameLabel.parentElement.style.display = 'none';
            }
            if (buildingPrkLabel && buildingPrkLabel.parentElement) {
                buildingPrkLabel.parentElement.style.display = 'block';
            }
            if (tableNameLabel && tableNameLabel.parentElement) {
                tableNameLabel.parentElement.style.display = 'block';
            }
        }
    },
    
    async loadDefaultQuery() {
        if (!this.currentQuery) return;
        
        if (!confirm('This will replace the current query with the default. Continue?')) {
            return;
        }
        
        try {
            const data = await this.apiRequest(`queries/${this.currentQuery.query_name}/default`);
            
            if (this.queryMode === 'basic') {
                this.populateBasicMode(data.query_sql);
            } else {
                document.getElementById('querySQL').value = data.query_sql;
            }
            
            document.getElementById('queryDescription').value = data.description || '';
            this.showNotification('Default query loaded', 'info');
        } catch (error) {
            this.showNotification('Failed to load default query', 'error');
        }
    },
    
    async testQuery() {
        if (!this.currentQuery) return;
        
        const querySQL = this.buildQueryFromMode();
        
        if (!querySQL) {
            this.showNotification('Query cannot be empty', 'error');
            return;
        }
        
        if (!querySQL.toLowerCase().trim().startsWith('select')) {
            this.showNotification('Query must be a SELECT statement', 'error');
            return;
        }
        
        // Client-side validation
        const dangerous = ['drop', 'delete', 'truncate', 'insert', 'update', 'alter', 'create'];
        const queryLower = querySQL.toLowerCase();
        
        for (const keyword of dangerous) {
            if (queryLower.includes(keyword)) {
                this.showNotification(`Query contains forbidden keyword: ${keyword}`, 'error');
                return;
            }
        }
        
        this.showNotification('✅ Query syntax is valid!', 'success');
    },
    
    buildQueryFromMode() {
        if (this.queryMode === 'advanced') {
            return document.getElementById('querySQL').value.trim();
        } else {
            if (!this.currentQuery) return '';
            
            let querySQL = this.currentQuery.query_sql;
            
            // For device_query
            if (this.currentQuery.query_name === 'device_query') {
                const deviceType = document.getElementById('deviceType').value.trim();
                const deviceTable = document.getElementById('deviceTableName').value.trim();
                
                if (deviceType) {
                    querySQL = querySQL.replace(/dvcDeviceType_FRK\s*=\s*\d+/gi, `dvcDeviceType_FRK = ${deviceType}`);
                }
                
                if (deviceTable) {
                    querySQL = querySQL.replace(/FROM\s+\w+/gi, `FROM ${deviceTable}`);
                }
            }
            // For building_query
            else if (this.currentQuery.query_name === 'building_query') {
                const buildingPrk = document.getElementById('buildingPrkField').value.trim();
                const buildingTable = document.getElementById('buildingTableName').value.trim();
                
                if (buildingPrk) {
                    // Replace the first column in SELECT
                    querySQL = querySQL.replace(/SELECT\s+[\w_]+\s*,/gi, `SELECT ${buildingPrk},`);
                }
                
                if (buildingTable) {
                    querySQL = querySQL.replace(/FROM\s+\w+/gi, `FROM ${buildingTable}`);
                }
            }
            
            return querySQL;
        }
    },
    
    async saveQuery() {
        if (!this.currentQuery) return;
        
        const queryName = document.getElementById('queryName').value;
        const queryDescription = document.getElementById('queryDescription').value.trim();
        const querySQL = this.buildQueryFromMode();
        
        if (!querySQL) {
            this.showNotification('Query cannot be empty', 'error');
            return;
        }
        
        if (!querySQL.toLowerCase().trim().startsWith('select')) {
            this.showNotification('Only SELECT queries are allowed', 'error');
            return;
        }
        
        if (!confirm('Save this query? Changes will take effect immediately.')) {
            return;
        }
        
        try {
            await this.apiRequest('queries', {
                method: 'POST',
                body: JSON.stringify({
                    query_name: queryName,
                    query_sql: querySQL,
                    description: queryDescription
                })
            });
            
            this.showNotification('Query saved successfully!', 'success');
            await this.loadQueries();
            await this.loadQueryForEdit(queryName);
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to save query', 'error');
        }
    },
    
    cancelEdit() {
        if (confirm('Discard changes?')) {
            document.getElementById('queryEditor').style.display = 'none';
            document.getElementById('editorPlaceholder').style.display = 'flex';
            document.getElementById('loadDefaultBtn').style.display = 'none';
            document.getElementById('testQueryBtn').style.display = 'none';
            
            document.querySelectorAll('.query-item').forEach(item => {
                item.classList.remove('active');
            });
            
            this.currentQuery = null;
        }
    },
    
    async loadUsers() {
        const usersList = document.getElementById('usersList');
        if (!usersList) return;
        
        usersList.innerHTML = '<div class="loader">Loading users...</div>';
        
        try {
            const users = await this.apiRequest('users');
            
            usersList.innerHTML = '';
            
            if (users.length === 0) {
                usersList.innerHTML = '<p class="empty-state">No users found</p>';
                return;
            }
            
            users.forEach(user => {
                const userCard = this.createUserCard(user);
                usersList.appendChild(userCard);
            });
            
        } catch (error) {
            usersList.innerHTML = '<p class="error-state">Failed to load users</p>';
            this.showNotification('Failed to load users', 'error');
        }
    },
    
    createUserCard(user) {
        const div = document.createElement('div');
        div.className = 'user-card';
        
        const isCurrentUser = user.username === this.username;
        
        div.innerHTML = `
            <div class="user-card-header">
                <div>
                    <h4 class="user-card-username">
                        ${user.username}
                        ${isCurrentUser ? '<span class="badge" style="background: #3b82f6; color: white;">You</span>' : ''}
                        ${user.is_admin ? '<span class="badge" style="background: #f59e0b; color: white;">Admin</span>' : ''}
                    </h4>
                    <p class="user-card-date">Created: ${new Date(user.created_at).toLocaleDateString()}</p>
                </div>
                <div class="user-card-actions">
                    ${!isCurrentUser ? `
                        <button class="btn btn-secondary btn-sm" onclick="AdminPanel.toggleUserAdmin(${user.id}, ${!user.is_admin})">
                            ${user.is_admin ? 'Remove Admin' : 'Make Admin'}
                        </button>
                        <button class="btn btn-info btn-sm" onclick="AdminPanel.resetUserPassword(${user.id}, '${user.username}')">
                            Reset Password
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="AdminPanel.deleteUser(${user.id}, '${user.username}')">
                            Delete
                        </button>
                    ` : '<span style="color: #64748b; font-size: 0.85rem;">Use "Change Password" tab to update your password</span>'}
                </div>
            </div>
        `;
        
        return div;
    },
    
    async createUser(event) {
        event.preventDefault();
        
        const username = document.getElementById('newUsername').value.trim();
        const password = document.getElementById('newUserPassword').value;
        const isAdmin = document.getElementById('newUserIsAdmin').checked;
        
        if (username.length < 3) {
            this.showNotification('Username must be at least 3 characters', 'error');
            return;
        }
        
        if (password.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest('users', {
                method: 'POST',
                body: JSON.stringify({
                    username: username,
                    password: password,
                    is_admin: isAdmin
                })
            });
            
            this.showNotification(`User '${username}' created successfully!`, 'success');
            document.getElementById('createUserForm').reset();
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to create user', 'error');
        }
    },
    
    async toggleUserAdmin(userId, makeAdmin) {
        const action = makeAdmin ? 'grant admin privileges to' : 'remove admin privileges from';
        
        if (!confirm(`Are you sure you want to ${action} this user?`)) {
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    is_admin: makeAdmin
                })
            });
            
            this.showNotification('User updated successfully', 'success');
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to update user', 'error');
        }
    },
    
    async resetUserPassword(userId, username) {
        const newPassword = prompt(`Enter new password for user '${username}':\n(Minimum 6 characters)`);
        
        if (!newPassword) return;
        
        if (newPassword.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    new_password: newPassword
                })
            });
            
            this.showNotification(`Password reset successfully for user '${username}'`, 'success');
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to reset password', 'error');
        }
    },
    
    async deleteUser(userId, username) {
        if (!confirm(`Are you sure you want to delete user '${username}'?\n\nThis action cannot be undone.`)) {
            return;
        }
        
        try {
            await this.apiRequest(`users/${userId}`, {
                method: 'DELETE'
            });
            
            this.showNotification(`User '${username}' deleted successfully`, 'success');
            this.loadUsers();
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to delete user', 'error');
        }
    },
    
    async changePassword(event) {
        event.preventDefault();
        
        const currentPassword = document.getElementById('currentPassword').value;
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (newPassword !== confirmPassword) {
            this.showNotification('New passwords do not match', 'error');
            return;
        }
        
        if (newPassword.length < 6) {
            this.showNotification('Password must be at least 6 characters', 'error');
            return;
        }
        
        try {
            await this.apiRequest('change-password', {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });
            
            this.showNotification('Password changed successfully! Redirecting to login...', 'success');
            document.getElementById('changePasswordForm').reset();
            
            setTimeout(() => {
                localStorage.removeItem('adminToken');
                localStorage.removeItem('adminUsername');
                localStorage.removeItem('isAdmin');
                window.location.href = '/login';
            }, 2000);
            
        } catch (error) {
            this.showNotification(error.message || 'Failed to change password', 'error');
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Admin] DOM Content Loaded - Initializing AdminPanel...');
    AdminPanel.init();
});