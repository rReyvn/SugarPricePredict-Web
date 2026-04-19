import os
import pandas as pd
import joblib
from django.conf import settings
from django.utils import timezone
from .models import TrainingLock
from .pipeline import (
    clean_data,
    transform_data,
    train_model,
    merge_data,
    load_and_prepare_df,
    forecast_future_data,
    get_model_paths,
)


def train_on_all_datasets_task(price_type: str):
    """
    A Django Q task that finds all datasets for a given price type,
    cleans, merges, trains a model, and saves the artifacts.
    """
    try:
        print(f"Starting model training for price type: {price_type}...")
        paths = get_model_paths(price_type)
        upload_dir = os.path.join(settings.BASE_DIR, "rfr_model", "datasets", price_type)

        all_files = [
            os.path.join(upload_dir, f)
            for f in os.listdir(upload_dir)
            if f.endswith(".xlsx")
        ]

        if not all_files:
            print(f"No datasets found in {upload_dir} to train on.")
            return

        list_of_cleaned_dfs = []
        print(f"Found {len(all_files)} datasets. Cleaning...")
        for file_path in all_files:
            try:
                raw_df = load_and_prepare_df(file_path)
                cleaned_df = clean_data(raw_df)
                list_of_cleaned_dfs.append(cleaned_df)
            except Exception as e:
                print(
                    f"--> Skipping file {os.path.basename(file_path)} due to error: {e}"
                )

        if not list_of_cleaned_dfs:
            print("No valid datasets could be processed. Aborting training.")
            return

        # Merge all cleaned datasets
        print("Merging datasets...")
        merged_df = merge_data(list_of_cleaned_dfs)
        merged_df = merged_df.sort_values(by="Date").reset_index(drop=True)

        # Transform data (feature engineering)
        print("Running feature engineering...")
        df_transformed, province_mapping = transform_data(merged_df)

        # Train Model
        print("Training the model...")
        model, evaluation, plot, df_eval, line_plot_data = train_model(df_transformed)

        # Generate and save forecast results
        print("Generating forecast...")
        forecast_df = forecast_future_data(df_transformed, province_mapping, model)

        # Generate and cache predictions for each province
        print("Generating and caching predictions for each province...")
        all_provinces = sorted(df_transformed["Province"].unique().tolist())
        cached_predictions = {}

        # Individual provinces
        for province in all_provinces:
            df_hist = df_transformed[df_transformed["Province"] == province].copy()
            df_pred = forecast_df[forecast_df["Province"] == province].copy()
            cached_predictions[province] = {
                "historical": df_hist,
                "predicted": df_pred,
            }

        # Mean of all provinces
        df_hist_mean = df_transformed.groupby("Date")["Price"].mean().reset_index()
        df_pred_mean = forecast_df.groupby("Date")["Prediction"].mean().reset_index()
        cached_predictions["All"] = {
            "historical": df_hist_mean,
            "predicted": df_pred_mean,
        }

        # Save artifacts
        print("Saving model and artifacts...")
        joblib.dump(model, paths["model_path"])
        joblib.dump(province_mapping, paths["province_map_path"])
        joblib.dump(forecast_df, paths["forecast_results_path"])
        joblib.dump(evaluation, paths["evaluation_metrics_path"])
        joblib.dump(df_transformed, paths["df_transformed_path"])
        joblib.dump(cached_predictions, paths["cached_predictions_path"])
        joblib.dump(line_plot_data, paths["eval_plot_line_path"])
        plot.savefig(paths["eval_plot_path"])
        plot.close()

        # Save the timestamp
        with open(paths["last_training_timestamp_path"], "w") as f:
            f.write(timezone.now().isoformat())

        print("Model training completed successfully.")

    except Exception as e:
        print(f"An error occurred during model training: {e}")
        raise
    finally:
        # Always release the lock
        lock = TrainingLock.objects.get(pk=1)
        lock.is_locked = False
        lock.save()

