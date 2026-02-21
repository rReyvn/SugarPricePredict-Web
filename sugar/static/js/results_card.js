document.addEventListener('DOMContentLoaded', function () {
    // --- Results Fetching and Rendering ---
    const resultsContainer = document.getElementById('results-container');
    let currentProvince = "All";

    if (!resultsContainer) {
        console.warn('Results container not found. Skipping results rendering.');
        return;
    }

    const predictionResultsUrl = resultsContainer.dataset.resultsUrl;
    const predictionTableUrl = resultsContainer.dataset.tableUrl;

    function fetchAndRenderResults() {
        resultsContainer.innerHTML = `
            <div class="flex flex-col items-center justify-center p-6 bg-white rounded-2xl shadow-md h-96">
                <svg class="animate-spin h-8 w-8 text-indigo-600 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <p class="text-center text-lg font-medium text-gray-700">Generating prediction results...</p>
                <p class="text-center text-sm text-gray-500 mt-2">This may take a moment.</p>
            </div>
        `;

        let url = predictionResultsUrl;
        const params = new URLSearchParams();
        if (currentProvince) {
            params.append('province', currentProvince);
        }
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
                resultsContainer.innerHTML = `
                    <div class="p-6 bg-white rounded-2xl shadow-md">
                        <div class="flex flex-wrap justify-between items-center mb-4 gap-4">
                            <h2 class="text-xl font-semibold">Prediction Results</h2>
                            <div class="flex items-center gap-4">
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
                                        </nav>
                                    </div>
                                    <div id="plot-container" class="py-4">
                                        <div id="combined-plot-div" class="rounded-lg" style="height: 400px;"></div>
                                    </div>
                                    <div id="table-container" class="hidden py-4">
                                        <div id="table-content-area" class="rounded-lg overflow-y-auto max-h-96 border border-gray-200">
                                            <!-- Table content loads here -->
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="p-4">
                                <h3 class="text-lg font-semibold mb-4">Model Evaluation</h3>
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                                    <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                        <p class="text-sm font-medium text-gray-500">RMSE</p>
                                        <p class="mt-1 text-2xl font-semibold text-gray-900">${data.rmse.toFixed(2)}</p>
                                    </div>
                                    <div class="p-4 bg-white rounded-lg border border-gray-200 text-center">
                                        <p class="text-sm font-medium text-gray-500">MAPE</p>
                                        <p class="mt-1 text-2xl font-semibold text-gray-900">${data.mape.toFixed(2)}%</p>
                                    </div>
                                </div>
                                <div>
                                    <img src="${data.plot}" alt="Model Evaluation Plot" class="rounded-lg w-full max-w-sm mx-auto" />
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                const customProvinceSelectButton = document.getElementById('custom-province-select-button');
                const selectedProvinceText = document.getElementById('selected-province-text');
                const customProvinceOptions = document.getElementById('custom-province-options');
                const plotTabBtn = document.getElementById('plot-tab-btn');
                const tableTabBtn = document.getElementById('table-tab-btn');
                const plotContainer = document.getElementById('plot-container');
                const tableContainer = document.getElementById('table-container');
                let tableHasBeenLoaded = false;

                const combinedPlotDiv = document.getElementById('combined-plot-div');
                if (data.combined_plot_data && combinedPlotDiv) {
                    Plotly.newPlot(combinedPlotDiv, data.combined_plot_data.data, data.combined_plot_data.layout, {
                        responsive: true
                    });
                }

                // Clear previous options
                customProvinceOptions.innerHTML = '';

                // Populate custom dropdown with options
                const addOption = (value, text) => {
                    const optionDiv = document.createElement('div');
                    optionDiv.dataset.value = value;
                    optionDiv.textContent = text;
                    optionDiv.classList.add('text-gray-900', 'relative', 'cursor-default', 'select-none', 'py-2', 'px-4', 'rounded-full', 'hover:bg-indigo-600', 'hover:text-white');
                    customProvinceOptions.appendChild(optionDiv);

                    // Add click listener for selection
                    optionDiv.addEventListener('click', () => {
                        selectedProvinceText.textContent = (value === "All" ? "All Provinces" : text); // Ensure "All Provinces" is displayed
                        currentProvince = value;
                        customProvinceOptions.classList.add('hidden'); // Hide options after selection
                        fetchAndRenderResults();
                        tableHasBeenLoaded = false;
                    });
                };

                addOption("All", "All Provinces"); // Always add "All Provinces" option

                if (data.provinces) {
                    data.provinces.forEach(province => {
                        addOption(province, province);
                    });
                }

                // Set initial selected value based on data or currentProvince
                let selectedValueForDisplay = "All Provinces";
                let selectedValueForBackend = "All";

                if (data.selected_province && data.selected_province !== "") {
                    selectedValueForBackend = data.selected_province;
                    selectedValueForDisplay = data.selected_province === "All" ? "All Provinces" : data.selected_province;
                } else if (currentProvince && currentProvince !== "") {
                    selectedValueForBackend = currentProvince;
                    selectedValueForDisplay = currentProvince === "All" ? "All Provinces" : currentProvince;
                }

                selectedProvinceText.textContent = selectedValueForDisplay;
                currentProvince = selectedValueForBackend; // Update currentProvince for subsequent fetches

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
                    tableContainer.classList.add('hidden');
                    plotContainer.classList.remove('hidden');
                    plotTabBtn.classList.add('text-indigo-600', 'border-indigo-500');
                    plotTabBtn.classList.remove('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                    tableTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                    tableTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
                });

                tableTabBtn.addEventListener('click', () => {
                    plotContainer.classList.add('hidden');
                    tableContainer.classList.remove('hidden');
                    tableTabBtn.classList.add('text-indigo-600', 'border-indigo-500');
                    tableTabBtn.classList.remove('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                    plotTabBtn.classList.add('text-gray-500', 'hover:text-gray-700', 'hover:border-gray-300');
                    plotTabBtn.classList.remove('text-indigo-600', 'border-indigo-500');
                    if (!tableHasBeenLoaded) {
                        fetchAndRenderTable();
                        tableHasBeenLoaded = true;
                    }
                });

            })
            .catch(error => {
                resultsContainer.innerHTML = `
                    <div class="p-6 bg-white rounded-2xl shadow-md text-center">
                        <h2 class="text-xl font-semibold mb-2">No Results Yet</h2>
                        <p class="text-gray-500">The model has not been trained yet. Click the "Retrain model" button to generate the first prediction.</p>
                        <p class="text-red-500 mt-2">Error: ${error.message}</p>
                    </div>
                `;
                console.warn('Could not fetch results:', error.message);
            });
    }

    function fetchAndRenderTable() {
        const tableContentArea = document.getElementById('table-content-area');
        tableContentArea.innerHTML = `<div class="flex flex-col items-center justify-center p-4 h-full"><svg class="animate-spin h-6 w-6 text-indigo-600 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><p class="text-center text-gray-700">Loading table data...</p></div>`;
        let url = predictionTableUrl;
        const params = new URLSearchParams();
        if (currentProvince) {
            params.append('province', currentProvince);
        }
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
                tableContentArea.innerHTML = data.forecast_table;
            })
            .catch(error => {
                tableContentArea.innerHTML = `<p class="text-center text-red-500 p-4">Error: ${error.message}</p>`;
                console.warn('Could not fetch table:', error.message);
            });
    }

    fetchAndRenderResults(); // Initial load
});
