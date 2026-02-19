from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django_q.tasks import async_task
from django_q.models import Task
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
    COMBINED_PLOT_PATH,  # Added
    EVALUATION_METRICS_PATH,  # Added
    MODEL_PATH,  # Added
    PROVINCE_MAP_PATH,  # Added
    forecast_future_data,  # Added
    plot_combined_forecast,  # Added
    DF_TRANSFORMED_PATH,  # Added
)


@csrf_exempt
@require_POST
def start_training_view(request):
    """
    Starts the model training task, ensuring only one runs at a time.
    """
    task_name = "rfr_model.q_tasks.train_on_all_datasets_task"
    
    # Check for existing running or queued tasks. A task is considered "in-progress" 
    # if it has been created but does not have a success=True/False flag yet.
    in_progress_tasks = Task.objects.filter(func=task_name, success__isnull=True).count()

    if in_progress_tasks > 0:
        return JsonResponse(
            {"error": "A training task is already in progress. Please wait for it to complete."},
            status=409,  # 409 Conflict
        )

    try:
        # The task now finds all datasets by itself.
        async_task(task_name, timeout=300)
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
    selected_province = request.GET.get("province")
    horizon_str = request.GET.get("horizon", "180")  # Default to 180 days

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
        DF_TRANSFORMED_PATH,  # Now required
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
        df_transformed = joblib.load(
            DF_TRANSFORMED_PATH
        )  # Load the stored df_transformed

        # Determine prediction start date (day after the last date in the historical data)
        prediction_start_date = df_transformed["Date"].max() + pd.Timedelta(days=1)

        # Get list of all provinces for the dropdown
        all_provinces = sorted(df_transformed["Province"].unique().tolist())

        # Validate selected_province
        if selected_province and selected_province not in all_provinces:
            return JsonResponse(
                {"error": f"Province '{selected_province}' not found."}, status=400
            )

        # Generate forecast data dynamically based on selection
        # forecast_future_data will always generate for all provinces, then we filter/aggregate
        forecast_df_full = forecast_future_data(
            df_transformed,
            province_mapping,
            model,
            horizon=horizon,  # Pass the horizon to forecast_future_data
        )

        df_for_table = None
        df_historical_for_plot = None
        df_predicted_for_plot = None
        plot_title = "Forecasted Sugar Prices"

        if selected_province:
            # Filter for specific province
            df_for_table = forecast_df_full[
                forecast_df_full["Province"] == selected_province
            ].copy()
            df_for_table = df_for_table[
                df_for_table["Date"]
                <= (df_for_table["Date"].min() + pd.Timedelta(days=horizon - 1))
            ].copy()
            df_for_table["Prediction"] = df_for_table["Prediction"].round(0)

            df_historical_for_plot = df_transformed[
                df_transformed["Province"] == selected_province
            ].copy()
            df_predicted_for_plot = forecast_df_full[
                forecast_df_full["Province"] == selected_province
            ].copy()
            df_predicted_for_plot = df_predicted_for_plot[
                df_predicted_for_plot["Date"]
                <= (
                    df_predicted_for_plot["Date"].min() + pd.Timedelta(days=horizon - 1)
                )
            ].copy()

            plot_title = f"Forecasted Sugar Prices ({selected_province})"

        else:  # "All Provinces" selected - Calculate mean
            # Mean for table (forecast only)
            df_for_table = (
                forecast_df_full.groupby("Date")["Prediction"].mean().reset_index()
            )
            df_for_table["Province"] = (
                "All"  # Add Province column for consistent display
            )
            df_for_table = df_for_table[
                df_for_table["Date"]
                <= (df_for_table["Date"].min() + pd.Timedelta(days=horizon - 1))
            ].copy()
            df_for_table["Prediction"] = df_for_table["Prediction"].round(0)

            # Mean historical for plot
            df_historical_for_plot = (
                df_transformed.groupby("Date")["Price"].mean().reset_index()
            )
            df_historical_for_plot["Province"] = "Mean"

            # Mean predicted for plot
            df_predicted_for_plot = (
                forecast_df_full.groupby("Date")["Prediction"].mean().reset_index()
            )
            df_predicted_for_plot["Province"] = "Mean"
            df_predicted_for_plot = df_predicted_for_plot[
                df_predicted_for_plot["Date"]
                <= (
                    df_predicted_for_plot["Date"].min() + pd.Timedelta(days=horizon - 1)
                )
            ].copy()

            plot_title = "Forecasted Sugar Prices (Mean of All Provinces)"

        # Format 'Date' column for table
        # Rename 'Prediction' to 'Price' for table display consistency if showing mean forecast
        if not selected_province:
            df_for_table = df_for_table.rename(columns={"Prediction": "Price"})

        # Convert the price column to int to remove .0 decimals
        if "Price" in df_for_table.columns:
            df_for_table["Price"] = df_for_table["Price"].astype(int)
        elif "Prediction" in df_for_table.columns:
            df_for_table["Prediction"] = df_for_table["Prediction"].astype(int)

        df_for_table["Date"] = df_for_table["Date"].dt.strftime("%d-%m-%Y")

        # Prepare forecast table HTML
        forecast_table_html = df_for_table.to_html(
            classes="min-w-full divide-y divide-gray-200", border=0, index=False
        )
        forecast_table_html = forecast_table_html.replace(
            "<th>",
            '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">',
        )
        forecast_table_html = forecast_table_html.replace(
            "<td>", '<td class="px-6 py-4 whitespace-nowrap text-left">'
        )

        rmse_value = round(evaluation_metrics["RMSE"], 2)
        mape_value = round(evaluation_metrics["MAPE"], 2)

        # Encode evaluation plot to base64
        with open(EVAL_PLOT_PATH, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        plot_base64 = f"data:image/png;base64,{encoded_string}"

        # Limit historical data to 3 months before prediction starts
        if not df_predicted_for_plot.empty:
            prediction_start_date = df_predicted_for_plot["Date"].min()
            three_months_before = prediction_start_date - pd.DateOffset(months=3)
            df_historical_for_plot = df_historical_for_plot[
                df_historical_for_plot["Date"] >= three_months_before
            ].copy()

        # Generate Plotly data dynamically
        plotly_combined_plot_data = plot_combined_forecast(
            df_historical_for_plot, df_predicted_for_plot, title=plot_title
        )

        return JsonResponse(
            {
                "forecast_table": forecast_table_html,
                "plot": plot_base64,  # Original evaluation plot (Matplotlib)
                "rmse": rmse_value,
                "mape": mape_value,
                "combined_plot_data": plotly_combined_plot_data,  # New Plotly JSON data
                "provinces": all_provinces,  # List of provinces for frontend dropdown
                "selected_province": selected_province,
                "selected_horizon": horizon,
                "prediction_start_date": prediction_start_date.strftime("%Y-%m-%d"),
            }
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"Failed to generate results: {str(e)}"}, status=500
        )

