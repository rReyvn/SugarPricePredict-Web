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
from django.db import transaction
from .models import TrainingLock
from .pipeline import (
    EVAL_PLOT_PATH,
    EVALUATION_METRICS_PATH,
    DF_TRANSFORMED_PATH,
    CACHED_PREDICTIONS_PATH,
    plot_combined_forecast,
)


@csrf_exempt
@require_POST
def start_training_view(request):
    """
    Starts the model training task, ensuring only one runs at a time
    using a database lock.
    """
    try:
        with transaction.atomic():
            # Get or create the lock object and lock it.
            lock, created = TrainingLock.objects.select_for_update().get_or_create(pk=1)

            if lock.is_locked:
                return JsonResponse(
                    {"error": "A training task is already in progress. Please wait for it to complete."},
                    status=409,  # 409 Conflict
                )

            # Check for tasks that might have failed without releasing the lock
            task_name = "rfr_model.q_tasks.train_on_all_datasets_task"
            in_progress_tasks = Task.objects.filter(func=task_name, success__isnull=True).count()
            if in_progress_tasks > 0:
                return JsonResponse(
                    {"error": "A training task is already in progress (according to Django Q). Please wait for it to complete."},
                    status=409,
                )

            # Acquire lock and start the task
            lock.is_locked = True
            lock.save()
            async_task(task_name, hook='rfr_model.hooks.training_complete_hook', timeout=300)

        return JsonResponse(
            {"message": "Model training started in the background."}, status=202
        )
    except Exception as e:
        # This will catch exceptions from the transaction or task creation
        return JsonResponse({"error": f"Failed to start training: {str(e)}"}, status=500)



def prediction_results_view(request):
    """
    Loads the pre-computed forecast and evaluation plot and returns them.
    Can also generate forecast based on selected province.
    """
    selected_province = request.GET.get("province") or "All"

    # Required files for initial load and evaluation metrics
    required_files_base = [
        EVAL_PLOT_PATH,
        EVALUATION_METRICS_PATH,
        DF_TRANSFORMED_PATH,
        CACHED_PREDICTIONS_PATH,
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
        evaluation_metrics = joblib.load(EVALUATION_METRICS_PATH)
        df_transformed = joblib.load(DF_TRANSFORMED_PATH)
        cached_predictions = joblib.load(CACHED_PREDICTIONS_PATH)

        # Determine prediction start date (day after the last date in the historical data)
        prediction_start_date = df_transformed["Date"].max() + pd.Timedelta(days=1)

        # Get list of all provinces for the dropdown
        all_provinces = sorted(df_transformed["Province"].unique().tolist())

        # Validate selected_province
        if selected_province not in all_provinces and selected_province != "All":
            return JsonResponse(
                {"error": f"Province '{selected_province}' not found."}, status=400
            )

        # Get data from cache
        province_data = cached_predictions[selected_province]
        df_historical_for_plot = province_data["historical"]
        df_predicted_for_plot = province_data["predicted"]

        df_for_table = df_predicted_for_plot.copy()
        df_for_table["Prediction"] = df_for_table["Prediction"].round(0)

        if selected_province == "All":
            plot_title = "Forecasted Sugar Prices (Mean of All Provinces)"
        else:
            plot_title = f"Forecasted Sugar Prices ({selected_province})"

        # Format 'Date' column for table
        if selected_province == "All":
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

        # Limit historical data to 6 months before prediction starts
        if not df_predicted_for_plot.empty:
            prediction_start_date = df_predicted_for_plot["Date"].min()
            three_months_before = prediction_start_date - pd.DateOffset(months=6)
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
    the selected province.
    """
    selected_province = request.GET.get("province") or "All"

    # Required files for generating the table
    required_files_for_table = [
        CACHED_PREDICTIONS_PATH,
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
        cached_predictions = joblib.load(CACHED_PREDICTIONS_PATH)
        df_transformed = joblib.load(DF_TRANSFORMED_PATH)

        # Get list of all provinces for validation
        all_provinces = sorted(df_transformed["Province"].unique().tolist())
        if selected_province not in all_provinces and selected_province != "All":
            return JsonResponse(
                {"error": f"Province '{selected_province}' not found."}, status=400
            )

        # Get data from cache
        province_data = cached_predictions[selected_province]
        df_for_table = province_data["predicted"].copy()


        # Round and format for display
        df_for_table["Prediction"] = df_for_table["Prediction"].round(0)
        df_for_table["Date"] = df_for_table["Date"].dt.strftime("%d-%m-%Y")
        
        # Rename 'Prediction' to 'Price' for mean view
        if selected_province == "All":
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
