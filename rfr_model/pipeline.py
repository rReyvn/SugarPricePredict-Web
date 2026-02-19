import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import root_mean_squared_error, mean_absolute_percentage_error
from sklearn import tree
from hijridate import Hijri, Gregorian
from pathlib import Path
import os
from django.conf import settings

# Define paths for model artifacts
MODEL_DIR = os.path.join(settings.BASE_DIR, "rfr", "output", "model")
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "rfr_model.joblib")
PROVINCE_MAP_PATH = os.path.join(MODEL_DIR, "province_mapping.joblib")
EVAL_PLOT_PATH = os.path.join(MODEL_DIR, "evaluation_plot.png")
LAST_TRAINING_TIMESTAMP_PATH = os.path.join(MODEL_DIR, "last_training_timestamp.txt")
FORECAST_RESULTS_PATH = os.path.join(MODEL_DIR, "forecast_results.joblib")
COMBINED_PLOT_PATH = os.path.join(MODEL_DIR, "combined_forecast_plot.png")
EVALUATION_METRICS_PATH = os.path.join(MODEL_DIR, "evaluation_metrics.joblib")
DF_TRANSFORMED_PATH = os.path.join(MODEL_DIR, "df_transformed.joblib")


def load_and_prepare_df(file_path):
    """
    Loads an Excel file and prepares it for cleaning by ensuring
    it has a 'Province' column.
    """
    df = pd.read_excel(file_path)

    # Safely drop "No" column if it exists
    if "No" in df.columns:
        df = df.drop(columns=["No"])

    # Check for "Province" or "Komoditas (Rp)"
    if "Province" in df.columns:
        return df
    elif "Komoditas (Rp)" in df.columns:
        return df.rename(columns={"Komoditas (Rp)": "Province"})
    else:
        raise ValueError(
            f"File '{os.path.basename(file_path)}' is missing a 'Province' or 'Komoditas (Rp)' column."
        )


