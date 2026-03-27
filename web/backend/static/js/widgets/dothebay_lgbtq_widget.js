(function () {
    class DoTheBayLgbtqWidget {
        constructor(root, config) {
            this.root = root;
            this.config = {
                title: 'DoTheBay LGBTQ',
                endpoint: '/api/widgets/dothebay-lgbtq',
                rotateMs: 6500,
                refreshMs: 30 * 60 * 1000,
                ...config,
            };
            this.payload = null;
            this.events = [];
            this.index = 0;
            this.rotationTimer = null;
            this.refreshTimer = null;
        }

        init(config) {
            this.config = { ...this.config, ...(config || {}) };
            this.renderShell();
            this.fetchAndRender();
            return this;
        }

        update(data) {
            const payload = data && typeof data === 'object' ? data : null;
            this.applyPayload(payload);
            return this;
        }

        render() {
            this.renderCurrentCard();
            return this;
        }

        destroy() {
            window.clearInterval(this.rotationTimer);
            window.clearInterval(this.refreshTimer);
            this.rotationTimer = null;
            this.refreshTimer = null;
            this.root.innerHTML = '';
        }

        renderShell() {
            this.root.innerHTML = `
                <div class="dtb-widget-shell">
                    <div class="dtb-widget-stage"></div>
                </div>
            `;
        }

        async fetchAndRender() {
            try {
                const response = await fetch(this.config.endpoint, { cache: 'no-store' });
                if (!response.ok) {
                    throw new Error(`Request failed (${response.status})`);
                }
                const payload = await response.json();
                this.applyPayload(payload);
            } catch (error) {
                this.applyPayload({
                    source: this.config.endpoint,
                    fetchedAt: null,
                    stale: true,
                    events: [],
                    error: error.message || 'Unable to load events',
                });
            }
            if (!this.refreshTimer) {
                this.refreshTimer = window.setInterval(() => this.fetchAndRender(), this.config.refreshMs);
            }
        }

        applyPayload(payload) {
            this.payload = payload || {};
            this.events = Array.isArray(this.payload.events) ? this.payload.events : [];
            if (this.index >= this.events.length) {
                this.index = 0;
            }
            this.renderCurrentCard();
            this.configureRotation();
        }

        configureRotation() {
            if (this.rotationTimer) {
                window.clearInterval(this.rotationTimer);
                this.rotationTimer = null;
            }
            if (this.events.length <= 1) {
                return;
            }
            this.rotationTimer = window.setInterval(() => {
                this.index = (this.index + 1) % this.events.length;
                this.renderCurrentCard(true);
            }, Math.max(5000, Number(this.config.rotateMs) || 6500));
        }

        renderCurrentCard(animate = false) {
            const stage = this.root.querySelector('.dtb-widget-stage');
            if (!stage) {
                return;
            }
            const event = this.events[this.index] || null;

            if (!event) {
                stage.innerHTML = `
                    <div class="dtb-event-card dtb-event-empty">
                        <div class="dtb-event-copy">
                            <div class="dtb-title-row">
                                <div class="dtb-title">${this.escapeHtml(this.config.title || 'DoTheBay LGBTQ')}</div>
                            </div>
                            <div class="dtb-empty-title">No LGBTQ events available</div>
                            <div class="dtb-empty-subtitle">${this.payload?.stale ? 'Showing no cached items after a fetch failure.' : 'Check back later for new listings.'}</div>
                        </div>
                    </div>
                `;
                return;
            }

            const href = event.eventUrl || '#';
            const imageStyle = event.imageUrl
                ? `style="background-image:url('${this.escapeAttribute(event.imageUrl)}')"`
                : '';
            const subtitleParts = [event.dateTimeText, event.venue].filter(Boolean);
            const subtitle = subtitleParts.join(' • ');
            const staleBadge = this.payload?.stale ? '<span class="dtb-badge">cached</span>' : '';

            stage.innerHTML = `
                <a class="dtb-event-card ${animate ? 'dtb-event-enter' : ''}" href="${this.escapeAttribute(href)}" target="_blank" rel="noopener noreferrer">
                    <div class="ds-cover-image" ${imageStyle}></div>
                    <div class="dtb-event-overlay"></div>
                    <div class="dtb-event-copy">
                        <div class="dtb-title-row">
                            <div class="dtb-title">${this.escapeHtml(this.config.title || 'DoTheBay LGBTQ')}</div>
                            ${staleBadge}
                        </div>
                        <div class="dtb-event-headline">${this.escapeHtml(event.title || 'Untitled event')}</div>
                        ${subtitle ? `<div class="dtb-event-subtitle">${this.escapeHtml(subtitle)}</div>` : ''}
                        ${event.summary ? `<div class="dtb-event-summary">${this.escapeHtml(event.summary)}</div>` : ''}
                        <div class="dtb-footer">
                            <span>${this.escapeHtml(this.formatFetchedAt(this.payload?.fetchedAt))}</span>
                            <span>${this.index + 1}/${this.events.length}</span>
                        </div>
                    </div>
                </a>
            `;
        }

        formatFetchedAt(value) {
            if (!value) {
                return 'Local events';
            }
            try {
                return `Updated ${new Date(value).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
            } catch (error) {
                return 'Local events';
            }
        }

        escapeHtml(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        escapeAttribute(value) {
            return this.escapeHtml(value);
        }
    }

    window.DoTheBayLgbtqWidget = DoTheBayLgbtqWidget;
})();
