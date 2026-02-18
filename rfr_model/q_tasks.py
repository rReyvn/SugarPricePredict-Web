import os
import pandas as pd
import joblib
from django.conf import settings
from datetime import datetime
from .pipeline import clean_data, transform_data, train_model, merge_data, load_and_prepare_df


from .pipeline import (
    clean_data,
    transform_data,
    train_model,
    merge_data,
    load_and_prepare_df,
    forecast_future_data,
    MODEL_PATH,
    PROVINCE_MAP_PATH,
    EVAL_PLOT_PATH,
    LAST_TRAINING_TIMESTAMP_PATH,
    FORECAST_RESULTS_PATH,
)


def train_on_all_datasets_task():
    """
    A Django Q task that finds all datasets, cleans, merges,
    trains a model, and saves the artifacts.
    """
    try:
        print("Starting model training on all datasets...")
        upload_dir = os.path.join(settings.BASE_DIR, "datasets")
        
        all_files = [os.path.join(upload_dir, f) for f in os.listdir(upload_dir) if f.endswith('.xlsx')]
        
        if not all_files:
            print("No datasets found to train on.")
            return

        list_of_cleaned_dfs = []
        print(f"Found {len(all_files)} datasets. Cleaning...")
        for file_path in all_files:
            try:
                raw_df = load_and_prepare_df(file_path)
                cleaned_df = clean_data(raw_df)
                list_of_cleaned_dfs.append(cleaned_df)
            except Exception as e:
                print(f"--> Skipping file {os.path.basename(file_path)} due to error: {e}")

        if not list_of_cleaned_dfs:
            print("No valid datasets could be processed. Aborting training.")
            return
        
        # Merge all cleaned datasets
        print("Merging datasets...")
        merged_df = merge_data(list_of_cleaned_dfs)
        
        # Transform data (feature engineering)
        print("Running feature engineering...")
        df_transformed, province_mapping = transform_data(merged_df)

        # Train Model
        print("Training the model...")
        model, evaluation, plot = train_model(df_transformed)

        # Generate and save forecast results
        print("Generating forecast...")
        forecast_df = forecast_future_data(df_transformed, province_mapping, model)
        
        # Save artifacts
        print("Saving model and artifacts...")
        joblib.dump(model, MODEL_PATH)
        joblib.dump(province_mapping, PROVINCE_MAP_PATH)
        joblib.dump(forecast_df, FORECAST_RESULTS_PATH)
        plot.savefig(EVAL_PLOT_PATH)
        plot.close()
        
        # Save the timestamp
        with open(LAST_TRAINING_TIMESTAMP_PATH, 'w') as f:
            f.write(datetime.now().isoformat())

        print("Model training completed successfully.")
        
    except Exception as e:
        # In a real project, you'd have more robust logging here
        print(f"An error occurred during model training: {e}")
        # Optionally, re-raise the exception if you want Django Q to mark the task as failed
        raise
