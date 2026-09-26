document.addEventListener("DOMContentLoaded", () => {
    // State
    let currentTab = "overview";
    let allActivities = [];
    let allCourses = [];

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
    loadDashboardData();
    setInterval(loadDashboardData, 30000); // Polling UI data every 30s

    function setupNavigation() {
        navItems.forEach(item => {
            item.addEventListener("click", () => {
                const targetTab = item.getAttribute("data-tab");
                navItems.forEach(i => i.classList.remove("active"));
                tabPanes.forEach(p => p.classList.remove("active"));

                item.classList.add("active");
                const targetPane = document.getElementById(`pane-${targetTab}`);
                if (targetPane) targetPane.classList.add("active");

                currentTab = targetTab;
                pageTitle.innerText = item.innerText.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]\s*/g, '');
            });
        });

        // Sync Now action
        btnSyncNow.addEventListener("click", async () => {
            btnSyncNow.disabled = true;
            btnSyncNow.innerText = "⏳ Syncing...";
            try {
                const res = await fetch("/api/trigger-check", { method: "POST" });
                const data = await res.json();
                setTimeout(() => {
                    btnSyncNow.disabled = false;
                    btnSyncNow.innerText = "🔄 Sync Now";
                    loadDashboardData();
                }, 2500);
            } catch (e) {
                alert("Failed to initiate sync: " + e.message);
                btnSyncNow.disabled = false;
                btnSyncNow.innerText = "🔄 Sync Now";
            }
        });

        // Table filters
        document.getElementById("searchActivities").addEventListener("input", renderActivitiesTable);
        document.getElementById("filterType").addEventListener("change", renderActivitiesTable);
        document.getElementById("filterStatus").addEventListener("change", renderActivitiesTable);

        // Timeline filter
        document.getElementById("filterTimelineCourse").addEventListener("change", renderTimeline);

        // AI Copilot events
        document.querySelectorAll(".ai-prompt-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const prompt = chip.getAttribute("data-prompt");
                document.getElementById("aiUserInput").value = prompt;
                sendAiQuery(prompt);
            });
        });

        const btnSendAi = document.getElementById("btnSendAiQuery");
        if (btnSendAi) {
            btnSendAi.addEventListener("click", () => {
                const input = document.getElementById("aiUserInput");
                if (input.value.trim()) {
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
        document.getElementById("settingsForm").addEventListener("submit", saveSettings);
        document.getElementById("btnTestWhatsApp").addEventListener("click", sendTestWhatsApp);
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
        const res = await fetch("/api/overview");
        const data = await res.json();

        document.getElementById("statUpcoming24h").innerText = data.upcoming_24h || 0;
        document.getElementById("statPending").innerText = data.pending_assignments || 0;
        document.getElementById("statSubmitted").innerText = data.submitted_count || 0;
        document.getElementById("statOverdue").innerText = data.overdue_count || 0;

        // Portal status
        if (data.portal_status === "OK") {
            portalStatusText.innerText = "Portal Connected";
            portalStatusBadge.style.color = "var(--success)";
        } else {
            portalStatusText.innerText = "Check Warning: " + (data.portal_last_error || "Offline");
            portalStatusBadge.style.color = "var(--critical)";
        }

        if (data.portal_last_checked) {
            const dt = new Date(data.portal_last_checked);
            lastCheckedText.innerText = "Last checked: " + dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }

    async function fetchCourses() {
        const res = await fetch("/api/courses");
        allCourses = await res.json();
        renderCoursesGrid();
        populateCourseFilter();
    }

    async function fetchActivities() {
        const res = await fetch("/api/activities");
        allActivities = await res.json();
        renderUrgentList();
        renderTimeline();
        renderActivitiesTable();
    }

    async function fetchNotifications() {
        const res = await fetch("/api/notifications");
        const logs = await res.json();
        renderNotifications(logs);
    }

    async function fetchSettings() {
        const res = await fetch("/api/settings");
        const settings = await res.json();
        
        if (settings.check_interval_minutes) {
            document.getElementById("settingInterval").value = settings.check_interval_minutes;
        }
        if (settings.whatsapp_provider) {
            document.getElementById("settingProvider").value = settings.whatsapp_provider;
        }
        if (settings.whatsapp_to_number) {
            document.getElementById("settingPhone").value = settings.whatsapp_to_number;
        }
        if (settings.reminder_hours) {
            document.getElementById("settingReminderHours").value = settings.reminder_hours.replace(/[\[\]]/g, '');
        }
        if (settings.daily_summary_time) {
            document.getElementById("settingDailyTime").value = settings.daily_summary_time;
        }
    }

    function renderUrgentList() {
        const container = document.getElementById("urgentDeadlinesList");
        const urgentItems = allActivities.filter(a => 
            a.deadline && 
            a.remaining_hours !== null && 
            a.remaining_hours <= 72 && 
            a.submission_status !== "Submitted" && 
            a.submission_status !== "Graded"
        );

        if (urgentItems.length === 0) {
            container.innerHTML = `<p class="empty-state">No urgent deadlines within 72 hours! 🎉</p>`;
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
        const courseFilter = document.getElementById("filterTimelineCourse").value;

        let filtered = allActivities.filter(a => a.deadline);
        if (courseFilter) {
            filtered = filtered.filter(a => a.course_id === courseFilter);
        }

        if (filtered.length === 0) {
            container.innerHTML = `<p class="empty-state">No upcoming deadlines found for this selection.</p>`;
            return;
        }

        // Sort by deadline ascending
        filtered.sort((a, b) => new Date(a.deadline) - new Date(b.deadline));

        container.innerHTML = filtered.map(item => `
            <div class="timeline-item ${item.remaining_hours !== null && item.remaining_hours <= 24 ? 'critical' : ''}">
                <div class="timeline-info">
                    <h4>${escapeHtml(item.title)}</h4>
                    <div class="timeline-meta">
                        <strong>${escapeHtml(item.course_name)}</strong> • [${escapeHtml(item.activity_type)}] • Status: ${escapeHtml(item.submission_status)}
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

    function renderCoursesGrid() {
        const container = document.getElementById("coursesGrid");
        if (allCourses.length === 0) {
            container.innerHTML = `<p class="empty-state">No courses detected yet. Run a sync to discover enrolled subjects.</p>`;
            return;
        }

        container.innerHTML = allCourses.map(c => {
            const att = (typeof c.attendance_pct === 'number') ? c.attendance_pct : 100.0;
            const attClass = att < 75.0 ? 'badge-critical' : 'badge-low';
            const isFyp = c.is_fyp || (c.name && c.name.toLowerCase().includes('design project'));

            return `
            <div class="course-card ${isFyp ? 'fyp-card' : ''}">
                <div class="course-card-header">
                    <div>
                        <div class="course-title">
                            ${isFyp ? '<span class="badge" style="background:#f59e0b; color:#fff; font-size:10px; margin-right:4px;">🎓 FYP</span>' : ''}
                            ${escapeHtml(c.name)}
                        </div>
                        <div class="course-code">${escapeHtml(c.code || c.course_id)} ${c.instructor ? '• ' + escapeHtml(c.instructor) : ''}</div>
                    </div>
                    <span class="badge ${c.pending_tasks > 0 ? 'badge-high' : 'badge-low'}">
                        ${c.pending_tasks} Pending
                    </span>
                </div>
                <div class="course-card-body">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 13px;">
                        <span>📊 Attendance:</span>
                        <span class="badge ${attClass}" style="font-weight: 600;">
                            ${att.toFixed(1)}% ${att < 75.0 ? '⚠️' : '✅'}
                        </span>
                    </div>
                    <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
                        Total Activities Tracked: <strong>${c.total_activities}</strong>
                    </p>
                    <a href="${escapeHtml(c.url)}" target="_blank" class="btn btn-outline btn-sm">
                        🔗 Open on ODOCUST
                    </a>
                </div>
            </div>
            `;
        }).join("");
    }

    function populateCourseFilter() {
        const select = document.getElementById("filterTimelineCourse");
        select.innerHTML = `<option value="">All Courses</option>` + 
            allCourses.map(c => `<option value="${c.course_id}">${escapeHtml(c.name)}</option>`).join("");
    }

    function renderActivitiesTable() {
        const tbody = document.getElementById("activitiesTableBody");
        const query = document.getElementById("searchActivities").value.toLowerCase();
        const typeFilter = document.getElementById("filterType").value;
        const statusFilter = document.getElementById("filterStatus").value;

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
            return `
                <tr>
                    <td>
                        <span class="badge ${badgeClass}">${a.priority}</span>
                        ${a.is_fyp ? '<div style="margin-top:4px;"><span class="badge" style="background:#f59e0b; color:#fff; font-size:10px;">🎓 FYP</span></div>' : ''}
                    </td>
                    <td><strong>${escapeHtml(a.activity_type)}</strong></td>
                    <td>${escapeHtml(a.course_name)}</td>
                    <td>
                        <div style="font-weight: 600;">${escapeHtml(a.title)}</div>
                        ${a.ai_summary ? `
                            <div style="margin-top: 6px; font-size: 12px; color: #c7d2fe; background: rgba(99,102,241,0.1); padding: 6px 10px; border-radius: 6px; border-left: 3px solid #818cf8; white-space: pre-line;">
                                <strong>🤖 AI Brief:</strong> ${escapeHtml(a.ai_summary)}
                            </div>
                        ` : ''}
                        <div style="margin-top: 6px; display: flex; gap: 8px; flex-wrap: wrap;">
                            ${a.local_file_path ? `
                                <a href="/api/download-file?path=${encodeURIComponent(a.local_file_path)}" class="btn btn-outline btn-sm" style="font-size: 11px; padding: 2px 8px; color: var(--success); border-color: var(--success);">
                                    💾 Download File
                                </a>
                            ` : (a.attachment_url ? `
                                <a href="${escapeHtml(a.attachment_url)}" target="_blank" style="font-size: 11px; color: var(--primary);">📎 Attachment</a>
                            ` : '')}
                        </div>
                    </td>
                    <td>
                        <div>${formatDate(a.deadline)}</div>
                        <small style="color: var(--text-muted);">${escapeHtml(a.remaining_str)}</small>
                    </td>
                    <td>
                        <span class="badge ${a.submission_status === 'Submitted' ? 'badge-low' : 'badge-high'}">
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
            container.innerHTML = `<p class="empty-state">No notifications dispatched yet.</p>`;
            recentContainer.innerHTML = `<p class="empty-state">No recent alerts.</p>`;
            return;
        }

        recentContainer.innerHTML = logs.slice(0, 4).map(l => `
            <div class="notification-card">
                <strong>[${escapeHtml(l.notification_type)}]</strong> • ${new Date(l.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
                    ${escapeHtml(l.message_text.substring(0, 100))}...
                </div>
            </div>
        `).join("");

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

    async function saveSettings(e) {
        e.preventDefault();
        const settings = {
            check_interval_minutes: document.getElementById("settingInterval").value,
            whatsapp_provider: document.getElementById("settingProvider").value,
            whatsapp_to_number: document.getElementById("settingPhone").value,
            reminder_hours: JSON.stringify(document.getElementById("settingReminderHours").value.split(",").map(n => parseInt(n.trim()))),
            daily_summary_time: document.getElementById("settingDailyTime").value
        };

        try {
            const res = await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ settings })
            });
            const data = await res.json();
            alert("Settings saved successfully!");
        } catch (err) {
            alert("Failed to save settings: " + err.message);
        }
    }

    async function sendTestWhatsApp() {
        const phone = document.getElementById("settingPhone").value;
        if (!phone) {
            alert("Please enter a WhatsApp phone number first.");
            return;
        }

        try {
            const res = await fetch("/api/send-test-whatsapp", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ phone_number: phone })
            });
            const data = await res.json();
            alert(data.message || "Test message initiated!");
            fetchNotifications();
        } catch (err) {
            alert("Test message error: " + err.message);
        }
    }

    function formatDate(dateStr) {
        if (!dateStr) return "No deadline";
        const d = new Date(dateStr);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    // --- AI COPILOT & GPA FUNCTIONS ---
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
            
            // Format response (convert **bold** and newlines)
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
        const curCgpa = parseFloat(document.getElementById("simCurrentCgpa").value) || 3.20;
        const credits = parseInt(document.getElementById("simCredits").value) || 100;
        const targetGpa = parseFloat(document.getElementById("simTargetGpa").value) || 3.66;
        const resultBox = document.getElementById("gpaResultBox");

        resultBox.innerHTML = `<em>Simulating CUST degree progression...</em>`;

        try {
            const res = await fetch("/api/gpa/projection");
            const data = await res.json();

            // Custom projection using user inputs
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
                    • Semester Target GPA: <strong>${targetGpa.toFixed(2)}</strong> (based on 15 credits)<br>
                    • Absolute Mathematical Ceiling: <strong>${maxCgpa}</strong> (if you achieve straight A's)
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

    async function calculateFinalMarks() {
        const sessional = parseFloat(document.getElementById("calcSessionalObtained").value) || 0;
        const sessionalTotal = parseFloat(document.getElementById("calcSessionalTotal").value) || 50;
        const finalTotal = parseFloat(document.getElementById("calcFinalTotal").value) || 50;
        const targetGrade = document.getElementById("calcTargetGrade").value || "A";
        const resultBox = document.getElementById("calcResultBox");

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

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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
        const course_id = sel.value;
        const course_name = sel.options[sel.selectedIndex]?.dataset.name || course_id;
        const component = document.getElementById("mgComponent").value.trim();
        const component_type = document.getElementById("mgCompType").value;
        const obtained = parseFloat(document.getElementById("mgObtained").value);
        const total = parseFloat(document.getElementById("mgTotal").value);
        const msg = document.getElementById("mgSaveMsg");

        if (!course_id || !component || isNaN(obtained) || isNaN(total) || total <= 0) {
            msg.textContent = "⚠️ Fill in all fields correctly.";
            msg.style.color = "#ef4444";
            return;
        }
        if (obtained > total) {
            msg.textContent = "⚠️ Obtained cannot exceed total.";
            msg.style.color = "#ef4444";
            return;
        }

        try {
            const res = await fetch("/api/margin/add-mark", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({course_id, course_name, component, component_type, obtained, total})
            });
            const data = await res.json();
            msg.textContent = "✅ Saved!";
            msg.style.color = "#4ade80";
            setTimeout(() => { msg.textContent = ""; }, 3000);
            loadMarginReport();
        } catch (e) {
            msg.textContent = "❌ Save failed.";
            msg.style.color = "#ef4444";
        }
    }

    async function loadMarginReport() {
        const container = document.getElementById("mgReportContainer");
        if (!container) return;
        container.innerHTML = "<p class='empty-state'>Loading...</p>";

        try {
            const data = await fetch("/api/margin/report").then(r => r.json());
            if (!data.courses || data.courses.length === 0) {
                container.innerHTML = "<p class='empty-state'>No marks logged yet. Add component marks above to start tracking.</p>";
                return;
            }

            container.innerHTML = data.courses.map(course => {
                const barPct = Math.min(100, course.current_pct || 0);
                const levelClass = course.alert_level;
                const components = (course.components || []).map(c =>
                    `<tr>
                        <td>${escapeHtml(c.component)}</td>
                        <td><span class="type-badge">${escapeHtml(c.component_type)}</span></td>
                        <td>${c.obtained} / ${c.total}</td>
                        <td>${c.pct}%</td>
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
                        <span>Current %: <strong>${course.current_pct}%</strong></span>
                        <span>Buffer until A drops: <strong>${course.marks_buffer} marks</strong></span>
                        <span>Need for A (60mk sessional): <strong>${course.marks_needed_for_A}</strong></span>
                    </div>
                    <p style="font-size:13px; color:var(--text-secondary); margin-top:8px;">${escapeHtml(course.message)}</p>
                    ${components ? `<table class="mg-components-table"><thead><tr><th>Component</th><th>Type</th><th>Marks</th><th>%</th></tr></thead><tbody>${components}</tbody></table>` : ""}
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
        resultCard.style.display = "block";
        resultContent.innerHTML = "<p>🔄 Running AI Rubric Audit...</p>";

        try {
            const data = await fetch("/api/rubric/audit", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
            }).then(r => r.json());
            renderAuditResult(resultContent, data);
            loadAuditHistory();
        } catch (e) {
            resultContent.innerHTML = `<p class="empty-state">❌ Audit failed: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function scanSubmissionsFolder() {
        const resultCard = document.getElementById("raResultCard");
        const resultContent = document.getElementById("raResultContent");
        resultCard.style.display = "block";
        resultContent.innerHTML = "<p>📂 Scanning submissions/ folder...</p>";

        try {
            const data = await fetch("/api/rubric/scan-submissions").then(r => r.json());
            if (data.count === 0) {
                resultContent.innerHTML = "<p class='empty-state'>No draft files found in <code>submissions/</code>. Drop a file there first.</p>";
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
            resultContent.innerHTML = `<p class="empty-state">❌ Scan failed: ${escapeHtml(e.message)}</p>`;
        }
    }

    function renderAuditResult(container, data) {
        const score = data.coverage_score || 0;
        const scoreClass = score >= 80 ? "high" : score >= 50 ? "medium" : "low";
        const missing = (data.missing_items || []);
        const fmt = (data.formatting_issues || []);

        const missingHtml = missing.length
            ? `<h4 style="margin:12px 0 6px;">❌ Missing Rubric Items (${missing.length})</h4>
               <ul class="ra-checklist">${missing.map(m => `<li><span class="check-icon">❌</span>${escapeHtml(m)}</li>`).join("")}</ul>`
            : `<p style="color:#4ade80; margin:8px 0;">✅ All rubric items appear to be addressed!</p>`;

        const fmtHtml = fmt.length
            ? `<h4 style="margin:12px 0 6px;">⚠️ Formatting Issues (${fmt.length})</h4>
               <ul class="ra-checklist">${fmt.map(f => `<li><span class="check-icon">⚠️</span>${escapeHtml(f)}</li>`).join("")}</ul>`
            : "";

        container.innerHTML = `
            <div class="ra-score-row">
                <div class="ra-score-circle ${scoreClass}">${score}</div>
                <div>
                    <strong style="font-size:15px;">Coverage Score: ${score}/100</strong>
                    <p style="margin:4px 0; font-size:13px; color:var(--text-secondary);">
                        File: <code>${escapeHtml(data.draft_file)}</code> &nbsp;·&nbsp;
                        Method: <span class="ra-method-badge">${escapeHtml(data.method)}</span>
                    </p>
                    <p style="margin:4px 0; font-size:13px; color:var(--text-secondary);">${escapeHtml(data.audit_result)}</p>
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
                container.innerHTML = "<p class='empty-state'>No audits yet.</p>";
                return;
            }
            container.innerHTML = audits.map(a => {
                const score = a.coverage_score;
                const color = score >= 80 ? "#4ade80" : score >= 50 ? "#facc15" : "#ef4444";
                const missing = (a.missing_items || []).length;
                return `<div class="ra-history-row">
                    <span class="ra-history-score" style="color:${color};">${score}</span>
                    <div>
                        <strong>${escapeHtml(a.draft_file)}</strong>
                        ${a.course_name ? `<span style="font-size:11px; color:var(--text-muted);"> · ${escapeHtml(a.course_name)}</span>` : ""}
                        <br><span style="font-size:12px; color:var(--text-secondary);">${escapeHtml(a.audit_result?.slice(0, 120))}...</span>
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

    // ================================================================
    //  WIRE: Load data on tab switch for new panes
    // ================================================================
    const _originalSetupNavigation = setupNavigation;
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const tab = item.getAttribute("data-tab");
            if (tab === "margin-guard") {
                populateCourseDropdown();
                loadMarginReport();
            } else if (tab === "rubric-auditor") {
                loadAuditHistory();
            }
        });
    });

    // Expose to HTML onclick= attributes (outside DOMContentLoaded closure)
    window.addMarkEntry = addMarkEntry;
    window.loadMarginReport = loadMarginReport;
    window.runRubricAudit = runRubricAudit;
    window.scanSubmissionsFolder = scanSubmissionsFolder;
    window.loadAuditHistory = loadAuditHistory;
});

