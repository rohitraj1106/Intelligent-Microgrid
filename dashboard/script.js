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

    const client = new Paho.MQTT.Client(BROKER, PORT, CLIENT_ID);

    client.onConnectionLost = (responseObject) => {
        console.error("MQTT Connection Lost:", responseObject.errorMessage);
        document.querySelector('.status-indicator').innerHTML = '<span class="dot" style="background:red"></span> Disconnected';
    };

    client.onMessageArrived = (message) => {
        const topic = message.destinationName;
        const payload = JSON.parse(message.payloadString);
        
        // --- NODE FILTERING ---
        // Topics are in format: dashboard/trace/{node_id}/{component}
        const topicParts = topic.split('/');
        const msgNodeId = topicParts[2];
        const targetNodeId = document.querySelector('.node-badge').textContent.replace('Node: ', '').trim();

        if (msgNodeId !== targetNodeId) {
            // Silently ignore messages from other nodes to prevent "fluctuation"
            return;
        }

        console.log(`Msg on ${topic}:`, payload);

        if (topic.includes('/edge')) {
            updateEdgeLayer(payload);
        } else if (topic.includes('/forecast')) {
            updateForecastLayer(payload);
        } else if (topic.includes('/agent')) {
            updateAgentLayer(payload);
        } else if (topic.includes('/orchestrator')) {
            updateOrchestratorLayer(payload);
        }
    };

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
        // 1. Show LLM Logic with typing animation
        reasoningText.textContent = ""; // Clear existing
        typeText(reasoningText, data.reasoning);
        
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

    let typingTimer = null;
    function typeText(element, text) {
        if (typingTimer) clearTimeout(typingTimer);
        element.textContent = ""; 

        let i = 0;
        const speed = 25;
        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                typingTimer = setTimeout(type, speed);
            } else {
                typingTimer = null;
            }
        }
        type();
    }

    // Connect to Broker
    client.connect({
        onSuccess: () => {
            console.log("Connected to MQTT Broker via WebSockets");
            client.subscribe("dashboard/trace/#");
            document.querySelector('.status-indicator').innerHTML = '<span class="dot pulse"></span> Total System Active';
        },
        onFailure: (err) => {
            console.error("Connect failed:", err.errorMessage);
        }
    });

});
