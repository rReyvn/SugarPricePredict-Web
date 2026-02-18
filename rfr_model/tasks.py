import os
import pandas as pd
import joblib
from celery import shared_task
from django.conf import settings
from .pipeline import clean_data, transform_data, train_model, load_and_prepare_df

MODEL_DIR = os.path.join(settings.BASE_DIR, "rfr", "output", "model")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "rfr_model.joblib")
PROVINCE_MAP_PATH = os.path.join(MODEL_DIR, "province_mapping.joblib")
EVAL_PLOT_PATH = os.path.join(MODEL_DIR, "evaluation_plot.png")
LAST_DATASET_PATH = os.path.join(MODEL_DIR, "last_trained_dataset.txt")


@shared_task(bind=True)
def train_rfr_model_task(self, file_path):
    """
    Celery task to train the Random Forest Regression model.
    It cleans, transforms, trains, and saves the model while reporting progress.
    """
    try:
        # 1. Update state: Starting
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100, 'step': 'Starting...'})

        # 2. Load and Clean Data
        self.update_state(state='PROGRESS', meta={'current': 10, 'total': 100, 'step': 'Loading and cleaning data...'})
        df_raw = pd.read_excel(file_path)
        df_prepared = load_and_prepare_df(df_raw)
        df_clean = clean_data(df_prepared)
        
        # 3. Transform Data (Feature Engineering)
        self.update_state(state='PROGRESS', meta={'current': 40, 'total': 100, 'step': 'Running feature engineering...'})
        df_transformed, province_mapping = transform_data(df_clean)

        # 4. Train Model
        self.update_state(state='PROGRESS', meta={'current': 70, 'total': 100, 'step': 'Training the model...'})
        model, evaluation, plot = train_model(df_transformed)
        
        # 5. Save the trained model, province mapping, plot, and dataset path
        self.update_state(state='PROGRESS', meta={'current': 90, 'total': 100, 'step': 'Saving artifacts...'})
        joblib.dump(model, MODEL_PATH)
        joblib.dump(province_mapping, PROVINCE_MAP_PATH)
        plot.savefig(EVAL_PLOT_PATH)
        plot.close() # Close the plot to free up memory
        
        with open(LAST_DATASET_PATH, 'w') as f:
            f.write(file_path)

        # 6. Final state
        self.update_state(state='SUCCESS', meta={'current': 100, 'total': 100, 'step': 'Completed!'})
        
        return {'status': 'Task Completed!', 'evaluation': evaluation}

    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        # You might want to log the full traceback as well
        # import traceback
        # traceback.print_exc()
        return {'status': 'Task Failed', 'error': str(e)}
