// ==========================================
// Global State
// ==========================================
let currentTab = 'leaderboards';
let activeDatasets = [];
let activePrompts = [];
let selectedDatasetId = null;
let selectedRunResultId = null;
let benchmarkChartInstance = null;
let runPollingInterval = null;

// ==========================================
// API Helper
// ==========================================
const API_URL = '';

async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch(`${API_URL}${endpoint}`, options);
        if (!response.ok) {
            throw new Error(`API Error: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Fetch error on ${endpoint}:`, error);
        alert(`Request failed: ${error.message}`);
        throw error;
    }
}

// ==========================================
// Tab Switching
// ==========================================
function switchTab(tabId) {
    currentTab = tabId;
    
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('href') === `#${tabId}`) {
            item.classList.add('active');
        }
    });

    // Update active pane
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    const targetPane = document.getElementById(`tab-${tabId}`);
    if (targetPane) targetPane.classList.add('active');

    // Update headers
    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');

    if (tabId === 'leaderboards') {
        titleEl.textContent = 'Leaderboards';
        subtitleEl.textContent = 'Benchmarking model accuracy, prompt versions, and guardrails.';
        loadLeaderboards();
    } else if (tabId === 'datasets') {
        titleEl.textContent = 'Evaluation Datasets';
        subtitleEl.textContent = 'Manage test suites for Finance, Healthcare, Safety, and Agent loops.';
        loadDatasets();
    } else if (tabId === 'prompts') {
        titleEl.textContent = 'Prompt Templates';
        subtitleEl.textContent = 'Track and compare system prompt template versions to prevent regressions.';
        loadPromptsTab();
    } else if (tabId === 'evaluations') {
        titleEl.textContent = 'Run Evaluations';
        subtitleEl.textContent = 'Trigger background multi-model runs and inspect details.';
        loadDatasets(); // Needed for run dropdowns
        loadPrompts();  // Needed for run dropdowns
        loadRuns();
    } else if (tabId === 'playground') {
        titleEl.textContent = 'Prompt Playground';
        subtitleEl.textContent = 'Run side-by-side prompt debugging and check guardrails instantly.';
    }
}

// ==========================================
// Leaderboards Loading & Charts
// ==========================================
async function loadLeaderboards() {
    try {
        const [models, prompts, datasets] = await Promise.all([
            apiCall('/api/leaderboards/models'),
            apiCall('/api/leaderboards/prompts'),
            apiCall('/api/leaderboards/datasets')
        ]);

        // Render stats cards based on top model
        if (models && models.length > 0) {
            document.getElementById('top-model-name').textContent = models[0].model_name;
            
            // Calculate averages
            let totalLatency = 0;
            let totalCost = 0;
            let totalRuns = 0;
            models.forEach(m => {
                totalLatency += m.avg_latency_ms;
                totalCost += m.total_cost;
                totalRuns += m.run_count;
            });
            const avgLat = Math.round(totalLatency / models.length);
            
            document.getElementById('avg-latency-val').textContent = `${avgLat} ms`;
            document.getElementById('total-spending-val').textContent = `$${totalCost.toFixed(4)}`;
            document.getElementById('total-evals-val').textContent = totalRuns;
        } else {
            document.getElementById('top-model-name').textContent = 'None';
            document.getElementById('avg-latency-val').textContent = '0 ms';
            document.getElementById('total-spending-val').textContent = '$0.00';
            document.getElementById('total-evals-val').textContent = '0';
        }

        // Render tables
        renderModelLeaderboard(models);
        renderPromptLeaderboard(prompts);
        renderDatasetLeaderboard(datasets);

        // Render Chart.js
        renderChart(models);
    } catch (e) {
        console.error("Failed to load leaderboards", e);
    }
}

function renderModelLeaderboard(data) {
    const tbody = document.getElementById('model-leaderboard-body');
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No runs recorded yet. Execute an evaluation run to generate ranks!</td></tr>';
        return;
    }
    data.forEach(m => {
        tbody.innerHTML += `
            <tr>
                <td><strong>${m.model_name}</strong></td>
                <td><span class="badge badge-success">${m.avg_score}%</span></td>
                <td>${m.avg_latency_ms} ms</td>
                <td>$${m.total_cost.toFixed(5)}</td>
                <td>${m.run_count} runs</td>
            </tr>
        `;
    });
}

function renderPromptLeaderboard(data) {
    const tbody = document.getElementById('prompt-leaderboard-body');
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No prompt-specific evals recorded.</td></tr>';
        return;
    }
    data.forEach(p => {
        tbody.innerHTML += `
            <tr>
                <td>${p.prompt_name}</td>
                <td><span class="badge badge-info">v${p.prompt_version}</span></td>
                <td><span class="badge badge-success">${p.avg_score}%</span></td>
                <td>${p.avg_latency_ms} ms</td>
                <td>${p.run_count} runs</td>
            </tr>
        `;
    });
}

function renderDatasetLeaderboard(data) {
    const tbody = document.getElementById('dataset-leaderboard-body');
    tbody.innerHTML = '';
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No dataset evaluations recorded.</td></tr>';
        return;
    }
    data.forEach(d => {
        tbody.innerHTML += `
            <tr>
                <td>${d.dataset_name}</td>
                <td><span class="badge badge-info">${d.category}</span></td>
                <td><span class="badge badge-success">${d.pass_rate}%</span></td>
                <td>${d.run_count} runs</td>
            </tr>
        `;
    });
}

