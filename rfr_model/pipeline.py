import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import root_mean_squared_error, mean_absolute_percentage_error
from hijridate import Hijri, Gregorian
import os
from django.conf import settings


def get_model_paths(price_type: str) -> dict:
    """
    Returns a dictionary of paths for model artifacts based on the price type.
    """
    if price_type not in ["local", "premium"]:
        raise ValueError("price_type must be either 'local' or 'premium'")

    model_dir = os.path.join(settings.BASE_DIR, "rfr_model", "output", price_type)
    os.makedirs(model_dir, exist_ok=True)

    return {
        "model_dir": model_dir,
        "model_path": os.path.join(model_dir, "rfr_model.joblib"),
        "province_map_path": os.path.join(model_dir, "province_mapping.joblib"),
        "eval_plot_path": os.path.join(model_dir, "evaluation_plot.png"),
        "last_training_timestamp_path": os.path.join(
            model_dir, "last_training_timestamp.txt"
        ),
        "forecast_results_path": os.path.join(model_dir, "forecast_results.joblib"),
        "combined_plot_path": os.path.join(model_dir, "combined_forecast_plot.png"),
        "evaluation_metrics_path": os.path.join(model_dir, "evaluation_metrics.joblib"),
        "df_transformed_path": os.path.join(model_dir, "df_transformed.joblib"),
        "cached_predictions_path": os.path.join(model_dir, "cached_predictions.joblib"),
        "eval_plot_line_path": os.path.join(model_dir, "eval_plot_line.joblib"),
    }


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
        # Drop "Semua Provinsi" and "Maluku Utara"
        df = df[~df["Province"].isin(["Semua Provinsi", "Maluku Utara"])]
        return df
    elif "Komoditas (Rp)" in df.columns:
        df = df.rename(columns={"Komoditas (Rp)": "Province"})
        # Drop "Semua Provinsi" and "Maluku Utara" data
        df = df[~df["Province"].isin(["Semua Provinsi", "Maluku Utara"])]
        return df
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
    for lag in [1]:
        df[f"lag_{lag}"] = df.groupby("Province", group_keys=False)["Price"].shift(lag)

    # 3) Time based features
    df["month"] = df["Date"].dt.month
    df["year"] = df["Date"].dt.year

    # Drop rows with no lag features
    df_transform = df.dropna(subset=["lag_1"]).reset_index(drop=True)

    return df_transform, province_mapping


