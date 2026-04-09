document.addEventListener('DOMContentLoaded', () => {
    // --- MQTT CONFIGURATION ---
    const BROKER = "localhost";
    const PORT = 9001; // WebSocket port
    const CLIENT_ID = "Dashboard_" + Math.random().toString(16).substr(2, 8);
    
    // UI Elements
    const rawList = document.getElementById('rawList');
    const edgeOutput = document.getElementById('edgeOutput');
    const reasoningText = document.getElementById('reasoningText');
    const agentOutput = document.getElementById('agentOutput');
    const checkList = document.getElementById('checkList');
    const fsmState = document.getElementById('fsmState');
    const fsmReason = document.getElementById('fsmReason');

    // Keep edge telemetry reception continuous but limit UI paint frequency.
    const EDGE_RENDER_INTERVAL_MS = 15000;
    let edgeLastRenderAt = 0;
    let edgeLatestPayload = null;
    let edgeRenderTimer = null;
    let hasRenderedEdgeOnce = false;

    // --- DEMO DATA PLAYBACK ---
    let demoData = null;
    let startTime = Date.now();

    async function initDemo() {
        try {
            const response = await fetch('demo_data.json');
            demoData = await response.json();
            console.log("Demo data loaded:", demoData);
            
            document.querySelector('.status-indicator').innerHTML = '<span class="dot pulse" style="background:#34d399"></span> Node: DELHI_01 [DEMO MODE]';
            
            // Start simulation loop
            setInterval(playbackTick, 1000); 
        } catch (err) {
            console.error("Failed to load demo data:", err);
            document.querySelector('.status-indicator').innerHTML = '<span class="dot" style="background:red"></span> Demo Data Missing';
        }
    }

    function playbackTick() {
        if (!demoData) return;
        
        const elapsed = (Date.now() - startTime) / 1000;
        const totalDuration = demoData.mqtt_messages.length > 0 
            ? demoData.mqtt_messages[demoData.mqtt_messages.length-1].relative_time 
            : 0;

        // Loop the demo
        const relativeTime = elapsed % totalDuration;

        // Find messages that should have "arrived" in this tick
        // Since we tick every 1s, we just look for the closest message or just use the index for simplicity
        // For a demo, we can just cycle through the array to keep things moving.
        
        // Actually, let's just use the current index to make it feel "live"
        const msgIndex = Math.floor((elapsed / 15) % demoData.mqtt_messages.length);
        const msg = demoData.mqtt_messages[msgIndex];

        if (msg) {
            handleDemoMessage(msg.topic, msg.payload);
        }
    }

    function handleDemoMessage(topic, payload) {
        // topics: dashboard/trace/{node_id}/{component}
        if (topic.includes('/edge')) {
            scheduleEdgeLayerUpdate(payload);
        } else if (topic.includes('/forecast')) {
            updateForecastLayer(payload);
        } else if (topic.includes('/agent')) {
            updateAgentLayer(payload);
        } else if (topic.includes('/orchestrator')) {
            updateOrchestratorLayer(payload);
        }
    }

    function scheduleEdgeLayerUpdate(data) {
        const now = Date.now();
        edgeLatestPayload = data;

        // First payload should render immediately so dashboard does not look empty.
        if (!hasRenderedEdgeOnce) {
            updateEdgeLayer(edgeLatestPayload);
            edgeLastRenderAt = now;
            hasRenderedEdgeOnce = true;
            return;
        }

        const elapsed = now - edgeLastRenderAt;
        if (elapsed >= EDGE_RENDER_INTERVAL_MS) {
            updateEdgeLayer(edgeLatestPayload);
            edgeLastRenderAt = now;
            if (edgeRenderTimer) {
                clearTimeout(edgeRenderTimer);
                edgeRenderTimer = null;
            }
            return;
        }

        // Timer already pending; keep replacing payload buffer only.
        if (edgeRenderTimer) {
            return;
        }

        const waitMs = EDGE_RENDER_INTERVAL_MS - elapsed;
        edgeRenderTimer = setTimeout(() => {
            if (edgeLatestPayload) {
                updateEdgeLayer(edgeLatestPayload);
                edgeLastRenderAt = Date.now();
            }
            edgeRenderTimer = null;
        }, waitMs);
    }

    function updateEdgeLayer(data) {
        // Update Raw Sweep
        const out = data.output;
        rawList.innerHTML = `
            <li>Voltage: <span class="val">${out.voltage_v.toFixed(1)}V</span></li>
            <li>Current: <span class="val">${out.current_a ? out.current_a.toFixed(2) : (out.load_kw / 0.23).toFixed(2)}A</span></li>
            <li>Battery: <span class="num">${out.soc_pct.toFixed(1)}%</span></li>
        `;
        // Update Cleaned JSON
        edgeOutput.innerHTML = `<code>${JSON.stringify(data.output, null, 2)}</code>`;
        
        // Highlight the step
        document.getElementById('phase1').classList.add('visible');
    }

    function updateForecastLayer(data) {
        document.getElementById('forecastInput').textContent = data.input;
        const bars = document.getElementById('forecastBars');
        const labels = document.getElementById('timeLabels');
        bars.innerHTML = ""; 
        labels.innerHTML = "";
        
        const loadDat = data.output.load;
        const solarDat = data.output.solar;
        const startHour = data.output.start_hour || 0;

        const tooltip = document.getElementById('chartTooltip');

        loadDat.forEach((l, i) => {
            const s = solarDat[i] || 0;
            const hour = (startHour + i) % 24;
            const hourStr = hour.toString().padStart(2, '0') + ":00";

            // Bar Pair
            const pair = document.createElement('div');
            pair.className = 'bar-pair';
            const loadH = Math.min(100, (l / 3.5) * 100);
            const solarH = Math.min(100, (s / 3.5) * 100);
            
            pair.innerHTML = `
                <div class="bar load" style="height: ${loadH}%" data-val="${l.toFixed(2)}" data-time="${hourStr}" data-type="Load"></div>
                <div class="bar solar" style="height: ${solarH}%" data-val="${s.toFixed(2)}" data-time="${hourStr}" data-type="Solar"></div>
            `;
            
            // Tooltip Event Listeners
            pair.querySelectorAll('.bar').forEach(bar => {
                bar.addEventListener('mousemove', (e) => {
                    tooltip.innerHTML = `<span class="label">${bar.dataset.time} | ${bar.dataset.type}</span><span class="value">${bar.dataset.val} kW</span>`;
                    tooltip.classList.add('visible');
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                    tooltip.style.borderColor = bar.classList.contains('load') ? 'var(--accent-primary)' : '#f59e0b';
                });
                bar.addEventListener('mouseleave', () => {
                    tooltip.classList.remove('visible');
                });
            });

            bars.appendChild(pair);

            // Time Label
            const lbl = document.createElement('span');
            lbl.textContent = hour.toString().padStart(2, '0');
            labels.appendChild(lbl);
        });

        document.getElementById('phase2').classList.add('visible');
    }

    function updateAgentLayer(data) {
        // Render reasoning instantly to avoid animation-induced lag.
        reasoningText.textContent = data.reasoning;
        
        // 2. Show JSON Result
        agentOutput.innerHTML = `<code>${JSON.stringify(data.output, null, 2)}</code>`;
        
        // 3. Highlight step
        document.getElementById('phase3').classList.add('visible', 'pulse-glow');
        setTimeout(() => document.getElementById('phase3').classList.remove('pulse-glow'), 2000);
    }

    function updateOrchestratorLayer(data) {
        const out = data.output;
        
        // Color the FSM state display based on what's happening
        const stateEl = document.getElementById('fsmState');
        if (out.fsm_state === 'P2P_TRADING') {
            stateEl.style.color = '#34d399'; // green — active trade
        } else if (out.fsm_state === 'EMERGENCY') {
            stateEl.style.color = '#ef4444'; // red
        } else if (out.fsm_state === 'ISLANDED') {
            stateEl.style.color = '#a78bfa'; // purple
        } else {
            stateEl.style.color = '#f59e0b'; // gold — default
        }
        stateEl.textContent = `STATE: ${out.fsm_state}`;
        fsmReason.textContent = out.reason || "System nominal.";

        // Action rows
        const strategyClass = (out.last_strategy && out.last_strategy !== 'NONE') ? 'pass' : '';
        const verdictClass = out.strategy_status === 'ALLOWED' || out.strategy_status === 'IN_PROGRESS' || out.strategy_status === 'COMPLETED' ? 'pass' : (out.strategy_status === 'REJECTED' ? 'fail' : '');

        checkList.innerHTML = `
            <div class="check-item ${strategyClass}">
                <span>Strategic Action</span> <span class="status">${out.last_strategy || '--'}</span>
            </div>
            <div class="check-item ${verdictClass}">
                <span>Action Status</span> <span class="status">${out.strategy_status || '--'}</span>
            </div>
            <div class="check-item">
                <span>SoC Monitor</span> <span class="status">${Number.isFinite(out.soc) ? out.soc.toFixed(1) : '--'}%</span>
            </div>
        `;

        // Pulse glow when actively trading
        const phase4 = document.getElementById('phase4');
        if (out.fsm_state === 'P2P_TRADING') {
            phase4.classList.add('pulse-glow');
        } else {
            phase4.classList.remove('pulse-glow');
        }

        phase4.classList.add('visible');
    }

    // Call initDemo instead of MQTT connect
    initDemo();
});
