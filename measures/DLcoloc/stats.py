import pandas as pd
import numpy as np
from scipy.stats import spearmanr, kendalltau, pearsonr
import warnings


pred_csv = 'f:/Sandbox/embl_project/colocalization/prediction/preds_mu.csv'


def conf_intervals(df, y_nm, y_pred_nm, fun, n=100):
    sample = []
    for _ in range(n):
        sample_df = df.sample(len(df), replace=True)
        corrs = []
        for g in sample_df.groupby(['datasetId', 'baseSf', 'baseAdduct']):
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                res = fun(g[1][y_nm], g[1][y_pred_nm])[0]
            if np.isnan(res):
                continue
            corrs.append(res)
        sample.append(np.array(corrs).mean())
    sample = np.array(sample)

    ci_lo = np.percentile(sample, 2.5)
    median = np.percentile(sample, 50)
    mean = np.mean(sample)
    st = np.std(sample)
    ci_hi = np.percentile(sample, 97.5)

    conf = f'mean={mean:0.3f}|median={median:0.3f}|std={st:0.3f} ({ci_lo:0.3f}-{ci_hi:0.3f}) (95% CI)'
    return conf


def accuracy_datasetwise(df, cols, fun=spearmanr):
    acc = []
    for g in df.groupby(['datasetId', 'baseSf', 'baseAdduct']):
        acc.append(fun(g[1][cols[0]], g[1][cols[1]])[0])
    acc = np.array(acc)
    return np.mean(acc), np.median(acc)


if __name__ == '__main__':
    df_preds = pd.read_csv(pred_csv)
    df_preds['pred'] = df_preds['pred'].apply(lambda x: np.round(x))

    mean, median = accuracy_datasetwise(df_preds, cols=['rank', 'pred'], fun=spearmanr)
    print(f'Spearman dataset-wise: mean {mean:0.3f}, median {median:0.3f}')
    mean, median = accuracy_datasetwise(df_preds, cols=['rank', 'pred'], fun=kendalltau)
    print(f'Kendalltau dataset-wise: mean {mean:0.3f}, median {median:0.3f}')

    print('_____________________\nConfidence intervals:')
    print('Spearman:', conf_intervals(df_preds, 'rank', 'pred', spearmanr, n=100))
    print('Kendalltau:', conf_intervals(df_preds, 'rank', 'pred', kendalltau, n=100))