def train_model(df_mining: pd.DataFrame, sugar_type: str):
    """
    Trains the Random Forest Regressor model and evaluates it.
    """
    if sugar_type == "local":
        RFR_PARAMS = dict(
            n_estimators=75,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features="sqrt",
            bootstrap=True,
            random_state=42,
            n_jobs=1,
        )
    elif sugar_type == "premium":
        RFR_PARAMS = dict(
            n_estimators=25,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features="log2",
            bootstrap=True,
            random_state=42,
            n_jobs=1,
        )
    train_size = 0.8
    val_size = 0.1
    
    FEATURE_COLS = [
        "Province_id",
        "lag_1",
        "month",
        "year",
    ]
    TARGET_COL = "Price"

    # Specify X for features and y for target
    X = df_mining.drop(columns=[TARGET_COL])
    y = df_mining[TARGET_COL]

    # Time-based train-val-test split
    train_index = int(len(df_mining) * train_size)
    val_index = int(len(df_mining) * (train_size + val_size))

    X_train = X.iloc[:train_index]
    y_train = y.iloc[:train_index]

    X_val = X.iloc[train_index:val_index]
    y_val = y.iloc[train_index:val_index]

    X_test = X.iloc[val_index:]
    y_test = y.iloc[val_index:]

    model = RandomForestRegressor(**RFR_PARAMS)
    model.fit(X_train[FEATURE_COLS], y_train)

    # Predict on the training set
    y_train_pred = model.predict(X_train[FEATURE_COLS])
    overall_train_rmse = root_mean_squared_error(y_train, y_train_pred)
    overall_train_mape = mean_absolute_percentage_error(y_train, y_train_pred) * 100
    df_train_eval = pd.DataFrame(
        {
            "Province": X_train["Province"],
            "Actual": y_train,
            "Predicted": y_train_pred,
        }
    )

    # Predict on the test set
    y_pred = model.predict(X_test[FEATURE_COLS])

    # Overall Evaluation Metrics
    overall_rmse = root_mean_squared_error(y_test, y_pred)
    overall_mape = mean_absolute_percentage_error(y_test, y_pred) * 100

    # Validation metrics — only computed when val_size > 0
    if val_size > 0.0 and not X_val.empty:
        y_val_pred = model.predict(X_val[FEATURE_COLS])
        overall_val_rmse = root_mean_squared_error(y_val, y_val_pred)
        overall_val_mape = mean_absolute_percentage_error(y_val, y_val_pred) * 100
        df_val_eval = pd.DataFrame(
            {
                "Province": X_val["Province"],
                "Actual": y_val,
                "Predicted": y_val_pred,
            }
        )
    else:
        overall_val_rmse = 0.0
        overall_val_mape = 0.0
        df_val_eval = pd.DataFrame(columns=["Province", "Actual", "Predicted"])

    df_eval = pd.DataFrame(
        {
            "Date": X_test["Date"],
            "Province": X_test["Province"],
            "Actual": y_test,
            "Predicted": y_pred,
        }
    )

    per_province_metrics = {}
    for province in df_eval["Province"].unique():
        province_df = df_eval[df_eval["Province"] == province]
        rmse = root_mean_squared_error(province_df["Actual"], province_df["Predicted"])
        mape = (
            mean_absolute_percentage_error(
                province_df["Actual"], province_df["Predicted"]
            )
            * 100
        )
        
        province_val_df = df_val_eval[df_val_eval["Province"] == province]
        if not province_val_df.empty:
            val_rmse = root_mean_squared_error(province_val_df["Actual"], province_val_df["Predicted"])
            val_mape = mean_absolute_percentage_error(province_val_df["Actual"], province_val_df["Predicted"]) * 100
        else:
            val_rmse = 0.0
            val_mape = 0.0

        province_train_df = df_train_eval[df_train_eval["Province"] == province]
        if not province_train_df.empty:
            train_rmse = root_mean_squared_error(province_train_df["Actual"], province_train_df["Predicted"])
            train_mape = mean_absolute_percentage_error(province_train_df["Actual"], province_train_df["Predicted"]) * 100
        else:
            train_rmse = 0.0
            train_mape = 0.0
            
        per_province_metrics[province] = {
            "RMSE": rmse, "MAPE": mape, 
            "Val_RMSE": val_rmse, "Val_MAPE": val_mape,
            "Train_RMSE": train_rmse, "Train_MAPE": train_mape
        }

    # Prepare results for presentation
    evaluation_metrics = {
        "overall": {
            "RMSE": overall_rmse, "MAPE": overall_mape,
            "Val_RMSE": overall_val_rmse, "Val_MAPE": overall_val_mape,
            "Train_RMSE": overall_train_rmse, "Train_MAPE": overall_train_mape
        },
        "by_province": per_province_metrics,
        "split_ratio": {"train": train_size, "val": val_size, "test": 1.0 - train_size - val_size}
    }

    # The plot is no longer returned as we only want the line plot

    # Generate line plot data
    line_plot_data = plot_actual_vs_prediction_line(
        df_eval,
        sugar_type,
    )

    return model, evaluation_metrics, df_eval, line_plot_data