function renderChart(models) {
    const ctx = document.getElementById('modelBenchmarkChart').getContext('2d');
    
    // Destroy previous instance
    if (benchmarkChartInstance) {
        benchmarkChartInstance.destroy();
    }

    if (!models || models.length === 0) {
        return;
    }

    const labels = models.map(m => m.model_name);
    const scores = models.map(m => m.avg_score);
    const latencies = models.map(m => m.avg_latency_ms);

    benchmarkChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Score Index (%)',
                    data: scores,
                    backgroundColor: 'rgba(139, 92, 246, 0.4)',
                    borderColor: '#8b5cf6',
                    borderWidth: 1,
                    yAxisID: 'y'
                },
                {
                    label: 'Avg Latency (ms)',
                    data: latencies,
                    backgroundColor: 'rgba(0, 240, 255, 0.2)',
                    borderColor: '#00f0ff',
                    borderWidth: 1,
                    type: 'line',
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9ca3af' }
                },
                y: {
                    position: 'left',
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#9ca3af' }
                },
                y1: {
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#9ca3af' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#f3f4f6' }
                }
            }
        }
    });
}

// ==========================================
// Datasets Tab Management
// ==========================================
async function loadDatasets() {
    try {
        const data = await apiCall('/api/datasets');
        activeDatasets = data;
        
        // Populate dropdowns in runs
        const runDatasetDropdown = document.getElementById('run-dataset');
        if (runDatasetDropdown) {
            runDatasetDropdown.innerHTML = '<option value="">-- Select Dataset --</option>';
            data.forEach(d => {
                runDatasetDropdown.innerHTML += `<option value="${d.id}">${d.name} (${d.category})</option>`;
            });
        }

        // Render dataset list on Left
        const listContainer = document.getElementById('dataset-list');
        if (listContainer) {
            listContainer.innerHTML = '';
            if (data.length === 0) {
                listContainer.innerHTML = '<p class="text-center text-muted pad-20">No datasets found. Create one to begin!</p>';
                return;
            }
            data.forEach(d => {
                const isActive = selectedDatasetId === d.id ? 'active' : '';
                listContainer.innerHTML += `
                    <div class="list-item ${isActive}" onclick="selectDataset('${d.id}')">
                        <div>
                            <span class="list-item-title">${d.name}</span>
                            <div class="list-item-subtitle">${d.category}</div>
                        </div>
                        <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteDataset('${d.id}')">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                `;
            });
        }
    } catch (e) {
        console.error(e);
    }
}

