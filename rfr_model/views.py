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
)


@csrf_exempt
@require_POST
def start_training_view(request):
    """
    Starts the model training task for all datasets.
    """
    try:
        # The task now finds all datasets by itself.
        async_task("rfr_model.q_tasks.train_on_all_datasets_task")
        return JsonResponse(
            {"message": "Model training started in the background."}, status=202
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def prediction_results_view(request):
    """
    Loads the pre-computed forecast and evaluation plot and returns them.
    """
    required_files = [FORECAST_RESULTS_PATH, EVAL_PLOT_PATH]
    for f in required_files:
        if not os.path.exists(f):
            return JsonResponse(
                {
                    "error": f"Artifact {os.path.basename(f)} not found. Please train a model first."
                },
                status=404,
            )

    try:
        # Load the pre-computed forecast DataFrame
        forecast_df = joblib.load(FORECAST_RESULTS_PATH)

        # Format 'Date' column to 'd-m-Y'
        forecast_df["Date"] = forecast_df["Date"].dt.strftime("%d-%m-%Y")

        # Prepare forecast table
        forecast_table_html = forecast_df.to_html(
            classes="min-w-full divide-y divide-gray-200", border=0, index=False
        )
        # Manually add classes to th and td for alignment and spacing
        forecast_table_html = forecast_table_html.replace('<th>', '<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">')
        forecast_table_html = forecast_table_html.replace('<td>', '<td class="px-6 py-4 whitespace-nowrap text-left">')

        # Encode plot to base64
        with open(EVAL_PLOT_PATH, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()

        plot_base64 = f"data:image/png;base64,{encoded_string}"

        return JsonResponse(
            {"forecast_table": forecast_table_html, "plot": plot_base64}
        )
    except Exception as e:
        return JsonResponse({"error": f"Failed to generate results: {str(e)}"}, status=500)