def plot_actual_vs_prediction_line(
    df_eval, sugar_type: str, title="Comparison Between Actual and Predicted Prices"
):
    """
    Prepares comparison between actual and predicted prices for client-side plotting with Plotly.
    """
    traces = []

    # Group by province to create a trace for each
    for province, group in df_eval.groupby("Province"):
        # Actual data trace
        traces.append(
            {
                "x": group["Date"].dt.strftime("%Y-%m-%d").tolist(),
                "y": group["Actual"].tolist(),
                "mode": "lines",
                "name": f"{province} - Actual",
                "line": {"color": "blue"},
                "visible": "legendonly",  # Initially hidden
            }
        )

        # Predicted data trace
        traces.append(
            {
                "x": group["Date"].dt.strftime("%Y-%m-%d").tolist(),
                "y": group["Predicted"].tolist(),
                "mode": "lines",
                "name": f"{province} - Predicted",
                "line": {"dash": "dash", "color": "red"},
                "visible": "legendonly",  # Initially hidden
            }
        )

    # Add traces for the mean of all provinces
    df_mean = df_eval.groupby("Date").mean(numeric_only=True).reset_index()
    traces.append(
        {
            "x": df_mean["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "y": df_mean["Actual"].tolist(),
            "mode": "lines",
            "name": "Mean - Actual",
            "line": {"color": "darkblue", "width": 3},
            "visible": True,  # Initially visible
        }
    )
    traces.append(
        {
            "x": df_mean["Date"].dt.strftime("%Y-%m-%d").tolist(),
            "y": df_mean["Predicted"].tolist(),
            "mode": "lines",
            "name": "Mean - Predicted",
            "line": {"dash": "dash", "color": "darkred", "width": 3},
            "visible": True,  # Initially visible
        }
    )

    layout = {
        "title": {
            "text": f"{title} - {sugar_type.capitalize()}",
            "y": 0.95,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
        },
        "xaxis": {"title": {"text": "Date", "standoff": 10}},
        "yaxis": {"title": {"text": "Price", "standoff": 10}},
        "hovermode": "x unified",
        "legend": {"traceorder": "normal"},
        "margin": {"t": 50},
    }

    return {"data": traces, "layout": layout}


def forecast_future_data(
    df_transform: pd.DataFrame,
    province_mapping: dict,
    model: RandomForestRegressor,
    selected_province: str = None,  # Added parameter
):
    """
    Forecasts future sugar prices for a given horizon using a trained model.
    """

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

        for i in range(1, 180 + 1):
            next_date = last_date + pd.Timedelta(days=i)

            month = next_date.month
            year = next_date.year

            lag_1 = last_rows.iloc[-1]["Price"]

            X_future = pd.DataFrame(
                {
                    "Province_id": [prov_id],
                    "lag_1": [lag_1],
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
    title: str = "Forecasted Sugar Prices",
):
    """
    Prepares historical and forecasted sugar prices data for client-side plotting with Plotly.
    Returns a dictionary with 'data' and 'layout' suitable for Plotly.js.
    """
    traces = []

    # Sort historical data to ensure chronological plotting
    df_historical = df_historical.sort_values("Date")

    # Historical data trace
    if (
        "Province" in df_historical.columns
        and len(df_historical["Province"].unique()) > 1
    ):
        # Plotting individual provinces
        for province in df_historical["Province"].unique():
            hist_data = df_historical[df_historical["Province"] == province]
            traces.append(
                {
                    "x": hist_data["Date"].dt.strftime("%Y-%m-%d").tolist(),
                    "y": hist_data["Price"].tolist(),
                    "mode": "lines",
                    "name": f"{province} Historical",
                    "line": {"color": "blue"},
                }
            )
    else:
        # Plotting mean or a single province
        traces.append(
            {
                "x": df_historical["Date"].dt.strftime("%Y-%m-%d").tolist(),
                "y": df_historical["Price"].tolist(),
                "mode": "lines",
                "name": "Historical",
                "line": {"color": "blue"},
            }
        )

    # Sort predicted data to ensure chronological plotting
    df_predicted = df_predicted.sort_values("Date")

    # Predicted data trace
    if (
        "Province" in df_predicted.columns
        and len(df_predicted["Province"].unique()) > 1
    ):
        # Plotting individual provinces
        for province in df_predicted["Province"].unique():
            pred_data = df_predicted[df_predicted["Province"] == province]
            traces.append(
                {
                    "x": pred_data["Date"].dt.strftime("%Y-%m-%d").tolist(),
                    "y": pred_data["Prediction"].tolist(),
                    "mode": "lines",
                    "name": f"{province} Forecast",
                    "line": {"dash": "dash", "color": "red"},
                }
            )
    else:
        # Plotting mean or a single province
        traces.append(
            {
                "x": df_predicted["Date"].dt.strftime("%Y-%m-%d").tolist(),
                "y": df_predicted["Prediction"].tolist(),
                "mode": "lines",
                "name": "Forecast",
                "line": {"dash": "dash", "color": "red"},
            }
        )

    layout = {
        "title": {
            "text": title,
            "y": 0.95,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
        },
        "xaxis": {
            "title": {
                "text": "Date",
                "standoff": 10,
            }
        },
        "yaxis": {
            "title": {
                "text": "Price",
                "standoff": 10,
            }
        },
        "hovermode": "x unified",
        "margin": {"t": 50},
    }

    return {"data": traces, "layout": layout}