def clean_data(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the raw dataset by melting, cleaning dates, cleaning prices,
    and filling missing values.
    """
    # Select Date columns
    date_cols = [c for c in df_raw.columns if c not in ["Province"]]

    # Change dataset format from wide to long
    df_long = df_raw.melt(
        id_vars=["Province"],
        value_vars=date_cols,
        var_name="Date",
        value_name="Price",
    )

    # Clean date column
    df_long["Date"] = pd.to_datetime(
        df_long["Date"].str.replace(" ", "").str.strip(),
        format="%d/%m/%Y",
        errors="coerce",
    )

    # Clean price column
    df_long["Price"] = (
        df_long["Price"]
        .astype(str)
        .str.strip()
        .replace("-", np.nan)
        .str.replace(",", "", regex=False)
    )
    df_long["Price"] = pd.to_numeric(df_long["Price"], errors="coerce")

    # Forward/Backward Fill Based on Each Province
    df_long = (
        df_long.groupby("Province", sort=False, group_keys=False)[
            ["Date", "Price", "Province"]
        ]
        .apply(
            lambda g: (
                g.set_index("Date")
                .reindex(
                    pd.date_range(
                        start=g["Date"].min(),
                        end=g["Date"].max(),
                        freq="D",
                    )
                )
                .assign(Province=lambda x: x["Province"].ffill().bfill())
                .assign(Price=lambda x: x["Price"].ffill().bfill())
                .rename_axis("Date")
                .reset_index()
            )
        )
        .reset_index(drop=True)
    )

    # Sort by date and province
    df_long = df_long.sort_values(["Date", "Province"]).reset_index(drop=True)
    df_long["Price"] = df_long["Price"].round().astype(int)

    return df_long


def merge_data(list_of_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Merges a list of cleaned DataFrames into a single DataFrame.
    """
    if not list_of_dfs:
        return pd.DataFrame()

    # Merge all dataframes
    df_merged = pd.concat(list_of_dfs, ignore_index=True)

    # Sort and drop duplicate each province and date, keeping the last entry
    df_merged = df_merged.drop_duplicates(
        subset=["Province", "Date"], keep="last"
    ).reset_index(drop=True)

    return df_merged


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers features for the model, including province IDs, lag features,
    and holiday features.
    """

    # Helper functions for holiday features
    def eid_delta_days(ts: pd.Timestamp) -> int:
        g = Gregorian(ts.year, ts.month, ts.day)
        h = g.to_hijri()
        eid_h = Hijri(h.year, 10, 1)  # 1 Syawal
        eid_g = eid_h.to_gregorian()
        eid_date = pd.Timestamp(eid_g.year, eid_g.month, eid_g.day)
        return (ts.normalize() - eid_date).days

    def eid_flags(ts: pd.Timestamp):
        d = eid_delta_days(ts)
        before = 1 if -7 <= d <= -1 else 0
        day = 1 if d == 0 else 0
        after = 1 if 1 <= d <= 6 else 0
        return pd.Series([before, day, after], index=["before_eid", "eid", "after_eid"])

    # Data type normalization
    df["Date"] = pd.to_datetime(df["Date"])
    df["Province"] = df["Province"].astype("string")
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    # Feature Engineering
    # 1) Province -> numeric (ID)
    province_mean_prices = df.groupby("Province")["Price"].mean().sort_values()
    province_mapping = {
        province: i for i, province in enumerate(province_mean_prices.index)
    }
    df["Province_id"] = df["Province"].map(province_mapping)

    # 2) Lag features
    for lag in [1, 14]:
        df[f"lag_{lag}"] = df.groupby("Province", group_keys=False)["Price"].shift(lag)

    # 3) Moving holiday features
    df[["before_eid", "eid", "after_eid"]] = df["Date"].apply(eid_flags)

    # 4) Time based features
    df["month"] = df["Date"].dt.month
    df["year"] = df["Date"].dt.year

    # Drop rows with no lag features
    df_transform = df.dropna(subset=["lag_1", "lag_14"]).reset_index(drop=True)

    return df_transform, province_mapping


def train_model(df_mining: pd.DataFrame):
    """
    Trains the Random Forest Regressor model and evaluates it.
    """
    RFR_PARAMS = dict(
        n_estimators=60,
        max_depth=None,
        min_samples_split=20,
        min_samples_leaf=5,
        max_features="sqrt",
        bootstrap=True,
        random_state=42,
        n_jobs=1,
    )
    train_size = 0.9
    FEATURE_COLS = [
        "Province_id",
        "lag_1",
        "lag_14",
        "before_eid",
        "eid",
        "after_eid",
        "month",
        "year",
    ]
    TARGET_COL = "Price"

    # Specify X for features and y for target
    X = df_mining[FEATURE_COLS]
    y = df_mining[TARGET_COL]

    # Time-based train-test split
    split_index = int(len(df_mining) * train_size)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    model = RandomForestRegressor(**RFR_PARAMS)
    model.fit(X_train, y_train)

    # Predict
    y_pred = model.predict(X_test)

    # Evaluation Metrics
    rmse = root_mean_squared_error(y_test, y_pred)
    mape = mean_absolute_percentage_error(y_test, y_pred) * 100

    # Prepare results for presentation
    evaluation = {"RMSE": rmse, "MAPE": mape}

    # Create scatter plot for visualization
    plt.figure(figsize=(5, 5))
    plt.scatter(y_test, y_pred, alpha=0.6)
    max_val = max(y_test.max(), y_pred.max())
    min_val = min(y_test.min(), y_pred.min())
    plt.plot([min_val, max_val], [min_val, max_val], "r--", linewidth=2)
    plt.title("Actual vs Prediction")
    plt.xlabel("Actual")
    plt.ylabel("Prediction")
    plt.tight_layout()

    # The plot is returned to be handled by the view (e.g., save to buffer)
    plot = plt

    return model, evaluation, plot


def forecast_future_data(
    df_transform: pd.DataFrame,
    province_mapping: dict,
    model: RandomForestRegressor,
    horizon: int = 180,
    selected_province: str = None, # Added parameter
):
    """
    Forecasts future sugar prices for a given horizon using a trained model.
    """

    # Helper functions for holiday features
    def eid_delta_days(ts: pd.Timestamp) -> int:
        g = Gregorian(ts.year, ts.month, ts.day)
        h = g.to_hijri()
        eid_h = Hijri(h.year, 10, 1)
        eid_g = eid_h.to_gregorian()
        eid_date = pd.Timestamp(eid_g.year, eid_g.month, eid_g.day)
        return (ts.normalize() - eid_date).days

    forecast_results = []
    
    # Filter provinces if selected_province is provided
    if selected_province:
        provinces = [selected_province]
    else:
        provinces = df_transform["Province"].unique()

    # The notebook trains a new model here. We will use the one passed as a parameter.
    # Re-fitting the model on the full dataset before forecasting
    FEATURE_COLS = [
        "Province_id",
        "lag_1",
        "lag_14",
        "before_eid",
        "eid",
        "after_eid",
        "month",
        "year",
    ]
    TARGET_COL = "Price"
    X_full = df_transform[FEATURE_COLS]
    y_full = df_transform[TARGET_COL]
    model.fit(X_full, y_full)

    for prov in provinces:
        g = df_transform[df_transform["Province"] == prov].copy()
        g = g.sort_values("Date").reset_index(drop=True)

        last_date = g["Date"].max()
        last_rows = g.tail(30).copy()

        prov_id = province_mapping[prov]

        for i in range(1, horizon + 1):
            next_date = last_date + pd.Timedelta(days=i)

            month = next_date.month
            year = next_date.year

            lag_1 = last_rows.iloc[-1]["Price"]
            lag_14 = last_rows.iloc[-14]["Price"] if len(last_rows) >= 14 else lag_1

            d = eid_delta_days(next_date)
            before_eid = 1 if -7 <= d <= -1 else 0
            eid_day = 1 if d == 0 else 0
            after_eid = 1 if 1 <= d <= 6 else 0

            X_future = pd.DataFrame(
                {
                    "Province_id": [prov_id],
                    "lag_1": [lag_1],
                    "lag_14": [lag_14],
                    "before_eid": [before_eid],
                    "eid": [eid_day],
                    "after_eid": [after_eid],
                    "month": [month],
                    "year": [year],
                }
            )

            predicted_price = model.predict(X_future)[0]

            forecast_results.append(
                {
                    "Date": next_date,
                    "Province": prov,
                    "Prediction": round(predicted_price),
                }
            )

            new_row = pd.DataFrame(
                [
                    {
                        "Date": next_date,
                        "Price": predicted_price,
                        "Province": prov,
                        "Province_id": prov_id,
                    }
                ]
            )
            last_rows = pd.concat([last_rows, new_row], ignore_index=True)

    df_forecast = pd.DataFrame(forecast_results)
    df_forecast = df_forecast.sort_values(["Province", "Date"]).reset_index(drop=True)
    return df_forecast


def plot_combined_forecast(
    df_historical: pd.DataFrame,
    df_predicted: pd.DataFrame,
    title: str = "Historical and Forecasted Sugar Prices",
):
    """
    Prepares historical and forecasted sugar prices data for client-side plotting with Plotly.
    Returns a dictionary with 'data' and 'layout' suitable for Plotly.js.
    """
    traces = []

    # Historical data trace
    if "Province" in df_historical.columns and len(df_historical["Province"].unique()) > 1:
        # Plotting individual provinces
        for province in df_historical["Province"].unique():
            hist_data = df_historical[df_historical["Province"] == province]
            traces.append({
                'x': hist_data["Date"].dt.strftime('%Y-%m-%d').tolist(),
                'y': hist_data["Price"].tolist(),
                'mode': 'lines',
                'name': f"{province} Historical",
                'line': {'color': 'blue'}
            })
    else:
        # Plotting mean or a single province
        traces.append({
            'x': df_historical["Date"].dt.strftime('%Y-%m-%d').tolist(),
            'y': df_historical["Price"].tolist(),
            'mode': 'lines',
            'name': "Historical",
            'line': {'color': 'blue'}
        })
    
    # Predicted data trace
    if "Province" in df_predicted.columns and len(df_predicted["Province"].unique()) > 1:
        # Plotting individual provinces
        for province in df_predicted["Province"].unique():
            pred_data = df_predicted[df_predicted["Province"] == province]
            traces.append({
                'x': pred_data["Date"].dt.strftime('%Y-%m-%d').tolist(),
                'y': pred_data["Prediction"].tolist(),
                'mode': 'lines',
                'name': f"{province} Forecast",
                'line': {'dash': 'dash', 'color': 'red'}
            })
    else:
        # Plotting mean or a single province
        traces.append({
            'x': df_predicted["Date"].dt.strftime('%Y-%m-%d').tolist(),
            'y': df_predicted["Prediction"].tolist(),
            'mode': 'lines',
            'name': "Forecast",
            'line': {'dash': 'dash', 'color': 'red'}
        })

    layout = {
        'title': title,
        'xaxis': {'title': 'Date'},
        'yaxis': {'title': 'Price'},
        'hovermode': 'x unified'
    }

    return {'data': traces, 'layout': layout}

