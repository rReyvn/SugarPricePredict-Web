from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django_q.tasks import async_task
from django.conf import settings
import os
import json
import pandas as pd
import joblib
import io
import base64
from .pipeline import (
    EVAL_PLOT_PATH,
    FORECAST_RESULTS_PATH,
    COMBINED_PLOT_PATH, # Added
    EVALUATION_METRICS_PATH, # Added
    MODEL_PATH, # Added
    PROVINCE_MAP_PATH, # Added
    forecast_future_data, # Added
    plot_combined_forecast, # Added
    DF_TRANSFORMED_PATH, # Added
)


@csrf_exempt
@require_POST
def start_training_view(request):
    """
    Starts the model training task for all datasets.
    """
    try:
        # The task now finds all datasets by itself.
        async_task("rfr_model.q_tasks.train_on_all_datasets_task", timeout=300)
        return JsonResponse(
            {"message": "Model training started in the background."}, status=202
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def prediction_results_view(request):
    """
    Loads the pre-computed forecast and evaluation plot and returns them.
    Can also generate forecast based on selected province and horizon.
    """
    selected_province = request.GET.get('province')
    horizon_str = request.GET.get('horizon', '180') # Default to 180 days

    try:
        horizon = int(horizon_str)
        if not (1 <= horizon <= 180):
            raise ValueError("Horizon must be between 1 and 180.")
    except ValueError as e:
        return JsonResponse({"error": f"Invalid horizon value: {e}"}, status=400)

    # Required files for initial load and evaluation metrics
    required_files_base = [
        EVAL_PLOT_PATH,
        EVALUATION_METRICS_PATH,
        MODEL_PATH,
        PROVINCE_MAP_PATH,
        DF_TRANSFORMED_PATH, # Now required
    ]
    
    # Check for existence of all base required files
    for f in required_files_base:
        if not os.path.exists(f):
            return JsonResponse(
                {
                    "error": f"Artifact {os.path.basename(f)} not found. Please train a model first."
                },
                status=404,
            )

    try:
        # Load necessary artifacts
        model = joblib.load(MODEL_PATH)
        province_mapping = joblib.load(PROVINCE_MAP_PATH)
        evaluation_metrics = joblib.load(EVALUATION_METRICS_PATH)
        df_transformed = joblib.load(DF_TRANSFORMED_PATH) # Load the stored df_transformed
        
        # Get list of all provinces for the dropdown
        all_provinces = sorted(df_transformed["Province"].unique().tolist())

        # Validate selected_province
        if selected_province and selected_province not in all_provinces:
            return JsonResponse({"error": f"Province '{selected_province}' not found."}, status=400)

        # Generate forecast data dynamically based on selection
        # forecast_future_data will always generate for all provinces, then we filter/aggregate
        forecast_df_full = forecast_future_data(
            df_transformed,
            province_mapping,
            model,
            horizon=horizon, # Pass the horizon to forecast_future_data
        )

        df_for_table = None
        df_historical_for_plot = None
        df_predicted_for_plot = None
        plot_title = "Historical and Forecasted Sugar Prices"

        if selected_province:
            # Filter for specific province
            df_for_table = forecast_df_full[forecast_df_full["Province"] == selected_province].copy()
            df_for_table = df_for_table[df_for_table['Date'] <= (df_for_table['Date'].min() + pd.Timedelta(days=horizon-1))].copy()

            df_historical_for_plot = df_transformed[df_transformed["Province"] == selected_province].copy()
            df_predicted_for_plot = forecast_df_full[forecast_df_full["Province"] == selected_province].copy()
            df_predicted_for_plot = df_predicted_for_plot[df_predicted_for_plot['Date'] <= (df_predicted_for_plot['Date'].min() + pd.Timedelta(days=horizon-1))].copy()

            plot_title = f"Historical and Forecasted Sugar Prices ({selected_province})"

        else: # "All Provinces" selected - Calculate mean
            # Mean for table (forecast only)
            df_for_table = forecast_df_full.groupby("Date")["Prediction"].mean().reset_index()
            df_for_table["Province"] = "Mean" # Add Province column for consistent display
            df_for_table = df_for_table[df_for_table['Date'] <= (df_for_table['Date'].min() + pd.Timedelta(days=horizon-1))].copy()

            # Mean historical for plot
            df_historical_for_plot = df_transformed.groupby("Date")["Price"].mean().reset_index()
            df_historical_for_plot["Province"] = "Mean"

            # Mean predicted for plot
            df_predicted_for_plot = forecast_df_full.groupby("Date")["Prediction"].mean().reset_index()
            df_predicted_for_plot["Province"] = "Mean"
            df_predicted_for_plot = df_predicted_for_plot[df_predicted_for_plot['Date'] <= (df_predicted_for_plot['Date'].min() + pd.Timedelta(days=horizon-1))].copy()


            plot_title = "Historical and Forecasted Sugar Prices (Mean of All Provinces)"
        
        # Format 'Date' column for table
        # Rename 'Prediction' to 'Price' for table display consistency if showing mean forecast
        if not selected_province:
            df_for_table = df_for_table.rename(columns={'Prediction': 'Price'})

        df_for_table["Date"] = df_for_table["Date"].dt.strftime("%d-%m-%Y")


        # Prepare forecast table HTML
        forecast_table_html = df_for_table.to_html(
            classes="min-w-full divide-y divide-gray-200", border=0, index=False
        )
        forecast_table_html = forecast_table_html.replace('<th>', '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">')
        forecast_table_html = forecast_table_html.replace('<td>', '<td class="px-6 py-4 whitespace-nowrap text-left">')

        rmse_value = round(evaluation_metrics["RMSE"], 2)
        mape_value = round(evaluation_metrics["MAPE"], 2)

        # Encode evaluation plot to base64
        with open(EVAL_PLOT_PATH, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        plot_base64 = f"data:image/png;base64,{encoded_string}"
        
        # Generate and encode combined plot to base64 dynamically
        buf = io.BytesIO()
        plot_combined_forecast(df_historical_for_plot, df_predicted_for_plot, buf, title=plot_title)
        buf.seek(0) # Rewind the buffer
        combined_encoded_string = base64.b64encode(buf.read()).decode()
        combined_plot_base64 = f"data:image/png;base64,{combined_encoded_string}"
        buf.close()

        return JsonResponse(
            {
                "forecast_table": forecast_table_html,
                "plot": plot_base64, # Original evaluation plot (Actual vs. Prediction)
                "rmse": rmse_value,
                "mape": mape_value,
                "combined_plot": combined_plot_base64, # Dynamically generated combined plot
                "provinces": all_provinces, # List of provinces for frontend dropdown
                "selected_province": selected_province,
                "selected_horizon": horizon,
            }
        )
    except Exception as e:
        return JsonResponse({"error": f"Failed to generate results: {str(e)}"}, status=500)

