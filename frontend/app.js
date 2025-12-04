// frontend/app.js

// Check authentication BEFORE DOM loads
(function() {
    const token = localStorage.getItem('adminToken');
    if (!token && window.location.pathname !== '/login') {
        console.log('No token found, redirecting to login...');
        window.location.replace('/login');
    }
})();

document.addEventListener('DOMContentLoaded', () => {
    App.initialize();
});

const App = {
    API_BASE_URL: 'http://127.0.0.1:7070/api',
    BUILD_PAGE_SIZE: 100,
    allBuildings: [],
    selectedBuildingId: null,
    elements: {},
    token: null,
    username: null,

    initialize() {
        // Double-check authentication
        this.token = localStorage.getItem('adminToken');
        this.username = localStorage.getItem('adminUsername');
        
        if (!this.token) {
            console.log('No token in initialize, redirecting to login...');
            window.location.replace('/login');
            return;
        }
        
        console.log('Token found, user:', this.username);

        this.elements.buildingsContainer = document.getElementById('deviceList');
        this.elements.loader = document.getElementById('loader');
        this.elements.notification = document.getElementById('notification');
        this.elements.buildingSearch = document.querySelector('.building-search');
        this.elements.buildingDropdown = document.querySelector('.building-dropdown');
        this.elements.clearFilter = document.querySelector('.clear-filter');
        this.elements.ignoreModal = document.getElementById('ignoreModal');
        this.elements.modalTitle = document.getElementById('modalTitle');
        this.elements.modalItemList = document.getElementById('modalItemList');
        this.elements.modalConfirmBtn = document.getElementById('modalConfirmBtn');
        this.elements.modalCancelBtn = document.getElementById('modalCancelBtn');
        this.elements.closeButton = document.querySelector('.close-button');
        this.elements.modalSearch = document.getElementById('modalSearch');
        this.elements.modalSelectAllBtn = document.getElementById('modalSelectAllBtn');
        this.elements.logoutBtn = document.getElementById('logoutBtn');

        // Setup logout button
        if (this.elements.logoutBtn) {
            this.elements.logoutBtn.addEventListener('click', () => this.logout());
        }

        this.setupBuildingSelector();
        this.loadAllBuildings();
    },

    logout() {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
            window.location.replace('/login');
        }
    },

    showNotification(text, isError = false, timeout = 3000) {
        if (!this.elements.notification) return;
        const { notification } = this.elements;
        notification.textContent = text;
        notification.style.backgroundColor = isError ? '#ef4444' : '#333';
        notification.classList.add('show');
        
        if (notification.timeoutId) {
            clearTimeout(notification.timeoutId);
        }
        notification.timeoutId = setTimeout(() => {
             notification.classList.remove('show');
             notification.timeoutId = null;
        }, timeout);
    },

    async apiRequest(endpoint, options = {}) {
        const url = `${this.API_BASE_URL}/${endpoint}`;
        
        // Add authentication header
        const headers = {
            ...options.headers
        };
        
        // Only add auth header for admin endpoints
        if (endpoint.startsWith('admin/')) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        try {
            if(this.elements.loader) this.elements.loader.style.display = 'block';
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            if (response.status === 401) {
                // Token expired, redirect to login
                this.showNotification('Session expired. Please login again.', true);
                setTimeout(() => {
                    localStorage.removeItem('adminToken');
                    localStorage.removeItem('adminUsername');
                    window.location.replace('/login');
                }, 2000);
                throw new Error('Unauthorized');
            }
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: `Request failed with status ${response.status}` }));
                throw new Error(errorData.detail || `Request failed: ${response.status}`);
            }
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            }
            return {};
        } catch (error) {
            console.error(`API request error for ${endpoint}:`, error);
            this.showNotification(error.message || 'An unexpected error occurred', true);
            throw error;
        } finally {
             if(this.elements.loader) this.elements.loader.style.display = 'none';
        }
    },

    escapeHtml(str) {
        return String(str || '').replace(/[&<>"']/g, s => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;',
            '"': '&quot;', "'": '&#39;'
        }[s]));
    },

    setupBuildingSelector() {
        const { buildingSearch, buildingDropdown, clearFilter } = this.elements;
        if (!buildingSearch || !buildingDropdown || !clearFilter) {
            console.error("Building selector elements not found!");
            return;
        }

        buildingSearch.addEventListener('input', () => {
            const query = buildingSearch.value.toLowerCase();
            buildingDropdown.innerHTML = '';

            if (query.length === 0) {
                buildingDropdown.style.display = 'none';
                clearFilter.style.display = 'none';
                 if (this.selectedBuildingId !== null) {
                     this.selectedBuildingId = null;
                     this.loadAllBuildings();
                 }
                return;
            }

            const filtered = this.allBuildings.filter(b =>
                b.name.toLowerCase().includes(query)
            );

            if (filtered.length > 0) {
                filtered.forEach(building => {
                    const option = document.createElement('div');
                    option.className = 'building-option';
                    option.textContent = this.escapeHtml(building.name);
                    option.addEventListener('click', () => this.selectBuilding(building));
                    buildingDropdown.appendChild(option);
                });
                buildingDropdown.style.display = 'block';
            } else {
                 const noResult = document.createElement('div');
                 noResult.className = 'building-option muted';
                 noResult.textContent = 'No buildings found';
                 buildingDropdown.appendChild(noResult);
                 buildingDropdown.style.display = 'block';
            }
            clearFilter.style.display = 'block';
        });

        clearFilter.addEventListener('click', () => {
            buildingSearch.value = '';
            buildingDropdown.innerHTML = '';
            buildingDropdown.style.display = 'none';
            clearFilter.style.display = 'none';
            this.selectedBuildingId = null;
            this.loadAllBuildings();
        });

        document.addEventListener('click', (e) => {
            if (!buildingSearch.contains(e.target) && !buildingDropdown.contains(e.target)) {
                buildingDropdown.style.display = 'none';
            }
        });
    },

    selectBuilding(building) {
        const { buildingSearch, buildingDropdown, clearFilter } = this.elements;
        if (!buildingSearch || !buildingDropdown || !clearFilter) return;

        buildingSearch.value = this.escapeHtml(building.name);
        buildingDropdown.style.display = 'none';
        this.selectedBuildingId = building.id;
        clearFilter.style.display = 'block';
        this.loadFilteredBuilding(building);
    },

    async loadFilteredBuilding(building) {
        const { buildingsContainer } = this.elements;
        if (!buildingsContainer) return;

        buildingsContainer.innerHTML = '';
        const card = this.createBuildingCard(building);
        buildingsContainer.appendChild(card);
        
        try {
            await this.loadItemsForBuilding(card);
            const body = card.querySelector('.building-body');
            const toggleBtn = card.querySelector('.toggle-btn');
            if (body && toggleBtn) {
                body.style.display = 'block';
                toggleBtn.textContent = '-';
                const itemsList = card.querySelector('.items-list');
                if (itemsList) itemsList.dataset.loaded = 'true';
            }
        } catch (error) {
             console.error("Error auto-loading items for filtered building:", error);
             const itemsList = card.querySelector('.items-list');
             if (itemsList) itemsList.innerHTML = '<li class="muted">Error loading items.</li>';
             const body = card.querySelector('.building-body');
             const toggleBtn = card.querySelector('.toggle-btn');
             if (body && toggleBtn) {
                 body.style.display = 'block';
                 toggleBtn.textContent = '-';
             }
        }
    },

    async loadAllBuildings() {
        const { buildingsContainer } = this.elements;
        if (!buildingsContainer) return;

        buildingsContainer.innerHTML = '';
        this.selectedBuildingId = null;

        try {
            this.allBuildings = await this.apiRequest('buildings');
            if (this.allBuildings.length === 0) {
                 buildingsContainer.innerHTML = '<p class="muted">No buildings found.</p>';
            } else {
                 this.allBuildings.forEach(building => {
                     buildingsContainer.appendChild(this.createBuildingCard(building));
                 });
            }
        } catch (error) {
             buildingsContainer.innerHTML = '<p class="muted">Failed to load buildings. Please try again later.</p>';
        }
    },

    createBuildingCard(building) {
        const card = document.createElement('div');
        card.className = 'building-card';
        card.dataset.buildingId = building.id;
        const startTime = building.start_time || '20:00';

        card.innerHTML = `
            <div class="building-header">
                <button class="toggle-btn">+</button>
                <h2 class="building-title">${this.escapeHtml(building.name)} (ID: ${building.id})</h2>
                <div class="building-actions">
                    <button class="bulk-btn bulk-disarm">Set Ignore Flags</button>
                </div>
                <div class="building-time-control">
                    <label>Start Time:</label>
                    <input type="time" class="time-input start-time-input" value="${startTime}" required />
                    <button class="time-save-btn">Save</button>
                </div>
                <div class="building-status"></div>
            </div>
            <div class="building-body" style="display:none;">
                <div class="building-controls">
                    <input type="text" class="item-search" placeholder="Search proevents..."/>
                </div>
                <ul class="items-list"></ul>
                <div class="building-loader" style="display:none;">Loading...</div>
            </div>
        `;
        this.setupBuildingCardEvents(card);
        return card;
    },

    setupBuildingCardEvents(card) {
        const buildingId = card.dataset.buildingId;
        const itemsList = card.querySelector('.items-list');
        const header = card.querySelector('.building-header');
        const body = card.querySelector('.building-body');
        const toggleBtn = card.querySelector('.toggle-btn');
        const startTimeInput = card.querySelector('.start-time-input');
        const timeSaveBtn = card.querySelector('.time-save-btn');
        const ignoreFlagsBtn = card.querySelector('.bulk-disarm');
        const itemSearch = card.querySelector('.item-search');

        if (!itemsList || !header || !body || !toggleBtn || !startTimeInput || !timeSaveBtn || !ignoreFlagsBtn || !itemSearch) {
             console.error("Failed to find all elements within building card for ID:", buildingId);
             card.style.opacity = '0.5';
             card.style.pointerEvents = 'none';
             return;
        }

        const toggleVisibility = async () => {
            const isHidden = body.style.display === 'none';
            if (isHidden) {
                try {
                    if (!itemsList.dataset.loaded || itemsList.children.length === 0 || itemsList.children[0].classList.contains('muted')) {
                         await this.loadItemsForBuilding(card);
                         itemsList.dataset.loaded = 'true';
                    }
                    body.style.display = 'block';
                    toggleBtn.textContent = '-';
                } catch (error) {
                     console.error(`Error loading items for building ${buildingId} on toggle:`, error);
                     itemsList.innerHTML = '<li class="muted">Error loading proevents.</li>';
                     body.style.display = 'block';
                     toggleBtn.textContent = '-';
                     itemsList.dataset.loaded = 'false';
                }
            } else {
                body.style.display = 'none';
                toggleBtn.textContent = '+';
            }
        };

        header.addEventListener('click', (e) => {
            if (!e.target.closest('.building-time-control') && !e.target.closest('.building-actions') && !e.target.closest('.toggle-btn')) {
                toggleVisibility();
            }
        });
        
        toggleBtn.addEventListener('click', (e) => {
             e.stopPropagation();
             toggleVisibility();
        });

        timeSaveBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const startTime = startTimeInput.value;

            if (!startTime) {
                this.showNotification('Start time is required.', true);
                return;
            }

            try {
                await this.apiRequest(`buildings/${buildingId}/time`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        building_id: parseInt(buildingId),
                        start_time: startTime
                    })
                });
                this.showNotification('Building schedule updated successfully');
                 const buildingIndex = this.allBuildings.findIndex(b => b.id === parseInt(buildingId));
                 if (buildingIndex > -1) {
                     this.allBuildings[buildingIndex].start_time = startTime;
                 }
            } catch (error) {
                 console.error("Failed to save building schedule:", error);
            }
        });

        let searchDebounceTimer;
        itemSearch.addEventListener('input', () => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                 itemsList.dataset.loaded = 'false';
                 this.loadItemsForBuilding(card, true, itemSearch.value.trim());
            }, 400);
        });

        ignoreFlagsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showIgnoreSelectionModal(buildingId);
        });
    },

    async loadItemsForBuilding(card, reset = false, search = '') {
        const buildingId = card.dataset.buildingId;
        const itemsList = card.querySelector('.items-list');
        const loader = card.querySelector('.building-loader');

        if (!itemsList || !loader) {
             console.error("Missing itemsList or loader element in card for building:", buildingId);
             throw new Error("Card structure incomplete.");
        }

        if (reset) itemsList.innerHTML = '';
        loader.style.display = 'block';
        itemsList.style.display = 'none';

        try {
            const items = await this.apiRequest(`devices?building=${buildingId}&limit=${this.BUILD_PAGE_SIZE}&search=${encodeURIComponent(search)}`);
            
            itemsList.innerHTML = '';

            if (items.length === 0) {
                 itemsList.innerHTML = `<li class="muted">${search ? 'No proevents found matching search.' : 'No proevents found.'}</li>`;
            } else {
                 items.forEach(item => {
                     const itemElement = this.createItem(item);
                     if (itemElement) {
                         itemsList.appendChild(itemElement);
                     }
                 });
            }
        } catch(error) {
             console.error(`Error loading items for building ${buildingId}:`, error);
             itemsList.innerHTML = '<li class="muted">Error loading proevents. Please try again.</li>';
             throw error;
        }
        finally {
            loader.style.display = 'none';
            itemsList.style.display = '';
            this.updateBuildingStatus(card);
        }
    },

    createItem(item) {
        if (!item || typeof item.id === 'undefined' || typeof item.name === 'undefined') {
             console.warn("Received invalid item data:", item);
             return null;
        }

        const li = document.createElement('li');
        const state = (item.state || 'unknown').toLowerCase();
        const isIgnored = item.is_ignored;

        li.className = 'device-item';
        li.dataset.itemId = item.id;
        li.dataset.state = state;

        const isArmed = state === 'armed';
        const stateColor = isArmed ? '#ef4444' : '#22c55e';
        const stateClass = isArmed ? 'status-all-armed' : 'state-unknown';

        const ignoredIndicator = isIgnored ? '<span style="color: #9ca3af; font-style: italic;"> (Ignored)</span>' : '';

        li.innerHTML = `
            <span class="device-state-indicator ${stateClass}" style="background-color: ${stateColor};"></span>
            <div class="device-name">
                ${this.escapeHtml(item.name)} (ID: ${item.id})${ignoredIndicator}
            </div>
        `;
        return li;
    },

    updateBuildingStatus(card) {
        const items = card.querySelectorAll('.device-item');
        const statusEl = card.querySelector('.building-status');

        if (!statusEl) return;

        const firstItemIsMuted = items.length === 1 && items[0].classList.contains('muted');

        if (items.length === 0 || firstItemIsMuted) {
            statusEl.textContent = 'No ProEvents';
            statusEl.className = 'building-status status-none-armed';
            return;
        }

        const armedCount = Array.from(items).filter(d => d.dataset.state === 'armed').length;

        if (armedCount === items.length) {
            statusEl.textContent = 'All Armed';
            statusEl.className = 'building-status status-all-armed';
        } else if (armedCount > 0) {
            statusEl.textContent = 'Partially Armed';
            statusEl.className = 'building-status status-partial-armed';
        } else {
            statusEl.textContent = 'All Disarmed';
            statusEl.className = 'building-status status-none-armed';
        }
    },

    async showIgnoreSelectionModal(buildingId) {
        if (!this.elements.ignoreModal || !this.elements.modalTitle || !this.elements.modalItemList ||
            !this.elements.modalConfirmBtn || !this.elements.modalCancelBtn || !this.elements.closeButton ||
            !this.elements.modalSearch || !this.elements.modalSelectAllBtn) {
            console.error("Modal elements not found!");
            this.showNotification("Error: Could not open ignore settings.", true);
            return;
        }

        const { 
            modalTitle, modalItemList, ignoreModal, modalSearch, 
            modalSelectAllBtn, modalConfirmBtn, modalCancelBtn, closeButton 
        } = this.elements;

        modalTitle.textContent = `Select ProEvents to Ignore on Disarm`;
        modalItemList.innerHTML = '<div class="loader">Loading...</div>';
        ignoreModal.style.display = 'block';
        
        modalSearch.value = '';
        modalSelectAllBtn.textContent = 'Select All';
        modalConfirmBtn.disabled = true;
        modalCancelBtn.disabled = false;

        let allModalItems = [];

        const oldConfirmHandler = modalConfirmBtn.__currentClickHandler__; 
        if (oldConfirmHandler) modalConfirmBtn.removeEventListener('click', oldConfirmHandler);
        const oldCancelHandler = modalCancelBtn.__currentClickHandler__;
        if (oldCancelHandler) modalCancelBtn.removeEventListener('click', oldCancelHandler);
        const oldCloseHandler = closeButton.__currentClickHandler__;
        if (oldCloseHandler) closeButton.removeEventListener('click', oldCloseHandler);
        modalSearch.oninput = null;
        modalSelectAllBtn.onclick = null;

        try {
            allModalItems = await this.apiRequest(`devices?building=${buildingId}&limit=10000`);
            modalItemList.innerHTML = '';

            if (allModalItems.length === 0) {
                 modalItemList.innerHTML = '<p class="muted">No proevents found in this building.</p>';
            } else {
                 allModalItems.forEach(item => {
                     if (item && typeof item.id !== 'undefined' && typeof item.name !== 'undefined') {
                         const div = document.createElement('div');
                         div.className = 'device-item';
                         div.dataset.itemId = item.id;
                         div.dataset.buildingFrk = buildingId; 
                         div.dataset.devicePrk = item.id;

                         div.innerHTML = `
                             <div class="device-name">${this.escapeHtml(item.name)} (ID: ${item.id})</div>
                             <label class="ignore-alarm-label">
                                 <input type="checkbox" class="ignore-item-checkbox" ${item.is_ignored ? 'checked' : ''} />
                                 Ignore on Disarm
                             </label>
                         `;
                         modalItemList.appendChild(div);
                     } else {
                          console.warn("Skipping invalid item data in modal:", item);
                     }
                 });
                 modalConfirmBtn.disabled = false;
            }
        } catch (error) {
             console.error("Error loading items into ignore modal:", error);
             modalItemList.innerHTML = '<p class="muted">Error loading proevents. Please try again.</p>';
        }
        
        modalSearch.oninput = () => {
            const query = modalSearch.value.toLowerCase();
            const modalItems = modalItemList.querySelectorAll('.device-item');
            let allVisibleChecked = true;
            let visibleCount = 0;
            
            modalItems.forEach(item => {
                const nameElement = item.querySelector('.device-name');
                if (!nameElement) return;
                
                const name = nameElement.textContent.toLowerCase();
                const isVisible = name.includes(query);
                item.style.display = isVisible ? 'flex' : 'none';

                 if (isVisible) {
                     visibleCount++;
                     const checkbox = item.querySelector('.ignore-item-checkbox');
                     if (checkbox && !checkbox.checked) {
                         allVisibleChecked = false;
                     }
                 }
            });
             modalSelectAllBtn.textContent = (allVisibleChecked && visibleCount > 0) ? 'Deselect All' : 'Select All';
        };
        
        modalSelectAllBtn.onclick = () => {
            const isSelectAll = modalSelectAllBtn.textContent === 'Select All';
            const modalItems = modalItemList.querySelectorAll('.device-item');
            modalItems.forEach(item => {
                if (item.style.display !== 'none') {
                    const checkbox = item.querySelector('.ignore-item-checkbox');
                    if (checkbox) checkbox.checked = isSelectAll;
                }
            });
            modalSelectAllBtn.textContent = isSelectAll ? 'Deselect All' : 'Select All';
        };

        const confirmHandler = async () => {
            const itemsToUpdate = [];
            const itemElements = modalItemList.querySelectorAll('.device-item');
            
            itemElements.forEach(itemEl => {
                const checkbox = itemEl.querySelector('.ignore-item-checkbox');
                const itemId = parseInt(itemEl.dataset.itemId, 10);
                const buildingFrk = parseInt(itemEl.dataset.buildingFrk, 10);
                const devicePrk = parseInt(itemEl.dataset.devicePrk, 10);

                 if (!isNaN(itemId) && !isNaN(buildingFrk) && !isNaN(devicePrk) && checkbox) {
                     itemsToUpdate.push({
                         item_id: itemId,
                         building_frk: buildingFrk,
                         device_prk: devicePrk, 
                         ignore: checkbox.checked
                     });
                 } else {
                      console.warn("Skipping item with invalid data attributes during save:", itemEl);
                 }
            });

            if (itemsToUpdate.length === 0 && allModalItems.length > 0) {
                 this.showNotification("No changes detected or no items to update.", false);
                 closeModal();
                 return;
            } else if (allModalItems.length === 0 && itemsToUpdate.length === 0) {
                 closeModal();
                 return;
            }

            modalConfirmBtn.disabled = true;
            modalCancelBtn.disabled = true; 
            
            try {
                await this.apiRequest('proevents/ignore/bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items: itemsToUpdate })
                });
                this.showNotification('Ignore settings saved. Applying changes...');
                
                await this.apiRequest(`buildings/${buildingId}/reevaluate`, {
                    method: 'POST'
                });
                this.showNotification('Changes applied successfully.');

                const card = document.querySelector(`.building-card[data-building-id='${buildingId}']`);
                if (card) {
                    const itemSearchInput = card.querySelector('.item-search');
                    const cardItemsList = card.querySelector('.items-list');
                    if (cardItemsList) cardItemsList.dataset.loaded = 'false'; 
                    
                    const cardBody = card.querySelector('.building-body');
                    if (cardBody && cardBody.style.display !== 'none') {
                         await this.loadItemsForBuilding(card, true, itemSearchInput ? itemSearchInput.value.trim() : '');
                         if (cardItemsList) cardItemsList.dataset.loaded = 'true';
                    } else {
                         if(cardItemsList) cardItemsList.innerHTML = '';
                    }
                }
                
                closeModal();

            } catch (error) {
                console.error("Failed to save ignore settings or re-evaluate:", error);
                modalConfirmBtn.disabled = false;
                modalCancelBtn.disabled = false;
            }
        };
        
        const closeModal = () => {
             if (!ignoreModal) return;
            
            ignoreModal.style.display = 'none';

            modalSearch.oninput = null;
            modalSelectAllBtn.onclick = null;
            
            const confirmHandlerToRemove = modalConfirmBtn.__currentClickHandler__;
            if (confirmHandlerToRemove) {
                 modalConfirmBtn.removeEventListener('click', confirmHandlerToRemove);
                 modalConfirmBtn.__currentClickHandler__ = null;
            }
            modalConfirmBtn.disabled = false;

            const cancelHandlerToRemove = modalCancelBtn.__currentClickHandler__;
            if (cancelHandlerToRemove) {
                modalCancelBtn.removeEventListener('click', cancelHandlerToRemove);
                modalCancelBtn.__currentClickHandler__ = null;
            }
             modalCancelBtn.disabled = false;

            const closeHandlerToRemove = closeButton.__currentClickHandler__;
             if (closeHandlerToRemove) {
                closeButton.removeEventListener('click', closeHandlerToRemove);
                closeButton.__currentClickHandler__ = null;
            }

            if (modalItemList) modalItemList.innerHTML = '';
        };

        modalConfirmBtn.__currentClickHandler__ = confirmHandler; 
        modalConfirmBtn.addEventListener('click', confirmHandler);
        
        modalCancelBtn.__currentClickHandler__ = closeModal;
        modalCancelBtn.addEventListener('click', closeModal);
        
        closeButton.__currentClickHandler__ = closeModal;
        closeButton.addEventListener('click', closeModal);
    }
};