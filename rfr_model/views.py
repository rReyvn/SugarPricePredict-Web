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
    get_model_paths,
    plot_combined_forecast,
)


@csrf_exempt
@require_POST
def start_training_view(request):
    """
    Starts the model training task based on the provided price_type,
    ensuring only one runs at a time using a database lock.
    """
    try:
        data = json.loads(request.body)
        price_type = data.get("price_type")

        if price_type not in ["local", "premium"]:
            return JsonResponse(
                {"error": "Invalid 'price_type'. Must be 'local' or 'premium'."},
                status=400,
            )

        with transaction.atomic():
            lock, created = TrainingLock.objects.select_for_update().get_or_create(pk=1)

            if lock.is_locked:
                return JsonResponse(
                    {
                        "error": "A training task is already in progress. Please wait for it to complete."
                    },
                    status=409,
                )

            task_name = "rfr_model.q_tasks.train_on_all_datasets_task"
            in_progress_tasks = Task.objects.filter(
                func=task_name, success__isnull=True
            ).count()
            if in_progress_tasks > 0:
                return JsonResponse(
                    {
                        "error": "A training task is already in progress (according to Django Q). Please wait."
                    },
                    status=409,
                )

            lock.is_locked = True
            lock.save()
            async_task(
                task_name,
                price_type,
                hook="rfr_model.hooks.training_complete_hook",
                timeout=300,
            )

        return JsonResponse(
            {"message": f"Model training for '{price_type}' started in the background."},
            status=202,
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body."}, status=400)
    except Exception as e:
        return JsonResponse(
            {"error": f"Failed to start training: {str(e)}"}, status=500
        )



def prediction_results_view(request):
    """
    Loads the pre-computed forecast and evaluation data for a given
    price_type and returns them. Can also generate forecast based on
    a selected province.
    """
    selected_province = request.GET.get("province") or "All"
    price_type = request.GET.get("price_type") or "local"

    if price_type not in ["local", "premium"]:
        return JsonResponse(
            {"error": "Invalid 'price_type'. Must be 'local' or 'premium'."}, status=400
        )

    try:
        paths = get_model_paths(price_type)
        required_files = [
            paths["eval_plot_path"],
            paths["evaluation_metrics_path"],
            paths["df_transformed_path"],
            paths["cached_predictions_path"],
            paths["eval_plot_line_path"],
        ]

        for f in required_files:
            if not os.path.exists(f):
                return JsonResponse(
                    {
                        "error": f"Artifact {os.path.basename(f)} not found for '{price_type}' model. Please train it first."
                    },
                    status=404,
                )

        # Load necessary artifacts
        evaluation_metrics = joblib.load(paths["evaluation_metrics_path"])
        df_transformed = joblib.load(paths["df_transformed_path"])
        cached_predictions = joblib.load(paths["cached_predictions_path"])
        eval_plot_line_data = joblib.load(paths["eval_plot_line_path"])

        # Determine prediction start date
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
            plot_title = f"Forecasted Sugar Prices (Mean, {price_type.capitalize()})"
        else:
            plot_title = (
                f"Forecasted Sugar Prices ({selected_province}, {price_type.capitalize()})"
            )

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

        # Encode evaluation plot to base64
        with open(paths["eval_plot_path"], "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        plot_base64 = f"data:image/png;base64,{encoded_string}"

        # Limit historical data for plotting
        if not df_predicted_for_plot.empty:
            prediction_start_date = df_predicted_for_plot["Date"].min()
            six_months_before = prediction_start_date - pd.DateOffset(months=6)
            df_historical_for_plot = df_historical_for_plot[
                df_historical_for_plot["Date"] >= six_months_before
            ].copy()

        # Generate Plotly data dynamically
        plotly_combined_plot_data = plot_combined_forecast(
            df_historical_for_plot, df_predicted_for_plot, title=plot_title
        )

        return JsonResponse(
            {
                "forecast_table": forecast_table_html,
                "plot": plot_base64,
                "evaluation_metrics": evaluation_metrics,
                "combined_plot_data": plotly_combined_plot_data,
                "eval_plot_line_data": eval_plot_line_data,
                "provinces": all_provinces,
                "selected_province": selected_province,
                "prediction_start_date": prediction_start_date.strftime("%Y-%m-%d"),
                "price_type": price_type,
            }
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"Failed to generate results: {str(e)}"}, status=500
        )

def prediction_table_view(request):
    """
    Generates and returns only the prediction table HTML based on
    the selected province and price_type.
    """
    selected_province = request.GET.get("province") or "All"
    price_type = request.GET.get("price_type") or "local"

    if price_type not in ["local", "premium"]:
        return JsonResponse(
            {"error": "Invalid 'price_type'. Must be 'local' or 'premium'."}, status=400
        )

    try:
        paths = get_model_paths(price_type)
        required_files = [
            paths["cached_predictions_path"],
            paths["df_transformed_path"],
        ]

        for f in required_files:
            if not os.path.exists(f):
                return JsonResponse(
                    {
                        "error": f"Artifact {os.path.basename(f)} not found for '{price_type}' model. Please train it first."
                    },
                    status=404,
                )

        # Load necessary artifacts
        cached_predictions = joblib.load(paths["cached_predictions_path"])
        df_transformed = joblib.load(paths["df_transformed_path"])

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