def prediction_table_view(request):
    """
    Generates and returns only the prediction table HTML based on
    the selected province and horizon.
    """
    selected_province = request.GET.get("province")
    horizon_str = request.GET.get("horizon", "180")  # Default to 180 days

    try:
        horizon = int(horizon_str)
        if not (1 <= horizon <= 180):
            raise ValueError("Horizon must be between 1 and 180.")
    except ValueError as e:
        return JsonResponse({"error": f"Invalid horizon value: {e}"}, status=400)

    # Required files for generating the table
    required_files_for_table = [
        MODEL_PATH,
        PROVINCE_MAP_PATH,
        DF_TRANSFORMED_PATH,
    ]

    for f in required_files_for_table:
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
        df_transformed = joblib.load(DF_TRANSFORMED_PATH)

        # Get list of all provinces for validation
        all_provinces = sorted(df_transformed["Province"].unique().tolist())
        if selected_province and selected_province not in all_provinces:
            return JsonResponse(
                {"error": f"Province '{selected_province}' not found."}, status=400
            )

        # Generate forecast data dynamically
        forecast_df_full = forecast_future_data(
            df_transformed, province_mapping, model, horizon=horizon
        )

        df_for_table = None
        if selected_province:
            # Filter for specific province
            df_for_table = forecast_df_full[
                forecast_df_full["Province"] == selected_province
            ].copy()
        else:
            # "All Provinces" - Calculate mean
            df_for_table = (
                forecast_df_full.groupby("Date")["Prediction"].mean().reset_index()
            )
            df_for_table["Province"] = "All"

        # Trim to the exact horizon length
        df_for_table = df_for_table[
            df_for_table["Date"] <= (df_for_table["Date"].min() + pd.Timedelta(days=horizon - 1))
        ].copy()

        # Round and format for display
        df_for_table["Prediction"] = df_for_table["Prediction"].round(0)
        df_for_table["Date"] = df_for_table["Date"].dt.strftime("%d-%m-%Y")
        
        # Rename 'Prediction' to 'Price' for mean view
        if not selected_province:
            df_for_table = df_for_table.rename(columns={"Prediction": "Price"})
        
        # Convert numeric columns to int
        if "Price" in df_for_table.columns:
            df_for_table["Price"] = df_for_table["Price"].astype(int)
        if "Prediction" in df_for_table.columns:
            df_for_table["Prediction"] = df_for_table["Prediction"].astype(int)

        # Prepare forecast table HTML
        forecast_table_html = df_for_table.to_html(
            classes="min-w-full divide-y divide-gray-200", border=0, index=False
        )
        forecast_table_html = forecast_table_html.replace(
            "<th>",
            '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">',
        )
        forecast_table_html = forecast_table_html.replace(
            "<td>", '<td class="px-6 py-4 whitespace-nowrap text-left">'
        )

        return JsonResponse({"forecast_table": forecast_table_html})

    except Exception as e:
        return JsonResponse(
            {"error": f"Failed to generate prediction table: {str(e)}"}, status=500
        )
