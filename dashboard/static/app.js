document.addEventListener("DOMContentLoaded", () => {
    // State
    let currentTab = "overview";
    let allActivities = [];
    let allCourses = [];
    let currentFypFilter = "all";

    // Elements
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("pageTitle");
    const btnSyncNow = document.getElementById("btnSyncNow");
    const portalStatusBadge = document.getElementById("portalStatusBadge");
    const portalStatusText = document.getElementById("portalStatusText");
    const lastCheckedText = document.getElementById("lastCheckedText");

    // Init
    setupNavigation();
    setupFypFilters();
    loadDashboardData();
    setInterval(loadDashboardData, 30000); // Polling UI data every 30s

    function setupNavigation() {
        navItems.forEach(item => {
            item.addEventListener("click", () => {
                const targetTab = item.getAttribute("data-tab");
                activateTab(targetTab);
            });
        });

        // Sync Now action
        if (btnSyncNow) {
            btnSyncNow.addEventListener("click", async () => {
                btnSyncNow.disabled = true;
                btnSyncNow.innerHTML = `<span class="sync-icon">⏳</span><span class="sync-text">Syncing...</span>`;
                try {
                    const res = await fetch("/api/trigger-check", { method: "POST" });
                    const data = await res.json();
                    setTimeout(() => {
                        btnSyncNow.disabled = false;
                        btnSyncNow.innerHTML = `<span class="sync-icon">🔄</span><span class="sync-text">Sync Portal Now</span>`;
                        loadDashboardData();
                    }, 2500);
                } catch (e) {
                    alert("Failed to initiate sync: " + e.message);
                    btnSyncNow.disabled = false;
                    btnSyncNow.innerHTML = `<span class="sync-icon">🔄</span><span class="sync-text">Sync Portal Now</span>`;
                }
            });
        }

        // Table filters
        const searchInput = document.getElementById("searchActivities");
        if (searchInput) searchInput.addEventListener("input", renderActivitiesTable);
        const filterType = document.getElementById("filterType");
        if (filterType) filterType.addEventListener("change", renderActivitiesTable);
        const filterStatus = document.getElementById("filterStatus");
        if (filterStatus) filterStatus.addEventListener("change", renderActivitiesTable);

        // Timeline filter
        const filterTimeline = document.getElementById("filterTimelineCourse");
        if (filterTimeline) filterTimeline.addEventListener("change", renderTimeline);

        // AI Copilot events
        document.querySelectorAll(".ai-prompt-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const prompt = chip.getAttribute("data-prompt");
                const input = document.getElementById("aiUserInput");
                if (input) input.value = prompt;
                sendAiQuery(prompt);
            });
        });

        const btnSendAi = document.getElementById("btnSendAiQuery");
        if (btnSendAi) {
            btnSendAi.addEventListener("click", () => {
                const input = document.getElementById("aiUserInput");
                if (input && input.value.trim()) {
                    sendAiQuery(input.value.trim());
                    input.value = "";
                }
            });
        }

        const aiInput = document.getElementById("aiUserInput");
        if (aiInput) {
            aiInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") {
                    if (aiInput.value.trim()) {
                        sendAiQuery(aiInput.value.trim());
                        aiInput.value = "";
                    }
                }
            });
        }

        const btnSimGpa = document.getElementById("btnSimulateGpa");
        if (btnSimGpa) btnSimGpa.addEventListener("click", simulateGpa);

        const btnCalcFinal = document.getElementById("btnCalcFinal");
        if (btnCalcFinal) btnCalcFinal.addEventListener("click", calculateFinalMarks);

        // Settings form
        const settingsForm = document.getElementById("settingsForm");
        if (settingsForm) settingsForm.addEventListener("submit", saveSettings);
        const btnTestWhatsapp = document.getElementById("btnTestWhatsApp");
        if (btnTestWhatsapp) btnTestWhatsapp.addEventListener("click", sendTestWhatsApp);
    }

    function activateTab(targetTab) {
        if (!targetTab) return;
        currentTab = targetTab;

        // Nav active state
        navItems.forEach(i => {
            if (i.getAttribute("data-tab") === targetTab) {
                i.classList.add("active");
                if (pageTitle) {
                    const labelSpan = i.querySelector(".nav-label");
                    pageTitle.innerText = labelSpan ? labelSpan.innerText : targetTab.toUpperCase();
                }
            } else {
                i.classList.remove("active");
            }
        });

        // Tab pane active state
        document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
        const targetPane = document.getElementById(`pane-${targetTab}`);
        if (targetPane) {
            targetPane.classList.add("active");
        }

        // Sub-pane hooks
        if (targetTab === "margin-guard") {
            populateCourseDropdown();
            loadMarginReport();
        } else if (targetTab === "rubric-auditor") {
            loadAuditHistory();
        } else if (targetTab === "fyp") {
            renderFypCommandCenter();
        }
    }

    function setupFypFilters() {
        document.querySelectorAll(".fyp-filter-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".fyp-filter-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                currentFypFilter = btn.getAttribute("data-fyp-filter") || "all";
                renderFypCommandCenter();
            });
        });
    }

    async function loadDashboardData() {
        try {
            await Promise.all([
                fetchOverview(),
                fetchCourses(),
                fetchActivities(),
                fetchNotifications(),
                fetchSettings()
            ]);
        } catch (e) {
            console.error("Error loading dashboard data:", e);
        }
    }

    async function fetchOverview() {
        try {
            const res = await fetch("/api/overview");
            const data = await res.json();

            // Stats counters
            setInnerText("statUpcoming24h", data.upcoming_24h || 0);
            setInnerText("statPending", data.pending_assignments || 0);
            setInnerText("statSubmitted", data.submitted_count || 0);
            setInnerText("statOverdue", data.overdue_count || 0);
            setInnerText("statTotalCourses", data.total_courses || 10);
            setInnerText("navCourseCount", data.total_courses || 10);
            setInnerText("coursesTotalBadge", `${data.total_courses || 10} Subjects Monitored`);

            // FYP activities count
            if (data.fyp_activities_count !== undefined) {
                setInnerText("statFypActivities", data.fyp_activities_count);
            }

            // Executive profile metrics
            if (data.profile) {
                setInnerText("ovCurrentCgpa", data.profile.current_cgpa ? data.profile.current_cgpa.toFixed(2) : "2.53");
                setInnerText("ovCreditHours", `${data.profile.completed_credits || 104} Credit Hours`);
                setInnerText("ovTargetGpa", data.profile.target_gpa ? data.profile.target_gpa.toFixed(2) : "4.00");
                setInnerText("topbarGpaTarget", data.profile.target_gpa ? data.profile.target_gpa.toFixed(2) : "4.00");
                if (data.profile.latest_sgpa !== undefined) {
                    setInnerText("ovLatestSgpa", data.profile.latest_sgpa.toFixed(2));
                }
                if (data.profile.latest_term) {
                    setInnerText("ovLatestTerm", data.profile.latest_term);
                }

                // Sync simulator inputs if present
                const simCgpaInput = document.getElementById("simCurrentCgpa");
                if (simCgpaInput && !simCgpaInput.dataset.userEdited) {
                    simCgpaInput.value = data.profile.current_cgpa ? data.profile.current_cgpa.toFixed(2) : "2.53";
                }
                const simCreditsInput = document.getElementById("simCredits");
                if (simCreditsInput && !simCreditsInput.dataset.userEdited) {
                    simCreditsInput.value = data.profile.completed_credits || 104;
                }

                // Render transcript table if terms exist
                if (data.profile.terms && data.profile.terms.length > 0) {
                    renderTranscriptTable(data.profile.terms);
                }
            }
            if (data.avg_attendance !== undefined) {
                setInnerText("ovAvgAttendance", `${data.avg_attendance.toFixed(1)}%`);
            }

            // Portal status
            if (portalStatusText && portalStatusBadge) {
                if (data.portal_status === "OK") {
                    portalStatusText.innerText = "Portal Connected";
                    portalStatusBadge.style.color = "var(--success)";
                } else {
                    portalStatusText.innerText = "Check Warning: " + (data.portal_last_error || "Offline");
                    portalStatusBadge.style.color = "var(--critical)";
                }
            }

            if (data.portal_last_checked && lastCheckedText) {
                const dt = new Date(data.portal_last_checked);
                lastCheckedText.innerText = "Last checked: " + dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            }
        } catch (e) {
            console.warn("fetchOverview error:", e);
        }
    }

    async function fetchCourses() {
        try {
            const res = await fetch("/api/courses");
            allCourses = await res.json();
            renderCoursesGrid();
            populateCourseFilter();
            populateCourseDropdown();
        } catch (e) {
            console.warn("fetchCourses error:", e);
        }
    }

    async function fetchActivities() {
        try {
            const res = await fetch("/api/activities");
            allActivities = await res.json();

            // Update badge counters
            const upcomingCount = allActivities.filter(a => a.deadline && a.remaining_hours !== null && a.remaining_hours <= 72).length;
            setInnerText("navDeadlineCount", upcomingCount);

            renderUrgentList();
            renderTimeline();
            renderActivitiesTable();
            renderFypCommandCenter();
        } catch (e) {
            console.warn("fetchActivities error:", e);
        }
    }

    async function fetchNotifications() {
        try {
            const res = await fetch("/api/notifications");
            const logs = await res.json();
            renderNotifications(logs);
        } catch (e) {
            console.warn("fetchNotifications error:", e);
        }
    }

    async function fetchSettings() {
        try {
            const res = await fetch("/api/settings");
            const settings = await res.json();
            
            setValueIfElem("settingInterval", settings.check_interval_minutes);
            setValueIfElem("settingProvider", settings.whatsapp_provider);
            setValueIfElem("settingPhone", settings.whatsapp_to_number);
            if (settings.reminder_hours) {
                setValueIfElem("settingReminderHours", settings.reminder_hours.replace(/[\[\]]/g, ''));
            }
            setValueIfElem("settingDailyTime", settings.daily_summary_time);
            setValueIfElem("settingCurrentCgpa", settings.current_cgpa || "2.53");
            setValueIfElem("settingCompletedCredits", settings.completed_credits || "104");
            setValueIfElem("settingTargetGpa", settings.target_gpa || "4.00");
        } catch (e) {
            console.warn("fetchSettings error:", e);
        }
    }

    function renderUrgentList() {
        const container = document.getElementById("urgentDeadlinesList");
        if (!container) return;

        const urgentItems = allActivities.filter(a => 
            a.deadline && 
            a.remaining_hours !== null && 
            a.remaining_hours <= 72 && 
            a.submission_status !== "Submitted" && 
            a.submission_status !== "Graded"
        );

        if (urgentItems.length === 0) {
            container.innerHTML = `<p class="empty-state">No urgent deadlines within 72 hours! 🎉 All tasks are on schedule.</p>`;
            return;
        }

        container.innerHTML = urgentItems.map(item => `
            <div class="urgent-item ${item.remaining_hours <= 24 ? 'critical' : 'high'}">
                <div class="urgent-info">
                    <h4>${escapeHtml(item.title)}</h4>
                    <div class="urgent-meta">
                        📚 <strong>${escapeHtml(item.course_name)}</strong> • ⏳ Due: ${formatDate(item.deadline)}
                    </div>
                </div>
                <div class="countdown-pill ${item.remaining_hours <= 24 ? 'urgent' : ''}">
                    ⏱️ ${escapeHtml(item.remaining_str)}
                </div>
            </div>
        `).join("");
    }

    function renderTimeline() {
        const container = document.getElementById("timelineContainer");
        if (!container) return;
        const filterElem = document.getElementById("filterTimelineCourse");
        const courseFilter = filterElem ? filterElem.value : "";

        let filtered = allActivities.filter(a => a.deadline);
        if (courseFilter) {
            filtered = filtered.filter(a => a.course_id === courseFilter);
        }

        if (filtered.length === 0) {
            container.innerHTML = `<p class="empty-state">No upcoming deadlines found for this selection.</p>`;
            return;
        }

        filtered.sort((a, b) => new Date(a.deadline) - new Date(b.deadline));

        container.innerHTML = filtered.map(item => `
            <div class="timeline-item ${item.remaining_hours !== null && item.remaining_hours <= 24 ? 'critical' : ''}">
                <div class="timeline-info">
                    <h4>${escapeHtml(item.title)}</h4>
                    <div class="timeline-meta">
                        <strong>${escapeHtml(item.course_name)}</strong> • [${escapeHtml(item.activity_type)}] • Status: <span class="badge ${item.submission_status === 'Submitted' ? 'badge-success' : 'badge-high'}">${escapeHtml(item.submission_status)}</span>
                    </div>
                </div>
                <div class="timeline-deadline">
                    <span class="countdown-pill ${item.remaining_hours !== null && item.remaining_hours <= 24 ? 'urgent' : ''}">
                        ${escapeHtml(item.remaining_str)}
                    </span>
                </div>
            </div>
        `).join("");
    }

    // ================================================================
    //  DEDICATED FYP COMMAND CENTER RENDERING
    // ================================================================

    function renderFypCommandCenter() {
        const container = document.getElementById("fypCardsGrid");
        if (!container) return;

        const fypActivities = allActivities.filter(a => a.is_fyp);
        
        // Update files count
        const filesCount = fypActivities.filter(a => a.local_file_path || a.attachment_url).length;
        setInnerText("fypFilesCount", `${filesCount} Files`);

        let filtered = fypActivities;
        if (currentFypFilter !== "all") {
            filtered = fypActivities.filter(a => a.activity_type === currentFypFilter);
        }

        if (filtered.length === 0) {
            container.innerHTML = `<p class="empty-state" style="grid-column: 1/-1;">No items found under filter '${currentFypFilter}'.</p>`;
            return;
        }

        container.innerHTML = filtered.map(item => {
            const hasLocalFile = Boolean(item.local_file_path);
            const fileName = hasLocalFile ? item.local_file_path.split(/[\\/]/).pop() : item.attachment_name;
            const ext = fileName && fileName.includes('.') ? fileName.split('.').pop().toUpperCase() : 'FILE';

            let typeIcon = '📄';
            if (ext === 'PDF') typeIcon = '📕';
            else if (ext === 'DOCX' || ext === 'DOC') typeIcon = '📘';
            else if (ext === 'XLSX' || ext === 'XLS') typeIcon = '📗';
            else if (ext === 'PPTX' || ext === 'PPT') typeIcon = '📙';

            return `
            <div class="fyp-item-card ${hasLocalFile ? 'has-file' : ''}">
                <div>
                    <div class="fyp-item-header">
                        <span class="fyp-item-type">${escapeHtml(item.activity_type)}</span>
                        <span class="badge ${item.submission_status === 'Submitted' ? 'badge-success' : 'badge-subtle'}">
                            ${escapeHtml(item.submission_status)}
                        </span>
                    </div>

                    <div class="fyp-item-title">${escapeHtml(item.title)}</div>

                    ${item.description ? `
                        <div class="fyp-item-desc">${escapeHtml(item.description.substring(0, 150))}${item.description.length > 150 ? '...' : ''}</div>
                    ` : ''}

                    ${item.ai_summary ? `
                        <div class="fyp-ai-brief-box">
                            <strong>🤖 Gemini 3.8 Brief:</strong><br>${escapeHtml(item.ai_summary)}
                        </div>
                    ` : ''}
                </div>

                <div class="fyp-item-footer">
                    <div>
                        ${hasLocalFile ? `
                            <span class="fyp-file-tag">${typeIcon} <strong>${escapeHtml(ext)}</strong> Ready Offline</span>
                        ` : (item.deadline ? `
                            <span style="font-size: 11px; color: var(--text-muted);">Due: ${formatDate(item.deadline)}</span>
                        ` : `<span style="font-size: 11px; color: var(--text-muted);">Design Project Track</span>`)}
                    </div>

                    <div>
                        ${hasLocalFile ? `
                            <a href="/api/download-file?path=${encodeURIComponent(item.local_file_path)}" class="btn btn-gold btn-sm">
                                💾 Download ${escapeHtml(ext)}
                            </a>
                        ` : (item.attachment_url ? `
                            <a href="${escapeHtml(item.attachment_url)}" target="_blank" class="btn btn-outline btn-sm">
                                📎 Portal File
                            </a>
                        ` : `
                            <a href="${escapeHtml(item.portal_url)}" target="_blank" class="btn btn-outline btn-sm">
                                🔗 Open Portal
                            </a>
                        `)}
                    </div>
                </div>
            </div>
            `;
        }).join("");
    }

    // ================================================================
    //  COURSES GRID RENDERING
    // ================================================================

    function renderCoursesGrid() {
        const container = document.getElementById("coursesGrid");
        if (!container) return;

        if (allCourses.length === 0) {
            container.innerHTML = `<p class="empty-state">No courses detected yet. Run a sync to discover enrolled subjects.</p>`;
            return;
        }

        container.innerHTML = allCourses.map(c => {
            const att = (typeof c.attendance_pct === 'number') ? c.attendance_pct : 100.0;
            const attClass = att >= 85.0 ? 'safe' : (att >= 75.0 ? 'warning' : 'critical');
            const attBadgeClass = att >= 85.0 ? 'badge-success' : (att >= 75.0 ? 'badge-high' : 'badge-critical');
            const isFyp = c.is_fyp || (c.name && c.name.toLowerCase().includes('design project'));

            return `
            <div class="course-card ${isFyp ? 'fyp-card' : ''}">
                <div>
                    <div class="course-card-header">
                        <div>
                            <div class="course-title">
                                ${isFyp ? '<span class="badge badge-gold-glow" style="margin-right:6px; font-size:10px;">🎓 FYP</span>' : ''}
                                ${escapeHtml(c.name)}
                            </div>
                            <div class="course-code">${escapeHtml(c.code || c.course_id)} ${c.instructor ? '• ' + escapeHtml(c.instructor) : ''}</div>
                        </div>
                        <span class="badge ${c.pending_tasks > 0 ? 'badge-high' : 'badge-low'}">
                            ${c.pending_tasks} Pending
                        </span>
                    </div>

                    <div class="course-att-row">
                        <div class="att-labels">
                            <span style="color:var(--text-secondary); font-size:12px;">Attendance Status</span>
                            <span class="badge ${attBadgeClass}" style="font-weight:700;">${att.toFixed(1)}%</span>
                        </div>
                        <div class="att-track">
                            <div class="att-fill ${attClass}" style="width: ${Math.min(100, Math.max(0, att))}%;"></div>
                        </div>
                    </div>
                </div>

                <div class="course-card-actions">
                    <span style="font-size: 12px; color: var(--text-muted);">
                        📋 <strong>${c.total_activities}</strong> items tracked
                    </span>
                    <a href="${escapeHtml(c.url)}" target="_blank" class="btn btn-outline btn-sm">
                        🔗 Open on Portal
                    </a>
                </div>
            </div>
            `;
        }).join("");
    }

    function populateCourseFilter() {
        const select = document.getElementById("filterTimelineCourse");
        if (!select) return;
        select.innerHTML = `<option value="">All Courses</option>` + 
            allCourses.map(c => `<option value="${c.course_id}">${escapeHtml(c.name)}</option>`).join("");
    }

    // ================================================================
    //  ACTIVITIES & DOCUMENT INTELLIGENCE TABLE
    // ================================================================

    function renderActivitiesTable() {
        const tbody = document.getElementById("activitiesTableBody");
        if (!tbody) return;

        const searchInput = document.getElementById("searchActivities");
        const query = searchInput ? searchInput.value.toLowerCase() : "";
        const typeFilterElem = document.getElementById("filterType");
        const typeFilter = typeFilterElem ? typeFilterElem.value : "";
        const statusFilterElem = document.getElementById("filterStatus");
        const statusFilter = statusFilterElem ? statusFilterElem.value : "";

        let filtered = allActivities.filter(a => {
            const matchesQuery = !query || 
                a.title.toLowerCase().includes(query) || 
                a.course_name.toLowerCase().includes(query) ||
                (a.description && a.description.toLowerCase().includes(query));
            
            const matchesType = !typeFilter || a.activity_type === typeFilter;
            const matchesStatus = !statusFilter || a.submission_status === statusFilter;

            return matchesQuery && matchesType && matchesStatus;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No matching activities found.</td></tr>`;
            return;
        }

        tbody.innerHTML = filtered.map(a => {
            const badgeClass = `badge-${a.priority.toLowerCase()}`;
            const hasLocalFile = Boolean(a.local_file_path);
            const hasAiBrief = Boolean(a.ai_summary);

            return `
                <tr>
                    <td>
                        <span class="badge ${badgeClass}">${a.priority}</span>
                        ${a.is_fyp ? '<div style="margin-top:4px;"><span class="badge badge-gold-glow" style="font-size:9px;">🎓 FYP</span></div>' : ''}
                    </td>
                    <td><strong>${escapeHtml(a.activity_type)}</strong></td>
                    <td><span style="font-weight:600;">${escapeHtml(a.course_name)}</span></td>
                    <td>
                        <div style="font-weight: 700; color: #fff;">${escapeHtml(a.title)}</div>
                        
                        <!-- Document Intelligence Pipeline Stepper -->
                        <div class="doc-pipeline-bar">
                            <span class="pipe-step done">🌐 Extracted</span>
                            <span class="pipe-arrow">➔</span>
                            <span class="pipe-step ${hasLocalFile ? 'done' : ''}">${hasLocalFile ? '📥 Downloaded' : '⏳ Remote File'}</span>
                            <span class="pipe-arrow">➔</span>
                            <span class="pipe-step ${hasAiBrief ? 'done' : ''}">${hasAiBrief ? '🧠 Gemini Brief' : 'AI Pending'}</span>
                        </div>

                        ${a.ai_summary ? `
                            <div style="margin-top: 8px; font-size: 12px; color: #c7d2fe; background: rgba(99,102,241,0.08); padding: 8px 12px; border-radius: 6px; border-left: 3px solid #818cf8; white-space: pre-line; line-height: 1.45;">
                                <strong>🤖 AI Executive Brief:</strong><br>${escapeHtml(a.ai_summary)}
                            </div>
                        ` : ''}

                        <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
                            ${hasLocalFile ? `
                                <a href="/api/download-file?path=${encodeURIComponent(a.local_file_path)}" class="btn btn-outline btn-sm" style="font-size: 11px; padding: 3px 10px; color: #34d399; border-color: rgba(16,185,129,0.4);">
                                    💾 Download File
                                </a>
                            ` : (a.attachment_url ? `
                                <a href="${escapeHtml(a.attachment_url)}" target="_blank" style="font-size: 11px; color: var(--primary);">📎 Attachment</a>
                            ` : '')}
                        </div>
                    </td>
                    <td>
                        <div style="font-weight:600;">${formatDate(a.deadline)}</div>
                        <small style="color: var(--text-muted);">${escapeHtml(a.remaining_str)}</small>
                    </td>
                    <td>
                        <span class="badge ${a.submission_status === 'Submitted' ? 'badge-success' : 'badge-high'}">
                            ${escapeHtml(a.submission_status)}
                        </span>
                    </td>
                    <td>
                        <a href="${escapeHtml(a.portal_url)}" target="_blank" class="btn btn-outline btn-sm">
                            Open
                        </a>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function renderNotifications(logs) {
        const container = document.getElementById("notificationsLogList");
        const recentContainer = document.getElementById("recentAlertsList");

        if (logs.length === 0) {
            if (container) container.innerHTML = `<p class="empty-state">No notifications dispatched yet.</p>`;
            if (recentContainer) recentContainer.innerHTML = `<p class="empty-state">No recent alerts recorded yet.</p>`;
            return;
        }

        if (recentContainer) {
            recentContainer.innerHTML = logs.slice(0, 4).map(l => `
                <div class="notif-item">
                    <div class="notif-header">
                        <span class="notif-type">${escapeHtml(l.notification_type)}</span>
                        <span class="notif-time">${new Date(l.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                    <div class="notif-msg">${escapeHtml(l.message_text.substring(0, 100))}...</div>
                </div>
            `).join("");
        }

        if (container) {
            container.innerHTML = logs.map(l => `
                <div class="card" style="margin-bottom: 12px; padding: 16px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                        <span class="badge badge-${l.priority.toLowerCase()}">${l.priority}</span>
                        <span style="font-size: 12px; color: var(--text-muted);">${new Date(l.sent_at).toLocaleString()}</span>
                    </div>
                    <div style="font-size: 13px; line-height: 1.5; white-space: pre-wrap;">${escapeHtml(l.message_text)}</div>
                </div>
            `).join("");
        }
    }

    async function saveSettings(e) {
        e.preventDefault();
        const settings = {
            check_interval_minutes: document.getElementById("settingInterval").value,
            whatsapp_provider: document.getElementById("settingProvider").value,
            whatsapp_to_number: document.getElementById("settingPhone").value,
            reminder_hours: JSON.stringify(document.getElementById("settingReminderHours").value.split(",").map(n => parseInt(n.trim()))),
            daily_summary_time: document.getElementById("settingDailyTime").value,
            current_cgpa: document.getElementById("settingCurrentCgpa") ? document.getElementById("settingCurrentCgpa").value : "2.50",
            completed_credits: document.getElementById("settingCompletedCredits") ? document.getElementById("settingCompletedCredits").value : "100",
            target_gpa: document.getElementById("settingTargetGpa") ? document.getElementById("settingTargetGpa").value : "4.00"
        };

        try {
            const res = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ settings })
            });
            const data = await res.json();
            alert("Settings saved successfully!");
            fetchOverview();
        } catch (err) {
            alert("Failed to save settings: " + err.message);
        }
    }

    async function sendTestWhatsApp() {
        const phone = document.getElementById("settingPhone").value;
        if (!phone) {
            alert("Please enter a contact phone number or handle first.");
            return;
        }

        try {
            const res = await fetch("/api/send-test-whatsapp", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ phone_number: phone })
            });
            const data = await res.json();
            alert(data.message || "Test alert dispatched!");
            fetchNotifications();
        } catch (err) {
            alert("Alert test error: " + err.message);
        }
    }

    function formatDate(dateStr) {
        if (!dateStr) return "No deadline";
        const d = new Date(dateStr);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    // ================================================================
    //  AI COPILOT & GPA FUNCTIONS
    // ================================================================

    async function sendAiQuery(queryText) {
        const chatContainer = document.getElementById("aiChatMessages");
        if (!chatContainer) return;

        // 1. Add User Message
        const userDiv = document.createElement("div");
        userDiv.className = "ai-message user";
        userDiv.innerHTML = `<div class="ai-bubble">${escapeHtml(queryText)}</div>`;
        chatContainer.appendChild(userDiv);

        // 2. Add Assistant Thinking Bubble
        const assistantDiv = document.createElement("div");
        assistantDiv.className = "ai-message assistant";
        assistantDiv.innerHTML = `
            <div class="ai-avatar">🤖</div>
            <div class="ai-bubble"><em>Analyzing portal data and calculating insights...</em></div>
        `;
        chatContainer.appendChild(assistantDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        try {
            const res = await fetch("/api/ai/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query: queryText })
            });
            const data = await res.json();
            
            let formatted = escapeHtml(data.response || "No response received.")
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');

            assistantDiv.querySelector(".ai-bubble").innerHTML = formatted;
        } catch (err) {
            assistantDiv.querySelector(".ai-bubble").innerHTML = `⚠️ Error querying Academic Agent: ${escapeHtml(err.message)}`;
        }
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async function simulateGpa() {
        const curCgpa = parseFloat(document.getElementById("simCurrentCgpa").value) || 2.53;
        const credits = parseInt(document.getElementById("simCredits").value) || 104;
        const targetGpa = parseFloat(document.getElementById("simTargetGpa").value) || 4.00;
        const resultBox = document.getElementById("gpaResultBox");
        if (!resultBox) return;

        resultBox.innerHTML = `<em>Simulating CUST degree progression...</em>`;

        try {
            const res = await fetch("/api/gpa/projection");
            const data = await res.json();

            const semCredits = 15;
            const newTotalQp = (curCgpa * credits) + (targetGpa * semCredits);
            const newCgpa = (newTotalQp / (credits + semCredits)).toFixed(2);
            const diff = (newCgpa - curCgpa).toFixed(2);
            const maxCgpa = (((curCgpa * credits) + (4.0 * semCredits)) / (credits + semCredits)).toFixed(2);

            resultBox.innerHTML = `
                <div style="font-weight: 700; font-size: 14px; margin-bottom: 6px;">
                    🎯 Projected Degree CGPA: <span style="font-size: 16px; color: #34d399;">${newCgpa}</span> 
                    (${diff >= 0 ? '+' : ''}${diff})
                </div>
                <div style="margin-bottom: 6px;">
                    • Target Semester GPA: <strong>${targetGpa.toFixed(2)}</strong> (based on 15 credits)<br>
                    • Absolute Mathematical Ceiling: <strong>${maxCgpa}</strong> (with straight A's)
                </div>
                ${data.advising && data.advising.length > 0 ? `
                    <div style="margin-top: 8px; font-size: 12px; color: #fde68a;">
                        <strong>💡 Academic Advisor Insights:</strong><br>
                        ${data.advising.map(a => `• ${escapeHtml(a)}`).join('<br>')}
                    </div>
                ` : ''}
            `;
        } catch (e) {
            resultBox.innerHTML = `⚠️ Error: ${escapeHtml(e.message)}`;
        }
    }

    function renderTranscriptTable(terms) {
        const tbody = document.getElementById("transcriptTableBody");
        if (!tbody) return;

        if (!terms || terms.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 20px; color: var(--text-muted);">No transcript records synced yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = terms.map((t, idx) => {
            const isLatest = idx === terms.length - 1;
            const sgpaNum = parseFloat(t.sgpa);
            const sgpaColor = sgpaNum >= 3.5 ? 'var(--gold)' : (sgpaNum >= 2.5 ? 'var(--success)' : 'var(--warning)');
            const statusBadge = isLatest 
                ? `<span class="badge badge-gold-glow">Latest Term</span>` 
                : `<span class="badge badge-subtle">Completed</span>`;

            const coursesSummary = (t.courses && t.courses.length > 0)
                ? `<span title="${t.courses.map(c => `${c.course}: ${c.grade} (${c.credit_hours} CH)`).join('\n')}" style="cursor: help; text-decoration: underline dotted;">${t.courses.length} courses</span>`
                : `${t.courses ? t.courses.length : 0} courses`;

            return `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05); ${isLatest ? 'background: rgba(245, 158, 11, 0.08); font-weight: 600;' : ''}">
                    <td style="padding: 12px 14px;">
                        <strong>${escapeHtml(t.term)}</strong>
                        ${isLatest ? ' <span style="font-size: 10px; color: var(--gold);">(Active Baseline)</span>' : ''}
                    </td>
                    <td style="padding: 12px 14px; text-align: right; color: var(--text-muted);">${t.attempted_ch ? Number(t.attempted_ch).toFixed(1) : '-'}</td>
                    <td style="padding: 12px 14px; text-align: right; color: var(--text-muted);">${t.earned_ch ? Number(t.earned_ch).toFixed(1) : '-'}</td>
                    <td style="padding: 12px 14px; text-align: right;"><strong>${t.cumulative_ch ? Number(t.cumulative_ch).toFixed(1) : '-'}</strong></td>
                    <td style="padding: 12px 14px; text-align: right; color: ${sgpaColor}; font-weight: 700;">${sgpaNum.toFixed(2)}</td>
                    <td style="padding: 12px 14px; text-align: right; color: var(--primary); font-weight: 700; font-size: 14px;">${parseFloat(t.cgpa).toFixed(2)}</td>
                    <td style="padding: 12px 14px; text-align: center;">${coursesSummary}</td>
                    <td style="padding: 12px 14px; text-align: center;">${statusBadge}</td>
                </tr>
            `;
        }).join("");
    }

    async function calculateFinalMarks() {
        const sessional = parseFloat(document.getElementById("calcSessionalObtained").value) || 0;
        const sessionalTotal = parseFloat(document.getElementById("calcSessionalTotal").value) || 50;
        const finalTotal = parseFloat(document.getElementById("calcFinalTotal").value) || 50;
        const targetGrade = document.getElementById("calcTargetGrade").value || "A";
        const resultBox = document.getElementById("calcResultBox");
        if (!resultBox) return;

        resultBox.innerHTML = `<em>Calculating required exam score...</em>`;

        try {
            const res = await fetch("/api/gpa/calculate-final", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    sessional_obtained: sessional,
                    sessional_total: sessionalTotal,
                    final_exam_total: finalTotal,
                    target_grade: targetGrade
                })
            });
            const data = await res.json();

            let color = data.is_achievable ? "#34d399" : "#f87171";
            resultBox.innerHTML = `
                <div style="font-weight: 700; color: ${color}; margin-bottom: 4px;">
                    ${escapeHtml(data.status_message)}
                </div>
                <div style="font-size: 12px; color: #94a3b8;">
                    Current Sessional: ${sessional}/${sessionalTotal} (${((sessional/sessionalTotal)*100).toFixed(1)}%) • Target: ${targetGrade} (${data.target_percentage}%)
                </div>
            `;
        } catch (e) {
            resultBox.innerHTML = `⚠️ Calculation failed: ${escapeHtml(e.message)}`;
        }
    }

    // ================================================================
    //  SESSIONAL MARGIN GUARD
    // ================================================================

    async function populateCourseDropdown() {
        const sel = document.getElementById("mgCourseSelect");
        if (!sel) return;
        try {
            const courses = await fetch("/api/courses").then(r => r.json());
            sel.innerHTML = courses.map(c =>
                `<option value="${escapeHtml(c.course_id)}" data-name="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`
            ).join("") || "<option value=''>No courses found</option>";
        } catch (e) {
            sel.innerHTML = "<option value=''>Failed to load</option>";
        }
    }

    async function addMarkEntry() {
        const sel = document.getElementById("mgCourseSelect");
        const course_id = sel ? sel.value : "";
        const course_name = sel && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].dataset.name : course_id;
        const componentElem = document.getElementById("mgComponent");
        const component = componentElem ? componentElem.value.trim() : "";
        const compTypeElem = document.getElementById("mgCompType");
        const component_type = compTypeElem ? compTypeElem.value : "other";
        const obtElem = document.getElementById("mgObtained");
        const obtained = obtElem ? parseFloat(obtElem.value) : NaN;
        const totElem = document.getElementById("mgTotal");
        const total = totElem ? parseFloat(totElem.value) : NaN;
        const msg = document.getElementById("mgSaveMsg");

        if (!course_id || !component || isNaN(obtained) || isNaN(total) || total <= 0) {
            if (msg) { msg.textContent = "⚠️ Fill in all fields correctly."; msg.style.color = "#ef4444"; }
            return;
        }
        if (obtained > total) {
            if (msg) { msg.textContent = "⚠️ Obtained cannot exceed total."; msg.style.color = "#ef4444"; }
            return;
        }

        try {
            const res = await fetch("/api/margin/add-mark", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({course_id, course_name, component, component_type, obtained, total})
            });
            const data = await res.json();
            if (msg) {
                msg.textContent = "✅ Saved!";
                msg.style.color = "#34d399";
                setTimeout(() => { msg.textContent = ""; }, 3000);
            }
            loadMarginReport();
        } catch (e) {
            if (msg) { msg.textContent = "❌ Save failed."; msg.style.color = "#ef4444"; }
        }
    }

    async function loadMarginReport() {
        const container = document.getElementById("mgReportContainer");
        if (!container) return;
        container.innerHTML = "<p class='empty-state'>Loading buffer report...</p>";

        try {
            const data = await fetch("/api/margin/report").then(r => r.json());
            if (!data.courses || data.courses.length === 0) {
                container.innerHTML = "<p class='empty-state'>No marks logged yet. Log component scores above to calculate your 15-mark buffer.</p>";
                return;
            }

            container.innerHTML = data.courses.map(course => {
                const barPct = Math.min(100, course.current_pct || 0);
                const levelClass = course.alert_level;
                const components = (course.components || []).map(c =>
                    `<tr>
                        <td>${escapeHtml(c.component)}</td>
                        <td><span class="badge badge-subtle">${escapeHtml(c.component_type)}</span></td>
                        <td>${c.obtained} / ${c.total}</td>
                        <td><strong>${c.pct}%</strong></td>
                    </tr>`
                ).join("");

                return `
                <div class="mg-course-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4>${escapeHtml(course.course_name)}</h4>
                        <span class="mg-alert-badge ${levelClass}">${levelClass}</span>
                    </div>
                    <div class="mg-bar-wrapper">
                        <div class="mg-bar-fill ${levelClass}" style="width:${barPct}%"></div>
                    </div>
                    <div class="mg-stats">
                        <span>Obtained: <strong>${course.obtained_total} / ${course.possible_total}</strong></span>
                        <span>Current Sessional %: <strong>${course.current_pct}%</strong></span>
                        <span>Buffer until Grade A drops: <strong>${course.marks_buffer} marks</strong></span>
                        <span>Sessional Target: <strong>${course.marks_needed_for_A}</strong></span>
                    </div>
                    <p style="font-size:13px; color:var(--text-secondary); margin-top:8px;">${escapeHtml(course.message)}</p>
                    ${components ? `<table class="mg-components-table"><thead><tr><th>Component</th><th>Type</th><th>Score</th><th>%</th></tr></thead><tbody>${components}</tbody></table>` : ""}
                </div>`;
            }).join("");
        } catch (e) {
            container.innerHTML = `<p class="empty-state">⚠️ Failed to load: ${escapeHtml(e.message)}</p>`;
        }
    }

    // ================================================================
    //  PRE-SUBMISSION RUBRIC AUDITOR
    // ================================================================

    async function runRubricAudit() {
        const draftPath = document.getElementById("raDraftPath").value.trim();
        if (!draftPath) { alert("Please enter the draft file path."); return; }

        const payload = {
            draft_file_path: draftPath,
            activity_id: document.getElementById("raActivityId").value.trim(),
            course_name: document.getElementById("raCourseName").value.trim(),
            assignment_title: document.getElementById("raAssignmentTitle").value.trim(),
            assignment_description: document.getElementById("raDescription").value.trim()
        };

        const resultCard = document.getElementById("raResultCard");
        const resultContent = document.getElementById("raResultContent");
        if (resultCard) resultCard.style.display = "block";
        if (resultContent) resultContent.innerHTML = "<p>🔄 Running Gemini AI Rubric Audit...</p>";

        try {
            const data = await fetch("/api/rubric/audit", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
            }).then(r => r.json());
            renderAuditResult(resultContent, data);
            loadAuditHistory();
        } catch (e) {
            if (resultContent) resultContent.innerHTML = `<p class="empty-state">❌ Audit failed: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function scanSubmissionsFolder() {
        const resultCard = document.getElementById("raResultCard");
        const resultContent = document.getElementById("raResultContent");
        if (resultCard) resultCard.style.display = "block";
        if (resultContent) resultContent.innerHTML = "<p>📂 Scanning submissions/ folder for drafts...</p>";

        try {
            const data = await fetch("/api/rubric/scan-submissions").then(r => r.json());
            if (data.count === 0) {
                resultContent.innerHTML = "<p class='empty-state'>No draft files found in <code>submissions/</code> folder. Drop a .pdf or .docx draft there first.</p>";
                return;
            }
            let html = `<p style="margin-bottom:12px;"><strong>${data.count} draft(s) audited:</strong></p>`;
            data.audits.forEach(a => {
                const div = document.createElement("div");
                div.style.marginBottom = "16px";
                renderAuditResult(div, a);
                html += div.innerHTML;
            });
            resultContent.innerHTML = html;
            loadAuditHistory();
        } catch (e) {
            if (resultContent) resultContent.innerHTML = `<p class="empty-state">❌ Scan failed: ${escapeHtml(e.message)}</p>`;
        }
    }

    function renderAuditResult(container, data) {
        if (!container) return;
        const score = data.coverage_score || 0;
        const scoreClass = score >= 80 ? "high" : score >= 50 ? "medium" : "low";
        const missing = (data.missing_items || []);
        const fmt = (data.formatting_issues || []);

        const missingHtml = missing.length
            ? `<h4 style="margin:14px 0 6px; font-size:14px;">❌ Missing Rubric Requirements (${missing.length})</h4>
               <ul class="ra-checklist">${missing.map(m => `<li><span>❌</span>${escapeHtml(m)}</li>`).join("")}</ul>`
            : `<p style="color:#34d399; margin:10px 0;">✅ All core rubric requirements are addressed!</p>`;

        const fmtHtml = fmt.length
            ? `<h4 style="margin:14px 0 6px; font-size:14px;">⚠️ Formatting / Structure Recommendations (${fmt.length})</h4>
               <ul class="ra-checklist">${fmt.map(f => `<li><span>⚠️</span>${escapeHtml(f)}</li>`).join("")}</ul>`
            : "";

        container.innerHTML = `
            <div class="ra-score-row">
                <div class="ra-score-circle ${scoreClass}">${score}</div>
                <div>
                    <strong style="font-size:16px;">Coverage Score: ${score} / 100</strong>
                    <p style="margin:4px 0; font-size:12px; color:var(--text-secondary);">
                        File: <code>${escapeHtml(data.draft_file)}</code> &nbsp;·&nbsp;
                        Engine: <span class="ra-method-badge">${escapeHtml(data.method)}</span>
                    </p>
                    <p style="margin:6px 0; font-size:13px; color:var(--text-secondary); line-height:1.45;">${escapeHtml(data.audit_result)}</p>
                </div>
            </div>
            ${missingHtml}
            ${fmtHtml}
        `;
    }

    async function loadAuditHistory() {
        const container = document.getElementById("raHistoryContainer");
        if (!container) return;
        try {
            const audits = await fetch("/api/rubric/history?limit=15").then(r => r.json());
            if (!audits.length) {
                container.innerHTML = "<p class='empty-state'>No previous audits recorded.</p>";
                return;
            }
            container.innerHTML = audits.map(a => {
                const score = a.coverage_score;
                const color = score >= 80 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f87171";
                const missing = (a.missing_items || []).length;
                return `<div class="ra-history-row">
                    <span class="ra-history-score" style="color:${color};">${score}</span>
                    <div>
                        <strong>${escapeHtml(a.draft_file)}</strong>
                        ${a.course_name ? `<span style="font-size:11px; color:var(--text-muted);"> · ${escapeHtml(a.course_name)}</span>` : ""}
                        <br><span style="font-size:12px; color:var(--text-secondary);">${escapeHtml(a.audit_result?.slice(0, 110))}...</span>
                    </div>
                    <span class="ra-method-badge">${escapeHtml(a.method)}</span>
                    <span style="font-size:11px; color:var(--text-muted); white-space:nowrap;">
                        ${missing} missing · ${a.audited_at?.slice(0,16).replace("T"," ")}
                    </span>
                </div>`;
            }).join("");
        } catch (e) {
            container.innerHTML = `<p class="empty-state">Failed: ${escapeHtml(e.message)}</p>`;
        }
    }

    // Helper functions
    function setInnerText(elemId, text) {
        const el = document.getElementById(elemId);
        if (el) el.innerText = text;
    }

    function setValueIfElem(elemId, val) {
        const el = document.getElementById(elemId);
        if (el && val !== undefined) el.value = val;
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Window-level exports for onclick handlers in HTML
    window.switchTab = activateTab;
    window.addMarkEntry = addMarkEntry;
    window.loadMarginReport = loadMarginReport;
    window.runRubricAudit = runRubricAudit;
    window.scanSubmissionsFolder = scanSubmissionsFolder;
    window.loadAuditHistory = loadAuditHistory;
});