async function selectDataset(id) {
    selectedDatasetId = id;
    
    // Highlight list selection
    document.querySelectorAll('#dataset-list .list-item').forEach(item => {
        item.classList.remove('active');
    });
    // Add active
    loadDatasets(); // triggers re-render with active highlight

    const detailsPanel = document.getElementById('dataset-details-panel');
    detailsPanel.innerHTML = '<div class="panel-placeholder"><i class="fa-solid fa-arrows-spin fa-spin large-icon"></i><p>Loading test cases...</p></div>';

    try {
        const ds = activeDatasets.find(d => d.id === id);
        const testCases = await apiCall(`/api/datasets/${id}/testcases`);

        let testCasesHTML = '';
        if (testCases.length === 0) {
            testCasesHTML = '<tr><td colspan="4" class="text-center text-muted">No test cases in this dataset yet. Click add test case below.</td></tr>';
        } else {
            testCases.forEach((tc, idx) => {
                const expectedToolsBadge = tc.expected_tools && tc.expected_tools.length > 0 
                    ? tc.expected_tools.map(t => `<span class="badge badge-info">${t}</span>`).join(' ')
                    : '<span class="text-muted">None</span>';
                    
                testCasesHTML += `
                    <tr>
                        <td><strong>#${idx + 1}</strong></td>
                        <td class="text-wrap"><code>${escapeHTML(tc.input_prompt)}</code></td>
                        <td>${expectedToolsBadge}</td>
                        <td>
                            <button class="btn btn-danger btn-sm" onclick="deleteTestCase('${tc.id}')">
                                <i class="fa-solid fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
        }

        detailsPanel.innerHTML = `
            <div class="panel-header flex-between">
                <div>
                    <h3>${ds.name}</h3>
                    <p class="subtitle">Category: ${ds.category} | Description: ${ds.description || 'N/A'}</p>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-secondary btn-sm" onclick="showImportModal('${ds.id}')">
                        <i class="fa-solid fa-file-import"></i> Import Cases
                    </button>
                    <button class="btn btn-primary btn-sm" onclick="showAddTestCaseModal('${ds.id}')">
                        <i class="fa-solid fa-plus"></i> Add Test Case
                    </button>
                </div>
            </div>
            
            <div class="table-wrapper margin-top-20">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Input Prompt / Query</th>
                            <th>Expected Tools</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${testCasesHTML}
                    </tbody>
                </table>
            </div>
        `;
    } catch (e) {
        console.error(e);
    }
}

// Create Dataset Modal helpers
function showCreateDatasetModal() { document.getElementById('create-dataset-modal').classList.add('active'); }
function hideCreateDatasetModal() { document.getElementById('create-dataset-modal').classList.remove('active'); }

async function createDataset(e) {
    e.preventDefault();
    const name = document.getElementById('ds-name').value;
    const category = document.getElementById('ds-category').value;
    const description = document.getElementById('ds-desc').value;

    try {
        await apiCall('/api/datasets', 'POST', { name, category, description });
        hideCreateDatasetModal();
        loadDatasets();
    } catch (e) {
        console.error(e);
    }
}

async function deleteDataset(id) {
    if (!confirm('Are you sure you want to delete this dataset and all associated test cases?')) return;
    try {
        await apiCall(`/api/datasets/${id}`, 'DELETE');
        if (selectedDatasetId === id) selectedDatasetId = null;
        loadDatasets();
        // reset right panel if deleted
        document.getElementById('dataset-details-panel').innerHTML = `
            <div class="panel-placeholder">
                <i class="fa-solid fa-database large-icon"></i>
                <p>Select a dataset from the left panel to manage its test cases.</p>
            </div>
        `;
    } catch (e) {
        console.error(e);
    }
}

// Add Test Case Modal helpers
function showAddTestCaseModal(datasetId) {
    document.getElementById('tc-dataset-id').value = datasetId;
    document.getElementById('add-testcase-modal').classList.add('active');
}
function hideAddTestCaseModal() {
    document.getElementById('add-testcase-modal').classList.remove('active');
}

async function createTestCase(e) {
    e.preventDefault();
    const datasetId = document.getElementById('tc-dataset-id').value;
    const input_prompt = document.getElementById('tc-input').value;
    const reference_context = document.getElementById('tc-context').value;
    const expected_output = document.getElementById('tc-output').value;
    const toolsStr = document.getElementById('tc-tools').value;
    
    // Parse expected tools
    let expected_tools = null;
    if (toolsStr && toolsStr.trim() !== '') {
        expected_tools = toolsStr.split(',').map(t => t.trim());
    }

    try {
        await apiCall(`/api/datasets/${datasetId}/testcases`, 'POST', {
            input_prompt,
            reference_context: reference_context || null,
            expected_output: expected_output || null,
            expected_tools
        });
        hideAddTestCaseModal();
        selectDataset(datasetId);
    } catch (e) {
        console.error(e);
    }
}

async function deleteTestCase(id) {
    if (!confirm('Are you sure you want to delete this test case?')) return;
    try {
        await apiCall(`/api/testcases/${id}`, 'DELETE');
        selectDataset(selectedDatasetId);
    } catch (e) {
        console.error(e);
    }
}

// ==========================================
// Prompts Version Management
// ==========================================
async function loadPrompts() {
    try {
        const data = await apiCall('/api/prompts');
        activePrompts = data;

        const runPromptDropdown = document.getElementById('run-prompt');
        if (runPromptDropdown) {
            runPromptDropdown.innerHTML = '<option value="">-- Default / No Template --</option>';
            data.forEach(p => {
                runPromptDropdown.innerHTML += `<option value="${p.id}">${p.name} (v${p.version})</option>`;
            });
        }
    } catch (e) {
        console.error(e);
    }
}

// ==========================================
// Run Evaluations tab Management
// ==========================================
async function loadRuns() {
    try {
        const data = await apiCall('/api/evaluations/runs');
        renderRunsHistory(data);

        // If any run is in PENDING or RUNNING status, start polling if not already started
        const hasActiveRuns = data.some(r => r.status === 'PENDING' || r.status === 'RUNNING');
        if (hasActiveRuns && !runPollingInterval) {
            runPollingInterval = setInterval(loadRuns, 3000);
        } else if (!hasActiveRuns && runPollingInterval) {
            clearInterval(runPollingInterval);
            runPollingInterval = null;
            // Refresh dashboard data as well since runs completed
            loadLeaderboards();
        }
    } catch (e) {
        console.error(e);
    }
}

function renderRunsHistory(runs) {
    const tbody = document.getElementById('runs-history-body');
    tbody.innerHTML = '';
    if (!runs || runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No runs enqueued yet. Start an evaluation run from the left panel!</td></tr>';
        return;
    }
    runs.forEach(r => {
        let statusBadge = '';
        let viewButton = '';
        if (r.status === 'PENDING') {
            statusBadge = '<span class="badge badge-warning"><i class="fa-solid fa-spinner fa-spin"></i> Pending</span>';
            viewButton = '<button class="btn btn-secondary btn-sm" disabled>Queueing...</button>';
        } else if (r.status === 'RUNNING') {
            statusBadge = '<span class="badge badge-info"><i class="fa-solid fa-rotate fa-spin"></i> Running</span>';
            viewButton = '<button class="btn btn-secondary btn-sm" disabled>Evaluating...</button>';
        } else if (r.status === 'COMPLETED') {
            statusBadge = '<span class="badge badge-success">Completed</span>';
            viewButton = `<button class="btn btn-primary btn-sm" onclick="viewRunDetails('${r.id}')"><i class="fa-solid fa-eye"></i> View Results</button>`;
        } else {
            statusBadge = '<span class="badge badge-danger">Failed</span>';
            viewButton = `<button class="btn btn-danger btn-sm" disabled>Failed</button>`;
        }

        tbody.innerHTML += `
            <tr>
                <td><strong>${r.name}</strong></td>
                <td><code>${r.model_name}</code></td>
                <td>${statusBadge}</td>
                <td>$${r.total_cost.toFixed(5)}</td>
                <td>${viewButton}</td>
            </tr>
        `;
    });
}

async function triggerEvaluationRun(e) {
    e.preventDefault();
    const name = document.getElementById('run-name').value;
    const dataset_id = document.getElementById('run-dataset').value;
    const prompt_template_id = document.getElementById('run-prompt').value || null;
    const model_name = document.getElementById('run-model').value;

    try {
        await apiCall('/api/evaluations/run', 'POST', {
            name,
            dataset_id,
            prompt_template_id,
            model_name
        });
        document.getElementById('run-name').value = '';
        loadRuns();
    } catch (e) {
        console.error(e);
    }
}

// Run Details Modal helpers
let currentRunResults = [];

let currentRun = null;

async function viewRunDetails(runId) {
    document.getElementById('run-details-modal').classList.add('active');
    const listContainer = document.getElementById('run-results-list');
    const detailsPane = document.getElementById('run-results-detail-content');

    listContainer.innerHTML = '<p class="text-center padding-20"><i class="fa-solid fa-spinner fa-spin"></i> Loading results...</p>';
    detailsPane.innerHTML = '<div class="panel-placeholder"><p>Select a result on the left to inspect detailed evaluator logs.</p></div>';

    try {
        const run = await apiCall(`/api/evaluations/runs/${runId}`);
        document.getElementById('run-details-title').textContent = `Results: ${run.name}`;
        document.getElementById('run-details-meta').textContent = `Model: ${run.model_name} | Total API Cost: $${run.total_cost.toFixed(5)}`;

        currentRun = run;
        currentRunResults = run.results;
        
        listContainer.innerHTML = '';
        if (run.results.length === 0) {
            listContainer.innerHTML = '<p class="text-muted text-center padding-20">No case evaluations found in this run.</p>';
            return;
        }

        // Add Aggregate Summary item at the top of the sidebar list
        listContainer.innerHTML += `
            <div class="list-item active" id="run-summary-item" onclick="showRunSummary()" style="border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 12px; margin-bottom: 8px;">
                <div>
                    <span class="list-item-title"><i class="fa-solid fa-gauge-high"></i> Performance Summary</span>
                    <div class="list-item-subtitle">View aggregate statistics</div>
                </div>
            </div>
        `;

        run.results.forEach((res, index) => {
            const hasSafetyViolation = res.metric_scores.some(s => s.metric_type.startsWith('safety') && s.score > 0.0);
            const hasHallucination = res.metric_scores.some(s => s.metric_type === 'hallucination' && s.score > 0.8);
            
            let badgeClass = 'badge-success';
            let badgeText = 'Pass';
            if (hasSafetyViolation) {
                badgeClass = 'badge-danger';
                badgeText = 'Violation';
            } else if (hasHallucination) {
                badgeClass = 'badge-warning';
                badgeText = 'Hallucination';
            }

            listContainer.innerHTML += `
                <div class="list-item" id="result-item-${res.id}" onclick="selectRunResult('${res.id}')">
                    <div>
                        <span class="list-item-title">Test Case #${index + 1}</span>
                        <div class="list-item-subtitle">${res.latency_ms.toFixed(0)} ms | $${res.estimated_cost.toFixed(5)}</div>
                    </div>
                    <span class="badge ${badgeClass}">${badgeText}</span>
                </div>
            `;
        });

        // Show run summary by default
        showRunSummary();
    } catch (e) {
        console.error(e);
    }
}

function showRunSummary() {
    // Highlight summary item and deselect others
    document.querySelectorAll('#run-results-list .list-item').forEach(item => {
        item.classList.remove('active');
    });
    const summaryItem = document.getElementById('run-summary-item');
    if (summaryItem) summaryItem.classList.add('active');

    const detailsPane = document.getElementById('run-results-detail-content');
    if (!currentRun || currentRun.results.length === 0) return;

    // Calculate aggregates
    let totalLatency = 0;
    let totalCost = 0;
    let totalTokens = 0;
    let passedCases = 0;
    const metricSums = {};
    const metricCounts = {};
    
    currentRun.results.forEach(res => {
        totalLatency += res.latency_ms;
        totalCost += res.estimated_cost;
        totalTokens += (res.prompt_tokens + res.completion_tokens);
        
        const hasSafetyViolation = res.metric_scores.some(s => s.metric_type.startsWith('safety') && s.score > 0.0);
        const hasHallucination = res.metric_scores.some(s => s.metric_type === 'hallucination' && s.score > 0.8);
        if (!hasSafetyViolation && !hasHallucination) {
            passedCases++;
        }
        
        res.metric_scores.forEach(s => {
            if (!metricSums[s.metric_type]) {
                metricSums[s.metric_type] = 0;
                metricCounts[s.metric_type] = 0;
            }
            metricSums[s.metric_type] += s.score;
            metricCounts[s.metric_type]++;
        });
    });
    
    const avgLatency = Math.round(totalLatency / currentRun.results.length);
    const passRate = Math.round((passedCases / currentRun.results.length) * 100);
    const totalCostStr = totalCost.toFixed(5);
    
    // Build metric averages breakdown list
    let metricsHTML = '';
    const metricTypes = Object.keys(metricSums);
    if (metricTypes.length === 0) {
        metricsHTML = '<p class="text-muted">No evaluator metrics computed.</p>';
    } else {
        metricTypes.forEach(m => {
            const avg = metricSums[m] / metricCounts[m];
            let displayVal = avg.toFixed(2);
            let pct = Math.round(avg * 100);
            let color = 'var(--neon-emerald)';
            
            if (m.startsWith('safety') || m === 'hallucination') {
                pct = Math.round((1 - avg) * 100); // compliance
                displayVal = `${(avg * 100).toFixed(0)}% violation`;
                if (avg > 0.5) color = 'var(--neon-coral)';
                else if (avg > 0.1) color = 'var(--neon-amber)';
            } else if (m === 'response_score') {
                pct = Math.round((avg / 5.0) * 100);
                displayVal = `${avg.toFixed(1)} / 5`;
            } else {
                displayVal = `${pct}%`;
            }
            
            metricsHTML += `
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9em; margin-bottom: 5px;">
                        <span>${formatMetricName(m)}</span>
                        <span style="font-weight: 600; color: ${color}">${displayVal}</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${pct}%; height: 100%; background: ${color}; border-radius: 4px; transition: width 0.3s ease;"></div>
                    </div>
                </div>
            `;
        });
    }
    
    detailsPane.innerHTML = `
        <div style="padding: 20px;">
            <h3 style="margin-top: 0;">Run Performance Overview</h3>
            <p class="subtitle" style="margin-bottom: 20px;">Comprehensive benchmarks and guardrail health metrics for this run.</p>
            
            <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 25px; display: grid;">
                <div class="stat-card" style="padding: 15px; background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-icon emerald"><i class="fa-solid fa-square-check"></i></div>
                    <div class="stat-info" style="display: flex; flex-direction: column;">
                        <span class="stat-label">Pass Rate</span>
                        <span class="stat-value" style="font-size: 1.5rem; color: var(--neon-emerald);">${passRate}%</span>
                    </div>
                </div>
                <div class="stat-card" style="padding: 15px; background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-icon cyan"><i class="fa-solid fa-clock"></i></div>
                    <div class="stat-info" style="display: flex; flex-direction: column;">
                        <span class="stat-label">Avg Latency</span>
                        <span class="stat-value" style="font-size: 1.5rem; color: var(--neon-cyan);">${avgLatency} ms</span>
                    </div>
                </div>
                <div class="stat-card" style="padding: 15px; background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-icon purple"><i class="fa-solid fa-coins"></i></div>
                    <div class="stat-info" style="display: flex; flex-direction: column;">
                        <span class="stat-label">Total Cost</span>
                        <span class="stat-value" style="font-size: 1.5rem; color: var(--neon-purple);">$${totalCostStr}</span>
                    </div>
                </div>
                <div class="stat-card" style="padding: 15px; background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-icon coral"><i class="fa-solid fa-chart-simple"></i></div>
                    <div class="stat-info" style="display: flex; flex-direction: column;">
                        <span class="stat-label">Total Tokens</span>
                        <span class="stat-value" style="font-size: 1.5rem; color: var(--neon-coral);">${totalTokens}</span>
                    </div>
                </div>
            </div>
            
            <div class="glass-panel" style="padding: 20px;">
                <h4 style="margin-top: 0; margin-bottom: 15px;"><i class="fa-solid fa-gauge-high text-cyan"></i> Evaluator Breakdowns</h4>
                <div style="display: grid; grid-template-columns: 1fr; gap: 10px;">
                    ${metricsHTML}
                </div>
            </div>
        </div>
    `;
}

function hideRunDetailsModal() {
    document.getElementById('run-details-modal').classList.remove('active');
}

function selectRunResult(resultId) {
    selectedRunResultId = resultId;
    
    // Highlight sidebar item
    document.querySelectorAll('#run-results-list .list-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.getElementById(`result-item-${resultId}`);
    if (activeItem) activeItem.classList.add('active');

    const res = currentRunResults.find(r => r.id === resultId);
    const detailPane = document.getElementById('run-results-detail-content');

    if (!res) {
        detailPane.innerHTML = '<p class="text-danger">Failed to render selection.</p>';
        return;
    }

    // Build metric scores rows HTML
    let scoresHTML = '';
    if (res.metric_scores.length === 0) {
        scoresHTML = '<p class="text-muted">No evaluator metrics computed.</p>';
    } else {
        res.metric_scores.forEach(s => {
            let scoreVal = s.score;
            let barColor = 'var(--neon-emerald)';
            if (s.metric_type.startsWith('safety') || s.metric_type === 'hallucination') {
                if (scoreVal > 0.5) barColor = 'var(--neon-coral)';
                else if (scoreVal > 0.1) barColor = 'var(--neon-amber)';
            } else if (s.metric_type === 'response_score') {
                scoreVal = `${scoreVal} / 5`;
            }
            
            scoresHTML += `
                <div class="score-row">
                    <div class="score-row-header">
                        <span class="score-name">${formatMetricName(s.metric_type)}</span>
                        <span class="score-value-bold" style="color: ${barColor}">${scoreVal}</span>
                    </div>
                    <p class="score-explanation">${s.explanation || 'No rationale logged.'}</p>
                </div>
            `;
        });
    }

    // Render agent trace if present
    let traceHTML = '';
    if (res.agent_trace && res.agent_trace.length > 0) {
        let traceStepsHTML = '';
        res.agent_trace.forEach(step => {
            if (step.type === 'tool_call') {
                traceStepsHTML += `
                    <div class="trace-step tool-step">
                        <span class="step-lbl badge badge-info"><i class="fa-solid fa-screwdriver-wrench"></i> Tool Run</span>
                        <strong>${step.tool_name}</strong>
                        <div class="step-code"><strong>Input:</strong> <code>${JSON.stringify(step.tool_input)}</code></div>
                        <div class="step-code"><strong>Output:</strong> <code>${step.tool_output}</code></div>
                    </div>
                `;
            } else {
                traceStepsHTML += `
                    <div class="trace-step thought-step">
                        <span class="step-lbl badge badge-success"><i class="fa-solid fa-lightbulb"></i> Thought</span>
                        <p class="step-text">${step.content}</p>
                    </div>
                `;
            }
        });
        
        traceHTML = `
            <div class="detail-section">
                <h4>Agent Trajectory (Tool calls)</h4>
                <div class="trace-timeline-wrapper">
                    ${traceStepsHTML}
                </div>
            </div>
        `;
    }

    // Render detail layout
    detailPane.innerHTML = `
        <div class="detail-section">
            <h4>TestCase Prompt Query</h4>
            <div class="detail-box">${escapeHTML(res.test_case?.input_prompt || 'N/A')}</div>
        </div>

        ${res.test_case?.reference_context ? `
            <div class="detail-section">
                <h4>Grounding / Reference Context</h4>
                <div class="detail-box">${escapeHTML(res.test_case.reference_context)}</div>
            </div>
        ` : ''}

        <div class="detail-section">
            <h4>Generated Response</h4>
            <div class="detail-box" style="border-left: 3px solid var(--neon-cyan); background-color: rgba(0, 240,255, 0.015);">${escapeHTML(res.generated_response)}</div>
        </div>

        ${traceHTML}

        <div class="detail-section">
            <h4>Evaluators Benchmarks</h4>
            <div class="scores-breakdown">
                ${scoresHTML}
            </div>
        </div>
    `;
}

// ==========================================
// Playground Tab Management
// ==========================================
async function runComparison() {
    const input_prompt = document.getElementById('play-prompt').value;
    const reference_context = document.getElementById('play-context').value || null;
    const expected_output = document.getElementById('play-expected').value || null;
    const toolsStr = document.getElementById('play-tools').value;
    
    // Parse expected tools
    let expected_tools = null;
    if (toolsStr && toolsStr.trim() !== '') {
        expected_tools = toolsStr.split(',').map(t => t.trim());
    }

    if (!input_prompt || input_prompt.trim() === '') {
        alert("Please enter a query prompt before running evaluation.");
        return;
    }

    // Set A
    const model_name_a = document.getElementById('compare-model-a').value;
    const system_prompt_a = document.getElementById('compare-system-a').value || null;
    
    // Set B
    const model_name_b = document.getElementById('compare-model-b').value;
    const system_prompt_b = document.getElementById('compare-system-b').value || null;

    // Show output row and clear previous
    const outputRow = document.getElementById('comparison-results-row');
    outputRow.style.display = 'grid';
    
    const panelA = document.getElementById('panel-output-a');
    const panelB = document.getElementById('panel-output-b');

    panelA.innerHTML = '<h3>Model Configuration A</h3><div class="panel-placeholder"><i class="fa-solid fa-spinner fa-spin large-icon"></i><p>Running Model A & evaluating...</p></div>';
    panelB.innerHTML = '<h3>Model Configuration B</h3><div class="panel-placeholder"><i class="fa-solid fa-spinner fa-spin large-icon"></i><p>Running Model B & evaluating...</p></div>';

    // Trigger evaluations concurrently
    const callA = apiCall('/api/evaluations/quick-check', 'POST', {
        input_prompt,
        reference_context,
        expected_output,
        expected_tools,
        model_name: model_name_a,
        system_prompt: system_prompt_a
    });

    const callB = apiCall('/api/evaluations/quick-check', 'POST', {
        input_prompt,
        reference_context,
        expected_output,
        expected_tools,
        model_name: model_name_b,
        system_prompt: system_prompt_b
    });

    try {
        const [resA, resB] = await Promise.all([callA, callB]);
        renderPlaygroundPanel(panelA, 'Model Configuration A', model_name_a, resA);
        renderPlaygroundPanel(panelB, 'Model Configuration B', model_name_b, resB);
    } catch (err) {
        console.error(err);
        panelA.innerHTML = '<p class="text-danger">Failed to process comparison evaluation.</p>';
        panelB.innerHTML = '<p class="text-danger">Failed to process comparison evaluation.</p>';
    }
}

function renderPlaygroundPanel(panelEl, title, modelName, res) {
    // Score Breakdown
    let scoresHTML = '';
    const scoresArray = Object.values(res.scores);
    
    if (scoresArray.length === 0) {
        scoresHTML = '<p class="text-muted">No evaluator metrics registered.</p>';
    } else {
        scoresArray.forEach(s => {
            let scoreVal = s.score;
            let barColor = 'var(--neon-emerald)';
            if (s.metric_type.startsWith('safety') || s.metric_type === 'hallucination') {
                if (scoreVal > 0.5) barColor = 'var(--neon-coral)';
                else if (scoreVal > 0.1) barColor = 'var(--neon-amber)';
            } else if (s.metric_type === 'response_score') {
                scoreVal = `${scoreVal} / 5`;
            }
            
            scoresHTML += `
                <div class="score-row">
                    <div class="score-row-header">
                        <span class="score-name">${formatMetricName(s.metric_type)}</span>
                        <span class="score-value-bold" style="color: ${barColor}">${scoreVal}</span>
                    </div>
                    <p class="score-explanation">${s.explanation || 'No rationale provided.'}</p>
                </div>
            `;
        });
    }

    panelEl.innerHTML = `
        <div class="panel-header">
            <h3>${title}</h3>
            <span class="badge badge-info">${modelName}</span>
        </div>
        
        <div class="output-meta-bar">
            <div class="meta-item"><i class="fa-solid fa-clock"></i> Latency: <span class="value">${res.latency_ms.toFixed(0)} ms</span></div>
            <div class="meta-item"><i class="fa-solid fa-receipt"></i> Est. Cost: <span class="value">$${res.estimated_cost.toFixed(5)}</span></div>
            <div class="meta-item"><i class="fa-solid fa-file-code"></i> Tokens: <span class="value">${res.prompt_tokens + res.completion_tokens}</span></div>
        </div>

        <div class="output-text-block">${escapeHTML(res.generated_response)}</div>

        <div class="metrics-section">
            <h5>Guardrails & Evaluators</h5>
            <div class="scores-breakdown">
                ${scoresHTML}
            </div>
        </div>
    `;
}

// ==========================================
// Formatting Helpers
// ==========================================
function formatMetricName(name) {
    const map = {
        'response_score': 'Response Quality (1-5)',
        'hallucination': 'Hallucination Level (0-1)',
        'grounding_check': 'Grounding Match (0-1)',
        'safety_pii': 'PII Leakage Guardrail',
        'safety_injection': 'Prompt Injection Guardrail',
        'safety_toxicity': 'Toxicity Guardrail',
        'safety_unsafe': 'Unsafe Advice Guardrail',
        'rag_context_precision': 'RAG Context Precision',
        'rag_context_recall': 'RAG Context Recall',
        'rag_faithfulness': 'RAG Faithfulness',
        'rag_answer_relevancy': 'Answer Relevancy',
        'agent_tool_selection': 'Agent Tool Selection',
        'agent_tool_correctness': 'Agent Tool Arguments',
        'agent_loop_detection': 'Agent Loop Detection',
        'agent_task_completion': 'Agent Task Completion'
    };
    return map[name] || name;
}

function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ==========================================
// Initial Load
// ==========================================
function loadAllData() {
    if (currentTab === 'leaderboards') loadLeaderboards();
    else if (currentTab === 'datasets') loadDatasets();
    else if (currentTab === 'prompts') loadPromptsTab();
    else if (currentTab === 'evaluations') {
        loadDatasets();
        loadPrompts();
        loadRuns();
    }
}

// On page load
window.addEventListener('DOMContentLoaded', () => {
    loadLeaderboards();
});

// ==========================================
// Prompts Tab & Versions Comparison Layout
// ==========================================
let selectedPromptName = null;

async function loadPromptsTab() {
    try {
        const data = await apiCall('/api/prompts');
        activePrompts = data;

        // Group prompts by name
        const groups = {};
        data.forEach(p => {
            if (!groups[p.name]) groups[p.name] = [];
            groups[p.name].push(p);
        });

        // Sort each group by version descending
        Object.keys(groups).forEach(name => {
            groups[name].sort((a, b) => b.version - a.version);
        });

        const listContainer = document.getElementById('prompt-list');
        if (listContainer) {
            listContainer.innerHTML = '';
            const names = Object.keys(groups);
            if (names.length === 0) {
                listContainer.innerHTML = '<p class="text-center text-muted pad-20">No prompt templates found. Create one to begin!</p>';
                return;
            }

            names.forEach(name => {
                const isActive = selectedPromptName === name ? 'active' : '';
                const versionsCount = groups[name].length;
                const latestPrompt = groups[name][0];
                listContainer.innerHTML += `
                    <div class="list-item ${isActive}" onclick="selectPromptGroup('${escapeJS(name)}')">
                        <div>
                            <span class="list-item-title">${escapeHTML(name)}</span>
                            <div class="list-item-subtitle">${versionsCount} version(s) | Latest: v${latestPrompt.version}</div>
                        </div>
                    </div>
                `;
            });
        }
    } catch (e) {
        console.error(e);
    }
}

function selectPromptGroup(name) {
    selectedPromptName = name;
    
    // Highlight list item
    document.querySelectorAll('#prompt-list .list-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // We reload list to show active state without breaking click
    loadPromptsTab();

    const detailsPanel = document.getElementById('prompt-details-panel');
    detailsPanel.innerHTML = '<div class="panel-placeholder"><i class="fa-solid fa-arrows-spin fa-spin large-icon"></i><p>Loading prompt history...</p></div>';

    // Find all versions
    const versions = activePrompts.filter(p => p.name === name).sort((a, b) => b.version - a.version);
    if (versions.length === 0) return;

    // Build version dropdown options
    let optionsHTML = '';
    versions.forEach(p => {
        optionsHTML += `<option value="${p.id}">Version ${p.version} (${new Date(p.created_at).toLocaleDateString()})</option>`;
    });

    // Build options for comparison dropdowns
    let compOptionsA = '';
    let compOptionsB = '';
    versions.forEach((p, idx) => {
        const selectedA = idx === 0 ? 'selected' : '';
        const selectedB = idx === 1 || (versions.length === 1 && idx === 0) ? 'selected' : '';
        compOptionsA += `<option value="${p.id}" ${selectedA}>v${p.version}</option>`;
        compOptionsB += `<option value="${p.id}" ${selectedB}>v${p.version}</option>`;
    });

    detailsPanel.innerHTML = `
        <div class="panel-header flex-between">
            <div>
                <h3>${escapeHTML(name)}</h3>
                <p class="subtitle">Manage templates and compare history side-by-side.</p>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
            <!-- Left sub-panel: Version Viewer & New Version Creator -->
            <div>
                <div class="glass-panel" style="padding: 15px; margin-bottom: 20px; background: rgba(255,255,255,0.01);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h4 style="margin: 0;">Template Viewer</h4>
                        <select id="viewer-version-select" class="select-sm" onchange="loadVersionToViewer(this.value)" style="width: auto;">
                            ${optionsHTML}
                        </select>
                    </div>
                    <textarea id="prompt-viewer-text" readonly rows="8" class="width-full" style="background: rgba(0,0,0,0.2); font-family: monospace; font-size: 0.9em; padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); color: #ccc; resize: vertical;">${escapeHTML(versions[0].template_text)}</textarea>
                </div>

                <div class="glass-panel" style="padding: 15px; background: rgba(255,255,255,0.01);">
                    <h4 style="margin-top: 0; margin-bottom: 10px;">Draft New Version (v${versions[0].version + 1})</h4>
                    <form onsubmit="createNewPromptVersion(event)" class="form-grid">
                        <input type="hidden" id="new-version-name" value="${escapeHTML(name)}">
                        <div class="form-group">
                            <textarea id="new-version-text" required rows="6" placeholder="Write new prompt text..." class="width-full" style="font-family: monospace; font-size: 0.9em;"></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary btn-sm"><i class="fa-solid fa-circle-plus"></i> Save New Version</button>
                    </form>
                </div>
            </div>

            <!-- Right sub-panel: Diff / Side-by-Side Comparison -->
            <div class="glass-panel" style="padding: 15px; background: rgba(255,255,255,0.01); display: flex; flex-direction: column;">
                <h4 style="margin-top: 0; margin-bottom: 10px;">Compare Versions</h4>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="flex: 1;">
                        <label style="font-size: 0.8em; color: #9ca3af;">Version A</label>
                        <select id="compare-ver-a" class="select-sm width-full">${compOptionsA}</select>
                    </div>
                    <div style="flex: 1;">
                        <label style="font-size: 0.8em; color: #9ca3af;">Version B</label>
                        <select id="compare-ver-b" class="select-sm width-full">${compOptionsB}</select>
                    </div>
                </div>
                <button class="btn btn-secondary btn-sm width-full" onclick="executePromptComparison()" style="margin-bottom: 15px;">
                    <i class="fa-solid fa-arrows-left-right"></i> Compare Side-by-Side
                </button>
                <div id="compare-output-area" style="flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; display: none;">
                    <div>
                        <div style="font-size: 0.8em; font-weight: 600; margin-bottom: 5px; color: var(--neon-cyan);">Version A Text</div>
                        <div id="compare-text-a" style="white-space: pre-wrap; font-family: monospace; font-size: 0.8em; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05); height: 250px; overflow-y: auto;"></div>
                    </div>
                    <div>
                        <div style="font-size: 0.8em; font-weight: 600; margin-bottom: 5px; color: var(--neon-purple);">Version B Text</div>
                        <div id="compare-text-b" style="white-space: pre-wrap; font-family: monospace; font-size: 0.8em; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05); height: 250px; overflow-y: auto;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function loadVersionToViewer(promptId) {
    const prompt = activePrompts.find(p => p.id === promptId);
    if (prompt) {
        document.getElementById('prompt-viewer-text').value = prompt.template_text;
    }
}

async function createNewPromptVersion(e) {
    e.preventDefault();
    const name = document.getElementById('new-version-name').value;
    const template_text = document.getElementById('new-version-text').value;

    try {
        await apiCall('/api/prompts', 'POST', { name, template_text });
        loadPromptsTab();
        // reselect group
        setTimeout(() => {
            selectPromptGroup(name);
        }, 300);
    } catch (e) {
        console.error(e);
    }
}

function executePromptComparison() {
    const idA = document.getElementById('compare-ver-a').value;
    const idB = document.getElementById('compare-ver-b').value;
    
    const pA = activePrompts.find(p => p.id === idA);
    const pB = activePrompts.find(p => p.id === idB);
    
    if (pA && pB) {
        document.getElementById('compare-text-a').textContent = pA.template_text;
        document.getElementById('compare-text-b').textContent = pB.template_text;
        document.getElementById('compare-output-area').style.display = 'grid';
    }
}

// Modal Toggle Helpers
function showCreatePromptModal() {
    document.getElementById('create-prompt-modal').classList.add('active');
}

function hideCreatePromptModal() {
    document.getElementById('create-prompt-modal').classList.remove('active');
}

async function createNewPrompt(e) {
    e.preventDefault();
    const name = document.getElementById('prompt-name-input').value;
    const template_text = document.getElementById('prompt-text-input').value;

    try {
        await apiCall('/api/prompts', 'POST', { name, template_text });
        hideCreatePromptModal();
        document.getElementById('prompt-name-input').value = '';
        document.getElementById('prompt-text-input').value = '';
        selectedPromptName = name;
        loadPromptsTab();
    } catch (err) {
        console.error(err);
    }
}

// ==========================================
// CSV/JSON Dataset Import Helpers
// ==========================================
function showImportModal(datasetId) {
    document.getElementById('import-dataset-id').value = datasetId;
    document.getElementById('import-testcase-modal').classList.add('active');
}

function hideImportModal() {
    document.getElementById('import-testcase-modal').classList.remove('active');
}

async function importFile(e) {
    e.preventDefault();
    const datasetId = document.getElementById('import-dataset-id').value;
    const fileInput = document.getElementById('import-file-input');
    
    if (fileInput.files.length === 0) {
        alert("Please choose a file to upload.");
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await fetch(`/api/datasets/${datasetId}/import`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to import file.");
        }
        
        const res = await response.json();
        alert(res.message || "Test cases imported successfully.");
        
        hideImportModal();
        fileInput.value = '';
        selectDataset(datasetId);
    } catch (err) {
        console.error(err);
        alert(`Import failed: ${err.message}`);
    }
}

// JS Escape helper
function escapeJS(str) {
    if (!str) return '';
    return str.replace(/'/g, "\\'");
}
