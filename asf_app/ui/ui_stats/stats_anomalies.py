# asf_app/ui/ui_stats/stats_anomalies.py
# -*- coding: utf-8 -*-



def detect_outliers_zscore(series, threshold=3):
    if series.empty:
        return []
    z = (series - series.mean()) / series.std(ddof=0)
    return series[z.abs() > threshold]


def detect_anomalies(df):
    anomalies = {}

    # BE avec nb_colis anormal
    if "nb_colis" in df:
        out = detect_outliers_zscore(df["nb_colis"])
        if not out.empty:
            anomalies["colis_outliers"] = df.loc[out.index]

    # Destinations anormales
    dest_counts = df["destination_iata"].value_counts()
    out_dest = detect_outliers_zscore(dest_counts)
    if not out_dest.empty:
        anomalies["destinations_anormales"] = out_dest

    # Expéditeurs anormaux
    exp_counts = df["expediteur"].value_counts()
    out_exp = detect_outliers_zscore(exp_counts)
    if not out_exp.empty:
        anomalies["expediteurs_anormaux"] = out_exp

    return anomalies
