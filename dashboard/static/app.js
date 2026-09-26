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
});
