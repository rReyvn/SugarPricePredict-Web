document.addEventListener('DOMContentLoaded', function () {
    // --- Results Fetching and Rendering ---
    const resultsContainer = document.getElementById('results-container');
    let currentProvince = "All";
    let plotTabBtn, tableTabBtn, evalTabBtn, plotContainer, tableContainer, evalContainer, tableHasBeenLoaded = false;

    if (!resultsContainer) {
        console.warn('Results container not found. Skipping results rendering.');
        return;
    }

    const predictionResultsUrl = resultsContainer.dataset.resultsUrl;
    const predictionTableUrl = resultsContainer.dataset.tableUrl;
    let activeTab = 'plot'; // Initialize active tab

    function switchTab(tabName) {
        if (tabName === 'plot') {
            tableContainer.classList.add('hidden');
            if (evalContainer) evalContainer.classList.add('hidden');
            plotContainer.classList.remove('hidden');
            plotTabBtn.classList.add('text-indigo-600', 'border-indigo-500');
            plotTabBtn.classList.remove('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            tableTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            tableTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            if (evalTabBtn) {
                evalTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                evalTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            }
            activeTab = 'plot';
        } else if (tabName === 'table') {
            plotContainer.classList.add('hidden');
            if (evalContainer) evalContainer.classList.add('hidden');
            tableContainer.classList.remove('hidden');
            tableTabBtn.classList.add('text-indigo-600', 'border-indigo-500');
            tableTabBtn.classList.remove('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            plotTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            plotTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            if (evalTabBtn) {
                evalTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                evalTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            }
            activeTab = 'table';
            if (!tableHasBeenLoaded) {
                fetchAndRenderTable();
                tableHasBeenLoaded = true;
            }
        } else if (tabName === 'eval') {
            plotContainer.classList.add('hidden');
            tableContainer.classList.add('hidden');
            if (evalContainer) evalContainer.classList.remove('hidden');
            if (evalTabBtn) {
                evalTabBtn.classList.add('text-indigo-600', 'border-indigo-500');
                evalTabBtn.classList.remove('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            }
            plotTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            plotTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            tableTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
            tableTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
            activeTab = 'eval';
            const evalPlotLineDiv = document.getElementById('eval-plot-line-div');
            if (evalPlotLineDiv && evalPlotLineDiv.data) {
                 Plotly.Plots.resize(evalPlotLineDiv);
            }
        }
    }

    function fetchAndRenderResults() {
        resultsContainer.innerHTML = `
            <div class="flex flex-col items-center justify-center p-4 bg-white rounded-2xl shadow-md h-96">
                <svg class="animate-spin h-8 w-8 text-indigo-600 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p class="text-center text-lg font-medium text-gray-700">Generating prediction results...</p>
                <p class="text-center text-sm text-gray-500 mt-2">This may take a moment.</p>
            </div>
        `;

        const urlParams = new URLSearchParams(window.location.search);
        const priceType = urlParams.get('price_type') || 'local';

        let url = predictionResultsUrl;
        const params = new URLSearchParams();
        if (currentProvince) {
            params.append('province', currentProvince);
        }
        params.append('price_type', priceType);

        if (params.toString()) {
            url += `?${params.toString()}`;
        }

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || 'An unknown error occurred')
                    });
                }
                return response.json();
            })
            .then(data => {
                console.log(data); // For debugging
                // Determine which metrics to display based on the selected province
                let metrics;
                if (data.selected_province && data.selected_province !== "All") {
                    metrics = data.evaluation_metrics.by_province[data.selected_province];
                } else {
                    metrics = data.evaluation_metrics.overall;
                }
                const rmse = metrics ? metrics.RMSE.toFixed(2) : 'N/A';
                const mape = metrics ? metrics.MAPE.toFixed(2) : 'N/A';
                const val_rmse = (metrics && metrics.Val_RMSE !== undefined) ? metrics.Val_RMSE.toFixed(2) : 'N/A';
                const val_mape = (metrics && metrics.Val_MAPE !== undefined) ? metrics.Val_MAPE.toFixed(2) : 'N/A';
                const splitRatio = data.evaluation_metrics.split_ratio;
                const trainPct = splitRatio ? (splitRatio.train * 100).toFixed(0) : 0;
                const valPct = splitRatio ? (splitRatio.val * 100).toFixed(0) : 0;
                const testPct = splitRatio ? (splitRatio.test * 100).toFixed(0) : 0;

                resultsContainer.innerHTML = `
                    <div class="p-4 bg-white rounded-2xl shadow-md">
                        <div class="flex flex-wrap justify-between items-center mb-4 gap-4">
                            <h2 class="text-xl font-semibold">Prediction Results</h2>
                            <div class="flex items-center gap-4">
                                <div class="flex items-center gap-2">
                                    <button id="prev-province-btn" class="p-2 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed">
                                        <svg class="h-5 w-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
                                        </svg>
                                    </button>
                                    <div class="w-48">
                                        <div class="relative">
                                            <label for="custom-province-select-button" class="block text-sm font-medium text-gray-700 sr-only">Province</label>
                                            <button id="custom-province-select-button" type="button" class="relative w-full cursor-default rounded-full bg-white py-2 pl-3 pr-12 flex items-center justify-center shadow-sm border border-gray-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm">
                                                <span id="selected-province-text" class="block truncate">All Provinces</span>
                                                <span class="pointer-events-none absolute inset-y-0 right-0 ml-3 flex items-center pr-4">
                                                    <svg class="h-5 w-5 text-gray-400" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                                                        <path fill-rule="evenodd" d="M10 3a.75.75 0 01.55.24l3.25 3.5a.75.75 0 11-1.1 1.02L10 4.852 7.3 7.76a.75.75 0 01-1.1-1.02l3.25-3.5A.75.75 0 0110 3zm-3.75 9.75a.75.75 0 011.1 0L10 15.148l2.65-2.908a.75.75 0 011.1 1.02l-3.25 3.5a.75.75 0 01-1.1 0l-3.25-3.5a.75.75 0 010-1.02z" clip-rule="evenodd" />
                                                    </svg>
                                                </span>
                                            </button>
                                            <div id="custom-province-options" class="absolute z-10 mt-2 w-full bg-white shadow-xl max-h-60 rounded-lg border border-gray-300 py-2 px-2 text-base overflow-auto focus:outline-none sm:text-sm hidden">
                                                <!-- Options will be injected here by JavaScript -->
                                            </div>
                                        </div>
                                    </div>
                                    <button id="next-province-btn" class="p-2 rounded-full bg-gray-200 hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed">
                                        <svg class="h-5 w-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-1 gap-6">
                            <div id="prediction-output-container">
                                    <div class="border-b border-gray-200">
                                        <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                                            <button id="plot-tab-btn" class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm text-indigo-600 border-indigo-500">
                                                Plot
                                            </button>
                                            <button id="table-tab-btn" class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm text-gray-500 hover:text-gray-700 hover:border-gray-300">
                                                Table
                                            </button>
                                            <button id="eval-tab-btn" class="whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm text-gray-500 hover:text-gray-700 hover:border-gray-300">
                                                Evaluation
                                            </button>
                                        </nav>
                                    </div>
                                    <div id="plot-container" class="py-4">
                                        <div id="combined-plot-div" class="rounded-lg" style="height: 400px;"></div>
                                    </div>
                                    <div id="table-container" class="hidden py-4">
                                        <div id="table-summary" class="mb-4">
                                            <!-- Summary cards will be injected here -->
                                        </div>
                                        <div id="table-content-area" class="rounded-lg overflow-y-auto max-h-96 border border-gray-200">
                                            <!-- Table content loads here -->
                                        </div>
                                    </div>
                                    <div id="eval-container" class="hidden py-4">
                                        <div class="mb-6 p-5 bg-white rounded-xl border border-gray-100 shadow-sm">
                                            <p class="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wider">Data Split Ratio</p>
                                            <div class="w-full flex h-3 rounded-full overflow-hidden bg-gray-100 mb-3 shadow-inner">
                                                <div class="bg-indigo-500 hover:bg-indigo-600 transition-colors duration-300" style="width: ${trainPct}%" title="Train: ${trainPct}%"></div>
                                                <div class="bg-sky-400 hover:bg-sky-500 transition-colors duration-300" style="width: ${valPct}%" title="Validation: ${valPct}%"></div>
                                                <div class="bg-teal-400 hover:bg-teal-500 transition-colors duration-300" style="width: ${testPct}%" title="Test: ${testPct}%"></div>
                                            </div>
                                            <div class="flex justify-between text-xs text-gray-600 font-medium px-1">
                                                <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-indigo-500 mr-2 shadow-sm"></span> Train (${trainPct}%)</div>
                                                <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-sky-400 mr-2 shadow-sm"></span> Val (${valPct}%)</div>
                                                <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-teal-400 mr-2 shadow-sm"></span> Test (${testPct}%)</div>
                                            </div>
                                        </div>
                                        <div class="grid grid-cols-1 gap-4">
                                            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                                                <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                                    <p class="text-sm font-medium text-gray-500">Test RMSE</p>
                                                    <p id="rmse-value" class="mt-1 text-2xl font-semibold text-gray-900">${rmse}</p>
                                                </div>
                                                <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                                    <p class="text-sm font-medium text-gray-500">Test MAPE</p>
                                                    <p id="mape-value" class="mt-1 text-2xl font-semibold text-gray-900">${mape}%</p>
                                                </div>
                                                <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                                    <p class="text-sm font-medium text-gray-500">Validation RMSE</p>
                                                    <p id="val-rmse-value" class="mt-1 text-2xl font-semibold text-gray-900">${val_rmse}</p>
                                                </div>
                                                <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                                    <p class="text-sm font-medium text-gray-500">Validation MAPE</p>
                                                    <p id="val-mape-value" class="mt-1 text-2xl font-semibold text-gray-900">${val_mape}%</p>
                                                </div>
                                            </div>
                                            <div class="flex flex-col gap-4">
                                                <div id="eval-plot-line-div" class="w-full rounded-lg" style="height: 400px;"></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                const customProvinceSelectButton = document.getElementById('custom-province-select-button');
                const selectedProvinceText = document.getElementById('selected-province-text');
                const customProvinceOptions = document.getElementById('custom-province-options');
                plotTabBtn = document.getElementById('plot-tab-btn');
                tableTabBtn = document.getElementById('table-tab-btn');
                evalTabBtn = document.getElementById('eval-tab-btn');
                plotContainer = document.getElementById('plot-container');
                tableContainer = document.getElementById('table-container');
                evalContainer = document.getElementById('eval-container');
                const prevProvinceBtn = document.getElementById('prev-province-btn');
                const nextProvinceBtn = document.getElementById('next-province-btn');
                tableHasBeenLoaded = false;

                // Handle province navigation
                prevProvinceBtn.disabled = !data.prev_province;
                nextProvinceBtn.disabled = !data.next_province;

                prevProvinceBtn.onclick = () => {
                    if (data.prev_province) {
                        currentProvince = data.prev_province;
                        fetchAndRenderResults();
                    }
                };

                nextProvinceBtn.onclick = () => {
                    if (data.next_province) {
                        currentProvince = data.next_province;
                        fetchAndRenderResults();
                    }
                };

                function updateEvalPlotVisibility(province) {
                    const evalPlotLineDiv = document.getElementById('eval-plot-line-div');
                    if (!evalPlotLineDiv) {
                        return;
                    }

                    const update = {
                        'visible': []
                    };
                    let isMeanVisible = (province === 'All');

                    evalPlotLineDiv.data.forEach((trace, i) => {
                        if (trace.name.startsWith('Mean')) {
                            update.visible.push(isMeanVisible);
                        } else {
                            // Extracts province name from trace name like "DKI JAKARTA - Actual"
                            const traceProvince = trace.name.split(' - ')[0];
                            update.visible.push(traceProvince === province);
                        }
                    });

                    Plotly.restyle(evalPlotLineDiv, update);
                }

                const combinedPlotDiv = document.getElementById('combined-plot-div');
                if (data.combined_plot_data && combinedPlotDiv) {
                    // Ensure layout and yaxis exist before modifying
                    if (!data.combined_plot_data.layout) {
                        data.combined_plot_data.layout = {};
                    }
                    if (!data.combined_plot_data.layout.yaxis) {
                        data.combined_plot_data.layout.yaxis = {};
                    }
                    // Apply tickformat and hoverformat for 0 decimal places
                    data.combined_plot_data.layout.yaxis.tickformat = '.0f';
                    data.combined_plot_data.layout.yaxis.hoverformat = '.0f';
                    Plotly.newPlot(combinedPlotDiv, data.combined_plot_data.data, data.combined_plot_data.layout, {
                        responsive: true
                    });
                }

                const evalPlotLineDiv = document.getElementById('eval-plot-line-div');
                if (data.eval_plot_line_data && evalPlotLineDiv) {
                    // Ensure layout and yaxis exist before modifying
                    if (!data.eval_plot_line_data.layout) {
                        data.eval_plot_line_data.layout = {};
                    }
                    if (!data.eval_plot_line_data.layout.yaxis) {
                        data.eval_plot_line_data.layout.yaxis = {};
                    }
                    // Apply tickformat and hoverformat for 0 decimal places
                    data.eval_plot_line_data.layout.yaxis.tickformat = '.0f';
                    data.eval_plot_line_data.layout.yaxis.hoverformat = '.0f';
                    Plotly.newPlot(evalPlotLineDiv, data.eval_plot_line_data.data, data.eval_plot_line_data.layout, {
                        responsive: true
                    });
                    updateEvalPlotVisibility(currentProvince);
                }


                // Clear previous options
                customProvinceOptions.innerHTML = '';

                // Populate custom dropdown with options
                data.provinces.forEach(province => {
                    const optionDiv = document.createElement('div');
                    optionDiv.dataset.value = province;
                    optionDiv.textContent = province === "All" ? "All Provinces" : province;
                    optionDiv.classList.add('text-gray-900', 'relative', 'cursor-default', 'select-none', 'py-2', 'px-4', 'rounded-full', 'hover:bg-indigo-600', 'hover:text-white');
                    customProvinceOptions.appendChild(optionDiv);

                    // Add click listener for selection
                    optionDiv.addEventListener('click', () => {
                        selectedProvinceText.textContent = (province === "All" ? "All Provinces" : province); // Ensure "All Provinces" is displayed
                        currentProvince = province;
                        customProvinceOptions.classList.add('hidden'); // Hide options after selection
                        fetchAndRenderResults();
                        tableHasBeenLoaded = false;
                    });
                });

                // Set initial selected value text
                selectedProvinceText.textContent = data.selected_province === "All" ? "All Provinces" : data.selected_province;

                // Toggle dropdown visibility
                customProvinceSelectButton.addEventListener('click', (event) => {
                    event.stopPropagation(); // Prevent document click from immediately closing
                    customProvinceOptions.classList.toggle('hidden');
                });

                // Close dropdown when clicking outside
                document.addEventListener('click', (event) => {
                    // Check if the click occurred outside the dropdown button and options container
                    const dropdownContainer = customProvinceSelectButton.closest('.relative'); // Assuming the relative div is the container
                    if (dropdownContainer && !dropdownContainer.contains(event.target)) {
                        customProvinceOptions.classList.add('hidden');
                    }
                });

                plotTabBtn.addEventListener('click', () => {
                    switchTab('plot');
                });

                tableTabBtn.addEventListener('click', () => {
                    switchTab('table');
                });

                evalTabBtn.addEventListener('click', () => {
                    switchTab('eval');
                });

                // After rendering, ensure the correct tab is displayed
                switchTab(activeTab);

            })
            .catch(error => {
                resultsContainer.innerHTML = `
                    <div class="p-4 bg-white rounded-2xl shadow-md text-center">
                        <h2 class="text-xl font-semibold mb-2">No Results Found</h2>
                        <p class="text-gray-500">The model may not have been trained for this price type yet. Please click the "Retrain model" button.</p>
                    </div>
                `;
                console.warn('Could not fetch results:', error.message);
                // Also show a notification to make the error obvious
                if (window.showNotification) {
                    window.showNotification(error.message, 'error');
                }
            });
    }

    function fetchAndRenderTable() {
        const tableContentArea = document.getElementById('table-content-area');
        tableContentArea.innerHTML = `<div class="flex flex-col items-center justify-center p-4 h-full"><svg class="animate-spin h-6 w-6 text-indigo-600 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><p class="text-center text-gray-700">Loading table data...</p></div>`;

        const urlParams = new URLSearchParams(window.location.search);
        const priceType = urlParams.get('price_type') || 'local';

        let url = predictionTableUrl;
        const params = new URLSearchParams();
        if (currentProvince) {
            params.append('province', currentProvince);
        }
        params.append('price_type', priceType);

        if (params.toString()) {
            url += `?${params.toString()}`;
        }

        fetch(url)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || 'An unknown error occurred')
                    });
                }
                return response.json();
            })
            .then(data => {
                const tableSummary = document.getElementById('table-summary');
                if (tableSummary) {
                    tableSummary.innerHTML = `
                        <div class="bg-white rounded-lg border border-gray-200 mb-4 shadow-sm overflow-hidden">
                            <div class="flex flex-col sm:flex-row divide-y sm:divide-y-0 sm:divide-x divide-gray-200">
                                <div class="flex-1 p-3 flex items-center justify-center">
                                    <div class="flex items-center space-x-3">
                                        <div class="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-emerald-50 text-emerald-500">
                                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                                        </div>
                                        <div class="text-left">
                                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Highest Prediction</p>
                                            <p class="text-lg font-bold text-gray-900 leading-tight">${data.highest_prediction !== null ? data.highest_prediction : 'N/A'}</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="flex-1 p-3 flex items-center justify-center">
                                    <div class="flex items-center space-x-3">
                                        <div class="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-rose-50 text-rose-500">
                                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"></path></svg>
                                        </div>
                                        <div class="text-left">
                                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Lowest Prediction</p>
                                            <p class="text-lg font-bold text-gray-900 leading-tight">${data.lowest_prediction !== null ? data.lowest_prediction : 'N/A'}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }
                tableContentArea.innerHTML = data.forecast_table;
            })
            .catch(error => {
                tableContentArea.innerHTML = `<p class="text-center text-red-500 p-4">Error: ${error.message}</p>`;
                console.warn('Could not fetch table:', error.message);
            });
    }

    fetchAndRenderResults();
});