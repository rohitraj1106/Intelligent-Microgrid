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
            <li>Current: <span class="val">${(out.load_kw / 0.23).toFixed(2)}A</span></li>
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
        bars.innerHTML = ""; // Clear
        
        const loadDat = data.output.load;
        const solarDat = data.output.solar;

        loadDat.forEach((l, i) => {
            const s = solarDat[i] || 0;
            const pair = document.createElement('div');
            pair.className = 'bar-pair';
            pair.innerHTML = `
                <div class="bar load" style="height: ${(l/3)*100}%"></div>
                <div class="bar solar" style="height: ${(s/3)*100}%"></div>
            `;
            bars.appendChild(pair);
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
        
        // Update Checks
        checkList.innerHTML = `
            <div class="check-item ${out.strategy_status === 'ALLOWED' ? 'pass' : (out.strategy_status === 'REJECTED' ? 'fail' : '')}">
                <span>Strategic Action</span> <span class="status">${out.last_strategy || '--'}</span>
            </div>
            <div class="check-item">
                <span>Action Status</span> <span class="status">${out.strategy_status || '--'}</span>
            </div>
            <div class="check-item">
                <span>SoC Monitor</span> <span class="status">${out.soc ? out.soc.toFixed(1) : '--'}%</span>
            </div>
        `;
        
        // Update FSM
        fsmState.textContent = `STATE: ${out.fsm_state}`;
        fsmReason.textContent = out.reason || "Safety check complete.";
        
        // Highlight step
        document.getElementById('phase4').classList.add('visible');
    }

    function typeText(element, text) {
        let i = 0;
        const speed = 25;
        function type() {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed);
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
